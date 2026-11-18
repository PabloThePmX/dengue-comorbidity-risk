"""Calibração, limiar, regra de seleção e gancho `selecao.executar` (T-4.9, D-53, R1, R7).

Dados sintéticos em pastas temporárias. Nada aqui lê microdados nem o ano de teste (R1): o OOF
de 2024 só aparece no teste que confere a guarda.
"""

import copy
import inspect
import json

import numpy as np
import pandas as pd
import pytest
from mlflow.tracking import MlflowClient
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from dengue_sinan import metrics, selecao
from dengue_sinan.config import load_config

REGIOES = ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"]
CANDIDATOS = ["elastic_net", "xgboost", "catboost", "mlp", "random_forest"]  # D-91: sem TabFM
N_POR_REGIAO = 400


@pytest.fixture
def cfg(tmp_path):
    """Config real, com dados, relatórios e mlruns em pastas temporárias; 30 reamostras."""
    base = load_config()
    caminhos = {
        "dados": str(tmp_path / "data"),
        "relatorios": str(tmp_path / "reports"),
        "mlruns": str(tmp_path / "mlruns"),
        "modelos": str(tmp_path / "models"),
    }
    return {**copy.deepcopy(base), "caminhos": caminhos, "ordem_dobras": REGIOES,
            "ordem_modelos": CANDIDATOS, "bootstrap_pareado": 30}


def _base_linhas(seed: int = 1) -> pd.DataFrame:
    """Linhas comuns a todos os modelos: ANO, região e alvo. Cada região tem positivos."""
    rng = np.random.default_rng(seed)
    partes = []
    for regiao in REGIOES:
        y = (rng.uniform(size=N_POR_REGIAO) < 0.12).astype(np.int64)
        if regiao == "Norte":  # só 5 eventos: a contagem tem que sair suprimida (R7)
            y[:] = 0
            y[:5] = 1
        y[0] = 1
        partes.append(pd.DataFrame({
            "ANO": rng.choice([2022, 2023], size=N_POR_REGIAO),
            "regiao": regiao,
            "y": y,
        }))
    return pd.concat(partes, ignore_index=True)


def _p_do_modelo(y: np.ndarray, sinal: float, ruido: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return np.clip(0.08 + sinal * y + rng.normal(0, ruido, y.size), 0.001, 0.999)


def _montar(tmp_path, cfg, sinais: dict[str, float] | None = None) -> dict:
    """Escreve o OOF de cada candidato e dos baselines e devolve o `resultados` do runner."""
    base = _base_linhas()
    y = base["y"].to_numpy()
    sinais = sinais or {m: 0.10 + 0.05 * i for i, m in enumerate(CANDIDATOS)}
    resultados = {}
    for i, modelo in enumerate(CANDIDATOS):
        pasta = tmp_path / "m1" / modelo
        pasta.mkdir(parents=True)
        df = base.assign(p=_p_do_modelo(y, sinais[modelo], 0.25, seed=100 + i))
        df.to_parquet(pasta / "oof.parquet", index=False)
        grupos = [d for _, d in df.groupby("regiao", sort=False)]
        pr_media = float(np.mean([metrics.pr_auc(d["y"], d["p"]) for d in grupos]))
        (pasta / "metricas.json").write_text(json.dumps({"pr_auc_media": pr_media}),
                                             encoding="utf-8")
        (pasta / "parametros.json").write_text(json.dumps({"tuning": {
            "t_cronometragem_s": 120.0, "orcamento_s": 600.0, "subamostra": False, "fracao": 1.0,
            "tentativas_concluidas": 7, "tentativas_podadas": 3, "tentativas_falhas": 0,
        }}), encoding="utf-8")
        resultados[modelo] = {"modelo": modelo, "pulado": False, "pasta": str(pasta),
                              "metricas": {"pr_auc_media": pr_media}}

    pasta_base = tmp_path / "data" / "oof"
    pasta_base.mkdir(parents=True)
    base.assign(p=float(base["y"].mean())).to_parquet(pasta_base / "oof_B0.parquet", index=False)
    base.assign(p=_p_do_modelo(y, 0.15, 0.3, seed=7)).to_parquet(
        pasta_base / "oof_B1.parquet", index=False)
    base.assign(p=(y | (np.arange(y.size) % 3 == 0)).astype(float)).to_parquet(
        pasta_base / "oof_B2.parquet", index=False)
    return resultados


def _ler_selecao(tmp_path) -> dict:
    return json.loads((tmp_path / "data" / "m1" / "selecao.json").read_text(encoding="utf-8"))


def _executar(cfg, resultados, monkeypatch) -> list[dict]:
    # O número esperado da população vem do config/esperado.yaml (2,45 M). Aqui é o sintético.
    monkeypatch.setattr(selecao, "_populacao_esperada", lambda: 5 * N_POR_REGIAO)
    return selecao.executar(cfg, resultados)


# --- Calibradores --------------------------------------------------------------------------------


def test_escolhe_o_calibrador_de_menor_brier_e_empate_vai_para_platt():
    assert selecao.escolher_calibrador({"platt": 0.0021, "isotonica": 0.0019}) == "isotonica"
    assert selecao.escolher_calibrador({"platt": 0.0019, "isotonica": 0.0021}) == "platt"
    assert selecao.escolher_calibrador({"platt": 0.002, "isotonica": 0.002}) == "platt"


def test_calibrador_escolhido_tem_o_menor_brier_fora_da_dobra(cfg, tmp_path):
    resultados = _montar(tmp_path, cfg)
    base = selecao._carregar_predicoes(cfg, resultados)[0]["elastic_net"]
    analise = selecao._analisar_candidato(base, len(REGIOES))

    menor = min(analise["brier_fora_da_dobra"], key=analise["brier_fora_da_dobra"].get)
    assert analise["calibrador_tipo"] == menor
    assert analise["brier_calibrado"] == analise["brier_fora_da_dobra"][menor]


def test_isotonica_aplicada_bate_com_o_predict_do_sklearn():
    rng = np.random.default_rng(3)
    p = rng.uniform(size=2_000)
    y = rng.binomial(1, p ** 2)
    # inclui valores fora do alcance dos nós
    consulta = np.concatenate([rng.uniform(size=300), [-0.5, 0.0, 1.0, 1.7]])

    sk = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(p, y)
    mine = selecao.ajustar_isotonica(p, y).aplicar(consulta)

    assert np.allclose(mine, sk.predict(consulta), atol=1e-12)


def test_platt_aplicada_bate_com_a_logistica_do_sklearn():
    rng = np.random.default_rng(4)
    p = rng.uniform(0.01, 0.99, 2_000)
    y = rng.binomial(1, p)
    consulta = rng.uniform(0.01, 0.99, 200)
    logit = lambda q: np.log(q / (1 - q))  # noqa: E731

    sk = LogisticRegression(C=np.inf, solver="lbfgs", max_iter=1000).fit(
        logit(p).reshape(-1, 1), y)
    mine = selecao.ajustar_platt(p, y).aplicar(consulta)

    assert np.allclose(mine, sk.predict_proba(logit(consulta).reshape(-1, 1))[:, 1], atol=1e-7)


def test_brier_fora_da_dobra_nunca_calibra_uma_linha_com_ajuste_que_a_viu():
    p = np.linspace(0.01, 0.99, 50)
    y = (p > 0.5).astype(int)
    dobra = np.repeat([0, 1, 2, 3, 4], 10)
    vistos = []

    def ajustar_espiao(p_treino, y_treino):
        # Guarda quais linhas entraram no ajuste (pelo valor de p, que é único).
        vistos.append(set(np.round(p_treino, 12)))
        return selecao.Calibrador("platt", {"coef": np.array([1.0]),
                                            "intercepto": np.array([0.0])})

    selecao.brier_fora_da_dobra(p, y, dobra, ajustar_espiao)

    for d, vistos_d in zip(range(5), vistos, strict=True):
        da_dobra = set(np.round(p[dobra == d], 12))
        assert vistos_d.isdisjoint(da_dobra)


def test_calibrador_gravado_recarrega_igual_e_recusa_arquivo_adulterado(tmp_path):
    cal = selecao.ajustar_isotonica(np.linspace(0, 1, 200), (np.linspace(0, 1, 200) > 0.6))
    pasta = tmp_path / "cal"

    selecao.salvar_calibrador(cal, pasta)
    recarregado = selecao.carregar_calibrador(pasta)
    q = np.linspace(0, 1, 37)

    assert recarregado.tipo == "isotonica"
    assert np.array_equal(recarregado.aplicar(q), cal.aplicar(q))

    (pasta / "calibrador.npz").write_bytes(b"adulterado")
    with pytest.raises(ValueError, match="SHA-256"):
        selecao.carregar_calibrador(pasta)


def test_calibrador_salvo_nao_usa_pickle(tmp_path):
    cal = selecao.ajustar_platt(np.linspace(0.05, 0.95, 100), np.tile([0, 1], 50))
    selecao.salvar_calibrador(cal, tmp_path)
    # allow_pickle=False levanta erro se houver objeto serializado
    with np.load(tmp_path / "calibrador.npz", allow_pickle=False) as npz:
        assert set(npz.files) == {"coef", "intercepto"}


# --- Regra de seleção ----------------------------------------------------------------------------


def _resumo(pr, ic, brier):
    return {"pr_auc_media": pr, "ic_inf": ic[0], "ic_sup": ic[1], "brier": brier}


ORDEM = ["elastic_net", "random_forest", "xgboost", "catboost", "mlp"]


def test_sem_empate_vence_a_maior_pr_auc_mesmo_com_brier_pior():
    resumos = {
        "elastic_net": _resumo(0.30, (0.29, 0.31), 0.0020),
        "random_forest": _resumo(0.25, (0.20, 0.28), 0.0010),
    }
    escolha = selecao.escolher_modelo(resumos, ORDEM)
    assert escolha["vencedor"] == "elastic_net"
    assert escolha["empatados"] == ["elastic_net"]


def test_diferenca_menor_que_0_005_empata_e_vence_o_menor_brier():
    resumos = {
        "elastic_net": _resumo(0.300, (0.29, 0.31), 0.0020),
        "random_forest": _resumo(0.297, (0.20, 0.25), 0.0015),  # IC disjunto, mas diff < 0,005
    }
    escolha = selecao.escolher_modelo(resumos, ORDEM)
    assert escolha["vencedor"] == "random_forest"
    assert set(escolha["empatados"]) == {"elastic_net", "random_forest"}


def test_ics_sobrepostos_empatam_mesmo_com_diferenca_maior_que_0_005():
    resumos = {
        "elastic_net": _resumo(0.300, (0.28, 0.32), 0.0020),
        "random_forest": _resumo(0.290, (0.27, 0.31), 0.0015),  # diff 0,010, ICs se cruzam
    }
    escolha = selecao.escolher_modelo(resumos, ORDEM)
    assert escolha["vencedor"] == "random_forest"


def test_diferenca_grande_e_ics_disjuntos_nao_empatam():
    resumos = {
        "elastic_net": _resumo(0.300, (0.29, 0.31), 0.0020),
        "random_forest": _resumo(0.290, (0.20, 0.285), 0.0010),
    }
    escolha = selecao.escolher_modelo(resumos, ORDEM)
    assert escolha["vencedor"] == "elastic_net"
    assert escolha["empatados"] == ["elastic_net"]


def test_empate_total_no_brier_vai_para_o_modelo_mais_simples():
    resumos = {
        "xgboost": _resumo(0.300, (0.29, 0.31), 0.0015),
        "elastic_net": _resumo(0.300, (0.29, 0.31), 0.0015),
    }
    assert selecao.escolher_modelo(resumos, ORDEM)["vencedor"] == "elastic_net"


def test_modelo_fora_da_faixa_de_empate_nao_vence_pelo_brier():
    resumos = {
        "elastic_net": _resumo(0.300, (0.29, 0.31), 0.0020),
        "random_forest": _resumo(0.299, (0.29, 0.31), 0.0018),
        "mlp": _resumo(0.200, (0.19, 0.21), 0.0001),  # Brier ótimo, mas fora do empate
    }
    assert selecao.escolher_modelo(resumos, ORDEM)["vencedor"] == "random_forest"


def test_a_regra_nao_recebe_a_comparacao_pareada():
    # A pareada é só reportada (D-53): a regra não tem parâmetro para ela.
    assert "pares" not in inspect.signature(selecao.escolher_modelo).parameters


def test_modelo_sem_posicao_de_simplicidade_e_recusado():
    with pytest.raises(ValueError, match="simplicidade"):
        selecao.escolher_modelo({"b1": _resumo(0.2, (0.1, 0.3), 0.001)}, ORDEM)


# --- Gancho da sessão (executar) ------------------------------------------------------------------


def test_executar_escolhe_um_modelo_grava_tudo_e_todos_os_checks_passam(cfg, tmp_path, monkeypatch):
    resultados = _montar(tmp_path, cfg)
    checks = _executar(cfg, resultados, monkeypatch)

    assert all(c["passou"] for c in checks), checks
    selecao_json = _ler_selecao(tmp_path)
    assert selecao_json["vencedor"] in CANDIDATOS
    assert 0.0 <= selecao_json["limiar"] <= 1.0
    for modelo in CANDIDATOS:
        assert (tmp_path / "data" / "m1" / modelo / "calibrador.json").exists()


def test_limiar_gravado_e_o_f2_maximo_nas_predicoes_calibradas(cfg, tmp_path, monkeypatch):
    resultados = _montar(tmp_path, cfg)
    _executar(cfg, resultados, monkeypatch)
    selecao_json = _ler_selecao(tmp_path)
    vencedor = selecao_json["vencedor"]

    oof = pd.read_parquet(tmp_path / "m1" / vencedor / "oof.parquet")
    cal = selecao.carregar_calibrador(tmp_path / "data" / "m1" / vencedor)
    p_cal = cal.aplicar(oof["p"].to_numpy())

    assert selecao_json["limiar"] == metrics.best_f2_threshold(oof["y"].to_numpy(), p_cal)


def test_pareada_cobre_21_pares_com_b1_e_e_so_reportada(cfg, tmp_path, monkeypatch):
    resultados = _montar(tmp_path, cfg)
    _executar(cfg, resultados, monkeypatch)
    relatorio = (tmp_path / "reports" / "m1" / "comparacao_pareada.md").read_text(encoding="utf-8")

    linhas_do_par = [ln for ln in relatorio.splitlines()
                     if ln.startswith("| ") and " − " in ln and not ln.startswith("| Par")]
    n = len(CANDIDATOS)  # pares entre candidatos (n·(n-1)/2) mais um par com B1 por candidato
    assert len(linhas_do_par) == n * (n - 1) // 2 + n
    assert any("B1" in ln for ln in linhas_do_par)
    assert "Não entra na seleção" in relatorio


def test_relatorio_oof_suprime_contagens_menores_que_10(cfg, tmp_path, monkeypatch):
    resultados = _montar(tmp_path, cfg)  # a região Norte tem 5 eventos
    _executar(cfg, resultados, monkeypatch)
    relatorio = (tmp_path / "reports" / "m1" / "comparacao_oof.md").read_text(encoding="utf-8")

    assert "Norte: <10" in relatorio
    assert "Norte: 5" not in relatorio


def test_relatorio_oof_so_tem_agregados_e_o_vencedor(cfg, tmp_path, monkeypatch):
    resultados = _montar(tmp_path, cfg)
    _executar(cfg, resultados, monkeypatch)
    relatorio = (tmp_path / "reports" / "m1" / "comparacao_oof.md").read_text(encoding="utf-8")
    selecao_json = _ler_selecao(tmp_path)

    assert f"**Vencedor: {selecao_json['vencedor']}.**" in relatorio
    assert "ANO" not in relatorio  # o relatório não despeja colunas de linha
    assert "regiao" not in relatorio
    for linha in relatorio.splitlines():
        if linha.startswith("| "):
            assert linha.count("|") >= 3  # tabelas de agregados, sem colunas de linha individual


def test_executar_registra_vencedor_e_motivo_no_mlflow(cfg, tmp_path, monkeypatch):
    resultados = _montar(tmp_path, cfg)
    _executar(cfg, resultados, monkeypatch)
    selecao_json = _ler_selecao(tmp_path)

    client = MlflowClient(tracking_uri=cfg["caminhos"]["mlruns"])
    experimento = client.get_experiment_by_name("dengue-comorbidity-risk")
    runs = client.search_runs([experimento.experiment_id],
                              filter_string="attributes.run_name = 'selecao'")
    assert len(runs) == 1
    assert runs[0].data.params["selecao.vencedor"] == selecao_json["vencedor"]
    assert runs[0].data.params["selecao.motivo"] == selecao_json["motivo"]


def test_executar_recusa_oof_com_ano_de_teste(cfg, tmp_path, monkeypatch):
    resultados = _montar(tmp_path, cfg)
    arquivo = tmp_path / "m1" / "xgboost" / "oof.parquet"
    df = pd.read_parquet(arquivo)
    df.loc[0, "ANO"] = 2024
    df.to_parquet(arquivo, index=False)

    with pytest.raises(RuntimeError, match="R1"):
        _executar(cfg, resultados, monkeypatch)


def test_executar_recusa_oof_com_linhas_fora_de_ordem(cfg, tmp_path, monkeypatch):
    resultados = _montar(tmp_path, cfg)
    arquivo = tmp_path / "m1" / "mlp" / "oof.parquet"
    df = pd.read_parquet(arquivo).sample(frac=1.0, random_state=0).reset_index(drop=True)
    df.to_parquet(arquivo, index=False)

    with pytest.raises(ValueError, match="fora de ordem"):
        _executar(cfg, resultados, monkeypatch)


def test_executar_checks_pegam_populacao_errada(cfg, tmp_path, monkeypatch):
    resultados = _montar(tmp_path, cfg)
    monkeypatch.setattr(selecao, "_populacao_esperada", lambda: 999_999)
    checks = selecao.executar(cfg, resultados)
    reprovados = {c["nome"] for c in checks if not c["passou"]}
    assert "linhas_oof" in reprovados


# --- Ponta a ponta do gancho: semente, sorteios compartilhados e vencedor -------------------------


def _reescrever_p(tmp_path, modelo, p):
    """Troca as predições de um candidato e recalcula a PR-AUC média gravada no metricas.json."""
    arquivo = tmp_path / "m1" / modelo / "oof.parquet"
    df = pd.read_parquet(arquivo).assign(p=np.asarray(p, dtype=float))
    df.to_parquet(arquivo, index=False)
    grupos = [g for _, g in df.groupby("regiao", sort=False)]
    pr = float(np.mean([metrics.pr_auc(g["y"], g["p"]) for g in grupos]))
    (tmp_path / "m1" / modelo / "metricas.json").write_text(
        json.dumps({"pr_auc_media": pr}), encoding="utf-8")


def _ics_independentes(cfg, tmp_path, seed):
    """IC 95% da PR-AUC média de cada candidato por uma passagem independente (mesmos sorteios)."""
    ref = pd.read_parquet(tmp_path / "m1" / CANDIDATOS[0] / "oof.parquet")
    y = ref["y"].to_numpy(np.int64)
    dobra = ref["regiao"].map({r: i for i, r in enumerate(REGIOES)}).to_numpy(np.int64)
    escores = {m: pd.read_parquet(tmp_path / "m1" / m / "oof.parquet")["p"].to_numpy(float)
               for m in CANDIDATOS}
    b1 = tmp_path / "data" / "oof" / "oof_B1.parquet"
    escores["B1"] = pd.read_parquet(b1)["p"].to_numpy(float)
    boot = metrics.paired_bootstrap_pr_auc(escores, y, dobra, n=cfg["bootstrap_pareado"], seed=seed)
    return {m: (float(np.quantile(boot["media"][m], 0.025)),
                float(np.quantile(boot["media"][m], 0.975))) for m in CANDIDATOS}


def test_ics_do_pareado_seguem_a_semente_do_config(cfg, tmp_path, monkeypatch):
    cfg = {**cfg, "seed": 777}  # semente diferente da padrão: um valor fixo no código falharia
    resultados = _montar(tmp_path, cfg)
    _executar(cfg, resultados, monkeypatch)
    sj = _ler_selecao(tmp_path)

    esperado = _ics_independentes(cfg, tmp_path, seed=777)
    assert sj["semente"] == 777
    for m in CANDIDATOS:
        assert sj["modelos"][m]["ic_95"] == pytest.approx(list(esperado[m]), abs=1e-12)


def test_ics_de_executar_vem_de_uma_passagem_com_os_mesmos_sorteios(cfg, tmp_path, monkeypatch):
    resultados = _montar(tmp_path, cfg)
    _executar(cfg, resultados, monkeypatch)
    sj = _ler_selecao(tmp_path)

    # Um único sorteio por reamostra, para todos os modelos (incluindo B1 no bootstrap).
    esperado = _ics_independentes(cfg, tmp_path, seed=cfg["seed"])
    for m in CANDIDATOS:
        assert sj["modelos"][m]["ic_95"] == pytest.approx(list(esperado[m]), abs=1e-12)


def test_vencedor_com_pr_auc_claramente_maior_e_ic_disjunto(cfg, tmp_path, monkeypatch):
    sinais = {m: 0.05 for m in CANDIDATOS}
    sinais["elastic_net"] = 0.6
    resultados = _montar(tmp_path, cfg, sinais)
    _executar(cfg, resultados, monkeypatch)
    sj = _ler_selecao(tmp_path)

    inf_topo = sj["modelos"]["elastic_net"]["ic_95"][0]
    for m in CANDIDATOS:  # pré-condição do cenário: ICs disjuntos
        if m != "elastic_net":
            assert sj["modelos"][m]["ic_95"][1] < inf_topo
    assert sj["vencedor"] == "elastic_net"
    assert sj["empatados"] == ["elastic_net"]


def _cenario_empate_por_brier(tmp_path, cfg, monkeypatch):
    """xgboost e catboost com o mesmo ranking (catboost = xgboost³): PR-AUC igual, Brier não."""
    sinais = {m: 0.05 for m in CANDIDATOS}
    sinais["xgboost"] = 0.5
    sinais["catboost"] = 0.5
    resultados = _montar(tmp_path, cfg, sinais)
    px = pd.read_parquet(tmp_path / "m1" / "xgboost" / "oof.parquet")["p"].to_numpy(float)
    _reescrever_p(tmp_path, "catboost", px ** 3)
    _executar(cfg, resultados, monkeypatch)
    sj = _ler_selecao(tmp_path)
    brier = {m: sj["modelos"][m]["brier_calibrado"] for m in ("xgboost", "catboost")}
    return sj, brier


def test_empate_induzido_desempata_pelo_brier(cfg, tmp_path, monkeypatch):
    sj, brier = _cenario_empate_por_brier(tmp_path, cfg, monkeypatch)

    assert set(sj["empatados"]) == {"xgboost", "catboost"}  # pré-condição: empate pela regra
    assert abs(brier["xgboost"] - brier["catboost"]) > 1e-9  # pré-condição: Brier diferente
    assert sj["vencedor"] == min(brier, key=brier.get)


def test_comparacao_pareada_significativa_contra_o_vencedor_nao_muda_o_vencedor(
    cfg, tmp_path, monkeypatch
):
    sj0, brier = _cenario_empate_por_brier(tmp_path, cfg, monkeypatch)
    vencedor = sj0["vencedor"]
    perdedor = "catboost" if vencedor == "xgboost" else "xgboost"
    assert vencedor == min(brier, key=brier.get)

    original = selecao._comparacao_pareada

    def pareada_contra_o_vencedor(*args, **kwargs):
        resultado = original(*args, **kwargs)
        for chave in list(resultado["pares"]):
            if set(chave) == {vencedor, perdedor}:
                # perdedor significativamente melhor que o vencedor (IC exclui 0 a favor dele)
                sinal = 1.0 if chave[0] == perdedor else -1.0
                resultado["pares"][chave] = {
                    "diferenca_por_dobra": np.full(5, 0.05 * sinal),
                    "estimativa": 0.05 * sinal,
                    "ic_inf": 0.04 * sinal if sinal > 0 else -0.06,
                    "ic_sup": 0.06 if sinal > 0 else -0.04,
                }
        return resultado

    monkeypatch.setattr(selecao, "_comparacao_pareada", pareada_contra_o_vencedor)
    _executar(cfg, _montar_de_novo_resultados(tmp_path), monkeypatch)
    sj1 = _ler_selecao(tmp_path)

    assert sj1["vencedor"] == vencedor  # a pareada não entra na regra
    assert sj1["empatados"] == sj0["empatados"]


def _montar_de_novo_resultados(tmp_path):
    """Os resultados já estão nas pastas de tmp_path: monta a mesma estrutura do runner."""
    return {m: {"pasta": str(tmp_path / "m1" / m)} for m in CANDIDATOS}
