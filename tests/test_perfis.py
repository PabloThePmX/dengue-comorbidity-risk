"""Testes da tabela de perfis (T-3.5, FR-06, D-52): lista de perfis, risco e razão pelo delta,
supressão (R7) e notas.

Os testes de funções puras usam coeficientes inventados, com as contas feitas à mão nos
comentários. Um teste de integração ajusta o E1 com o gerador sintético de `test_explain`.
Nada aqui lê `data/`.
"""

import math
from collections import Counter
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from test_explain import _cfg, _escrever_pares, _populacao_sintetica
from test_padrao_todas_sim import contagens_1_a_9_em_prosa

from dengue_sinan import explain
from dengue_sinan.profiling import COMORBIDADES

Z = explain.Z95
IDADES = np.linspace(0.0, 100.0, 201)
PARES_E1 = explain.PARES[:15]     # entram no E1 (15)
PARES_FORA = explain.PARES[15:]   # dados insuficientes (6)
DIABETES = explain._mascara(("DIABETES",))


def _expit(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-x))


def _e1_falso(beta: dict | None = None, cov: dict | None = None, incluidos=None,
              excluidos=None) -> explain.E1Ajustado:
    """E1 mínimo com colunas e nós reais (mesmo `matriz_de_desenho` do ajuste) e β/Σ inventados."""
    incluidos = list(PARES_E1 if incluidos is None else incluidos)
    excluidos = list(PARES_FORA if excluidos is None else excluidos)
    nos = {"idade": explain._nos(IDADES, explain.GL_IDADE),
           "idade_interacao": explain._nos(IDADES, explain.GL_IDADE_INTERACAO)}
    molde = pd.DataFrame([{"idade_anos": 40.0, "sexo": "F", "gestante": 0,
                           **{c: "Não" for c in COMORBIDADES}}])
    colunas = list(explain.matriz_de_desenho(molde, nos, incluidos).columns)
    p = len(colunas)
    b = np.zeros(p)
    for nome, valor in (beta or {}).items():
        b[colunas.index(nome)] = valor
    sigma = np.zeros((p, p))
    for (a, c), valor in (cov or {}).items():
        i, j = colunas.index(a), colunas.index(c)
        sigma[i, j] = sigma[j, i] = valor
    resultados = SimpleNamespace(params=b, bse=np.sqrt(np.diag(sigma)),
                                 pvalues=np.full(p, 0.5), cov_params=lambda: sigma)
    return explain.E1Ajustado(
        resultados=resultados, colunas=colunas, nos=nos, pares_incluidos=incluidos,
        pares_excluidos=excluidos, eventos_por_termo={}, n_casos=0, n_eventos=0, n_padroes=0,
        tempo_ajuste_s=0.0, log_verossimilhanca=0.0,
    )


def _celulas(linhas) -> pd.DataFrame:
    return pd.DataFrame(linhas, columns=["mascara", "faixa_etaria", "sexo", "gestante", "casos"])


def _combinacoes(linhas) -> pd.DataFrame:
    return pd.DataFrame(linhas, columns=["combinacao", "n_comorbidades", "casos", "eventos"])


BETA_DIABETES = {"Intercepto": -5.0, "DIABETES: Sim": 0.8}
COV_DIABETES = {("Intercepto", "Intercepto"): 0.09,
                ("DIABETES: Sim", "DIABETES: Sim"): 0.04,
                ("Intercepto", "DIABETES: Sim"): 0.01}


# --- Risco e razão pelo método delta -----------------------------------------------------------

def test_risco_delta_na_escala_do_logit_bate_a_conta_a_mao():
    # Aos 40 anos o termo DIABETES x Idade vale zero (centrado em 40). η = −5 + 0,8 = −4,2.
    # Var(η) = 0,09 + 0,04 + 2·0,01 = 0,15: a covariância entre intercepto e DIABETES entra.
    e1 = _e1_falso(BETA_DIABETES, COV_DIABETES)
    r = explain.risco_perfil(e1, 40, "F", 0, ("DIABETES",))
    erro = math.sqrt(0.15)
    assert r["logit"] == pytest.approx(-4.2)
    assert r["erro_logit"] == pytest.approx(erro)
    assert r["risco"] == pytest.approx(_expit(-4.2))  # ≈ 0,01477
    assert r["ic_inferior"] == pytest.approx(_expit(-4.2 - Z * erro))
    assert r["ic_superior"] == pytest.approx(_expit(-4.2 + Z * erro))
    assert r["ic_inferior"] < r["risco"] < r["ic_superior"]


def test_razao_delta_do_perfil_contra_saudavel_bate_a_conta_a_mao():
    # Saudável aos 40 anos: η0 = −5. Perfil DIABETES: d = x − x0 tem só DIABETES = 1, então
    # log RR = 0,8 e Var(log RR) = dᵀΣd = 0,04 (o intercepto se cancela). EP = 0,2.
    e1 = _e1_falso(BETA_DIABETES, COV_DIABETES)
    r = explain.razao_de_risco(e1, 40, "F", 0, ("DIABETES",))
    assert r["log_razao"] == pytest.approx(0.8)
    assert r["erro_log_razao"] == pytest.approx(0.2)
    assert r["razao"] == pytest.approx(math.exp(0.8))
    assert r["ic_inferior"] == pytest.approx(math.exp(0.8 - Z * 0.2))
    assert r["ic_superior"] == pytest.approx(math.exp(0.8 + Z * 0.2))


def test_razao_delta_usa_a_covariancia_entre_os_dois_termos_do_perfil():
    # Perfil DIABETES + HEMATOLOG: d = (1, 1) nesses termos, log RR = 0,8 + 0,5 = 1,3.
    # Var = 0,04 + 0,04 + 2·0,005 = 0,09, então EP = 0,3. A covariância 0,005 entra com fator 2.
    beta = {**BETA_DIABETES, "HEMATOLOG: Sim": 0.5}
    cov = {**COV_DIABETES, ("HEMATOLOG: Sim", "HEMATOLOG: Sim"): 0.04,
           ("DIABETES: Sim", "HEMATOLOG: Sim"): 0.005}
    e1 = _e1_falso(beta, cov)
    r = explain.razao_de_risco(e1, 40, "F", 0, ("DIABETES", "HEMATOLOG"))
    assert r["log_razao"] == pytest.approx(1.3)
    assert r["erro_log_razao"] == pytest.approx(0.3)
    assert r["ic_superior"] == pytest.approx(math.exp(1.3 + Z * 0.3))


def test_perfil_sem_comorbidades_tem_razao_1_por_definicao():
    e1 = _e1_falso(BETA_DIABETES, COV_DIABETES)
    r = explain.razao_de_risco(e1, 70, "F", 0, ())
    assert r["razao"] == 1.0
    assert r["ic_inferior"] == 1.0
    assert r["ic_superior"] == 1.0


def test_trio_usa_so_efeitos_individuais_e_pares_do_e1():
    # Trio aos 40 anos: individuais 0,8 + 0,5 + 1,0 e o par incluído DIABETES x HEMATOLOG 0,3.
    # DIABETES x RENAL está fora do E1 (dados insuficientes), então não entra. η = −5 + 2,6.
    beta = {"Intercepto": -5.0, "DIABETES: Sim": 0.8, "HEMATOLOG: Sim": 0.5,
            "RENAL: Sim": 1.0, "DIABETES x HEMATOLOG": 0.3}
    fora = [p for p in explain.PARES if p != ("DIABETES", "HEMATOLOG")]
    e1 = _e1_falso(beta, {}, incluidos=[("DIABETES", "HEMATOLOG")], excluidos=fora)
    assert "DIABETES x RENAL" not in e1.colunas
    r = explain.risco_perfil(e1, 40, "F", 0, ("DIABETES", "HEMATOLOG", "RENAL"))
    assert r["logit"] == pytest.approx(-2.4)
    assert r["risco"] == pytest.approx(_expit(-2.4))


def test_entradas_invalidas_sao_recusadas():
    e1 = _e1_falso(BETA_DIABETES, COV_DIABETES)
    with pytest.raises(ValueError):
        explain.risco_perfil(e1, 40, "X", 0, ())
    with pytest.raises(ValueError):
        explain.risco_perfil(e1, 40, "M", 1, ())  # gestante só com sexo F
    with pytest.raises(ValueError):
        explain.risco_perfil(e1, 121, "F", 0, ())
    with pytest.raises(ValueError):
        explain.risco_perfil(e1, 40, "F", 0, ("FOO",))


# --- Lista de perfis (gerada do E1 e das contagens) --------------------------------------------

COMBOS = _combinacoes([
    ("DIABETES + HEMATOLOG + RENAL", 3, 39, 0),
    ("DIABETES + HEPATOPAT + RENAL", 3, 9, 0),          # menos de 10 casos: fora
    ("AUTO_IMUNE + ACIDO_PEPT + DIABETES", 3, 10, 0),   # exatamente 10: entra
    ("HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA", 4, 200, 3),  # 4 comorbidades: entra
])


def test_lista_de_perfis_vem_dos_pares_do_e1():
    perfis = explain.gerar_perfis(_e1_falso(), COMBOS, minimo=10)
    assert Counter(p.grupo for p in perfis) == {1: 1, 2: 7, 3: 21, 4: 3}
    assert [p.nome for p in perfis if p.dados_insuficientes] == [
        f"{a} + {b}" for a, b in PARES_FORA]
    assert [p.nome for p in perfis if p.grupo == 3 and not p.dados_insuficientes] == [
        f"{a} + {b}" for a, b in PARES_E1]
    assert [p.nome for p in perfis if p.grupo == 4] == [
        "DIABETES + HEMATOLOG + RENAL",
        "AUTO_IMUNE + ACIDO_PEPT + DIABETES",
        "HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA",
    ]


def test_lista_de_perfis_muda_quando_o_e1_muda():
    # Outro E1: um par diferente fica de fora. A lista tem de acompanhar o E1, não uma lista fixa.
    fora = ("ACIDO_PEPT", "AUTO_IMUNE")
    e1 = _e1_falso(incluidos=[p for p in explain.PARES if p != fora], excluidos=[fora])
    perfis = explain.gerar_perfis(e1, COMBOS, minimo=10)
    assert [p.nome for p in perfis if p.dados_insuficientes] == ["ACIDO_PEPT + AUTO_IMUNE"]


def test_pares_do_e1_precisam_cobrir_as_21_combinacoes():
    with pytest.raises(ValueError):
        explain.gerar_perfis(_e1_falso(excluidos=PARES_FORA[:-1]), COMBOS, minimo=10)


def test_combinacao_mal_formada_no_arquivo_levanta_erro():
    ruim = _combinacoes([("DIABETES + HEMATOLOG", 3, 50, 1)])  # diz 3, tem 2
    with pytest.raises(ValueError):
        explain.gerar_perfis(_e1_falso(), ruim, minimo=10)


# --- Células, supressão e sexo -----------------------------------------------------------------

def test_sexo_f_e_m_saem_em_linhas_separadas():
    beta = {"Intercepto": -5.0, "Sexo: M (ref. F)": 0.4}
    e1 = _e1_falso(beta, {})
    perfil = explain.Perfil("Sem comorbidades", 1, ())
    celulas = _celulas([(0, "60–79", "F", 0, 100), (0, "60–79", "M", 0, 100)])
    (f, _), (m, _) = explain._linhas_do_perfil(e1, perfil, celulas, 10, [("60–79", 70.0)])
    assert (f[2], m[2]) == ("F", "M")
    assert f[3] != m[3]  # o sexo M muda o risco
    assert f[5] == "1,00 [1,00; 1,00]"


def test_celula_com_menos_de_10_casos_sai_sem_numero():
    e1 = _e1_falso(BETA_DIABETES, COV_DIABETES)
    perfil = explain.Perfil("DIABETES", 2, ("DIABETES",))
    celulas = _celulas([
        (0, "60–79", "F", 0, 500), (0, "60–79", "M", 0, 500),
        (DIABETES, "60–79", "F", 0, 9),    # menos de 10: suprimida
        (DIABETES, "60–79", "M", 0, 10),   # exatamente 10: publicada
    ])
    (f, publicada_f), (m, publicada_m) = explain._linhas_do_perfil(
        e1, perfil, celulas, 10, [("60–79", 70.0)])
    assert f[3:] == ["—", "—", "—"]
    assert not publicada_f
    assert m[3] != "—" and publicada_m


def test_razao_sai_sem_numero_se_a_celula_do_saudavel_estiver_suprimida():
    e1 = _e1_falso(BETA_DIABETES, COV_DIABETES)
    perfil = explain.Perfil("DIABETES", 2, ("DIABETES",))
    celulas = _celulas([
        (0, "60–79", "F", 0, 5),           # saudável com menos de 10: a razão sai
        (DIABETES, "60–79", "F", 0, 300),
    ])
    ((linha, publicada),) = explain._linhas_do_perfil(
        e1, perfil, celulas, 10, [("60–79", 70.0)])[:1]
    assert linha[3] != "—"  # o risco do perfil sai
    assert linha[5] == "—"  # a razão não


def test_perfil_com_dados_insuficientes_sai_sem_numero():
    perfil = explain.Perfil("HEMATOLOG + RENAL", 3, ("HEMATOLOG", "RENAL"), True)
    ((linha, publicada),) = explain._linhas_do_perfil(_e1_falso(), perfil, _celulas([]), 10)
    assert linha == ["HEMATOLOG + RENAL", "—", "—", "dados insuficientes", "—", "—"]
    assert not publicada


def _tabela_completa(e1, celulas):
    perfis = explain.gerar_perfis(e1, COMBOS, minimo=10)
    return explain._md_completa(e1, perfis, celulas, 10, n_omitidas=1)


def test_markdown_sem_contagem_de_1_a_9_e_com_notas_do_trio():
    e1 = _e1_falso(BETA_DIABETES, COV_DIABETES)
    celulas = _celulas([
        (0, "60–79", "F", 0, 500), (0, "60–79", "M", 0, 500),
        (DIABETES, "60–79", "F", 0, 300), (DIABETES, "60–79", "M", 0, 3),
    ])
    linhas, estatisticas = _tabela_completa(e1, celulas)
    texto = "\n".join(linhas)
    for linha in texto.splitlines():
        if linha.startswith("|"):
            for celula in linha.split("|"):
                assert not (celula.strip().isdigit() and 1 <= int(celula.strip()) <= 9)
    trio = [ln for ln in linhas if ln.startswith("| DIABETES + HEMATOLOG + RENAL |")]
    assert trio and all(explain.NOTA_TRIO in ln for ln in trio)
    comb4 = [ln for ln in linhas if ln.startswith("| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA |")]
    assert comb4 and all(explain.NOTA_COMBINACAO in ln for ln in comb4)
    assert estatisticas[1]["perfis"] == 1 and estatisticas[4]["perfis"] == 3
    assert estatisticas[3]["insuficientes"] == 6


def test_resumo_usa_so_a_faixa_60_79_e_as_mesmas_regras():
    e1 = _e1_falso(BETA_DIABETES, COV_DIABETES)
    celulas = _celulas([(0, "60–79", "F", 0, 500), (0, "60–79", "M", 0, 500),
                        (DIABETES, "60–79", "F", 0, 300)])
    perfis = explain.gerar_perfis(e1, COMBOS, minimo=10)
    linhas = explain._md_resumo(e1, perfis, celulas, 10)
    tabela = [ln for ln in linhas if ln.startswith("|") and "Sexo" not in ln]
    assert tabela and all("Sexo" not in ln for ln in tabela)
    assert any(ln.startswith("| Sem comorbidades | F |") for ln in tabela)
    assert all("0–4" not in ln and "80+" not in ln for ln in tabela)


def test_contagens_por_padrao_batem_com_contagem_direta():
    df = _populacao_sintetica(n=8000)
    celulas = explain.contagens_por_padrao(df)
    assert int(celulas["casos"].sum()) == len(df)
    so_diabetes = df[(df["DIABETES"] == "Sim")
                     & df[[c for c in COMORBIDADES if c != "DIABETES"]].ne("Sim").all(axis=1)]
    # Faixa 60–79 é [60, 80), como em profiling.FAIXAS (right=False).
    idade = so_diabetes["idade_anos"]
    direto = so_diabetes[(so_diabetes["gestante"] == 0) & (so_diabetes["sexo"] == "F")
                         & (idade >= 60) & (idade < 80)]
    obtido = explain._casos_observados(celulas, ("DIABETES",))
    assert obtido[("60–79", "F")] == len(direto)


def test_conferir_contagens_exige_bater_com_o_csv():
    celulas = explain.contagens_por_padrao(_populacao_sintetica(n=8000))
    por_padrao = celulas.groupby("mascara")["casos"].sum()
    masc = [int(m) for m in por_padrao.index if bin(int(m)).count("1") >= 3]
    nomes = [" + ".join(c for i, c in enumerate(COMORBIDADES) if m >> i & 1) for m in masc]
    combos = _combinacoes([(n, len(n.split(" + ")), int(por_padrao[m]), 0)
                           for n, m in zip(nomes, masc, strict=True)])
    explain.conferir_contagens(celulas, combos)  # bate: não levanta
    combos.loc[0, "casos"] += 1
    with pytest.raises(ValueError):
        explain.conferir_contagens(celulas, combos)


# --- Integração com um ajuste real (dados sintéticos) ------------------------------------------

@pytest.fixture(scope="module")
def e1_sintetico(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("perfis")
    cfg = _cfg(tmp)
    df = _populacao_sintetica(n=30_000)
    _escrever_pares(cfg, df)
    return explain.ajustar_e1(cfg, df)


def test_risco_e_razao_com_o_e1_ajustado(e1_sintetico):
    e1 = e1_sintetico
    assert e1.resultados.converged
    assert explain.razao_de_risco(e1, 60, "F", 0, ())["razao"] == 1.0
    com = explain.risco_perfil(e1, 60, "F", 0, ("DIABETES", "RENAL"))
    sem = explain.risco_perfil(e1, 60, "F", 0, ())
    assert com["ic_inferior"] < com["risco"] < com["ic_superior"]
    assert com["risco"] > sem["risco"]


# --- Grupo 4 (T-3.5, revisto): estimativa até 4 comorbidades; 5 ou mais sem número ---------------

COMBOS_5 = _combinacoes([
    ("DIABETES + HEMATOLOG + RENAL", 3, 39, 0),
    ("HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA", 4, 200, 3),
    ("DIABETES + HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA", 5, 40, 2),
    ("DIABETES + HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA + ACIDO_PEPT", 6, 15, 0),
    # 7 comorbidades com menos de 10 casos: fora da tabela
    ("DIABETES + HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA + ACIDO_PEPT + AUTO_IMUNE", 7, 9, 0),
])
CINCO = "DIABETES + HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA"


def test_grupo_4_estima_ate_4_e_marca_5_ou_mais_sem_estimativa():
    perfis = explain.gerar_perfis(_e1_falso(), COMBOS_5, minimo=10)
    g4 = [p for p in perfis if p.grupo == 4]
    assert [p.nome for p in g4] == [
        "DIABETES + HEMATOLOG + RENAL",
        "HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA",
        CINCO,
        "DIABETES + HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA + ACIDO_PEPT",
    ]
    assert [p.dados_insuficientes for p in g4] == [False, False, True, True]


def test_linha_de_5_ou_mais_sai_sem_numero_e_com_o_motivo():
    perfil = explain.Perfil(CINCO, 4, tuple(COMORBIDADES[:5]), dados_insuficientes=True)
    ((valores, publicada),) = explain._linhas_do_perfil(
        _e1_falso(), perfil, _celulas([(0, "60–79", "F", 0, 500)]), 10)
    assert valores == [CINCO, "—", "—",
                       "dados insuficientes (5+ comorbidades: poucos eventos; extrapolação "
                       "instável do E1)", "—", "—"]
    assert not publicada


def test_aviso_so_para_perfis_que_contem_os_dois_membros_do_par():
    par = [("HEMATOLOG", "RENAL")]
    assert explain._aviso(explain.Perfil("x", 3, ("HEMATOLOG", "RENAL")), par) \
        == explain.AVISO_PADRAO
    assert explain._aviso(explain.Perfil("x", 2, ("HEMATOLOG",)), par) == explain.SUPRIMIDO
    assert explain._aviso(explain.Perfil("x", 3, ("HEMATOLOG", "HEPATOPAT", "DIABETES")),
                          par) == explain.SUPRIMIDO
    assert explain._aviso(explain.Perfil("x", 4, ("DIABETES", "HEMATOLOG", "RENAL", "AUTO_IMUNE")),
                          par) == explain.AVISO_PADRAO


def test_markdown_marca_aviso_e_traz_as_linhas_de_5_ou_mais_sem_numero():
    e1 = _e1_falso(BETA_DIABETES, COV_DIABETES)
    celulas = _celulas([(0, "60–79", "F", 0, 500), (0, "60–79", "M", 0, 500)])
    perfis = explain.gerar_perfis(e1, COMBOS_5, minimo=10)
    sensiveis = [("HEMATOLOG", "HEPATOPAT")]
    linhas, estatisticas = explain._md_completa(e1, perfis, celulas, 10, 1, sensiveis)
    trio = [ln for ln in linhas if ln.startswith("| DIABETES + HEMATOLOG + RENAL |")]
    assert trio and all(explain.AVISO_PADRAO not in ln for ln in trio)
    quarteto = [ln for ln in linhas
                if ln.startswith("| HEMATOLOG + HEPATOPAT + RENAL + HIPERTENSA |")]
    assert quarteto and all(explain.AVISO_PADRAO in ln for ln in quarteto)
    cinco = [ln for ln in linhas if ln.startswith(f"| {CINCO} |")]
    assert len(cinco) == 1
    assert explain.AVISO_PADRAO in cinco[0] and cinco[0].endswith("| — |")
    assert "dados insuficientes (5+ comorbidades" in cinco[0]
    assert estatisticas[4]["perfis"] == 4 and estatisticas[4]["insuficientes"] == 2
    texto = "\n".join(linhas)
    assert "Grupo 4: Três ou mais comorbidades (4 perfis; 2 com dados insuficientes)" in texto
    assert "Cinco ou mais comorbidades" in texto
    assert contagens_1_a_9_em_prosa(texto) == []  # R7 também na prosa, não só nas tabelas
    resumo = "\n".join(explain._md_resumo(e1, perfis, celulas, 10, sensiveis))
    assert contagens_1_a_9_em_prosa(resumo) == []


# Chaves da seção `e1` de config/esperado.yaml que a T-3.5 lê, e o check de cada uma.
CHAVES_E1_PERFIS = {
    "perfis_grupo_1": "perfis_grupo_1",
    "perfis_grupo_2": "perfis_grupo_2",
    "perfis_grupo_3": "perfis_grupo_3",
    "pares_excluidos": "pares_dados_insuficientes",
    "pares_incluidos": "pares_incluidos",
    "combinacoes_3_ou_mais": "combinacoes_3_ou_mais_no_arquivo",
    "combinacoes_3_ou_mais_com_minimo": "combinacoes_3_ou_mais_com_minimo",
    "perfis_grupo_4": "perfis_grupo_4_com_minimo",
    "perfis_grupo_4_com_estimativa": "perfis_grupo_4_com_estimativa",
    "perfis_grupo_4_dados_insuficientes": "perfis_grupo_4_dados_insuficientes",
    "celulas_publicadas": "celulas_publicadas_com_minimo",
    "linhas_tabela_perfis": "linhas_completa",
}


def _esperado_e1(valor: int = 0) -> dict:
    return {chave: valor for chave in CHAVES_E1_PERFIS}


def _checks_do_fixture(esperado: dict) -> dict:
    e1 = _e1_falso()
    celulas = _celulas([])
    perfis = explain.gerar_perfis(e1, COMBOS_5, minimo=10)
    linhas, estatisticas = explain._md_completa(e1, perfis, celulas, 10, 1)
    return {c["nome"]: c for c in explain._checks_perfis(
        e1, perfis, COMBOS_5, celulas, 10, estatisticas, "\n".join(linhas), esperado)}


def test_checks_separam_grupo_4_com_estimativa_e_sem_estimativa():
    esperado = {**_esperado_e1(), "perfis_grupo_4_com_estimativa": 2,
                "perfis_grupo_4_dados_insuficientes": 2}
    checks = _checks_do_fixture(esperado)
    assert checks["perfis_grupo_4_com_estimativa"]["esperado"] == 2
    assert checks["perfis_grupo_4_com_estimativa"]["obtido"] == 2
    assert checks["perfis_grupo_4_dados_insuficientes"]["esperado"] == 2
    assert checks["perfis_grupo_4_dados_insuficientes"]["obtido"] == 2


def test_checks_leem_cada_esperado_do_dicionario_e_falham_se_um_mudar():
    # Os valores "obtidos" do fixture viram o esperado: o teste prova a ligação chave -> check.
    obtidos = {nome: c["obtido"] for nome, c in _checks_do_fixture(_esperado_e1()).items()}
    esperado = {chave: obtidos[nome] for chave, nome in CHAVES_E1_PERFIS.items()}
    assert all(c["passou"] for c in _checks_do_fixture(esperado).values())
    for chave, nome in CHAVES_E1_PERFIS.items():
        alterado = {**esperado, chave: esperado[chave] + 1}
        checks = _checks_do_fixture(alterado)
        assert checks[nome]["esperado"] == alterado[chave]
        assert [n for n, c in checks.items() if not c["passou"]] == [nome], chave


def test_secao_e1_do_esperado_yaml_tem_as_chaves_que_a_t35_le():
    lido = explain.ler_esperado_e1()
    assert set(CHAVES_E1_PERFIS) <= set(lido)
    assert lido["celulas_publicadas"] == 359 and lido["linhas_tabela_perfis"] == 940
