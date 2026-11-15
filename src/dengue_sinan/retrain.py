"""Ajuste final do modelo M1 em todo o conjunto de desenvolvimento."""

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from dengue_sinan.cv import _CATEGORICAL_FEATURES, _fold_preprocessor, _make_model
from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.guard import assert_dev_only

_ITERATIVE_PARAMETERS = {
    "xgboost": "n_estimators",
    "catboost": "iterations",
    "mlp": "max_epochs",
}


def fit_final_pipeline(
    modelo: str,
    params: dict,
    best_points: dict[str, int],
    df: pd.DataFrame,
    cfg: dict,
) -> tuple[Pipeline, dict, int | None]:
    """Retreina com hiperparâmetros fixos e mediana dos pontos iterativos."""
    assert_dev_only(df)
    model_params = dict(params)
    final_point = None
    if modelo in _ITERATIVE_PARAMETERS:
        if not best_points:
            raise ValueError(f"{modelo} requer um melhor ponto para cada dobra.")
        final_point = int(np.median(list(best_points.values())))
        model_params[_ITERATIVE_PARAMETERS[modelo]] = final_point
    estimator = _make_model(modelo, model_params, int(cfg["seed"]))
    if modelo == "xgboost":
        estimator.set_params(early_stopping_rounds=None)
    if modelo == "mlp":
        estimator.set_params(patience=1)

    features = build_feature_frame(df)
    labels = df["y"].to_numpy(dtype=np.int8)
    preprocessor = _fold_preprocessor(modelo)
    pipeline = Pipeline([("preprocessamento", preprocessor), ("modelo", estimator)])
    if modelo == "catboost":
        categorical = [column for column in _CATEGORICAL_FEATURES if column in features.columns]
        fit_features = features.astype({column: str for column in categorical})
        pipeline.fit(
            fit_features,
            labels,
            modelo__cat_features=categorical,
        )
    else:
        pipeline.fit(features, labels)
    return pipeline, model_params, final_point
