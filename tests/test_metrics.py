import numpy as np
import pytest

pytest.importorskip("sklearn")
pytest.importorskip("statsmodels")
from sklearn.metrics import average_precision_score, roc_auc_score  # noqa: E402

from dengue_sinan import metrics as M  # noqa: E402


@pytest.fixture
def dados():
    rng = np.random.default_rng(0)
    x = rng.normal(size=60_000)
    y = (rng.random(60_000) < 1 / (1 + np.exp(-(1.2 * x - 4.5)))).astype(int)
    return y, 1 / (1 + np.exp(-(x - 4.6)))


def test_celulas_reproduzem_sklearn(dados):
    y, p = dados
    tab = M.agregar(y, {"m": p})
    ordem, fins = M._ordem_e_fins(tab["s_m"].to_numpy())
    ap, auc = M._pr_roc_lote(
        tab["pos"].to_numpy()[None, :], tab["neg"].to_numpy()[None, :], ordem, fins
    )
    pq = M.quantizar(p)
    assert ap[0] == pytest.approx(average_precision_score(y, pq), abs=1e-9)
    assert auc[0] == pytest.approx(roc_auc_score(y, pq), abs=1e-9)


def test_bootstrap_cobre_estimativa_e_e_pareado(dados):
    y, p = dados
    tab = M.agregar(y, {"a": p, "b": p}, {"f": p > 0.01})
    bt = M.bootstrap_metricas(tab, B=80, seed=1)
    lo, hi = M.ic95(bt["pr_auc[a]"])
    assert lo < M.pr_auc(y, p) < hi
    assert np.allclose(
        bt["pr_auc[a]"], bt["pr_auc[b]"]
    )  # mesmas reamostras → diferença exatamente 0
    assert not np.isnan(bt["pr_auc[a]"]).any()


def test_limiar_e_matriz():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 1])
    p = np.array([0.9, 0.8, 0.7, 0.2, 0.1, 0.1, 0.05, 0.3])
    m = M.metricas_limiar(y, p >= 0.3)
    assert (m["TP"], m["FP"], m["FN"], m["TN"]) == (3, 1, 0, 4)
    assert m["sensibilidade"] == 1.0 and m["VPP"] == pytest.approx(0.75)
    lim, met = M.melhor_limiar_f2(y, p)
    assert lim == pytest.approx(0.3) and met["F2"] == pytest.approx(5 * 0.75 / (4 * 0.75 + 1))


def test_limiares_pareados_com_regra():
    y = np.array([1, 1, 0, 0, 0, 0, 0, 1])
    p = np.array([0.9, 0.8, 0.7, 0.2, 0.1, 0.1, 0.05, 0.3])
    assert M.limiar_para_sensibilidade(y, p, 1.0) == pytest.approx(0.3)
    assert M.limiar_para_fracao(y, p, 0.5) == pytest.approx(0.3)


def test_calibracao_perfeita(dados):
    y, p = dados
    r = M.calibracao_resumo(y, p)
    assert 0.8 < r["slope"] < 1.3 and abs(r["intercepto_citl"]) < 0.4


def test_decisao_todos_e_nenhum():
    y = np.array([1, 0, 0, 0])
    d = M.curva_decisao(y, flag=np.ones(4, bool), limiares=[0.1, 0.5])
    assert np.allclose(d["net_benefit"], M.net_benefit_todos(0.25, np.array([0.1, 0.5])))


def test_nri_zero_quando_iguais(dados):
    y, p = dados
    tab = M.agregar(y, {"m": p}, {"a": p > 0.01, "b": p > 0.01})
    pont, amostras = M.nri_bootstrap(tab, "f_a", "f_b", B=20, seed=0)
    assert pont == 0 and np.allclose(amostras, 0)
