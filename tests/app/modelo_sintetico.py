"""Modelo SINTÉTICO para testes: mesmo contrato do M1 v2 (idade, sexo, gestante), dados inventados.

Não usa nenhum dado do projeto. Grava o artefato pelo mesmo caminho do pipeline
(`artefatos.salvar`), então os hashes e o layout são os reais.
"""

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

from app.config import Config
from dengue_sinan.pipeline import artefatos
from dengue_sinan.pipeline.contrato import contrato_de_entrada
from dengue_sinan.pipeline.preprocessamento import matriz_modelo
from dengue_sinan.servico import ConfigServico

VARIAVEIS = ["idade_anos", "sexo", "gestante"]


class CalibradorSintetico:
    """Identidade com o mesmo método do calibrador real (`prever`)."""

    def prever(self, p):
        return np.asarray(p, dtype=float)


def criar_artefato(pasta_base, nome="m1-sintetico", versao="0.0.1"):
    rng = np.random.default_rng(7)
    n = 3000
    x = pd.DataFrame(
        {
            "idade_anos": rng.uniform(0, 100, n),
            "sexo": rng.choice(["F", "M", "I"], n, p=[0.5, 0.45, 0.05]),
            "gestante": rng.integers(0, 2, n),
        }
    )
    logit = -4.0 + 0.02 * x["idade_anos"].to_numpy() + 0.3 * x["gestante"].to_numpy()
    y = rng.random(n) < 1 / (1 + np.exp(-logit))
    motor = XGBClassifier(n_estimators=20, max_depth=2, random_state=1, n_jobs=1)
    motor.fit(matriz_modelo(x.assign(gestante=x["gestante"].astype("int8")), VARIAVEIS), y)
    objeto = {"motor": motor, "calibrador": CalibradorSintetico(), "variaveis": VARIAVEIS}
    meta = {
        "nome_modelo": nome,
        "algoritmo": "xgboost (SINTÉTICO)",
        "calibrador": "identidade (SINTÉTICO)",
        "anos_desenvolvimento": [2022, 2023],
        "data_treinamento_utc": "2000-01-01T00:00:00+00:00",
        "aviso": "MODELO SINTÉTICO DE TESTE. Sem relação com os dados do projeto.",
        "limitacoes": ["Modelo sintético de teste."],
        "variaveis_de_entrada": VARIAVEIS,
    }
    avaliacao = {
        "escopo": "SINTÉTICO",
        "e_teste_historico": False,
        "calibrado_validacao_cruzada": {
            "prevalencia": 0.0016,
            "pr_auc": 0.0086,
            "roc_auc": 0.65,
            "brier": 0.00161,
            "brier_referencia_prevalencia": 0.00162,
        },
    }
    return artefatos.salvar(
        pasta_base, nome, versao, objeto, meta, contrato_de_entrada(VARIAVEIS), avaliacao
    )


def config_para(pasta_artefato, **kw) -> Config:
    cs = ConfigServico(
        pasta_artefato.parent,
        pasta_artefato.name,
        None,
        limite_registros=kw.pop("limite_registros", 1000),
        m1_sha256=kw.pop("m1_sha256", None),
    )
    return Config(servico=cs, **kw)
