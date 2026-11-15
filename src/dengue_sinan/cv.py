"""Validação leave-one-region-out dos modelos preditivos."""

from collections.abc import Mapping

import numpy as np
import optuna
import pandas as pd
import torch
from catboost import CatBoostClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from xgboost import XGBClassifier

from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.folds import REGIONS, inner_split, loro_folds
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.metrics import brier, pr_auc
from dengue_sinan.mlp import MLPClassifier
from dengue_sinan.preprocess import make_preprocessor

_ITERATIVE_MODELS = {"xgboost", "catboost", "mlp"}
_CATEGORICAL_FEATURES = {
    "sexo",
    "diabetes",
    "hematolog",
    "hepatopat",
    "renal",
    "hipertensa",
    "acido_pept",
    "auto_imune",
    "febre",
    "mialgia",
    "cefaleia",
    "exantema",
    "vomito",
    "nausea",
    "dor_costas",
    "conjuntvit",
    "artrite",
    "artralgia",
    "dor_retro",
    "petequia_n",
    "leucopenia",
    "laco",
}


def _config(cfg: Mapping | str) -> dict:
    if isinstance(cfg, Mapping):
        return dict(cfg)
    from dengue_sinan.config import load_config

    return load_config(cfg)


def _make_model(modelo: str, params: dict, seed: int):
    """Cria um estimador sem pesos de classe ou reamostragem."""
    options = dict(params)
    if modelo == "elastic_net":
        return LogisticRegression(
            penalty="elasticnet",
            solver="saga",
            max_iter=2000,
            random_state=seed,
            **options,
        )
    if modelo == "random_forest":
        return RandomForestClassifier(
            n_jobs=-1,
            random_state=seed,
            **options,
        )
    if modelo == "xgboost":
        return XGBClassifier(
            objective="binary:logistic",
            eval_metric="aucpr",
            tree_method="hist",
            device="cuda" if torch.cuda.is_available() else "cpu",
            random_state=seed,
            n_jobs=-1,
            early_stopping_rounds=50,
            **options,
        )
    if modelo == "catboost":
        return CatBoostClassifier(
            loss_function="Logloss",
            eval_metric="PRAUC",
            task_type="GPU" if torch.cuda.is_available() else "CPU",
            random_seed=seed,
            allow_writing_files=False,
            verbose=False,
            **options,
        )
    if modelo == "mlp":
        return MLPClassifier(seed=seed, **options)
    raise ValueError(f"Modelo desconhecido: {modelo}")


def _fold_preprocessor(modelo: str):
    if modelo == "catboost":
        return "passthrough"
    if modelo == "elastic_net":
        return make_preprocessor("linear", interacoes_comorbidades=True)
    if modelo == "mlp":
        return make_preprocessor("linear")
    return make_preprocessor("arvore")


def _fit_fold(
    modelo: str,
    params: dict,
    seed: int,
    X: pd.DataFrame,
    y: np.ndarray,
    train_idx: np.ndarray,
    valid_idx: np.ndarray,
    validation_fraction: float,
) -> tuple[np.ndarray, int | None]:
    preprocessor = _fold_preprocessor(modelo)
    estimator = _make_model(modelo, params, seed)
    pipeline = Pipeline([("preprocessamento", preprocessor), ("modelo", estimator)])

    if modelo in _ITERATIVE_MODELS:
        fit_idx, stop_idx = inner_split(
            train_idx, y, validation_fraction, seed=seed
        )
        preprocessor.fit(X.iloc[fit_idx], y[fit_idx])
        X_fit = preprocessor.transform(X.iloc[fit_idx])
        X_stop = preprocessor.transform(X.iloc[stop_idx])
        X_valid = preprocessor.transform(X.iloc[valid_idx])
        y_fit, y_stop = y[fit_idx], y[stop_idx]
        if modelo == "xgboost":
            estimator.fit(
                X_fit,
                y_fit,
                eval_set=[(X_stop, y_stop)],
                verbose=False,
            )
            best_point = int(estimator.best_iteration) + 1
        elif modelo == "catboost":
            cat_features = [
                column for column in _CATEGORICAL_FEATURES if column in X.columns
            ]
            estimator.fit(
                X.iloc[fit_idx].astype({col: str for col in cat_features}),
                y_fit,
                cat_features=cat_features,
                eval_set=(
                    X.iloc[stop_idx].astype({col: str for col in cat_features}),
                    y_stop,
                ),
                early_stopping_rounds=50,
                verbose=False,
            )
            best_point = max(estimator.get_best_iteration() + 1, 1)
            X_valid = X.iloc[valid_idx].astype({col: str for col in cat_features})
        else:
            estimator.fit(X_fit, y_fit, eval_set=(X_stop, y_stop))
            best_point = int(estimator.best_epoch_)
        probability = estimator.predict_proba(X_valid)[:, 1]
        return probability, best_point

    pipeline.fit(X.iloc[train_idx], y[train_idx])
    return pipeline.predict_proba(X.iloc[valid_idx])[:, 1], None


def run_loro(
    cfg: dict | str,
    modelo: str,
    params: dict,
    df: pd.DataFrame,
    *,
    trial: optuna.Trial | None = None,
    sample_limit: int | None = None,
    fold_assignments: list[tuple[str, np.ndarray, np.ndarray]] | None = None,
) -> dict:
    """Produz predições OOF e métricas por região, sempre apenas em 2022–2023."""
    assert_dev_only(df)
    if modelo not in {"elastic_net", "random_forest", "xgboost", "catboost", "mlp"}:
        raise ValueError(f"Modelo não suportado: {modelo}")
    if "y" not in df:
        raise ValueError("DataFrame deve conter o desfecho y.")

    config = _config(cfg)
    seed = int(config["seed"])
    y = df["y"].to_numpy(dtype=np.int8)
    X = build_feature_frame(df)
    fold_order = config.get("ordem_dobras", list(REGIONS))
    assignments = fold_assignments or loro_folds(df, fold_order)
    folds = {region: (train, valid) for region, train, valid in assignments}
    if set(folds) != set(REGIONS):
        raise ValueError("As dobras devem cobrir exatamente as cinco regiões.")
    oof = np.full(len(df), np.nan, dtype=float)
    fold_metrics = []
    best_points = {}
    cumulative_pr_auc = []

    for step, region in enumerate(fold_order):
        if region not in folds:
            raise ValueError(f"Região de dobra desconhecida: {region}")
        train_idx, valid_idx = folds[region]
        fold_train_idx = train_idx
        if sample_limit is not None and len(fold_train_idx) > sample_limit:
            rng = np.random.default_rng(seed + step)
            sampled_parts = []
            labels = y[fold_train_idx]
            for label in (0, 1):
                class_idx = fold_train_idx[labels == label]
                class_count = max(1, round(sample_limit * len(class_idx) / len(labels)))
                sampled_parts.append(
                    rng.choice(class_idx, size=min(class_count, len(class_idx)), replace=False)
                )
            fold_train_idx = np.sort(np.concatenate(sampled_parts))

        probability, best_point = _fit_fold(
            modelo,
            params,
            seed + step,
            X,
            y,
            fold_train_idx,
            valid_idx,
            float(config["validacao_interna_frac"]),
        )
        oof[valid_idx] = probability
        labels_valid = y[valid_idx]
        fold_pr_auc = pr_auc(labels_valid, probability)
        fold_metrics.append(
            {
                "regiao": region,
                "pr_auc": fold_pr_auc,
                "brier": brier(labels_valid, probability),
            }
        )
        cumulative_pr_auc.append(fold_pr_auc)
        if best_point is not None:
            best_points[region] = best_point
        if trial is not None:
            trial.report(float(np.mean(cumulative_pr_auc)), step=step)
            if trial.should_prune():
                raise optuna.TrialPruned(f"Poda após a dobra {region}.")

    if np.isnan(oof).any():
        raise RuntimeError("A validação LORO não produziu exatamente uma predição por linha.")
    oof_frame = pd.DataFrame(
        {
            "ANO": df["ANO"].to_numpy(),
            "regiao": df["regiao"].to_numpy(),
            "y": y,
            "probabilidade": oof,
        }
    )
    return {
        "modelo": modelo,
        "oof": oof_frame,
        "fold_metrics": pd.DataFrame(fold_metrics),
        "mean_pr_auc": float(np.mean(cumulative_pr_auc)),
        "best_points": best_points,
        "sample_limit": sample_limit,
    }
