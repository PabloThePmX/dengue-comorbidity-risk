"""CatBoost do M1 (T-4.6, D-53, R1, R3, R5, R6, R8, FR-22).

Entra no `REGISTRO` de `cv.py` como `"catboost"`; o laço não muda. O modelo é iterativo: o laço
passa o treino sem a validação interna em `X_treino` e a validação interna (R6, das 4 regiões de
treino) em `X_parada`. A parada antecipada usa só `X_parada`, com `od_type="Iter"`, `od_wait` e
`eval_metric` vindos de `busca.catboost.fixos` (PRAUC). Nunca usa a região deixada de fora.

Pré-processamento da família "catboost" (R4, R5): `make_preprocessor("catboost")` devolve um
DataFrame com as categóricas como texto, primeiro, e as numéricas depois. Como no XGBoost, o ajuste
é feito em passos, porque a validação interna precisa estar transformada com o ajuste do treino:
1. `fit_transform` do pré-processador só com `X_treino`;
2. `transform` de `X_parada` com esse ajuste;
3. `fit` do CatBoost com `cat_features` (índices de `indices_cat_features_catboost`) e
   `eval_set=(X_parada transformado, y_parada)`.

Sem peso de classe (R3): `auto_class_weights`, `class_weights`, `scale_pos_weight` e os outros nomes
de R3 são recusados na construção. Semente do config em `random_seed` (R8).

Dispositivo (`task_type`): `"gpu"` se o CatBoost instalado treina na GPU com `eval_metric="PRAUC"`
no early stopping, senão `"cpu"` (`detectar_dispositivo`). Um parâmetro `device` explícito
("cpu" ou "gpu") tem prioridade. Achado da T-4.6 (plan `[VERIFY]`, "CatBoost aceita PRAUC na GPU?"):
a checagem é um treino real de 5 iterações na GPU com PRAUC, e não um teste de presença da GPU. Se
ele falhar, a detecção cai para CPU e avisa o motivo com `warnings.warn`. Em ambientes sem driver
CUDA compatível, o erro do CatBoost é `CatBoostError`; ele é o único capturado, para não esconder
outros bugs. Treino em GPU não garante bit a bit a mesma execução; em CPU, sim (mesma semente).

`allow_writing_files=False`: sem isso o CatBoost cria a pasta `catboost_info/` no diretório de
trabalho. Por isso o modelo nunca escreve no disco.

A predição vai até o melhor ponto de forma explícita (`ntree_end = melhor + 1`), e não pelo que o
modelo tiver guardado. Com `use_best_model` (padrão quando há `eval_set`) o modelo já vem podado, e
o corte dá o mesmo resultado; sem a poda, o corte é o que separa as árvores úteis das de sobra. O
teste espião prova a chamada e o efeito. Contrato `ModeloM1` em `cv.py`.
"""

from __future__ import annotations

import functools
import warnings

import mlflow
import numpy as np
from catboost import CatBoostClassifier, CatBoostError
from sklearn.pipeline import Pipeline

from dengue_sinan.guard import assert_dev_only
from dengue_sinan.preprocess import indices_cat_features_catboost, make_preprocessor
from dengue_sinan.search_space import PROIBIDOS_R3

PARAM_MLFLOW_DISPOSITIVO = "cb.device"
METRICA_MLFLOW_MELHOR = "cb.melhor_iteracao"
CHAVE_DISPOSITIVO = "device"  # parâmetro opcional: "cpu" ou "gpu"; sobrepõe a detecção
DISPOSITIVOS = {"cpu": "CPU", "gpu": "GPU"}  # nome do projeto -> task_type do CatBoost


def _treino_gpu_de_teste() -> None:
    """Treino de 5 iterações na GPU com PRAUC no early stopping. Levanta CatBoostError se a GPU
    não estiver disponível ou não aceitar essa métrica."""
    rng = np.random.default_rng(0)
    X = rng.normal(size=(60, 2))
    y = (X[:, 0] > 0).astype(int)
    CatBoostClassifier(
        iterations=5, task_type="GPU", eval_metric="PRAUC", od_type="Iter", od_wait=3,
        random_seed=0, allow_writing_files=False, verbose=False,
    ).fit(X[:40], y[:40], eval_set=(X[40:], y[40:]))


@functools.lru_cache(maxsize=1)
def detectar_dispositivo() -> str:
    """"gpu" se o treino de teste na GPU (com PRAUC) passa, senão "cpu". Uma vez por processo."""
    try:
        _treino_gpu_de_teste()
    except CatBoostError as erro:
        warnings.warn(
            f"CatBoost: GPU não disponível para o early stopping com PRAUC; usando CPU ({erro})",
            stacklevel=2,
        )
        return "cpu"
    return "gpu"


class CatBoostM1:
    """CatBoost como `ModeloM1` (ver `cv.py`). Um objeto novo por dobra."""

    iterativo = True

    def __init__(self, params: dict, seed: int) -> None:
        params = dict(params)
        dispositivo = params.pop(CHAVE_DISPOSITIVO, None)
        proibidos = sorted(k for k in params if any(p in k.lower() for p in PROIBIDOS_R3))
        if proibidos:
            raise ValueError(f"parâmetros de peso de classe proibidos (R3): {proibidos}")
        if params.get("od_type") != "Iter" or "od_wait" not in params:
            raise ValueError("catboost: falta od_type 'Iter' e od_wait (R6: parada na validação)")
        if dispositivo is not None and dispositivo not in DISPOSITIVOS:
            raise ValueError(
                f"catboost: device {dispositivo!r} inválido; use {sorted(DISPOSITIVOS)}")
        self._dispositivo = dispositivo or detectar_dispositivo()
        self._estimador = CatBoostClassifier(
            **params,
            random_seed=int(seed),  # R8
            task_type=DISPOSITIVOS[self._dispositivo],
            allow_writing_files=False,  # sem catboost_info/ no diretório de trabalho
            verbose=False,
        )
        self._pipeline = Pipeline([
            ("preprocessamento", make_preprocessor("catboost")),  # R4, R5
            ("catboost", self._estimador),
        ])
        self._melhor: int | None = None
        self._fixas: int | None = None

    def fixar_iteracoes(self, n: int) -> None:
        """Retreino final (T-4.10): treina exatamente `n` árvores, sem validação de parada.

        Chame antes de `ajustar`. Sem `eval_set` o CatBoost não para antes de `iterations`; o
        `od_type` que sobra não tem efeito (conferido: 41 árvores pedidas, 41 gravadas). O laço de
        validação nunca chama este método.
        """
        if isinstance(n, bool) or not isinstance(n, int) or n < 1:
            raise ValueError(f"catboost: nº de árvores fixo deve ser inteiro >= 1, não {n!r}")
        self._estimador.set_params(iterations=n)
        self._fixas = n

    def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None:
        assert_dev_only(X_treino)  # R1
        y = np.asarray(y_treino)
        pre = self._pipeline.named_steps["preprocessamento"]
        if self._fixas is not None:  # retreino final: sem validação de parada
            if X_parada is not None or y_parada is not None:
                raise ValueError("catboost com árvores fixas não usa validação de parada")
            X_t = pre.fit_transform(X_treino, y)  # R5
            self._estimador.fit(X_t, y, cat_features=indices_cat_features_catboost(pre))
            self._melhor = self._fixas - 1  # índice da última árvore, como após a parada
        else:
            if X_parada is None or y_parada is None:
                raise ValueError("catboost é iterativo: precisa de X_parada e y_parada (R6)")
            assert_dev_only(X_parada)  # R1
            y_p = np.asarray(y_parada)
            X_t = pre.fit_transform(X_treino, y)  # R5: ajuste só com o treino da dobra
            X_p = pre.transform(X_parada)  # R5: validação transformada com o ajuste do treino
            cat = indices_cat_features_catboost(pre)
            self._estimador.fit(X_t, y, cat_features=cat, eval_set=(X_p, y_p))
            melhor = self._estimador.get_best_iteration()
            if melhor is None:
                raise RuntimeError("CatBoost não informou o melhor ponto (a parada não rodou)")
            self._melhor = int(melhor)
        if mlflow.active_run() is not None:
            mlflow.log_param(PARAM_MLFLOW_DISPOSITIVO, self._dispositivo)
            mlflow.log_metric(METRICA_MLFLOW_MELHOR, float(self._melhor))

    def prever_proba(self, X) -> np.ndarray:
        if self._melhor is None:
            raise RuntimeError("chame ajustar antes de prever")
        assert_dev_only(X)  # R1
        X_t = self._pipeline.named_steps["preprocessamento"].transform(X)
        # ntree_end conta árvores, não índices: o melhor ponto é índice 0-based, então + 1.
        p = self._estimador.predict_proba(X_t, ntree_end=self._melhor + 1)[:, 1]
        return np.asarray(p, dtype=float)

    def melhor_ponto(self) -> int | None:
        return self._melhor


def construir_catboost(params: dict, cfg: dict) -> CatBoostM1:
    """Entrada do `REGISTRO`: cria um CatBoost novo (não ajustado), com a semente do config."""
    return CatBoostM1(params, seed=cfg["seed"])
