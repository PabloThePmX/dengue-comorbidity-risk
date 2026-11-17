"""Retreino final e congelamento do M1 (T-4.10) com dados sintéticos e árvores pequenas.

Nada aqui lê microdados (R7) nem o ano de teste (R1). Os artefatos vão para pastas temporárias.
Os checks reais (2022–23 completo, tempos na máquina do Colab) saem na sessão do Colab, não aqui.
"""

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dengue_sinan import artifacts, cv, retreino, runner, selecao, verify
from dengue_sinan.catboost_m1 import CatBoostM1
from dengue_sinan.config import load_config
from dengue_sinan.elastic_net_m1 import ElasticNetM1
from dengue_sinan.mlp import MLPM1
from dengue_sinan.profiling import COMORBIDADES, SINAIS
from dengue_sinan.random_forest import RandomForestM1
from dengue_sinan.xgboost_m1 import XGBoostM1

ORDEM = ["A", "B", "C"]  # 3 dobras: a mediana precisa de nº ímpar
N_POR_REGIAO = 150
PARAMS = {
    "xgboost": {
        "tree_method": "hist", "n_estimators": 300, "early_stopping_rounds": 5,
        "eval_metric": "aucpr", "learning_rate": 0.3, "max_depth": 3, "min_child_weight": 1.0,
        "subsample": 0.8, "colsample_bytree": 0.8, "reg_lambda": 1.0, "device": "cpu",
    },
    "catboost": {
        "loss_function": "Logloss", "iterations": 300, "od_type": "Iter", "od_wait": 5,
        "eval_metric": "PRAUC", "learning_rate": 0.1, "depth": 3, "l2_leaf_reg": 3.0,
        "device": "cpu",
    },
    "mlp": {
        "camadas_ocultas": "8", "dropout": 0.0, "weight_decay": 0.0001, "lr": 0.01,
        "batch_size": 256, "perda": "BCEWithLogitsLoss", "otimizador": "Adam",
        "epocas_max": 20, "paciencia_epocas": 3, "device": "cpu",
    },
    "elastic_net": {"C": 1.0, "l1_ratio": 0.5, "solver": "saga", "max_iter": 500},
    "random_forest": {"n_estimators": 20, "max_depth": 4, "min_samples_leaf": 5,
                      "max_features": "sqrt", "max_samples": 0.5, "criterion": "gini",
                      "bootstrap": True},
}


def cfg_teste(tmp_path: Path) -> dict:
    base = load_config()
    return {
        **copy.deepcopy(base),
        "anos_dev": [2022, 2023],
        "ordem_dobras": ORDEM,
        "ordem_modelos": ["elastic_net", "xgboost"],
        "caminhos": {
            "dados": str(tmp_path / "data"),
            "relatorios": str(tmp_path / "reports"),
            "mlruns": str(tmp_path / "mlruns"),
            "modelos": str(tmp_path / "models"),
        },
        "seed": 11,
    }


def frame(seed: int = 3) -> pd.DataFrame:
    """Casos com as features do dicionário (as que o M1 lê) e sinal fraco, 2022 e 2023."""
    rng = np.random.default_rng(seed)
    n = N_POR_REGIAO * len(ORDEM)
    df = pd.DataFrame({
        "ANO": rng.choice([2022, 2023], n).astype("int64"),
        "regiao": np.repeat(ORDEM, N_POR_REGIAO),
        "idade_anos": rng.uniform(0, 90, n),
        "sexo": rng.choice(["F", "M", "I"], n),
        "gestante": rng.integers(0, 2, n).astype("int8"),
        "dias_ate_notificacao": rng.integers(0, 60, n),
    })
    for c in [*COMORBIDADES, *SINAIS]:
        df[c] = rng.choice(["Sim", "Não", "Ausente"], n, p=[0.2, 0.7, 0.1])
    df["n_comorbidades"] = sum((df[c] == "Sim").astype(int) for c in COMORBIDADES)
    risco = 0.1 + 0.4 * (df["RENAL"] == "Sim") + 0.2 * (df["DIABETES"] == "Sim")
    df["y"] = (rng.uniform(size=n) < risco).astype("int64")
    return df.reset_index(drop=True)


def _pontos(valores: list[int]) -> dict[str, int]:
    return dict(zip(ORDEM, valores, strict=True))


def preparar_sessao(cfg: dict, df: pd.DataFrame) -> dict:
    """Pastas de `m1/` com parâmetros, métricas, calibrador e `selecao.json` (como a T-4.9 grava).

    Vencedor: XGBoost (melhores pontos 2, 4, 6: mediana 4, então 5 árvores). Candidato da demo:
    elastic net. Os calibradores são ajustados em predições sintéticas, como em `selecao.py`.
    """
    raiz = runner.pasta_m1(cfg)
    rng = np.random.default_rng(5)
    modelos_sel = {}
    melhores = {"xgboost": _pontos([2, 4, 6]), "mlp": _pontos([3, 4, 5]),
                "catboost": _pontos([2, 4, 6]), "elastic_net": None, "random_forest": None}
    for nome, pontos in [("xgboost", melhores["xgboost"]), ("elastic_net", None)]:
        pasta = raiz / nome
        pasta.mkdir(parents=True, exist_ok=True)
        p = rng.uniform(0.01, 0.9, 300)
        y = (rng.uniform(size=300) < p).astype(int)
        cal = selecao.ajustar_platt(p, y)
        selecao.salvar_calibrador(cal, pasta)
        melhores_pontos = pontos or {r: None for r in ORDEM}
        (pasta / runner.ARQ_PARAMETROS).write_text(json.dumps({
            "modelo": nome, "melhores_parametros": PARAMS[nome], "tuning": {}, "hash_dobras": "h",
            "hash_config": "c"}), encoding="utf-8")
        (pasta / runner.ARQ_METRICAS).write_text(json.dumps({
            "modelo": nome, "oof_pr_auc": 0.2, "pr_auc_media": 0.21 if nome == "xgboost" else 0.19,
            "pr_auc_por_dobra": {r: 0.2 for r in ORDEM}, "melhores_pontos": melhores_pontos,
            "linhas_oof": 450}), encoding="utf-8")
        modelos_sel[nome] = {
            "pr_auc_media": 0.21 if nome == "xgboost" else 0.19,
            "ic_95": [0.1, 0.3], "brier_calibrado": 0.1, "brier_fora_da_dobra": {},
            "calibrador": "platt", "limiar": 0.4,
        }
    sel = {
        "tarefa": "T-4.9", "vencedor": "xgboost", "empatados": ["xgboost"],
        "motivo": "maior PR-AUC média (teste)", "calibrador": "platt", "limiar": 0.4,
        "modelos": modelos_sel,
    }
    (raiz / selecao.NOME_SELECAO).write_text(json.dumps(sel), encoding="utf-8")
    manifesto = Path(cfg["caminhos"]["dados"]) / "manifest.json"
    manifesto.parent.mkdir(parents=True, exist_ok=True)
    manifesto.write_text(json.dumps({
        str(a): {"sha256_dbc": f"dbc{a}", "sha256_parquet": f"pq{a}"} for a in cfg["anos_dev"]
    }), encoding="utf-8")
    return {"xgboost": {"pasta": str(raiz / "xgboost")},
            "elastic_net": {"pasta": str(raiz / "elastic_net")}}


def _checks_por_nome(checks: list[dict]) -> dict[str, dict]:
    return {c["nome"]: c for c in checks}


# --- Contagem (D-37) ------------------------------------------------------------------------

def test_mediana_dos_pontos_vira_contagem_com_o_deslocamento_de_cada_familia():
    assert retreino.contagem_final("xgboost", [10, 3, 7, 5, 9]) == 8  # índice 7 + 1 árvore
    assert retreino.contagem_final("catboost", [10, 3, 7, 5, 9]) == 8
    assert retreino.contagem_final("mlp", [10, 3, 7, 5, 9]) == 7  # épocas são 1-based


def test_contagem_recusa_ponto_faltando_dobra_par_e_modelo_sem_regra():
    with pytest.raises(ValueError, match="falta o melhor ponto"):
        retreino.contagem_final("xgboost", [1, None, 3])
    with pytest.raises(ValueError, match="ímpar"):
        retreino.contagem_final("xgboost", [1, 2, 3, 4])
    with pytest.raises(ValueError, match="sem regra"):
        retreino.contagem_final("elastic_net", [1, 2, 3])


# --- Wrappers com número fixo de iterações (sem X_parada) -----------------------------------

def test_xgboost_com_arvores_fixas_treina_sem_parada_e_usa_so_essas_arvores():
    df = frame()
    modelo, n = retreino.treinar_final({"seed": 11, "validacao_interna_frac": 0.1},
                                       "xgboost", PARAMS["xgboost"], df, [2, 4, 6])
    assert isinstance(modelo, XGBoostM1) and n == 5
    assert modelo.melhor_ponto() == 4
    assert modelo._estimador.get_booster().num_boosted_rounds() == 5
    assert modelo._estimador.get_params()["early_stopping_rounds"] is None
    p = modelo.prever_proba(df.iloc[:50])
    assert ((p >= 0) & (p <= 1)).all()


def test_fixar_iteracoes_recusa_validacao_de_parada_e_contagem_invalida():
    df = frame()
    modelo = cv.construir_modelo("xgboost", PARAMS["xgboost"], {"seed": 1})
    modelo.fixar_iteracoes(3)
    y = df["y"].to_numpy()
    with pytest.raises(ValueError, match="não usa validação de parada"):
        modelo.ajustar(df, y, df, y)
    with pytest.raises(ValueError, match="inteiro"):
        cv.construir_modelo("xgboost", PARAMS["xgboost"], {"seed": 1}).fixar_iteracoes(0)


def test_catboost_com_arvores_fixas_grava_exatamente_n_arvores():
    df = frame()
    modelo, n = retreino.treinar_final({"seed": 11}, "catboost", PARAMS["catboost"], df, [1, 3, 5])
    assert isinstance(modelo, CatBoostM1) and n == 4
    assert modelo._estimador.tree_count_ == 4
    assert modelo.melhor_ponto() == 3


def test_mlp_com_epocas_fixas_treina_n_epocas_sem_validacao():
    df = frame()
    modelo, n = retreino.treinar_final({"seed": 11}, "mlp", PARAMS["mlp"], df, [3, 4, 5])
    assert isinstance(modelo, MLPM1) and n == 4  # mediana de [3, 4, 5]
    assert modelo.melhor_ponto() == 4
    assert len(modelo._estimador.historico_) == 4
    assert all("pr_auc_parada" not in h for h in modelo._estimador.historico_)


def test_nao_iterativos_treinam_com_o_conjunto_inteiro_e_sem_contagem():
    df = frame()
    for nome, classe in [("elastic_net", ElasticNetM1), ("random_forest", RandomForestM1)]:
        modelo, n = retreino.treinar_final({"seed": 11}, nome, PARAMS[nome], df, [None] * 3)
        assert isinstance(modelo, classe) and n is None
        p = modelo.prever_proba(df.iloc[:40])
        assert ((p >= 0) & (p <= 1)).all()


# --- Modelo da demo (D-69, D-70) -----------------------------------------------------------

def _medicao(nome: str, tempo: float = 0.2, viavel: bool = True) -> retreino.Medicao:
    return retreino.Medicao(nome=nome, bytes_payload=10, bytes_pasta=20,
                            tempo_predicao_s=tempo / 2, shap_viavel=viavel,
                            tempo_shap_s=tempo / 2 if viavel else None,
                            erro_shap=None if viavel else "ValueError")


def test_cumpre_demo_so_com_sem_tabfm_ate_um_segundo_e_shap_viavel():
    assert retreino.cumpre_demo(_medicao("xgboost", tempo=0.4))
    assert not retreino.cumpre_demo(_medicao("tabfm", tempo=0.4))
    assert not retreino.cumpre_demo(_medicao("xgboost", tempo=1.5))
    assert not retreino.cumpre_demo(_medicao("xgboost", viavel=False))
    motivos = retreino.razoes_fora_da_demo(_medicao("tabfm", tempo=1.5))
    assert len(motivos) == 2 and "licença" in motivos[0]


def test_ordem_da_demo_tira_o_vencedor_e_o_tabfm_e_ordena_por_pr_auc():
    modelos = {
        "tabfm": {"pr_auc_media": 0.9}, "xgboost": {"pr_auc_media": 0.5},
        "elastic_net": {"pr_auc_media": 0.4}, "catboost": {"pr_auc_media": 0.5},
        "random_forest": {"pr_auc_media": 0.2},
        "mlp": {"pr_auc_media": 0.3},
    }
    ordem = ["elastic_net", "xgboost", "catboost", "mlp", "random_forest", "tabfm"]
    assert retreino.ordem_demo(modelos, ordem, "xgboost") == [
        "catboost", "elastic_net", "mlp", "random_forest"]


def _fake_congelar(medicoes: dict[str, retreino.Medicao], chamadas: list[str]):
    """Substitui `_congelar`: grava só uma pasta com um arquivo e devolve a medição dada."""
    def fake(cfg, nome, df, resultados, sel, pasta, papel, hash_dobras):
        chamadas.append(nome)
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "payload.txt").write_text(nome, encoding="utf-8")
        return retreino.Congelado(
            nome=nome, papel=papel, pasta=pasta, iteracoes=5, medicao=medicoes[nome],
            carga_ok=True, diferenca_maxima=0.0, sha256_no_metadata="x", sha256_no_arquivo="x",
            limiar=0.4, limiar_selecao=0.4, calibrador_ok=True, sem_contagens=True,
            features_ok=True)
    return fake


def _rodar_fake(tmp_path, monkeypatch, vencedor: str, medicoes: dict):
    cfg = cfg_teste(tmp_path)
    df = frame()
    resultados = preparar_sessao(cfg, df)
    sel = json.loads((runner.pasta_m1(cfg) / selecao.NOME_SELECAO).read_text(encoding="utf-8"))
    sel["vencedor"] = vencedor
    sel["modelos"]["tabfm"] = {"pr_auc_media": 0.95, "brier_calibrado": 0.1,
                               "calibrador": "platt", "limiar": 0.4}
    sel["modelos"]["mlp"] = {"pr_auc_media": 0.3, "brier_calibrado": 0.1,
                             "calibrador": "platt", "limiar": 0.4}
    (runner.pasta_m1(cfg) / selecao.NOME_SELECAO).write_text(json.dumps(sel), encoding="utf-8")
    cfg["ordem_modelos"] = ["tabfm", "xgboost", "mlp", "elastic_net"]
    monkeypatch.setattr(runner, "_carregar_dados_de_desenvolvimento", lambda c: df)
    chamadas: list[str] = []
    monkeypatch.setattr(retreino, "_congelar", _fake_congelar(medicoes, chamadas))
    checks = retreino.executar(cfg, resultados)
    return cfg, _checks_por_nome(checks), chamadas


def test_vencedor_tabfm_escolhe_o_melhor_candidato_que_cumpre(tmp_path, monkeypatch):
    medicoes = {"tabfm": _medicao("tabfm", 0.1), "xgboost": _medicao("xgboost", 0.4),
                "mlp": _medicao("mlp", 0.4), "elastic_net": _medicao("elastic_net", 0.1)}
    cfg, por_nome, chamadas = _rodar_fake(tmp_path, monkeypatch, "tabfm", medicoes)
    assert chamadas == ["tabfm", "mlp"]  # mlp tem o maior PR-AUC entre os que não são TabFM
    assert por_nome["modelo_demo"]["obtido"] == "mlp"  # PR-AUC 0,3 > 0,19 de elastic net
    assert por_nome["modelo_demo_definido"]["passou"] is True
    assert "TabFM" in por_nome["motivo_demo"]["obtido"]


def test_tempo_acima_de_um_segundo_substitui_o_vencedor_na_demo(tmp_path, monkeypatch):
    medicoes = {"tabfm": _medicao("tabfm", 0.1), "xgboost": _medicao("xgboost", 1.6),
                "mlp": _medicao("mlp", 1.6), "elastic_net": _medicao("elastic_net", 0.2)}
    _, por_nome, chamadas = _rodar_fake(tmp_path, monkeypatch, "xgboost", medicoes)
    assert chamadas == ["xgboost", "mlp", "elastic_net"]  # tabfm nunca entra na demo
    assert por_nome["modelo_demo"]["obtido"] == "elastic_net"
    assert "acima de 1 s" in por_nome["motivo_demo"]["obtido"]


def test_vencedor_que_cumpre_vira_a_propria_demo_sem_treinar_outro(tmp_path, monkeypatch):
    medicoes = {"tabfm": _medicao("tabfm", 0.1), "xgboost": _medicao("xgboost", 0.3),
                "mlp": _medicao("mlp", 0.3), "elastic_net": _medicao("elastic_net", 0.3)}
    _, por_nome, chamadas = _rodar_fake(tmp_path, monkeypatch, "xgboost", medicoes)
    assert chamadas == ["xgboost"]
    assert por_nome["modelo_demo"]["obtido"] == "xgboost"


def test_sem_candidato_que_cumpra_a_sessao_reprova_o_bloco(tmp_path, monkeypatch):
    medicoes = {"tabfm": _medicao("tabfm", 0.1), "xgboost": _medicao("xgboost", 2.0),
                "mlp": _medicao("mlp", 2.0), "elastic_net": _medicao("elastic_net", 2.0)}
    _, por_nome, _ = _rodar_fake(tmp_path, monkeypatch, "xgboost", medicoes)
    assert por_nome["modelo_demo_definido"]["passou"] is False
    assert por_nome["modelo_demo"]["obtido"] == "nenhum"


# --- Integração real pequena: gravação, recarga, adulteração e R1 ----------------------------

@pytest.fixture
def sessao_real(tmp_path, monkeypatch):
    cfg = cfg_teste(tmp_path)
    df = frame()
    resultados = preparar_sessao(cfg, df)
    monkeypatch.setattr(runner, "_carregar_dados_de_desenvolvimento", lambda c: df)
    return cfg, df, resultados


def test_executar_grava_o_artefato_recarrega_e_reproduz_as_predicoes(sessao_real):
    cfg, _, resultados = sessao_real
    checks = retreino.executar(cfg, resultados)
    por_nome = _checks_por_nome(checks)
    pasta = runner._caminho(cfg, "modelos") / "m1_final"
    assert (pasta / "payload" / "m1.joblib").exists()
    assert por_nome["m1_final_carrega_e_prediz"]["passou"] is True
    assert por_nome["m1_final_predicoes_iguais_apos_carga"]["passou"] is True
    assert por_nome["m1_final_sha256_payload"]["passou"] is True
    sha = por_nome["m1_final_sha256_payload"]
    assert sha["obtido"] == sha["esperado"]
    assert por_nome["m1_final_iteracoes_finais"]["obtido"] == 5
    assert por_nome["m1_final_limiar_da_selecao"]["obtido"] == 0.4
    assert por_nome["m1_final_calibrador_da_selecao"]["passou"] is True
    assert por_nome["m1_final_sem_contagens_por_nivel"]["passou"] is True
    assert por_nome["m1_final_features_sem_proibidas"]["passou"] is True
    assert por_nome["m1_final_tamanho_payload_bytes"]["obtido"] > 0
    assert por_nome["m1_final_tempo_predicao_um_caso_s"]["obtido"] >= 0
    assert por_nome["modelo_demo_definido"]["passou"] is True  # o vencedor cumpre aqui


def test_artefato_nao_guarda_dados_nem_contagens(sessao_real):
    cfg, _, resultados = sessao_real
    retreino.executar(cfg, resultados)
    pasta = runner._caminho(cfg, "modelos") / "m1_final"
    meta = artifacts.ler_metadados(pasta)
    assert artifacts.inteiros_pequenos(meta) == []  # R7
    carregado = artifacts.load_bundle(pasta)
    assert isinstance(carregado, retreino.ModeloFinal)
    for valor in vars(carregado).values():
        assert not isinstance(valor, pd.DataFrame)  # nenhuma linha de caso no artefato
    assert meta["m1"]["melhores_pontos"] == [2, 4, 6]  # só os pontos das dobras


def test_hash_do_payload_confere_e_adulteracao_e_recusada(sessao_real):
    cfg, _, resultados = sessao_real
    retreino.executar(cfg, resultados)
    pasta = runner._caminho(cfg, "modelos") / "m1_final"
    artifacts.load_bundle(pasta)  # íntegro: carrega
    arquivo = pasta / "payload" / "m1.joblib"
    arquivo.write_bytes(arquivo.read_bytes() + b"\x00")
    with pytest.raises(artifacts.ArtefatoInvalido, match="SHA-256"):
        artifacts.load_bundle(pasta)


def test_guarda_recusa_dado_de_2024_antes_de_treinar(tmp_path, monkeypatch):
    cfg = cfg_teste(tmp_path)
    df = frame()
    df.loc[0, "ANO"] = 2024
    resultados = preparar_sessao(cfg, df)
    monkeypatch.setattr(runner, "_carregar_dados_de_desenvolvimento", lambda c: df)
    with pytest.raises(RuntimeError, match="R1"):
        retreino.executar(cfg, resultados)
    assert not (runner._caminho(cfg, "modelos") / "m1_final").exists()


def test_calibrador_e_limiar_nao_sao_reajustados(sessao_real):
    cfg, _, resultados = sessao_real
    checks = _checks_por_nome(retreino.executar(cfg, resultados))
    da_selecao = selecao.carregar_calibrador(runner.pasta_m1(cfg) / "xgboost")
    carregado = artifacts.load_bundle(runner._caminho(cfg, "modelos") / "m1_final")
    dentro = carregado.calibrador  # o que foi gravado no bundle
    assert dentro.tipo == da_selecao.tipo
    assert sorted(dentro.arrays) == sorted(da_selecao.arrays)
    for chave in da_selecao.arrays:
        assert np.array_equal(dentro.arrays[chave], da_selecao.arrays[chave])
    sonda = np.linspace(0.001, 0.999, 101)
    assert np.array_equal(dentro.aplicar(sonda), da_selecao.aplicar(sonda))
    assert carregado.limiar == 0.4
    assert checks["m1_final_limiar_da_selecao"]["passou"] is True
    assert checks["m1_final_calibrador_da_selecao"]["passou"] is True


def test_guarda_2024_recusa_no_executar_sem_chamar_o_treino(tmp_path, monkeypatch):
    cfg = cfg_teste(tmp_path)
    df = frame()
    df.loc[0, "ANO"] = 2024
    resultados = preparar_sessao(cfg, df)
    monkeypatch.setattr(runner, "_carregar_dados_de_desenvolvimento", lambda c: df)
    chamadas: list[str] = []
    monkeypatch.setattr(retreino, "_congelar", _fake_congelar({}, chamadas))
    with pytest.raises(RuntimeError, match="R1"):
        retreino.executar(cfg, resultados)
    assert chamadas == []  # nada foi treinado nem gravado

def test_shap_local_por_familia_devolve_uma_contribuicao_por_coluna(tmp_path):
    df = frame()
    X = df.iloc[:1]
    for nome in ["xgboost", "catboost", "random_forest", "elastic_net", "mlp"]:
        modelo, _ = retreino.treinar_final({"seed": 11}, nome, PARAMS[nome], df, [2, 4, 6])
        referencia = retreino._referencia_mlp(modelo, df) if nome == "mlp" else None
        final = retreino.ModeloFinal(nome, modelo, selecao.ajustar_platt(
            np.linspace(0.1, 0.9, 50), np.arange(50) % 2), 0.5,
            ["x"], referencia)
        phi = retreino.shap_local(final, X)
        p = modelo._pipeline.named_steps["preprocessamento"].transform(X).shape[1]
        assert phi.shape == (p,) and np.isfinite(phi).all(), nome


def test_shap_local_recusa_modelo_sem_explicacao_local():
    final = retreino.ModeloFinal("tabfm", object(), selecao.ajustar_platt(
        np.linspace(0.1, 0.9, 50), np.arange(50) % 2), 0.5, [], None)
    with pytest.raises(ValueError, match="D-69"):
        retreino.shap_local(final, frame().iloc[:1])


# --- Gravação com novas tentativas e checks de verificação -----------------------------------

def test_gravacao_repete_em_erro_de_es_e_desiste_depois_do_limite(monkeypatch):
    monkeypatch.setattr(runner, "PAUSA_E_S_S", 0.0)
    chamadas = []

    def falha_uma_vez():
        chamadas.append(1)
        if len(chamadas) == 1:
            raise OSError("falha passageira do Drive")

    retreino._com_tentativas(falha_uma_vez)
    assert len(chamadas) == 2

    def sempre_falha():
        raise OSError("sem Drive")

    with pytest.raises(OSError):
        retreino._com_tentativas(sempre_falha)


def test_verify_maximo_e_registro_nao_reprovam_fora_do_limite():
    assert verify.maximo("tempo", 1.0, 0.4)["passou"] is True
    assert verify.maximo("tempo", 1.0, 1.4)["passou"] is False
    registro = verify.registro("tamanho", 123)
    assert registro["passou"] is True and registro["esperado"] is None
    assert verify.registro("motivo", "texto")["obtido"] == "texto"


def test_inteiros_pequenos_aceita_iteracoes_do_m1_e_recusa_contagem():
    ok = {"m1": {"iteracoes_finais": 5, "melhores_pontos": [2, 4, 6]}}
    assert artifacts.inteiros_pequenos(ok) == []
    assert artifacts.inteiros_pequenos({"m1": {"n_casos": 5}}) != []
