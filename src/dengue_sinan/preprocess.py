"""Pré-processamento por família de modelos usando somente as features permitidas."""

from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import (
    OneHotEncoder,
    OrdinalEncoder,
    SplineTransformer,
    StandardScaler,
)

from dengue_sinan.profiling import COMORBIDADES, SINAIS

NUMERIC_FEATURES = ["idade_anos", "gestante", "n_comorbidades", "dias_ate_notificacao"]
CATEGORICAL_FEATURES = ["sexo", *COMORBIDADES, *SINAIS]
FEATURE_COLUMNS = [*NUMERIC_FEATURES, *CATEGORICAL_FEATURES]
CATBOOST_CATEGORICAL_INDICES = tuple(
    range(len(NUMERIC_FEATURES), len(NUMERIC_FEATURES) + len(CATEGORICAL_FEATURES))
)


class ComorbidityInteractions(BaseEstimator, TransformerMixin):
    """Cria somente os 21 produtos de indicadores Sim de pares de comorbidades."""

    def fit(self, x: pd.DataFrame, y: np.ndarray | None = None):
        missing = set(COMORBIDADES) - set(x.columns)
        if missing:
            raise ValueError(f"features ausentes para interações: {', '.join(sorted(missing))}")
        return self

    def transform(self, x: pd.DataFrame) -> np.ndarray:
        sim = pd.DataFrame({
            column: x[column].astype("string").isin({"1", "Sim"})
            for column in COMORBIDADES
        }, index=x.index)
        return np.column_stack([
            (sim[first] & sim[second]).to_numpy(dtype=np.float64)
            for first, second in combinations(COMORBIDADES, 2)
        ])

    def get_feature_names_out(self, input_features=None) -> np.ndarray:
        return np.asarray([
            f"{first}_sim__{second}_sim"
            for first, second in combinations(COMORBIDADES, 2)
        ], dtype=object)


def _base_preprocessor(familia: str) -> ColumnTransformer:
    if familia == "linear":
        return ColumnTransformer(
            transformers=[
                ("idade", Pipeline([
                    ("imputer", SimpleImputer(strategy="median")),
                    ("spline", SplineTransformer(n_knots=5, degree=3, include_bias=False)),
                    ("scale", StandardScaler()),
                ]), ["idade_anos"]),
                ("dias", Pipeline([
                    ("imputer", SimpleImputer(strategy="median")),
                    ("scale", StandardScaler()),
                ]), ["dias_ate_notificacao"]),
                ("categorias", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL_FEATURES),
                ("binarios_e_contagem", "passthrough", ["gestante", "n_comorbidades"]),
            ],
            remainder="drop",
            verbose_feature_names_out=False,
        )
    if familia == "arvore":
        return ColumnTransformer(
            transformers=[
                ("numericas", "passthrough", NUMERIC_FEATURES),
                ("categorias", OrdinalEncoder(
                    handle_unknown="use_encoded_value", unknown_value=-1,
                ), CATEGORICAL_FEATURES),
            ],
            remainder="drop",
            verbose_feature_names_out=False,
        )
    if familia == "catboost":
        return ColumnTransformer(
            transformers=[
                ("numericas", "passthrough", NUMERIC_FEATURES),
                ("categorias", "passthrough", CATEGORICAL_FEATURES),
            ],
            remainder="drop",
            verbose_feature_names_out=False,
        )
    raise ValueError("familia deve ser 'linear', 'arvore' ou 'catboost'")


def make_preprocessor(familia: str, interactions: bool = False):
    """Monta o transformador da família; interações são opcionais e só para Elastic Net."""
    preprocessor = _base_preprocessor(familia)
    if interactions:
        if familia != "linear":
            raise ValueError("interações 2 a 2 são permitidas apenas na família linear")
        return FeatureUnion([
            ("features", preprocessor),
            ("interacoes_comorbidades", ComorbidityInteractions()),
        ])
    return preprocessor
