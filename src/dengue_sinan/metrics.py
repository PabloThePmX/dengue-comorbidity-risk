"""Métricas de avaliação (T-2.4, plan › Incerteza e comparação, D-33, D-39, D-53).

Funções puras: recebem arrays de rótulo `y` (0/1) e de probabilidade `p`, nunca DataFrame de
microdados. Por isso não chamam `assert_dev_only` (guard.py): quem chama é que escolhe os dados
(R1). Nenhuma função usa pesos de classe (R3) nem semente global: a semente entra por parâmetro
(R8).

Convenções:
- Um caso é "alto risco" quando `p >= limiar` (spec › Critérios de sucesso, FR-08).
- Divisão por zero em precisão, recall e F-beta devolve 0.0.
"""

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

# Limite para logit(p) não virar infinito quando p é exatamente 0 ou 1.
_EPS_PROBABILIDADE = 1e-12
_QUANTIS_IC = (0.025, 0.975)


def pr_auc(y, p) -> float:
    """Área sob a curva precisão-recall (average precision). Métrica primária (D-09)."""
    return float(average_precision_score(np.asarray(y), np.asarray(p)))


def roc_auc(y, p) -> float:
    """Área sob a curva ROC. Secundária, para comparar com a literatura.

    Não é o critério de seleção: com positivos raros fica alta mesmo com muitos falsos negativos.
    """
    return float(roc_auc_score(np.asarray(y), np.asarray(p)))


def brier(y, p) -> float:
    """Brier score: erro quadrático médio das probabilidades. Menor é melhor."""
    return float(brier_score_loss(np.asarray(y), np.asarray(p)))


def calibration_slope_intercept(y, p) -> tuple[float, float]:
    """Calibration slope e intercept (calibration-in-the-large).

    - slope: coeficiente de `logit(p)` numa logística de `y` (com intercepto). Ideal = 1.
    - intercept: intercepto de uma logística de `y` com `logit(p)` como offset (coeficiente
      fixado em 1). Ideal = 0.

    Usa `statsmodels` (GLM binomial). Probabilidades exatamente 0 ou 1 são limitadas a
    [1e-12, 1 - 1e-12] antes do logit.
    """
    y_arr = np.asarray(y, dtype=float)
    p_arr = np.clip(np.asarray(p, dtype=float), _EPS_PROBABILIDADE, 1 - _EPS_PROBABILIDADE)
    logit_p = np.log(p_arr / (1 - p_arr))

    X = sm.add_constant(logit_p, has_constant="add")
    slope = sm.GLM(y_arr, X, family=sm.families.Binomial()).fit().params[1]

    intercepto_offset = np.ones_like(y_arr)  # coeficiente de logit(p) fixado em 1 pelo offset
    intercept = sm.GLM(
        y_arr, intercepto_offset, offset=logit_p, family=sm.families.Binomial()
    ).fit().params[0]
    return float(slope), float(intercept)


def _contagens(y, p, limiares) -> tuple[np.ndarray, np.ndarray, int]:
    """VP e FP para cada limiar, e o total de positivos. Vetorizado: uma ordenação só.

    Com `p` ordenado, os casos com `p >= limiar` são um sufixo; o número de positivos nesse
    sufixo sai de uma soma acumulada. Custo O(n log n) para qualquer número de limiares.
    """
    y_int = np.asarray(y).astype(np.int64)
    p_arr = np.asarray(p, dtype=float)
    ordem = np.argsort(p_arr, kind="stable")
    p_ord = p_arr[ordem]
    pos_acum = np.concatenate(([0], np.cumsum(y_int[ordem])))
    total_pos = int(pos_acum[-1])

    limiares = np.atleast_1d(np.asarray(limiares, dtype=float))
    abaixo = np.searchsorted(p_ord, limiares, side="left")  # casos com p < limiar
    vp = total_pos - pos_acum[abaixo]
    predicoes_positivas = len(p_arr) - abaixo
    fp = predicoes_positivas - vp
    return vp, fp, total_pos


def _fbeta(vp, fp, fn, beta: float):
    """F-beta = (1 + β²)·VP / ((1 + β²)·VP + β²·FN + FP). β > 1 prioriza o recall (D-33)."""
    b2 = beta * beta
    numerador = (1 + b2) * vp
    denominador = numerador + b2 * fn + fp
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(denominador > 0, numerador / denominador, 0.0)


def threshold_metrics(y, p, limiar: float) -> dict:
    """Acurácia, precisão, recall, F1 e F2 no limiar (predito positivo se `p >= limiar`)."""
    y_arr = np.asarray(y)
    vp, fp, total_pos = _contagens(y_arr, p, limiar)
    vp, fp = int(vp[0]), int(fp[0])
    fn = total_pos - vp
    tn = len(y_arr) - total_pos - fp
    precisao = vp / (vp + fp) if vp + fp > 0 else 0.0
    recall = vp / (vp + fn) if vp + fn > 0 else 0.0
    return {
        "acuracia": (vp + tn) / len(y_arr),
        "precisao": precisao,
        "recall": recall,
        "f1": float(_fbeta(vp, fp, fn, beta=1.0)),
        "f2": float(_fbeta(vp, fp, fn, beta=2.0)),
    }


def best_f2_threshold(y, p) -> float:
    """Limiar que maximiza o F2 (D-33). Varre os valores únicos de `p`.

    Empate: devolve o menor limiar entre os de F2 máximo, ou seja, o de maior recall.
    Escolha do limiar só nas predições fora da dobra (FR-17), nunca no teste (R1, P2).
    """
    p_arr = np.asarray(p, dtype=float)
    if p_arr.size == 0:
        raise ValueError("p vazio: não há limiar a escolher")
    candidatos = np.unique(p_arr)  # ordenados de forma crescente
    vp, fp, total_pos = _contagens(y, p_arr, candidatos)
    f2 = _fbeta(vp, fp, total_pos - vp, beta=2.0)
    return float(candidatos[int(np.argmax(f2))])


def net_benefit(y, p, limiares) -> pd.DataFrame:
    """Curva de decisão (decision curve analysis, D-39).

    Para cada limiar de risco `pt`:
        NB_modelo = VP/n − FP/n × pt/(1 − pt)
        NB_tratar_todos = prevalência − (1 − prevalência) × pt/(1 − pt)
        NB_tratar_ninguem = 0

    Devolve um DataFrame com colunas `limiar`, `modelo` (NB do modelo), `tratar_todos` e
    `tratar_ninguem`. Os limiares precisam estar em (0, 1).
    """
    limiares = np.asarray(limiares, dtype=float)
    if limiares.size == 0 or np.any((limiares <= 0) | (limiares >= 1)):
        raise ValueError("limiares de net benefit precisam estar em (0, 1)")

    y_arr = np.asarray(y)
    n = len(y_arr)
    vp, fp, total_pos = _contagens(y_arr, p, limiares)
    prevalencia = total_pos / n
    razao = limiares / (1 - limiares)  # custo relativo do falso positivo: pt / (1 − pt)

    return pd.DataFrame({
        "limiar": limiares,
        "modelo": vp / n - (fp / n) * razao,
        "tratar_todos": prevalencia - (1 - prevalencia) * razao,
        "tratar_ninguem": np.zeros_like(limiares),
    })


def _reamostra_estratificada(rng: np.random.Generator, grupos: list[np.ndarray]) -> np.ndarray:
    """Sorteia com reposição, dentro de cada grupo, o mesmo tamanho do grupo. Devolve índices."""
    partes = [g[rng.integers(0, len(g), size=len(g))] for g in grupos if len(g) > 0]
    return np.concatenate(partes) if partes else np.empty(0, dtype=np.int64)


def bootstrap_ci(fn, y, p, n: int, seed: int) -> tuple[float, float, float]:
    """Estimativa e IC 95% percentílico por bootstrap estratificado por `y`.

    `fn(y, p) -> float`. Cada reamostra mantém o nº de positivos e de negativos do conjunto
    original. Devolve (estimativa, ic_inf, ic_sup).
    """
    y_arr = np.asarray(y)
    p_arr = np.asarray(p)
    rng = np.random.default_rng(seed)
    grupos = [np.flatnonzero(y_arr == v) for v in np.unique(y_arr)]

    estatisticas = np.empty(n, dtype=float)
    for b in range(n):
        idx = _reamostra_estratificada(rng, grupos)
        estatisticas[b] = fn(y_arr[idx], p_arr[idx])

    ic_inf, ic_sup = np.quantile(estatisticas, _QUANTIS_IC)
    return float(fn(y_arr, p_arr)), float(ic_inf), float(ic_sup)


def paired_bootstrap_diff(
    fn, y, p_a, p_b, dobra, n: int, seed: int
) -> tuple[float, float, float]:
    """Diferença pareada `fn(modelo A) − fn(modelo B)`, média das dobras, com IC 95% (D-53).

    Em cada reamostra, para cada dobra, sorteia **os mesmos índices** para os dois modelos,
    estratificado por dobra e alvo (`y`). Calcula `fn` em cada dobra, tira a média das dobras e
    guarda `média_a − média_b`. Devolve (diferença na amostra original, ic_inf, ic_sup).
    """
    y_arr = np.asarray(y)
    a = np.asarray(p_a)
    b = np.asarray(p_b)
    d_arr = np.asarray(dobra)
    if not (len(y_arr) == len(a) == len(b) == len(d_arr)):
        raise ValueError("y, p_a, p_b e dobra precisam ter o mesmo tamanho")

    rng = np.random.default_rng(seed)
    dobras = list(dict.fromkeys(d_arr.tolist()))  # ordem de primeira aparição, sem repetir
    grupos_por_dobra = []
    for d in dobras:
        idx_d = np.flatnonzero(d_arr == d)
        grupos_por_dobra.append(
            [idx_d[y_arr[idx_d] == v] for v in np.unique(y_arr[idx_d])]
        )

    def diferenca_media(indices_por_dobra) -> float:
        medias_a = [fn(y_arr[ix], a[ix]) for ix in indices_por_dobra]
        medias_b = [fn(y_arr[ix], b[ix]) for ix in indices_por_dobra]
        return float(np.mean(medias_a) - np.mean(medias_b))

    estimativa = diferenca_media([np.flatnonzero(d_arr == d) for d in dobras])

    diferencas = np.empty(n, dtype=float)
    for k in range(n):
        indices = [_reamostra_estratificada(rng, grupos) for grupos in grupos_por_dobra]
        diferencas[k] = diferenca_media(indices)

    ic_inf, ic_sup = np.quantile(diferencas, _QUANTIS_IC)
    return estimativa, float(ic_inf), float(ic_sup)
