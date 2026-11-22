"""Camada de serviço: um único ponto de uso dos modelos para a API HTTP e para o Streamlit.

Regras desta camada:
- Não treina, não lê microdados e não importa `preparacao`, `treino` nem leitores de dados.
- Usa só `pipeline.inferencia` e `pipeline.artefatos` (hashes conferidos ao carregar).
- Nunca inventa resultado: o que não existe (E1, limiar de alto risco) volta como
  `indisponivel` ou `None`, com o motivo.
- Não guarda nem registra o conteúdo das entradas (NFR-03); o log só tem contagens.
"""

from dengue_sinan.servico.config import ConfigServico
from dengue_sinan.servico.erros import LoteGrande, ModeloIndisponivel
from dengue_sinan.servico.nucleo import Servico

__all__ = ["ConfigServico", "LoteGrande", "ModeloIndisponivel", "Servico"]
