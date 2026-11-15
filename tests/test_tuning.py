"""Testes unitários da busca retomável com Optuna (T-4.3)."""

from pathlib import Path

import numpy as np
import pandas as pd

from dengue_sinan.dataset import COMORBIDADES, SINAIS
from dengue_sinan.folds import DEFAULT_FOLD_ORDER
from dengue_sinan.tuning import stratified_fold_subsample, tune


def _make_dev_df(n_per_region: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(20261103)
    regioes = np.repeat(DEFAULT_FOLD_ORDER, n_per_region)
    n = len(regioes)

    idade = rng.uniform(5, 85, size=n)
    diab = rng.choice(["Não", "Sim"], size=n, p=[0.7, 0.3])
    logit = -2.2 + 0.03 * (idade - 40) + 1.5 * (diab == "Sim")
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
        vals = diab if c == "DIABETES" else ["Não"] * n
        data[c] = pd.Categorical(vals, categories=["Não", "Sim", "Ausente"])
    for s in SINAIS:
        data[s] = pd.Categorical(["Não"] * n, categories=["Não", "Sim", "Ausente"])

    df = pd.DataFrame(data)
    df["n_comorbidades"] = (
        df[COMORBIDADES].apply(lambda r: sum(v == "Sim" for v in r), axis=1).astype("int8")
    )
    return df


def test_tune_resumes_from_sqlite_without_losing_trials(tmp_path: Path) -> None:
    df = _make_dev_df(50)
    cfg = {
        "seed": 20261103,
        "anos_dev": [2022, 2023],
        "ordem_dobras": DEFAULT_FOLD_ORDER,
        "modo_teste_rapido": True,
        "caminhos": {
            "dados": str(tmp_path / "data"),
            "mlruns": str(tmp_path / "mlruns"),
            "optuna": str(tmp_path / "optuna"),
            "relatorios": str(tmp_path / "reports"),
        },
        "optuna": {
            "piso_min": 1,
            "teto_por_modelo_min": {"elastic_net": 5},
            "max_tentativas": {"elastic_net": 2},
            "poda_tentativas_iniciais": 2,
            "poda_dobras_aquecimento": 2,
        },
    }

    res1 = tune(cfg, "elastic_net", df, n_trials_override=2)
    assert res1["db_path"].is_file()
    assert res1["n_concluidas"] + res1["n_podadas"] == 2

    # Simula retomada pedindo 4 tentativas no mesmo SQLite
    res2 = tune(cfg, "elastic_net", df, n_trials_override=4)
    assert res2["n_concluidas"] + res2["n_podadas"] == 4
    assert res2["best_value"] >= res1["best_value"]


def test_stratified_fold_subsample_preserves_prevalence() -> None:
    df = _make_dev_df(100)
    sub = stratified_fold_subsample(df, frac=0.4, seed=20261103)
    assert len(sub) < len(df)
    assert np.isclose(sub["y"].mean(), df["y"].mean(), atol=0.02)
