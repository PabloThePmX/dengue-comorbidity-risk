"""Testes unitários das métricas de avaliação, calibração, net benefit e bootstrap (T-2.4)."""

import numpy as np
import pytest

from dengue_sinan.metrics import (
    best_f2_threshold,
    bootstrap_ci,
    brier,
    calibration_slope_intercept,
    net_benefit,
    paired_bootstrap_diff,
    pr_auc,
    roc_auc,
    threshold_metrics,
)


def test_threshold_metrics_f2_known_example() -> None:
    # 4 positivos verdadeiros, 1 falso negativo, 1 falso positivo, 4 negativos verdadeiros
    # Precisão = 4/5 = 0.8; Recall = 4/5 = 0.8 -> F1 = 0.8, F2 = 0.8
    y = np.array([1, 1, 1, 1, 1, 0, 0, 0, 0, 0])
    p = np.array([0.9, 0.8, 0.7, 0.6, 0.2, 0.65, 0.1, 0.1, 0.1, 0.1])
    res = threshold_metrics(y, p, limiar=0.5)
    assert res["precisao"] == pytest.approx(0.8)
    assert res["recall"] == pytest.approx(0.8)
    assert res["f1"] == pytest.approx(0.8)
    assert res["f2"] == pytest.approx(0.8)
    assert res["acuracia"] == pytest.approx(0.8)


def test_pr_auc_perfect_and_constant() -> None:
    y = np.array([0, 0, 0, 1, 1])
    p_perfect = np.array([0.01, 0.02, 0.03, 0.90, 0.95])
    assert pr_auc(y, p_perfect) == pytest.approx(1.0)
    assert roc_auc(y, p_perfect) == pytest.approx(1.0)
    assert brier(y, np.array([0.0, 0.0, 0.0, 1.0, 1.0])) == pytest.approx(0.0)

    p_const = np.full_like(y, 0.2, dtype=float)
    assert pr_auc(y, p_const) == pytest.approx(float(y.mean()))


def test_calibration_slope_and_intercept_on_calibrated_simulation() -> None:
    rng = np.random.default_rng(20261103)
    n = 20_000
    logits = rng.normal(-2.0, 1.2, size=n)
    p = 1.0 / (1.0 + np.exp(-logits))
    y = rng.binomial(1, p)

    slope, intercept = calibration_slope_intercept(y, p)
    assert slope == pytest.approx(1.0, abs=0.08)
    assert intercept == pytest.approx(0.0, abs=0.08)


def test_net_benefit_treat_all_matches_formula() -> None:
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0])  # prev = 0.2
    p = np.array([0.8, 0.7, 0.6, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1])
    pt = 0.25
    nb_df = net_benefit(y, p, [pt])

    prev = 0.2
    expected_treat_all = prev - (1.0 - prev) * (pt / (1.0 - pt))
    # Em pt = 0.25: VP = 2, FP = 1, n = 10 -> NB = 2/10 - (1/10)*(0.25/0.75) = 0.2 - 1/30
    expected_model = 0.2 - 0.1 * (0.25 / 0.75)

    assert nb_df.loc[0, "tratar_todos"] == pytest.approx(expected_treat_all)
    assert nb_df.loc[0, "modelo"] == pytest.approx(expected_model)
    assert nb_df.loc[0, "tratar_ninguem"] == 0.0


def test_best_f2_threshold_and_bootstrap() -> None:
    y = np.array([0, 0, 0, 0, 1, 1] * 10)
    p = np.array([0.05, 0.10, 0.15, 0.20, 0.80, 0.90] * 10)
    th = best_f2_threshold(y, p)
    assert 0.20 < th <= 0.80

    est, lo, hi = bootstrap_ci(pr_auc, y, p, n=50, seed=20261103)
    assert est == pytest.approx(1.0)
    assert lo <= est <= hi


def test_paired_bootstrap_diff_identical_predictions_returns_zero() -> None:
    y = np.array([0, 0, 0, 1, 0, 0, 0, 1])
    p = np.array([0.1, 0.2, 0.3, 0.8, 0.1, 0.2, 0.4, 0.9])
    dobra = np.array(["Sudeste"] * 4 + ["Sul"] * 4)

    diff, ic_inf, ic_sup = paired_bootstrap_diff(pr_auc, y, p, p, dobra, n=50, seed=20261103)
    assert diff == 0.0
    assert ic_inf == 0.0
    assert ic_sup == 0.0
