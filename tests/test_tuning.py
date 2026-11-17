"""Testes da busca Optuna (T-4.3) com dados sintéticos e um modelo "toy" barato (sem microdados).

Tudo roda em pastas temporárias: o SQLite do estudo, o `mlruns/` e os dados. O modelo "toy" entra
no `REGISTRO` só dentro do teste (monkeypatch), então o registro real não muda.
"""

import itertools
import os
from types import SimpleNamespace

import numpy as np
import optuna
import pandas as pd
import pytest
from mlflow.tracking import MlflowClient
from optuna.trial import TrialState

from dengue_sinan import cv, tuning
from dengue_sinan.config import load_config
from dengue_sinan.search_space import load_search_space

ORDEM = ["A", "B", "C"]  # 3 regiões bastam para testar a mecânica (o real tem 5)
N_POR_REGIAO = 600
PRIMEIRA_RF = {"n_estimators": 200, "max_depth": 8, "min_samples_leaf": 100,
               "max_features": "sqrt", "max_samples": 0.1}


class Toy:
    """Probabilidade = sigmoide(-3 + forca · sinal). forca 0 não tem sinal; negativa, anti-sinal."""

    iterativo = False

    def __init__(self, forca: float) -> None:
        self.forca = float(forca)

    def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None:
        if X_parada is not None:
            raise ValueError("toy não usa validação de parada")

    def prever_proba(self, X) -> np.ndarray:
        z = -3.0 + self.forca * X["sinal"].to_numpy(dtype=float)
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))

    def melhor_ponto(self) -> int | None:
        return None


def _construir_toy(params, cfg):
    return Toy(params["forca"])


@pytest.fixture
def toy(monkeypatch):
    monkeypatch.setitem(cv.REGISTRO, "toy", _construir_toy)
    return "toy"


def cfg_toy(tmp_path, max_tentativas: int = 6, teto_min: float = 40.0) -> dict:
    base = load_config()
    dados = tmp_path / "data"
    dados.mkdir(exist_ok=True)
    return {
        **base,
        "seed": 7,
        "ordem_dobras": ORDEM,
        "validacao_interna_frac": 0.2,
        "ordem_modelos": ["toy"],
        "busca": {"toy": {
            "parametros": {"forca": {"tipo": "float", "escala": "linear", "min": -1.0, "max": 3.0}},
            "primeira_tentativa": {"forca": 0.0},
        }},
        "optuna": {"max_tentativas": {"toy": max_tentativas},
                   "poda_tentativas_iniciais": 5, "poda_dobras_aquecimento": 2},
        "orcamento_teto_min": {"toy": teto_min},
        "orcamento_piso_min": 10,
        "caminhos": {**base["caminhos"], "dados": str(dados), "mlruns": str(tmp_path / "mlruns")},
    }


def frame(seed: int = 3) -> pd.DataFrame:
    """Casos de 2022 nas 3 regiões de `ORDEM`, com um sinal que prediz y."""
    rng = np.random.default_rng(seed)
    n = N_POR_REGIAO * len(ORDEM)
    sinal = rng.normal(size=n)
    y = (rng.uniform(size=n) < 1 / (1 + np.exp(-(-3.0 + 1.5 * sinal)))).astype("int64")
    return pd.DataFrame({
        "ANO": np.full(n, 2022, dtype="int64"),
        "regiao": np.repeat(ORDEM, N_POR_REGIAO),
        "sinal": sinal,
        "y": y,
    })


def estado_dos_trials(cfg: dict, modelo: str = "toy") -> dict:
    return {t.number: t for t in tuning.criar_estudo(cfg, modelo).trials}


# --- Fórmula do orçamento e subamostra (testes puros) ----------------------------------------

def test_orcamento_sem_subamostra_usa_t_vezes_max_limitado_ao_teto():
    r = tuning.calcular_orcamento(t_s=100, max_tentativas=25, piso_s=600, teto_s=2400)
    assert r["subamostra"] is False and r["fracao"] == 1.0
    assert r["orcamento_s"] == 2400  # min(teto 2400, 100 × 25 = 2500)


def test_orcamento_abaixo_do_teto_segue_t_vezes_max():
    r = tuning.calcular_orcamento(t_s=50, max_tentativas=20, piso_s=600, teto_s=2400)
    assert r["orcamento_s"] == 1000 and r["subamostra"] is False


def test_orcamento_nunca_fica_abaixo_do_piso_de_10_minutos():
    r = tuning.calcular_orcamento(t_s=10, max_tentativas=15, piso_s=600, teto_s=2400)
    assert r["orcamento_s"] == 600  # 10 × 15 = 150 s, o piso vale


def test_orcamento_com_subamostra_faz_3t_caber_no_teto():
    t, teto = 1000.0, 2400.0  # 3t = 3000 > 2400
    r = tuning.calcular_orcamento(t_s=t, max_tentativas=25, piso_s=600, teto_s=teto)
    assert r["subamostra"] is True
    assert r["fracao"] == pytest.approx(0.8)
    assert 3 * r["fracao"] * t == pytest.approx(teto)
    assert r["orcamento_s"] == pytest.approx(teto)  # fracao · t = teto/3, vezes ≥ 3 tentativas


def test_3t_igual_ao_teto_nao_pede_subamostra():
    r = tuning.calcular_orcamento(t_s=800, max_tentativas=25, piso_s=600, teto_s=2400)
    assert r["subamostra"] is False


def test_orcamento_recusa_tempo_nao_positivo():
    with pytest.raises(ValueError, match="positivo"):
        tuning.calcular_orcamento(t_s=0, max_tentativas=5, piso_s=600, teto_s=2400)


def test_subamostra_preserva_a_prevalencia_de_cada_dobra():
    df = frame()
    sub = tuning.subamostra_estratificada(df, fracao=0.5, seed=7)
    for regiao in ORDEM:
        antes = df.loc[df["regiao"] == regiao, "y"].mean()
        depois = sub.loc[sub["regiao"] == regiao, "y"].mean()
        assert abs(antes - depois) < 0.005, regiao
    assert set(sub["regiao"]) == set(ORDEM)
    assert abs(len(sub) - 0.5 * len(df)) <= 2 * len(ORDEM)  # arredondamento por estrato
    assert list(sub.index) == list(range(len(sub)))


def test_subamostra_e_reprodutivel_com_a_mesma_semente():
    df = frame()
    a = tuning.subamostra_estratificada(df, 0.3, seed=7)
    b = tuning.subamostra_estratificada(df, 0.3, seed=7)
    pd.testing.assert_frame_equal(a, b)


def test_subamostra_recusa_fracao_fora_de_zero_um():
    with pytest.raises(ValueError, match="fracao"):
        tuning.subamostra_estratificada(frame(), 1.5, seed=7)


def test_tune_recusa_ano_de_teste(tmp_path, toy):
    df = frame()
    df.loc[0, "ANO"] = 2024
    with pytest.raises(RuntimeError, match="teste congelado"):
        tuning.tune(cfg_toy(tmp_path), toy, df)


def test_tune_recusa_modelo_sem_busca(tmp_path):
    with pytest.raises(ValueError, match="sem_busca"):
        tuning.tune(load_config(), "tabfm", frame())


# --- Cronometragem, retomada e tentativa interrompida ----------------------------------------

def test_cronometragem_roda_a_primeira_tentativa_sozinha(tmp_path, toy):
    cfg = cfg_toy(tmp_path, max_tentativas=3)
    tuning.tune(cfg, toy, frame())
    estudo = tuning.criar_estudo(cfg, toy)
    cron = estudo.user_attrs["cronometragem"]
    assert cron["numero_tentativa"] == 0
    assert estudo.trials[0].params == {"forca": 0.0}  # o ponto de partida do config
    assert len(cron["tempos_dobras_s"]) == len(ORDEM)
    assert cron["t_s"] == pytest.approx(sum(cron["tempos_dobras_s"]))
    assert cron["t_s"] > 0


def test_orcamento_gravado_segue_a_formula(tmp_path, toy):
    cfg = cfg_toy(tmp_path, max_tentativas=3)
    r = tuning.tune(cfg, toy, frame())
    esperado = tuning.calcular_orcamento(r["t_cronometragem_s"], 3, 600, 2400)
    assert r["orcamento_s"] == pytest.approx(esperado["orcamento_s"])
    assert r["subamostra"] is False


def test_retomada_mantem_as_tentativas_anteriores(tmp_path, toy):
    df = frame()
    tuning.tune(cfg_toy(tmp_path, max_tentativas=2), toy, df)
    antes = estado_dos_trials(cfg_toy(tmp_path, max_tentativas=2))
    assert len(antes) == 2

    r = tuning.tune(cfg_toy(tmp_path, max_tentativas=4), toy, df)
    depois = estado_dos_trials(cfg_toy(tmp_path, max_tentativas=4))
    assert len(depois) == 4
    assert r["tentativas_concluidas"] + r["tentativas_podadas"] == 4
    for numero, antigo in antes.items():
        novo = depois[numero]
        assert (novo.params, novo.state, novo.value) == (antigo.params, antigo.state, antigo.value)


def test_tentativa_interrompida_vira_falha_e_nao_conta_no_orcamento(tmp_path, toy):
    cfg = cfg_toy(tmp_path, max_tentativas=3)
    estudo = tuning.criar_estudo(cfg, toy)
    interrompida = estudo.ask()  # simula uma sessão morta no meio da tentativa: fica "rodando"
    numero = interrompida.number
    assert estado_dos_trials(cfg)[numero].state == TrialState.RUNNING

    r = tuning.tune(cfg, toy, frame())
    assert r["interrompidas_na_retomada"] == 1
    assert estado_dos_trials(cfg)[numero].state == TrialState.FAIL
    # a falha não consumiu orçamento: as 3 tentativas do config ainda rodaram
    assert r["tentativas_concluidas"] + r["tentativas_podadas"] == 3


def test_poda_por_dobra_corta_tentativas_ruins_depois_do_aquecimento(tmp_path, toy):
    cfg = cfg_toy(tmp_path, max_tentativas=14)
    tuning.tune(cfg, toy, frame())
    trials = tuning.criar_estudo(cfg, toy).trials
    podadas = [t for t in trials if t.state == TrialState.PRUNED]
    assert podadas, "nenhuma tentativa foi podada; a poda não aconteceu"
    for t in podadas:
        assert len(t.intermediate_values) >= 2  # nunca antes da 2ª dobra concluída
        assert len(t.intermediate_values) < len(ORDEM)
    completas = [t for t in trials if t.state == TrialState.COMPLETE]
    assert completas and all(len(t.intermediate_values) == len(ORDEM) for t in completas)


def test_subamostra_entra_quando_3t_nao_cabe_no_teto(tmp_path, toy):
    cfg = cfg_toy(tmp_path, max_tentativas=6, teto_min=0.0001)  # teto de 6 ms: 3t sempre passa
    df = frame()
    r = tuning.tune(cfg, toy, df)
    assert r["subamostra"] is True and 0 < r["fracao"] < 1
    cron = tuning.criar_estudo(cfg, toy).user_attrs["cronometragem"]
    assert 3 * cron["fracao"] * cron["t_s"] == pytest.approx(0.006)
    assert r["linhas_busca"] < len(df)

    estudo = tuning.criar_estudo(cfg, toy)
    assert estudo.trials[0].params == {"forca": 0.0}  # o ponto de partida roda na subamostra
    # a cronometragem (dados completos) não conta: as 6 tentativas da busca rodaram
    assert r["tentativas_concluidas"] + r["tentativas_podadas"] == 6


def test_com_subamostra_o_tpe_nao_ve_a_tentativa_cronometrada(tmp_path, toy):
    cfg = cfg_toy(tmp_path, max_tentativas=5, teto_min=0.0001)
    tuning.tune(cfg, toy, frame())
    principal = tuning.criar_estudo(cfg, toy).trials
    assert len(principal) == 5  # sem a cronometragem: só as tentativas da busca
    cron = tuning.criar_estudo_cronometragem(cfg, toy).trials
    assert len(cron) == 1 and cron[0].state == TrialState.COMPLETE
    assert cron[0].params == {"forca": 0.0}
    assert tuning.criar_estudo(cfg, toy).user_attrs["cronometragem"]["numero_tentativa"] is None


def test_sem_subamostra_a_cronometragem_e_a_1a_tentativa_do_estudo_principal(tmp_path, toy):
    cfg = cfg_toy(tmp_path, max_tentativas=4)
    r = tuning.tune(cfg, toy, frame())
    assert r["subamostra"] is False
    principal = tuning.criar_estudo(cfg, toy).trials
    assert principal[0].params == {"forca": 0.0}
    assert principal[0].state == TrialState.COMPLETE
    assert len(principal) == 4  # a tentativa medida conta no orçamento e não é repetida
    assert tuning.criar_estudo(cfg, toy).user_attrs["cronometragem"]["numero_tentativa"] == 0


@pytest.mark.parametrize("teto_min", [40.0, 0.0001])
def test_retomada_nao_repete_a_cronometragem(tmp_path, toy, teto_min):
    df = frame()
    tuning.tune(cfg_toy(tmp_path, max_tentativas=2, teto_min=teto_min), toy, df)
    cron_antes = tuning.criar_estudo(cfg_toy(tmp_path, teto_min=teto_min), toy).user_attrs[
        "cronometragem"]
    medidas_antes = len(tuning.criar_estudo_cronometragem(cfg_toy(tmp_path), toy).trials)

    tuning.tune(cfg_toy(tmp_path, max_tentativas=4, teto_min=teto_min), toy, df)
    estudo_cron = tuning.criar_estudo_cronometragem(cfg_toy(tmp_path), toy)
    assert len(estudo_cron.trials) == medidas_antes == 1  # nenhuma nova medição
    cron_depois = tuning.criar_estudo(cfg_toy(tmp_path), toy).user_attrs["cronometragem"]
    assert cron_depois == cron_antes


def test_subamostra_fica_registrada_no_mlflow(tmp_path, toy):
    cfg = cfg_toy(tmp_path, max_tentativas=3, teto_min=0.0001)
    r = tuning.tune(cfg, toy, frame())
    run = MlflowClient().get_run(r["run_id"])
    assert run.data.params["tuning.subamostra"] == "True"
    assert float(run.data.params["tuning.fracao"]) == pytest.approx(r["fracao"], abs=1e-6)


def test_tempo_orcamento_e_tentativas_vao_para_o_mlflow(tmp_path, toy):
    cfg = cfg_toy(tmp_path, max_tentativas=3)
    r = tuning.tune(cfg, toy, frame())
    metricas = MlflowClient().get_run(r["run_id"]).data.metrics
    assert metricas["tuning.t_cronometragem_s"] == pytest.approx(r["t_cronometragem_s"])
    assert metricas["tuning.orcamento_s"] == pytest.approx(r["orcamento_s"])
    assert metricas["tuning.tentativas_concluidas"] == r["tentativas_concluidas"]
    assert metricas["tuning.tentativas_podadas"] == r["tentativas_podadas"]
    assert metricas["tuning.tempo_sessao_s"] > 0
    assert "tuning.melhor_pr_auc" in metricas


# --- Ponto de partida de cada modelo (decisão do Programador) --------------------------------

@pytest.mark.parametrize("modelo", ["elastic_net", "xgboost", "catboost", "mlp", "random_forest"])
def test_primeira_tentativa_de_cada_modelo_vem_do_config(tmp_path, monkeypatch, modelo):
    base = load_config()
    espaco = load_search_space(base)[modelo]
    recebidos: list[dict] = []

    class Gravador:
        iterativo = False

        def __init__(self, params):
            recebidos.append(dict(params))

        def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None:
            pass

        def prever_proba(self, X) -> np.ndarray:
            return np.full(len(X), 0.5)

        def melhor_ponto(self) -> int | None:
            return None

    monkeypatch.setitem(cv.REGISTRO, modelo, lambda params, cfg: Gravador(params))
    cfg = {
        **base,
        "caminhos": {**base["caminhos"], "dados": str(tmp_path / "data"),
                     "mlruns": str(tmp_path / "mlruns")},
        "optuna": {**base["optuna"],
                   "max_tentativas": {**base["optuna"]["max_tentativas"], modelo: 1}},
    }
    rng = np.random.default_rng(1)
    df = pd.DataFrame({
        "ANO": np.full(500, 2022, dtype="int64"),
        "regiao": np.array(base["ordem_dobras"])[rng.integers(0, 5, 500)],
        "y": rng.integers(0, 2, 500).astype("int64"),
    })
    tuning.tune(cfg, modelo, df)
    # a 1ª tentativa é a cronometragem: sem poda, parâmetros = fixos + ponto de partida do config
    assert recebidos[0] == {**espaco.fixos, **espaco.primeira_tentativa}


def test_random_forest_comeca_pelo_ponto_conservador_do_config():
    espaco = load_search_space(load_config())["random_forest"]
    assert espaco.primeira_tentativa == PRIMEIRA_RF


# --- Gancho do laço (cv.run_loro) ------------------------------------------------------------

def cfg_laco() -> dict:
    return {"ordem_dobras": ORDEM, "seed": 7, "validacao_interna_frac": 0.2, "ano_teste": 2024}


def test_gancho_ausente_nao_altera_o_resultado(toy):
    df = frame()
    sem = cv.run_loro(cfg_laco(), toy, {"forca": 1.0}, df)
    com = cv.run_loro(cfg_laco(), toy, {"forca": 1.0}, df, ao_fim_da_dobra=lambda r, i, p: None)
    pd.testing.assert_frame_equal(sem["oof"], com["oof"])
    assert sem["oof_pr_auc"] == com["oof_pr_auc"]
    assert sem["pr_auc_por_dobra"] == com["pr_auc_por_dobra"]


def test_gancho_e_chamado_depois_de_cada_dobra_na_ordem(toy):
    chamadas = []
    cv.run_loro(cfg_laco(), toy, {"forca": 1.0}, frame(),
                ao_fim_da_dobra=lambda regiao, indice, pr: chamadas.append((regiao, indice, pr)))
    assert [(r, i) for r, i, _ in chamadas] == [("A", 0), ("B", 1), ("C", 2)]
    assert all(0 <= pr <= 1 for _, _, pr in chamadas)


def test_trial_pruned_levantado_no_gancho_sai_do_laco(toy):
    def podar(regiao, indice, pr):
        raise optuna.TrialPruned("teste")

    with pytest.raises(optuna.TrialPruned):
        cv.run_loro(cfg_laco(), toy, {"forca": 1.0}, frame(), ao_fim_da_dobra=podar)


# --- Registro de modelos e alias -------------------------------------------------------------

def test_alias_aponta_para_a_melhor_e_pior_nao_sobrescreve(tmp_path, toy):
    cfg = cfg_toy(tmp_path, max_tentativas=8)
    df = frame()
    r = tuning.tune(cfg, toy, df)
    client = MlflowClient(tracking_uri=cfg["caminhos"]["mlruns"])
    versao = client.get_model_version_by_alias("m1-toy", "melhor-validacao")
    concluidas = [t for t in tuning.criar_estudo(cfg, toy).trials if t.state == TrialState.COMPLETE]
    melhor = max(concluidas, key=lambda t: (t.value, -t.number))
    assert versao.tags["trial_number"] == str(melhor.number)
    assert float(versao.tags["pr_auc"]) == pytest.approx(melhor.value)
    assert r["melhor_tentativa"] == melhor.number

    # nova sessão sem tentativas restantes: o alias não muda e nenhuma versão nova aparece
    r2 = tuning.tune(cfg, toy, df)
    assert r2["alias_atualizado"] is False
    assert client.get_model_version_by_alias("m1-toy", "melhor-validacao").version == versao.version

    # uma pior não move o alias; uma melhor move
    assert tuning.registrar_melhor_tentativa("toy", 999, melhor.value - 0.01, r2["run_id"]) is False
    assert client.get_model_version_by_alias("m1-toy", "melhor-validacao").version == versao.version
    assert tuning.registrar_melhor_tentativa("toy", 1000, melhor.value + 0.01, r2["run_id"]) is True
    novo = client.get_model_version_by_alias("m1-toy", "melhor-validacao")
    assert novo.version != versao.version and novo.tags["trial_number"] == "1000"


# --- Checagem do SQLite no diretório (T-4.3b) ------------------------------------------------

def test_checagem_sqlite_passa_e_apaga_o_arquivo_de_teste(tmp_path):
    pasta = tmp_path / "drive_falso"
    check = tuning.checar_sqlite_no_diretorio(pasta)
    assert check["passou"] is True
    assert check["obtido"] == "ok"
    assert list(pasta.glob("_checagem_*")) == []


def test_checagem_sqlite_reprova_quando_o_estudo_nao_abre(tmp_path, monkeypatch):
    def quebrado(*args, **kwargs):
        raise OSError("disco indisponível")

    monkeypatch.setattr(tuning.optuna, "create_study", quebrado)
    check = tuning.checar_sqlite_no_diretorio(tmp_path / "drive_falso")
    assert check["passou"] is False
    assert check["obtido"] == "erro: OSError"


# --- Provas da revisão: t, seed, timeout do orçamento e hardware -----------------------------

def test_t_da_cronometragem_bate_com_o_relogio_conhecido(tmp_path, toy, monkeypatch):
    # Relógio falso (só no módulo tuning). Ordem das leituras: início do tune (0), início da
    # tentativa (1), fim de cada uma das 3 dobras (3, 6, 10). Dobras: 2, 3 e 4 s; t = 9 s.
    seq = itertools.chain([0.0, 1.0, 3.0, 6.0, 10.0], itertools.count(1000.0))
    monkeypatch.setattr(tuning, "time", SimpleNamespace(perf_counter=lambda: next(seq)))
    cfg = cfg_toy(tmp_path, max_tentativas=3)
    r = tuning.tune(cfg, toy, frame())
    assert r["t_cronometragem_s"] == pytest.approx(9.0)
    cron = tuning.criar_estudo(cfg, toy).user_attrs["cronometragem"]
    assert cron["tempos_dobras_s"] == pytest.approx([2.0, 3.0, 4.0])
    assert cron["t_s"] == pytest.approx(9.0)
    # 3t = 27 s cabe no teto (2400 s); orçamento = max(piso 600, min(2400, 9 × 3)) = 600 s
    assert r["orcamento_s"] == pytest.approx(600.0)


def test_seed_do_config_controla_as_tentativas_sorteadas(tmp_path, toy):
    def sorteadas(nome: str, seed: int) -> list[float]:
        pasta = tmp_path / nome
        pasta.mkdir()
        cfg = {**cfg_toy(pasta, max_tentativas=8), "seed": seed}
        tuning.tune(cfg, toy, frame())
        return [t.params["forca"] for t in tuning.criar_estudo(cfg, toy).trials]

    assert sorteadas("a", 7) == sorteadas("b", 7)  # mesma seed: mesma sequência
    assert sorteadas("c", 7) != sorteadas("d", 8)  # seed diferente: sequência diferente


def _gravar_optimize(monkeypatch) -> list[dict]:
    chamadas: list[dict] = []
    original = optuna.study.Study.optimize

    def gravador(self, func, *args, **kwargs):
        chamadas.append(kwargs)
        return original(self, func, *args, **kwargs)

    monkeypatch.setattr(optuna.study.Study, "optimize", gravador)
    return chamadas


def test_timeout_da_busca_e_orcamento_menos_o_gasto_ja_feito(tmp_path, toy, monkeypatch):
    df = frame()
    tuning.tune(cfg_toy(tmp_path, max_tentativas=2), toy, df)
    estudo = tuning.criar_estudo(cfg_toy(tmp_path), toy)
    orcamento = estudo.user_attrs["cronometragem"]["orcamento_s"]
    # gasto já feito, lido das tentativas guardadas (tempo de cada dobra, gravado pelo Optuna)
    gasto = sum(sum(t.user_attrs["tempo_dobras_s"]) for t in estudo.trials)

    chamadas = _gravar_optimize(monkeypatch)
    tuning.tune(cfg_toy(tmp_path, max_tentativas=4), toy, df)
    busca = [c for c in chamadas if "timeout" in c]
    assert len(busca) == 1
    assert busca[0]["n_trials"] == 2  # 4 do config − 2 já feitas
    assert busca[0]["timeout"] == pytest.approx(orcamento - gasto, rel=1e-6)


def test_retomada_com_orcamento_esgotado_nao_roda_tentativa(tmp_path, toy, monkeypatch):
    df = frame()
    cfg_inicial = cfg_toy(tmp_path, max_tentativas=2)
    tuning.tune(cfg_inicial, toy, df)
    estudo = tuning.criar_estudo(cfg_inicial, toy)
    # estado de um orçamento já consumido: o orçamento gravado fica menor que o gasto
    cron = {**estudo.user_attrs["cronometragem"], "orcamento_s": 0.0}
    estudo.set_user_attr("cronometragem", cron)
    antes = len(estudo.trials)

    chamadas = _gravar_optimize(monkeypatch)
    tuning.tune(cfg_toy(tmp_path, max_tentativas=6), toy, df)
    assert [c for c in chamadas if "timeout" in c] == []  # nenhuma busca nova
    assert len(tuning.criar_estudo(cfg_inicial, toy).trials) == antes


def test_hardware_do_run_do_tune_vai_para_o_mlflow(tmp_path, toy):
    r = tuning.tune(cfg_toy(tmp_path, max_tentativas=2), toy, frame())
    params = MlflowClient().get_run(r["run_id"]).data.params
    assert params["hardware.vcpus"] == str(os.cpu_count())  # tracking.start_run grava o hardware
    assert float(params["hardware.ram_gib"]) > 0
    assert {"hardware.cpu", "hardware.gpu"} <= set(params)
