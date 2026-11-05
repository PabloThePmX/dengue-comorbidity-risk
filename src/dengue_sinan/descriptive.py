"""Análise descritiva agregada da população de desenvolvimento."""

from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd

from dengue_sinan.guard import assert_dev_only
from dengue_sinan.profiling import COMORBIDADES, code


def wilson_interval(events: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    """Proporção e intervalo de Wilson de 95% (ou do z informado)."""
    if n < 0 or events < 0 or events > n:
        raise ValueError("exige 0 <= events <= n")
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    proportion = events / n
    denominator = 1 + z**2 / n
    center = (proportion + z**2 / (2 * n)) / denominator
    half_width = z * np.sqrt(proportion * (1 - proportion) / n + z**2 / (4 * n**2))
    return proportion, max(0.0, center - half_width / denominator), min(
        1.0, center + half_width / denominator
    )


def pair_event_counts(frame: pd.DataFrame) -> pd.DataFrame:
    """Contagens de casos e eventos para os 21 pares com ambas as condições presentes."""
    assert_dev_only(frame)
    rows = []
    for first, second in combinations(COMORBIDADES, 2):
        both = _yes(frame[first]) & _yes(frame[second])
        rows.append({
            "comorbidade_a": first,
            "comorbidade_b": second,
            "casos": int(both.sum()),
            "eventos": int(frame.loc[both, "y"].sum()),
        })
    return pd.DataFrame(rows)


def combination_counts(frame: pd.DataFrame) -> pd.DataFrame:
    """Contagens para cada combinação exata observada de três ou mais comorbidades."""
    assert_dev_only(frame)
    selected = pd.DataFrame({column: _yes(frame[column]) for column in COMORBIDADES})
    keys = selected.apply(
        lambda row: tuple(column for column in COMORBIDADES if row[column]), axis=1
    )
    keys = keys[keys.map(len) >= 3]
    grouped = frame.loc[keys.index].assign(_combination=keys).groupby(
        "_combination", observed=True
    )["y"]
    table = grouped.agg(casos="size", eventos="sum").reset_index()
    table["comorbidades"] = table.pop("_combination").map(lambda values: ", ".join(values))
    return table[["comorbidades", "casos", "eventos"]].sort_values(
        ["casos", "comorbidades"], ascending=[False, True], ignore_index=True
    )


def _yes(series: pd.Series) -> pd.Series:
    values = series.astype("string")
    if values.isin({"Sim", "Não", "Ausente"}).any():
        return values.eq("Sim")
    return code(series).eq("1")


def risk_by_group(frame: pd.DataFrame, column: str) -> pd.DataFrame:
    """Risco bruto por categoria, com IC Wilson; preserva contagens para auditoria."""
    assert_dev_only(frame)
    if column in COMORBIDADES:
        category = pd.Series(
            np.select([_yes(frame[column]), code(frame[column]).eq("2")],
                      ["Sim", "Não"], default="Ausente"),
            index=frame.index,
        )
    else:
        category = frame[column].astype("string").fillna("Ausente")
    grouped = frame.groupby(category, observed=True)["y"]
    result = grouped.agg(casos="size", eventos="sum").reset_index(names="categoria")
    intervals = result.apply(
        lambda row: wilson_interval(int(row["eventos"]), int(row["casos"])), axis=1
    )
    result[["risco", "ic_inf", "ic_sup"]] = pd.DataFrame(intervals.tolist(), index=result.index)
    return result


def characteristics_by_outcome(frame: pd.DataFrame) -> pd.DataFrame:
    """Tabela agregada de características por desfecho, sem divulgar valores individuais."""
    assert_dev_only(frame)
    from dengue_sinan.dataset import build_feature_frame

    features = build_feature_frame(frame)
    rows: list[dict] = []
    for outcome, group in frame.groupby("y", observed=True):
        age = pd.to_numeric(group["idade_anos"], errors="coerce").dropna()
        rows.append({
            "desfecho": int(outcome),
            "variavel": "idade_anos",
            "categoria": "mediana (IQR)",
            "n": int(age.size),
            "valor": f"{age.median():.1f} ({age.quantile(.25):.1f}–{age.quantile(.75):.1f})",
        })
        categorical = ["CS_SEXO", "CS_GESTANT", "CS_RACA", *COMORBIDADES]
        for column in categorical:
            values = frame.loc[group.index, column].astype("string").fillna("Ausente")
            for category, count in values.value_counts(dropna=False).items():
                rows.append({
                    "desfecho": int(outcome),
                    "variavel": column,
                    "categoria": str(category),
                    "n": int(count),
                    "valor": "",
                })
        count = features.loc[group.index, "n_comorbidades"]
        for category, size in count.value_counts(dropna=False).items():
            rows.append({
                "desfecho": int(outcome),
                "variavel": "n_comorbidades",
                "categoria": str(category),
                "n": int(size),
                "valor": "",
            })
    return pd.DataFrame(rows)


def _markdown_table(frame: pd.DataFrame, minimum: int) -> str:
    safe = frame.copy()
    suppressed = pd.Series(False, index=safe.index)
    for column in ("casos", "n", "eventos"):
        if column in safe:
            suppressed |= pd.to_numeric(safe[column], errors="coerce") < minimum
    for column in ("risco", "ic_inf", "ic_sup", "valor"):
        if column in safe:
            safe.loc[suppressed, column] = np.nan
    for column in ("casos", "eventos", "n"):
        if column in safe:
            safe[column] = safe[column].map(
                lambda value: (
                    f"<{minimum}"
                    if isinstance(value, int | float | np.integer | np.floating)
                    and pd.notna(value) and value < minimum
                    else value
                )
            )
    headers = [str(column) for column in safe.columns]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    lines.extend("| " + " | ".join(str(value) for value in row) + " |"
                 for row in safe.itertuples(index=False, name=None))
    return "\n".join(lines)


def write_descriptive_reports(
    frame: pd.DataFrame, output_dir: str | Path, minimum: int = 10,
) -> None:
    """Gera tabelas agregadas e gráficos, aplicando supressão antes da publicação."""
    assert_dev_only(frame)
    if "n_comorbidades" not in frame:
        from dengue_sinan.dataset import build_feature_frame

        frame = frame.assign(n_comorbidades=build_feature_frame(frame)["n_comorbidades"])
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    (output / "tabela1.md").write_text(
        "# Características da população\n\n"
        "Valores agregados por desfecho; células com contagem abaixo do limite são suprimidas.\n\n"
        + _markdown_table(characteristics_by_outcome(frame), minimum) + "\n",
        encoding="utf-8",
    )
    risk_tables = [
        risk_by_group(frame, "faixa_etaria").assign(variavel="faixa_etaria"),
        risk_by_group(frame, "n_comorbidades").assign(variavel="n_comorbidades"),
        *(risk_by_group(frame, column).assign(variavel=column) for column in COMORBIDADES),
    ]
    risks = pd.concat(risk_tables, ignore_index=True)
    (output / "riscos_brutos.md").write_text(
        "# Riscos brutos\n\nRiscos descritivos; não substituem o E1.\n\n"
        + _markdown_table(risks, minimum) + "\n",
        encoding="utf-8",
    )
    pairs = pair_event_counts(frame)
    (output / "pares_comorbidades.md").write_text(
        "# Eventos por par de comorbidades\n\n"
        + _markdown_table(pairs, minimum) + "\n",
        encoding="utf-8",
    )
    triples = combination_counts(frame)
    (output / "combinacoes_3mais.md").write_text(
        "# Combinações exatas de três ou mais comorbidades\n\n"
        + _markdown_table(triples, minimum) + "\n",
        encoding="utf-8",
    )

    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(8, 5))
    axis.errorbar(
        risks["categoria"].astype(str) + " (" + risks["variavel"].astype(str) + ")",
        risks["risco"],
        yerr=[risks["risco"] - risks["ic_inf"], risks["ic_sup"] - risks["risco"]],
        fmt="o",
    )
    axis.set_ylabel("Risco bruto de desfecho grave")
    axis.tick_params(axis="x", rotation=45)
    figure.tight_layout()
    figure.savefig(output / "riscos_brutos.png", dpi=150)
    plt.close(figure)
