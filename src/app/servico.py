"""Camada fina de serviço da aplicação: delega TUDO ao `dengue_sinan.servico`.

Carga e verificação de hashes, validação, adaptador de contrato, relatório e "E1 indisponível"
vivem num lugar só (`dengue_sinan.servico`). Aqui ficam apenas o que é da aplicação: criar o
serviço a partir da configuração e informar a versão do sistema. Sem HTTP e sem Streamlit.
"""

import platform

from app import VERSAO_APP
from app.config import Config
from dengue_sinan.pipeline.inferencia import EntradaInvalida
from dengue_sinan.servico import LoteGrande, ModeloIndisponivel, Servico
from dengue_sinan.servico.nucleo import AVISO

__all__ = [
    "AVISO",
    "EntradaInvalida",
    "LoteGrande",
    "ModeloIndisponivel",
    "Servico",
    "criar_servico",
    "info_sistema",
]


def criar_servico(config: Config) -> Servico:
    """Serviço com a configuração dada, já tentando carregar o M1 (falha = modo degradado)."""
    s = Servico(config.servico)
    s.carregar()
    return s


def info_sistema() -> dict:
    return {"app": VERSAO_APP, "python": platform.python_version()}
