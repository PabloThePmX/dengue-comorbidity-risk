"""Testes do elastic net do M1 (T-4.6b) com dados sintéticos pequenos (sem microdados).

Rápidos em CPU. MLflow e `mlruns/` ficam numa pasta temporária.
"""

import warnings

import numpy as np
import pandas as pd
import pytest
from mlflow.tracking import MlflowClient
from sklearn.exceptions import ConvergenceWarning

from dengue_sinan import cv, elastic_net_m1, tracking
from dengue_sinan.config import load_config
from dengue_sinan.elastic_net_m1 import ElasticNetM1, construir_elastic_net
from dengue_sinan.profiling import COMORBIDADES, SINAIS

# O filtro cala o ConvergenceWarning só nos testes que não tratam convergência. Os testes de
# convergência checam o aviso com pytest.warns / catch_warnings, que registram mesmo com o filtro.
pytestmark = pytest.mark.filterwarnings("ignore::sklearn.exceptions.ConvergenceWarning")

ORDEM = ["A", "B", "C"]
N_POR_REGIAO = 200
PARAMS = {"C": 0.05, "l1_ratio": 0.5, "solver": "saga", "max_iter": 500}


def cfg_teste() -> dict:
    return {"ordem_dobras": ORDEM, "seed": 7, "validacao_interna_frac": 0.2, "ano_teste": 2024}


def frame(seed: int = 3, ano: int = 2022) -> pd.DataFrame:
    """Casos com as colunas de features do dicionário e um sinal fraco em RENAL e DIABETES."""
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


def modelo(**mudancas) -> ElasticNetM1:
    return ElasticNetM1({**PARAMS, **mudancas}, seed=7)


# --- Registro, construção e recusas ---------------------------------------------------------

def test_registrado_no_registro_do_laco():
    assert cv.REGISTRO["elastic_net"] is construir_elastic_net
    m = cv.construir_modelo("elastic_net", PARAMS, cfg_teste())
    assert isinstance(m, ElasticNetM1)
    assert m.iterativo is False
    assert m.melhor_ponto() is None


def test_cada_construcao_devolve_objeto_novo():
    assert cv.construir_modelo("elastic_net", PARAMS, cfg_teste()) is not \
        cv.construir_modelo("elastic_net", PARAMS, cfg_teste())


def test_semente_vem_do_config():
    m = construir_elastic_net(PARAMS, cfg_teste())
    assert m._estimador.random_state == 7


def test_penalty_e_recusado_por_estar_deprecado():
    with pytest.raises(ValueError, match="deprecado"):
        ElasticNetM1({**PARAMS, "penalty": "elasticnet"}, seed=7)


@pytest.mark.parametrize("chave", ["class_weight", "scale_pos_weight"])
def test_peso_de_classe_e_recusado_na_construcao(chave):
    with pytest.raises(ValueError, match="R3"):
        ElasticNetM1({**PARAMS, chave: "balanced"}, seed=7)


def test_solver_diferente_de_saga_e_recusado():
    with pytest.raises(ValueError, match="saga"):
        ElasticNetM1({**PARAMS, "solver": "lbfgs"}, seed=7)


def test_sem_l1_ratio_e_recusado():
    sem = {k: v for k, v in PARAMS.items() if k != "l1_ratio"}
    with pytest.raises(ValueError, match="l1_ratio"):
        ElasticNetM1(sem, seed=7)


def test_sem_class_weight_no_estimador():
    assert modelo()._estimador.class_weight is None


def test_ajustar_recusa_validacao_de_parada():
    df = frame()
    with pytest.raises(ValueError, match="não é iterativo"):
        modelo().ajustar(df, df["y"].to_numpy(), df, df["y"].to_numpy())


def test_prever_antes_de_ajustar_levanta():
    with pytest.raises(RuntimeError):
        modelo().prever_proba(frame())


def test_recusa_ano_de_teste_no_treino_e_na_predicao():
    df = frame()
    df_2024 = df.assign(ANO=2024)
    with pytest.raises(RuntimeError, match="R1"):
        modelo().ajustar(df_2024, df_2024["y"].to_numpy())
    m = modelo()
    m.ajustar(df, df["y"].to_numpy())
    with pytest.raises(RuntimeError, match="R1"):
        m.prever_proba(df_2024)


# --- Ajuste e predição ------------------------------------------------------------------------

def test_probabilidades_uma_por_linha_em_zero_um():
    df = frame()
    m = modelo()
    m.ajustar(df, df["y"].to_numpy())
    p = m.prever_proba(df)
    assert p.shape == (len(df),)
    assert np.isfinite(p).all()
    assert ((p >= 0) & (p <= 1)).all()


def test_pipeline_usa_interacoes_entre_comorbidades():
    # D-63: o elastic net recebe os 21 pares de comorbidades além das 75 colunas da família linear.
    df = frame()
    m = modelo()
    m.ajustar(df, df["y"].to_numpy())
    X_t = m._pipeline.named_steps["preprocessamento"].transform(df)
    assert X_t.shape[1] == 96


def test_l1_ratio_ativa_a_penalizacao_l1_sem_o_parametro_penalty():
    # Com C pequeno, a parte L1 do elastic net zera coeficientes; com l1_ratio = 0 (só L2), não.
    df = frame()
    y = df["y"].to_numpy()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", ConvergenceWarning)
        com_l1 = modelo(l1_ratio=0.99, C=0.02)
        com_l1.ajustar(df, y)
    sem_l1 = modelo(l1_ratio=0.0, C=0.02)
    sem_l1.ajustar(df, y)
    assert int((com_l1._estimador.coef_ == 0).sum()) > 0
    assert int((sem_l1._estimador.coef_ == 0).sum()) == 0


def test_mesma_semente_mesmos_coeficientes():
    df = frame()
    y = df["y"].to_numpy()
    a, b = modelo(), modelo()
    a.ajustar(df, y)
    b.ajustar(df, y)
    assert np.array_equal(a._estimador.coef_, b._estimador.coef_)


# --- Convergência do saga (ConvergenceWarning tratado, não silenciado) -------------------------

def test_convergencia_normal_nao_gera_aviso_e_fica_registrada():
    df = frame()
    m = modelo(l1_ratio=0.0)
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        m.ajustar(df, df["y"].to_numpy())
    assert not [a for a in avisos if issubclass(a.category, ConvergenceWarning)]
    assert m.convergiu_ is True
    assert m.avisos_convergencia_ == 0
    assert 1 <= m.n_iter_ < PARAMS["max_iter"]


def test_nao_convergencia_emite_o_aviso_e_fica_registrada(tmp_path):
    base = load_config()
    cfg = {**base, "ordem_dobras": ORDEM, "seed": 7,
           "caminhos": {**base["caminhos"], "dados": str(tmp_path / "data"),
                        "mlruns": str(tmp_path / "mlruns")}}
    df = frame()
    m = ElasticNetM1({**PARAMS, "max_iter": 1}, seed=7)
    with tracking.start_run(cfg, "teste-en") as run:
        # O aviso não é silenciado: pytest.warns o pega, e a execução continua.
        with pytest.warns(ConvergenceWarning):
            m.ajustar(df, df["y"].to_numpy())
        id_run = run.info.run_id
    assert m.convergiu_ is False
    assert m.n_iter_ == 1
    assert m.avisos_convergencia_ == 1
    dados = MlflowClient(tracking_uri=str(tmp_path / "mlruns")).get_run(id_run).data.metrics
    assert dados[elastic_net_m1.PARAM_MLFLOW_CONVERGIU] == 0.0
    assert dados[elastic_net_m1.PARAM_MLFLOW_N_ITER] == 1.0
    assert dados[elastic_net_m1.PARAM_MLFLOW_AVISOS] == 1.0


def test_laco_completo_com_elastic_net_uma_predicao_por_linha():
    df = frame()
    cfg = cfg_teste()
    resultado = cv.run_loro(cfg, "elastic_net", PARAMS, df)
    assert len(resultado["oof"]) == len(df)
    assert set(resultado["melhores_pontos"].values()) == {None}
