"""Relatórios de verificação (D-56, D-57, D-64), no formato de specs/contracts/interfaces.md.

Só agregados (R7): `obtido` aceita número, texto ou booleano; qualquer outra coisa (lista,
DataFrame, array) levanta erro. `esperado` vem de `config/esperado.yaml`, nunca de um notebook.
"""

import ctypes
import datetime as dt
import hashlib
import json
import math
import numbers
import os
import platform
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
PADRAO_TAREFA = re.compile(r"^T-\d+\.\d+[a-z]?$")  # T-2.1, T-4.3b; nada de caminho aqui


def _valor(nome: str, valor):
    """Normaliza um valor de check; recusa o que não é número, texto ou booleano (R7)."""
    if isinstance(valor, bool | str):
        return valor
    if isinstance(valor, numbers.Integral):
        return int(valor)
    if isinstance(valor, numbers.Real):
        numero = float(valor)
        if not math.isfinite(numero):
            raise ValueError(f"{nome}: valor não finito ({valor})")
        return numero
    raise TypeError(
        f"{nome}: só número, texto ou booleano (R7); recebi {type(valor).__name__}"
    )


def _numero(valor) -> bool:
    return isinstance(valor, int | float) and not isinstance(valor, bool)


def check(nome: str, esperado, obtido, tolerancia=0) -> dict:
    """Compara um valor obtido com o esperado. Números: |obtido − esperado| ≤ tolerância.

    Texto e booleano: igualdade exata (tipos diferentes nunca passam; `True` não é `1`).
    """
    esperado = _valor(nome, esperado)
    obtido = _valor(nome, obtido)
    tolerancia = _valor(f"{nome} (tolerancia)", tolerancia)
    if not _numero(tolerancia) or tolerancia < 0:
        raise ValueError(f"{nome}: a tolerância deve ser um número ≥ 0")
    if _numero(esperado) and _numero(obtido):
        passou = abs(obtido - esperado) <= tolerancia
    else:
        passou = type(esperado) is type(obtido) and esperado == obtido
    return {
        "nome": nome,
        "esperado": esperado,
        "obtido": obtido,
        "tolerancia": tolerancia,
        "passou": bool(passou),
    }


def commit_atual() -> str:
    """Commit do checkout (`git rev-parse HEAD`); "desconhecido" se não houver git (T-2.5)."""
    try:
        saida = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True,
            timeout=30, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return "desconhecido"
    return saida.stdout.strip()


def _ram_total_gib() -> float:
    """RAM física total. Windows: GlobalMemoryStatusEx; Linux (Colab): sysconf."""
    if os.name == "nt":
        class MemoriaStatus(ctypes.Structure):
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

        status = MemoriaStatus()
        status.dwLength = ctypes.sizeof(MemoriaStatus)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status))
        return status.ullTotalPhys / 2**30
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES") / 2**30


def _gpu_nome() -> str | None:
    """Nome da GPU pelo nvidia-smi; None se não houver (ou o comando não existir)."""
    try:
        saida = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=30, check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    linhas = saida.stdout.strip().splitlines()
    return linhas[0].strip() if linhas else None


def _hash_dados(cfg: dict) -> dict:
    """SHA-256 do .dbc de cada ano de desenvolvimento, lido de `data/manifest.json`."""
    manifesto = Path(cfg["caminhos"]["dados"]) / "manifest.json"
    if not manifesto.exists():
        return {}
    dados = json.loads(manifesto.read_text(encoding="utf-8"))
    return {
        str(ano): dados[str(ano)]["sha256_dbc"]
        for ano in cfg["anos_dev"]
        if str(ano) in dados
    }


def _ambiente_atual() -> dict:
    gpu = _gpu_nome()
    return {
        "python": platform.python_version(),
        "ram_gib": round(_ram_total_gib(), 1),
        "gpu": gpu or "sem GPU",
    }


def _agora() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gravar(caminho: Path, conteudo: dict) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    texto = json.dumps(conteudo, indent=2, ensure_ascii=False) + "\n"
    caminho.write_text(texto, encoding="utf-8")
    return caminho


def write_report(tarefa: str, checks: list[dict], out_dir: Path, cfg: dict) -> Path:
    """Grava `out_dir/<tarefa>.json`. `passou` = há checks e todos passaram."""
    if not PADRAO_TAREFA.match(tarefa):
        raise ValueError(f"id de tarefa inválido: {tarefa!r}")
    relatorio = {
        "tarefa": tarefa,
        "gerado_em": _agora(),
        "commit": commit_atual(),
        "ambiente": _ambiente_atual(),
        "hash_dados": _hash_dados(cfg),
        "checks": list(checks),
        "passou": bool(checks) and all(c["passou"] for c in checks),
    }
    return _gravar(Path(out_dir) / f"{tarefa}.json", relatorio)


def update_session_report(
    path: Path,
    bloco: str,
    checks: list[dict],
    cfg: dict,
    *,
    tarefa: str | None = None,
    sessao_completa: bool = False,
) -> Path:
    """Cria ou reescreve o bloco `bloco` do relatório de sessão (D-57), sem apagar os outros.

    `passou` geral = `sessao_completa` e todos os blocos passaram. `sessao_completa` fica False
    até a última etapa de `run_all_models` chamar esta função com `sessao_completa=True`.
    """
    path = Path(path)
    if path.exists():
        relatorio = json.loads(path.read_text(encoding="utf-8"))
    else:
        relatorio = {
            "sessao": path.stem,
            "ambiente": _ambiente_atual(),
            "hash_dados": _hash_dados(cfg),
            "blocos": [],
        }
    relatorio["gerado_em"] = _agora()
    relatorio["commit"] = commit_atual()
    novo = {"bloco": bloco}
    if tarefa is not None:
        novo["tarefa"] = tarefa
    novo["checks"] = list(checks)
    novo["passou"] = bool(checks) and all(c["passou"] for c in checks)
    blocos = [b for b in relatorio.get("blocos", []) if b["bloco"] != bloco]
    blocos.append(novo)  # na ordem em que foram gravados
    relatorio["blocos"] = blocos
    relatorio["sessao_completa"] = bool(sessao_completa)
    relatorio["passou"] = bool(sessao_completa) and bool(blocos) and all(
        b["passou"] for b in blocos)
    return _gravar(path, relatorio)


def show_report(path: Path) -> str:
    """Imprime o conteúdo de um arquivo de texto e o SHA-256 dos seus bytes; devolve o hash.

    É o que o agente lê pelo MCP do Colab (D-64) para salvar a cópia local e conferir o hash.
    """
    dados = Path(path).read_bytes()
    sha = hashlib.sha256(dados).hexdigest()
    print(dados.decode("utf-8"))
    print(f"SHA-256: {sha}")
    return sha


def environment(
    cfg: dict,
    *,
    gpu_nome: str | None = None,
    ram_gib: float | None = None,
    vcpus: int | None = None,
) -> list[dict]:
    """Confere GPU e RAM contra `cfg["ambiente"]`; o nº de vCPUs é só registro.

    Os argumentos substituem a detecção automática (usados nos testes com valores simulados).
    Um check de GPU passa se o nome contém o valor esperado; `gpu: null` não exige GPU.
    """
    minimo = cfg["ambiente"]
    gpu = gpu_nome if gpu_nome is not None else _gpu_nome()
    ram = ram_gib if ram_gib is not None else round(_ram_total_gib(), 1)
    cpus = vcpus if vcpus is not None else (os.cpu_count() or 0)

    esperada_gpu = minimo.get("gpu")
    passou_gpu = esperada_gpu is None or (gpu is not None and esperada_gpu in gpu)
    esperado_ram = minimo["ram_min_gib"]
    return [
        {
            "nome": "gpu",
            "esperado": esperada_gpu,
            "obtido": gpu or "sem GPU",
            "tolerancia": 0,
            "passou": bool(passou_gpu),
        },
        {
            "nome": "ram_gib",
            "esperado": esperado_ram,
            "obtido": _valor("ram_gib", ram),
            "tolerancia": 0,
            "passou": bool(ram >= esperado_ram),
        },
        {  # registro: nunca reprova a sessão
            "nome": "vcpus",
            "esperado": None,
            "obtido": int(cpus),
            "tolerancia": 0,
            "passou": True,
        },
    ]
