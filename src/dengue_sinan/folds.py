"""Dobras leave-one-region-out e validação interna para early stopping (§3.8, FR-22, R6)."""

import numpy as np
import pandas as pd

ORDEM_REGIOES = ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"]  # plan §B


def dobras_loro(
    regiao: pd.Series, ordem: list[str] | None = None
) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Devolve (região deixada de fora, índices de treino, índices de teste da dobra).

    Linhas sem região não pertencem a nenhuma dobra de teste e ficam sempre no treino.
    """
    reg = regiao.astype("string").to_numpy(dtype=object, na_value=None)
    presentes = [r for r in (ordem or ORDEM_REGIOES) if (reg == r).any()]
    posicoes = np.arange(len(reg))
    saida = []
    for r in presentes:
        teste = posicoes[reg == r]
        treino = posicoes[reg != r]
        saida.append((r, treino, teste))
    return saida


def validacao_interna(y: np.ndarray, frac: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Separa {frac} das linhas de TREINO, estratificado pelo alvo (para early stopping)."""
    rng = np.random.default_rng(seed)
    y = np.asarray(y)
    val = np.zeros(len(y), dtype=bool)
    for classe in (0, 1):
        idx = np.flatnonzero(y == classe)
        n = max(1, int(round(frac * len(idx)))) if len(idx) else 0
        val[rng.choice(idx, size=n, replace=False)] = True
    return np.flatnonzero(~val), np.flatnonzero(val)
