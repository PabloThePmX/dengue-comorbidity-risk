"""Elastic net do M1 (T-4.6b, D-53, D-63, R1, R3, R5, R8, FR-22).

Entra no `REGISTRO` de `cv.py` como `"elastic_net"`; o laço não muda. Não é iterativo: não há
parada antecipada, então `ajustar` recebe só o treino da dobra (`X_parada` é recusado) e
`melhor_ponto` é None. Logística com penalização mista, ajustada pelo solver `saga`.

Penalização: o argumento `penalty` está deprecado no sklearn 1.9 (removido na 1.10). Com `l1_ratio`
em (0, 1), a `LogisticRegression` já aplica o elastic net; por isso o construtor recusa `penalty`
e não o repassa. `l1_ratio` vem de `busca.elastic_net.parametros` (faixa [0; 0,99]: com `l1_ratio`
= 1 a solução não seria única, porque `n_comorbidades` é a soma exata das 7 indicadoras; T-4.1).

Pré-processamento da família "linear" com interações 2 a 2 entre comorbidades (D-63), dentro do
`Pipeline` (R5): o scaler, o spline e o one-hot só aprendem com o treino da dobra.

Sem peso de classe (R3): `class_weight` é recusado na construção. Semente do config em
`random_state` (R8). Predição: probabilidade de y = 1 em [0, 1] (`predict_proba`). Contrato
`ModeloM1` em `cv.py`.

Convergência (ConvergenceWarning do saga, perto de `l1_ratio` 0,99): o aviso não é silenciado. Ele
é capturado, contado, registrado no MLflow (`en.n_iter`, `en.convergiu`, `en.avisos_convergencia`)
e emitido de novo, para continuar aparecendo no log. Nada muda no ajuste: se não convergir, o
registro mostra, e a correção (mais iterações) é decisão a registrar no Registro de problemas.
"""

from __future__ import annotations

import warnings
from typing import Any

import mlflow
import numpy as np
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

from dengue_sinan.guard import assert_dev_only
from dengue_sinan.preprocess import make_preprocessor
from dengue_sinan.search_space import PROIBIDOS_R3

PARAM_MLFLOW_N_ITER = "en.n_iter"
PARAM_MLFLOW_CONVERGIU = "en.convergiu"
PARAM_MLFLOW_AVISOS = "en.avisos_convergencia"
SOLVER = "saga"


class ElasticNetM1:
    """Elastic net como `ModeloM1` (ver `cv.py`). Um objeto novo por dobra."""

    iterativo = False

    def __init__(self, params: dict[str, Any], seed: int) -> None:
        params = dict(params)
        proibidos = sorted(k for k in params if any(p in k.lower() for p in PROIBIDOS_R3))
        if proibidos:
            raise ValueError(f"parâmetros de peso de classe proibidos (R3): {proibidos}")
        if "penalty" in params:
            raise ValueError(
                "elastic net: 'penalty' está deprecado no sklearn 1.9; use l1_ratio (T-4.6b)")
        if params.get("solver") != SOLVER:
            raise ValueError(
                f"elastic net: solver deve ser {SOLVER!r}, não {params.get('solver')!r}")
        if "l1_ratio" not in params:
            raise ValueError("elastic net: falta l1_ratio")
        self._estimador = LogisticRegression(**params, random_state=int(seed))  # R8
        pre = make_preprocessor("linear", interacoes_comorbidade=True)  # R4, R5, D-63
        self._pipeline = Pipeline([
            ("preprocessamento", pre),
            ("logistica", self._estimador),
        ])
        self._ajustado = False
        self.n_iter_: int | None = None
        self.convergiu_: bool | None = None
        self.avisos_convergencia_: int = 0

    def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None:
        if X_parada is not None or y_parada is not None:
            raise ValueError("elastic_net não usa validação de parada (não é iterativo)")
        assert_dev_only(X_treino)  # R1
        with warnings.catch_warnings(record=True) as avisos:
            warnings.simplefilter("always")
            self._pipeline.fit(X_treino, np.asarray(y_treino))
        # Nada é silenciado: todo aviso capturado é emitido de novo depois de contado.
        for aviso in avisos:
            warnings.warn(aviso.message, aviso.category, stacklevel=2)
        convergencia = [a for a in avisos if issubclass(a.category, ConvergenceWarning)]
        self.n_iter_ = int(np.max(self._estimador.n_iter_))
        self.avisos_convergencia_ = len(convergencia)
        self.convergiu_ = self.avisos_convergencia_ == 0
        self._ajustado = True
        if mlflow.active_run() is not None:
            mlflow.log_metric(PARAM_MLFLOW_N_ITER, float(self.n_iter_))
            mlflow.log_metric(PARAM_MLFLOW_CONVERGIU, float(self.convergiu_))
            mlflow.log_metric(PARAM_MLFLOW_AVISOS, float(self.avisos_convergencia_))

    def prever_proba(self, X) -> np.ndarray:
        if not self._ajustado:
            raise RuntimeError("chame ajustar antes de prever")
        assert_dev_only(X)  # R1
        return np.asarray(self._pipeline.predict_proba(X)[:, 1], dtype=float)

    def melhor_ponto(self) -> int | None:
        return None


def construir_elastic_net(params: dict[str, Any], cfg: dict) -> ElasticNetM1:
    """Entrada do `REGISTRO`: cria um elastic net novo (não ajustado), com a semente do config."""
    return ElasticNetM1(params, seed=cfg["seed"])
