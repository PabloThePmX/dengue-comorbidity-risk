"""Baselines B0, B1 e B2 usados para comparação com os modelos preditivos."""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

from dengue_sinan.config import load_config
from dengue_sinan.dataset import COMORBIDITY_FEATURES, build_feature_frame
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
from dengue_sinan.reporting import markdown_table

B1_CATEGORICAL = ["sexo", "gestante", *COMORBIDITY_FEATURES]
B1_NUMERIC = ["n_comorbidades"]


def rule_b2(df: pd.DataFrame) -> np.ndarray:
    """Regra binária do grupo B do protocolo clínico (baseline B2)."""
    if "idade_anos" in df:
        age = pd.to_numeric(df["idade_anos"], errors="coerce")
    elif "NU_IDADE_N" in df:
        raise ValueError("Derive idade_anos antes de aplicar B2.")
    else:
        raise ValueError("B2 requer idade_anos.")
    if "gestante" not in df:
        raise ValueError("B2 requer gestante.")
    flags = age.lt(2) | age.gt(65) | df["gestante"].fillna(False).astype(bool)
    for source, target in zip(COMORBIDADES, COMORBIDITY_FEATURES, strict=True):
        column = target if target in df else source
        if column not in df:
            raise ValueError(f"B2 requer a variável {source}.")
        flags |= code(df[column]).eq("1") | df[column].eq("Sim")
    for column in ("LACO", "PETEQUIA_N"):
        if column not in df and column.lower() not in df:
            raise ValueError(f"B2 requer a variável {column}.")
        value = df[column] if column in df else df[column.lower()]
        flags |= code(value).eq("1") | value.eq("Sim")
    return flags.to_numpy(dtype=bool)


def _b1_pipeline() -> Pipeline:
    preprocessor = ColumnTransformer(
        [
            (
                "idade",
                Pipeline(
                    [
                        ("spline", SplineTransformer(n_knots=5, degree=3)),
                        ("scale", StandardScaler()),
                    ]
                ),
                ["idade_anos"],
            ),
            ("categoricas", OneHotEncoder(handle_unknown="ignore"), B1_CATEGORICAL),
            ("numericas", "passthrough", B1_NUMERIC),
        ],
        remainder="drop",
    )
    return Pipeline(
        [
            ("preprocessamento", preprocessor),
            ("modelo", LogisticRegression(penalty=None, max_iter=1000)),
        ]
    )


def _fold_metrics(y: np.ndarray, probability: np.ndarray, threshold: float) -> dict:
    result = {
        "pr_auc": pr_auc(y, probability),
        "brier": brier(y, probability),
        "roc_auc": roc_auc(y, probability),
        **calibration_slope_intercept(y, probability),
    }
    if threshold is not None:
        result.update(threshold_metrics(y, probability, threshold))
    return result


def run_baselines(df: pd.DataFrame, limiar: float = 0.01) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Gera predições OOF e métricas LORO dos três baselines."""
    assert_dev_only(df)
    if "y" not in df:
        raise ValueError("DataFrame deve conter o desfecho y.")
    features = build_feature_frame(df)
    b2 = rule_b2(df)
    oof = pd.DataFrame(
        {
            "ANO": df["ANO"].to_numpy(),
            "regiao": df["regiao"].to_numpy(),
            "y": df["y"].to_numpy(dtype=int),
            "b0": np.nan,
            "b1": np.nan,
            "b2": b2,
        }
    )
    per_fold = []
    for region, train_idx, valid_idx in loro_folds(df):
        y_train = df["y"].to_numpy()[train_idx]
        y_valid = df["y"].to_numpy()[valid_idx]
        prevalence = float(y_train.mean())
        oof.loc[valid_idx, "b0"] = prevalence
        model = _b1_pipeline()
        model.fit(features.iloc[train_idx], y_train)
        oof.loc[valid_idx, "b1"] = model.predict_proba(features.iloc[valid_idx])[:, 1]
        per_fold.append(
            {
                "regiao": region,
                "B0": _fold_metrics(y_valid, oof.loc[valid_idx, "b0"].to_numpy(), limiar),
                "B1": _fold_metrics(y_valid, oof.loc[valid_idx, "b1"].to_numpy(), limiar),
                "B2": threshold_metrics(y_valid, b2[valid_idx].astype(float), 0.5),
            }
        )

    metrics = []
    for name in ("b0", "b1"):
        metrics.append({"modelo": name.upper(), **_fold_metrics(oof["y"], oof[name], limiar)})
    metrics.append(
        {
            "modelo": "B2",
            **threshold_metrics(oof["y"], oof["b2"].astype(float), 0.5),
        }
    )
    for fold in per_fold:
        for model in ("B0", "B1", "B2"):
            metrics.append({"modelo": model, "regiao": fold["regiao"], **fold[model]})
    return pd.DataFrame(metrics), oof


def write_baseline_report(metrics: pd.DataFrame, path: str | Path) -> Path:
    """Escreve a tabela agregada dos baselines, sem predições por paciente."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("# Baselines\n\n" + markdown_table(metrics) + "\n", encoding="utf-8")
    return output


def run_and_log_baselines(
    df: pd.DataFrame, cfg: dict | str | Path
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Executa baselines, salva relatório agregado e registra OOF no MLflow."""
    from dengue_sinan.tracking import log_fold_metrics, log_oof_predictions, start_run

    config = load_config(cfg) if isinstance(cfg, (str, Path)) else cfg
    metrics, oof = run_baselines(df)
    report_path = Path(config["caminhos"]["relatorios"]) / "baselines.md"
    write_baseline_report(metrics, report_path)
    for model_name in ("B0", "B1", "B2"):
        with start_run(config, f"baseline-{model_name.lower()}"):
            model_metrics = metrics[metrics["modelo"] == model_name]
            for row in model_metrics.to_dict("records"):
                if "regiao" in row:
                    log_fold_metrics(
                        row["regiao"],
                        {
                            key: value
                            for key, value in row.items()
                            if key not in {"modelo", "regiao"} and pd.notna(value)
                        },
                    )
            log_oof_predictions(oof[["ANO", "regiao", "y", model_name.lower()]], config,
                               model_name.lower())
    return metrics, oof