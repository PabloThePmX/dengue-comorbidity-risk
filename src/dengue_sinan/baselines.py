"""Baselines B0, B1 e regra clínica B2."""

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer

from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.folds import loro_folds
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.metrics import (
    brier,
    calibration_slope_intercept,
    pr_auc,
    roc_auc,
    threshold_metrics,
)
from dengue_sinan.profiling import COMORBIDADES, code

B1_CATEGORICAL = ["sexo", "gestante", *COMORBIDADES]
B1_NUMERIC = ["idade_anos", "n_comorbidades"]


def make_b1_pipeline(seed: int = 20261103) -> Pipeline:
    """Pipeline logística não penalizada; todo preprocessing é ajustado no treino."""
    preprocessor = ColumnTransformer(
        transformers=[
            ("idade", Pipeline([
                ("imputer", SimpleImputer(strategy="median")),
                ("spline", SplineTransformer(n_knots=5, degree=3, include_bias=False)),
            ]), ["idade_anos"]),
            ("categorias", Pipeline([
                ("imputer", SimpleImputer(strategy="most_frequent")),
                ("onehot", OneHotEncoder(handle_unknown="ignore", drop="first")),
            ]), B1_CATEGORICAL),
            ("contagem", SimpleImputer(strategy="median"), ["n_comorbidades"]),
        ],
        remainder="drop",
    )
    return Pipeline([
        ("preprocess", preprocessor),
        ("model", LogisticRegression(C=np.inf, solver="lbfgs", max_iter=1000,
                                     random_state=seed)),
    ])


def _yes(series: pd.Series) -> pd.Series:
    values = series.astype("string")
    if values.isin({"Sim", "Não", "Ausente"}).any():
        return values.eq("Sim")
    return code(series).eq("1")


def rule_b2(frame: pd.DataFrame) -> np.ndarray:
    """Regra binária do grupo B do protocolo, conforme definição do TODO."""
    age = frame["idade_anos"] if "idade_anos" in frame else None
    if age is None:
        raise ValueError("rule_b2 requer idade_anos já derivada")
    numeric_age = pd.to_numeric(age, errors="coerce")
    high_risk = numeric_age.lt(2) | numeric_age.gt(65)
    if "gestante" in frame:
        pregnancy = frame["gestante"].astype("string").isin({"1", "True", "true"})
    elif "CS_GESTANT" in frame:
        pregnancy = code(frame["CS_GESTANT"]).isin({"1", "2", "3", "4"})
    else:
        raise ValueError("rule_b2 requer gestante ou CS_GESTANT")
    comorbidity = pd.concat([_yes(frame[column]) for column in COMORBIDADES], axis=1).any(axis=1)
    signs = pd.Series(False, index=frame.index)
    for column in ("LACO", "PETEQUIA_N"):
        if column in frame:
            signs |= _yes(frame[column])
    return (high_risk | pregnancy | comorbidity | signs).to_numpy(dtype=bool)


def _probability_metrics(y: np.ndarray, p: np.ndarray) -> dict[str, float]:
    slope, intercept = calibration_slope_intercept(y, p)
    return {
        "pr_auc": pr_auc(y, p),
        "brier": brier(y, p),
        "roc_auc": roc_auc(y, p),
        "calibration_slope": slope,
        "calibration_intercept": intercept,
    }


def run_baselines_loro(frame: pd.DataFrame, seed: int = 20261103) -> dict:
    """Executa B0/B1 fora da dobra e avalia a regra B2 sem ajustar parâmetros."""
    assert_dev_only(frame)
    if "y" not in frame:
        raise ValueError("frame precisa conter o alvo y")
    features = build_feature_frame(frame)
    labels = frame["y"].to_numpy(dtype=np.int8)
    oof = {name: np.full(len(frame), np.nan) for name in ("B0", "B1")}
    per_fold: dict[str, list[dict[str, float | str]]] = {"B0": [], "B1": []}

    for region, train_idx, valid_idx in loro_folds(frame):
        y_train, y_valid = labels[train_idx], labels[valid_idx]
        if np.unique(y_train).size < 2 or np.unique(y_valid).size < 2:
            raise ValueError(f"{region}: treino e validação precisam conter as duas classes")
        oof["B0"][valid_idx] = y_train.mean()
        model = make_b1_pipeline(seed)
        model.fit(features.iloc[train_idx][B1_NUMERIC + B1_CATEGORICAL], y_train)
        oof["B1"][valid_idx] = model.predict_proba(
            features.iloc[valid_idx][B1_NUMERIC + B1_CATEGORICAL]
        )[:, 1]

        for name in ("B0", "B1"):
            per_fold[name].append({
                "regiao": region,
                **_probability_metrics(y_valid, oof[name][valid_idx]),
            })

    if any(np.isnan(values).any() for values in oof.values()):
        raise RuntimeError("as predições OOF não cobriram todas as linhas")
    b2_predictions = rule_b2(frame)
    b2_metrics = threshold_metrics(labels, b2_predictions.astype(float), 0.5)
    return {
        "oof": oof,
        "fold_metrics": per_fold,
        "metrics": {name: _probability_metrics(labels, predictions)
                    for name, predictions in oof.items()},
        "b2": b2_metrics,
        "b2_predictions": b2_predictions,
    }
