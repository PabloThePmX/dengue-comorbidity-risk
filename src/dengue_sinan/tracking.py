"""Rastreamento reprodutível de execuções no MLflow."""

import ctypes
import json
import os
import platform
import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import mlflow
import pandas as pd


def _commit_hash() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.PIPE
    ).strip()


def _memory_gib() -> float:
    if os.name == "nt":
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("length", ctypes.c_ulong),
                ("memory_load", ctypes.c_ulong),
                ("total_phys", ctypes.c_ulonglong),
                ("avail_phys", ctypes.c_ulonglong),
                ("total_page", ctypes.c_ulonglong),
                ("avail_page", ctypes.c_ulonglong),
                ("total_virtual", ctypes.c_ulonglong),
                ("avail_virtual", ctypes.c_ulonglong),
                ("avail_extended", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("não foi possível consultar a memória disponível")
        return status.total_phys / 1024**3
    page_size = os.sysconf("SC_PAGE_SIZE")
    pages = os.sysconf("SC_PHYS_PAGES")
    return page_size * pages / 1024**3


def _hardware_info() -> dict[str, Any]:
    import torch

    return {
        "platform": platform.platform(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "ram_gib": round(_memory_gib(), 2),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
    }


def _data_hashes(cfg: dict[str, Any]) -> dict[str, dict[str, str]]:
    manifest_path = Path(cfg["caminhos"]["dados"]) / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"manifesto de dados não encontrado: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    hashes = {}
    for year in cfg["anos_dev"]:
        entry = manifest.get(str(year))
        if not entry or not entry.get("sha256_dbc") or not entry.get("sha256_parquet"):
            raise ValueError(f"manifesto sem hashes completos para {year}")
        hashes[str(year)] = {
            "sha256_dbc": entry["sha256_dbc"],
            "sha256_parquet": entry["sha256_parquet"],
        }
    return hashes


@contextmanager
def start_run(cfg: dict[str, Any], nome: str, tags: dict[str, str] | None = None):
    """Abre e fecha run MLflow com configuração, proveniência e hardware."""
    mlruns = Path(cfg["caminhos"]["mlruns"]).resolve()
    mlruns.mkdir(parents=True, exist_ok=True)
    os.environ["MLFLOW_ALLOW_FILE_STORE"] = "true"
    mlflow.set_tracking_uri(mlruns.as_uri())
    mlflow.set_experiment(cfg.get("experimento", "dengue-comorbidity-risk"))
    with mlflow.start_run(run_name=nome, tags=tags) as run:
        mlflow.log_dict(cfg, "config.json")
        mlflow.log_dict(_data_hashes(cfg), "hashes_dados.json")
        mlflow.log_dict(_hardware_info(), "hardware.json")
        mlflow.log_params({
            "seed": str(cfg["seed"]),
            "git_commit": _commit_hash(),
        })
        yield run


def log_fold_metrics(regiao: str, metricas: dict[str, float]) -> None:
    """Registra métricas de uma dobra usando nomes com prefixo da região."""
    mlflow.log_metrics({f"{regiao}.{name}": float(value)
                        for name, value in metricas.items() if pd.notna(value)})


def log_oof_predictions(
    cfg: dict[str, Any],
    nome: str,
    y: pd.Series,
    probabilities: pd.Series,
    regions: pd.Series,
) -> Path:
    """Salva predições OOF em Parquet no armazenamento MLflow local/Drive."""
    if not (len(y) == len(probabilities) == len(regions)):
        raise ValueError("y, probabilities e regions devem ter o mesmo tamanho")
    directory = Path(cfg["caminhos"]["mlruns"]) / "oof"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{nome}.parquet"
    pd.DataFrame({
        "y": y.to_numpy(),
        "probabilidade": probabilities.to_numpy(),
        "regiao": regions.astype("string").to_numpy(),
    }).to_parquet(path, index=False)
    mlflow.log_artifact(str(path), artifact_path="oof")
    return path
