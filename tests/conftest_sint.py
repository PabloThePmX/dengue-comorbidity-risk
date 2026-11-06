"""Gerador de dados SINTÉTICOS compartilhado pelos testes (nunca são dados do SINAN)."""

import importlib.util
from pathlib import Path

import numpy as np

_CAMINHO = Path(__file__).resolve().parents[1] / "notebooks" / "smoke_test_sintetico.py"
_spec = importlib.util.spec_from_file_location("smoke_sint", _CAMINHO)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)


def bruto_sintetico(n: int = 20_000, ano: int = 2022, seed: int = 1):
    return _mod._sim(n, ano, np.random.default_rng(seed), 0.0)
