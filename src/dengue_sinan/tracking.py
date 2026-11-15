"""Rastreamento de experimentos no MLflow (T-2.5, §3.14, R7)."""

import json
import os
import platform
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")

import mlflow  # noqa: E402
import pandas as pd  # noqa: E402
import psutil  # noqa: E402
import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
from mlflow.environment_variables import MLFLOW_ALLOW_FILE_STORE  # noqa: E402


def _flatten_dict(d: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """Achata um dicionário aninhado em pares chave=string para `mlflow.log_params`."""
    flat: dict[str, str] = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else str(k)
        if isinstance(v, dict):
            flat.update(_flatten_dict(v, prefix=key))
        else:
            flat[key] = str(v)
    return flat


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


def hardware_info() -> dict[str, str]:
    """Coleta informações de CPU, RAM e GPU para registro no MLflow."""
    gpu_name = "CPU"
    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return {
        "hardware.python": platform.python_version(),
        "hardware.vcpus": str(psutil.cpu_count(logical=True) or 1),
        "hardware.ram_gib": f"{psutil.virtual_memory().total / (1024**3):.1f}",
        "hardware.gpu": gpu_name,
    }


def _manifest_params(cfg: dict[str, Any]) -> dict[str, str]:
    """Extrai `sha256_dbc` e `sha256_parquet` dos anos de dev do `manifest.json`."""
    data_dir = Path(cfg.get("caminhos", {}).get("dados", "data"))
    manifest_path = data_dir / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    params: dict[str, str] = {}
    for ano in cfg.get("anos_dev", [2022, 2023]):
        entry = manifest.get(str(ano), {})
        if "sha256_dbc" in entry:
            params[f"manifest.{ano}.sha256_dbc"] = str(entry["sha256_dbc"])
        if "sha256_parquet" in entry:
            params[f"manifest.{ano}.sha256_parquet"] = str(entry["sha256_parquet"])
    return params


@contextmanager
def start_run(
    cfg: dict[str, Any],
    nome: str,
    tags: dict[str, str] | None = None,
    experiment_name: str = "dengue-comorbidity-risk",
) -> Iterator[mlflow.ActiveRun]:
    """Abre um run no MLflow registrando config, seed, hashes do manifesto, commit e hardware."""
    os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
    _ = MLFLOW_ALLOW_FILE_STORE
    mlruns_dir = Path(cfg.get("caminhos", {}).get("mlruns", "mlruns")).resolve()
    mlruns_dir.mkdir(parents=True, exist_ok=True)
    mlflow.set_tracking_uri(mlruns_dir.as_uri())
    mlflow.set_experiment(experiment_name)

    commit = _git_commit()
    run_tags = {"git.commit": commit, **(tags or {})}

    with mlflow.start_run(run_name=nome, tags=run_tags) as run:
        params = {
            **_flatten_dict(cfg, prefix="cfg"),
            "seed": str(cfg.get("seed", 20261103)),
            "git.commit": commit,
            **hardware_info(),
            **_manifest_params(cfg),
        }
        mlflow.log_params(params)
        mlflow.log_dict(cfg, "config.json")
        yield run


def log_fold_metrics(regiao: str, metricas: dict[str, float]) -> None:
    """Registra no MLflow as métricas de uma dobra (região)."""
    slug = regiao.lower().replace("-", "_").replace(" ", "_")
    payload = {f"dobra.{slug}.{k}": float(v) for k, v in metricas.items() if v is not None}
    mlflow.log_metrics(payload)


def log_oof_predictions(
    oof_df: pd.DataFrame,
    nome_modelo: str,
    cfg: dict[str, Any],
) -> Path:
    """Salva as predições OOF em Parquet na pasta `oof/` ao lado de `mlruns/` (no Drive — R7)."""
    mlruns_dir = Path(cfg.get("caminhos", {}).get("mlruns", "mlruns")).resolve()
    oof_dir = mlruns_dir.parent / "oof"
    oof_dir.mkdir(parents=True, exist_ok=True)
    oof_path = oof_dir / f"{nome_modelo}_oof.parquet"
    table = pa.Table.from_pandas(oof_df, preserve_index=False)
    pq.write_table(table, oof_path, compression="zstd")
    if mlflow.active_run() is not None:
        mlflow.log_param("oof_parquet_path", str(oof_path))
    return oof_path
