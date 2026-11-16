"""Testes do T-3.2: OR, RERI e AP, Benjamini-Hochberg, ranking e os relatórios (FR-05, FR-19, D-40).

Os testes de funções puras usam coeficientes e covariâncias inventados, com contas feitas à mão nos
comentários. O teste de integração ajusta o E1 com o gerador sintético da T-3.1 (`test_explain`).
Nada aqui lê `data/`.
"""

from types import SimpleNamespace

import numpy as np
import pytest
from test_explain import _cfg, _escrever_pares, _populacao_sintetica
from test_padrao_todas_sim import contagens_1_a_9_em_prosa

from dengue_sinan import explain
from dengue_sinan.profiling import COMORBIDADES

Z = explain.Z95
SEMENTE = 20261103
# OR_A = 2, OR_B = 3 e OR_AB = 2 · 3 · (5/3) = 10 (interação de 5/3).
THETA = np.array([np.log(2.0), np.log(3.0), np.log(5.0 / 3.0)])


def _e1_falso(colunas, beta, cov, nos=None, pares_incluidos=(), pvalues=None):
    """Um E1 mínimo: só o que as funções de OR leem (coeficientes, covariância, colunas e nós)."""
    beta = np.asarray(beta, dtype=float)
    cov = np.asarray(cov, dtype=float)
    resultados = SimpleNamespace(
        params=beta,
        bse=np.sqrt(np.diag(cov)),
        pvalues=np.full(len(beta), 0.5) if pvalues is None else np.asarray(pvalues, dtype=float),
        cov_params=lambda: cov,
    )
    return explain.E1Ajustado(
        resultados=resultados, colunas=list(colunas), nos=nos or {},
        pares_incluidos=list(pares_incluidos), pares_excluidos=[], eventos_por_termo={},
        n_casos=0, n_eventos=0, n_padroes=0, tempo_ajuste_s=0.0, log_verossimilhanca=0.0,
    )


# --- RERI e AP (conta à mão e método delta) ----------------------------------------------------

def test_reri_e_ap_batem_a_conta_a_mao():
    # OR_A = 2, OR_B = 3, OR_AB = 10. RERI = 10 − 2 − 3 + 1 = 6. AP = 6 / 10 = 0,6.
    r = explain.reri_ap_delta(THETA, np.zeros((3, 3)))
    assert r["or_a"] == pytest.approx(2.0)
    assert r["or_b"] == pytest.approx(3.0)
    assert r["or_ab"] == pytest.approx(10.0)
    assert r["reri"] == pytest.approx(6.0)
    assert r["ap"] == pytest.approx(0.6)


def test_delta_bate_formula_fechada_sem_covariancia_entre_termos():
    # Gradiente do RERI em (a, b, c): (E−A, E−B, E) = (8, 7, 10), com E = 10, A = 2, B = 3.
    #   variância = 64·0,01 + 49·0,04 + 100·0,0025 = 2,85.
    # Gradiente da AP: ((E−A−RERI)/E, (E−B−RERI)/E, (E−RERI)/E) = (0,2; 0,1; 0,4), RERI = 6.
    #   variância = 0,04·0,01 + 0,01·0,04 + 0,16·0,0025 = 0,0012.
    sigma = np.diag([0.01, 0.04, 0.0025])
    r = explain.reri_ap_delta(THETA, sigma)
    assert r["reri_ic"] == pytest.approx((6 - Z * np.sqrt(2.85), 6 + Z * np.sqrt(2.85)))
    assert r["ap_ic"] == pytest.approx((0.6 - Z * np.sqrt(0.0012), 0.6 + Z * np.sqrt(0.0012)))


def test_covariancia_entre_termos_entra_no_delta():
    # cov(a, c) = 0,001 soma 2 · 8 · 10 · 0,001 = 0,16 à variância do RERI: 2,85 + 0,16 = 3,01.
    sigma = np.diag([0.01, 0.04, 0.0025])
    sigma[0, 2] = sigma[2, 0] = 0.001
    r = explain.reri_ap_delta(THETA, sigma)
    assert r["reri_ic"] == pytest.approx((6 - Z * np.sqrt(3.01), 6 + Z * np.sqrt(3.01)))


def test_simulacao_concorda_com_o_delta_quando_a_incerteza_e_pequena():
    # Com pouca incerteza a aproximação linear é boa; a simulação deve bater com ela.
    sigma = np.diag([1e-4, 1e-4, 1e-4])
    delta = explain.reri_ap_delta(THETA, sigma)
    sim = explain.reri_ap_simulacao(THETA, sigma, np.random.default_rng(SEMENTE))
    assert sim["reri_ic"] == pytest.approx(delta["reri_ic"], abs=0.01)
    assert sim["ap_ic"] == pytest.approx(delta["ap_ic"], abs=0.01)


# --- Benjamini-Hochberg ------------------------------------------------------------------------

def test_bh_ajusta_como_o_exemplo_conhecido():
    # Em ordem: 0,005 · 4/1 = 0,02; 0,01 · 4/2 = 0,02; 0,03 · 4/3 = 0,04; 0,04 · 4/4 = 0,04.
    # Devolvidos na ordem de entrada: 0,01 → 0,02; 0,04 → 0,04; 0,03 → 0,04; 0,005 → 0,02.
    assert explain.ajustar_bh([0.01, 0.04, 0.03, 0.005]) == pytest.approx([0.02, 0.04, 0.04, 0.02])
    assert explain.ajustar_bh([]) == []


def test_medidas_sensiveis_ao_metodo_casos_construidos():
    # Base: delta e simulação concordam, com IC de RERI e AP fora do zero.
    base = {"reri_ic": (1.0, 2.0), "reri_sim_ic": (1.0, 2.0),
            "ap_ic": (0.1, 0.2), "ap_sim_ic": (0.1, 0.2)}
    assert explain.medidas_sensiveis_ao_metodo(base) == []
    # RERI: o delta exclui o zero e a simulação inclui.
    assert explain.medidas_sensiveis_ao_metodo({**base, "reri_sim_ic": (-0.5, 2.0)}) == ["RERI"]
    # AP: o mesmo caso, na outra medida.
    assert explain.medidas_sensiveis_ao_metodo({**base, "ap_sim_ic": (-0.1, 0.05)}) == ["AP"]
    # Ambas.
    ambos = {**base, "reri_sim_ic": (-0.5, 2.0), "ap_sim_ic": (-0.1, 0.05)}
    assert explain.medidas_sensiveis_ao_metodo(ambos) == ["RERI", "AP"]
    # Zero na borda conta como incluído (intervalo fechado): delta e simulação (0, 1) não divergem.
    assert explain.medidas_sensiveis_ao_metodo({**base, "reri_ic": (0.0, 1.0),
                                                "reri_sim_ic": (0.0, 1.0)}) == []
    # IC diferentes, mas os dois do mesmo lado do zero: não marca.
    assert explain.medidas_sensiveis_ao_metodo({**base, "reri_sim_ic": (1.5, 4.0)}) == []


def test_p_ajustado_no_caminho_or_interacoes_bate_com_bh_a_mao():
    # Exemplo conhecido (ver test_bh_ajusta_como_o_exemplo_conhecido): 0,01; 0,04; 0,03; 0,005
    # viram 0,02; 0,04; 0,04; 0,02, na ordem dos pares.
    colunas = ["Intercepto", "D: Sim", "H: Sim", "R: Sim", "A: Sim",
               "D x H", "D x R", "H x R", "R x A"]
    pares = [("D", "H"), ("D", "R"), ("H", "R"), ("R", "A")]
    pvalues = np.full(len(colunas), 0.5)
    pvalues[colunas.index("D x H")] = 0.01
    pvalues[colunas.index("D x R")] = 0.04
    pvalues[colunas.index("H x R")] = 0.03
    pvalues[colunas.index("R x A")] = 0.005
    e1 = _e1_falso(colunas, np.zeros(len(colunas)), np.eye(len(colunas)) * 0.01,
                   pares_incluidos=pares, pvalues=pvalues)
    linhas = explain.or_interacoes(e1)
    assert [r["p"] for r in linhas] == pytest.approx([0.01, 0.04, 0.03, 0.005])
    assert [r["p_ajustado"] for r in linhas] == pytest.approx([0.02, 0.04, 0.04, 0.02])


def test_or_principal_de_diabetes_e_hipertensa_aos_40_anos_e_exp_do_coeficiente():
    # Todos os efeitos principais e os splines da idade; aos 40 anos os splines zeram.
    colunas = ["Intercepto", *[f"{c}: Sim" for c in COMORBIDADES],
               *[f"DIABETES x Idade (spline) {j}" for j in (1, 2, 3)],
               *[f"HIPERTENSA x Idade (spline) {j}" for j in (1, 2, 3)]]
    beta = np.zeros(len(colunas))
    for k, c in enumerate(COMORBIDADES):
        beta[colunas.index(f"{c}: Sim")] = 0.3 + 0.1 * k
    for nome in colunas:
        if "spline" in nome:
            beta[colunas.index(nome)] = 0.05  # não entram aos 40 anos
    e1 = _e1_falso(colunas, beta, np.eye(len(colunas)) * 0.01,
                   nos={"idade_interacao": [0.0, 24.0, 43.0, 120.0]})
    efeitos = {r["comorbidade"]: r for r in explain.or_efeitos_principais(e1)}
    assert set(efeitos) == set(COMORBIDADES)
    for k, c in enumerate(COMORBIDADES):
        assert efeitos[c]["or"] == pytest.approx(np.exp(0.3 + 0.1 * k))
    assert efeitos["DIABETES"]["or"] == pytest.approx(np.exp(beta[colunas.index("DIABETES: Sim")]))
    assert efeitos["HIPERTENSA"]["or"] == pytest.approx(
        np.exp(beta[colunas.index("HIPERTENSA: Sim")]))


# --- Ranking (FR-19) ---------------------------------------------------------------------------

@pytest.mark.parametrize("ic_1, ic_2, esperado", [
    ((1.0, 2.0), (3.0, 4.0), False),   # disjuntos
    ((3.0, 4.0), (1.0, 2.0), False),   # disjuntos, ordem invertida
    ((1.0, 3.0), (2.0, 4.0), True),    # sobrepostos
    ((1.0, 10.0), (3.0, 4.0), True),   # um dentro do outro
    ((1.0, 2.0), (2.0, 3.0), True),    # tocam na borda
])
def test_sobreposicao_de_ics(ic_1, ic_2, esperado):
    assert explain.se_sobrepoe(ic_1, ic_2) is esperado
    assert explain.se_sobrepoe(ic_2, ic_1) is esperado


def test_ranking_marca_pares_sobrepostos_e_nao_e_transitivo():
    # A ~ B (2,5 ≤ 2,6), B ~ C (tocam em 1,5), mas A e C estão separados (2,5 > 1,5).
    principais = [
        {"comorbidade": "C", "or": 1.2, "ic_inferior": 1.0, "ic_superior": 1.5},
        {"comorbidade": "A", "or": 3.0, "ic_inferior": 2.5, "ic_superior": 4.0},
        {"comorbidade": "B", "or": 2.0, "ic_inferior": 1.5, "ic_superior": 2.6},
    ]
    r = explain.ranking_comorbidades(principais)
    assert [linha["comorbidade"] for linha in r["ordem"]] == ["A", "B", "C"]
    sem_ordem = {linha["comorbidade"]: linha["sem_ordem_com"] for linha in r["ordem"]}
    assert sem_ordem == {"A": ["B"], "B": ["A", "C"], "C": ["B"]}
    assert "C" not in sem_ordem["A"]
    assert r["pares_sem_ordem"] == [("A", "B"), ("B", "C")]


def test_ranking_sem_sobreposicao_nao_marca_nada():
    principais = [
        {"comorbidade": "X", "or": 4.0, "ic_inferior": 3.0, "ic_superior": 5.0},
        {"comorbidade": "Y", "or": 1.5, "ic_inferior": 1.2, "ic_superior": 1.9},
    ]
    r = explain.ranking_comorbidades(principais)
    assert r["pares_sem_ordem"] == []
    assert all(linha["sem_ordem_com"] == [] for linha in r["ordem"])


# --- OR por efeito e por idade -----------------------------------------------------------------

COLUNAS_IDADE = ["Intercepto", "RENAL: Sim", "DIABETES: Sim",
                 "DIABETES x Idade (spline) 1", "DIABETES x Idade (spline) 2",
                 "DIABETES x Idade (spline) 3"]


def _e1_com_idade(gamma_linear: float):
    # Base da interação com nós [0, 24, 43, 120]: a 1ª coluna é a própria idade (linear).
    beta = [0.0, 1.0, 0.8, gamma_linear, 0.0, 0.0]
    cov = np.eye(len(COLUNAS_IDADE)) * 0.01
    return _e1_falso(COLUNAS_IDADE, beta, cov, nos={"idade_interacao": [0.0, 24.0, 43.0, 120.0]})


def test_comorbidade_sem_termo_de_idade_nao_muda_com_a_idade():
    e1 = _e1_com_idade(0.02)
    assert explain.log_or_na_idade(e1, "RENAL", 20)["estimativa"] == pytest.approx(1.0)
    assert explain.log_or_na_idade(e1, "RENAL", 80)["estimativa"] == pytest.approx(1.0)


def test_or_de_diabetes_muda_com_a_idade_pelo_termo_de_interacao():
    # Aos 40 anos vale o efeito principal, 0,8. Aos 60, 0,8 + 0,02 · (60 − 40) = 1,2.
    e1 = _e1_com_idade(0.02)
    assert explain.log_or_na_idade(e1, "DIABETES", 40)["estimativa"] == pytest.approx(0.8)
    assert explain.log_or_na_idade(e1, "DIABETES", 60)["estimativa"] == pytest.approx(1.2)


def test_idades_representativas_seguem_as_faixas_do_profiling():
    # Meio de [0, 5), [5, 15), [15, 40), [40, 60), [60, 80); a faixa aberta 80+ usa 80.
    assert explain.idades_representativas() == [
        ("0–4", 2.5), ("5–14", 10.0), ("15–39", 27.5), ("40–59", 50.0), ("60–79", 70.0),
        ("80+", 80.0),
    ]


def test_or_por_faixa_usa_so_diabetes_e_hipertensa():
    colunas = ["Intercepto", "DIABETES: Sim", "HIPERTENSA: Sim",
               "DIABETES x Idade (spline) 1", "DIABETES x Idade (spline) 2",
               "DIABETES x Idade (spline) 3", "HIPERTENSA x Idade (spline) 1",
               "HIPERTENSA x Idade (spline) 2", "HIPERTENSA x Idade (spline) 3"]
    e1 = _e1_falso(colunas, np.zeros(len(colunas)), np.eye(len(colunas)) * 0.01,
                   nos={"idade_interacao": [0.0, 24.0, 43.0, 120.0]})
    linhas = explain.or_por_faixa(e1)
    assert [linha["faixa"] for linha in linhas] == ["0–4", "5–14", "15–39", "40–59", "60–79", "80+"]
    assert set(linhas[0]) == {"faixa", "idade", "DIABETES", "HIPERTENSA"}
    assert linhas[0]["DIABETES"]["or"] == pytest.approx(1.0)  # coeficientes zerados: OR = 1


# --- Integração com um E1 ajustado em dados sintéticos -----------------------------------------

@pytest.fixture(scope="module")
def ajuste(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("or")
    cfg = _cfg(tmp)
    df = _populacao_sintetica()
    # O gerador da T-3.1 deixa todos os 21 pares com >= 10 eventos. Para testar a exclusão,
    # zera-se o desfecho dos casos com DIABETES e AUTO_IMUNE: esse par fica com 0 eventos.
    df.loc[(df["DIABETES"] == "Sim") & (df["AUTO_IMUNE"] == "Sim"), "y"] = 0
    _escrever_pares(cfg, df)
    e1 = explain.ajustar_e1(cfg, df)
    explain.salvar_e1(cfg, e1)
    return cfg, e1


def _indice(e1, nome):
    return e1.colunas.index(nome)


def test_pares_excluidos_nao_aparecem_nas_tabelas_de_or_e_reri(ajuste):
    _, e1 = ajuste
    assert e1.pares_excluidos, "o teste precisa de ao menos um par com eventos insuficientes"
    excluidos = {frozenset(p) for p in e1.pares_excluidos}
    for tabela in (explain.or_interacoes(e1), explain.reri_ap_pares(e1, seed=SEMENTE)):
        pares = {frozenset((r["comorbidade_1"], r["comorbidade_2"])) for r in tabela}
        assert not pares & excluidos
        assert len(tabela) == len(e1.pares_incluidos)


def test_or_de_interacao_e_exp_do_coeficiente_do_produto(ajuste):
    _, e1 = ajuste
    beta = np.asarray(e1.resultados.params)
    for r in explain.or_interacoes(e1):
        i = _indice(e1, f"{r['comorbidade_1']} x {r['comorbidade_2']}")
        assert r["or"] == pytest.approx(np.exp(beta[i]))
        assert r["ic_inferior"] < r["or"] < r["ic_superior"]


def test_reri_e_ap_do_modelo_batem_com_os_or_dos_coeficientes(ajuste):
    # OR_AB = exp(β_A + β_B + β_AB), aos 40 anos: a mesma conta à mão, feita com os coeficientes.
    _, e1 = ajuste
    beta = np.asarray(e1.resultados.params)
    for r in explain.reri_ap_pares(e1, seed=SEMENTE):
        a, b = r["comorbidade_1"], r["comorbidade_2"]
        ou_a = np.exp(beta[_indice(e1, f"{a}: Sim")])
        ou_b = np.exp(beta[_indice(e1, f"{b}: Sim")])
        ou_ab = np.exp(beta[_indice(e1, f"{a}: Sim")] + beta[_indice(e1, f"{b}: Sim")]
                       + beta[_indice(e1, f"{a} x {b}")])
        assert r["or_a"] == pytest.approx(ou_a)
        assert r["or_ab"] == pytest.approx(ou_ab)
        assert r["reri"] == pytest.approx(ou_ab - ou_a - ou_b + 1)
        assert r["ap"] == pytest.approx(r["reri"] / ou_ab)


CONTEXTO_FALSO = {  # o que `contexto_padrao` daria com um ajuste de cenário A inventado
    "casos_padrao": 2000, "casos": 2453208,
    "pares_sensiveis": [("HEMATOLOG", "HEPATOPAT")],
    "ranking_principal": ["DIABETES", "HEMATOLOG", "HEPATOPAT", "RENAL", "HIPERTENSA",
                          "ACIDO_PEPT", "AUTO_IMUNE"],
    "ranking_a": ["DIABETES", "HEPATOPAT", "HEMATOLOG", "RENAL", "HIPERTENSA", "ACIDO_PEPT",
                  "AUTO_IMUNE"],
}


def test_executar_or_grava_os_tres_relatorios_com_aviso_p6(ajuste, monkeypatch):
    cfg, e1 = ajuste
    # Os ajustes de sensibilidade não existem neste tmp (são da execução real): o contexto vem
    # de um cenário A inventado. Ler os pickles reais está coberto em test_padrao_todas_sim.
    monkeypatch.setattr(explain, "contexto_padrao", lambda _cfg: CONTEXTO_FALSO)
    caminhos = explain.executar_or(cfg)
    assert set(caminhos) == {"or_interacoes", "reri_ap", "ranking"}
    for caminho in caminhos.values():
        assert caminho.exists()
        texto = caminho.read_text(encoding="utf-8")
        assert texto.startswith("# ")
        assert explain.AVISO_P6 in texto
    assert "Sem ordem definida" in caminhos["ranking"].read_text(encoding="utf-8")
    # R7 também na prosa dos três relatórios (mesma varredura de test_padrao_todas_sim).
    for caminho in caminhos.values():
        assert contagens_1_a_9_em_prosa(caminho.read_text(encoding="utf-8")) == [], caminho
    # A nota do padrão é a mesma nos três relatórios (T-3.2, pedido do Programador).
    nota = explain.nota_padrao(CONTEXTO_FALSO)[0]
    for caminho in caminhos.values():
        assert nota in caminho.read_text(encoding="utf-8")
    tabelas = [caminhos["or_interacoes"].read_text(encoding="utf-8"),
               caminhos["reri_ap"].read_text(encoding="utf-8")]
    for a, b in e1.pares_excluidos:
        for texto in tabelas:
            assert f"{a} × {b}" not in texto and f"{b} × {a}" not in texto
