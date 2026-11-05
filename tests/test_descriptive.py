import pandas as pd
import pytest

from dengue_sinan.descriptive import (
    combination_counts,
    pair_event_counts,
    risk_by_group,
    wilson_interval,
    write_descriptive_reports,
)


def _frame():
    return pd.DataFrame({
        "ANO": [2022] * 5,
        "y": [1, 0, 0, 1, 0],
        "DIABETES": ["1", "1", "2", "1", "2"],
        "HEMATOLOG": ["1", "2", "2", "1", "2"],
        "HEPATOPAT": ["1", "2", "2", "1", "2"],
        "RENAL": ["2"] * 5,
        "HIPERTENSA": ["2"] * 5,
        "ACIDO_PEPT": ["2"] * 5,
        "AUTO_IMUNE": ["2"] * 5,
    })


def test_wilson_interval_matches_hand_calculation():
    estimate, lower, upper = wilson_interval(5, 10)
    assert estimate == 0.5
    assert lower == pytest.approx(0.2366, abs=1e-3)
    assert upper == pytest.approx(0.7634, abs=1e-3)


def test_pair_and_exact_combination_counts():
    frame = _frame()
    pairs = pair_event_counts(frame)
    row = pairs.query("comorbidade_a == 'DIABETES' and comorbidade_b == 'HEMATOLOG'").iloc[0]
    assert row["casos"] == 2
    assert row["eventos"] == 2
    combinations = combination_counts(frame)
    assert combinations.iloc[0]["comorbidades"] == "DIABETES, HEMATOLOG, HEPATOPAT"
    assert combinations.iloc[0]["casos"] == 2


def test_risk_by_group_has_wilson_bounds():
    table = risk_by_group(_frame(), "DIABETES")
    yes = table.set_index("categoria").loc["Sim"]
    assert yes["casos"] == 3
    assert yes["eventos"] == 2
    assert yes["ic_inf"] < yes["risco"] < yes["ic_sup"]


def test_descriptive_reports_are_aggregate_and_suppress_small_cells(tmp_path):
    from test_baselines import _development_frame

    frame = _development_frame()
    write_descriptive_reports(frame, tmp_path)
    for name in (
        "tabela1.md", "riscos_brutos.md", "pares_comorbidades.md",
        "combinacoes_3mais.md", "riscos_brutos.png",
    ):
        assert (tmp_path / name).is_file()
    content = (tmp_path / "riscos_brutos.md").read_text(encoding="utf-8")
    assert "Riscos brutos" in content
    assert "20220110" not in content
