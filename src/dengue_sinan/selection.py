"""Calibração e seleção do vencedor M1 a partir de predições OOF."""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from dengue_sinan.calibration import apply_calibrator, fit_calibrators
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.metrics import (
    best_f2_threshold,
    brier,
    calibration_slope_intercept,
    fold_bootstrap_ci,
    paired_bootstrap_diff,
    pr_auc,
    roc_auc,
    threshold_metrics,
)
from dengue_sinan.reporting import markdown_table

_COMPLEXITY = {
    "elastic_net": 0,
    "random_forest": 1,
    "xgboost": 2,
    "catboost": 2,
    "mlp": 3,
}


def select_m1(
    results: dict[str, dict],
    baseline_oof: pd.DataFrame,
    cfg: dict,
    reports_dir: str | Path,
) -> dict:
    """Seleciona por PR-AUC LORO; empates usam Brier calibrado e simplicidade."""
    if not results:
        raise ValueError("Não há resultados OOF de M1 para selecionar.")
    required_baseline = {"ANO", "y", "regiao", "b0", "b1", "b2"}
    if not required_baseline.issubset(baseline_oof.columns):
        raise ValueError(f"baseline_oof precisa conter {sorted(required_baseline)}.")
    assert_dev_only(baseline_oof)
    labels = baseline_oof["y"].to_numpy(dtype=np.int8)
    folds = baseline_oof["regiao"].to_numpy()
    if any(
        not np.array_equal(result["oof"]["y"].to_numpy(dtype=np.int8), labels)
        or not np.array_equal(result["oof"]["regiao"].to_numpy(), folds)
        or not np.array_equal(
            result["oof"]["ANO"].to_numpy(), baseline_oof["ANO"].to_numpy()
        )
        for result in results.values()
    ):
        raise ValueError("As predições OOF de M1 não estão alinhadas ao baseline.")

    seed = int(cfg["seed"])
    bootstrap_n = int(cfg.get("bootstrap", {}).get("metricas", 1000))
    rows = []
    selected_calibrators = {}
    calibrated_oof = {}
    output = Path(reports_dir) / "m1"
    calibrators_dir = output / "calibradores"
    calibrators_dir.mkdir(parents=True, exist_ok=True)
    for model_name, result in results.items():
        probability = result["oof"]["probabilidade"].to_numpy(dtype=float)
        candidates = fit_calibrators(labels, probability, seed)
        calibrated_candidates = {
            name: apply_calibrator(calibrator, probability)
            for name, calibrator in candidates.items()
        }
        calibration_scores = {
            name: brier(labels, calibrated) for name, calibrated in calibrated_candidates.items()
        }
        calibration_name = min(calibration_scores, key=calibration_scores.get)
        calibrator = candidates[calibration_name]
        calibrated = calibrated_candidates[calibration_name]
        calibration = calibration_slope_intercept(labels, calibrated)
        estimate, lower, upper = fold_bootstrap_ci(
            pr_auc, labels, probability, folds, n=bootstrap_n, seed=seed
        )
        per_fold = {
            f"pr_auc_{region}": pr_auc(labels[folds == region], probability[folds == region])
            for region in cfg["ordem_dobras"]
        }
        threshold = best_f2_threshold(labels, calibrated)
        rows.append(
            {
                "modelo": model_name,
                "pr_auc": estimate,
                "pr_auc_ic_inferior": lower,
                "pr_auc_ic_superior": upper,
                "brier": calibration_scores[calibration_name],
                "calibrador": calibration_name,
                "limiar_f2": threshold,
                "roc_auc": roc_auc(labels, probability),
                "slope": calibration["slope"],
                "intercept": calibration["intercept"],
                **threshold_metrics(labels, calibrated, threshold),
                **per_fold,
            }
        )
        selected_calibrators[model_name] = calibrator
        calibrated_oof[model_name] = calibrated
        joblib.dump(calibrator, calibrators_dir / f"{model_name}.joblib")
        metadata = result.get("run_metadata", {})
        rows[-1].update(
            {
                "tempo_segundos": metadata.get("tempo_segundos"),
                "orcamento_segundos": metadata.get("orcamento_segundos"),
                "tentativas_concluidas": metadata.get("tentativas_concluidas"),
                "tentativas_podadas": metadata.get("tentativas_podadas"),
            }
        )

    model_rows = pd.DataFrame(rows).sort_values(
        ["pr_auc", "brier"], ascending=[False, True]
    ).reset_index(drop=True)
    best = model_rows.iloc[0]
    tied = model_rows[
        (best["pr_auc"] - model_rows["pr_auc"] < 0.005)
        | (
            (model_rows["pr_auc_ic_inferior"] <= best["pr_auc_ic_superior"])
            & (model_rows["pr_auc_ic_superior"] >= best["pr_auc_ic_inferior"])
        )
    ].copy()
    tied["complexidade"] = tied["modelo"].map(_COMPLEXITY)
    winner = tied.sort_values(
        ["brier", "complexidade", "modelo"], ascending=[True, True, True]
    ).iloc[0]
    winner_name = str(winner["modelo"])

    baseline_rows = []
    for name in ("b0", "b1", "b2"):
        probability = baseline_oof[name].to_numpy(dtype=float)
        row = {
            "modelo": name.upper(),
            "pr_auc": float(
                np.mean(
                    [
                        pr_auc(labels[folds == region], probability[folds == region])
                        for region in cfg["ordem_dobras"]
                    ]
                )
            ),
            "brier": brier(labels, probability),
            "roc_auc": roc_auc(labels, probability),
            **{
                f"pr_auc_{region}": pr_auc(
                    labels[folds == region], probability[folds == region]
                )
                for region in cfg["ordem_dobras"]
            },
        }
        if name != "b2":
            row.update(calibration_slope_intercept(labels, probability))
        else:
            row.update(threshold_metrics(labels, probability, 0.5))
        baseline_rows.append(row)
    comparison = pd.concat(
        [model_rows, pd.DataFrame(baseline_rows)],
        ignore_index=True,
        sort=False,
    )
    baseline = {
        "pr_auc": float(comparison.loc[comparison["modelo"] == "B1", "pr_auc"].iloc[0]),
        "brier": brier(labels, baseline_oof["b1"].to_numpy(dtype=float)),
    }

    paired_rows = []
    predictions = {
        name: result["oof"]["probabilidade"].to_numpy(dtype=float)
        for name, result in results.items()
    }
    predictions["B1"] = baseline_oof["b1"].to_numpy(dtype=float)
    for index, name_a in enumerate(predictions):
        for name_b in list(predictions)[index + 1 :]:
            difference, lower, upper = paired_bootstrap_diff(
                pr_auc,
                labels,
                predictions[name_a],
                predictions[name_b],
                folds,
                n=int(cfg.get("bootstrap_pareado", bootstrap_n)),
                seed=seed,
            )
            fold_differences = {
                f"diferenca_pr_auc_{region}": pr_auc(
                    labels[folds == region], predictions[name_a][folds == region]
                )
                - pr_auc(labels[folds == region], predictions[name_b][folds == region])
                for region in cfg["ordem_dobras"]
            }
            paired_rows.append(
                {
                    "modelo_a": name_a,
                    "modelo_b": name_b,
                    "diferenca_media_pr_auc": difference,
                    "ic_inferior": lower,
                    "ic_superior": upper,
                    **fold_differences,
                }
            )
    paired_comparison = pd.DataFrame(paired_rows)

    output.mkdir(parents=True, exist_ok=True)
    (output / "comparacao_oof.md").write_text(
        "# Comparação OOF dos modelos M1\n\n" + markdown_table(comparison) + "\n",
        encoding="utf-8",
    )
    (output / "comparacao_pareada.md").write_text(
        "# Comparação pareada de PR-AUC\n\n" + markdown_table(paired_comparison) + "\n",
        encoding="utf-8",
    )
    joblib.dump(selected_calibrators[winner_name], output / "calibrador.joblib")
    reason = (
        "maior PR-AUC média por dobra"
        if len(tied) == 1
        else "empate por diferença < 0,005 ou ICs sobrepostos; desempate por Brier e simplicidade"
    )
    (output / "selecao.json").write_text(
        json.dumps(
            {
                "modelo": winner_name,
                "calibrador": winner["calibrador"],
                "limiar_f2": float(winner["limiar_f2"]),
                "pr_auc": float(winner["pr_auc"]),
                "brier": float(winner["brier"]),
                "baseline_b1": baseline,
                "supera_b1_pr_auc": bool(winner["pr_auc"] > baseline["pr_auc"]),
                "motivo": reason,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "modelo": winner_name,
        "calibrador": selected_calibrators[winner_name],
        "calibrador_nome": str(winner["calibrador"]),
        "limiar": float(winner["limiar_f2"]),
        "comparison": comparison,
        "paired_comparison": paired_comparison,
        "calibrated_oof": calibrated_oof,
        "baseline_b1": baseline,
        "supera_b1_pr_auc": bool(winner["pr_auc"] > baseline["pr_auc"]),
        "motivo": reason,
    }
