import logging

import pandas as pd
import pytest

from dengue_sinan.checks import REQUIRED_COLUMNS, check_year


@pytest.fixture
def raw_frame():
    values = {column: ["2"] for column in REQUIRED_COLUMNS}
    values.update({
        "CLASSI_FIN": ["10"],
        "EVOLUCAO": ["1"],
        "CS_SEXO": ["M"],
        "CS_GESTANT": ["1"],
        "SG_UF": ["35"],
        "DT_SIN_PRI": ["20220120"],
        "DT_NOTIFIC": ["20220110"],
    })
    return pd.DataFrame(values)


def test_check_year_blocks_unknown_target_code(raw_frame):
    raw_frame.loc[0, "CLASSI_FIN"] = "1"
    with pytest.raises(ValueError, match="CLASSI_FIN"):
        check_year(raw_frame, 2022)


def test_check_year_logs_alerts_without_failing(raw_frame, caplog):
    with caplog.at_level(logging.WARNING):
        check_year(raw_frame, 2022)
    assert "posterior" in caplog.text
    assert "sexo M" in caplog.text


def test_check_year_blocks_missing_schema(raw_frame):
    with pytest.raises(ValueError, match="colunas obrigatórias"):
        check_year(raw_frame.drop(columns=["DIABETES"]), 2022)
