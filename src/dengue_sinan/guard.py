"""Proteções para impedir o uso prematuro do conjunto de teste."""

import pandas as pd


def assert_dev_only(df: pd.DataFrame) -> None:
    """Bloqueia dados do ano de teste em funções de desenvolvimento."""
    if "ANO" not in df:
        raise ValueError("DataFrame deve conter a coluna ANO para validar o split.")
    if pd.to_numeric(df["ANO"], errors="coerce").eq(2024).any():
        raise RuntimeError("2024 é teste congelado (R1)")