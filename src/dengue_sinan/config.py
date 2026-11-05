"""Leitura e validação da configuração do pipeline."""

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml


def load_config(path: str | Path) -> dict[str, Any]:
    """Carrega YAML e verifica os campos-base necessários para executar o projeto."""
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as stream:
        config = yaml.safe_load(stream)
    if not isinstance(config, Mapping):
        raise ValueError(f"{config_path}: a configuração deve ser um mapa YAML")

    required = {"seed", "anos_dev", "ano_teste", "caminhos"}
    missing = required - config.keys()
    if missing:
        names = ", ".join(sorted(missing))
        raise ValueError(f"{config_path}: campos obrigatórios ausentes: {names}")
    if not isinstance(config["caminhos"], Mapping):
        raise ValueError(f"{config_path}: 'caminhos' deve ser um mapa")
    if not config["anos_dev"] or config["ano_teste"] in config["anos_dev"]:
        raise ValueError("ano_teste deve ser separado e distinto dos anos_dev")
    if int(config["seed"]) < 0:
        raise ValueError("seed deve ser um inteiro não negativo")
    return dict(config)
