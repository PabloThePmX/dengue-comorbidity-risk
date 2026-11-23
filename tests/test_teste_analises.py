"""Testes das análises da T-5.2 (curva de decisão, calibração com bandas, subgrupos), D-93.

Só dados sintéticos pequenos: nenhum microdado, nenhum 2024 real (R1). Cada comportamento tem uma
referência independente: força bruta para o net benefit, filtro direto do DataFrame para os
subgrupos, linhas expandidas com os mesmos sorteios para as bandas de bootstrap.
O teste de escala (5,3 milhões de linhas) só roda com DENGUE_TESTES_LENTOS=1.
"""

import copy
import dataclasses
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from test_evaluate import REGIOES, _df_sintetico, _esperado_de, _fontes, _modelos, _sel_fonte

from dengue_sinan import artifacts, guard, metrics
from dengue_sinan import evaluate as ev
from dengue_sinan import teste_analises as ta
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


# --- Dados sintéticos para as análises -------------------------------------------------------

def _dados(n: int = 8000, seed: int = 3):
    """Casos com prevalência ~6% (eventos de sobra nos subgrupos grandes) e as predições."""
    rng = np.random.default_rng(seed)
    df = _df_sintetico(n=n, seed=seed)
    y = (rng.random(n) < 0.06).astype(np.int64)
    df["y"] = y
    base = np.log(0.06 / 0.94)
    p_m1 = 1 / (1 + np.exp(-(base + 0.9 * (y - 0.06) + 0.7 * rng.standard_normal(n))))
    p_e1 = np.round(1 / (1 + np.exp(-(base + 0.4 * (y - 0.06) + 0.5 * rng.standard_normal(n)))), 2)
    regra = rng.random(n) < (0.25 + 0.3 * y)
    return df, y, p_m1, p_e1, regra


def _bruto_nb(y, risco_ou_flag, t: float) -> float:
    """Net benefit por força bruta: laço sobre as linhas, sem vetorização."""
    vp = fp = 0
    for yi, ri in zip(y, risco_ou_flag, strict=True):
        tratar = ri >= t if not isinstance(ri, (bool, np.bool_)) else bool(ri)
        if tratar:
            vp += int(yi == 1)
            fp += int(yi == 0)
    return vp / len(y) - fp / len(y) * t / (1 - t)


GRADE = ta.grade_de_limiares(CFG_BASE)
MARCADOS = {"M1_principal": 0.0123, "M1_f2": 0.0371}
UNIAO = np.unique(np.concatenate([GRADE, list(MARCADOS.values())]))
REPRESENTANTES = np.concatenate([[UNIAO[0] / 2], (UNIAO[:-1] + UNIAO[1:]) / 2, [0.2]])


def _dados_decisao(n: int = 600, seed: int = 1):
    """Riscos tirados de UM valor por faixa de limiar: células por faixa = células por valor, então
    a reamostra de linhas expandidas pode ser calculada com os valores reais."""
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < 0.15).astype(np.int64)
    m = len(REPRESENTANTES)

    def escolher(forca: int) -> np.ndarray:
        return REPRESENTANTES[np.clip(rng.integers(0, 30, n) + y * rng.integers(0, forca, n),
                                      0, m - 1)]

    return y, escolher(25), escolher(10), rng.random(n) < (0.2 + 0.3 * y)


# --- Curva de decisão ------------------------------------------------------------------------

def test_net_benefit_bate_com_a_implementacao_em_forca_bruta_e_com_metrics():
    y, p_m1, p_b1, regra = _dados_decisao()
    res = ta.curva_de_decisao(y, {"M1": p_m1, "B1": p_b1}, regra, GRADE, MARCADOS, seed=1, n=3)
    prevalencia = y.mean()
    for j, t in enumerate(res.uniao):
        assert res.pontos["M1"][j] == pytest.approx(_bruto_nb(y, p_m1, t), abs=1e-12)
        assert res.pontos["B1"][j] == pytest.approx(_bruto_nb(y, p_b1, t), abs=1e-12)
        assert res.pontos["B2"][j] == pytest.approx(_bruto_nb(y, regra, t), abs=1e-12)
        assert res.pontos["tratar_todos"][j] == pytest.approx(
            prevalencia - (1 - prevalencia) * t / (1 - t), abs=1e-12)
    ref = metrics.net_benefit(y, p_m1, GRADE)
    assert res.pontos["M1"][res.idx_grade] == pytest.approx(ref["modelo"].to_numpy(), abs=1e-12)
    assert res.pontos["tratar_todos"][res.idx_grade] == pytest.approx(
        ref["tratar_todos"].to_numpy(), abs=1e-12)


def test_limiares_marcados_ficam_na_curva_na_posicao_certa():
    y, p_m1, p_b1, regra = _dados_decisao()
    res = ta.curva_de_decisao(y, {"M1": p_m1, "B1": p_b1}, regra, GRADE, MARCADOS, seed=1, n=3)
    for nome, t in MARCADOS.items():
        assert res.uniao[res.idx_marcados[nome]] == t
        assert res.pontos["M1"][res.idx_marcados[nome]] == pytest.approx(
            _bruto_nb(y, p_m1, t), abs=1e-12)


@pytest.mark.parametrize("k", [0, 1, 2, 3])
def test_bandas_da_decisao_batem_com_linhas_expandidas_dos_mesmos_sorteios(k):
    # A reamostra k, expandida em linhas com os pesos do MESMO sorteio, dá o NB de força bruta de
    # cada curva: vale para todos os modelos e para a regra (mesmos sorteios, D-53).
    y, p_m1, p_b1, regra = _dados_decisao()
    n, seed = 4, 11
    res = ta.curva_de_decisao(y, {"M1": p_m1, "B1": p_b1}, regra, GRADE, MARCADOS, seed=seed, n=n)
    cel = metrics.agrupar_celulas(y, {"M1": p_m1, "B1": p_b1, "B2": regra})
    semente = metrics.sementes_das_reamostras(seed, n)[k]
    w = metrics.Sorteio(cel.contagem, cel.n_negativas)(metrics.fluxo(semente, ta.FLUXO_DECISAO))
    linhas = np.repeat(np.arange(len(cel)), w.astype(int))
    y_r = cel.y[linhas]
    for j, t in enumerate(res.uniao):
        assert res.dist["M1"][k, j] == pytest.approx(
            _bruto_nb(y_r, cel.colunas["M1"][linhas], t), abs=1e-12)
        assert res.dist["B1"][k, j] == pytest.approx(
            _bruto_nb(y_r, cel.colunas["B1"][linhas], t), abs=1e-12)
        assert res.dist["B2"][k, j] == pytest.approx(
            _bruto_nb(y_r, cel.colunas["B2"][linhas].astype(bool), t), abs=1e-12)


def test_ic_da_decisao_e_o_quantil_das_reamostras_e_a_prevalencia_nao_varia():
    y, p_m1, p_b1, regra = _dados_decisao()
    n = 40
    res = ta.curva_de_decisao(y, {"M1": p_m1, "B1": p_b1}, regra, GRADE, MARCADOS, seed=5, n=n)
    j = ta.decisao_em_json(res, GRADE, MARCADOS, n, "B2", {})
    banda = np.quantile(res.dist["M1"][:, res.idx_grade], ta.QUANTIS_IC, axis=0)
    assert j["curvas"]["M1"]["ic_inf"] == pytest.approx(banda[0], abs=1e-15)
    assert j["curvas"]["M1"]["ic_sup"] == pytest.approx(banda[1], abs=1e-15)
    assert np.ptp(res.dist["tratar_todos"], axis=0).max() < 1e-12  # estratificado: prevalência fixa
    assert len(j["limiares"]) == 50 and j["tratar_ninguem"]["nb"] == [0.0] * 50


def test_decisao_recusa_grade_fora_de_0_1_e_n_zero():
    y, p_m1, p_b1, regra = _dados_decisao()
    with pytest.raises(ValueError, match="grade"):
        ta.curva_de_decisao(y, {"M1": p_m1}, regra, np.array([0.0, 0.1]), {}, seed=1, n=2)
    with pytest.raises(ValueError, match="pelo menos uma"):
        ta.curva_de_decisao(y, {"M1": p_m1}, regra, GRADE, {}, seed=1, n=0)


def test_limiar_de_operacao_fora_de_0_1_fica_sem_net_benefit_e_sem_erro():
    y, p_m1, p_b1, regra = _dados_decisao()
    marcados = {"M1_principal": 0.0123, "M1_f2": 1.0}
    res = ta.curva_de_decisao(y, {"M1": p_m1, "B1": p_b1}, regra, GRADE, marcados, seed=1, n=3)
    j = ta.decisao_em_json(res, GRADE, marcados, 3, "B2", {})
    assert j["pontos_marcados"]["M1_f2"]["nb"] is None
    assert j["pontos_marcados"]["M1_principal"]["nb"] is not None


def test_ponto_marcado_fora_do_intervalo_da_curva_e_sinalizado():
    y, p_m1, p_b1, regra = _dados_decisao()
    marcados = {"M1_principal": 0.2, "M1_f2": 0.0371}  # 20% está acima de dca_limiares.max
    res = ta.curva_de_decisao(y, {"M1": p_m1, "B1": p_b1}, regra, GRADE, marcados, seed=1, n=3)
    j = ta.decisao_em_json(res, GRADE, marcados, 3, "B2", {})
    assert j["pontos_marcados"]["M1_principal"]["dentro_da_faixa"] is False
    assert j["pontos_marcados"]["M1_f2"]["dentro_da_faixa"] is True
    assert j["pontos_marcados"]["M1_principal"]["nb"]["valor"] == pytest.approx(
        _bruto_nb(y, p_m1, 0.2), abs=1e-12)


def test_grade_vem_do_config_com_50_passos():
    assert len(GRADE) == CFG_BASE["dca_limiares"]["passos"] == 50
    assert GRADE[0] == CFG_BASE["dca_limiares"]["min"]
    assert GRADE[-1] == pytest.approx(CFG_BASE["dca_limiares"]["max"], abs=1e-15)


# --- Calibração por caixas -------------------------------------------------------------------

def _caixa_direta(p: np.ndarray, cortes: np.ndarray) -> np.ndarray:
    """Caixa de cada linha por comparação direta com os cortes (sem searchsorted)."""
    caixa = np.zeros(len(p), dtype=np.int64)
    for corte in cortes:
        caixa += (p >= corte).astype(np.int64)
    return caixa


def test_calibracao_por_caixa_bate_com_o_calculo_direto():
    _df, y, p_m1, p_e1, _regra = _dados()
    res = ta.calibracao_por_caixas(y, {"M1": p_m1, "E1": p_e1}, caixas=10, seed=2, n=5)
    for nome, p in (("M1", p_m1), ("E1", p_e1)):
        caixa = _caixa_direta(p, res.cortes[nome])
        for b in range(len(res.cortes[nome]) + 1):
            dentro = caixa == b
            assert res.n_caixa[nome][b] == dentro.sum()
            assert res.eventos_caixa[nome][b] == y[dentro].sum()
            assert res.previsto_medio[nome][b] == pytest.approx(p[dentro].mean(), abs=1e-12)
    assert len(res.cortes["M1"]) + 1 == 10  # M1 contínuo: as 10 caixas pedidas
    assert len(res.cortes["E1"]) + 1 < 10  # E1 com empates (2 casas): caixas colapsam, sem erro


def test_caixas_por_quantis_deixa_empates_na_mesma_caixa():
    p = np.array([0.1] * 50 + [0.2] * 30 + [0.3] * 20)
    cortes, caixa = ta.caixas_por_quantis(p, 10)
    for valor in (0.1, 0.2, 0.3):
        assert len(set(caixa[p == valor])) == 1
    assert len(cortes) + 1 == len(set(caixa))


@pytest.mark.parametrize("k", [0, 1, 2])
def test_bandas_de_calibracao_batem_com_linhas_expandidas_dos_mesmos_sorteios(k):
    _df, y, p_m1, p_e1, _regra = _dados(n=3000)
    n, seed = 3, 9
    res = ta.calibracao_por_caixas(y, {"M1": p_m1, "E1": p_e1}, caixas=10, seed=seed, n=n)
    caixas = {"M1": _caixa_direta(p_m1, res.cortes["M1"]),
              "E1": _caixa_direta(p_e1, res.cortes["E1"])}
    cel = metrics.agrupar_celulas(y, caixas)
    semente = metrics.sementes_das_reamostras(seed, n)[k]
    w = metrics.Sorteio(cel.contagem, cel.n_negativas)(metrics.fluxo(semente, ta.FLUXO_CALIBRACAO))
    linhas = np.repeat(np.arange(len(cel)), w.astype(int))
    y_r = cel.y[linhas]
    for nome in ("M1", "E1"):
        caixa_r = cel.colunas[nome][linhas]
        for b in range(len(res.cortes[nome]) + 1):
            dentro = caixa_r == b
            esperado = y_r[dentro].mean() if dentro.any() else np.nan
            assert res.dist[nome][k, b] == pytest.approx(esperado, abs=1e-12, nan_ok=True)


def test_calibracao_em_json_reusa_os_globais_e_suprime_caixa_com_1_a_9_eventos():
    rng = np.random.default_rng(4)
    n = 4000
    p = np.sort(rng.random(n)) * 0.02 + 0.001
    y = np.zeros(n, dtype=np.int64)
    y[-5:] = 1  # 5 eventos, todos na última caixa
    y[:200] = 0
    y[1000:1300] = 1  # eventos de sobra no meio
    res = ta.calibracao_por_caixas(y, {"M1": p}, caixas=10, seed=1, n=20)
    globais = {"M1": {"slope": {"valor": 1.0, "ic95": [0.9, 1.1]}}}
    j = ta.calibracao_em_json(res, 20, globais)
    assert j["modelos"]["M1"]["global"] == globais["M1"]  # reaproveitado, não recalculado
    ultima = j["modelos"]["M1"]["caixas"][-1]
    assert artifacts.inteiros_pequenos(json.loads(json.dumps(j))) == []
    if ultima["eventos"] == "<10":
        assert ultima["taxa_observada"] is None and ultima["ic95"] is None


def test_calibracao_recusa_n_zero_e_caixas_zero():
    y = np.array([0, 1, 0, 1])
    with pytest.raises(ValueError, match="pelo menos uma"):
        ta.calibracao_por_caixas(y, {"M1": np.array([0.1, 0.2, 0.3, 0.4])}, caixas=2, seed=1, n=0)
    with pytest.raises(ValueError, match="caixas"):
        ta.caixas_por_quantis(np.array([0.1, 0.2]), 0)


# --- Subgrupos: partições, métricas, R7, avisos ----------------------------------------------

RACAS = {"1": "Branca", "2": "Preta", "3": "Amarela", "4": "Parda", "5": "Indígena"}


def _mascaras_diretas(df: pd.DataFrame) -> dict[str, dict[str, np.ndarray]]:
    """Cada subgrupo como máscara, pelo filtro direto do DataFrame (sem usar o código testado)."""
    idade = df["idade_anos"]
    faixas = {"0–4": (0, 5), "5–14": (5, 15), "15–39": (15, 40), "40–59": (40, 60),
              "60–79": (60, 80), "80+": (80, np.inf)}
    raca = df["CS_RACA"].map(RACAS).fillna("Ignorado/em branco").to_numpy()
    return {
        "faixa_etaria": {r: ((idade >= a) & (idade < b)).to_numpy()
                         for r, (a, b) in faixas.items()},
        "sexo": {"F": (df["CS_SEXO"] == "F").to_numpy(), "M": (df["CS_SEXO"] == "M").to_numpy(),
                 "I": (df["CS_SEXO"] == "I").to_numpy(),
                 "em branco": (df["CS_SEXO"] == "").to_numpy()},
        "gestante": {"gestante": (df["gestante"] == 1).to_numpy(),
                     "não gestante": (df["gestante"] != 1).to_numpy()},
        "regiao": {r: (df["regiao"] == r).to_numpy() for r in REGIOES},
        "raca_cor": {r: raca == r for r in [*RACAS.values(), "Ignorado/em branco"]},
    }


def _subgrupos(df, y, p, regra, limiar, cfg, *, n=12, seed=7, processos=1) -> dict:
    return ta.analisar_subgrupos(df, y, p, regra, limiar, cfg, seed=seed, n=n,
                                 processos=processos)


def test_cada_particao_bate_com_o_filtro_direto_do_dataframe_e_cobre_todos_os_casos():
    df, y, p, _, regra = _dados()
    limiar = float(np.quantile(p, 0.8))
    j = _subgrupos(df, y, p, regra, limiar, CFG_BASE)
    mascaras = _mascaras_diretas(df)
    assert set(j["dimensoes"]) == set(mascaras)
    for dimensao, grupos in mascaras.items():
        bloco = j["dimensoes"][dimensao]
        assert set(bloco["subgrupos"]) == set(grupos)  # mesmos subgrupos, na ordem do spec
        assert bloco["particao_completa"] is True
        assert sum(m.sum() for m in grupos.values()) == len(df)  # a máscara direta também cobre
        for rotulo, mascara in grupos.items():
            s = bloco["subgrupos"][rotulo]
            assert s["n"] == ta.celula(int(mascara.sum())), (dimensao, rotulo)
            assert s["eventos"] == ta.celula(int(y[mascara].sum())), (dimensao, rotulo)


def test_metricas_de_cada_subgrupo_batem_com_o_calculo_direto_no_filtro():
    df, y, p, _, regra = _dados()
    limiar = float(np.quantile(p, 0.8))
    j = _subgrupos(df, y, p, regra, limiar, CFG_BASE, n=10)
    mascaras = _mascaras_diretas(df)
    com_metricas = 0
    for dimensao, grupos in mascaras.items():
        for rotulo, mascara in grupos.items():
            s = j["dimensoes"][dimensao]["subgrupos"][rotulo]
            if s["metricas"] is None:
                assert int(y[mascara].sum()) < 10
                continue
            com_metricas += 1
            m = s["metricas"]
            ys, ps = y[mascara], p[mascara]
            ref = metrics.threshold_metrics(ys, ps, limiar)
            assert m["pr_auc"]["valor"] == pytest.approx(metrics.pr_auc(ys, ps), abs=1e-12)
            assert m["recall"]["valor"] == pytest.approx(ref["recall"], abs=1e-12)
            assert m["precisao"]["valor"] == pytest.approx(ref["precisao"], abs=1e-12)
            rs = regra[mascara]
            assert m["regra_b2_recall"]["valor"] == pytest.approx(rs[ys == 1].mean(), abs=1e-12)
            assert m["regra_b2_precisao"]["valor"] == pytest.approx(ys[rs].mean(), abs=1e-12)
            cal = m["calibracao"]
            slope, intercepto = metrics.calibration_slope_intercept(ys, ps)
            assert cal["slope"]["valor"] == pytest.approx(slope, rel=1e-5)
            assert cal["intercepto"]["valor"] == pytest.approx(intercepto, rel=1e-5, abs=1e-7)
            assert cal["obs_esp"]["valor"] == pytest.approx(ys.sum() / ps.sum(), abs=1e-12)
            for chave in ("pr_auc", "recall", "precisao"):
                lo, hi = m[chave]["ic95"]
                assert lo <= hi
    assert com_metricas >= 15  # a maioria dos subgrupos tem métricas nesta amostra


def test_bootstrap_do_subgrupo_e_estratificado_por_alvo_dentro_do_subgrupo():
    # Em TODA reamostra, os eventos e os não eventos do subgrupo mantêm o total do subgrupo.
    df, y, p, _, regra = _dados()
    limiar = float(np.quantile(p, 0.8))
    mascara = (df["regiao"] == "Norte").to_numpy()
    ys = y[mascara]
    estado, _, meta = ta.estado_do_subgrupo(ys, p[mascara], regra[mascara], limiar, 14)
    for semente in metrics.sementes_das_reamostras(7, 6):
        w = estado.sorteio(metrics.fluxo(semente, 14), estado.pesos)
        y_cel = estado.ordenados["M1"].y
        assert w[y_cel == 1].sum() == ys.sum()
        assert w[y_cel == 0].sum() == (ys == 0).sum()
        wl = estado.sorteio_limiares(metrics.fluxo(semente, 15))
        assert wl[meta["limiares"]["y"] == 1].sum() == ys.sum()


def test_subgrupo_com_4_eventos_sai_sem_metricas_e_o_json_nao_tem_1_a_9():
    df, y, p, _, regra = _dados()
    y = y.copy()
    gest = np.flatnonzero((df["gestante"] == 1).to_numpy())
    y[gest] = 0
    y[gest[:4]] = 1  # gestantes com 4 eventos
    df = df.assign(y=y)
    df["CS_SEXO"] = df["CS_SEXO"].replace("", "I")  # sem branco: depois recria um com 4 casos
    df.loc[df.index[:4], "CS_SEXO"] = ""
    j = _subgrupos(df, y, p, regra, float(np.quantile(p, 0.8)), CFG_BASE)
    g = j["dimensoes"]["gestante"]["subgrupos"]["gestante"]
    assert g["eventos"] == "<10" and g["metricas"] is None and g["prevalencia"] is None
    assert "sem métricas" in g["motivo_sem_metricas"] and g["aviso_ic_largo"]
    branco = j["dimensoes"]["sexo"]["subgrupos"]["em branco"]
    assert branco["n"] == "<10" and branco["metricas"] is None
    assert artifacts.inteiros_pequenos(json.loads(json.dumps(j))) == []


def test_aviso_de_ic_largo_para_os_nomeados_do_spec_e_pela_regra_geral():
    for dimensao, rotulo in (("sexo", "I"), ("sexo", "em branco"), ("gestante", "gestante"),
                             ("regiao", "Norte")):
        # mesmo com muitos eventos, o do spec recebe aviso (por nome)
        assert ta.aviso_de_subgrupo(dimensao, rotulo, 5000) is not None
    assert ta.aviso_de_subgrupo("regiao", "Sul", 5000) is None  # não nomeado e com eventos de sobra
    assert "menos de 100 eventos" in ta.aviso_de_subgrupo("regiao", "Sul", 99)
    assert ta.aviso_de_subgrupo("regiao", "Sul", 100) is None
    assert ta.MIN_EVENTOS_AVISO == 100


def test_aviso_aparece_no_json_dos_subgrupos_nomeados_e_dos_com_poucos_eventos():
    df, y, p, _, regra = _dados()
    j = _subgrupos(df, y, p, regra, float(np.quantile(p, 0.8)), CFG_BASE)
    for dimensao, rotulo in ta.SUBGRUPOS_COM_AVISO_NOMEADO:
        assert j["dimensoes"][dimensao]["subgrupos"][rotulo]["aviso_ic_largo"]
    for d in j["dimensoes"].values():
        for s in d["subgrupos"].values():
            eventos = s["eventos"] if isinstance(s["eventos"], int) else 0
            if eventos < 100:
                assert s["aviso_ic_largo"]


def _separar(df, y, p, regiao="Norte"):
    """Torna o escore perfeitamente separável SÓ na região (eventos com risco alto)."""
    p = p.copy()
    m = (df["regiao"] == regiao).to_numpy()
    posicao = np.arange(m.sum())
    p[m] = np.where(y[m] == 1, 0.5 + 1e-4 * posicao, 0.01 + 1e-6 * posicao)
    return p


def test_subgrupo_separavel_devolve_indisponivel_e_nao_aborta_a_avaliacao():
    # Política provisória: reamostra sem convergência é descartada só para slope e intercepto; mais
    # de 5% descartadas -> IC indisponível; o erro de UM subgrupo nunca derruba os demais.
    df, y, p, _, regra = _dados()
    p = _separar(df, y, p)
    j = _subgrupos(df, y, p, regra, float(np.quantile(p, 0.8)), CFG_BASE, n=12)
    norte = j["dimensoes"]["regiao"]["subgrupos"]["Norte"]["metricas"]
    cal = norte["calibracao"]
    assert cal["slope"]["valor"] is None and cal["slope"]["ic95"] is None
    assert "não convergiu" in cal["slope"]["motivo"]
    assert cal["intercepto"]["ic95"] is None and "5%" in cal["intercepto"]["motivo"]
    assert cal["reamostras_descartadas"] == 12 and cal["fracao_descartada"] == 1.0
    assert norte["pr_auc"]["ic95"] is not None  # as demais métricas usam todas as reamostras
    assert norte["pr_auc"]["valor"] == pytest.approx(1.0)
    sul = j["dimensoes"]["regiao"]["subgrupos"]["Sul"]["metricas"]["calibracao"]
    assert sul["reamostras_descartadas"] == 0 and sul["slope"]["ic95"] is not None  # converge
    assert "indisponível" in j["politica_descarte"] and j["limite_descarte"] == 0.05
    assert artifacts.inteiros_pequenos(json.loads(json.dumps(j))) == []


def test_contagem_de_reamostras_de_1_a_9_sai_como_texto():
    assert ta.contagem_de_reamostras(0) == 0 and ta.contagem_de_reamostras(3) == "3"
    assert ta.contagem_de_reamostras(10) == 10


def test_subgrupos_nao_dependem_do_numero_de_processos():
    df, y, p, _, regra = _dados(n=4000)
    limiar = float(np.quantile(p, 0.8))
    um = _subgrupos(df, y, p, regra, limiar, CFG_BASE, n=6, processos=1)
    dois = _subgrupos(df, y, p, regra, limiar, CFG_BASE, n=6, processos=2)
    assert json.dumps(um, sort_keys=True) == json.dumps(dois, sort_keys=True)


def test_semente_muda_os_ics_dos_subgrupos_e_a_mesma_semente_reproduz():
    df, y, p, _, regra = _dados(n=4000)
    limiar = float(np.quantile(p, 0.8))
    a1 = _subgrupos(df, y, p, regra, limiar, CFG_BASE, n=10, seed=1)
    a2 = _subgrupos(df, y, p, regra, limiar, CFG_BASE, n=10, seed=1)
    b = _subgrupos(df, y, p, regra, limiar, CFG_BASE, n=10, seed=2)
    assert a1 == a2 and a1 != b
    outros = ta.analisar_subgrupos(df, y, p, regra, limiar, CFG_BASE, seed=1, n=10, processos=1)
    assert outros == a1


def test_subgrupos_diferentes_usam_fluxos_diferentes_da_mesma_sub_semente():
    # Dois subgrupos com os mesmos dados não repetem os mesmos números aleatórios.
    rng = np.random.default_rng(1)
    y = rng.permutation(np.array([0] * 80 + [1] * 20))
    p = np.linspace(0.01, 0.2, 100)
    regra = y == 1
    e1, _, _ = ta.estado_do_subgrupo(y, p, regra, 0.1, ta.FLUXO_SUBGRUPOS)
    e2, _, _ = ta.estado_do_subgrupo(y, p, regra, 0.1, ta.FLUXO_SUBGRUPOS + 2)
    for e in (e1, e2):
        e.pontos()
    semente = metrics.sementes_das_reamostras(3, 1)[0]
    assert e1.reamostra(semente)[0]["M1/pr_auc"] != e2.reamostra(semente)[0]["M1/pr_auc"]


def test_particoes_sexo_raca_e_regiao_tratam_branco_e_ignorado_como_categoria():
    df = _df_sintetico(n=500)
    df["CS_SEXO"] = ["F", "M", "I", "", "X"] * 100  # "X" (fora do domínio) cai em "em branco"
    df["CS_RACA"] = ["1", "9", "", "7", "4"] * 100
    particoes = ta.definir_particoes(df, CFG_BASE)
    sexo = particoes["sexo"]
    assert [sexo.rotulos[c] for c in sexo.codigos[:5]] == ["F", "M", "I", "em branco", "em branco"]
    raca = particoes["raca_cor"]
    assert [raca.rotulos[c] for c in raca.codigos[:5]] == [
        "Branca", "Ignorado/em branco", "Ignorado/em branco", "Ignorado/em branco", "Parda"]
    assert all(p.completa for p in particoes.values())


def test_regiao_sem_informacao_vira_subgrupo_proprio_e_a_particao_continua_completa():
    df = _df_sintetico(n=300)
    df["regiao"] = pd.array(df["regiao"], dtype="string")
    df.loc[df.index[:7], "regiao"] = pd.NA
    particao = ta.definir_particoes(df, CFG_BASE)["regiao"]
    assert particao.rotulos[-1] == ta.SEM_REGIAO and particao.completa
    assert (particao.codigos == len(particao.rotulos) - 1).sum() == 7


def test_rotulos_de_faixas_vem_das_bordas_do_config():
    assert ta.rotulos_de_faixas(CFG_BASE["faixas"]) == [
        "0–4", "5–14", "15–39", "40–59", "60–79", "80+"]


# --- Integração com evaluate: contrato, seleção, lacre, ensaio -------------------------------

def test_analises_padrao_na_ordem_metricas_decisao_calibracao_subgrupos_erros_criterios():
    assert [a.nome for a in ev.ANALISES_PADRAO] == ["metricas", "decisao", "calibracao",
                                                    "subgrupos", "erros", "criterios"]


def test_json_traz_as_tres_analises_novas_e_as_tabelas_viram_csv_com_hash_no_lacre(
        cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    js = _json_do_teste(cfg)["analises"]
    assert {"metricas", "decisao", "calibracao", "subgrupos"} <= set(js)
    assert len(js["decisao"]["limiares"]) == 50
    assert js["calibracao"]["reamostras"] == 2000
    assert set(js["subgrupos"]["dimensoes"]) == set(ta.DIMENSOES)
    lacre = json.loads((pasta / "LACRE.json").read_text(encoding="utf-8"))
    csvs = {"metricas__metricas.csv", "decisao__curva_decisao.csv", "calibracao__calibracao_M1.csv",
            "calibracao__calibracao_E1.csv", "subgrupos__subgrupos.csv"}
    assert csvs <= set(lacre["relatorios"])
    for nome, sha in lacre["relatorios"].items():
        assert ev._sha256_texto((pasta / nome).read_text(encoding="utf-8")) == sha
    md = (pasta / "metricas.md").read_text(encoding="utf-8")
    for titulo in ("## Curva de decisão", "## Calibração por caixas", "## Subgrupos"):
        assert titulo in md
    assert execucao.ordem[-1] == "gravado:LACRE.json"  # o lacre continua por último


def test_limiar_f2_vem_do_selecao_json_e_o_sha_vai_para_o_lacre(cfg, df, esperado):
    sel = {"conteudo": {"vencedor": "xgboost", "limiar_f2": 0.0237}, "sha256": "b" * 64,
           "caminho": "x"}
    modelos = _modelos(df)
    fontes = dataclasses.replace(_fontes(df, modelos), selecao=lambda c: sel)
    ev.evaluate_test_once(cfg, fontes=fontes)
    decisao = _json_do_teste(cfg)["analises"]["decisao"]
    f2, principal = decisao["pontos_marcados"]["M1_f2"], decisao["pontos_marcados"]["M1_principal"]
    assert f2["limiar"] == 0.0237 and decisao["limiar_f2"] == 0.0237
    assert principal["limiar"] == modelos.m1.limiar != 0.0237  # o principal é o congelado
    with guard.leitura_do_teste():
        p_m1 = modelos.m1.prever_proba(df)
    ref = metrics.net_benefit(df["y"].to_numpy(), p_m1, [0.0237])["modelo"].iloc[0]
    assert f2["nb"]["valor"] == pytest.approx(ref, abs=1e-12)
    ref_p = metrics.net_benefit(df["y"].to_numpy(), p_m1, [modelos.m1.limiar])["modelo"].iloc[0]
    assert principal["nb"]["valor"] == pytest.approx(ref_p, abs=1e-12)
    lacre = json.loads((Path(cfg["caminhos"]["relatorios"]) / "teste" / "LACRE.json")
                       .read_text(encoding="utf-8"))
    assert lacre["selecao"] == {"sha256": "b" * 64, "limiar_f2": 0.0237}
    assert decisao["selecao_sha256"] == "b" * 64


@pytest.mark.parametrize("conteudo", [
    {}, {"limiar_f2": None}, {"limiar_f2": "0.1"}, {"limiar_f2": -0.1}, {"limiar_f2": 1.5},
    {"limiar_f2": float("nan")}, {"limiar_f2": float("inf")}, {"limiar_f2": True}, [], None])
def test_selecao_sem_limiar_f2_valido_aborta_antes_de_ler_2024(cfg, df, esperado, conteudo):
    lidos = []

    def populacao(c):
        lidos.append(1)
        return df.copy()

    fontes = dataclasses.replace(
        _fontes(df), populacao=populacao,
        selecao=lambda c: {"conteudo": conteudo, "sha256": "c" * 64, "caminho": "x"})
    with pytest.raises(ValueError, match="limiar_f2"):
        ev.evaluate_test_once(cfg, fontes=fontes)
    assert lidos == []  # 2024 não foi lido
    assert not (Path(cfg["caminhos"]["relatorios"]) / "teste").exists()


def test_selecao_inexistente_aborta_antes_de_ler_2024(cfg, df, esperado):
    # Fonte real: sem <dados>/m1/selecao.json o erro vem antes da carga de 2024.
    lidos = []
    fontes = dataclasses.replace(_fontes(df), selecao=ev.carregar_selecao,
                                 populacao=lambda c: lidos.append(1) or df.copy())
    with pytest.raises(FileNotFoundError, match="selecao.json"):
        ev.evaluate_test_once(cfg, fontes=fontes)
    assert lidos == []


def test_carregar_selecao_devolve_o_sha256_dos_bytes_do_arquivo(cfg):
    import hashlib

    pasta = Path(cfg["caminhos"]["dados"]) / "m1"
    pasta.mkdir(parents=True)
    texto = json.dumps({"vencedor": "xgboost", "limiar_f2": 0.02}).encode("utf-8")
    (pasta / "selecao.json").write_bytes(texto)
    sel = ev.carregar_selecao(cfg)
    assert sel["sha256"] == hashlib.sha256(texto).hexdigest()
    assert ev.validar_limiar_f2(sel["conteudo"]) == 0.02


def test_analise_decisao_sem_selecao_no_contexto_levanta_erro(df):
    pred = ev.predizer(_modelos(df), df, dentro_do_teste=True)
    ctx = ev.Contexto(cfg=CFG_BASE, modo="teste", y=df["y"].to_numpy(), predicoes=pred, df=df,
                      seed=1, n_metricas=3)
    with pytest.raises(ValueError, match="selecao.json"):
        ev.analise_decisao(ctx)


def test_calibracao_reusa_slope_intercepto_e_obs_esp_da_analise_metricas(cfg, df, esperado):
    ev.evaluate_test_once(cfg, fontes=_fontes(df))
    js = _json_do_teste(cfg)["analises"]
    for nome in ("M1", "E1"):
        globais = js["calibracao"]["modelos"][nome]["global"]
        assert globais["slope"] == js["metricas"]["modelos"][nome]["slope"]
        assert globais["intercepto"] == js["metricas"]["modelos"][nome]["intercepto"]
        assert globais["obs_esp"] == js["metricas"]["modelos"][nome]["obs_esp"]
        assert globais["obs_esp"]["valor"] > 0


def test_obs_esp_global_bate_com_soma_dos_eventos_sobre_soma_das_probabilidades(cfg, df, esperado):
    modelos = _modelos(df)
    ev.evaluate_test_once(cfg, fontes=_fontes(df, modelos))
    obs = _json_do_teste(cfg)["analises"]["metricas"]["modelos"]["M1"]["obs_esp"]["valor"]
    with guard.leitura_do_teste():
        p = modelos.m1.prever_proba(df)
    assert obs == pytest.approx(df["y"].sum() / p.sum(), abs=1e-12)


def test_semente_do_config_chega_as_bandas_e_aos_subgrupos(cfg, df, esperado, tmp_path):
    resultados = {}
    for nome, seed in (("a1", 111), ("a2", 111), ("b", 222)):
        c = copy.deepcopy(cfg)
        c["caminhos"]["relatorios"] = str(tmp_path / nome)
        c["seed"] = seed
        ev.evaluate_test_once(c, fontes=_fontes(df))
        resultados[nome] = _json_do_teste(c)["analises"]
    for analise in ("decisao", "calibracao", "subgrupos"):
        assert resultados["a1"][analise] == resultados["a2"][analise]
        assert resultados["a1"][analise] != resultados["b"][analise]  # outra semente, outros ICs


def test_analises_novas_nao_dependem_do_numero_de_processos(cfg, df, esperado, tmp_path):
    saidas = {}
    for processos in (1, 2):
        c = copy.deepcopy(cfg)
        c["caminhos"]["relatorios"] = str(tmp_path / f"p{processos}")
        c["bootstrap"]["processos"] = processos
        ev.evaluate_test_once(c, fontes=_fontes(df))
        saidas[processos] = _json_do_teste(c)["analises"]
    assert saidas[1] == saidas[2]


def test_ensaio_roda_as_analises_novas_sem_tocar_o_teste_nem_criar_lacre(cfg):
    dev = pd.concat([_df_sintetico(n=2000, ano=2022), _df_sintetico(n=1500, seed=8, ano=2023)],
                    ignore_index=True)
    modelos = _modelos(dev)
    fontes = ev.Fontes(populacao=lambda c: dev.copy(), hash_dados=lambda c: {},
                       modelos=lambda c: modelos, features=lambda d: d, selecao=_sel_fonte)
    ev.ensaiar_em_desenvolvimento(cfg, fontes=fontes)
    base = Path(cfg["caminhos"]["relatorios"])
    assert not (base / "teste").exists()  # nada de lacre nem de relatório do teste
    js = json.loads((base / "ensaio" / "metricas.json").read_text(encoding="utf-8"))
    assert js["aviso"].startswith("ENSAIO, não é avaliação")
    assert {"metricas", "decisao", "calibracao", "subgrupos"} <= set(js["analises"])
    assert "ENSAIO, não é avaliação" in (base / "ensaio" / "metricas.md").read_text(
        encoding="utf-8")
    assert (base / "ensaio" / "subgrupos__subgrupos.csv").exists()


def test_ensaio_recusa_selecao_sem_limiar_f2(cfg):
    dev = _df_sintetico(n=300, ano=2022)
    fontes = ev.Fontes(populacao=lambda c: dev.copy(), hash_dados=lambda c: {},
                       modelos=lambda c: _modelos(dev), features=lambda d: d,
                       selecao=lambda c: {"conteudo": {}, "sha256": "d" * 64, "caminho": "x"})
    with pytest.raises(ValueError, match="limiar_f2"):
        ev.ensaiar_em_desenvolvimento(cfg, fontes=fontes)
    assert not (Path(cfg["caminhos"]["relatorios"]) / "ensaio").exists()


def test_ensaio_continua_recusando_2024_com_as_analises_novas(cfg):
    misturado = pd.concat([_df_sintetico(n=500, ano=2022), _df_sintetico(n=100, ano=2024)],
                          ignore_index=True)
    fontes = ev.Fontes(populacao=lambda c: misturado.copy(), hash_dados=lambda c: {},
                       modelos=lambda c: _modelos(misturado), features=lambda d: d,
                       selecao=_sel_fonte)
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        ev.ensaiar_em_desenvolvimento(cfg, fontes=fontes)


def test_leitura_do_teste_continua_fechada_depois_das_analises(cfg, df, esperado):
    ev.evaluate_test_once(cfg, fontes=_fontes(df))
    assert not guard.leitura_do_teste_aberta()


# --- Saída agregada (R7) e verificação (D-64) ------------------------------------------------

def test_tabela_com_inteiro_de_1_a_9_e_recusada_mas_texto_e_float_passam():
    ruim = ev.Saida({"t": pd.DataFrame({"n": [5, 20]})}, "", {})
    with pytest.raises(ValueError, match="contagem de 1 a 9"):
        ev._validar_saida("x", ruim)
    ruim_objeto = ev.Saida({"t": pd.DataFrame({"n": pd.Series([3, 40], dtype=object)})}, "", {})
    with pytest.raises(ValueError, match="contagem de 1 a 9"):
        ev._validar_saida("x", ruim_objeto)
    ok = ev.Saida({"t": pd.DataFrame({"n": ["<10", 40], "taxa": [3.0, 0.5], "ic": [[1, 2], None]})},
                  "", {})
    ev._validar_saida("x", ok)


def test_checks_da_t52_passam_na_avaliacao_sintetica_e_registram_tempos(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    checks = {c["nome"]: c for c in ev.checks_teste(cfg, execucao, esperado, ambiente=[])}
    for nome in ("curva_decisao_com_os_limiares_do_config", "curva_decisao_dentro_de_dca_min_e_max",
                 "bandas_de_calibracao_com_as_reamostras_do_config",
                 "reamostras_dos_subgrupos_do_config", "limiar_f2_lido_do_selecao_json",
                 "subgrupos_presentes_por_particao",
                 "politica_de_reamostras_descartadas_registrada",
                 "sem_contagens_de_1_a_9_nas_tabelas", "sem_contagens_de_1_a_9_no_json"):
        assert checks[nome]["passou"] is True, nome
    assert checks["curva_decisao_com_os_limiares_do_config"]["obtido"] == 50
    assert checks["bandas_de_calibracao_com_as_reamostras_do_config"]["obtido"] == 2000
    for analise in ("metricas", "decisao", "calibracao", "subgrupos"):
        assert f"tempo_analise_{analise}_s" in checks


def test_check_do_f2_reprova_se_o_json_nao_bate_com_a_selecao_lida(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    js = json.loads(execucao.json_texto)
    js["analises"]["decisao"]["limiar_f2"] = 0.5
    execucao.json_texto = json.dumps(js)
    checks = {c["nome"]: c for c in ev.checks_teste(cfg, execucao, esperado, ambiente=[])}
    assert checks["limiar_f2_lido_do_selecao_json"]["passou"] is False


def test_check_de_particao_reprova_se_uma_dimensao_some(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    js = json.loads(execucao.json_texto)
    del js["analises"]["subgrupos"]["dimensoes"]["raca_cor"]
    execucao.json_texto = json.dumps(js)
    checks = {c["nome"]: c for c in ev.checks_teste(cfg, execucao, esperado, ambiente=[])}
    assert checks["subgrupos_presentes_por_particao"]["passou"] is False


def test_check_da_curva_reprova_se_um_limiar_sai_da_faixa_do_config(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    js = json.loads(execucao.json_texto)
    js["analises"]["decisao"]["limiares"][-1] = 0.2
    execucao.json_texto = json.dumps(js)
    checks = {c["nome"]: c for c in ev.checks_teste(cfg, execucao, esperado, ambiente=[])}
    assert checks["curva_decisao_dentro_de_dca_min_e_max"]["passou"] is False


def test_gerar_verificacao_do_lacre_inclui_os_checks_da_t52_e_confere_os_csv(cfg, df, esperado):
    ev.evaluate_test_once(cfg, fontes=_fontes(df))
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    dados = json.loads(ev.gerar_verificacao_do_lacre(cfg, ambiente=[]).read_text(encoding="utf-8"))
    nomes = {c["nome"]: c for c in dados["checks"]}
    assert dados["passou"] is True and nomes["limiar_f2_lido_do_selecao_json"]["passou"] is True
    (pasta / "subgrupos__subgrupos.csv").write_text("adulterado", encoding="utf-8")
    dados = json.loads(ev.gerar_verificacao_do_lacre(cfg, ambiente=[]).read_text(encoding="utf-8"))
    assert dados["passou"] is False


# --- Fecho da T-5.2 (1): ordem de cada dimensão de subgrupos ----------------------------------

ORDEM_DOBRAS_FORA_DE_ORDEM = ["Norte", "Sul", "Sudeste", "Nordeste", "Centro-Oeste"]


def test_ordem_das_dimensoes_no_json_e_a_do_config_a_dos_rotulos_e_a_fixa_documentada():
    df, y, p, _, regra = _dados(n=3000)
    cfg = {**CFG_BASE, "faixas": [0, 10, 50], "ordem_dobras": ORDEM_DOBRAS_FORA_DE_ORDEM}
    j = _subgrupos(df, y, p, regra, float(np.quantile(p, 0.8)), cfg, n=4)
    dimensoes = j["dimensoes"]
    # região: a ordem do config (`ordem_dobras`), que NÃO é a alfabética nem a do spec
    assert dimensoes["regiao"]["ordem"] == ORDEM_DOBRAS_FORA_DE_ORDEM
    assert dimensoes["regiao"]["ordem"] != sorted(ORDEM_DOBRAS_FORA_DE_ORDEM)
    # faixas etárias: as bordas do config, em ordem crescente de idade
    assert dimensoes["faixa_etaria"]["ordem"] == ["0–9", "10–49", "50+"]
    # sexo, gestante e raça/cor: ordem fixa documentada no código
    assert dimensoes["sexo"]["ordem"] == ["F", "M", "I", "em branco"]
    assert dimensoes["gestante"]["ordem"] == ["gestante", "não gestante"]
    assert dimensoes["raca_cor"]["ordem"] == ["Branca", "Preta", "Amarela", "Parda", "Indígena",
                                              "Ignorado/em branco"]
    assert j["ordem_dimensoes"] == ["faixa_etaria", "sexo", "gestante", "regiao", "raca_cor"]
    for d in dimensoes.values():  # e cada `ordem` lista exatamente os subgrupos do bloco
        assert sorted(d["ordem"]) == sorted(d["subgrupos"])


def test_ordem_do_config_chega_ao_json_gravado_mesmo_com_as_chaves_ordenadas(cfg, df, esperado):
    cfg["ordem_dobras"] = ORDEM_DOBRAS_FORA_DE_ORDEM
    ev.evaluate_test_once(cfg, fontes=_fontes(df))
    regiao = _json_do_teste(cfg)["analises"]["subgrupos"]["dimensoes"]["regiao"]
    assert regiao["ordem"] == ORDEM_DOBRAS_FORA_DE_ORDEM
    assert list(regiao["subgrupos"]) == sorted(ORDEM_DOBRAS_FORA_DE_ORDEM)  # o dict sai ordenado


# --- Fecho da T-5.2 (2): fronteira de 5% de reamostras descartadas -----------------------------

def _dist_com_descartes(n: int, k: int) -> dict[str, np.ndarray]:
    descartada = np.zeros(n)
    descartada[:k] = 1.0
    ajustado = np.where(descartada == 1.0, np.nan, 1.0)
    return {"M1/calibracao_descartada": descartada, "M1/slope": ajustado,
            "M1/intercepto": ajustado - 1.0, "M1/obs_esp": np.ones(n)}


@pytest.mark.parametrize("n, k, ic_sai", [
    (40, 0, True),
    (40, 2, True),     # exatamente 5%: o IC SAI (limite inclusivo)
    (40, 3, False),    # logo acima (7,5%): IC indisponível
    (20, 1, True),     # exatamente 5% com outro n
    (20, 2, False),
    (20, 20, False),
])
def test_fronteira_de_5_por_cento_de_reamostras_descartadas_no_slope_e_no_intercepto(n, k, ic_sai):
    ponto = {"slope": 1.0, "intercepto": 0.0, "obs_esp": 1.0}
    cal = ta._calibracao_do_subgrupo(ponto, _dist_com_descartes(n, k), n)
    for chave in ("slope", "intercepto"):
        assert (cal[chave]["ic95"] is not None) is ic_sai, (n, k, chave)
        if not ic_sai:
            assert "5%" in cal[chave]["motivo"] and cal[chave]["valor"] is not None  # ponto fica
    assert cal["fracao_descartada"] == pytest.approx(k / n)
    assert cal["reamostras_descartadas"] == ta.contagem_de_reamostras(k)
    assert cal["obs_esp"]["ic95"] is not None  # obs/esp não depende do ajuste: sempre sai


def _forcar_falha_do_ajuste(monkeypatch, falhas: set[int]) -> None:
    """Faz `Calibracao.slope_e_intercepto` levantar RuntimeError nas chamadas de número `falhas`
    (por instância; a 1ª de cada uma é a do ponto estimado, as seguintes são as reamostras)."""
    original = metrics.Calibracao.slope_e_intercepto
    chamadas: dict[int, int] = {}

    def com_falhas(self, w, inicio=(0.0, 1.0, 0.0)):
        chamadas[id(self)] = chamadas.get(id(self), 0) + 1
        if chamadas[id(self)] in falhas:
            raise RuntimeError("falha forçada do ajuste")
        return original(self, w, inicio)

    monkeypatch.setattr(metrics.Calibracao, "slope_e_intercepto", com_falhas)


@pytest.mark.parametrize("falhas, esperado_descartadas, ic_sai", [
    ({2, 3}, "2", True),         # 2 de 40 = 5% exatos: o IC do slope e do intercepto sai
    ({2, 3, 4}, "3", False),     # 3 de 40 = 7,5%: indisponível
])
def test_fronteira_de_5_por_cento_de_ponta_a_ponta_forcando_o_ajuste_a_falhar(
        monkeypatch, falhas, esperado_descartadas, ic_sai):
    df, y, p, _, regra = _dados(n=3000)
    limiar = float(np.quantile(p, 0.8))
    base = _subgrupos(df, y, p, regra, limiar, CFG_BASE, n=40)
    _forcar_falha_do_ajuste(monkeypatch, falhas)
    j = _subgrupos(df, y, p, regra, limiar, CFG_BASE, n=40)
    visitados = 0
    for dimensao, d in j["dimensoes"].items():
        for rotulo, s in d["subgrupos"].items():
            m, m0 = s["metricas"], base["dimensoes"][dimensao]["subgrupos"][rotulo]["metricas"]
            if m is None:
                continue
            visitados += 1
            cal = m["calibracao"]
            assert cal["reamostras_descartadas"] == esperado_descartadas, (dimensao, rotulo)
            for chave in ("slope", "intercepto"):
                assert (cal[chave]["ic95"] is not None) is ic_sai, (dimensao, rotulo, chave)
                assert cal[chave]["valor"] == m0["calibracao"][chave]["valor"]  # ponto não muda
            # descarte parcial: as demais métricas continuam usando TODAS as reamostras
            for chave in ("pr_auc", "recall", "precisao", "regra_b2_recall", "regra_b2_precisao"):
                assert m[chave] == m0[chave], (dimensao, rotulo, chave)
            assert cal["obs_esp"] == m0["calibracao"]["obs_esp"]
    assert visitados >= 15
    assert artifacts.inteiros_pequenos(json.loads(json.dumps(j))) == []


# --- Escala: 5,3 milhões de linhas (fora da suíte) -------------------------------------------

@pytest.mark.skipif(os.environ.get("DENGUE_TESTES_LENTOS") != "1",
                    reason="escala de 5,3 milhões de linhas: só com DENGUE_TESTES_LENTOS=1")
def test_escala_5_milhoes_das_analises_da_t52_mede_o_tempo():
    import time

    n, eventos = 5_331_745, 11_338
    rng = np.random.default_rng(20261103)
    y = np.zeros(n, dtype=np.int64)
    y[rng.choice(n, eventos, replace=False)] = 1
    base = np.log(eventos / (n - eventos))
    p_m1 = np.clip(1 / (1 + np.exp(-(base + 0.9 * rng.standard_normal(n) + 1.0 * y))), 1e-9, 1)
    p_b1 = np.clip(1 / (1 + np.exp(-(base + 0.9 * rng.standard_normal(n) + 0.5 * y))), 1e-9, 1)
    padroes = rng.integers(0, 900, n)  # E1: um risco por padrão de covariáveis (empates)
    p_e1 = 1 / (1 + np.exp(-(base + 0.3 * rng.standard_normal(900)[padroes])))
    df = pd.DataFrame({
        "idade_anos": rng.integers(0, 95, n).astype(float),
        "CS_SEXO": rng.choice(["F", "M", "I", ""], n, p=[0.5, 0.49, 0.005, 0.005]),
        "gestante": (rng.random(n) < 0.01).astype("int8"),
        "regiao": rng.choice(REGIOES, n),
        "CS_RACA": rng.choice(["1", "2", "3", "4", "5", "9", ""], n)})
    regra = rng.random(n) < 0.12
    limiar = float(np.quantile(p_m1, 0.97))
    medidas = {}
    inicio = time.perf_counter()
    ta.curva_de_decisao(y, {"M1": p_m1, "B1": p_b1}, regra, GRADE, MARCADOS, seed=1, n=1000)
    medidas["decisao_1000_s"] = time.perf_counter() - inicio
    inicio = time.perf_counter()
    ta.calibracao_por_caixas(y, {"M1": p_m1, "E1": p_e1}, caixas=10, seed=1, n=2000)
    medidas["calibracao_2000_s"] = time.perf_counter() - inicio
    for processos in (1, 2):
        for reamostras in (2, 6):
            inicio = time.perf_counter()
            ta.analisar_subgrupos(df, y, p_m1, regra, limiar, CFG_BASE, seed=1, n=reamostras,
                                  processos=processos)
            medidas[f"subgrupos_p{processos}_n{reamostras}_s"] = time.perf_counter() - inicio
    print("\nMEDIDAS T-5.2:", json.dumps(medidas, indent=1))
