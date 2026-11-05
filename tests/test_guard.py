import pandas as pd
import pytest

from dengue_sinan.guard import assert_dev_only


def test_dev_guard_accepts_development_years():
    assert_dev_only(pd.DataFrame({"ANO": [2022, 2023]}))


def test_dev_guard_rejects_test_year():
    with pytest.raises(RuntimeError, match="teste congelado"):
        assert_dev_only(pd.DataFrame({"ANO": [2022, 2024]}))
