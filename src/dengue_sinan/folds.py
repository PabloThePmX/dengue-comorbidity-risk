"""Divisões de validação leave-one-region-out e interna."""

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit

from dengue_sinan.guard import assert_dev_only

REGIONS = ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")


def _validate_regions(df: pd.DataFrame) -> None:
    if "regiao" not in df or "y" not in df:
        raise ValueError("DataFrame deve conter as colunas regiao e y.")
    if df["regiao"].isna().any():
        n_missing = int(df["regiao"].isna().sum())
        raise ValueError(f"{n_missing} linhas sem região; interrompa e consulte o Programador.")
    unexpected = sorted(set(df["regiao"].unique()) - set(REGIONS))
    if unexpected:
        raise ValueError(f"Regiões fora do domínio esperado: {unexpected}")
    if set(df["regiao"].unique()) != set(REGIONS):
        absent = sorted(set(REGIONS) - set(df["regiao"].unique()))
        raise ValueError(f"Regiões sem observações: {absent}")


def _validate_order(regions_order: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    order = tuple(regions_order)
    if len(order) != len(REGIONS) or set(order) != set(REGIONS):
        raise ValueError("regions_order deve conter cada uma das cinco regiões uma vez.")
    return order


def loro_folds(
    df: pd.DataFrame, regions_order: tuple[str, ...] | list[str] = REGIONS
) -> list[tuple[str, np.ndarray, np.ndarray]]:
    """Cria cinco dobras, cada uma validando em uma região inteira."""
    assert_dev_only(df)
    _validate_regions(df)
    order = _validate_order(regions_order)
    regions = df["regiao"].to_numpy()
    indices = np.arange(len(df))
    return [(region, indices[regions != region], indices[regions == region]) for region in order]


def _fold_codes(df: pd.DataFrame, order: tuple[str, ...]) -> np.ndarray:
    assert_dev_only(df)
    _validate_regions(df)
    lookup = {name: index for index, name in enumerate(order)}
    return df["regiao"].map(lookup).to_numpy(dtype=np.uint8)


def save_folds(
    df: pd.DataFrame,
    path: str | Path,
    regions_order: tuple[str, ...] | list[str] = REGIONS,
) -> tuple[Path, str]:
    """Persiste a atribuição regional compacta e devolve caminho e hash das dobras."""
    order = _validate_order(regions_order)
    codes = _fold_codes(df, order)
    digest = hashlib.sha256(
        codes.tobytes() + json.dumps(order, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    output = Path(path)
    if output.suffix != ".npz":
        output = output.with_suffix(".npz")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")
    with temporary.open("wb") as file:
        np.savez_compressed(
            file,
            region_codes=codes,
            regions=np.asarray(order, dtype=str),
            sha256=np.asarray(digest),
        )
    temporary.replace(output)
    return output, digest


def load_folds(
    df: pd.DataFrame,
    path: str | Path,
    regions_order: tuple[str, ...] | list[str] = REGIONS,
) -> tuple[list[tuple[str, np.ndarray, np.ndarray]], str]:
    """Valida o hash das dobras persistidas e reconstrói os índices LORO."""
    order = _validate_order(regions_order)
    codes = _fold_codes(df, order)
    with np.load(Path(path), allow_pickle=False) as archive:
        stored_codes = archive["region_codes"]
        stored_order = tuple(archive["regions"].tolist())
        stored_digest = str(archive["sha256"].item())
    digest = hashlib.sha256(
        stored_codes.tobytes() + json.dumps(stored_order, ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    if not np.array_equal(stored_codes, codes) or stored_order != order:
        raise ValueError("As dobras salvas não correspondem à população ou ordem atual.")
    if digest != stored_digest:
        raise ValueError("O arquivo de dobras está corrompido (hash inválido).")
    regions = np.asarray(order, dtype=object)[stored_codes]
    indices = np.arange(len(df))
    folds = [
        (region, indices[regions != region], indices[regions == region]) for region in order
    ]
    return folds, digest


def verify_and_save_folds(
    df: pd.DataFrame,
    path: str | Path,
    reports_dir: str | Path,
    expected_events: dict[str, int],
    regions_order: tuple[str, ...] | list[str] = REGIONS,
) -> tuple[Path, str, list[dict]]:
    """Persiste as dobras LORO e registra os eventos por região e o hash."""
    from dengue_sinan.verify import check_result, write_report

    order = _validate_order(regions_order)
    if set(expected_events) != set(order):
        raise ValueError("expected_events deve conter exatamente as cinco regiões.")
    output, saved_hash = save_folds(df, path, order)
    folds, loaded_hash = load_folds(df, output, order)
    validations = np.concatenate([valid for _, _, valid in folds])
    checks = [
        check_result("numero_dobras", len(order), len(folds)),
        check_result("linhas_validacao_unicas", len(df), len(np.unique(validations))),
        check_result("hash_dobras", saved_hash, loaded_hash),
        check_result("arquivo_dobras", True, output.is_file()),
    ]
    for region, _, valid in folds:
        obtained_events = int(df.iloc[valid]["y"].sum())
        checks.append(
            check_result(
                f"eventos_dobra_{region}",
                int(expected_events[region]),
                obtained_events,
            )
        )
    write_report(
        reports_dir,
        "T-2.3",
        checks,
        hash_dobras=loaded_hash,
    )
    return output, loaded_hash, checks


def inner_split(
    idx_treino: np.ndarray,
    y: pd.Series | np.ndarray,
    frac: float,
    seed: int,
) -> tuple[np.ndarray, np.ndarray]:
    """Reserva validação estratificada apenas entre os índices do treino externo."""
    indices = np.asarray(idx_treino)
    labels = y.iloc[indices].to_numpy() if isinstance(y, pd.Series) else np.asarray(y)[indices]
    if not 0 < frac < 1:
        raise ValueError("frac deve estar estritamente entre 0 e 1.")
    if len(np.unique(labels)) != 2 or np.min(np.bincount(labels.astype(int))) < 2:
        raise ValueError("A validação interna exige ao menos duas linhas de cada classe.")
    splitter = StratifiedShuffleSplit(n_splits=1, test_size=frac, random_state=seed)
    fit_local, stop_local = next(splitter.split(np.zeros(len(indices)), labels))
    return indices[fit_local], indices[stop_local]
