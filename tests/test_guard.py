import pandas as pd
import pytest

from dengue_sinan.guard import assert_dev_only


def test_assert_dev_only_accepts_development_years():
    assert_dev_only(pd.DataFrame({"ANO": [2022, 2023]}))


def test_assert_dev_only_rejects_test_year():
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        assert_dev_only(pd.DataFrame({"ANO": [2023, 2024]}))


def test_assert_dev_only_requires_year_column():
    with pytest.raises(ValueError, match="coluna ANO"):
        assert_dev_only(pd.DataFrame({"y": [0]}))