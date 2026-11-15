"""Testes unitários da execução em sessão única e retomada após queda (T-4.3b a T-4.10)."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dengue_sinan.dataset import COMORBIDADES, SINAIS
from dengue_sinan.folds import DEFAULT_FOLD_ORDER
from dengue_sinan.runner import run_all_models


def _make_dev_df(n_per_region: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(20261103)
    regioes = np.repeat(DEFAULT_FOLD_ORDER, n_per_region)
    n = len(regioes)

    idade = rng.uniform(5, 85, size=n)
    diab = rng.choice(["Não", "Sim"], size=n, p=[0.7, 0.3])
    hipert = rng.choice(["Não", "Sim"], size=n, p=[0.6, 0.4])
    logit = -2.2 + 0.03 * (idade - 40) + 1.5 * (diab == "Sim") + 1.2 * (hipert == "Sim")
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


def test_run_all_models_simulated_crash_and_resume(tmp_path: Path) -> None:
    df = _make_dev_df(50)
    cfg = {
        "seed": 20261103,
        "anos_dev": [2022, 2023],
        "ordem_dobras": DEFAULT_FOLD_ORDER,
        "ordem_modelos": ["elastic_net", "xgboost"],
        "modo_teste_rapido": True,
        "bootstrap_pareado": 20,
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
            "teto_por_modelo_min": {"elastic_net": 5, "xgboost": 5},
            "max_tentativas": {"elastic_net": 1, "xgboost": 1},
            "poda_tentativas_iniciais": 2,
            "poda_dobras_aquecimento": 2,
        },
    }

    # 1ª execução cai depois de elastic_net
    with pytest.raises(RuntimeError, match="Queda simulada"):
        run_all_models(cfg, df_override=df, fail_after_model="elastic_net")

    concluido_en = tmp_path / "m1" / "elastic_net" / "CONCLUIDO.json"
    assert concluido_en.is_file()
    mtime_en_before = concluido_en.stat().st_mtime_ns

    # 2ª execução pula elastic_net, conclui xgboost, seleção, SHAP e retreino
    res = run_all_models(cfg, df_override=df)
    assert concluido_en.stat().st_mtime_ns == mtime_en_before
    assert res["m1_bundle_path"].is_file()

    report = json.loads(res["session_report_path"].read_text(encoding="utf-8"))
    assert report["sessao_completa"] is True
    assert report["passou"] is True
    blocos = {b["bloco"]: b["passou"] for b in report["blocos"]}
    for b_name in ("checagem_inicial", "elastic_net", "xgboost", "selecao", "shap", "retreino"):
        assert blocos[b_name] is True
