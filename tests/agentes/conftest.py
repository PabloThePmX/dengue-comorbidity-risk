"""Evita bytecode dentro do repositório ao importar os scripts de agentes (melhor esforço)."""

import sys

sys.dont_write_bytecode = True
