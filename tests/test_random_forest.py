"""Testes do Random Forest do M1 (T-4.4) com dados sintéticos e árvores pequenas (sem microdados).

Rápidos em CPU. MLflow e `mlruns/` ficam numa pasta temporária.
"""

import numpy as np
import pandas as pd
import pytest
from mlflow.tracking import MlflowClient

from dengue_sinan import cv, tracking
from dengue_sinan.config import load_config
from dengue_sinan.profiling import COMORBIDADES, SINAIS
from dengue_sinan.random_forest import (
    RandomForestM1,
    construir_random_forest,
    corrigir_probabilidade,
    subamostrar_negativos,
)

ORDEM = ["A", "B", "C"]
N_POR_REGIAO = 200
PARAMS = {"n_estimators": 20, "max_depth": 4, "min_samples_leaf": 10,
          "max_features": "sqrt", "max_samples": 0.5, "criterion": "gini", "bootstrap": True}


def cfg_teste() -> dict:
    return {"ordem_dobras": ORDEM, "seed": 7, "validacao_interna_frac": 0.2, "ano_teste": 2024}


def frame(seed: int = 3, ano: int = 2022) -> pd.DataFrame:
    """Casos com as 26 features do dicionário (as colunas que a família "arvore" lê) e um sinal."""
    rng = np.random.default_rng(seed)
    n = N_POR_REGIAO * len(ORDEM)
    df = pd.DataFrame({
        "ANO": np.full(n, ano, dtype="int64"),
        "regiao": np.repeat(ORDEM, N_POR_REGIAO),
        "idade_anos": rng.uniform(0, 90, n),
        "sexo": rng.choice(["F", "M", "I"], n),
        "gestante": rng.integers(0, 2, n).astype("int8"),
        "dias_ate_notificacao": rng.integers(0, 60, n),
    })
    for c in [*COMORBIDADES, *SINAIS]:
        df[c] = rng.choice(["Sim", "Não", "Ausente"], n, p=[0.2, 0.7, 0.1])
    df["n_comorbidades"] = sum((df[c] == "Sim").astype(int) for c in COMORBIDADES)
    risco = 0.05 + 0.25 * (df["RENAL"] == "Sim") + 0.1 * (df["DIABETES"] == "Sim")
    df["y"] = (rng.uniform(size=n) < risco).astype("int64")
    return df.reset_index(drop=True)


# --- Correção de probabilidade e subamostra (funções puras) ---------------------------------

def test_correcao_bate_com_a_formula_do_spec():
    # p' = p / (p + (1 − p) / taxa). Com p = 0,2 e taxa = 0,5: 0,2 / (0,2 + 1,6) = 1/9.
    assert float(corrigir_probabilidade(0.2, 0.5)) == pytest.approx(0.2 / (0.2 + 0.8 / 0.5))
    assert float(corrigir_probabilidade(0.2, 0.5)) == pytest.approx(1 / 9)


def test_correcao_desfaz_a_amostragem_de_negativos():
    """Derivação independente: com p_s = p / (p + (1 − p)·taxa), a correção volta a p."""
    p = np.array([0.001, 0.01, 0.2, 0.5, 0.9])
    for taxa in (0.1, 0.25, 0.5, 0.9):
        p_amostra = p / (p + (1 - p) * taxa)
        assert corrigir_probabilidade(p_amostra, taxa) == pytest.approx(p, abs=1e-12)


def test_correcao_com_taxa_um_nao_muda_nada():
    p = np.array([0.0, 0.3, 1.0])
    assert corrigir_probabilidade(p, 1.0) == pytest.approx(p)


def test_correcao_fica_em_zero_um_e_reduz_a_probabilidade_amostrada():
    p = np.linspace(0, 1, 101)
    corrigida = corrigir_probabilidade(p, 0.1)
    assert (corrigida >= 0).all() and (corrigida <= 1).all()
    # Com negativos subamostrados o modelo superestima o risco: a correção nunca sobe o valor.
    assert (corrigida <= p + 1e-12).all()
    assert corrigida[0] == 0.0 and corrigida[-1] == pytest.approx(1.0)


@pytest.mark.parametrize("taxa", [0.0, -0.1, 1.5])
def test_correcao_recusa_taxa_fora_de_zero_um(taxa):
    with pytest.raises(ValueError, match="taxa"):
        corrigir_probabilidade(0.3, taxa)


def test_correcao_recusa_probabilidade_fora_de_zero_um():
    with pytest.raises(ValueError, match="fora de"):
        corrigir_probabilidade([0.2, 1.2], 0.5)


def test_subamostra_mantem_todos_os_positivos_e_a_fracao_de_negativos():
    y = np.array([1] * 10 + [0] * 1000)
    pos = subamostrar_negativos(y, taxa=0.25, seed=7)
    assert int(y[pos].sum()) == 10
    assert int((y[pos] == 0).sum()) == 250


def test_subamostra_e_reprodutivel_com_a_mesma_semente_e_muda_com_outra():
    y = np.array([1] * 5 + [0] * 500)
    assert np.array_equal(subamostrar_negativos(y, 0.3, 7), subamostrar_negativos(y, 0.3, 7))
    assert not np.array_equal(subamostrar_negativos(y, 0.3, 7), subamostrar_negativos(y, 0.3, 8))


def test_subamostra_com_taxa_um_devolve_tudo_e_recusa_taxa_invalida():
    y = np.array([0, 1, 0])
    assert np.array_equal(subamostrar_negativos(y, 1.0, 7), np.arange(3))
    with pytest.raises(ValueError, match="taxa"):
        subamostrar_negativos(y, 0.0, 7)


# --- Contrato, registro e recusas ------------------------------------------------------------

def test_registrado_no_registro_do_laco():
    assert cv.REGISTRO["random_forest"] is construir_random_forest
    modelo = cv.construir_modelo("random_forest", PARAMS, cfg_teste())
    assert isinstance(modelo, RandomForestM1)
    assert modelo.iterativo is False and modelo.melhor_ponto() is None


def test_cada_construcao_devolve_objeto_novo():
    a = cv.construir_modelo("random_forest", PARAMS, cfg_teste())
    b = cv.construir_modelo("random_forest", PARAMS, cfg_teste())
    assert a is not b


def test_semente_vem_do_config():
    modelo = construir_random_forest(PARAMS, {"seed": 123})
    assert modelo._seed == 123


@pytest.mark.parametrize("chave", ["class_weight", "scale_pos_weight", "is_unbalance"])
def test_parametro_de_peso_de_classe_e_recusado(chave):
    with pytest.raises(ValueError, match="R3"):
        RandomForestM1({**PARAMS, chave: "balanced"}, seed=7)


def test_taxa_fora_de_zero_um_e_recusada_na_construcao():
    for taxa in (0.0, 1.2):
        with pytest.raises(ValueError, match="taxa"):
            RandomForestM1({**PARAMS, "taxa_negativos": taxa}, seed=7)


def test_ajustar_recusa_ano_de_teste():
    df = frame()
    df.loc[0, "ANO"] = 2024  # R1
    modelo = RandomForestM1(PARAMS, seed=7)
    with pytest.raises(RuntimeError, match="teste congelado"):
        modelo.ajustar(df, df["y"])


def test_ajustar_recusa_validacao_de_parada():
    df = frame()
    modelo = RandomForestM1(PARAMS, seed=7)
    with pytest.raises(ValueError, match="não usa validação de parada"):
        modelo.ajustar(df, df["y"], df, df["y"])


def test_prever_antes_de_ajustar_levanta():
    with pytest.raises(RuntimeError, match="ajustar"):
        RandomForestM1(PARAMS, seed=7).prever_proba(frame())


def test_pipeline_usa_a_familia_arvore_e_sem_peso_de_classe():
    df = frame()
    modelo = RandomForestM1(PARAMS, seed=7)
    modelo.ajustar(df, df["y"])
    floresta = modelo._pipeline.named_steps["floresta"]
    assert floresta.class_weight is None  # R3
    assert floresta.random_state == 7  # R8
    assert "preprocessamento" in modelo._pipeline.named_steps  # R5: pré-processamento no Pipeline


# --- Predição, determinismo e dobras ---------------------------------------------------------

def test_probabilidades_uma_por_linha_em_zero_um():
    df = frame()
    modelo = RandomForestM1(PARAMS, seed=7)
    modelo.ajustar(df.iloc[:400], df["y"].iloc[:400])
    p = modelo.prever_proba(df.iloc[400:])
    assert p.shape == (len(df) - 400,)
    assert np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()


def test_mesma_semente_mesmas_probabilidades_bit_a_bit():
    df = frame()
    a = cv.run_loro(cfg_teste(), "random_forest", PARAMS, df)
    b = cv.run_loro(cfg_teste(), "random_forest", PARAMS, df)
    assert np.array_equal(a["oof"]["p"].to_numpy(), b["oof"]["p"].to_numpy())


def test_predicao_roda_em_sequencia_para_ser_deterministica():
    """Predição com threads soma as árvores em ordem variável (ver `ajustar`)."""
    modelo = RandomForestM1(PARAMS, seed=7)
    modelo.ajustar(frame(), frame()["y"])
    assert modelo._pipeline.named_steps["floresta"].n_jobs == 1
    assert modelo._pipeline.named_steps["floresta"].random_state == 7


def test_outra_semente_muda_as_probabilidades():
    df = frame()
    a = cv.run_loro(cfg_teste(), "random_forest", PARAMS, df)
    outro = {**cfg_teste(), "seed": 99}
    b = cv.run_loro(outro, "random_forest", PARAMS, df)
    assert not np.array_equal(a["oof"]["p"].to_numpy(), b["oof"]["p"].to_numpy())


def test_laco_completo_uma_predicao_por_linha_e_um_modelo_novo_por_dobra(monkeypatch):
    criados: list[RandomForestM1] = []

    def gravar(params, cfg):
        modelo = construir_random_forest(params, cfg)
        criados.append(modelo)
        return modelo

    monkeypatch.setitem(cv.REGISTRO, "random_forest", gravar)
    df = frame()
    resultado = cv.run_loro(cfg_teste(), "random_forest", PARAMS, df)
    assert len(resultado["oof"]) == len(df)
    assert sorted(resultado["posicoes"].tolist()) == list(range(len(df)))
    assert len(criados) == len(ORDEM)
    assert len({id(m) for m in criados}) == len(ORDEM)


# --- Subamostra de negativos: só no treino da dobra e com a correção -------------------------

def test_subamostra_so_no_treino_da_dobra_e_predicao_inteira(monkeypatch):
    criados: list[RandomForestM1] = []

    def gravar(params, cfg):
        modelo = construir_random_forest(params, cfg)
        criados.append(modelo)
        return modelo

    monkeypatch.setitem(cv.REGISTRO, "random_forest", gravar)
    df = frame()
    params = {**PARAMS, "taxa_negativos": 0.5}
    resultado = cv.run_loro(cfg_teste(), "random_forest", params, df)

    # Cada dobra treina com as outras regiões, subamostradas; a predição cobre a região toda.
    assert len(resultado["oof"]) == len(df)
    for regiao, modelo in zip(ORDEM, criados, strict=True):
        treino = df[df["regiao"] != regiao]
        positivos = int((treino["y"] == 1).sum())
        negativos = int((treino["y"] == 0).sum())
        assert modelo.linhas_ajuste == positivos + round(negativos * 0.5)
        assert modelo.taxa == 0.5


def test_sem_taxa_o_ajuste_usa_o_treino_inteiro(monkeypatch):
    criados: list[RandomForestM1] = []

    def gravar(params, cfg):
        modelo = construir_random_forest(params, cfg)
        criados.append(modelo)
        return modelo

    monkeypatch.setitem(cv.REGISTRO, "random_forest", gravar)
    df = frame()
    cv.run_loro(cfg_teste(), "random_forest", PARAMS, df)
    for regiao, modelo in zip(ORDEM, criados, strict=True):
        assert modelo.linhas_ajuste == int((df["regiao"] != regiao).sum())
        assert modelo.taxa == 1.0


def test_com_taxa_a_probabilidade_prevista_e_a_corrigida_da_floresta():
    df = frame()
    modelo = RandomForestM1({**PARAMS, "taxa_negativos": 0.25}, seed=7)
    modelo.ajustar(df, df["y"])
    bruta = modelo._pipeline.predict_proba(df)[:, 1]
    assert modelo.prever_proba(df) == pytest.approx(corrigir_probabilidade(bruta, 0.25))


# --- Taxa anotada no MLflow -----------------------------------------------------------------

def test_taxa_fica_anotada_no_run_do_mlflow(tmp_path):
    base = load_config()
    cfg = {**base, "ordem_dobras": ORDEM, "seed": 7,
           "caminhos": {**base["caminhos"], "dados": str(tmp_path / "data"),
                        "mlruns": str(tmp_path / "mlruns")}}
    df = frame()
    with tracking.start_run(cfg, "teste-rf") as run:
        RandomForestM1({**PARAMS, "taxa_negativos": 0.5}, seed=7).ajustar(df, df["y"])
        id_run = run.info.run_id
    client = MlflowClient(tracking_uri=str(tmp_path / "mlruns"))
    assert client.get_run(id_run).data.params["rf.taxa_negativos"] == "0.5"


def test_sem_subamostra_a_taxa_1_tambem_fica_anotada(tmp_path):
    base = load_config()
    cfg = {**base, "ordem_dobras": ORDEM, "seed": 7,
           "caminhos": {**base["caminhos"], "dados": str(tmp_path / "data"),
                        "mlruns": str(tmp_path / "mlruns")}}
    df = frame()
    with tracking.start_run(cfg, "teste-rf-sem-taxa") as run:
        RandomForestM1(PARAMS, seed=7).ajustar(df, df["y"])
        id_run = run.info.run_id
    client = MlflowClient(tracking_uri=str(tmp_path / "mlruns"))
    assert client.get_run(id_run).data.params["rf.taxa_negativos"] == "1.0"
