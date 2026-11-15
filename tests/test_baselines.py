import pandas as pd
import pytest

from dengue_sinan.baselines import rule_b2, run_baselines
from dengue_sinan.profiling import COMORBIDADES, SINAIS, add_derived


def _profile(rows=5):
    data = {
        "idade_anos": [30, 1, 66, 30, 30][:rows],
        "gestante": [False, False, False, True, False][:rows],
        "laco": ["2"] * rows,
        "petequia_n": ["2"] * rows,
        "diabetes": ["Não"] * rows,
        "hematolog": ["Não"] * rows,
        "hepatopat": ["Não"] * rows,
        "renal": ["Não"] * rows,
        "hipertensa": ["Não"] * rows,
        "acido_pept": ["Não"] * rows,
        "auto_imune": ["Não"] * rows,
    }
    return pd.DataFrame(data)


def test_rule_b2_matches_protocol_conditions():
    df = _profile()
    df.loc[4, "diabetes"] = "Sim"
    assert rule_b2(df).tolist() == [False, True, True, True, True]


def test_rule_b2_recognizes_laco_and_petequia_n():
    df = _profile()
    df.loc[0, "laco"] = "Sim"
    df.loc[1, "petequia_n"] = "1"
    assert rule_b2(df).tolist() == [True, True, True, True, False]


def test_rule_b2_requires_explicit_age_and_features():
    with pytest.raises(ValueError, match="idade_anos"):
        rule_b2(pd.DataFrame({"gestante": [False]}))


def test_run_baselines_returns_one_oof_prediction_per_development_row():
    regions = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]
    rows = 200
    data = {name: ["2"] * rows for name in COMORBIDADES + SINAIS}
    for column in COMORBIDADES:
        data[column] = ["1" if (index // 5) % 2 else "2" for index in range(rows)]
    data.update(
        {
            "ANO": [2022] * rows,
            "regiao": [regions[index // 40] for index in range(rows)],
            "CLASSI_FIN": ["12" if index % 5 == 0 else "10" for index in range(rows)],
            "EVOLUCAO": ["1"] * rows,
            "NU_IDADE_N": [f"4{5 + index % 80:03d}" for index in range(rows)],
            "ANO_NASC": ["2000"] * rows,
            "DT_SIN_PRI": ["20220101"] * rows,
            "DT_NOTIFIC": ["20220102"] * rows,
            "CS_SEXO": ["M" if index % 2 else "F" for index in range(rows)],
            "CS_GESTANT": ["1" if index % 11 == 0 else "5" for index in range(rows)],
            "CS_RACA": ["1"] * rows,
            "ID_MN_RESI": [
                ["110020", "230440", "530010", "355030", "431490"][index // 40]
                for index in range(rows)
            ],
            "SG_UF": [
                ["11", "23", "53", "35", "43"][index // 40] for index in range(rows)
            ],
        }
    )
    df = add_derived(pd.DataFrame(data))

    metrics, oof = run_baselines(df)

    assert len(oof) == rows
    assert oof["b0"].notna().all()
    assert oof["b1"].between(0, 1).all()
    assert set(metrics["modelo"]) == {"B0", "B1", "B2"}