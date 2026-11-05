"""Validação leave-one-region-out dos modelos preditivos M1."""

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from dengue_sinan.baselines import B1_CATEGORICAL, B1_NUMERIC, make_b1_pipeline
from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.folds import inner_split, loro_folds
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.metrics import (
    brier,
    calibration_slope_intercept,
    pr_auc,
    roc_auc,
)
from dengue_sinan.mlp import MLPClassifier
from dengue_sinan.preprocess import (
    CATBOOST_CATEGORICAL_INDICES,
    FEATURE_COLUMNS,
    make_preprocessor,
)

_FORBIDDEN_WEIGHT_PARAMS = {
    "class_weight", "scale_pos_weight", "is_unbalance", "auto_class_weights", "pos_weight",
}


def _validate_params(params: dict) -> None:
    forbidden = _FORBIDDEN_WEIGHT_PARAMS & params.keys()
    if forbidden:
        raise ValueError(f"parâmetros de correção de desbalanceamento proibidos (R3): {forbidden}")


def _make_model(model_name: str, params: dict, seed: int):
    _validate_params(params)
    if model_name == "elastic_net":
        from sklearn.linear_model import LogisticRegression

        return "linear", LogisticRegression(
            penalty="elasticnet",
            solver="saga",
            max_iter=params.pop("max_iter", 5000),
            random_state=seed,
            **params,
        ), False
    if model_name == "random_forest":
        return "arvore", RandomForestClassifier(
            random_state=seed,
            n_jobs=-1,
            **params,
        ), False
    if model_name == "xgboost":
        model_params = params.copy()
        model_params.setdefault("tree_method", "hist")
        model_params.setdefault("eval_metric", "aucpr")
        model_params.setdefault("early_stopping_rounds", 50)
        model_params.setdefault("n_estimators", 2000)
        model_params["random_state"] = seed
        model_params["n_jobs"] = -1
        return "arvore", XGBClassifier(**model_params), True
    if model_name == "catboost":
        model_params = params.copy()
        model_params.setdefault("iterations", 3000)
        model_params.setdefault("eval_metric", "PRAUC")
        model_params.setdefault("random_seed", seed)
        model_params.setdefault("verbose", False)
        model_params.setdefault("allow_writing_files", False)
        return "catboost", CatBoostClassifier(**model_params), True
    if model_name == "mlp":
        model_params = params.copy()
        if "lr" in model_params:
            model_params["learning_rate"] = model_params.pop("lr")
        model_params.setdefault("seed", seed)
        return "linear", MLPClassifier(**model_params), True
    if model_name == "tabfm":
        raise RuntimeError(
            "TabFM bloqueado: verifique licença, limite de contexto, velocidade e versão "
            "do pacote conforme T-4.7 antes de implementar."
        )
    raise ValueError(f"modelo desconhecido: {model_name}")


def _fold_metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, float]:
    slope, intercept = calibration_slope_intercept(labels, probabilities)
    return {
        "pr_auc": pr_auc(labels, probabilities),
        "brier": brier(labels, probabilities),
        "roc_auc": roc_auc(labels, probabilities),
        "calibration_slope": slope,
        "calibration_intercept": intercept,
    }


def run_loro(
    cfg: dict,
    familia: str,
    params: dict,
    df: pd.DataFrame,
    trial=None,
) -> dict:
    """Gera OOF em cinco regiões e usa apenas regiões de treino para early stopping."""
    assert_dev_only(df, int(cfg.get("ano_teste", 2024)))
    if "y" not in df:
        raise ValueError("df precisa conter o alvo y")
    seed = int(cfg["seed"])
    labels = df["y"].to_numpy(dtype=np.int8)
    features = build_feature_frame(df)
    if familia == "b1":
        model_name = "b1"
    else:
        model_name = familia

    oof = np.full(len(df), np.nan, dtype=np.float64)
    fold_rows = []
    best_points = {}
    models = {}
    for step, (region, train_idx, valid_idx) in enumerate(loro_folds(df)):
        y_train, y_valid = labels[train_idx], labels[valid_idx]
        if np.unique(y_train).size < 2 or np.unique(y_valid).size < 2:
            raise ValueError(f"{region}: treino e validação precisam conter as duas classes")
        x_train = features.iloc[train_idx]
        x_valid = features.iloc[valid_idx]

        if model_name == "b1":
            model = make_b1_pipeline(seed)
            columns = B1_NUMERIC + B1_CATEGORICAL
            model.fit(x_train[columns], y_train)
            probabilities = model.predict_proba(x_valid[columns])[:, 1]
            best_points[region] = None
            models[region] = model
        else:
            preprocessing_family, estimator, iterative = _make_model(
                model_name, params.copy(), seed
            )
            preprocessor = make_preprocessor(
                preprocessing_family, interactions=(model_name == "elastic_net")
            )
            if iterative:
                fit_idx, stop_idx = inner_split(
                    train_idx, labels, float(cfg.get("validacao_interna_frac", 0.1)),
                    seed + step,
                )
                x_fit = features.iloc[fit_idx][FEATURE_COLUMNS]
                y_fit = labels[fit_idx]
                x_stop = features.iloc[stop_idx][FEATURE_COLUMNS]
                y_stop = labels[stop_idx]
                preprocessor.fit(x_fit, y_fit)
                transformed_fit = preprocessor.transform(x_fit)
                transformed_stop = preprocessor.transform(x_stop)
                transformed_valid = preprocessor.transform(x_valid[FEATURE_COLUMNS])
                if model_name == "xgboost":
                    estimator.fit(
                        transformed_fit, y_fit,
                        eval_set=[(transformed_stop, y_stop)],
                        verbose=False,
                    )
                elif model_name == "catboost":
                    estimator.fit(
                        transformed_fit, y_fit,
                        eval_set=(transformed_stop, y_stop),
                        cat_features=list(CATBOOST_CATEGORICAL_INDICES),
                        early_stopping_rounds=50,
                        use_best_model=True,
                        verbose=False,
                    )
                else:
                    estimator.fit(
                        transformed_fit, y_fit,
                        validation_data=(transformed_stop, y_stop),
                    )
            else:
                x_fit = x_train[FEATURE_COLUMNS]
                y_fit = y_train
                preprocessor.fit(x_fit, y_fit)
                transformed_fit = preprocessor.transform(x_fit)
                transformed_valid = preprocessor.transform(x_valid[FEATURE_COLUMNS])
                if model_name == "catboost":
                    estimator.fit(
                        transformed_fit, y_fit,
                        cat_features=list(CATBOOST_CATEGORICAL_INDICES),
                        verbose=False,
                    )
                else:
                    estimator.fit(transformed_fit, y_fit)

            probabilities = estimator.predict_proba(transformed_valid)[:, 1]
            if model_name == "xgboost":
                best_points[region] = int(estimator.best_iteration) + 1
            elif model_name == "catboost":
                best_points[region] = int(estimator.best_iteration_) + 1
            elif model_name == "mlp":
                best_points[region] = int(estimator.best_epoch_)
            elif model_name == "random_forest":
                best_points[region] = int(estimator.n_estimators)
            else:
                best_points[region] = None
            models[region] = Pipeline([("preprocess", preprocessor), ("model", estimator)])

        oof[valid_idx] = probabilities
        metrics = _fold_metrics(y_valid, probabilities)
        fold_rows.append({"regiao": region, **metrics})
        if trial is not None:
            trial.report(float(np.mean([row["pr_auc"] for row in fold_rows])), step=step)
            if trial.should_prune():
                import optuna

                raise optuna.TrialPruned(f"poda após a dobra {region}")

    if np.isnan(oof).any():
        raise RuntimeError("run_loro não produziu uma predição OOF por linha")
    aggregate = _fold_metrics(labels, oof)
    return {
        "oof": oof,
        "fold_metrics": pd.DataFrame(fold_rows),
        "mean_pr_auc": float(pd.DataFrame(fold_rows)["pr_auc"].mean()),
        "oof_metrics": aggregate,
        "best_points": best_points,
        "models": models,
    }
