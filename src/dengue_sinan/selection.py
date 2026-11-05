"""Calibração e seleção final de M1 usando somente predições OOF."""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy.stats import t

from dengue_sinan.calibration import select_calibrator_and_threshold
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.metrics import (
    brier,
    calibration_slope_intercept,
    pr_auc,
    roc_auc,
    threshold_metrics,
)

_COMPLEXITY = {
    "elastic_net": 0,
    "random_forest": 1,
    "xgboost": 2,
    "catboost": 2,
    "mlp": 3,
    "tabfm": 4,
}


def _json_value(value):
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if isinstance(value, np.generic):
        return _json_value(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _pr_auc_interval(scores: list[float]) -> tuple[float, float]:
    values = np.asarray(scores, dtype=np.float64)
    if values.shape != (5,) or not np.isfinite(values).all():
        raise ValueError("cada modelo deve conter PR-AUC finita nas cinco dobras")
    mean = float(values.mean())
    margin = float(t.ppf(0.975, df=4) * values.std(ddof=1) / np.sqrt(5))
    return mean - margin, mean + margin


def _intervals_overlap(first: tuple[float, float], second: tuple[float, float]) -> bool:
    return max(first[0], second[0]) <= min(first[1], second[1])


def _markdown_table(frame: pd.DataFrame) -> str:
    headers = [str(column) for column in frame.columns]
    lines = ["| " + " | ".join(headers) + " |"]
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in frame.itertuples(index=False, name=None):
        lines.append("| " + " | ".join(str(value) for value in row) + " |")
    return "\n".join(lines)


def _choose_model(
    results: dict[str, dict],
    calibrations: dict[str, dict],
) -> tuple[str, str, dict[str, tuple[float, float]]]:
    if not results or set(results) != set(calibrations):
        raise ValueError("resultados e calibrações devem conter os mesmos modelos")
    unsupported = set(results) - (_COMPLEXITY.keys() - {"tabfm"})
    if unsupported:
        raise ValueError(f"modelos ainda não elegíveis: {sorted(unsupported)}")

    intervals = {
        model: _pr_auc_interval([row["pr_auc"] for row in result["fold_metrics"]])
        for model, result in results.items()
    }
    top = max(results, key=lambda model: results[model]["mean_pr_auc"])
    top_mean = float(results[top]["mean_pr_auc"])
    ties = [
        model for model, result in results.items()
        if abs(float(result["mean_pr_auc"]) - top_mean) < 0.005
        or _intervals_overlap(intervals[top], intervals[model])
    ]
    selected = min(
        ties,
        key=lambda model: (
            float(calibrations[model]["brier"]),
            _COMPLEXITY[model],
        ),
    )
    reason = (
        f"Maior PR-AUC média: {top} ({top_mean:.6f}). "
        f"Empate conforme tolerância/IC: {', '.join(ties)}. "
        f"Desempate por menor Brier OOF calibrado e, depois, simplicidade: {selected}."
    )
    return selected, reason, intervals


def calibrate_and_select_m1(
    cfg: dict,
    frame: pd.DataFrame,
    validation_runs: dict[str, dict],
    baseline_results: dict | None = None,
) -> dict:
    """Valida OOF, escolhe calibrador/limiar por modelo e registra o vencedor."""
    assert_dev_only(frame, int(cfg.get("ano_teste", 2024)))
    if "y" not in frame or "regiao" not in frame:
        raise ValueError("frame precisa conter y e regiao")
    calibrations = {}
    for model, result in validation_runs.items():
        path = Path(result["oof_artifact"])
        if not path.is_file():
            raise FileNotFoundError(f"predições OOF ausentes para {model}: {path}")
        oof = pd.read_parquet(path)
        if len(oof) != len(frame):
            raise ValueError(f"{model}: o OOF não tem uma linha por observação")
        if not np.array_equal(oof["y"].to_numpy(), frame["y"].to_numpy()):
            raise ValueError(f"{model}: rótulos do OOF não correspondem ao desenvolvimento")
        if not np.array_equal(
            oof["regiao"].astype("string").to_numpy(),
            frame["regiao"].astype("string").to_numpy(),
        ):
            raise ValueError(f"{model}: regiões do OOF não correspondem ao desenvolvimento")
        calibrations[model] = select_calibrator_and_threshold(
            frame, oof["probabilidade"].to_numpy()
        )

    selected, reason, intervals = _choose_model(validation_runs, calibrations)
    rows = []
    for model, result in validation_runs.items():
        calibration = calibrations[model]
        calibrated = calibration["oof_calibrated"]
        raw_oof = pd.read_parquet(result["oof_artifact"])["probabilidade"].to_numpy()
        slope, intercept = calibration_slope_intercept(
            frame["y"].to_numpy(dtype=np.int8), raw_oof
        )
        rows.append({
            "modelo": model,
            "pr_auc_media": float(result["mean_pr_auc"]),
            "pr_auc_ic95": intervals[model],
            "pr_auc_dobras": [
                float(row["pr_auc"]) for row in result["fold_metrics"]
            ],
            "brier_oof_calibrado": float(calibration["brier"]),
            "roc_auc": roc_auc(frame["y"].to_numpy(dtype=np.int8), raw_oof),
            "calibration_slope": slope,
            "calibration_intercept": intercept,
            "metodo_calibracao": calibration["method"],
            "limiar_f2": float(calibration["threshold"]),
            **threshold_metrics(
                frame["y"].to_numpy(dtype=np.int8),
                calibrated,
                float(calibration["threshold"]),
            ),
            "selecionado": model == selected,
        })

    if baseline_results is not None:
        labels = frame["y"].to_numpy(dtype=np.int8)
        for model in ("B0", "B1"):
            probabilities = np.asarray(baseline_results["oof"][model], dtype=np.float64)
            slope, intercept = calibration_slope_intercept(labels, probabilities)
            rows.append({
                "modelo": model,
                "pr_auc_media": float(
                    np.mean([row["pr_auc"] for row in baseline_results["fold_metrics"][model]])
                ),
                "pr_auc_ic95": None,
                "pr_auc_dobras": [
                    float(row["pr_auc"]) for row in baseline_results["fold_metrics"][model]
                ],
                "brier_oof_calibrado": brier(labels, probabilities),
                "metodo_calibracao": "nenhuma",
                "limiar_f2": 0.5,
                "calibration_slope": slope,
                "calibration_intercept": intercept,
                **threshold_metrics(labels, probabilities, 0.5),
                "selecionado": False,
            })
        b2 = np.asarray(baseline_results["b2_predictions"], dtype=np.float64)
        slope, intercept = calibration_slope_intercept(labels, b2)
        rows.append({
            "modelo": "B2",
            "pr_auc_media": pr_auc(labels, b2),
            "pr_auc_ic95": None,
            "pr_auc_dobras": [],
            "brier_oof_calibrado": brier(labels, b2),
            "metodo_calibracao": "regra binária",
            "limiar_f2": 0.5,
            "calibration_slope": slope,
            "calibration_intercept": intercept,
            **threshold_metrics(labels, b2, 0.5),
            "selecionado": False,
        })

    report_dir = Path(cfg["caminhos"]["relatorios"]) / "m1"
    report_dir.mkdir(parents=True, exist_ok=True)
    table = pd.DataFrame(rows)
    (report_dir / "comparacao_oof.md").write_text(
        "# Comparação e seleção M1 em validação OOF\n\n"
        f"**Decisão:** {selected}. {reason}\n\n"
        f"{_markdown_table(table)}\n",
        encoding="utf-8",
    )
    selection = {
        "modelo": selected,
        "motivo": reason,
        "params": validation_runs[selected]["params"],
        "best_points": validation_runs[selected]["best_points"],
        "oof_metrics": validation_runs[selected]["oof_metrics"],
        "calibracao": {
            "metodo": calibrations[selected]["method"],
            "brier": calibrations[selected]["brier"],
            "threshold": calibrations[selected]["threshold"],
            "candidate_brier": calibrations[selected]["candidate_brier"],
        },
        "metricas_modelos": rows,
    }
    (report_dir / "selecao_m1.json").write_text(
        json.dumps(_json_value(selection), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    joblib.dump(
        calibrations[selected]["calibrator"],
        report_dir / "calibrador_m1.joblib",
        compress=3,
    )
    selection["calibrator"] = calibrations[selected]["calibrator"]
    selection["threshold"] = calibrations[selected]["threshold"]
    return selection
