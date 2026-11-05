"""Serialização de artefatos sem microdados."""

import json
from pathlib import Path
from typing import Any

import joblib

_REQUIRED_METADATA = {
    "commit",
    "hashes_dados",
    "config",
    "data_treino",
    "metricas_validacao",
    "features",
    "versoes_bibliotecas",
}


def save_bundle(obj: Any, caminho: str | Path, metadados: dict[str, Any]) -> Path:
    """Persiste modelo e metadados obrigatórios, recusando o objeto de ajuste com dados."""
    from dengue_sinan.explain import E1Fit

    if isinstance(obj, E1Fit) or (hasattr(obj, "model") and hasattr(obj.model, "data")):
        raise ValueError("serialize compact_e1(fit), não o resultado com dados de ajuste")
    missing = _REQUIRED_METADATA - metadados.keys()
    if missing:
        raise ValueError(f"metadados ausentes: {', '.join(sorted(missing))}")
    json.dumps(metadados, ensure_ascii=False)
    target = Path(caminho)
    target.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"obj": obj, "metadados": metadados}, target, compress=3)
    return target


def load_bundle(caminho: str | Path) -> tuple[Any, dict[str, Any]]:
    """Carrega o modelo e seus metadados após validar a estrutura serializada."""
    source = Path(caminho)
    if not source.is_file():
        raise FileNotFoundError(f"artefato não encontrado: {source}")
    payload = joblib.load(source)
    if (
        not isinstance(payload, dict)
        or not {"obj", "metadados"} <= payload.keys()
        or not isinstance(payload["metadados"], dict)
    ):
        raise ValueError(f"artefato inválido: {source}")
    missing = _REQUIRED_METADATA - payload["metadados"].keys()
    if missing:
        raise ValueError(f"artefato sem metadados obrigatórios: {', '.join(sorted(missing))}")
    return payload["obj"], payload["metadados"]
