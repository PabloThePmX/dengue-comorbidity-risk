"""Testes unitários da avaliação única no conjunto de teste e lacre R2 (T-5.1 a T-5.4)."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dengue_sinan.dataset import COMORBIDADES, SINAIS
from dengue_sinan.evaluate import evaluate_test_once
from dengue_sinan.explain import run_e1_pipeline
from dengue_sinan.folds import DEFAULT_FOLD_ORDER
from dengue_sinan.runner import run_all_models


def _make_population_df(ano: int, n_per_region: int = 50) -> pd.DataFrame:
    rng = np.random.default_rng(20261103 + ano)
    regioes = np.repeat(DEFAULT_FOLD_ORDER, n_per_region)
    n = len(regioes)

    idade = rng.uniform(5, 85, size=n)
    diab = rng.choice(["Não", "Sim"], size=n, p=[0.7, 0.3])
    hipert = rng.choice(["Não", "Sim"], size=n, p=[0.6, 0.4])
    logit = -2.0 + 0.03 * (idade - 40) + 1.5 * (diab == "Sim") + 1.2 * (hipert == "Sim")
    prob = 1.0 / (1.0 + np.exp(-logit))
    y = rng.binomial(1, prob).astype("int8")

    data: dict[str, object] = {
        "ANO": np.full(n, ano),
        "regiao": regioes,
        "faixa_etaria": np.where(idade < 40, "20-39", "60-79"),
        "CS_RACA": rng.choice(["1", "4", "9"], size=n),
        "SG_UF": rng.choice(["32", "35"], size=n, p=[0.2, 0.8]),
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


def test_evaluate_test_once_writes_lacre_and_blocks_second_call(tmp_path: Path) -> None:
    df_dev = _make_population_df(2022, 45)
    df_test = _make_population_df(2024, 45)

    cfg = {
        "seed": 20261103,
        "anos_dev": [2022, 2023],
        "ano_teste": 2024,
        "ordem_dobras": DEFAULT_FOLD_ORDER,
        "ordem_modelos": ["elastic_net"],
        "modo_teste_rapido": True,
        "supressao_min_celula": 10,
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

    # Prepara E1, B1 e M1 congelados em 2022–23
    run_e1_pipeline(cfg, df_dev)
    run_all_models(cfg, df_override=df_dev)

    # 1ª chamada no teste 2024 gera os relatórios e o LACRE.json
    res = evaluate_test_once(cfg, df_test_override=df_test)
    assert res["lacre_path"].is_file()
    assert res["metricas_md_path"].is_file()
    assert res["erros_md_path"].is_file()
    assert (tmp_path / "reports" / "teste" / "curva_decisao.png").is_file()
    assert (tmp_path / "reports" / "teste" / "calibracao_teste.png").is_file()
    assert (tmp_path / "reports" / "teste" / "subgrupos.md").is_file()

    # 2ª chamada é bloqueada pelo LACRE.json (R2)
    with pytest.raises(RuntimeError, match="teste já avaliado"):
        evaluate_test_once(cfg, df_test_override=df_test)
