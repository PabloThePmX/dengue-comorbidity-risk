import numpy as np
import pandas as pd
import pytest

from dengue_sinan.folds import (
    REGIONS,
    inner_split,
    load_folds,
    loro_folds,
    save_folds,
    verify_and_save_folds,
)


def _region_frame():
    return pd.DataFrame(
        {
            "ANO": [2022] * 10,
            "regiao": np.repeat(REGIONS, 2),
            "y": [0, 1] * 5,
        }
    )


def test_loro_folds_partition_each_row_once():
    df = _region_frame()
    folds = loro_folds(df)
    assert len(folds) == 5
    validation_indices = []
    for region, train, validation in folds:
        assert not set(train) & set(validation)
        assert set(df.iloc[validation]["regiao"]) == {region}
        validation_indices.extend(validation)
    assert sorted(validation_indices) == list(range(len(df)))


def test_loro_folds_rejects_missing_region():
    df = _region_frame()
    df.loc[0, "regiao"] = None
    with pytest.raises(ValueError, match="sem região"):
        loro_folds(df)


def test_inner_split_preserves_stratification_and_indices():
    y = np.tile([0, 1], 5000)
    train, stopping = inner_split(np.arange(len(y)), y, 0.1, 42)
    assert not set(train) & set(stopping)
    assert len(train) + len(stopping) == len(y)
    assert abs(y[train].mean() - y[stopping].mean()) < 0.0001


def test_saved_folds_round_trip_and_reject_changed_population(tmp_path):
    df = _region_frame()
    order = ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"]
    path, saved_hash = save_folds(df, tmp_path / "folds", order)

    folds, loaded_hash = load_folds(df, path, order)

    assert saved_hash == loaded_hash
    assert [region for region, _, _ in folds] == order
    assert all(len(validation) > 0 for _, _, validation in folds)
    reordered = df.iloc[::-1].reset_index(drop=True)
    with pytest.raises(ValueError, match="não correspondem"):
        load_folds(reordered, path, order)


def test_verify_and_save_folds_writes_hash_and_region_event_checks(tmp_path, monkeypatch):
    import dengue_sinan.verify as verify

    monkeypatch.setattr(verify, "_commit", lambda: "test-commit")
    monkeypatch.setattr(
        verify,
        "_hardware",
        lambda: {"gpu": "CPU", "cpu_count": 1, "ram_gib": 8.0},
    )
    df = _region_frame()
    expected_events = {
        region: int(df.loc[df["regiao"] == region, "y"].sum()) for region in REGIONS
    }

    path, digest, checks = verify_and_save_folds(
        df, tmp_path / "m1" / "dobras.npz", tmp_path / "reports", expected_events
    )

    report_path = tmp_path / "reports" / "verificacao" / "T-2.3.json"
    assert path.is_file()
    assert digest
    assert all(check["passou"] for check in checks)
    assert report_path.is_file()