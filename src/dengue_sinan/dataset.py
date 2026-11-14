"""Carregamento da população SINAN em memória e montagem do frame de features (T-2.1)."""

from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow.parquet as pq

from dengue_sinan import profiling
from dengue_sinan.checks import REQUIRED_COLUMNS, check_year
from dengue_sinan.config import DEFAULT_EXPECTED_PATH, load_expected
from dengue_sinan.guard import assert_dev_only, assert_dev_years
from dengue_sinan.verify import check, write_report

COMORBIDADES = profiling.COMORBIDADES
SINAIS = profiling.SINAIS
THREE_LEVEL_COLS = [*COMORBIDADES, *SINAIS]
METADATA_COLS = ("ANO", "y", "regiao", "faixa_etaria", "CS_RACA", "idade_de_ano_nasc")


def _write_exclusion_flowchart(
    raw_by_year: pd.DataFrame,
    cfg: dict[str, Any],
) -> pd.DataFrame:
    """Gera e salva `reports/fluxograma.md` com `exclusion_flow` e `exclusion_reasons` (FR-02)."""
    flow = profiling.exclusion_flow(raw_by_year, year="ANO")
    reasons = profiling.exclusion_reasons(raw_by_year, year="ANO")

    reports_dir = Path(cfg.get("caminhos", {}).get("relatorios", "reports"))
    reports_dir.mkdir(parents=True, exist_ok=True)
    flow_path = reports_dir / "fluxograma.md"

    sections = [
        "# Fluxograma de exclusão (FR-02)",
        "",
        "Contagem de registros após cada filtro de população, por ano do arquivo.",
        "",
        profiling.markdown_table(flow, decimals=0),
        "",
        "## Motivos de exclusão",
    ]
    for title, table in reasons.items():
        sections.extend(["", f"### {title}", "", profiling.markdown_table(table, decimals=0)])

    flow_path.write_text("\n".join(sections) + "\n", encoding="utf-8")
    return flow


def load_population(
    cfg: dict[str, Any],
    anos: list[int],
    *,
    return_flow: bool = False,
) -> pd.DataFrame | tuple[pd.DataFrame, pd.DataFrame]:
    """Lê apenas as colunas necessárias dos Parquets dos anos pedidos e filtra a população (T-2.1).

    Recebe `anos` explicitamente (sem default que inclua 2024 — R1).
    Executa os checks bloqueantes de qualidade (FR-03) antes do filtro de população e
    grava `reports/fluxograma.md` (FR-02).
    """
    if not isinstance(anos, list) or not anos:
        raise ValueError("A lista 'anos' deve ser informada explicitamente e não pode ser vazia.")

    data_dir = Path(cfg["caminhos"]["dados"])
    yearly_frames: list[pd.DataFrame] = []

    for ano in anos:
        parquet_path = data_dir / "parquet" / f"dengue_{ano}.parquet"
        if not parquet_path.is_file():
            raise FileNotFoundError(f"Arquivo Parquet não encontrado: {parquet_path}")

        schema_names = set(pq.ParquetFile(parquet_path).schema.names)
        missing = sorted(set(REQUIRED_COLUMNS) - schema_names)
        if missing:
            raise ValueError(
                f"Ano {ano}: colunas obrigatórias ausentes: {', '.join(missing)}"
            )

        table = pq.read_table(parquet_path, columns=list(REQUIRED_COLUMNS))
        df_year = table.to_pandas(strings_to_categorical=True)
        check_year(df_year, ano)
        df_year["ANO"] = int(ano)
        yearly_frames.append(df_year)

    raw_all = pd.concat(yearly_frames, ignore_index=True)
    flow = _write_exclusion_flowchart(raw_all, cfg)

    mask = profiling.population_mask(raw_all)
    pop = profiling.add_derived(raw_all.loc[mask]).reset_index(drop=True)

    if return_flow:
        return pop, flow
    return pop


def load_dev_population(
    cfg: dict[str, Any],
    anos: list[int] | None = None,
) -> pd.DataFrame:
    """Carrega a população para funções de treino/desenvolvimento bloqueando 2024 (R1, T-2.2)."""
    target_years = list(anos) if anos is not None else list(cfg.get("anos_dev", [2022, 2023]))
    ano_teste = int(cfg.get("ano_teste", 2024))
    assert_dev_years(target_years, ano_teste=ano_teste)
    pop = load_population(cfg, target_years)
    assert isinstance(pop, pd.DataFrame)
    assert_dev_only(pop, ano_teste=ano_teste)
    return pop


def _map_three_levels(series: pd.Series) -> pd.Series:
    """Converte código SINAN ('1'=Sim, '2'=Não, resto/branco='Ausente') em categórica."""
    cleaned = profiling.code(series)
    mapped = cleaned.map({"1": "Sim", "2": "Não"}).fillna("Ausente")
    return pd.Series(
        pd.Categorical(mapped, categories=["Não", "Sim", "Ausente"]),
        index=series.index,
    )


def build_feature_frame(df: pd.DataFrame, max_days: int = 60) -> pd.DataFrame:
    """Monta o DataFrame com a lista fechada de features da §1.3 (R4) + metadados de dobra."""
    if "ANO" in df.columns:
        assert_dev_only(df)

    if "idade_anos" not in df.columns or "gestante" not in df.columns:
        df = profiling.add_derived(df)

    out = pd.DataFrame(index=df.index)
    out["idade_anos"] = pd.to_numeric(df["idade_anos"], errors="coerce").astype("float64")

    sexo_raw = profiling.code(df["CS_SEXO"])
    sexo_clean = sexo_raw.where(sexo_raw.isin({"M", "F"}), "I")
    out["sexo"] = pd.Series(
        pd.Categorical(sexo_clean, categories=["F", "M", "I"]),
        index=df.index,
    )

    out["gestante"] = df["gestante"].astype("bool").astype("int8")

    for col in THREE_LEVEL_COLS:
        out[col] = _map_three_levels(df[col])

    comorb_sim = pd.DataFrame({c: out[c].eq("Sim") for c in COMORBIDADES}, index=df.index)
    out["n_comorbidades"] = comorb_sim.sum(axis=1).astype("int8")

    onset = profiling.parse_date(df["DT_SIN_PRI"])
    notified = profiling.parse_date(df["DT_NOTIFIC"])
    delay = (notified - onset).dt.days.astype("float64")
    out["dias_ate_notificacao"] = delay.clip(lower=0.0, upper=float(max_days))

    for meta_col in METADATA_COLS:
        if meta_col in df.columns:
            out[meta_col] = df[meta_col]

    return out


def verify_t2_1(
    cfg: dict[str, Any],
    *,
    expected_path: str | Path = DEFAULT_EXPECTED_PATH,
    out_dir: str | Path | None = None,
) -> Path:
    """Executa a verificação da T-2.1 contra `config/esperado.yaml` e grava `T-2.1.json` (D-56)."""
    esperado = load_expected(expected_path)
    anos_dev = [int(a) for a in cfg.get("anos_dev", [2022, 2023])]
    assert_dev_years(anos_dev, ano_teste=int(cfg.get("ano_teste", 2024)))

    res = load_population(cfg, anos_dev, return_flow=True)
    assert isinstance(res, tuple)
    pop, flow = res

    checks = [
        check("casos_dev", esperado["casos_dev"], int(len(pop))),
        check("eventos_dev", esperado["eventos_dev"], int(pop["y"].sum())),
    ]

    for ano in anos_dev:
        pop_ano = pop[pop["ANO"] == ano]
        exp_pop = esperado["populacao_por_ano"][ano]
        exp_ev = esperado["eventos_por_ano"][ano]
        checks.append(check(f"populacao_{ano}", exp_pop, int(len(pop_ano))))
        checks.append(check(f"eventos_{ano}", exp_ev, int(pop_ano["y"].sum())))

        flow_esp = esperado["fluxograma_exclusao"][ano]
        for step_label, exp_step_count in flow_esp.items():
            obt_step_count = int(flow.loc[step_label, ano])
            checks.append(check(f"fluxo_{ano}_{step_label}", exp_step_count, obt_step_count))

    dest_dir = (
        Path(out_dir)
        if out_dir is not None
        else Path(cfg.get("caminhos", {}).get("relatorios", "reports")) / "verificacao"
    )
    return write_report("T-2.1", checks, dest_dir, cfg)
