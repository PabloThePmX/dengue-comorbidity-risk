"""Testes do avaliador comparativo (T-8.7, D-97, D-99, contrato "Comparação em 2025").

Dados SINTÉTICOS com respostas conhecidas e amostras pequenas (a suíte já é lenta). Nenhum teste lê
dado real: o único arquivo lido é um parquet criado em `tmp_path`.
"""

import ast
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import average_precision_score

from dengue_sinan import comparar as cmp

ANO = 2025
N = 2000
CFG = {"seed": 20261103, "dca_limiares": {"min": 0.01, "max": 0.5, "passos": 5}}
REAMOSTRAS = 20
ORIGEM_MODULO = Path(cmp.__file__)


# --- Dados sintéticos -----------------------------------------------------------------------

def _referencia(n: int = N, prevalencia: float = 0.2, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    y = (rng.random(n) < prevalencia).astype(np.int64)
    return pd.DataFrame({"ANO": ANO, "LINHA": np.arange(1, n + 1, dtype=np.int64), "y": y})


def _previsoes(ref: pd.DataFrame, p, estimavel=None) -> pd.DataFrame:
    df = pd.DataFrame({"ANO": ref["ANO"].to_numpy(), "LINHA": ref["LINHA"].to_numpy(),
                       "p": np.asarray(p, dtype=float)})
    if estimavel is not None:
        df["estimavel"] = np.asarray(estimavel, dtype=bool)
    return df


def _perfeito(ref: pd.DataFrame) -> np.ndarray:
    """Separa perfeitamente os casos (PR-AUC 1)."""
    return 0.1 + 0.8 * ref["y"].to_numpy()


def _razoavel(ref: pd.DataFrame, seed: int = 3) -> np.ndarray:
    """Classes sobrepostas: PR-AUC bem acima da prevalência e abaixo de 1."""
    u = np.random.default_rng(seed).random(len(ref))
    return 0.05 + 0.3 * ref["y"].to_numpy() + 0.5 * u


def _aleatorio(ref: pd.DataFrame, seed: int = 4) -> np.ndarray:
    return np.random.default_rng(seed).random(len(ref))


def _conjunto(ref: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Quatro modelos: M1 razoável, E1 (todos estimáveis), B0 constante e a lora aleatória."""
    return {
        "m1_main": _previsoes(ref, _razoavel(ref)),
        "e1_main": _previsoes(ref, _razoavel(ref, seed=5), estimavel=np.ones(len(ref), bool)),
        "b0_main": _previsoes(ref, np.full(len(ref), 0.2)),
        "m1_lora": _previsoes(ref, _aleatorio(ref)),
    }


def _manifesto(bootstrap: int = REAMOSTRAS) -> dict:
    """Mínimo do manifesto que o avaliador usa: modelos, origem, limiar e comparação."""
    return {
        "comparacao": {"orcamentos_de_alertas": [0.05, 0.10, 0.14], "bootstrap": bootstrap},
        "modelos": [
            {"id": "m1_main", "origem": {"branch": "main"}, "treino_anos": [2022, 2023],
             "limiar": {"valor": 0.5}},
            {"id": "e1_main", "origem": {"branch": "main"}, "treino_anos": [2022, 2023],
             "limiar": None},
            {"id": "b0_main", "origem": {"branch": "main"}, "treino_anos": [2022, 2023],
             "limiar": {"valor": 0.15}},
            {"id": "m1_lora", "origem": {"branch": "feat/lora"}, "treino_anos": [2022, 2023],
             "limiar": {"valor": 0.3}},
        ],
    }


def _conformidade_ok() -> dict[str, dict]:
    """Conformidade no formato que o avaliador recebe (mapeada pelo `conformidade_do_modelo`)."""
    base = {"r3_busca": {"com_correcao_de_desbalanceamento": False},
            "todas_no_dicionario_do_projeto": True,
            "anos_de_treino_dos_metadados": [2022, 2023]}
    return {modelo: dict(base) for modelo in ("m1_main", "e1_main", "b0_main", "m1_lora")}


def _calcular(prev: dict[str, pd.DataFrame], ref: pd.DataFrame, **kw) -> dict:
    alinhado = cmp.alinhar(ref, prev, ano=ANO)
    return cmp.calcular(alinhado, _manifesto(), CFG, _conformidade_ok(),
                        reamostras=kw.pop("reamostras", REAMOSTRAS), **kw)


# --- Alinhamento: recusas ---------------------------------------------------------------------

def test_linha_faltando_recusa():
    ref = _referencia()
    prev = _conjunto(ref)
    prev["m1_lora"] = prev["m1_lora"].iloc[1:]
    with pytest.raises(ValueError, match="faltam 1 linha"):
        cmp.alinhar(ref, prev, ano=ANO)


def test_linha_duplicada_recusa():
    ref = _referencia()
    prev = _conjunto(ref)
    prev["m1_main"] = pd.concat([prev["m1_main"], prev["m1_main"].iloc[:1]], ignore_index=True)
    with pytest.raises(ValueError, match="repetido"):
        cmp.alinhar(ref, prev, ano=ANO)


def test_ano_errado_recusa():
    ref = _referencia()
    prev = _conjunto(ref)
    prev["m1_main"]["ANO"] = 2024
    with pytest.raises(ValueError, match="ano diferente"):
        cmp.alinhar(ref, prev, ano=ANO)


@pytest.mark.parametrize("valor", [-0.01, 1.2])
def test_p_fora_de_zero_um_recusa(valor):
    ref = _referencia()
    prev = _conjunto(ref)
    prev["m1_main"].loc[5, "p"] = valor
    with pytest.raises(ValueError, match=r"fora de \[0, 1\]"):
        cmp.alinhar(ref, prev, ano=ANO)


def test_nan_fora_de_nao_estimavel_recusa():
    """Para o E1, NaN é permitido só onde estimavel = false (D-99)."""
    ref = _referencia()
    prev = _conjunto(ref)
    prev["m1_main"].loc[3, "p"] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        cmp.alinhar(ref, prev, ano=ANO)
    prev = _conjunto(ref)
    prev["e1_main"].loc[7, "p"] = np.nan  # estimavel = true e p NaN: também recusa
    with pytest.raises(ValueError, match="estimavel"):
        cmp.alinhar(ref, prev, ano=ANO)


def test_e1_sem_estimavel_nao_alinha():
    ref = _referencia()
    prev = _conjunto(ref)
    prev["e1_main"] = prev["e1_main"].drop(columns=["estimavel"])
    with pytest.raises(ValueError, match="estimavel"):
        cmp.alinhar(ref, prev, ano=ANO)


def test_carregar_previsoes_le_parquet_e_recusa_coluna_faltando(tmp_path):
    ref = _referencia(n=50)
    df = _previsoes(ref, _razoavel(ref))
    caminho = tmp_path / "p_m1_main_2025.parquet"
    df.to_parquet(caminho, index=False)
    lido = cmp.carregar_previsoes(caminho)
    assert list(lido.columns) == ["ANO", "LINHA", "p"]
    assert len(lido) == 50
    df.drop(columns=["p"]).to_parquet(tmp_path / "ruim.parquet", index=False)
    with pytest.raises(ValueError, match="colunas"):
        cmp.carregar_previsoes(tmp_path / "ruim.parquet")


# --- Métricas e populações --------------------------------------------------------------------

def test_modelo_perfeito_tem_pr_auc_um():
    ref = _referencia()
    prev = _conjunto(ref)
    prev["m1_main"] = _previsoes(ref, _perfeito(ref))
    res = _calcular(prev, ref)
    bloco = res["metricas"]["principal"]["m1_main"]["pr_auc"]
    assert bloco["valor"] == pytest.approx(1.0)
    assert bloco["ic95"] == pytest.approx([1.0, 1.0])
    # separação perfeita: o ajuste do slope não converge e sai como indisponível, sem derrubar
    assert res["metricas"]["principal"]["m1_main"]["calibration_slope"]["valor"] is None


def test_modelo_aleatorio_pr_auc_perto_da_prevalencia():
    ref = _referencia(n=6000, prevalencia=0.2)
    prev = _conjunto(ref)
    prev["m1_main"] = _previsoes(ref, _aleatorio(ref, seed=9))
    res = _calcular(prev, ref)
    prevalencia = float(ref["y"].mean())
    valor = res["metricas"]["principal"]["m1_main"]["pr_auc"]["valor"]
    assert valor == pytest.approx(prevalencia, abs=0.03)


def test_empate_entre_dois_modelos_sem_diferenca_detectavel():
    ref = _referencia()
    prev = _conjunto(ref)
    prev["m1_lora"] = _previsoes(ref, _razoavel(ref))  # idêntico ao M1
    res = _calcular(prev, ref)
    dif = res["diferencas_pr_auc_vs_referencia"]["principal"]["m1_lora"]
    assert dif["valor"] == pytest.approx(0.0)
    assert dif["leitura"] == "sem diferença detectável"


def test_modelo_claramente_pior_recebe_leitura_pior():
    ref = _referencia()
    prev = _conjunto(ref)
    prev["m1_main"] = _previsoes(ref, _perfeito(ref))
    prev["m1_lora"] = _previsoes(ref, _aleatorio(ref))
    res = _calcular(prev, ref)
    dif = res["diferencas_pr_auc_vs_referencia"]["principal"]["m1_lora"]
    assert dif["valor"] < 0
    assert dif["leitura"] == "pior"
    assert dif["ic95"][1] < 0


def test_referencia_nao_se_compara_com_ela_mesma():
    ref = _referencia()
    res = _calcular(_conjunto(ref), ref)
    assert res["diferencas_pr_auc_vs_referencia"]["principal"]["m1_main"] is None


def test_e1_fora_da_principal_e_principal_igual_para_todos():
    ref = _referencia()
    prev = _conjunto(ref)
    estimavel = np.ones(N, dtype=bool)
    estimavel[:100] = False  # 100 casos que o E1 não estima
    prev["e1_main"] = _previsoes(ref, np.where(estimavel, _razoavel(ref, seed=5), np.nan),
                                 estimavel=estimavel)
    res = _calcular(prev, ref)
    principal = res["populacoes"]["principal"]
    assert principal["casos"] == N - 100
    assert principal["eventos"] == int(ref["y"].to_numpy()[estimavel].sum())
    # a principal é o subconjunto do E1 para TODOS: o PR-AUC do M1 é o do subconjunto
    esperado = average_precision_score(ref["y"].to_numpy()[estimavel],
                                       prev["m1_main"]["p"].to_numpy()[estimavel])
    obtido = res["metricas"]["principal"]["m1_main"]["pr_auc"]["valor"]
    assert obtido == pytest.approx(esperado)
    # na população completa o E1 não estima: null em todas as métricas dele
    completa = res["metricas"]["completa"]["e1_main"]
    assert all(v is None for v in completa.values())
    assert res["orcamentos"]["completa"]["e1_main"] is None
    assert res["diferencas_pr_auc_vs_referencia"]["completa"]["e1_main"] is None
    assert res["metricas"]["completa"]["m1_main"]["pr_auc"]["valor"] is not None


# --- Orçamento de alertas e empates ----------------------------------------------------------

def test_k_do_orcamento_arredonda_pelo_mais_proximo():
    assert cmp.k_do_orcamento(0.05, 2000) == 100
    assert cmp.k_do_orcamento(0.14, 2000) == 280
    with pytest.raises(ValueError):
        cmp.k_do_orcamento(0.05, 5)  # zero alertas não tem recall definido


def test_empate_de_p_no_orcamento_desempata_por_linha():
    p = np.array([0.5, 0.5, 0.5, 0.1])
    linha = np.array([30, 10, 20, 40])
    marcados = cmp.marcar_orcamento(p, linha, 2)
    # os dois de maior p com menor LINHA entre os empatados (10 e 20), não a ordem do arquivo
    assert marcados.tolist() == [False, True, True, False]


def test_orcamento_empate_e_determinismo():
    ref = _referencia()
    prev = _conjunto(ref)
    res1 = _calcular(prev, ref)
    res2 = _calcular(prev, ref)
    # B0 é constante: todos empatam; o orçamento marca exatamente k casos
    assert res1["orcamentos"]["principal"]["b0_main"]["0.05"]["alertas"] == 100
    assert json.dumps(res1["orcamentos"], sort_keys=True) == json.dumps(
        res2["orcamentos"], sort_keys=True)


def test_limiar_proprio_so_para_quem_tem_limiar():
    ref = _referencia()
    res = _calcular(_conjunto(ref), ref)
    assert res["no_limiar_proprio"]["e1_main"] is None
    bloco = res["no_limiar_proprio"]["m1_main"]
    assert bloco["limiar"] == pytest.approx(0.5)
    assert bloco["alertas"] == int((_conjunto(ref)["m1_main"]["p"] >= 0.5).sum())
    assert bloco["recall"]["ic95"] is not None


# --- Calibração, R7 e curva de decisão -----------------------------------------------------

def test_r7_suprime_taxa_de_caixa_com_menos_de_dez_eventos():
    ref = _referencia(prevalencia=0.002)  # ~4 eventos no total: toda caixa tem < 10
    res = _calcular(_conjunto(ref), ref)
    for caixa in res["calibracao"]["m1_main"]:
        assert caixa["observado"] is None
        assert caixa["ic95"] is None


def test_caixa_r7_formas():
    suprimida = cmp._caixa_r7(casos=5, eventos=1, previsto=0.3, dist=np.array([0.1, 0.2]))
    assert suprimida == {"previsto": None, "observado": None, "ic95": None, "casos": "<10"}
    poucos = cmp._caixa_r7(casos=50, eventos=3, previsto=0.02, dist=np.array([0.01, 0.05]))
    assert poucos["observado"] is None and poucos["casos"] == 50
    normal = cmp._caixa_r7(casos=50, eventos=20, previsto=0.4, dist=np.array([0.3, 0.5]))
    assert normal["observado"] == pytest.approx(0.4)
    assert normal["ic95"][0] <= 0.4 <= normal["ic95"][1]


def test_curva_de_decisao_tem_um_valor_por_limiar_e_modelo():
    ref = _referencia()
    res = _calcular(_conjunto(ref), ref)
    curva = res["curva_decisao"]
    assert len(curva["limiares"]) == 5
    for modelo in ("m1_main", "e1_main", "b0_main", "m1_lora"):
        assert len(curva[modelo]) == 5
        assert all(np.isfinite(curva[modelo]))


# --- Reprodutibilidade e formato --------------------------------------------------------------

def test_mesma_semente_mesmo_resultado():
    ref = _referencia()
    prev = _conjunto(ref)
    a = _calcular(prev, ref)
    b = _calcular(prev, ref)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
    assert a["semente"] == CFG["seed"]
    assert a["reamostras"] == REAMOSTRAS


def test_escrever_gera_json_e_md_que_o_validador_aceita(tmp_path):
    ref = _referencia()
    res = _calcular(_conjunto(ref), ref)
    arquivos = cmp.escrever_agregados(tmp_path, res)
    nomes = {p.name for p in arquivos}
    assert {"metricas.json", "metricas.md", "diferencas.md", "orcamentos.md",
            "conformidade.md"} <= nomes
    lido = json.loads((tmp_path / "metricas.json").read_text(encoding="utf-8"))
    cmp.validar_agregados(lido)  # não levanta
    assert lido == json.loads(json.dumps(res))
    assert "PR-AUC" in (tmp_path / "metricas.md").read_text(encoding="utf-8")


def _valido() -> dict:
    ref = _referencia()
    return json.loads(json.dumps(_calcular(_conjunto(ref), ref)))


@pytest.mark.parametrize("mutacao", [
    lambda d: d.pop("curva_decisao"),                       # chave faltando
    lambda d: d.__setitem__("extra", 1),                    # chave a mais
    lambda d: d["diferencas_pr_auc_vs_referencia"]["principal"]["m1_lora"].__setitem__(
        "leitura", "talvez"),                               # leitura fora da lista
    lambda d: d.__setitem__("modelo_de_referencia", "x"),   # referência que não está no conjunto
    lambda d: d["diferencas_pr_auc_vs_referencia"]["principal"].__setitem__(
        "m1_main", {"valor": 0.0, "ic95": [0.0, 0.0], "leitura": "sem diferença detectável"}),
    lambda d: d["metricas"]["principal"]["m1_main"]["pr_auc"].__setitem__("ic95", [0.9, 0.1]),
    lambda d: d["metricas"]["principal"]["m1_main"].pop("brier"),
    lambda d: d["populacoes"]["principal"].__setitem__("eventos", 5),       # R7: célula < 10
    lambda d: d["orcamentos"]["principal"]["m1_main"]["0.05"].__setitem__("alertas", 7),
    lambda d: d["calibracao"]["m1_main"].append(
        {"previsto": 0.1, "observado": 0.5, "ic95": None, "casos": "<10"}),  # R7 contrária
    lambda d: d["calibracao"]["m1_main"][0].__setitem__("casos", 3),        # R7: 1 a 9 casos
    lambda d: d["conformidade"]["m1_main"].__setitem__("r3_sem_correcao", "sim"),
    lambda d: d.__setitem__("ano", "2025"),
])
def test_validar_recusa_fora_do_formato(mutacao):
    dados = _valido()
    mutacao(dados)
    with pytest.raises(ValueError):
        cmp.validar_agregados(dados)


def test_validar_aceita_bloco_de_slope_indisponivel():
    dados = _valido()
    dados["metricas"]["principal"]["m1_main"]["calibration_slope"] = {"valor": None,
                                                                       "ic95": None}
    cmp.validar_agregados(dados)


def test_calcular_recusa_modelo_sem_previsao():
    ref = _referencia()
    prev = _conjunto(ref)
    alinhado = cmp.alinhar(ref, prev, ano=ANO)
    manifesto = _manifesto()
    manifesto["modelos"].append({"id": "m1_soneca", "origem": {"branch": "feat/soneca"},
                                 "treino_anos": [2022, 2023], "limiar": None})
    with pytest.raises(ValueError, match="m1_soneca"):
        cmp.calcular(alinhado, manifesto, CFG, _conformidade_ok(), reamostras=REAMOSTRAS)


# --- Conformidade (mapeamento dos JSON dos scripts) ----------------------------------------

def test_conformidade_forma_do_projeto():
    conf = {"r3_busca": {"aplicavel": True, "com_correcao_de_desbalanceamento": False},
            "todas_no_dicionario_do_projeto": True,
            "anos_de_treino_dos_metadados": [2022, 2023],
            "ano_de_comparacao_fora_do_treino": True}
    modelo = {"id": "m1_main", "origem": {"branch": "main"}, "treino_anos": [2022, 2023]}
    assert cmp.conformidade_do_modelo(conf, modelo, ANO) == {
        "r3_sem_correcao": True, "r4_variaveis_no_dicionario": True,
        "treino_sem_ano_de_comparacao": True, "versoes_diferentes_do_treino": None,
        "externo": False}


def test_conformidade_forma_da_lora_com_versoes_diferentes():
    conf = {"r3_busca": {"com_correcao_de_desbalanceamento": False},
            "todas_no_dicionario_do_projeto": True,
            "versoes_do_ambiente": {"python": "3.13.1", "pandas": "3.1.1"},
            "metadados_da_branch": {"anos_de_treino_config": [2022, 2023],
                                    "versoes_de_treino": {"python": "3.13.1",
                                                          "pandas": "2.2.0"}}}
    modelo = {"id": "m1_lora", "origem": {"branch": "feat/lora"}, "treino_anos": [2022, 2023]}
    res = cmp.conformidade_do_modelo(conf, modelo, ANO)
    assert res["versoes_diferentes_do_treino"] is True
    assert res["externo"] is True
    assert res["treino_sem_ano_de_comparacao"] is True


def test_conformidade_recusa_chave_faltando_e_marca_r3():
    modelo = {"id": "m1_soneca", "origem": {"branch": "feat/soneca"}, "treino_anos": [2022, 2023]}
    with pytest.raises(ValueError, match="todas_no_dicionario_do_projeto"):
        cmp.conformidade_do_modelo({"r3_busca": {}}, modelo, ANO)
    conf = {"r3_busca": {"com_correcao_de_desbalanceamento": True},
            "todas_no_dicionario_do_projeto": True,
            "anos_na_assinatura_dos_dados": [2022, 2025]}
    res = cmp.conformidade_do_modelo(conf, modelo, ANO)
    assert res["r3_sem_correcao"] is False
    assert res["treino_sem_ano_de_comparacao"] is False


# --- Caso pequeno calculado à mão (n = 20, 5 eventos) -------------------------------------------
#
# Linhas 1..20. Eventos (y = 1): L1, L3, L5, L8, L15. p por linha:
#   0,9: L1 (evento), L2       empate: o desempate por LINHA põe L1 antes
#   0,8: L3 (evento)
#   0,7: L4, L5 (evento)       empate
#   0,6: L6
#   0,5: L7, L8 (evento)       empate
#   0,4: L9      0,3: L10      0,15: L15 (evento)      0,1: L11..L14, L16..L20
# Orçamentos: k = round(X · 20): 5% -> 1; 10% -> 2; 14% -> 3.
# Ordem por (-p, LINHA): L1, L2, L3, L4, L5, ...
#   k=1: {L1} -> VP 1 -> recall 1/5 = 0,2; precisão 1/1 = 1,0
#   k=2: {L1, L2} -> VP 1 -> recall 0,2; precisão 1/2 = 0,5
#   k=3: {L1, L2, L3} -> VP 2 -> recall 2/5 = 0,4; precisão 2/3
# Limiar próprio 0,7: p >= 0,7 são L1..L5 -> 5 alertas, VP 3 (L1, L3, L5): recall 3/5, precisão 3/5.
# ROC-AUC: 5 eventos x 15 não eventos = 75 pares. Para cada evento, os não eventos abaixo dele
#   (empate conta 0,5): L1 14,5; L3 14; L5 13,5; L8 11,5; L15 9. Soma 62,5 -> 62,5 / 75.
# Brier: soma de (p - y)^2 = 1,1125 (eventos) + 2,25 (não eventos) = 3,3625 -> / 20 = 0,168125.
# Observado/esperado: 5 eventos / Σp (7,35) = 5 / 7,35.
# Curva de decisão em t = 0,3: p >= 0,3 são L1..L10 -> VP 4 (L1, L3, L5, L8), FP 6.
#   NB = 4/20 - (6/20) · (0,3 / 0,7) = 0,2 - 0,128571 = 1/14 = 0,0714286.

HAND_LINHA = np.arange(1, 21, dtype=np.int64)
HAND_P_POR_LINHA = {1: 0.9, 2: 0.9, 3: 0.8, 4: 0.7, 5: 0.7, 6: 0.6, 7: 0.5, 8: 0.5, 9: 0.4,
                    10: 0.3, 15: 0.15}
HAND_EVENTOS = {1, 3, 5, 8, 15}
HAND_P = np.array([HAND_P_POR_LINHA.get(int(v), 0.1) for v in HAND_LINHA])
HAND_Y = np.array([1 if int(v) in HAND_EVENTOS else 0 for v in HAND_LINHA], dtype=np.int64)


def _previsao_invertida(p, **extra) -> pd.DataFrame:
    """Previsões em ordem INVERTIDA: o alinhamento tem de juntar pela chave, não pela posição."""
    df = pd.DataFrame({"ANO": ANO, "LINHA": HAND_LINHA, "p": p})
    for chave, valor in extra.items():
        df[chave] = valor
    return df.iloc[::-1].reset_index(drop=True)


def _calcular_a_mao() -> dict:
    ref = pd.DataFrame({"ANO": ANO, "LINHA": HAND_LINHA, "y": HAND_Y})
    prev = {
        "m1_main": _previsao_invertida(HAND_P),
        "e1_main": _previsao_invertida(HAND_P, estimavel=np.ones(20, dtype=bool)),
        "b0_main": _previsao_invertida(np.full(20, 0.25)),
        "m1_lora": _previsao_invertida(np.full(20, 0.05)),
    }
    manifesto = _manifesto()
    manifesto["modelos"][0]["limiar"] = {"valor": 0.7}
    manifesto["modelos"][2]["limiar"] = {"valor": 0.15}
    # grade 0,3 / 0,6 / 0,9: começa exatamente em 0,3 (linspace de 0,1 a 0,9 daria
    # 0,30000000000000004 e L10, com p = 0,3, sairia do "p >= t")
    cfg = {"seed": 1, "dca_limiares": {"min": 0.3, "max": 0.9, "passos": 3}}
    alinhado = cmp.alinhar(ref, prev, ano=ANO)
    return cmp.calcular(alinhado, manifesto, cfg, _conformidade_ok(), reamostras=5)


def test_caso_a_mao_recall_e_precisao_nos_orcamentos_com_empates():
    orc = _calcular_a_mao()["orcamentos"]["principal"]["m1_main"]
    assert orc["0.05"]["alertas"] == 1
    assert orc["0.05"]["recall"]["valor"] == pytest.approx(1 / 5)
    assert orc["0.05"]["precisao"]["valor"] == pytest.approx(1.0)
    assert orc["0.10"]["alertas"] == 2
    assert orc["0.10"]["recall"]["valor"] == pytest.approx(1 / 5)
    assert orc["0.10"]["precisao"]["valor"] == pytest.approx(1 / 2)
    assert orc["0.14"]["alertas"] == 3
    assert orc["0.14"]["recall"]["valor"] == pytest.approx(2 / 5)
    assert orc["0.14"]["precisao"]["valor"] == pytest.approx(2 / 3)


def test_caso_a_mao_limiar_proprio():
    lim = _calcular_a_mao()["no_limiar_proprio"]["m1_main"]
    assert lim["limiar"] == pytest.approx(0.7)
    assert lim["alertas"] == 5
    assert lim["recall"]["valor"] == pytest.approx(3 / 5)
    assert lim["precisao"]["valor"] == pytest.approx(3 / 5)


def test_caso_a_mao_roc_brier_obs_esp_e_net_benefit():
    from sklearn.metrics import brier_score_loss, roc_auc_score

    res = _calcular_a_mao()
    met = res["metricas"]["principal"]["m1_main"]
    assert met["roc_auc"]["valor"] == pytest.approx(62.5 / 75)
    assert met["brier"]["valor"] == pytest.approx(3.3625 / 20)
    assert met["obs_esp"]["valor"] == pytest.approx(5 / 7.35)
    # conferência independente (sklearn) das mesmas contas
    assert met["roc_auc"]["valor"] == pytest.approx(roc_auc_score(HAND_Y, HAND_P))
    assert met["brier"]["valor"] == pytest.approx(brier_score_loss(HAND_Y, HAND_P))
    limiares = np.array(res["curva_decisao"]["limiares"])
    assert limiares[0] == 0.3
    assert res["curva_decisao"]["m1_main"][0] == pytest.approx(1 / 14)


def test_caso_a_mao_populacao_e_prevalencia():
    pop = _calcular_a_mao()["populacoes"]["principal"]
    assert pop["casos"] == 20
    assert pop["eventos"] == 5
    assert pop["prevalencia"] == pytest.approx(0.25)


def test_calcular_recusa_ano_diferente_do_esperado():
    ref = _referencia()
    alinhado = cmp.alinhar(ref, _conjunto(ref), ano=ANO)
    with pytest.raises(ValueError, match="ano de comparação"):
        cmp.calcular(alinhado, _manifesto(), CFG, _conformidade_ok(), reamostras=5,
                     ano_esperado=2024)
    cmp.calcular(alinhado, _manifesto(), CFG, _conformidade_ok(), reamostras=5,
                 ano_esperado=ANO)


# --- Validação: leitura coerente com o IC e R7 nos gráficos -------------------------------------

@pytest.mark.parametrize("leitura, ic", [
    ("melhor", [-0.1, 0.2]),                    # IC cruza 0: não pode ser "melhor"
    ("pior", [-0.2, 0.1]),                      # IC cruza 0: não pode ser "pior"
    ("sem diferença detectável", [0.1, 0.2]),   # IC acima de 0: é "melhor"
    ("melhor", [-0.5, -0.1]),                   # IC abaixo de 0: é "pior"
])
def test_validar_recusa_leitura_que_nao_bate_com_o_ic(leitura, ic):
    dados = _valido()
    bloco = dados["diferencas_pr_auc_vs_referencia"]["principal"]["m1_lora"]
    bloco.update({"valor": sum(ic) / 2, "ic95": ic, "leitura": leitura})
    with pytest.raises(ValueError, match="não bate"):
        cmp.validar_agregados(dados)


def test_validar_aceita_leitura_coerente_com_o_ic():
    dados = _valido()
    bloco = dados["diferencas_pr_auc_vs_referencia"]["principal"]["m1_lora"]
    bloco.update({"valor": 0.1, "ic95": [0.05, 0.2], "leitura": "melhor"})
    cmp.validar_agregados(dados)


def test_graficos_recusa_alertas_de_1_a_9_e_aceita_zero_ou_dez():
    from dengue_sinan import comparar_graficos as cg

    dados = _valido()
    cg.validar(dados)
    dados["orcamentos"]["principal"]["m1_main"]["0.05"]["alertas"] = 7
    with pytest.raises(ValueError, match="R7"):
        cg.validar(dados)
    dados["orcamentos"]["principal"]["m1_main"]["0.05"]["alertas"] = 10
    cg.validar(dados)


# --- Isolamento: o módulo só importa o que pode e não lê dados ----------------------------------

ALLOWED_DENGUE = {"metrics", "teste_analises", "comparacao_manifesto", "comparar"}
PROIBIDOS_TERCEIROS = ("xgboost", "lightgbm", "catboost", "torch", "sklearn.pipeline")
LEITORES = {"read_parquet", "read_csv", "read_pickle", "read_table", "read_feather", "read_excel"}


def _violacoes(caminho) -> list[str]:
    """Lista o que o módulo em `caminho` não pode ter (lista vazia = aprovado)."""
    arvore = ast.parse(Path(caminho).read_text(encoding="utf-8"))
    achados: list[str] = []

    def proibido_terceiro(nome: str) -> bool:
        return any(nome == p or nome.startswith(p + ".") for p in PROIBIDOS_TERCEIROS)

    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            for alias in no.names:
                nome = alias.name
                if nome.startswith("dengue_sinan."):
                    if nome.split(".")[1] not in ALLOWED_DENGUE:
                        achados.append(f"import {nome}")
                elif proibido_terceiro(nome):
                    achados.append(f"import {nome}")
        elif isinstance(no, ast.ImportFrom) and no.module:
            if no.module == "dengue_sinan":
                for alias in no.names:
                    if alias.name not in ALLOWED_DENGUE:
                        achados.append(f"from dengue_sinan import {alias.name}")
            elif no.module.startswith("dengue_sinan."):
                if no.module.split(".")[1] not in ALLOWED_DENGUE:
                    achados.append(f"from {no.module} import ...")
            elif proibido_terceiro(no.module):
                achados.append(f"from {no.module} import ...")
            elif no.module == "pandas" and any(a.name in LEITORES for a in no.names):
                achados.append("from pandas import leitor")
            for alias in no.names:
                if alias.name.startswith("leitura_"):
                    achados.append(f"importa {alias.name}")
    # leitura de arquivo só em carregar_previsoes; nenhum uso de leitura_* no corpo
    for no in arvore.body:
        if isinstance(no, ast.FunctionDef) and no.name == "carregar_previsoes":
            continue
        for sub in ast.walk(no):
            if isinstance(sub, ast.Attribute) and sub.attr in LEITORES:
                achados.append(f"{sub.attr} fora de carregar_previsoes")
            if isinstance(sub, ast.Attribute) and sub.attr.startswith("leitura_"):
                achados.append(f"uso de {sub.attr}")
    return achados


def test_modulo_original_passa_no_teste_estatico():
    assert _violacoes(ORIGEM_MODULO) == []


MUTACOES = [
    "import xgboost",
    "import lightgbm as lgb",
    "import catboost",
    "import torch",
    "from sklearn.pipeline import Pipeline",
    "import sklearn.pipeline",
    "from dengue_sinan import tuning",
    "from dengue_sinan import tracking",
    "from dengue_sinan import retreino",
    "from dengue_sinan import comparacao_entrada",
    "import dengue_sinan.elastic_net_m1",
    "import dengue_sinan.dataset",
    "from dengue_sinan.checks import algo",
    "from dengue_sinan.guard import leitura_do_ano_de_comparacao",
    "from dengue_sinan import guard",
    "def _vaza():\n    return pd.read_parquet('x.parquet')",
    "def _vaza():\n    return pd.read_csv('x.csv')",
    "from pandas import read_csv",
]


@pytest.mark.parametrize("linha", MUTACOES)
def test_teste_estatico_detecta_mutacao_em_copia(tmp_path, linha):
    copia = tmp_path / "comparar.py"
    copia.write_text(ORIGEM_MODULO.read_text(encoding="utf-8") + "\n" + linha + "\n",
                     encoding="utf-8")
    assert _violacoes(copia), f"não detectou: {linha!r}"
