import numpy as np
import pytest

from dengue_sinan.metrics import (
    best_f2_threshold,
    bootstrap_ci,
    brier,
    calibration_slope_intercept,
    fold_bootstrap_ci,
    net_benefit,
    paired_bootstrap_diff,
    pr_auc,
    threshold_metrics,
)


def test_pr_auc_perfect_and_constant_predictors():
    y = np.array([0, 1, 0, 1])
    assert pr_auc(y, [0.1, 0.9, 0.2, 0.8]) == 1
    assert pr_auc(y, np.full(4, 0.5)) == pytest.approx(0.5)


def test_threshold_metrics_f2_matches_hand_calculation():
    result = threshold_metrics([1, 1, 0, 0], [0.9, 0.1, 0.8, 0.1], 0.5)
    assert result["f2"] == pytest.approx(5 * 0.5 * 0.5 / (4 * 0.5 + 0.5))
    assert result["recall"] == 0.5


def test_best_f2_threshold_returns_optimal_candidate():
    assert best_f2_threshold([1, 1, 0, 0], [0.9, 0.8, 0.2, 0.1]) == pytest.approx(0.8)


def test_best_f2_threshold_matches_brute_force_with_tied_probabilities():
    y = np.array([0, 1, 1, 0, 1, 0, 0, 1])
    probability = np.array([0.3, 0.8, 0.3, 0.8, 0.2, 0.3, 0.1, 0.2])
    candidates = np.unique(probability)
    expected = max(
        candidates,
        key=lambda threshold: (
            threshold_metrics(y, probability, threshold)["f2"],
            threshold,
        ),
    )

    assert best_f2_threshold(y, probability) == expected


def test_net_benefit_includes_treat_all_and_none():
    result = net_benefit([1, 0, 0, 0], [0.8, 0.2, 0.1, 0.05], [0.2])
    assert result.loc[0, "tratar_todos"] == pytest.approx(0.25 - 0.75 * 0.2 / 0.8)
    assert result.loc[0, "tratar_ninguem"] == 0


def test_calibration_slope_and_intercept_are_near_ideal():
    rng = np.random.default_rng(42)
    p = np.linspace(0.02, 0.98, 20000)
    y = rng.binomial(1, p)
    metrics = calibration_slope_intercept(y, p)
    assert metrics["slope"] == pytest.approx(1, abs=0.06)
    assert metrics["intercept"] == pytest.approx(0, abs=0.06)


def test_bootstrap_ci_is_reproducible():
    y = np.array([0, 0, 0, 1, 1])
    p = np.array([0.1, 0.3, 0.4, 0.7, 0.9])
    first = bootstrap_ci(pr_auc, y, p, 100, 11)
    assert first == bootstrap_ci(pr_auc, y, p, 100, 11)
    assert first[1] <= first[0] <= first[2]


def test_paired_bootstrap_difference_is_zero_for_identical_predictions():
    y = np.tile([0, 1, 0, 1], 5)
    probability = np.tile([0.1, 0.9, 0.4, 0.7], 5)
    fold = np.repeat(["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"], 4)

    estimate = paired_bootstrap_diff(pr_auc, y, probability, probability, fold, 20, 7)

    assert estimate == (0.0, 0.0, 0.0)


def test_fold_bootstrap_ci_uses_mean_fold_metric():
    y = np.tile([0, 1, 0, 1], 5)
    probability = np.tile([0.1, 0.9, 0.4, 0.7], 5)
    fold = np.repeat(["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"], 4)

    estimate = fold_bootstrap_ci(pr_auc, y, probability, fold, 20, 7)

    assert estimate[0] == 1
    assert estimate[1] <= estimate[0] <= estimate[2]


def test_probability_validation_rejects_bad_inputs():
    with pytest.raises(ValueError, match="probabilidades finitas"):
        brier([0, 1], [0.1, float("nan")])