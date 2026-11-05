import numpy as np
import pandas as pd
import pytest

from dengue_sinan.folds import REGIONS, inner_split, loro_folds


def test_loro_folds_leave_out_one_region_and_cover_all_rows():
    frame = pd.DataFrame({"regiao": np.repeat(REGIONS, 4)})
    folds = loro_folds(frame)
    assert len(folds) == 5
    validation = []
    for region, train_idx, valid_idx in folds:
        assert set(frame.iloc[valid_idx]["regiao"]) == {region}
        assert not set(train_idx) & set(valid_idx)
        validation.extend(valid_idx)
    assert sorted(validation) == list(range(len(frame)))


def test_loro_rejects_missing_regions_and_nulls():
    with pytest.raises(ValueError, match="regiao nula"):
        loro_folds(pd.DataFrame({"regiao": [None]}))
    with pytest.raises(ValueError, match="sem observações"):
        loro_folds(pd.DataFrame({"regiao": list(REGIONS[:-1])}))


def test_inner_split_is_stratified_and_reproducible():
    y = np.tile([0, 1], 500)
    indices = np.arange(len(y))
    fit, stopping = inner_split(indices, y, 0.1, 20261103)
    assert not set(fit) & set(stopping)
    assert len(fit) + len(stopping) == len(indices)
    assert abs(y[fit].mean() - y[stopping].mean()) < 0.01
    assert np.array_equal(stopping, inner_split(indices, y, 0.1, 20261103)[1])
