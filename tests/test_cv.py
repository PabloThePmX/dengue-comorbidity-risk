import numpy as np
import pytest
from test_baselines import _development_frame

from dengue_sinan.cv import run_loro


def test_random_forest_loro_returns_one_oof_prediction_per_record():
    frame = _development_frame()
    result = run_loro(
        {"seed": 20261103, "ano_teste": 2024},
        "random_forest",
        {"n_estimators": 10, "min_samples_leaf": 2, "max_features": "sqrt"},
        frame,
    )
    assert len(result["oof"]) == len(frame)
    assert np.isfinite(result["oof"]).all()
    assert set(result["best_points"]) == {
        "Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul",
    }


def test_cv_refuses_the_frozen_test_year():
    frame = _development_frame()
    frame.loc[0, "ANO"] = 2024
    with pytest.raises(RuntimeError, match="teste congelado"):
        run_loro({"seed": 1, "ano_teste": 2024}, "random_forest", {}, frame)


def test_cv_rejects_class_imbalance_parameters():
    with pytest.raises(ValueError, match="R3"):
        run_loro(
            {"seed": 1, "ano_teste": 2024},
            "random_forest",
            {"n_estimators": 5, "class_weight": "balanced"},
            _development_frame(),
        )
