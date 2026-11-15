"""Pré-processadores ajustados dentro de cada dobra de validação."""

from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    OneHotEncoder,
    OrdinalEncoder,
    SplineTransformer,
    StandardScaler,
)

from dengue_sinan.dataset import COMORBIDITY_FEATURES, SYMPTOM_FEATURES

_CATEGORICAL = ["sexo", *COMORBIDITY_FEATURES, *SYMPTOM_FEATURES]
_NUMERIC = ["idade_anos", "gestante", "n_comorbidades", "dias_ate_notificacao"]


class ComorbidityInteractions(BaseEstimator, TransformerMixin):
    """Cria produtos binários Sim×Sim para os pares de comorbidades."""

    def fit(self, X: pd.DataFrame, y=None):
        missing = sorted(set(COMORBIDITY_FEATURES) - set(X.columns))
        if missing:
            raise ValueError(f"Colunas de comorbidade ausentes: {missing}")
        self.feature_names_in_ = np.asarray(COMORBIDITY_FEATURES, dtype=object)
        self.pairs_ = list(combinations(COMORBIDITY_FEATURES, 2))
        return self

    def transform(self, X: pd.DataFrame) -> np.ndarray:
        if not hasattr(self, "pairs_"):
            raise RuntimeError("ComorbidityInteractions precisa ser ajustado antes de transformar.")
        values = np.column_stack(
            [X[first].eq("Sim").to_numpy() & X[second].eq("Sim").to_numpy()
             for first, second in self.pairs_]
        )
        return values.astype(np.float64)

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        if not hasattr(self, "pairs_"):
            raise RuntimeError("ComorbidityInteractions precisa ser ajustado antes dos nomes.")
        return np.asarray(
            [f"{first}__{second}" for first, second in self.pairs_], dtype=object
        )


def make_preprocessor(
    familia: str, *, interacoes_comorbidades: bool = False
) -> ColumnTransformer:
    """Monta o pré-processador linear ou de árvores; o ajuste ocorre só no treino da dobra."""
    if familia == "linear":
        transformers = [
            (
                "idade",
                Pipeline(
                    [
                        ("spline", SplineTransformer(n_knots=5, degree=3, extrapolation="linear")),
                        ("escala", StandardScaler()),
                    ]
                ),
                ["idade_anos"],
            ),
            ("numericas", StandardScaler(), ["n_comorbidades", "dias_ate_notificacao"]),
            ("gestante", "passthrough", ["gestante"]),
            (
                "categoricas",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                ["sexo", *COMORBIDITY_FEATURES, *SYMPTOM_FEATURES],
            ),
        ]
        if interacoes_comorbidades:
            transformers.append(
                ("interacoes_comorbidades", ComorbidityInteractions(), COMORBIDITY_FEATURES)
            )
        return ColumnTransformer(transformers, remainder="drop")

    if familia == "arvore":
        return ColumnTransformer(
            [
                (
                    "categoricas",
                    OrdinalEncoder(
                        categories=[
                            ["F", "I", "M"],
                            *[["Ausente", "Não", "Sim"] for _ in COMORBIDITY_FEATURES],
                            *[["Ausente", "Não", "Sim"] for _ in SYMPTOM_FEATURES],
                        ],
                        handle_unknown="use_encoded_value",
                        unknown_value=-1,
                    ),
                    _CATEGORICAL,
                ),
                ("numericas", "passthrough", _NUMERIC),
            ],
            remainder="drop",
        )

    raise ValueError("familia deve ser 'linear' ou 'arvore'.")
