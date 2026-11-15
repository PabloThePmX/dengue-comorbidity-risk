"""Pré-processamento por família de modelos para triagem M1 (T-4.1, R4, R5)."""

from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    OneHotEncoder,
    OrdinalEncoder,
    PolynomialFeatures,
    SplineTransformer,
    StandardScaler,
)

from dengue_sinan.dataset import COMORBIDADES, METADATA_COLS, SINAIS

CATEGORICAL_FEATURES = ["sexo", *COMORBIDADES, *SINAIS]
NUMERIC_FEATURES = ["idade_anos", "gestante", "n_comorbidades", "dias_ate_notificacao"]
M1_FEATURES = [*NUMERIC_FEATURES, *CATEGORICAL_FEATURES]
FORBIDDEN_FEATURES = {
    "PETEQUIAS",
    "LACO_N",
    "CLASSI_FIN",
    "EVOLUCAO",
    "DT_INTERNA",
    "DT_OBITO",
    "DT_ENCERRA",
    "HOSPITALIZ",
    *METADATA_COLS,
}


class SimBinaryExtractor(BaseEstimator, TransformerMixin):
    """Extrai indicadores binários (1.0 se 'Sim', 0.0 caso contrário) das 7 comorbidades."""

    def fit(self, X, y=None):  # noqa: ANN001, ARG002
        return self

    def transform(self, X):  # noqa: ANN001
        import numpy as np
        import pandas as pd

        df = pd.DataFrame(X)
        out = np.zeros((len(df), df.shape[1]), dtype=np.float64)
        for idx, col in enumerate(df.columns):
            s = df[col].astype("string").str.strip()
            out[:, idx] = s.isin({"Sim", "1", "True", "true"}).to_numpy(dtype=np.float64)
        return out

    def get_feature_names_out(self, input_features=None):  # noqa: ANN001
        if input_features is None:
            return [f"{c}_Sim" for c in COMORBIDADES]
        return [f"{c}_Sim" for c in input_features]


def assert_allowed_features(columns: list[str] | set[str]) -> None:
    """Falha se alguma coluna pertencer à lista proibida (R4)."""
    forbidden = set(columns) & FORBIDDEN_FEATURES
    if forbidden:
        raise ValueError(f"Colunas proibidas detectadas nas features (R4): {sorted(forbidden)}")


def make_preprocessor(
    familia: str,
    *,
    include_comorbidity_interactions: bool | None = None,
) -> ColumnTransformer:
    """Cria o `ColumnTransformer` adequado à família do modelo (T-4.1, R5).

    Famílias aceitas:
    - `"linear"` ou `"mlp"`: spline + escala em `idade_anos`, `StandardScaler` em
      `dias_ate_notificacao` (e `n_comorbidades`), one-hot nas categóricas;
    - `"elastic_net"`: igual a `"linear"`, mais interações 2 a 2 entre comorbidades = Sim;
    - `"arvore"` (ou `"random_forest"`, `"xgboost"`): `OrdinalEncoder` nas categóricas e
      numéricas cruas (`passthrough`);
    - `"catboost"`: numéricas cruas e categóricas em `passthrough` (para `cat_features`).
    """
    fam = familia.strip().lower()
    if include_comorbidity_interactions is None:
        include_comorbidity_interactions = fam in {"elastic_net", "elasticnet"}

    if fam in {"linear", "mlp", "elastic_net", "elasticnet"}:
        age_pipe = Pipeline(
            [
                ("spline", SplineTransformer(n_knots=5, degree=3, include_bias=False)),
                ("scaler", StandardScaler()),
            ]
        )
        transformers: list[tuple[str, object, list[str]]] = [
            ("idade", age_pipe, ["idade_anos"]),
            ("dias", StandardScaler(), ["dias_ate_notificacao"]),
            ("n_comorb", StandardScaler(), ["n_comorbidades"]),
            ("gestante", "passthrough", ["gestante"]),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ]
        if include_comorbidity_interactions:
            inter_pipe = Pipeline(
                [
                    ("sim", SimBinaryExtractor()),
                    (
                        "poly",
                        PolynomialFeatures(
                            degree=2,
                            interaction_only=True,
                            include_bias=False,
                        ),
                    ),
                ]
            )
            transformers.append(("comorb_inter", inter_pipe, list(COMORBIDADES)))

        return ColumnTransformer(
            transformers=transformers,
            remainder="drop",
            verbose_feature_names_out=True,
        )

    if fam in {"arvore", "tree", "random_forest", "rf", "xgboost", "xgb", "tabfm"}:
        return ColumnTransformer(
            transformers=[
                ("num", "passthrough", NUMERIC_FEATURES),
                (
                    "cat",
                    OrdinalEncoder(
                        handle_unknown="use_encoded_value",
                        unknown_value=-1,
                        encoded_missing_value=-1,
                    ),
                    CATEGORICAL_FEATURES,
                ),
            ],
            remainder="drop",
            verbose_feature_names_out=True,
        )

    if fam == "catboost":
        return ColumnTransformer(
            transformers=[
                ("num", "passthrough", NUMERIC_FEATURES),
                ("cat", "passthrough", CATEGORICAL_FEATURES),
            ],
            remainder="drop",
            verbose_feature_names_out=False,
        )

    raise ValueError(
        f"Família desconhecida: '{familia}'. Use 'linear', 'elastic_net', 'arvore' ou 'catboost'."
    )


def get_catboost_cat_indices() -> list[int]:
    """Devolve os índices das colunas categóricas após o `make_preprocessor('catboost')`."""
    start = len(NUMERIC_FEATURES)
    return list(range(start, start + len(CATEGORICAL_FEATURES)))


__all__ = [
    "CATEGORICAL_FEATURES",
    "M1_FEATURES",
    "NUMERIC_FEATURES",
    "SimBinaryExtractor",
    "assert_allowed_features",
    "get_catboost_cat_indices",
    "make_preprocessor",
]
