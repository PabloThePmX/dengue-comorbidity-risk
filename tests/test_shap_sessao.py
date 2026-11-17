"""Gancho `shap_global.executar_sessao` (T-4.8) com modelos sintéticos e árvores pequenas.

Nada aqui lê microdados (R7) nem o ano de teste (R1). Os arquivos vão para pastas temporárias.
"""

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dengue_sinan import runner, selecao, shap_global
from dengue_sinan.config import load_config
from dengue_sinan.profiling import COMORBIDADES, SINAIS

ORDEM = ["A", "B", "C"]
N_POR_REGIAO = 160
PARAMS = {
    "xgboost": {"tree_method": "hist", "n_estimators": 300, "early_stopping_rounds": 5,
                "eval_metric": "aucpr", "learning_rate": 0.3, "max_depth": 3,
                "min_child_weight": 1.0, "subsample": 0.8, "colsample_bytree": 0.8,
                "reg_lambda": 1.0, "device": "cpu"},
    "catboost": {"loss_function": "Logloss", "iterations": 300, "od_type": "Iter", "od_wait": 5,
                 "eval_metric": "PRAUC", "learning_rate": 0.1, "depth": 3, "l2_leaf_reg": 3.0,
                 "device": "cpu"},
    "elastic_net": {"C": 1.0, "l1_ratio": 0.5, "solver": "saga", "max_iter": 500},
}


def frame(seed: int = 4) -> pd.DataFrame:
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
    risco = 0.3 + 0.4 * (df["RENAL"] == "Sim") + 0.2 * (df["DIABETES"] == "Sim")
    df["y"] = (rng.uniform(size=n) < risco).astype("int64")
    return df.reset_index(drop=True)


def cfg_teste(tmp_path: Path) -> dict:
    base = load_config()
    return {
        **copy.deepcopy(base),
        "seed": 11,
        "ordem_dobras": ORDEM,
        "ordem_modelos": ["elastic_net", "xgboost", "catboost"],
        "shap": {"amostra": 150},
        "supressao_min_celula": 10,
        "caminhos": {"dados": str(tmp_path / "data"), "relatorios": str(tmp_path / "reports"),
                     "mlruns": str(tmp_path / "mlruns"), "modelos": str(tmp_path / "models")},
    }


def preparar(cfg: dict, vencedor: str, pr_auc: dict[str, float]) -> dict:
    """Pastas de cada modelo com parâmetros e métricas (pontos 2, 4, 6: mediana 4), e o
    `selecao.json` com o vencedor e o PR-AUC médio de cada um."""
    raiz = runner.pasta_m1(cfg)
    resultados = {}
    for nome in ["elastic_net", "xgboost", "catboost"]:
        pasta = raiz / nome
        pasta.mkdir(parents=True, exist_ok=True)
        pontos = None if nome == "elastic_net" else dict(zip(ORDEM, [2, 4, 6], strict=True))
        (pasta / runner.ARQ_PARAMETROS).write_text(json.dumps({
            "modelo": nome, "melhores_parametros": PARAMS[nome]}), encoding="utf-8")
        (pasta / runner.ARQ_METRICAS).write_text(json.dumps({
            "modelo": nome, "oof_pr_auc": pr_auc[nome], "pr_auc_media": pr_auc[nome],
            "pr_auc_por_dobra": {r: pr_auc[nome] for r in ORDEM},
            "melhores_pontos": pontos or {r: None for r in ORDEM}}), encoding="utf-8")
        resultados[nome] = {"pasta": str(pasta)}
    sel = {"vencedor": vencedor, "modelos": {
        nome: {"pr_auc_media": pr_auc[nome], "calibrador": "platt", "limiar": 0.4,
               "brier_calibrado": 0.1} for nome in pr_auc}}
    (raiz / selecao.NOME_SELECAO).write_text(json.dumps(sel), encoding="utf-8")
    return resultados


@pytest.fixture
def sessao(tmp_path, monkeypatch):
    df = frame()
    monkeypatch.setattr(runner, "_carregar_dados_de_desenvolvimento", lambda c: df)
    return df


def test_escolhe_o_vencedor_se_for_de_arvore_senao_o_de_maior_pr_auc():
    assert shap_global.escolher_modelo_shap(
        {"vencedor": "xgboost", "modelos": {}}) == "xgboost"
    sel = {"vencedor": "elastic_net", "modelos": {
        "xgboost": {"pr_auc_media": 0.2}, "catboost": {"pr_auc_media": 0.3},
        "elastic_net": {"pr_auc_media": 0.4}}}
    assert shap_global.escolher_modelo_shap(sel) == "catboost"
    empate = {"vencedor": "mlp", "modelos": {
        "xgboost": {"pr_auc_media": 0.2}, "catboost": {"pr_auc_media": 0.2}}}
    assert shap_global.escolher_modelo_shap(empate) == "xgboost"


def test_gancho_grava_agregados_e_devolve_checks_verdes(tmp_path, sessao):
    cfg = cfg_teste(tmp_path)
    resultados = preparar(cfg, "xgboost", {"elastic_net": 0.2, "xgboost": 0.3, "catboost": 0.25})

    checks = shap_global.executar_sessao(cfg, resultados)

    por_nome = {c["nome"]: c for c in checks}
    assert all(c["passou"] for c in checks), [c for c in checks if not c["passou"]]
    assert por_nome["amostra_tamanho"]["obtido"] == 150
    out = runner._caminho(cfg, "relatorios") / "shap"
    manifesto = shap_global.carregar_manifesto(out)
    assert manifesto["modelo"] == "xgboost"
    assert manifesto["n_arvores"] == 5  # mediana de [2, 4, 6] + 1
    assert shap_global.arquivos_conferem(out, manifesto)


def test_vencedor_nao_arvore_usa_o_catboost_se_tiver_maior_pr_auc(tmp_path, sessao):
    cfg = cfg_teste(tmp_path)
    resultados = preparar(cfg, "elastic_net",
                          {"elastic_net": 0.4, "xgboost": 0.2, "catboost": 0.3})

    shap_global.executar_sessao(cfg, resultados)

    manifesto = shap_global.carregar_manifesto(runner._caminho(cfg, "relatorios") / "shap")
    assert manifesto["modelo"] == "catboost"


def test_gancho_recusa_dado_de_2024_antes_de_ajustar(tmp_path, monkeypatch):
    cfg = cfg_teste(tmp_path)
    df = frame()
    df.loc[0, "ANO"] = 2024
    monkeypatch.setattr(runner, "_carregar_dados_de_desenvolvimento", lambda c: df)
    resultados = preparar(cfg, "xgboost", {"elastic_net": 0.2, "xgboost": 0.3, "catboost": 0.25})
    with pytest.raises(RuntimeError, match="R1"):
        shap_global.executar_sessao(cfg, resultados)
    assert not (runner._caminho(cfg, "relatorios") / "shap").exists()


def test_selecao_ainda_nao_existe_recusa(tmp_path, sessao):
    cfg = cfg_teste(tmp_path)
    with pytest.raises(FileNotFoundError, match="seleção"):
        shap_global.executar_sessao(cfg, {})


class ModeloSemGuarda:
    """Modelo falso que não confere o ano em nenhum método (o caso que a guarda do gancho cobre)."""

    iterativo = True

    def __init__(self) -> None:
        self.ajustou = False

    def fixar_iteracoes(self, n: int) -> None:
        pass

    def ajustar(self, X, y, *args, **kwargs) -> None:
        self.ajustou = True

    def melhor_ponto(self) -> int:
        return 4


def test_guarda_do_executar_sessao_dispara_antes_do_modelo(tmp_path, monkeypatch):
    from dengue_sinan import cv, guard

    cfg = cfg_teste(tmp_path)
    df = frame()
    df.loc[0, "ANO"] = 2024
    monkeypatch.setattr(runner, "_carregar_dados_de_desenvolvimento", lambda c: df)
    resultados = preparar(cfg, "xgboost", {"elastic_net": 0.2, "xgboost": 0.3, "catboost": 0.25})
    fake = ModeloSemGuarda()
    monkeypatch.setattr(cv, "construir_modelo", lambda nome, params, cfg_: fake)
    vistos = []

    def guarda_espiao(df_):  # o gancho importa a guarda do módulo no momento da chamada
        vistos.append(int(df_["ANO"].max()))
        raise RuntimeError("guarda espiã: executar_sessao disparou")

    monkeypatch.setattr(guard, "assert_dev_only", guarda_espiao)
    with pytest.raises(RuntimeError, match="guarda espiã"):
        shap_global.executar_sessao(cfg, resultados)
    assert vistos == [2024]
    assert fake.ajustou is False  # a guarda do gancho vem antes de qualquer ajuste
