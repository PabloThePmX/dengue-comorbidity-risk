import pandas as pd
import pytest

from dengue_sinan.descriptive import (
    combination_counts,
    pair_event_counts,
    risk_table,
    run_descriptive,
    suppress_small_cells,
    wilson_ci,
)
from dengue_sinan.profiling import COMORBIDADES, SINAIS, add_derived


def test_wilson_interval_for_half_rate():
    lower, upper = wilson_ci(5, 10)
    assert lower == pytest.approx(0.2366, abs=0.001)
    assert upper == pytest.approx(0.7634, abs=0.001)


def test_suppression_hides_small_cells():
    table = pd.DataFrame({"categoria": ["a", "b"], "casos": [9, 10], "eventos": [0, 1]})
    result = suppress_small_cells(table)
    assert (result.loc[0] == "<10").all()
    assert result.loc[1, "casos"] == 10


def _comorbidity_data():
    data = {name: ["2"] * 20 for name in COMORBIDADES}
    data["ANO"] = [2022] * 20
    data["y"] = [0] * 19 + [1]
    data["DIABETES"] = ["1"] * 12 + ["2"] * 8
    data["RENAL"] = ["1"] * 12 + ["2"] * 8
    data["HEMATOLOG"] = ["1"] * 10 + ["2"] * 10
    data["y"] = [1] + [0] * 19
    return pd.DataFrame(data)


def test_pair_event_counts_has_all_21_pairs_and_uses_dev_data():
    table = pair_event_counts(_comorbidity_data())
    assert len(table) == 21
    pair = table[(table["comorbidade_1"] == "DIABETES") & (table["comorbidade_2"] == "RENAL")]
    assert pair.iloc[0]["casos"] == 12
    assert pair.iloc[0]["eventos"] == 1


def test_combination_counts_groups_exact_combinations():
    table = combination_counts(_comorbidity_data())
    assert table.iloc[0]["casos"] == 10
    assert set(table.columns) == {"comorbidades", "casos", "eventos"}


def test_risk_table_suppresses_cells_below_minimum():
    data = pd.DataFrame({"group": ["small"] * 9 + ["large"] * 11, "y": [1] * 20})
    table = risk_table(data, "group")
    small = table[table["group"] == "<10"]
    assert small.iloc[0]["eventos"] == "<10"


def test_run_descriptive_writes_aggregates_and_private_combination_counts(tmp_path):
    rows = 30
    data = {name: ["2"] * rows for name in COMORBIDADES + SINAIS}
    data.update(
        {
            "ANO": [2022] * rows,
            "CLASSI_FIN": ["12" if i < 12 else "10" for i in range(rows)],
            "EVOLUCAO": ["1"] * rows,
            "NU_IDADE_N": [f"4{10 + i:03d}" for i in range(rows)],
            "ANO_NASC": ["2000"] * rows,
            "DT_SIN_PRI": ["20220101"] * rows,
            "DT_NOTIFIC": ["20220102"] * rows,
            "CS_SEXO": ["F" if i % 2 else "M" for i in range(rows)],
            "CS_GESTANT": ["5"] * rows,
            "CS_RACA": ["1"] * rows,
            "ID_MN_RESI": ["355030"] * rows,
            "SG_UF": ["35"] * rows,
        }
    )
    df = add_derived(pd.DataFrame(data))
    reports = tmp_path / "reports"
    mlruns = tmp_path / "mlruns"

    tables = run_descriptive(
        df,
        {
            "supressao_min_celula": 10,
            "caminhos": {"relatorios": str(reports), "mlruns": str(mlruns)},
        },
    )

    assert len(tables["pares"]) == 21
    assert (reports / "descritiva" / "tabela1.md").exists()
    assert (reports / "descritiva" / "riscos_brutos.md").exists()
    assert (reports / "descritiva" / "risco_por_faixa_etaria.png").exists()
    assert (reports / "descritiva" / "pares_comorbidades.md").exists()
    assert (mlruns / "descritiva" / "combinacoes_3mais.parquet").exists()