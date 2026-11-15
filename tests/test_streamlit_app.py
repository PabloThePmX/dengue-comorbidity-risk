"""Testes unitários e de latência (< 1 s) do app Streamlit (T-6.1 a T-6.4, NFR-06, R7)."""

import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd

from app.streamlit_app import (
    DISCLAIMER_TEXT,
    PERFIL_SUBTITLE,
    SHAP_LOCAL_PHRASE,
    TRIAGEM_SUBTITLE,
    compute_perfil_tab,
    compute_triagem_tab,
)
from dengue_sinan.artifacts import load_bundle
from dengue_sinan.dataset import COMORBIDADES, SINAIS
from dengue_sinan.explain import run_e1_pipeline
from dengue_sinan.folds import DEFAULT_FOLD_ORDER
from dengue_sinan.runner import run_all_models


def _make_dev_df(n_per_region: int = 40) -> pd.DataFrame:
    rng = np.random.default_rng(20261103)
    regioes = np.repeat(DEFAULT_FOLD_ORDER, n_per_region)
    n = len(regioes)

    idade = rng.uniform(5, 85, size=n)
    diab = rng.choice(["Não", "Sim"], size=n, p=[0.7, 0.3])
    hipert = rng.choice(["Não", "Sim"], size=n, p=[0.6, 0.4])
    logit = -2.0 + 0.03 * (idade - 40) + 1.5 * (diab == "Sim") + 1.2 * (hipert == "Sim")
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
        data[s] = pd.Categorical(["Não"] * n, categories=["Não", "Sim", "Ausente"])

    df = pd.DataFrame(data)
    df["n_comorbidades"] = (
        df[COMORBIDADES].apply(lambda r: sum(v == "Sim" for v in r), axis=1).astype("int8")
    )
    return df


def test_streamlit_tabs_respond_under_1s_for_20_profiles(tmp_path: Path) -> None:
    df = _make_dev_df(40)
    cfg = {
        "seed": 20261103,
        "anos_dev": [2022, 2023],
        "ordem_dobras": DEFAULT_FOLD_ORDER,
        "ordem_modelos": ["elastic_net"],
        "modo_teste_rapido": True,
        "caminhos": {
            "dados": str(tmp_path / "data"),
            "m1": str(tmp_path / "m1"),
            "modelos": str(tmp_path / "models"),
            "mlruns": str(tmp_path / "mlruns"),
            "optuna": str(tmp_path / "optuna"),
            "relatorios": str(tmp_path / "reports"),
        },
        "optuna": {
            "piso_min": 1,
            "teto_por_modelo_min": {"elastic_net": 5},
            "max_tentativas": {"elastic_net": 1},
            "poda_tentativas_iniciais": 2,
            "poda_dobras_aquecimento": 2,
        },
    }

    run_e1_pipeline(cfg, df)
    run_all_models(cfg, df_override=df)

    e1_bundle = load_bundle(tmp_path / "models" / "e1_final.joblib")
    m1_bundle = load_bundle(tmp_path / "models" / "m1_final.joblib")

    for i in range(20):
        idade = 10.0 + i * 3.5
        sexo = "F" if i % 2 == 0 else "M"
        comorbs = [COMORBIDADES[i % len(COMORBIDADES)]] if i % 3 != 0 else []
        sinais = [SINAIS[i % len(SINAIS)]]

        t0 = time.perf_counter()
        res_p = compute_perfil_tab(
            e1_bundle,
            idade_anos=idade,
            sexo=sexo,
            gestante=False,
            comorbidades_ativas=comorbs,
        )
        elapsed_p = time.perf_counter() - t0
        assert elapsed_p < 1.0
        assert res_p["aviso"] == DISCLAIMER_TEXT
        assert res_p["frase_aba"] == PERFIL_SUBTITLE
        assert 0.0 <= res_p["risco"] <= 1.0

        t1 = time.perf_counter()
        res_t = compute_triagem_tab(
            m1_bundle,
            idade_anos=idade,
            sexo=sexo,
            gestante=False,
            comorbidades_ativas=comorbs,
            sinais_ativos=sinais,
            dias_ate_atendimento=float(i % 10),
        )
        elapsed_t = time.perf_counter() - t1
        assert elapsed_t < 1.0
        assert res_t["aviso"] == DISCLAIMER_TEXT
        assert res_t["frase_aba"] == TRIAGEM_SUBTITLE
        assert res_t["frase_shap"] == SHAP_LOCAL_PHRASE
        assert len(res_t["top_5_fatores"]) == 5


def test_no_microdata_tracked_in_git_r7() -> None:
    res = subprocess.run(
        ["git", "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = res.stdout.splitlines()
    for f in tracked:
        assert not f.endswith((".dbc", ".parquet", ".dbf")), f"Microdado rastreado no git (R7): {f}"
