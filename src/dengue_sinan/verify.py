"""Relatórios de verificação automatizada do Colab (D-56, D-57, R7)."""

import datetime as dt
import json
import math
import platform
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import psutil

from dengue_sinan.download import sha256_file

Scalar = int | float | str | bool

_TASK_TO_BLOCK_DEFAULT = {
    "checagem_inicial": "T-4.3b",
    "random_forest": "T-4.4",
    "xgboost": "T-4.5",
    "catboost": "T-4.6",
    "elastic_net": "T-4.6b",
    "mlp": "T-4.6b",
    "tabfm": "T-4.7",
    "shap": "T-4.8",
    "selecao": "T-4.9",
    "retreino": "T-4.10",
}


def _to_scalar(value: Any, field_name: str) -> Scalar:
    """Converte escalares NumPy para tipos nativos e recusa coleções/DataFrames/nulos (R7)."""
    if value is None:
        raise TypeError(f"{field_name} não pode ser None; apenas número, texto ou booleano.")
    if isinstance(value, bool | np.bool_):
        return bool(value)
    if isinstance(value, int | np.integer):
        return int(value)
    if isinstance(value, float | np.floating):
        val = float(value)
        if math.isnan(val) or math.isinf(val):
            raise ValueError(f"{field_name} não pode ser NaN ou infinito.")
        return val
    if isinstance(value, str):
        return value
    raise TypeError(
        f"{field_name} deve ser número, texto ou booleano (R7: só agregados), "
        f"recebido {type(value).__name__}."
    )


def check(
    nome: str,
    esperado: Any,
    obtido: Any,
    tolerancia: float = 0,
) -> dict[str, Any]:
    """Compara valor obtido com esperado e devolve o dicionário padronizado do check (D-56)."""
    if not isinstance(nome, str) or not nome.strip():
        raise ValueError("O nome do check deve ser uma string não vazia.")
    esp = _to_scalar(esperado, "esperado")
    obt = _to_scalar(obtido, "obtido")
    tol = _to_scalar(tolerancia, "tolerancia")
    if isinstance(tol, bool | str) or tol < 0:
        raise ValueError("tolerancia deve ser um número >= 0.")

    if isinstance(esp, bool) or isinstance(obt, bool):
        passed = (esp is obt) if (isinstance(esp, bool) and isinstance(obt, bool)) else False
    elif isinstance(esp, int | float) and isinstance(obt, int | float):
        passed = abs(float(obt) - float(esp)) <= float(tol)
    else:
        passed = obt == esp

    return {
        "nome": nome,
        "esperado": esp,
        "obtido": obt,
        "tolerancia": tol,
        "passou": bool(passed),
    }


def _validate_checks(checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Valida uma lista de checks garantindo que todos os campos respeitem R7."""
    if not isinstance(checks, list):
        raise TypeError("checks deve ser uma lista de dicionários.")
    validated: list[dict[str, Any]] = []
    for item in checks:
        if not isinstance(item, dict):
            raise TypeError("Cada check deve ser um dicionário.")
        rebuilt = check(
            nome=item["nome"],
            esperado=item["esperado"],
            obtido=item["obtido"],
            tolerancia=item.get("tolerancia", 0),
        )
        validated.append(rebuilt)
    return validated


def _git_commit() -> str:
    """Obtém o SHA atual do git ou 'desconhecido' fora de um repositório."""
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


def _default_environment() -> dict[str, Any]:
    """Coleta informações básicas de hardware e versão do Python."""
    ram_gib = round(psutil.virtual_memory().total / (1024**3), 1)
    gpu_name = "CPU"
    try:
        import torch

        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
    except Exception:
        pass
    return {
        "python": platform.python_version(),
        "ram_gib": ram_gib,
        "vcpus": psutil.cpu_count(logical=True) or 1,
        "gpu": gpu_name,
    }


def _manifest_hashes(cfg: dict[str, Any] | None) -> dict[str, str]:
    """Lê os hashes SHA-256 dos Parquets de dev (2022–23) no manifest.json, se existir."""
    if not cfg or "caminhos" not in cfg or "dados" not in cfg["caminhos"]:
        return {}
    manifest_path = Path(cfg["caminhos"]["dados"]) / "manifest.json"
    if not manifest_path.is_file():
        return {}
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    anos = [str(a) for a in cfg.get("anos_dev", [2022, 2023])]
    hashes: dict[str, str] = {}
    for ano in anos:
        if ano in manifest and "sha256_parquet" in manifest[ano]:
            hashes[ano] = str(manifest[ano]["sha256_parquet"])
    return hashes


def write_report(
    tarefa: str,
    checks: list[dict[str, Any]],
    out_dir: str | Path,
    cfg: dict[str, Any] | None = None,
    *,
    hash_dados: dict[str, str] | None = None,
    ambiente: dict[str, Any] | None = None,
    commit: str | None = None,
) -> Path:
    """Grava `out_dir/<tarefa>.json` no formato do contrato de verificação (D-56)."""
    validated = _validate_checks(checks)
    out_path = Path(out_dir) / f"{tarefa}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    report = {
        "tarefa": str(tarefa),
        "gerado_em": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": commit if commit is not None else _git_commit(),
        "ambiente": ambiente if ambiente is not None else _default_environment(),
        "hash_dados": hash_dados if hash_dados is not None else _manifest_hashes(cfg),
        "checks": validated,
        "passou": bool(validated) and all(c["passou"] for c in validated),
    }
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return out_path


def update_session_report(
    path: str | Path,
    bloco: str,
    checks: list[dict[str, Any]],
    cfg: dict[str, Any] | None = None,
    *,
    tarefa: str | None = None,
    sessao_completa: bool | None = None,
    hash_dados: dict[str, str] | None = None,
    hash_dobras: str | None = None,
    ambiente: dict[str, Any] | None = None,
    commit: str | None = None,
) -> Path:
    """Cria ou atualiza um bloco em `sessao-m1.json` preservando os demais blocos (D-57)."""
    validated = _validate_checks(checks)
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    if report_path.is_file():
        existing = json.loads(report_path.read_text(encoding="utf-8"))
    else:
        existing = {
            "sessao": "sessao-m1",
            "gerado_em": dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "commit": commit if commit is not None else _git_commit(),
            "ambiente": ambiente if ambiente is not None else _default_environment(),
            "hash_dados": hash_dados if hash_dados is not None else _manifest_hashes(cfg),
            "hash_dobras": hash_dobras or "",
            "blocos": [],
            "sessao_completa": True if sessao_completa is None else bool(sessao_completa),
            "passou": False,
        }

    existing["gerado_em"] = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    existing["commit"] = commit if commit is not None else _git_commit()
    if ambiente is not None:
        existing["ambiente"] = ambiente
    if hash_dados is not None:
        existing["hash_dados"] = hash_dados
    if hash_dobras is not None:
        existing["hash_dobras"] = hash_dobras
    if sessao_completa is not None:
        existing["sessao_completa"] = bool(sessao_completa)

    block_entry = {
        "bloco": str(bloco),
        "tarefa": tarefa or _TASK_TO_BLOCK_DEFAULT.get(str(bloco), ""),
        "checks": validated,
        "passou": bool(validated) and all(c["passou"] for c in validated),
    }

    blocos: list[dict[str, Any]] = list(existing.get("blocos", []))
    for idx, b in enumerate(blocos):
        if b.get("bloco") == bloco:
            blocos[idx] = block_entry
            break
    else:
        blocos.append(block_entry)

    existing["blocos"] = blocos
    existing["passou"] = (
        bool(existing.get("sessao_completa", True))
        and bool(blocos)
        and all(b.get("passou", False) for b in blocos)
    )

    report_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
    return report_path


__all__ = [
    "check",
    "sha256_file",
    "update_session_report",
    "write_report",
]
