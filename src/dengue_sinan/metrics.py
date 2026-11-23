"""Métricas de avaliação (T-2.4, plan › Incerteza e comparação, D-33, D-39, D-53).

Funções puras: recebem arrays de rótulo `y` (0/1) e de probabilidade `p`, nunca DataFrame de
microdados. Por isso não chamam `assert_dev_only` (guard.py): quem chama é que escolhe os dados
(R1). Nenhuma função usa pesos de classe (R3) nem semente global: a semente entra por parâmetro
(R8).

Convenções:
- Um caso é "alto risco" quando `p >= limiar` (spec › Critérios de sucesso, FR-08).
- Divisão por zero em precisão, recall e F-beta devolve 0.0.
"""

import multiprocessing
from collections.abc import Iterator
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from multiprocessing import shared_memory
from typing import Any

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


def threshold_for_min_recall(y, p, recall_min: float) -> float:
    """Limiar de maior precisão entre os que dão recall ≥ `recall_min` (D-92).

    Candidatos: valores únicos de `p` (predito positivo se `p >= limiar`). Entre os que atingem o
    recall mínimo, devolve o de maior precisão. Empate de precisão: o MAIOR limiar. Sem folga:
    recall igual a `recall_min` já conta.

    `recall_min` precisa estar em [0, 1]. Com 1 é sempre atingível (o menor valor de `p` pega
    todos os eventos). Sem eventos o recall não é definido e a função levanta ValueError.
    Escolha do limiar só nas predições fora da dobra (FR-17), nunca no teste (R1, P2).
    """
    y_arr = np.asarray(y)
    p_arr = np.asarray(p, dtype=float)
    if p_arr.size == 0:
        raise ValueError("p vazio: não há limiar a escolher")
    if y_arr.shape != p_arr.shape:
        raise ValueError("y e p precisam ter o mesmo tamanho")
    if not 0.0 <= recall_min <= 1.0:  # também recusa NaN
        raise ValueError(f"recall_min precisa estar em [0, 1]: {recall_min}")
    if not (y_arr == 1).any():
        raise ValueError("sem eventos: o recall não é definido, não há limiar a escolher")

    candidatos = np.unique(p_arr)  # ordenados de forma crescente
    vp, fp, total_pos = _contagens(y_arr, p_arr, candidatos)
    recall = vp / total_pos
    precisao = vp / (vp + fp)  # vp + fp >= 1: cada candidato é um valor de p
    precisao_valida = np.where(recall >= recall_min, precisao, -np.inf)
    # Empate: np.flatnonzero devolve índices crescentes; o último é o maior limiar.
    empatados = np.flatnonzero(precisao_valida == precisao_valida.max())
    return float(candidatos[empatados[-1]])


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


# --- Bootstrap pareado vetorizado para a PR-AUC (T-4.9, D-53) ---------------------------------
#
# `paired_bootstrap_diff` chama `average_precision_score` em cada dobra e em cada reamostra: com
# 2,45 M de linhas isso custa ~3 s por reamostra e por modelo. A função abaixo chega ao mesmo
# resultado sem reordenar a cada reamostra:
# - uma reamostra com reposição, estratificada por (dobra, alvo), equivale a dar a cada linha um
#   peso igual ao nº de vezes em que foi sorteada (`np.bincount`). A PR-AUC depende só dos pesos;
# - a ordem decrescente por escore é calculada uma vez por modelo e dobra; na reamostra, os pesos
#   são só reordenados e somados (inteiros, portanto exatos: `cumsum` nos fins dos grupos de
#   escore igual, como o sklearn trata os empates);
# - os sorteios seguem a mesma sequência de `paired_bootstrap_diff` (mesma semente, mesma ordem de
#   chamadas ao gerador) e valem para todos os modelos: o mesmo sorteio vale para todos os pares.


def _ordenar_por_escore(p: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Ordem decrescente do escore, fins dos grupos de escore igual e o `y` ordenado."""
    ordem = np.argsort(-p, kind="stable")
    ordenado = p[ordem]
    fins = np.concatenate((np.flatnonzero(ordenado[1:] != ordenado[:-1]), [len(p) - 1]))
    return ordem, fins, y[ordem]


def _pr_auc_com_pesos(pesos: np.ndarray, fins: np.ndarray, y_ordenado: np.ndarray) -> float:
    """PR-AUC (average precision) das linhas com `pesos` inteiros, já na ordem por escore.

    Igual a `average_precision_score` do sklearn: Σ_g (VP_g / P) · precisão_g, com g os grupos de
    escore igual; VP e a contagem acumulada saem de `cumsum` lido nos fins dos grupos. Peso 0 é
    linha ausente da reamostra.
    """
    vp = np.cumsum(pesos * y_ordenado)[fins]
    total = np.cumsum(pesos)[fins]
    positivos = vp[-1]
    ganho = np.diff(vp, prepend=0)
    precisao = np.divide(vp, total, out=np.zeros(vp.shape, dtype=float), where=total > 0)
    return float(np.dot(ganho, precisao) / positivos)


def paired_bootstrap_pr_auc(
    escores: dict[str, np.ndarray], y, dobra, n: int, seed: int
) -> dict:
    """PR-AUC por dobra em `n` reamostras, para vários modelos, com os MESMOS sorteios (D-53).

    Mesma semântica de `paired_bootstrap_diff(pr_auc, ...)`: em cada reamostra e em cada dobra,
    sorteia com reposição, dentro de cada classe de `y`, o mesmo nº de linhas; a PR-AUC da dobra
    sai da reamostra; todos os modelos usam os mesmos índices. Com a mesma semente e os mesmos
    dados, a diferença das médias por reamostra é a de `paired_bootstrap_diff` (teste de
    concordância em `tests/test_metrics.py`).

    Devolve:
    - `dobras`: as dobras na ordem de primeira aparição (a mesma de `paired_bootstrap_diff`);
    - `por_dobra`: por modelo, array (n, nº de dobras) com a PR-AUC de cada dobra em cada reamostra;
    - `media`: por modelo, array (n,) com a média das dobras em cada reamostra.

    Levanta ValueError se algum tamanho não bate, se não há modelo ou se uma dobra não tem positivo
    (a PR-AUC não é definida).
    """
    y_arr = np.asarray(y).astype(np.int64)
    d_arr = np.asarray(dobra)
    if not escores:
        raise ValueError("nenhum modelo para o bootstrap")
    if len(d_arr) != len(y_arr):
        raise ValueError("y e dobra precisam ter o mesmo tamanho")
    for nome, p in escores.items():
        if len(p) != len(y_arr):
            raise ValueError(f"{nome}: y, p e dobra precisam ter o mesmo tamanho")

    rng = np.random.default_rng(seed)
    dobras = list(dict.fromkeys(d_arr.tolist()))  # ordem de primeira aparição
    grupos_por_dobra: list[list[np.ndarray]] = []
    tamanhos: list[int] = []
    estruturas: dict[str, list[tuple[np.ndarray, np.ndarray, np.ndarray]]] = {
        nome: [] for nome in escores
    }
    for d in dobras:
        idx_d = np.flatnonzero(d_arr == d)
        y_d = y_arr[idx_d]
        if not (y_d == 1).any():
            raise ValueError(f"dobra {d!r} sem positivos: a PR-AUC não é definida")
        tamanhos.append(len(idx_d))
        # Grupos por classe, na ordem de np.unique (a de paired_bootstrap_diff), em posições
        # locais da dobra.
        grupos_por_dobra.append([np.flatnonzero(y_d == v) for v in np.unique(y_d)])
        for nome, p in escores.items():
            p_d = np.asarray(p, dtype=float)[idx_d]
            estruturas[nome].append(_ordenar_por_escore(p_d, y_d))

    por_dobra = {nome: np.empty((n, len(dobras)), dtype=float) for nome in escores}
    for k in range(n):
        contagens = []
        for indice, grupos in enumerate(grupos_por_dobra):
            cnt = np.zeros(tamanhos[indice], dtype=np.int64)
            for g in grupos:  # a mesma ordem de chamadas de paired_bootstrap_diff
                cnt += np.bincount(g[rng.integers(0, len(g), size=len(g))],
                                   minlength=tamanhos[indice])
            contagens.append(cnt)
        for nome, lista in estruturas.items():
            for indice, (ordem, fins, y_ord) in enumerate(lista):
                por_dobra[nome][k, indice] = _pr_auc_com_pesos(
                    contagens[indice][ordem], fins, y_ord)

    return {
        "dobras": dobras,
        "por_dobra": por_dobra,
        "media": {nome: arr.mean(axis=1) for nome, arr in por_dobra.items()},
    }


# --- Métricas com pesos para o teste (T-5.1, D-93) --------------------------------------------
#
# A avaliação final tem 5,3 milhões de linhas e o bootstrap é real (1.000 reamostras). Três ideias,
# todas exatas (a distribuição das estatísticas é a do bootstrap de linhas):
# - cada reamostra é um vetor de pesos (quantas vezes cada linha foi sorteada) e as métricas são
#   calculadas com esses pesos, sem reconstruir os dados;
# - linhas idênticas (mesmo alvo e mesmas predições) formam uma CÉLULA, e o sorteio é multinomial
#   sobre as células (`agrupar_celulas`, `Sorteio`): a soma dos pesos de linhas sorteadas com
#   reposição, dentro de uma célula, tem a mesma distribuição que o peso sorteado para a célula;
# - PR-AUC e ROC dependem só dos positivos e de quantos negativos há ENTRE eles na ordem por escore:
#   os negativos viram contagens por "vão" (`ordenar`, `bins`), lidas com um `bincount` sem ordenar
#   nada a cada reamostra. É uma reformulação exata do mesmo cálculo, valendo para qualquer vetor
#   de pesos, e por isso o pareamento entre modelos (D-53) é preservado.


@dataclass(frozen=True)
class Celulas:
    """Linhas agrupadas por valores idênticos. As células com y = 0 vêm primeiro.

    `contagem`: nº de linhas de cada célula; `y`: alvo da célula; `colunas`: valor de cada coluna
    agrupada na célula; `n_negativas`: quantas células têm y = 0.
    """

    contagem: np.ndarray
    y: np.ndarray
    colunas: dict[str, np.ndarray]
    n_negativas: int

    def __len__(self) -> int:
        return len(self.contagem)


def agrupar_celulas(y, colunas: dict[str, np.ndarray]) -> Celulas:
    """Agrupa as linhas por (y, *colunas). Cada coluna tem o tamanho de `y`. Levanta ValueError
    se `y` não for 0/1, se estiver vazio ou se algum tamanho não bater."""
    y_arr = np.asarray(y).astype(np.int64)
    if y_arr.ndim != 1 or y_arr.size == 0:
        raise ValueError("y precisa ser um vetor não vazio")
    if not np.isin(y_arr, (0, 1)).all():
        raise ValueError("y precisa ser 0 ou 1")
    quadro = {"__y__": y_arr}
    for nome, valores in colunas.items():
        valores = np.asarray(valores)
        if valores.shape != y_arr.shape:
            raise ValueError(f"{nome}: tamanho diferente de y")
        quadro[nome] = valores
    ids = pd.DataFrame(quadro).groupby(list(quadro), sort=False, dropna=False).ngroup().to_numpy()
    n_celulas = int(ids.max()) + 1
    contagem = np.bincount(ids, minlength=n_celulas).astype(np.int64)
    _, primeiro = np.unique(ids, return_index=True)  # primeira linha de cada célula
    primeiro = primeiro[np.argsort(y_arr[primeiro], kind="stable")]  # y = 0 primeiro
    # A contagem acompanha a mesma ordem: refaz a partir do id da primeira linha.
    contagem = contagem[ids[primeiro]]
    y_celula = y_arr[primeiro]
    return Celulas(contagem=contagem, y=y_celula,
                   colunas={nome: np.asarray(v)[primeiro] for nome, v in colunas.items()},
                   n_negativas=int((y_celula == 0).sum()))


class Sorteio:
    """Reamostra com reposição, estratificada por y, de linhas agrupadas em células.

    Cada reamostra sorteia, para cada classe, tantas linhas quantas a classe tem; o peso de uma
    célula é o nº de linhas sorteadas nela, multinomial com probabilidade proporcional à
    contagem. Custo O(#células). Quando todas as células de uma classe têm 1 linha (sem
    repetição), o sorteio é direto (`integers` + `bincount`, a mesma distribuição, ~2× mais rápido).
    """

    def __init__(self, contagem: np.ndarray, n_negativas: int) -> None:
        c = np.asarray(contagem, dtype=np.int64)
        self._n0 = int(n_negativas)
        self._tamanho = len(c)
        self._classes = []  # por classe: (fatia, linhas da classe, pvals ou None se todas têm 1)
        for fatia in (slice(0, self._n0), slice(self._n0, len(c))):
            parte = c[fatia]
            linhas = int(parte.sum())
            if linhas == 0:
                continue
            pvals = None if (parte == 1).all() else parte / linhas
            self._classes.append((fatia, linhas, pvals))

    def __call__(self, rng: np.random.Generator, saida: np.ndarray | None = None) -> np.ndarray:
        """Pesos (float64) de uma reamostra. `saida` reaproveita um vetor já alocado."""
        w = np.empty(self._tamanho, dtype=np.float64) if saida is None else saida
        for fatia, linhas, pvals in self._classes:
            if pvals is None:  # células de 1 linha: `linhas` sorteios entre as `linhas` células
                w[fatia] = np.bincount(rng.integers(0, linhas, size=linhas), minlength=linhas)
            else:
                w[fatia] = rng.multinomial(linhas, pvals)
        return w


def sementes_das_reamostras(seed: int, n: int) -> list[np.random.SeedSequence]:
    """Uma sub-semente por reamostra (`SeedSequence(seed).spawn(n)`). A reamostra k usa sempre a
    k-ésima, qualquer que seja o nº de processos: o resultado não depende do paralelismo (R8)."""
    return np.random.SeedSequence(seed).spawn(n)


def fluxo(semente: np.random.SeedSequence, indice: int) -> np.random.Generator:
    """Gerador do `indice`-ésimo fluxo de uma sub-semente, sem alterar o objeto recebido."""
    return np.random.default_rng(np.random.SeedSequence(
        entropy=semente.entropy, spawn_key=(*semente.spawn_key, indice)))


class MemoriaCompartilhada:
    """Arrays em memória compartilhada: os processos do bootstrap leem sem copiar.

    Uso: `with MemoriaCompartilhada(arrays) as mem:` e passe `mem.descritor` (pequeno, picklável)
    aos processos, que chamam `abrir_compartilhada`. Ao sair do bloco os blocos são liberados.
    Com `consumir=True`, cada array é retirado do dict `arrays` depois de copiado, para o pico de
    memória não somar as duas cópias (quem chama não pode mais guardar outra referência a eles).
    """

    def __init__(self, arrays: dict[str, np.ndarray], consumir: bool = False) -> None:
        self._blocos: list[shared_memory.SharedMemory] = []
        self.descritor: dict[str, tuple[str, tuple, str]] = {}
        try:
            for nome in list(arrays):
                a = np.ascontiguousarray(arrays.pop(nome) if consumir else arrays[nome])
                bloco = shared_memory.SharedMemory(create=True, size=max(a.nbytes, 1))
                self._blocos.append(bloco)
                destino = np.ndarray(a.shape, dtype=a.dtype, buffer=bloco.buf)
                destino[...] = a
                del destino
                self.descritor[nome] = (bloco.name, a.shape, a.dtype.str)
        except BaseException:
            self.fechar()
            raise

    def fechar(self) -> None:
        for bloco in self._blocos:
            try:
                bloco.close()
                bloco.unlink()
            except (FileNotFoundError, BufferError):
                pass
        self._blocos = []

    def __enter__(self) -> "MemoriaCompartilhada":
        return self

    def __exit__(self, *args) -> None:
        self.fechar()


def abrir_compartilhada(descritor: dict) -> tuple[dict[str, np.ndarray],
                                                   list[shared_memory.SharedMemory]]:
    """Abre os blocos de `MemoriaCompartilhada.descritor` como arrays somente leitura. Devolve os
    arrays e os blocos (quem chama guarda os blocos enquanto usar os arrays)."""
    arrays, blocos = {}, []
    for nome, (bloco_nome, forma, tipo) in descritor.items():
        try:
            bloco = shared_memory.SharedMemory(name=bloco_nome, track=False)
        except TypeError:  # Python < 3.13: sem `track`
            bloco = shared_memory.SharedMemory(name=bloco_nome)
        blocos.append(bloco)
        a = np.ndarray(forma, dtype=np.dtype(tipo), buffer=bloco.buf)
        a.flags.writeable = False
        arrays[nome] = a
    return arrays, blocos


@dataclass(frozen=True)
class Ordenado:
    """Um modelo preparado uma vez para o bootstrap de pesos (linhas ou células).

    - `y`, `p`, `x` (logit de `p`, limitado), `x2` (x²), `ex` (e^x) e `erro2` ((p − y)²): vetores
      fixos, na ordem dos dados, usados nas somas ponderadas (Brier, observado/esperado e
      calibração);
    - `bins`: para cada elemento negativo, em que "vão" cai. Seja v₀ > v₁ > … o escore dos grupos
      com positivo, em ordem decrescente: bin 2g = negativos com escore entre v_{g−1} e v_g (acima
      de v_g e abaixo de v_{g−1}); bin 2g + 1 = negativos empatados com v_g. Positivos vão para o
      último bin (descartado);
    - `pos_idx`, `pos_grupo`: onde estão os positivos e a que grupo (g) cada um pertence.
    """

    y: np.ndarray
    p: np.ndarray
    x: np.ndarray
    x2: np.ndarray
    ex: np.ndarray
    erro2: np.ndarray
    bins: np.ndarray
    pos_idx: np.ndarray
    pos_grupo: np.ndarray
    n_grupos: int
    n_bins: int

    def grandes(self) -> dict[str, np.ndarray]:
        """Os vetores do tamanho dos dados (os que vão para a memória compartilhada)."""
        return {"y": self.y, "p": self.p, "x": self.x, "x2": self.x2, "ex": self.ex,
                "erro2": self.erro2, "bins": self.bins}

    @classmethod
    def montar(cls, grandes: dict[str, np.ndarray], pos_idx: np.ndarray, pos_grupo: np.ndarray,
               n_grupos: int, n_bins: int) -> "Ordenado":
        return cls(pos_idx=pos_idx, pos_grupo=pos_grupo, n_grupos=n_grupos, n_bins=n_bins,
                   **grandes)

    def pequenos(self) -> tuple[np.ndarray, np.ndarray, int, int]:
        return self.pos_idx, self.pos_grupo, self.n_grupos, self.n_bins


def ordenar(p, y) -> Ordenado:
    """Prepara `p` (escore ou probabilidade) e `y` (0/1) para `*_pesos`. Levanta ValueError se
    os tamanhos não baterem ou se algum escore não for finito."""
    p_arr = np.asarray(p, dtype=float)
    y_arr = np.asarray(y).astype(np.int64)
    if p_arr.shape != y_arr.shape or p_arr.ndim != 1:
        raise ValueError("p e y precisam ser vetores do mesmo tamanho")
    if p_arr.size == 0 or not np.isfinite(p_arr).all():
        raise ValueError("p vazio ou com valor não finito")
    if not np.isin(y_arr, (0, 1)).all():
        raise ValueError("y precisa ser 0 ou 1")
    pos = np.flatnonzero(y_arr == 1)
    valores = np.unique(p_arr[pos])  # escores dos grupos com positivo, em ordem crescente
    g = len(valores)
    bins = np.full(len(p_arr), 2 * g + 1, dtype=np.intp)
    neg = np.flatnonzero(y_arr == 0)
    if g > 0 and len(neg) > 0:
        s = p_arr[neg]
        direita = np.searchsorted(valores, s, side="right")  # nº de valores <= s
        esquerda = np.searchsorted(valores, s, side="left")  # nº de valores < s
        bins[neg] = 2 * (g - direita) + (direita > esquerda)  # acima: g - direita; empate: +1
    pos_grupo = (g - 1 - np.searchsorted(valores, p_arr[pos])).astype(np.intp)
    p_limitado = np.clip(p_arr, _EPS_PROBABILIDADE, 1 - _EPS_PROBABILIDADE)
    ex = p_limitado / (1 - p_limitado)
    x = np.log(ex)
    return Ordenado(y=y_arr.astype(np.float64), p=p_arr, x=x, x2=x * x, ex=ex,
                    erro2=(p_arr - y_arr) ** 2, bins=bins, pos_idx=pos, pos_grupo=pos_grupo,
                    n_grupos=g, n_bins=2 * g + 2)


def pesos_estratificados(y, n: int, seed: int) -> Iterator[np.ndarray]:
    """`n` reamostras com reposição, estratificadas por `y`, como vetores de pesos inteiros.

    Referência por linha (a de `paired_bootstrap_pr_auc`, mesma semente e mesma sequência de
    sorteios): cada reamostra é um vetor (float) em que o peso de cada linha é o nº de vezes em que
    foi sorteada. O bootstrap da avaliação usa `Sorteio` (células, uma sub-semente por reamostra).
    """
    y_arr = np.asarray(y)
    rng = np.random.default_rng(seed)
    grupos = [np.flatnonzero(y_arr == v) for v in np.unique(y_arr)]
    for _ in range(n):
        w = np.zeros(len(y_arr), dtype=np.float64)
        for g in grupos:
            sorteio = rng.integers(0, len(g), size=len(g))
            w[g] += np.bincount(sorteio, minlength=len(g))
        yield w


def _acumular(w: np.ndarray, o: Ordenado) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Pesos dos positivos por grupo e dos negativos por vão e por empate (ver `Ordenado`)."""
    g = o.n_grupos
    por_bin = np.bincount(o.bins, weights=w, minlength=o.n_bins)
    positivos = np.bincount(o.pos_grupo, weights=w[o.pos_idx], minlength=g)
    return positivos, por_bin[0:2 * g + 1:2], por_bin[1:2 * g:2]


def pr_auc_pesos(w: np.ndarray, o: Ordenado) -> float:
    """PR-AUC com os pesos `w` (na ordem dos dados). Mesma regra de `pr_auc`.

    Σ_g (VP_g / P) · precisão_g sobre os grupos de escore com positivo; os negativos acima de cada
    grupo e empatados com ele saem dos vãos (`Ordenado`). Grupos só de negativos têm ganho zero e
    não entram. Levanta ValueError se a reamostra não tem positivo.
    """
    pos, vao, empate = _acumular(w, o)
    vp = np.cumsum(pos)
    total_positivos = float(vp[-1]) if vp.size else 0.0
    if not total_positivos > 0:
        raise ValueError("PR-AUC não definida: a reamostra não tem positivos")
    negativos_ate_g = np.cumsum(vao)[:-1] + np.cumsum(empate)  # inclui os empatados com g
    total = vp + negativos_ate_g
    precisao = np.divide(vp, total, out=np.zeros(vp.shape, dtype=float), where=total > 0)
    return float(np.dot(pos, precisao) / total_positivos)


def roc_auc_pesos(w: np.ndarray, o: Ordenado) -> float:
    """ROC-AUC com pesos: P(escore de positivo > escore de negativo) + ½ P(empate).

    Para cada grupo de positivos, conta os negativos com escore menor (e metade dos empatados).
    Levanta ValueError sem positivo ou sem negativo: a ROC-AUC não é definida.
    """
    pos, vao, empate = _acumular(w, o)
    total_positivos = float(pos.sum())
    total_negativos = float(vao.sum() + empate.sum())
    if not (total_positivos > 0 and total_negativos > 0):
        raise ValueError("ROC-AUC não definida: a reamostra não tem positivos e negativos")
    negativos_ate_g = np.cumsum(vao)[:-1] + np.cumsum(empate)
    abaixo = total_negativos - negativos_ate_g + empate / 2.0
    return float(np.dot(pos, abaixo) / (total_positivos * total_negativos))


def brier_pesos(w: np.ndarray, o: Ordenado) -> float:
    """Brier com pesos: Σ w (p − y)² / Σ w (média ponderada, um produto escalar)."""
    return float(np.dot(w, o.erro2) / float(w.sum()))


def obs_esp_pesos(w: np.ndarray, o: Ordenado) -> float:
    """Razão observado/esperado com pesos: Σ w y / Σ w p (eventos observados sobre a soma das
    probabilidades previstas). Ideal = 1. NaN se a soma das previsões for zero."""
    esperado = float(np.dot(w, o.p))
    return float(np.dot(w, o.y)) / esperado if esperado > 0 else float("nan")


class Limiarizado:
    """Um limiar de um modelo, com os vetores fixos pré-calculados (T-5.1).

    `marcado` é o bool de `p >= limiar`, na ordem dos dados (linhas ou células). `metricas(w)`
    calcula acurácia, precisão, recall, F1 e F2 com os pesos `w`: equivale a `threshold_metrics`
    com cada linha repetida `w` vezes, mas sem recriar os vetores a cada reamostra. Com as células
    de `agrupar_celulas(y, flags)` (no máximo 2 × 2^k células para k modelos) cada reamostra custa
    O(#células), não O(#linhas).
    """

    def __init__(self, y, marcado) -> None:
        y_f = np.asarray(y, dtype=np.float64)
        m_f = np.asarray(marcado, dtype=np.float64)
        self._y = y_f
        self._m = m_f
        self._ym = y_f * m_f

    def metricas(self, w: np.ndarray) -> dict:
        n = float(w.sum())
        positivos = float(np.dot(w, self._y))
        marcados = float(np.dot(w, self._m))
        vp = float(np.dot(w, self._ym))
        fp = marcados - vp
        fn = positivos - vp
        tn = n - positivos - fp
        precisao = vp / marcados if marcados > 0 else 0.0
        recall = vp / positivos if positivos > 0 else 0.0
        return {
            "acuracia": (vp + tn) / n,
            "precisao": precisao,
            "recall": recall,
            "f1": float(_fbeta(vp, fp, fn, beta=1.0)),
            "f2": float(_fbeta(vp, fp, fn, beta=2.0)),
            "vp": vp,
            "marcados": marcados,
        }


def threshold_pesos(w: np.ndarray, y: np.ndarray, marcado: np.ndarray) -> dict:
    """Acurácia, precisão, recall, F1 e F2 com pesos (ver `Limiarizado`)."""
    return Limiarizado(y, marcado).metricas(w)


_MAX_ITERACOES_NEWTON = 50
_TOL_NEWTON = 1e-9
_MAX_ITERACOES_AMORTECIDO = 200  # Newton amortecido (só se o puro falhar)
_RETROCESSOS = 40  # reduções do passo (×½) na busca linear
_MASSA_ERRO_MINIMA = 1e-6  # abaixo disto o ajuste é separação perfeita, não um máximo
# Passo máximo por iteração. Longe da solução, o Newton de uma logística pode dar passos enormes
# quando há logits muito negativos (ex.: −20): limitar o passo não muda o ponto de convergência,
# só impede que a iteração salte para longe. Perto da solução o passo é menor que o limite.
_PASSO_MAXIMO_NEWTON = 2.0


_BLOCO_CALIBRACAO = 8192  # elementos por bloco: 7 vetores de 64 KB cabem na cache L2 do núcleo


class Trabalho:
    """Três vetores de trabalho de um bloco, reaproveitados por todos os modelos de um processo (a
    calibração não aloca nada por iteração)."""

    def __init__(self, bloco: int = _BLOCO_CALIBRACAO) -> None:
        self.e = np.empty(bloco, dtype=np.float64)
        self.p = np.empty(bloco, dtype=np.float64)
        self.q = np.empty(bloco, dtype=np.float64)


class Calibracao:
    """Slope e intercepto de calibração com pesos, por Newton com início quente (T-5.1).

    Mesmas definições de `calibration_slope_intercept`: o slope é o coeficiente de logit(p) numa
    logística de y com intercepto; o intercepto é o da logística com logit(p) como offset. Cada
    reamostra parte da solução da amostra inteira e converge em poucas iterações. Se não
    convergir dentro do limite, levanta RuntimeError: nunca devolve um número parcial.

    Custo por iteração: o gradiente usa só a soma ponderada de p (a parte de y é uma soma sobre os
    positivos, calculada uma vez por ajuste), e o intercepto usa e^x pré-calculado
    (σ(x + a) = t / (1 + t), t = e^x e^a), sem `exp` por iteração. Os dados são percorridos em
    blocos de `bloco` elementos: todas as contas de um bloco acontecem na cache do núcleo, e os
    vetores grandes são lidos uma vez por iteração (as contas por bloco são as mesmas, só a ordem
    das somas muda, e é a mesma em qualquer processo).
    """

    def __init__(self, x: np.ndarray, y: np.ndarray, *, x2: np.ndarray | None = None,
                 ex: np.ndarray | None = None, pos_idx: np.ndarray | None = None,
                 trabalho: Trabalho | None = None, bloco: int = _BLOCO_CALIBRACAO) -> None:
        self._x = np.ascontiguousarray(x, dtype=np.float64)
        x2 = self._x * self._x if x2 is None else x2
        ex = np.exp(self._x) if ex is None else ex
        y_f = np.asarray(y, dtype=np.float64)
        self._pos = np.flatnonzero(y_f == 1) if pos_idx is None else pos_idx
        self._x_pos = self._x[self._pos]
        tr = Trabalho(bloco) if trabalho is None else trabalho
        n = len(self._x)
        self._fatias = [slice(i, min(i + bloco, n)) for i in range(0, n, bloco)]
        self._xs = [self._x[s] for s in self._fatias]
        self._x2s = [x2[s] for s in self._fatias]
        self._exs = [ex[s] for s in self._fatias]
        self._bufs = [(tr.e[: s.stop - s.start], tr.p[: s.stop - s.start],
                       tr.q[: s.stop - s.start]) for s in self._fatias]
        self.iteracoes_slope = 0
        self.iteracoes_intercepto = 0

    def slope_e_intercepto(self, w: np.ndarray, inicio: tuple[float, float, float] = (0.0, 1.0, 0.0)
                           ) -> tuple[float, float, float]:
        """(intercepto livre, slope, intercepto de calibração) com pesos `w`.

        `inicio` = (intercepto livre, slope, intercepto de calibração) de partida. Os dois ajustes
        são de modelos diferentes (o do slope tem dois parâmetros; o do intercepto fixa o
        coeficiente em 1), então não dividem as contas por iteração: dividem os pesos, os
        vetores fixos e a memória de trabalho.
        """
        a, b = self.slope_intercepto(w, (inicio[0], inicio[1]))
        return a, b, self.intercepto(w, inicio=inicio[2])

    def slope_intercepto(self, w: np.ndarray,
                         inicio: tuple[float, float] = (0.0, 1.0)) -> tuple[float, float]:
        """(intercepto, slope) do ajuste com pesos `w`; `inicio` = (intercepto, slope).

        Newton puro (rápido). Se ele não convergir ou o Hessiano degenerar, repete o ajuste com
        Newton amortecido (busca linear com retrocesso na log-verossimilhança, até 200
        iterações), que cobre probabilidades exatamente 0 ou 1 (calibrador isotônico) e pontos
        de partida ruins. Sem convergir mesmo assim, levanta o erro: nunca devolve número parcial.
        """
        w_pos = w[self._pos]
        soma_y = float(w_pos.sum())  # Σ w y  (y só é 1 nos positivos)
        soma_xy = float(np.dot(w_pos, self._x_pos))  # Σ w y x
        dados = list(zip([w[s] for s in self._fatias], self._xs, self._x2s, self._bufs,
                         strict=True))
        try:
            return self._newton_slope(dados, soma_y, soma_xy, w_pos, inicio, amortecido=False)
        except (RuntimeError, ValueError):
            return self._newton_slope(dados, soma_y, soma_xy, w_pos, inicio, amortecido=True)

    def _somas_slope(self, dados: list, a: float, b: float) -> tuple[float, ...]:
        """(Σq, Σqx, Σqx², Σqp, Σqpx, Σqpx²) com q = w p e p = σ(a + b x)."""
        sq = sqx = sqx2 = sqp = sqpx = sqpx2 = 0.0
        for wb, xb, x2b, (e, p, q) in dados:
            np.multiply(xb, -b, out=e)
            e -= a
            np.exp(e, out=e)
            e += 1.0
            np.reciprocal(e, out=p)  # p = σ(a + b x)
            np.multiply(wb, p, out=q)  # q = w p
            sq += q.sum()
            sqx += np.dot(q, xb)
            sqx2 += np.dot(q, x2b)
            np.multiply(q, p, out=e)  # w p²
            sqp += e.sum()
            sqpx += np.dot(e, xb)
            sqpx2 += np.dot(e, x2b)
        return sq, sqx, sqx2, sqp, sqpx, sqpx2

    def _logver_slope(self, dados: list, soma_y: float, soma_xy: float, a: float,
                      b: float) -> float:
        """Log-verossimilhança Σ w [y z − log(1 + e^z)], z = a + b x (só usada no amortecido)."""
        total = a * soma_y + b * soma_xy
        for wb, xb, _, (e, _p, _q) in dados:
            np.multiply(xb, b, out=e)
            e += a
            np.logaddexp(0.0, e, out=e)
            total -= float(np.dot(wb, e))
        return total

    def _newton_slope(self, dados: list, soma_y: float, soma_xy: float, w_pos: np.ndarray,
                      inicio: tuple[float, float], *, amortecido: bool) -> tuple[float, float]:
        a, b = inicio
        for it in range(1, (_MAX_ITERACOES_AMORTECIDO if amortecido else _MAX_ITERACOES_NEWTON)
                        + 1):
            sq, sqx, sqx2, sqp, sqpx, sqpx2 = self._somas_slope(dados, a, b)
            g0, g1 = soma_y - sq, soma_xy - sqx  # gradiente: Σ w (y − p) [1, x]
            h00, h01, h11 = sq - sqp, sqx - sqpx, sqx2 - sqpx2  # Hessiano: Σ w p (1 − p) [1, x, x²]
            det = h00 * h11 - h01 * h01
            if not det > 0 or not np.isfinite(det):
                raise ValueError("calibração não identificável: escore constante ou degenerado")
            da = (h11 * g0 - h01 * g1) / det
            db = (-h01 * g0 + h00 * g1) / det
            # Reduz o passo inteiro (a direção é a do Newton). Limitar cada coordenada à parte
            # cria ciclos quando o passo é grande.
            fator = min(1.0, _PASSO_MAXIMO_NEWTON / max(abs(da), abs(db), 1e-300))
            da *= fator
            db *= fator
            if amortecido:
                logver = self._logver_slope(dados, soma_y, soma_xy, a, b)
                subida = g0 * da + g1 * db  # > 0: o Hessiano é definido positivo
                t = 1.0
                for _ in range(_RETROCESSOS):
                    novo = self._logver_slope(dados, soma_y, soma_xy, a + t * da, b + t * db)
                    if novo >= logver + 1e-4 * t * subida - 1e-12 * max(1.0, abs(logver)):
                        break
                    t *= 0.5
                else:
                    raise RuntimeError("slope de calibração não convergiu: a busca linear falhou")
                da *= t
                db *= t
            a += da
            b += db
            if max(abs(da), abs(db)) < _TOL_NEWTON:
                # Passo pequeno não basta: com separação perfeita a probabilidade satura em 0 ou
                # 1 e o passo some sem haver máximo. O MLE de um dado não separável deixa massa de
                # erro Σ_pos w(1 − p) + Σ_neg w p bem acima de zero; perto de 0 é separação.
                p_pos = 1.0 / (1.0 + np.exp(-(a + b * self._x_pos)))
                w_p_pos = float(np.dot(w_pos, p_pos))
                massa_de_erro = (soma_y - w_p_pos) + (sq - w_p_pos)
                if not massa_de_erro > _MASSA_ERRO_MINIMA:
                    raise RuntimeError("slope de calibração não convergiu: o escore separa os "
                                       "eventos (separação perfeita), não há máximo finito")
                self.iteracoes_slope = it
                return float(a), float(b)
        raise RuntimeError("slope de calibração não convergiu: revise o dado")

    def intercepto(self, w: np.ndarray, inicio: float = 0.0) -> float:
        """Intercepto (calibração-no-grande) com pesos `w`: logística com offset logit(p).

        Mesma estratégia do slope: Newton puro e, se falhar, Newton amortecido.
        """
        w_pos = w[self._pos]
        soma_y = float(w_pos.sum())
        soma_xy = float(np.dot(w_pos, self._x_pos))
        dados = list(zip([w[s] for s in self._fatias], self._exs, self._xs, self._bufs,
                         strict=True))
        try:
            return self._newton_intercepto(dados, soma_y, soma_xy, inicio, amortecido=False)
        except (RuntimeError, ValueError):
            return self._newton_intercepto(dados, soma_y, soma_xy, inicio, amortecido=True)

    def _logver_intercepto(self, dados: list, soma_y: float, soma_xy: float, a: float) -> float:
        total = a * soma_y + soma_xy
        for wb, _, xb, (e, _p, _q) in dados:
            np.add(xb, a, out=e)
            np.logaddexp(0.0, e, out=e)
            total -= float(np.dot(wb, e))
        return total

    def _newton_intercepto(self, dados: list, soma_y: float, soma_xy: float, inicio: float,
                           *, amortecido: bool) -> float:
        a = inicio
        for it in range(1, (_MAX_ITERACOES_AMORTECIDO if amortecido else _MAX_ITERACOES_NEWTON)
                        + 1):
            ea = float(np.exp(a))
            soma_p = h = 0.0
            for wb, exb, _, (e, p, q) in dados:
                np.multiply(exb, ea, out=e)  # t = e^x e^a
                np.add(e, 1.0, out=p)  # 1 + t
                np.divide(e, p, out=q)  # σ(x + a) = t / (1 + t)
                soma_p += np.dot(wb, q)
                np.divide(q, p, out=e)  # σ (1 − σ) = σ / (1 + t)
                h += np.dot(wb, e)
            g = soma_y - soma_p
            if not h > 0 or not np.isfinite(h):
                raise ValueError("intercepto de calibração não identificável")
            da = float(np.clip(g / h, -_PASSO_MAXIMO_NEWTON, _PASSO_MAXIMO_NEWTON))
            if amortecido:
                logver = self._logver_intercepto(dados, soma_y, soma_xy, a)
                subida = g * da
                t = 1.0
                for _ in range(_RETROCESSOS):
                    novo = self._logver_intercepto(dados, soma_y, soma_xy, a + t * da)
                    if novo >= logver + 1e-4 * t * subida - 1e-12 * max(1.0, abs(logver)):
                        break
                    t *= 0.5
                else:
                    raise RuntimeError(
                        "intercepto de calibração não convergiu: a busca linear falhou")
                da *= t
            a += da
            if abs(da) < _TOL_NEWTON:
                self.iteracoes_intercepto = it
                return float(a)
        raise RuntimeError("intercepto de calibração não convergiu: revise o dado")


# --- Cálculo das reamostras, em 1 ou vários processos (T-5.1, D-93, R8) ---------------------

# Vetores por modelo na memória compartilhada
CAMPOS_GRANDES = ("p", "x", "x2", "ex", "erro2", "bins")
_BLOCOS_POR_PROCESSO = 3  # blocos de reamostras por processo (equilibra o fim do trabalho)


class Reamostrador:
    """O que um processo precisa para calcular reamostras: os modelos ordenados, as calibrações, os
    sorteios e as células dos limiares. Construído uma vez por processo (no principal ou num
    trabalhador), a partir de arrays que podem estar em memória compartilhada.

    `grandes`: "contagem", "y" e, por modelo, "<modelo>/<campo>" para cada campo de
    `CAMPOS_GRANDES`. `meta` (pequeno, picklável): "nomes" (os modelos, na ordem),
    "metricas_limiar", "n_negativas", "modelos" (por modelo: pos_idx, pos_grupo, n_grupos,
    n_bins, constante) e "limiares" (contagem, n_negativas, y, marcados por nome).

    Chaves opcionais de `meta` (T-5.2, subgrupos):
    - "completo" (padrão True): com False, só PR-AUC, observado/esperado e calibração (sem ROC-AUC
      nem Brier), que é o que os subgrupos usam;
    - "tolerante" (padrão False): com True, um ajuste de slope ou intercepto que não converge
      (separação perfeita, escore degenerado) não derruba o cálculo: o ponto estimado fica
      indisponível e a reamostra é marcada em "<modelo>/calibracao_descartada" (1.0; 0.0 se
      converge) com slope e intercepto NaN. Nunca sai número parcial. Com False (T-5.1) o erro
      sobe, como sempre;
    - "fluxo" (padrão 0): índice-base dos fluxos da sub-semente (`fluxo(semente, base)` sorteia as
      células dos escores e `base + 1` as dos limiares), para subgrupos distintos não repetirem
      os mesmos números aleatórios."""

    def __init__(self, grandes: dict[str, np.ndarray], meta: dict) -> None:
        self.meta = meta
        self.completo = bool(meta.get("completo", True))
        self.tolerante = bool(meta.get("tolerante", False))
        self.fluxo_base = int(meta.get("fluxo", 0))
        self.nomes = tuple(meta["nomes"])
        self.metricas_limiar = tuple(meta["metricas_limiar"])
        self.contagem = grandes["contagem"]
        self.sorteio = Sorteio(self.contagem, meta["n_negativas"])
        self.pesos = np.empty(len(self.contagem), dtype=np.float64)
        trabalho = Trabalho()
        self.ordenados: dict[str, Ordenado] = {}
        self.calibracoes: dict[str, Calibracao] = {}
        for nome in self.nomes:
            m = meta["modelos"][nome]
            o = Ordenado.montar(
                {"y": grandes["y"], **{c: grandes[f"{nome}/{c}"] for c in CAMPOS_GRANDES}},
                m["pos_idx"], m["pos_grupo"], m["n_grupos"], m["n_bins"])
            self.ordenados[nome] = o
            self.calibracoes[nome] = Calibracao(
                o.x, o.y, x2=o.x2, ex=o.ex, pos_idx=o.pos_idx, trabalho=trabalho)
        limiares = meta["limiares"]
        self.contagem_limiares = limiares["contagem"]
        self.sorteio_limiares = Sorteio(limiares["contagem"], limiares["n_negativas"])
        self.limiarizados = {nome: Limiarizado(limiares["y"], marcado)
                             for nome, marcado in limiares["marcados"].items()}
        self.inicio: dict[str, tuple[float, float, float]] = meta.get("inicio", {})

    def liberar(self) -> None:
        """Solta os vetores grandes (no modo com processos, os trabalhadores têm os seus e o
        principal só espera)."""
        self.ordenados, self.calibracoes = {}, {}
        self.contagem = self.pesos = self.sorteio = None

    def pontos(self) -> tuple[dict, dict]:
        """Métricas na amostra original (pesos = contagem das células). Define o início quente do
        Newton de cada modelo. No modo tolerante, um ajuste de calibração que não converge deixa
        o slope (e o intercepto, se também falhar) como None e marca "calibracao_indisponivel"."""
        w = self.contagem.astype(np.float64)
        pontos: dict[str, dict] = {}
        for nome in self.nomes:
            o, c = self.ordenados[nome], self.calibracoes[nome]
            constante = self.meta["modelos"][nome]["constante"]
            indisponivel = False
            try:
                if constante:
                    livre, slope = 0.0, None
                    intercepto = c.intercepto(w)
                else:
                    livre, slope, intercepto = c.slope_e_intercepto(w)
            except (RuntimeError, ValueError):
                if not self.tolerante:
                    raise
                livre, slope, intercepto, indisponivel = 0.0, None, None, True
                try:  # o ajuste só do intercepto (offset) costuma convergir mesmo sem o slope
                    intercepto = c.intercepto(w)
                except (RuntimeError, ValueError):
                    pass
            self.inicio[nome] = (livre, 1.0 if slope is None else slope,
                                 0.0 if intercepto is None else intercepto)
            pontos[nome] = {
                "pr_auc": pr_auc_pesos(w, o),
                "intercepto": intercepto,
                "slope": slope,
                "obs_esp": obs_esp_pesos(w, o),
            }
            if self.completo:
                pontos[nome]["roc_auc"] = roc_auc_pesos(w, o)
                pontos[nome]["brier"] = brier_pesos(w, o)
            if self.tolerante:
                pontos[nome]["calibracao_indisponivel"] = indisponivel
        wl = self.contagem_limiares.astype(np.float64)
        return pontos, {nome: lim.metricas(wl) for nome, lim in self.limiarizados.items()}

    def _calibrar_reamostra(self, nome: str, w: np.ndarray, valores: dict[str, float]) -> None:
        """Slope e intercepto da reamostra. No modo tolerante, falha de convergência vira NaN nos
        dois e `<modelo>/calibracao_descartada` = 1.0 (a reamostra só sai da calibração)."""
        c = self.calibracoes[nome]
        constante = self.meta["modelos"][nome]["constante"]
        try:
            if constante:
                valores[f"{nome}/intercepto"] = c.intercepto(w, inicio=self.inicio[nome][2])
            else:
                _, valores[f"{nome}/slope"], valores[f"{nome}/intercepto"] = (
                    c.slope_e_intercepto(w, self.inicio[nome]))
            descartada = 0.0
        except (RuntimeError, ValueError):
            if not self.tolerante:
                raise
            valores[f"{nome}/intercepto"] = float("nan")
            if not constante:
                valores[f"{nome}/slope"] = float("nan")
            descartada = 1.0
        if self.tolerante:
            valores[f"{nome}/calibracao_descartada"] = descartada

    def reamostra(self, semente: np.random.SeedSequence) -> tuple[dict[str, float], int]:
        """Uma reamostra: (valores por "modelo/métrica", iterações máximas do Newton). O fluxo
        `fluxo_base` da sub-semente sorteia as células dos escores; o seguinte, as dos limiares."""
        w = self.sorteio(fluxo(semente, self.fluxo_base), self.pesos)
        valores: dict[str, float] = {}
        iteracoes = 0
        for nome in self.nomes:
            o, c = self.ordenados[nome], self.calibracoes[nome]
            valores[f"{nome}/pr_auc"] = pr_auc_pesos(w, o)
            if self.completo:
                valores[f"{nome}/roc_auc"] = roc_auc_pesos(w, o)
                valores[f"{nome}/brier"] = brier_pesos(w, o)
            valores[f"{nome}/obs_esp"] = obs_esp_pesos(w, o)
            self._calibrar_reamostra(nome, w, valores)
            iteracoes = max(iteracoes, c.iteracoes_slope, c.iteracoes_intercepto)
        wl = self.sorteio_limiares(fluxo(semente, self.fluxo_base + 1))
        for nome, lim in self.limiarizados.items():
            t = lim.metricas(wl)
            for k in self.metricas_limiar:
                valores[f"{nome}/limiar_{k}"] = t[k]
        return valores, iteracoes

    def bloco(self, sementes: list[np.random.SeedSequence]) -> tuple[dict[str, np.ndarray], int]:
        """Reamostras de um bloco de sementes, na ordem: arrays (len(sementes),) por chave."""
        colunas: dict[str, list[float]] = {}
        iteracoes = 0
        for semente in sementes:
            valores, it = self.reamostra(semente)
            iteracoes = max(iteracoes, it)
            for chave, v in valores.items():
                colunas.setdefault(chave, []).append(v)
        return {k: np.asarray(v, dtype=float) for k, v in colunas.items()}, iteracoes


METRICAS_NO_LIMIAR = ("acuracia", "precisao", "recall", "f1", "f2")


def montar_estado(y, probs: dict[str, np.ndarray], marcados: dict[str, np.ndarray], *,
                  completo: bool = True, tolerante: bool = False,
                  fluxo_base: int = 0) -> tuple[Reamostrador, dict, dict]:
    """Agrupa as linhas em células e prepara o estado do bootstrap no processo principal.

    `probs`: escore de cada modelo (probabilístico), na ordem das linhas de `y`; `marcados`: flag
    de alto risco (bool) de cada modelo ou regra, para as métricas no limiar. Devolve o estado, os
    vetores grandes (os que vão para a memória compartilhada) e os pequenos (`meta`, picklável).
    `completo`, `tolerante` e `fluxo_base`: ver `Reamostrador`.
    """
    y_arr = np.asarray(y).astype(np.int64)
    celulas = agrupar_celulas(y_arr, dict(probs))
    limiares = agrupar_celulas(y_arr, dict(marcados))
    grandes: dict[str, np.ndarray] = {"contagem": celulas.contagem}
    meta: dict[str, Any] = {
        "nomes": tuple(probs), "metricas_limiar": METRICAS_NO_LIMIAR,
        "n_negativas": celulas.n_negativas, "modelos": {},
        "limiares": {"contagem": limiares.contagem, "n_negativas": limiares.n_negativas,
                     "y": limiares.y, "marcados": limiares.colunas},
        "completo": bool(completo), "tolerante": bool(tolerante), "fluxo": int(fluxo_base),
    }
    for nome in probs:
        o = ordenar(celulas.colunas[nome], celulas.y)
        grandes["y"] = o.y
        grandes.update({f"{nome}/{c}": getattr(o, c) for c in CAMPOS_GRANDES})
        pos_idx, pos_grupo, n_grupos, n_bins = o.pequenos()
        meta["modelos"][nome] = {"pos_idx": pos_idx, "pos_grupo": pos_grupo, "n_grupos": n_grupos,
                                 "n_bins": n_bins, "constante": bool(np.ptp(probs[nome]) == 0)}
    return Reamostrador(grandes, meta), grandes, meta


_ESTADO_TRABALHADOR: dict[str, Any] = {}


def _iniciar_trabalhador(descritor: dict, meta: dict) -> None:
    """Inicializador de cada processo do bootstrap: abre a memória compartilhada (sem copiar),
    limita o BLAS a 1 thread (os processos já ocupam os núcleos) e monta o estado."""
    from threadpoolctl import threadpool_limits

    _ESTADO_TRABALHADOR["limite"] = threadpool_limits(limits=1)
    grandes, blocos = abrir_compartilhada(descritor)
    _ESTADO_TRABALHADOR["blocos"] = blocos  # mantém a memória aberta enquanto o processo vive
    _ESTADO_TRABALHADOR["estado"] = Reamostrador(grandes, meta)


def _bloco_do_trabalhador(sementes: list[np.random.SeedSequence]) -> tuple[dict, int]:
    return _ESTADO_TRABALHADOR["estado"].bloco(sementes)


def _juntar(partes: list[tuple[dict[str, np.ndarray], int]]) -> tuple[dict[str, np.ndarray], int]:
    chaves = partes[0][0].keys()
    return ({k: np.concatenate([p[0][k] for p in partes]) for k in chaves},
            max(p[1] for p in partes))


def rodar_reamostras(
    estado: Reamostrador, grandes: dict[str, np.ndarray], meta: dict,
    sementes: list[np.random.SeedSequence], processos: int,
) -> tuple[dict[str, np.ndarray], int]:
    """Calcula todas as reamostras. O resultado de cada reamostra depende só da sua sub-semente:
    é o mesmo com 1, 2, 4 ou 8 processos. Com 1 processo não há pool. Com pool, `grandes` é
    consumido e `estado` deixa de servir (só `estado.inicio` e as iterações continuam válidos)."""
    from threadpoolctl import threadpool_limits

    if processos <= 1:
        with threadpool_limits(limits=1):  # mesma soma que nos trabalhadores: resultado idêntico
            return estado.bloco(sementes)
    n_blocos = min(len(sementes), processos * _BLOCOS_POR_PROCESSO)
    blocos = [list(b) for b in np.array_split(np.arange(len(sementes)), n_blocos)]
    por_bloco = [[sementes[i] for i in indices] for indices in blocos]
    meta_trabalhadores = {**meta, "inicio": estado.inicio}
    estado.liberar()  # o principal só espera: não guarda os vetores grandes além da cópia
    with MemoriaCompartilhada(grandes, consumir=True) as memoria:
        contexto = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=processos, mp_context=contexto,
                                 initializer=_iniciar_trabalhador,
                                 initargs=(memoria.descritor, meta_trabalhadores)) as pool:
            partes = list(pool.map(_bloco_do_trabalhador, por_bloco))
    return _juntar(partes)


# --- Vários Reamostradores no mesmo conjunto de processos (T-5.2: subgrupos) ------------------

_SEPARADOR_CHAVE = "||"
_ESTADO_VARIOS: dict[str, Any] = {}


def _iniciar_varios(descritor: dict, metas: dict) -> None:
    """Inicializador do pool dos subgrupos: abre a memória compartilhada de todos os subgrupos de
    uma vez e monta um Reamostrador por subgrupo (os arrays de cada um têm o prefixo `chave||`)."""
    from threadpoolctl import threadpool_limits

    _ESTADO_VARIOS["limite"] = threadpool_limits(limits=1)
    grandes, blocos = abrir_compartilhada(descritor)
    _ESTADO_VARIOS["blocos"] = blocos
    por_chave: dict[str, dict[str, np.ndarray]] = {chave: {} for chave in metas}
    for nome, array in grandes.items():
        chave, campo = nome.split(_SEPARADOR_CHAVE, 1)
        por_chave[chave][campo] = array
    _ESTADO_VARIOS["estados"] = {chave: Reamostrador(por_chave[chave], metas[chave])
                                 for chave in metas}


def _bloco_varios(sementes: list[np.random.SeedSequence]) -> dict[str, tuple[dict, int]]:
    return {chave: estado.bloco(sementes) for chave, estado in _ESTADO_VARIOS["estados"].items()}


def rodar_varios(
    estados: dict[str, tuple[Reamostrador, dict[str, np.ndarray], dict]],
    sementes: list[np.random.SeedSequence], processos: int,
) -> dict[str, tuple[dict[str, np.ndarray], int]]:
    """Como `rodar_reamostras`, para vários Reamostradores (um por subgrupo) com UM só conjunto de
    processos e uma só memória compartilhada. Cada processo calcula, para um bloco de sementes,
    todos os subgrupos. `estados`: chave -> (estado, grandes, meta). O resultado de cada reamostra
    de cada subgrupo depende só da sub-semente e do `fluxo` do subgrupo (`meta["fluxo"]`): é o
    mesmo com 1, 2, 4 ou 8 processos. Com pool, os `grandes` são consumidos e os estados deixam de
    servir (só `estado.inicio` continua válido). As chaves não podem conter "||"."""
    from threadpoolctl import threadpool_limits

    if not estados:
        return {}
    if any(_SEPARADOR_CHAVE in chave for chave in estados):
        raise ValueError(f"chave de subgrupo com o separador {_SEPARADOR_CHAVE!r}")
    if processos <= 1:
        with threadpool_limits(limits=1):
            return {chave: estado.bloco(sementes) for chave, (estado, _, _) in estados.items()}
    n_blocos = min(len(sementes), processos * _BLOCOS_POR_PROCESSO)
    blocos = [list(b) for b in np.array_split(np.arange(len(sementes)), n_blocos)]
    por_bloco = [[sementes[i] for i in indices] for indices in blocos]
    metas = {chave: {**meta, "inicio": estado.inicio}
             for chave, (estado, _, meta) in estados.items()}
    todos: dict[str, np.ndarray] = {}
    for chave, (estado, grandes, _) in estados.items():
        estado.liberar()
        for campo in list(grandes):
            todos[f"{chave}{_SEPARADOR_CHAVE}{campo}"] = grandes.pop(campo)
    with MemoriaCompartilhada(todos, consumir=True) as memoria:
        contexto = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=processos, mp_context=contexto,
                                 initializer=_iniciar_varios,
                                 initargs=(memoria.descritor, metas)) as pool:
            partes = list(pool.map(_bloco_varios, por_bloco))
    return {chave: _juntar([parte[chave] for parte in partes]) for chave in estados}
