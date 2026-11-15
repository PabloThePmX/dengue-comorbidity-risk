"""Análise descritiva agregada da coorte de desenvolvimento."""

import itertools
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd
from scipy.stats import norm

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from dengue_sinan.config import load_config
from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.profiling import COMORBIDADES, code
from dengue_sinan.reporting import markdown_table


def wilson_ci(events: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Intervalo de Wilson bilateral para uma proporção."""
    if n <= 0 or not 0 <= events <= n or not 0 < alpha < 1:
        raise ValueError("Exige 0 <= events <= n, n positivo e alpha entre 0 e 1.")
    z = norm.ppf(1 - alpha / 2)
    proportion = events / n
    denominator = 1 + z**2 / n
    center = (proportion + z**2 / (2 * n)) / denominator
    half_width = (
        z * np.sqrt(proportion * (1 - proportion) / n + z**2 / (4 * n**2)) / denominator
    )
    return float(max(0, center - half_width)), float(min(1, center + half_width))


def suppress_small_cells(table: pd.DataFrame, min_cases: int = 10) -> pd.DataFrame:
    """Suprime a linha publicada quando o número de casos da célula é menor que o mínimo."""
    if "casos" not in table:
        raise ValueError("Tabela deve conter a coluna casos para aplicar supressão.")
    output = table.astype(object).copy()
    suppressed = output["casos"] < min_cases
    output.loc[suppressed, :] = "<10"
    return output


def risk_table(df: pd.DataFrame, column: str, min_cases: int = 10) -> pd.DataFrame:
    """Risco bruto por categoria com IC de Wilson e supressão de células pequenas."""
    grouped = df.groupby(column, dropna=False, observed=True)["y"]
    table = grouped.agg(casos="size", eventos="sum").reset_index()
    table["risco"] = table["eventos"] / table["casos"]
    intervals = [wilson_ci(int(row.eventos), int(row.casos)) for row in table.itertuples()]
    table["ic_inferior"] = [interval[0] for interval in intervals]
    table["ic_superior"] = [interval[1] for interval in intervals]
    return suppress_small_cells(table, min_cases)


def _yes_matrix(df: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        {name: code(df[name]).eq("1") | df[name].eq("Sim") for name in COMORBIDADES},
        index=df.index,
    )


def pair_event_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Contagem de casos/eventos em que ambas as comorbidades de cada par estão presentes."""
    assert_dev_only(df)
    yes = _yes_matrix(df)
    rows = []
    for first, second in itertools.combinations(COMORBIDADES, 2):
        selected = yes[first] & yes[second]
        rows.append(
            {
                "comorbidade_1": first,
                "comorbidade_2": second,
                "casos": int(selected.sum()),
                "eventos": int(df.loc[selected, "y"].sum()),
            }
        )
    return pd.DataFrame(rows)


def combination_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Contagem por combinação exata observada de três ou mais comorbidades."""
    assert_dev_only(df)
    yes = _yes_matrix(df).to_numpy(dtype=np.uint8)
    bit_weights = 1 << np.arange(len(COMORBIDADES), dtype=np.uint8)
    masks = yes @ bit_weights
    grouped = pd.DataFrame({"mask": masks, "y": df["y"].to_numpy()}).groupby("mask")["y"]
    counts = grouped.agg(casos="size", eventos="sum")
    rows = []
    for mask, row in counts.iterrows():
        diseases = [
            disease
            for bit, disease in enumerate(COMORBIDADES)
            if mask & (1 << bit)
        ]
        if len(diseases) >= 3:
            rows.append(
                {
                    "comorbidades": " + ".join(diseases),
                    "casos": int(row["casos"]),
                    "eventos": int(row["eventos"]),
                }
            )
    return pd.DataFrame(rows, columns=["comorbidades", "casos", "eventos"])


def _table1(df: pd.DataFrame, min_cases: int) -> pd.DataFrame:
    rows = []
    descriptive = df.copy()
    descriptive["faixa_etaria"] = descriptive["faixa_etaria"].astype("string").fillna("Ausente")
    descriptive["n_comorbidades_grupo"] = pd.cut(
        descriptive["n_comorbidades"],
        [-1, 0, 1, 2, 7],
        labels=["0", "1", "2", "3+"],
    ).astype("string")
    columns = [
        "faixa_etaria",
        "CS_SEXO",
        "CS_GESTANT",
        "CS_RACA",
        "n_comorbidades_grupo",
        *COMORBIDADES,
    ]
    for outcome, outcome_df in descriptive.groupby("y", observed=True):
        for column in columns:
            values = code(outcome_df[column]).fillna("Ausente")
            for category, count in values.value_counts(dropna=False).items():
                if count < min_cases:
                    continue
                rows.append(
                    {
                        "desfecho": int(outcome),
                        "variavel": column,
                        "categoria": category,
                        "n": int(count),
                        "percentual": float(100 * count / len(outcome_df)),
                    }
                )
        age = outcome_df["idade_anos"].dropna()
        if len(age) >= min_cases:
            q1, median, q3 = age.quantile([0.25, 0.5, 0.75])
            rows.append(
                {
                    "desfecho": int(outcome),
                    "variavel": "idade_anos",
                    "categoria": "mediana (IQR)",
                    "n": len(age),
                    "percentual": f"{median:.1f} ({q1:.1f}–{q3:.1f})",
                }
            )
    return pd.DataFrame(rows)


def _write_markdown(table: pd.DataFrame, path: Path, title: str) -> None:
    path.write_text(
        f"# {title}\n\nRiscos brutos, descritivos; não substituem o E1.\n\n"
        + markdown_table(table)
        + "\n",
        encoding="utf-8",
    )


def run_descriptive(df: pd.DataFrame, cfg: dict | str | Path) -> dict[str, pd.DataFrame]:
    """Gera tabelas e figuras descritivas apenas com a coorte 2022–2023."""
    assert_dev_only(df)
    config = load_config(cfg) if isinstance(cfg, (str, Path)) else cfg
    minimum = int(config["supressao_min_celula"])
    output = Path(config["caminhos"]["relatorios"]) / "descritiva"
    output.mkdir(parents=True, exist_ok=True)

    analysis_df = df.copy()
    analysis_df["n_comorbidades"] = build_feature_frame(df)["n_comorbidades"]
    table1 = _table1(analysis_df, minimum)
    _write_markdown(table1, output / "tabela1.md", "Características por desfecho")

    risk_tables = {}
    presence = _yes_matrix(df)
    for name in COMORBIDADES:
        risk_tables[name] = risk_table(
            df.assign(_presente=presence[name].map({True: "Sim", False: "Não"})),
            "_presente",
            minimum,
        )
    risk_tables["n_comorbidades"] = risk_table(analysis_df, "n_comorbidades", minimum)
    risk_tables["faixa_etaria"] = risk_table(analysis_df, "faixa_etaria", minimum)
    risks = pd.concat(
        [table.assign(variavel=name) for name, table in risk_tables.items()],
        ignore_index=True,
    )
    _write_markdown(risks, output / "riscos_brutos.md", "Riscos brutos por perfil")

    fig, axis = plt.subplots(figsize=(8, 5))
    age_risks = risk_table(analysis_df, "faixa_etaria", minimum)
    visible = age_risks[age_risks["casos"] != "<10"]
    axis.bar(visible["faixa_etaria"].astype(str), visible["risco"].astype(float))
    axis.set_ylabel("Risco bruto")
    axis.set_xlabel("Faixa etária")
    fig.tight_layout()
    fig.savefig(output / "risco_por_faixa_etaria.png", dpi=150)
    plt.close(fig)

    pairs = pair_event_counts(df)
    combinations = combination_counts(df)
    pair_publication = pairs.assign(
        casos_publicados=pairs["casos"].map(lambda n: str(n) if n >= minimum else "<10"),
        eventos_publicados=pairs["eventos"].map(lambda n: str(n) if n >= minimum else "<10"),
    )[["comorbidade_1", "comorbidade_2", "casos_publicados", "eventos_publicados"]]
    (output / "pares_comorbidades.md").write_text(
        markdown_table(pair_publication), encoding="utf-8"
    )
    internal_dir = Path(config["caminhos"]["mlruns"]) / "descritiva"
    internal_dir.mkdir(parents=True, exist_ok=True)
    combinations.to_parquet(internal_dir / "combinacoes_3mais.parquet", index=False)
    return {"tabela1": table1, "riscos": risks, "pares": pairs, "combinacoes": combinations}