"""Transformações de campos do SINAN em variáveis analisáveis."""

import numpy as np
import pandas as pd

# NU_IDADE_N: 1º dígito = unidade, 3 dígitos seguintes = valor (dicionário NINDIN, §3.7 do spec).
_AGE_UNIT_TO_YEARS = {
    1: 1 / 24 / 365.25,  # horas
    2: 1 / 365.25,  # dias
    3: 1 / 12,  # meses
    4: 1.0,  # anos
}

# 1º dígito do código IBGE de UF/município → macrorregião.
_IBGE_REGION = {
    "1": "Norte",
    "2": "Nordeste",
    "3": "Sudeste",
    "4": "Sul",
    "5": "Centro-Oeste",
}


def _as_code_string(series: pd.Series) -> pd.Series:
    """Normaliza códigos que chegam como int, float ("4018.0") ou texto."""
    text = series.astype("string").str.strip()
    return text.str.replace(r"\.0$", "", regex=True)


def decode_age_years(nu_idade_n: pd.Series) -> pd.Series:
    """Converte NU_IDADE_N para anos fracionários; códigos inválidos viram NaN."""
    code = _as_code_string(nu_idade_n)
    valid = code.str.fullmatch(r"[1-4]\d{3}").fillna(False).astype(bool)
    unit = pd.to_numeric(code.where(valid).str[0], errors="coerce")
    value = pd.to_numeric(code.where(valid).str[1:], errors="coerce")
    factor = unit.map(_AGE_UNIT_TO_YEARS)
    return (value * factor).astype("float64").where(valid, np.nan)


def region_from_ibge(code: pd.Series) -> pd.Series:
    """Macrorregião a partir do código IBGE de UF (2 dígitos) ou município (6–7 dígitos)."""
    text = _as_code_string(code)
    well_formed = text.str.fullmatch(r"[1-5]\d(\d{4,5})?").fillna(False).astype(bool)
    return text.where(well_formed).str[0].map(_IBGE_REGION)
