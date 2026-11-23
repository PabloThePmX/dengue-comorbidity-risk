"""Métricas com pesos inteiros para o teste (T-5.1, D-93, D-53): cada função tem uma referência.

Todos os dados são sintéticos e pequenos, salvo o teste de escala, que só roda com
DENGUE_TESTES_LENTOS=1 (fora da suíte padrão).
"""

import os

import numpy as np
import pytest

from dengue_sinan import metrics as m


def _amostra(seed: int = 7, n: int = 4000, prevalencia: float = 0.05):
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < prevalencia).astype(np.int64)
    p = np.round(np.clip(0.02 + 0.3 * y + 0.25 * rng.random(n), 0.001, 0.999), 3)  # com empates
    return y, p


def _amostra_calibrada(seed: int = 7, n: int = 20000, prevalencia: float = 0.02):
    """Escores com sobreposição (logística do ruído): calibração bem definida, sem separação."""
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < prevalencia).astype(np.int64)
    p = 1 / (1 + np.exp(-(np.log(prevalencia / (1 - prevalencia)) + 0.8 * rng.standard_normal(n)
                          + 0.6 * y)))
    return y, p


def test_pr_auc_com_pesos_unitarios_bate_com_pr_auc():
    y, p = _amostra()
    o = m.ordenar(p, y)
    assert m.pr_auc_pesos(np.ones(len(y)), o) == pytest.approx(m.pr_auc(y, p), abs=1e-12)


def test_roc_auc_com_pesos_unitarios_bate_com_roc_auc_inclusive_empates():
    y, p = _amostra()  # p tem muitos empates: o tratamento de empate é o que está sendo testado
    o = m.ordenar(p, y)
    assert m.roc_auc_pesos(np.ones(len(y)), o) == pytest.approx(m.roc_auc(y, p), abs=1e-12)


def test_roc_auc_com_pesos_igual_a_linhas_repetidas():
    rng = np.random.default_rng(3)
    y = np.array([1, 0, 1, 0, 0, 1, 0, 0])
    p = np.array([0.9, 0.9, 0.4, 0.2, 0.7, 0.5, 0.2, 0.1])
    w = rng.integers(0, 4, size=len(y)).astype(float)
    repetido_y = np.repeat(y, w.astype(int))
    repetido_p = np.repeat(p, w.astype(int))
    o = m.ordenar(p, y)
    assert m.roc_auc_pesos(w, o) == pytest.approx(m.roc_auc(repetido_y, repetido_p), abs=1e-12)


def test_roc_auc_sem_negativo_na_reamostra_levanta_erro():
    y = np.array([1, 0, 0])
    o = m.ordenar([0.9, 0.5, 0.1], y)
    with pytest.raises(ValueError, match="ROC-AUC não definida"):
        m.roc_auc_pesos(np.array([1.0, 0.0, 0.0]), o)


def test_brier_com_pesos_unitarios_bate_com_brier():
    y, p = _amostra()
    o = m.ordenar(p, y)
    assert m.brier_pesos(np.ones(len(y)), o) == pytest.approx(m.brier(y, p), abs=1e-12)


def test_limiarizado_com_pesos_unitarios_bate_com_threshold_metrics():
    y, p = _amostra()
    limiar = 0.3
    ref = m.threshold_metrics(y, p, limiar)
    lim = m.Limiarizado(y, p >= limiar)
    obtido = lim.metricas(np.ones(len(y)))
    for k in ("acuracia", "precisao", "recall", "f1", "f2"):
        assert obtido[k] == pytest.approx(ref[k], abs=1e-12), k


def test_threshold_pesos_e_a_mesma_coisa_que_limiarizado():
    y, p = _amostra()
    marcado = p >= 0.4
    w = np.random.default_rng(1).integers(0, 3, size=len(y)).astype(float)
    assert m.threshold_pesos(w, y, marcado) == m.Limiarizado(y, marcado).metricas(w)


def test_calibracao_com_pesos_unitarios_bate_com_statsmodels():
    y, p = _amostra_calibrada()
    slope_ref, intercepto_ref = m.calibration_slope_intercept(y, p)
    o = m.ordenar(p, y)
    c = m.Calibracao(o.x, y)
    intercepto_livre, slope = c.slope_intercepto(np.ones(len(y)))
    intercepto = c.intercepto(np.ones(len(y)), inicio=intercepto_livre)
    assert slope == pytest.approx(slope_ref, rel=1e-6)
    assert intercepto == pytest.approx(intercepto_ref, rel=1e-6, abs=1e-8)


def test_calibracao_intercepto_e_o_offset_e_nao_o_livre():
    # Mutação: usar o intercepto do ajuste livre como calibração-no-grande daria outro número.
    y, p = _amostra_calibrada()
    o = m.ordenar(p, y)
    c = m.Calibracao(o.x, y)
    livre, slope = c.slope_intercepto(np.ones(len(y)))
    offset = c.intercepto(np.ones(len(y)), inicio=livre)
    assert abs(offset - livre) > 1e-3
    assert offset == pytest.approx(m.calibration_slope_intercept(y, p)[1], rel=1e-6, abs=1e-8)


def test_calibracao_com_logits_extremos_converge_e_bate_com_statsmodels():
    # Logits de até −20 (como um E1 com covariáveis raras): o Newton sem limite de passo diverge.
    rng = np.random.default_rng(12)
    n = 30000
    x = np.where(rng.random(n) < 0.05, -20 + rng.random(n), -6 + rng.standard_normal(n))
    p = 1 / (1 + np.exp(-x))
    y = (rng.random(n) < 1 / (1 + np.exp(-(x * 0.8 - 0.4)))).astype(np.int64)
    slope_ref, intercepto_ref = m.calibration_slope_intercept(y, p)
    o = m.ordenar(p, y)
    c = m.Calibracao(o.x, y)
    livre, slope = c.slope_intercepto(np.ones(n))
    offset = c.intercepto(np.ones(n), inicio=livre)
    assert slope == pytest.approx(slope_ref, rel=1e-5)
    assert offset == pytest.approx(intercepto_ref, rel=1e-5, abs=1e-6)


def test_calibracao_separada_nao_converge_e_levanta_erro():
    # Escore perfeitamente separável: não há máximo finito; nunca devolve número parcial.
    y = np.array([0] * 50 + [1] * 50)
    p = np.concatenate([np.full(50, 0.1), np.full(50, 0.9)])
    o = m.ordenar(p, y)
    c = m.Calibracao(o.x, y)
    with pytest.raises((RuntimeError, ValueError), match="não (convergiu|identificável)"):
        c.slope_intercepto(np.ones(len(y)))


def test_calibracao_com_escore_constante_nao_e_identificavel():
    y, _ = _amostra(n=500)
    o = m.ordenar(np.full(len(y), 0.05), y)
    with pytest.raises(ValueError, match="não identificável"):
        m.Calibracao(o.x, y).slope_intercepto(np.ones(len(y)))


def test_pesos_estratificados_mesma_semente_mesmos_pesos():
    y, _ = _amostra(n=300)
    a = [w.copy() for w in m.pesos_estratificados(y, 4, seed=11)]
    b = [w.copy() for w in m.pesos_estratificados(y, 4, seed=11)]
    for wa, wb in zip(a, b, strict=True):
        assert np.array_equal(wa, wb)


def test_pesos_estratificados_preservam_o_numero_de_positivos_e_negativos():
    y, _ = _amostra(n=600)
    for w in m.pesos_estratificados(y, 5, seed=2):
        assert w[y == 1].sum() == (y == 1).sum()
        assert w[y == 0].sum() == (y == 0).sum()


def test_bootstrap_com_pesos_bate_com_paired_bootstrap_pr_auc_de_uma_dobra():
    # Mesmos sorteios de paired_bootstrap_pr_auc: a PR-AUC de cada reamostra é a mesma.
    y, p = _amostra(n=3000)
    p2 = np.clip(p * 0.7, 0.0, 1.0)
    referencia = m.paired_bootstrap_pr_auc({"A": p, "B": p2}, y, np.zeros(len(y), int),
                                           n=25, seed=99)["media"]["A"]
    o = m.ordenar(p, y)
    obtido = np.array([m.pr_auc_pesos(w, o) for w in m.pesos_estratificados(y, 25, seed=99)])
    assert np.max(np.abs(obtido - referencia)) < 1e-12


def test_bootstrap_de_escala_nao_muda_a_ordem_de_ties():
    # A reamostra com pesos não reordena os dados: o resultado é igual ao de linhas repetidas.
    y = np.array([1, 0, 1, 0, 0, 1, 0, 0, 1, 0])
    p = np.array([0.5, 0.5, 0.5, 0.1, 0.1, 0.9, 0.1, 0.5, 0.7, 0.1])
    o = m.ordenar(p, y)
    w = np.array([2, 0, 1, 3, 0, 1, 1, 0, 2, 1], dtype=float)
    rep_y = np.repeat(y, w.astype(int))
    rep_p = np.repeat(p, w.astype(int))
    assert m.pr_auc_pesos(w, o) == pytest.approx(m.pr_auc(rep_y, rep_p), abs=1e-12)


@pytest.mark.parametrize("valor", [[], [0.1, 0.2], "x"])
def test_ordenar_recusa_tamanho_errado_ou_vazio(valor):
    with pytest.raises(ValueError):
        m.ordenar(valor, [0])


def test_ordenar_recusa_escore_nao_finito_e_y_fora_de_0_1():
    with pytest.raises(ValueError, match="não finito"):
        m.ordenar([0.1, float("nan")], [0, 1])
    with pytest.raises(ValueError, match="0 ou 1"):
        m.ordenar([0.1, 0.2], [0, 2])


@pytest.mark.skipif(os.environ.get("DENGUE_TESTES_LENTOS") != "1",
                    reason="escala de 5,3 milhões de linhas: só com DENGUE_TESTES_LENTOS=1")
def test_escala_5_milhoes_roda_duas_reamostras_com_pesos():
    n, eventos = 5_331_745, 11_338
    rng = np.random.default_rng(20261103)
    y = np.zeros(n, dtype=np.int64)
    y[rng.choice(n, eventos, replace=False)] = 1
    p = 1 / (1 + np.exp(-(np.log(0.00213 / 0.99787) + 0.9 * rng.standard_normal(n) + 0.9 * y)))
    o = m.ordenar(p, y)
    obtidos = [m.pr_auc_pesos(w, o) for w in m.pesos_estratificados(y, 2, seed=1)]
    assert all(0.0 < v < 1.0 for v in obtidos)


def test_roc_com_empates_entre_classes_bate_com_roc_auc():
    # Escores sobrepostos e arredondados: há empates entre positivos e negativos. O termo de
    # metade do empate tem de contar (no conjunto de _amostra() não há empate entre classes).
    y, p = _amostra_calibrada(seed=4, n=6000, prevalencia=0.1)
    p = np.round(p, 2)
    o = m.ordenar(p, y)
    assert m.roc_auc_pesos(np.ones(len(y)), o) == pytest.approx(m.roc_auc(y, p), abs=1e-12)


def test_limiarizado_com_escores_sobrepostos_bate_com_threshold_metrics():
    # Com _amostra() todo positivo fica acima do limiar: o vp não depende da marcação. Aqui há
    # positivos e negativos dos dois lados do limiar, e a conta tem de bater com threshold_metrics.
    y, p = _amostra_calibrada(seed=5, n=6000, prevalencia=0.1)
    limiar = float(np.quantile(p, 0.8))
    ref = m.threshold_metrics(y, p, limiar)
    obtido = m.Limiarizado(y, p >= limiar).metricas(np.ones(len(y)))
    assert 0 < obtido["vp"] < y.sum()
    for k in ("acuracia", "precisao", "recall", "f1", "f2"):
        assert obtido[k] == pytest.approx(ref[k], abs=1e-12), k


# --- Otimização do bootstrap (T-5.1, D-93): vãos, células, Newton, sementes, memória ----------

def _amostra_com_empates(seed: int, n: int = 400, prevalencia: float = 0.1):
    """Escores arredondados em 1 casa: muitos empates, inclusive entre positivos e negativos."""
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < prevalencia).astype(np.int64)
    y[:3] = 1
    y[3:6] = 0
    p = np.round(np.clip(0.3 + 0.25 * y + 0.3 * rng.standard_normal(n), 0.01, 0.99), 1)
    return y, p


@pytest.mark.parametrize("seed", range(12))
def test_pr_e_roc_por_vaos_batem_com_o_sklearn_em_linhas_repetidas(seed):
    # Reformulação exata: para QUALQUER vetor de pesos (com zeros, empates entre as classes) o
    # resultado é o do sklearn nas linhas repetidas.
    y, p = _amostra_com_empates(seed)
    rng = np.random.default_rng(100 + seed)
    w = rng.integers(0, 4, size=len(y)).astype(float)
    w[:6] = np.maximum(w[:6], 1)  # garante positivo e negativo na reamostra
    o = m.ordenar(p, y)
    ry, rp = np.repeat(y, w.astype(int)), np.repeat(p, w.astype(int))
    assert m.pr_auc_pesos(w, o) == pytest.approx(m.pr_auc(ry, rp), abs=1e-12)
    assert m.roc_auc_pesos(w, o) == pytest.approx(m.roc_auc(ry, rp), abs=1e-12)


def test_pr_e_roc_por_vaos_com_escore_constante_e_um_grupo_so():
    y = np.array([1, 0, 0, 1, 0, 0, 0])
    o = m.ordenar(np.full(len(y), 0.2), y)
    w = np.array([2.0, 1, 3, 1, 0, 2, 1])
    assert m.pr_auc_pesos(w, o) == pytest.approx(3 / 10, abs=1e-12)  # prevalência ponderada
    assert m.roc_auc_pesos(w, o) == pytest.approx(0.5, abs=1e-12)


def test_pr_auc_sem_positivo_na_reamostra_levanta_erro():
    o = m.ordenar([0.9, 0.5, 0.1], [1, 0, 0])
    with pytest.raises(ValueError, match="PR-AUC não definida"):
        m.pr_auc_pesos(np.array([0.0, 1.0, 1.0]), o)


def test_celulas_agrupam_linhas_identicas_e_preservam_contagens():
    y = np.array([0, 1, 0, 0, 1, 0, 1])
    a = np.array([0.1, 0.1, 0.1, 0.2, 0.1, 0.2, 0.3])
    b = np.array([True, True, True, False, True, False, True])
    cel = m.agrupar_celulas(y, {"a": a, "b": b})
    assert cel.contagem.sum() == len(y)
    assert cel.n_negativas == 2 and (cel.y[: cel.n_negativas] == 0).all()
    achados = {(int(yy), float(aa), bool(bb)): int(c) for yy, aa, bb, c
               in zip(cel.y, cel.colunas["a"], cel.colunas["b"], cel.contagem, strict=True)}
    assert achados == {(0, 0.1, True): 2, (0, 0.2, False): 2,
                       (1, 0.1, True): 2, (1, 0.3, True): 1}


def test_agrupar_celulas_recusa_y_invalido_vazio_ou_tamanho_diferente():
    with pytest.raises(ValueError, match="0 ou 1"):
        m.agrupar_celulas([0, 2], {"a": [0.1, 0.2]})
    with pytest.raises(ValueError, match="não vazio"):
        m.agrupar_celulas([], {"a": []})
    with pytest.raises(ValueError, match="tamanho"):
        m.agrupar_celulas([0, 1], {"a": [0.1]})


def _chaves(y, p, marcado):
    return [(int(a), float(b), bool(c)) for a, b, c in zip(y, p, marcado, strict=True)]


@pytest.mark.parametrize("seed", range(5))
def test_metricas_nas_celulas_batem_com_as_das_linhas_repetidas(seed):
    # Pesos por linha somados por célula (= pesos da célula) dão as métricas do sklearn nas
    # linhas repetidas: PR, ROC, Brier e as métricas no limiar.
    y, p = _amostra_com_empates(seed, n=300)
    w_linha = np.random.default_rng(seed).integers(0, 4, size=len(y)).astype(float)
    w_linha[:6] = np.maximum(w_linha[:6], 1)
    marcado = p >= 0.4
    cel = m.agrupar_celulas(y, {"p": p, "m": marcado})
    por_chave: dict = {}
    for k, w in zip(_chaves(y, p, marcado), w_linha, strict=True):
        por_chave[k] = por_chave.get(k, 0.0) + w
    w_cel = np.array([por_chave[k] for k in _chaves(cel.y, cel.colunas["p"], cel.colunas["m"])])
    ry, rp = np.repeat(y, w_linha.astype(int)), np.repeat(p, w_linha.astype(int))
    o = m.ordenar(cel.colunas["p"], cel.y)
    assert m.pr_auc_pesos(w_cel, o) == pytest.approx(m.pr_auc(ry, rp), abs=1e-12)
    assert m.roc_auc_pesos(w_cel, o) == pytest.approx(m.roc_auc(ry, rp), abs=1e-12)
    assert m.brier_pesos(w_cel, o) == pytest.approx(m.brier(ry, rp), abs=1e-12)
    ref = m.threshold_metrics(ry, rp, 0.4)
    obtido = m.Limiarizado(cel.y, cel.colunas["m"]).metricas(w_cel)
    for k in ("acuracia", "precisao", "recall", "f1", "f2"):
        assert obtido[k] == pytest.approx(ref[k], abs=1e-12), k


def test_sorteio_mantem_o_tamanho_das_classes_e_a_distribuicao_binomial_de_cada_celula():
    y = np.array([0] * 6 + [1] * 3)
    cel = m.agrupar_celulas(y, {"p": [0.1, 0.1, 0.1, 0.2, 0.2, 0.3, 0.4, 0.4, 0.5]})
    sorteio = m.Sorteio(cel.contagem, cel.n_negativas)
    rng = np.random.default_rng(0)
    n_rep = 8000
    pesos = np.array([sorteio(rng).copy() for _ in range(n_rep)])
    n0 = cel.n_negativas
    assert (pesos[:, :n0].sum(axis=1) == 6).all()  # estratificado: negativos
    assert (pesos[:, n0:].sum(axis=1) == 3).all()  # estratificado: positivos
    tamanho = np.where(cel.y == 0, 6, 3)  # linhas da classe da célula
    media = cel.contagem  # peso ~ Binomial(tamanho, contagem / tamanho)
    variancia = cel.contagem * (1 - cel.contagem / tamanho)
    erro_padrao = np.sqrt(variancia / n_rep)
    assert np.all(np.abs(pesos.mean(axis=0) - media) < 5 * erro_padrao)
    assert np.all(np.abs(pesos.var(axis=0) / np.maximum(variancia, 1e-9) - 1) < 0.15)


def test_sorteio_e_equivalente_ao_bootstrap_de_linhas_em_media_e_desvio():
    # O bootstrap por células tem a distribuição do de linhas (pesos_estratificados): mesmas
    # médias e desvios de PR-AUC, Brier, slope e intercepto em muitas reamostras.
    y, p = _amostra_calibrada(seed=3, n=500, prevalencia=0.15)
    p = np.round(p, 2)  # duplicatas: as células agrupam
    n_rep = 2500
    o_linhas = m.ordenar(p, y)
    c_linhas = m.Calibracao(o_linhas.x, y)
    inicio = c_linhas.slope_e_intercepto(np.ones(len(y)))
    linhas: dict[str, list] = {k: [] for k in ("pr", "brier", "slope", "interc")}
    for w in m.pesos_estratificados(y, n_rep, seed=1):
        linhas["pr"].append(m.pr_auc_pesos(w, o_linhas))
        linhas["brier"].append(m.brier_pesos(w, o_linhas))
        _, s, i = c_linhas.slope_e_intercepto(w, inicio)
        linhas["slope"].append(s)
        linhas["interc"].append(i)
    cel = m.agrupar_celulas(y, {"p": p})
    assert len(cel) < len(y)
    o = m.ordenar(cel.colunas["p"], cel.y)
    c = m.Calibracao(o.x, o.y, x2=o.x2, ex=o.ex, pos_idx=o.pos_idx)
    sorteio = m.Sorteio(cel.contagem, cel.n_negativas)
    celulas: dict[str, list] = {k: [] for k in linhas}
    for semente in m.sementes_das_reamostras(2, n_rep):
        w = sorteio(m.fluxo(semente, 0))
        celulas["pr"].append(m.pr_auc_pesos(w, o))
        celulas["brier"].append(m.brier_pesos(w, o))
        _, s, i = c.slope_e_intercepto(w, inicio)
        celulas["slope"].append(s)
        celulas["interc"].append(i)
    for k in linhas:
        a, b = np.array(linhas[k]), np.array(celulas[k])
        erro_padrao = np.sqrt((a.var() + b.var()) / n_rep)
        assert abs(a.mean() - b.mean()) < 4.5 * erro_padrao, k
        assert 0.9 < a.std() / b.std() < 1.1, k


def test_newton_com_pesos_inteiros_bate_com_statsmodels_em_linhas_repetidas():
    y, p = _amostra_calibrada(seed=9, n=3000, prevalencia=0.05)
    w = np.random.default_rng(4).integers(0, 4, size=len(y)).astype(float)
    ry, rp = np.repeat(y, w.astype(int)), np.repeat(p, w.astype(int))
    slope_ref, intercepto_ref = m.calibration_slope_intercept(ry, rp)
    o = m.ordenar(p, y)
    c = m.Calibracao(o.x, o.y, x2=o.x2, ex=o.ex, pos_idx=o.pos_idx)
    livre, slope, intercepto = c.slope_e_intercepto(w)
    assert slope == pytest.approx(slope_ref, rel=1e-6)
    assert intercepto == pytest.approx(intercepto_ref, rel=1e-6, abs=1e-8)
    assert abs(livre - intercepto) > 1e-3  # o intercepto livre não é o de calibração


def test_slope_e_intercepto_numa_chamada_e_igual_as_duas_chamadas_separadas():
    y, p = _amostra_calibrada()
    o = m.ordenar(p, y)
    w = np.random.default_rng(8).integers(0, 3, size=len(y)).astype(float)
    c = m.Calibracao(o.x, o.y, x2=o.x2, ex=o.ex, pos_idx=o.pos_idx)
    livre, slope, intercepto = c.slope_e_intercepto(w)
    livre2, slope2 = c.slope_intercepto(w)
    assert (livre, slope) == (livre2, slope2)
    assert intercepto == c.intercepto(w)


def test_newton_que_nao_converge_levanta_erro_na_chamada_unica():
    y = np.array([0] * 50 + [1] * 50)
    p = np.concatenate([np.full(50, 0.1), np.full(50, 0.9)])
    o = m.ordenar(p, y)
    with pytest.raises((RuntimeError, ValueError), match="não (convergiu|identificável)"):
        m.Calibracao(o.x, o.y).slope_e_intercepto(np.ones(len(y)))


def test_sementes_por_reamostra_sao_reprodutiveis_e_independentes_de_n():
    a = m.sementes_das_reamostras(123, 5)
    b = m.sementes_das_reamostras(123, 50)
    c = m.sementes_das_reamostras(124, 5)
    for k in range(5):
        assert m.fluxo(a[k], 0).random() == m.fluxo(b[k], 0).random()
    assert m.fluxo(a[0], 0).random() != m.fluxo(c[0], 0).random()
    assert m.fluxo(a[0], 0).random() != m.fluxo(a[1], 0).random()


def test_fluxo_nao_altera_a_semente_e_os_dois_fluxos_sao_diferentes():
    s = m.sementes_das_reamostras(5, 1)[0]
    primeiro = m.fluxo(s, 0).random(3)
    assert np.array_equal(primeiro, m.fluxo(s, 0).random(3))  # chamar de novo dá o mesmo
    assert not np.array_equal(primeiro, m.fluxo(s, 1).random(3))


def test_memoria_compartilhada_devolve_os_mesmos_dados_somente_leitura():
    arrays = {"a": np.arange(10, dtype=np.float64), "b": np.array([3, 1, 2], dtype=np.intp),
              "vazio": np.empty(0)}
    with m.MemoriaCompartilhada(arrays) as mem:
        abertos, blocos = m.abrir_compartilhada(mem.descritor)
        for nome, original in arrays.items():
            assert np.array_equal(abertos[nome], original)
            assert abertos[nome].dtype == original.dtype
        with pytest.raises(ValueError):
            abertos["a"][0] = 99.0  # somente leitura
        assert arrays["a"][0] == 0.0  # a escrita não vazou para o original
        del abertos
        for bloco in blocos:
            bloco.close()


def test_memoria_compartilhada_consumir_esvazia_o_dict_de_origem_e_mantem_os_dados():
    origem = {"a": np.arange(6, dtype=np.float64), "b": np.array([1, 2], dtype=np.intp)}
    copia = {k: v.copy() for k, v in origem.items()}
    with m.MemoriaCompartilhada(origem, consumir=True) as mem:
        assert origem == {}  # nenhuma referência sobra no principal
        abertos, blocos = m.abrir_compartilhada(mem.descritor)
        for nome, esperado in copia.items():
            assert np.array_equal(abertos[nome], esperado)
        del abertos
        for bloco in blocos:
            bloco.close()


@pytest.mark.parametrize("bloco", [1, 7, 500, 100_000])
def test_calibracao_em_blocos_da_o_mesmo_resultado_qualquer_que_seja_o_tamanho_do_bloco(bloco):
    # O bloco só muda a ordem das somas: o resultado é o de statsmodels (com bloco 7 há bloco final
    # curto; com 1 cada elemento é um bloco; com 100.000 há um bloco só).
    y, p = _amostra_calibrada(seed=11, n=2000, prevalencia=0.05)
    w = np.random.default_rng(6).integers(0, 4, size=len(y)).astype(float)
    ry, rp = np.repeat(y, w.astype(int)), np.repeat(p, w.astype(int))
    slope_ref, intercepto_ref = m.calibration_slope_intercept(ry, rp)
    o = m.ordenar(p, y)
    tamanho = min(bloco, 8192)  # `Trabalho` tem o tamanho do maior bloco
    c = m.Calibracao(o.x, o.y, x2=o.x2, ex=o.ex, pos_idx=o.pos_idx, trabalho=m.Trabalho(tamanho),
                     bloco=tamanho)
    _, slope, intercepto = c.slope_e_intercepto(w)
    assert slope == pytest.approx(slope_ref, rel=1e-6)
    assert intercepto == pytest.approx(intercepto_ref, rel=1e-6, abs=1e-8)


def test_sorteio_de_celulas_de_uma_linha_tem_a_distribuicao_do_bootstrap_de_linhas():
    # Sem linhas repetidas o sorteio é direto (integers + bincount): cada peso é Binomial(n, 1/n).
    y = np.array([0] * 8 + [1] * 4)
    cel = m.agrupar_celulas(y, {"p": np.arange(12) / 20})
    assert (cel.contagem == 1).all()
    sorteio = m.Sorteio(cel.contagem, cel.n_negativas)
    rng = np.random.default_rng(3)
    n_rep = 6000
    pesos = np.array([sorteio(rng).copy() for _ in range(n_rep)])
    assert (pesos[:, :8].sum(axis=1) == 8).all() and (pesos[:, 8:].sum(axis=1) == 4).all()
    tamanho = np.where(cel.y == 0, 8, 4)
    variancia = (1 - 1 / tamanho)  # n · (1/n) · (1 − 1/n)
    assert np.all(np.abs(pesos.mean(axis=0) - 1) < 5 * np.sqrt(variancia / n_rep))
    assert np.all(np.abs(pesos.var(axis=0) / variancia - 1) < 0.15)


# --- Robustez do Newton com probabilidade exatamente 0 (isotônica) ---------------------------

def _amostra_com_zeros_exatos(seed: int):
    """Amostra pequena, escores em poucos níveis (como a isotônica), 30% deles exatamente 0, e
    eventos nesses pontos (logit −27,6 pelo limite)."""
    rng = np.random.default_rng(seed)
    n = int(rng.integers(40, 400))
    niveis = np.array([0.0, 0.01, 0.03, 0.08, 0.2, 0.5])
    p = rng.choice(niveis, n, p=[0.3, 0.25, 0.2, 0.15, 0.07, 0.03])
    risco = np.where(p == 0, 0.004, p) * rng.uniform(0.5, 2)
    y = (rng.random(n) < np.clip(risco, 0, 1)).astype(int)
    zeros = np.flatnonzero(p == 0)
    if len(zeros) and rng.random() < 0.6:
        y[rng.choice(zeros)] = 1  # evento onde a probabilidade é exatamente 0
    return y, p


def test_newton_com_zeros_exatos_converge_nos_casos_em_que_o_statsmodels_converge():
    # Antes: ~4% das amostras levantavam RuntimeError/ValueError. Os que sobram são separação
    # (o statsmodels devolve slope de 1e15 ou ~20 sem convergir): o erro é o certo, não um número.
    from scipy.optimize import brentq

    avaliadas = regulares = falhas_regulares = falhas = 0
    maior_dif_slope = maior_dif_intercepto = 0.0
    for seed in range(1000):
        y, p = _amostra_com_zeros_exatos(seed)
        if y.sum() < 2 or y.sum() == len(y) or len(np.unique(p)) < 3:
            continue
        avaliadas += 1
        o = m.ordenar(p, y)
        c = m.Calibracao(o.x, o.y, x2=o.x2, ex=o.ex, pos_idx=o.pos_idx)
        try:
            _, slope, intercepto = c.slope_e_intercepto(np.ones(len(y)))
        except (RuntimeError, ValueError):
            falhas += 1
            slope = None
        try:
            slope_sm, _ = m.calibration_slope_intercept(y, p)
        except Exception:  # noqa: BLE001  statsmodels também pode falhar nesses casos
            continue
        if not np.isfinite(slope_sm) or abs(slope_sm) > 10:  # statsmodels divergiu: sem referência
            continue
        regulares += 1
        if slope is None:
            falhas_regulares += 1
            continue
        maior_dif_slope = max(maior_dif_slope, abs(slope - slope_sm) / max(1.0, abs(slope_sm)))
        ref = brentq(lambda t, y=y, x=o.x: float(np.sum(y - 1 / (1 + np.exp(-(x + t))))), -60, 60,
                     xtol=1e-13)  # o intercepto do statsmodels não é confiável com zeros exatos
        maior_dif_intercepto = max(maior_dif_intercepto, abs(intercepto - ref))
    assert avaliadas > 900 and regulares > 800
    assert falhas_regulares == 0
    assert falhas / avaliadas < 0.015
    assert maior_dif_slope < 1e-6 and maior_dif_intercepto < 1e-8


def test_newton_amortecido_com_zeros_exatos_e_eventos_neles_nao_levanta_erro():
    y, p = _amostra_com_zeros_exatos(1)
    assert (p == 0).any() and y[p == 0].sum() >= 0
    o = m.ordenar(p, y)
    c = m.Calibracao(o.x, o.y, x2=o.x2, ex=o.ex, pos_idx=o.pos_idx)
    _, slope, intercepto = c.slope_e_intercepto(np.ones(len(y)))
    assert np.isfinite(slope) and np.isfinite(intercepto)
    assert slope == pytest.approx(m.calibration_slope_intercept(y, p)[0], rel=1e-5)


def test_intercepto_com_partida_muito_longe_converge_pelo_newton_amortecido():
    # De a = 150 o Newton puro (passo máximo 2, 50 iterações) não chega; o amortecido (200) chega.
    from scipy.optimize import brentq

    y, p = _amostra_calibrada(seed=2, n=3000, prevalencia=0.05)
    o = m.ordenar(p, y)
    c = m.Calibracao(o.x, o.y, x2=o.x2, ex=o.ex, pos_idx=o.pos_idx)
    obtido = c.intercepto(np.ones(len(y)), inicio=150.0)
    ref = brentq(lambda t: float(np.sum(y - 1 / (1 + np.exp(-(o.x + t))))), -60, 60, xtol=1e-13)
    assert obtido == pytest.approx(ref, abs=1e-8)
    assert c.iteracoes_intercepto > 50  # só o amortecido chega até aqui



# --- Separação perfeita: erro, nunca um slope falso por saturação numérica --------------------

def _casos_separaveis():
    """Os 80 casos de escore separável (p = 0,9 nos eventos e 0,1 nos demais) com pesos inteiros
    0–3; os casos 167, 217, 222, 292 e 327 devolviam slope ~16,5 após ~40 iterações."""
    rng = np.random.default_rng(7)
    for caso in range(400):
        n = int(rng.integers(80, 300))
        y = (rng.uniform(size=n) < 0.25).astype(int)
        if y.sum() < 2:
            y[:2] = 1
        tipo = caso % 5
        if tipo == 0:
            p = np.where(y == 1, rng.choice([0.0, 0.3, 0.6, 1.0], n),
                         rng.choice([0.0, 0.1, 0.5], n))
        elif tipo == 1:
            p = np.where(rng.uniform(size=n) < 0.5, 0.0, rng.uniform(0.05, 0.6, n))
        elif tipo == 2:
            p = np.where(y == 1, 0.9, 0.1)
        elif tipo == 3:
            p = np.clip(0.2 + 0.2 * (y - 0.25) + rng.normal(0, 0.1, n), 0.02, 0.98)
            p[np.flatnonzero(y == 1)[0]] = 0.0
        else:
            p = np.clip(0.2 + 0.2 * (y - 0.25) + rng.normal(0, 0.1, n), 0.02, 0.98)
        w = rng.integers(0, 4, n)
        if w[y == 1].sum() == 0:
            w[np.flatnonzero(y == 1)[0]] = 1
        if w[y == 0].sum() == 0:
            w[np.flatnonzero(y == 0)[0]] = 1
        if tipo == 2:
            yield caso, y, p, w.astype(float)


def _ajustar_slope(y, p, w):
    o = m.ordenar(p, y)
    return m.Calibracao(o.x, o.y, x2=o.x2, ex=o.ex, pos_idx=o.pos_idx).slope_e_intercepto(w)


def test_separacao_perfeita_com_pesos_variados_levanta_erro_nos_80_casos():
    casos = list(_casos_separaveis())
    assert len(casos) == 80
    for _caso, y, p, w in casos:
        with pytest.raises((RuntimeError, ValueError)):
            _ajustar_slope(y, p, w)  # antes: 5 dos 80 devolviam slope ~16,5


@pytest.mark.parametrize("caso_alvo", [167, 217, 222, 292, 327])
def test_casos_fixos_que_devolviam_slope_falso_agora_levantam_erro(caso_alvo):
    caso, y, p, w = next(c for c in _casos_separaveis() if c[0] == caso_alvo)
    with pytest.raises((RuntimeError, ValueError)):
        _ajustar_slope(y, p, w)


def test_separacao_com_pesos_unitarios_tambem_levanta_erro():
    y = np.array([0] * 40 + [1] * 10)
    p = np.where(y == 1, 0.9, 0.1)
    with pytest.raises((RuntimeError, ValueError)):
        _ajustar_slope(y, p, np.ones(len(y)))


def test_saturacao_parcial_sem_separacao_converge_e_bate_com_o_statsmodels():
    # Escore em 0,1 / 0,9 mas com sobreposição (eventos em 0,1 e não eventos em 0,9): há máximo.
    rng = np.random.default_rng(5)
    n = 300
    p = rng.choice([0.1, 0.9], n)
    y = (rng.random(n) < np.where(p == 0.9, 0.7, 0.2)).astype(int)
    w = rng.integers(1, 4, n).astype(float)
    ry, rp = np.repeat(y, w.astype(int)), np.repeat(p, w.astype(int))
    slope_ref, _ = m.calibration_slope_intercept(ry, rp)
    _, slope, _ = _ajustar_slope(y, p, w)
    assert slope == pytest.approx(slope_ref, rel=1e-6)


# --- T-5.2: observado/esperado, modo tolerante, vários estados num só pool -------------------

def _estado_pequeno(seed: int = 5, n: int = 3000, **opcoes):
    y, p = _amostra_calibrada(seed=seed, n=n, prevalencia=0.05)
    marcados = {"M1": p >= np.quantile(p, 0.8), "B2": (np.arange(n) % 3 == 0)}
    return y, p, m.montar_estado(y, {"M1": p}, marcados, **opcoes)


def test_obs_esp_com_pesos_bate_com_linhas_repetidas():
    rng = np.random.default_rng(2)
    y, p = _amostra_calibrada(n=500, prevalencia=0.1)
    w = rng.integers(0, 4, size=len(y)).astype(float)
    o = m.ordenar(p, y)
    repetido_y, repetido_p = np.repeat(y, w.astype(int)), np.repeat(p, w.astype(int))
    assert m.obs_esp_pesos(w, o) == pytest.approx(repetido_y.sum() / repetido_p.sum(), abs=1e-12)
    assert o.p is not None and np.array_equal(o.p, p)  # o escore original, sem o clip do logit


def test_obs_esp_com_previsao_toda_zero_e_nan():
    y = np.array([1, 0, 0, 1])
    o = m.ordenar(np.zeros(4), y)
    assert np.isnan(m.obs_esp_pesos(np.ones(4), o))


def test_reamostrador_completo_false_nao_calcula_roc_nem_brier_mas_calcula_obs_esp():
    _, _, (estado, _, _) = _estado_pequeno(completo=False)
    pontos, _ = estado.pontos()
    assert set(pontos["M1"]) >= {"pr_auc", "obs_esp", "slope", "intercepto"}
    assert "roc_auc" not in pontos["M1"] and "brier" not in pontos["M1"]
    valores, _ = estado.reamostra(m.sementes_das_reamostras(1, 1)[0])
    assert "M1/obs_esp" in valores and "M1/roc_auc" not in valores and "M1/brier" not in valores


def test_reamostrador_completo_padrao_mantem_roc_brier_e_acrescenta_obs_esp():
    _, _, (estado, _, _) = _estado_pequeno()
    pontos, _ = estado.pontos()
    assert {"roc_auc", "brier", "obs_esp"} <= set(pontos["M1"])
    valores, _ = estado.reamostra(m.sementes_das_reamostras(1, 1)[0])
    assert {"M1/roc_auc", "M1/brier", "M1/obs_esp"} <= set(valores)
    assert "M1/calibracao_descartada" not in valores  # só no modo tolerante


def _separavel(n: int = 400):
    rng = np.random.default_rng(9)
    y = (rng.random(n) < 0.2).astype(np.int64)
    posicao = np.arange(n)
    p = np.where(y == 1, 0.5 + 1e-4 * posicao, 0.01 + 1e-6 * posicao)
    return y, p


def test_modo_tolerante_marca_o_ponto_indisponivel_e_descarta_a_reamostra_sem_levantar():
    y, p = _separavel()
    estado, _, _ = m.montar_estado(y, {"M1": p}, {"M1": p >= 0.4}, tolerante=True,
                                   completo=False)
    pontos, _ = estado.pontos()
    assert pontos["M1"]["slope"] is None and pontos["M1"]["calibracao_indisponivel"] is True
    assert pontos["M1"]["intercepto"] is not None  # o ajuste só do intercepto converge
    valores, _ = estado.reamostra(m.sementes_das_reamostras(1, 1)[0])
    assert np.isnan(valores["M1/slope"]) and np.isnan(valores["M1/intercepto"])
    assert valores["M1/calibracao_descartada"] == 1.0
    assert valores["M1/pr_auc"] == pytest.approx(1.0)  # as demais métricas continuam valendo


def test_sem_modo_tolerante_a_separacao_continua_levantando_erro():
    y, p = _separavel()
    estado, _, _ = m.montar_estado(y, {"M1": p}, {"M1": p >= 0.4})
    with pytest.raises((RuntimeError, ValueError)):  # separação perfeita: nunca devolve número
        estado.pontos()


def test_modo_tolerante_sem_problema_nao_descarta_e_da_o_mesmo_slope_do_modo_normal():
    y, p, (tolerante, _, _) = _estado_pequeno(tolerante=True)
    _, _, (normal, _, _) = _estado_pequeno()
    semente = m.sementes_das_reamostras(3, 1)[0]
    tolerante.pontos()
    normal.pontos()
    a, _ = tolerante.reamostra(semente)
    b, _ = normal.reamostra(semente)
    assert a["M1/calibracao_descartada"] == 0.0
    assert a["M1/slope"] == b["M1/slope"] and a["M1/intercepto"] == b["M1/intercepto"]


def test_fluxo_base_muda_os_sorteios_e_a_mesma_base_reproduz():
    _, _, (e0, _, _) = _estado_pequeno(fluxo_base=0)
    _, _, (e10, _, _) = _estado_pequeno(fluxo_base=10)
    _, _, (e10b, _, _) = _estado_pequeno(fluxo_base=10)
    for e in (e0, e10, e10b):
        e.pontos()
    semente = m.sementes_das_reamostras(4, 1)[0]
    v0, v10, v10b = (e.reamostra(semente)[0] for e in (e0, e10, e10b))
    assert v0["M1/pr_auc"] != v10["M1/pr_auc"] and v10 == v10b


def _estados_para_varios():
    estados = {}
    for chave, (seed, base) in {"a": (5, 10), "b": (6, 12)}.items():
        _, _, estado = _estado_pequeno(seed=seed, n=1500, tolerante=True, completo=False,
                                       fluxo_base=base)
        estado[0].pontos()
        estados[chave] = estado
    return estados


def test_rodar_varios_da_o_mesmo_que_cada_estado_sozinho_com_1_ou_2_processos():
    sementes = m.sementes_das_reamostras(8, 6)
    referencia = {k: e[0].bloco(sementes) for k, e in _estados_para_varios().items()}
    um = m.rodar_varios(_estados_para_varios(), sementes, 1)
    dois = m.rodar_varios(_estados_para_varios(), sementes, 2)
    for chave, (colunas, iteracoes) in referencia.items():
        for resultado in (um, dois):
            assert resultado[chave][1] == iteracoes
            assert resultado[chave][0].keys() == colunas.keys()
            for nome, valores in colunas.items():
                assert np.array_equal(resultado[chave][0][nome], valores, equal_nan=True), nome


def test_rodar_varios_sem_estados_e_chave_com_separador():
    assert m.rodar_varios({}, m.sementes_das_reamostras(1, 2), 2) == {}
    estados = _estados_para_varios()
    estados["x||y"] = estados.pop("a")
    with pytest.raises(ValueError, match="separador"):
        m.rodar_varios(estados, m.sementes_das_reamostras(1, 2), 2)
