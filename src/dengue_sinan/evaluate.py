"""Avaliação final única no conjunto de teste 2024 com lacre (T-5.1 a T-5.4, R1, R2, R7)."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.special import expit

from dengue_sinan import profiling
from dengue_sinan.artifacts import load_bundle
from dengue_sinan.baselines import B1_FEATURES, rule_b2
from dengue_sinan.dataset import COMORBIDADES, build_feature_frame, load_population
from dengue_sinan.descriptive import suppress_small_cells
from dengue_sinan.metrics import (
    bootstrap_ci,
    brier,
    calibration_slope_intercept,
    net_benefit,
    paired_bootstrap_diff,
    pr_auc,
    roc_auc,
    threshold_metrics,
)
from dengue_sinan.verify import check, sha256_file, write_report

matplotlib.use("Agg")

RACA_LABELS: dict[str, str] = {
    "1": "Branca",
    "2": "Preta",
    "3": "Amarela",
    "4": "Parda",
    "5": "Indígena",
    "9": "Ignorado",
}


def _git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
        return res.stdout.strip()
    except Exception:
        return "desconhecido"


def _predict_e1_probs(e1_model: Any, feat: pd.DataFrame) -> np.ndarray:
    """Prediz probabilidades no conjunto de teste usando o artefato E1 congelado."""
    X = e1_model.design_matrix(feat)
    beta = e1_model.params.reindex(e1_model.feature_names).to_numpy(dtype=np.float64)
    logits = X.to_numpy(dtype=np.float64) @ beta
    return np.asarray(expit(logits), dtype=np.float64)


def _plot_decision_curves(
    y: np.ndarray,
    p_m1: np.ndarray,
    p_b1: np.ndarray,
    b2_mask: np.ndarray,
    limiar_m1: float,
    out_path: Path,
) -> pd.DataFrame:
    """Plota a curva de decisão (0,1%–5%) para M1, B1 e B2 marcando o limiar F2 (T-5.2)."""
    thresholds = np.linspace(0.001, 0.05, 50)
    nb_m1 = net_benefit(y, p_m1, thresholds)
    nb_b1 = net_benefit(y, p_b1, thresholds)
    nb_b2 = net_benefit(y, b2_mask.astype(float), thresholds)

    merged = pd.DataFrame(
        {
            "limiar": nb_m1["limiar"],
            "M1": nb_m1["modelo"],
            "B1": nb_b1["modelo"],
            "B2": nb_b2["modelo"],
            "tratar_todos": nb_m1["tratar_todos"],
            "tratar_ninguem": nb_m1["tratar_ninguem"],
        }
    )

    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(merged["limiar"] * 100.0, merged["M1"], label="M1 (Triagem)", linewidth=2.0)
    ax.plot(merged["limiar"] * 100.0, merged["B1"], label="B1 (Perfil logístico)", linestyle="--")
    ax.plot(merged["limiar"] * 100.0, merged["B2"], label="B2 (Regra MS)", linestyle="-.")
    ax.plot(
        merged["limiar"] * 100.0,
        merged["tratar_todos"],
        label="Tratar todos",
        color="gray",
        alpha=0.6,
    )
    ax.axhline(0.0, color="black", linestyle=":", label="Tratar ninguém")
    if 0.001 <= limiar_m1 <= 0.05:
        ax.axvline(
            limiar_m1 * 100.0,
            color="red",
            linestyle=":",
            label=f"Limiar F2 ({limiar_m1:.3f})",
        )
    ax.set_xlabel("Limiar de probabilidade (%)")
    ax.set_ylabel("Benefício líquido (Net Benefit)")
    ax.set_title("Curva de Decisão no Teste 2024 (0,1% a 5%)")
    ax.legend(loc="best")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    return merged


def _plot_calibration_curves(
    y: np.ndarray,
    p_m1: np.ndarray,
    p_e1: np.ndarray,
    out_path: Path,
    n_boot: int = 200,
    seed: int = 20261103,
) -> None:
    """Plota curva de calibração com bandas bootstrap para M1 e E1 no teste 2024 (T-5.2)."""
    rng = np.random.default_rng(int(seed))
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.plot([0.0, 0.05], [0.0, 0.05], "k--", alpha=0.6, label="Ideal")

    for label, p_arr in (("M1 (Triagem)", p_m1), ("E1 (Perfil)", p_e1)):
        quantiles = np.quantile(p_arr, np.linspace(0.0, 1.0, 11))
        quantiles[0] = -1.0
        quantiles[-1] = 1.01
        bins = np.digitize(p_arr, quantiles[1:-1])

        mean_pred: list[float] = []
        obs_rate: list[float] = []
        lo_band: list[float] = []
        hi_band: list[float] = []

        for b in range(10):
            in_bin = bins == b
            if not np.any(in_bin):
                continue
            y_b = y[in_bin]
            p_b = p_arr[in_bin]
            obs_b = float(np.mean(y_b))
            mean_pred.append(float(np.mean(p_b)))
            obs_rate.append(obs_b)

            n_b = len(y_b)
            # Soma de n_b sorteios com reposição de y_b binário ~ Binomial(n_b, obs_b)
            boot_means = rng.binomial(n_b, np.clip(obs_b, 0.0, 1.0), size=int(n_boot)) / float(
                max(1, n_b)
            )
            lo, hi = np.percentile(boot_means, [2.5, 97.5])
            lo_band.append(float(lo))
            hi_band.append(float(hi))

        ax.plot(mean_pred, obs_rate, marker="o", label=label)
        ax.fill_between(mean_pred, lo_band, hi_band, alpha=0.2)

    max_x = max(0.02, float(np.quantile(p_m1, 0.99)) * 1.2)
    ax.set_xlim(0.0, min(1.0, max_x))
    ax.set_ylim(0.0, min(1.0, max_x))
    ax.set_xlabel("Probabilidade prevista média")
    ax.set_ylabel("Proporção observada de eventos")
    ax.set_title("Curva de Calibração no Teste 2024 (M1 e E1)")
    ax.legend(loc="best")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _subgroup_analysis(
    feat: pd.DataFrame,
    y: np.ndarray,
    p_m1: np.ndarray,
    limiar_m1: float,
    min_cell: int = 10,
    n_boot: int = 200,
    seed: int = 20261103,
) -> pd.DataFrame:
    """Calcula PR-AUC, recall no limiar e calibração por subgrupo com avisos de IC largo (T-5.2)."""
    df_sub = feat.copy()
    if "CS_RACA" in df_sub.columns:
        r_codes = profiling.code(df_sub["CS_RACA"]).fillna("9")
        df_sub["raca_cor"] = r_codes.map(lambda c: RACA_LABELS.get(str(c), "Ignorado"))
    else:
        df_sub["raca_cor"] = "Ignorado"

    subgroups = [
        ("Faixa etária", "faixa_etaria"),
        ("Sexo", "sexo"),
        ("Gestante", "gestante"),
        ("Região", "regiao"),
        ("Raça/cor", "raca_cor"),
    ]

    rows: list[dict[str, Any]] = []
    for dim_label, col in subgroups:
        if col not in df_sub.columns:
            continue
        for val, grp in df_sub.groupby(col, observed=False):
            idx = grp.index.to_numpy()
            if len(idx) == 0:
                continue
            y_g = y[idx]
            p_g = p_m1[idx]
            n_casos = int(len(y_g))
            n_ev = int(y_g.sum())

            if n_ev > 0 and n_ev < n_casos:
                prauc_est, prauc_lo, prauc_hi = bootstrap_ci(
                    pr_auc, y_g, p_g, n=min(n_boot, 100), seed=seed
                )
                slope_g, _ = calibration_slope_intercept(y_g, p_g)
            else:
                prauc_est, prauc_lo, prauc_hi = 0.0, 0.0, 0.0
                slope_g = 1.0

            tm = threshold_metrics(y_g, p_g, limiar_m1)
            aviso = "IC largo (< 100 eventos)" if n_ev < 100 else "OK"
            if str(val) in {"Norte", "1", "True"} and n_ev < 250:
                aviso = "IC largo / no limite de eventos"

            rows.append(
                {
                    "dimensao": dim_label,
                    "subgrupo": str(val),
                    "casos": n_casos,
                    "eventos": n_ev,
                    "pr_auc": prauc_est,
                    "pr_auc_ic95_inf": prauc_lo,
                    "pr_auc_ic95_sup": prauc_hi,
                    "recall_limiar": tm["recall"],
                    "brier": brier(y_g, p_g),
                    "slope": slope_g,
                    "aviso": aviso,
                }
            )

    out_df = pd.DataFrame(rows)
    return suppress_small_cells(
        out_df,
        count_cols=["casos", "eventos"],
        min_cell=min_cell,
        mask_cols=[
            "pr_auc",
            "pr_auc_ic95_inf",
            "pr_auc_ic95_sup",
            "recall_limiar",
            "brier",
            "slope",
        ],
    )


def _error_analysis(
    feat: pd.DataFrame,
    y: np.ndarray,
    p_m1: np.ndarray,
    limiar_m1: float,
    min_cell: int = 10,
) -> dict[str, pd.DataFrame]:
    """Descreve em agregados os 100 FNs de maior risco, calibração e ES (T-5.3, R7)."""
    fn_mask = (y == 1) & (p_m1 < float(limiar_m1))
    fn_indices = np.flatnonzero(fn_mask)
    if len(fn_indices) > 0:
        order_desc = np.argsort(-p_m1[fn_indices])[:100]
        top_fn_idx = fn_indices[order_desc]
        fn_df = feat.iloc[top_fn_idx]

        fn_summary_rows: list[dict[str, Any]] = []
        for col_name, label in (
            ("faixa_etaria", "Faixa etária"),
            ("regiao", "Região"),
            ("n_comorbidades", "Nº comorbidades"),
        ):
            if col_name in fn_df.columns:
                counts = fn_df[col_name].astype(str).value_counts()
                for k, cnt in counts.items():
                    fn_summary_rows.append(
                        {"dimensao": label, "categoria": str(k), "casos": int(cnt)}
                    )
        fn_agg = suppress_small_cells(
            pd.DataFrame(fn_summary_rows), count_cols=["casos"], min_cell=min_cell
        )
    else:
        fn_agg = pd.DataFrame(columns=["dimensao", "categoria", "casos"])

    # Células de comorbidade com pior calibração (diferença entre risco observado e previsto médio)
    comorb_rows: list[dict[str, Any]] = []
    for c in COMORBIDADES:
        if c not in feat.columns:
            continue
        mask_c = (feat[c].astype(str) == "Sim").to_numpy()
        n_c = int(mask_c.sum())
        if n_c == 0:
            continue
        ev_c = int(y[mask_c].sum())
        obs_c = float(ev_c / n_c)
        pred_c = float(np.mean(p_m1[mask_c]))
        comorb_rows.append(
            {
                "comorbidade": c,
                "casos": n_c,
                "eventos": ev_c,
                "obs_pct": obs_c * 100.0,
                "pred_pct": pred_c * 100.0,
                "erro_abs_pct": abs(obs_c - pred_c) * 100.0,
            }
        )
    comorb_cal_df = pd.DataFrame(comorb_rows)
    if not comorb_cal_df.empty:
        comorb_cal_df = comorb_cal_df.sort_values("erro_abs_pct", ascending=False).reset_index(
            drop=True
        )
        comorb_cal_df = suppress_small_cells(
            comorb_cal_df,
            count_cols=["casos", "eventos"],
            min_cell=min_cell,
            mask_cols=["obs_pct", "pred_pct", "erro_abs_pct"],
        )

    # Espírito Santo (SG_UF == "32" ou "ES") vs demais UFs do Sudeste / Brasil (spec §3.7)
    if "SG_UF" in feat.columns:
        uf_s = feat["SG_UF"].astype(str).str.strip()
        es_mask = uf_s.isin({"32", "ES"}).to_numpy()
    else:
        es_mask = np.zeros(len(feat), dtype=bool)

    es_rows: list[dict[str, Any]] = []
    for label_es, m_es in (("Espírito Santo (ES)", es_mask), ("Demais UFs", ~es_mask)):
        n_g = int(m_es.sum())
        if n_g == 0:
            continue
        ev_g = int(y[m_es].sum())
        es_rows.append(
            {
                "recorte": label_es,
                "casos": n_g,
                "eventos": ev_g,
                "pr_auc": pr_auc(y[m_es], p_m1[m_es]) if 0 < ev_g < n_g else 0.0,
                "brier": brier(y[m_es], p_m1[m_es]),
            }
        )
    es_df = suppress_small_cells(
        pd.DataFrame(es_rows),
        count_cols=["casos", "eventos"],
        min_cell=min_cell,
        mask_cols=["pr_auc", "brier"],
    )

    return {
        "fn_agg": fn_agg,
        "comorb_cal_df": comorb_cal_df,
        "es_df": es_df,
    }


def evaluate_test_once(
    cfg: dict[str, Any],
    *,
    df_test_override: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Avalia E1, M1, B1 e B2 no teste 2024 uma única vez e grava `LACRE.json` (T-5.1, R2)."""
    reports_dir = Path(cfg.get("caminhos", {}).get("relatorios", "reports"))
    teste_dir = reports_dir / "teste"
    teste_dir.mkdir(parents=True, exist_ok=True)
    lacre_path = teste_dir / "LACRE.json"

    if lacre_path.is_file():
        raise RuntimeError("teste já avaliado (R2)")

    seed = int(cfg.get("seed", 20261103))
    min_cell = int(cfg.get("supressao_min_celula", 10))
    n_boot = int(cfg.get("bootstrap_metricas", 1000))
    n_boot_cal = int(cfg.get("bootstrap_calibracao", 2000))
    if cfg.get("modo_teste_rapido", False):
        n_boot = min(n_boot, 30)
        n_boot_cal = min(n_boot_cal, 30)

    # Único ponto autorizado a carregar 2024 (R1, R2)
    ano_teste = int(cfg.get("ano_teste", 2024))
    raw_test = (
        df_test_override
        if df_test_override is not None
        else load_population(cfg, [ano_teste])
    )
    assert isinstance(raw_test, pd.DataFrame)
    feat = (
        build_feature_frame(raw_test, allow_test=True)
        if "n_comorbidades" not in raw_test.columns
        else raw_test
    )
    if "SG_UF" in raw_test.columns and "SG_UF" not in feat.columns:
        feat["SG_UF"] = raw_test["SG_UF"]

    y_test = feat["y"].to_numpy(dtype=np.int8)
    dobra_test = (
        feat["regiao"].astype(str).to_numpy()
        if "regiao" in feat.columns
        else np.full(len(feat), "Brasil")
    )

    models_dir = Path(cfg.get("caminhos", {}).get("modelos", "models"))
    e1_path = models_dir / "e1_final.joblib"
    if not e1_path.is_file():
        e1_path = models_dir / "e1.joblib"
    m1_path = models_dir / "m1_final.joblib"
    b1_path = models_dir / "b1.joblib"

    e1_bundle = load_bundle(e1_path)
    m1_bundle = load_bundle(m1_path)
    b1_bundle = load_bundle(b1_path)

    p_e1 = _predict_e1_probs(e1_bundle["model"], feat)
    p_m1 = m1_bundle.predict_proba(feat)[:, 1]
    p_b1 = b1_bundle.predict_proba(feat[B1_FEATURES])[:, 1]
    prev_dev = float(b1_bundle["metadata"].get("prev_dev", float(y_test.mean())))
    p_b0 = np.full(len(feat), prev_dev, dtype=np.float64)
    b2_mask = rule_b2(feat)

    default_limiar = getattr(m1_bundle["model"], "limiar", 0.5)
    limiar_m1 = float(m1_bundle["metadata"].get("limiar_f2", default_limiar))
    limiar_b1 = float(b1_bundle["metadata"].get("limiar_f2", 0.5))

    m1_prauc, m1_prauc_lo, m1_prauc_hi = bootstrap_ci(pr_auc, y_test, p_m1, n=n_boot, seed=seed)
    b1_prauc, b1_prauc_lo, b1_prauc_hi = bootstrap_ci(pr_auc, y_test, p_b1, n=n_boot, seed=seed)
    e1_prauc, e1_prauc_lo, e1_prauc_hi = bootstrap_ci(pr_auc, y_test, p_e1, n=n_boot, seed=seed)
    b0_prauc = pr_auc(y_test, p_b0)

    diff_m1_b0, diff_b0_lo, diff_b0_hi = paired_bootstrap_diff(
        pr_auc, y_test, p_m1, p_b0, dobra=dobra_test, n=n_boot, seed=seed
    )
    diff_m1_b1, diff_b1_lo, diff_b1_hi = paired_bootstrap_diff(
        pr_auc, y_test, p_m1, p_b1, dobra=dobra_test, n=n_boot, seed=seed
    )

    m1_slope, m1_inter = calibration_slope_intercept(y_test, p_m1)
    e1_slope, e1_inter = calibration_slope_intercept(y_test, p_e1)
    b1_slope, b1_inter = calibration_slope_intercept(y_test, p_b1)

    tm_m1 = threshold_metrics(y_test, p_m1, limiar_m1)
    tm_b1 = threshold_metrics(y_test, p_b1, limiar_b1)
    tm_b2 = threshold_metrics(y_test, b2_mask.astype(float), 0.5)

    # Critérios de sucesso SC-01 a SC-04 (T-5.4)
    sc01_pass = bool(diff_b0_lo > 0.0)
    sc02_pass = bool(diff_m1_b1 > 0.0)
    sc03_pass = bool(tm_m1["recall"] >= tm_b2["recall"] and tm_m1["precisao"] > tm_b2["precisao"])
    sc04_pass = bool(0.8 <= m1_slope <= 1.2)

    metrics_df = pd.DataFrame(
        [
            {
                "modelo": "M1 (Triagem)",
                "pr_auc": m1_prauc,
                "pr_auc_ic95_inf": m1_prauc_lo,
                "pr_auc_ic95_sup": m1_prauc_hi,
                "roc_auc": roc_auc(y_test, p_m1),
                "brier": brier(y_test, p_m1),
                "slope": m1_slope,
                "intercept": m1_inter,
                "limiar": limiar_m1,
                "recall": tm_m1["recall"],
                "precisao": tm_m1["precisao"],
                "f2": tm_m1["f2"],
            },
            {
                "modelo": "E1 (Perfil explicativo)",
                "pr_auc": e1_prauc,
                "pr_auc_ic95_inf": e1_prauc_lo,
                "pr_auc_ic95_sup": e1_prauc_hi,
                "roc_auc": roc_auc(y_test, p_e1),
                "brier": brier(y_test, p_e1),
                "slope": e1_slope,
                "intercept": e1_inter,
                "limiar": "-",
                "recall": "-",
                "precisao": "-",
                "f2": "-",
            },
            {
                "modelo": "B1 (Baseline perfil)",
                "pr_auc": b1_prauc,
                "pr_auc_ic95_inf": b1_prauc_lo,
                "pr_auc_ic95_sup": b1_prauc_hi,
                "roc_auc": roc_auc(y_test, p_b1),
                "brier": brier(y_test, p_b1),
                "slope": b1_slope,
                "intercept": b1_inter,
                "limiar": limiar_b1,
                "recall": tm_b1["recall"],
                "precisao": tm_b1["precisao"],
                "f2": tm_b1["f2"],
            },
            {
                "modelo": "B0 (Prevalência)",
                "pr_auc": b0_prauc,
                "pr_auc_ic95_inf": b0_prauc,
                "pr_auc_ic95_sup": b0_prauc,
                "roc_auc": 0.5,
                "brier": brier(y_test, p_b0),
                "slope": 0.0,
                "intercept": 0.0,
                "limiar": "-",
                "recall": "-",
                "precisao": "-",
                "f2": "-",
            },
            {
                "modelo": "B2 (Protocolo MS)",
                "pr_auc": "-",
                "pr_auc_ic95_inf": "-",
                "pr_auc_ic95_sup": "-",
                "roc_auc": "-",
                "brier": "-",
                "slope": "-",
                "intercept": "-",
                "limiar": "regra",
                "recall": tm_b2["recall"],
                "precisao": tm_b2["precisao"],
                "f2": tm_b2["f2"],
            },
        ]
    )

    sc_df = pd.DataFrame(
        [
            {
                "criterio": "SC-01 (M1 supera B0 em PR-AUC; IC da diferença > 0)",
                "valor_obtido": f"diff={diff_m1_b0:.4f} [{diff_b0_lo:.4f}, {diff_b0_hi:.4f}]",
                "status": "passou" if sc01_pass else "falhou",
            },
            {
                "criterio": "SC-02 (Comparação M1 vs B1 em PR-AUC; desejável > 0)",
                "valor_obtido": f"diff={diff_m1_b1:.4f} [{diff_b1_lo:.4f}, {diff_b1_hi:.4f}]",
                "status": "passou" if sc02_pass else "falhou",
            },
            {
                "criterio": "SC-03 (Recall M1 >= Recall B2 com maior precisão no limiar)",
                "valor_obtido": (
                    f"recall M1={tm_m1['recall']:.4f} vs B2={tm_b2['recall']:.4f}; "
                    f"prec M1={tm_m1['precisao']:.4f} vs B2={tm_b2['precisao']:.4f}"
                ),
                "status": "passou" if sc03_pass else "falhou",
            },
            {
                "criterio": "SC-04 (Calibration slope de M1 no teste entre 0,8 e 1,2)",
                "valor_obtido": f"slope={m1_slope:.4f}",
                "status": "passou" if sc04_pass else "falhou",
            },
        ]
    )

    metricas_md_path = teste_dir / "metricas.md"
    diff_b1_str = f"`{diff_m1_b1:.4f}` (IC 95%: `[{diff_b1_lo:.4f}, {diff_b1_hi:.4f}]`)"
    diff_b0_str = f"`{diff_m1_b0:.4f}` (IC 95%: `[{diff_b0_lo:.4f}, {diff_b0_hi:.4f}]`)"
    metricas_md_path.write_text(
        f"# Avaliação Final Única no Conjunto de Teste ({ano_teste}) (T-5.1, T-5.4)\n\n"
        f"- **Diferença PR-AUC (M1 − B1):** {diff_b1_str}\n"
        f"- **Diferença PR-AUC (M1 − B0):** {diff_b0_str}\n\n"
        f"## Métricas principais\n\n"
        f"{profiling.markdown_table(metrics_df, decimals=4)}\n\n"
        f"## Critérios de sucesso (SC-01 a SC-04 — T-5.4)\n\n"
        f"{profiling.markdown_table(sc_df)}\n",
        encoding="utf-8",
    )

    # T-5.2: Curva de decisão, calibração e subgrupos
    nb_df = _plot_decision_curves(
        y_test, p_m1, p_b1, b2_mask, limiar_m1, teste_dir / "curva_decisao.png"
    )
    (teste_dir / "curva_decisao.md").write_text(
        f"# Curva de Decisão no Teste ({ano_teste}) (T-5.2)\n\n"
        f"{profiling.markdown_table(nb_df, decimals=5)}\n",
        encoding="utf-8",
    )
    _plot_calibration_curves(
        y_test,
        p_m1,
        p_e1,
        teste_dir / "calibracao_teste.png",
        n_boot=n_boot_cal,
        seed=seed,
    )
    sub_df = _subgroup_analysis(
        feat, y_test, p_m1, limiar_m1, min_cell=min_cell, n_boot=n_boot, seed=seed
    )
    (teste_dir / "subgrupos.md").write_text(
        f"# Desempenho por Subgrupos no Teste ({ano_teste}) (T-5.2)\n\n"
        f"{profiling.markdown_table(sub_df, decimals=4)}\n",
        encoding="utf-8",
    )

    # T-5.3: Análise de erros em agregados (R7)
    err_res = _error_analysis(feat, y_test, p_m1, limiar_m1, min_cell=min_cell)
    erros_md_path = teste_dir / "erros.md"
    erros_md_path.write_text(
        f"# Análise de Erros no Conjunto de Teste ({ano_teste}) (T-5.3, R7)\n\n"
        f"> **Apenas agregados (R7); células `< {min_cell}` suprimidas (`<{min_cell}`).**\n\n"
        f"## Perfil dos até 100 falsos negativos de maior risco previsto\n\n"
        f"{profiling.markdown_table(err_res['fn_agg'])}\n\n"
        f"## Calibração por comorbidade\n\n"
        f"{profiling.markdown_table(err_res['comorb_cal_df'], decimals=3)}\n\n"
        f"## Recorte Espírito Santo (ES) vs demais UFs (§3.7)\n\n"
        f"{profiling.markdown_table(err_res['es_df'], decimals=4)}\n",
        encoding="utf-8",
    )

    # Lacre (T-5.1, R2)
    data_dir = Path(cfg.get("caminhos", {}).get("dados", "data"))
    test_parquet = data_dir / "parquet" / f"dengue_{ano_teste}.parquet"
    if not test_parquet.is_file():
        test_parquet = data_dir / f"DENGBR{str(ano_teste)[-2:]}.parquet"
    lacre_payload = {
        "gerado_em": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _git_commit(),
        "ano_teste": ano_teste,
        "casos_teste": int(len(feat)),
        "eventos_teste": int(y_test.sum()),
        "hashes_artefatos": {
            "e1": sha256_file(e1_path),
            "m1": sha256_file(m1_path),
            "b1": sha256_file(b1_path),
        },
        "hash_dados_teste": sha256_file(test_parquet) if test_parquet.is_file() else "sintetico",
        "criterios_sucesso": {
            "SC-01": sc01_pass,
            "SC-02": sc02_pass,
            "SC-03": sc03_pass,
            "SC-04": sc04_pass,
        },
    }
    lacre_path.write_text(
        json.dumps(lacre_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    verif_dir = reports_dir / "verificacao"
    t5_checks = [
        check("lacre_gravado", True, lacre_path.is_file()),
        check("metricas_md_existe", True, metricas_md_path.is_file()),
        check("curva_decisao_png_existe", True, (teste_dir / "curva_decisao.png").is_file()),
        check("calibracao_teste_png_existe", True, (teste_dir / "calibracao_teste.png").is_file()),
        check("subgrupos_md_existe", True, (teste_dir / "subgrupos.md").is_file()),
        check("erros_md_existe", True, erros_md_path.is_file()),
        check("casos_teste_positivos", True, bool(len(feat) > 0)),
        check("eventos_teste_positivos", True, bool(int(y_test.sum()) > 0)),
    ]
    write_report("T-5.1_a_T-5.4", t5_checks, verif_dir, cfg)

    return {
        "lacre_path": lacre_path,
        "metricas_md_path": metricas_md_path,
        "erros_md_path": erros_md_path,
        "metrics_df": metrics_df,
        "sc_df": sc_df,
    }
