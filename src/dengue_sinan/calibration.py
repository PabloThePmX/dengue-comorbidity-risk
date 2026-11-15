"""Calibradores de probabilidade ajustados exclusivamente em predições de desenvolvimento."""

from dataclasses import dataclass

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression


@dataclass
class PlattCalibrator:
    model: LogisticRegression
    epsilon: float

    def predict(self, probability) -> np.ndarray:
        values = np.asarray(probability, dtype=float)
        logits = np.log(np.clip(values, self.epsilon, 1 - self.epsilon) /
                        (1 - np.clip(values, self.epsilon, 1 - self.epsilon)))
        return self.model.predict_proba(logits.reshape(-1, 1))[:, 1]


def fit_calibrators(y, probability, seed: int) -> dict:
    labels = np.asarray(y, dtype=np.int8).reshape(-1)
    values = np.asarray(probability, dtype=float).reshape(-1)
    if len(labels) != len(values) or not len(labels):
        raise ValueError("y e probabilidade devem ter o mesmo tamanho não nulo.")
    if not np.isin(labels, [0, 1]).all() or not np.isfinite(values).all():
        raise ValueError("y deve ser binário e as probabilidades devem ser finitas.")
    if ((values < 0) | (values > 1)).any() or len(np.unique(labels)) != 2:
        raise ValueError("Probabilidades devem estar em [0, 1] e y conter as duas classes.")

    epsilon = np.finfo(float).eps
    logits = np.log(np.clip(values, epsilon, 1 - epsilon) /
                    (1 - np.clip(values, epsilon, 1 - epsilon)))
    platt_model = LogisticRegression(random_state=seed, max_iter=1000)
    platt_model.fit(logits.reshape(-1, 1), labels)
    isotonic = IsotonicRegression(out_of_bounds="clip")
    isotonic.fit(values, labels)
    return {
        "platt": PlattCalibrator(platt_model, epsilon),
        "isotonic": isotonic,
    }


def apply_calibrator(calibrator, probability) -> np.ndarray:
    """Aplica um Platt ou isotônico e valida o formato de saída."""
    calibrated = np.asarray(calibrator.predict(probability), dtype=float).reshape(-1)
    if not np.isfinite(calibrated).all() or ((calibrated < 0) | (calibrated > 1)).any():
        raise RuntimeError("O calibrador produziu probabilidades fora de [0, 1].")
    return calibrated
