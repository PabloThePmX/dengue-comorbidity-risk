"""Configuração da camada de produto (API e frontend).

O que é do modelo (pasta dos artefatos, identificador do M1, limite de registros, pino SHA-256)
vem de `dengue_sinan.servico.ConfigServico` (config/app.json e DENGUE_*), uma fonte só. Aqui
ficam só as opções da camada HTTP e do frontend, lidas de variáveis `DENGUE_APP_*`.
Nada aqui lê dados, manifestos ou credenciais. Os padrões servem para execução local.
"""

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from dengue_sinan.servico import ConfigServico

MAX_CORPO_PADRAO = 256 * 1024  # 256 KiB: bem acima de 1000 perfis (~60 KB)


class ConfigInvalida(ValueError):
    """Variável de ambiente com valor inaceitável."""


@dataclass(frozen=True)
class Config:
    servico: ConfigServico = field(default_factory=ConfigServico.carregar)
    api_url: str = "http://127.0.0.1:8000"
    log_nivel: str = "INFO"
    timeout_s: float = 5.0
    max_corpo_bytes: int = MAX_CORPO_PADRAO


def _numero(env: Mapping[str, str], nome: str, padrao, tipo, minimo):
    bruto = env.get(nome)
    if bruto is None or bruto == "":
        return padrao
    try:
        valor = tipo(bruto)
    except ValueError:
        raise ConfigInvalida(f"{nome}: valor inválido ({bruto!r})") from None
    if valor < minimo:
        raise ConfigInvalida(f"{nome}: deve ser >= {minimo}")
    return valor


def carregar_config(env: Mapping[str, str] | None = None) -> Config:
    env = os.environ if env is None else env
    nivel = env.get("DENGUE_APP_LOG_NIVEL", "INFO").upper()
    if nivel not in ("DEBUG", "INFO", "WARNING", "ERROR"):
        raise ConfigInvalida(f"DENGUE_APP_LOG_NIVEL: nível inválido ({nivel!r})")
    api_url = env.get("DENGUE_APP_API_URL", "http://127.0.0.1:8000").rstrip("/")
    if not api_url.startswith(("http://", "https://")):
        raise ConfigInvalida("DENGUE_APP_API_URL deve começar com http:// ou https://")
    try:
        servico = ConfigServico.carregar(ambiente=env)
    except ValueError as e:
        raise ConfigInvalida(str(e)) from None
    return Config(
        servico=servico,
        api_url=api_url,
        log_nivel=nivel,
        timeout_s=_numero(env, "DENGUE_APP_TIMEOUT_S", 5.0, float, 0.1),
        max_corpo_bytes=_numero(env, "DENGUE_APP_MAX_CORPO_BYTES", MAX_CORPO_PADRAO, int, 1024),
    )
