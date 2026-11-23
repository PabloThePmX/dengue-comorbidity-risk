"""Testes da análise de erros (T-5.3, D-93) com dados sintéticos pequenos: nenhum microdado,
nenhum 2024 real (R1). Cada comportamento tem uma referência independente: seleção em força bruta
dos falsos negativos, filtros diretos do DataFrame para as células e o Espírito Santo.
"""

import copy
import dataclasses
import io
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_evaluate import _df_sintetico, _esperado_de, _fontes, _modelos, _sel_fonte

from dengue_sinan import artifacts, metrics
from dengue_sinan import evaluate as ev
from dengue_sinan import teste_analises as ta
from dengue_sinan import teste_criterios as tc
from dengue_sinan import teste_erros as te
from dengue_sinan.config import load_config
from dengue_sinan.profiling import COMORBIDADES

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


def _dados(n: int = 8000, seed: int = 3, casas: int | None = 3):
    """Casos com prevalência ~6% e risco previsto arredondado a `casas` (muitos empates); sem
    arredondar (`casas=None`), cada caso tem o seu risco."""
    rng = np.random.default_rng(seed)
    df = _df_sintetico(n=n, seed=seed)
    y = (rng.random(n) < 0.06).astype(np.int64)
    df["y"] = y
    base = np.log(0.06 / 0.94)
    bruto = 1 / (1 + np.exp(-(base + 0.9 * (y - 0.06) + 0.7 * rng.standard_normal(n))))
    p = np.clip(bruto if casas is None else np.round(bruto, casas), 0.001, 0.999)
    regra = rng.random(n) < (0.25 + 0.3 * y)
    return df, y, p, regra


def _erros(df, y, p, regra, limiar=None, *, n=12, seed=7, processos=1, **extra) -> dict:
    limiar = float(np.quantile(p, 0.8)) if limiar is None else limiar
    return te.analisar_erros(df, y, p, regra, limiar, CFG_BASE, seed=seed, n=n,
                             processos=processos, **extra)


def _fn_bruto(y, p, limiar, n=100) -> list[int]:
    """Os n falsos negativos de maior risco por força bruta: laço e sort do Python (risco
    decrescente, empate pela posição), sem numpy."""
    candidatos = [i for i in range(len(y)) if y[i] == 1 and p[i] < limiar]
    return sorted(candidatos, key=lambda i: (-p[i], i))[:n]


# --- Falsos negativos de maior risco ---------------------------------------------------------

@pytest.mark.parametrize("seed", [1, 2, 3, 4])
def test_os_100_falsos_negativos_batem_com_a_selecao_em_forca_bruta_inclusive_empates(seed):
    _, y, p, _ = _dados(n=6000, seed=seed)
    limiar = float(np.quantile(p, 0.8))
    escolhidos, total = te.selecionar_falsos_negativos(y, p, limiar)
    esperado = _fn_bruto(y, p, limiar)
    assert escolhidos.tolist() == esperado
    assert total == sum(1 for i in range(len(y)) if y[i] == 1 and p[i] < limiar) > 100
    assert len(set(p[esperado])) < len(esperado)  # há empates entre os escolhidos (o caso difícil)


def test_selecao_pega_os_de_maior_risco_e_so_entre_os_nao_detectados():
    _, y, p, _ = _dados(n=6000, seed=5)
    limiar = float(np.quantile(p, 0.8))
    escolhidos, _ = te.selecionar_falsos_negativos(y, p, limiar)
    assert (y[escolhidos] == 1).all()  # só eventos
    assert (p[escolhidos] < limiar).all()  # nenhum detectado
    fora = np.setdiff1d(np.flatnonzero((y == 1) & (p < limiar)), escolhidos)
    assert p[escolhidos].min() >= p[fora].max()  # os de MAIOR risco, não os de menor


def test_empate_no_corte_vale_a_linha_que_vem_antes_na_ordem_dos_dados():
    n = 300
    y = np.ones(n, dtype=np.int64)
    p = np.full(n, 0.01)  # todos empatados, todos abaixo do limiar
    escolhidos, total = te.selecionar_falsos_negativos(y, p, 0.5)
    assert escolhidos.tolist() == list(range(100)) and total == n
    p[250:260] = 0.02  # dez de risco maior, no fim: entram primeiro, depois as primeiras posições
    escolhidos, _ = te.selecionar_falsos_negativos(y, p, 0.5)
    assert escolhidos.tolist() == [*range(250, 260), *range(90)]


def test_com_menos_de_100_falsos_negativos_devolve_todos_e_o_total():
    _, y, p, _ = _dados(n=3000, seed=6)
    limiar = float(np.quantile(p[y == 1], 0.06))  # poucos eventos abaixo do limiar
    escolhidos, total = te.selecionar_falsos_negativos(y, p, limiar)
    assert total < 100 and len(escolhidos) == total
    assert escolhidos.tolist() == _fn_bruto(y, p, limiar)


def test_limiar_e_estrito_risco_igual_ao_limiar_conta_como_detectado():
    y = np.array([1, 1, 1, 0])
    p = np.array([0.1, 0.2, 0.3, 0.4])
    escolhidos, total = te.selecionar_falsos_negativos(y, p, 0.2)
    assert escolhidos.tolist() == [0] and total == 1  # p = 0,2 é detectado (p >= limiar)


def test_json_tem_o_n_pedido_o_total_e_o_perfil_so_dos_selecionados():
    d, y, p, regra = _dados()
    j = _erros(d, y, p, regra)
    fn = j["falsos_negativos"]
    limiar = j["limiar_m1"]
    total = int(((y == 1) & (p < limiar)).sum())
    assert j["n_pedido"] == te.N_FALSOS_NEGATIVOS == 100
    assert fn["total"] == total and fn["n_perfil"] == 100 and fn["perfil_publicado"] is True
    assert fn["eventos"] == int(y.sum())
    assert fn["detectados"] == int(((y == 1) & (p >= limiar)).sum())
    assert fn["total"] + fn["detectados"] == fn["eventos"]
    assert "limiar principal congelado" in fn["criterio_selecao"]
    assert "vem antes" in fn["regra_empate"]


def test_com_menos_de_10_falsos_negativos_o_perfil_nao_e_publicado():
    d, y, p, regra = _dados(n=3000, seed=2)
    limiar = float(np.quantile(p[y == 1], 0.03))
    assert int(((y == 1) & (p < limiar)).sum()) < 10
    j = _erros(d, y, p, regra, limiar=limiar)
    fn = j["falsos_negativos"]
    assert fn["perfil_publicado"] is False and fn["perfil"] == [] and fn["risco_previsto"] is None
    assert fn["n_perfil"] in ("<10", 0) and "R7" in fn["motivo_sem_perfil"]
    assert artifacts.inteiros_pequenos(json.loads(json.dumps(j))) == []


def test_risco_previsto_sai_em_quantis_e_nenhum_valor_individual_vai_para_o_json():
    d, y, p, regra = _dados(casas=None)
    j = _erros(d, y, p, regra)
    escolhidos = _fn_bruto(y, p, j["limiar_m1"])
    q = j["falsos_negativos"]["risco_previsto"]
    assert set(q) == {"q01", "mediana", "q99"}
    assert q["q01"] == pytest.approx(np.quantile(p[escolhidos], 0.01))
    assert q["mediana"] == pytest.approx(np.median(p[escolhidos]))
    assert q["q99"] == pytest.approx(np.quantile(p[escolhidos], 0.99))
    assert q["q01"] <= q["mediana"] <= q["q99"] < j["limiar_m1"]
    # o mínimo e o máximo exatos dos 100 (valores individuais) não aparecem como medida
    valores = {float(p[escolhidos].min()), float(p[escolhidos].max())}
    assert not valores & set(q.values())


# --- Perfil em agregados contra o cálculo direto ---------------------------------------------

def _rotulo_idade(i: float) -> str:
    for a, b, r in ((0, 5, "0–4"), (5, 15, "5–14"), (15, 40, "15–39"), (40, 60, "40–59"),
                    (60, 80, "60–79"), (80, np.inf, "80+")):
        if a <= i < b:
            return r
    raise AssertionError(i)


def _rotulo_atraso(d: float) -> str:
    if np.isnan(d):
        return "sem data"
    for a, b, r in ((0, 2, "0–1"), (2, 4, "2–3"), (4, 7, "4–6"), (7, 15, "7–14"),
                    (15, np.inf, "15+")):
        if a <= d < b:
            return r
    raise AssertionError(d)


def _categorias_diretas(d: pd.DataFrame) -> dict[tuple[str, str], np.ndarray]:
    """(dimensão, categoria) -> máscara, por laços e filtros simples (sem usar o código testado)."""
    sexo = d["CS_SEXO"].where(d["CS_SEXO"].isin(["F", "M", "I"]), "em branco")
    n_com = sum((d[c] == "Sim").astype(int) for c in COMORBIDADES)
    saida = {}
    for r in ("0–4", "5–14", "15–39", "40–59", "60–79", "80+"):
        saida[("Faixa etária", r)] = np.array([_rotulo_idade(i) == r for i in d["idade_anos"]])
    for r in ("F", "M", "I", "em branco"):
        saida[("Sexo", r)] = (sexo == r).to_numpy()
    saida[("Gestante", "gestante")] = (d["gestante"] == 1).to_numpy()
    saida[("Gestante", "não gestante")] = (d["gestante"] != 1).to_numpy()
    for k, r in enumerate(("0", "1", "2", "3+")):
        saida[("Número de comorbidades", r)] = (n_com >= 3 if k == 3 else n_com == k).to_numpy()
    for c in COMORBIDADES:
        saida[(f"Comorbidade {c}", "Sim")] = (d[c] == "Sim").to_numpy()
    for r in ("Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"):
        saida[("Região de residência", r)] = (d["regiao"] == r).to_numpy()
    for r in ("0–1", "2–3", "4–6", "7–14", "15+", "sem data"):
        saida[("Atraso até a notificação (dias)", r)] = np.array(
            [_rotulo_atraso(v) == r for v in d["dias_ate_notificacao"]])
    return saida


def test_perfil_em_agregados_bate_com_a_contagem_direta_nos_tres_grupos():
    d, y, p, regra = _dados()
    j = _erros(d, y, p, regra)
    limiar = j["limiar_m1"]
    grupos = {"fn": np.array(_fn_bruto(y, p, limiar)),
              "eventos": np.flatnonzero(y == 1),
              "detectados": np.flatnonzero((y == 1) & (p >= limiar))}
    diretas = _categorias_diretas(d)
    perfil = {(e["dimensao"], e["categoria"]): e for e in j["falsos_negativos"]["perfil"]}
    assert set(perfil) == set(diretas)  # todas as dimensões do spec, nenhuma a mais
    for chave, mascara in diretas.items():
        for g, idx in grupos.items():
            contagem = int(mascara[idx].sum())
            e = perfil[chave]
            assert e[f"{g}_n"] == ta.celula(contagem), (chave, g)
            if 0 < contagem < 10:
                assert e[f"{g}_pct"] is None
            else:
                assert e[f"{g}_pct"] == pytest.approx(100.0 * contagem / len(idx)), (chave, g)


def test_dimensoes_do_perfil_vem_do_config_e_do_spec():
    d = _df_sintetico(n=500)
    cfg = {**CFG_BASE, "faixas": [0, 10, 50], "ordem_dobras": ["Norte", "Sul", "Sudeste",
                                                                "Nordeste", "Centro-Oeste"]}
    dim = {x.chave: x for x in te.dimensoes_do_perfil(d, cfg)}
    assert dim["faixa_etaria"].rotulos == ("0–9", "10–49", "50+")
    assert dim["regiao"].rotulos == ("Norte", "Sul", "Sudeste", "Nordeste", "Centro-Oeste")
    assert dim["n_comorbidades"].rotulos == ("0", "1", "2", "3+")
    assert dim["atraso"].rotulos == ("0–1", "2–3", "4–6", "7–14", "15+", "sem data")
    assert [c for c in dim if c.startswith("comorbidade_")] == [f"comorbidade_{c}"
                                                                for c in COMORBIDADES]


def test_numero_de_comorbidades_bate_com_a_coluna_n_comorbidades():
    d = _df_sintetico(n=800)
    assert (te.numero_de_comorbidades(d) == d["n_comorbidades"].to_numpy()).all()


def _sem_1_a_9_no_texto(texto: str) -> bool:
    """Nenhuma contagem de 1 a 9 com proporção ("5 (5,0%)") em tabela markdown. As contagens
    suprimidas aparecem como "<10"; os rótulos de categoria ("1", "2") não são contagens."""
    return re.search(r"\| [1-9] \(", texto) is None


def test_r7_nada_de_1_a_9_no_json_nas_tabelas_nem_no_markdown_e_a_supressao_aparece():
    d, y, p, regra = _dados()
    # força células pequenas no perfil: poucas gestantes entre os falsos negativos
    j = _erros(d, y, p, regra)
    assert artifacts.inteiros_pequenos(json.loads(json.dumps(j))) == []
    tabelas = te.tabelas_erros(j)
    for nome, tabela in tabelas.items():
        assert ev._inteiros_pequenos_na_tabela(tabela) == [], nome
        assert len(tabela) <= ev.LIMITE_LINHAS_TABELA
    texto = te.markdown_erros(j)
    assert _sem_1_a_9_no_texto(texto)
    perfil = tabelas["perfil_falsos_negativos"]
    assert (perfil["fn_n"] == "<10").any()  # a supressão realmente aconteceu (não é vacuidade)
    assert "<10" in texto
    pequeno = perfil[perfil["fn_n"] == "<10"]
    assert pequeno["fn_pct"].isna().all()  # e a proporção daquela célula também sai
    csv = pd.read_csv(io.StringIO(perfil.to_csv(index=False)))
    numericos = pd.to_numeric(csv["fn_n"], errors="coerce").dropna()
    assert not numericos.between(1, 9).any()


def test_saida_da_analise_passa_no_validador_de_agregados():
    d, y, p, regra = _dados()
    j = _erros(d, y, p, regra)
    saida = ev.Saida(te.tabelas_erros(j), te.markdown_erros(j), j, arquivo="erros.md")
    ev._validar_saida("erros", saida)


# --- Células de comorbidade ------------------------------------------------------------------

def _mascaras_comorbidade(d: pd.DataFrame) -> dict[str, np.ndarray]:
    n_com = sum((d[c] == "Sim").astype(int) for c in COMORBIDADES).to_numpy()
    saida = {f"{c} = Sim": (d[c] == "Sim").to_numpy() for c in COMORBIDADES}
    saida |= {"0 comorbidades": n_com == 0, "1 comorbidade": n_com == 1,
              "2 comorbidades": n_com == 2, "3 ou mais comorbidades": n_com >= 3}
    return saida


def test_celulas_de_comorbidade_batem_com_o_calculo_direto():
    d, y, p, regra = _dados()
    limiar = float(np.quantile(p, 0.8))
    j = _erros(d, y, p, regra, limiar=limiar, n=10)
    celulas = {c["celula"]: c for c in j["calibracao_comorbidades"]["celulas"]}
    mascaras = _mascaras_comorbidade(d)
    assert set(celulas) == set(mascaras)  # 7 comorbidades e 0, 1, 2, 3+
    com_metricas = 0
    for rotulo, mascara in mascaras.items():
        c = celulas[rotulo]
        ys, ps = y[mascara], p[mascara]
        assert c["n"] == ta.celula(int(mascara.sum())) and c["eventos"] == ta.celula(int(ys.sum()))
        if int(ys.sum()) < 10:
            assert c["metricas"] is None
            continue
        com_metricas += 1
        m = c["metricas"]
        slope, intercepto = metrics.calibration_slope_intercept(ys, ps)
        assert m["obs_esp"]["valor"] == pytest.approx(ys.sum() / ps.sum(), abs=1e-12)
        assert m["intercepto"]["valor"] == pytest.approx(intercepto, rel=1e-5, abs=1e-7)
        assert m["slope"]["valor"] == pytest.approx(slope, rel=1e-5)
        assert c["risco_previsto_medio"] == pytest.approx(ps.mean(), abs=1e-12)
        for chave in ("obs_esp", "intercepto"):
            lo, hi = m[chave]["ic95"]
            assert lo <= hi
    assert com_metricas >= 8


def test_celulas_saem_ordenadas_pelo_maior_desvio_e_as_sem_metrica_no_fim():
    d, y, p, regra = _dados()
    # uma comorbidade com só 6 eventos: sem métricas, e vai para o fim
    d = d.copy()
    d["HEPATOPAT"] = "Não"
    eventos = np.flatnonzero(y == 1)[:6]
    nao_eventos = np.flatnonzero(y == 0)[:60]
    d.loc[d.index[np.concatenate([eventos, nao_eventos])], "HEPATOPAT"] = "Sim"
    d["n_comorbidades"] = sum((d[c] == "Sim").astype("int8") for c in COMORBIDADES)
    j = _erros(d, y, p, regra)
    celulas = j["calibracao_comorbidades"]["celulas"]
    hep = next(c for c in celulas if c["celula"] == "HEPATOPAT = Sim")
    assert hep["eventos"] == "<10" and hep["metricas"] is None and hep["prevalencia"] is None
    assert "sem métricas" in hep["motivo_sem_metricas"]
    assert celulas[-1]["celula"] == "HEPATOPAT = Sim"  # sem métrica vai para o fim
    desvios = [abs(np.log(c["metricas"]["obs_esp"]["valor"])) for c in celulas if c["metricas"]]
    assert desvios == sorted(desvios, reverse=True)  # maior desvio primeiro
    assert [c["desvio_abs_log"] for c in celulas if c["metricas"]] == pytest.approx(desvios)
    assert artifacts.inteiros_pequenos(json.loads(json.dumps(j))) == []


def test_celula_com_observado_maior_que_esperado_e_lida_como_subestimativa():
    d, y, p, regra = _dados()
    p = np.clip(p * 0.5, 0.0005, 0.999)  # o modelo passa a subestimar em todo lugar
    j = _erros(d, y, p, regra)
    for c in j["calibracao_comorbidades"]["celulas"]:
        if c["metricas"]:
            assert c["metricas"]["obs_esp"]["valor"] > 1
            assert "subestima" in c["sentido"]


def test_politica_de_descarte_da_t52_vale_nas_celulas_de_comorbidade():
    d, y, p, regra = _dados()
    j = _erros(d, y, p, regra)["calibracao_comorbidades"]
    assert j["politica_descarte"] == ta.POLITICA_DESCARTE and j["limite_descarte"] == 0.05
    for c in j["celulas"]:
        if c["metricas"]:
            assert c["metricas"]["reamostras_descartadas"] == 0
            assert c["metricas"]["fracao_descartada"] == 0.0


# --- Espírito Santo à parte ------------------------------------------------------------------

def _es_direto(d: pd.DataFrame) -> np.ndarray:
    """ES pela UF de residência: município primeiro; sem município válido, a UF (laço simples)."""
    saida = []
    for mun, uf in zip(d["ID_MN_RESI"], d["SG_UF"], strict=True):
        mun = "" if pd.isna(mun) else str(mun)
        uf = "" if pd.isna(uf) else str(uf)
        if len(mun) >= 6 and mun[:2].isdigit() and mun[0] in "12345":
            saida.append(mun[:2] == "32")
        else:
            saida.append(uf[:2] == "32")
    return np.array(saida)


def test_espirito_santo_bate_com_o_filtro_direto_e_nao_mistura_com_o_resto():
    d, y, p, regra = _dados()
    d = d.copy()
    d["ID_MN_RESI"] = d["ID_MN_RESI"].astype(object)
    # município ausente: vale a UF; município de outra UF com SG_UF "32": vale o município
    d.loc[d.index[:40], "ID_MN_RESI"] = None
    d.loc[d.index[:40], "SG_UF"] = "32"
    d.loc[d.index[40:80], "ID_MN_RESI"] = "331234"
    d.loc[d.index[40:80], "SG_UF"] = "32"
    limiar = float(np.quantile(p, 0.8))
    j = _erros(d, y, p, regra, limiar=limiar, n=10)
    es = _es_direto(d)
    assert es[:40].all() and not es[40:80].any()  # os casos de borda estão onde se espera
    assert (te.mascara_espirito_santo(d)[0] == es).all()
    grupos = j["espirito_santo"]["grupos"]
    assert set(grupos) == {"ES", "resto_do_brasil"}
    assert grupos["ES"]["n"] == int(es.sum()) and grupos["resto_do_brasil"]["n"] == int((~es).sum())
    for nome, mascara in (("ES", es), ("resto_do_brasil", ~es)):
        g, ys, ps = grupos[nome], y[mascara], p[mascara]
        assert g["eventos"] == ta.celula(int(ys.sum()))
        assert g["prevalencia"] == pytest.approx(ys.mean())
        m = g["metricas"]
        ref = metrics.threshold_metrics(ys, ps, limiar)
        assert m["pr_auc"]["valor"] == pytest.approx(metrics.pr_auc(ys, ps), abs=1e-12)
        assert m["recall"]["valor"] == pytest.approx(ref["recall"], abs=1e-12)
        assert m["precisao"]["valor"] == pytest.approx(ref["precisao"], abs=1e-12)
        assert m["calibracao"]["obs_esp"]["valor"] == pytest.approx(ys.sum() / ps.sum(), abs=1e-12)
        assert m["pr_auc"]["ic95"][0] <= m["pr_auc"]["ic95"][1]
    # o ES não é o resto: se fossem misturados, as métricas dos dois grupos coincidiriam
    assert grupos["ES"]["metricas"]["pr_auc"]["valor"] != grupos["resto_do_brasil"]["metricas"][
        "pr_auc"]["valor"]


def test_codigo_uf_usa_o_municipio_malformado_cai_na_uf_e_sem_nada_fica_desconhecido():
    d = pd.DataFrame({
        "ID_MN_RESI": ["320530", "350000", "32", None, "", "abc", "9999", None],
        "SG_UF": ["35", "32", "35", "32", "31", "33", None, None]})
    uf = te.codigo_uf_residencia(d)
    # o município bem formado vale (mesmo contra a UF); o código de UF sozinho também; município
    # ausente ou malformado cai na UF; sem nenhum dos dois, a UF é desconhecida
    assert uf.iloc[:6].tolist() == ["32", "35", "32", "32", "31", "33"]
    assert uf.iloc[6:].isna().all()
    es, conhecida = te.mascara_espirito_santo(d)
    assert es.tolist() == [True, False, True, True, False, False, False, False]
    assert conhecida.tolist() == [True] * 6 + [False, False]


def test_es_com_poucos_eventos_leva_aviso_e_com_menos_de_10_sai_sem_metricas():
    d, y, p, regra = _dados()
    es = _es_direto(d)
    y = y.copy()
    y[es] = 0
    y[np.flatnonzero(es)[:30]] = 1  # 30 eventos no ES
    j = _erros(d, y, p, regra)
    assert j["espirito_santo"]["aviso"] and "poucos eventos" in j["espirito_santo"]["aviso"]
    assert j["espirito_santo"]["grupos"]["ES"]["aviso_ic_largo"]
    assert j["espirito_santo"]["grupos"]["ES"]["metricas"] is not None
    y[es] = 0
    y[np.flatnonzero(es)[:4]] = 1  # 4 eventos: R7
    j = _erros(d, y, p, regra)
    g = j["espirito_santo"]["grupos"]["ES"]
    assert g["eventos"] == "<10" and g["metricas"] is None and g["prevalencia"] is None
    assert "sem métricas" in g["motivo_sem_metricas"]
    assert artifacts.inteiros_pequenos(json.loads(json.dumps(j))) == []


def test_es_com_muitos_eventos_nao_leva_aviso():
    d, y, p, regra = _dados(n=40000, seed=4)
    es = _es_direto(d)
    assert int(y[es].sum()) >= 100
    assert _erros(d, y, p, regra, n=4)["espirito_santo"]["aviso"] is None


def test_criterio_do_es_e_a_nota_do_sistema_ficam_documentados():
    d, y, p, regra = _dados(n=3000)
    j = _erros(d, y, p, regra, n=4)["espirito_santo"]
    assert "residência" in j["criterio_uf"] and "32" in j["criterio_uf"]
    assert "e-SUS" in j["nota_sistema"]
    assert j["sem_uf_conhecida"] == 0


# --- Bootstrap: semente, processos, fluxos ---------------------------------------------------

def test_resultado_nao_depende_do_numero_de_processos():
    d, y, p, regra = _dados(n=4000)
    um = _erros(d, y, p, regra, n=6, processos=1)
    dois = _erros(d, y, p, regra, n=6, processos=2)
    assert json.dumps(um, sort_keys=True) == json.dumps(dois, sort_keys=True)


def test_mesma_semente_reproduz_e_outra_semente_muda_os_ics():
    d, y, p, regra = _dados(n=4000)
    a1 = _erros(d, y, p, regra, n=10, seed=1)
    a2 = _erros(d, y, p, regra, n=10, seed=1)
    b = _erros(d, y, p, regra, n=10, seed=2)
    assert a1 == a2 and a1 != b
    assert a1["falsos_negativos"] == b["falsos_negativos"]  # a seleção não é aleatória


def test_cada_celula_e_grupo_usa_o_seu_fluxo_a_partir_de_100(monkeypatch):
    d, y, p, regra = _dados(n=4000)
    vistos = []
    original = ta.estado_do_subgrupo

    def espiar(y_sub, p_sub, regra_sub, limiar, fluxo_base):
        vistos.append(fluxo_base)
        return original(y_sub, p_sub, regra_sub, limiar, fluxo_base)

    monkeypatch.setattr(ta, "estado_do_subgrupo", espiar)
    j = _erros(d, y, p, regra, n=4)
    assert te.FLUXO_ERROS == 100 and vistos[0] == 100
    assert len(set(vistos)) == len(vistos)  # nenhum fluxo repetido
    assert all(b - a >= 2 for a, b in zip(vistos, vistos[1:], strict=False))  # 2 fluxos por estado
    com_metricas = sum(1 for c in j["calibracao_comorbidades"]["celulas"] if c["metricas"]) + sum(
        1 for g in j["espirito_santo"]["grupos"].values() if g["metricas"])
    assert len(vistos) == com_metricas
    assert min(vistos) >= 100  # não invade os fluxos da T-5.1 (0 e 1), decisão (2), calibração (3)


def test_recusa_n_zero():
    d, y, p, regra = _dados(n=1000)
    with pytest.raises(ValueError, match="pelo menos uma"):
        _erros(d, y, p, regra, n=0)


# --- Integração com evaluate: arquivos, lacre, ensaio, checks --------------------------------

def _json_do_teste(cfg: dict) -> dict:
    return json.loads((Path(cfg["caminhos"]["relatorios"]) / "teste" / "metricas.json")
                      .read_text(encoding="utf-8"))


def test_avaliacao_grava_erros_e_criterios_com_csv_e_todos_os_hashes_no_lacre(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    lacre = json.loads((pasta / "LACRE.json").read_text(encoding="utf-8"))
    esperados = {"metricas.md", "metricas.json", "erros.md", "criterios.md",
                 "erros__perfil_falsos_negativos.csv", "erros__calibracao_comorbidades.csv",
                 "erros__espirito_santo.csv", "criterios__criterios.csv"}
    assert esperados <= set(lacre["relatorios"])
    for nome, sha in lacre["relatorios"].items():  # todo arquivo gravado entra no lacre
        assert ev._sha256_texto((pasta / nome).read_text(encoding="utf-8")) == sha, nome
    gravados = {p.name for p in pasta.iterdir()} - {"LACRE.json"}
    assert gravados == set(lacre["relatorios"])  # e nada fica de fora
    assert execucao.ordem[-1] == "gravado:LACRE.json" and execucao.ordem[0] == "calculo_concluido"
    js = _json_do_teste(cfg)["analises"]
    assert {"erros", "criterios"} <= set(js)
    md = (pasta / "metricas.md").read_text(encoding="utf-8")
    assert "erros.md" in md and "criterios.md" in md  # o metricas.md só aponta para os dois
    assert "Falsos negativos de maior risco" not in md
    assert "Avaliação única em 2024" in (pasta / "erros.md").read_text(encoding="utf-8")


def test_arquivos_do_teste_nao_tem_nenhuma_linha_individual(cfg, df, esperado):
    ev.evaluate_test_once(cfg, fontes=_fontes(df))
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    modelos = _modelos(df)
    from dengue_sinan import guard

    with guard.leitura_do_teste():
        p = modelos.m1.prever_proba(df)
    y = df["y"].to_numpy()
    escolhidos = _fn_bruto(y, p, modelos.m1.limiar)
    texto = "\n".join(arq.read_text(encoding="utf-8") for arq in pasta.iterdir()
                      if arq.name.startswith("erros"))
    texto += json.dumps(_json_do_teste(cfg)["analises"]["erros"], ensure_ascii=False)
    # Os quantis publicados (mediana com n ímpar, por exemplo) podem coincidir com o valor de um
    # caso sem identificá-lo: fora eles, o risco de nenhum dos selecionados aparece, inteiro, em
    # nenhum arquivo (o mínimo e o máximo, em especial).
    quantis = set(_json_do_teste(cfg)["analises"]["erros"]["falsos_negativos"][
        "risco_previsto"].values())
    individuais = [i for i in escolhidos if float(p[i]) not in quantis]
    assert len(individuais) >= len(escolhidos) - 3
    for i in individuais:
        for forma in (repr(float(p[i])), f"{p[i]:.6f}", f"{p[i]:.6f}".replace(".", ",")):
            assert re.search(r"(?<![\d.,])" + re.escape(forma) + r"(?!\d)", texto) is None, i
    for tabela in pasta.glob("erros__*.csv"):
        quadro = pd.read_csv(tabela)
        assert len(quadro) <= ev.LIMITE_LINHAS_TABELA
        assert not {"LINHA", "ANO", "idade_anos", "y"} & set(quadro.columns)  # nada de caso
    assert _sem_1_a_9_no_texto((pasta / "erros.md").read_text(encoding="utf-8"))
    assert _sem_1_a_9_no_texto((pasta / "criterios.md").read_text(encoding="utf-8"))


def _blocos_do_bootstrap_proprio(analises: dict) -> dict:
    """Só o que vem do bootstrap DESTAS análises (não o que vem de `metricas`, que muda com a
    semente de qualquer jeito): métricas das células de comorbidade, os grupos do ES e o SC-02."""
    erros = analises["erros"]
    return {"celulas": [c["metricas"] for c in erros["calibracao_comorbidades"]["celulas"]],
            "es": erros["espirito_santo"]["grupos"],
            "sc02": analises["criterios"]["sc02"]["detalhe"]}


def _avaliar_com(cfg, df, tmp_path, nome, seed, n) -> dict:
    c = copy.deepcopy(cfg)
    c["caminhos"]["relatorios"] = str(tmp_path / nome)
    c["seed"] = seed
    c["bootstrap"]["metricas"] = n
    ev.evaluate_test_once(c, fontes=_fontes(df))
    return _json_do_teste(c)["analises"]


def test_semente_do_config_chega_ao_bootstrap_de_erros_e_do_sc02(cfg, df, esperado, tmp_path):
    esperado["bootstrap"]["metricas"] = 37
    resultados = {nome: _avaliar_com(cfg, df, tmp_path, nome, seed, 37)
                  for nome, seed in (("a1", 111), ("a2", 111), ("b", 222))}
    blocos = {k: _blocos_do_bootstrap_proprio(v) for k, v in resultados.items()}
    assert blocos["a1"] == blocos["a2"]  # mesma semente reproduz
    assert blocos["a1"]["celulas"] != blocos["b"]["celulas"]  # outra semente, outros ICs
    assert blocos["a1"]["es"] != blocos["b"]["es"]
    assert blocos["a1"]["sc02"] != blocos["b"]["sc02"]
    # e são exatamente os da chamada direta com a semente e o n do config (não 1, não 1000)
    modelos = _modelos(df)
    pred = ev.predizer(modelos, df, dentro_do_teste=True)
    y = df["y"].to_numpy()
    for nome, seed in (("a1", 111), ("b", 222)):
        direto_erros = json.loads(json.dumps(te.analisar_erros(
            df, y, pred.probabilidades["M1"], pred.b2, modelos.m1.limiar, CFG_BASE, seed=seed,
            n=37, processos=1)))
        direto_sc02 = json.loads(json.dumps(tc.diferencas_no_limiar(
            y, ev._flags(pred), seed=seed, n=37)))
        obtido = blocos[nome]
        assert obtido["celulas"] == [c["metricas"] for c in
                                     direto_erros["calibracao_comorbidades"]["celulas"]]
        assert obtido["es"] == direto_erros["espirito_santo"]["grupos"]
        assert obtido["sc02"] == {"recall": direto_sc02["recall"],
                                  "precisao": direto_sc02["precisao"]}


def test_n_de_reamostras_do_config_chega_a_erros_e_ao_sc02(cfg, df, esperado, tmp_path):
    esperado["bootstrap"]["metricas"] = 37
    a = _avaliar_com(cfg, df, tmp_path, "n37", 5, 37)
    assert a["erros"]["reamostras"] == 37
    assert a["criterios"]["sc02"]["reamostras_do_sc02"] == 37  # o n usado no SC-02, não copiado
    assert a["metricas"]["reamostras"] == 37


def test_reamostras_pequenas_saem_como_texto_em_erros_e_no_sc02(cfg, df, esperado, tmp_path):
    esperado["bootstrap"]["metricas"] = 5
    a = _avaliar_com(cfg, df, tmp_path, "n5", 5, 5)
    assert a["erros"]["reamostras"] == "5"
    assert a["criterios"]["sc02"]["reamostras_do_sc02"] == "5"
    assert artifacts.inteiros_pequenos(a["erros"]) == []
    assert artifacts.inteiros_pequenos(a["criterios"]) == []
    d, y, p, regra = _dados(n=2000)
    assert _erros(d, y, p, regra, n=5)["reamostras"] == "5"


def test_analises_novas_nao_dependem_do_numero_de_processos_na_avaliacao(cfg, df, esperado,
                                                                         tmp_path):
    saidas = {}
    for processos in (1, 2):
        c = copy.deepcopy(cfg)
        c["caminhos"]["relatorios"] = str(tmp_path / f"p{processos}")
        c["bootstrap"]["processos"] = processos
        ev.evaluate_test_once(c, fontes=_fontes(df))
        saidas[processos] = _json_do_teste(c)["analises"]
    assert saidas[1]["erros"] == saidas[2]["erros"]
    assert saidas[1]["criterios"] == saidas[2]["criterios"]


def test_ensaio_roda_erros_e_criterios_com_a_marca_sem_tocar_o_teste_nem_criar_lacre(cfg):
    dev = pd.concat([_df_sintetico(n=2000, ano=2022), _df_sintetico(n=1500, seed=8, ano=2023)],
                    ignore_index=True)
    modelos = _modelos(dev)
    fontes = ev.Fontes(populacao=lambda c: dev.copy(), hash_dados=lambda c: {},
                       modelos=lambda c: modelos, features=lambda d: d, selecao=_sel_fonte)
    ev.ensaiar_em_desenvolvimento(cfg, fontes=fontes)
    base = Path(cfg["caminhos"]["relatorios"])
    assert not (base / "teste").exists()
    for nome in ("erros.md", "criterios.md"):
        assert "ENSAIO, não é avaliação" in (base / "ensaio" / nome).read_text(encoding="utf-8")
    assert (base / "ensaio" / "erros__espirito_santo.csv").exists()
    js = json.loads((base / "ensaio" / "metricas.json").read_text(encoding="utf-8"))
    assert {"erros", "criterios"} <= set(js["analises"])


def test_checks_d64_novos_passam_na_avaliacao_sintetica(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    checks = {c["nome"]: c for c in ev.checks_teste(cfg, execucao, esperado, ambiente=[])}
    for nome in ("erros_com_n_falsos_negativos_do_config", "erros_sem_contagens_de_1_a_9",
                 "criterios_sc01_a_sc04_presentes", "espirito_santo_a_parte_presente"):
        assert checks[nome]["passou"] is True, nome
    for sc in ("sc01", "sc02", "sc03", "sc04"):
        assert f"{sc}_passou" in checks


def _checks_com(cfg, execucao, esperado, mexer) -> dict:
    js = json.loads(execucao.json_texto)
    mexer(js["analises"])
    execucao = dataclasses.replace(execucao, json_texto=json.dumps(js))
    return {c["nome"]: c for c in ev.checks_teste(cfg, execucao, esperado, ambiente=[])}


def test_checks_d64_reprovam_quando_o_json_nao_tem_o_que_deveria(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))

    def n_errado(a):
        a["erros"]["falsos_negativos"]["n_perfil"] = 12345

    def pedido_errado(a):
        a["erros"]["n_pedido"] = 50

    def sem_campo(a):
        del a["criterios"]["sc03"]["ic95"]

    def sem_es(a):
        del a["erros"]["espirito_santo"]["grupos"]["ES"]

    def contagem_pequena(a):
        a["erros"]["falsos_negativos"]["detectados"] = 7

    assert _checks_com(cfg, execucao, esperado, n_errado)[
        "erros_com_n_falsos_negativos_do_config"]["passou"] is False
    assert _checks_com(cfg, execucao, esperado, pedido_errado)[
        "erros_com_n_falsos_negativos_do_config"]["passou"] is False
    assert _checks_com(cfg, execucao, esperado, sem_campo)[
        "criterios_sc01_a_sc04_presentes"]["passou"] is False
    assert _checks_com(cfg, execucao, esperado, sem_es)[
        "espirito_santo_a_parte_presente"]["passou"] is False
    assert _checks_com(cfg, execucao, esperado, contagem_pequena)[
        "erros_sem_contagens_de_1_a_9"]["passou"] is False


def test_check_das_reamostras_reprova_quando_erros_ou_sc02_usam_outro_n(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    nome = "reamostras_dos_erros_e_do_sc02_do_config"
    ok = _checks_com(cfg, execucao, esperado, lambda a: None)[nome]
    assert ok["passou"] is True

    def erros_com_1000(a):
        a["erros"]["reamostras"] = 1000

    def sc02_com_1000(a):
        a["criterios"]["sc02"]["reamostras_do_sc02"] = 1000

    def sc02_sem_campo(a):
        del a["criterios"]["sc02"]["reamostras_do_sc02"]

    for mexer in (erros_com_1000, sc02_com_1000, sc02_sem_campo):
        assert _checks_com(cfg, execucao, esperado, mexer)[nome]["passou"] is False, mexer


def test_check_do_n_aceita_menos_de_100_falsos_negativos_quando_o_total_e_menor(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))

    def poucos(a):
        a["erros"]["falsos_negativos"]["total"] = 40
        a["erros"]["falsos_negativos"]["n_perfil"] = 40

    assert _checks_com(cfg, execucao, esperado, poucos)[
        "erros_com_n_falsos_negativos_do_config"]["passou"] is True


def test_gerar_verificacao_do_lacre_confere_erros_md_e_criterios_md(cfg, df, esperado):
    ev.evaluate_test_once(cfg, fontes=_fontes(df))
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    dados = json.loads(ev.gerar_verificacao_do_lacre(cfg, ambiente=[]).read_text(encoding="utf-8"))
    assert dados["passou"] is True
    nomes = {c["nome"] for c in dados["checks"]}
    assert "espirito_santo_a_parte_presente" in nomes
    (pasta / "erros.md").write_text("adulterado", encoding="utf-8")
    dados = json.loads(ev.gerar_verificacao_do_lacre(cfg, ambiente=[]).read_text(encoding="utf-8"))
    assert dados["passou"] is False


def test_queda_ao_gravar_erros_md_nao_deixa_lacre_nem_resultado_parcial(cfg, df, esperado,
                                                                        monkeypatch):
    original = ev._gravar_atomico

    def cai(caminho, texto):
        if caminho.name == "criterios.md":
            raise OSError("queda simulada")
        original(caminho, texto)

    monkeypatch.setattr(ev, "_gravar_atomico", cai)
    with pytest.raises(OSError, match="queda simulada"):
        ev.evaluate_test_once(cfg, fontes=_fontes(df))
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    assert not (pasta / "LACRE.json").exists()
    assert not list(pasta.glob("*.md")) and not list(pasta.glob("*.csv"))  # limpou o que gravou
    monkeypatch.setattr(ev, "_gravar_atomico", original)
    ev.evaluate_test_once(cfg, fontes=_fontes(df))  # nova execução é permitida (D-93)


def test_arquivo_da_saida_precisa_ser_um_nome_md_simples_e_diferente_do_metricas():
    ok = ev.Saida({}, "", {}, arquivo="erros.md")
    ev._validar_saida("x", ok)
    for ruim in ("erros.txt", "../erros.md", "sub/erros.md", "metricas.md"):
        with pytest.raises(ValueError, match="arquivo"):
            ev._validar_saida("x", ev.Saida({}, "", {}, arquivo=ruim))


def test_erros_usa_o_limiar_congelado_do_m1_e_a_regra_b2_do_contexto(cfg, df, esperado):
    modelos = _modelos(df)
    ev.evaluate_test_once(cfg, fontes=_fontes(df, modelos))
    fn = _json_do_teste(cfg)["analises"]["erros"]["falsos_negativos"]
    assert fn["limiar"] == modelos.m1.limiar  # o congelado, não um recalculado
