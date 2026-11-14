"""Testes da guarda contra leitura/uso do ano de teste 2024 (T-2.2, R1)."""

import pandas as pd
import pytest

from dengue_sinan.guard import assert_dev_only, assert_dev_years


def test_assert_dev_only_passes_with_2022_and_2023() -> None:
    df = pd.DataFrame({"ANO": [2022, 2023, 2022], "y": [0, 1, 0]})
    assert_dev_only(df)


def test_assert_dev_only_fails_with_2024() -> None:
    df = pd.DataFrame({"ANO": [2022, 2023, 2024], "y": [0, 1, 0]})
    with pytest.raises(RuntimeError, match=r"2024 é teste congelado \(R1\)"):
        assert_dev_only(df)


def test_assert_dev_years_fails_with_2024() -> None:
    with pytest.raises(RuntimeError, match=r"2024 é teste congelado \(R1\)"):
        assert_dev_years([2022, 2024])
