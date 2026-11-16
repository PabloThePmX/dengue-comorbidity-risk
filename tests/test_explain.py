"""Testes do E1 (T-3.1) com dados sintéticos de uma logística conhecida (R1, R7, R8, R9).

Nada aqui lê `data/`: a população é simulada com semente fixa.
"""

import dataclasses
import itertools
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import statsmodels.api as sm

from dengue_sinan import descriptive, explain
from dengue_sinan.profiling import COMORBIDADES

SEED = 20261103
N = 60_000
IDADE_SLOPE = 0.03
BETA_VERDADEIRO = {
    "Intercepto": -5.5,
    "Idade (spline) 1": IDADE_SLOPE,  # efeito linear: fica na coluna x da base
    "Sexo: M (ref. F)": 0.2,
    "Gestante: Sim": 0.6,
    "DIABETES: Sim": 0.8,
    "HEMATOLOG: Sim": 0.5,
    "HEPATOPAT: Sim": 0.4,
    "RENAL: Sim": 1.0,
    "HIPERTENSA: Sim": 0.6,
    "ACIDO_PEPT: Sim": 0.3,
    "AUTO_IMUNE: Sim": 0.2,
    "DIABETES: Ausente": -0.3,
    "DIABETES x RENAL": 0.5,
    # log-OR de DIABETES cresce 0,02 por ano em torno de 40 anos (interação centrada em 40)
    "DIABETES x Idade (spline) 1": 0.02,
}


def _cfg(tmp_path: Path, supressao: int = 10) -> dict:
    return {
        "seed": SEED,
        "anos_dev": [2022, 2023],
        "ano_teste": 2024,
        "supressao_min_celula": supressao,
        "caminhos": {"dados": str(tmp_path / "data"), "relatorios": str(tmp_path / "reports")},
    }


def _populacao_sintetica(n: int = N, seed: int = SEED) -> pd.DataFrame:
    """Linhas no formato de `build_feature_frame`, com efeitos conhecidos (logit)."""
    rng = np.random.default_rng(seed)
    idade = rng.uniform(0, 90, n)
    sexo = rng.choice(["F", "M", "I"], size=n, p=[0.5, 0.495, 0.005])
    gestante = ((sexo == "F") & (rng.uniform(size=n) < 0.05)).astype("int8")
    df = pd.DataFrame({"ANO": rng.choice([2022, 2023], size=n), "idade_anos": idade,
                       "sexo": sexo, "gestante": gestante})
    eta = BETA_VERDADEIRO["Intercepto"] + IDADE_SLOPE * idade
    eta = eta + BETA_VERDADEIRO["Sexo: M (ref. F)"] * (sexo == "M")
    eta = eta + BETA_VERDADEIRO["Gestante: Sim"] * gestante
    for c in COMORBIDADES:
        u = rng.uniform(size=n)
        valor = np.where(u < 0.01, "Ausente", np.where(u < 0.31, "Sim", "Não"))
        df[c] = pd.Categorical(valor, categories=["Sim", "Não", "Ausente"])
        eta = eta + BETA_VERDADEIRO.get(f"{c}: Sim", 0.0) * (valor == "Sim")
        eta = eta + BETA_VERDADEIRO.get(f"{c}: Ausente", 0.0) * (valor == "Ausente")
    eta = eta + BETA_VERDADEIRO["DIABETES x RENAL"] * (
        (df["DIABETES"] == "Sim") & (df["RENAL"] == "Sim"))
    eta = eta + BETA_VERDADEIRO["DIABETES x Idade (spline) 1"] * (
        (df["DIABETES"] == "Sim") * (idade - explain.IDADE_REFERENCIA))
    p = 1 / (1 + np.exp(-eta))
    df["y"] = (rng.uniform(size=n) < p).astype("int8")
    return df


def _escrever_pares(cfg: dict, df: pd.DataFrame) -> None:
    caminho = Path(cfg["caminhos"]["dados"]) / "descritiva" / "pares_comorbidades.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    descriptive.pair_event_counts(df).to_csv(caminho, index=False)


@pytest.fixture(scope="module")
def sintetico(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e1")
    cfg = _cfg(tmp)
    df = _populacao_sintetica()
    _escrever_pares(cfg, df)
    e1 = explain.ajustar_e1(cfg, df)
    return cfg, df, e1


# --- Recuperação dos coeficientes --------------------------------------------------------------

def test_recupera_coeficientes_verdadeiros_dentro_de_4_erros_padrao(sintetico):
    _, _, e1 = sintetico
    assert e1.resultados.converged
    params = pd.Series(np.asarray(e1.resultados.params), index=e1.colunas)
    erros = pd.Series(np.asarray(e1.resultados.bse), index=e1.colunas)
    for nome, verdadeiro in BETA_VERDADEIRO.items():
        assert abs(params[nome] - verdadeiro) <= 4 * erros[nome], nome


def test_log_or_aos_40_anos_e_recuperado_e_helper_le_outras_idades(sintetico):
    _, _, e1 = sintetico
    params = pd.Series(np.asarray(e1.resultados.params), index=e1.colunas)
    erros = pd.Series(np.asarray(e1.resultados.bse), index=e1.colunas)
    # Verdadeiro: 0,8 aos 40 anos; a interação linear com a idade adiciona 0,02 por ano.
    aos_40 = explain.log_or_na_idade(e1, "DIABETES", 40)
    assert aos_40["estimativa"] == pytest.approx(params["DIABETES: Sim"], abs=1e-9)
    assert abs(aos_40["estimativa"] - 0.8) <= 4 * erros["DIABETES: Sim"]
    aos_60 = explain.log_or_na_idade(e1, "DIABETES", 60)
    assert abs(aos_60["estimativa"] - 1.2) <= 4 * aos_60["erro_padrao"]
    assert aos_60["ic_inferior"] < aos_60["estimativa"] < aos_60["ic_superior"]


def test_termos_de_idade_nao_lineares_sao_nulos(sintetico):
    # A simulação é linear na idade: as outras colunas da base devem ficar em torno de zero.
    _, _, e1 = sintetico
    params = pd.Series(np.asarray(e1.resultados.params), index=e1.colunas)
    erros = pd.Series(np.asarray(e1.resultados.bse), index=e1.colunas)
    for nome in [c for c in e1.colunas if c.startswith("Idade (spline) ") and c[-1] != "1"]:
        assert abs(params[nome]) <= 4 * erros[nome], nome


# --- Sem penalização (R9) ----------------------------------------------------------------------

def test_ajuste_sem_penalizacao_zera_o_gradiente(sintetico):
    # Com penalização, o gradiente da log-verossimilhança no ponto ajustado não seria zero.
    _, df, e1 = sintetico
    agrupado = explain._agrupar(df)
    X = explain.matriz_de_desenho(agrupado, e1.nos, e1.pares_incluidos).to_numpy(float)
    mu = np.asarray(e1.resultados.mu)
    escore = X.T @ (agrupado["eventos"].to_numpy(float) - agrupado["casos"].to_numpy(float) * mu)
    assert np.max(np.abs(escore)) < 1e-4


# --- Pares (arquivo de T-2.6) ------------------------------------------------------------------

def _tabela_pares(eventos_por_par: dict[tuple[str, str], int]) -> pd.DataFrame:
    linhas = [{"comorbidade_1": a, "comorbidade_2": b, "casos": 1000, "eventos": e}
              for (a, b), e in eventos_por_par.items()]
    return pd.DataFrame(linhas)


def test_pares_incluidos_vem_do_arquivo_e_excluem_menos_de_10_eventos(tmp_path):
    eventos = {p: 50 for p in explain.PARES}
    eventos[("DIABETES", "HEMATOLOG")] = 9   # 1–9 eventos: fora
    eventos[("DIABETES", "HEPATOPAT")] = 10  # 10: dentro
    caminho = tmp_path / "pares.csv"
    _tabela_pares(eventos).to_csv(caminho, index=False)

    tabela = explain.ler_pares(caminho)
    incluidos, excluidos = explain.pares_do_arquivo(tabela)

    assert ("DIABETES", "HEPATOPAT") in incluidos
    assert excluidos == [("DIABETES", "HEMATOLOG")]
    assert len(incluidos) + len(excluidos) == 21


def test_arquivo_de_pares_incompleto_falha(tmp_path):
    eventos = {p: 50 for p in explain.PARES[:-1]}  # falta um par
    caminho = tmp_path / "pares.csv"
    _tabela_pares(eventos).to_csv(caminho, index=False)
    with pytest.raises(ValueError, match="21 pares"):
        explain.ler_pares(caminho)


def test_pares_do_arquivo_nao_batendo_com_os_dados_falha(tmp_path, sintetico):
    cfg, df, _ = sintetico
    trocado = df.copy()  # cópia com eventos alterados para quebrar a conferência
    trocado.loc[trocado["DIABETES"] == "Sim", "y"] = 0
    with pytest.raises(ValueError, match="não bate com os dados"):
        explain._conferir_pares(explain.ler_pares(explain._caminho_pares(cfg)), trocado)


# --- Ausente como nível próprio (D-07) ---------------------------------------------------------

def test_ausente_e_nivel_proprio_e_nao_entra_em_interacao(sintetico):
    _, _, e1 = sintetico
    for c in COMORBIDADES:
        assert f"{c}: Ausente" in e1.colunas
        assert f"{c}: Sim" in e1.colunas
    for col in e1.colunas:
        if " x " in col:
            assert "Ausente" not in col


def test_matriz_mostra_ausente_como_indicador_proprio():
    df = pd.DataFrame({
        "idade_anos": [10.0, 30.0, 50.0], "sexo": ["F", "M", "I"], "gestante": [0, 0, 0],
        **{c: pd.Categorical(["Ausente", "Sim", "Não"],
                             categories=["Sim", "Não", "Ausente"]) for c in COMORBIDADES},
    })
    nos = {"idade": explain._nos(df["idade_anos"].to_numpy(float), 5),
           "idade_interacao": explain._nos(df["idade_anos"].to_numpy(float), 3)}
    X = explain.matriz_de_desenho(df, nos, [])
    assert X["DIABETES: Ausente"].tolist() == [1.0, 0.0, 0.0]
    assert X["DIABETES: Sim"].tolist() == [0.0, 1.0, 0.0]


# --- Splines e posto --------------------------------------------------------------------------

def test_base_spline_e_linear_alem_dos_nos_e_tem_gl_colunas():
    nos = [0.0, 10.0, 20.0, 30.0, 40.0, 50.0]  # gl = 5
    x = np.array([60.0, 70.0, 80.0, 90.0])
    base = explain._base_spline(x, nos)
    assert base.shape == (4, 5)
    assert np.allclose(np.diff(base, n=2, axis=0), 0.0, atol=1e-6)


def _matriz_antiga(df, nos, pares):
    """Parametrização antiga: interação sem centrar (Sim * B_j(idade)). Só para a comparação."""
    X = explain.matriz_de_desenho(df, nos, pares)
    interacao = explain._base_spline(df["idade_anos"].to_numpy(float), nos["idade_interacao"])
    for c in ("HIPERTENSA", "DIABETES"):
        sim = (df[c] == "Sim").to_numpy(float)
        for j in range(interacao.shape[1]):
            X[f"{c} x Idade (spline) {j + 1}"] = sim * interacao[:, j]
    return X


def test_centrar_na_idade_de_referencia_nao_muda_modelo_nem_previsoes(sintetico):
    _, df, e1 = sintetico
    agr = explain._agrupar(df)
    eventos = agr["eventos"].to_numpy(float)
    casos = agr["casos"].to_numpy(float)
    X_nova = explain.matriz_de_desenho(agr, e1.nos, e1.pares_incluidos)
    X_antiga = _matriz_antiga(agr, e1.nos, e1.pares_incluidos)
    nova = explain._ajustar_glm(X_nova.to_numpy(float), eventos, casos)
    antiga = explain._ajustar_glm(X_antiga.to_numpy(float), eventos, casos)
    # mesma log-verossimilhança e mesmos ajustes nos padrões observados
    assert abs(explain._log_verossimilhanca(eventos, casos, nova.mu)
               - explain._log_verossimilhanca(eventos, casos, antiga.mu)) < 1e-6
    assert np.max(np.abs(np.asarray(nova.mu) - np.asarray(antiga.mu))) < 1e-8
    # mesmas previsões numa grade de idades x sexo x comorbidades (demais em Não)
    linhas = []
    for idade, sexo in itertools.product([0.0, 5.0, 20.0, 40.0, 60.0, 80.0, 90.0],
                                          ["F", "M", "I"]):
        for d, h in itertools.product(["Não", "Ausente", "Sim"], repeat=2):
            linha = {"idade_anos": idade, "sexo": sexo, "gestante": 0,
                     **{c: "Não" for c in COMORBIDADES}, "DIABETES": d, "HIPERTENSA": h}
            linhas.append(linha)
    grade = pd.DataFrame(linhas)
    for c in COMORBIDADES:
        grade[c] = pd.Categorical(grade[c], categories=["Sim", "Não", "Ausente"])
    eta_nova = explain.matriz_de_desenho(grade, e1.nos, e1.pares_incluidos).to_numpy(float) @ (
        nova.params)
    eta_antiga = _matriz_antiga(grade, e1.nos, e1.pares_incluidos).to_numpy(float) @ (
        antiga.params)
    assert np.max(np.abs(eta_nova - eta_antiga)) < 1e-6
    # o efeito principal novo é o contraste antigo aos 40 anos: β + Σ γ_j B_j(40)
    ref = explain._base_spline(np.array([float(explain.IDADE_REFERENCIA)]),
                               e1.nos["idade_interacao"])[0]
    for c in ("DIABETES", "HIPERTENSA"):
        i_principal = list(X_antiga.columns).index(f"{c}: Sim")
        gammas = [antiga.params[list(X_antiga.columns).index(f"{c} x Idade (spline) {j + 1}")]
                  for j in range(len(ref))]
        esperado = antiga.params[i_principal] + float(np.dot(gammas, ref))
        assert abs(nova.params[list(X_nova.columns).index(f"{c}: Sim")] - esperado) < 1e-6


def test_desenho_tem_posto_completo(sintetico):
    _, df, e1 = sintetico
    X = explain.matriz_de_desenho(explain._agrupar(df), e1.nos, e1.pares_incluidos).to_numpy()
    assert np.linalg.matrix_rank(X) == X.shape[1]


# --- Guarda (R1) -------------------------------------------------------------------------------

def test_guarda_recusa_2024(tmp_path):
    cfg = _cfg(tmp_path)
    df = _populacao_sintetica(n=2_000)
    df.loc[0, "ANO"] = 2024
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        explain.ajustar_e1(cfg, df)


@pytest.mark.parametrize("chamada", [
    lambda df, cfg: explain.checar_equivalencia(df, None, [], 10, 0),
    lambda df, cfg: explain.contagens_por_padrao(df),
    lambda df, cfg: explain.padrao_todas_sim(df),
    lambda df, cfg: explain.resumo_padrao(df),
    lambda df, cfg: explain._acrescentar_diagnostico(cfg, df),
], ids=["checar_equivalencia", "contagens_por_padrao", "padrao_todas_sim", "resumo_padrao",
        "_acrescentar_diagnostico"])
def test_auxiliares_de_casos_recusam_o_ano_de_teste(tmp_path, chamada):
    # Defesa em profundidade (R1): mesmo sem o guard do chamador, o auxiliar recusa 2024.
    cfg = _cfg(tmp_path)
    df = _populacao_sintetica(n=500)
    df.loc[0, "ANO"] = 2024
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        chamada(df, cfg)


def test_nivel_sem_casos_falha(tmp_path):
    cfg = _cfg(tmp_path)
    df = _populacao_sintetica(n=5_000)
    df["RENAL"] = pd.Categorical(np.where(df["RENAL"] == "Ausente", "Não", df["RENAL"]),
                                 categories=["Sim", "Não", "Ausente"])
    _escrever_pares(cfg, df)
    with pytest.raises(ValueError, match="sem nenhum caso"):
        explain.ajustar_e1(cfg, df)


# --- Equivalência agrupado x linha a linha -----------------------------------------------------

def test_agrupado_e_igual_a_linha_a_linha_numa_amostra(sintetico):
    cfg, df, e1 = sintetico
    equivalencia = explain.checar_equivalencia(df, e1, e1.pares_incluidos, n=20_000,
                                               seed=cfg["seed"])
    assert equivalencia["passou"], equivalencia
    assert equivalencia["dif_relativa_log_verossimilhanca"] < 1e-8
    assert equivalencia["dif_relativa_escore"] < 1e-8
    assert equivalencia["dif_relativa_informacao"] < 1e-8


def test_ajustes_linha_a_linha_e_agrupado_dao_o_mesmo_resultado(sintetico):
    # Nos dados sintéticos os dois ajustes convergem: coeficientes e erros-padrão iguais (1e-6).
    cfg, df, e1 = sintetico
    amostra = df.sample(n=20_000, random_state=cfg["seed"])
    X_linha = explain.matriz_de_desenho(amostra, e1.nos, e1.pares_incluidos).to_numpy(float)
    linha = sm.Logit(amostra["y"].to_numpy(float), X_linha).fit(
        method="newton", maxiter=100, tol=1e-10, disp=False)
    agrupado = explain._agrupar(amostra)
    X_agr = explain.matriz_de_desenho(agrupado, e1.nos, e1.pares_incluidos).to_numpy(float)
    agr = explain._ajustar_glm(X_agr, agrupado["eventos"].to_numpy(float),
                               agrupado["casos"].to_numpy(float))
    assert np.max(np.abs(np.asarray(linha.params) - np.asarray(agr.params))) < 1e-6
    assert np.max(np.abs(np.asarray(linha.bse) - np.asarray(agr.bse))) < 1e-6


# --- Persistência e relatório ------------------------------------------------------------------

def test_salvar_e_carregar_recupera_o_ajuste_sem_dados(tmp_path, sintetico):
    _, df, e1 = sintetico
    cfg = _cfg(tmp_path)
    explain.salvar_e1(cfg, e1)
    carregado = explain.load_e1(cfg)
    assert np.allclose(np.asarray(carregado.resultados.params),
                       np.asarray(e1.resultados.params))
    assert carregado.colunas == e1.colunas
    assert carregado.nos == e1.nos
    assert carregado.pares_incluidos == e1.pares_incluidos
    assert carregado.resultados.model.endog is None  # remove_data: sem as linhas do ajuste


def test_relatorio_traz_aviso_p6_e_suprime_termos_pequenos(tmp_path, sintetico):
    _, _, e1 = sintetico
    cfg = _cfg(tmp_path, supressao=10**9)  # força a supressão de todos os termos binários
    excluido = dataclasses.replace(
        e1, pares_excluidos=[("ACIDO_PEPT", "AUTO_IMUNE")],
        pares_incluidos=[p for p in e1.pares_incluidos if p != ("ACIDO_PEPT", "AUTO_IMUNE")])
    caminho = explain.escrever_relatorio(cfg, excluido)
    texto = caminho.read_text(encoding="utf-8")
    assert "associação, não causa (P6)" in texto
    assert "suprimido (R7)" in texto
    assert "ACIDO_PEPT + AUTO_IMUNE | eventos insuficientes" in texto
    assert "eventos insuficientes" in texto
