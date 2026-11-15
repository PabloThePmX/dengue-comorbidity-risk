"""Testes da análise descritiva, IC de Wilson, supressão R7 e contagem de pares (T-2.6, T-2.7)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dengue_sinan.dataset import COMORBIDADES
from dengue_sinan.descriptive import (
    DISCLAIMER_HEADER,
    combination_counts,
    generate_descriptive_reports,
    pair_event_counts,
    suppress_small_cells,
    wilson_ci,
)


def test_wilson_ci_bounds_and_center() -> None:
    p, lo, hi = wilson_ci(10, 100)
    assert p == pytest.approx(0.10)
    assert 0.05 < lo < 0.10 < hi < 0.18

    p0, lo0, hi0 = wilson_ci(0, 100)
    assert p0 == 0.0
    assert lo0 == pytest.approx(0.0)
    assert hi0 > 0.0


def test_suppress_small_cells_masks_counts_below_10() -> None:
    df = pd.DataFrame(
        {
            "perfil": ["A", "B"],
            "casos": [50, 8],
            "eventos": [12, 2],
            "risco_pct": [24.0, 25.0],
        }
    )
    sup = suppress_small_cells(
        df,
        count_cols=["casos", "eventos"],
        min_cell=10,
        mask_cols=["risco_pct"],
    )
    assert sup.loc[0, "casos"] == 50
    assert sup.loc[0, "risco_pct"] == 24.0
    assert sup.loc[1, "casos"] == "<10"
    assert sup.loc[1, "eventos"] == "<10"
    assert sup.loc[1, "risco_pct"] == "<10"


def test_pair_and_combination_counts_and_descriptive_reports(tmp_path: Path) -> None:
    rng = np.random.default_rng(20261103)
    n = 120
    data: dict[str, object] = {
        "ANO": np.full(n, 2022),
        "idade_anos": rng.uniform(10, 80, size=n),
        "faixa_etaria": pd.Categorical(["40–59"] * n),
        "sexo": pd.Categorical(["F"] * 60 + ["M"] * 60, categories=["F", "M", "I"]),
        "gestante": np.zeros(n, dtype="int8"),
        "CS_RACA": ["1"] * n,
        "regiao": ["Sudeste"] * n,
        "y": np.array([1] * 20 + [0] * 100, dtype="int8"),
    }
    for c in COMORBIDADES:
        data[c] = pd.Categorical(["Não"] * n, categories=["Não", "Sim", "Ausente"])

    df = pd.DataFrame(data)
    # Primeiras 15 linhas têm DIABETES + HIPERTENSA + RENAL = Sim (12 com y=1)
    for col in ("DIABETES", "HIPERTENSA", "RENAL"):
        s = df[col].astype("object")
        s.iloc[:15] = "Sim"
        df[col] = pd.Categorical(s, categories=["Não", "Sim", "Ausente"])
    df["n_comorbidades"] = (
        df[COMORBIDADES].apply(lambda r: sum(v == "Sim" for v in r), axis=1).astype("int8")
    )

    pairs = pair_event_counts(df)
    assert len(pairs) == 21
    dh = pairs[(pairs["comorbidade_a"] == "DIABETES") & (pairs["comorbidade_b"] == "HIPERTENSA")]
    assert int(dh["casos"].iloc[0]) == 15
    assert int(dh["eventos"].iloc[0]) == 15

    combos = combination_counts(df)
    assert len(combos) == 1
    assert combos.loc[0, "combinacao"] == "DIABETES + RENAL + HIPERTENSA"
    assert int(combos.loc[0, "casos"]) == 15

    cfg = {
        "supressao_min_celula": 10,
        "caminhos": {"relatorios": str(tmp_path / "reports")},
    }
    res = generate_descriptive_reports(cfg, df)
    assert res["tabela1_path"].is_file()
    assert res["riscos_path"].is_file()
    assert (tmp_path / "reports" / "descritiva" / "risco_comorbidades.png").is_file()
    assert DISCLAIMER_HEADER in res["tabela1_path"].read_text(encoding="utf-8")
    assert DISCLAIMER_HEADER in res["riscos_path"].read_text(encoding="utf-8")
