"""Testes do SHAP global (T-4.8) com dados sintéticos e árvores pequenas, em CPU. Sem microdados.

Cobrem: amostra estratificada e determinística (R8), R1, cálculo à mão num toco de árvore,
identidades (aditividade, coerência, simetria) em XGBoost e CatBoost, uso só até o melhor ponto,
ponta a ponta com os wrappers, e a regra de não gravar nada por linha (R7).
"""

import csv
import json

import numpy as np
import pandas as pd
import pytest
import xgboost as xgb
from catboost import CatBoostClassifier

from dengue_sinan import shap_global
from dengue_sinan.catboost_m1 import CatBoostM1
from dengue_sinan.preprocess import FEATURES_PERMITIDAS, make_preprocessor
from dengue_sinan.profiling import COMORBIDADES, SINAIS
from dengue_sinan.xgboost_m1 import XGBoostM1

PARAMS_XGB = {
    "tree_method": "hist", "n_estimators": 20, "early_stopping_rounds": 5,
    "eval_metric": "aucpr", "learning_rate": 0.3, "max_depth": 3, "min_child_weight": 1.0,
    "subsample": 0.8, "colsample_bytree": 0.8, "reg_lambda": 1.0, "device": "cpu",
}
PARAMS_CAT = {
    "loss_function": "Logloss", "iterations": 30, "od_type": "Iter", "od_wait": 5,
    "eval_metric": "PRAUC", "learning_rate": 0.1, "depth": 3, "l2_leaf_reg": 3.0,
    "device": "cpu",
}


def cfg_teste(tmp_path, amostra: int = 300) -> dict:
    return {
        "seed": 7,
        "ano_teste": 2024,
        "anos_dev": [2022, 2023],
        "supressao_min_celula": 10,
        "shap": {"amostra": amostra},
        "caminhos": {"dados": str(tmp_path / "data"), "relatorios": str(tmp_path / "reports")},
    }


def frame(n: int = 600, seed: int = 3, ano: int = 2022) -> pd.DataFrame:
    """Casos com as 26 features do dicionário e um sinal, para haver o que explicar."""
    rng = np.random.default_rng(seed)
    df = pd.DataFrame({
        "ANO": np.full(n, ano, dtype="int64"),
        "idade_anos": rng.uniform(0, 90, n),
        "sexo": rng.choice(["F", "M", "I"], n),
        "gestante": rng.integers(0, 2, n).astype("int8"),
        "dias_ate_notificacao": rng.integers(0, 60, n),
    })
    for c in [*COMORBIDADES, *SINAIS]:
        df[c] = rng.choice(["Sim", "Não", "Ausente"], n, p=[0.2, 0.7, 0.1])
    df["n_comorbidades"] = sum((df[c] == "Sim").astype(int) for c in COMORBIDADES)
    risco = 0.05 + 0.4 * (df["RENAL"] == "Sim") + 0.2 * (df["DIABETES"] == "Sim")
    df["y"] = (rng.uniform(size=n) < risco).astype("int64")
    return df.reset_index(drop=True)


def xgb_ajustado(df: pd.DataFrame) -> XGBoostM1:
    modelo = XGBoostM1(PARAMS_XGB, seed=7)
    n_p = len(df) // 5
    modelo.ajustar(df.iloc[n_p:], df["y"].to_numpy()[n_p:],
                   df.iloc[:n_p], df["y"].to_numpy()[:n_p])
    return modelo


def cat_ajustado(df: pd.DataFrame) -> CatBoostM1:
    modelo = CatBoostM1(PARAMS_CAT, seed=7)
    n_p = len(df) // 5
    modelo.ajustar(df.iloc[n_p:], df["y"].to_numpy()[n_p:],
                   df.iloc[:n_p], df["y"].to_numpy()[:n_p])
    return modelo


# ---------- amostra estratificada e determinística (R8) ----------

def test_amostra_tem_n_linhas_ordenadas_sem_repeticao_e_mesma_proporcao():
    y = np.array([1] * 300 + [0] * 2700)
    pos = shap_global.amostra_estratificada(y, 500, seed=11)
    assert pos.size == 500
    assert np.all(np.diff(pos) > 0)  # ordenadas e sem repetição
    assert y[pos].sum() == 50  # 10% de positivos, como na população


def test_amostra_e_determinística_e_depende_da_semente():
    y = np.random.default_rng(0).integers(0, 2, 5000)
    a = shap_global.amostra_estratificada(y, 800, seed=5)
    b = shap_global.amostra_estratificada(y, 800, seed=5)
    c = shap_global.amostra_estratificada(y, 800, seed=6)
    assert np.array_equal(a, b)
    assert not np.array_equal(a, c)


def test_amostra_recusa_tamanho_fora_do_intervalo():
    with pytest.raises(ValueError):
        shap_global.amostra_estratificada(np.zeros(10), 11, seed=1)


# ---------- R1 ----------

def test_r1_recusa_ano_de_teste(tmp_path):
    df = frame()
    df.loc[0, "ANO"] = 2024
    modelo = xgb_ajustado(frame())
    with pytest.raises(RuntimeError, match="R1"):
        shap_global.calcular_shap_global(modelo, df, cfg_teste(tmp_path))


def test_modelo_que_nao_e_arvore_do_m1_e_recusado(tmp_path):
    df = frame()
    with pytest.raises(ValueError, match="XGBoostM1 ou CatBoostM1"):
        shap_global.calcular_shap_global(object(), df, cfg_teste(tmp_path))


# ---------- cálculo à mão num toco de árvore ----------

def test_toco_de_arvore_bate_com_o_calculo_a_mao():
    """Uma árvore com um corte (toco). Pelo TreeSHAP, a contribuição da feature do corte é
    v(x) − E, com E a média dos valores das folhas ponderada pela cobertura (nº de casos de
    treino em cada folha). Calculado aqui a partir do próprio dump da árvore, sem a função."""
    rng = np.random.default_rng(1)
    X = rng.normal(size=(300, 2))
    y = (X[:, 0] > 0.2).astype(int)
    clf = xgb.XGBClassifier(n_estimators=1, max_depth=1, learning_rate=1.0,
                            tree_method="hist", device="cpu", random_state=0).fit(X, y)
    booster = clf.get_booster()
    arvore = booster.trees_to_dataframe()
    raiz = arvore[arvore["Node"] == 0].iloc[0]
    feat = int(str(raiz["Feature"]).lstrip("f"))
    corte = float(raiz["Split"])
    folhas = arvore[arvore["Feature"] == "Leaf"].set_index("ID")
    v_sim, c_sim = float(folhas.loc[raiz["Yes"], "Gain"]), float(folhas.loc[raiz["Yes"], "Cover"])
    v_nao, c_nao = float(folhas.loc[raiz["No"], "Gain"]), float(folhas.loc[raiz["No"], "Cover"])
    esperado_E = (c_sim * v_sim + c_nao * v_nao) / (c_sim + c_nao)
    # "Yes" = x < corte, comparado em float32 como o XGBoost faz. Em float64, uma linha colada no
    # corte cai do outro lado e a média muda (foi o que aconteceu na primeira versão deste teste).
    v_x = np.where(X[:, feat].astype(np.float32) < np.float32(corte), v_sim, v_nao)
    # os valores das folhas do dump são os pesos; a margem é o peso mais um deslocamento que se
    # cancela no SHAP (conferido: contribuição = peso − E, com E = média ponderada pela cobertura)
    phi_feat = v_x - esperado_E

    agregado = shap_global.agregar(clf, 1, X)

    assert agregado["importancia_abs"][feat] == pytest.approx(np.abs(phi_feat).mean(), abs=1e-5)
    outra = 1 - feat
    assert agregado["importancia_abs"][outra] == pytest.approx(0.0, abs=1e-7)
    # toco: só efeito principal; a diagonal da feature é o efeito e não há interação
    assert agregado["interacoes_abs"][feat, feat] == pytest.approx(
        agregado["importancia_abs"][feat], abs=1e-5)
    assert agregado["interacoes_abs"][feat, outra] == pytest.approx(0.0, abs=1e-7)


# ---------- identidades: aditividade, coerência, simetria ----------

def test_identidades_xgboost_em_modelo_com_interacao():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(500, 4))
    y = ((X[:, 0] > 0) ^ (X[:, 1] > 0)).astype(int)  # interação de verdade
    clf = xgb.XGBClassifier(n_estimators=15, max_depth=3, tree_method="hist",
                            device="cpu", random_state=0).fit(X, y)
    ag = shap_global.agregar(clf, 15, X, lote=128)  # lotes pequenos: testa a soma em lotes
    assert ag["erro_aditividade"] < shap_global.TOLERANCIA_IDENTIDADE
    assert ag["erro_soma"] < shap_global.TOLERANCIA_IDENTIDADE
    assert ag["erro_simetria"] < shap_global.TOLERANCIA_IDENTIDADE
    assert np.allclose(ag["interacoes_abs"], ag["interacoes_abs"].T)
    # a interação de verdade aparece fora da diagonal
    assert ag["interacoes_abs"][0, 1] > ag["interacoes_abs"][0, 2]


def test_identidades_catboost_com_categoricas_e_truncagem():
    df = frame(n=400)
    df_cat = df[["sexo", "RENAL", "DIABETES", "idade_anos", "n_comorbidades"]].astype(
        {"sexo": str, "RENAL": str, "DIABETES": str})
    cat_idx = [0, 1, 2]
    modelo = CatBoostClassifier(iterations=30, depth=3, allow_writing_files=False,
                                verbose=False, random_seed=0)
    modelo.fit(df_cat, df["y"].to_numpy(), cat_features=cat_idx)
    ag = shap_global.agregar(modelo, 5, df_cat, cat_idx=cat_idx, lote=100)  # só 5 árvores
    assert ag["erro_aditividade"] < shap_global.TOLERANCIA_IDENTIDADE
    assert ag["erro_soma"] < shap_global.TOLERANCIA_IDENTIDADE
    assert ag["erro_simetria"] < shap_global.TOLERANCIA_IDENTIDADE
    assert np.allclose(ag["interacoes_abs"], ag["interacoes_abs"].T)


def test_catboost_usa_so_as_arvores_pedidas():
    """Com 5 árvores, a margem do modelo encurtado é a que a aditividade confere. Se o corte não
    valesse, a soma das contribuições não bateria com essa margem."""
    df = frame(n=400)
    df_cat = df[["sexo", "RENAL", "idade_anos"]].astype({"sexo": str, "RENAL": str})
    modelo = CatBoostClassifier(iterations=30, depth=3, allow_writing_files=False,
                                verbose=False, random_seed=0)
    modelo.fit(df_cat, df["y"].to_numpy(), cat_features=[0, 1])
    ag5 = shap_global.agregar(modelo, 5, df_cat, cat_idx=[0, 1])
    ag30 = shap_global.agregar(modelo, 30, df_cat, cat_idx=[0, 1])
    assert ag5["erro_aditividade"] < shap_global.TOLERANCIA_IDENTIDADE
    assert not np.allclose(ag5["importancia_abs"], ag30["importancia_abs"])


# ---------- ponta a ponta com os wrappers ----------

def test_ponta_a_ponta_xgboost_com_o_wrapper(tmp_path):
    df = frame(n=600)
    modelo = xgb_ajustado(df)
    cfg = cfg_teste(tmp_path, amostra=300)
    res = shap_global.calcular_shap_global(modelo, df, cfg)
    p = len(res.features)
    assert res.tipo == "xgboost"
    assert res.n_amostra == 300
    assert res.n_colunas_entrada == p == 26
    assert set(res.features) <= set(FEATURES_PERMITIDAS)  # R4
    assert res.importancia_abs.shape == (p,)
    assert res.interacoes_abs.shape == (p, p)
    assert res.erro_aditividade < shap_global.TOLERANCIA_IDENTIDADE
    assert res.erro_soma < shap_global.TOLERANCIA_IDENTIDADE
    assert res.erro_simetria < shap_global.TOLERANCIA_IDENTIDADE


def test_ponta_a_ponta_catboost_com_o_wrapper_e_nomes_originais(tmp_path):
    df = frame(n=600)
    modelo = cat_ajustado(df)
    res = shap_global.calcular_shap_global(modelo, df, cfg_teste(tmp_path, amostra=300))
    assert res.tipo == "catboost"
    assert res.features == res.colunas_modelo  # CatBoost: nomes já são os originais
    assert res.erro_aditividade < shap_global.TOLERANCIA_IDENTIDADE
    assert res.erro_soma < shap_global.TOLERANCIA_IDENTIDADE


def test_xgboost_nomes_do_modelo_trazem_o_transformador(tmp_path):
    df = frame(n=600)
    res = shap_global.calcular_shap_global(xgb_ajustado(df), df,
                                           cfg_teste(tmp_path, amostra=200))
    assert any(c.startswith("niveis__") for c in res.colunas_modelo)
    assert "HIPERTENSA" in res.features and "idade_anos" in res.features


def test_mesmo_modelo_e_mesma_amostra_dao_o_mesmo_resultado(tmp_path):
    df = frame(n=600)
    modelo = xgb_ajustado(df)
    cfg = cfg_teste(tmp_path, amostra=250)
    a = shap_global.calcular_shap_global(modelo, df, cfg)
    b = shap_global.calcular_shap_global(modelo, df, cfg)
    assert np.array_equal(a.importancia_abs, b.importancia_abs)
    assert np.array_equal(a.interacoes_abs, b.interacoes_abs)


# ---------- gravação: só agregados, nada por linha (R7) ----------

def test_gravacao_escreve_so_agregados_e_nada_por_linha(tmp_path):
    df = frame(n=600)
    cfg = cfg_teste(tmp_path, amostra=300)
    res = shap_global.calcular_shap_global(xgb_ajustado(df), df, cfg)
    out = tmp_path / "shap"
    manifesto = shap_global.gravar_shap_global(res, out, cfg)

    arquivos = sorted(p.name for p in out.iterdir())
    assert arquivos == sorted([shap_global.ARQ_IMPORTANCIA, shap_global.ARQ_INTERACOES,
                               shap_global.ARQ_MANIFESTO])
    p = manifesto["n_features"]
    for nome in shap_global.ARQUIVOS_DADOS:
        with open(out / nome, encoding="utf-8") as f:
            linhas = list(csv.reader(f))
        assert len(linhas) <= p + 1  # cabeçalho + uma linha por feature, nunca por caso
        assert all(len(linha) <= p + 1 for linha in linhas)
    # o manifesto não tem nenhuma lista com o tamanho da amostra
    dados = json.loads((out / shap_global.ARQ_MANIFESTO).read_text(encoding="utf-8"))

    def listas(obj):
        if isinstance(obj, list):
            yield obj
            for item in obj:
                yield from listas(item)
        elif isinstance(obj, dict):
            for v in obj.values():
                yield from listas(v)

    assert all(len(lista) <= p for lista in listas(dados))
    assert shap_global.arquivos_conferem(out, manifesto)


def test_sha_do_manifesto_bate_com_os_arquivos_e_detecta_alteracao(tmp_path):
    df = frame(n=600)
    cfg = cfg_teste(tmp_path, amostra=200)
    res = shap_global.calcular_shap_global(xgb_ajustado(df), df, cfg)
    out = tmp_path / "shap"
    manifesto = shap_global.gravar_shap_global(res, out, cfg)
    assert shap_global.arquivos_conferem(out, manifesto)
    with open(out / shap_global.ARQ_IMPORTANCIA, "a", encoding="utf-8") as f:
        f.write("x,y,0\n")
    assert not shap_global.arquivos_conferem(out, manifesto)


def test_importancia_csv_tem_nome_original_e_coluna_do_modelo(tmp_path):
    df = frame(n=600)
    cfg = cfg_teste(tmp_path, amostra=200)
    res = shap_global.calcular_shap_global(xgb_ajustado(df), df, cfg)
    out = tmp_path / "shap"
    shap_global.gravar_shap_global(res, out, cfg)
    with open(out / shap_global.ARQ_IMPORTANCIA, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    assert [linha["feature"] for linha in linhas] == list(res.features)
    assert [linha["coluna_modelo"] for linha in linhas] == list(res.colunas_modelo)
    assert all(float(linha["media_abs_shap"]) >= 0 for linha in linhas)


def test_pre_processador_da_familia_arvore_mapeia_uma_para_uma():
    pre = make_preprocessor("arvore")
    df = frame(n=50)
    pre.fit(df)
    colunas = [str(c) for c in pre.get_feature_names_out()]
    originais = [shap_global._nome_original(c) for c in colunas]
    assert len(set(originais)) == len(originais) == len(colunas) == 26


# ---------- R8: a semente vem do config, e muda a amostra ----------

def test_semente_vem_do_config_e_muda_a_amostra(tmp_path, monkeypatch):
    df = frame(n=600)
    modelo = xgb_ajustado(df)
    posicoes = []
    original = shap_global.amostra_estratificada

    def espiar(y, n, seed):
        pos = original(y, n, seed)
        posicoes.append(pos)
        return pos

    monkeypatch.setattr(shap_global, "amostra_estratificada", espiar)
    cfg_a = cfg_teste(tmp_path, amostra=200)
    cfg_b = dict(cfg_a, seed=8)
    res_a = shap_global.calcular_shap_global(modelo, df, cfg_a)
    res_b = shap_global.calcular_shap_global(modelo, df, cfg_b)
    assert res_a.seed == cfg_a["seed"] == 7
    assert res_b.seed == cfg_b["seed"] == 8
    assert not np.array_equal(posicoes[0], posicoes[1])


# ---------- matriz de interações: a parte fora da diagonal também é medida ----------

def test_interacao_real_aparece_fora_da_diagonal():
    rng = np.random.default_rng(2)
    X = rng.normal(size=(500, 3))
    y = ((X[:, 0] > 0) ^ (X[:, 1] > 0)).astype(int)  # só as features 0 e 1 interagem
    clf = xgb.XGBClassifier(n_estimators=15, max_depth=3, tree_method="hist",
                            device="cpu", random_state=0).fit(X, y)
    m = shap_global.agregar(clf, 15, X)["interacoes_abs"]
    assert m[0, 1] > 0
    assert m[1, 0] == pytest.approx(m[0, 1], abs=1e-9)
    assert m[0, 1] > m[0, 2]
