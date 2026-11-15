"""Rastreamento reprodutível de experimentos com MLflow."""

import ctypes
import hashlib
import json
import os
import platform
import subprocess
from pathlib import Path

import mlflow
import pandas as pd
import torch

from dengue_sinan.config import load_config

_FINAL_MODEL_NAME = "dengue-m1"
_FINAL_MODEL_ALIAS = "melhor-validacao"


def _config(cfg: dict | str | Path) -> dict:
    return load_config(cfg) if isinstance(cfg, (str, Path)) else cfg


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _hardware() -> dict[str, str | int]:
    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_ulong),
            ("dwMemoryLoad", ctypes.c_ulong),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if os.name == "nt":
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            raise OSError("Não foi possível consultar a memória física disponível.")
        memory_bytes = status.ullTotalPhys
    else:
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        memory_bytes = pages * page_size
    return {
        "cpu": platform.processor() or platform.machine(),
        "cpu_count": os.cpu_count() or 0,
        "ram_gib": round(memory_bytes / (1024**3), 2),
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else "nenhuma",
    }


def _configure_mlflow(config: dict) -> Path:
    tracking_uri = Path(config["caminhos"]["mlruns"]).resolve()
    tracking_uri.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
    mlflow.set_tracking_uri(tracking_uri.as_uri())
    registry_path = tracking_uri.with_name(f"{tracking_uri.name}_registry.db")
    mlflow.set_registry_uri(f"sqlite:///{registry_path.as_posix()}")
    return tracking_uri


def start_run(
    cfg: dict | str | Path,
    nome: str,
    tags: dict | None = None,
    *,
    include_hardware: bool = True,
):
    """Abre um run e registra configuração, proveniência e hardware."""
    config = _config(cfg)
    data_dir = Path(config["caminhos"]["dados"])
    manifest_path = data_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    hashes = {
        "sha256_manifest": _sha256(manifest_path),
        "anos": {},
    }
    for year in config["anos_dev"]:
        entry = manifest[str(year)]
        parquet_path = data_dir / entry["parquet"]
        dbc_path = data_dir / "raw" / entry["arquivo"]
        hashes["anos"][str(year)] = {
            "sha256_dbc": _sha256(dbc_path),
            "sha256_parquet": _sha256(parquet_path),
        }

    _configure_mlflow(config)
    run = mlflow.start_run(run_name=nome, tags=tags)
    mlflow.log_param("seed", config["seed"])
    mlflow.log_dict(config, "config.json")
    mlflow.log_dict(hashes, "hashes_dados.json")
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    mlflow.set_tag("git_commit", commit)
    if include_hardware:
        mlflow.log_dict(_hardware(), "hardware.json")
    return run


def log_fold_metrics(regiao: str, metricas: dict[str, float]) -> None:
    """Registra métricas identificadas pela região de validação."""
    mlflow.log_metrics({f"{name}_{regiao}": float(value) for name, value in metricas.items()})


def log_oof_predictions(oof: pd.DataFrame, cfg: dict | str | Path, nome: str) -> Path:
    """Persiste predições OOF em armazenamento local/Drive, nunca no git."""
    config = _config(cfg)
    output_dir = Path(config["caminhos"]["mlruns"]) / "oof"
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{nome}.parquet"
    oof.to_parquet(path, index=False)
    mlflow.log_artifact(str(path), artifact_path="oof")
    return path


def register_final_model(
    bundle: dict,
    bundle_path: str | Path,
    features: pd.DataFrame,
    cfg: dict | str | Path,
) -> str:
    """Registra o bundle final M1 e atualiza o alias selecionado por validação."""
    from mlflow import MlflowClient
    from mlflow.exceptions import MlflowException

    from dengue_sinan.artifacts import M1PyFuncModel, mlflow_signature

    config = _config(cfg)
    _configure_mlflow(config)
    bundle_file = Path(bundle_path)
    bundle_hash = _sha256(bundle_file)
    client = MlflowClient()

    def set_and_verify_alias(version: str | int) -> str:
        client.set_registered_model_alias(
            _FINAL_MODEL_NAME, _FINAL_MODEL_ALIAS, version
        )
        resolved = client.get_model_version_by_alias(
            _FINAL_MODEL_NAME, _FINAL_MODEL_ALIAS
        )
        if str(resolved.version) != str(version):
            raise RuntimeError(
                f"O alias {_FINAL_MODEL_ALIAS} aponta para a versão "
                f"{resolved.version}, esperada {version}."
            )
        return str(version)

    try:
        client.get_registered_model(_FINAL_MODEL_NAME)
    except MlflowException as error:
        if error.error_code != "RESOURCE_DOES_NOT_EXIST":
            raise
        client.create_registered_model(_FINAL_MODEL_NAME)

    existing = next(
        (
            version
            for version in client.search_model_versions(
                f"name='{_FINAL_MODEL_NAME}'"
            )
            if version.tags.get("sha256_bundle") == bundle_hash
        ),
        None,
    )
    if existing is not None:
        return set_and_verify_alias(existing.version)

    with start_run(config, "registro-m1-final", include_hardware=False) as run:
        mlflow.log_artifact(str(bundle_file), artifact_path="bundle")
        model_info = mlflow.pyfunc.log_model(
            name="m1_final",
            python_model=M1PyFuncModel(bundle),
            signature=mlflow_signature(features),
            code_paths=[str(Path(__file__).resolve().parents[1])],
        )
        version = client.create_model_version(
            name=_FINAL_MODEL_NAME,
            source=model_info.model_uri,
            run_id=run.info.run_id,
            tags={
                "sha256_bundle": bundle_hash,
                "modelo": str(bundle["metadados"]["modelo"]),
                "hash_dobras": str(bundle["metadados"]["hash_dobras"]),
            },
        )
        version_number = set_and_verify_alias(version.version)
        mlflow.set_tags(
            {
                "registered_model": _FINAL_MODEL_NAME,
                "registered_model_alias": _FINAL_MODEL_ALIAS,
                "registered_model_version": version_number,
            }
        )
    return version_number