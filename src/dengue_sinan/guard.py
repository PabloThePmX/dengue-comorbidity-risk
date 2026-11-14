"""Guarda contra leitura ou uso do conjunto de teste congelado (2024) antes da T-5.1 (R1)."""

from collections.abc import Iterable

import pandas as pd

TEST_YEAR = 2024


def assert_dev_years(anos: Iterable[int | str], ano_teste: int = TEST_YEAR) -> None:
    """Levanta RuntimeError se a lista de anos contiver o ano de teste congelado (R1)."""
    normalized = {int(str(a).strip()) for a in anos}
    if int(ano_teste) in normalized:
        raise RuntimeError("2024 é teste congelado (R1)")


def assert_dev_only(df: pd.DataFrame, ano_teste: int = TEST_YEAR) -> None:
    """Levanta RuntimeError se `df['ANO']` contiver o ano de teste congelado (R1)."""
    if "ANO" not in df.columns:
        raise ValueError("DataFrame não possui a coluna 'ANO' necessária para verificar R1.")
    anos = pd.to_numeric(df["ANO"].astype("string").str.strip(), errors="coerce")
    if (anos == int(ano_teste)).any():
        raise RuntimeError("2024 é teste congelado (R1)")
