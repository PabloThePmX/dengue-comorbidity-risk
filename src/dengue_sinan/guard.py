"""Guardas contra uso indevido do teste (R1, R2) e contra features proibidas (R4, §3.8)."""

import pandas as pd

ANOS_DEV = (2022, 2023)
ANO_TESTE = 2024

# Campos que NUNCA podem virar feature (revisão de vazamento, §3.8; regra R4 da constituição).
FEATURES_PROIBIDAS_PREFIXOS = ("ALRM_", "GRAV_", "RESUL_", "DT_")
FEATURES_PROIBIDAS = {
    "CLASSI_FIN",
    "EVOLUCAO",
    "CRITERIO",
    "HOSPITALIZ",
    "ANO",
    "regiao",
    "SG_UF",
    "ID_MN_RESI",
    "ID_UNIDADE",
    "ID_MUNICIP",
    "SG_UF_NOT",
    "CS_RACA",
    "CS_ESCOL_N",
    "faixa_etaria",
    "y",
    "PETEQUIAS",
    "LACO_N",
    "NU_ANO",
    "SEM_NOT",
    "SEM_PRI",
    "NDUPLIC_N",
    "TP_SISTEMA",
    "idade_de_ano_nasc",
    "ANO_NASC",
}


def assert_dev_only(df: pd.DataFrame, coluna: str = "ANO") -> None:
    """Falha se o DataFrame tiver qualquer linha do ano de teste (R1).

    Toda função que treina, ajusta, calibra, escolhe limiar ou seleciona modelo chama isto.
    """
    anos = pd.to_numeric(df[coluna], errors="coerce").dropna().astype(int).unique()
    if ANO_TESTE in set(anos.tolist()):
        raise PermissionError(
            f"R1: dados de {ANO_TESTE} (teste congelado) não podem entrar em treino, tuning, "
            f"calibração, limiar ou seleção. Anos recebidos: {sorted(anos.tolist())}."
        )


def assert_features_permitidas(colunas: list[str], permitidas: list[str]) -> None:
    """Falha se alguma coluna de X estiver fora da lista fechada do data-model §D (R4)."""
    fora = [c for c in colunas if c not in set(permitidas)]
    proibidas = [
        c for c in colunas if c in FEATURES_PROIBIDAS or c.startswith(FEATURES_PROIBIDAS_PREFIXOS)
    ]
    if fora or proibidas:
        raise ValueError(f"R4: features fora da lista fechada: {sorted(set(fora + proibidas))}")
