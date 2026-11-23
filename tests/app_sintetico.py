"""Apoio dos testes da demo (T-6.1): entradas de exemplo, a tabela do contrato escrita à mão e um
M1 sintético pequeno. Nada aqui lê microdados (R7) nem o ano de teste (R1)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from dengue_sinan import preprocess, retreino, selecao
from dengue_sinan.profiling import COMORBIDADES, SINAIS

# Tabela "Vira a feature" do contrato (specs/contracts/interfaces.md › Entrada de casos), escrita
# aqui de propósito: o teste não pode importar a tabela do código que ele confere.
CONTRATO_COMORBIDADES = [
    ("diabetes", "DIABETES"), ("hematologica", "HEMATOLOG"), ("hepatopatia", "HEPATOPAT"),
    ("renal_cronica", "RENAL"), ("hipertensao", "HIPERTENSA"), ("acido_peptica", "ACIDO_PEPT"),
    ("autoimune", "AUTO_IMUNE"),
]
CONTRATO_SINAIS = [
    ("febre", "FEBRE"), ("mialgia", "MIALGIA"), ("cefaleia", "CEFALEIA"),
    ("exantema", "EXANTEMA"), ("vomito", "VOMITO"), ("nausea", "NAUSEA"),
    ("dor_costas", "DOR_COSTAS"), ("conjuntvit", "CONJUNTVIT"), ("artrite", "ARTRITE"),
    ("artralgia", "ARTRALGIA"), ("dor_retro", "DOR_RETRO"), ("petequia_n", "PETEQUIA_N"),
    ("leucopenia", "LEUCOPENIA"), ("laco", "LACO"),
]
CONTRATO_NIVEL = {"sim": "Sim", "nao": "Não", "ignorado": "Ausente"}
CONTRATO_GESTANTE = {"sim": 1, "nao": 0, "ignorado": 0}


def bruta(idade=40, sexo="F", gestante="nao", dias=2, sim=(), ignorado=()) -> dict:
    """Entrada da aba Triagem: tudo `nao`, menos o que vem em `sim` e `ignorado` (campos do
    contrato, ex.: "febre")."""
    campos = [c for c, _ in CONTRATO_COMORBIDADES + CONTRATO_SINAIS]
    dados = {c: "sim" if c in sim else "ignorado" if c in ignorado else "nao" for c in campos}
    return {"idade_anos": idade, "sexo": sexo, "gestante": gestante,
            "dias_ate_notificacao": dias, **dados}


def frame_do_contrato(entrada: dict) -> pd.DataFrame:
    """A linha de features que o contrato manda para a entrada, montada à mão (sem `app`)."""
    linha = {
        "ANO": 2023,
        "idade_anos": float(entrada["idade_anos"]),
        "sexo": entrada["sexo"],
        "gestante": np.int8(CONTRATO_GESTANTE[entrada["gestante"]]),
        "dias_ate_notificacao": entrada["dias_ate_notificacao"],
        "n_comorbidades": sum(entrada[c] == "sim" for c, _ in CONTRATO_COMORBIDADES),
    }
    for campo, feature in CONTRATO_COMORBIDADES + CONTRATO_SINAIS:
        linha[feature] = CONTRATO_NIVEL[entrada[campo]]
    df = pd.DataFrame([linha])
    for feature in [*COMORBIDADES, *SINAIS]:
        df[feature] = pd.Categorical(df[feature], categories=["Sim", "Não", "Ausente"])
    return df


PARAMS_XGB = {
    "tree_method": "hist", "n_estimators": 300, "early_stopping_rounds": 5,
    "eval_metric": "aucpr", "learning_rate": 0.3, "max_depth": 3, "min_child_weight": 1.0,
    "subsample": 0.8, "colsample_bytree": 0.8, "reg_lambda": 1.0, "device": "cpu",
}


def populacao_sintetica(n: int = 900, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "ANO": rng.choice([2022, 2023], n).astype("int64"),
        "idade_anos": rng.uniform(0, 90, n),
        "sexo": rng.choice(["F", "M", "I"], n),
        "gestante": rng.integers(0, 2, n).astype("int8"),
        "dias_ate_notificacao": rng.integers(0, 60, n),
    })
    for c in [*COMORBIDADES, *SINAIS]:
        df[c] = rng.choice(["Sim", "Não", "Ausente"], n, p=[0.25, 0.65, 0.1])
    df["n_comorbidades"] = sum((df[c] == "Sim").astype(int) for c in COMORBIDADES)
    risco = 0.1 + 0.4 * (df["RENAL"] == "Sim") + 0.2 * (df["VOMITO"] == "Sim")
    df["y"] = (rng.uniform(size=n) < risco).astype("int64")
    return df


def m1_sintetico(limiar: float = 0.4) -> retreino.ModeloFinal:
    """`ModeloFinal` de XGBoost pequeno (5 árvores, CPU) com calibrador de Platt e o `limiar`."""
    df = populacao_sintetica()
    modelo, _ = retreino.treinar_final({"seed": 11}, "xgboost", PARAMS_XGB, df, [2, 4, 6])
    rng = np.random.default_rng(5)
    p = rng.uniform(0.01, 0.9, 300)
    cal = selecao.ajustar_platt(p, (rng.uniform(size=300) < p).astype(int))
    pre = modelo._pipeline.named_steps["preprocessamento"]
    return retreino.ModeloFinal(nome="xgboost", modelo=modelo, calibrador=cal, limiar=limiar,
                                features=preprocess.colunas_do_preprocessor(pre))
