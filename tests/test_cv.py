"""Testes unitários do laço de validação LORO com early stopping (T-4.2)."""

from pathlib import Path

import numpy as np
import pandas as pd

from dengue_sinan.baselines import run_baselines
from dengue_sinan.cv import correct_subsampled_prob, run_loro
from dengue_sinan.dataset import COMORBIDADES, SINAIS
from dengue_sinan.folds import DEFAULT_FOLD_ORDER


def _make_dev_df(n_per_region: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(20261103)
    regioes = np.repeat(DEFAULT_FOLD_ORDER, n_per_region)
    n = len(regioes)

    idade = rng.uniform(5, 85, size=n)
    diab = rng.choice(["Não", "Sim"], size=n, p=[0.7, 0.3])
    hipert = rng.choice(["Não", "Sim"], size=n, p=[0.6, 0.4])
    logit = -2.5 + 0.03 * (idade - 40) + 1.6 * (diab == "Sim") + 1.2 * (hipert == "Sim")
    prob = 1.0 / (1.0 + np.exp(-logit))
    y = rng.binomial(1, prob).astype("int8")

    data: dict[str, object] = {
        "ANO": np.full(n, 2022),
        "regiao": regioes,
        "idade_anos": idade,
        "sexo": pd.Categorical(rng.choice(["F", "M"], size=n), categories=["F", "M", "I"]),
        "gestante": np.zeros(n, dtype="int8"),
        "dias_ate_notificacao": rng.uniform(0, 10, size=n),
        "y": y,
    }
    for c in COMORBIDADES:
        vals = diab if c == "DIABETES" else (hipert if c == "HIPERTENSA" else ["Não"] * n)
        data[c] = pd.Categorical(vals, categories=["Não", "Sim", "Ausente"])
    for s in SINAIS:
        vals = rng.choice(["Não", "Sim"], size=n, p=[0.8, 0.2])
        data[s] = pd.Categorical(vals, categories=["Não", "Sim", "Ausente"])

    df = pd.DataFrame(data)
    df["n_comorbidades"] = (
        df[COMORBIDADES].apply(lambda r: sum(v == "Sim" for v in r), axis=1).astype("int8")
    )
    return df


def test_run_loro_reproduces_b1_from_t2_8(tmp_path: Path) -> None:
    df = _make_dev_df(80)
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
    base_res = run_baselines(cfg, df)
    loro_res = run_loro(cfg, "b1", {}, df)

    assert np.allclose(loro_res["oof_p"], base_res["b1"]["oof_p"])
    assert np.isclose(loro_res["pr_auc_oof"], base_res["b1"]["pr_auc_oof"])
    for reg in DEFAULT_FOLD_ORDER:
        assert np.isclose(
            loro_res["pr_auc_por_dobra"][reg],
            base_res["b1"]["pr_auc_por_dobra"][reg],
        )


def test_run_loro_with_xgboost_and_mlp_early_stopping() -> None:
    df = _make_dev_df(60)
    cfg = {"seed": 20261103, "ordem_dobras": DEFAULT_FOLD_ORDER}

    res_xgb = run_loro(
        cfg,
        "xgboost",
        {"n_estimators": 25, "max_depth": 3, "early_stopping_rounds": 5, "n_jobs": 1},
        df,
    )
    assert len(res_xgb["oof_p"]) == len(df)
    assert not np.isnan(res_xgb["oof_p"]).any()
    assert set(res_xgb["melhores_pontos"].keys()) == set(DEFAULT_FOLD_ORDER)
    assert all(1 <= pt <= 25 for pt in res_xgb["melhores_pontos"].values())

    res_mlp = run_loro(
        cfg,
        "mlp",
        {
            "hidden_layers": (16,),
            "max_epochs": 12,
            "patience": 3,
            "batch_size": 64,
            "device": "cpu",
        },
        df,
    )
    assert len(res_mlp["oof_p"]) == len(df)
    assert all(1 <= pt <= 12 for pt in res_mlp["melhores_pontos"].values())


def test_correct_subsampled_prob() -> None:
    p = np.array([0.0, 0.2, 0.5, 1.0])
    corrected = correct_subsampled_prob(p, 0.5)
    assert corrected[0] == 0.0
    assert corrected[-1] == 1.0
    assert np.all(corrected[1:3] < p[1:3])
