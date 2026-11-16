"""Carrega `config/base.yaml`: seed, anos, caminhos e orçamentos (T-2.0, R8)."""

from pathlib import Path

import yaml

CONFIG_PADRAO = Path(__file__).resolve().parents[2] / "config" / "base.yaml"
CHAVES_OBRIGATORIAS = ("seed", "anos_dev", "ano_teste", "caminhos", "ambiente")


def load_config(path: str | Path = CONFIG_PADRAO) -> dict:
    """Lê o YAML e valida o que não pode faltar. Levanta ValueError se algo estiver errado."""
    with open(path, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"{path}: o arquivo de configuração deve ser um mapa YAML")
    faltando = [chave for chave in CHAVES_OBRIGATORIAS if chave not in cfg]
    if faltando:
        raise ValueError(f"{path}: faltam as chaves {faltando}")
    # R1: o ano de teste nunca entra no desenvolvimento.
    if cfg["ano_teste"] in cfg["anos_dev"]:
        raise ValueError(f"{path}: ano_teste={cfg['ano_teste']} está em anos_dev (R1)")
    return cfg
