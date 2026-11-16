"""Testes dos baselines B0, B1 e B2 (T-2.8) com dados sintéticos (nenhum microdado real)."""

import numpy as np
import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

from dengue_sinan import baselines as bl
from dengue_sinan.profiling import COMORBIDADES

ORDEM = ["Sudeste", "Sul", "Norte"]  # 3 regiões bastam para testar a mecânica das dobras


def caso(**campos) -> dict:
    """Caso sem nenhum critério de alto risco (idade 30, sem gestação, sem sinais); campos mudam."""
    base = {"idade_anos": 30.0, "gestante": 0, "LACO": "Não", "PETEQUIA_N": "Não",
            "sexo": "F", **{c: "Não" for c in COMORBIDADES}}
    base.update(campos)
    return base


def frame(linhas: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(linhas)
    for c in [*COMORBIDADES, "LACO", "PETEQUIA_N"]:
        if c in df.columns:
            df[c] = pd.Categorical(df[c], categories=["Sim", "Não", "Ausente"])
    df["gestante"] = df["gestante"].astype("int8")
    return df


def alto_risco(**campos) -> bool:
    return bool(bl.rule_b2(frame([caso(**campos)]))[0])


# --- B2: regra do protocolo, caso a caso ----------------------------------------------------

def test_b2_caso_sem_criterio_nao_e_alto_risco():
    assert alto_risco() is False


@pytest.mark.parametrize("idade, esperado", [
    (0, True), (1, True), (1.9, True),      # abaixo de 2 anos
    (2, False), (30, False),                  # 2 anos entra no limite (não é < 2)
    (65, False),                              # 65 anos não é > 65
    (65.5, True), (66, True), (120, True),   # acima de 65
])
def test_b2_limites_de_idade(idade, esperado):
    assert alto_risco(idade_anos=idade) is esperado


def test_b2_gestante_sim_e_alto_risco():
    assert alto_risco(gestante=1) is True
    assert alto_risco(gestante=0) is False


@pytest.mark.parametrize("comorbidade", COMORBIDADES)
def test_b2_cada_comorbidade_sim_e_alto_risco(comorbidade):
    assert alto_risco(**{comorbidade: "Sim"}) is True


@pytest.mark.parametrize("comorbidade", COMORBIDADES)
def test_b2_comorbidade_nao_ou_ausente_nao_conta(comorbidade):
    assert alto_risco(**{comorbidade: "Não"}) is False
    assert alto_risco(**{comorbidade: "Ausente"}) is False


def test_b2_laco_sim_e_alto_risco_e_petequia_sim_tambem():
    assert alto_risco(LACO="Sim") is True
    assert alto_risco(PETEQUIA_N="Sim") is True


def test_b2_laco_ou_petequia_ausente_nao_conta():
    assert alto_risco(LACO="Ausente", PETEQUIA_N="Não") is False


def test_b2_devolve_um_booleano_por_linha():
    df = frame([caso(), caso(idade_anos=1), caso(RENAL="Sim"), caso(PETEQUIA_N="Sim")])
    saida = bl.rule_b2(df)
    assert saida.dtype == bool
    assert saida.tolist() == [False, True, True, True]


# --- B0 --------------------------------------------------------------------------------------

def test_b0_prediz_a_prevalencia_do_treino_nao_da_validacao():
    treino = frame([caso(y=1)] * 10 + [caso(y=0)] * 90).assign(ANO=2022)     # 10% no treino
    validacao = frame([caso(y=1)] * 50 + [caso(y=0)] * 50).assign(ANO=2023)  # 50% na validação
    p = bl.prever_b0(treino, validacao)
    assert len(p) == len(validacao)
    assert np.allclose(p, 0.10)


# --- B1 --------------------------------------------------------------------------------------

def test_b1_nao_usa_n_comorbidades():
    assert "n_comorbidades" not in bl.COLUNAS_B1
    assert "n_comorbidades" not in bl.CATEGORICAS_B1


def test_b1_nao_muda_com_n_comorbidades():
    rng = np.random.default_rng(1)
    treino = _dados_sinteticos(rng, n=3000)
    valid = _dados_sinteticos(rng, n=500)
    modelo = bl.ajustar_b1(treino)
    p_antes = bl.prever_b1(modelo, valid)

    valid_com_coluna = valid.assign(n_comorbidades=rng.integers(0, 8, size=len(valid)))
    p_depois = bl.prever_b1(modelo, valid_com_coluna)
    assert np.array_equal(p_antes, p_depois)


def test_b1_roda_dentro_de_pipeline_com_spline_so_do_treino():
    rng = np.random.default_rng(2)
    treino = _dados_sinteticos(rng, n=3000, idade_max=50)
    modelo = bl.ajustar_b1(treino)
    assert isinstance(modelo, Pipeline)

    # Os nós da spline vêm do treino (idades até 50). Se fossem ajustados na validação
    # (idades até 120), o nó máximo passaria de 50.
    spline = modelo.named_steps["preprocessamento"].named_transformers_["idade"]
    # Os nós internos (sem os de extrapolação nas pontas, que o SplineTransformer acrescenta).
    nos_internos = spline.bsplines_[0].t[spline.degree:-spline.degree]
    assert nos_internos.max() <= 50 + 1e-9
    assert nos_internos.min() >= treino["idade_anos"].min() - 1e-9


def test_b1_sem_pesos_de_classe():
    logistica = bl.fazer_pipeline_b1().named_steps["logistica"]
    assert logistica.class_weight is None
    assert np.isinf(logistica.C)  # sem penalização (ver fazer_pipeline_b1)


def test_b1_recusa_treino_com_2024():
    df = _dados_sinteticos(np.random.default_rng(3), n=50).assign(ANO=2024)
    with pytest.raises(RuntimeError, match="R1"):
        bl.ajustar_b1(df)


# --- Métricas e dobras -------------------------------------------------------------------------

def test_metricas_probabilisticas_tem_as_quatro_medidas_mais_calibracao():
    y = np.array([0, 0, 1, 0, 1, 1, 0, 0])
    p = np.array([0.1, 0.2, 0.8, 0.3, 0.7, 0.9, 0.2, 0.1])
    m = bl.metricas_probabilisticas(y, p)
    assert set(m) == {"pr_auc", "roc_auc", "brier", "calibracao_slope", "calibracao_intercept"}
    assert m["pr_auc"] == pytest.approx(1.0)
    assert m["roc_auc"] == pytest.approx(1.0)


def test_slope_de_preditor_constante_e_nan():
    y = np.array([0, 1, 0, 0, 1, 0])
    m = bl.metricas_probabilisticas(y, np.full(6, 1 / 3))
    assert np.isnan(m["calibracao_slope"])
    assert np.isfinite(m["calibracao_intercept"])


def test_metricas_regra_sao_recall_precisao_e_f2_sem_pr_auc():
    y = np.array([1, 1, 0, 0, 0, 1])
    flag = np.array([1, 0, 1, 0, 0, 1], dtype=float)
    m = bl.metricas_regra(y, flag)
    assert set(m) == {"recall", "precisao", "f2"}
    # VP = 2, FP = 1, FN = 1: recall 2/3, precisão 2/3, F2 = 5·VP / (5·VP + 4·FN + FP)
    assert m["recall"] == pytest.approx(2 / 3)
    assert m["precisao"] == pytest.approx(2 / 3)
    assert m["f2"] == pytest.approx(10 / 15)


def test_avaliar_dobras_gera_metricas_por_dobra_e_oof():
    rng = np.random.default_rng(4)
    partes = []
    for regiao in ORDEM:
        d = _dados_sinteticos(rng, n=2000)
        d["regiao"] = regiao
        partes.append(d)
    df = pd.concat(partes, ignore_index=True)
    df["ANO"] = np.where(np.arange(len(df)) % 2 == 0, 2022, 2023).astype("int64")
    df = _com_papeis(df)

    cfg = {"ordem_dobras": ORDEM}
    res = bl.avaliar_dobras(cfg, df)

    assert set(res) == {"B0", "B1", "B2"}
    for nome in ("B0", "B1", "B2"):
        assert set(res[nome]["por_dobra"]) == set(ORDEM)
        assert len(res[nome]["oof_df"]) == len(df)  # cada caso aparece uma vez no OOF
    assert set(res["B0"]["por_dobra"]["Sul"]) == {
        "pr_auc", "roc_auc", "brier", "calibracao_slope", "calibracao_intercept"}
    assert set(res["B2"]["por_dobra"]["Sul"]) == {"recall", "precisao", "f2"}
    # Sinal forte de idade e diabetes: a logística supera a prevalência do treino.
    assert res["B1"]["oof"]["pr_auc"] > res["B0"]["oof"]["pr_auc"]


def test_avaliar_dobras_recusa_2024():
    df = _dados_sinteticos(np.random.default_rng(5), n=200).assign(ANO=2024)
    df["regiao"] = ORDEM[0]
    df = _com_papeis(df)
    with pytest.raises(RuntimeError, match="R1"):
        bl.avaliar_dobras({"ordem_dobras": ORDEM}, df)


# --- Dados sintéticos -----------------------------------------------------------------------

def _dados_sinteticos(rng, n: int, idade_max: float = 120.0) -> pd.DataFrame:
    """Casos com risco que sobe com a idade e com diabetes (prevalência ~15%); ANO 2022."""
    idade = rng.uniform(0, idade_max, size=n)
    diabetes = rng.random(n) < 0.2
    logit = -4.0 + 0.04 * idade + 1.2 * diabetes
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    linhas = []
    for i in range(n):
        linhas.append(caso(
            idade_anos=float(idade[i]), sexo="M" if i % 2 else "F",
            gestante=0, DIABETES="Sim" if diabetes[i] else "Não", y=int(y[i]), ANO=2022,
        ))
    return frame(linhas)


def _com_papeis(df: pd.DataFrame) -> pd.DataFrame:
    """Papéis de T-2.3 sintéticos: cada região é validação na própria dobra; o resto é treino."""
    out = df.copy()
    for regiao in ORDEM:
        papel = np.where(out["regiao"] == regiao, "validacao", "ajuste")
        out[f"papel_{regiao}"] = papel
    return out


# --- Relatório e MLflow (R7, T-2.5) -----------------------------------------------------------

def _cfg_tmp(tmp_path):
    from dengue_sinan.config import load_config
    base = load_config()
    dados = tmp_path / "data"
    dados.mkdir()
    return {**base, "ordem_dobras": ORDEM,
            "caminhos": {**base["caminhos"], "dados": str(dados),
                         "mlruns": str(tmp_path / "mlruns"),
                         "relatorios": str(tmp_path / "reports")}}


def _resultados_sinteticos(tmp_path):
    rng = np.random.default_rng(6)
    partes = []
    for regiao in ORDEM:
        d = _dados_sinteticos(rng, n=600)
        d["regiao"] = regiao
        partes.append(d)
    df = _com_papeis(pd.concat(partes, ignore_index=True))
    df["LINHA"] = np.arange(len(df), dtype="int64")
    cfg = _cfg_tmp(tmp_path)
    return cfg, bl.avaliar_dobras(cfg, df)


def test_relatorio_so_agregados_e_suprime_eventos_pequenos(tmp_path):
    cfg, resultados = _resultados_sinteticos(tmp_path)
    # Força uma dobra com menos de 10 eventos para checar a supressão (R7).
    oof = resultados["B0"]["oof_df"]
    no_norte = oof.index[oof["regiao"] == "Norte"]
    oof.loc[no_norte, "y"] = 0
    oof.loc[no_norte[:4], "y"] = 1  # 4 eventos na dobra Norte: abaixo de 10

    caminho = bl.escrever_relatorio(cfg, resultados, tmp_path / "baselines.md", "ab" * 32)
    texto = caminho.read_text(encoding="utf-8")
    assert "# Baselines B0, B1 e B2 (FR-04)" in texto
    assert "| Norte | <10 |" in texto
    assert "**OOF agrupado**" in texto
    assert "B2 é uma regra, não um modelo" in texto
    assert "| Dobra (validação) | Eventos | Recall | Precisão | F2 |" in texto
    # Nenhuma linha individual: a tabela tem uma linha por dobra e uma de OOF.
    assert texto.count("| Sudeste |") == 3  # uma em cada tabela (B0, B1, B2)


def test_registrar_mlflow_grava_tres_runs_e_eles_voltam(tmp_path):
    from mlflow.tracking import MlflowClient
    cfg, resultados = _resultados_sinteticos(tmp_path)
    ids = bl.registrar_mlflow(cfg, resultados)

    client = MlflowClient(tracking_uri=str(tmp_path / "mlruns"))
    experimento = client.get_experiment_by_name(bl.tracking.NOME_EXPERIMENTO)
    runs = client.search_runs([experimento.experiment_id])
    assert len(runs) == 3
    for nome in ("B0", "B1", "B2"):
        run = client.get_run(ids[nome])
        assert run.data.tags["baseline"] == nome
        assert run.info.status == "FINISHED"
        assert f"OOF/{'f2' if nome == 'B2' else 'pr_auc'}" in run.data.metrics
    # Slope por dobra de B0 é NaN (predição constante) e não vai ao MLflow; o OOF tem slope,
    # porque as prevalências de treino variam entre as dobras.
    assert "Sudeste/calibracao_slope" not in client.get_run(ids["B0"]).data.metrics
    assert "OOF/calibracao_slope" in client.get_run(ids["B0"]).data.metrics
    assert client.get_run(ids["B1"]).data.params["B1.penalizacao"] == "nenhuma (C=inf)"
