"""Métricas de avaliação, calibração, curva de decisão e bootstrap (T-2.4, §3.12, D-53)."""

from collections.abc import Callable
from typing import NamedTuple

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    fbeta_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)

_EPS = 1e-7


class CalibrationSlopeIntercept(NamedTuple):
    """Resultado de calibração suportando `(slope, intercept)` e `res['slope']`."""

    slope: float
    intercept: float

    def __getitem__(self, key: int | str) -> float:  # type: ignore[override]
        if isinstance(key, str):
            if key == "slope":
                return self.slope
            if key == "intercept":
                return self.intercept
            raise KeyError(key)
        return tuple.__getitem__(self, key)


def _as_1d_float(arr: pd.Series | np.ndarray | list[float]) -> np.ndarray:
    return np.asarray(arr, dtype=np.float64).ravel()


def pr_auc(y: pd.Series | np.ndarray, p: pd.Series | np.ndarray) -> float:
    """Área sob a curva Precisão-Recall (`average_precision_score`)."""
    y_arr, p_arr = _as_1d_float(y), _as_1d_float(p)
    if np.all(p_arr == p_arr[0]):
        return float(np.mean(y_arr))
    return float(average_precision_score(y_arr, p_arr))


def roc_auc(y: pd.Series | np.ndarray, p: pd.Series | np.ndarray) -> float:
    """Área sob a curva ROC."""
    y_arr, p_arr = _as_1d_float(y), _as_1d_float(p)
    if len(np.unique(y_arr)) < 2:
        return float("nan")
    return float(roc_auc_score(y_arr, p_arr))


def brier(y: pd.Series | np.ndarray, p: pd.Series | np.ndarray) -> float:
    """Brier score (erro quadrático médio das probabilidades)."""
    return float(brier_score_loss(_as_1d_float(y), _as_1d_float(p)))


def calibration_slope_intercept(
    y: pd.Series | np.ndarray,
    p: pd.Series | np.ndarray,
) -> CalibrationSlopeIntercept:
    """Calcula calibration slope e calibration-in-the-large (intercept com offset) via GLM."""
    y_arr = _as_1d_float(y)
    p_clip = np.clip(_as_1d_float(p), _EPS, 1.0 - _EPS)
    logit_p = np.log(p_clip / (1.0 - p_clip))

    # Calibration-in-the-large: y ~ 1 + offset(logit(p))
    ones = np.ones((len(y_arr), 1), dtype=np.float64)
    glm_int = sm.GLM(y_arr, ones, family=sm.families.Binomial(), offset=logit_p)
    res_int = glm_int.fit(disp=False)
    intercept = float(res_int.params[0])

    # Calibration slope: y ~ 1 + logit(p)
    if np.allclose(logit_p, logit_p[0]):
        slope = 0.0
    else:
        design = sm.add_constant(logit_p, has_constant="add")
        glm_slope = sm.GLM(y_arr, design, family=sm.families.Binomial())
        res_slope = glm_slope.fit(disp=False)
        slope = float(res_slope.params[1])

    return CalibrationSlopeIntercept(slope=slope, intercept=intercept)


def threshold_metrics(
    y: pd.Series | np.ndarray,
    p: pd.Series | np.ndarray,
    limiar: float,
) -> dict[str, float]:
    """Calcula acurácia, precisão, recall, F1 e F2 para `p >= limiar`."""
    y_true = _as_1d_float(y).astype(np.int8)
    y_pred = (_as_1d_float(p) >= float(limiar)).astype(np.int8)
    return {
        "limiar": float(limiar),
        "acuracia": float(accuracy_score(y_true, y_pred)),
        "precisao": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "f2": float(fbeta_score(y_true, y_pred, beta=2.0, zero_division=0)),
    }


def best_f2_threshold(
    y: pd.Series | np.ndarray,
    p: pd.Series | np.ndarray,
) -> float:
    """Encontra o limiar em `p` que maximiza a métrica F2 (D-33)."""
    y_arr = _as_1d_float(y).astype(np.int8)
    p_arr = _as_1d_float(p)
    precisions, recalls, thresholds = precision_recall_curve(y_arr, p_arr)
    if len(thresholds) == 0:
        return float(p_arr[0]) if len(p_arr) else 0.5

    # precision_recall_curve devolve len(thresholds) + 1 pontos; os primeiros batem com limiares
    p_vals = precisions[:-1]
    r_vals = recalls[:-1]
    denom = 4.0 * p_vals + r_vals
    f2_scores = np.where(denom > 0, (5.0 * p_vals * r_vals) / denom, 0.0)
    best_idx = int(np.argmax(f2_scores))
    return float(thresholds[best_idx])


def net_benefit(
    y: pd.Series | np.ndarray,
    p: pd.Series | np.ndarray,
    limiares: np.ndarray | list[float],
) -> pd.DataFrame:
    """Calcula a curva de decisão (net benefit): NB = VP/n − FP/n × (pt / (1 − pt))."""
    y_arr = _as_1d_float(y).astype(bool)
    p_arr = _as_1d_float(p)
    n = float(len(y_arr))
    prev = float(y_arr.mean())

    rows: list[dict[str, float]] = []
    for pt in np.asarray(limiares, dtype=np.float64):
        odds = pt / (1.0 - pt)
        pred_pos = p_arr >= pt
        vp = float(np.sum(pred_pos & y_arr))
        fp = float(np.sum(pred_pos & ~y_arr))
        nb_model = (vp / n) - (fp / n) * odds
        nb_all = prev - (1.0 - prev) * odds
        rows.append(
            {
                "limiar": float(pt),
                "modelo": float(nb_model),
                "tratar_todos": float(nb_all),
                "tratar_ninguem": 0.0,
            }
        )
    return pd.DataFrame(rows)


def _is_pr_auc_fn(fn: Callable[[np.ndarray, np.ndarray], float]) -> bool:
    """Verifica se a métrica passada ao bootstrap é `pr_auc` (`average_precision_score`)."""
    return fn is pr_auc or getattr(fn, "__name__", "") == "pr_auc"


def _fast_pr_auc_bootstrap_samples(
    y_arr: np.ndarray,
    p_arr: np.ndarray,
    n: int,
    seed: int,
) -> np.ndarray:
    """Calcula `n` reamostras bootstrap estratificadas de `pr_auc` sem reordenar `N` linhas.

    Usa a identidade exata da Average Precision não-interpolada: `ΔRecall` só é não-nulo nos
    limiares distintos dos casos positivos (`K <= n_pos`), reduzindo a complexidade de
    `O(n * N log N)` para `O(N log K + n * K)`.
    """
    n_boot = int(n)
    if n_boot <= 0:
        return np.empty(0, dtype=np.float64)

    n_total = len(y_arr)
    if n_total == 0:
        return np.zeros(n_boot, dtype=np.float64)

    pos_idx = np.flatnonzero(y_arr == 1)
    neg_idx = np.flatnonzero(y_arr == 0)
    n_pos = len(pos_idx)
    n_neg = len(neg_idx)

    if n_pos == 0 or n_neg == 0 or np.all(p_arr == p_arr[0]):
        return np.full(n_boot, float(np.mean(y_arr)), dtype=np.float64)

    p_pos = p_arr[pos_idx]
    p_neg = p_arr[neg_idx]

    # Limiares distintos dos positivos em ordem decrescente (via -p_pos crescente)
    neg_uniq_t, pos_bucket = np.unique(-p_pos, return_inverse=True)
    k_bins = len(neg_uniq_t)

    # Cada negativo cai no 1º limiar k tal que p_neg >= t_k (isto é, -p_neg <= -t_k)
    neg_bucket = np.searchsorted(neg_uniq_t, -p_neg, side="left")
    neg_counts = np.bincount(neg_bucket, minlength=k_bins + 1)
    neg_probs = neg_counts / float(n_neg)

    rng_pos = np.random.default_rng(int(seed))
    rng_neg = np.random.default_rng(int(seed) + 1_000_003)

    samples = np.empty(n_boot, dtype=np.float64)
    chunk_size = 250
    for start in range(0, n_boot, chunk_size):
        end = min(n_boot, start + chunk_size)
        m_chunk = end - start

        tp_bins = np.empty((m_chunk, k_bins), dtype=np.float64)
        for i in range(m_chunk):
            b_pos = rng_pos.integers(0, n_pos, size=n_pos)
            tp_bins[i] = np.bincount(pos_bucket[b_pos], minlength=k_bins)

        fp_bins = rng_neg.multinomial(n_neg, neg_probs, size=m_chunk)[:, :k_bins].astype(
            np.float64
        )
        tp_cum = np.cumsum(tp_bins, axis=1)
        fp_cum = np.cumsum(fp_bins, axis=1)

        prec = tp_cum / np.maximum(1.0, tp_cum + fp_cum)
        rec = tp_cum / float(n_pos)
        d_rec = np.diff(rec, axis=1, prepend=0.0)
        samples[start:end] = np.sum(d_rec * prec, axis=1)

    return samples


def fast_pr_auc_fold_bootstrap_means(
    y: pd.Series | np.ndarray,
    p: pd.Series | np.ndarray,
    dobra: pd.Series | np.ndarray,
    n: int = 1000,
    seed: int = 20261103,
) -> tuple[dict[str, float], np.ndarray]:
    """Devolve `(pr_auc_por_dobra, medias_bootstrap)` com sorteios pareados por `seed`."""
    y_arr = _as_1d_float(y).astype(np.int8)
    p_arr = _as_1d_float(p)
    fold_arr = np.asarray(dobra).astype(str)
    unique_folds = list(dict.fromkeys(fold_arr))

    fold_obs: dict[str, float] = {}
    boot_sum = np.zeros(int(n), dtype=np.float64)

    for f_idx, f_name in enumerate(unique_folds):
        in_fold = fold_arr == f_name
        y_f = y_arr[in_fold]
        p_f = p_arr[in_fold]
        fold_obs[f_name] = pr_auc(y_f, p_f)
        fold_seed = int(seed) + f_idx * 10_007
        boot_sum += _fast_pr_auc_bootstrap_samples(y_f, p_f, int(n), fold_seed)

    n_folds = max(1, len(unique_folds))
    return fold_obs, boot_sum / float(n_folds)


def bootstrap_ci(
    fn: Callable[[np.ndarray, np.ndarray], float],
    y: pd.Series | np.ndarray,
    p: pd.Series | np.ndarray,
    n: int = 1000,
    seed: int = 20261103,
) -> tuple[float, float, float]:
    """IC 95% por bootstrap estratificado pelo alvo: devolve `(estimativa, ic_inf, ic_sup)`."""
    y_arr = _as_1d_float(y).astype(np.int8)
    p_arr = _as_1d_float(p)
    estimate = float(fn(y_arr, p_arr))

    if _is_pr_auc_fn(fn):
        samples = _fast_pr_auc_bootstrap_samples(y_arr, p_arr, int(n), int(seed))
        ic_inf, ic_sup = np.percentile(samples, [2.5, 97.5])
        return estimate, float(ic_inf), float(ic_sup)

    idx_pos = np.flatnonzero(y_arr == 1)
    idx_neg = np.flatnonzero(y_arr == 0)
    rng = np.random.default_rng(int(seed))

    samples = np.empty(int(n), dtype=np.float64)
    for i in range(int(n)):
        boot_pos = rng.choice(idx_pos, size=len(idx_pos), replace=True) if len(idx_pos) else idx_pos
        boot_neg = rng.choice(idx_neg, size=len(idx_neg), replace=True) if len(idx_neg) else idx_neg
        boot_idx = np.concatenate([boot_pos, boot_neg])
        samples[i] = float(fn(y_arr[boot_idx], p_arr[boot_idx]))

    ic_inf, ic_sup = np.percentile(samples, [2.5, 97.5])
    return estimate, float(ic_inf), float(ic_sup)


def paired_bootstrap_diff(
    fn: Callable[[np.ndarray, np.ndarray], float],
    y: pd.Series | np.ndarray,
    p_a: pd.Series | np.ndarray,
    p_b: pd.Series | np.ndarray,
    dobra: pd.Series | np.ndarray,
    n: int = 1000,
    seed: int = 20261103,
) -> tuple[float, float, float]:
    """Diferença pareada de `fn` média entre as dobras com IC 95% bootstrap estratificado (D-53)."""
    y_arr = _as_1d_float(y).astype(np.int8)
    pa_arr = _as_1d_float(p_a)
    pb_arr = _as_1d_float(p_b)
    fold_arr = np.asarray(dobra).astype(str)
    unique_folds = list(dict.fromkeys(fold_arr))

    if _is_pr_auc_fn(fn):
        obs_a, boot_a = fast_pr_auc_fold_bootstrap_means(
            y_arr, pa_arr, fold_arr, n=int(n), seed=seed
        )
        obs_b, boot_b = fast_pr_auc_fold_bootstrap_means(
            y_arr, pb_arr, fold_arr, n=int(n), seed=seed
        )
        point_diff = float(np.mean([obs_a[f] - obs_b[f] for f in unique_folds]))
        if np.array_equal(pa_arr, pb_arr):
            return 0.0, 0.0, 0.0
        boot_diffs = boot_a - boot_b
        ic_inf, ic_sup = np.percentile(boot_diffs, [2.5, 97.5])
        return point_diff, float(ic_inf), float(ic_sup)

    # Estimativa pontual observada: média nas dobras de A menos média nas dobras de B
    fold_diffs_obs: list[float] = []
    strata_by_fold: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for f_name in unique_folds:
        in_fold = fold_arr == f_name
        idx_pos = np.flatnonzero(in_fold & (y_arr == 1))
        idx_neg = np.flatnonzero(in_fold & (y_arr == 0))
        strata_by_fold[f_name] = (idx_pos, idx_neg)
        score_a = float(fn(y_arr[in_fold], pa_arr[in_fold]))
        score_b = float(fn(y_arr[in_fold], pb_arr[in_fold]))
        fold_diffs_obs.append(score_a - score_b)

    point_diff = float(np.mean(fold_diffs_obs))
    if np.array_equal(pa_arr, pb_arr):
        return 0.0, 0.0, 0.0

    rng = np.random.default_rng(int(seed))
    boot_diffs = np.empty(int(n), dtype=np.float64)

    for i in range(int(n)):
        diffs_iter: list[float] = []
        for f_name in unique_folds:
            idx_pos, idx_neg = strata_by_fold[f_name]
            b_pos = (
                rng.choice(idx_pos, size=len(idx_pos), replace=True)
                if len(idx_pos)
                else idx_pos
            )
            b_neg = (
                rng.choice(idx_neg, size=len(idx_neg), replace=True)
                if len(idx_neg)
                else idx_neg
            )
            b_idx = np.concatenate([b_pos, b_neg])
            sa = float(fn(y_arr[b_idx], pa_arr[b_idx]))
            sb = float(fn(y_arr[b_idx], pb_arr[b_idx]))
            diffs_iter.append(sa - sb)
        boot_diffs[i] = float(np.mean(diffs_iter))

    ic_inf, ic_sup = np.percentile(boot_diffs, [2.5, 97.5])
    return point_diff, float(ic_inf), float(ic_sup)
