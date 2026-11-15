"""Leitura da configuração do projeto."""

from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    """Carrega configuração YAML e exige um objeto no nível superior."""
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file)
    if not isinstance(config, dict):
        raise ValueError(f"A configuração em {config_path} deve ser um mapa YAML.")
    return config