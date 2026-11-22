"""Descoberta, comparação e leitura segura de artefatos já gravados (só lê)."""

import json
import re
from pathlib import Path

from dengue_sinan.pipeline import artefatos

_ID = re.compile(r"^(?P<nome>.+)-(?P<versao>\d+(?:\.\d+)*)$")


def separar_id(identificador: str) -> tuple[str, tuple[int, ...]]:
    m = _ID.match(identificador)
    if not m:
        raise ValueError(f"identificador sem versão numérica: {identificador!r}")
    return m["nome"], tuple(int(p) for p in m["versao"].split("."))


def listar(pasta_base: Path) -> list[dict]:
    """Pastas de artefato em `pasta_base`, da mais antiga para a mais nova por nome e versão.

    Não carrega modelo nem verifica hash: só olha os nomes. Use `verificar` para conferir.
    """
    pasta_base = Path(pasta_base)
    if not pasta_base.is_dir():
        return []
    achados = []
    for p in pasta_base.iterdir():
        if not p.is_dir():
            continue
        try:
            nome, versao = separar_id(p.name)
        except ValueError:
            continue
        achados.append({"identificador": p.name, "nome": nome, "versao": versao, "pasta": p})
    return sorted(achados, key=lambda a: (a["nome"], a["versao"]))


def mais_recente(pasta_base: Path, prefixo: str) -> str | None:
    """Identificador da maior versão cujo nome começa com `prefixo` (ex.: 'm1'), ou None."""
    candidatos = [a for a in listar(pasta_base) if a["nome"].split("-")[0] == prefixo]
    return candidatos[-1]["identificador"] if candidatos else None


def verificar(pasta: Path) -> dict:
    """Confere presença e hashes; devolve os metadados. Levanta `ArtefatoInvalido`."""
    return artefatos.verificar(Path(pasta))


def comparar(pasta_base: Path, identificadores: list[str]) -> list[dict]:
    """Tabela lado a lado das métricas de desenvolvimento GUARDADAS nos artefatos.

    Não recalcula nada. A comparação só vale entre artefatos avaliados nos mesmos dados e
    dobras: a coluna `escopo` mostra de onde vem cada número.
    """
    linhas = []
    for ident in identificadores:
        pasta = Path(pasta_base) / ident
        verificar(pasta)
        av = json.loads((pasta / "avaliacao_dev.json").read_text("utf-8"))
        cal = av.get("calibrado_validacao_cruzada", {})
        linhas.append(
            {
                "identificador": ident,
                "escopo": av.get("escopo"),
                "e_teste_historico": av.get("e_teste_historico"),
                "n": cal.get("n"),
                "pr_auc": cal.get("pr_auc"),
                "roc_auc": cal.get("roc_auc"),
                "brier": cal.get("brier"),
                "brier_referencia_prevalencia": cal.get("brier_referencia_prevalencia"),
            }
        )
    return linhas
