"""Predições fora da dobra (OOF) do M1 e dos baselines, na mesma validação leave-one-region-out.

O M1 usa exatamente o mesmo procedimento de `modelos.cv_oof` (mesmos parâmetros, semente,
parada antecipada e dobras); aqui o laço é repetido só para guardar, por dobra, o que a Etapa
3.2 precisa registrar (número de árvores, parâmetros reais do estimador, convergência). Um teste
confere que as predições coincidem com as de `cv_oof`.

O conglomerado (município) entra só como coluna de identificação do resultado; nenhum modelo o vê.
As predições individuais ficam em armazenamento local ignorado pelo Git, nunca em `reports/`.
"""

from pathlib import Path

import numpy as np
import pandas as pd

from dengue_sinan.folds import ORDEM_REGIOES, dobras_loro
from dengue_sinan.guard import anos_marcados, marcar_anos, verificar_dev
from dengue_sinan.modelos import ModeloM1, calibrar_cruzado
from dengue_sinan.pipeline.baselines import (
    VARIAVEIS_B1,
    VARIAVEIS_B1_IDADE,
    BaselineLogistico,
    previsao_b0,
)
from dengue_sinan.pipeline.preprocessamento import normalizar_x
from dengue_sinan.pipeline.treino import ConfigTreino

MODELOS = ("m1", "m1_cal_naoaninhado", "b0", "b1", "b1_idade")
COLUNAS_P = {m: f"p_{m}" for m in MODELOS}
ROTULOS = {
    "m1": "M1 2.0.0 (sem calibrar)",
    "m1_cal_naoaninhado": "M1 2.0.0 (calibrado, não aninhado)",
    "b0": "B0 (prevalência do treino)",
    "b1": "B1 (idade, sexo, gestante)",
    "b1_idade": "B1-idade",
}
PARAMETROS_XGB_REGISTRADOS = ("device", "tree_method", "eval_metric", "n_jobs", "random_state")


def verificar_dobras(regiao: pd.Series) -> list[dict]:
    """Confere o desenho LORO e devolve um resumo por dobra. Falha se houver sobreposição."""
    reg = regiao.astype("string").to_numpy(dtype=object, na_value=None)
    resumo = []
    for r, tr, te in dobras_loro(regiao):
        if np.intersect1d(tr, te).size:
            raise AssertionError(f"dobra {r}: treino e teste se sobrepõem")
        if (reg[te] != r).any() or (reg[tr] == r).any():
            raise AssertionError(f"dobra {r}: região de teste presente no treino")
        resumo.append({"regiao": r, "n_treino": int(len(tr)), "n_teste": int(len(te))})
    return resumo


def gerar_oof(x, y, regiao, meta, cfg: ConfigTreino, conglomerado, incluir_calibrado=True):
    """Devolve (tabela OOF por linha, informações por dobra). Uma predição por linha e modelo."""
    verificar_dev(x, regiao, meta=meta, contexto="oof.gerar_oof")  # R1
    resumo = verificar_dobras(regiao)
    x = normalizar_x(x, cfg.variaveis)
    marcar_anos(x, anos_marcados(x, regiao) or pd.unique(meta["ANO"]))
    y = np.asarray(y)
    n = len(y)
    p = {m: np.full(n, np.nan) for m in MODELOS}
    fold_id = np.full(n, -1)
    dobras = []
    kw = {
        "paciencia": cfg.paciencia,
        "val_frac": cfg.val_frac,
        "max_iter": cfg.max_iter,
        "n_jobs": cfg.n_jobs,
    }
    for k, (_, tr, te) in enumerate(dobras_loro(regiao), start=1):
        fold_id[te] = k
        m1 = ModeloM1(cfg.algoritmo, cfg.params, cfg.seed, **kw).ajustar(x.iloc[tr], y[tr])
        p["m1"][te] = m1.prever(x.iloc[te])
        p["b0"][te] = previsao_b0(y[tr])
        info = {
            "dobra": k,
            **resumo[k - 1],
            "eventos_treino": int(y[tr].sum()),
            "eventos_teste": int(y[te].sum()),
            "melhor_iteracao_m1": int(m1.melhor_),
            "parametros_estimador": {
                q: _nativo(m1.motor_.get_params().get(q)) for q in PARAMETROS_XGB_REGISTRADOS
            },
        }
        for nome, vars_ in (("b1", VARIAVEIS_B1), ("b1_idade", VARIAVEIS_B1_IDADE)):
            b = BaselineLogistico(vars_).ajustar(x.iloc[tr], y[tr])
            p[nome][te] = b.prever(x.iloc[te])
            info[nome] = {
                "variaveis": b.colunas_usadas(),
                "convergiu": b.convergencia.convergiu,
                "n_iter": b.convergencia.n_iter,
                "avisos": b.convergencia.avisos,
            }
        dobras.append(info)
    if incluir_calibrado:  # método herdado da Etapa 2; NÃO é calibração aninhada (ver 3.1)
        p["m1_cal_naoaninhado"] = calibrar_cruzado(p["m1"], y, regiao, cfg.calibrador, meta=meta)
    tabela = pd.DataFrame(
        {
            "fold": fold_id,
            "regiao": regiao.astype("string").to_numpy(),
            "ANO": np.asarray(meta["ANO"]),
            "conglomerado": np.asarray(conglomerado),
            "y": y,
        }
        | {COLUNAS_P[m]: p[m] for m in MODELOS if incluir_calibrado or m != "m1_cal_naoaninhado"}
    )
    elegivel = tabela["fold"] > 0  # linhas sem região não entram em nenhum teste
    tabela = tabela.loc[elegivel].reset_index(drop=True)
    colunas_p = [c for c in tabela.columns if c.startswith("p_")]
    if tabela[colunas_p].isna().any().any():
        raise AssertionError("há linhas elegíveis sem predição de algum modelo")
    return tabela, {
        "dobras": dobras,
        "linhas_sem_regiao_excluidas": int((~elegivel).sum()),
        "ordem_regioes": [r for r in ORDEM_REGIOES if r in set(regiao.dropna())],
    }


def _nativo(v):
    return v.item() if hasattr(v, "item") else v


def salvar_oof_local(
    tabela: pd.DataFrame, pasta: Path, nome: str = "oof_predicoes.parquet"
) -> Path:
    """Grava as predições individuais SÓ em armazenamento local. Recusa `reports/`."""
    pasta = Path(pasta).resolve()
    if "reports" in {p.lower() for p in pasta.parts}:
        raise PermissionError(f"recusado: predições individuais não vão para reports/ ({pasta})")
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / nome
    tabela.to_parquet(caminho, index=False)
    return caminho
