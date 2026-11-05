"""Dobras leave-one-region-out e divisões internas reproduzíveis."""

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

REGIONS = ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")


def loro_folds(frame: pd.DataFrame) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Devolve índices posicionais de treino e validação para as cinco regiões."""
    required = {"regiao"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"colunas ausentes para LORO: {', '.join(sorted(missing))}")
    if frame["regiao"].isna().any():
        raise ValueError("regiao nula impede a validação leave-one-region-out")

    observed = set(frame["regiao"].astype(str).unique())
    unexpected = observed - set(REGIONS)
    if unexpected:
        raise ValueError(f"regiões não reconhecidas: {', '.join(sorted(unexpected))}")
    if observed != set(REGIONS):
        missing_regions = set(REGIONS) - observed
        raise ValueError(f"regiões sem observações para LORO: {', '.join(sorted(missing_regions))}")

    regions = frame["regiao"].astype(str).to_numpy()
    positions = np.arange(len(frame))
    return [
        (region, positions[regions != region], positions[regions == region])
        for region in REGIONS
    ]


def inner_split(
    idx_treino: np.ndarray, y: pd.Series | np.ndarray, frac: float, seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Separa uma fração estratificada da região de treino para early stopping."""
    if not 0 < frac < 1:
        raise ValueError("frac deve estar estritamente entre 0 e 1")
    indices = np.asarray(idx_treino, dtype=int)
    labels = np.asarray(y)
    if indices.ndim != 1 or len(indices) < 2:
        raise ValueError("idx_treino precisa conter ao menos duas posições")
    if labels.ndim != 1 or indices.max(initial=-1) >= len(labels) or indices.min(initial=0) < 0:
        raise ValueError("índices de treino incompatíveis com y")
    splitter = StratifiedShuffleSplit(n_splits=1, test_size=frac, random_state=seed)
    fit_rel, stop_rel = next(splitter.split(np.zeros(len(indices)), labels[indices]))
    return indices[fit_rel], indices[stop_rel]
