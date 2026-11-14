"""Testes dos checks bloqueantes e alertas de qualidade (FR-03, T-2.1)."""

import logging

import pandas as pd
import pytest

from dengue_sinan.checks import REQUIRED_COLUMNS, check_year


@pytest.fixture
def synthetic_raw_df() -> pd.DataFrame:
    data = {col: ["2", "2"] for col in REQUIRED_COLUMNS}
    data.update(
        {
            "CLASSI_FIN": ["10", "12"],
            "EVOLUCAO": ["1", "2"],
            "NU_IDADE_N": ["4035", "33"],
            "ANO_NASC": ["1987", "1989"],
            "DT_SIN_PRI": ["20220110", "20220115"],
            "DT_NOTIFIC": ["20220112", "20220116"],
            "CS_SEXO": ["F", "M"],
            "CS_GESTANT": ["5", "6"],
            "CS_RACA": ["1", "4"],
            "ID_MN_RESI": ["355030", "320530"],
            "SG_UF": ["35", "32"],
        }
    )
    return pd.DataFrame(data)


def test_blocking_check_fails_on_invalid_classi_fin(synthetic_raw_df: pd.DataFrame) -> None:
    synthetic_raw_df.loc[0, "CLASSI_FIN"] = "1"
    with pytest.raises(ValueError, match="CLASSI_FIN"):
        check_year(synthetic_raw_df, 2022)


def test_blocking_check_fails_on_invalid_evolucao(synthetic_raw_df: pd.DataFrame) -> None:
    synthetic_raw_df.loc[0, "EVOLUCAO"] = "5"
    with pytest.raises(ValueError, match="EVOLUCAO"):
        check_year(synthetic_raw_df, 2022)


def test_blocking_check_fails_on_missing_column(synthetic_raw_df: pd.DataFrame) -> None:
    with pytest.raises(ValueError, match="colunas obrigatórias ausentes"):
        check_year(synthetic_raw_df.drop(columns=["DIABETES"]), 2022)


def test_alerts_do_not_interrupt_and_invalid_age_is_not_blocking(
    synthetic_raw_df: pd.DataFrame,
    caplog: pytest.LogCaptureFixture,
) -> None:
    # DT_SIN_PRI > DT_NOTIFIC, gestante com sexo M, >50% ignorado em DIABETES na UF 35,
    # e código de idade inválido ("9999").
    synthetic_raw_df.loc[0, "DT_SIN_PRI"] = "20220120"
    synthetic_raw_df.loc[0, "DT_NOTIFIC"] = "20220110"
    synthetic_raw_df.loc[1, "CS_SEXO"] = "M"
    synthetic_raw_df.loc[1, "CS_GESTANT"] = "2"
    synthetic_raw_df.loc[0, "DIABETES"] = "9"
    synthetic_raw_df.loc[0, "NU_IDADE_N"] = "9999"

    with caplog.at_level(logging.WARNING):
        alerts = check_year(synthetic_raw_df, 2022)

    assert alerts["sintomas_apos_notificacao"] == 1
    assert alerts["gestante_sexo_m"] == 1
    assert alerts["uf_comorbidade_ignorado_acima_50pct"] >= 1
    assert "DT_SIN_PRI > DT_NOTIFIC" in caplog.text
    assert "CS_SEXO = M" in caplog.text
