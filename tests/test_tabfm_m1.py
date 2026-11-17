"""Testes do TabFM do M1 (T-4.7) com um duplo falso do pacote `tabfm` (sem a biblioteca real).

O pacote real só roda no Colab (D-69). Aqui `_carregar_pacote` e `_commit_instalado` são trocados
por um classificador falso que guarda o que recebe no `fit` e prevê a partir de uma coluna. MLflow
e `mlruns/` ficam numa pasta temporária.
"""

import sys
import types

import numpy as np
import pandas as pd
import pytest
from mlflow.tracking import MlflowClient
from sklearn.base import BaseEstimator

from dengue_sinan import cv, tabfm_m1, tracking
from dengue_sinan.config import load_config
from dengue_sinan.preprocess import make_preprocessor
from dengue_sinan.profiling import COMORBIDADES, SINAIS
from dengue_sinan.tabfm_m1 import (
    TabFMM1,
    construir_tabfm,
    detectar_dispositivo,
    subamostra_estratificada,
)

ORDEM = ["A", "B", "C"]
N_POR_REGIAO = 200
COMMIT = "0123456789abcdef0123456789abcdef01234567"  # 40 hex: o commit do fake
ALIAS = "tabfm_v1_0_0_pytorch"


def cfg_teste(max_num_rows: int = 100, n_estimators=None) -> dict:
    """Config mínimo do laço, com o bloco `tabfm` de teste (o commit é o do fake)."""
    return {
        "ordem_dobras": ORDEM, "seed": 7, "validacao_interna_frac": 0.2, "ano_teste": 2024,
        "tabfm": {"commit_pacote": COMMIT, "alias_pesos": ALIAS,
                  "max_num_rows": max_num_rows, "n_estimators": n_estimators},
    }


def frame(n_por_regiao: int = N_POR_REGIAO, ano: int = 2022, seed: int = 3) -> pd.DataFrame:
    """Casos com as features da família "arvore" e alvo com exatamente 30% de positivos.

    `idade_anos` é única por linha (0, 1, 2...): assim o contexto que o fake recebe identifica
    as linhas de treino de que saiu.
    """
    rng = np.random.default_rng(seed)
    n = n_por_regiao * len(ORDEM)
    df = pd.DataFrame({
        "ANO": np.full(n, ano, dtype="int64"),
        "regiao": np.repeat(ORDEM, n_por_regiao),
        "idade_anos": np.arange(n, dtype=float),
        "sexo": rng.choice(["F", "M", "I"], n),
        "gestante": rng.integers(0, 2, n).astype("int8"),
        "dias_ate_notificacao": rng.integers(0, 60, n),
    })
    for c in [*COMORBIDADES, *SINAIS]:
        df[c] = rng.choice(["Sim", "Não", "Ausente"], n, p=[0.2, 0.7, 0.1])
    df["n_comorbidades"] = sum((df[c] == "Sim").astype(int) for c in COMORBIDADES)
    y = np.zeros(n, dtype="int64")
    y[: n * 3 // 10] = 1
    rng.shuffle(y)
    df["y"] = y
    return df.reset_index(drop=True)


def _coluna_idade() -> int:
    """Posição da `idade_anos` na saída do pré-processador "arvore" (a mesma que o fake lê)."""
    pre = make_preprocessor("arvore").fit(frame())
    nomes = list(pre.get_feature_names_out())
    return next(i for i, nome in enumerate(nomes) if nome.endswith("idade_anos"))


class Gravacoes:
    """O que o fake viu: cada `fit` (contexto e kwargs) e cada chamada de predição."""

    def __init__(self) -> None:
        self.fits: list[dict] = []
        self.predicoes: list[int] = []


@pytest.fixture
def pacote_falso(monkeypatch):
    col_idade = _coluna_idade()
    gravacoes = Gravacoes()

    class ClassificadorFalso(BaseEstimator):  # sklearn-compatível, como o TabFMClassifier (FAQ)
        def __init__(self, model=None, max_num_rows=None, n_estimators=None):
            self.model = model
            self.max_num_rows = max_num_rows
            self.n_estimators = n_estimators

        def fit(self, X, y):  # sem kwargs: nenhum peso de classe chega aqui (R3)
            gravacoes.fits.append({
                "X": np.asarray(X).copy(), "y": np.asarray(y).copy(),
                "max_num_rows": self.max_num_rows, "n_estimators": self.n_estimators,
                "model": self.model,
            })
            self.classes_ = np.unique(y)
            return self

        def predict_proba(self, X):
            X = np.asarray(X)
            gravacoes.predicoes.append(len(X))
            p = np.clip(X[:, col_idade] / 1000.0, 0.0, 1.0)
            return np.column_stack([1.0 - p, p])

    pacote = types.SimpleNamespace(TabFMClassifier=ClassificadorFalso)
    pesos = types.SimpleNamespace(load=lambda: "pesos-falsos")
    monkeypatch.setattr(tabfm_m1, "_carregar_pacote", lambda alias, commit: (pacote, pesos))
    monkeypatch.setattr(tabfm_m1, "_commit_instalado", lambda: COMMIT)
    gravacoes.col_idade = col_idade
    return gravacoes


# --- Registro e contrato ------------------------------------------------------------------------

def test_registrado_no_registro_e_sem_busca_nem_parada():
    assert cv.REGISTRO["tabfm"] is construir_tabfm
    modelo = cv.construir_modelo("tabfm", {}, cfg_teste())
    assert isinstance(modelo, TabFMM1)
    assert modelo.iterativo is False  # R6 não se aplica: sem parada
    assert modelo.melhor_ponto() is None


def test_config_real_tem_commit_fixo_alias_e_limite():
    tab = load_config()["tabfm"]
    assert isinstance(tab["max_num_rows"], int) and tab["max_num_rows"] >= 1  # valor: base.yaml
    assert tabfm_m1.COMMIT_RE.fullmatch(tab["commit_pacote"])  # D-90: SHA completo
    assert tab["alias_pesos"] == "tabfm_v1_0_0_pytorch"  # D-90: 1.0.0, não 1.1.0
    assert "n_estimators" in tab


@pytest.mark.parametrize("commit", [
    "1.0.1", "fbb6655", "FBB665569425FD2F490C6576B3AF967876FE11FF", "g" * 40, 1234, None,
])
def test_commit_pacote_precisa_ser_sha_completo(commit):
    bloco = {**cfg_teste()["tabfm"], "commit_pacote": commit}
    with pytest.raises(ValueError, match="commit_pacote"):
        TabFMM1({}, bloco, seed=7)


def test_commit_do_config_sem_a_chave_e_recusado():
    bloco = {k: v for k, v in cfg_teste()["tabfm"].items() if k != "commit_pacote"}
    with pytest.raises(ValueError, match="commit_pacote"):
        TabFMM1({}, bloco, seed=7)


class _DistribuicaoFalsa:
    def __init__(self, direct_url):
        self._direct_url = direct_url

    def read_text(self, nome):
        assert nome == "direct_url.json"
        return self._direct_url


def test_commit_instalado_le_o_direct_url_do_pip(monkeypatch):
    texto = ('{"url": "https://github.com/google-research/tabfm.git", '
             f'"vcs_info": {{"commit_id": "{COMMIT}", "vcs": "git"}}}}')
    monkeypatch.setattr(tabfm_m1.importlib.metadata, "distribution",
                        lambda nome: _DistribuicaoFalsa(texto))
    assert tabfm_m1._commit_instalado() == COMMIT


def test_commit_instalado_e_none_quando_nao_veio_de_git(monkeypatch):
    # instalado do PyPI: sem direct_url.json, ou com origem que não é git
    monkeypatch.setattr(tabfm_m1.importlib.metadata, "distribution",
                        lambda nome: _DistribuicaoFalsa(None))
    assert tabfm_m1._commit_instalado() is None
    monkeypatch.setattr(tabfm_m1.importlib.metadata, "distribution",
                        lambda nome: _DistribuicaoFalsa('{"dir_info": {"editable": true}}'))
    assert tabfm_m1._commit_instalado() is None


def test_pacote_sem_metadados_recusa_com_mensagem(monkeypatch):
    def sem_pacote(nome):
        raise tabfm_m1.importlib.metadata.PackageNotFoundError(nome)
    monkeypatch.setattr(tabfm_m1.importlib.metadata, "distribution", sem_pacote)
    with pytest.raises(RuntimeError, match="não instalado"):
        tabfm_m1._commit_instalado()


def test_alias_e_atributo_do_pacote_e_nao_submodulo(monkeypatch):
    pesos = types.SimpleNamespace(load=lambda: "pesos")
    pacote = types.ModuleType("tabfm")
    setattr(pacote, ALIAS, pesos)
    monkeypatch.setitem(sys.modules, "tabfm", pacote)
    assert tabfm_m1._carregar_pacote(ALIAS, COMMIT) == (pacote, pesos)


def test_alias_ausente_recusa_dizendo_o_commit(monkeypatch):
    monkeypatch.setitem(sys.modules, "tabfm", types.ModuleType("tabfm"))  # sem o atributo
    with pytest.raises(RuntimeError, match="tabfm_v1_1_0_pytorch") as erro:
        tabfm_m1._carregar_pacote("tabfm_v1_1_0_pytorch", COMMIT)
    assert COMMIT in str(erro.value)
    assert "--no-deps" in str(erro.value)


def test_construir_sem_bloco_tabfm_recusa():
    with pytest.raises(ValueError, match="tabfm"):
        construir_tabfm({}, {"seed": 7})


def test_hiperparametros_sao_recusados():
    with pytest.raises(ValueError, match="sem_busca"):
        TabFMM1({"n_estimators": 3}, cfg_teste()["tabfm"], seed=7)


@pytest.mark.parametrize("ajuste", [
    {"max_num_rows": 0}, {"max_num_rows": True}, {"max_num_rows": "100"},
    {"n_estimators": 0}, {"n_estimators": "3"},
])
def test_valores_invalidos_no_config_sao_recusados(ajuste):
    bloco = {**cfg_teste()["tabfm"], **ajuste}
    with pytest.raises(ValueError):
        TabFMM1({}, bloco, seed=7)


def test_chave_faltando_no_config_e_recusada():
    bloco = {k: v for k, v in cfg_teste()["tabfm"].items() if k != "alias_pesos"}
    with pytest.raises(ValueError, match="alias_pesos"):
        TabFMM1({}, bloco, seed=7)


def test_ajustar_recusa_validacao_de_parada(pacote_falso):
    df = frame()
    modelo = TabFMM1({}, cfg_teste()["tabfm"], seed=7)
    with pytest.raises(ValueError, match="parada"):
        modelo.ajustar(df, df["y"], df.iloc[:50], df["y"].iloc[:50])


def test_prever_antes_de_ajustar_levanta(pacote_falso):
    with pytest.raises(RuntimeError, match="ajustar"):
        TabFMM1({}, cfg_teste()["tabfm"], seed=7).prever_proba(frame())


# --- Pacote ausente e versão fixa ---------------------------------------------------------------

def test_sem_pacote_instalado_recusa_com_instrucao_util(monkeypatch):
    monkeypatch.setitem(sys.modules, "tabfm", None)  # `import tabfm` levanta ImportError
    df = frame()
    modelo = TabFMM1({}, cfg_teste()["tabfm"], seed=7)
    with pytest.raises(RuntimeError, match="pip install") as erro:
        modelo.ajustar(df, df["y"])
    assert "D-69" in str(erro.value)
    assert "Colab" in str(erro.value)


def test_commit_instalado_diferente_do_config_recusa(pacote_falso, monkeypatch):
    monkeypatch.setattr(tabfm_m1, "_commit_instalado", lambda: "f" * 40)
    df = frame()
    with pytest.raises(RuntimeError, match="commit fixo"):
        TabFMM1({}, cfg_teste()["tabfm"], seed=7).ajustar(df, df["y"])


# --- Contexto: subamostra estratificada ---------------------------------------------------------

def test_subamostra_proporcional_ao_alvo():
    y = np.zeros(1000, dtype="int64")
    y[:300] = 1
    pos = subamostra_estratificada(y, 100, seed=7)
    assert pos.size == 100
    assert np.all(np.diff(pos) > 0)  # ordenada e sem repetição
    assert (y[pos] == 1).sum() == 30  # 30% de 100
    assert (y[pos] == 0).sum() == 70


def test_subamostra_devolve_tudo_quando_cabe():
    y = np.array([0, 1, 0, 1, 0])
    assert np.array_equal(subamostra_estratificada(y, 10, seed=7), np.arange(5))


def test_subamostra_e_determinista_com_a_semente_e_muda_com_ela():
    y = np.zeros(5000, dtype="int64")
    y[:1500] = 1
    a = subamostra_estratificada(y, 200, seed=7)
    b = subamostra_estratificada(y, 200, seed=7)
    c = subamostra_estratificada(y, 200, seed=8)
    assert np.array_equal(a, b)  # R8
    assert not np.array_equal(a, c)


def test_contexto_com_um_positivo_em_mil_fica_sem_positivo_e_isso_e_registrado():
    """Prevalência natural (P5, sem R3): 1 positivo em 1.000 não entra no contexto de 100 linhas.

    É o efeito esperado da proporção, não um bug; o Registro da T-4.7 traz a decisão pendente.
    """
    y = np.zeros(1000, dtype="int64")
    y[0] = 1
    pos = subamostra_estratificada(y, 100, seed=7)
    assert pos.size == 100
    assert (y[pos] == 1).sum() == 0


def test_subamostra_recusa_tamanho_zero():
    with pytest.raises(ValueError, match="pelo menos 1"):
        subamostra_estratificada(np.array([0, 1]), 0, seed=7)


def test_ajustar_so_com_contexto_do_treino_no_tamanho_certo(pacote_falso):
    df = frame()
    treino = df.iloc[:400]  # só as 2 primeiras regiões: a 3ª fica fora da dobra
    validacao = df.iloc[400:]
    modelo = TabFMM1({}, cfg_teste(max_num_rows=100)["tabfm"], seed=7)
    modelo.ajustar(treino, treino["y"])

    (ajuste,) = pacote_falso.fits
    assert ajuste["max_num_rows"] == 100
    assert ajuste["X"].shape[0] == 100  # contexto no tamanho do limite
    assert ajuste["model"] == "pesos-falsos"
    idades_contexto = set(ajuste["X"][:, pacote_falso.col_idade].astype(int))
    idades_treino = set(treino["idade_anos"].astype(int))
    idades_validacao = set(validacao["idade_anos"].astype(int))
    assert idades_contexto <= idades_treino  # só linhas do treino da dobra
    assert idades_contexto.isdisjoint(idades_validacao)  # nunca a região de fora
    assert modelo.contexto_linhas_ == 100
    # proporção do treino da dobra (o alvo não é exato nessas 400 linhas): ±1 pelo arredondamento
    assert abs(modelo.contexto_positivos_ - 100 * treino["y"].mean()) <= 1


def test_rotulo_de_cada_linha_do_contexto_e_o_real(pacote_falso):
    """Alinhamento X e y: `idade_anos` é única por linha, então o rótulo real de cada linha do
    contexto é `df.loc[idade, "y"]`; o y que o fake recebeu tem que ser esse, na mesma ordem."""
    df = frame()
    treino = df.iloc[:400]
    modelo = TabFMM1({}, cfg_teste()["tabfm"], seed=7)
    modelo.ajustar(treino, treino["y"])
    (ajuste,) = pacote_falso.fits
    idades = ajuste["X"][:, pacote_falso.col_idade].astype(int)
    rotulos_reais = df.loc[idades, "y"].to_numpy()
    assert np.array_equal(rotulos_reais, ajuste["y"])


def test_estratificacao_do_contexto_bate_com_o_alvo_do_treino(pacote_falso):
    df = frame()
    modelo = TabFMM1({}, cfg_teste(max_num_rows=100)["tabfm"], seed=7)
    modelo.ajustar(df, df["y"])
    (ajuste,) = pacote_falso.fits
    assert (ajuste["y"] == 1).sum() == 30
    assert (ajuste["y"] == 0).sum() == 70


def test_n_estimators_so_vai_ao_pacote_quando_configurado(pacote_falso):
    df = frame()
    TabFMM1({}, cfg_teste()["tabfm"], seed=7).ajustar(df, df["y"])
    TabFMM1({}, cfg_teste(n_estimators=4)["tabfm"], seed=7).ajustar(df, df["y"])
    padrao, configurado = pacote_falso.fits
    assert padrao["n_estimators"] is None  # null: padrão do pacote
    assert configurado["n_estimators"] == 4


def test_ajuste_nao_recebe_peso_de_classe(pacote_falso):
    """R3: o `fit` falso não aceita kwargs; o ajuste roda e nenhum peso chega a ele."""
    df = frame()
    TabFMM1({}, cfg_teste()["tabfm"], seed=7).ajustar(df, df["y"])
    assert len(pacote_falso.fits) == 1


# --- Predição -----------------------------------------------------------------------------------

def test_uma_predicao_por_linha_em_blocos_e_na_ordem(pacote_falso, monkeypatch):
    monkeypatch.setattr(tabfm_m1, "TAMANHO_BLOCO_PREDICAO", 7)
    df = frame()
    modelo = TabFMM1({}, cfg_teste()["tabfm"], seed=7)
    modelo.ajustar(df.iloc[:400], df["y"].iloc[:400])
    X = df.iloc[400:425]  # 25 linhas, blocos de 7 -> 4 chamadas (7, 7, 7, 4)
    p = modelo.prever_proba(X)
    assert p.shape == (25,)
    assert pacote_falso.predicoes == [7, 7, 7, 4]
    assert np.allclose(p, X["idade_anos"].to_numpy() / 1000.0)  # ordem preservada
    assert np.all((p >= 0) & (p <= 1))


def test_probabilidade_fora_de_0_1_e_recusada(pacote_falso, monkeypatch):
    df = frame()
    modelo = TabFMM1({}, cfg_teste()["tabfm"], seed=7)
    modelo.ajustar(df.iloc[:400], df["y"].iloc[:400])
    monkeypatch.setattr(type(modelo._pipeline.named_steps["tabfm"]), "predict_proba",
                        lambda self, X: np.column_stack([np.zeros(len(X)), np.full(len(X), 1.5)]))
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        modelo.prever_proba(df.iloc[400:410])


# --- R1 -----------------------------------------------------------------------------------------

def test_recusa_ano_de_teste_no_treino_e_na_predicao(pacote_falso):
    df = frame()
    df_teste = df.copy()
    df_teste.loc[0, "ANO"] = 2024  # R1
    with pytest.raises(RuntimeError, match="teste congelado"):
        TabFMM1({}, cfg_teste()["tabfm"], seed=7).ajustar(df_teste, df_teste["y"])
    modelo = TabFMM1({}, cfg_teste()["tabfm"], seed=7)
    modelo.ajustar(df, df["y"])
    with pytest.raises(RuntimeError, match="teste congelado"):
        modelo.prever_proba(df_teste)


# --- Laço e MLflow ------------------------------------------------------------------------------

def test_laco_leave_one_region_out_roda_com_o_contrato(pacote_falso):
    df = frame()
    res = cv.run_loro(cfg_teste(max_num_rows=50), "tabfm", {}, df)
    assert len(pacote_falso.fits) == 3  # uma dobra por região
    assert all(ajuste["X"].shape[0] == 50 for ajuste in pacote_falso.fits)
    assert res["melhores_pontos"] == {"A": None, "B": None, "C": None}
    assert len(res["oof"]) == len(df)  # uma predição por linha, uma vez cada
    assert res["oof"]["p"].between(0, 1).all()


def test_versao_contexto_e_dispositivo_ficam_no_mlflow(tmp_path, pacote_falso):
    base = load_config()
    cfg = {**base, "seed": 7,
           "caminhos": {**base["caminhos"], "dados": str(tmp_path / "data"),
                        "mlruns": str(tmp_path / "mlruns")}}
    df = frame()
    # config próprio: o contexto de 100 linhas cabe no frame de teste (600 linhas)
    bloco = cfg_teste(max_num_rows=100)["tabfm"]
    with tracking.start_run(cfg, "teste-tabfm") as run:
        # Duas dobras no mesmo run: os valores são os mesmos, sem erro de parâmetro repetido.
        TabFMM1({}, bloco, seed=7).ajustar(df.iloc[:1000], df["y"].iloc[:1000])
        TabFMM1({}, bloco, seed=7).ajustar(df.iloc[:1000], df["y"].iloc[:1000])
        id_run = run.info.run_id
    client = MlflowClient(tracking_uri=str(tmp_path / "mlruns"))
    dados = client.get_run(id_run).data
    assert dados.params[tabfm_m1.PARAM_MLFLOW_COMMIT] == COMMIT
    assert dados.params[tabfm_m1.PARAM_MLFLOW_MAX_LINHAS] == str(bloco["max_num_rows"])
    assert dados.params[tabfm_m1.PARAM_MLFLOW_N_ESTIMATORS] == "padrao_do_pacote"
    assert dados.params[tabfm_m1.PARAM_MLFLOW_DISPOSITIVO] in ("cpu", "cuda")
    assert dados.metrics[tabfm_m1.METRICA_MLFLOW_CONTEXTO] == bloco["max_num_rows"]
    assert dados.metrics[tabfm_m1.METRICA_MLFLOW_POSITIVOS] == 30


def test_detectar_dispositivo_devolve_cpu_ou_cuda():
    assert detectar_dispositivo() in ("cpu", "cuda")
