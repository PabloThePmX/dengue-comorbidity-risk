import logging

import pandas as pd
import pytest

from dengue_sinan.checks import REQUIRED_COLUMNS, check_data


def _valid_data():
    data = {column: ["2"] for column in REQUIRED_COLUMNS}
    data.update(
        {
            "CLASSI_FIN": ["10"],
            "EVOLUCAO": ["1"],
            "DT_SIN_PRI": ["20220101"],
            "DT_NOTIFIC": ["20220102"],
            "CS_SEXO": ["M"],
            "CS_GESTANT": ["1"],
            "SG_UF": ["35"],
        }
    )
    return pd.DataFrame(data)


def test_check_data_rejects_unknown_outcome_code():
    data = _valid_data()
    data.loc[0, "CLASSI_FIN"] = "1"
    with pytest.raises(ValueError, match="domínio inesperado"):
        check_data(data, 2022)


def test_check_data_rejects_missing_column():
    data = _valid_data().drop(columns="LEUCOPENIA")
    with pytest.raises(ValueError, match="colunas obrigatórias ausentes"):
        check_data(data, 2022)


def test_quality_alerts_do_not_stop_processing(caplog):
    data = _valid_data()
    data.loc[0, "DT_SIN_PRI"] = "20220103"
    with caplog.at_level(logging.WARNING):
        check_data(data, 2022)
    assert "posterior a DT_NOTIFIC" in caplog.text