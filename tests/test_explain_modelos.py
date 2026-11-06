import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")
pytest.importorskip("statsmodels")
from conftest_sint import bruto_sintetico  # noqa: E402

from dengue_sinan import explain as E  # noqa: E402
from dengue_sinan import modelos as MD  # noqa: E402
from dengue_sinan.dataset import montar_features, montar_populacao  # noqa: E402


@pytest.fixture(scope="module")
def base():
    pop = montar_populacao(bruto_sintetico(n=80_000, seed=5), 2022)
    return pop, montar_features(pop)


def test_e1_recupera_efeito_conhecido(base):
    pop, x = base
    agg, exc = E.agregar_e1(pop, x)
    assert exc["linhas_analisadas"] + exc["linhas_excluidas"] == len(pop)
    nos = E.nos_da_idade(x["idade_anos"])
    pares = [(r.A, r.B) for r in E.pares_com_eventos(agg).itertuples() if r.entra_no_E1]
    m = E.ajustar_e1(agg, nos, pares)
    r = E.or_com_ic(m, {"RENAL"}, 50)
    assert r["ic95_inf"] < np.exp(1.2) < r["ic95_sup"] * 1.25  # efeito verdadeiro da simulação: 1,2
    rk = E.ranking_comorbidades(m, 50)
    assert rk.loc[0, "comorbidade"] == "RENAL" and len(rk) == 7


def test_binomial_agrupado_equivale_a_linha_a_linha(base):
    import patsy
    import statsmodels.api as sm

    pop, x = base
    agg, _ = E.agregar_e1(pop, x)
    nos = E.nos_da_idade(x["idade_anos"])
    m = E.ajustar_e1(agg, nos, [], interacao_idade=(), comorbidades=["RENAL", "DIABETES"])
    rows = agg.loc[agg.index.repeat(agg["n"])].reset_index(drop=True)
    rows["y"] = 0
    # eventos: distribuir k por padrão (o ajuste só depende das somas)
    desfecho = np.column_stack([agg["k"], agg["n"] - agg["k"]])
    X = patsy.dmatrix(m.rhs, agg, return_type="dataframe")
    ref = sm.GLM(desfecho, X, family=sm.families.Binomial()).fit()
    assert np.allclose(ref.params, m.beta)


def test_reri_bate_com_a_formula_nos_or_do_modelo(base):
    pop, x = base
    agg, _ = E.agregar_e1(pop, x)
    nos = E.nos_da_idade(x["idade_anos"])
    m = E.ajustar_e1(agg, nos, [("DIABETES", "RENAL")])
    a = E.or_com_ic(m, {"DIABETES"}, 50)["OR"]
    b = E.or_com_ic(m, {"RENAL"}, 50)["OR"]
    ab = E.or_com_ic(m, {"DIABETES", "RENAL"}, 50)["OR"]
    r = E.reri_ap(m, "DIABETES", "RENAL", 50)
    assert r["RERI"] == pytest.approx(ab - a - b + 1)
    assert r["AP"] == pytest.approx((ab - a - b + 1) / ab)
    assert r["RERI_ic95_inf"] < r["RERI"] < r["RERI_ic95_sup"]


def test_b2_flag_regras(base):
    _, x = base
    x = x.copy()
    x[:] = x.iloc[0]
    x = pd.concat([x.iloc[[0]]] * 6, ignore_index=True)
    for c in [
        "DIABETES",
        "HEMATOLOG",
        "HEPATOPAT",
        "RENAL",
        "HIPERTENSA",
        "ACIDO_PEPT",
        "AUTO_IMUNE",
        "LACO",
        "PETEQUIA_N",
    ]:
        x[c] = pd.Categorical(["Não"] * 6, categories=["Não", "Sim", "Ausente"])
    x["idade_anos"] = [30.0, 1.5, 70.0, 30.0, 30.0, 30.0]
    x["gestante"] = [0, 0, 0, 1, 0, 0]
    x["n_comorbidades"] = 0
    x.loc[4, "n_comorbidades"] = 1
    x["LACO"] = pd.Categorical(["Não"] * 5 + ["Sim"], categories=["Não", "Sim", "Ausente"])
    assert MD.b2_flag(x).tolist() == [False, True, True, True, True, True]


def test_selecao_regra_do_spec():
    r = pd.DataFrame(
        {
            "modelo": ["elastic_net", "xgboost"],
            "pr_auc_media": [0.040, 0.044],
            "brier": [0.01, 0.02],
        }
    )
    assert MD.selecionar_modelo(r)[0] == "elastic_net"  # empate (< 0,005): menor Brier
    r["pr_auc_media"] = [0.040, 0.060]
    assert MD.selecionar_modelo(r)[0] == "xgboost"  # diferença > 0,005
    r.loc[:, "brier"] = 0.01
    r["pr_auc_media"] = [0.040, 0.042]
    assert MD.selecionar_modelo(r)[0] == "elastic_net"  # empate total: o mais simples


def test_calibrador_monotono_e_cruzado():
    rng = np.random.default_rng(0)
    p = rng.random(5000) * 0.05
    y = (rng.random(5000) < p * 1.5).astype(int)
    c = MD.Calibrador("isotonica").ajustar(p, y)
    g = np.linspace(0, 0.05, 50)
    assert (np.diff(c.prever(g)) >= -1e-12).all()
    reg = pd.Series(rng.choice(["Norte", "Sul", "Sudeste"], 5000))
    out = MD.calibrar_cruzado(p, y, reg, "platt")
    assert not np.isnan(out).any()


def test_candidato_de_boosting_com_early_stopping_na_validacao_interna(base):
    pop, x = base
    y = pop["y"].to_numpy()
    params = {
        "max_depth": 3,
        "learning_rate": 0.1,
        "min_child_weight": 5,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_lambda": 1.0,
    }
    r = MD.cv_oof(
        "xgboost", params, x, y, pop["regiao"], seed=1, max_iter=60, paciencia=10, n_jobs=1
    )
    assert not np.isnan(r["oof"][pop["regiao"].notna().to_numpy()]).any()
    assert r["pr_auc_media"] > y.mean()  # melhor que o piso (B0)
    assert len(r["melhor_iter"]) == pop["regiao"].nunique()
