"""Checks bloqueantes e alertas de qualidade dos microdados."""

import logging
from collections.abc import Iterable

import pandas as pd

from dengue_sinan.profiling import COMORBIDADES, SINAIS, code, parse_date

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = tuple(dict.fromkeys([
    "CLASSI_FIN", "EVOLUCAO", "NU_IDADE_N", "ANO_NASC", "DT_SIN_PRI", "DT_NOTIFIC",
    "CS_SEXO", "CS_GESTANT", "CS_RACA", "ID_MN_RESI", "SG_UF",
    *COMORBIDADES, *SINAIS,
]))
CLASSI_FIN_VALUES = {"0", "8", "10", "11", "12"}
EVOLUCAO_VALUES = {"0", "1", "2", "3", "4", "9"}


def _validate_domain(
    frame: pd.DataFrame, column: str, allowed: set[str], year: int | str,
) -> None:
    values = code(frame[column])
    unexpected = sorted(set(values.dropna().unique()) - allowed)
    if unexpected:
        raise ValueError(
            f"{year}: {column} contém valores fora do domínio observado: {unexpected}"
        )


def _alert_quality(frame: pd.DataFrame, year: int | str) -> None:
    onset = parse_date(frame["DT_SIN_PRI"])
    notification = parse_date(frame["DT_NOTIFIC"])
    late_onset = (onset.notna() & notification.notna() & (onset > notification)).sum()
    if late_onset:
        logger.warning("%s: %d registros têm DT_SIN_PRI posterior a DT_NOTIFIC", year, late_onset)

    pregnant = code(frame["CS_GESTANT"]).isin({"1", "2", "3", "4"})
    male_pregnant = (pregnant & code(frame["CS_SEXO"]).eq("M")).sum()
    if male_pregnant:
        logger.warning("%s: %d registros têm gestante com sexo M", year, male_pregnant)

    uf = code(frame["SG_UF"]).fillna("<branco>")
    for column in COMORBIDADES:
        value = code(frame[column])
        ignored = value.isna() | ~value.isin({"1", "2"})
        share = ignored.groupby(uf).mean()
        high = share[share > 0.5]
        for state, proportion in high.items():
            logger.warning(
                "%s/%s: %s tem %.1f%% de valores ignorados/ausentes",
                year, state, column, proportion * 100,
            )


def check_year(frame: pd.DataFrame, year: int | str) -> None:
    """Falha em schema/domínios novos e registra os alertas especificados no TODO."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(f"{year}: colunas obrigatórias ausentes: {', '.join(missing)}")
    _validate_domain(frame, "CLASSI_FIN", CLASSI_FIN_VALUES, year)
    _validate_domain(frame, "EVOLUCAO", EVOLUCAO_VALUES, year)
    _alert_quality(frame, year)


def check_years(frames: Iterable[tuple[int, pd.DataFrame]]) -> None:
    """Valida cada ano separadamente, antes de concatenar ou filtrar a população."""
    for year, frame in frames:
        check_year(frame, year)
