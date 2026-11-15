"""Testes das dobras leave-one-region-out e validação interna (T-2.3, D-53, R6)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dengue_sinan.folds import DEFAULT_FOLD_ORDER, inner_split, load_folds, loro_folds, save_folds


@pytest.fixture
def synthetic_dev_df() -> pd.DataFrame:
    rng = np.random.default_rng(20261103)
    regioes = np.repeat(DEFAULT_FOLD_ORDER, 400)
    y = rng.binomial(1, 0.05, size=len(regioes))
    return pd.DataFrame(
        {
            "ANO": 2022,
            "regiao": regioes,
            "y": y,
        }
    )


def test_loro_folds_order_disjoint_and_complete(synthetic_dev_df: pd.DataFrame) -> None:
    folds = loro_folds(synthetic_dev_df)
    assert len(folds) == 5
    assert [reg for reg, _, _ in folds] == DEFAULT_FOLD_ORDER

    all_val_indices: list[np.ndarray] = []
    for regiao, idx_train, idx_val in folds:
        # Nenhuma interseção treino/validação
        assert len(np.intersect1d(idx_train, idx_val)) == 0
        # União cobre todas as linhas
        assert len(idx_train) + len(idx_val) == len(synthetic_dev_df)
        # Validação contém apenas a região deixada de fora
        val_regions = set(synthetic_dev_df.iloc[idx_val]["regiao"].unique())
        assert val_regions == {regiao}
        all_val_indices.append(idx_val)

    # Cada linha aparece em exatamente uma validação
    combined_val = np.sort(np.concatenate(all_val_indices))
    assert np.array_equal(combined_val, np.arange(len(synthetic_dev_df)))


def test_loro_folds_rejects_null_region(synthetic_dev_df: pd.DataFrame) -> None:
    bad = synthetic_dev_df.copy()
    bad.loc[0, "regiao"] = None
    with pytest.raises(ValueError, match="PARE E PERGUNTE"):
        loro_folds(bad)


def test_inner_split_preserves_prevalence() -> None:
    rng = np.random.default_rng(42)
    n = 50_000
    y = np.zeros(n, dtype=np.int8)
    y[:1000] = 1  # prevalência exata de 2.00%
    rng.shuffle(y)
    idx_train = np.arange(n)

    idx_fit, idx_val = inner_split(idx_train, y, frac=0.10, seed=20261103)
    assert len(np.intersect1d(idx_fit, idx_val)) == 0
    assert len(idx_fit) + len(idx_val) == n
    diff_pp = abs(float(y[idx_fit].mean()) - float(y[idx_val].mean())) * 100.0
    assert diff_pp < 0.01


def test_save_and_load_folds_checks_sha256(
    synthetic_dev_df: pd.DataFrame,
    tmp_path: Path,
) -> None:
    cfg = {
        "seed": 20261103,
        "validacao_interna_frac": 0.10,
        "ordem_dobras": DEFAULT_FOLD_ORDER,
    }
    fold_file = tmp_path / "folds.parquet"
    sha = save_folds(cfg, synthetic_dev_df, fold_file)
    assert len(sha) == 64

    loaded = load_folds(fold_file, sha)
    assert len(loaded) == len(synthetic_dev_df)
    assert "dobra_validacao" in loaded.columns

    with pytest.raises(ValueError, match="difere do esperado"):
        load_folds(fold_file, "0" * 64)
