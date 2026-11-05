"""Avaliação externa única do teste de 2024."""

import json
import os
import platform
import time
from pathlib import Path

import numpy as np

from dengue_sinan.artifacts import load_bundle
from dengue_sinan.baselines import B1_CATEGORICAL, B1_NUMERIC, rule_b2
from dengue_sinan.dataset import build_feature_frame, load_population
from dengue_sinan.download import sha256_file
from dengue_sinan.explain import E1Bundle, predict_e1
from dengue_sinan.metrics import (
    bootstrap_ci,
    brier,
    calibration_slope_intercept,
    pr_auc,
    roc_auc,
    threshold_metrics,
)


def _probability_metrics(labels: np.ndarray, probabilities: np.ndarray, n: int, seed: int) -> dict:
    metrics = {}
    functions = {
        "pr_auc": pr_auc,
        "brier": brier,
        "roc_auc": roc_auc,
        "calibration_slope": lambda y, p: calibration_slope_intercept(y, p)[0],
        "calibration_intercept": lambda y, p: calibration_slope_intercept(y, p)[1],
    }
    for offset, (name, function) in enumerate(functions.items()):
        estimate, lower, upper = bootstrap_ci(
            function, labels, probabilities, n, seed + offset
        )
        metrics[name] = {"estimate": estimate, "ic_inf": lower, "ic_sup": upper}
    return metrics


def _bootstrap_difference(
    labels: np.ndarray,
    first: np.ndarray,
    second: np.ndarray,
    n: int,
    seed: int,
) -> dict[str, float]:
    estimate = pr_auc(labels, first) - pr_auc(labels, second)
    positive = np.flatnonzero(labels == 1)
    negative = np.flatnonzero(labels == 0)
    rng = np.random.default_rng(seed)
    values = np.empty(n)
    for index in range(n):
        draw = np.concatenate([
            rng.choice(negative, len(negative), replace=True),
            rng.choice(positive, len(positive), replace=True),
        ])
        values[index] = pr_auc(labels[draw], first[draw]) - pr_auc(
            labels[draw], second[draw]
        )
    lower, upper = np.quantile(values, [0.025, 0.975])
    return {"estimate": float(estimate), "ic_inf": float(lower), "ic_sup": float(upper)}


def _threshold_ci(
    labels: np.ndarray,
    probabilities: np.ndarray,
    threshold: float,
    n: int,
    seed: int,
) -> dict[str, dict[str, float]]:
    output = {}
    for offset, metric in enumerate(("acuracia", "precisao", "recall", "f1", "f2")):
        def function(y, p, metric=metric):
            return threshold_metrics(y, p, threshold)[metric]

        estimate, lower, upper = bootstrap_ci(function, labels, probabilities, n, seed + offset)
        output[metric] = {"estimate": estimate, "ic_inf": lower, "ic_sup": upper}
    return output


def _markdown_metrics(results: dict[str, dict]) -> str:
    lines = [
        "| Modelo | Métrica | Estimativa | IC 95% |",
        "| --- | --- | ---: | ---: |",
    ]
    for model, metrics in results.items():
        for metric, values in metrics.items():
            lines.append(
                f"| {model} | {metric} | {values['estimate']:.6g} | "
                f"[{values['ic_inf']:.6g}, {values['ic_sup']:.6g}] |"
            )
    return "\n".join(lines)


def evaluate_test_once(cfg: dict) -> dict:
    """Carrega 2024 somente após verificar artefatos e obter o lacre exclusivo."""
    test_year = int(cfg.get("ano_teste", 2024))
    reports = Path(cfg["caminhos"]["relatorios"]) / "teste"
    reports.mkdir(parents=True, exist_ok=True)
    latch = reports / "LACRE.json"
    if latch.exists():
        raise RuntimeError("teste já avaliado (R2)")

    models_dir = Path(cfg["caminhos"].get("modelos", "models"))
    artifact_paths = {
        "E1": models_dir / "e1_final.joblib",
        "B1": models_dir / "b1_final.joblib",
        "M1": models_dir / "m1_final.joblib",
    }
    for name, path in artifact_paths.items():
        if not path.is_file():
            raise FileNotFoundError(f"artefato congelado {name} não encontrado: {path}")
    model_payloads = {name: load_bundle(path) for name, path in artifact_paths.items()}
    e1, e1_metadata = model_payloads["E1"]
    b1, _ = model_payloads["B1"]
    m1, m1_metadata = model_payloads["M1"]
    if not isinstance(e1, E1Bundle):
        raise ValueError("artefato E1 não contém um E1Bundle compacto")
    if not isinstance(m1, dict) or not {"pipeline", "calibrator", "threshold"} <= m1.keys():
        raise ValueError("artefato M1 precisa conter pipeline, calibrator e threshold")
    if not hasattr(b1, "predict_proba"):
        raise ValueError("artefato B1 não implementa predict_proba")

    descriptor = os.open(latch, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump({"status": "in_progress", "ano_teste": test_year}, stream)

    test_frame = load_population(cfg, [test_year])
    features = build_feature_frame(test_frame)
    labels = test_frame["y"].to_numpy(dtype=np.int8)
    m1_raw = m1["pipeline"].predict_proba(features)[:, 1]
    m1_probabilities = np.asarray(m1["calibrator"].transform(m1_raw), dtype=np.float64)
    b1_probabilities = b1.predict_proba(
        features[B1_NUMERIC + B1_CATEGORICAL]
    )[:, 1]
    e1_probabilities = predict_e1(e1, test_frame)["risco"].to_numpy()
    b0_probability = float(m1_metadata.get("probabilidade_b0", np.nan))
    if not 0 <= b0_probability <= 1:
        raise ValueError("metadados M1 precisam incluir probabilidade_b0 válida")
    b0_probabilities = np.full(len(labels), b0_probability)
    predictions = {
        "B0": b0_probabilities,
        "B1": b1_probabilities,
        "E1": e1_probabilities,
        "M1": m1_probabilities,
    }
    bootstrap_count = int(cfg.get("bootstrap", {}).get("metricas", 1000))
    results = {
        name: _probability_metrics(
            labels, probabilities, bootstrap_count, int(cfg["seed"]) + index * 10
        )
        for index, (name, probabilities) in enumerate(predictions.items())
    }
    results["diferenca_pr_auc_M1_menos_B1"] = {
        "PR-AUC": _bootstrap_difference(
            labels, m1_probabilities, b1_probabilities,
            bootstrap_count, int(cfg["seed"]) + 100,
        )
    }
    threshold = float(m1["threshold"])
    results["M1"]["limiar_F2"] = {
        "estimate": threshold, "ic_inf": threshold, "ic_sup": threshold,
    }
    results["M1"].update(_threshold_ci(
        labels, m1_probabilities, threshold, bootstrap_count, int(cfg["seed"]) + 200
    ))
    b2_probabilities = rule_b2(test_frame).astype(float)
    results["B2"] = _threshold_ci(
        labels, b2_probabilities, 0.5, bootstrap_count, int(cfg["seed"]) + 300
    )

    manifest_path = Path(cfg["caminhos"]["dados"]) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    data_entry = manifest.get(str(test_year))
    if not data_entry or not data_entry.get("sha256_parquet"):
        raise ValueError(f"manifesto sem hash do Parquet de teste para {test_year}")
    latch_content = {
        "status": "completed",
        "ano_teste": test_year,
        "data_avaliacao": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "commit": e1_metadata["commit"],
        "hash_parquet_teste": data_entry["sha256_parquet"],
        "hash_artefatos": {
            name: sha256_file(path) for name, path in artifact_paths.items()
        },
        "plataforma": platform.platform(),
    }
    (reports / "metricas.md").write_text(
        "# Avaliação única no teste congelado\n\n"
        f"Ano do arquivo: {test_year}.\n\n"
        f"{_markdown_metrics(results)}\n\n"
        "O conjunto de teste não foi usado para ajustar modelos, calibradores ou limiares.\n",
        encoding="utf-8",
    )
    temporary_latch = latch.with_suffix(".tmp")
    temporary_latch.write_text(json.dumps(latch_content, indent=2), encoding="utf-8")
    temporary_latch.replace(latch)
    return results
