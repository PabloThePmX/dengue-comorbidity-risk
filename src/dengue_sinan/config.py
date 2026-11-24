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
    # D-97: o ano de comparação (opcional) também fica fora do desenvolvimento e do teste.
    ano_comparacao = cfg.get("ano_comparacao")
    if ano_comparacao is not None:
        if ano_comparacao in cfg["anos_dev"]:
            raise ValueError(f"{path}: ano_comparacao={ano_comparacao} está em anos_dev (R1)")
        if ano_comparacao == cfg["ano_teste"]:
            raise ValueError(f"{path}: ano_comparacao={ano_comparacao} é o ano_teste (R1)")
    return cfg
