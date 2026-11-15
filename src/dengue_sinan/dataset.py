"""Carregamento anual do SINAN e construção das features aprovadas."""

import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from dengue_sinan.checks import check_data
from dengue_sinan.config import load_config
from dengue_sinan.profiling import (
    COMORBIDADES,
    SINAIS,
    add_derived,
    code,
    exclusion_flow,
    exclusion_reasons,
    population_mask,
)

logger = logging.getLogger(__name__)
SOURCE_COLUMNS = [
    "CLASSI_FIN",
    "EVOLUCAO",
    "NU_IDADE_N",
    "ANO_NASC",
    "DT_SIN_PRI",
    "DT_NOTIFIC",
    "CS_SEXO",
    "CS_GESTANT",
    "CS_RACA",
    "ID_MN_RESI",
    "SG_UF",
    *COMORBIDADES,
    *SINAIS,
]
COMORBIDITY_FEATURES = [f"{name.lower()}" for name in COMORBIDADES]
SYMPTOM_FEATURES = [f"{name.lower()}" for name in SINAIS]
FEATURE_COLUMNS = [
    "idade_anos",
    "sexo",
    "gestante",
    *COMORBIDITY_FEATURES,
    "n_comorbidades",
    *SYMPTOM_FEATURES,
    "dias_ate_notificacao",
]


def _format_suppressed(value: int) -> str:
    return str(value) if value >= 10 else "<10"


def _write_flow_report(frames: list[pd.DataFrame], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    combined = pd.concat(frames, ignore_index=True)
    flow = exclusion_flow(combined)
    reasons = exclusion_reasons(combined)
    lines = [
        "# Fluxograma de seleção da população",
        "",
        "Contagens agregadas por ano; células com menos de 10 observações foram suprimidas.",
        "",
        "| Etapa | " + " | ".join(map(str, flow.columns)) + " |",
        "|---|" + "|".join("---:" for _ in flow.columns) + "|",
    ]
    for step, row in flow.iterrows():
        lines.append(f"| {step} | " + " | ".join(_format_suppressed(int(n)) for n in row) + " |")
    for title, table in reasons.items():
        lines.extend(["", f"## {title}", ""])
        if table.empty:
            lines.append("Nenhum registro excluído nesta etapa.")
            continue
        columns = table.columns.tolist()
        lines.append("| Valor | " + " | ".join(map(str, columns)) + " |")
        lines.append("|---|" + "|".join("---:" for _ in columns) + "|")
        for label, row in table.iterrows():
            lines.append(
                f"| {label} | "
                + " | ".join(_format_suppressed(int(n)) for n in row)
                + " |"
            )
    (reports_dir / "fluxograma.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_population(cfg: dict | str | Path, anos: list[int]) -> pd.DataFrame:
    """Carrega explicitamente os anos solicitados, valida e filtra a população."""
    if not anos or len(set(anos)) != len(anos):
        raise ValueError("Informe uma lista não vazia de anos sem duplicatas.")
    config = load_config(cfg) if isinstance(cfg, (str, Path)) else cfg
    data_dir = Path(config["caminhos"]["dados"])
    raw_frames = []
    selected_frames = []
    for year in anos:
        path = data_dir / "parquet" / f"dengue_{year}.parquet"
        table = pq.read_table(path, columns=SOURCE_COLUMNS)
        raw = table.to_pandas(strings_to_categorical=True)
        raw["ANO"] = year
        check_data(raw, year)
        raw_frames.append(raw)
        selected = add_derived(raw.loc[population_mask(raw)].copy())
        selected_frames.append(selected)

    reports_dir = Path(config["caminhos"]["relatorios"])
    _write_flow_report(raw_frames, reports_dir)
    population = pd.concat(selected_frames, ignore_index=True)
    logger.info(
        "População carregada para %s: %s casos, %s eventos",
        anos,
        len(population),
        int(population["y"].sum()),
    )
    return population


def _three_level(series: pd.Series) -> pd.Series:
    values = code(series)
    return pd.Series(
        np.select([values.eq("1"), values.eq("2")], ["Sim", "Não"], default="Ausente"),
        index=series.index,
        dtype="string",
    )


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Constrói exclusivamente as features M1 especificadas em TODO §1.3."""
    required = set(SOURCE_COLUMNS) - {"CLASSI_FIN", "EVOLUCAO"}
    missing = sorted(required - set(df.columns))
    if missing:
        raise ValueError(f"Colunas para construção das features ausentes: {missing}")

    features = pd.DataFrame(index=df.index)
    features["idade_anos"] = pd.to_numeric(df["idade_anos"], errors="coerce")
    sex = code(df["CS_SEXO"])
    features["sexo"] = sex.where(sex.isin({"M", "F"}), "I").astype("string")
    features["gestante"] = df["gestante"].astype("int8")

    comorbidity_levels = []
    for source, target in zip(COMORBIDADES, COMORBIDITY_FEATURES, strict=True):
        features[target] = _three_level(df[source])
        comorbidity_levels.append(features[target].eq("Sim").astype("int8"))
    features["n_comorbidades"] = pd.concat(comorbidity_levels, axis=1).sum(axis=1).astype("int8")

    for source, target in zip(SINAIS, SYMPTOM_FEATURES, strict=True):
        features[target] = _three_level(df[source])

    onset = pd.to_datetime(code(df["DT_SIN_PRI"]), format="%Y%m%d", errors="coerce")
    notified = pd.to_datetime(code(df["DT_NOTIFIC"]), format="%Y%m%d", errors="coerce")
    days = (notified - onset).dt.days
    features["dias_ate_notificacao"] = days.clip(lower=0, upper=60).astype("float64")
    return features[FEATURE_COLUMNS]