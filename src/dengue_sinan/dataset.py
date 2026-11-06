"""Montagem da população e da matriz de features (spec §3.6, §3.8, §3.9; data-model §D)."""

import numpy as np
import pandas as pd

from dengue_sinan.profiling import (
    COMORBIDADES,
    SINAIS,
    add_derived,
    code,
    parse_date,
    population_mask,
)

SEXOS = ["F", "M", "I"]
NIVEIS = ["Não", "Sim", "Ausente"]  # codificação ordinal fixa para árvores: 0, 1, 2
SINTOMAS = [s for s in SINAIS if s not in ("LEUCOPENIA", "LACO")]  # 12 sintomas do item 33
ACHADOS = ["LEUCOPENIA", "LACO"]
DIAS_MAX = 60  # [ASSUMPTION] do spec §3.9: atraso truncado em [0, 60]

PARES = [(a, b) for i, a in enumerate(COMORBIDADES) for b in COMORBIDADES[i + 1 :]]
FEATURES_M1 = (
    ["idade_anos", "sexo", "gestante"]
    + COMORBIDADES
    + ["n_comorbidades"]
    + SINTOMAS
    + ACHADOS
    + ["dias_ate_notificacao"]
)
FEATURES_PERFIL = ["idade_anos", "sexo", "gestante"] + COMORBIDADES + ["n_comorbidades"]
CATEGORICAS = ["sexo"] + COMORBIDADES + SINTOMAS + ACHADOS

# Colunas lidas do Parquet. As de auditoria (GRAV_*, ALRM_*, ID_UNIDADE, NDUPLIC_N) NUNCA
# entram em X; servem só à checagem de consistência e à análise de duplicatas.
COLUNAS_BASE = (
    [
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
    ]
    + COMORBIDADES
    + SINAIS
)
COLUNAS_AUDITORIA = ["ID_UNIDADE", "NDUPLIC_N", "CRITERIO"]


def tres_niveis(serie: pd.Series) -> pd.Categorical:
    """1 → Sim, 2 → Não, qualquer outra coisa (branco, 9...) → Ausente (D-07)."""
    valores = code(serie)
    sim = (valores == "1").fillna(False).to_numpy(dtype=bool)
    nao = (valores == "2").fillna(False).to_numpy(dtype=bool)
    texto = np.where(sim, "Sim", np.where(nao, "Não", "Ausente"))
    return pd.Categorical(texto, categories=NIVEIS)


def montar_populacao(raw: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Aplica a população de D-45 e acrescenta y, idade, faixa, região e gestante."""
    df = raw.copy()
    df["ANO"] = ano
    df = df[population_mask(df)].copy()
    return add_derived(df).reset_index(drop=True)


def montar_features(pop: pd.DataFrame) -> pd.DataFrame:
    """Matriz X da lista fechada do data-model §D. Só campos disponíveis na notificação."""
    x = pd.DataFrame(index=pop.index)
    x["idade_anos"] = pop["idade_anos"].astype("float64")
    sexo = code(pop["CS_SEXO"]).where(lambda s: s.isin({"M", "F"}), "I").fillna("I")
    x["sexo"] = pd.Categorical(sexo.astype(object), categories=SEXOS)
    x["gestante"] = pop["gestante"].astype("int8")
    for campo in COMORBIDADES + SINTOMAS + ACHADOS:
        x[campo] = tres_niveis(pop[campo])
    x["n_comorbidades"] = sum((x[c] == "Sim").astype("int8") for c in COMORBIDADES).astype("int8")
    atraso = (parse_date(pop["DT_NOTIFIC"]) - parse_date(pop["DT_SIN_PRI"])).dt.days
    x["dias_ate_notificacao"] = atraso.clip(lower=0, upper=DIAS_MAX).astype("float64")
    return x[FEATURES_M1]


def matriz_arvore(x: pd.DataFrame, dias_nan: float | None = None) -> pd.DataFrame:
    """Codificação ordinal FIXA (sem estado, logo sem possibilidade de vazamento) para árvores.

    `dias_nan`: valor constante para atraso ausente (Random Forest não aceita NaN); None mantém
    NaN (XGBoost e HistGradientBoosting lidam nativamente).
    """
    out = x.copy()
    for campo in CATEGORICAS:
        out[campo] = out[campo].cat.codes.astype("int8")
    if dias_nan is not None:
        out["dias_ate_notificacao"] = out["dias_ate_notificacao"].fillna(dias_nan)
    return out


def adicionar_pares(x: pd.DataFrame) -> pd.DataFrame:
    """Anexa as 21 interações Sim×Sim entre comorbidades (usadas no elastic net)."""
    out = x.copy()
    for a, b in PARES:
        out[f"ix_{a}_{b}"] = ((x[a] == "Sim") & (x[b] == "Sim")).astype("int8")
    return out


def faixa_ou_nan(pop: pd.DataFrame) -> pd.Series:
    return pop["faixa_etaria"].astype("string")


def completos_para_e1(pop: pd.DataFrame, x: pd.DataFrame) -> pd.Series:
    """Análise de casos completos do E1: sexo M/F e nenhuma comorbidade \"Ausente\".

    Evita níveis esparsos (quase-separação) no modelo com IC. B1 e M1 usam todas as linhas.
    """
    ok = x["sexo"].isin(["M", "F"])
    for campo in COMORBIDADES:
        ok &= x[campo] != "Ausente"
    return ok.astype(bool)


CLASSI_ESPERADO = {"0", "8", "10", "11", "12"}
EVOLUCAO_ESPERADA = {"0", "1", "2", "3", "4", "9"}


def checar_dominios_alvo(raw: pd.DataFrame, ano: int) -> dict:
    """Check BLOQUEANTE (FR-03): CLASSI_FIN e EVOLUCAO só com os códigos observados no profiling.

    Aparecer 1/2/8 do dicionário de 2024 em CLASSI_FIN (ou qualquer código novo) muda a definição
    do alvo (D-02): o notebook para com mensagem clara.
    """
    inesperados = {}
    for campo, ok in (("CLASSI_FIN", CLASSI_ESPERADO), ("EVOLUCAO", EVOLUCAO_ESPERADA)):
        vistos = set(code(raw[campo]).dropna().unique().tolist())
        if vistos - ok:
            inesperados[campo] = sorted(vistos - ok)
    if inesperados:
        raise ValueError(
            f"Check bloqueante (ano {ano}): códigos fora do domínio conhecido "
            f"{inesperados}. O alvo (D-02) precisa ser redecidido pelo Programador."
        )
    return {
        "ano": ano,
        "CLASSI_FIN": sorted(set(code(raw["CLASSI_FIN"]).dropna().unique().tolist())),
        "EVOLUCAO": sorted(set(code(raw["EVOLUCAO"]).dropna().unique().tolist())),
    }


def empilhar_populacoes(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Concatena anos mantendo colunas categóricas leves (união das categorias)."""
    saida = {}
    for c in frames[0].columns:
        series = [f[c] for f in frames]
        if all(isinstance(s.dtype, pd.CategoricalDtype) for s in series):
            from pandas.api.types import union_categoricals

            saida[c] = pd.Series(union_categoricals(series, ignore_order=True))
        else:
            saida[c] = pd.concat(series, ignore_index=True)
    return pd.DataFrame(saida)
