"""Exportação dos resultados agregados da Etapa 3.2 (tabelas e metadados), com supressão.

Só entram agregados: métricas por modelo e escopo, contagens por região e diagnósticos. Nunca
predições individuais, identificadores de município ou de paciente. Contagens de 1 a 9 são
suprimidas (R7), com supressão complementar quando o total publicado permitiria recuperá-las.
"""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from dengue_sinan.folds import ORDEM_REGIOES
from dengue_sinan.pipeline.contrato import RAIZ
from dengue_sinan.pipeline.metricas import METRICAS
from dengue_sinan.pipeline.oof import ROTULOS

MINIMO = 10  # células com 1 a 9 casos são suprimidas
MINIMO_COMPLEMENTAR = 20  # a complementar escolhida deve ficar bem acima do limite
COLUNAS_PROIBIDAS = {"conglomerado", "municipio", "id", "p_m1", "p_b0", "p_b1", "p_b1_idade", "y"}
LIMITE_LINHAS = 500  # tabela agregada com mais linhas que isso é suspeita
MODULOS_DO_CODIGO = (
    "pipeline/*.py",
    "folds.py",
    "modelos.py",
    "guard.py",
    "dataset.py",
    "metrics.py",
    "profiling.py",
    "features.py",
    "etapa1.py",
)


def plano_supressao(contagens: pd.DataFrame, col_eventos: str = "n_eventos") -> pd.DataFrame:
    """Marca regiões com 1 a 9 eventos (primária) e uma complementar por família.

    A família é o conjunto de regiões, cuja soma é o total publicado na tabela global. Se há
    célula primária, esconde-se também a menor célula visível com pelo menos
    `MINIMO_COMPLEMENTAR` eventos (ou, na falta dela, a maior), para que o total não revele a
    célula escondida por diferença.
    """
    df = contagens.copy()
    ev = df[col_eventos]
    df["suprimida"] = ev.between(1, MINIMO - 1)
    df["complementar"] = False
    if df["suprimida"].any():
        visiveis = df[~df["suprimida"]]
        grandes = visiveis[visiveis[col_eventos] >= MINIMO_COMPLEMENTAR]
        alvo = (grandes if len(grandes) else visiveis)[col_eventos]
        if len(alvo):
            alvo_idx = alvo.idxmin() if len(grandes) else alvo.idxmax()
            df.loc[alvo_idx, "complementar"] = True
    df["oculta"] = df["suprimida"] | df["complementar"]
    return df


def _largo(res: list[dict], modelo: str, escopo: str) -> dict:
    linha = {}
    for r in res:
        if r["modelo"] == modelo and r["escopo"] == escopo:
            m = r["metrica"]
            linha[m] = r["estimativa"]
            linha[f"{m}_ic_inf"] = r["ic_inf"]
            linha[f"{m}_ic_sup"] = r["ic_sup"]
            linha[f"{m}_replicacoes_validas"] = r["n_validas"]
    return linha


def tabelas(boot: dict, modelos: list[str], regioes: list[str], contagens: pd.DataFrame) -> dict:
    """Monta as tabelas agregadas. Regiões ocultas pela supressão perdem contagens e métricas."""
    res = boot["resultado"]
    plano = plano_supressao(contagens).set_index("regiao")
    metricas_cols = [c for m in METRICAS for c in (m, f"{m}_ic_inf", f"{m}_ic_sup")]
    glob = pd.DataFrame(
        [{"modelo": m, "rotulo": ROTULOS[m]} | _largo(res, m, "global") for m in modelos]
    )
    media = pd.DataFrame(
        [{"modelo": m, "rotulo": ROTULOS[m]} | _largo(res, m, "media_das_dobras") for m in modelos]
    )
    linhas = []
    for k, r in enumerate(regioes, start=1):
        for m in modelos:
            linhas.append(
                {"dobra": k, "regiao": r, "modelo": m, "rotulo": ROTULOS[m]} | _largo(res, m, r)
            )
    reg = pd.DataFrame(linhas)
    for r in regioes:  # supressão: some qualquer coisa derivada de uma região oculta
        if plano.loc[r, "oculta"]:
            reg.loc[reg["regiao"] == r, metricas_cols] = np.nan
    cont = contagens.copy()
    colunas_contagem = ["n_linhas", "n_eventos", "n_conglomerados"]
    cont[colunas_contagem] = cont[colunas_contagem].astype("Int64")
    ocultas = cont["regiao"].map(plano["oculta"]).fillna(False).astype(bool)
    cont.loc[ocultas, colunas_contagem + ["prevalencia"]] = pd.NA
    cont["supressao"] = np.where(
        cont["regiao"].map(plano["suprimida"]).fillna(False).astype(bool),
        "primaria",
        np.where(
            cont["regiao"].map(plano["complementar"]).fillna(False).astype(bool), "complementar", ""
        ),
    )
    n_total = int(contagens["n_linhas"].sum())
    ev_total = int(contagens["n_eventos"].sum())
    glob_cont = {"n_linhas": n_total, "n_eventos": ev_total, "prevalencia": ev_total / n_total}
    dif = pd.DataFrame(boot["diferencas"])
    if len(dif):
        for r in regioes:
            if plano.loc[r, "oculta"]:
                dif.loc[dif["escopo"] == r, ["estimativa", "ic_inf", "ic_sup"]] = np.nan
        dif = dif.sort_values(["comparacao", "metrica", "escopo"]).reset_index(drop=True)
    return {
        "metricas_globais": glob,
        "media_das_dobras": media,
        "metricas_por_dobra": reg,
        "contagens_por_regiao": cont,
        "diferencas_m1_vs_baselines": dif,
        "contagens_globais": pd.DataFrame([glob_cont]),
    }


def verificar_agregado(df: pd.DataFrame, nome: str) -> None:
    """Falha se a tabela parece conter dados individuais."""
    if COLUNAS_PROIBIDAS & set(df.columns):
        raise ValueError(f"{nome}: colunas proibidas {COLUNAS_PROIBIDAS & set(df.columns)}")
    if len(df) > LIMITE_LINHAS:
        raise ValueError(f"{nome}: {len(df)} linhas; tabela agregada não passa de {LIMITE_LINHAS}")


def gravar(tab: dict, metadados: dict, diagnostico: dict, pasta: Path) -> list[Path]:
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    escritos = []
    for nome, df in tab.items():
        verificar_agregado(df, nome)
        caminho = pasta / f"{nome}.csv"
        df.to_csv(caminho, index=False, float_format="%.6g")
        escritos.append(caminho)
    for nome, obj in (("metadados_avaliacao", metadados), ("diagnostico_bootstrap", diagnostico)):
        caminho = pasta / f"{nome}.json"
        caminho.write_text(
            json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n",
            "utf-8",
        )
        escritos.append(caminho)
    return escritos


def hash_do_codigo(raiz: Path = RAIZ) -> dict:
    """SHA-256 dos módulos relevantes. Sem Git, é a identificação de revisão disponível."""
    base = raiz / "src" / "dengue_sinan"
    arquivos = sorted({p for padrao in MODULOS_DO_CODIGO for p in base.glob(padrao)})
    por_arquivo = {
        str(p.relative_to(raiz)): hashlib.sha256(p.read_bytes()).hexdigest() for p in arquivos
    }
    combinado = hashlib.sha256(
        "\n".join(f"{k}:{v}" for k, v in por_arquivo.items()).encode()
    ).hexdigest()
    return {
        "git": "indisponível: a pasta do projeto não tem .git; nenhum commit é registrado",
        "sha256_combinado": combinado,
        "sha256_por_arquivo": por_arquivo,
    }


def ordem_regioes() -> list[str]:
    return list(ORDEM_REGIOES)
