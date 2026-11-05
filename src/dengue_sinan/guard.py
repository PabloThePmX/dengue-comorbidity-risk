"""Proteções contra o uso acidental do teste congelado no desenvolvimento."""

import pandas as pd


def assert_dev_only(frame: pd.DataFrame, test_year: int = 2024) -> None:
    """Recusa dados do ano de teste em operações de treino, tuning e seleção."""
    if "ANO" not in frame:
        raise ValueError("DataFrame precisa da coluna ANO para validar o conjunto de dados")
    years = set(pd.to_numeric(frame["ANO"], errors="coerce").dropna().astype(int).unique())
    if test_year in years:
        raise RuntimeError(f"{test_year} é teste congelado (R1)")
