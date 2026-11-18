"""Etapa 1B — análises EXPLORATÓRIAS J2 a J6 (só 2022–2023, sem validação temporal independente).

Regras desta etapa (Estratégia A):
- só 2022 e 2023; o carregador recusa 2024 (R1);
- o modelo v1 congelado e `reports/modelo_risco_dengue/` não são tocados;
- toda saída vai para `reports/etapa1/<experimento>/` e é marcada como EXPLORATÓRIA;
- tabelas com contagens < 10 são suprimidas (R7).

Este módulo só contém funções. Os scripts `reports/etapa1/*/executar.py` as chamam.
Nenhum resultado numérico é escrito à mão: tudo sai do cálculo sobre os dados.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from dengue_sinan import explain as E
from dengue_sinan import modelos as MD
from dengue_sinan.dataset import (
    ACHADOS,
    SINTOMAS,
    empilhar_populacoes,
    montar_features,
    montar_populacao,
)
from dengue_sinan.guard import ANO_TESTE, ANOS_DEV, marcar_anos, verificar_dev
from dengue_sinan.metrics import (
    agregar,
    bootstrap_metricas,
    brier,
    calibracao_resumo,
    ic95,
    melhor_limiar_f2,
    metricas_limiar,
    pr_auc,
    roc_auc,
)
from dengue_sinan.profiling import (
    COMORBIDADES,
    code,
    parse_date,
    population_mask,
    target,
)

AVISO_EXPLORATORIO = (
    "EXPLORATÓRIO: calculado só com 2022–2023, sem validação temporal independente "
    "(o teste de 2024 já foi consultado na versão 1 e não é usado aqui)."
)
MIN_CELULA = 10  # R7

COLUNAS_J2 = [
    "CLASSI_FIN",
    "EVOLUCAO",
    "NU_IDADE_N",
    "ANO_NASC",
    "DT_SIN_PRI",
    "DT_NOTIFIC",
    "CS_SEXO",
    "CS_GESTANT",
    "CS_RACA",
    "SG_UF",
    "ID_MN_RESI",
    *COMORBIDADES,
    "FEBRE",
    "MIALGIA",
    "CEFALEIA",
    "EXANTEMA",
    "VOMITO",
    "NAUSEA",
    "DOR_COSTAS",
    "CONJUNTVIT",
    "ARTRITE",
    "ARTRALGIA",
    "PETEQUIA_N",
    "LEUCOPENIA",
    "LACO",
    "DOR_RETRO",
]


# ------------------------------------------------------------------------------ dados e saída
def sha256_arquivo(caminho: Path, bloco: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while chunk := f.read(bloco):
            h.update(chunk)
    return h.hexdigest()


def carregar_bruto_dev(
    data_dir: str | Path, anos=ANOS_DEV, colunas: list[str] | None = None
) -> tuple[dict[int, pd.DataFrame], dict]:
    """Lê `dengue_{ano}.parquet` de 2022 e 2023. RECUSA 2024 e qualquer ano fora de ANOS_DEV.

    Devolve (dataframes por ano, registro com SHA-256 real de cada arquivo e colunas ausentes).
    Hash nulo não é aceito como rastreabilidade: o arquivo precisa existir para ser lido.
    """
    import pyarrow.parquet as pq

    anos = [int(a) for a in anos]
    proibidos = [a for a in anos if a not in ANOS_DEV or a == ANO_TESTE]
    if proibidos:
        raise PermissionError(
            f"R1/Estratégia A: anos {proibidos} não podem ser carregados nesta etapa."
        )
    brutos, registro = {}, {"arquivos": {}, "colunas_ausentes": {}}
    for ano in anos:
        caminho = Path(data_dir) / f"dengue_{ano}.parquet"
        if not caminho.exists():
            raise FileNotFoundError(f"Parquet de {ano} não encontrado em {caminho}")
        nomes = pq.read_schema(caminho).names
        pedidas = colunas if colunas is not None else nomes
        presentes = [c for c in pedidas if c in nomes]
        registro["colunas_ausentes"][str(ano)] = [c for c in pedidas if c not in nomes]
        brutos[ano] = pd.read_parquet(caminho, columns=presentes)
        registro["arquivos"][str(ano)] = {
            "caminho": str(caminho),
            "bytes": caminho.stat().st_size,
            "sha256": sha256_arquivo(caminho),
            "linhas": int(len(brutos[ano])),
        }
    return brutos, registro


def montar_dev(brutos: dict[int, pd.DataFrame]):
    """População (D-45, inalterada), X (lista fechada) e metadados; tudo marcado como dev."""
    pops = [montar_populacao(df, ano) for ano, df in brutos.items()]
    pop = empilhar_populacoes(pops)
    x = montar_features(pop)
    verificar_dev(pop, x, meta=pop[["ANO"]], contexto="etapa1.montar_dev")
    return pop, x


def suprimir_pequenas(df: pd.DataFrame, colunas: list[str], minimo: int = MIN_CELULA):
    """R7: contagens entre 1 e minimo−1 viram NaN (a coluna `suprimido` marca a linha)."""
    out = df.copy()
    out["suprimido"] = False
    for c in colunas:
        pequeno = (out[c] > 0) & (out[c] < minimo)
        out.loc[pequeno, c] = np.nan
        out["suprimido"] |= pequeno
    return out


def salvar_tabela(df: pd.DataFrame, pasta: Path, nome: str, contagens: list[str] | None = None):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    if contagens:
        df = suprimir_pequenas(df, [c for c in contagens if c in df.columns])
    df.to_csv(pasta / f"{nome}.csv", index=True if df.index.name else False)
    return df


def salvar_json(obj: dict, pasta: Path, nome: str):
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(obj, indent=2, ensure_ascii=False, default=float)
    (pasta / f"{nome}.json").write_text(texto, "utf-8")


# ------------------------------------------------------------------------------ J2 reprodução
def _linha(item, hist, rep, tol_rel=0.0):
    if hist is None or rep is None or (isinstance(hist, float) and np.isnan(hist)):
        diff, rel, concl = np.nan, np.nan, "sem referência histórica"
    else:
        diff = rep - hist
        rel = diff / hist if hist else np.nan
        igual = abs(diff) == 0 or (not np.isnan(rel) and abs(rel) <= tol_rel)
        concl = "reproduzido" if igual else "DIVERGE — investigar (não forçar)"
    return {
        "item": item,
        "historico": hist,
        "reproduzido": rep,
        "diferenca": diff,
        "diferenca_relativa": rel,
        "conclusao": concl,
    }


def reproduzir_populacao(pop: pd.DataFrame, resultados_json: dict, prevalencia_ano: pd.DataFrame):
    """Compara população, eventos, prevalência e distribuição por ano com o registro de v1."""
    h = resultados_json["populacao_dev"]
    linhas = [
        _linha("casos (dev)", h["casos"], int(len(pop))),
        _linha("eventos (dev)", h["eventos"], int(pop["y"].sum())),
        _linha("prevalência (dev)", h["prevalencia"], float(pop["y"].mean()), tol_rel=1e-12),
    ]
    h_ano = prevalencia_ano.set_index("ANO")
    for ano, g in pop.groupby("ANO"):
        if int(ano) in h_ano.index:
            linhas.append(_linha(f"casos {ano}", float(h_ano.loc[ano, "casos"]), float(len(g))))
            linhas.append(
                _linha(
                    f"eventos {ano}", float(h_ano.loc[ano, "eventos (y=1)"]), float(g["y"].sum())
                )
            )
    return pd.DataFrame(linhas)


CAUSAS_CANDIDATAS = [
    "Arquivo DATASUS revisado depois do registro v1 (o v1 não guardou o SHA-256 dos Parquets).",
    "Versões diferentes de bibliotecas (v1: Python 3.12.10/Windows; ver metadados do modelo).",
    "Early stopping com sorteio por linha; outra versão do XGBoost pode gerar árvores diferentes.",
    "Busca v1 cortada por tempo: a grade avaliada pode ter sido outra.",
]


def reproduzir_metricas_oof(
    x, y, regiao, resultados_json: dict, config: dict, params_xgb: dict | None = None
) -> pd.DataFrame:
    """Refaz B0, B1 e o M1 (XGBoost + isotônica) em LORO 2022–23 e compara com o registro v1.

    Usa os parâmetros e a configuração registrados em v1. Não procura parâmetros novos.
    """
    y = np.asarray(y)
    ok = regiao.notna().to_numpy()
    params = params_xgb or resultados_json["selecao_m1"]["params"]
    oof_b0 = MD.oof_b0(y, regiao)
    oof_b1 = MD.oof_b1(x, y, regiao)
    cv = MD.cv_oof(
        "xgboost",
        params,
        x,
        y,
        regiao,
        seed=config["SEED"],
        max_iter=config["MAX_ITER_BOOSTING"],
        paciencia=config["PACIENCIA_BOOSTING"],
        val_frac=config["VALIDACAO_INTERNA_FRAC"],
        n_jobs=config.get("N_JOBS", -1),
        device=config.get("DEVICE", "cpu"),
    )
    cal = MD.calibrar_cruzado(cv["oof"], y, regiao, resultados_json["selecao_m1"]["calibrador"])
    hist = {r["modelo"]: r for r in resultados_json["dev"]["metricas_oof"]}
    linhas = []
    for nome_h, p in (
        ("B0 (prevalência)", oof_b0),
        ("B1 (logística simples)", oof_b1),
        ("xgboost (calibrado)", cal),
    ):
        pm = np.asarray(p)[ok]
        yy = y[ok]
        rep = {"PR-AUC (pooled)": pr_auc(yy, pm), "Brier": brier(yy, pm)}
        if nome_h != "B0 (prevalência)":
            rep["ROC-AUC"] = roc_auc(yy, pm)
            cr = calibracao_resumo(yy, pm)
            rep.update(
                {"slope": cr["slope"], "intercepto (CITL)": cr["intercepto_citl"], "O:E": cr["O:E"]}
            )
        for met, val in rep.items():
            h = hist.get(nome_h, {}).get(met)
            linhas.append(_linha(f"{nome_h} · {met}", h, float(val), tol_rel=0.0))
    return pd.DataFrame(linhas)


def comparar_configuracao(metadados_json: dict, config_atual: dict, versoes_atuais: dict):
    """Configuração e ambiente de v1 × atual (parâmetros divergentes ficam explícitos)."""
    linhas = []
    for k, v in metadados_json.get("config", {}).items():
        a = config_atual.get(k)
        linhas.append({"campo": f"config.{k}", "v1": v, "atual": a, "igual": v == a})
    for k, v in metadados_json.get("ambiente", {}).items():
        a = versoes_atuais.get(k)
        linhas.append({"campo": f"ambiente.{k}", "v1": v, "atual": a, "igual": v == a})
    return pd.DataFrame(linhas)


# ------------------------------------------------------------------------------ J3 ACIDO_PEPT
def codificacao_original(brutos: dict[int, pd.DataFrame], campo: str = "ACIDO_PEPT"):
    """Valores crus do campo por ano e por desfecho, ANTES de qualquer filtro (item 1)."""
    linhas = []
    for ano, df in brutos.items():
        valor = code(df[campo]).fillna("<branco>")
        y = target(df)
        t = pd.crosstab(valor, y).rename(columns={0: "y0", 1: "y1"})
        for v, r in t.iterrows():
            linhas.append(
                {
                    "ANO": ano,
                    "valor": v,
                    "casos_y0": int(r.get("y0", 0)),
                    "casos_y1": int(r.get("y1", 0)),
                }
            )
    return pd.DataFrame(linhas)


def conferir_construcao(pop: pd.DataFrame, x: pd.DataFrame, agg: pd.DataFrame, campo: str):
    """A variável do E1 (== "Sim") bate com a do X e com o agregado? (item 2)."""
    sim_x = int((x[campo] == "Sim").sum())
    ev_x = int(pop.loc[x[campo] == "Sim", "y"].sum())
    exp = agg[agg[campo] == 1]
    return pd.DataFrame(
        [
            {
                "campo": campo,
                "expostos_em_X": sim_x,
                "eventos_em_X": ev_x,
                "expostos_no_agregado_E1": int(exp["n"].sum()),
                "eventos_no_agregado_E1": int(exp["k"].sum()),
                "diferenca_casos_completos": sim_x - int(exp["n"].sum()),
            }
        ]
    )


def tabela_cruzada(agg: pd.DataFrame, campo: str = "ACIDO_PEPT") -> pd.DataFrame:
    """Casos e eventos de `campo` com cada outra comorbidade (item 3)."""
    linhas = []
    for o in [c for c in COMORBIDADES if c != campo]:

        def s(a, b, o=o):
            m = agg[(agg[campo] == a) & (agg[o] == b)]
            return int(m["n"].sum()), int(m["k"].sum())

        (n11, k11), (n10, k10), (n01, k01), (n00, k00) = s(1, 1), s(1, 0), s(0, 1), s(0, 0)
        linhas.append(
            {
                "outra": o,
                "casos_ambos": n11,
                "eventos_ambos": k11,
                "casos_so_campo": n10,
                "eventos_so_campo": k10,
                "casos_so_outra": n01,
                "eventos_so_outra": k01,
                "casos_nenhum": n00,
                "eventos_nenhum": k00,
            }
        )
    return pd.DataFrame(linhas)


def perfil_expostos(agg: pd.DataFrame, campo: str = "ACIDO_PEPT") -> pd.DataFrame:
    """Expostos × não expostos: casos, eventos, idade mediana, outras comorbidades (item 4)."""
    outras = [c for c in COMORBIDADES if c != campo]
    d = agg.assign(n_outras=agg[outras].sum(axis=1).clip(upper=3))
    linhas = []
    for exp, g in d.groupby(campo):
        w = g["n"].to_numpy()
        ordem = np.argsort(g["idade"].to_numpy())
        cum = np.cumsum(w[ordem]) / w.sum()
        med = float(g["idade"].to_numpy()[ordem][np.searchsorted(cum, 0.5)])
        linhas.append(
            {
                "grupo": f"{campo}={exp}",
                "casos": int(w.sum()),
                "eventos": int(g["k"].sum()),
                "prevalencia_%": 100 * g["k"].sum() / w.sum(),
                "idade_mediana": med,
            }
        )
        for k, gg in g.groupby("n_outras"):
            linhas.append(
                {
                    "grupo": f"{campo}={exp}, outras comorbidades={'3+' if k == 3 else k}",
                    "casos": int(gg["n"].sum()),
                    "eventos": int(gg["k"].sum()),
                    "prevalencia_%": 100 * gg["k"].sum() / gg["n"].sum(),
                    "idade_mediana": np.nan,
                }
            )
    return pd.DataFrame(linhas)


def colinearidade(agg: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Correlação phi (ponderada) entre as sete flags e VIF ponderado (item 5)."""
    cols = [*COMORBIDADES, "sexo_M", "idade"]
    w = agg["n"].to_numpy(dtype=float)
    Z = agg[cols].to_numpy(dtype=float)
    mu = (Z * w[:, None]).sum(0) / w.sum()
    cov = ((Z - mu).T * w) @ (Z - mu) / w.sum()
    dp = np.sqrt(np.diag(cov))
    corr = pd.DataFrame(cov / np.outer(dp, dp), index=cols, columns=cols)
    vif = []
    for j, c in enumerate(cols):
        outros = np.delete(np.arange(len(cols)), j)
        A = np.column_stack([np.ones(len(Z)), Z[:, outros]]) * np.sqrt(w)[:, None]
        b = Z[:, j] * np.sqrt(w)
        coef, *_ = np.linalg.lstsq(A, b, rcond=None)
        res = ((b - A @ coef) ** 2).sum()
        tot = (((Z[:, j] - mu[j]) * np.sqrt(w)) ** 2).sum()
        r2 = 1 - res / tot if tot > 0 else np.nan
        vif.append({"variavel": c, "R2_ponderado": r2, "VIF": 1 / (1 - r2) if r2 < 1 else np.inf})
    return corr.round(4), pd.DataFrame(vif)


def diagnostico_separacao(agg: pd.DataFrame, modelos: dict[str, E.ModeloGLM], campo: str):
    """Células vazias e sinais de (quase) separação nos modelos ajustados (item 6)."""
    celulas = []
    for o in [c for c in COMORBIDADES if c != campo]:
        m = agg[(agg[campo] == 1) & (agg[o] == 1)]
        celulas.append(
            {
                "combinacao": f"{campo}+{o}",
                "casos": int(m["n"].sum()),
                "eventos": int(m["k"].sum()),
                "sem_eventos": int(m["k"].sum()) == 0,
            }
        )
    ajuste = []
    for nome, m in modelos.items():
        se = np.sqrt(np.diag(m.cov.to_numpy()))
        mu = np.asarray(m.res.fittedvalues)
        ajuste.append(
            {
                "modelo": nome,
                "convergiu": bool(m.res.converged),
                "max_abs_beta": float(np.abs(m.beta).max()),
                "max_erro_padrao": float(se.max()),
                "prob_ajustada_min": float(mu.min()),
                "prob_ajustada_max": float(mu.max()),
                "sinal_de_separacao": bool(
                    se.max() > 5 or np.abs(m.beta).max() > 15 or not m.res.converged
                ),
            }
        )
    return pd.DataFrame(celulas), pd.DataFrame(ajuste)


def _linha_or(modelo, spec, m, campo, idade, eventos, base=None, rotulo=None):
    base = base or set()
    L = E._linhas(m, E._perfil_df(idade, base | {campo})) - E._linhas(m, E._perfil_df(idade, base))
    L = L[0]
    est, se = float(L @ m.beta.to_numpy()), float(np.sqrt(L @ m.cov.to_numpy() @ L))
    return {
        "modelo": modelo,
        "contraste": rotulo or f"{campo} (sem outras)",
        "OR": float(np.exp(est)),
        "ic95_inf": float(np.exp(est - 1.96 * se)),
        "ic95_sup": float(np.exp(est + 1.96 * se)),
        "eventos_expostos": eventos,
        "especificacao": spec,
        "convergiu": bool(m.res.converged),
        "AIC": float(m.res.aic),
    }


def comparar_especificacoes(agg: pd.DataFrame, nos: tuple, idade_ref: float, campo="ACIDO_PEPT"):
    """OR do campo em modelos bruto, idade+sexo, mútuo, mútuo+pares e E1 oficial (itens 7 e 8).

    Cada linha traz a especificação e o contraste exato. NENHUMA estimativa é escolhida aqui.
    """
    eventos = int(agg.loc[agg[campo] == 1, "k"].sum())
    linhas = []
    bruto = E._or_bruto(agg, campo)
    linhas.append(
        {
            "modelo": "bruto",
            "contraste": campo,
            "OR": bruto["OR_bruto"],
            "ic95_inf": bruto["bruto_ic95_inf"],
            "ic95_sup": bruto["bruto_ic95_sup"],
            "eventos_expostos": eventos,
            "especificacao": "tabela 2×2 (Woolf)",
            "convergiu": True,
            "AIC": np.nan,
        }
    )
    pares = [(r.A, r.B) for r in E.pares_com_eventos(agg).itertuples() if r.entra_no_E1]
    modelos: dict[str, E.ModeloGLM] = {}
    specs = {
        "A idade+sexo (só o campo)": dict(pares=[], idade=(), com=[campo]),
        "B mútuo aditivo (7)": dict(pares=[], idade=(), com=COMORBIDADES),
        "C mútuo + pares elegíveis": dict(pares=pares, idade=(), com=None),
        "D E1 oficial (pares + idade×HAS/DM)": dict(pares=pares, idade=E.INTERACAO_IDADE, com=None),
    }
    for nome, s in specs.items():
        if s["com"] is None:  # modelo com interações: monta o rhs completo
            m = E.ajustar_e1(agg, nos, s["pares"], interacao_idade=s["idade"])
        else:
            m = E.ajustar_e1(agg, nos, [], interacao_idade=(), comorbidades=s["com"])
        modelos[nome] = m
        linhas.append(_linha_or(nome, m.rhs, m, campo, idade_ref, eventos))
    # contrastes condicionais no E1 oficial: o campo somado a cada outra comorbidade presente
    for o in [c for c in COMORBIDADES if c != campo]:
        linhas.append(
            _linha_or(
                "D E1 oficial (pares + idade×HAS/DM)",
                modelos["D E1 oficial (pares + idade×HAS/DM)"].rhs,
                modelos["D E1 oficial (pares + idade×HAS/DM)"],
                campo,
                idade_ref,
                eventos,
                base={o},
                rotulo=f"{campo} dado {o}=Sim",
            )
        )
    return pd.DataFrame(linhas), modelos


def estabilidade(pop, x, agg_total, nos, campo="ACIDO_PEPT"):
    """Estabilidade do OR mútuo: por ano, sem uma outra comorbidade e por estrato (item 9)."""
    linhas = []

    def _ajusta(agg, com, rotulo, estrato=""):
        try:
            m = E.ajustar_e1(agg, nos, [], interacao_idade=(), comorbidades=com)
            b, se = float(m.beta[campo]), float(np.sqrt(m.cov.loc[campo, campo]))
            linhas.append(
                {
                    "analise": rotulo,
                    "estrato": estrato,
                    "OR": float(np.exp(b)),
                    "ic95_inf": float(np.exp(b - 1.96 * se)),
                    "ic95_sup": float(np.exp(b + 1.96 * se)),
                    "eventos_expostos": int(agg.loc[agg[campo] == 1, "k"].sum()),
                    "convergiu": bool(m.res.converged),
                }
            )
        except Exception as erro:  # pragma: no cover - registra a falha, não esconde
            linhas.append({"analise": rotulo, "estrato": estrato, "erro": repr(erro)})

    _ajusta(agg_total, COMORBIDADES, "mútuo aditivo (todos os anos)")
    for ano in sorted(pop["ANO"].unique()):
        sel = (pop["ANO"] == ano).to_numpy()
        a, _ = E.agregar_e1(pop[sel].reset_index(drop=True), x[sel].reset_index(drop=True))
        _ajusta(a, COMORBIDADES, "mútuo aditivo", f"ANO={ano}")
    for o in [c for c in COMORBIDADES if c != campo]:
        _ajusta(agg_total, [c for c in COMORBIDADES if c != o], f"mútuo sem {o}")
    outras = [c for c in COMORBIDADES if c != campo]
    n_outras = agg_total[outras].sum(axis=1)
    _ajusta(agg_total[n_outras == 0], [campo], "idade+sexo só o campo", "sem outras comorbidades")
    _ajusta(agg_total[n_outras >= 1], [campo], "idade+sexo só o campo", "≥1 outra comorbidade")
    return pd.DataFrame(linhas)


def conferir_implementacao(agg: pd.DataFrame, nos: tuple, campo="ACIDO_PEPT", max_linhas=3_000_000):
    """Refaz o mútuo por três vias e compara o coeficiente de `campo` (item 10).

    (a) binomial agrupado do E1; (b) GLM com `freq_weights` sobre a proporção; (c) logística
    linha a linha (statsmodels Logit, Newton) sobre a tabela expandida.
    """
    import patsy
    import statsmodels.api as sm

    rhs = E.ajustar_e1(agg, nos, [], interacao_idade=(), comorbidades=COMORBIDADES).rhs
    X = patsy.dmatrix(rhs, agg, return_type="dataframe")
    a = sm.GLM(
        np.column_stack([agg["k"], agg["n"] - agg["k"]]), X, family=sm.families.Binomial()
    ).fit(maxiter=100)
    b = sm.GLM(agg["k"] / agg["n"], X, family=sm.families.Binomial(), freq_weights=agg["n"]).fit(
        maxiter=100
    )
    linhas = [
        {
            "via": "(a) binomial agrupado (E1)",
            "beta": float(a.params[campo]),
            "OR": float(np.exp(a.params[campo])),
        },
        {
            "via": "(b) freq_weights",
            "beta": float(b.params[campo]),
            "OR": float(np.exp(b.params[campo])),
        },
    ]
    if int(agg["n"].sum()) <= max_linhas:
        idx = np.repeat(np.arange(len(agg)), agg["n"].to_numpy())
        ev = np.concatenate(
            [np.r_[np.ones(k), np.zeros(n - k)] for n, k in zip(agg["n"], agg["k"], strict=True)]
        )
        # Newton (como o GLM): o lbfgs do scikit-learn não converge com rigor nas colunas do
        # spline sem escala e daria uma diferença de otimizador, não de implementação.
        c = sm.Logit(ev, X.to_numpy()[idx]).fit(disp=0, maxiter=200, method="newton")
        j = list(X.columns).index(campo)
        linhas.append(
            {
                "via": "(c) linha a linha (Logit, Newton)",
                "beta": float(c.params[j]),
                "OR": float(np.exp(c.params[j])),
            }
        )
    else:
        linhas.append({"via": "(c) linha a linha (Logit, Newton)", "beta": np.nan, "OR": np.nan})
    t = pd.DataFrame(linhas)
    t["diferenca_beta_vs_a"] = t["beta"] - t.loc[0, "beta"]
    return t


# ------------------------------------------------------------------------------ J4 momento
def _delta_dias(a: pd.Series, b: pd.Series) -> pd.Series:
    return (parse_date(a) - parse_date(b)).dt.days


def preparar_momento(brutos: dict[int, pd.DataFrame]) -> pd.DataFrame:
    """População da v1 (inalterada) com as datas e os deltas de J4. Só 2022–23."""
    quadros = []
    for ano, df in brutos.items():
        d = df.copy()
        d["ANO"] = ano
        d = d[population_mask(d)].copy()
        d["y"] = target(d)
        d["grave"] = (code(d["CLASSI_FIN"]) == "12").fillna(False).astype("int8")
        d["obito"] = (code(d["EVOLUCAO"]) == "2").fillna(False).astype("int8")
        d["d_inv"] = _delta_dias(d["DT_INVEST"], d["DT_NOTIFIC"]) if "DT_INVEST" in d else np.nan
        d["d_enc"] = _delta_dias(d["DT_ENCERRA"], d["DT_NOTIFIC"]) if "DT_ENCERRA" in d else np.nan
        d["d_enc_inv"] = (
            _delta_dias(d["DT_ENCERRA"], d["DT_INVEST"])
            if {"DT_ENCERRA", "DT_INVEST"} <= set(d)
            else np.nan
        )
        d["d_sint_not"] = _delta_dias(d["DT_NOTIFIC"], d["DT_SIN_PRI"])
        quadros.append(d)
    out = pd.concat(quadros, ignore_index=True)
    return marcar_anos(out, list(brutos))


def _resumo_delta(s: pd.Series) -> dict:
    n = len(s)
    v = s.dropna()
    q = (
        v.quantile([0.5, 0.75, 0.9, 0.95, 0.99])
        if len(v)
        else pd.Series([np.nan] * 5, index=[0.5, 0.75, 0.9, 0.95, 0.99])
    )
    return {
        "n": n,
        "% ausente": 100 * s.isna().mean(),
        "% negativo": 100 * (v < 0).sum() / n,
        "% zero": 100 * (v == 0).sum() / n,
        "mediana": q[0.5],
        "p75": q[0.75],
        "p90": q[0.9],
        "p95": q[0.95],
        "p99": q[0.99],
        "% > 7 d": 100 * (v > 7).sum() / n,
        "% > 30 d": 100 * (v > 30).sum() / n,
    }


def distribuicao_deltas(d: pd.DataFrame) -> pd.DataFrame:
    """Deltas por desfecho, gravidade, óbito e ano (itens 1–6)."""
    grupos = {
        "total": pd.Series("todos", index=d.index),
        "y": d["y"].map({0: "y=0", 1: "y=1"}),
        "gravidade": d["grave"].map({0: "não grave (CLASSI 10/11)", 1: "grave (CLASSI 12)"}),
        "óbito": d["obito"].map({0: "demais", 1: "óbito pelo agravo"}),
        "ano": d["ANO"].astype(str),
    }
    linhas = []
    for tipo, g in grupos.items():
        for nivel in sorted(g.unique()):
            sub = d[g == nivel]
            for delta in ("d_inv", "d_enc", "d_enc_inv", "d_sint_not"):
                linhas.append(
                    {
                        "agrupamento": tipo,
                        "grupo": nivel,
                        "delta": delta,
                        **_resumo_delta(sub[delta]),
                    }
                )
    return pd.DataFrame(linhas)


def datas_inconsistentes(d: pd.DataFrame) -> pd.DataFrame:
    """Datas ausentes ou fora de ordem (item 7). Regra do dicionário: investigação ≥ notificação."""
    n = len(d)
    regras = {
        "DT_INVEST ausente ou inválida": d["d_inv"].isna(),
        "DT_ENCERRA ausente ou inválida": d["d_enc"].isna(),
        "DT_INVEST anterior à DT_NOTIFIC (contraria o dicionário)": d["d_inv"] < 0,
        "DT_ENCERRA anterior à DT_INVEST (contraria o dicionário)": d["d_enc_inv"] < 0,
        "DT_ENCERRA anterior à DT_NOTIFIC": d["d_enc"] < 0,
        "DT_SIN_PRI posterior à DT_NOTIFIC": d["d_sint_not"] < 0,
    }
    linhas = []
    for nome, mask in regras.items():
        mask = mask.fillna(False)
        linhas.append(
            {
                "regra": nome,
                "registros": int(mask.sum()),
                "% da população": 100 * mask.mean() if n else np.nan,
                "eventos": int(d.loc[mask, "y"].sum()),
                "prevalencia_y_%": 100 * d.loc[mask, "y"].mean() if mask.any() else np.nan,
            }
        )
    return pd.DataFrame(linhas)


def campos_por_atraso_investigacao(
    d: pd.DataFrame, campos: list[str] | None = None
) -> pd.DataFrame:
    """% de "Sim" de cada campo clínico por faixa de (DT_INVEST − DT_NOTIFIC) e por desfecho.

    Mostra se o preenchimento difere entre quem foi investigado no mesmo dia e quem foi depois.
    Isso é INDÍCIO, não prova de quando o campo foi preenchido.
    """
    campos = campos or [*COMORBIDADES, *SINTOMAS, *ACHADOS]
    campos = [c for c in dict.fromkeys(campos) if c in d.columns]
    faixa = pd.cut(
        d["d_inv"],
        [-np.inf, -1, 0, 7, 30, np.inf],
        labels=["<0", "0 (mesmo dia)", "1–7", "8–30", ">30"],
    )
    faixa = faixa.astype("string").fillna("sem data")
    linhas = []
    for campo in campos:
        sim = code(d[campo]) == "1"
        for (f, y), g in sim.groupby([faixa, d["y"]]):
            linhas.append(
                {
                    "campo": campo,
                    "faixa_invest_menos_notific_dias": f,
                    "y": int(y),
                    "casos": int(len(g)),
                    "n_sim": int(g.sum()),
                    "%_sim": 100 * g.mean(),
                }
            )
    return pd.DataFrame(linhas)


def nota_inconclusiva() -> dict:
    return {
        "classificacao_padrao": "inconclusivo",
        "motivo": "DT_INVEST é a data da investigação (item 31), não a de cada campo.",
        "documentacao_necessaria": [
            "log de alterações/auditoria do SINAN por campo (quem alterou, quando)",
            "data de digitação e de última alteração do registro (DT_DIGITA, se disponível)",
            "instrutivo de cada ano (SINAN Online × e-SUS VS) sobre os itens 33 e 34",
            "confirmação com a vigilância estadual do fluxo notificação → investigação (2022–2024)",
        ],
    }


# ------------------------------------------------------------------------------ J6 petéquias
def petequias(brutos: dict[int, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """PETEQUIA_N × PETEQUIAS na população da v1 (itens 1–6). Não presume equivalência."""
    quadros = []
    for ano, df in brutos.items():
        d = df.copy()
        d["ANO"] = ano
        d = d[population_mask(d)].copy()
        d["y"] = target(d)
        quadros.append(d)
    d = pd.concat(quadros, ignore_index=True)
    out: dict[str, pd.DataFrame] = {}
    if "PETEQUIAS" not in d:
        out["aviso"] = pd.DataFrame([{"aviso": "coluna PETEQUIAS ausente no Parquet"}])
        return out
    a = code(d["PETEQUIA_N"]).fillna("<branco>")
    b = code(d["PETEQUIAS"]).fillna("<branco>")
    cruz = pd.crosstab(a, b)
    cruz.index.name, cruz.columns.name = "PETEQUIA_N", "PETEQUIAS"
    out["cruzada"] = cruz.reset_index()
    out["distribuicao"] = pd.concat(
        [
            a.value_counts()
            .rename_axis("valor")
            .reset_index(name="casos")
            .assign(campo="PETEQUIA_N"),
            b.value_counts()
            .rename_axis("valor")
            .reset_index(name="casos")
            .assign(campo="PETEQUIAS"),
        ]
    )
    ev = []
    for campo, s in (("PETEQUIA_N", a), ("PETEQUIAS", b)):
        for v, g in d.groupby(s):
            ev.append(
                {
                    "campo": campo,
                    "valor": v,
                    "casos": int(len(g)),
                    "eventos": int(g["y"].sum()),
                    "prevalencia_y_%": 100 * g["y"].mean(),
                    "% dos eventos": 100 * g["y"].sum() / max(d["y"].sum(), 1),
                    "% dos nao eventos": 100 * (len(g) - g["y"].sum()) / max((1 - d["y"]).sum(), 1),
                }
            )
    out["por_desfecho"] = pd.DataFrame(ev)
    out["por_classificacao"] = pd.crosstab(code(d["CLASSI_FIN"]), [b]).reset_index()
    sim_a, sim_b = (a == "1"), (b == "1")
    valido = a.isin(["1", "2"]) & b.isin(["1", "2"])
    po = float((sim_a[valido] == sim_b[valido]).mean()) if valido.any() else np.nan
    pa, pb = sim_a[valido].mean(), sim_b[valido].mean()
    pe = pa * pb + (1 - pa) * (1 - pb)
    kappa = (po - pe) / (1 - pe) if valido.any() and pe < 1 else np.nan
    so_b = int((sim_b & ~sim_a).sum())
    ambos = int((sim_a & sim_b).sum())
    if np.isnan(kappa):
        indicio = "sem dados suficientes"
    elif kappa >= 0.8 and po >= 0.95:
        indicio = "indício de REDUNDÂNCIA (concordância alta)"
    elif ambos == 0 or kappa < 0.2:
        indicio = "indício de COMPLEMENTARIDADE ou campos independentes"
    else:
        indicio = "concordância parcial: inconsistência ou complementaridade; ver tabelas"
    out["redundancia"] = pd.DataFrame(
        [
            {
                "n_validos_ambos_1_2": int(valido.sum()),
                "concordancia_observada": po,
                "kappa": kappa,
                "ambos_sim": ambos,
                "so_PETEQUIAS_sim": so_b,
                "so_PETEQUIA_N_sim": int((sim_a & ~sim_b).sum()),
                "indicio_automatico": indicio + " — não é conclusão; exige documentação do campo",
            }
        ]
    )
    return out


# ------------------------------------------------------------------------------ J5 ablação
SUSPEITAS = ["dias_ate_notificacao", "VOMITO", "LEUCOPENIA", "PETEQUIA_N"]


def variantes_ablacao() -> dict[str, list[str]]:
    """Colunas retiradas em cada variante (nenhuma é retirada em definitivo)."""
    return {
        "1 M1 completo": [],
        "2 sem dias_ate_notificacao": ["dias_ate_notificacao"],
        "3 sem VOMITO": ["VOMITO"],
        "4 sem LEUCOPENIA": ["LEUCOPENIA"],
        "5 sem PETEQUIA_N": ["PETEQUIA_N"],
        "6 sem as 4 suspeitas": list(SUSPEITAS),
        "G1 sem sintomas e achados (só perfil + atraso)": [*SINTOMAS, *ACHADOS],
        "G2 sem sintomas, achados e atraso (só perfil)": [
            *SINTOMAS,
            *ACHADOS,
            "dias_ate_notificacao",
        ],
        "G3 sem as 4 suspeitas e sem LACO": [*SUSPEITAS, "LACO"],
    }


def executar_ablacao(
    x, y, regiao, params, seed, config, variantes=None, B=500, meta=None
) -> dict[str, pd.DataFrame]:
    """LORO com o MESMO XGBoost, dobras, semente e calibração (isotônica cruzada) em cada variante.

    Mantém população, divisão, pré-processamento e métricas comparáveis. Os ICs vêm de bootstrap
    com as MESMAS reamostras para todas as variantes, o que permite diferenças pareadas.
    """
    variantes = variantes or variantes_ablacao()
    y = np.asarray(y)
    ok = regiao.notna().to_numpy()
    cal = {}
    for nome, retirar in variantes.items():
        xv = x.drop(columns=retirar)  # attrs preservados; R1 verificada dentro de cv_oof
        r = MD.cv_oof(
            "xgboost",
            params,
            xv,
            y,
            regiao,
            seed,
            meta=meta,
            max_iter=config["MAX_ITER_BOOSTING"],
            paciencia=config["PACIENCIA_BOOSTING"],
            val_frac=config["VALIDACAO_INTERNA_FRAC"],
            n_jobs=config.get("N_JOBS", -1),
            device=config.get("DEVICE", "cpu"),
        )
        cal[nome] = MD.calibrar_cruzado(r["oof"], y, regiao, "isotonica", meta=meta)
    yy = y[ok]
    scores = {n: np.asarray(p)[ok] for n, p in cal.items()}
    flags = {}
    metricas = []
    for nome, p in scores.items():
        lim, _ = melhor_limiar_f2(yy, p)  # limiar escolhido só em dev, por variante
        flags[nome] = p >= lim
        cr = calibracao_resumo(yy, p)
        m = metricas_limiar(yy, flags[nome])
        metricas.append(
            {
                "variante": nome,
                "colunas_retiradas": ", ".join(variantes[nome]) or "—",
                "PR-AUC": pr_auc(yy, p),
                "ROC-AUC": roc_auc(yy, p),
                "Brier": brier(yy, p),
                "slope": cr["slope"],
                "intercepto": cr["intercepto_citl"],
                "O:E": cr["O:E"],
                "limiar_F2_dev": lim,
                "sensibilidade": m["sensibilidade"],
                "precisao_VPP": m["VPP"],
                "especificidade": m["especificidade"],
                "pct_sinalizados": m["pct_sinalizados"],
            }
        )
    tab = agregar(yy, scores=scores, flags=flags, casas=2)
    boot = bootstrap_metricas(tab, B=B, seed=seed)
    ref = next(iter(variantes))
    linhas_ic, linhas_dif = [], []
    for nome in scores:
        for met in ("pr_auc", "roc_auc", "brier"):
            lo, hi = ic95(boot[f"{met}[{nome}]"])
            linhas_ic.append({"variante": nome, "metrica": met, "ic95_inf": lo, "ic95_sup": hi})
            if nome != ref:
                dif = boot[f"{met}[{nome}]"] - boot[f"{met}[{ref}]"]
                lo, hi = ic95(dif)
                pt = next(
                    m[{"pr_auc": "PR-AUC", "roc_auc": "ROC-AUC", "brier": "Brier"}[met]]
                    for m in metricas
                    if m["variante"] == nome
                )
                pr = next(
                    m[{"pr_auc": "PR-AUC", "roc_auc": "ROC-AUC", "brier": "Brier"}[met]]
                    for m in metricas
                    if m["variante"] == ref
                )
                linhas_dif.append(
                    {
                        "variante": nome,
                        "metrica": met,
                        "diferenca_vs_completo": pt - pr,
                        "ic95_inf": lo,
                        "ic95_sup": hi,
                    }
                )
    return {
        "metricas": pd.DataFrame(metricas),
        "ic95": pd.DataFrame(linhas_ic),
        "diferencas_pareadas": pd.DataFrame(linhas_dif),
    }


def ablacao_temporal(x, y, ano, params, seed, config, variantes=None) -> pd.DataFrame:
    """Treino em 2022, teste em 2023 (ambos dev). Discriminação e calibração sem recalibrar.

    EXPLORATÓRIO: 2023 faz parte do desenvolvimento e não é teste independente. Sem limiar.
    """
    variantes = variantes or variantes_ablacao()
    y = np.asarray(y)
    ano = np.asarray(ano).astype(int)
    tr, te = np.flatnonzero(ano == 2022), np.flatnonzero(ano == 2023)
    linhas = []
    for nome, retirar in variantes.items():
        xv = x.drop(columns=retirar)
        m = MD.ModeloM1(
            "xgboost",
            params,
            seed,
            paciencia=config["PACIENCIA_BOOSTING"],
            val_frac=config["VALIDACAO_INTERNA_FRAC"],
            max_iter=config["MAX_ITER_BOOSTING"],
            n_jobs=config.get("N_JOBS", -1),
            device=config.get("DEVICE", "cpu"),
        )
        m.ajustar(xv.iloc[tr], y[tr])
        p = m.prever(xv.iloc[te])
        cr = calibracao_resumo(y[te], p)
        linhas.append(
            {
                "variante": nome,
                "PR-AUC": pr_auc(y[te], p),
                "ROC-AUC": roc_auc(y[te], p),
                "Brier": brier(y[te], p),
                "slope": cr["slope"],
                "intercepto": cr["intercepto_citl"],
                "O:E": cr["O:E"],
                "n_teste": int(len(te)),
                "eventos_teste": int(y[te].sum()),
            }
        )
    return pd.DataFrame(linhas)
