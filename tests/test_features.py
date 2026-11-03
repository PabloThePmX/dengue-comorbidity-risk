import math

import pandas as pd
import pytest

from dengue_sinan.features import decode_age_years, region_from_ibge


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        (1005, 5 / 24 / 365.25),  # 5 horas
        (2010, 10 / 365.25),  # 10 dias
        (3009, 9 / 12),  # 9 meses
        (4018, 18.0),  # 18 anos
        (4000, 0.0),  # 0 anos
        ("4018", 18.0),  # texto
        (4018.0, 18.0),  # float vindo do Parquet
    ],
)
def test_decode_age_valid_units(code, expected):
    result = decode_age_years(pd.Series([code]))
    assert result.iloc[0] == pytest.approx(expected)


@pytest.mark.parametrize("code", [None, "", "abc", 5018, 18, 40180, -4018, "4 18"])
def test_decode_age_invalid_returns_nan(code):
    result = decode_age_years(pd.Series([code], dtype=object))
    assert math.isnan(result.iloc[0])


def test_decode_age_keeps_index_and_length():
    s = pd.Series([4018, None, 3009], index=[10, 20, 30])
    result = decode_age_years(s)
    assert list(result.index) == [10, 20, 30]
    assert result.dtype == "float64"


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("110020", "Norte"),  # Porto Velho/RO
        ("230440", "Nordeste"),  # Fortaleza/CE
        ("355030", "Sudeste"),  # São Paulo/SP
        ("431490", "Sul"),  # Porto Alegre/RS
        ("530010", "Centro-Oeste"),  # Brasília/DF
        (35, "Sudeste"),  # código de UF
        ("35", "Sudeste"),
        (None, None),
        ("", None),
        ("999999", None),
    ],
)
def test_region_from_ibge(code, expected):
    result = region_from_ibge(pd.Series([code], dtype=object))
    value = result.iloc[0]
    assert (value is None or pd.isna(value)) if expected is None else value == expected
