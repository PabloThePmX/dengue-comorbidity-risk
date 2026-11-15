"""Verificações de qualidade executadas antes dos filtros de população."""

import logging

import pandas as pd

from dengue_sinan.profiling import COMORBIDADES, SINAIS, code, parse_date

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = [
    "CLASSI_FIN",
    "EVOLUCAO",
    "NU_IDADE_N",
    "ANO_NASC",
    "DT_SIN_PRI",
    "DT_NOTIFIC",
    "CS_SEXO",
    "CS_GESTANT",
    "CS_RACA",
    "ID_MN_RESI",
    "SG_UF",
    *COMORBIDADES,
    *SINAIS,
]
CLASSI_FIN_VALUES = {"0", "8", "10", "11", "12"}
EVOLUCAO_VALUES = {"0", "1", "2", "3", "4", "9"}


def check_columns(df: pd.DataFrame, year: int) -> None:
    """Falha se o arquivo anual não contiver alguma coluna usada pelo pipeline."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(df.columns))
    if missing:
        raise ValueError(f"{year}: colunas obrigatórias ausentes: {', '.join(missing)}")


def check_domains(df: pd.DataFrame, year: int) -> None:
    """Falha diante de códigos novos nos campos que definem população e desfecho."""
    allowed = {
        "CLASSI_FIN": CLASSI_FIN_VALUES,
        "EVOLUCAO": EVOLUCAO_VALUES,
    }
    for column, valid in allowed.items():
        values = set(code(df[column]).dropna().unique())
        unexpected = sorted(values - valid)
        if unexpected:
            raise ValueError(
                f"{year}: domínio inesperado em {column}: {unexpected}; "
                f"valores permitidos: {sorted(valid)} e branco"
            )


def log_quality_warnings(df: pd.DataFrame, year: int) -> None:
    """Registra inconsistências não bloqueantes com contexto anual."""
    onset = parse_date(df["DT_SIN_PRI"])
    notified = parse_date(df["DT_NOTIFIC"])
    late_order = int((onset.notna() & notified.notna() & (onset > notified)).sum())
    if late_order:
        logger.warning("%s: DT_SIN_PRI posterior a DT_NOTIFIC em %d linhas", year, late_order)

    pregnant_male = int(
        (code(df["CS_GESTANT"]).isin({"1", "2", "3", "4"}) & code(df["CS_SEXO"]).eq("M")).sum()
    )
    if pregnant_male:
        logger.warning("%s: gestante com sexo M em %d linhas", year, pregnant_male)

    if "SG_UF" not in df or not len(df):
        return
    strata = pd.DataFrame({"uf": code(df["SG_UF"]), "ano": year}, index=df.index)
    for column in COMORBIDADES:
        values = code(df[column])
        ignored = values.isin({"", "9", "9.0"})
        rates = ignored.groupby([strata["uf"], strata["ano"]], dropna=False).mean()
        high = rates[rates > 0.5]
        for (uf, _), rate in high.items():
            logger.warning(
                "%s/%s: %s tem %.1f%% de valores ignorados", year, uf, column, 100 * rate
            )


def check_data(df: pd.DataFrame, year: int) -> None:
    """Executa bloqueios e alertas de qualidade para um ano."""
    check_columns(df, year)
    check_domains(df, year)
    log_quality_warnings(df, year)