"""Testes dos critérios SC-01 a SC-04 (T-5.4, D-36, D-93) com dados sintéticos: nenhum microdado,
nenhum 2024 real (R1). Os critérios são conferidos contra valores conhecidos de dados construídos
para passar e para falhar, e as bordas (recall e precisão iguais, slope em 0,8 e 1,2) têm teste
próprio. A diferença contra a B2 é conferida contra a T-5.1 (os mesmos sorteios).
"""

import copy
import json
from pathlib import Path

import numpy as np
import pytest
from test_evaluate import _df_sintetico, _esperado_de, _fontes, _modelos

from dengue_sinan import artifacts, metrics
from dengue_sinan import evaluate as ev
from dengue_sinan import teste_criterios as tc
from dengue_sinan.config import load_config

CFG_BASE = load_config()


@pytest.fixture
def cfg(tmp_path) -> dict:
    return {**copy.deepcopy(CFG_BASE),
            "caminhos": {**CFG_BASE["caminhos"], "dados": str(tmp_path / "data"),
                         "relatorios": str(tmp_path / "reports"),
                         "modelos": str(tmp_path / "models")},
            "bootstrap": {"metricas": 20, "calibracao": 2000, "processos": 1}}


@pytest.fixture
def df():
    return _df_sintetico()


@pytest.fixture
def esperado(df, monkeypatch):
    esp = _esperado_de(df)
    monkeypatch.setattr(ev, "_ler_esperado_teste", lambda caminho=None: esp)
    return esp


def _json_do_teste(cfg: dict) -> dict:
    return json.loads((Path(cfg["caminhos"]["relatorios"]) / "teste" / "metricas.json")
                      .read_text(encoding="utf-8"))


# --- Blocos de entrada conhecidos ------------------------------------------------------------

def _bloco(valor, ic=None) -> dict:
    return {"valor": valor, "ic95": ic}


def _metricas(d01=(0.05, [0.01, 0.09]), d04=(0.02, [0.005, 0.03]), slope=(1.0, [0.9, 1.1]),
              n=1000) -> dict:
    return {"reamostras": n, "diferencas_pr_auc": {"M1_menos_B0": _bloco(*d01),
                                                   "M1_menos_B1": _bloco(*d04)},
            "modelos": {"M1": {"slope": _bloco(*slope), "limiar": 0.0123}}}


def _sc02(recall_m1=0.8, recall_b2=0.7, prec_m1=0.1, prec_b2=0.05) -> dict:
    def metrica(m1, b2):
        return {"M1": _bloco(m1, [m1 - 0.01, m1 + 0.01]), "B2": _bloco(b2, [b2 - 0.01, b2 + 0.01]),
                "diferenca": _bloco(m1 - b2, [m1 - b2 - 0.02, m1 - b2 + 0.02])}

    return {"recall": metrica(recall_m1, recall_b2), "precisao": metrica(prec_m1, prec_b2),
            "reamostras": 1000}


def _avaliar(**kw) -> dict:
    sc02 = kw.pop("sc02", _sc02())
    return tc.avaliar_criterios(_metricas(**kw), sc02)


# --- SC-01 -----------------------------------------------------------------------------------

@pytest.mark.parametrize("valor, ic, passou", [
    (0.05, [0.01, 0.09], True),       # M1 acima do B0, IC sem 0
    (0.05, [1e-9, 0.09], True),       # limite inferior mal acima de 0
    (0.05, [0.0, 0.09], False),       # borda: o IC toca 0, então inclui 0
    (0.01, [-0.02, 0.04], False),     # IC inclui 0
    (-0.05, [-0.09, -0.01], False),   # IC sem 0, mas M1 PIOR que B0: não supera
    (0.05, None, False),              # sem IC não há como dizer
])
def test_sc01_passa_so_se_o_ic_da_diferenca_fica_acima_de_zero(valor, ic, passou):
    sc = _avaliar(d01=(valor, ic))["sc01"]
    assert sc["passou"] is passou
    assert sc["valor"] == valor and sc["ic95"] == ic
    if ic is not None:
        assert sc["ic_inclui_zero"] is bool(ic[0] <= 0 <= ic[1])


# --- SC-02: recall igual ou maior E precisão maior -------------------------------------------

@pytest.mark.parametrize("recall_m1, recall_b2, prec_m1, prec_b2, passou", [
    (0.80, 0.70, 0.10, 0.05, True),    # recall maior, precisão maior
    (0.70, 0.70, 0.10, 0.05, True),    # recall IGUAL passa (>=), precisão maior
    (0.70, 0.70, 0.05, 0.05, False),   # recall igual e precisão igual: falha pela precisão
    (0.80, 0.70, 0.05, 0.05, False),   # precisão igual falha mesmo com recall maior
    (0.80, 0.70, 0.04, 0.05, False),   # precisão menor
    (0.69, 0.70, 0.10, 0.05, False),   # recall menor, precisão maior: falha pelo recall
    (0.69, 0.70, 0.04, 0.05, False),   # as duas piores
])
def test_sc02_recall_maior_ou_igual_e_precisao_estritamente_maior(recall_m1, recall_b2, prec_m1,
                                                                   prec_b2, passou):
    sc = _avaliar(sc02=_sc02(recall_m1, recall_b2, prec_m1, prec_b2))["sc02"]
    assert sc["passou"] is passou
    assert sc["recall_ok"] is (recall_m1 >= recall_b2)
    assert sc["precisao_ok"] is (prec_m1 > prec_b2)


def test_sc02_traz_os_valores_e_os_ics_das_duas_diferencas_e_se_o_ic_sustenta():
    sc02 = _sc02(0.80, 0.70, 0.10, 0.05)
    sc = _avaliar(sc02=sc02)["sc02"]
    assert sc["valor"] == {"recall_m1_menos_b2": pytest.approx(0.10),
                           "precisao_m1_menos_b2": pytest.approx(0.05)}
    assert sc["ic95"]["recall_m1_menos_b2"] == sc02["recall"]["diferenca"]["ic95"]
    assert sc["ic_sustenta"] == {"recall": True, "precisao": True}  # limites inferiores > 0
    # estimativa pontual passa, mas o IC da diferença de recall inclui 0: não sustenta
    sc02["recall"]["diferenca"]["ic95"] = [-0.01, 0.2]
    sc = _avaliar(sc02=sc02)["sc02"]
    assert sc["passou"] is True and sc["ic_sustenta"]["recall"] is False
    # borda do IC: limite inferior do recall = 0 sustenta (>=); o da precisão = 0 não (>)
    sc02["recall"]["diferenca"]["ic95"] = [0.0, 0.2]
    sc02["precisao"]["diferenca"]["ic95"] = [0.0, 0.2]
    sc = _avaliar(sc02=sc02)["sc02"]
    assert sc["ic_sustenta"] == {"recall": True, "precisao": False}
    assert set(sc["detalhe"]) == {"recall", "precisao"}


# --- SC-03: slope entre 0,8 e 1,2 ------------------------------------------------------------

@pytest.mark.parametrize("slope, passou", [
    (1.0, True), (0.8, True), (1.2, True),          # as duas bordas passam
    (0.7999999, False), (1.2000001, False),         # logo fora falha
    (0.5, False), (2.0, False), (None, False),
])
def test_sc03_slope_entre_08_e_12_inclusive_pela_estimativa(slope, passou):
    ic = None if slope is None else [slope - 0.3, slope + 0.3]
    sc = _avaliar(slope=(slope, ic))["sc03"]
    assert sc["passou"] is passou
    assert sc["valor"] == slope and sc["ic95"] == ic


def test_sc03_passa_pela_estimativa_mesmo_com_ic_que_sai_do_intervalo_e_informa():
    sc = _avaliar(slope=(0.85, [0.7, 1.0]))["sc03"]
    assert sc["passou"] is True and sc["ic_dentro_do_intervalo"] is False
    sc = _avaliar(slope=(1.0, [0.85, 1.15]))["sc03"]
    assert sc["passou"] is True and sc["ic_dentro_do_intervalo"] is True
    assert _avaliar(slope=(1.0, [0.8, 1.2]))["sc03"]["ic_dentro_do_intervalo"] is True  # borda


# --- SC-04: reportado qualquer que seja o sinal ----------------------------------------------

@pytest.mark.parametrize("valor, ic, sentido, superou", [
    (0.02, [0.005, 0.03], "M1 acima do B1 (IC exclui 0)", True),
    (-0.02, [-0.03, -0.005], "M1 abaixo do B1 (IC exclui 0)", False),  # pior: ainda "passou"
    (0.001, [-0.01, 0.012], "IC inclui 0", False),
])
def test_sc04_e_reportado_qualquer_que_seja_o_sinal(valor, ic, sentido, superou):
    sc = _avaliar(d04=(valor, ic))["sc04"]
    assert sc["passou"] is True  # "reportado" = passou
    assert sc["sentido"] == sentido and sc["superou_b1"] is superou
    assert sc["valor"] == valor and sc["ic95"] == ic
    assert "não condição" in sc["nota"]


def test_sc04_sem_ic_nao_foi_reportado():
    sc = _avaliar(d04=(0.02, None))["sc04"]
    assert sc["passou"] is False and sc["sentido"] is None


def test_json_dos_criterios_tem_valor_ic95_criterio_e_passou_em_cada_um():
    j = _avaliar()
    for sc in tc.CRITERIOS:
        assert all(campo in j[sc] for campo in tc.CAMPOS), sc
        assert isinstance(j[sc]["passou"], bool) and j[sc]["criterio"]
    assert j["texto_d36"] == ("Se o teste sair pior que a validação, reportar como resultado "
                              "(drift); é proibido voltar e trocar modelo, peso, calibrador ou "
                              "limiar.")
    assert j["limiar_m1"] == 0.0123
    assert artifacts.inteiros_pequenos(json.loads(json.dumps(j))) == []


def test_reamostras_de_1_a_9_sai_como_texto_para_nao_virar_contagem_pequena():
    j = tc.avaliar_criterios(_metricas(n=5), _sc02())
    assert j["reamostras"] == "5"
    assert artifacts.inteiros_pequenos(json.loads(json.dumps(j))) == []


# --- SC-02 pelo bootstrap: valores conhecidos e os mesmos sorteios da T-5.1 ------------------

def _flags(y, m1, b0, b1, b2) -> dict:
    return {"M1": np.asarray(m1, dtype=bool), "B0": np.asarray(b0, dtype=bool),
            "B1": np.asarray(b1, dtype=bool), "B2": np.asarray(b2, dtype=bool)}


def _cenario(n_pos=200, n_neg=2000, vp_m1=170, fp_m1=300, vp_b2=150, fp_b2=900):
    """y e flags com contagens exatas: M1 captura `vp_m1` eventos e marca `fp_m1` não eventos; a
    B2 captura `vp_b2` e marca `fp_b2`. B0 e B1 são irrelevantes aqui."""
    y = np.array([1] * n_pos + [0] * n_neg)
    m1 = np.zeros(len(y), dtype=bool)
    b2 = np.zeros(len(y), dtype=bool)
    m1[:vp_m1] = True
    m1[n_pos:n_pos + fp_m1] = True
    b2[:vp_b2] = True
    b2[n_pos:n_pos + fp_b2] = True
    return y, _flags(y, m1, m1, m1, b2)


def test_diferencas_no_limiar_batem_com_as_contagens_conhecidas():
    y, marcados = _cenario()
    r = tc.diferencas_no_limiar(y, marcados, seed=1, n=40)
    assert r["recall"]["M1"]["valor"] == pytest.approx(170 / 200)
    assert r["recall"]["B2"]["valor"] == pytest.approx(150 / 200)
    assert r["precisao"]["M1"]["valor"] == pytest.approx(170 / 470)
    assert r["precisao"]["B2"]["valor"] == pytest.approx(150 / 1050)
    assert r["recall"]["diferenca"]["valor"] == pytest.approx(170 / 200 - 150 / 200)
    assert r["precisao"]["diferenca"]["valor"] == pytest.approx(170 / 470 - 150 / 1050)
    for m in ("recall", "precisao"):
        for chave in ("M1", "B2", "diferenca"):
            lo, hi = r[m][chave]["ic95"]
            assert lo <= r[m][chave]["valor"] <= hi or chave == "diferenca"
    assert r["recall"]["diferenca"]["ic95"][0] > 0  # 85% contra 75%, com 200 eventos


def test_cenario_que_passa_o_sc02_de_ponta_a_ponta():
    y, marcados = _cenario(vp_m1=170, fp_m1=300, vp_b2=150, fp_b2=900)
    j = tc.avaliar_criterios(_metricas(), tc.diferencas_no_limiar(y, marcados, seed=1, n=40))
    assert j["sc02"]["passou"] is True


def test_cenario_que_falha_o_sc02_pelo_recall_mesmo_com_precisao_maior():
    # M1 mais preciso, com menos recall
    y, marcados = _cenario(vp_m1=120, fp_m1=100, vp_b2=150, fp_b2=900)
    j = tc.avaliar_criterios(_metricas(), tc.diferencas_no_limiar(y, marcados, seed=1, n=40))
    assert j["sc02"]["recall_ok"] is False and j["sc02"]["precisao_ok"] is True
    assert j["sc02"]["passou"] is False


def test_cenario_com_recall_e_precisao_iguais_falha_pela_precisao():
    y, marcados = _cenario(vp_m1=150, fp_m1=900, vp_b2=150, fp_b2=900)  # flags de mesma contagem
    r = tc.diferencas_no_limiar(y, marcados, seed=1, n=40)
    assert r["recall"]["diferenca"]["valor"] == 0.0 and r["precisao"]["diferenca"]["valor"] == 0.0
    j = tc.avaliar_criterios(_metricas(), r)
    assert j["sc02"]["recall_ok"] is True and j["sc02"]["precisao_ok"] is False
    assert j["sc02"]["passou"] is False


def test_recall_igual_com_precisao_maior_passa():
    y, marcados = _cenario(vp_m1=150, fp_m1=300, vp_b2=150, fp_b2=900)
    j = tc.avaliar_criterios(_metricas(), tc.diferencas_no_limiar(y, marcados, seed=1, n=40))
    assert j["sc02"]["recall_ok"] is True and j["sc02"]["precisao_ok"] is True
    assert j["sc02"]["passou"] is True


def _predicoes(df):
    modelos = _modelos(df)
    return ev.predizer(modelos, df, dentro_do_teste=True), modelos


def test_os_sorteios_sao_os_da_t51_recall_e_precisao_de_m1_e_b2_batem_com_o_ic_de_la(df):
    pred, _ = _predicoes(df)
    y = df["y"].to_numpy()
    res = ev.calcular_metricas(y, pred, seed=77, n=30, processos=1)
    r = tc.diferencas_no_limiar(y, ev._flags(pred), seed=77, n=30)
    for modelo in ("M1", "B2"):
        da_t51 = res.json["modelos"][modelo]["no_limiar"]
        for medida in ("recall", "precisao"):
            assert r[medida][modelo]["valor"] == da_t51[medida]["valor"]
            assert r[medida][modelo]["ic95"] == da_t51[medida]["ic95"]  # mesmos sorteios
    # e a diferença é a diferença reamostra a reamostra, não a diferença dos ICs
    dist = res.distribuicoes
    ref = np.quantile(dist["M1/limiar_recall"] - dist["B2/limiar_recall"], [0.025, 0.975])
    assert r["recall"]["diferenca"]["ic95"] == pytest.approx(ref.tolist(), abs=1e-12)
    ref = np.quantile(dist["M1/limiar_precisao"] - dist["B2/limiar_precisao"], [0.025, 0.975])
    assert r["precisao"]["diferenca"]["ic95"] == pytest.approx(ref.tolist(), abs=1e-12)


def test_diferenca_vem_do_calculo_direto_nos_dados_sinteticos(df):
    pred, modelos = _predicoes(df)
    y = df["y"].to_numpy()
    r = tc.diferencas_no_limiar(y, ev._flags(pred), seed=3, n=10)
    p = pred.probabilidades["M1"]
    ref_m1 = metrics.threshold_metrics(y, p, modelos.m1.limiar)
    assert r["recall"]["M1"]["valor"] == pytest.approx(ref_m1["recall"], abs=1e-12)
    assert r["precisao"]["M1"]["valor"] == pytest.approx(ref_m1["precisao"], abs=1e-12)
    b2 = pred.b2
    assert r["recall"]["B2"]["valor"] == pytest.approx(b2[y == 1].mean(), abs=1e-12)
    assert r["precisao"]["B2"]["valor"] == pytest.approx(y[b2].mean(), abs=1e-12)


def test_o_limiar_do_sc02_e_o_congelado_do_m1(df):
    pred, _ = _predicoes(df)
    y = df["y"].to_numpy()
    base = tc.diferencas_no_limiar(y, ev._flags(pred), seed=3, n=5)
    pred2 = ev.Predicoes(probabilidades=pred.probabilidades, b2=pred.b2,
                         limiares={**pred.limiares, "M1": pred.limiares["M1"] * 3})
    outro = tc.diferencas_no_limiar(y, ev._flags(pred2), seed=3, n=5)
    # limiar maior, menos recall
    assert outro["recall"]["M1"]["valor"] < base["recall"]["M1"]["valor"]
    assert outro["recall"]["B2"]["valor"] == base["recall"]["B2"]["valor"]  # a B2 não mudou


def test_recusa_n_zero():
    y, marcados = _cenario()
    with pytest.raises(ValueError, match="pelo menos uma"):
        tc.diferencas_no_limiar(y, marcados, seed=1, n=0)


# --- Integração: a análise lê a anterior, não recalcula --------------------------------------

def test_analise_criterios_sem_a_analise_metricas_levanta_erro(df):
    pred, _ = _predicoes(df)
    ctx = ev.Contexto(cfg=CFG_BASE, modo="teste", y=df["y"].to_numpy(), predicoes=pred, df=df,
                      seed=1, n_metricas=5)
    with pytest.raises(ValueError, match="'metricas'"):
        ev.analise_criterios(ctx)


def test_valores_de_sc01_sc03_e_sc04_sao_exatamente_os_da_t51_sem_recalcular(cfg, df, esperado,
                                                                           monkeypatch):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    metricas = execucao.saidas["metricas"].json
    # depois de rodar as análises, nenhuma chamada de bootstrap das métricas pode acontecer
    chamadas = []
    monkeypatch.setattr(metrics, "rodar_reamostras", lambda *a, **k: chamadas.append(1))
    pred, _ = _predicoes(df)
    ctx = ev.Contexto(cfg=cfg, modo="teste", y=df["y"].to_numpy(), predicoes=pred, df=df,
                      seed=cfg["seed"], n_metricas=cfg["bootstrap"]["metricas"],
                      anteriores={"metricas": execucao.saidas["metricas"]})
    j = ev.analise_criterios(ctx).json
    assert chamadas == []
    d = metricas["diferencas_pr_auc"]
    for sc, par in (("sc01", "M1_menos_B0"), ("sc04", "M1_menos_B1")):
        assert j[sc]["valor"] == d[par]["valor"] and j[sc]["ic95"] == d[par]["ic95"]
    slope = metricas["modelos"]["M1"]["slope"]
    assert j["sc03"]["valor"] == slope["valor"] and j["sc03"]["ic95"] == slope["ic95"]
    assert j == execucao.saidas["criterios"].json  # e é o mesmo que a avaliação gravou


def test_json_gravado_tem_as_quatro_chaves_e_o_limiar_congelado(cfg, df, esperado):
    modelos = _modelos(df)
    ev.evaluate_test_once(cfg, fontes=_fontes(df, modelos))
    j = _json_do_teste(cfg)["analises"]["criterios"]
    for sc in tc.CRITERIOS:
        assert all(campo in j[sc] for campo in tc.CAMPOS)
    assert j["limiar_m1"] == modelos.m1.limiar  # o congelado
    assert artifacts.inteiros_pequenos(j) == []


def test_markdown_lista_os_quatro_criterios_com_valor_ic_e_resultado_e_o_texto_do_d36(cfg, df,
                                                                                      esperado):
    ev.evaluate_test_once(cfg, fontes=_fontes(df))
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    md = (pasta / "criterios.md").read_text(encoding="utf-8")
    js = _json_do_teste(cfg)["analises"]["criterios"]
    for sc in ("SC-01", "SC-02", "SC-03", "SC-04"):
        assert f"## {sc}:" in md
    assert tc.TEXTO_D36 in md
    assert md.count("**passou**") + md.count("**falhou**") >= 4
    for sc in tc.CRITERIOS:  # o resultado do markdown é o do JSON
        rotulo = "**passou**" if js[sc]["passou"] else "**falhou**"
        nome = sc.upper().replace("SC", "SC-")
        linha = next(ln for ln in md.splitlines() if ln.startswith(f"| {nome} "))
        assert rotulo in linha
    assert "(" in md and ";" in md  # os ICs aparecem


def test_tabela_dos_criterios_tem_uma_linha_por_medida_e_nenhum_inteiro_pequeno():
    j = _avaliar()
    t = tc.tabela_criterios(j)
    assert list(t["criterio"]) == ["SC-01", "SC-02", "SC-02", "SC-03", "SC-04"]
    assert set(t["resultado"]) <= {"passou", "falhou"}
    assert ev._inteiros_pequenos_na_tabela(t) == []


def test_ordem_final_das_analises_padrao_termina_em_erros_e_criterios():
    nomes = [a.nome for a in ev.ANALISES_PADRAO]
    assert nomes[-2:] == ["erros", "criterios"]
    assert nomes.index("metricas") < nomes.index("criterios")
