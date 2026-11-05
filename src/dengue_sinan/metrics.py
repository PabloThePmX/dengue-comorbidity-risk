"""Métricas de discriminação, calibração, decisão e incerteza."""

from collections.abc import Callable, Sequence

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy.optimize import brentq
from scipy.special import expit
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    fbeta_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


def _arrays(y: Sequence[int], p: Sequence[float]) -> tuple[np.ndarray, np.ndarray]:
    labels = np.asarray(y, dtype=np.int8)
    probabilities = np.asarray(p, dtype=np.float64)
    if labels.ndim != 1 or probabilities.ndim != 1 or len(labels) != len(probabilities):
        raise ValueError("y e p devem ser vetores unidimensionais de mesmo tamanho")
    if len(labels) == 0 or not np.isin(labels, (0, 1)).all():
        raise ValueError("y deve conter pelo menos uma observação binária")
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("p deve conter probabilidades finitas entre 0 e 1")
    return labels, probabilities


def pr_auc(y: Sequence[int], p: Sequence[float]) -> float:
    labels, probabilities = _arrays(y, p)
    return float(average_precision_score(labels, probabilities))


def roc_auc(y: Sequence[int], p: Sequence[float]) -> float:
    labels, probabilities = _arrays(y, p)
    if np.unique(labels).size < 2:
        raise ValueError("ROC-AUC requer exemplos das duas classes")
    return float(roc_auc_score(labels, probabilities))


def brier(y: Sequence[int], p: Sequence[float]) -> float:
    labels, probabilities = _arrays(y, p)
    return float(brier_score_loss(labels, probabilities))


def calibration_slope_intercept(y: Sequence[int], p: Sequence[float]) -> tuple[float, float]:
    """Retorna slope e calibration-in-the-large (intercept com slope fixo em 1)."""
    labels, probabilities = _arrays(y, p)
    if np.unique(labels).size < 2:
        raise ValueError("calibração logística requer exemplos das duas classes")
    clipped = np.clip(probabilities, 1e-8, 1 - 1e-8)
    logit = np.log(clipped / (1 - clipped))

    positive = logit[labels == 1]
    negative = logit[labels == 0]
    complete_separation = (
        np.max(negative) < np.min(positive) or np.max(positive) < np.min(negative)
    )
    if np.ptp(logit) < 1e-12 or complete_separation:
        slope = float("nan")
    else:
        design = sm.add_constant(logit, has_constant="add")
        slope_fit = sm.GLM(labels, design, family=sm.families.Binomial()).fit()
        slope = float(slope_fit.params[1])

    def calibration_error(intercept: float) -> float:
        return float(np.sum(expit(logit + intercept)) - labels.sum())

    intercept = brentq(calibration_error, -100, 100)
    return slope, float(intercept)


def threshold_metrics(y: Sequence[int], p: Sequence[float], limiar: float) -> dict[str, float]:
    labels, probabilities = _arrays(y, p)
    if not 0 <= limiar <= 1:
        raise ValueError("limiar deve estar entre 0 e 1")
    predictions = probabilities >= limiar
    return {
        "acuracia": float(accuracy_score(labels, predictions)),
        "precisao": float(precision_score(labels, predictions, zero_division=0)),
        "recall": float(recall_score(labels, predictions, zero_division=0)),
        "f1": float(f1_score(labels, predictions, zero_division=0)),
        "f2": float(fbeta_score(labels, predictions, beta=2, zero_division=0)),
    }


def best_f2_threshold(y: Sequence[int], p: Sequence[float]) -> float:
    labels, probabilities = _arrays(y, p)
    if not labels.any():
        raise ValueError("não é possível escolher limiar F2 sem eventos positivos")
    candidates = np.unique(np.concatenate(([0.0], probabilities, [1.0])))
    scores = [threshold_metrics(labels, probabilities, threshold)["f2"] for threshold in candidates]
    best = max(scores)
    return float(max(threshold for threshold, score in zip(candidates, scores, strict=True)
                     if score == best))


def net_benefit(
    y: Sequence[int],
    p: Sequence[float],
    limiares: Sequence[float],
    modelo: str = "modelo",
) -> pd.DataFrame:
    """Retorna benefício líquido do modelo, de tratar todos e de não tratar ninguém."""
    labels, probabilities = _arrays(y, p)
    thresholds = np.asarray(limiares, dtype=np.float64)
    if thresholds.ndim != 1 or not np.isfinite(thresholds).all():
        raise ValueError("limiares deve ser um vetor finito")
    if ((thresholds <= 0) | (thresholds >= 1)).any():
        raise ValueError("limiares de decisão devem estar estritamente entre 0 e 1")
    n = len(labels)
    rows = []
    for threshold in thresholds:
        predicted = probabilities >= threshold
        weight = threshold / (1 - threshold)
        rows.append({
            "limiar": float(threshold),
            "modelo": float((np.sum(predicted & (labels == 1))
                             - np.sum(predicted & (labels == 0)) * weight) / n),
            "tratar_todos": float(labels.mean() - (1 - labels.mean()) * weight),
            "tratar_ninguem": 0.0,
            "nome_modelo": modelo,
        })
    return pd.DataFrame(rows, columns=[
        "limiar", "modelo", "tratar_todos", "tratar_ninguem", "nome_modelo",
    ])


def bootstrap_ci(
    fn: Callable[[np.ndarray, np.ndarray], float],
    y: Sequence[int],
    p: Sequence[float],
    n: int,
    seed: int,
) -> tuple[float, float, float]:
    """IC percentil estratificado por classe, mantendo a prevalência observada."""
    labels, probabilities = _arrays(y, p)
    if n < 1:
        raise ValueError("n deve ser positivo")
    positive = np.flatnonzero(labels == 1)
    negative = np.flatnonzero(labels == 0)
    if not len(positive) or not len(negative):
        raise ValueError("bootstrap estratificado requer as duas classes")
    estimate = float(fn(labels, probabilities))
    rng = np.random.default_rng(seed)
    samples = np.empty(n, dtype=np.float64)
    for index in range(n):
        draw = np.concatenate([
            rng.choice(negative, size=len(negative), replace=True),
            rng.choice(positive, size=len(positive), replace=True),
        ])
        samples[index] = fn(labels[draw], probabilities[draw])
    lower, upper = np.quantile(samples, [0.025, 0.975])
    return estimate, float(lower), float(upper)
