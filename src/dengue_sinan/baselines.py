"""Baselines B0 (prevalência), B1 (logística simples) e B2 (protocolo MS) (T-2.8, FR-04)."""

from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

from dengue_sinan import profiling
from dengue_sinan.artifacts import save_bundle
from dengue_sinan.dataset import COMORBIDADES, build_feature_frame
from dengue_sinan.folds import DEFAULT_FOLD_ORDER, loro_folds
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.metrics import (
    best_f2_threshold,
    brier,
    calibration_slope_intercept,
    pr_auc,
    roc_auc,
    threshold_metrics,
)
from dengue_sinan.tracking import log_fold_metrics, log_oof_predictions, start_run
from dengue_sinan.verify import check, write_report

B1_FEATURES = ["idade_anos", "sexo", "gestante", *COMORBIDADES, "n_comorbidades"]


def _is_sim(series: pd.Series) -> pd.Series:
    cleaned = series.astype("string").str.strip()
    return cleaned.isin({"Sim", "1", "True", "true"})


def rule_b2(df: pd.DataFrame) -> np.ndarray:
    """Regra binária do Grupo B do protocolo do MS (T-2.8, §3.10):

    "Alto risco" (`True`) se qualquer condição for verdadeira:
    - `idade_anos < 2` ou `idade_anos > 65`;
    - `gestante == 1` (ou True);
    - `>= 1` comorbidade = Sim (ou `n_comorbidades >= 1`);
    - `LACO` = Sim ou `PETEQUIA_N` = Sim.
    """
    idade = pd.to_numeric(df["idade_anos"], errors="coerce")
    age_risk = (idade < 2.0) | (idade > 65.0)

    if "gestante" in df.columns:
        gest_risk = df["gestante"].astype("string").isin({"1", "True", "true"})
    else:
        gest_risk = profiling.code(df["CS_GESTANT"]).isin({"1", "2", "3", "4"})

    if "n_comorbidades" in df.columns:
        comorb_risk = pd.to_numeric(df["n_comorbidades"], errors="coerce").fillna(0) >= 1
    else:
        comorb_risk = pd.Series(False, index=df.index)
        for c in COMORBIDADES:
            if c in df.columns:
                comorb_risk = comorb_risk | _is_sim(df[c])

    bleed_risk = pd.Series(False, index=df.index)
    for col in ("LACO", "PETEQUIA_N"):
        if col in df.columns:
            bleed_risk = bleed_risk | _is_sim(df[col])

    result = (age_risk.fillna(False) | gest_risk.fillna(False) | comorb_risk | bleed_risk).to_numpy(
        dtype=bool
    )
    return result


def make_b1_pipeline(seed: int = 20261103) -> Pipeline:
    """Cria o Pipeline sklearn do baseline B1 (logística sem penalização e sem pesos — R3, R5)."""
    age_pipe = Pipeline(
        [
            ("spline", SplineTransformer(n_knots=5, degree=3, include_bias=False)),
            ("scaler", StandardScaler()),
        ]
    )
    cat_cols = ["sexo", *COMORBIDADES]
    preprocessor = ColumnTransformer(
        transformers=[
            ("idade", age_pipe, ["idade_anos"]),
            ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), cat_cols),
            ("n_comorb", StandardScaler(), ["n_comorbidades"]),
            ("gestante", "passthrough", ["gestante"]),
        ],
        remainder="drop",
    )
    clf = LogisticRegression(
        penalty=None,
        solver="lbfgs",
        max_iter=500,
        random_state=int(seed),
    )
    return Pipeline([("preprocess", preprocessor), ("clf", clf)])


def _evaluate_prob_oof(
    y: np.ndarray,
    oof_p: np.ndarray,
    folds: list[tuple[str, np.ndarray, np.ndarray]],
    limiar: float,
) -> tuple[dict[str, float], dict[str, dict[str, float]]]:
    """Calcula métricas por dobra e agrupadas no OOF."""
    by_fold: dict[str, dict[str, float]] = {}
    for regiao, _, idx_val in folds:
        yv, pv = y[idx_val], oof_p[idx_val]
        cal = calibration_slope_intercept(yv, pv)
        by_fold[regiao] = {
            "pr_auc": pr_auc(yv, pv),
            "brier": brier(yv, pv),
            "roc_auc": roc_auc(yv, pv),
            "slope": cal.slope,
            "intercept": cal.intercept,
        }

    cal_all = calibration_slope_intercept(y, oof_p)
    thresh = threshold_metrics(y, oof_p, limiar)
    overall = {
        "pr_auc_oof": pr_auc(y, oof_p),
        "pr_auc_media_dobras": float(np.mean([m["pr_auc"] for m in by_fold.values()])),
        "brier_oof": brier(y, oof_p),
        "roc_auc_oof": roc_auc(y, oof_p),
        "slope_oof": cal_all.slope,
        "intercept_oof": cal_all.intercept,
        **thresh,
    }
    return overall, by_fold


def run_baselines(cfg: dict[str, Any], df: pd.DataFrame) -> dict[str, Any]:
    """Executa B0, B1 e B2 nas 5 dobras LORO, registra no MLflow e salva `reports/baselines.md`."""
    assert_dev_only(df)
    feat = build_feature_frame(df) if "n_comorbidades" not in df.columns else df
    ordem = cfg.get("ordem_dobras", DEFAULT_FOLD_ORDER)
    seed = int(cfg.get("seed", 20261103))

    folds = loro_folds(feat, ordem_dobras=ordem)
    y = feat["y"].to_numpy(dtype=np.int8)
    n = len(feat)

    # 1. B0 — Prevalência do treino de cada dobra
    oof_b0 = np.zeros(n, dtype=np.float64)
    for _, idx_train, idx_val in folds:
        oof_b0[idx_val] = float(y[idx_train].mean())

    # No limiar, B0 prevê "ninguém agrava" (limiar > max(oof_b0))
    b0_overall, b0_folds = _evaluate_prob_oof(y, oof_b0, folds, limiar=1.0)
    with start_run(cfg, "baseline-B0", tags={"baseline": "B0"}):
        for reg, m in b0_folds.items():
            log_fold_metrics(reg, m)
        mlflow.log_metrics(b0_overall)
        log_oof_predictions(
            pd.DataFrame({"y": y, "p_oof": oof_b0, "regiao": feat["regiao"]}),
            "B0",
            cfg,
        )

    # 2. B1 — Logística simples sem penalização (dentro de Pipeline por dobra — R5)
    oof_b1 = np.zeros(n, dtype=np.float64)
    X_b1 = feat[B1_FEATURES]
    for _, idx_train, idx_val in folds:
        pipe = make_b1_pipeline(seed=seed)
        pipe.fit(X_b1.iloc[idx_train], y[idx_train])
        oof_b1[idx_val] = pipe.predict_proba(X_b1.iloc[idx_val])[:, 1]

    limiar_b1 = best_f2_threshold(y, oof_b1)
    b1_overall, b1_folds = _evaluate_prob_oof(y, oof_b1, folds, limiar=limiar_b1)
    with start_run(cfg, "baseline-B1", tags={"baseline": "B1"}):
        for reg, m in b1_folds.items():
            log_fold_metrics(reg, m)
        mlflow.log_metrics(b1_overall)
        log_oof_predictions(
            pd.DataFrame({"y": y, "p_oof": oof_b1, "regiao": feat["regiao"]}),
            "B1",
            cfg,
        )

    # 3. B2 — Regra do protocolo MS (binária, sem PR-AUC)
    pred_b2 = rule_b2(feat).astype(np.float64)
    b2_thresh = threshold_metrics(y, pred_b2, limiar=0.5)
    with start_run(cfg, "baseline-B2", tags={"baseline": "B2"}):
        mlflow.log_metrics(b2_thresh)
        log_oof_predictions(
            pd.DataFrame({"y": y, "alto_risco": pred_b2.astype(bool), "regiao": feat["regiao"]}),
            "B2",
            cfg,
        )

    summary_table = pd.DataFrame(
        [
            {
                "Modelo": "B0 (Prevalência)",
                "PR-AUC OOF": b0_overall["pr_auc_oof"],
                "PR-AUC média dobras": b0_overall["pr_auc_media_dobras"],
                "Brier": b0_overall["brier_oof"],
                "ROC-AUC": b0_overall["roc_auc_oof"],
                "Slope": b0_overall["slope_oof"],
                "Limiar": b0_overall["limiar"],
                "Acurácia": b0_overall["acuracia"],
                "Precisão": b0_overall["precisao"],
                "Recall": b0_overall["recall"],
                "F1": b0_overall["f1"],
                "F2": b0_overall["f2"],
            },
            {
                "Modelo": "B1 (Logística simples)",
                "PR-AUC OOF": b1_overall["pr_auc_oof"],
                "PR-AUC média dobras": b1_overall["pr_auc_media_dobras"],
                "Brier": b1_overall["brier_oof"],
                "ROC-AUC": b1_overall["roc_auc_oof"],
                "Slope": b1_overall["slope_oof"],
                "Limiar": b1_overall["limiar"],
                "Acurácia": b1_overall["acuracia"],
                "Precisão": b1_overall["precisao"],
                "Recall": b1_overall["recall"],
                "F1": b1_overall["f1"],
                "F2": b1_overall["f2"],
            },
            {
                "Modelo": "B2 (Regra protocolo MS)",
                "PR-AUC OOF": np.nan,
                "PR-AUC média dobras": np.nan,
                "Brier": np.nan,
                "ROC-AUC": np.nan,
                "Slope": np.nan,
                "Limiar": 0.5,
                "Acurácia": b2_thresh["acuracia"],
                "Precisão": b2_thresh["precisao"],
                "Recall": b2_thresh["recall"],
                "F1": b2_thresh["f1"],
                "F2": b2_thresh["f2"],
            },
        ]
    )

    reports_dir = Path(cfg.get("caminhos", {}).get("relatorios", "reports"))
    reports_dir.mkdir(parents=True, exist_ok=True)
    baselines_md = reports_dir / "baselines.md"
    baselines_md.write_text(
        "# Baselines B0, B1 e B2 — Desenvolvimento (2022–2023)\n\n"
        f"{profiling.markdown_table(summary_table, decimals=4)}\n",
        encoding="utf-8",
    )

    # Salva o artefato congelado de B1 ajustado em todo 2022–2023 para avaliação em T-5.1
    default_models_dir = reports_dir.parent / "models"
    models_dir = Path(cfg.get("caminhos", {}).get("modelos", default_models_dir))
    models_dir.mkdir(parents=True, exist_ok=True)
    b1_full_pipe = make_b1_pipeline(seed=seed)
    b1_full_pipe.fit(feat[B1_FEATURES], y)
    b1_bundle_path = save_bundle(
        b1_full_pipe,
        models_dir / "b1.joblib",
        cfg=cfg,
        extra_metadata={
            "modelo_tipo": "B1-logistica-perfil",
            "prev_dev": float(y.mean()),
            "limiar_f2": float(limiar_b1),
        },
    )

    b0_ret = {
        **b0_overall,
        "pr_auc_media": b0_overall["pr_auc_media_dobras"],
        "pr_auc_por_dobra": {r: m["pr_auc"] for r, m in b0_folds.items()},
        "oof_p": oof_b0,
    }
    b1_ret = {
        **b1_overall,
        "pr_auc_media": b1_overall["pr_auc_media_dobras"],
        "pr_auc_por_dobra": {r: m["pr_auc"] for r, m in b1_folds.items()},
        "oof_p": oof_b1,
    }

    return {
        "b0": b0_ret,
        "b1": b1_ret,
        "b2": b2_thresh,
        "b0_folds": b0_folds,
        "b1_folds": b1_folds,
        "baselines_md": baselines_md,
        "b1_bundle_path": b1_bundle_path,
    }


def verify_t2_8(
    cfg: dict[str, Any],
    df: pd.DataFrame,
    *,
    out_dir: str | Path | None = None,
) -> Path:
    """Executa os baselines B0, B1, B2 e grava o relatório `T-2.8.json` (D-56)."""
    res = run_baselines(cfg, df)
    prev_dev = float(df["y"].mean())
    b0_prauc = float(res["b0"]["pr_auc_oof"])
    b1_prauc = float(res["b1"]["pr_auc_oof"])

    dest_dir = (
        Path(out_dir)
        if out_dir is not None
        else Path(cfg.get("caminhos", {}).get("relatorios", "reports")) / "verificacao"
    )
    checks = [
        check(
            "b0_pr_auc_aprox_prevalencia",
            round(prev_dev, 4),
            round(b0_prauc, 4),
            tolerancia=0.0005,
        ),
        check("b1_supera_b0_em_pr_auc", True, bool(b1_prauc > b0_prauc)),
        check("b2_f2_calculado", True, bool(res["b2"]["f2"] >= 0.0)),
        check("baselines_md_existe", True, res["baselines_md"].is_file()),
    ]
    return write_report("T-2.8", checks, dest_dir, cfg)
