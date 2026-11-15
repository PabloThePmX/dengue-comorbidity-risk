"""Relatórios agregados de verificação para execuções no Colab."""

import json
import platform
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from dengue_sinan.tracking import _hardware


def check_result(
    nome: str,
    esperado: int | float | str | bool,
    obtido: int | float | str | bool,
    tolerancia: int | float = 0,
) -> dict:
    """Compara um resultado verificável sem incluir dados por paciente."""
    if isinstance(esperado, (int, float)) and isinstance(obtido, (int, float)):
        passou = abs(float(obtido) - float(esperado)) <= float(tolerancia)
    else:
        passou = obtido == esperado
    return {
        "nome": nome,
        "esperado": esperado,
        "obtido": obtido,
        "tolerancia": tolerancia,
        "passou": bool(passou),
    }


def check_at_most(
    nome: str,
    limite: int | float,
    obtido: int | float,
) -> dict:
    """Verifica um limite superior, como o orçamento de tempo de um modelo."""
    return {
        "nome": nome,
        "esperado": limite,
        "obtido": obtido,
        "tolerancia": 0,
        "passou": bool(float(obtido) <= float(limite)),
    }


def _commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _environment() -> dict:
    hardware = _hardware()
    return {
        "python": platform.python_version(),
        "gpu": hardware["gpu"],
        "vcpus": int(hardware["cpu_count"]),
        "ram_gib": float(hardware["ram_gib"]),
    }


def _write_atomic(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path


def write_report(
    reports_dir: str | Path,
    tarefa: str,
    checks: list[dict],
    *,
    hash_dados: dict[str, str] | None = None,
    hash_dobras: str | None = None,
) -> Path:
    """Grava um relatório agregado de tarefa sem incluir predições individuais."""
    report = {
        "tarefa": tarefa,
        "gerado_em": datetime.now(UTC).isoformat(),
        "commit": _commit(),
        "ambiente": _environment(),
        "hash_dados": hash_dados or {},
        "checks": checks,
        "passou": all(item["passou"] for item in checks),
    }
    if hash_dobras is not None:
        report["hash_dobras"] = hash_dobras
    return _write_atomic(Path(reports_dir) / "verificacao" / f"{tarefa}.json", report)


def update_session_report(
    reports_dir: str | Path,
    *,
    bloco: str,
    tarefa: str,
    checks: list[dict],
    hash_dados: dict[str, str],
    hash_dobras: str,
    sessao_completa: bool = False,
) -> Path:
    """Atualiza um bloco da sessão M1 sem descartar progresso anterior."""
    path = Path(reports_dir) / "verificacao" / "sessao-m1.json"
    if path.exists():
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("sessao") != "sessao-m1":
            raise ValueError(f"Relatório de sessão incompatível: {path}")
    else:
        report = {}

    if report.get("hash_dados") != hash_dados or report.get("hash_dobras") != hash_dobras:
        report = {
            "sessao": "sessao-m1",
            "gerado_em": "",
            "commit": _commit(),
            "ambiente": _environment(),
            "hash_dados": hash_dados,
            "hash_dobras": hash_dobras,
            "blocos": [],
            "sessao_completa": False,
            "passou": False,
        }
    block = {
        "bloco": bloco,
        "tarefa": tarefa,
        "checks": checks,
        "passou": all(item["passou"] for item in checks),
    }
    blocks = report["blocos"]
    existing_index = next(
        (index for index, item in enumerate(blocks) if item["bloco"] == bloco), None
    )
    if existing_index is None:
        blocks.append(block)
    else:
        blocks[existing_index] = block
    report["gerado_em"] = datetime.now(UTC).isoformat()
    report["sessao_completa"] = bool(sessao_completa)
    report["passou"] = report["sessao_completa"] and all(
        item["passou"] for item in blocks
    )
    return _write_atomic(path, report)
