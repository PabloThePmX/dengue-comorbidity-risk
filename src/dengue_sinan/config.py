"""Carregamento dos arquivos YAML de configuração do projeto."""

from pathlib import Path
from typing import Any

import yaml

DEFAULT_CONFIG_PATH = Path("config/base.yaml")
DEFAULT_EXPECTED_PATH = Path("config/esperado.yaml")


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Lê o arquivo YAML de configuração e devolve um dicionário."""
    config_path = Path(path)
    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Configuração inválida em {config_path}: esperado mapeamento YAML.")
    return data


def load_expected(path: str | Path = DEFAULT_EXPECTED_PATH) -> dict[str, Any]:
    """Lê os valores de referência do profiling (2022–2023) de config/esperado.yaml."""
    return load_config(path)
