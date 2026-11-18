"""Etapa 1B — testes das análises exploratórias J2–J6 com dados SINTÉTICOS (nunca do SINAN)."""

import json

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")
pytest.importorskip("statsmodels")
pytest.importorskip("pyarrow")
from conftest_sint import bruto_sintetico  # noqa: E402

from dengue_sinan import etapa1 as ET  # noqa: E402
from dengue_sinan import explain as E  # noqa: E402
from dengue_sinan.guard import anos_marcados  # noqa: E402

CONFIG = {
    "SEED": 3, "MAX_ITER_BOOSTING": 40, "PACIENCIA_BOOSTING": 8, "VALIDACAO_INTERNA_FRAC": 0.1,
    "N_JOBS": 1, "DEVICE": "cpu",
}  # fmt: skip
PARAMS = {"max_depth": 3, "learning_rate": 0.1, "min_child_weight": 5, "subsample": 0.8,
          "colsample_bytree": 0.8, "reg_lambda": 1.0}  # fmt: skip


def com_campos_extras(df: pd.DataFrame, seed: int, petequias_igual=True) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    d = df.copy()
    notif = pd.to_datetime(d["DT_NOTIFIC"], format="%Y%m%d")
    inv = rng.integers(0, 11, len(d))
    d["DT_INVEST"] = (notif + pd.to_timedelta(inv, unit="D")).dt.strftime("%Y%m%d")
    d["DT_ENCERRA"] = (
        notif + pd.to_timedelta(inv + rng.integers(5, 40, len(d)), unit="D")
    ).dt.strftime("%Y%m%d")
    d["PETEQUIAS"] = d["PETEQUIA_N"] if petequias_igual else rng.choice(["1", "2"], len(d))
    return d


@pytest.fixture(scope="module")
def brutos():
    return {
        2022: com_campos_extras(bruto_sintetico(n=40_000, ano=2022, seed=21), 1),
        2023: com_campos_extras(bruto_sintetico(n=40_000, ano=2023, seed=22), 2),
    }


@pytest.fixture(scope="module")
def dev(brutos):
    pop, x = ET.montar_dev(brutos)
    return pop, x


# ------------------------------------------------------------------ carregador e R1
def test_carregador_recusa_2024_e_exige_arquivo(tmp_path):
    with pytest.raises(PermissionError, match="2024"):
        ET.carregar_bruto_dev(tmp_path, anos=(2023, 2024))
    with pytest.raises(FileNotFoundError):
        ET.carregar_bruto_dev(tmp_path, anos=(2022,))


def test_carregador_registra_hash_real_e_colunas_ausentes(tmp_path, brutos):
    for ano, df in brutos.items():
        df.to_parquet(tmp_path / f"dengue_{ano}.parquet")
    lidos, reg = ET.carregar_bruto_dev(tmp_path, colunas=["CLASSI_FIN", "EVOLUCAO", "NAO_EXISTE"])
    assert set(lidos) == {2022, 2023}
    for ano in ("2022", "2023"):
        sha = reg["arquivos"][ano]["sha256"]
        assert isinstance(sha, str) and len(sha) == 64  # nunca nulo
        assert reg["colunas_ausentes"][ano] == ["NAO_EXISTE"]
    assert set(lidos[2022].columns) == {"CLASSI_FIN", "EVOLUCAO"}


def test_montar_dev_marca_origem(dev):
    pop, x = dev
    assert anos_marcados(pop) == {2022, 2023} and anos_marcados(x) == {2022, 2023}


def test_suprimir_pequenas_aplica_r7():
    t = pd.DataFrame({"a": [0, 3, 9, 10, 500]})
    s = ET.suprimir_pequenas(t, ["a"])
    assert s["a"].isna().tolist() == [False, True, True, False, False]
    assert s["suprimido"].tolist() == [False, True, True, False, False]


# ------------------------------------------------------------------ J2
def test_reproduzir_populacao_reproduz_e_acusa_divergencia(dev):
    pop, _ = dev
    hist = {
        "populacao_dev": {
            "casos": len(pop),
            "eventos": int(pop["y"].sum()),
            "prevalencia": float(pop["y"].mean()),
        }
    }
    prev = (pop.groupby("ANO")["y"].agg(["size", "sum"]).reset_index()
            .rename(columns={"size": "casos", "sum": "eventos (y=1)"}))  # fmt: skip
    ok = ET.reproduzir_populacao(pop, hist, prev)
    assert (ok["conclusao"] == "reproduzido").all()
    hist["populacao_dev"]["eventos"] += 5
    ruim = ET.reproduzir_populacao(pop, hist, prev)
    assert ruim.loc[ruim["item"] == "eventos (dev)", "conclusao"].iloc[0].startswith("DIVERGE")


def test_reproduzir_metricas_oof_tem_estrutura_e_nao_forca(dev):
    pop, x = dev
    y = pop["y"].to_numpy()
    hist = {
        "selecao_m1": {"params": PARAMS, "calibrador": "isotonica"},
        "dev": {"metricas_oof": [
            {"modelo": "B0 (prevalência)", "PR-AUC (pooled)": 0.5, "Brier": 0.5},
            {"modelo": "B1 (logística simples)", "PR-AUC (pooled)": 0.5, "Brier": 0.5},
            {"modelo": "xgboost (calibrado)", "PR-AUC (pooled)": 0.5, "ROC-AUC": 0.5, "Brier": 0.5},
        ]},
    }  # fmt: skip
    t = ET.reproduzir_metricas_oof(x, y, pop["regiao"], hist, CONFIG)
    assert {"historico", "reproduzido", "diferenca", "conclusao"} <= set(t.columns)
    assert t["conclusao"].str.startswith("DIVERGE").any()  # valores fictícios não são forçados
    assert t["reproduzido"].notna().all()


def test_comparar_configuracao():
    t = ET.comparar_configuracao({"config": {"SEED": 1, "X": 2}, "ambiente": {"numpy": "1"}},
                                 {"SEED": 1, "X": 3}, {"numpy": "2"})  # fmt: skip
    assert t.set_index("campo")["igual"].to_dict() == {
        "config.SEED": True,
        "config.X": False,
        "ambiente.numpy": False,
    }


# ------------------------------------------------------------------ J3
@pytest.fixture(scope="module")
def e1(dev):
    pop, x = dev
    agg, _ = E.agregar_e1(pop, x)
    nos = E.nos_da_idade(x["idade_anos"])
    return pop, x, agg, nos


def test_j3_construcao_cruzada_perfil_e_colinearidade(brutos, e1):
    pop, x, agg, nos = e1
    cod = ET.codificacao_original(brutos)
    assert {"ANO", "valor", "casos_y0", "casos_y1"} <= set(cod.columns)
    c = ET.conferir_construcao(pop, x, agg, "ACIDO_PEPT")
    assert c.loc[0, "diferenca_casos_completos"] >= 0  # casos completos só podem tirar linhas
    cz = ET.tabela_cruzada(agg)
    assert len(cz) == 6 and (cz["casos_ambos"] >= cz["eventos_ambos"]).all()
    # soma das quatro células = total de casos do agregado
    assert (
        cz[["casos_ambos", "casos_so_campo", "casos_so_outra", "casos_nenhum"]].sum(axis=1)
        == agg["n"].sum()
    ).all()
    pe = ET.perfil_expostos(agg)
    assert pe["casos"].iloc[0] > 0
    corr, vif = ET.colinearidade(agg)
    assert corr.shape == (9, 9) and np.allclose(np.diag(corr), 1.0)
    assert (vif["VIF"] >= 1 - 1e-9).all()


def test_j3_especificacoes_estabilidade_e_implementacao(e1):
    pop, x, agg, nos = e1
    tab, modelos = ET.comparar_especificacoes(agg, nos, idade_ref=float(x["idade_anos"].median()))
    assert {
        "bruto",
        "A idade+sexo (só o campo)",
        "B mútuo aditivo (7)",
        "C mútuo + pares elegíveis",
    } <= set(tab["modelo"])
    assert tab["OR"].notna().all() and (tab["ic95_inf"] <= tab["OR"]).all()
    assert any(tab["contraste"].str.contains("dado "))
    cel, aj = ET.diagnostico_separacao(agg, modelos, "ACIDO_PEPT")
    assert len(cel) == 6 and aj["convergiu"].all()
    est = ET.estabilidade(pop, x, agg, nos)
    assert {"mútuo aditivo (todos os anos)"} <= set(est["analise"])
    assert (est["analise"] == "mútuo sem DIABETES").any() and est["estrato"].str.contains(
        "ANO="
    ).any()
    impl = ET.conferir_implementacao(agg, nos)
    assert (
        len(impl) == 3 and impl["diferenca_beta_vs_a"].abs().max() < 1e-3
    )  # as três vias coincidem


# ------------------------------------------------------------------ J4
def test_j4_deltas_distribuicao_e_inconsistencias(brutos):
    d = ET.preparar_momento(brutos)
    assert anos_marcados(d) == {2022, 2023}
    assert d["d_inv"].between(0, 10).all()  # construído assim no sintético
    dist = ET.distribuicao_deltas(d)
    assert {"total", "y", "gravidade", "óbito", "ano"} <= set(dist["agrupamento"])
    tot = dist[(dist["agrupamento"] == "total") & (dist["delta"] == "d_inv")].iloc[0]
    assert tot["n"] == len(d) and 0 <= tot["mediana"] <= 10 and tot["% negativo"] == 0
    inc = ET.datas_inconsistentes(d)
    assert inc.loc[inc["regra"].str.startswith("DT_INVEST anterior"), "registros"].iloc[0] == 0
    # injeta inconsistências conhecidas e confere a contagem
    d2 = d.copy()
    d2.loc[d2.index[:7], "d_inv"] = -3
    assert ET.datas_inconsistentes(d2).loc[2, "registros"] == 7
    camp = ET.campos_por_atraso_investigacao(d)
    assert {"campo", "faixa_invest_menos_notific_dias", "y", "%_sim"} <= set(camp.columns)
    assert ET.nota_inconclusiva()["classificacao_padrao"] == "inconclusivo"


def test_j4_sem_colunas_de_data_nao_quebra(brutos):
    sem = {a: df.drop(columns=["DT_INVEST", "DT_ENCERRA"]) for a, df in brutos.items()}
    d = ET.preparar_momento(sem)
    assert d["d_inv"].isna().all()
    assert (ET.datas_inconsistentes(d).iloc[0]["% da população"]) == 100.0


# ------------------------------------------------------------------ J6
def test_j6_redundancia_e_independencia(brutos):
    r = ET.petequias(brutos)["redundancia"].iloc[0]
    assert r["kappa"] == pytest.approx(1.0) and "REDUNDÂNCIA" in r["indicio_automatico"]
    base = {
        a: df.drop(columns=["PETEQUIAS", "DT_INVEST", "DT_ENCERRA"]) for a, df in brutos.items()
    }
    indep = {a: com_campos_extras(df, 9 + a, petequias_igual=False) for a, df in base.items()}
    r2 = ET.petequias(indep)["redundancia"].iloc[0]
    assert abs(r2["kappa"]) < 0.1 and "COMPLEMENTARIDADE" in r2["indicio_automatico"]
    saida = ET.petequias({a: df.drop(columns="PETEQUIAS") for a, df in brutos.items()})
    assert "aviso" in saida


# ------------------------------------------------------------------ J5
def test_j5_variantes_nao_removem_definitivamente(dev):
    pop, x = dev
    v = ET.variantes_ablacao()
    assert len(v) >= 6 and v["1 M1 completo"] == []
    assert set(v["6 sem as 4 suspeitas"]) == set(ET.SUSPEITAS)
    for cols in v.values():
        assert set(cols) <= set(x.columns)
    assert anos_marcados(x.drop(columns=["VOMITO"])) == {2022, 2023}  # a marca de R1 sobrevive


def test_j5_ablacao_loro_e_temporal(dev):
    pop, x = dev
    y = pop["y"].to_numpy()
    var = {k: v for k, v in ET.variantes_ablacao().items() if k.split()[0] in {"1", "2", "6", "G2"}}
    r = ET.executar_ablacao(x, y, pop["regiao"], PARAMS, 3, CONFIG, variantes=var, B=40)
    m = r["metricas"]
    assert list(m["variante"]) == list(var) and m["PR-AUC"].between(0, 1).all()
    assert {
        "slope",
        "intercepto",
        "sensibilidade",
        "precisao_VPP",
        "especificidade",
        "pct_sinalizados",
    } <= set(m.columns)
    d = r["diferencas_pareadas"]
    assert "1 M1 completo" not in set(d["variante"]) and len(d) == 3 * (len(var) - 1)
    assert (d["ic95_inf"] <= d["ic95_sup"]).all()
    t = ET.ablacao_temporal(x, y, pop["ANO"], PARAMS, 3, CONFIG, variantes=var)
    assert len(t) == len(var) and (t["n_teste"] == int((pop["ANO"] == 2023).sum())).all()


def test_j5_recusa_dados_de_2024(brutos):
    from dengue_sinan.dataset import montar_features, montar_populacao

    pop24 = montar_populacao(bruto_sintetico(n=6_000, ano=2024, seed=31), 2024)
    x24 = montar_features(pop24)
    with pytest.raises(PermissionError, match="R1"):
        ET.executar_ablacao(x24, pop24["y"].to_numpy(), pop24["regiao"], PARAMS, 1, CONFIG, B=10)


def test_salvar_tabela_e_json(tmp_path):
    ET.salvar_tabela(pd.DataFrame({"casos": [3, 50]}), tmp_path, "t", contagens=["casos"])
    assert pd.read_csv(tmp_path / "t.csv")["casos"].isna().tolist() == [True, False]
    ET.salvar_json({"a": np.float64(1.5)}, tmp_path, "j")
    assert json.loads((tmp_path / "j.json").read_text("utf-8")) == {"a": 1.5}
