"""Dobras leave-one-region-out (LORO) e validação interna estratificada (T-2.3, D-53, R6)."""

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.model_selection import StratifiedShuffleSplit

from dengue_sinan.config import DEFAULT_EXPECTED_PATH, load_expected
from dengue_sinan.download import sha256_file
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.verify import check, write_report

DEFAULT_FOLD_ORDER = ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"]


def loro_folds(
    df: pd.DataFrame,
    ordem_dobras: list[str] | None = None,
) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Devolve `[(regiao, idx_treino, idx_validacao)]` na ordem fixa `ordem_dobras` (D-53)."""
    assert_dev_only(df)
    if "regiao" not in df.columns:
        raise ValueError("DataFrame precisa conter a coluna 'regiao'.")
    if df["regiao"].isna().any():
        raise ValueError(
            "🛑 PARE E PERGUNTE: encontradas linhas com 'regiao' nula ao construir as dobras."
        )

    order = list(ordem_dobras) if ordem_dobras is not None else list(DEFAULT_FOLD_ORDER)
    regioes_series = df["regiao"].astype("string")
    present = set(regioes_series.unique())
    unknown = sorted(present - set(order))
    if unknown:
        raise ValueError(f"Regiões desconhecidas encontradas: {unknown}")

    folds: list[tuple[str, np.ndarray, np.ndarray]] = []
    for regiao in order:
        if regiao not in present:
            continue
        is_val = (regioes_series == regiao).to_numpy(dtype=bool)
        idx_val = np.flatnonzero(is_val)
        idx_train = np.flatnonzero(~is_val)
        if len(idx_train) == 0 or len(idx_val) == 0:
            raise ValueError(f"Dobra '{regiao}' ficou sem amostras de treino ou de validação.")
        folds.append((regiao, idx_train, idx_val))
    return folds


def inner_split(
    idx_treino: np.ndarray,
    y: pd.Series | np.ndarray,
    frac: float = 0.10,
    seed: int = 20261103,
) -> tuple[np.ndarray, np.ndarray]:
    """Separa `idx_treino` em `(idx_ajuste, idx_parada)` estratificado pelo alvo (R6)."""
    idx_arr = np.asarray(idx_treino, dtype=np.int64)
    y_arr = np.asarray(y)[idx_arr]
    splitter = StratifiedShuffleSplit(n_splits=1, test_size=float(frac), random_state=int(seed))
    rel_fit, rel_val = next(splitter.split(idx_arr, y_arr))
    return idx_arr[rel_fit], idx_arr[rel_val]


def save_folds(
    cfg: dict[str, Any],
    df: pd.DataFrame,
    caminho: str | Path,
) -> str:
    """Salva em Parquet a dobra de validação e as flags de validação interna; devolve o SHA-256."""
    assert_dev_only(df)
    ordem = cfg.get("ordem_dobras", DEFAULT_FOLD_ORDER)
    frac = float(cfg.get("validacao_interna_frac", 0.10))
    seed = int(cfg.get("seed", 20261103))

    folds = loro_folds(df, ordem_dobras=ordem)
    y_arr = df["y"].to_numpy()

    fold_df = pd.DataFrame(
        {
            "id": np.arange(len(df), dtype=np.int64),
            "dobra_validacao": df["regiao"].astype("string").to_numpy(),
        }
    )

    for regiao, idx_train, _ in folds:
        _, idx_parada = inner_split(idx_train, y_arr, frac=frac, seed=seed)
        flag = np.zeros(len(df), dtype=bool)
        flag[idx_parada] = True
        fold_df[f"parada_{regiao}"] = flag

    out_path = Path(caminho)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(fold_df, preserve_index=False)
    pq.write_table(table, out_path, compression="zstd")
    return sha256_file(out_path)


def load_folds(caminho: str | Path, hash_esperado: str) -> pd.DataFrame:
    """Lê o arquivo Parquet de dobras e falha se o SHA-256 divergir de `hash_esperado` (D-53)."""
    fold_path = Path(caminho)
    if not fold_path.is_file():
        raise FileNotFoundError(f"Arquivo de dobras não encontrado: {fold_path}")
    actual_hash = sha256_file(fold_path)
    if actual_hash != hash_esperado:
        raise ValueError(
            f"Hash do arquivo de dobras ({actual_hash}) difere do esperado ({hash_esperado})."
        )
    return pq.read_table(fold_path).to_pandas()


def verify_t2_3(
    cfg: dict[str, Any],
    df: pd.DataFrame,
    *,
    folds_path: str | Path | None = None,
    expected_path: str | Path = DEFAULT_EXPECTED_PATH,
    out_dir: str | Path | None = None,
) -> Path:
    """Verifica as dobras LORO e o hash do arquivo salvo, gravando `T-2.3.json` (D-56)."""
    assert_dev_only(df)
    esperado = load_expected(expected_path)
    ordem = cfg.get("ordem_dobras", DEFAULT_FOLD_ORDER)
    folds = loro_folds(df, ordem_dobras=ordem)

    target_folds_path = (
        Path(folds_path)
        if folds_path is not None
        else Path(cfg["caminhos"]["dados"]) / "folds_2022_2023.parquet"
    )
    fold_hash = save_folds(cfg, df, target_folds_path)
    loaded = load_folds(target_folds_path, fold_hash)

    checks = [
        check("n_dobras", 5, len(folds)),
        check("linhas_arquivo_dobras", int(len(df)), int(len(loaded))),
        check("hash_dobras_nao_vazio", True, bool(len(fold_hash) == 64)),
    ]

    y_arr = df["y"].to_numpy()
    for regiao, _, idx_val in folds:
        exp_casos = esperado["casos_por_regiao_dev"][regiao]
        exp_eventos = esperado["eventos_por_regiao_dev"][regiao]
        checks.append(check(f"casos_{regiao}", exp_casos, int(len(idx_val))))
        checks.append(check(f"eventos_{regiao}", exp_eventos, int(y_arr[idx_val].sum())))

    dest_dir = (
        Path(out_dir)
        if out_dir is not None
        else Path(cfg.get("caminhos", {}).get("relatorios", "reports")) / "verificacao"
    )
    return write_report("T-2.3", checks, dest_dir, cfg)
