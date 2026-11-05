import numpy as np
import pytest

from dengue_sinan.metrics import (
    best_f2_threshold,
    bootstrap_ci,
    brier,
    calibration_slope_intercept,
    net_benefit,
    pr_auc,
    threshold_metrics,
)


def test_pr_auc_perfect_and_constant_predictors():
    y = np.array([0, 0, 1, 1])
    assert pr_auc(y, [0.1, 0.2, 0.8, 0.9]) == 1
    assert pr_auc(y, [0.5] * 4) == pytest.approx(y.mean())


def test_threshold_metrics_and_best_f2():
    y = [1, 1, 0, 0]
    p = [0.9, 0.4, 0.3, 0.1]
    metrics = threshold_metrics(y, p, 0.5)
    assert metrics["recall"] == 0.5
    assert metrics["f2"] == pytest.approx(5 / 9)
    assert best_f2_threshold(y, p) == pytest.approx(0.4)


def test_brier_score():
    assert brier([0, 1], [0.2, 0.8]) == pytest.approx(0.04)


def test_calibration_slope_and_intercept_for_calibrated_probabilities():
    probabilities = np.repeat([0.2, 0.5, 0.8], 50)
    labels = np.concatenate([
        np.tile([1, 0, 0, 0, 0], 10),
        np.tile([1, 0], 25),
        np.tile([1, 1, 1, 1, 0], 10),
    ])
    slope, intercept = calibration_slope_intercept(labels, probabilities)
    assert slope == pytest.approx(1, abs=1e-8)
    assert intercept == pytest.approx(0, abs=1e-8)


def test_calibration_slope_is_undefined_for_constant_probabilities():
    slope, intercept = calibration_slope_intercept([0, 0, 1, 1], [0.5] * 4)
    assert np.isnan(slope)
    assert intercept == pytest.approx(0)


def test_bootstrap_ci_is_reproducible_and_stratified():
    estimate = bootstrap_ci(brier, [0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9], 30, 42)
    repeated = bootstrap_ci(brier, [0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9], 30, 42)
    assert estimate == repeated
    assert estimate[1] <= estimate[0] <= estimate[2]


def test_net_benefit_matches_treat_all_formula():
    result = net_benefit([1, 0, 0, 0], [0.8, 0.2, 0.1, 0.1], [0.5])
    assert result.loc[0, "tratar_todos"] == pytest.approx(0.25 - 0.75)
    assert result.loc[0, "tratar_ninguem"] == 0
    assert result.loc[0, "modelo"] == pytest.approx(0.25)
