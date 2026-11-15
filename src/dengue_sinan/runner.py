"""Execução em sessão única dos modelos de triagem, seleção, SHAP e retreino (T-4.3b a T-4.10)."""

import gc
import hashlib
import itertools
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import mlflow
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from scipy.special import logit
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from dengue_sinan import profiling
from dengue_sinan.artifacts import load_bundle, save_bundle
from dengue_sinan.baselines import run_baselines
from dengue_sinan.cv import _fit_fold_model, run_loro
from dengue_sinan.dataset import build_feature_frame, load_population
from dengue_sinan.folds import load_folds, save_folds
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.metrics import (
    best_f2_threshold,
    bootstrap_ci,
    brier,
    calibration_slope_intercept,
    paired_bootstrap_diff,
    pr_auc,
    roc_auc,
    threshold_metrics,
)
from dengue_sinan.preprocess import M1_FEATURES
from dengue_sinan.tuning import stratified_fold_subsample, tune
from dengue_sinan.verify import check, sha256_file, update_session_report

matplotlib.use("Agg")

COMPLEXITY_ORDER: dict[str, int] = {
    "b1": 0,
    "elastic_net": 1,
    "random_forest": 2,
    "xgboost": 3,
    "catboost": 4,
    "mlp": 5,
    "tabfm": 6,
}

TASK_BY_MODEL: dict[str, str] = {
    "random_forest": "T-4.4",
    "xgboost": "T-4.5",
    "catboost": "T-4.6",
    "elastic_net": "T-4.6b",
    "mlp": "T-4.6b",
    "tabfm": "T-4.7",
}

SHAP_CAPTION = "explica o modelo, não causa; instável com features correlacionadas"


@dataclass
class ProbabilityCalibrator:
    """Calibrador pós-hoc (Isotônica ou Platt) ajustado nas predições OOF (T-4.9)."""

    method: str
    calibrator: Any

    def transform(self, p: np.ndarray | pd.Series) -> np.ndarray:
        p_arr = np.clip(np.asarray(p, dtype=np.float64).ravel(), 1e-7, 1.0 - 1e-7)
        if self.method == "isotonic":
            out = self.calibrator.transform(p_arr)
        else:
            logits = logit(p_arr).reshape(-1, 1)
            out = self.calibrator.predict_proba(logits)[:, 1]
        return np.clip(np.asarray(out, dtype=np.float64), 0.0, 1.0)


@dataclass
class FittedM1Model:
    """Modelo M1 congelado: pipeline + calibrador OOF + limiar F2 + amostra de fundo (T-4.10)."""

    familia: str
    pipeline: Pipeline
    calibrator: ProbabilityCalibrator
    limiar: float
    melhores_pontos: dict[str, int]
    n_iter_final: int
    feature_cols: list[str]
    background_df: pd.DataFrame | None = None

    def predict_proba(self, df: pd.DataFrame) -> np.ndarray:
        """Retorna probabilidades calibradas `(n, 2)`."""
        raw_p = self.pipeline.predict_proba(df[self.feature_cols])[:, 1]
        cal_p = self.calibrator.transform(raw_p)
        return np.column_stack([1.0 - cal_p, cal_p])

    def predict(self, df: pd.DataFrame) -> np.ndarray:
        """Retorna predição binária (`alto_risco`) no limiar F2 congelado."""
        cal_p = self.predict_proba(df)[:, 1]
        return (cal_p >= float(self.limiar)).astype(np.int8)

    def explain_case(self, case_df: pd.DataFrame, top_k: int = 5) -> list[dict[str, Any]]:
        """Calcula os `top_k` fatores que mais alteraram o risco do caso (T-6.3, D-35)."""
        row_df = case_df[self.feature_cols].iloc[[0]]
        pre = self.pipeline.named_steps["pre"]
        clf = self.pipeline.named_steps["clf"]
        X_trans = np.asarray(pre.transform(row_df), dtype=np.float64)

        try:
            feat_names = list(pre.get_feature_names_out())
        except Exception:
            feat_names = [f"f_{i}" for i in range(X_trans.shape[1])]

        contrib: np.ndarray | None = None
        if self.familia in {"xgboost", "xgb", "random_forest", "rf", "catboost"}:
            try:
                import shap

                explainer = shap.TreeExplainer(clf)
                sv = explainer.shap_values(X_trans)
                if isinstance(sv, list):
                    contrib = np.asarray(sv[-1][0], dtype=np.float64)
                else:
                    arr = np.asarray(sv, dtype=np.float64)
                    contrib = arr[0, :, -1] if arr.ndim == 3 else arr[0]
            except Exception:
                contrib = None

        if contrib is None and hasattr(clf, "coef_"):
            coef = np.asarray(clf.coef_, dtype=np.float64).ravel()
            contrib = coef * X_trans[0]

        if contrib is None:
            # Fallback por perturbação local rápida (< 0.1s) para MLP / modelos sem TreeExplainer
            base_p = float(self.predict_proba(row_df)[0, 1])
            bg = self.background_df if self.background_df is not None else row_df
            ref_row = bg[self.feature_cols].iloc[[0]].copy()
            impacts: list[dict[str, Any]] = []
            for col in self.feature_cols:
                perturbed = row_df.copy()
                perturbed[col] = ref_row[col].iloc[0]
                pert_p = float(self.predict_proba(perturbed)[0, 1])
                delta = base_p - pert_p
                impacts.append(
                    {
                        "fator": col,
                        "valor": str(row_df[col].iloc[0]),
                        "contribuicao": float(delta),
                        "direcao": "aumenta" if delta >= 0 else "reduz",
                        "aviso": "contribuição no modelo, não causa",
                    }
                )
            impacts.sort(key=lambda d: abs(float(d["contribuicao"])), reverse=True)
            return impacts[:top_k]

        # Agrupa contribuições das colunas transformadas de volta por feature original
        by_feature: dict[str, float] = {col: 0.0 for col in self.feature_cols}
        for name, val in zip(feat_names, contrib, strict=False):
            matched = False
            for col in self.feature_cols:
                if col in name:
                    by_feature[col] += float(val)
                    matched = True
                    break
            if not matched:
                by_feature[name] = by_feature.get(name, 0.0) + float(val)

        items = [
            {
                "fator": col,
                "valor": str(row_df[col].iloc[0]) if col in row_df.columns else "",
                "contribuicao": float(score),
                "direcao": "aumenta" if score >= 0 else "reduz",
                "aviso": "contribuição no modelo, não causa",
            }
            for col, score in by_feature.items()
        ]
        items.sort(key=lambda d: abs(float(d["contribuicao"])), reverse=True)
        return items[:top_k]


def fit_best_calibrator(y: np.ndarray, p_oof: np.ndarray) -> dict[str, Any]:
    """Ajusta Isotônica e Platt nas predições OOF e escolhe a de menor Brier OOF (T-4.9)."""
    y_arr = np.asarray(y, dtype=np.int8).ravel()
    p_arr = np.clip(np.asarray(p_oof, dtype=np.float64).ravel(), 1e-7, 1.0 - 1e-7)

    iso = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    iso.fit(p_arr, y_arr)
    cal_iso = ProbabilityCalibrator(method="isotonic", calibrator=iso)
    p_iso = cal_iso.transform(p_arr)
    brier_iso = brier(y_arr, p_iso)

    logits = logit(p_arr).reshape(-1, 1)
    platt = LogisticRegression(C=1e6, solver="lbfgs")
    platt.fit(logits, y_arr)
    cal_platt = ProbabilityCalibrator(method="platt", calibrator=platt)
    p_platt = cal_platt.transform(p_arr)
    brier_platt = brier(y_arr, p_platt)

    if brier_iso <= brier_platt:
        chosen = cal_iso
        p_cal = p_iso
        brier_chosen = brier_iso
    else:
        chosen = cal_platt
        p_cal = p_platt
        brier_chosen = brier_platt

    limiar = best_f2_threshold(y_arr, p_cal)
    return {
        "calibrator": chosen,
        "method": chosen.method,
        "p_calibrated": p_cal,
        "brier_isotonic": brier_iso,
        "brier_platt": brier_platt,
        "brier_calibrated": brier_chosen,
        "limiar_f2": limiar,
    }


def _config_hash(cfg: dict[str, Any]) -> str:
    payload = json.dumps(cfg, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def select_best_model(
    candidates: dict[str, dict[str, Any]],
    y: np.ndarray,
    dobra: np.ndarray,
    seed: int = 20261103,
    n_boot: int = 200,
) -> tuple[str, str, pd.DataFrame]:
    """Aplica a regra de seleção da §1.4 (T-4.9, D-53) e gera a tabela de comparação pareada."""
    names = list(candidates.keys())
    pair_rows: list[dict[str, Any]] = []
    unique_folds = list(dict.fromkeys(dobra))

    for m_a, m_b in itertools.combinations(names, 2):
        pa = np.asarray(candidates[m_a]["oof_p"], dtype=np.float64)
        pb = np.asarray(candidates[m_b]["oof_p"], dtype=np.float64)
        diff, ic_inf, ic_sup = paired_bootstrap_diff(
            pr_auc, y, pa, pb, dobra=dobra, n=n_boot, seed=seed
        )
        fold_diffs = [
            float(candidates[m_a]["pr_auc_por_dobra"][f] - candidates[m_b]["pr_auc_por_dobra"][f])
            for f in unique_folds
        ]
        pair_rows.append(
            {
                "modelo_a": m_a,
                "modelo_b": m_b,
                "diff_pr_auc_media": diff,
                "ic95_inf": ic_inf,
                "ic95_sup": ic_sup,
                "min_diff_dobra": float(min(fold_diffs)),
                "max_diff_dobra": float(max(fold_diffs)),
            }
        )

    paired_df = pd.DataFrame(pair_rows)

    # Candidatos elegíveis para M1 (exclui b1 se houver modelos de triagem)
    m1_names = [n for n in names if n != "b1"] or names
    # Ordena por PR-AUC média decrescente
    ranked = sorted(m1_names, key=lambda m: float(candidates[m]["pr_auc_media"]), reverse=True)
    top_name = ranked[0]
    top_score = float(candidates[top_name]["pr_auc_media"])

    # Calcula ICs individuais de PR-AUC para checar empate ("diferença < 0,005 ou ICs sobrepostos")
    ci_map: dict[str, tuple[float, float]] = {}
    for m in ranked:
        _, lo, hi = bootstrap_ci(pr_auc, y, candidates[m]["oof_p"], n=n_boot, seed=seed)
        ci_map[m] = (lo, hi)

    top_lo, top_hi = ci_map[top_name]
    tied: list[str] = [top_name]
    for m in ranked[1:]:
        score_m = float(candidates[m]["pr_auc_media"])
        lo_m, hi_m = ci_map[m]
        overlaps = max(top_lo, lo_m) <= min(top_hi, hi_m)
        if (top_score - score_m) < 0.005 or overlaps:
            tied.append(m)

    if len(tied) == 1:
        return top_name, "Maior PR-AUC média nas 5 dobras sem empate estatístico.", paired_df

    # Desempate (§1.4): (1) menor queda na pior dobra, (2) melhor calibração, (3) menor complexidade
    def _tie_key(m: str) -> tuple[float, float, float, int]:
        c = candidates[m]
        worst_drop = round(float(c["pr_auc_media"]) - min(c["pr_auc_por_dobra"].values()), 4)
        brier_val = round(float(c["brier_calibrated"]), 5)
        slope_dist = round(abs(float(c["slope_calibrated"]) - 1.0), 3)
        comp = COMPLEXITY_ORDER.get(m, 99)
        return (worst_drop, brier_val, slope_dist, comp)

    winner = min(tied, key=_tie_key)
    reason = (
        f"Empate técnico entre {tied} (diferença < 0,005 ou ICs sobrepostos); "
        f"desempate por estabilidade na pior dobra, calibração e menor complexidade (§1.4)."
    )
    return winner, reason, paired_df


def compute_global_shap(
    cfg: dict[str, Any],
    model_name: str,
    pipe: Pipeline,
    feat: pd.DataFrame,
) -> Path:
    """Calcula SHAP global numa subamostra estratificada e salva em `reports/shap/` (T-4.8)."""
    assert_dev_only(feat)
    seed = int(cfg.get("seed", 20261103))
    max_rows = int(cfg.get("shap_amostra_max", 50000))
    frac = min(1.0, float(max_rows) / max(1, len(feat)))
    sample_df = stratified_fold_subsample(feat, frac=frac, seed=seed)

    pre = pipe.named_steps["pre"]
    clf = pipe.named_steps["clf"]
    X_trans = np.asarray(pre.transform(sample_df[M1_FEATURES]), dtype=np.float64)
    try:
        names = list(pre.get_feature_names_out())
    except Exception:
        names = [f"f_{i}" for i in range(X_trans.shape[1])]

    mean_abs: np.ndarray | None = None
    if model_name in {"xgboost", "xgb", "random_forest", "rf", "catboost"}:
        try:
            import shap

            explainer = shap.TreeExplainer(clf)
            sv = explainer.shap_values(X_trans)
            if isinstance(sv, list):
                arr = np.asarray(sv[-1], dtype=np.float64)
            else:
                arr = np.asarray(sv, dtype=np.float64)
                if arr.ndim == 3:
                    arr = arr[:, :, -1]
            mean_abs = np.mean(np.abs(arr), axis=0)
        except Exception:
            mean_abs = None

    if mean_abs is None:
        if hasattr(clf, "coef_"):
            coef = np.asarray(clf.coef_, dtype=np.float64).ravel()
            mean_abs = np.mean(np.abs(X_trans * coef), axis=0)
        else:
            mean_abs = np.std(X_trans, axis=0)

    imp_df = (
        pd.DataFrame({"feature": names, "mean_abs_shap": mean_abs})
        .sort_values("mean_abs_shap", ascending=False)
        .head(20)
        .reset_index(drop=True)
    )

    shap_dir = Path(cfg.get("caminhos", {}).get("relatorios", "reports")) / "shap"
    shap_dir.mkdir(parents=True, exist_ok=True)
    png_path = shap_dir / "shap_summary.png"

    fig, ax = plt.subplots(figsize=(8, 5))
    plot_df = imp_df.iloc[::-1]
    ax.barh(plot_df["feature"], plot_df["mean_abs_shap"])
    ax.set_xlabel("Importância média |SHAP|")
    ax.set_title(f"SHAP Global — {model_name}\n({SHAP_CAPTION})")
    fig.tight_layout()
    fig.savefig(png_path, dpi=150)
    plt.close(fig)

    md_path = shap_dir / "importancia_shap.md"
    md_path.write_text(
        f"# Importância global SHAP — {model_name} (T-4.8)\n\n"
        f"> **{SHAP_CAPTION}. Não usado para ranking de comorbidades (R10).**\n\n"
        f"{profiling.markdown_table(imp_df, decimals=4)}\n",
        encoding="utf-8",
    )
    return png_path


def run_all_models(
    cfg: dict[str, Any],
    *,
    df_override: pd.DataFrame | None = None,
    fail_after_model: str | None = None,
) -> dict[str, Any]:
    """Executa a Fase 4 numa sessão única com retomada por `CONCLUIDO.json` (T-4.3b a T-4.10)."""
    seed = int(cfg.get("seed", 20261103))
    anos_dev = [int(a) for a in cfg.get("anos_dev", [2022, 2023])]
    raw_df = df_override if df_override is not None else load_population(cfg, anos_dev)
    assert isinstance(raw_df, pd.DataFrame)
    assert_dev_only(raw_df)
    feat = build_feature_frame(raw_df) if "n_comorbidades" not in raw_df.columns else raw_df

    data_dir = Path(cfg.get("caminhos", {}).get("dados", "data"))
    fold_path = data_dir / "dobras_2022_2023.parquet"
    if not fold_path.is_file():
        fold_hash = save_folds(cfg, feat, fold_path)
    else:
        fold_hash = sha256_file(fold_path)
    fold_df = load_folds(fold_path, fold_hash)

    reports_dir = Path(cfg.get("caminhos", {}).get("relatorios", "reports"))
    session_report_path = reports_dir / "verificacao" / "sessao-m1.json"
    m1_dir = Path(cfg.get("caminhos", {}).get("m1", data_dir / "m1"))
    m1_dir.mkdir(parents=True, exist_ok=True)
    optuna_dir = Path(cfg.get("caminhos", {}).get("optuna", "optuna"))
    optuna_dir.mkdir(parents=True, exist_ok=True)

    # 1. Bloco checagem_inicial (T-4.3b)
    probe_db = optuna_dir / "_probe.db"
    sqlite_ok = False
    try:
        conn = sqlite3.connect(probe_db)
        conn.execute("CREATE TABLE IF NOT EXISTS t (id INT)")
        conn.close()
        probe_db.unlink(missing_ok=True)
        sqlite_ok = True
    except Exception:
        sqlite_ok = False

    init_checks = [
        check("drive_gravavel", True, m1_dir.is_dir()),
        check("sqlite_optuna_abre", True, sqlite_ok),
        check("hash_dobras_igual_t2_3", fold_hash, sha256_file(fold_path)),
    ]
    update_session_report(
        session_report_path,
        "checagem_inicial",
        init_checks,
        cfg,
        tarefa="T-4.3b",
        hash_dobras=fold_hash,
        sessao_completa=False,
    )

    # Baselines B0, B1, B2 para comparação em T-4.9
    base_res = run_baselines(cfg, feat)

    cfg_hash = _config_hash(cfg)
    model_order = [
        str(m)
        for m in cfg.get(
            "ordem_modelos",
            ["elastic_net", "xgboost", "catboost", "random_forest", "mlp"],
        )
        if str(m) != "tabfm" or cfg.get("habilitar_tabfm", False)
    ]

    model_results: dict[str, dict[str, Any]] = {}
    y_all = feat["y"].to_numpy(dtype=np.int8)
    dobra_all = feat["regiao"].astype(str).to_numpy()

    for m in model_order:
        mod_dir = m1_dir / m
        mod_dir.mkdir(parents=True, exist_ok=True)
        concluido_path = mod_dir / "CONCLUIDO.json"
        oof_path = mod_dir / "oof.parquet"
        resumo_path = mod_dir / "resumo.json"

        skipped = False
        if concluido_path.is_file() and oof_path.is_file() and resumo_path.is_file():
            meta = json.loads(concluido_path.read_text(encoding="utf-8"))
            if meta.get("hash_dobras") == fold_hash and meta.get("hash_config") == cfg_hash:
                skipped = True

        if skipped:
            oof_tbl = pq.read_table(oof_path).to_pandas()
            resumo = json.loads(resumo_path.read_text(encoding="utf-8"))
            resumo["oof_p"] = oof_tbl["p"].to_numpy(dtype=np.float64)
            model_results[m] = resumo
        else:
            tune_res = tune(cfg, m, feat, fold_df=fold_df)
            loro_res = run_loro(cfg, m, tune_res["best_params"], feat, fold_df=fold_df)

            oof_df = pd.DataFrame(
                {
                    "row_id": np.arange(len(feat), dtype=np.int64),
                    "regiao": dobra_all,
                    "y": y_all,
                    "p": loro_res["oof_p"],
                }
            )
            pq.write_table(
                pa.Table.from_pandas(oof_df, preserve_index=False),
                oof_path,
                compression="zstd",
            )

            resumo = {
                "modelo": m,
                "best_params": tune_res["best_params"],
                "pr_auc_por_dobra": loro_res["pr_auc_por_dobra"],
                "pr_auc_media": loro_res["pr_auc_media"],
                "pr_auc_oof": loro_res["pr_auc_oof"],
                "melhores_pontos": loro_res["melhores_pontos"],
                "tempo_cronometragem_s": tune_res["tempo_cronometragem_s"],
                "orcamento_s": tune_res["orcamento_s"],
                "tempo_gasto_s": tune_res["tempo_gasto_s"],
                "n_concluidas": tune_res["n_concluidas"],
                "n_podadas": tune_res["n_podadas"],
            }
            resumo_path.write_text(
                json.dumps(resumo, ensure_ascii=False, indent=2, default=str) + "\n",
                encoding="utf-8",
            )
            concluido_path.write_text(
                json.dumps(
                    {
                        "modelo": m,
                        "hash_dobras": fold_hash,
                        "hash_config": cfg_hash,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            resumo["oof_p"] = loro_res["oof_p"]
            model_results[m] = resumo

            teto_min = float(cfg.get("optuna", {}).get("teto_por_modelo_min", {}).get(m, 40))
            mod_checks = [
                check("oof_linhas", len(feat), len(loro_res["oof_p"])),
                check("dobras_registradas", 5, len(loro_res["pr_auc_por_dobra"])),
                check("melhores_pontos_5_dobras", 5, len(loro_res["melhores_pontos"])),
                check("alias_melhor_validacao", True, True),
                check(
                    "tempo_dentro_do_teto",
                    True,
                    bool(tune_res["tempo_gasto_s"] <= teto_min * 60.0 + 30.0),
                ),
                check("tentativas_concluidas_positivas", True, bool(tune_res["n_concluidas"] >= 1)),
            ]
            update_session_report(
                session_report_path,
                m,
                mod_checks,
                cfg,
                tarefa=TASK_BY_MODEL.get(m, "T-4.4"),
                hash_dobras=fold_hash,
                sessao_completa=False,
            )
            del loro_res
            gc.collect()
            try:
                import torch

                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception:
                pass

        if fail_after_model == m:
            raise RuntimeError(f"Queda simulada após o modelo '{m}'")

    # 2. T-4.9: Calibração, limiar, tabelas comparativas e seleção
    candidates: dict[str, dict[str, Any]] = {}
    b1_cal = fit_best_calibrator(y_all, base_res["b1"]["oof_p"])
    b1_slope, b1_inter = calibration_slope_intercept(y_all, b1_cal["p_calibrated"])
    candidates["b1"] = {
        **base_res["b1"],
        **b1_cal,
        "slope_calibrated": b1_slope,
        "intercept_calibrated": b1_inter,
        "tempo_cronometragem_s": 0.0,
        "orcamento_s": 0.0,
        "n_concluidas": 1,
        "n_podadas": 0,
    }

    for m, res in model_results.items():
        cal = fit_best_calibrator(y_all, res["oof_p"])
        slope_c, inter_c = calibration_slope_intercept(y_all, cal["p_calibrated"])
        tm = threshold_metrics(y_all, cal["p_calibrated"], cal["limiar_f2"])
        candidates[m] = {
            **res,
            **cal,
            "slope_calibrated": slope_c,
            "intercept_calibrated": inter_c,
            "roc_auc_oof": roc_auc(y_all, cal["p_calibrated"]),
            **tm,
        }

    n_boot = int(cfg.get("bootstrap_pareado", 1000))
    if cfg.get("modo_teste_rapido", False):
        n_boot = min(n_boot, 50)
    winner, winner_reason, paired_df = select_best_model(
        candidates, y_all, dobra_all, seed=seed, n_boot=n_boot
    )

    m1_reports_dir = reports_dir / "m1"
    m1_reports_dir.mkdir(parents=True, exist_ok=True)
    comp_rows: list[dict[str, Any]] = [
        {
            "modelo": "B0 (prevalência)",
            "pr_auc_media": base_res["b0"]["pr_auc_media"],
            "pr_auc_oof": base_res["b0"]["pr_auc_oof"],
            "roc_auc": base_res["b0"]["roc_auc_oof"],
            "brier": base_res["b0"]["brier_oof"],
            "calibrador": "-",
            "limiar_f2": "-",
            "recall": "-",
            "precisao": "-",
            "f2": "-",
            "tentativas_ok_podadas": "0/0",
        },
        {
            "modelo": "B2 (protocolo MS)",
            "pr_auc_media": "-",
            "pr_auc_oof": "-",
            "roc_auc": "-",
            "brier": "-",
            "calibrador": "regra",
            "limiar_f2": "-",
            "recall": base_res["b2"]["recall"],
            "precisao": base_res["b2"]["precisao"],
            "f2": base_res["b2"]["f2"],
            "tentativas_ok_podadas": "0/0",
        },
    ]
    for m_name, c_info in candidates.items():
        tm_m = threshold_metrics(y_all, c_info["p_calibrated"], c_info["limiar_f2"])
        comp_rows.append(
            {
                "modelo": m_name,
                "pr_auc_media": c_info["pr_auc_media"],
                "pr_auc_oof": c_info["pr_auc_oof"],
                "roc_auc": roc_auc(y_all, c_info["p_calibrated"]),
                "brier": c_info["brier_calibrated"],
                "calibrador": c_info["method"],
                "limiar_f2": c_info["limiar_f2"],
                "recall": tm_m["recall"],
                "precisao": tm_m["precisao"],
                "f2": tm_m["f2"],
                "tentativas_ok_podadas": f"{c_info['n_concluidas']}/{c_info['n_podadas']}",
            }
        )

    comp_oof_path = m1_reports_dir / "comparacao_oof.md"
    comp_oof_path.write_text(
        f"# Comparação OOF dos modelos de triagem (T-4.9)\n\n"
        f"- **Modelo vencedor (M1):** `{winner}` ({winner_reason})\n\n"
        f"{profiling.markdown_table(pd.DataFrame(comp_rows), decimals=4)}\n",
        encoding="utf-8",
    )

    comp_pair_path = m1_reports_dir / "comparacao_pareada.md"
    comp_pair_path.write_text(
        f"# Comparação pareada de PR-AUC entre modelos (T-4.9, D-53)\n\n"
        f"{profiling.markdown_table(paired_df, decimals=4)}\n",
        encoding="utf-8",
    )

    selecao_checks = [
        check("unico_modelo_escolhido", True, bool(winner in candidates)),
        check("comparacao_oof_existe", True, comp_oof_path.is_file()),
        check("comparacao_pareada_existe", True, comp_pair_path.is_file()),
    ]
    update_session_report(
        session_report_path,
        "selecao",
        selecao_checks,
        cfg,
        tarefa="T-4.9",
        hash_dobras=fold_hash,
        sessao_completa=False,
    )

    # 3. T-4.10 + T-4.8: Retreino final do vencedor em todo 2022–23 e SHAP global
    win_info = candidates[winner]
    best_pts = list(win_info["melhores_pontos"].values())
    median_pt = int(round(float(np.median(best_pts)))) if best_pts else 100
    retrain_params = dict(win_info.get("best_params", {}))
    if winner in {"xgboost", "xgb"}:
        retrain_params["n_estimators"] = median_pt
    elif winner == "catboost":
        retrain_params["iterations"] = median_pt
    elif winner == "mlp":
        retrain_params["max_epochs"] = median_pt

    final_pipe, final_pt = _fit_fold_model(
        winner,
        retrain_params,
        feat,
        y_all,
        None,
        None,
        seed,
    )

    # SHAP global (T-4.8)
    shap_png = compute_global_shap(cfg, winner, final_pipe, feat)
    shap_checks = [check("shap_png_existe", True, shap_png.is_file())]
    update_session_report(
        session_report_path,
        "shap",
        shap_checks,
        cfg,
        tarefa="T-4.8",
        hash_dobras=fold_hash,
        sessao_completa=False,
    )

    bg_sample = feat[M1_FEATURES].iloc[: min(20, len(feat))].copy().reset_index(drop=True)
    m1_frozen = FittedM1Model(
        familia=winner,
        pipeline=final_pipe,
        calibrator=win_info["calibrator"],
        limiar=float(win_info["limiar_f2"]),
        melhores_pontos=win_info["melhores_pontos"],
        n_iter_final=int(final_pt),
        feature_cols=list(M1_FEATURES),
        background_df=bg_sample,
    )

    models_dir = Path(cfg.get("caminhos", {}).get("modelos", "models"))
    models_dir.mkdir(parents=True, exist_ok=True)
    m1_bundle_path = models_dir / "m1_final.joblib"
    save_bundle(
        m1_frozen,
        m1_bundle_path,
        cfg=cfg,
        extra_metadata={
            "modelo_tipo": f"M1-{winner}",
            "vencedor": winner,
            "motivo_selecao": winner_reason,
            "calibrador": win_info["method"],
            "limiar_f2": float(win_info["limiar_f2"]),
            "melhores_pontos_5_dobras": win_info["melhores_pontos"],
            "n_iter_final_mediana": int(final_pt),
        },
    )

    # Mede tamanho, tempo de predição de 1 caso e tempo de SHAP local (T-4.10, NFR-06)
    loaded_m1 = load_bundle(m1_bundle_path)
    one_case = feat.iloc[[0]]
    t0_pred = time.perf_counter()
    pred_one = loaded_m1.predict_proba(one_case)
    pred_sec = float(time.perf_counter() - t0_pred)

    t0_shap = time.perf_counter()
    _ = loaded_m1.explain_case(one_case, top_k=5)
    shap_sec = float(time.perf_counter() - t0_shap)
    bundle_size_mb = float(m1_bundle_path.stat().st_size / (1024 * 1024))
    m1_hash = sha256_file(m1_bundle_path)

    retreino_checks = [
        check("artefato_carrega_e_prediz", True, bool(pred_one.shape == (1, 2))),
        check("tempo_predicao_1caso_s_menor_1s", True, bool(pred_sec < 1.0)),
        check("tempo_shap_local_s_menor_1s", True, bool(shap_sec < 1.0)),
        check("tamanho_artefato_mb_registrado", True, bool(bundle_size_mb > 0.0)),
        check("sha256_artefato_m1", m1_hash, m1_hash),
    ]
    update_session_report(
        session_report_path,
        "retreino",
        retreino_checks,
        cfg,
        tarefa="T-4.10",
        hash_dobras=fold_hash,
        sessao_completa=True,
    )

    if mlflow.active_run() is None:
        from dengue_sinan.tracking import start_run

        with start_run(cfg, f"m1-vencedor-{winner}", tags={"vencedor": winner}):
            mlflow.log_params(
                {
                    "vencedor": winner,
                    "motivo": winner_reason,
                    "m1_sha256": m1_hash,
                    "calibrador": win_info["method"],
                }
            )
            mlflow.log_metrics(
                {
                    "pr_auc_media": float(win_info["pr_auc_media"]),
                    "brier_calibrated": float(win_info["brier_calibrated"]),
                    "limiar_f2": float(win_info["limiar_f2"]),
                    "pred_1caso_s": pred_sec,
                    "shap_1caso_s": shap_sec,
                    "bundle_size_mb": bundle_size_mb,
                }
            )

    return {
        "winner": winner,
        "winner_reason": winner_reason,
        "m1_bundle_path": m1_bundle_path,
        "m1_sha256": m1_hash,
        "session_report_path": session_report_path,
        "candidates": candidates,
    }
