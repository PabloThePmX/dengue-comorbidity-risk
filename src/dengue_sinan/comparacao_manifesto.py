"""Manifesto da comparação em 2025 (D-97): carrega e valida antes de qualquer leitura de 2025.

O manifesto declara o conjunto fechado de modelos (artefato com SHA-256, anos de treino, limiar).
Aqui só se valida o arquivo; a avaliação e o lacre vêm depois. Não lê dados.
"""

import re
from pathlib import Path

import yaml

from dengue_sinan.config import CONFIG_PADRAO, load_config

MANIFESTO_PADRAO = CONFIG_PADRAO.parent / "comparacao" / "manifesto.yaml"
_SHA256 = re.compile(r"[0-9a-f]{64}")
CHAVES_DO_MODELO = ("id", "papel", "origem", "artefato", "treino_anos", "limiar")
CHAVES_DOS_DADOS = ("ano", "arquivo", "sha256")


def carregar_manifesto(path: str | Path = MANIFESTO_PADRAO, cfg: dict | None = None) -> dict:
    """Lê o manifesto e levanta ValueError se algo violar o D-97."""
    with open(path, encoding="utf-8") as f:
        m = yaml.safe_load(f)
    cfg = cfg if cfg is not None else load_config()
    ano = cfg.get("ano_comparacao")
    if m.get("ano_comparacao") != ano:
        raise ValueError(f"manifesto: ano_comparacao={m.get('ano_comparacao')} difere do config "
                         f"({ano})")
    ids: list[str] = []
    for modelo in m["modelos"]:
        faltam = [c for c in CHAVES_DO_MODELO if c not in modelo]
        if faltam:
            raise ValueError(f"manifesto: modelo {modelo.get('id')} sem as chaves {faltam}")
        ids.append(modelo["id"])
        if ano in modelo["treino_anos"]:
            raise ValueError(f"manifesto: {modelo['id']} foi treinado em {ano} (R1, D-97)")
        artefato = modelo["artefato"]
        if artefato is not None and not _SHA256.fullmatch(str(artefato.get("sha256", ""))):
            raise ValueError(f"manifesto: {modelo['id']} sem SHA-256 válido (64 hex)")
    if len(set(ids)) != len(ids):
        raise ValueError("manifesto: ids de modelos repetidos")
    _validar_dados(m.get("dados"), ano)
    for fora in m.get("fora_do_conjunto", []):
        if fora["id"] in ids:
            raise ValueError(f"manifesto: {fora['id']} está dentro e fora do conjunto")
    return m


def _validar_dados(dados, ano: int) -> None:
    """Chave `dados` (T-8.9): o .dbc do ano de comparação, pelo nome e pelo SHA-256 (64 hex)."""
    if not isinstance(dados, dict):
        raise ValueError("manifesto: falta a chave `dados` (ano, arquivo e sha256 do .dbc, T-8.9)")
    faltam = [c for c in CHAVES_DOS_DADOS if c not in dados]
    if faltam:
        raise ValueError(f"manifesto: `dados` sem as chaves {faltam}")
    if dados["ano"] != ano:
        raise ValueError(f"manifesto: dados.ano={dados['ano']} difere do ano de comparação ({ano})")
    if dados["arquivo"] != f"DENGBR{ano % 100:02d}.dbc":
        raise ValueError(f"manifesto: dados.arquivo={dados['arquivo']!r} não é o .dbc de {ano}")
    if not _SHA256.fullmatch(str(dados["sha256"])):
        raise ValueError("manifesto: dados sem SHA-256 válido (64 hex)")


def exportar_json(destino: str | Path, path: str | Path = MANIFESTO_PADRAO,
                  cfg: dict | None = None) -> Path:
    """Grava o manifesto validado em JSON, para ambientes sem PyYAML (o worktree da branch).

    Passa por `carregar_manifesto`: só sai o que o YAML validado diz, sem edição à mão.
    """
    import json

    m = carregar_manifesto(path, cfg)
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(m, indent=2, ensure_ascii=False, default=str) + "\n",
                       encoding="utf-8")
    return destino
