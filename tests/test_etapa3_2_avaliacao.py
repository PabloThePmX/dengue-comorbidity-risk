"""Etapa 3.2 — infraestrutura de avaliação do M1 (OOF, baselines, métricas, bootstrap, exportação).

Dados SINTÉTICOS. Nenhum teste lê dados reais nem o ano de 2024.
"""

import json
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest
from conftest_pipeline import config_rapida, mundo  # noqa: F401
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

from dengue_sinan.folds import dobras_loro
from dengue_sinan.modelos import cv_oof
from dengue_sinan.pipeline import baselines, bootstrap, exportacao, metricas, oof
from dengue_sinan.pipeline.contrato import RAIZ
from dengue_sinan.pipeline.preparacao import carregar_agrupamento

MODELOS = ["m1", "b0", "b1", "b1_idade"]
TODOS = list(oof.MODELOS)


@pytest.fixture(scope="module")
def avaliacao(mundo):  # noqa: F811
    cong = carregar_agrupamento(mundo["preparado"])
    tab, info = oof.gerar_oof(
        mundo["x"], mundo["y"], mundo["regiao"], mundo["meta"], mundo["cfg"], cong
    )
    return {"tab": tab, "info": info, "cong": cong}


def _tabela_pequena(rng, n_cong=30, por_cong=40, regioes=("Sudeste", "Sul")):
    linhas = []
    for k in range(n_cong):
        reg = regioes[k % len(regioes)]
        p = np.round(rng.uniform(0.001, 0.05, por_cong), 3)  # poucos níveis → empates
        y = (rng.uniform(size=por_cong) < p * 4).astype(int)
        linhas.append(pd.DataFrame({"regiao": reg, "conglomerado": f"c{k}", "y": y, "p_m1": p}))
    df = pd.concat(linhas, ignore_index=True)
    df["p_b0"] = df.groupby("regiao")["y"].transform("mean") * 0 + 0.01
    return df


# ---------- 1. treino/teste por dobra
def test_01_treino_e_teste_separados_em_cada_dobra(mundo):  # noqa: F811
    regiao = mundo["regiao"]
    for r, tr, te in dobras_loro(regiao):
        assert set(tr).isdisjoint(te)
        assert (regiao.iloc[te] == r).all()
        assert not (regiao.iloc[tr] == r).any()


def test_01_cada_linha_e_prevista_na_dobra_da_sua_regiao(avaliacao):
    tab = avaliacao["tab"]
    ordem = {r: k for k, r in enumerate(["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"], 1)}
    assert (tab["fold"] == tab["regiao"].map(ordem)).all()
    assert set(tab["ANO"]) <= {2022, 2023}


# ---------- 2. sem vazamento de rótulo
def test_02_trocar_rotulos_de_uma_regiao_nao_muda_a_predicao_dela(mundo):  # noqa: F811
    x, y, regiao = mundo["x"], np.asarray(mundo["y"]).copy(), mundo["regiao"]
    cong = carregar_agrupamento(mundo["preparado"])
    base, _ = oof.gerar_oof(
        x, y, regiao, mundo["meta"], mundo["cfg"], cong, incluir_calibrado=False
    )
    alvo = "Sul"
    y2 = y.copy()
    m = (regiao == alvo).to_numpy()
    y2[m] = 1 - y2[m]
    alt, _ = oof.gerar_oof(
        x, y2, regiao, mundo["meta"], mundo["cfg"], cong, incluir_calibrado=False
    )
    for modelo in MODELOS:
        col = oof.COLUNAS_P[modelo]
        sel = (base["regiao"] == alvo).to_numpy()
        assert np.array_equal(base.loc[sel, col], alt.loc[sel, col]), modelo
    outra = (base["regiao"] != alvo).to_numpy()  # sanidade: as outras regiões usam esse rótulo
    assert not np.array_equal(base.loc[outra, "p_b1"], alt.loc[outra, "p_b1"])


# ---------- 3. B0
def test_03_b0_usa_so_a_prevalencia_do_treino(mundo, avaliacao):  # noqa: F811
    y, regiao, tab = np.asarray(mundo["y"]), mundo["regiao"], avaliacao["tab"]
    for r, tr, _ in dobras_loro(regiao):
        esperado = y[tr].mean()
        valores = tab.loc[tab["regiao"] == r, "p_b0"].unique()
        assert len(valores) == 1 and valores[0] == pytest.approx(esperado)
        assert valores[0] != pytest.approx(y[(regiao == r).to_numpy()].mean())
    assert baselines.previsao_b0([0, 0, 1, 1]) == 0.5
    with pytest.raises(ValueError):
        baselines.previsao_b0([])


# ---------- 4 e 5. variáveis dos baselines
def test_04_b1_usa_as_tres_variaveis_autorizadas(avaliacao):
    for d in avaliacao["info"]["dobras"]:
        assert sorted(d["b1"]["variaveis"]) == ["gestante", "idade_anos", "sexo"]


def test_05_b1_idade_usa_so_idade(avaliacao):
    for d in avaliacao["info"]["dobras"]:
        assert d["b1_idade"]["variaveis"] == ["idade_anos"]


def test_04_05_baseline_recusa_variavel_nao_autorizada():
    with pytest.raises(ValueError, match="autorizada"):
        baselines.BaselineLogistico(["idade_anos", "conglomerado"])
    with pytest.raises(ValueError, match="autorizada"):
        baselines.BaselineLogistico(["idade_anos", "regiao"])


# ---------- 6. município fora dos preditores
def test_06_municipio_e_uf_nunca_entram_na_matriz_de_preditores(mundo):  # noqa: F811
    x = mundo["x"]
    assert list(x.columns) == ["idade_anos", "sexo", "gestante"]
    cfg = mundo["cfg"]
    assert cfg.variaveis == ["idade_anos", "sexo", "gestante"]
    cong = carregar_agrupamento(mundo["preparado"])
    assert len(cong) == len(x)
    assert "conglomerado" not in x.columns and "conglomerado" in mundo["conjunto"].columns


def test_06_artefato_de_producao_nao_conhece_o_conglomerado(mundo):  # noqa: F811
    contrato = json.loads((mundo["artefato"] / "contrato.json").read_text("utf-8"))
    assert "conglomerado" not in json.dumps(contrato)


def test_06_conglomerado_tem_uma_regiao_cada(avaliacao):
    g = avaliacao["tab"].groupby("conglomerado")["regiao"].nunique()
    assert (g == 1).all()


# ---------- 7. bootstrap por conglomerado
def test_07_bootstrap_mantem_as_linhas_do_conglomerado_juntas(avaliacao):
    tab = avaliacao["tab"]
    t = metricas.montar_tabela(tab, ["m1", "b0"])
    pesos = bootstrap.pesos_bootstrap(t, 5, 11)
    assert np.all(pesos == np.round(pesos)) and pesos.min() >= 0
    for r in t.regioes:  # estratificado: cada região mantém o número de conglomerados
        idx = t.indice_regiao[r]
        assert np.all(pesos[:, idx].sum(1) == len(idx))
    # uma réplica = repetir blocos inteiros: o total de linhas é a soma de peso × tamanho
    tamanho = np.asarray(t.N["m1"].sum(1)).ravel()
    assert np.all(pesos @ tamanho >= 0)


def test_07_pesos_equivalem_a_reamostrar_linhas_do_conglomerado_inteiro():
    rng = np.random.default_rng(3)
    df = _tabela_pequena(rng)
    t = metricas.montar_tabela(df, ["m1", "b0"])
    pesos = bootstrap.pesos_bootstrap(t, 1, 5)
    por_cong = dict(zip(t.conglomerados, pesos[0], strict=True))
    explicit = pd.concat(
        [df[df["conglomerado"] == c] for c, w in por_cong.items() for _ in range(int(w))]
    )
    por_pesos = metricas.metricas_todas(t, ["m1", "b0"], pesos=pesos)[("m1", "global")]
    assert por_pesos["pr_auc"][0] == pytest.approx(
        average_precision_score(explicit["y"], explicit["p_m1"])
    )
    assert por_pesos["roc_auc"][0] == pytest.approx(roc_auc_score(explicit["y"], explicit["p_m1"]))
    assert por_pesos["brier"][0] == pytest.approx(brier_score_loss(explicit["y"], explicit["p_m1"]))


# ---------- 8. sementes
def test_08_mesma_semente_reproduz_e_outra_semente_muda(avaliacao):
    t = metricas.montar_tabela(avaliacao["tab"], MODELOS)
    a = bootstrap.pesos_bootstrap(t, 20, 7)
    assert np.array_equal(a, bootstrap.pesos_bootstrap(t, 20, 7))
    assert not np.array_equal(a, bootstrap.pesos_bootstrap(t, 20, 8))
    r1 = bootstrap.executar_bootstrap(t, MODELOS, 40, 7)
    r2 = bootstrap.executar_bootstrap(t, MODELOS, 40, 7)
    assert r1["resultado"] == r2["resultado"]


def test_08_oof_reproduz_com_a_mesma_configuracao(mundo, avaliacao):  # noqa: F811
    cong = carregar_agrupamento(mundo["preparado"])
    de_novo, _ = oof.gerar_oof(
        mundo["x"], mundo["y"], mundo["regiao"], mundo["meta"], mundo["cfg"], cong
    )
    pd.testing.assert_frame_equal(avaliacao["tab"], de_novo)


def test_08_m1_oof_e_igual_ao_cv_oof_da_etapa_2(mundo, avaliacao):  # noqa: F811
    cfg = mundo["cfg"]
    ref = cv_oof(
        cfg.algoritmo,
        cfg.params,
        mundo["x"],
        mundo["y"],
        mundo["regiao"],
        cfg.seed,
        meta=mundo["meta"],
        paciencia=cfg.paciencia,
        val_frac=cfg.val_frac,
        max_iter=cfg.max_iter,
        n_jobs=cfg.n_jobs,
    )["oof"]
    tab = avaliacao["tab"]
    assert len(tab) == len(ref)
    assert np.array_equal(tab["p_m1"].to_numpy(), np.asarray(ref))


# ---------- 9. métricas em casos controlados
def test_09_separacao_perfeita_e_pior_caso():
    y = np.array([0, 0, 0, 1, 1])
    p = np.array([0.1, 0.2, 0.3, 0.8, 0.9])
    t = metricas.montar_tabela(
        pd.DataFrame({"regiao": "Sul", "conglomerado": list("abcde"), "y": y, "p_m1": p}),
        ["m1"],
    )
    m = metricas.metricas_todas(t, ["m1"])[("m1", "global")]
    assert m["roc_auc"][0] == 1.0 and m["pr_auc"][0] == 1.0
    assert m["brier"][0] == pytest.approx(np.mean((p - y) ** 2))
    assert m["prevalencia"][0] == pytest.approx(0.4)
    assert m["razao_pr_auc_prevalencia"][0] == pytest.approx(1.0 / 0.4)
    inv = metricas.montar_tabela(
        pd.DataFrame({"regiao": "Sul", "conglomerado": list("abcde"), "y": y, "p_m1": 1 - p}),
        ["m1"],
    )
    assert metricas.metricas_todas(inv, ["m1"])[("m1", "global")]["roc_auc"][0] == 0.0


def test_09_valores_a_mao_com_empates():
    # níveis 0.2 (2 neg, 1 pos) e 0.6 (1 neg, 2 pos)
    n = np.array([3.0, 3.0])
    e = np.array([1.0, 2.0])
    p = np.array([0.2, 0.6])
    m = metricas.metricas_de_contagens(n, e, p)
    # ROC: pares pos×neg = 3×3 = 9; acertos: 2 pos(0.6)×2 neg(0.2) = 4; empates: 1×2 + 2×1 = 4 → ½
    assert m["roc_auc"][0] == pytest.approx((4 + 0.5 * 4) / 9)
    # AP: limiar 0.6: prec 2/3, rec 2/3 ; limiar 0.2: prec 3/6, ganho 1/3 → 2/3·2/3 + 1/2·1/3
    assert m["pr_auc"][0] == pytest.approx(2 / 3 * 2 / 3 + 0.5 * 1 / 3)
    assert m["brier"][0] == pytest.approx((1 * 0.8**2 + 2 * 0.2**2 + 2 * 0.4**2 + 1 * 0.6**2) / 6)


def test_09_contagens_batem_com_scikit_learn_com_empates():
    rng = np.random.default_rng(1)
    df = _tabela_pequena(rng, n_cong=40, por_cong=60)
    t = metricas.montar_tabela(df, ["m1", "b0"])
    m = metricas.metricas_todas(t, ["m1", "b0"])
    g = m[("m1", "global")]
    assert g["pr_auc"][0] == pytest.approx(average_precision_score(df["y"], df["p_m1"]))
    assert g["roc_auc"][0] == pytest.approx(roc_auc_score(df["y"], df["p_m1"]))
    assert g["brier"][0] == pytest.approx(brier_score_loss(df["y"], df["p_m1"]))
    assert g["bss"][0] == pytest.approx(1 - g["brier"][0] / m[("b0", "global")]["brier"][0])
    media = np.mean([m[("m1", r)]["pr_auc"][0] for r in t.regioes])
    assert m[("m1", "media_das_dobras")]["pr_auc"][0] == pytest.approx(media)


def test_09_media_das_dobras_difere_da_metrica_no_pool(avaliacao):
    t = metricas.montar_tabela(avaliacao["tab"], MODELOS)
    m = metricas.metricas_todas(t, MODELOS)
    assert m[("m1", "media_das_dobras")]["roc_auc"][0] != pytest.approx(
        m[("m1", "global")]["roc_auc"][0]
    )
    # B0 é constante dentro da dobra: ROC por dobra = 0,5; no pool ≠ 0,5 (mistura prevalências)
    for r in t.regioes:
        assert m[("b0", r)]["roc_auc"][0] == pytest.approx(0.5)
    assert m[("b0", "global")]["roc_auc"][0] != pytest.approx(0.5)


# ---------- 10. réplicas inválidas
def test_10_replicas_sem_as_duas_classes_viram_nan_e_sao_contadas():
    rng = np.random.default_rng(0)
    linhas = []
    for k in range(10):  # um único conglomerado tem os eventos → muitas réplicas sem evento
        n = 20
        y = np.zeros(n, dtype=int)
        if k == 0:
            y[:3] = 1
        linhas.append(
            pd.DataFrame(
                {"regiao": "Sul", "conglomerado": f"c{k}", "y": y, "p_m1": rng.uniform(0, 1, n)}
            )
        )
    df = pd.concat(linhas, ignore_index=True)
    df["p_b0"] = 0.015
    t = metricas.montar_tabela(df, ["m1", "b0"])
    r = bootstrap.executar_bootstrap(t, ["m1", "b0"], 300, 4)
    inval = r["diagnostico"]["replicacoes_invalidas_por_metrica"]
    assert any(v > 0 for v in inval.values())
    linha = next(
        x
        for x in r["resultado"]
        if x["modelo"] == "m1" and x["escopo"] == "global" and x["metrica"] == "roc_auc"
    )
    assert linha["n_validas"] < 300
    iv = bootstrap.intervalo(np.array([0.5, np.nan, 0.7, np.nan, 0.6]))
    assert iv["n_replicacoes"] == 5 and iv["n_validas"] == 3
    assert np.isfinite(iv["ic_inf"])
    vazio = bootstrap.intervalo(np.array([np.nan, np.nan]))
    assert vazio["n_validas"] == 0 and np.isnan(vazio["ic_inf"])


# ---------- 11. supressão
def test_11_supressao_primaria_e_complementar():
    cont = pd.DataFrame(
        {
            "regiao": ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"],
            "n_linhas": [1000, 800, 500, 300, 100],
            "n_eventos": [200, 50, 5, 30, 0],
            "n_conglomerados": [10, 8, 5, 4, 2],
            "prevalencia": [0.2, 0.0625, 0.01, 0.1, 0.0],
        }
    )
    plano = exportacao.plano_supressao(cont).set_index("regiao")
    assert plano.loc["Centro-Oeste", "suprimida"]
    assert not plano.loc["Norte", "suprimida"]  # zero não é suprimido; 1 a 9 é
    assert plano["complementar"].sum() == 1
    assert plano.loc["Nordeste", "complementar"]  # menor célula visível com ≥ 20 eventos
    assert plano.loc[["Centro-Oeste", "Nordeste"], "oculta"].all()


def test_11_tabelas_exportadas_nao_trazem_celula_pequena(avaliacao):
    t = metricas.montar_tabela(avaliacao["tab"], MODELOS)
    cont = pd.DataFrame(
        [
            {
                "regiao": r,
                "n_linhas": t.linhas_por_regiao[r],
                "n_eventos": t.eventos_por_regiao[r] if r != "Norte" else 4,
                "n_conglomerados": len(t.indice_regiao[r]),
                "prevalencia": 0.01,
            }
            for r in t.regioes
        ]
    )
    boot = bootstrap.executar_bootstrap(t, MODELOS, 20, 1)
    tab = exportacao.tabelas(boot, MODELOS, t.regioes, cont)
    c = tab["contagens_por_regiao"].set_index("regiao")
    assert pd.isna(c.loc["Norte", "n_eventos"])
    assert c.loc["Norte", "supressao"] == "primaria"
    assert (c["supressao"] == "complementar").sum() == 1
    oculto = c.index[c["n_eventos"].isna()]
    por_dobra = tab["metricas_por_dobra"]
    assert por_dobra.loc[por_dobra["regiao"].isin(oculto), "pr_auc"].isna().all()
    vis = c["n_eventos"].dropna()
    assert not vis.between(1, 9).any()


# ---------- 12. sem predição individual
def test_12_verificador_recusa_tabela_individual(avaliacao):
    with pytest.raises(ValueError, match="proibidas"):
        exportacao.verificar_agregado(avaliacao["tab"].head(5), "oof")
    grande = pd.DataFrame({"a": range(exportacao.LIMITE_LINHAS + 1)})
    with pytest.raises(ValueError, match="agregada"):
        exportacao.verificar_agregado(grande, "grande")


def test_12_oof_nao_pode_ser_gravado_em_reports(avaliacao):
    with pytest.raises(PermissionError, match="reports"):
        oof.salvar_oof_local(avaliacao["tab"], RAIZ / "reports" / "etapa3" / "oof")
    assert not (RAIZ / "reports" / "etapa3" / "oof").exists()


def test_12_avaliacao_completa_gera_so_agregados(mundo, tmp_path):  # noqa: F811
    from dataclasses import asdict

    from dengue_sinan.pipeline.avaliar_oof import executar

    cfg_arq = tmp_path / "treino.json"
    cfg_arq.write_text(json.dumps(asdict(config_rapida())), "utf-8")
    av = json.loads((RAIZ / "config" / "avaliacao_oof.json").read_text("utf-8"))
    av["bootstrap"]["replicacoes"] = 30
    av_arq = tmp_path / "avaliacao.json"
    av_arq.write_text(json.dumps(av), "utf-8")
    saida, local = tmp_path / "agregado", tmp_path / "local"
    r = executar(cfg_arq, av_arq, mundo["preparado"], saida, local)
    arquivos = {p.name for p in saida.iterdir()}
    assert {"metricas_globais.csv", "metadados_avaliacao.json", "diagnostico_bootstrap.json"} <= (
        arquivos
    )
    assert not any(p.suffix == ".parquet" for p in saida.rglob("*"))
    assert (local / av["versao_avaliacao"] / "oof_predicoes.parquet").exists()
    textos = "".join(p.read_text("utf-8") for p in saida.iterdir())
    assert "p_m1" not in textos and "conglomerado\n" not in textos
    meta = json.loads((saida / "metadados_avaliacao.json").read_text("utf-8"))
    for chave in ("dados", "modelo", "dobras", "bootstrap", "ambiente", "codigo", "agrupamento"):
        assert chave in meta
    est = meta["modelo"]["parametros_do_estimador_xgboost"]
    assert {"device", "tree_method", "eval_metric"} <= set(est)
    assert "indisponível" in meta["codigo"]["git"]
    assert meta["bootstrap"]["seed"] == av["bootstrap"]["seed"]
    assert meta["agrupamento"]["usado_como_preditor"] is False
    assert r["oof_local"]
    with pytest.raises(FileExistsError):  # nunca sobrescreve
        executar(cfg_arq, av_arq, mundo["preparado"], saida, local)


def test_12_nenhum_arquivo_individual_em_reports_ou_versionado():
    proibidos = []
    for p in (RAIZ / "reports").rglob("*"):
        if p.is_file() and (p.suffix == ".parquet" or "oof_predicoes" in p.name):
            proibidos.append(str(p))
    assert proibidos == []
    gi = (RAIZ / ".gitignore").read_text("utf-8")
    assert "*.parquet" in gi and "/artefatos/oof/" in gi


# ---------- 13. R1
def test_13_baseline_e_oof_recusam_2024(mundo):  # noqa: F811
    meta = pd.DataFrame({"ANO": [2024] * len(mundo["x"])}, index=mundo["x"].index)
    with pytest.raises(PermissionError):
        baselines.BaselineLogistico(["idade_anos"]).ajustar(mundo["x"], mundo["y"], meta)
    cong = carregar_agrupamento(mundo["preparado"])
    with pytest.raises(PermissionError):
        oof.gerar_oof(mundo["x"], mundo["y"], mundo["regiao"], meta, mundo["cfg"], cong)


def test_13_config_de_avaliacao_nao_menciona_2024_como_dado():
    av = json.loads((RAIZ / "config" / "avaliacao_oof.json").read_text("utf-8"))
    assert "2024" not in json.dumps(av)


# ---------- 14. inferência independente
def test_14_inferencia_nao_importa_modulos_de_avaliacao(mundo, tmp_path):  # noqa: F811
    codigo = (
        "import sys, json\n"
        "from dengue_sinan.pipeline.inferencia import carregar_modelo\n"
        f"m = carregar_modelo({str(mundo['artefato'])!r})\n"
        "m.prever([{'idade_anos': 30, 'sexo': 'F'}])\n"
        "novos = ['oof', 'baselines', 'metricas', 'bootstrap', 'exportacao', 'avaliar_oof',\n"
        "         'preparacao', 'treino']\n"
        "print(json.dumps([n for n in novos if f'dengue_sinan.pipeline.{n}' in sys.modules]))\n"
    )
    import os

    saida = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, "PYTHONPATH": str(RAIZ / "src")},
    )
    assert json.loads(saida.stdout.strip().splitlines()[-1]) == []


def test_14_modulos_novos_nao_tem_dependencia_circular():
    import ast

    ordem = {
        "baselines": 0,
        "metricas": 0,
        "oof": 1,
        "bootstrap": 1,
        "exportacao": 2,
        "avaliar_oof": 3,
    }
    for nome, nivel in ordem.items():
        arvore = ast.parse((RAIZ / "src/dengue_sinan/pipeline" / f"{nome}.py").read_text("utf-8"))
        for no in ast.walk(arvore):
            if isinstance(no, ast.ImportFrom) and no.module == "dengue_sinan.pipeline":
                for a in no.names:
                    if a.name in ordem:
                        assert ordem[a.name] < nivel, f"{nome} importa {a.name}"
            if (
                isinstance(no, ast.ImportFrom)
                and no.module
                and no.module.startswith("dengue_sinan.pipeline.")
            ):
                alvo = no.module.rsplit(".", 1)[1]
                if alvo in ordem:
                    assert ordem[alvo] < nivel or alvo == nome, f"{nome} importa {alvo}"
