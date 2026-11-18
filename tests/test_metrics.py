"""Testes das métricas (T-2.4) com casos pequenos calculados à mão e dados sintéticos.

Nenhum microdado real. Sementes sempre por parâmetro (R8).
"""

import numpy as np
import pytest

from dengue_sinan import metrics

# Exemplo usado em vários testes: y = [1, 1, 1, 0, 0], p = [0.9, 0.4, 0.3, 0.2, 0.1].
Y_EXEMPLO = np.array([1, 1, 1, 0, 0])
P_EXEMPLO = np.array([0.9, 0.4, 0.3, 0.2, 0.1])


# --- F2, F1 e limiar -----------------------------------------------------------------------------


def test_threshold_metrics_f2_de_exemplo_conhecido():
    # Limiar 0,5: prevê positivo só o caso 0.9. VP = 1, FP = 0, FN = 2, VN = 2.
    # precisão = 1/1 = 1; recall = 1/3.
    # F2 = 5·P·R / (4·P + R) = (5/3) / (13/3) = 5/13 ≈ 0,3846.
    # F1 = 2·P·R / (P + R) = (2/3) / (4/3) = 0,5. Acurácia = (1 + 2)/5 = 0,6.
    r = metrics.threshold_metrics(Y_EXEMPLO, P_EXEMPLO, 0.5)
    assert r["precisao"] == pytest.approx(1.0)
    assert r["recall"] == pytest.approx(1 / 3)
    assert r["f2"] == pytest.approx(5 / 13)
    assert r["f1"] == pytest.approx(0.5)
    assert r["acuracia"] == pytest.approx(0.6)


def test_threshold_metrics_sem_previsao_positiva_nao_divide_por_zero():
    # Limiar 0,95: ninguém é positivo. Precisão e F2 viram 0 por convenção; recall = 0.
    r = metrics.threshold_metrics(Y_EXEMPLO, P_EXEMPLO, 0.95)
    assert r["precisao"] == 0.0
    assert r["recall"] == 0.0
    assert r["f2"] == 0.0


def test_best_f2_threshold_escolhe_o_limiar_de_maior_f2():
    # F2 por limiar (candidatos = valores de p):
    #   0,9 -> VP 1, FP 0, FN 2 -> 5/13 = 0,385
    #   0,4 -> VP 2, FP 0, FN 1 -> 10/14 = 0,714
    #   0,3 -> VP 3, FP 0, FN 0 -> 1,000   <- máximo
    #   0,2 -> VP 3, FP 1, FN 0 -> 15/16 = 0,938
    #   0,1 -> VP 3, FP 2, FN 0 -> 15/17 = 0,882
    assert metrics.best_f2_threshold(Y_EXEMPLO, P_EXEMPLO) == pytest.approx(0.3)


# --- Limiar de precisão máxima com recall mínimo (D-92) -----------------------------------------
#
# Mesmo exemplo: precisão e recall por limiar (candidatos = valores de p):
#   0,9 -> VP 1, FP 0 -> precisão 1,00, recall 1/3
#   0,4 -> VP 2, FP 0 -> precisão 1,00, recall 2/3
#   0,3 -> VP 3, FP 0 -> precisão 1,00, recall 1
#   0,2 -> VP 3, FP 1 -> precisão 0,75, recall 1
#   0,1 -> VP 3, FP 2 -> precisão 0,60, recall 1


def test_min_recall_exemplo_a_mao_empate_de_precisao_vai_para_o_maior_limiar():
    # recall ≥ 2/3: sobram 0,4, 0,3, 0,2 e 0,1. Precisão 1 em 0,4 e 0,3: empate, vale 0,4.
    assert metrics.threshold_for_min_recall(Y_EXEMPLO, P_EXEMPLO, 2 / 3) == pytest.approx(0.4)


def test_min_recall_acima_de_2_3_exclui_o_limiar_04():
    # recall ≥ 0,7: sobram 0,3, 0,2 e 0,1. Maior precisão é 1, em 0,3.
    assert metrics.threshold_for_min_recall(Y_EXEMPLO, P_EXEMPLO, 0.7) == pytest.approx(0.3)


def test_min_recall_igual_ao_recall_de_um_limiar_conta_sem_folga():
    # recall ≥ 1/3 exatamente: 0,9 entra (recall 1/3), tem precisão 1 e é o maior limiar com
    # precisão 1. Com ">" em vez de "≥" o resultado seria 0,4: o teste pega essa troca.
    assert metrics.threshold_for_min_recall(Y_EXEMPLO, P_EXEMPLO, 1 / 3) == pytest.approx(0.9)


def test_min_recall_1_escolhe_a_maior_precisao_que_pega_todos_os_eventos():
    # recall = 1: 0,3, 0,2 e 0,1. A precisão cai com o limiar, então 0,3 vence.
    assert metrics.threshold_for_min_recall(Y_EXEMPLO, P_EXEMPLO, 1.0) == pytest.approx(0.3)


def test_min_recall_zero_devolve_o_maior_limiar_de_precisao_maxima():
    # recall ≥ 0 libera tudo: precisão 1 em 0,9, 0,4 e 0,3. Empate: o maior, 0,9.
    assert metrics.threshold_for_min_recall(Y_EXEMPLO, P_EXEMPLO, 0.0) == pytest.approx(0.9)


def test_min_recall_score_constante_devolve_o_unico_valor():
    # B0: um só candidato. Recall 1 para qualquer recall_min ≤ 1.
    p = np.full(5, 0.4)
    y = np.array([1, 1, 0, 0, 0])
    assert metrics.threshold_for_min_recall(y, p, 0.6843) == pytest.approx(0.4)
    assert metrics.threshold_for_min_recall(y, p, 1.0) == pytest.approx(0.4)


def test_min_recall_bate_com_a_busca_bruta_em_dados_aleatorios():
    # Confere contra a definição, sem atalho: testa todo candidato, filtra por recall e pega a
    # maior precisão, com empate para o maior limiar.
    rng = np.random.default_rng(42)
    for _ in range(50):
        n = 60
        y = (rng.uniform(size=n) < 0.2).astype(int)
        y[0] = 1
        p = np.round(rng.uniform(size=n), 1)  # poucos valores distintos: empates de propósito
        recall_min = float(rng.choice([0.0, 0.3, 0.5, 0.6843, 0.9, 1.0]))

        melhor = None
        for t in sorted(set(p.tolist())):
            r = metrics.threshold_metrics(y, p, t)
            if r["recall"] >= recall_min:
                if melhor is None or r["precisao"] >= melhor[1]:
                    melhor = (t, r["precisao"])  # o último de maior precisão é o maior limiar
        esperado = melhor[0]

        assert metrics.threshold_for_min_recall(y, p, recall_min) == pytest.approx(esperado)


def test_min_recall_resultado_atinge_o_recall_minimo():
    rng = np.random.default_rng(7)
    y = (rng.uniform(size=200) < 0.1).astype(int)
    y[0] = 1
    p = rng.uniform(size=200)
    for recall_min in (0.1, 0.5, 0.6843, 0.95):
        t = metrics.threshold_for_min_recall(y, p, recall_min)
        assert metrics.threshold_metrics(y, p, t)["recall"] >= recall_min


def test_min_recall_recusa_recall_fora_de_0_1():
    with pytest.raises(ValueError, match="recall_min"):
        metrics.threshold_for_min_recall(Y_EXEMPLO, P_EXEMPLO, 1.2)
    with pytest.raises(ValueError, match="recall_min"):
        metrics.threshold_for_min_recall(Y_EXEMPLO, P_EXEMPLO, -0.1)
    with pytest.raises(ValueError, match="recall_min"):
        metrics.threshold_for_min_recall(Y_EXEMPLO, P_EXEMPLO, float("nan"))


def test_min_recall_sem_eventos_levanta_erro():
    with pytest.raises(ValueError, match="sem eventos"):
        metrics.threshold_for_min_recall([0, 0, 0], [0.1, 0.5, 0.9], 0.5)


def test_min_recall_recusa_p_vazio_e_tamanho_diferente():
    with pytest.raises(ValueError, match="vazio"):
        metrics.threshold_for_min_recall([], [], 0.5)
    with pytest.raises(ValueError, match="mesmo tamanho"):
        metrics.threshold_for_min_recall([1, 0], [0.5], 0.5)


# --- Ranking e calibração ------------------------------------------------------------------------


def test_pr_auc_do_preditor_perfeito_e_1():
    assert metrics.pr_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == pytest.approx(1.0)


def test_pr_auc_do_preditor_constante_e_a_prevalencia():
    # 2 positivos em 5 casos: prevalência 0,4. Preditor constante = prevalência.
    y = [1, 1, 0, 0, 0]
    assert metrics.pr_auc(y, [0.3] * 5) == pytest.approx(0.4)


def test_roc_auc_do_preditor_perfeito_e_1():
    assert metrics.roc_auc([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9]) == pytest.approx(1.0)


def test_brier_de_exemplo_conhecido():
    # y = [1, 0], p = [0,8, 0,2]: erros (1 − 0,8)² = 0,04 e (0 − 0,2)² = 0,04; média = 0,04.
    assert metrics.brier([1, 0], [0.8, 0.2]) == pytest.approx(0.04)


def test_calibracao_perfeita_tem_slope_1_e_intercept_0():
    rng = np.random.default_rng(20261103)
    logit_verdadeiro = rng.normal(-3.0, 1.5, 200_000)
    p = 1 / (1 + np.exp(-logit_verdadeiro))
    y = rng.binomial(1, p)

    slope, intercept = metrics.calibration_slope_intercept(y, p)

    assert slope == pytest.approx(1.0, abs=0.03)
    assert intercept == pytest.approx(0.0, abs=0.03)


def test_calibracao_superconfiante_tem_slope_perto_de_meio():
    # Previsões em escala logit dobrada: o modelo é 2× confiante demais.
    # A logística de y em logit(p') tem coeficiente ≈ 1/2.
    rng = np.random.default_rng(20261103)
    logit_verdadeiro = rng.normal(-3.0, 1.5, 200_000)
    p_verdadeiro = 1 / (1 + np.exp(-logit_verdadeiro))
    y = rng.binomial(1, p_verdadeiro)
    p_confiante = 1 / (1 + np.exp(-2 * logit_verdadeiro))

    slope, intercept = metrics.calibration_slope_intercept(y, p_confiante)

    assert slope == pytest.approx(0.5, abs=0.05)
    # Intercepto com offset: 1,46 medido (escala 2·logit sem deslocamento); ver teste de 2L + 0,5.
    assert intercept == pytest.approx(1.46, abs=0.05)


# --- Net benefit ---------------------------------------------------------------------------------


def test_net_benefit_tratar_todos_bate_com_a_formula():
    # y = [1, 1, 0, 0]: prevalência 0,5. Em pt = 0,2, pt/(1−pt) = 0,25.
    # NB tratar todos = 0,5 − 0,5 × 0,25 = 0,375. Tratar ninguém = 0.
    y = [1, 1, 0, 0]
    p = [0.9, 0.4, 0.3, 0.1]
    df = metrics.net_benefit(y, p, [0.2])

    assert list(df.columns) == ["limiar", "modelo", "tratar_todos", "tratar_ninguem"]
    assert df["tratar_todos"].iloc[0] == pytest.approx(0.375)
    assert df["tratar_ninguem"].iloc[0] == 0.0


def test_net_benefit_do_modelo_bate_com_a_formula():
    # y = [1, 1, 0, 0], p = [0,9; 0,4; 0,3; 0,1].
    # pt = 0,5: positivos = {0,9}, VP = 1, FP = 0 -> NB = 1/4 = 0,25.
    # pt = 0,2: positivos = {0,9; 0,4; 0,3}, VP = 2, FP = 1 -> NB = 2/4 − (1/4)·0,25 = 0,4375.
    y = [1, 1, 0, 0]
    p = [0.9, 0.4, 0.3, 0.1]
    df = metrics.net_benefit(y, p, [0.5, 0.2]).set_index("limiar")

    assert df.loc[0.5, "modelo"] == pytest.approx(0.25)
    assert df.loc[0.2, "modelo"] == pytest.approx(0.4375)


def test_net_benefit_rejeita_limiar_fora_de_0_1():
    with pytest.raises(ValueError):
        metrics.net_benefit([1, 0], [0.8, 0.2], [0.0])


# --- Bootstrap -----------------------------------------------------------------------------------


def test_bootstrap_ci_estratificado_preserva_o_numero_de_positivos():
    # Com reamostragem estratificada por y, toda reamostra tem exatamente 3 positivos.
    y = np.array([1, 1, 1, 0, 0, 0, 0, 0])
    p = np.linspace(0, 1, 8)

    est, ic_inf, ic_sup = metrics.bootstrap_ci(lambda yy, pp: float(yy.sum()), y, p, 50, 1)

    assert (est, ic_inf, ic_sup) == (3.0, 3.0, 3.0)


def test_bootstrap_ci_mesma_semente_mesmo_resultado():
    rng = np.random.default_rng(7)
    y = rng.binomial(1, 0.2, 500)
    p = rng.uniform(size=500)

    a = metrics.bootstrap_ci(metrics.pr_auc, y, p, 30, seed=11)
    b = metrics.bootstrap_ci(metrics.pr_auc, y, p, 30, seed=11)

    assert a == b


def test_paired_bootstrap_diff_com_p_iguais_da_zero_e_ic_zero():
    rng = np.random.default_rng(3)
    n = 2_000
    y = rng.binomial(1, 0.1, n)
    p = rng.uniform(size=n)
    dobra = np.repeat(["Sudeste", "Sul", "Norte", "Nordeste", "Centro-Oeste"], n // 5)

    diferenca, ic_inf, ic_sup = metrics.paired_bootstrap_diff(
        metrics.pr_auc, y, p, p.copy(), dobra, n=100, seed=20261103
    )

    assert diferenca == 0.0
    assert (ic_inf, ic_sup) == (0.0, 0.0)


def test_paired_bootstrap_diff_detecta_modelo_melhor():
    # Modelo A separa perfeitamente os positivos; B dá a mesma probabilidade a todos.
    # PR-AUC de B por dobra = prevalência da dobra.
    # A diferença esperada é 1 − média das prevalências das cinco dobras.
    rng = np.random.default_rng(5)
    dobras = ["Sudeste", "Sul", "Norte", "Nordeste", "Centro-Oeste"]
    n_por_dobra = 400
    y = np.concatenate([rng.binomial(1, 0.1, n_por_dobra) for _ in dobras])
    dobra = np.repeat(dobras, n_por_dobra)
    # Garante pelo menos um positivo e um negativo em cada dobra.
    for k in range(len(dobras)):
        y[k * n_por_dobra] = 1
        y[k * n_por_dobra + 1] = 0
    p_a = 0.05 + 0.9 * y
    p_b = np.full(len(y), 0.5)

    prevalencias = [y[dobra == d].mean() for d in dobras]
    esperada = 1 - np.mean(prevalencias)

    diferenca, ic_inf, ic_sup = metrics.paired_bootstrap_diff(
        metrics.pr_auc, y, p_a, p_b, dobra, n=200, seed=20261103
    )

    assert diferenca == pytest.approx(esperada)
    assert 0 < ic_inf <= diferenca <= ic_sup


def test_paired_bootstrap_diff_recusa_tamanhos_diferentes():
    with pytest.raises(ValueError):
        metrics.paired_bootstrap_diff(
            metrics.pr_auc, [1, 0, 1], [0.1, 0.2], [0.1, 0.2, 0.3], ["a", "a", "a"], n=2, seed=1
        )


def test_paired_bootstrap_diff_escala_moderada_roda_com_vetores_grandes():
    # Escala moderada (300 mil linhas, 5 dobras, 5 reamostras): checa vetorização e forma.
    # Não é o tamanho real (~2,45 milhões de linhas), que só roda na T-4.9.
    rng = np.random.default_rng(9)
    dobras = np.repeat(["a", "b", "c", "d", "e"], 60_000)
    y = rng.binomial(1, 0.02, dobras.size)
    p_a = np.clip(0.02 + 0.5 * y + rng.normal(0, 0.05, y.size), 0, 1)
    p_b = rng.uniform(size=y.size)

    diferenca, ic_inf, ic_sup = metrics.paired_bootstrap_diff(
        metrics.pr_auc, y, p_a, p_b, dobras, n=5, seed=20261103
    )

    assert np.isfinite([diferenca, ic_inf, ic_sup]).all()
    assert ic_inf <= ic_sup


# --- Intercepto com offset (calibration-in-the-large) versus ajuste livre -------------------------


def _logit_verdadeiro_e_y(n: int = 400_000, seed: int = 20261103):
    """Logit verdadeiro L ~ N(−3; 1,5) e y ~ Bernoulli(expit(L)). Semente fixa (R8)."""
    rng = np.random.default_rng(seed)
    logit_real = rng.normal(-3.0, 1.5, n)
    y = rng.binomial(1, 1 / (1 + np.exp(-logit_real)))
    return logit_real, y


def _ajuste_livre_statsmodels(y, logit_pred) -> tuple[float, float]:
    """Referência independente: logística de y em logit(p) com slope livre (sem offset)."""
    import statsmodels.api as sm

    X = sm.add_constant(logit_pred, has_constant="add")
    resultado = sm.GLM(y, X, family=sm.families.Binomial()).fit()
    return float(resultado.params[1]), float(resultado.params[0])  # (slope, intercepto)


def test_intercepto_com_offset_recupera_deslocamento_de_meio_logit():
    # Previsão com logit = logit_real + 0,5 (superestima o risco). Com offset, o intercepto
    # estima −0,5. Medido: −0,4987 em n = 400 mil. Tolerância 0,03 ≈ 3–4 erros-padrão.
    # Atenção: neste caso o ajuste livre também dá −0,5 (slope = 1), então este teste sozinho
    # não distingue as duas definições; quem distingue é o teste da escala 2·logit + 0,5.
    logit_real, y = _logit_verdadeiro_e_y()
    p = 1 / (1 + np.exp(-(logit_real + 0.5)))

    _, intercept = metrics.calibration_slope_intercept(y, p)

    assert intercept == pytest.approx(-0.5, abs=0.03)


def test_intercepto_com_offset_difere_do_ajuste_livre_em_miscalibracao_de_escala():
    # Previsão com logit = 2·logit_real + 0,5. O verdadeiro efeito de logit_pred é 0,5 (slope)
    # e −0,25 (intercepto livre). Com offset, o coeficiente fica fixo em 1 e o intercepto
    # vale ≈ 0,96 (medido). Se o código usasse ajuste livre, daria −0,25 e este teste falha.
    logit_real, y = _logit_verdadeiro_e_y()
    logit_pred = 2 * logit_real + 0.5
    p = 1 / (1 + np.exp(-logit_pred))

    slope_offset, intercept_offset = metrics.calibration_slope_intercept(y, p)
    slope_livre, intercept_livre = _ajuste_livre_statsmodels(y, logit_pred)

    assert slope_offset == pytest.approx(0.5, abs=0.03)
    assert intercept_offset == pytest.approx(0.96, abs=0.05)
    # Referência independente (statsmodels com slope livre): intercepto ≈ −0,25.
    assert intercept_livre == pytest.approx(-0.25, abs=0.05)
    assert slope_livre == pytest.approx(0.5, abs=0.03)
    # Os dois interceptos têm que ser claramente diferentes.
    assert intercept_offset - intercept_livre > 0.5


# --- Índices pareados -----------------------------------------------------------------------------


def test_paired_bootstrap_diff_usa_os_mesmos_indices_para_os_dois_modelos():
    # fn = média de p. Com p_b = p_a + 0,1 e os mesmos índices nas duas predições, a diferença
    # média_a − média_b é exatamente −0,1 em toda reamostra: IC [−0,1; −0,1].
    # Se os índices fossem sorteados separadamente para A e B, o IC teria largura > 0.
    rng = np.random.default_rng(42)
    dobras = ["Sudeste", "Sul", "Norte", "Nordeste", "Centro-Oeste"]
    n_por_dobra = 300
    y = rng.binomial(1, 0.15, n_por_dobra * len(dobras))
    dobra = np.repeat(dobras, n_por_dobra)
    p_a = rng.uniform(size=y.size)
    p_b = p_a + 0.1

    diferenca, ic_inf, ic_sup = metrics.paired_bootstrap_diff(
        lambda yy, pp: float(np.mean(pp)), y, p_a, p_b, dobra, n=50, seed=20261103
    )

    assert diferenca == pytest.approx(-0.1)
    assert ic_inf == pytest.approx(-0.1)
    assert ic_sup == pytest.approx(-0.1)


# --- Bootstrap pareado vetorizado (T-4.9, D-53) --------------------------------------------------


def _dados_pareados(seed: int = 3, n_por_dobra: int = 3_000):
    """Cinco dobras, três modelos (um com empates): dados pequenos, para a referência."""
    rng = np.random.default_rng(seed)
    dobras = ["Sudeste", "Sul", "Norte", "Nordeste", "Centro-Oeste"]
    dobra = np.repeat(dobras, n_por_dobra)
    y = (rng.uniform(size=dobra.size) < 0.05).astype(int)
    for d in dobras:  # garante positivo em cada dobra
        y[np.flatnonzero(dobra == d)[0]] = 1
    p_a = np.clip(0.05 + 0.3 * y + rng.normal(0, 0.1, y.size), 0, 1)
    p_b = np.round(np.clip(0.02 + 0.2 * y + rng.normal(0, 0.15, y.size), 0, 1), 2)  # com empates
    p_c = np.full(y.size, float(y.mean()))  # constante, como B0
    return y, dobra, p_a, p_b, p_c


@pytest.mark.parametrize("par", [("a", "b"), ("a", "c"), ("b", "c")])
def test_bootstrap_vetorizado_concorda_com_paired_bootstrap_diff(par):
    y, dobra, p_a, p_b, p_c = _dados_pareados()
    escores = {"a": p_a, "b": p_b, "c": p_c}
    n, seed = 40, 20261103

    vet = metrics.paired_bootstrap_pr_auc(escores, y, dobra, n=n, seed=seed)
    x, z = par
    ref = metrics.paired_bootstrap_diff(metrics.pr_auc, y, escores[x], escores[z], dobra,
                                        n=n, seed=seed)

    dif = vet["media"][x] - vet["media"][z]
    estimativa = np.mean([metrics.pr_auc(y[dobra == d], escores[x][dobra == d])
                          - metrics.pr_auc(y[dobra == d], escores[z][dobra == d])
                          for d in vet["dobras"]])
    ic_inf, ic_sup = np.quantile(dif, (0.025, 0.975))

    assert estimativa == pytest.approx(ref[0], abs=1e-10)
    assert ic_inf == pytest.approx(ref[1], abs=1e-10)
    assert ic_sup == pytest.approx(ref[2], abs=1e-10)


def test_bootstrap_vetorizado_usa_os_mesmos_sorteios_para_todos_os_modelos():
    # Um modelo duplicado tem que dar diferença exatamente zero em toda reamostra. Se os
    # sorteios fossem independentes, a diferença teria variância.
    y, dobra, p_a, p_b, _ = _dados_pareados()
    vet = metrics.paired_bootstrap_pr_auc({"a": p_a, "a_copia": p_a.copy(), "b": p_b}, y, dobra,
                                          n=50, seed=20261103)

    assert np.all(vet["media"]["a"] - vet["media"]["a_copia"] == 0.0)
    assert np.std(vet["media"]["a"] - vet["media"]["b"]) > 0


def test_bootstrap_vetorizado_recusa_dobra_sem_positivo():
    y = np.array([0, 1, 0, 0])
    dobra = np.array(["a", "a", "b", "b"])
    with pytest.raises(ValueError, match="sem positivos"):
        metrics.paired_bootstrap_pr_auc({"m": np.array([0.1, 0.2, 0.3, 0.4])}, y, dobra, n=2,
                                        seed=1)


def test_pr_auc_ponderada_por_contagens_bate_com_linhas_repetidas():
    # Peso = nº de cópias da linha: a PR-AUC com pesos tem que ser igual à de linhas repetidas.
    rng = np.random.default_rng(8)
    p = np.round(rng.uniform(size=60), 1)  # com empates de propósito
    y = rng.binomial(1, 0.3, 60)
    y[0] = 1
    pesos = rng.integers(0, 4, 60)
    repetidas_y = np.repeat(y, pesos)
    repetidas_p = np.repeat(p, pesos)
    if repetidas_y.sum() == 0:
        pytest.skip("amostra sem positivo")

    ordem, fins, yo = metrics._ordenar_por_escore(p, y.astype(np.int64))
    com_pesos = metrics._pr_auc_com_pesos(pesos[ordem].astype(np.int64), fins, yo)

    assert com_pesos == pytest.approx(metrics.pr_auc(repetidas_y, repetidas_p), abs=1e-12)
