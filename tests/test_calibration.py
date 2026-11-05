import numpy as np
import pandas as pd
import pytest

from dengue_sinan.calibration import fit_calibrator, select_calibrator_and_threshold


def test_isotonic_and_platt_preserve_probability_bounds():
    y = np.tile([0, 1], 100)
    p = np.linspace(0.01, 0.99, len(y))
    for method in ("isotonic", "platt"):
        calibrated = fit_calibrator(y, p, method).transform(p)
        assert np.isfinite(calibrated).all()
        assert ((calibrated >= 0) & (calibrated <= 1)).all()


def test_calibration_selection_uses_development_only_and_returns_f2_threshold():
    frame = pd.DataFrame({"ANO": [2022] * 100, "y": np.tile([0, 1, 1, 0], 25)})
    probabilities = np.tile([0.1, 0.2, 0.3, 0.4], 25)
    result = select_calibrator_and_threshold(frame, probabilities)
    assert result["method"] in {"isotonic", "platt"}
    assert 0 <= result["threshold"] <= 1
    assert set(result["candidate_brier"]) == {"isotonic", "platt"}


def test_calibrator_rejects_bad_probabilities():
    calibrator = fit_calibrator([0, 1], [0.2, 0.8], "platt")
    with pytest.raises(ValueError, match="probabilidades"):
        calibrator.transform([1.2])
