"""Checks bloqueantes e alertas de qualidade dos microdados SINAN (FR-03, T-2.1)."""

import logging
from collections.abc import Iterable

import pandas as pd

from dengue_sinan.profiling import COMORBIDADES, SINAIS, code, parse_date

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS: tuple[str, ...] = tuple(
    dict.fromkeys(
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
            "ID_MN_RESI",
            "SG_UF",
            *COMORBIDADES,
            *SINAIS,
        ]
    )
)

# Domínios observados no profiling (valores em branco são tratados como NA por `code()`).
CLASSI_FIN_ALLOWED = {"0", "8", "10", "11", "12"}
EVOLUCAO_ALLOWED = {"0", "1", "2", "3", "4", "9"}


def _validate_domain(
    frame: pd.DataFrame,
    column: str,
    allowed: set[str],
    year: int | str,
) -> None:
    """Falha com ValueError se aparecer qualquer código fora do domínio observado no profiling."""
    values = code(frame[column])
    unexpected = sorted(set(values.dropna().unique()) - allowed)
    if unexpected:
        raise ValueError(
            f"Ano {year}: coluna {column} contém valores fora do domínio esperado: {unexpected}"
        )


def _emit_quality_alerts(frame: pd.DataFrame, year: int | str) -> dict[str, int]:
    """Registra alertas não bloqueantes (DT_SIN_PRI > DT_NOTIFIC, gestante M, ignorado > 50%)."""
    onset = parse_date(frame["DT_SIN_PRI"])
    notified = parse_date(frame["DT_NOTIFIC"])
    symptom_after_notif = int((onset.notna() & notified.notna() & (onset > notified)).sum())
    if symptom_after_notif > 0:
        logger.warning(
            "Alerta %s: %d registros com DT_SIN_PRI > DT_NOTIFIC.",
            year,
            symptom_after_notif,
        )

    pregnant = code(frame["CS_GESTANT"]).isin({"1", "2", "3", "4"})
    male_pregnant = int((pregnant & code(frame["CS_SEXO"]).eq("M")).sum())
    if male_pregnant > 0:
        logger.warning(
            "Alerta %s: %d registros de gestante com CS_SEXO = M.",
            year,
            male_pregnant,
        )

    high_ignored_uf_count = 0
    uf = code(frame["SG_UF"]).fillna("<branco>")
    for col in COMORBIDADES:
        vals = code(frame[col])
        ignored = vals.isna() | ~vals.isin({"1", "2"})
        share_by_uf = ignored.groupby(uf, observed=True).mean()
        for uf_code, ratio in share_by_uf[share_by_uf > 0.50].items():
            high_ignored_uf_count += 1
            logger.warning(
                "Alerta %s (UF %s): comorbidade %s tem %.1f%% de ignorado/ausente (> 50%%).",
                year,
                uf_code,
                col,
                ratio * 100.0,
            )

    return {
        "sintomas_apos_notificacao": symptom_after_notif,
        "gestante_sexo_m": male_pregnant,
        "uf_comorbidade_ignorado_acima_50pct": high_ignored_uf_count,
    }


def check_year(frame: pd.DataFrame, year: int | str) -> dict[str, int]:
    """Executa checks bloqueantes e alertas para um ano antes do filtro de população (FR-03)."""
    missing = sorted(set(REQUIRED_COLUMNS) - set(frame.columns))
    if missing:
        raise ValueError(
            f"Ano {year}: colunas obrigatórias ausentes: {', '.join(missing)}"
        )

    _validate_domain(frame, "CLASSI_FIN", CLASSI_FIN_ALLOWED, year)
    _validate_domain(frame, "EVOLUCAO", EVOLUCAO_ALLOWED, year)
    return _emit_quality_alerts(frame, year)


def check_years(frames: Iterable[tuple[int | str, pd.DataFrame]]) -> dict[str, dict[str, int]]:
    """Executa `check_year` para uma sequência de pares (ano, DataFrame)."""
    return {str(year): check_year(frame, year) for year, frame in frames}
