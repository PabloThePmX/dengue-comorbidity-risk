"""Testes do laço de validação com early stopping (T-4.2) com dados sintéticos (sem microdados).

Modelos "espiões" registram o que receberam em `ajustar` e `prever_proba`, para provar que
nenhuma linha é prevista por um modelo que a viu no treino (R1, R6). Os nomes dos modelos fake
entram no registro só dentro do teste (monkeypatch), então o registro real não muda.
"""

import numpy as np
import pandas as pd
import pytest

from dengue_sinan import baselines, cv, folds, metrics
from dengue_sinan.profiling import COMORBIDADES

ORDEM = ["A", "B", "C"]  # 3 regiões bastam para testar a mecânica das dobras
N_POR_REGIAO = 120


def cfg_teste() -> dict:
    return {"ordem_dobras": ORDEM, "seed": 7, "validacao_interna_frac": 0.2, "ano_teste": 2024}


def frame_sintetico(seed: int = 3) -> pd.DataFrame:
    """Casos de 2022 nas 3 regiões, com as colunas que o B1 e a regra B2 leem."""
    rng = np.random.default_rng(seed)
    n = N_POR_REGIAO * len(ORDEM)
    df = pd.DataFrame({
        "ANO": np.full(n, 2022, dtype="int64"),
        "regiao": np.repeat(ORDEM, N_POR_REGIAO),
        "idade_anos": rng.uniform(0, 90, n),
        "sexo": rng.choice(["F", "M", "I"], n),
        "gestante": rng.integers(0, 2, n).astype("int8"),
        "LACO": rng.choice(["Sim", "Não", "Ausente"], n),
        "PETEQUIA_N": rng.choice(["Sim", "Não", "Ausente"], n),
    })
    for c in COMORBIDADES:
        df[c] = rng.choice(["Sim", "Não", "Ausente"], n, p=[0.2, 0.7, 0.1])
    risco = 0.05 + 0.25 * (df["RENAL"] == "Sim") + 0.1 * (df["DIABETES"] == "Sim")
    df["y"] = (rng.uniform(size=n) < risco).astype("int64")
    return df.reset_index(drop=True)


class Espiao:
    """Modelo fake: guarda os índices vistos em `ajustar` e os previstos em `prever_proba`."""

    iterativo = False
    instancias: list["Espiao"] = []

    def __init__(self) -> None:
        self.visto_treino: set[int] = set()
        self.visto_parada: set[int] = set()
        self.previstos: list[int] = []
        Espiao.instancias.append(self)

    def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None:
        self.visto_treino = set(X_treino.index)
        self.visto_parada = set() if X_parada is None else set(X_parada.index)

    def prever_proba(self, X) -> np.ndarray:
        self.previstos = list(X.index)
        return np.full(len(X), 0.5)

    def melhor_ponto(self) -> int | None:
        return None


class EspiaoIterativo(Espiao):
    iterativo = True

    def melhor_ponto(self) -> int | None:
        return 10 + len(Espiao.instancias)  # 11, 12, 13 nas três dobras


class SemMelhorPonto(EspiaoIterativo):
    def melhor_ponto(self) -> int | None:
        return None


@pytest.fixture
def registro_espiao(monkeypatch):
    Espiao.instancias = []
    monkeypatch.setitem(cv.REGISTRO, "espiao", lambda params, cfg: Espiao())
    monkeypatch.setitem(cv.REGISTRO, "espiao_it", lambda params, cfg: EspiaoIterativo())
    monkeypatch.setitem(cv.REGISTRO, "sem_ponto", lambda params, cfg: SemMelhorPonto())
    return Espiao


def _posicoes_validacao(cfg: dict, df: pd.DataFrame) -> dict[str, np.ndarray]:
    return {regiao: pos_val for regiao, _, pos_val in folds.loro_folds(cfg, df)}


# --- Contrato, registro e recusas ------------------------------------------------------------

def test_registro_recusa_modelo_desconhecido():
    with pytest.raises(ValueError, match="não registrado"):
        cv.construir_modelo("nao_existe", {}, cfg_teste())


def test_b1_recusa_hiperparametros():
    with pytest.raises(ValueError, match="não tem hiperparâmetros"):
        cv.construir_modelo("b1", {"C": 1.0}, cfg_teste())


def test_b1_ajustar_recusa_validacao_de_parada():
    df = frame_sintetico()
    modelo = cv.construir_modelo("b1", {}, cfg_teste())
    with pytest.raises(ValueError, match="não usa validação de parada"):
        modelo.ajustar(df, df["y"], df, df["y"])


def test_run_loro_recusa_ano_de_teste():
    df = frame_sintetico()
    df.loc[0, "ANO"] = 2024  # R1: o ano de teste nunca entra no laço
    with pytest.raises(RuntimeError, match="teste congelado"):
        cv.run_loro(cfg_teste(), "b1", {}, df)


def test_run_loro_exige_indice_de_posicoes():
    df = frame_sintetico().set_index(pd.Index(np.arange(len(frame_sintetico())) + 10))
    with pytest.raises(ValueError, match="índice 0..n-1"):
        cv.run_loro(cfg_teste(), "b1", {}, df)


def test_prever_proba_fora_de_zero_um_levanta(monkeypatch):
    class Ruim(Espiao):
        def prever_proba(self, X):
            return np.full(len(X), 1.5)

    monkeypatch.setitem(cv.REGISTRO, "ruim", lambda params, cfg: Ruim())
    with pytest.raises(ValueError, match="fora de"):
        cv.run_loro(cfg_teste(), "ruim", {}, frame_sintetico())


# --- OOF: uma predição por linha e nenhuma linha vista no treino ----------------------------

def test_oof_tem_uma_predicao_por_linha(registro_espiao):
    df = frame_sintetico()
    resultado = cv.run_loro(cfg_teste(), "espiao", {}, df)
    oof = resultado["oof"]
    assert len(oof) == len(df)
    assert sorted(resultado["posicoes"].tolist()) == list(range(len(df)))
    assert not pd.Series(resultado["posicoes"]).duplicated().any()
    assert list(oof.columns) == ["ANO", "regiao", "y", "p"]


def test_modelo_nao_preve_linha_que_viu_no_treino(registro_espiao):
    df = frame_sintetico()
    cfg = cfg_teste()
    cv.run_loro(cfg, "espiao", {}, df)
    validacoes = _posicoes_validacao(cfg, df)
    assert len(Espiao.instancias) == len(ORDEM)
    for regiao, modelo in zip(ORDEM, Espiao.instancias, strict=True):
        previstos = set(modelo.previstos)
        assert previstos == set(validacoes[regiao].tolist())
        assert previstos.isdisjoint(modelo.visto_treino)


def test_b1_treina_so_nas_quatro_regioes_de_treino(registro_espiao):
    """Modelo não iterativo: recebe o treino inteiro das outras regiões, nunca a de validação."""
    df = frame_sintetico()
    cfg = cfg_teste()
    cv.run_loro(cfg, "espiao", {}, df)
    for regiao, modelo in zip(ORDEM, Espiao.instancias, strict=True):
        esperado_treino = set(df.index[df["regiao"] != regiao].tolist())
        assert modelo.visto_treino == esperado_treino
        assert modelo.visto_parada == set()


# --- Early stopping: validação interna só das regiões de treino (R6) -----------------------

def test_validacao_interna_so_vem_das_regioes_de_treino(registro_espiao):
    df = frame_sintetico()
    cfg = cfg_teste()
    cv.run_loro(cfg, "espiao_it", {}, df)
    for regiao, modelo in zip(ORDEM, Espiao.instancias, strict=True):
        regioes_parada = set(df.loc[sorted(modelo.visto_parada), "regiao"])
        assert regioes_parada == set(ORDEM) - {regiao}
        assert regiao not in regioes_parada


def test_parada_nunca_usa_a_regiao_deixada_de_fora(registro_espiao):
    """Para cada dobra, nenhum caso da região de validação entra em ajuste nem em parada."""
    df = frame_sintetico()
    cfg = cfg_teste()
    cv.run_loro(cfg, "espiao_it", {}, df)
    validacoes = _posicoes_validacao(cfg, df)
    for regiao, modelo in zip(ORDEM, Espiao.instancias, strict=True):
        assert modelo.visto_parada.isdisjoint(validacoes[regiao].tolist())
        assert modelo.visto_treino.isdisjoint(validacoes[regiao].tolist())


def test_ajuste_e_parada_particionam_o_treino_da_dobra(registro_espiao):
    df = frame_sintetico()
    cfg = cfg_teste()
    cv.run_loro(cfg, "espiao_it", {}, df)
    for regiao, modelo in zip(ORDEM, Espiao.instancias, strict=True):
        treino = set(df.index[df["regiao"] != regiao].tolist())
        assert modelo.visto_treino | modelo.visto_parada == treino
        assert modelo.visto_treino.isdisjoint(modelo.visto_parada)
        # Mesma divisão de folds.inner_split: a validação interna é reproduzível (R8).
        pos_ajuste, pos_parada = folds.inner_split(
            np.array(sorted(treino)), df["y"].to_numpy(), cfg["validacao_interna_frac"],
            cfg["seed"])
        assert set(pos_ajuste.tolist()) == modelo.visto_treino
        assert set(pos_parada.tolist()) == modelo.visto_parada


# --- Melhores pontos e métricas --------------------------------------------------------------

def test_melhores_pontos_por_dobra_sao_devolvidos(registro_espiao):
    resultado = cv.run_loro(cfg_teste(), "espiao_it", {}, frame_sintetico())
    assert resultado["melhores_pontos"] == {"A": 11, "B": 12, "C": 13}


def test_modelo_iterativo_sem_melhor_ponto_levanta(registro_espiao):
    with pytest.raises(ValueError, match="melhor_ponto"):
        cv.run_loro(cfg_teste(), "sem_ponto", {}, frame_sintetico())


def test_nao_iterativo_devolve_melhor_ponto_none(registro_espiao):
    resultado = cv.run_loro(cfg_teste(), "espiao", {}, frame_sintetico())
    assert resultado["melhores_pontos"] == {"A": None, "B": None, "C": None}


def test_metricas_do_resultado_conferem_com_o_oof(registro_espiao):
    resultado = cv.run_loro(cfg_teste(), "espiao", {}, frame_sintetico())
    oof = resultado["oof"]
    assert resultado["oof_pr_auc"] == pytest.approx(metrics.pr_auc(oof["y"], oof["p"]))
    esperado_media = np.mean(list(resultado["pr_auc_por_dobra"].values()))
    assert resultado["pr_auc_media"] == pytest.approx(esperado_media)
    assert set(resultado["pr_auc_por_dobra"]) == set(ORDEM)


# --- B1 reproduz exatamente o baseline da T-2.8 ---------------------------------------------

def test_b1_do_laco_reproduz_o_baseline_t28():
    """Mesmo pipeline e mesmas dobras que `baselines.avaliar_dobras`: métricas iguais."""
    df = frame_sintetico()
    cfg = cfg_teste()
    base = df.copy()
    for regiao in ORDEM:
        base[f"papel_{regiao}"] = np.where(base["regiao"] == regiao, "validacao", "ajuste")

    referencia = baselines.avaliar_dobras(cfg, base)["B1"]
    resultado = cv.run_loro(cfg, "b1", {}, df)

    for regiao in ORDEM:
        assert resultado["pr_auc_por_dobra"][regiao] == pytest.approx(
            referencia["por_dobra"][regiao]["pr_auc"], abs=1e-12)
    assert resultado["oof_pr_auc"] == pytest.approx(referencia["oof"]["pr_auc"], abs=1e-12)
    assert resultado["melhores_pontos"] == {regiao: None for regiao in ORDEM}


def test_run_loro_nao_altera_o_dataframe_de_entrada():
    df = frame_sintetico()
    antes = df.copy()
    cv.run_loro(cfg_teste(), "b1", {}, df)
    pd.testing.assert_frame_equal(df, antes)
