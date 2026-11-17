"""Random Forest do M1 (T-4.4, D-53, R1, R3, R5, R8).

Entra no `REGISTRO` de `cv.py` como `"random_forest"`; o laço não muda. Pré-processamento da família
"arvore" (R4, R5): `make_preprocessor("arvore")` vai dentro de um `Pipeline` com o estimador, e o
ajuste inteiro usa só o treino da dobra.

Sem peso de classe (R3). A exceção prevista pelo R3 é a subamostra de negativos, por memória. Ela
fica **desligada por padrão** (`taxa_negativos` ausente): com uma taxa em (0, 1], o ajuste usa todos
os positivos e uma amostra sorteada dos negativos, só no treino da dobra. Como a amostra muda a
prevalência, as probabilidades previstas são corrigidas por

    p' = p / (p + (1 − p) / taxa)

Derivação: com todos os positivos e uma fração `taxa` dos negativos, a probabilidade do modelo na
amostra é p_s = p / (p + (1 − p)·taxa). Invertendo, p = taxa·p_s / (taxa·p_s + 1 − p_s), que é a
fórmula acima com p = p_s. A taxa fica registrada no MLflow (`rf.taxa_negativos`) em todo run ativo.
"""

from __future__ import annotations

import mlflow
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline

from dengue_sinan.guard import assert_dev_only
from dengue_sinan.preprocess import make_preprocessor
from dengue_sinan.search_space import PROIBIDOS_R3

COLUNA_ALVO = "y"
CHAVE_TAXA = "taxa_negativos"  # parâmetro opcional do modelo; ausente = sem subamostra
PARAM_MLFLOW_TAXA = "rf.taxa_negativos"


def corrigir_probabilidade(p, taxa: float) -> np.ndarray:
    """p' = p / (p + (1 − p) / taxa), para probabilidades de um modelo treinado com negativos
    subamostrados (taxa = fração de negativos mantida, em (0, 1])."""
    if not 0 < taxa <= 1:
        raise ValueError(f"taxa de negativos deve estar em (0, 1], não {taxa}")
    arr = np.asarray(p, dtype=float)
    if not np.isfinite(arr).all() or (arr < 0).any() or (arr > 1).any():
        raise ValueError("probabilidade fora de [0, 1] ou não finita")
    return taxa * arr / (taxa * arr + (1.0 - arr))


def subamostrar_negativos(y, taxa: float, seed: int) -> np.ndarray:
    """Posições (ordenadas) de todos os positivos e de uma fração `taxa` dos negativos.

    Sorteio com a semente do config (R8). Com `taxa` = 1, devolve todas as posições.
    """
    if not 0 < taxa <= 1:
        raise ValueError(f"taxa de negativos deve estar em (0, 1], não {taxa}")
    y = np.asarray(y)
    if taxa == 1:
        return np.arange(y.size)
    positivos = np.flatnonzero(y == 1)
    negativos = np.flatnonzero(y == 0)
    k = int(round(negativos.size * taxa))
    rng = np.random.default_rng(seed)
    escolhidos = rng.choice(negativos, size=k, replace=False)
    return np.sort(np.concatenate([positivos, escolhidos]))


class RandomForestM1:
    """Random Forest como `ModeloM1` (ver `cv.py`). Um objeto novo por dobra."""

    iterativo = False

    def __init__(self, params: dict, seed: int) -> None:
        params = dict(params)
        taxa = params.pop(CHAVE_TAXA, None)
        proibidos = sorted(k for k in params if any(p in k.lower() for p in PROIBIDOS_R3))
        if proibidos:
            raise ValueError(f"parâmetros de peso de classe proibidos (R3): {proibidos}")
        self.taxa = 1.0 if taxa is None else float(taxa)
        if not 0 < self.taxa <= 1:
            raise ValueError(f"taxa de negativos deve estar em (0, 1], não {taxa}")
        self._params = params
        self._seed = int(seed)
        self._pipeline: Pipeline | None = None
        self.linhas_ajuste: int | None = None

    def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None:
        if X_parada is not None or y_parada is not None:
            raise ValueError("random_forest não usa validação de parada")
        assert_dev_only(X_treino)  # R1
        y = np.asarray(y_treino)
        X = X_treino
        if self.taxa < 1:
            pos = subamostrar_negativos(y, self.taxa, self._seed)
            X, y = X_treino.iloc[pos], y[pos]
        self.linhas_ajuste = len(y)
        self._pipeline = Pipeline([
            ("preprocessamento", make_preprocessor("arvore")),
            ("floresta", RandomForestClassifier(**self._params, random_state=self._seed,
                                                n_jobs=-1)),
        ])
        self._pipeline.fit(X, y)
        # O treino usa todas as vCPUs (as árvores saem idênticas com a mesma semente). A predição
        # fica em sequência: com threads, a soma das probabilidades das árvores tem ordem variável e
        # o resultado muda no último bit entre execuções (medido: ~1e-16), o que quebra o R8.
        self._pipeline.named_steps["floresta"].set_params(n_jobs=1)
        if mlflow.active_run() is not None:
            mlflow.log_param(PARAM_MLFLOW_TAXA, str(self.taxa))

    def prever_proba(self, X) -> np.ndarray:
        if self._pipeline is None:
            raise RuntimeError("chame ajustar antes de prever")
        assert_dev_only(X)  # R1
        p = self._pipeline.predict_proba(X)[:, 1]
        if self.taxa < 1:
            p = corrigir_probabilidade(p, self.taxa)
        return np.asarray(p, dtype=float)

    def melhor_ponto(self) -> int | None:
        return None


def construir_random_forest(params: dict, cfg: dict) -> RandomForestM1:
    """Entrada do `REGISTRO`: cria um Random Forest novo (não ajustado), com a semente do config."""
    return RandomForestM1(params, seed=cfg["seed"])
