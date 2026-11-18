"""Baselines autorizados da Etapa 3.2: B0, B1 e B1-idade.

Todos são ajustados só com as linhas de treino da dobra. Nenhum usa município, UF ou região.
A idade entra por spline cúbico (5 nós por quantis do treino), como no B1 da v1, porque a taxa de
eventos tem formato em U com a idade; uma idade linear seria um baseline artificialmente fraco.
"""

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.exceptions import ConvergenceWarning
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer

from dengue_sinan.guard import verificar_dev
from dengue_sinan.modelos import logreg_sem_penalizacao
from dengue_sinan.pipeline.contrato import SEXOS

VARIAVEIS_B1 = ["idade_anos", "sexo", "gestante"]
VARIAVEIS_B1_IDADE = ["idade_anos"]


def previsao_b0(y_treino) -> float:
    """B0: a prevalência do treino da dobra. Nunca olha a região de teste."""
    y_treino = np.asarray(y_treino)
    if len(y_treino) == 0:
        raise ValueError("B0 precisa de linhas de treino")
    return float(y_treino.mean())


@dataclass
class InfoConvergencia:
    convergiu: bool
    n_iter: int
    avisos: list[str]


class BaselineLogistico:
    """Regressão logística sem penalização sobre `variaveis` (B1 ou B1-idade)."""

    def __init__(self, variaveis: list[str], max_iter: int = 1000):
        if not set(variaveis) <= set(VARIAVEIS_B1):
            raise ValueError(f"variáveis fora da lista autorizada: {variaveis}")
        self.variaveis = list(variaveis)
        blocos = [
            (
                "idade",
                SplineTransformer(n_knots=5, degree=3, knots="quantile", include_bias=False),
                ["idade_anos"],
            )
        ]
        if "sexo" in self.variaveis:
            blocos.append(("sexo", OneHotEncoder(categories=[list(SEXOS)]), ["sexo"]))
        if "gestante" in self.variaveis:
            blocos.append(("gestante", "passthrough", ["gestante"]))
        self.pipe = Pipeline(
            [("prep", ColumnTransformer(blocos)), ("clf", logreg_sem_penalizacao(max_iter))]
        )
        self.convergencia: InfoConvergencia | None = None

    def ajustar(self, x: pd.DataFrame, y, meta=None):
        verificar_dev(x, meta=meta, contexto="BaselineLogistico.ajustar")  # R1
        entrada = x[self.variaveis]
        if entrada.isna().any().any():
            raise ValueError("baseline não imputa valores: entrada com ausentes")
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            self.pipe.fit(entrada, np.asarray(y))
        textos = [str(a.message) for a in avisos if issubclass(a.category, ConvergenceWarning)]
        n_iter = int(np.max(self.pipe.named_steps["clf"].n_iter_))
        self.convergencia = InfoConvergencia(not textos, n_iter, textos)
        return self

    def prever(self, x: pd.DataFrame) -> np.ndarray:
        return self.pipe.predict_proba(x[self.variaveis])[:, 1]

    def colunas_usadas(self) -> list[str]:
        return list(self.pipe.named_steps["prep"].feature_names_in_)
