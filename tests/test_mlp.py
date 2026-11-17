"""Testes do MLP do M1 (T-4.6b) com dados sintéticos pequenos e redes pequenas (sem microdados).

Rápidos em CPU. MLflow e `mlruns/` ficam numa pasta temporária. A primeira chamada ao torch no
processo custa alguns segundos (carga preguiçosa dos módulos); as seguintes são rápidas.
"""

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp
import torch
from mlflow.tracking import MlflowClient
from sklearn.compose import ColumnTransformer
from sklearn.metrics import average_precision_score

from dengue_sinan import cv, mlp, tracking
from dengue_sinan.config import load_config
from dengue_sinan.mlp import (
    MLPM1,
    EstimadorMLP,
    camadas_de_rotulo,
    construir_mlp,
)
from dengue_sinan.profiling import COMORBIDADES, SINAIS

ORDEM = ["A", "B", "C"]
N_POR_REGIAO = 200
PARAMS = {
    "camadas_ocultas": "16", "dropout": 0.0, "weight_decay": 0.0, "lr": 0.01,
    "batch_size": 256, "epocas_max": 4, "paciencia_epocas": 2,
    "perda": "BCEWithLogitsLoss", "otimizador": "Adam", "device": "cpu",
}


def cfg_teste() -> dict:
    return {"ordem_dobras": ORDEM, "seed": 7, "validacao_interna_frac": 0.2, "ano_teste": 2024}


def frame(seed: int = 3, ano: int = 2022) -> pd.DataFrame:
    """Casos com as 26 features do dicionário e um sinal fraco em RENAL e DIABETES."""
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


def matriz_esparsa(n: int, d: int = 12, seed: int = 0, taxa_positivos: float = 0.2):
    """CSR float32 aleatória e rótulos com positivos e negativos (para o EstimadorMLP direto)."""
    rng = np.random.default_rng(seed)
    X = sp.random(n, d, density=0.4, format="csr", dtype=np.float32, random_state=seed)
    y = (rng.uniform(size=n) < taxa_positivos).astype(np.int64)
    return X, y


def espiar_linhas(monkeypatch) -> list:
    """Registra (objeto X, nº de linhas pedidas) de cada chamada a `mlp._linhas`."""
    chamadas: list = []
    original = mlp._linhas

    def espiao(X, sel):
        n = len(range(*sel.indices(X.shape[0]))) if isinstance(sel, slice) else len(sel)
        chamadas.append((X, n))
        return original(X, sel)

    monkeypatch.setattr(mlp, "_linhas", espiao)
    return chamadas


# --- Rótulos de camada ------------------------------------------------------------------------

@pytest.mark.parametrize("rotulo, esperado", [
    ("64", [64]), ("128", [128]), ("128x64", [128, 64]), ("32x16x8", [32, 16, 8]),
])
def test_rotulo_de_camada_vira_lista(rotulo, esperado):
    assert camadas_de_rotulo(rotulo) == esperado


@pytest.mark.parametrize(
    "rotulo", ["", "0", "64x0", "64x", "x64", "abc", "-4", "1_000", "64,32", 64])
def test_rotulo_de_camada_invalido_levanta(rotulo):
    with pytest.raises(ValueError, match="camadas_ocultas"):
        camadas_de_rotulo(rotulo)


# --- Registro, construção e recusas -----------------------------------------------------------

def test_registrado_no_registro_do_laco():
    assert cv.REGISTRO["mlp"] is construir_mlp
    m = cv.construir_modelo("mlp", PARAMS, cfg_teste())
    assert isinstance(m, MLPM1)
    assert m.iterativo is True
    assert m.melhor_ponto() is None


def test_cada_construcao_devolve_objeto_novo():
    a = cv.construir_modelo("mlp", PARAMS, cfg_teste())
    b = cv.construir_modelo("mlp", PARAMS, cfg_teste())
    assert a is not b
    assert a._estimador is not b._estimador


def test_semente_vem_do_config():
    assert construir_mlp(PARAMS, cfg_teste())._estimador.seed == 7


@pytest.mark.parametrize("chave", ["pos_weight", "class_weight"])
def test_peso_de_classe_e_recusado_na_construcao(chave):
    with pytest.raises(ValueError, match="R3"):
        MLPM1({**PARAMS, chave: 10.0}, seed=7)


def test_perda_diferente_de_bcewithlogits_e_recusada():
    with pytest.raises(ValueError, match="BCEWithLogitsLoss"):
        MLPM1({**PARAMS, "perda": "CrossEntropyLoss"}, seed=7)


def test_otimizador_diferente_de_adam_e_recusado():
    with pytest.raises(ValueError, match="Adam"):
        MLPM1({**PARAMS, "otimizador": "SGD"}, seed=7)


@pytest.mark.parametrize("apagar", ["lr", "epocas_max", "paciencia_epocas"])
def test_parametro_obrigatorio_faltando_e_recusado(apagar):
    sem = {k: v for k, v in PARAMS.items() if k != apagar}
    with pytest.raises(ValueError, match="faltam"):
        MLPM1(sem, seed=7)


def test_parametro_desconhecido_e_recusado():
    with pytest.raises(ValueError, match="sobram"):
        MLPM1({**PARAMS, "neuronios_extra": 3}, seed=7)


def test_device_invalido_e_recusado():
    with pytest.raises(ValueError, match="device"):
        MLPM1({**PARAMS, "device": "tpu"}, seed=7)


def test_cuda_sem_gpu_levanta_em_vez_de_trocar_em_silencio(monkeypatch):
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="cuda"):
        MLPM1({**PARAMS, "device": "cuda"}, seed=7)


def test_epocas_zero_e_recusado():
    with pytest.raises(ValueError, match="epocas_max"):
        MLPM1({**PARAMS, "epocas_max": 0}, seed=7)


def test_ajustar_sem_validacao_de_parada_levanta():
    df = frame()
    with pytest.raises(ValueError, match="R6"):
        MLPM1(PARAMS, seed=7).ajustar(df, df["y"].to_numpy())


def test_prever_antes_de_ajustar_levanta():
    with pytest.raises(RuntimeError):
        MLPM1(PARAMS, seed=7).prever_proba(frame())


def test_recusa_ano_de_teste_no_treino():
    df = frame()
    df_2024 = df.assign(ANO=2024)
    with pytest.raises(RuntimeError, match="R1"):
        MLPM1(PARAMS, seed=7).ajustar(df_2024, df["y"].to_numpy(), df, df["y"].to_numpy())


# --- Parada antecipada, melhores pesos e predição ---------------------------------------------

def test_para_no_early_stopping_com_paciencia_e_melhor_epoca_antes_do_teto():
    # Rótulos de validação independentes das features: a PR-AUC para de melhorar cedo.
    X, y = matriz_esparsa(900, seed=1, taxa_positivos=0.15)
    Xp, yp = matriz_esparsa(400, seed=2, taxa_positivos=0.15)
    e = EstimadorMLP(camadas=(16,), lr=0.01, batch_size=128, epocas_max=40,
                     paciencia_epocas=3, seed=7, dispositivo="cpu")
    e.fit(X, y, X_parada=Xp, y_parada=yp)
    treinadas = len(e.historico_)
    assert treinadas < 40, "deveria parar antes do teto de épocas"
    assert treinadas == e.melhor_epoca_ + 3, "para exatamente após a paciência"


def test_pesos_restaurados_sao_os_da_melhor_epoca():
    X, y = matriz_esparsa(900, seed=1, taxa_positivos=0.15)
    Xp, yp = matriz_esparsa(400, seed=2, taxa_positivos=0.15)
    e = EstimadorMLP(camadas=(16,), lr=0.01, batch_size=128, epocas_max=20,
                     paciencia_epocas=3, seed=7, dispositivo="cpu")
    e.fit(X, y, X_parada=Xp, y_parada=yp)
    pr_na_melhor = e.historico_[e.melhor_epoca_ - 1]["pr_auc_parada"]
    pr_restaurada = average_precision_score(yp, e.predict_proba(Xp)[:, 1])
    assert pr_restaurada == pytest.approx(pr_na_melhor, abs=1e-9)


def test_parada_usa_so_a_validacao_interna(monkeypatch):
    # Treino (X) e parada (Xp) são objetos diferentes: o treino só lê X, a parada só lê Xp.
    X, y = matriz_esparsa(600, seed=1)
    Xp, yp = matriz_esparsa(200, seed=2)
    chamadas = espiar_linhas(monkeypatch)
    e = EstimadorMLP(camadas=(8,), lr=0.01, batch_size=256, epocas_max=3,
                     paciencia_epocas=5, seed=7, dispositivo="cpu")
    e.fit(X, y, X_parada=Xp, y_parada=yp)
    objetos = {id(obj) for obj, _ in chamadas}
    assert objetos == {id(X), id(Xp)}
    epocas = len(e.historico_)
    chamadas_parada = [n for obj, n in chamadas if obj is Xp]
    assert len(chamadas_parada) == epocas  # uma leitura da validação interna por época
    assert all(n <= 200 for n in chamadas_parada)


def test_validacao_interna_sem_positivos_levanta():
    X, y = matriz_esparsa(200, seed=1)
    Xp, _ = matriz_esparsa(50, seed=2)
    with pytest.raises(ValueError, match="sem positivos"):
        EstimadorMLP(camadas=(8,), epocas_max=2, dispositivo="cpu").fit(
            X, y, X_parada=Xp, y_parada=np.zeros(50, dtype=int))


def test_perda_e_bcewithlogits_sem_pos_weight(monkeypatch):
    # R3: a perda é criada sem argumentos (nada de pos_weight), e a criação é espiada aqui.
    criados: list[dict] = []
    original = torch.nn.BCEWithLogitsLoss

    def espiao(*args, **kwargs):
        criados.append(dict(kwargs))
        return original(*args, **kwargs)

    monkeypatch.setattr(mlp.nn, "BCEWithLogitsLoss", espiao)
    X, y = matriz_esparsa(200, seed=1)
    Xp, yp = matriz_esparsa(60, seed=2)
    EstimadorMLP(camadas=(4,), epocas_max=1, paciencia_epocas=1, seed=7,
                 dispositivo="cpu").fit(X, y, X_parada=Xp, y_parada=yp)
    assert criados == [{}]


def test_probabilidades_uma_por_linha_em_zero_um():
    df = frame()
    m = MLPM1(PARAMS, seed=7)
    m.ajustar(df.iloc[:400], df["y"].to_numpy()[:400], df.iloc[400:], df["y"].to_numpy()[400:])
    p = m.prever_proba(df)
    assert p.shape == (len(df),)
    assert np.isfinite(p).all()
    assert ((p >= 0) & (p <= 1)).all()


# --- Determinismo (R8) -------------------------------------------------------------------------

def test_mesma_semente_mesmas_probabilidades_bit_a_bit():
    X, y = matriz_esparsa(500, seed=1)
    Xp, yp = matriz_esparsa(200, seed=2)
    a = EstimadorMLP(camadas=(8,), lr=0.01, batch_size=128, epocas_max=3, paciencia_epocas=5,
                     seed=7, dispositivo="cpu")
    b = EstimadorMLP(camadas=(8,), lr=0.01, batch_size=128, epocas_max=3, paciencia_epocas=5,
                     seed=7, dispositivo="cpu")
    a.fit(X, y, X_parada=Xp, y_parada=yp)
    b.fit(X, y, X_parada=Xp, y_parada=yp)
    assert np.array_equal(a.predict_proba(Xp), b.predict_proba(Xp))


def test_outra_semente_muda_as_probabilidades():
    X, y = matriz_esparsa(500, seed=1)
    Xp, yp = matriz_esparsa(200, seed=2)
    kw = dict(camadas=(8,), lr=0.01, batch_size=128, epocas_max=3, paciencia_epocas=5,
              dispositivo="cpu")
    a = EstimadorMLP(seed=7, **kw).fit(X, y, X_parada=Xp, y_parada=yp)
    b = EstimadorMLP(seed=8, **kw).fit(X, y, X_parada=Xp, y_parada=yp)
    assert not np.array_equal(a.predict_proba(Xp), b.predict_proba(Xp))


def test_semente_do_torch_e_fixada_no_ajuste(monkeypatch):
    chamadas: list[int] = []
    original = torch.manual_seed

    def espiao(s):
        chamadas.append(int(s))
        return original(s)

    monkeypatch.setattr(torch, "manual_seed", espiao)
    X, y = matriz_esparsa(200, seed=1)
    Xp, yp = matriz_esparsa(60, seed=2)
    EstimadorMLP(camadas=(4,), epocas_max=1, paciencia_epocas=1, seed=7,
                 dispositivo="cpu").fit(X, y, X_parada=Xp, y_parada=yp)
    assert chamadas == [7]


# --- Memória: nunca densificar a matriz inteira ------------------------------------------------

def test_treino_converte_so_um_lote_por_vez_para_denso(monkeypatch):
    X, y = matriz_esparsa(3000, seed=1)
    Xp, yp = matriz_esparsa(300, seed=2)
    chamadas = espiar_linhas(monkeypatch)
    EstimadorMLP(camadas=(4,), lr=0.01, batch_size=1024, epocas_max=1, paciencia_epocas=1,
                 seed=7, dispositivo="cpu").fit(X, y, X_parada=Xp, y_parada=yp)
    treino = [n for obj, n in chamadas if obj is X]
    assert len(treino) == 3  # 1024 + 1024 + 952
    assert max(treino) <= 1024
    assert sum(treino) == 3000


def test_predicao_converte_em_blocos(monkeypatch):
    X, y = matriz_esparsa(600, seed=1)
    Xp, yp = matriz_esparsa(120, seed=2)
    e = EstimadorMLP(camadas=(4,), epocas_max=1, paciencia_epocas=1, seed=7,
                     dispositivo="cpu").fit(X, y, X_parada=Xp, y_parada=yp)
    monkeypatch.setattr(mlp, "TAMANHO_BLOCO_PREDICAO", 250)
    chamadas = espiar_linhas(monkeypatch)
    p = e.predict_proba(X)
    assert p.shape == (600, 2)
    assert [n for _, n in chamadas] == [250, 250, 100]


def test_linhas_devolve_denso_float32_so_das_linhas_pedidas():
    X, _ = matriz_esparsa(50, d=7, seed=3)
    bloco = mlp._linhas(X, np.array([4, 0, 9]))
    assert isinstance(bloco, np.ndarray)
    assert bloco.dtype == np.float32
    assert bloco.shape == (3, 7)
    assert np.array_equal(bloco, X[[4, 0, 9]].toarray())


# --- Laço completo, MLflow e um modelo novo por dobra -------------------------------------------

def test_laco_cria_um_modelo_novo_por_dobra_e_tem_melhor_epoca(monkeypatch):
    df = frame()
    criados: list[object] = []
    original = cv.REGISTRO["mlp"]

    def espiao(params, cfg):
        m = original(params, cfg)
        criados.append(m)
        return m

    monkeypatch.setitem(cv.REGISTRO, "mlp", espiao)
    resultado = cv.run_loro(cfg_teste(), "mlp", PARAMS, df)
    assert len(criados) == len(ORDEM)
    assert len({id(m) for m in criados}) == len(ORDEM)
    assert len(resultado["oof"]) == len(df)
    assert all(v is not None and 1 <= v <= PARAMS["epocas_max"]
               for v in resultado["melhores_pontos"].values())


def test_dispositivo_e_melhor_epoca_ficam_no_mlflow(tmp_path):
    base = load_config()
    cfg = {**base, "ordem_dobras": ORDEM, "seed": 7,
           "caminhos": {**base["caminhos"], "dados": str(tmp_path / "data"),
                        "mlruns": str(tmp_path / "mlruns")}}
    df = frame()
    with tracking.start_run(cfg, "teste-mlp") as run:
        cv.run_loro(cfg, "mlp", PARAMS, df)
        id_run = run.info.run_id
    dados = MlflowClient(tracking_uri=str(tmp_path / "mlruns")).get_run(id_run).data
    assert dados.params[mlp.PARAM_MLFLOW_DISPOSITIVO] == "cpu"
    assert mlp.METRICA_MLFLOW_MELHOR in dados.metrics


def test_recusa_ano_de_teste_na_validacao_de_parada():
    df = frame()
    m = MLPM1(PARAMS, seed=7)
    with pytest.raises(RuntimeError, match="R1"):
        m.ajustar(df.iloc[:300], df["y"].to_numpy()[:300],
                  df.iloc[300:400].assign(ANO=2024), df["y"].to_numpy()[300:400])


# --- Revisão da Sakura: validação transformada (R5), lotes densos (memória) e semente dos lotes ---

def test_validacao_e_transformada_e_nunca_reajustada(monkeypatch):
    # R5: o pré-processador ajusta uma única vez, só com o treino. A validação interna só é
    # transformada com esse ajuste; um fit_transform extra em X_parada vazaria a validação.
    df = frame()
    treino, parada = df.iloc[:400], df.iloc[400:]
    ajustes: list[int] = []
    original = ColumnTransformer.fit_transform

    def espiao(self, X, y=None, **kwargs):
        ajustes.append(len(X))
        return original(self, X, y, **kwargs)

    monkeypatch.setattr(ColumnTransformer, "fit_transform", espiao)
    MLPM1(PARAMS, seed=7).ajustar(
        treino, treino["y"].to_numpy(), parada, parada["y"].to_numpy())
    assert ajustes == [400]


def _guardada(X, limite: int):
    """CSR cujo `toarray` falha quando a matriz tem mais linhas que `limite`: pega densificação
    da matriz inteira (só o lote e o bloco de predição podem virar densos). O limite fica na
    classe, para que as fatias de `X[sel]` (também desta classe) herdem o mesmo limite."""

    def toarray(self, *args, **kwargs):
        if self.shape[0] > limite:
            raise AssertionError(
                f"matriz inteira densificada: {self.shape[0]} linhas > limite {limite}")
        return sp.csr_matrix.toarray(self, *args, **kwargs)

    classe = type("CsrGuardada", (sp.csr_matrix,), {"toarray": toarray})
    return classe(X)


def test_treino_nunca_densifica_a_matriz_inteira():
    # Lotes de 1024 linhas: qualquer toarray da matriz de 3.000 linhas levanta.
    X, y = matriz_esparsa(3000, seed=1)
    Xp, yp = matriz_esparsa(300, seed=2)
    EstimadorMLP(camadas=(4,), lr=0.01, batch_size=1024, epocas_max=1, paciencia_epocas=1,
                 seed=7, dispositivo="cpu").fit(
        _guardada(X, 1024), y, X_parada=_guardada(Xp, 1024), y_parada=yp)


def test_predicao_nunca_densifica_a_matriz_inteira(monkeypatch):
    X, y = matriz_esparsa(600, seed=1)
    Xp, yp = matriz_esparsa(120, seed=2)
    e = EstimadorMLP(camadas=(4,), epocas_max=1, paciencia_epocas=1, seed=7,
                     dispositivo="cpu").fit(X, y, X_parada=Xp, y_parada=yp)
    monkeypatch.setattr(mlp, "TAMANHO_BLOCO_PREDICAO", 250)
    p = e.predict_proba(_guardada(X, 250))  # bloco de 250: toarray de 600 linhas levanta
    assert p.shape == (600, 2)


def test_lotes_embaralhados_com_a_semente_do_config(monkeypatch):
    sementes: list[int] = []
    original = torch.randperm

    def espiao(n, generator=None, **kwargs):
        sementes.append(generator.initial_seed())
        return original(n, generator=generator, **kwargs)

    monkeypatch.setattr(torch, "randperm", espiao)
    X, y = matriz_esparsa(300, seed=1)
    Xp, yp = matriz_esparsa(60, seed=2)
    EstimadorMLP(camadas=(4,), epocas_max=2, paciencia_epocas=5, seed=7,
                 dispositivo="cpu").fit(X, y, X_parada=Xp, y_parada=yp)
    assert sementes and set(sementes) == {7}
