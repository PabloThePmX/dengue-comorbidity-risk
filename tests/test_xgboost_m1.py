"""Testes do XGBoost do M1 (T-4.5) com dados sintéticos e árvores pequenas (sem microdados).

Rápidos em CPU. MLflow e `mlruns/` ficam numa pasta temporária.
"""

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb
from mlflow.tracking import MlflowClient
from sklearn.compose import ColumnTransformer

from dengue_sinan import cv, tracking, xgboost_m1
from dengue_sinan.config import load_config
from dengue_sinan.profiling import COMORBIDADES, SINAIS
from dengue_sinan.xgboost_m1 import XGBoostM1, construir_xgboost

ORDEM = ["A", "B", "C"]
N_POR_REGIAO = 200
PARAMS = {
    "tree_method": "hist", "n_estimators": 300, "early_stopping_rounds": 5,
    "eval_metric": "aucpr", "learning_rate": 0.3, "max_depth": 3, "min_child_weight": 1.0,
    "subsample": 0.8, "colsample_bytree": 0.8, "reg_lambda": 1.0, "device": "cpu",
}


def cfg_teste() -> dict:
    return {"ordem_dobras": ORDEM, "seed": 7, "validacao_interna_frac": 0.2, "ano_teste": 2024}


def frame(seed: int = 3, ano: int = 2022) -> pd.DataFrame:
    """Casos com as 26 features do dicionário (as colunas que a família "arvore" lê) e um sinal
    fraco, para a parada antecipada acontecer antes do teto de árvores."""
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


def _espiar_fit(monkeypatch) -> list[tuple[np.ndarray, list]]:
    """Registra X e eval_set de cada `XGBClassifier.fit` (sem mudar o comportamento)."""
    registros: list[tuple[np.ndarray, list]] = []
    original = xgb.XGBClassifier.fit

    def espiao(self, X, y, **kwargs):
        registros.append((np.asarray(X), kwargs.get("eval_set")))
        return original(self, X, y, **kwargs)

    monkeypatch.setattr(xgb.XGBClassifier, "fit", espiao)
    return registros


def _espiar_fit_transform(monkeypatch) -> list[int]:
    """Número de linhas que chegam a `ColumnTransformer.fit_transform` (R5)."""
    linhas: list[int] = []
    original = ColumnTransformer.fit_transform

    def espiao(self, X, y=None, **kwargs):
        linhas.append(len(X))
        return original(self, X, y, **kwargs)

    monkeypatch.setattr(ColumnTransformer, "fit_transform", espiao)
    return linhas


# --- Registro, construção e recusas ---------------------------------------------------------

def test_registrado_no_registro_do_laco():
    assert cv.REGISTRO["xgboost"] is construir_xgboost
    modelo = cv.construir_modelo("xgboost", PARAMS, cfg_teste())
    assert isinstance(modelo, XGBoostM1)
    assert modelo.iterativo is True
    assert modelo.melhor_ponto() is None


def test_cada_construcao_devolve_objeto_novo():
    a = cv.construir_modelo("xgboost", PARAMS, cfg_teste())
    b = cv.construir_modelo("xgboost", PARAMS, cfg_teste())
    assert a is not b


def test_semente_vem_do_config():
    modelo = construir_xgboost(PARAMS, {"seed": 123})
    assert modelo._estimador.get_params()["random_state"] == 123  # R8


def test_metrica_de_parada_e_a_do_config():
    modelo = XGBoostM1(PARAMS, seed=7)
    assert modelo._estimador.get_params()["eval_metric"] == "aucpr"


@pytest.mark.parametrize("chave", ["scale_pos_weight", "class_weight", "is_unbalance"])
def test_parametro_de_peso_de_classe_e_recusado_na_construcao(chave):
    with pytest.raises(ValueError, match="R3"):
        XGBoostM1({**PARAMS, chave: 3.0}, seed=7)


def test_sem_early_stopping_no_config_e_recusado():
    params = {k: v for k, v in PARAMS.items() if k != "early_stopping_rounds"}
    with pytest.raises(ValueError, match="early_stopping_rounds"):
        XGBoostM1(params, seed=7)


def test_ajustar_sem_validacao_interna_levanta():
    df = frame()
    with pytest.raises(ValueError, match="R6"):
        XGBoostM1(PARAMS, seed=7).ajustar(df, df["y"])


def test_ajustar_recusa_ano_de_teste_no_treino_e_na_parada():
    df = frame()
    df_teste = df.copy()
    df_teste.loc[0, "ANO"] = 2024  # R1
    with pytest.raises(RuntimeError, match="teste congelado"):
        XGBoostM1(PARAMS, seed=7).ajustar(df_teste, df_teste["y"], df.iloc[:50], df["y"].iloc[:50])
    with pytest.raises(RuntimeError, match="teste congelado"):
        XGBoostM1(PARAMS, seed=7).ajustar(df, df["y"], df_teste.iloc[:50], df["y"].iloc[:50])


def test_prever_antes_de_ajustar_levanta():
    with pytest.raises(RuntimeError, match="ajustar"):
        XGBoostM1(PARAMS, seed=7).prever_proba(frame())


def test_prever_recusa_ano_de_teste():
    df = frame()
    modelo = XGBoostM1(PARAMS, seed=7)
    modelo.ajustar(df.iloc[:400], df["y"].iloc[:400], df.iloc[400:500], df["y"].iloc[400:500])
    with pytest.raises(RuntimeError, match="teste congelado"):
        modelo.prever_proba(frame(ano=2024))


# --- Dispositivo ------------------------------------------------------------------------------

def test_device_explicito_vai_ao_estimador():
    modelo = XGBoostM1({**PARAMS, "device": "cpu"}, seed=7)
    assert modelo._estimador.get_params()["device"] == "cpu"
    assert modelo._dispositivo == "cpu"


def test_sem_device_usa_a_deteccao(monkeypatch):
    monkeypatch.setattr(xgboost_m1, "detectar_dispositivo", lambda: "cuda")
    params = {k: v for k, v in PARAMS.items() if k != "device"}
    modelo = XGBoostM1(params, seed=7)
    assert modelo._estimador.get_params()["device"] == "cuda"


def test_deteccao_devolve_cpu_ou_cuda_e_fica_em_cache():
    primeira = xgboost_m1.detectar_dispositivo()
    assert primeira in {"cpu", "cuda"}
    assert xgboost_m1.detectar_dispositivo() == primeira


# --- Parada antecipada, pré-processamento e validação interna (R5, R6) -----------------------

def test_parada_usa_so_a_validacao_interna(monkeypatch):
    df = frame()
    treino, parada = df.iloc[:400], df.iloc[400:500]
    registros = _espiar_fit(monkeypatch)
    modelo = XGBoostM1(PARAMS, seed=7)
    modelo.ajustar(treino, treino["y"], parada, parada["y"])

    X_fit, eval_set = registros[-1]
    assert len(X_fit) == len(treino)  # o ajuste não vê a validação interna
    assert eval_set is not None and len(eval_set) == 1
    X_eval, y_eval = eval_set[0]
    pre = modelo._pipeline.named_steps["preprocessamento"]
    assert np.array_equal(X_eval, pre.transform(parada))  # validação transformada com o treino
    assert np.array_equal(y_eval, parada["y"].to_numpy())


def test_pre_processador_so_ajusta_com_o_treino(monkeypatch):
    df = frame()
    treino, parada = df.iloc[:400], df.iloc[400:500]
    linhas = _espiar_fit_transform(monkeypatch)
    XGBoostM1(PARAMS, seed=7).ajustar(treino, treino["y"], parada, parada["y"])
    assert linhas == [len(treino)]  # R5: o ajuste do pré-processador nunca viu a parada


def test_pipeline_usa_a_familia_arvore_sem_peso_de_classe():
    modelo = XGBoostM1(PARAMS, seed=7)
    assert "preprocessamento" in modelo._pipeline.named_steps  # R5
    assert modelo._estimador.get_params()["scale_pos_weight"] in (None, 1)  # R3: padrão


# --- Predição, melhor ponto e determinismo ----------------------------------------------------

def test_melhor_ponto_e_inteiro_e_nao_passa_do_teto():
    df = frame()
    modelo = XGBoostM1(PARAMS, seed=7)
    modelo.ajustar(df.iloc[:400], df["y"].iloc[:400], df.iloc[400:500], df["y"].iloc[400:500])
    melhor = modelo.melhor_ponto()
    assert isinstance(melhor, int)
    assert 0 <= melhor <= PARAMS["n_estimators"]


def test_predicao_usa_so_as_arvores_ate_o_melhor_ponto(monkeypatch):
    """Sem o `iteration_range` explícito, a predição usaria outro ponto (ou todas as árvores)."""
    df = frame()
    modelo = XGBoostM1(PARAMS, seed=7)
    modelo.ajustar(df.iloc[:400], df["y"].iloc[:400], df.iloc[400:500], df["y"].iloc[400:500])
    melhor = modelo.melhor_ponto()
    X_teste = df.iloc[500:]

    chamadas: list = []
    original = xgb.XGBClassifier.predict_proba

    def espiao(self, X, **kwargs):
        chamadas.append(kwargs.get("iteration_range"))
        return original(self, X, **kwargs)

    monkeypatch.setattr(xgb.XGBClassifier, "predict_proba", espiao)
    ate_melhor = modelo.prever_proba(X_teste)
    assert chamadas == [(0, melhor + 1)]

    # Parada de fato aconteceu: o booster tem mais árvores que o melhor ponto.
    X_t = modelo._pipeline.named_steps["preprocessamento"].transform(X_teste)
    todas = modelo._estimador.get_booster().num_boosted_rounds()
    assert todas > melhor + 1
    com_todas = original(modelo._estimador, X_t, iteration_range=(0, todas))[:, 1]
    assert not np.allclose(com_todas, ate_melhor)


def test_probabilidades_uma_por_linha_em_zero_um():
    df = frame()
    modelo = XGBoostM1(PARAMS, seed=7)
    modelo.ajustar(df.iloc[:400], df["y"].iloc[:400], df.iloc[400:500], df["y"].iloc[400:500])
    p = modelo.prever_proba(df.iloc[500:])
    assert p.shape == (len(df) - 500,)
    assert np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()


def test_laco_completo_uma_predicao_por_linha_e_melhor_ponto_no_teto():
    df = frame()
    resultado = cv.run_loro(cfg_teste(), "xgboost", PARAMS, df)
    assert len(resultado["oof"]) == len(df)
    assert sorted(resultado["posicoes"].tolist()) == list(range(len(df)))
    p = resultado["oof"]["p"].to_numpy()
    assert np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()
    assert set(resultado["melhores_pontos"]) == set(ORDEM)
    for melhor in resultado["melhores_pontos"].values():
        assert isinstance(melhor, int) and 0 <= melhor <= PARAMS["n_estimators"]


def test_laco_cria_um_modelo_novo_por_dobra(monkeypatch):
    criados: list[XGBoostM1] = []

    def gravar(params, cfg):
        modelo = construir_xgboost(params, cfg)
        criados.append(modelo)
        return modelo

    monkeypatch.setitem(cv.REGISTRO, "xgboost", gravar)
    cv.run_loro(cfg_teste(), "xgboost", PARAMS, frame())
    assert len(criados) == len(ORDEM)
    assert len({id(m) for m in criados}) == len(ORDEM)


def test_mesma_semente_mesmas_probabilidades_bit_a_bit():
    df = frame()
    a = cv.run_loro(cfg_teste(), "xgboost", PARAMS, df)
    b = cv.run_loro(cfg_teste(), "xgboost", PARAMS, df)
    assert np.array_equal(a["oof"]["p"].to_numpy(), b["oof"]["p"].to_numpy())
    assert a["melhores_pontos"] == b["melhores_pontos"]


def test_outra_semente_muda_as_probabilidades():
    df = frame()
    a = cv.run_loro(cfg_teste(), "xgboost", PARAMS, df)
    b = cv.run_loro({**cfg_teste(), "seed": 99}, "xgboost", PARAMS, df)
    assert not np.array_equal(a["oof"]["p"].to_numpy(), b["oof"]["p"].to_numpy())


# --- MLflow: dispositivo e melhor iteração ----------------------------------------------------

def test_dispositivo_e_melhor_iteracao_ficam_no_mlflow(tmp_path):
    base = load_config()
    cfg = {**base, "ordem_dobras": ORDEM, "seed": 7,
           "caminhos": {**base["caminhos"], "dados": str(tmp_path / "data"),
                        "mlruns": str(tmp_path / "mlruns")}}
    df = frame()
    with tracking.start_run(cfg, "teste-xgb") as run:
        # 3 dobras no mesmo run: o parâmetro de dispositivo é o mesmo em todas, sem erro.
        cv.run_loro(cfg, "xgboost", PARAMS, df)
        id_run = run.info.run_id
    client = MlflowClient(tracking_uri=str(tmp_path / "mlruns"))
    dados = client.get_run(id_run).data
    assert dados.params[xgboost_m1.PARAM_MLFLOW_DISPOSITIVO] == "cpu"
    assert xgboost_m1.METRICA_MLFLOW_MELHOR in dados.metrics
