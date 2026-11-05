"""Retreino de modelos finais em dados de desenvolvimento."""

import hashlib
import statistics
from datetime import date
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
import shap
import torch
from sklearn.pipeline import Pipeline

from dengue_sinan.artifacts import save_bundle
from dengue_sinan.baselines import B1_CATEGORICAL, B1_NUMERIC, make_b1_pipeline
from dengue_sinan.cv import _make_model
from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.descriptive import combination_counts, pair_event_counts
from dengue_sinan.explain import (
    compact_e1,
    fit_e1,
    profiles_table,
    write_e1_reports,
)
from dengue_sinan.folds import REGIONS
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.preprocess import FEATURE_COLUMNS, make_preprocessor
from dengue_sinan.profiling import COMORBIDADES
from dengue_sinan.tracking import _commit_hash, _data_hashes

_PACKAGES = (
    "catboost",
    "mlflow",
    "numpy",
    "pandas",
    "scikit-learn",
    "statsmodels",
    "torch",
    "xgboost",
)


def _json_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    if isinstance(value, Path):
        return str(value)
    return value


def _library_versions() -> dict[str, str]:
    versions = {}
    for package in _PACKAGES:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            continue
    return versions


def _code_hash() -> str:
    root = Path(__file__).resolve().parents[2]
    digest = hashlib.sha256()
    for folder in ("src", "app", "scripts"):
        for path in sorted((root / folder).rglob("*.py")):
            digest.update(path.relative_to(root).as_posix().encode("utf-8"))
            digest.update(path.read_bytes())
    return digest.hexdigest()


def _metadata(
    cfg: dict[str, Any],
    frame: pd.DataFrame,
    features: list[str],
    validation_metrics: dict[str, Any],
) -> dict[str, Any]:
    assert_dev_only(frame, int(cfg.get("ano_teste", 2024)))
    return {
        "commit": _commit_hash(),
        "code_sha256": _code_hash(),
        "hashes_dados": _data_hashes(cfg),
        "config": _json_value(cfg),
        "data_treino": date.today().isoformat(),
        "metricas_validacao": _json_value(validation_metrics),
        "features": _json_value(features),
        "versoes_bibliotecas": _library_versions(),
    }


def _assert_development_years(cfg: dict[str, Any], frame: pd.DataFrame) -> None:
    assert_dev_only(frame, int(cfg.get("ano_teste", 2024)))
    expected = {int(year) for year in cfg["anos_dev"]}
    observed = set(pd.to_numeric(frame["ANO"], errors="coerce").dropna().astype(int))
    if observed != expected:
        raise ValueError(
            f"retreino final requer todos e somente os anos {sorted(expected)}; "
            f"recebidos {sorted(observed)}"
        )


def _check_demo_viability(
    pipeline: Pipeline,
    calibrator: Any,
    raw_features: pd.DataFrame,
    labels: np.ndarray,
    familia: str,
    shap_background: np.ndarray | None = None,
) -> dict[str, float]:
    if len(raw_features) < 20:
        raise ValueError("são necessárias 20 linhas de desenvolvimento para testar a demo")
    profiles = raw_features.iloc[:20]
    pipeline.predict_proba(profiles.iloc[:1])
    started = perf_counter()
    single_probability = pipeline.predict_proba(profiles.iloc[:1])[:, 1]
    calibrator.transform(single_probability)
    single_prediction_seconds = perf_counter() - started
    started = perf_counter()
    probabilities = pipeline.predict_proba(profiles)[:, 1]
    calibrator.transform(probabilities)
    prediction_seconds = perf_counter() - started
    if prediction_seconds >= 1:
        raise RuntimeError(
            "o modelo excede 1 s para 20 perfis; a decisão de modelo para a demo "
            "requer revisão (Q-14)"
        )

    if shap_background is None:
        background_indices = np.flatnonzero(labels == labels[0])[:50].tolist()
        other_class = np.flatnonzero(labels != labels[0])[:50].tolist()
        background_indices = (background_indices + other_class)[:100]
        background = pipeline.named_steps["preprocess"].transform(
            raw_features.iloc[background_indices]
        )
    else:
        background = shap_background
    row = pipeline.named_steps["preprocess"].transform(profiles.iloc[:1])
    estimator = pipeline.named_steps["model"]
    started = perf_counter()
    if familia == "mlp":
        background_tensor = torch.as_tensor(background, dtype=torch.float32)
        row_tensor = torch.as_tensor(np.asarray(row), dtype=torch.float32)
        explainer = shap.GradientExplainer(estimator.model_, background_tensor)
        explainer.shap_values(row_tensor)
    else:
        explainer = shap.Explainer(estimator, background)
        explainer(row)
    shap_seconds = perf_counter() - started
    if single_prediction_seconds + shap_seconds >= 1:
        raise RuntimeError(
            "predição e explicação local excedem 1 s; a decisão de modelo para a demo "
            "requer revisão (Q-14)"
        )
    return {
        "predicao_20_perfis_segundos": float(prediction_seconds),
        "predicao_1_perfil_segundos": float(single_prediction_seconds),
        "shap_local_1_perfil_segundos": float(shap_seconds),
    }


def train_final_e1(
    cfg: dict[str, Any],
    frame: pd.DataFrame,
    reference_profile: dict[str, Any],
    age_references: dict[str, float],
    gestante: bool,
) -> Path:
    """Ajusta E1 em todo o desenvolvimento e salva apenas seu estado compacto."""
    _assert_development_years(cfg, frame)
    pairs = pair_event_counts(frame)
    combinations = combination_counts(frame)
    fit = fit_e1(frame, pair_counts=pairs)
    profiles = profiles_table(
        fit,
        frame,
        pairs,
        combinations,
        age_references,
        gestante,
        minimum_cases=int(cfg.get("supressao_min_celula", 10)),
    )
    write_e1_reports(
        fit,
        Path(cfg["caminhos"]["relatorios"]) / "e1",
        reference_profile,
        profiles,
    )
    model = compact_e1(fit)
    metadata = _metadata(
        cfg,
        frame,
        [
            "idade_anos",
            "sexo",
            "gestante",
            *COMORBIDADES,
            *[f"{first}:{second}" for first, second in fit.eligible_pairs],
        ],
        {"convergiu": bool(fit.result.mle_retvals.get("converged", False))},
    )
    target = Path(cfg["caminhos"]["modelos"]) / "e1_final.joblib"
    return save_bundle(model, target, metadata)


def train_final_b1(
    cfg: dict[str, Any],
    frame: pd.DataFrame,
    validation_metrics: dict[str, Any],
) -> Path:
    """Ajusta baseline B1 em todo o desenvolvimento."""
    _assert_development_years(cfg, frame)
    features = build_feature_frame(frame)
    model = make_b1_pipeline(int(cfg["seed"]))
    columns = B1_NUMERIC + B1_CATEGORICAL
    model.fit(features[columns], frame["y"].to_numpy(dtype=np.int8))
    metadata = _metadata(cfg, frame, columns, validation_metrics)
    target = Path(cfg["caminhos"]["modelos"]) / "b1_final.joblib"
    return save_bundle(model, target, metadata)


def train_final_m1(
    cfg: dict[str, Any],
    frame: pd.DataFrame,
    familia: str,
    params: dict[str, Any],
    calibrator: Any,
    threshold: float,
    best_points: dict[str, int | None],
    validation_metrics: dict[str, Any],
) -> Path:
    """Retreina o M1 selecionado sem early stopping e congela bundle + proveniência."""
    _assert_development_years(cfg, frame)
    if familia not in {"elastic_net", "random_forest", "xgboost", "catboost", "mlp"}:
        raise ValueError(f"modelo final não suportado ou bloqueado: {familia}")
    if set(best_points) != set(REGIONS):
        raise ValueError(f"best_points deve conter exatamente as regiões: {REGIONS}")
    if not np.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("threshold deve ser finito e estar entre 0 e 1")
    if not callable(getattr(calibrator, "transform", None)):
        raise TypeError("calibrator deve implementar transform(probabilities)")

    iterative = familia in {"random_forest", "xgboost", "catboost", "mlp"}
    if iterative:
        points = list(best_points.values())
        if any(point is None or int(point) < 1 for point in points):
            raise ValueError("modelos iterativos precisam de 5 melhores pontos positivos")
        n_estimators = int(statistics.median(map(int, points)))
    else:
        n_estimators = None

    model_params = params.copy()
    if familia == "xgboost":
        model_params.pop("early_stopping_rounds", None)
        model_params["n_estimators"] = n_estimators
    elif familia == "catboost":
        model_params["iterations"] = n_estimators
    elif familia == "random_forest":
        model_params["n_estimators"] = n_estimators
    elif familia == "mlp":
        model_params["epochs"] = n_estimators
        model_params["early_stopping"] = False

    family, estimator, _ = _make_model(familia, model_params, int(cfg["seed"]))
    preprocessor = make_preprocessor(
        family, interactions=(familia == "elastic_net")
    )
    features = build_feature_frame(frame)[FEATURE_COLUMNS]
    labels = frame["y"].to_numpy(dtype=np.int8)
    preprocessor.fit(features, labels)
    transformed = preprocessor.transform(features)
    if familia == "catboost":
        from dengue_sinan.preprocess import CATBOOST_CATEGORICAL_INDICES

        estimator.fit(
            transformed,
            labels,
            cat_features=list(CATBOOST_CATEGORICAL_INDICES),
            verbose=False,
        )
    else:
        estimator.fit(transformed, labels)
    if familia == "mlp":
        estimator.model_.to("cpu")
        estimator.device_ = torch.device("cpu")
    pipeline = Pipeline([("preprocess", preprocessor), ("model", estimator)])
    shap_background = None
    if familia == "mlp":
        shap_background = np.stack([
            transformed[labels == class_value].mean(axis=0)
            for class_value in (0, 1)
        ]).astype(np.float32)

    bundle = {
        "pipeline": pipeline,
        "calibrator": calibrator,
        "threshold": float(threshold),
        "probabilidade_b0": float(labels.mean()),
        "modelo": familia,
        "params": params,
        "best_points": best_points,
        "numero_iteracoes_final": n_estimators,
        "shap_background": shap_background,
    }
    demo_diagnostics = _check_demo_viability(
        pipeline,
        calibrator,
        features,
        labels,
        familia,
        shap_background=shap_background,
    )
    metadata = _metadata(
        cfg,
        frame,
        list(FEATURE_COLUMNS),
        validation_metrics,
    )
    target = Path(cfg["caminhos"]["modelos"]) / "m1_final.joblib"
    saved = save_bundle(bundle, target, metadata)
    digest = hashlib.sha256(saved.read_bytes()).hexdigest()
    digest_path = saved.with_suffix(saved.suffix + ".sha256")
    digest_path.write_text(f"{digest}  {saved.name}\n", encoding="ascii")
    size_path = saved.with_suffix(saved.suffix + ".diagnostico.json")
    size_path.write_text(
        (
            "{\n"
            f'  "tamanho_bytes": {saved.stat().st_size},\n'
            f'  "predicao_20_perfis_segundos": '
            f'{demo_diagnostics["predicao_20_perfis_segundos"]:.8f},\n'
            f'  "predicao_1_perfil_segundos": '
            f'{demo_diagnostics["predicao_1_perfil_segundos"]:.8f},\n'
            f'  "shap_local_1_perfil_segundos": '
            f'{demo_diagnostics["shap_local_1_perfil_segundos"]:.8f}\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    return saved
