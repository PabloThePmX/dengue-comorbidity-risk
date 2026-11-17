"""XGBoost do M1 (T-4.5, D-53, R1, R3, R5, R6, R8, FR-22).

Entra no `REGISTRO` de `cv.py` como `"xgboost"`; o laço não muda. O modelo é iterativo: o laço
passa o treino sem a validação interna em `X_treino` e a validação interna (R6, das 4 regiões de
treino) em `X_parada`. A parada antecipada usa só `X_parada`, com `eval_metric="aucpr"` (vem de
`busca.xgboost.fixos`). Nunca usa a região deixada de fora.

Pré-processamento da família "arvore" (R4, R5): `make_preprocessor("arvore")` é o primeiro passo
do `Pipeline`. A parada antecipada precisa da validação interna já transformada, então o ajuste
é feito em passos, e não por `Pipeline.fit(..., eval_set=...)` (o Pipeline não transforma o
`eval_set`):
1. `fit_transform` do pré-processador só com `X_treino`;
2. `transform` de `X_parada` com esse ajuste;
3. `fit` do XGBoost com `eval_set=[(X_parada transformado, y_parada)]`.

Sem peso de classe (R3): `scale_pos_weight` e os outros nomes de R3 são recusados na construção.
Semente do config (R8). Dispositivo: `device="cuda"` se o XGBoost instalado conseguir treinar na
GPU, senão `"cpu"` (`detectar_dispositivo`). Um parâmetro `device` explícito tem prioridade.

A predição vai até o melhor ponto de forma explícita (`iteration_range`), e não pelo padrão da
biblioteca. Contrato `ModeloM1` em `cv.py`.
"""

from __future__ import annotations

import functools
import json
import warnings

import mlflow
import numpy as np
import xgboost as xgb
from sklearn.pipeline import Pipeline

from dengue_sinan.guard import assert_dev_only
from dengue_sinan.preprocess import make_preprocessor
from dengue_sinan.search_space import PROIBIDOS_R3

PARAM_MLFLOW_DISPOSITIVO = "xgb.device"
METRICA_MLFLOW_MELHOR = "xgb.melhor_iteracao"
CHAVE_DISPOSITIVO = "device"  # parâmetro opcional: sobrepõe a detecção


@functools.lru_cache(maxsize=1)
def detectar_dispositivo() -> str:
    """"cuda" se o XGBoost instalado treina na GPU, senão "cpu". Feito uma vez por processo.

    Pedir `device="cuda"` sem GPU não dá erro: o XGBoost troca para CPU com um aviso. Por isso a
    decisão lê o dispositivo que o booster usou de fato, em `save_config()`.
    """
    clf = xgb.XGBClassifier(device="cuda", n_estimators=1, tree_method="hist")
    with warnings.catch_warnings():  # sem GPU o XGBoost avisa que trocou para CPU: é o esperado
        warnings.simplefilter("ignore", UserWarning)
        clf.fit(np.zeros((4, 1)), np.array([0, 1, 0, 1]))
    efetivo = json.loads(clf.get_booster().save_config())["learner"]["generic_param"]["device"]
    return "cuda" if efetivo.startswith("cuda") else "cpu"


class XGBoostM1:
    """XGBoost como `ModeloM1` (ver `cv.py`). Um objeto novo por dobra."""

    iterativo = True

    def __init__(self, params: dict, seed: int) -> None:
        params = dict(params)
        dispositivo = params.pop(CHAVE_DISPOSITIVO, None)
        proibidos = sorted(k for k in params if any(p in k.lower() for p in PROIBIDOS_R3))
        if proibidos:
            raise ValueError(f"parâmetros de peso de classe proibidos (R3): {proibidos}")
        if "early_stopping_rounds" not in params:
            raise ValueError("xgboost: falta early_stopping_rounds (R6: parada na validação)")
        self._dispositivo = dispositivo or detectar_dispositivo()
        self._estimador = xgb.XGBClassifier(
            **params, random_state=int(seed), device=self._dispositivo)  # R8
        self._pipeline = Pipeline([
            ("preprocessamento", make_preprocessor("arvore")),  # R4, R5
            ("xgb", self._estimador),
        ])
        self._melhor: int | None = None
        self._fixas: int | None = None

    def fixar_iteracoes(self, n: int) -> None:
        """Retreino final (T-4.10): treina exatamente `n` árvores, sem validação de parada.

        Chame antes de `ajustar`. Tira a parada antecipada do estimador (o XGBoost recusa
        `early_stopping_rounds` sem `eval_set`); o laço de validação nunca chama este método.
        """
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError(f"xgboost: nº de árvores fixo deve ser inteiro >= 1, não {n!r}")
        self._estimador.set_params(n_estimators=n, early_stopping_rounds=None)
        self._fixas = n

    def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None:
        assert_dev_only(X_treino)  # R1
        pre = self._pipeline.named_steps["preprocessamento"]
        y = np.asarray(y_treino)
        if self._fixas is not None:  # retreino final: sem validação de parada
            if X_parada is not None or y_parada is not None:
                raise ValueError("xgboost com árvores fixas não usa validação de parada")
            X_t = pre.fit_transform(X_treino, y)  # R5
            self._estimador.fit(X_t, y, verbose=False)
            self._melhor = self._fixas - 1  # índice da última árvore, como após a parada
        else:
            if X_parada is None or y_parada is None:
                raise ValueError("xgboost é iterativo: precisa de X_parada e y_parada (R6)")
            assert_dev_only(X_parada)  # R1
            y_p = np.asarray(y_parada)
            X_t = pre.fit_transform(X_treino, y)  # R5: ajuste só com o treino da dobra
            X_p = pre.transform(X_parada)  # R5: validação transformada com o ajuste do treino
            self._estimador.fit(X_t, y, eval_set=[(X_p, y_p)], verbose=False)
            self._melhor = int(self._estimador.best_iteration)
        if mlflow.active_run() is not None:
            mlflow.log_param(PARAM_MLFLOW_DISPOSITIVO, self._dispositivo)
            mlflow.log_metric(METRICA_MLFLOW_MELHOR, float(self._melhor))

    def prever_proba(self, X) -> np.ndarray:
        if self._melhor is None:
            raise RuntimeError("chame ajustar antes de prever")
        assert_dev_only(X)  # R1
        X_t = self._pipeline.named_steps["preprocessamento"].transform(X)
        p = self._estimador.predict_proba(X_t, iteration_range=(0, self._melhor + 1))[:, 1]
        return np.asarray(p, dtype=float)

    def melhor_ponto(self) -> int | None:
        return self._melhor


def construir_xgboost(params: dict, cfg: dict) -> XGBoostM1:
    """Entrada do `REGISTRO`: cria um XGBoost novo (não ajustado), com a semente do config."""
    return XGBoostM1(params, seed=cfg["seed"])
