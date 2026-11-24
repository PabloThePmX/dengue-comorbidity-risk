"""Integração T-8.7 (comparar.py) com T-8.8 (comparar_graficos.py), com previsões SINTÉTICAS.

Roda o avaliador de verdade (alinhar, calcular, escrever_agregados, validar_agregados) sobre
previsões de mentira em tmp_path e gera as figuras a partir da saída real dele. Nenhum dado real
é lido, e o ano de comparação aparece só como rótulo do sintético.
"""

import copy
import json

import numpy as np
import pandas as pd
import pytest

from dengue_sinan import comparar as cmp
from dengue_sinan import comparar_graficos as cg

ANO = 2025
N = 3000
REAMOSTRAS = 20
CFG = {"seed": 20261103, "dca_limiares": {"min": 0.01, "max": 0.5, "passos": 5}}

MODELOS = [
    {"id": "m1_main", "origem": {"branch": "main"}, "treino_anos": [2022, 2023],
     "limiar": {"valor": 0.5}},
    {"id": "e1_main", "origem": {"branch": "main"}, "treino_anos": [2022, 2023], "limiar": None},
    {"id": "b0_main", "origem": {"branch": "main"}, "treino_anos": [2022, 2023],
     "limiar": {"valor": 0.15}},
    {"id": "m1_soneca", "origem": {"branch": "feat/soneca"}, "treino_anos": [2022, 2023],
     "limiar": {"valor": 0.5}},
    {"id": "m1_lora", "origem": {"branch": "feat/lora"}, "treino_anos": [2022, 2023],
     "limiar": {"valor": 0.3}},
]
CONFORMIDADE_BASE = {"r3_busca": {"com_correcao_de_desbalanceamento": False},
                     "todas_no_dicionario_do_projeto": True,
                     "anos_de_treino_dos_metadados": [2022, 2023]}


def _referencia(n: int = N) -> pd.DataFrame:
    y = (np.random.default_rng(1).random(n) < 0.2).astype(np.int64)
    return pd.DataFrame({"ANO": ANO, "LINHA": np.arange(1, n + 1, dtype=np.int64), "y": y})


def _df(ref: pd.DataFrame, p, estimavel=None) -> pd.DataFrame:
    df = pd.DataFrame({"ANO": ref["ANO"].to_numpy(), "LINHA": ref["LINHA"].to_numpy(),
                       "p": np.asarray(p, dtype=float)})
    if estimavel is not None:
        df["estimavel"] = np.asarray(estimavel, dtype=bool)
    return df


def _previsoes(ref: pd.DataFrame) -> dict[str, pd.DataFrame]:
    n = len(ref)
    y = ref["y"].to_numpy()
    estimavel = (ref["LINHA"].to_numpy() % 7) != 0  # o E1 não estima cerca de 1 em 7 casos
    p_e1 = np.where(estimavel,
                    0.05 + 0.3 * y + 0.5 * np.random.default_rng(5).random(n), np.nan)
    return {
        "m1_main": _df(ref, 0.05 + 0.3 * y + 0.5 * np.random.default_rng(3).random(n)),
        "e1_main": _df(ref, p_e1, estimavel),
        "b0_main": _df(ref, np.full(n, 0.2)),                    # B0 constante
        "m1_soneca": _df(ref, 0.1 + 0.8 * y),                    # modelo perfeito
        "m1_lora": _df(ref, np.random.default_rng(4).random(n)),  # aleatório
    }


def _pipeline(pasta, n: int = N) -> tuple[pd.DataFrame, dict]:
    """Roda o avaliador de verdade e devolve (referência, metricas.json lido do disco)."""
    ref = _referencia(n)
    alinhado = cmp.alinhar(ref, _previsoes(ref), ano=ANO)
    manifesto = {"comparacao": {"orcamentos_de_alertas": [0.05, 0.10, 0.14],
                                "bootstrap": REAMOSTRAS}, "modelos": MODELOS}
    conformidade = {m["id"]: dict(CONFORMIDADE_BASE) for m in MODELOS}
    resultado = cmp.calcular(alinhado, manifesto, CFG, conformidade, reamostras=REAMOSTRAS)
    cmp.escrever_agregados(pasta, resultado)
    dados = json.loads((pasta / "metricas.json").read_text(encoding="utf-8"))
    return ref, dados


@pytest.fixture(scope="module")
def saida_real(tmp_path_factory):
    pasta = tmp_path_factory.mktemp("comparacao")
    ref, dados = _pipeline(pasta / "reports")
    return ref, dados, pasta / "reports"


_ULTIMA_FIGURA_CAL: list = []


def _pontos_por_painel_da_calibracao(dados, monkeypatch, tmp_path) -> list[int]:
    """Gera as figuras e conta os pontos de cada painel de calibração (um por modelo, na ordem)."""
    capturadas = {}
    original = cg._salvar

    def espiar(figura, caminho):
        capturadas[caminho.name] = figura
        return original(figura, caminho)

    monkeypatch.setattr(cg, "_salvar", espiar)
    cg.gerar_graficos(dados, tmp_path / "figuras")
    eixos = capturadas[cg.ARQ_CALIBRACAO].axes
    _ULTIMA_FIGURA_CAL[:] = [capturadas[cg.ARQ_CALIBRACAO]]
    return [sum(len(ln.get_xdata()) for ln in eixos[i].get_lines() if ln.get_linestyle() == "None")
            for i in range(len(dados["modelos"]))]


def test_json_do_comparar_entra_no_validador_do_desenho(saida_real):
    _, dados, _ = saida_real
    cg.validar(dados)  # não levanta: o formato do comparar é o do contrato


def test_figuras_saem_da_saida_real_do_comparar_sem_quebrar(saida_real, tmp_path):
    _, dados, _ = saida_real
    caminhos = cg.gerar_graficos(dados, tmp_path / "figuras")
    assert [c.name for c in caminhos] == list(cg.FIGURAS)
    for c in caminhos:
        assert c.read_bytes().startswith(b"\x89PNG") and c.stat().st_size > 5_000, c.name


def test_populacao_principal_e_o_subconjunto_que_o_e1_estima(saida_real):
    ref, dados, _ = saida_real
    estimavel = (ref["LINHA"].to_numpy() % 7) != 0
    principal = dados["populacoes"]["principal"]
    assert principal["casos"] == int(estimavel.sum())
    assert principal["eventos"] == int(ref["y"].to_numpy()[estimavel].sum())
    assert dados["populacoes"]["completa"]["casos"] == N


def test_diferenca_e_modelo_menos_m1_e_leitura_segue_o_ic(saida_real):
    _, dados, _ = saida_real
    pr = dados["metricas"]["principal"]
    difs = dados["diferencas_pr_auc_vs_referencia"]["principal"]
    assert difs["m1_main"] is None  # a referência não se compara com ela mesma
    for m, dif in difs.items():
        if dif is None:
            continue
        esperado = pr[m]["pr_auc"]["valor"] - pr["m1_main"]["pr_auc"]["valor"]
        assert dif["valor"] == pytest.approx(esperado, abs=1e-9), m
    assert difs["m1_soneca"]["leitura"] == "melhor"  # o perfeito supera o M1 com IC > 0


def test_b0_constante_tem_pr_auc_igual_a_prevalencia(saida_real):
    _, dados, _ = saida_real
    prevalencia = dados["populacoes"]["principal"]["prevalencia"]
    assert dados["metricas"]["principal"]["b0_main"]["pr_auc"]["valor"] == pytest.approx(
        prevalencia, abs=1e-9)


def test_caixa_com_casos_e_sem_taxa_da_saida_real_nao_vira_ponto(saida_real, monkeypatch,
                                                                  tmp_path):
    _, dados, _ = saida_real
    sem_taxa = [c for m in dados["modelos"] for c in (dados["calibracao"][m] or [])
                if c["casos"] != "<10" and c["observado"] is None]
    assert sem_taxa, "o cenário não produziu caixa com casos numéricos e taxa suprimida"
    pontos = _pontos_por_painel_da_calibracao(dados, monkeypatch, tmp_path)
    esperado = [len(cg._caixas_publicaveis(dados["calibracao"][m])) for m in dados["modelos"]]
    assert pontos == esperado
    total = sum(len(dados["calibracao"][m] or []) for m in dados["modelos"])
    texto = " ".join(" ".join(x.get_text() for x in _ULTIMA_FIGURA_CAL[0].texts).split())
    trecho = f"sem ponto (taxa suprimida pelo R7 ou zero): {total - sum(esperado)} de {total}"
    assert trecho in texto


def test_caixa_suprimida_R7_no_formato_do_comparar_nao_vira_ponto(saida_real, monkeypatch,
                                                                    tmp_path):
    """A forma "<10" que o comparar grava (interfaces.md, Convenções).

    Achado: com caixas por quantis, o comparar não produz caixa com menos de 10 casos em população
    válida (o R7 dos alertas recusa antes). Então a forma é testada trocando uma caixa da saída
    real pela forma suprimida, que o comparar também aceita."""
    _, dados, _ = saida_real
    real = copy.deepcopy(dados)
    real["calibracao"]["m1_main"][0] = {"previsto": None, "observado": None, "ic95": None,
                                        "casos": "<10"}
    cmp.validar_agregados(real)  # o comparar aceita a forma suprimida
    cg.validar(real)             # e o desenho também
    pontos = _pontos_por_painel_da_calibracao(real, monkeypatch, tmp_path)
    esperado = [len(cg._caixas_publicaveis(real["calibracao"][m])) for m in real["modelos"]]
    assert pontos == esperado
    assert pontos[0] < len(real["calibracao"]["m1_main"])  # a suprimida ficou de fora


def test_conformidade_e_externo_chegam_ao_desenho(saida_real):
    _, dados, _ = saida_real
    assert dados["conformidade"]["m1_soneca"]["externo"] is True
    assert dados["conformidade"]["m1_main"]["externo"] is False
