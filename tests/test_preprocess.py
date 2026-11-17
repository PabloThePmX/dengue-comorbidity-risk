"""Testes do pré-processamento por família (T-4.1). Dados sintéticos; nenhum microdado real."""

import random

import numpy as np
import pandas as pd
import pytest
import scipy.sparse as sp
from populacao_sintetica import linha

from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.preprocess import (
    CATEGORICAS_CATBOOST,
    FEATURES_PERMITIDAS,
    NUMERICAS_CATBOOST,
    PROIBIDAS_EXATAS,
    PROIBIDAS_PREFIXOS,
    colunas_do_preprocessor,
    indices_cat_features_catboost,
    make_preprocessor,
    validar_colunas,
    validar_preprocessor,
)
from dengue_sinan.profiling import COMORBIDADES, SINAIS, add_derived

# Cópia literal do "Dicionário de features" de specs/data-model.md. Se o dicionário mudar, este
# teste deve mudar junto (e a decisão passa pelo Programador).
DICIONARIO = {
    "idade_anos", "sexo", "gestante", "n_comorbidades", "dias_ate_notificacao",
    "DIABETES", "HEMATOLOG", "HEPATOPAT", "RENAL", "HIPERTENSA", "ACIDO_PEPT", "AUTO_IMUNE",
    "FEBRE", "MIALGIA", "CEFALEIA", "EXANTEMA", "VOMITO", "NAUSEA", "DOR_COSTAS", "CONJUNTVIT",
    "ARTRITE", "ARTRALGIA", "DOR_RETRO", "PETEQUIA_N", "LEUCOPENIA", "LACO",
}

DATAS_NOTIFIC = ["20220110", "20220120", "20220301", "20221201"]  # atraso 0, 10, 50 e 325 dias
MUNICIPIOS = ["310620", "330455", "150010", "431490", "510100"]  # SE, SP, PA, RS, MT
COLUNAS_PROIBIDAS_NO_FRAME = ["SG_UF", "ID_MN_RESI", "CS_RACA", "ANO", "regiao", "CLASSI_FIN",
                              "EVOLUCAO", "y", "faixa_etaria", "NU_IDADE_N", "ANO_NASC"]
FAMILIAS = [
    ("linear", {}, 75),
    ("linear", {"interacoes_comorbidade": True}, 96),
    ("arvore", {}, 26),
    ("catboost", {}, 26),
]


def _registros(n: int, seed: int) -> list[dict]:
    """Notificações sintéticas com os campos do dicionário; códigos "9" viram Ausente."""
    rnd = random.Random(seed)
    registros = []
    for _ in range(n):
        codigos = {c: rnd.choice(["1", "2", "9", None]) for c in [*COMORBIDADES, *SINAIS]}
        registros.append(linha(
            NU_IDADE_N=f"4{rnd.randrange(100):03d}",
            CS_SEXO=rnd.choice(["M", "F", "I", None]),
            CS_GESTANT=rnd.choice(["1", "2", "3", "4", "5", "9"]),
            DT_NOTIFIC=rnd.choice(DATAS_NOTIFIC),
            ID_MN_RESI=rnd.choice(MUNICIPIOS),
            CLASSI_FIN=rnd.choice(["10", "11", "12"]),
            EVOLUCAO=rnd.choice(["1", "2"]),
            **codigos,
        ))
    return registros


def _features(n: int, seed: int) -> pd.DataFrame:
    """Frame de features pelo caminho real (add_derived + build_feature_frame), com colunas de
    fora do dicionário (UF, região, ano...) presentes, como no dataset de verdade."""
    bruto = pd.DataFrame(_registros(n, seed))
    bruto["ANO"] = 2022
    return build_feature_frame(add_derived(bruto))


def _validacao_extrema(valid: pd.DataFrame) -> pd.DataFrame:
    """Validação com idade fora da faixa do treino, dias no limite, sexo e níveis desconhecidos."""
    v = valid.copy()
    v["idade_anos"] = 99.0
    v["dias_ate_notificacao"] = 60
    v["sexo"] = "X"
    for c in [*COMORBIDADES, *SINAIS]:
        v[c] = pd.Series(["Talvez"] * len(v), index=v.index, dtype=object)
    return v


def _ajuste(pre) -> dict:
    """Parâmetros que dependem do ajuste: nós da spline e médias/escalas do treino (R5)."""
    idade = pre.named_transformers_["idade"].named_steps
    dias = pre.named_transformers_["dias"].named_steps
    return {
        "nos_spline": [b.t.copy() for b in idade["spline"].bsplines_],
        "media_idade": idade["escala"].mean_.copy(),
        "media_dias": dias["escala"].mean_.copy(),
        "escala_dias": dias["escala"].scale_.copy(),
    }


def _iguais(a: dict, b: dict) -> bool:
    for chave in a:
        x, y = a[chave], b[chave]
        if isinstance(x, list):  # nós da spline: uma lista de arrays
            if len(x) != len(y) or not all(
                np.array_equal(p, q) for p, q in zip(x, y, strict=True)
            ):
                return False
        elif not np.array_equal(x, y):
            return False
    return True


@pytest.fixture(scope="module")
def treino() -> pd.DataFrame:
    return _features(400, seed=1)


@pytest.fixture(scope="module")
def valid() -> pd.DataFrame:
    return _features(150, seed=2)


def test_lista_permitida_bate_com_o_dicionario_de_features():
    assert set(FEATURES_PERMITIDAS) == DICIONARIO
    assert len(FEATURES_PERMITIDAS) == 26


def test_validar_colunas_recusa_coluna_proibida_e_aceita_as_permitidas():
    validar_colunas(FEATURES_PERMITIDAS)
    for proibida in ["UF", "SG_UF", "regiao", "ANO", "CRITERIO", "ALRM_1", "GRAV_X",
                     "RESUL_SORO", "DT_NOTIFIC", "HOSPITALIZ", "LACO_N", "PETEQUIAS"]:
        with pytest.raises(ValueError, match="proibidas|fora do dicionário"):
            validar_colunas([proibida])
    with pytest.raises(ValueError, match="fora do dicionário"):
        validar_colunas(["coluna_inventada"])


def test_proibidas_do_r4_estao_fora_da_lista_permitida():
    assert not (PROIBIDAS_EXATAS & set(FEATURES_PERMITIDAS))
    assert not any(f.startswith(PROIBIDAS_PREFIXOS) for f in FEATURES_PERMITIDAS)


@pytest.mark.parametrize("familia, kwargs, largura", FAMILIAS)
def test_colunas_lidas_saem_da_lista_permitida_e_nenhuma_proibida_entra(
        treino, familia, kwargs, largura):
    pre = make_preprocessor(familia, **kwargs).fit(treino)
    lidas = colunas_do_preprocessor(pre)
    validar_preprocessor(pre)
    assert set(lidas) == set(FEATURES_PERMITIDAS)
    assert not set(lidas) & PROIBIDAS_EXATAS
    # As colunas proibidas estão no frame, mas não são lidas (remainder="drop").
    assert set(COLUNAS_PROIBIDAS_NO_FRAME) <= set(treino.columns)
    nomes = [n.split("__", 1)[-1] for n in pre.get_feature_names_out()]
    assert not [n for n in nomes if n.startswith(PROIBIDAS_PREFIXOS) or n in PROIBIDAS_EXATAS]


@pytest.mark.parametrize("familia, kwargs, largura", FAMILIAS)
def test_ajustado_so_no_treino_transforma_validacao_com_mesmo_numero_de_colunas(
        treino, valid, familia, kwargs, largura):
    pre = make_preprocessor(familia, **kwargs).fit(treino)
    saida_treino = pre.transform(treino)
    saida_valid = pre.transform(valid)
    assert saida_treino.shape == (len(treino), largura)
    assert saida_valid.shape == (len(valid), largura)
    if sp.issparse(saida_valid):
        assert np.isfinite(saida_valid.data).all()
    elif familia != "catboost":  # o CatBoost devolve texto nas categóricas
        assert not np.isnan(saida_valid).any()


def test_r5_validacao_nao_altera_os_parametros_ajustados(treino, valid):
    pre = make_preprocessor("linear", interacoes_comorbidade=True).fit(treino)
    antes = _ajuste(pre)
    pre.transform(_validacao_extrema(valid))
    assert _iguais(antes, _ajuste(pre))


def test_r5_contraste_ajustar_com_validacao_muda_os_parametros(treino, valid):
    """Prova de que o teste acima pega vazamento: se a validação entrasse no ajuste, os nós
    e as médias mudariam."""
    so_treino = _ajuste(make_preprocessor("linear").fit(treino))
    com_validacao = _ajuste(make_preprocessor("linear").fit(
        pd.concat([treino, _validacao_extrema(valid)], ignore_index=True)))
    assert not _iguais(so_treino, com_validacao)


@pytest.mark.parametrize("familia, kwargs", [("linear", {}), ("arvore", {})])
def test_categoria_desconhecida_na_validacao_nao_quebra(treino, valid, familia, kwargs):
    pre = make_preprocessor(familia, **kwargs).fit(treino)
    extrema = _validacao_extrema(valid)
    saida = pre.transform(extrema)
    assert saida.shape[0] == len(extrema)
    if familia == "linear":
        bloco_sexo = pre.named_transformers_["sexo"].transform(extrema[["sexo"]])
        # Todas as linhas têm sexo "X", que não está nas categorias: one-hot vira zeros.
        assert (np.asarray(bloco_sexo.sum(axis=1)).ravel() == 0).all()
    else:
        col_sexo = pre.named_transformers_["sexo"].transform(extrema[["sexo"]])[:, 0]
        assert np.isnan(col_sexo).all()  # ordinal desconhecido vira NaN


def test_niveis_ausente_sao_tratados_nas_tres_familias(treino):
    df = treino.head(2).copy()
    for c in [*COMORBIDADES, *SINAIS]:
        df[c] = pd.Series(["Sim", "Ausente"], index=df.index, dtype=object)
    df["sexo"] = "F"
    niveis_cols = [*COMORBIDADES, *SINAIS]
    lin = make_preprocessor("linear").fit(treino)
    bloco = pd.DataFrame(lin.named_transformers_["niveis"].transform(df[niveis_cols]).toarray(),
                         columns=lin.named_transformers_["niveis"].get_feature_names_out())
    assert bloco.loc[0, "DIABETES_Sim"] == 1 and bloco.loc[0, "DIABETES_Ausente"] == 0
    assert bloco.loc[1, "DIABETES_Ausente"] == 1 and bloco.loc[1, "DIABETES_Sim"] == 0

    arv = make_preprocessor("arvore").fit(treino)
    ordinal = arv.named_transformers_["niveis"].transform(df[niveis_cols])
    assert ordinal[0, 0] == 1 and ordinal[1, 0] == 2  # Sim = 1, Ausente = 2 (1ª coluna = DIABETES)

    cat = make_preprocessor("catboost").fit(treino)
    assert cat.transform(df)["DIABETES"].tolist() == ["Sim", "Ausente"]


def test_interacoes_so_entre_comorbidades_sim(treino):
    pre = make_preprocessor("linear", interacoes_comorbidade=True).fit(treino)
    nomes = [n.split("__", 1)[1] for n in pre.get_feature_names_out() if n.startswith("pares__")]
    assert len(nomes) == 21  # 7 comorbidades: C(7, 2) pares
    assert all("Ausente" not in n and "Não" not in n for n in nomes)
    assert all(n.count("=Sim") == 2 for n in nomes)

    # Só DIABETES e HEMATOLOG em Sim: exatamente o par deles vale 1.
    df = treino.head(1).copy()
    for c in COMORBIDADES:
        df[c] = pd.Series(["Ausente"], index=df.index, dtype=object)
    df["DIABETES"] = "Sim"
    df["HEMATOLOG"] = "Sim"
    pares = pre.named_transformers_["pares"].transform(df[list(COMORBIDADES)])[0]
    ativos = [nomes[i] for i in np.flatnonzero(pares)]
    assert ativos == ["DIABETES=Sim x HEMATOLOG=Sim"]


def test_interacoes_ficam_so_na_linear_com_o_parametro():
    assert "pares" not in [t[0] for t in make_preprocessor("linear").transformers]
    assert "pares" in [t[0] for t in make_preprocessor(
        "linear", interacoes_comorbidade=True).transformers]
    with pytest.raises(ValueError, match="só existe na família 'linear'"):
        make_preprocessor("arvore", interacoes_comorbidade=True)
    with pytest.raises(ValueError, match="desconhecida"):
        make_preprocessor("xgboost")


def test_catboost_entrega_dataframe_na_ordem_e_indices_de_cat_features(treino, valid):
    pre = make_preprocessor("catboost").fit(treino)
    saida = pre.transform(valid)
    assert isinstance(saida, pd.DataFrame)
    assert list(saida.columns) == [*CATEGORICAS_CATBOOST, *NUMERICAS_CATBOOST]
    assert indices_cat_features_catboost(pre) == list(range(len(CATEGORICAS_CATBOOST)))
    assert all(isinstance(v, str) for v in saida[CATEGORICAS_CATBOOST].to_numpy().ravel())
    assert all(saida[c].dtype == np.float64 for c in NUMERICAS_CATBOOST)


def test_saida_em_float32_e_esparsa_na_linear(treino):
    lin = make_preprocessor("linear", interacoes_comorbidade=True).fit(treino)
    saida = lin.transform(treino)
    assert sp.issparse(saida) and saida.dtype == np.float32
    arv = make_preprocessor("arvore").fit(treino).transform(treino)
    assert isinstance(arv, np.ndarray) and arv.dtype == np.float32


def test_validar_preprocessor_pega_coluna_proibida_injetada():
    pre = make_preprocessor("arvore")
    pre.transformers[2] = (pre.transformers[2][0], pre.transformers[2][1],
                           [*pre.transformers[2][2], "SG_UF"])
    with pytest.raises(ValueError, match="proibidas"):
        validar_preprocessor(pre)
