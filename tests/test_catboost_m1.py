"""Testes do CatBoost do M1 (T-4.6) com dados sintéticos e árvores pequenas (sem microdados).

Rápidos em CPU. MLflow, `mlruns/` e qualquer arquivo do CatBoost ficam numa pasta temporária.
"""

import warnings

import numpy as np
import pandas as pd
import pytest
from catboost import CatBoostClassifier, CatBoostError
from mlflow.tracking import MlflowClient
from sklearn.compose import ColumnTransformer

from dengue_sinan import catboost_m1, cv, tracking
from dengue_sinan.catboost_m1 import CatBoostM1, construir_catboost
from dengue_sinan.config import load_config
from dengue_sinan.preprocess import CATEGORICAS_CATBOOST, indices_cat_features_catboost
from dengue_sinan.profiling import COMORBIDADES, SINAIS
from dengue_sinan.search_space import load_search_space

ORDEM = ["A", "B", "C"]
N_POR_REGIAO = 200
PARAMS = {
    "loss_function": "Logloss", "iterations": 300, "learning_rate": 0.3, "depth": 3,
    "l2_leaf_reg": 3.0, "od_type": "Iter", "od_wait": 5, "eval_metric": "PRAUC", "device": "cpu",
}


def cfg_teste() -> dict:
    return {"ordem_dobras": ORDEM, "seed": 7, "validacao_interna_frac": 0.2, "ano_teste": 2024}


def frame(seed: int = 3, ano: int = 2022) -> pd.DataFrame:
    """Casos com as 26 features do dicionário (as colunas que a família "catboost" lê) e um sinal
    fraco, para a parada antecipada acontecer antes do teto de iterações."""
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


def _ajustado(df: pd.DataFrame, params: dict = PARAMS) -> CatBoostM1:
    modelo = CatBoostM1(params, seed=7)
    modelo.ajustar(df.iloc[:400], df["y"].iloc[:400], df.iloc[400:500], df["y"].iloc[400:500])
    return modelo


def _espiar_fit(monkeypatch) -> list[tuple[pd.DataFrame, dict]]:
    """Registra X e os argumentos de cada `CatBoostClassifier.fit` (sem mudar o comportamento)."""
    registros: list[tuple[pd.DataFrame, dict]] = []
    original = CatBoostClassifier.fit

    def espiao(self, X, y=None, **kwargs):
        registros.append((X, kwargs))
        return original(self, X, y, **kwargs)

    monkeypatch.setattr(CatBoostClassifier, "fit", espiao)
    return registros


def _espiar_predict_proba(monkeypatch) -> list[dict]:
    """Registra os argumentos de cada `CatBoostClassifier.predict_proba` (sem mudar o resultado)."""
    chamadas: list[dict] = []
    original = CatBoostClassifier.predict_proba

    def espiao(self, X, **kwargs):
        chamadas.append(kwargs)
        return original(self, X, **kwargs)

    monkeypatch.setattr(CatBoostClassifier, "predict_proba", espiao)
    return chamadas


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
    assert cv.REGISTRO["catboost"] is construir_catboost
    modelo = cv.construir_modelo("catboost", PARAMS, cfg_teste())
    assert isinstance(modelo, CatBoostM1)
    assert modelo.iterativo is True
    assert modelo.melhor_ponto() is None


def test_cada_construcao_devolve_objeto_novo():
    a = cv.construir_modelo("catboost", PARAMS, cfg_teste())
    b = cv.construir_modelo("catboost", PARAMS, cfg_teste())
    assert a is not b


def test_semente_vem_do_config():
    modelo = construir_catboost(PARAMS, {"seed": 123})
    assert modelo._estimador.get_params()["random_seed"] == 123  # R8


def test_metrica_de_parada_e_a_do_config():
    modelo = CatBoostM1(PARAMS, seed=7)
    assert modelo._estimador.get_params()["eval_metric"] == "PRAUC"


def test_nao_escreve_arquivos_do_catboost():
    modelo = CatBoostM1(PARAMS, seed=7)
    assert modelo._estimador.get_params()["allow_writing_files"] is False  # sem catboost_info/


@pytest.mark.parametrize("chave", ["auto_class_weights", "class_weights", "scale_pos_weight"])
def test_parametro_de_peso_de_classe_e_recusado_na_construcao(chave):
    with pytest.raises(ValueError, match="R3"):
        CatBoostM1({**PARAMS, chave: "Balanced"}, seed=7)


@pytest.mark.parametrize("params", [
    {k: v for k, v in PARAMS.items() if k != "od_wait"},
    {**PARAMS, "od_type": "IncToDec"},
])
def test_parada_sem_od_iter_e_recusada(params):
    with pytest.raises(ValueError, match="R6"):
        CatBoostM1(params, seed=7)


def test_device_invalido_e_recusado():
    with pytest.raises(ValueError, match="device"):
        CatBoostM1({**PARAMS, "device": "tpu"}, seed=7)


def test_ajustar_sem_validacao_interna_levanta():
    df = frame()
    with pytest.raises(ValueError, match="R6"):
        CatBoostM1(PARAMS, seed=7).ajustar(df, df["y"])


def test_ajustar_recusa_ano_de_teste_no_treino_e_na_parada():
    df = frame()
    df_teste = df.copy()
    df_teste.loc[0, "ANO"] = 2024  # R1
    with pytest.raises(RuntimeError, match="teste congelado"):
        CatBoostM1(PARAMS, seed=7).ajustar(df_teste, df_teste["y"], df.iloc[:50], df["y"].iloc[:50])
    with pytest.raises(RuntimeError, match="teste congelado"):
        CatBoostM1(PARAMS, seed=7).ajustar(df, df["y"], df_teste.iloc[:50], df["y"].iloc[:50])


def test_prever_antes_de_ajustar_levanta():
    with pytest.raises(RuntimeError, match="ajustar"):
        CatBoostM1(PARAMS, seed=7).prever_proba(frame())


def test_prever_recusa_ano_de_teste():
    modelo = _ajustado(frame())
    with pytest.raises(RuntimeError, match="teste congelado"):
        modelo.prever_proba(frame(ano=2024))


def test_config_real_monta_o_modelo():
    """Os `fixos` e a 1ª tentativa de `busca.catboost` do config montam o modelo sem erro."""
    cfg = load_config()
    espaco = load_search_space(cfg)["catboost"]
    modelo = CatBoostM1({**espaco.fixos, **espaco.primeira_tentativa, "device": "cpu"},
                        seed=cfg["seed"])
    params = modelo._estimador.get_params()
    assert params["iterations"] == 3000
    assert params["od_type"] == "Iter" and params["od_wait"] == 50
    assert params["eval_metric"] == "PRAUC"
    assert params["learning_rate"] == 0.05
    assert params["depth"] == 6


# --- Dispositivo ------------------------------------------------------------------------------

def test_device_cpu_vai_ao_estimador():
    modelo = CatBoostM1({**PARAMS, "device": "cpu"}, seed=7)
    assert modelo._estimador.get_params()["task_type"] == "CPU"
    assert modelo._dispositivo == "cpu"


def test_device_gpu_vira_task_type_gpu_sem_treinar():
    modelo = CatBoostM1({**PARAMS, "device": "gpu"}, seed=7)
    assert modelo._estimador.get_params()["task_type"] == "GPU"
    assert modelo._dispositivo == "gpu"


def test_sem_device_usa_a_deteccao(monkeypatch):
    monkeypatch.setattr(catboost_m1, "detectar_dispositivo", lambda: "gpu")
    params = {k: v for k, v in PARAMS.items() if k != "device"}
    modelo = CatBoostM1(params, seed=7)
    assert modelo._estimador.get_params()["task_type"] == "GPU"


def test_deteccao_devolve_cpu_ou_gpu_e_fica_em_cache():
    primeira = catboost_m1.detectar_dispositivo()
    assert primeira in {"cpu", "gpu"}
    assert catboost_m1.detectar_dispositivo() == primeira


def test_gpu_que_recusa_o_treino_cai_para_cpu_com_aviso(monkeypatch):
    def recusa():
        raise CatBoostError("GPU indisponível (teste)")

    monkeypatch.setattr(catboost_m1, "_treino_gpu_de_teste", recusa)
    # __wrapped__ pula o cache do lru_cache, para o teste não depender de chamadas anteriores.
    with pytest.warns(UserWarning, match="usando CPU"):
        assert catboost_m1.detectar_dispositivo.__wrapped__() == "cpu"


def test_gpu_que_treina_com_prauc_vira_gpu(monkeypatch):
    monkeypatch.setattr(catboost_m1, "_treino_gpu_de_teste", lambda: None)
    assert catboost_m1.detectar_dispositivo.__wrapped__() == "gpu"


def test_erro_que_nao_e_do_catboost_se_propaga_sem_virar_cpu(monkeypatch):
    """Só CatBoostError cai para CPU. Um bug (RuntimeError) tem de estourar, sem aviso falso."""
    def bug():
        raise RuntimeError("bug")

    monkeypatch.setattr(catboost_m1, "_treino_gpu_de_teste", bug)
    with warnings.catch_warnings(record=True) as avisos:
        warnings.simplefilter("always")
        with pytest.raises(RuntimeError, match="bug"):
            catboost_m1.detectar_dispositivo.__wrapped__()
    assert not avisos


# --- Parada antecipada, pré-processamento e validação interna (R5, R6) -----------------------

def test_parada_usa_so_a_validacao_interna(monkeypatch):
    df = frame()
    treino, parada = df.iloc[:400], df.iloc[400:500]
    registros = _espiar_fit(monkeypatch)
    modelo = CatBoostM1(PARAMS, seed=7)
    modelo.ajustar(treino, treino["y"], parada, parada["y"])

    X_fit, args = registros[-1]
    assert len(X_fit) == len(treino)  # o ajuste não vê a validação interna
    X_eval, y_eval = args["eval_set"]
    pre = modelo._pipeline.named_steps["preprocessamento"]
    assert X_eval.equals(pre.transform(parada))  # validação transformada com o treino
    assert np.array_equal(y_eval, parada["y"].to_numpy())


def test_pre_processador_so_ajusta_com_o_treino(monkeypatch):
    df = frame()
    treino, parada = df.iloc[:400], df.iloc[400:500]
    linhas = _espiar_fit_transform(monkeypatch)
    CatBoostM1(PARAMS, seed=7).ajustar(treino, treino["y"], parada, parada["y"])
    assert linhas == [len(treino)]  # R5: o ajuste do pré-processador nunca viu a parada


def test_categoricas_vao_como_cat_features(monkeypatch):
    df = frame()
    registros = _espiar_fit(monkeypatch)
    _ajustado(df)
    _, args = registros[-1]
    assert args["cat_features"] == list(range(len(CATEGORICAS_CATBOOST)))  # categóricas primeiro
    pre = _ajustado(df)._pipeline.named_steps["preprocessamento"]
    assert args["cat_features"] == indices_cat_features_catboost(pre)


def test_pipeline_usa_a_familia_catboost_sem_peso_de_classe():
    modelo = CatBoostM1(PARAMS, seed=7)
    assert "preprocessamento" in modelo._pipeline.named_steps  # R5
    assert modelo._estimador.get_params().get("class_weights") is None  # R3


# --- Predição, melhor ponto e determinismo ----------------------------------------------------

def test_melhor_ponto_e_inteiro_e_nao_passa_do_teto():
    modelo = _ajustado(frame())
    melhor = modelo.melhor_ponto()
    assert isinstance(melhor, int)
    assert 0 <= melhor <= PARAMS["iterations"]


def test_predicao_corta_as_arvores_no_melhor_ponto_de_forma_explicita(monkeypatch):
    """O espião prova que a predição pede `ntree_end = melhor + 1` (e não o padrão)."""
    df = frame()
    modelo = _ajustado(df)
    melhor = modelo.melhor_ponto()
    chamadas = _espiar_predict_proba(monkeypatch)
    modelo.prever_proba(df.iloc[500:])
    assert chamadas == [{"ntree_end": melhor + 1}]


def test_corte_no_melhor_ponto_separa_as_arvores_de_sobra(monkeypatch):
    """Sem a poda do `use_best_model`, o modelo guarda árvores depois do melhor ponto. O corte
    explícito tem de deixá-las de fora: a predição muda em relação ao modelo inteiro."""
    df = frame()
    modelo = CatBoostM1({**PARAMS, "use_best_model": False}, seed=7)
    modelo.ajustar(df.iloc[:400], df["y"].iloc[:400], df.iloc[400:500], df["y"].iloc[400:500])
    melhor = modelo.melhor_ponto()
    assert modelo._estimador.tree_count_ > melhor + 1  # a parada de fato aconteceu

    X_teste = df.iloc[500:]
    ate_melhor = modelo.prever_proba(X_teste)
    X_t = modelo._pipeline.named_steps["preprocessamento"].transform(X_teste)
    com_todas = modelo._estimador.predict_proba(X_t)[:, 1]
    assert not np.allclose(com_todas, ate_melhor)


def test_probabilidades_uma_por_linha_em_zero_um():
    df = frame()
    modelo = _ajustado(df)
    p = modelo.prever_proba(df.iloc[500:])
    assert p.shape == (len(df) - 500,)
    assert np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()


def test_laco_completo_uma_predicao_por_linha_e_melhor_ponto_no_teto():
    df = frame()
    resultado = cv.run_loro(cfg_teste(), "catboost", PARAMS, df)
    assert len(resultado["oof"]) == len(df)
    assert sorted(resultado["posicoes"].tolist()) == list(range(len(df)))
    p = resultado["oof"]["p"].to_numpy()
    assert np.isfinite(p).all() and (p >= 0).all() and (p <= 1).all()
    assert set(resultado["melhores_pontos"]) == set(ORDEM)
    for melhor in resultado["melhores_pontos"].values():
        assert isinstance(melhor, int) and 0 <= melhor <= PARAMS["iterations"]


def test_laco_cria_um_modelo_novo_por_dobra(monkeypatch):
    criados: list[CatBoostM1] = []

    def gravar(params, cfg):
        modelo = construir_catboost(params, cfg)
        criados.append(modelo)
        return modelo

    monkeypatch.setitem(cv.REGISTRO, "catboost", gravar)
    cv.run_loro(cfg_teste(), "catboost", PARAMS, frame())
    assert len(criados) == len(ORDEM)
    assert len({id(m) for m in criados}) == len(ORDEM)


def test_mesma_semente_mesmas_probabilidades_bit_a_bit():
    df = frame()
    a = cv.run_loro(cfg_teste(), "catboost", PARAMS, df)
    b = cv.run_loro(cfg_teste(), "catboost", PARAMS, df)
    assert np.array_equal(a["oof"]["p"].to_numpy(), b["oof"]["p"].to_numpy())
    assert a["melhores_pontos"] == b["melhores_pontos"]


def test_outra_semente_muda_as_probabilidades():
    df = frame()
    a = cv.run_loro(cfg_teste(), "catboost", PARAMS, df)
    b = cv.run_loro({**cfg_teste(), "seed": 99}, "catboost", PARAMS, df)
    assert not np.array_equal(a["oof"]["p"].to_numpy(), b["oof"]["p"].to_numpy())


def test_nao_cria_catboost_info_no_diretorio_de_trabalho(tmp_path, monkeypatch):
    """Sem `allow_writing_files=False` o CatBoost cria `catboost_info/` aqui. Nada deve aparecer."""
    monkeypatch.chdir(tmp_path)
    df = frame()
    modelo = CatBoostM1(PARAMS, seed=7)
    modelo.ajustar(df.iloc[:400], df["y"].iloc[:400], df.iloc[400:500], df["y"].iloc[400:500])
    modelo.prever_proba(df.iloc[500:])
    assert list(tmp_path.iterdir()) == []


# --- MLflow: dispositivo e melhor iteração ----------------------------------------------------

def test_dispositivo_e_melhor_iteracao_ficam_no_mlflow(tmp_path):
    base = load_config()
    cfg = {**base, "ordem_dobras": ORDEM, "seed": 7,
           "caminhos": {**base["caminhos"], "dados": str(tmp_path / "data"),
                        "mlruns": str(tmp_path / "mlruns")}}
    df = frame()
    with tracking.start_run(cfg, "teste-cb") as run:
        # 3 dobras no mesmo run: o parâmetro de dispositivo é o mesmo em todas, sem erro.
        cv.run_loro(cfg, "catboost", PARAMS, df)
        id_run = run.info.run_id
    client = MlflowClient(tracking_uri=str(tmp_path / "mlruns"))
    dados = client.get_run(id_run).data
    assert dados.params[catboost_m1.PARAM_MLFLOW_DISPOSITIVO] == "cpu"
    assert catboost_m1.METRICA_MLFLOW_MELHOR in dados.metrics
