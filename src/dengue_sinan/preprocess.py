"""Pré-processamento por família de modelo (T-4.1, D-63, R4, R5).

Ponto de entrada: `make_preprocessor(familia, interacoes_comorbidade=False)`. Devolve um
`ColumnTransformer` **não ajustado**. Quem chama (T-4.2, T-4.4 a T-4.7) põe o estimador depois dele
num `Pipeline` e ajusta tudo junto só com o treino da dobra (R5). Nada é ajustado aqui.

Entrada esperada: o DataFrame de `dataset.build_feature_frame` (colunas do
[dicionário de features](../../specs/data-model.md#dicionário-de-features)). Colunas que não são
features (UF, ano, raça, etc.) podem estar presentes: `remainder="drop"` as ignora, e
`validar_preprocessor` garante que nenhuma delas é lida.

Famílias:
- `"linear"` (elastic net e MLP): `idade_anos` em spline + escala; `dias_ate_notificacao` em
  escala; `sexo` e as 21 colunas de comorbidade e sintoma em one-hot de 3 níveis (todos os níveis,
  sem coluna de referência, porque o modelo é penalizado); `gestante` e `n_comorbidades` cruas.
  Com `interacoes_comorbidade=True` (só elastic net, D-63), acrescenta os produtos 2 a 2 entre as 7
  comorbidades em "Sim" (21 colunas). O MLP usa sem interações: a rede aprende as interações.
- `"arvore"` (Random Forest, XGBoost): `OrdinalEncoder` com ordem fixa (Não=0, Sim=1, Ausente=2;
  sexo F, I, M); idade, dias, gestante e n_comorbidades cruas (só convertidas para float32).
- `"catboost"`: as categóricas viram texto e seguem como `cat_features`, sem encoder; numéricas
  como float. A saída é um DataFrame (`set_output(transform="pandas")`) com as categóricas primeiro.
  Os índices vêm de `indices_cat_features_catboost`.

Escolhas (detalhes no Registro de execução, T-4.1):
- Spline: `SplineTransformer(n_knots=5, degree=3, knots="quantile", include_bias=False)`. Os nós
  são quantis, ajustados só no treino da dobra (R5). `include_bias=False` tira uma base para não
  colidir com o intercepto (a documentação do sklearn recomenda isso num modelo linear).
- Desempenho (~2,45 M de linhas): na família linear a saída é uma matriz CSR em `float32`
  (`sparse_threshold=1.0`; os blocos densos passam por cast). Na árvore a saída é um array denso
  `float32`, de ~250 MB no M1. Quem consome a linear precisa de `toarray()` por lote no MLP.
  Categoria desconhecida: no one-hot vira linha de zeros; no ordinal vira NaN (XGBoost e RF tratam
  NaN como ausente).
"""

from __future__ import annotations

from collections.abc import Iterable
from itertools import combinations

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import (
    FunctionTransformer,
    OneHotEncoder,
    OrdinalEncoder,
    PolynomialFeatures,
    SplineTransformer,
    StandardScaler,
)

from dengue_sinan.profiling import COMORBIDADES, SINAIS

FAMILIAS = ("linear", "arvore", "catboost")

IDADE = "idade_anos"
DIAS = "dias_ate_notificacao"
SEXO = "sexo"
GESTANTE = "gestante"
N_COMORB = "n_comorbidades"

# Comorbidades e sintomas: 3 níveis (D-07). Ordem fixa: Não, Sim, Ausente.
_NIVEIS_3 = ["Não", "Sim", "Ausente"]
_SEXO_NIVEIS = ["F", "I", "M"]
_CAT3 = [*COMORBIDADES, *SINAIS]  # 7 comorbidades + 14 sintomas = 21 colunas de 3 níveis

# Lista fechada de features (R4): cópia do dicionário de features em data-model.md. Um teste
# compara esta tupla com a lista literal do dicionário, então mudar uma delas quebra o teste.
FEATURES_PERMITIDAS: tuple[str, ...] = (
    IDADE, SEXO, GESTANTE, *COMORBIDADES, N_COMORB, *SINAIS, DIAS,
)

# Colunas que não podem entrar no X (R4 e data-model: "só para dobras e subgrupos" etc.).
PROIBIDAS_EXATAS = frozenset({
    "UF", "SG_UF", "regiao", "ANO", "LINHA", "y", "faixa_etaria", "idade_de_ano_nasc",
    "ID_MN_RESI", "ID_UNIDADE", "ID_MUNICIP", "CS_RACA", "CS_ESCOL_N", "CS_SEXO", "CS_GESTANT",
    "NU_IDADE_N", "ANO_NASC", "DT_NOTIFIC", "DT_SIN_PRI", "SEM_PRI", "SEMANA", "HOSPITALIZ",
    "CRITERIO", "CLASSI_FIN", "EVOLUCAO", "PETEQUIAS", "LACO_N",
})
PROIBIDAS_PREFIXOS = (
    "ALRM_", "GRAV_", "RESUL_", "SOROTIP", "HISTOPA", "IMUNOH", "DT_", "CS_", "ID_", "SG_",
    "NU_IDADE",
)

CATEGORICAS_CATBOOST = [SEXO, *_CAT3]
NUMERICAS_CATBOOST = [IDADE, DIAS, GESTANTE, N_COMORB]

_ORDINAL_SEGURO = {
    "handle_unknown": "use_encoded_value",
    "unknown_value": np.nan,
    "encoded_missing_value": np.nan,
    "dtype": np.float32,
}


def validar_colunas(colunas: Iterable[str]) -> None:
    """Recusa coluna proibida (R4) ou fora do dicionário de features. Levanta ValueError."""
    colunas = list(colunas)
    proibidas = sorted({c for c in colunas
                        if c in PROIBIDAS_EXATAS or c.startswith(PROIBIDAS_PREFIXOS)})
    if proibidas:
        raise ValueError(f"colunas proibidas (R4): {proibidas}")
    fora = sorted({c for c in colunas if c not in FEATURES_PERMITIDAS})
    if fora:
        raise ValueError(f"colunas fora do dicionário de features: {fora}")


def colunas_do_preprocessor(pre: ColumnTransformer) -> list[str]:
    """Colunas de entrada que o ColumnTransformer lê (sem repetição, na ordem em que aparecem)."""
    usadas: list[str] = []
    for _, _, colunas in pre.transformers:
        usadas.extend(colunas)
    return list(dict.fromkeys(usadas))


def validar_preprocessor(pre: ColumnTransformer) -> None:
    """Confere que todas as colunas lidas pelo pré-processador saem de FEATURES_PERMITIDAS."""
    validar_colunas(colunas_do_preprocessor(pre))


class ParesDeComorbidadesSim(BaseEstimator, TransformerMixin):
    """Produtos 2 a 2 dos indicadores "Sim" das comorbidades (D-63).

    Recebe as colunas de comorbidade em texto (Sim, Não ou Ausente) e as transforma em
    indicadores (1 se "Sim", 0 caso contrário). Usa `PolynomialFeatures(degree=2,
    interaction_only=True, include_bias=False)` e guarda só os termos de grau 2: 7 comorbidades
    dão 21 pares. Os termos de grau 1 (já estão no one-hot) e qualquer termo com "Ausente" ficam
    de fora.
    """

    def fit(self, X, y=None):
        self.n_features_in_ = X.shape[1]
        if hasattr(X, "columns"):
            self.feature_names_in_ = np.asarray(X.columns, dtype=object)
        self.pf_ = PolynomialFeatures(degree=2, interaction_only=True, include_bias=False)
        self.pf_.fit(self._indicadores(X))
        self.mascara_ = self.pf_.powers_.sum(axis=1) == 2
        return self

    def transform(self, X):
        pares = self.pf_.transform(self._indicadores(X))[:, self.mascara_]
        return pares.astype(np.float32, copy=False)

    def get_feature_names_out(self, input_features=None):
        if input_features is not None:
            nomes = list(input_features)
        elif hasattr(self, "feature_names_in_"):
            nomes = list(self.feature_names_in_)
        else:
            nomes = [f"x{i}" for i in range(self.n_features_in_)]
        # Mesma ordem de PolynomialFeatures: pares (i, j) com i < j, em ordem lexicográfica.
        return np.array([f"{a}=Sim x {b}=Sim" for a, b in combinations(nomes, 2)], dtype=object)

    @staticmethod
    def _indicadores(X) -> np.ndarray:
        return (np.asarray(X) == "Sim").astype(np.float32)


def _como_texto(X) -> pd.DataFrame:
    """Categóricas do CatBoost como texto. NaN vira "nan"; as features não têm NaN no build."""
    return pd.DataFrame(X).astype(str)


def _como_float(X) -> pd.DataFrame:
    return pd.DataFrame(X).astype(np.float64)


def _para_float32(X) -> np.ndarray:
    """Cast para float32 (memória: ~2,45 M de linhas). Valores pequenos e exatos (0/1, 0–7)."""
    return np.asarray(X, dtype=np.float32)


def _float32() -> FunctionTransformer:
    return FunctionTransformer(_para_float32, feature_names_out="one-to-one")


def _idade_spline() -> Pipeline:
    return Pipeline([
        ("spline", SplineTransformer(n_knots=5, degree=3, knots="quantile", include_bias=False)),
        ("escala", StandardScaler()),
        ("float32", _float32()),
    ])


def _linear(interacoes_comorbidade: bool) -> ColumnTransformer:
    blocos = [
        ("idade", _idade_spline(), [IDADE]),
        ("dias", Pipeline([("escala", StandardScaler()), ("float32", _float32())]), [DIAS]),
        ("sexo", OneHotEncoder(categories=[_SEXO_NIVEIS], handle_unknown="ignore",
                               sparse_output=True, dtype=np.float32), [SEXO]),
        ("niveis", OneHotEncoder(categories=[_NIVEIS_3] * len(_CAT3), handle_unknown="ignore",
                                 sparse_output=True, dtype=np.float32), _CAT3),
        ("cruas", _float32(), [GESTANTE, N_COMORB]),
    ]
    if interacoes_comorbidade:
        blocos.append(("pares", ParesDeComorbidadesSim(), list(COMORBIDADES)))
    # sparse_threshold=1.0: a saída fica esparsa (CSR float32). Com o padrão (0,3) os blocos
    # densos (spline, escala, pares) fariam a saída virar densa em float64, ~1,9 GB no M1.
    return ColumnTransformer(blocos, remainder="drop", sparse_threshold=1.0)


def _arvore() -> ColumnTransformer:
    return ColumnTransformer([
        ("sexo", OrdinalEncoder(categories=[_SEXO_NIVEIS], **_ORDINAL_SEGURO), [SEXO]),
        ("niveis", OrdinalEncoder(categories=[_NIVEIS_3] * len(_CAT3), **_ORDINAL_SEGURO), _CAT3),
        ("cruas", _float32(), [IDADE, DIAS, GESTANTE, N_COMORB]),
    ], remainder="drop")


def _catboost() -> ColumnTransformer:
    return ColumnTransformer([
        ("categoricas", FunctionTransformer(_como_texto, feature_names_out="one-to-one"),
         CATEGORICAS_CATBOOST),
        ("numericas", FunctionTransformer(_como_float, feature_names_out="one-to-one"),
         NUMERICAS_CATBOOST),
    ], remainder="drop", verbose_feature_names_out=False).set_output(transform="pandas")


def make_preprocessor(familia: str, *, interacoes_comorbidade: bool = False) -> ColumnTransformer:
    """ColumnTransformer da família (não ajustado). Levanta ValueError para família desconhecida
    ou para interações fora da família "linear" (D-63)."""
    if familia not in FAMILIAS:
        raise ValueError(f"família {familia!r} desconhecida; use {FAMILIAS}")
    if interacoes_comorbidade and familia != "linear":
        raise ValueError("interacoes_comorbidade só existe na família 'linear' (D-63)")
    if familia == "linear":
        pre = _linear(interacoes_comorbidade)
    elif familia == "arvore":
        pre = _arvore()
    else:
        pre = _catboost()
    validar_preprocessor(pre)
    return pre


def indices_cat_features_catboost(pre: ColumnTransformer) -> list[int]:
    """Índices das categóricas na saída do pré-processador da família "catboost" (já ajustado).

    Use em `CatBoostClassifier(cat_features=...)`, com o DataFrame que `pre.transform` devolve.
    """
    nomes = list(pre.get_feature_names_out())
    return [nomes.index(c) for c in CATEGORICAS_CATBOOST]
