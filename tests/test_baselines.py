import numpy as np
import pandas as pd

from dengue_sinan.baselines import rule_b2, run_baselines_loro
from dengue_sinan.checks import REQUIRED_COLUMNS
from dengue_sinan.profiling import add_derived

_REGION_CODES = ["110020", "230440", "355030", "431490", "530010"]


def _development_frame():
    rows = []
    for region_index, ibge in enumerate(_REGION_CODES):
        positive_indices = set(np.random.default_rng(2022 + region_index).choice(
            40, size=4, replace=False
        ))
        for index in range(40):
            positive = index in positive_indices
            row = {column: "2" for column in REQUIRED_COLUMNS}
            row.update({
                "ANO": 2022,
                "CLASSI_FIN": "12" if positive else "10",
                "EVOLUCAO": "1",
                "NU_IDADE_N": f"40{20 + index:02d}",
                "ANO_NASC": "1980",
                "DT_SIN_PRI": "20220110",
                "DT_NOTIFIC": "20220112",
                "CS_SEXO": "F" if index % 2 else "M",
                "CS_GESTANT": "6",
                "CS_RACA": "1",
                "ID_MN_RESI": ibge,
                "SG_UF": ibge[:2],
                "DIABETES": "1" if index % 3 == 0 else "2",
                "HEMATOLOG": "2",
                "HEPATOPAT": "2",
                "RENAL": "2",
                "HIPERTENSA": "2",
                "ACIDO_PEPT": "2",
                "AUTO_IMUNE": "2",
                "LACO": "1" if index % 5 == 0 else "2",
                "PETEQUIA_N": "2",
            })
            rows.append(row)
    return add_derived(pd.DataFrame(rows))


def test_b2_rule_uses_age_comorbidity_and_signs():
    frame = pd.DataFrame({
        "idade_anos": [1, 30, 30],
        "gestante": [False, False, False],
        "DIABETES": ["2", "1", "2"],
        "HEMATOLOG": ["2"] * 3,
        "HEPATOPAT": ["2"] * 3,
        "RENAL": ["2"] * 3,
        "HIPERTENSA": ["2"] * 3,
        "ACIDO_PEPT": ["2"] * 3,
        "AUTO_IMUNE": ["2"] * 3,
        "LACO": ["2", "2", "1"],
        "PETEQUIA_N": ["2"] * 3,
    })
    assert rule_b2(frame).tolist() == [True, True, True]


def test_baselines_produce_one_oof_prediction_per_development_row():
    frame = _development_frame()
    result = run_baselines_loro(frame)
    assert len(result["oof"]["B0"]) == len(frame)
    assert np.isfinite(result["oof"]["B1"]).all()
    assert len(result["fold_metrics"]["B1"]) == 5
    assert set(result["b2"]) == {"acuracia", "precisao", "recall", "f1", "f2"}
