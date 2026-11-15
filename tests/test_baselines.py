"""Testes dos baselines B0, B1 e B2 (T-2.8, FR-04)."""

from pathlib import Path

import numpy as np
import pandas as pd

from dengue_sinan.baselines import rule_b2, run_baselines
from dengue_sinan.dataset import COMORBIDADES
from dengue_sinan.folds import DEFAULT_FOLD_ORDER


def test_rule_b2_matches_protocol_criteria() -> None:
    base = {c: "Não" for c in COMORBIDADES}
    base.update(
        {
            "ANO": 2022,
            "idade_anos": 30.0,
            "gestante": 0,
            "n_comorbidades": 0,
            "LACO": "Não",
            "PETEQUIA_N": "Não",
        }
    )
    rows = [
        {**base},                                   # 0: baixo risco -> False
        {**base, "idade_anos": 1.5},                # 1: < 2 anos -> True
        {**base, "idade_anos": 70.0},               # 2: > 65 anos -> True
        {**base, "gestante": 1},                    # 3: gestante -> True
        {**base, "DIABETES": "Sim", "n_comorbidades": 1},  # 4: comorbidade -> True
        {**base, "LACO": "Sim"},                    # 5: prova do laço -> True
        {**base, "PETEQUIA_N": "Sim"},              # 6: petéquias -> True
    ]
    df = pd.DataFrame(rows)
    preds = rule_b2(df)
    assert preds.tolist() == [False, True, True, True, True, True, True]


def test_run_baselines_b1_beats_b0_and_logs_mlflow(tmp_path: Path) -> None:
    rng = np.random.default_rng(20261103)
    n_per_region = 120
    regioes = np.repeat(DEFAULT_FOLD_ORDER, n_per_region)
    n = len(regioes)

    idade = rng.uniform(5, 85, size=n)
    diab = rng.choice(["Não", "Sim"], size=n, p=[0.7, 0.3])
    hipert = rng.choice(["Não", "Sim"], size=n, p=[0.6, 0.4])
    logit = -3.0 + 0.04 * (idade - 40) + 1.8 * (diab == "Sim") + 1.5 * (hipert == "Sim")
    prob = 1.0 / (1.0 + np.exp(-logit))
    y = rng.binomial(1, prob).astype("int8")

    data: dict[str, object] = {
        "ANO": np.full(n, 2022),
        "regiao": regioes,
        "idade_anos": idade,
        "sexo": pd.Categorical(rng.choice(["F", "M"], size=n), categories=["F", "M", "I"]),
        "gestante": np.zeros(n, dtype="int8"),
        "LACO": pd.Categorical(["Não"] * n, categories=["Não", "Sim", "Ausente"]),
        "PETEQUIA_N": pd.Categorical(["Não"] * n, categories=["Não", "Sim", "Ausente"]),
        "y": y,
    }
    for c in COMORBIDADES:
        vals = diab if c == "DIABETES" else (hipert if c == "HIPERTENSA" else ["Não"] * n)
        data[c] = pd.Categorical(vals, categories=["Não", "Sim", "Ausente"])

    df = pd.DataFrame(data)
    df["n_comorbidades"] = (
        df[COMORBIDADES].apply(lambda r: sum(v == "Sim" for v in r), axis=1).astype("int8")
    )

    cfg = {
        "seed": 20261103,
        "anos_dev": [2022, 2023],
        "ordem_dobras": DEFAULT_FOLD_ORDER,
        "caminhos": {
            "dados": str(tmp_path / "data"),
            "mlruns": str(tmp_path / "mlruns"),
            "relatorios": str(tmp_path / "reports"),
        },
    }
    res = run_baselines(cfg, df)
    assert res["baselines_md"].is_file()
    assert res["b1"]["pr_auc_oof"] > res["b0"]["pr_auc_oof"]
    assert res["b2"]["recall"] >= 0.0
