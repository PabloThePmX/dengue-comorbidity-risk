"""Carregamento da população SINAN e construção das features autorizadas."""

from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from dengue_sinan import profiling
from dengue_sinan.checks import REQUIRED_COLUMNS, check_year

_COMORBIDITIES = profiling.COMORBIDADES
_BINARY_FEATURES = [*profiling.COMORBIDADES, *profiling.SINAIS]


def _data_dir(cfg: dict[str, Any]) -> Path:
    try:
        return Path(cfg["caminhos"]["dados"])
    except (KeyError, TypeError) as exc:
        raise ValueError("configuração precisa definir caminhos.dados") from exc


def _write_flow_report(frames: list[pd.DataFrame], cfg: dict[str, Any]) -> None:
    minimum = int(cfg.get("supressao_min_celula", 10))
    flow_parts = [profiling.exclusion_flow(frame) for frame in frames]
    flow = pd.concat(flow_parts, axis=1)
    flow = flow.astype("Int64").fillna(0).astype("int64")
    flow = flow.mask(flow < minimum, f"<{minimum}")
    reason_parts = []
    for frame in frames:
        for label, table in profiling.exclusion_reasons(frame).items():
            part = table.copy()
            part = part.mask(part < minimum, f"<{minimum}")
            part.insert(0, "motivo", label)
            reason_parts.append(part)
    flow_path = Path(cfg.get("caminhos", {}).get("relatorios", "reports")) / "fluxograma.md"
    flow_path.parent.mkdir(parents=True, exist_ok=True)
    flow_path.write_text(
        "# Fluxograma de exclusão\n\n"
        "Contagens após cada filtro, separadas por ano do arquivo.\n\n"
        f"```text\n{flow.to_string()}\n```\n\n"
        "## Valores dos registros excluídos\n\n"
        f"```text\n{pd.concat(reason_parts).to_string()}\n```\n",
        encoding="utf-8",
    )


def load_population(cfg: dict[str, Any], anos: list[int]) -> pd.DataFrame:
    """Lê explicitamente os anos solicitados, valida schema/domínios e filtra a população."""
    if not anos or len(anos) != len(set(anos)):
        raise ValueError("anos deve ser uma lista não vazia sem repetições")

    data_dir = _data_dir(cfg)
    yearly: list[pd.DataFrame] = []
    for year in anos:
        parquet_path = data_dir / "parquet" / f"dengue_{year}.parquet"
        if not parquet_path.is_file():
            raise FileNotFoundError(f"Parquet de {year} não encontrado: {parquet_path}")
        present_columns = set(pq.ParquetFile(parquet_path).schema.names)
        missing_columns = set(REQUIRED_COLUMNS) - present_columns
        if missing_columns:
            raise ValueError(
                f"{year}: colunas obrigatórias ausentes: {', '.join(sorted(missing_columns))}"
            )
        table = pq.read_table(parquet_path, columns=list(REQUIRED_COLUMNS))
        frame = table.to_pandas(strings_to_categorical=True)
        check_year(frame, year)
        frame["ANO"] = year
        yearly.append(frame)

    _write_flow_report(yearly, cfg)
    combined = pd.concat(yearly, ignore_index=True)
    population = combined.loc[profiling.population_mask(combined)].copy()
    return profiling.add_derived(population).reset_index(drop=True)


def _yes_no_missing(series: pd.Series) -> pd.Series:
    values = profiling.code(series)
    return pd.Series(
        values.map({"1": "Sim", "2": "Não"}).fillna("Ausente"),
        index=series.index,
        dtype="string",
    )


def build_feature_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Constrói apenas as features M1 e os metadados não preditores autorizados."""
    out = pd.DataFrame(index=frame.index)
    out["idade_anos"] = pd.to_numeric(frame["idade_anos"], errors="coerce")

    sex = profiling.code(frame["CS_SEXO"])
    out["sexo"] = sex.where(sex.isin({"M", "F"}), "I").astype("string")
    out["gestante"] = profiling.code(frame["CS_GESTANT"]).isin({"1", "2", "3", "4"}).astype(
        "int8"
    )

    for column in _BINARY_FEATURES:
        out[column] = _yes_no_missing(frame[column])
    out["n_comorbidades"] = out[_COMORBIDITIES].eq("Sim").sum(axis=1).astype("int8")

    onset = profiling.parse_date(frame["DT_SIN_PRI"])
    notified = profiling.parse_date(frame["DT_NOTIFIC"])
    delay = (notified - onset).dt.days.clip(lower=0, upper=60)
    out["dias_ate_notificacao"] = delay.astype("float64")

    for column in ("ANO", "y", "regiao", "faixa_etaria", "CS_RACA", "idade_de_ano_nasc"):
        if column in frame:
            out[column] = frame[column]
    return out
