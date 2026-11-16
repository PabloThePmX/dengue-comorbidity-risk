"""Dobras leave-one-region-out e validação interna (T-2.3, R1, R6, D-53, D-72).

Cada dobra deixa uma região de fora (validação); as outras quatro são o treino, do qual 10%
(estratificado pelo alvo) viram a validação interna usada para parada antecipada (R6).
Todos os modelos usam estas mesmas dobras; o hash do conteúdo confere que o PC e o Colab
têm as mesmas (D-72).
"""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

from dengue_sinan.guard import assert_dev_only

COLUNA_REGIAO = "regiao"
COLUNA_ALVO = "y"
PAPEIS = ("ajuste", "parada", "validacao")


def _checar_entrada(cfg: dict, df: pd.DataFrame) -> None:
    """Confere o que as dobras precisam: teste fora, ANO inteiro, região sem nulos (🛑 se não)."""
    assert_dev_only(df)  # R1: ano de teste não entra em nenhuma dobra
    if not pd.api.types.is_integer_dtype(df["ANO"]):
        # Com ANO em texto a guarda não reconhece 2024; por isso o dtype é exigido aqui.
        raise ValueError(f"coluna ANO precisa ser inteira, não {df['ANO'].dtype} (R1)")
    if df[COLUNA_REGIAO].isna().any():
        raise ValueError("há linhas com regiao nula: parar e perguntar ao Programador (T-2.3)")
    presentes = set(df[COLUNA_REGIAO].astype(str).unique())
    esperadas = set(cfg["ordem_dobras"])
    if presentes != esperadas:
        raise ValueError(f"regiões nos dados {sorted(presentes)} != ordem_dobras "
                         f"{sorted(esperadas)}")


def loro_folds(cfg: dict, df: pd.DataFrame) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Uma dobra por região, na ordem de `cfg["ordem_dobras"]` (D-53).

    Devolve (regiao, posições de treino, posições de validação), posições de `df`.
    """
    _checar_entrada(cfg, df)
    regioes = df[COLUNA_REGIAO].astype(str).to_numpy()
    dobras = []
    for regiao in cfg["ordem_dobras"]:
        validacao = np.flatnonzero(regioes == regiao)
        treino = np.flatnonzero(regioes != regiao)
        dobras.append((regiao, treino, validacao))
    return dobras


def inner_split(
    idx_treino: np.ndarray, y, frac: float, seed: int
) -> tuple[np.ndarray, np.ndarray]:
    """Separa o treino da dobra em (ajuste, parada): `frac` para parada, estratificado por y.

    `idx_treino` são só as regiões de treino (R6): nunca a região deixada de fora.
    Posições ordenadas, para o mesmo resultado em qualquer execução.
    """
    idx_treino = np.asarray(idx_treino)
    y_treino = np.asarray(y)[idx_treino]
    divisor = StratifiedShuffleSplit(n_splits=1, test_size=frac, random_state=seed)
    pos_ajuste, pos_parada = next(divisor.split(np.zeros(len(y_treino)), y_treino))
    return np.sort(idx_treino[pos_ajuste]), np.sort(idx_treino[pos_parada])


def build_folds_frame(cfg: dict, df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por caso: id, ANO, LINHA, dobra (região de validação) e o papel em cada dobra.

    `papel_<região>` é `ajuste`, `parada` (validação interna) ou `validacao` (região deixada
    de fora). id = ano do arquivo + nº da linha no arquivo (D-46, T-2.3).
    """
    dobras = loro_folds(cfg, df)
    y = df[COLUNA_ALVO].to_numpy()
    out = pd.DataFrame({
        "ANO": df["ANO"].to_numpy(dtype="int64"),
        "LINHA": df["LINHA"].to_numpy(dtype="int64"),
    })
    out.insert(0, "id", out["ANO"].astype(str) + "-" + out["LINHA"].astype(str))
    out["dobra"] = df[COLUNA_REGIAO].astype(str).to_numpy()
    for regiao, idx_treino, _ in dobras:
        ajuste, parada = inner_split(idx_treino, y, cfg["validacao_interna_frac"], cfg["seed"])
        papel = np.full(len(df), "validacao", dtype=object)
        papel[ajuste] = "ajuste"
        papel[parada] = "parada"
        out[f"papel_{regiao}"] = papel
    return out


def _canonico(df_folds: pd.DataFrame) -> bytes:
    """CSV canônico (D-72): colunas em ordem fixa, linhas por (ANO, LINHA), sem índice."""
    if df_folds.duplicated(["ANO", "LINHA"]).any():
        # Sem chave única a ordem das linhas não é canônica e o hash deixaria de valer (D-72).
        raise ValueError("(ANO, LINHA) repetido: o id do caso não é único")
    papeis = sorted(c for c in df_folds.columns if c.startswith("papel_"))
    colunas = ["id", "ANO", "LINHA", "dobra", *papeis]
    texto = (
        df_folds[colunas]
        .sort_values(["ANO", "LINHA"], kind="mergesort")
        .to_csv(index=False, lineterminator="\n")
    )
    return texto.encode("utf-8")


def folds_hash(df_folds: pd.DataFrame) -> str:
    """SHA-256 do conteúdo das dobras (D-72); não depende da ordem das linhas nem do Parquet."""
    return hashlib.sha256(_canonico(df_folds)).hexdigest()


def save_folds(cfg: dict, df: pd.DataFrame, caminho: str | Path) -> str:
    """Grava as dobras em Parquet em `caminho` e devolve o hash do conteúdo."""
    df_folds = build_folds_frame(cfg, df)  # já confere R1, ANO e regiões
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    df_folds.to_parquet(caminho, index=False)
    return folds_hash(df_folds)


def load_folds(caminho: str | Path, hash_esperado: str) -> pd.DataFrame:
    """Lê as dobras e recusa o arquivo se o hash do conteúdo não for o esperado (D-72)."""
    df_folds = pd.read_parquet(caminho)
    obtido = folds_hash(df_folds)
    if obtido != hash_esperado:
        raise ValueError(f"hash das dobras {obtido} != esperado {hash_esperado} (D-72)")
    return df_folds
