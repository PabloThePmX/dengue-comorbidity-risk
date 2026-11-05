"""Calibração de probabilidades e seleção do limiar pela validação OOF."""

from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from dengue_sinan.guard import assert_dev_only
from dengue_sinan.metrics import best_f2_threshold, brier


@dataclass
class ProbabilityCalibrator:
    """Wrapper uniforme para isotônica e Platt, recebendo probabilidades brutas."""

    method: str
    estimator: object

    def transform(self, probabilities):
        raw = np.asarray(probabilities, dtype=np.float64).reshape(-1)
        if not np.isfinite(raw).all() or ((raw < 0) | (raw > 1)).any():
            raise ValueError("probabilidades devem ser finitas e estar entre 0 e 1")
        if self.method == "isotonic":
            return np.asarray(self.estimator.predict(raw), dtype=np.float64)
        if self.method == "platt":
            logit = _logit(raw).reshape(-1, 1)
            return self.estimator.predict_proba(logit)[:, 1]
        raise ValueError(f"método de calibração desconhecido: {self.method}")


def _logit(probabilities: np.ndarray) -> np.ndarray:
    clipped = np.clip(probabilities, 1e-8, 1 - 1e-8)
    return np.log(clipped / (1 - clipped))


def fit_calibrator(y, probabilities, method: str) -> ProbabilityCalibrator:
    labels = np.asarray(y, dtype=np.int8).reshape(-1)
    raw = np.asarray(probabilities, dtype=np.float64).reshape(-1)
    if len(labels) != len(raw) or not len(labels) or not np.isin(labels, (0, 1)).all():
        raise ValueError("y e probabilidades precisam estar alinhados e y deve ser binário")
    if not np.isfinite(raw).all() or ((raw < 0) | (raw > 1)).any():
        raise ValueError("probabilidades devem ser finitas e estar entre 0 e 1")
    if np.unique(labels).size < 2:
        raise ValueError("calibração requer exemplos das duas classes")
    if method == "isotonic":
        estimator = IsotonicRegression(out_of_bounds="clip").fit(raw, labels)
    elif method == "platt":
        estimator = LogisticRegression(C=np.inf, solver="lbfgs", max_iter=1000)
        estimator.fit(_logit(raw).reshape(-1, 1), labels)
    else:
        raise ValueError("method deve ser 'isotonic' ou 'platt'")
    return ProbabilityCalibrator(method, estimator)


def select_calibrator_and_threshold(frame, probabilities) -> dict:
    """Compara isotônica/Platt no OOF e escolhe limiar F2 sem acessar o teste."""
    assert_dev_only(frame)
    labels = frame["y"].to_numpy(dtype=np.int8)
    raw = np.asarray(probabilities, dtype=np.float64)
    if len(raw) != len(labels):
        raise ValueError("probabilidades OOF devem ter uma entrada por linha")
    candidates = {}
    for method in ("isotonic", "platt"):
        calibrator = fit_calibrator(labels, raw, method)
        calibrated = calibrator.transform(raw)
        candidates[method] = {
            "calibrator": calibrator,
            "probabilities": calibrated,
            "brier": brier(labels, calibrated),
        }
    selected = min(candidates, key=lambda method: (candidates[method]["brier"], method))
    result = candidates[selected]
    return {
        "method": selected,
        "calibrator": result["calibrator"],
        "oof_calibrated": result["probabilities"],
        "brier": result["brier"],
        "threshold": best_f2_threshold(labels, result["probabilities"]),
        "candidate_brier": {method: value["brier"] for method, value in candidates.items()},
    }
