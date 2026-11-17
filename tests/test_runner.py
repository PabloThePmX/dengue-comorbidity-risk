"""Testes da sessão única (T-4.3b) com dados sintéticos e dois modelos "toy" baratos.

Nada aqui lê microdados nem o ano de teste (R1). Os dados, os T-2.3.json e os manifests são
gerados em pastas temporárias; os modelos entram no `REGISTRO` só dentro do teste.
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from dengue_sinan import cv, folds, runner, tuning, verify
from dengue_sinan.config import load_config
from dengue_sinan.runner import ChecagemInicialFalhou, Gancho

ORDEM = ["A", "B", "C"]  # 3 regiões bastam para a mecânica (a sessão real tem 5)
N_POR_REGIAO = 300
DBC = {"2022": "a" * 64, "2023": "b" * 64}
ESPACO_TOY = {
    "parametros": {"forca": {"tipo": "float", "escala": "linear", "min": -1.0, "max": 3.0}},
    "primeira_tentativa": {"forca": 0.0},
}


def _sigmoide(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


class ToyPlano:
    """Modelo não iterativo: probabilidade = sigmoide(-3 + forca · sinal)."""

    iterativo = False

    def __init__(self, forca: float) -> None:
        self.forca = float(forca)

    def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None:
        if X_parada is not None:
            raise ValueError("toy_a não usa validação de parada")

    def prever_proba(self, X) -> np.ndarray:
        return _sigmoide(-3.0 + self.forca * X["sinal"].to_numpy(dtype=float))

    def melhor_ponto(self) -> int | None:
        return None


class ToyIterativo(ToyPlano):
    """Modelo iterativo: exige a validação de parada e informa um melhor ponto fixo."""

    iterativo = True

    def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None:
        if X_parada is None:
            raise ValueError("toy_b precisa da validação de parada")

    def melhor_ponto(self) -> int | None:
        return 7


@pytest.fixture
def toys(monkeypatch):
    monkeypatch.setitem(cv.REGISTRO, "toy_a", lambda p, c: ToyPlano(p["forca"]))
    monkeypatch.setitem(cv.REGISTRO, "toy_b", lambda p, c: ToyIterativo(p["forca"]))
    return ["toy_a", "toy_b"]


def cfg_sessao(tmp_path: Path) -> dict:
    base = load_config()
    return {
        **base,
        "seed": 7,
        "ordem_dobras": ORDEM,
        "validacao_interna_frac": 0.2,
        "ordem_modelos": ["toy_a", "toy_b"],
        "busca": {"toy_a": ESPACO_TOY, "toy_b": ESPACO_TOY},
        "optuna": {"max_tentativas": {"toy_a": 2, "toy_b": 2},
                   "poda_tentativas_iniciais": 5, "poda_dobras_aquecimento": 2},
        "orcamento_teto_min": {"toy_a": 40, "toy_b": 40},
        "orcamento_piso_min": 10,
        "ambiente": {"gpu": None, "ram_min_gib": 0},  # sem GPU nem RAM mínima: CI local
        "caminhos": {
            **base["caminhos"],
            "dados": str(tmp_path / "drive" / "data"),
            "mlruns": str(tmp_path / "mlruns"),
            "relatorios": str(tmp_path / "reports"),
        },
    }


def frame(seed: int = 3) -> pd.DataFrame:
    """Casos sintéticos de 2022 nas 3 regiões, com um sinal que prediz y."""
    rng = np.random.default_rng(seed)
    n = N_POR_REGIAO * len(ORDEM)
    sinal = rng.normal(size=n)
    y = (rng.uniform(size=n) < _sigmoide(-3.0 + 1.5 * sinal)).astype("int64")
    return pd.DataFrame({
        "ANO": np.full(n, 2022, dtype="int64"),
        "LINHA": np.arange(n, dtype="int64"),
        "regiao": np.repeat(ORDEM, N_POR_REGIAO),
        "sinal": sinal,
        "y": y,
    })


def preparar_referencias(cfg: dict, df: pd.DataFrame, tmp_path: Path, *,
                         dbc: dict = DBC, hash_dobras: str | None = None) -> Path:
    """Escreve o T-2.3.json, o manifest do Drive e o esperado.yaml que a checagem lê."""
    if hash_dobras is None:
        hash_dobras = folds.folds_hash(folds.build_folds_frame(cfg, df))
    t23 = Path(cfg["caminhos"]["relatorios"]) / "verificacao" / "T-2.3.json"
    t23.parent.mkdir(parents=True, exist_ok=True)
    t23.write_text(json.dumps({
        "tarefa": "T-2.3",
        "hash_dados": dbc,
        "checks": [{"nome": "hash_conteudo_dobras", "esperado": hash_dobras,
                    "obtido": hash_dobras, "tolerancia": 0, "passou": True}],
        "passou": True,
    }), encoding="utf-8")
    manifesto = Path(cfg["caminhos"]["dados"]) / "manifest.json"
    manifesto.parent.mkdir(parents=True, exist_ok=True)
    manifesto.write_text(json.dumps({
        ano: {"sha256_dbc": sha, "sha256_parquet": "c" * 64} for ano, sha in dbc.items()
    }), encoding="utf-8")
    esperado = tmp_path / "esperado.yaml"
    esperado.write_text(yaml.safe_dump({"desenvolvimento": {
        "populacao_total": len(df), "eventos_total": int(df["y"].sum()),
    }}), encoding="utf-8")
    return esperado


def rodar(cfg, df, esperado, **kwargs):
    return runner.run_all_models(cfg, carregar_dados=lambda _c: df, esperado_path=esperado,
                                 **kwargs)


def relatorio(cfg: dict) -> dict:
    return json.loads(runner.caminho_relatorio(cfg).read_text(encoding="utf-8"))


def blocos(cfg: dict) -> dict:
    return {b["bloco"]: b for b in relatorio(cfg)["blocos"]}


def concluido(cfg: dict, modelo: str) -> bool:
    return (runner.pasta_m1(cfg) / modelo / runner.ARQ_CONCLUIDO).exists()


def gancho_ok(cfg, resultados):
    return [verify.check("modelos_na_sessao", 2, len(resultados))]


def espiar_tune(monkeypatch) -> list[str]:
    """Conta as chamadas de `tuning.tune` (um modelo que pula não chama)."""
    chamados: list[str] = []
    original = tuning.tune

    def tune(cfg, modelo, df):
        chamados.append(modelo)
        return original(cfg, modelo, df)

    monkeypatch.setattr(tuning, "tune", tune)
    return chamados


# --- Sessão completa e marcadores -------------------------------------------------------------

def test_sessao_treina_os_dois_modelos_e_grava_marcadores(tmp_path, toys):
    cfg = cfg_sessao(tmp_path)
    df = frame()
    esperado = preparar_referencias(cfg, df, tmp_path)
    recebidos = {}

    def gancho(cfg_, resultados):
        recebidos.update(resultados)
        return gancho_ok(cfg_, resultados)

    resultados = rodar(cfg, df, esperado, ganchos=(
        Gancho("teste", "T-0.0", "", funcao=gancho),))

    assert sorted(resultados) == ["toy_a", "toy_b"]
    assert sorted(recebidos) == ["toy_a", "toy_b"]  # o gancho recebe o resumo de cada modelo
    for modelo in ("toy_a", "toy_b"):
        oof = pd.read_parquet(runner.pasta_m1(cfg) / modelo / runner.ARQ_OOF)
        assert len(oof) == len(df)  # uma predição por linha, nenhuma repetida
        assert list(oof.columns) == ["ANO", "regiao", "y", "p"]
        assert concluido(cfg, modelo)
    rel = relatorio(cfg)
    assert [b["bloco"] for b in rel["blocos"]] == ["checagem_inicial", "toy_a", "toy_b", "teste"]
    assert all(b["passou"] for b in rel["blocos"])
    assert rel["sessao_completa"] is True and rel["passou"] is True
    assert rel["hash_dobras"] == folds.folds_hash(folds.build_folds_frame(cfg, df))


def test_interrupcao_depois_do_primeiro_modelo_e_reexecucao_pula_o_concluido(
    tmp_path, toys, monkeypatch
):
    cfg = cfg_sessao(tmp_path)
    df = frame()
    esperado = preparar_referencias(cfg, df, tmp_path)

    def queda(modelo):
        if modelo == "toy_a":
            raise RuntimeError("queda simulada depois do 1º modelo")

    with pytest.raises(RuntimeError, match="queda simulada"):
        rodar(cfg, df, esperado, ganchos=(), ao_concluir_modelo=queda)

    assert concluido(cfg, "toy_a") and not concluido(cfg, "toy_b")
    assert [b["bloco"] for b in relatorio(cfg)["blocos"]] == ["checagem_inicial", "toy_a"]
    assert all(b["passou"] for b in relatorio(cfg)["blocos"])

    chamados = espiar_tune(monkeypatch)
    rodar(cfg, df, esperado, ganchos=(Gancho("teste", "T-0.0", "", funcao=gancho_ok),))

    assert chamados == ["toy_b"]  # o 1º foi pulado pelo CONCLUIDO.json
    rel = relatorio(cfg)
    # verify.update_session_report põe o bloco regravado no fim (ordem de gravação)
    assert sorted(b["bloco"] for b in rel["blocos"]) == sorted(
        ["checagem_inicial", "toy_a", "toy_b", "teste"])
    assert all(b["passou"] for b in rel["blocos"])  # o bloco do 1º modelo foi mantido
    assert rel["sessao_completa"] is True and rel["passou"] is True


def test_hash_de_dobras_diferente_refaz_os_modelos(tmp_path, toys, monkeypatch):
    cfg = cfg_sessao(tmp_path)
    df = frame(seed=3)
    esperado = preparar_referencias(cfg, df, tmp_path)
    rodar(cfg, df, esperado, ganchos=())

    outro = frame(seed=11)  # outras linhas: outro hash de dobras
    esperado = preparar_referencias(cfg, outro, tmp_path)
    chamados = espiar_tune(monkeypatch)
    rodar(cfg, outro, esperado, ganchos=())

    assert chamados == ["toy_a", "toy_b"]  # os dois CONCLUIDO têm o hash antigo


def test_hash_da_config_muda_com_qualquer_valor(tmp_path):
    cfg = cfg_sessao(tmp_path)
    copia = json.loads(json.dumps(cfg))
    assert runner.hash_config(cfg) == runner.hash_config(copia)
    assert runner.hash_config(cfg) != runner.hash_config({**cfg, "shap": {"amostra": 1}})


# --- Checagem inicial -------------------------------------------------------------------------

def _checks_falhos(cfg) -> list[str]:
    bloco = blocos(cfg)["checagem_inicial"]
    return [c["nome"] for c in bloco["checks"] if not c["passou"]]


def test_checagem_reprova_sha_do_dbc_e_nao_treina(tmp_path, toys, monkeypatch):
    cfg = cfg_sessao(tmp_path)
    df = frame()
    esperado = preparar_referencias(cfg, df, tmp_path, dbc={"2022": "a" * 64, "2023": "f" * 64})
    manifesto = Path(cfg["caminhos"]["dados"]) / "manifest.json"
    manifesto.write_text(json.dumps({
        "2022": {"sha256_dbc": "a" * 64}, "2023": {"sha256_dbc": "e" * 64}}), encoding="utf-8")
    chamados = espiar_tune(monkeypatch)

    with pytest.raises(ChecagemInicialFalhou, match="sha256_dbc_2023"):
        rodar(cfg, df, esperado, ganchos=())

    assert chamados == []
    assert _checks_falhos(cfg) == ["sha256_dbc_2023"]
    assert relatorio(cfg)["passou"] is False
    assert not concluido(cfg, "toy_a")


def test_checagem_reprova_hash_das_dobras_e_nao_treina(tmp_path, toys, monkeypatch):
    cfg = cfg_sessao(tmp_path)
    df = frame()
    esperado = preparar_referencias(cfg, df, tmp_path, hash_dobras="0" * 64)
    chamados = espiar_tune(monkeypatch)

    with pytest.raises(ChecagemInicialFalhou, match="hash_conteudo_dobras"):
        rodar(cfg, df, esperado, ganchos=())

    assert chamados == []
    assert _checks_falhos(cfg) == ["hash_conteudo_dobras"]


def test_checagem_reprova_ram_abaixo_do_minimo_do_config(tmp_path, toys, monkeypatch):
    cfg = {**cfg_sessao(tmp_path), "ambiente": {"gpu": None, "ram_min_gib": 10 ** 6}}
    df = frame()
    esperado = preparar_referencias(cfg, df, tmp_path)
    chamados = espiar_tune(monkeypatch)

    with pytest.raises(ChecagemInicialFalhou, match="ram_gib"):
        rodar(cfg, df, esperado, ganchos=())

    assert chamados == []
    assert _checks_falhos(cfg) == ["ram_gib"]


# --- Gravação com novas tentativas (item 7) ---------------------------------------------------

def test_gravacao_repete_erro_de_es_na_primeira_tentativa(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "PAUSA_E_S_S", 0.0)
    original = runner._substituir
    chamadas = []

    def falha_na_primeira(origem, destino):
        chamadas.append(origem)
        if len(chamadas) == 1:
            raise OSError("falha passageira do Drive")
        original(origem, destino)

    monkeypatch.setattr(runner, "_substituir", falha_na_primeira)
    destino = tmp_path / "pasta" / "arquivo.json"

    runner._gravar_json(destino, {"x": 1})

    assert len(chamadas) == 2
    assert json.loads(destino.read_text(encoding="utf-8")) == {"x": 1}
    assert not [p for p in destino.parent.iterdir() if p.name.startswith(".tmp-")]


def test_gravacao_desiste_depois_de_quatro_tentativas_sem_deixar_arquivo_pela_metade(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(runner, "PAUSA_E_S_S", 0.0)
    chamadas = []

    def sempre_falha(origem, destino):
        chamadas.append(origem)
        raise OSError("Drive indisponível")

    monkeypatch.setattr(runner, "_substituir", sempre_falha)
    destino = tmp_path / "arquivo.json"

    with pytest.raises(OSError, match="indisponível"):
        runner._gravar_json(destino, {"x": 1})

    assert len(chamadas) == runner.TENTATIVAS_E_S == 4  # 1 tentativa + 3 novas
    assert not destino.exists()


# --- Ganchos ----------------------------------------------------------------------------------

def test_gancho_padrao_ausente_e_pulado_com_aviso(tmp_path, toys, caplog):
    cfg = cfg_sessao(tmp_path)
    df = frame()
    esperado = preparar_referencias(cfg, df, tmp_path)

    # Um gancho ausente seguido de um que roda: sem o 2º, o pulo não grava relatório algum.
    ganchos = (Gancho("selecao", "T-4.9", "dengue_sinan.selecao_inexistente:executar"),
               Gancho("teste", "T-0.0", "", funcao=gancho_ok))
    with caplog.at_level(logging.WARNING, logger="dengue_sinan.runner"):
        rodar(cfg, df, esperado, ganchos=ganchos)  # módulo que não existe: pulado com aviso

    assert "gancho selecao" in caplog.text and "pulado" in caplog.text
    rel = relatorio(cfg)
    assert [b["bloco"] for b in rel["blocos"]] == ["checagem_inicial", "toy_a", "toy_b", "teste"]
    assert rel["sessao_completa"] is False and rel["passou"] is False


def test_resolver_devolve_none_para_gancho_que_nao_existe():
    assert runner._resolver("dengue_sinan.selecao_inexistente:executar") is None
    assert callable(runner._resolver("dengue_sinan.selecao:executar"))  # T-4.9 existe agora
    assert runner._resolver("dengue_sinan.runner:funcao_que_nao_existe") is None
    assert callable(runner._resolver("dengue_sinan.runner:main"))


# --- Config da sessão e entrada de linha de comando -------------------------------------------

def test_config_da_sessao_aponta_dados_e_mlruns_para_o_drive(tmp_path):
    cfg = cfg_sessao(tmp_path)
    pasta = tmp_path / "drive_projeto"

    caminho = runner.config_da_sessao(cfg, pasta)

    lido = load_config(caminho)  # passa na validação de load_config
    assert lido["caminhos"]["dados"] == str(pasta / "data")
    assert lido["caminhos"]["mlruns"] == str(pasta / "mlruns")
    assert lido["caminhos"]["modelos"] == str(pasta / "models")  # T-4.10: artefatos no Drive
    assert lido["seed"] == cfg["seed"] and lido["ordem_dobras"] == cfg["ordem_dobras"]


def test_entrada_devolve_zero_quando_a_sessao_termina(tmp_path, monkeypatch):
    cfg = cfg_sessao(tmp_path)
    caminho = tmp_path / "config.yaml"
    caminho.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")
    monkeypatch.setattr(runner, "run_all_models", lambda cfg_, **kw: {})

    assert runner.main(["--config", str(caminho)]) == 0


def test_entrada_devolve_um_quando_run_all_models_levanta(tmp_path, monkeypatch):
    cfg = cfg_sessao(tmp_path)
    caminho = tmp_path / "config.yaml"
    caminho.write_text(yaml.safe_dump(cfg, allow_unicode=True), encoding="utf-8")

    def levanta(cfg_, **kw):
        raise RuntimeError("falha simulada na sessão")

    monkeypatch.setattr(runner, "run_all_models", levanta)

    assert runner.main(["--config", str(caminho)]) == 1


# --- Cobertura das mutações sobreviventes (Sakura, T-4.3b) ------------------------------------

def test_mudanca_no_config_refaz_os_modelos(tmp_path, toys, monkeypatch):
    cfg = cfg_sessao(tmp_path)
    df = frame()
    esperado = preparar_referencias(cfg, df, tmp_path)
    rodar(cfg, df, esperado, ganchos=())

    mudado = {**cfg, "optuna": {**cfg["optuna"], "max_tentativas": {"toy_a": 3, "toy_b": 3}}}
    chamados = espiar_tune(monkeypatch)
    rodar(mudado, df, esperado, ganchos=())

    assert chamados == ["toy_a", "toy_b"]  # mesmas dobras, config diferente: CONCLUIDO não vale


def test_erro_que_nao_e_de_es_nao_e_repetido_e_nao_deixa_lixo(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "PAUSA_E_S_S", 0.0)
    chamadas: list[Path] = []
    destino = tmp_path / "pasta" / "arquivo.json"

    def escrever(tmp: Path) -> None:
        chamadas.append(tmp)
        tmp.write_text("parcial", encoding="utf-8")
        raise ValueError("erro de lógica, não de E/S")

    with pytest.raises(ValueError, match="erro de lógica"):
        runner._gravar_atomico(destino, escrever)

    assert len(chamadas) == 1  # uma única tentativa: só E/S é repetida
    assert not destino.exists()
    assert not [p for p in destino.parent.iterdir() if p.name.startswith(".tmp-")]


def test_modelo_que_reprova_um_check_nao_ganha_concluido_e_treina_de_novo(
    tmp_path, toys, monkeypatch
):
    cfg = cfg_sessao(tmp_path)
    df = frame()
    esperado = preparar_referencias(cfg, df, tmp_path)
    apertado = {**cfg, "orcamento_teto_min": {**cfg["orcamento_teto_min"], "toy_a": 1e-6}}

    rodar(apertado, df, esperado, ganchos=())  # teto de tempo estourado no toy_a

    bloco = blocos(cfg)["toy_a"]
    assert bloco["passou"] is False
    assert [c["nome"] for c in bloco["checks"] if not c["passou"]] == [
        "tempo_busca_dentro_do_teto"]
    assert not concluido(cfg, "toy_a")  # reprovado: sem marcador
    assert concluido(cfg, "toy_b")

    chamados = espiar_tune(monkeypatch)
    rodar(cfg, df, esperado, ganchos=())  # teto normal de volta

    # O teto voltou ao normal: a config mudou, então o hash de config do toy_b também muda e
    # ele refaz; o que este teste prova é que o toy_a, reprovado, treina de novo.
    assert chamados == ["toy_a", "toy_b"]
    assert concluido(cfg, "toy_a")


def test_gancho_do_primeiro_ausente_impede_sessao_completa(tmp_path, toys):
    cfg = cfg_sessao(tmp_path)
    df = frame()
    esperado = preparar_referencias(cfg, df, tmp_path)

    rodar(cfg, df, esperado, ganchos=(
        Gancho("selecao", "T-4.9", "dengue_sinan.selecao_inexistente:executar"),  # não existe
        Gancho("teste", "T-0.0", "", funcao=gancho_ok),
    ))

    rel = relatorio(cfg)
    assert "teste" in [b["bloco"] for b in rel["blocos"]]  # o último rodou
    assert rel["sessao_completa"] is False  # mas o 1º foi pulado


@pytest.mark.parametrize("campo, nome", [("populacao_total", "casos_dev"),
                                         ("eventos_total", "eventos_dev")])
def test_checagem_reprova_casos_e_eventos_diferentes_do_esperado(
    tmp_path, toys, monkeypatch, campo, nome
):
    cfg = cfg_sessao(tmp_path)
    df = frame()
    esperado = preparar_referencias(cfg, df, tmp_path)
    dados = yaml.safe_load(esperado.read_text(encoding="utf-8"))
    dados["desenvolvimento"][campo] += 1  # o esperado não bate com o df
    esperado.write_text(yaml.safe_dump(dados), encoding="utf-8")
    chamados = espiar_tune(monkeypatch)

    with pytest.raises(ChecagemInicialFalhou, match=nome):
        rodar(cfg, df, esperado, ganchos=())

    assert chamados == []
    assert _checks_falhos(cfg) == [nome]


# --- Modelo sem busca (TabFM, D-69): uma execução, sem Optuna, sem alias -----------------------

def _fabrica_sem_busca(params, cfg):
    """Fábrica de um modelo sem hiperparâmetros: recebe `{}` e nunca um espaço de busca."""
    assert params == {}, params
    return ToyPlano(1.0)


def test_modelo_sem_busca_roda_uma_vez_sem_tune_e_sem_checks_de_alias(tmp_path, monkeypatch):
    monkeypatch.setitem(cv.REGISTRO, "toy_sb", _fabrica_sem_busca)
    cfg = cfg_sessao(tmp_path)
    cfg["ordem_modelos"] = ["toy_sb"]
    cfg["busca"] = {"toy_sb": {"sem_busca": True}}
    cfg["orcamento_teto_min"] = {"toy_sb": 30}
    cfg["optuna"]["max_tentativas"] = {"toy_sb": 1}
    df = frame()
    esperado = preparar_referencias(cfg, df, tmp_path)

    def tune_proibido(cfg_, modelo, df_):
        raise AssertionError(f"tune não deve rodar para {modelo} (sem_busca)")

    monkeypatch.setattr(tuning, "tune", tune_proibido)
    resultados = rodar(cfg, df, esperado, ganchos=())

    assert resultados["toy_sb"]["melhores_parametros"] == {}
    assert concluido(cfg, "toy_sb")
    parametros = json.loads((runner.pasta_m1(cfg) / "toy_sb" / runner.ARQ_PARAMETROS).read_text(
        encoding="utf-8"))
    assert parametros["tuning"]["sem_busca"] is True
    assert parametros["tuning"]["tentativas_concluidas"] == 0
    bloco = blocos(cfg)["toy_sb"]
    nomes = [c["nome"] for c in bloco["checks"]]
    assert "alias_melhor_validacao" not in nomes and "tentativa_concluida" not in nomes
    assert {"oof_uma_linha_por_caso", "pr_auc_em_todas_as_dobras"} <= set(nomes)
    assert bloco["passou"] is True


# --- Bloco `shap` entra no relatório pela sessão; ordem dos ganchos padrão -------------------

def checks_shap_fieis() -> list[dict]:
    """Mesmos nomes e formato que `verificacao_shap.checks` devolve (sem rodar o SHAP)."""
    return [
        verify.check("agregados_gravados", True, True),
        verify.check("amostra_tamanho", 150, 150),
        verify.check("aditividade_erro_max", 0.0, 1e-7, tolerancia=1e-4),
    ]


def test_bloco_shap_vai_para_o_relatorio_da_sessao(tmp_path, toys):
    cfg = cfg_sessao(tmp_path)
    df = frame()
    esperado = preparar_referencias(cfg, df, tmp_path)
    chamadas = []

    def gancho_shap(cfg_, resultados):
        chamadas.append(sorted(resultados))
        return checks_shap_fieis()

    rodar(cfg, df, esperado, ganchos=(Gancho("shap", "T-4.8", "", funcao=gancho_shap),))

    bloco = blocos(cfg)["shap"]  # o runner grava o bloco a partir dos checks devolvidos
    assert bloco["tarefa"] == "T-4.8"
    assert bloco["checks"] == checks_shap_fieis()
    assert bloco["passou"] is True
    assert chamadas == [["toy_a", "toy_b"]]  # o gancho recebe o resultado de cada modelo


def test_ganchos_padrao_rodam_selecao_shap_e_retreino_nessa_ordem():
    assert [(g.bloco, g.tarefa, g.alvo) for g in runner.GANCHOS_PADRAO] == [
        ("selecao", "T-4.9", "dengue_sinan.selecao:executar"),
        ("shap", "T-4.8", "dengue_sinan.shap_global:executar_sessao"),
        ("retreino", "T-4.10", "dengue_sinan.retreino:executar"),
    ]
    for gancho in runner.GANCHOS_PADRAO:  # cada alvo existe e é chamável
        assert callable(runner._resolver(gancho.alvo)), gancho.alvo
