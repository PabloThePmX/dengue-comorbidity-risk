"""Execução explícita dos estágios de desenvolvimento, sem carregar o teste."""

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from dengue_sinan.baselines import run_baselines_loro
from dengue_sinan.config import load_config
from dengue_sinan.dataset import load_population
from dengue_sinan.selection import calibrate_and_select_m1
from dengue_sinan.training import train_final_b1, train_final_e1, train_final_m1
from dengue_sinan.tuning import tune

M1_CANDIDATES = ("elastic_net", "random_forest", "xgboost", "catboost", "mlp")


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


def _read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"arquivo de etapa anterior não encontrado: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _optuna_dir(cfg: dict) -> Path:
    return Path(cfg["caminhos"]["mlruns"]).parent / "optuna"


def _run_tuning(cfg: dict, frame: pd.DataFrame, model: str | None = None) -> None:
    baseline = run_baselines_loro(frame, int(cfg["seed"]))
    output = Path(cfg["caminhos"]["mlruns"]) / "oof"
    output.mkdir(parents=True, exist_ok=True)
    oof = pd.DataFrame({
        "y": frame["y"].to_numpy(),
        "regiao": frame["regiao"].astype("string").to_numpy(),
        "B0": baseline["oof"]["B0"],
        "B1": baseline["oof"]["B1"],
        "B2": baseline["b2_predictions"].astype(float),
    })
    oof.to_parquet(output / "baselines.parquet", index=False)
    metrics = {
        "metrics": baseline["metrics"],
        "fold_metrics": baseline["fold_metrics"],
        "b2": baseline["b2"],
    }
    (output / "baselines_metricas.json").write_text(
        json.dumps(_json_value(metrics), indent=2, ensure_ascii=False, allow_nan=False),
        encoding="utf-8",
    )
    models = (model,) if model is not None else M1_CANDIDATES
    for candidate in models:
        tune(cfg, candidate, frame)


def _load_baselines(cfg: dict, frame: pd.DataFrame) -> dict:
    output = Path(cfg["caminhos"]["mlruns"]) / "oof"
    oof = pd.read_parquet(output / "baselines.parquet")
    if len(oof) != len(frame):
        raise ValueError("OOF dos baselines não tem uma linha por observação")
    if not oof["y"].equals(frame["y"].reset_index(drop=True)):
        raise ValueError("rótulos OOF dos baselines não correspondem ao desenvolvimento")
    if not oof["regiao"].astype("string").equals(
        frame["regiao"].astype("string").reset_index(drop=True)
    ):
        raise ValueError("regiões OOF dos baselines não correspondem ao desenvolvimento")
    metrics = _read_json(output / "baselines_metricas.json")
    return {
        "oof": {model: oof[model].to_numpy() for model in ("B0", "B1")},
        "b2_predictions": oof["B2"].to_numpy(dtype=bool),
        "fold_metrics": metrics["fold_metrics"],
        "metrics": metrics["metrics"],
        "b2": metrics["b2"],
    }


def _run_selection(cfg: dict, frame: pd.DataFrame) -> None:
    validation_dir = _optuna_dir(cfg)
    runs = {
        model: _read_json(validation_dir / f"{model}_melhor_validacao.json")
        for model in M1_CANDIDATES
    }
    calibrate_and_select_m1(cfg, frame, runs, _load_baselines(cfg, frame))


def _run_final_training(cfg: dict, frame: pd.DataFrame) -> None:
    report_dir = Path(cfg["caminhos"]["relatorios"]) / "m1"
    selection = _read_json(report_dir / "selecao_m1.json")
    calibrator_path = report_dir / "calibrador_m1.joblib"
    if not calibrator_path.is_file():
        raise FileNotFoundError(f"calibrador OOF não encontrado: {calibrator_path}")
    calibrator = joblib.load(calibrator_path)
    train_final_m1(
        cfg,
        frame,
        selection["modelo"],
        selection["params"],
        calibrator,
        float(selection["calibracao"]["threshold"]),
        selection["best_points"],
        selection["oof_metrics"],
    )
    baseline_metrics = _read_json(
        Path(cfg["caminhos"]["mlruns"]) / "oof" / "baselines_metricas.json"
    )
    train_final_b1(cfg, frame, baseline_metrics["metrics"]["B1"])


def _run_e1(cfg: dict, frame: pd.DataFrame, args: argparse.Namespace) -> None:
    if not args.reference_profile or not args.age_references or args.gestante is None:
        raise ValueError(
            "o estágio e1 exige --reference-profile, --age-references e --gestante; "
            "os perfis de referência são decisões explícitas do projeto"
        )
    reference = _read_json(Path(args.reference_profile))
    ages = _read_json(Path(args.age_references))
    train_final_e1(cfg, frame, reference, ages, args.gestante == "sim")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config/base.yaml")
    parser.add_argument(
        "--stage",
        required=True,
        choices=("tune", "select", "train", "e1"),
        help="estágio de desenvolvimento; não inclui a avaliação única de 2024",
    )
    parser.add_argument("--reference-profile")
    parser.add_argument("--age-references")
    parser.add_argument("--gestante", choices=("sim", "nao"))
    parser.add_argument(
        "--model",
        choices=M1_CANDIDATES,
        help="executa apenas um candidato na etapa tune; útil para retomar no Colab",
    )
    args = parser.parse_args()
    if args.model is not None and args.stage != "tune":
        parser.error("--model só pode ser usado com --stage tune")

    cfg = load_config(args.config)
    frame = load_population(cfg, [int(year) for year in cfg["anos_dev"]])
    if args.stage == "tune":
        _run_tuning(cfg, frame, args.model)
    elif args.stage == "select":
        _run_selection(cfg, frame)
    elif args.stage == "train":
        _run_final_training(cfg, frame)
    else:
        _run_e1(cfg, frame, args)


if __name__ == "__main__":
    main()
