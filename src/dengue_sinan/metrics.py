"""Métricas de discriminação, calibração e utilidade clínica."""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _validated_arrays(y: np.ndarray | pd.Series, p: np.ndarray | pd.Series):
    labels = np.asarray(y, dtype=int)
    probabilities = np.asarray(p, dtype=float)
    if labels.ndim != 1 or probabilities.ndim != 1 or len(labels) != len(probabilities):
        raise ValueError("y e p devem ser vetores unidimensionais de mesmo tamanho.")
    if not len(labels) or not np.isin(labels, [0, 1]).all():
        raise ValueError("y deve conter ao menos uma observação e apenas valores 0/1.")
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("p deve conter probabilidades finitas entre 0 e 1.")
    return labels, probabilities


def pr_auc(y, p) -> float:
    labels, probabilities = _validated_arrays(y, p)
    return float(average_precision_score(labels, probabilities))


def roc_auc(y, p) -> float:
    labels, probabilities = _validated_arrays(y, p)
    return float(roc_auc_score(labels, probabilities))


def brier(y, p) -> float:
    labels, probabilities = _validated_arrays(y, p)
    return float(brier_score_loss(labels, probabilities))


def calibration_slope_intercept(y, p) -> dict[str, float]:
    """Calcula slope e calibration-in-the-large com regressões logísticas distintas."""
    labels, probabilities = _validated_arrays(y, p)
    if len(np.unique(labels)) != 2:
        raise ValueError("Calibração requer observações das duas classes.")
    eps = np.finfo(float).eps
    logits = np.log(np.clip(probabilities, eps, 1 - eps) /
                    (1 - np.clip(probabilities, eps, 1 - eps)))
    if np.ptp(logits) == 0:
        prevalence = labels.mean()
        observed_logit = np.log(prevalence / (1 - prevalence))
        return {"slope": None, "intercept": float(observed_logit - logits[0])}
    slope_fit = sm.GLM(labels, sm.add_constant(logits), family=sm.families.Binomial()).fit()
    intercept_fit = sm.GLM(
        labels,
        np.ones((len(labels), 1)),
        family=sm.families.Binomial(),
        offset=logits,
    ).fit()
    return {"slope": float(slope_fit.params[1]), "intercept": float(intercept_fit.params[0])}


def threshold_metrics(y, p, limiar: float) -> dict[str, float]:
    labels, probabilities = _validated_arrays(y, p)
    if not 0 <= limiar <= 1:
        raise ValueError("limiar deve estar entre 0 e 1.")
    predictions = probabilities >= limiar
    precision = precision_score(labels, predictions, zero_division=0)
    recall = recall_score(labels, predictions, zero_division=0)
    f1 = f1_score(labels, predictions, zero_division=0)
    denominator = 4 * precision + recall
    f2 = 5 * precision * recall / denominator if denominator else 0.0
    return {
        "acuracia": float(accuracy_score(labels, predictions)),
        "precisao": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "f2": float(f2),
    }


def best_f2_threshold(y, p) -> float:
    labels, probabilities = _validated_arrays(y, p)
    order = np.argsort(-probabilities, kind="mergesort")
    sorted_probabilities = probabilities[order]
    sorted_labels = labels[order]
    true_positives = np.cumsum(sorted_labels, dtype=np.int64)
    predicted_positives = np.arange(1, len(labels) + 1)
    group_ends = np.flatnonzero(
        np.r_[sorted_probabilities[:-1] != sorted_probabilities[1:], True]
    )
    tp = true_positives[group_ends]
    positive_count = int(labels.sum())
    precision = tp / predicted_positives[group_ends]
    recall = tp / positive_count if positive_count else np.zeros(len(tp))
    denominator = 4 * precision + recall
    f2 = np.divide(
        5 * precision * recall,
        denominator,
        out=np.zeros_like(denominator, dtype=float),
        where=denominator > 0,
    )
    best_index = int(np.argmax(f2))
    return float(sorted_probabilities[group_ends[best_index]])


def net_benefit(y, p, limiares) -> pd.DataFrame:
    labels, probabilities = _validated_arrays(y, p)
    thresholds = np.asarray(limiares, dtype=float)
    if ((thresholds <= 0) | (thresholds >= 1)).any():
        raise ValueError("Os limiares de decisão devem estar entre 0 e 1, sem incluir extremos.")
    n = len(labels)
    prevalence = labels.mean()
    rows = []
    for threshold in thresholds:
        predictions = probabilities >= threshold
        tp = np.count_nonzero(predictions & (labels == 1))
        fp = np.count_nonzero(predictions & (labels == 0))
        rows.append(
            {
                "limiar": threshold,
                "modelo": tp / n - fp / n * threshold / (1 - threshold),
                "tratar_todos": prevalence - (1 - prevalence) * threshold / (1 - threshold),
                "tratar_ninguem": 0.0,
            }
        )
    return pd.DataFrame(rows)


def bootstrap_ci(fn, y, p, n: int, seed: int) -> tuple[float, float, float]:
    """IC percentil estratificado por desfecho, reamostrando cada classe separadamente."""
    labels, probabilities = _validated_arrays(y, p)
    if n < 1:
        raise ValueError("n deve ser positivo.")
    classes = [np.flatnonzero(labels == value) for value in (0, 1)]
    if any(not len(indices) for indices in classes):
        raise ValueError("Bootstrap estratificado requer observações das duas classes.")
    estimate = float(fn(labels, probabilities))
    rng = np.random.default_rng(seed)
    samples = np.empty(n, dtype=float)
    for iteration in range(n):
        sampled = np.concatenate(
            [rng.choice(indices, size=len(indices), replace=True) for indices in classes]
        )
        samples[iteration] = fn(labels[sampled], probabilities[sampled])
    lower, upper = np.quantile(samples, [0.025, 0.975])
    return estimate, float(lower), float(upper)


def paired_bootstrap_diff(
    fn, y, p_a, p_b, dobra, n: int, seed: int
) -> tuple[float, float, float]:
    """Compara médias por dobra com reamostragens pareadas por dobra e desfecho."""
    labels, probabilities_a = _validated_arrays(y, p_a)
    labels_b, probabilities_b = _validated_arrays(y, p_b)
    folds = np.asarray(dobra)
    if not np.array_equal(labels, labels_b) or len(probabilities_a) != len(probabilities_b):
        raise ValueError("As predições pareadas precisam estar alinhadas.")
    if folds.ndim != 1 or len(folds) != len(labels) or pd.isna(folds).any():
        raise ValueError("dobra deve conter um identificador não nulo por linha.")
    if n < 1:
        raise ValueError("n deve ser positivo.")
    fold_values = np.unique(folds)
    strata = [
        np.flatnonzero((folds == fold) & (labels == outcome))
        for fold in fold_values
        for outcome in (0, 1)
    ]
    if any(not len(indices) for indices in strata):
        raise ValueError("Cada dobra deve conter observações das duas classes.")

    def mean_fold_difference(indices: np.ndarray) -> float:
        differences = []
        for fold in fold_values:
            fold_indices = indices[folds[indices] == fold]
            differences.append(
                float(
                    fn(labels[fold_indices], probabilities_a[fold_indices])
                    - fn(labels[fold_indices], probabilities_b[fold_indices])
                )
            )
        return float(np.mean(differences))

    estimate = mean_fold_difference(np.arange(len(labels)))
    rng = np.random.default_rng(seed)
    samples = np.empty(n, dtype=float)
    for iteration in range(n):
        sampled = np.concatenate(
            [rng.choice(indices, size=len(indices), replace=True) for indices in strata]
        )
        samples[iteration] = mean_fold_difference(sampled)
    lower, upper = np.quantile(samples, [0.025, 0.975])
    return estimate, float(lower), float(upper)


def fold_bootstrap_ci(fn, y, p, dobra, n: int, seed: int) -> tuple[float, float, float]:
    """Calcula IC da média por dobra com reamostragem estratificada por dobra e alvo."""
    labels, probabilities = _validated_arrays(y, p)
    folds = np.asarray(dobra)
    if folds.ndim != 1 or len(folds) != len(labels) or pd.isna(folds).any():
        raise ValueError("dobra deve conter um identificador não nulo por linha.")
    if n < 1:
        raise ValueError("n deve ser positivo.")
    fold_values = np.unique(folds)
    strata = [
        np.flatnonzero((folds == fold) & (labels == outcome))
        for fold in fold_values
        for outcome in (0, 1)
    ]
    if any(not len(indices) for indices in strata):
        raise ValueError("Cada dobra deve conter observações das duas classes.")

    def mean_fold_score(indices: np.ndarray) -> float:
        return float(
            np.mean(
                [
                    fn(labels[indices[folds[indices] == fold]],
                       probabilities[indices[folds[indices] == fold]])
                    for fold in fold_values
                ]
            )
        )

    estimate = mean_fold_score(np.arange(len(labels)))
    rng = np.random.default_rng(seed)
    samples = np.empty(n, dtype=float)
    for iteration in range(n):
        sampled = np.concatenate(
            [rng.choice(indices, size=len(indices), replace=True) for indices in strata]
        )
        samples[iteration] = mean_fold_score(sampled)
    lower, upper = np.quantile(samples, [0.025, 0.975])
    return estimate, float(lower), float(upper)