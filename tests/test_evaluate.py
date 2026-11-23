"""Testes da avaliação final (T-5.1, D-93) com dados sintéticos: nenhum microdado real.

O teste de 2024 é simulado com um DataFrame pequeno e modelos falsos que, como os wrappers reais,
chamam `guard.assert_dev_only` em `prever_proba`. Os esperados vêm de `esperado` nos testes, nunca
de `config/esperado.yaml`, que é o de 2024 real.
"""

import copy
import json
import logging
import os
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from dengue_sinan import artifacts, dataset, explain, guard, metrics, verify
from dengue_sinan import evaluate as ev
from dengue_sinan.config import load_config
from dengue_sinan.profiling import COMORBIDADES

REGIOES = ["Centro-Oeste", "Nordeste", "Norte", "Sudeste", "Sul"]
SELECAO_FALSA = {"conteudo": {"vencedor": "xgboost", "limiar_f2": 0.012},
                 "sha256": "a" * 64, "caminho": "selecao.json"}


def _sel_fonte(cfg: dict) -> dict:
    """`Fontes.selecao` dos testes: o selecao.json é sintético (nunca o do Drive)."""
    return SELECAO_FALSA


# --- Dados e modelos sintéticos --------------------------------------------------------------

def _df_sintetico(n: int = 3000, seed: int = 5, ano: int = 2024) -> pd.DataFrame:
    """Frame com as colunas que o M1, o B1, a regra B2 e o E1 leem (sem microdado real)."""
    rng = np.random.default_rng(seed)
    idade = rng.integers(0, 91, n).astype(float)
    sexo = rng.choice(["M", "F", "I"], n, p=[0.45, 0.5, 0.05])
    gestante = ((sexo == "F") & (rng.random(n) < 0.05)).astype("int8")
    df = pd.DataFrame({"ANO": np.int64(ano), "idade_anos": idade, "sexo": sexo,
                       "gestante": gestante})
    for c in COMORBIDADES:
        df[c] = rng.choice(["Sim", "Não", "Ausente"], n, p=[0.12, 0.83, 0.05])
    df["LACO"] = rng.choice(["Sim", "Não", "Ausente"], n, p=[0.05, 0.9, 0.05])
    df["PETEQUIA_N"] = rng.choice(["Sim", "Não", "Ausente"], n, p=[0.05, 0.9, 0.05])
    df["regiao"] = rng.choice(REGIOES, n)
    # Colunas que só os subgrupos leem (nunca são feature): sexo cru ("I" e em branco), raça/cor.
    df["CS_SEXO"] = np.where((sexo == "I") & (rng.random(n) < 0.5), "", sexo)
    df["CS_RACA"] = rng.choice(["1", "2", "3", "4", "5", "9", ""], n,
                               p=[0.3, 0.05, 0.02, 0.4, 0.03, 0.1, 0.1])
    escore = (-5.0 + 0.02 * (idade - 40) + 0.9 * (df["DIABETES"] == "Sim")
              + 0.7 * (df["HIPERTENSA"] == "Sim") + rng.standard_normal(n) * 0.6)
    df["y"] = (rng.random(n) < 1 / (1 + np.exp(-escore))).astype(np.int64)
    if df["y"].sum() < 30:  # garante eventos suficientes para as métricas
        df.loc[:29, "y"] = 1
    # Colunas que só a análise de erros lê (T-5.3). Sorteadas com um gerador à parte: os dados
    # acima (e os testes que dependem deles) não mudam.
    extra = np.random.default_rng(seed + 1000)
    df["n_comorbidades"] = sum((df[c] == "Sim").astype("int8") for c in COMORBIDADES)
    df["dias_ate_notificacao"] = extra.integers(0, 20, n).astype(float)
    df.loc[extra.random(n) < 0.02, "dias_ate_notificacao"] = np.nan  # data ausente
    ufs = {"Sudeste": ["31", "32", "33", "35"], "Sul": ["41", "42", "43"],
           "Centro-Oeste": ["50", "51", "52", "53"], "Nordeste": ["21", "26", "29"],
           "Norte": ["11", "13", "15"]}
    uf = np.array([ufs[r][k] for r, k in zip(df["regiao"], extra.integers(0, 3, n), strict=True)])
    df["SG_UF"] = uf
    df["ID_MN_RESI"] = np.char.add(uf, extra.integers(1000, 9999, n).astype(str))
    return df


def _esperado_de(df: pd.DataFrame) -> dict:
    eventos = df.loc[df["y"] == 1, "regiao"].value_counts()
    return {"populacao_total": int(len(df)), "eventos_total": int(df["y"].sum()),
            "eventos_por_regiao": {r: int(eventos.get(r, 0)) for r in REGIOES},
            "bootstrap": {"metricas": 20, "calibracao": 2000}}


class FakeM1:
    """Imita ModeloFinal: `prever_proba` chama o guard como o wrapper real (R1)."""

    def __init__(self, p: np.ndarray, limiar: float, nome: str = "xgboost") -> None:
        self._p = p
        self.limiar = limiar
        self.nome = nome

    def prever_proba(self, df: pd.DataFrame) -> np.ndarray:
        guard.assert_dev_only(df)
        return self._p[df.index.to_numpy()]


class FakeBase:
    """Imita B0Final e B1Final: `predizer` devolve a probabilidade bruta e tem `limiar`."""

    def __init__(self, p: np.ndarray, limiar: float) -> None:
        self._p = p
        self.limiar = limiar

    def predizer(self, df: pd.DataFrame) -> np.ndarray:
        return self._p[df.index.to_numpy()]


def _e1_sintetico(df: pd.DataFrame, seed: int = 1) -> artifacts.E1Leve:
    idade = df["idade_anos"].to_numpy(dtype=float)
    nos = {"idade": explain._nos(idade, explain.GL_IDADE),
           "idade_interacao": explain._nos(idade, explain.GL_IDADE_INTERACAO)}
    X = explain.matriz_de_desenho(df, nos, [])
    colunas = list(X.columns)
    rng = np.random.default_rng(seed)
    k = len(colunas)
    desvio = np.maximum(X.std(axis=0).to_numpy(), 0.2)  # piso: indicador raro não vira coef. enorme
    # Cada termo varia ~0,2 no logit: o risco muda entre os casos (sem isso a calibração não tem
    # variação para ajustar). O intercepto é fixado para a prevalência ficar baixa.
    params = rng.normal(0, 1, k) * 0.2 / desvio
    params[colunas.index("Intercepto")] = -5.0
    return artifacts.E1Leve(params=params, cov=np.eye(k) * 0.01,
                            colunas=colunas, nos=nos, pares_incluidos=[], pares_excluidos=[],
                            idade_referencia=explain.IDADE_REFERENCIA,
                            features=list(explain.CHAVES_PADRAO))


def _modelos(df: pd.DataFrame) -> ev.Modelos:
    rng = np.random.default_rng(9)
    base = 1 / (1 + np.exp(-(-5.0 + 0.9 * df["y"].to_numpy() + rng.standard_normal(len(df)))))
    p_m1 = np.clip(base, 1e-6, 1 - 1e-6)
    p_b1 = np.clip(0.6 * base + 0.2 * rng.random(len(df)), 1e-6, 1 - 1e-6)
    return ev.Modelos(
        m1=FakeM1(p_m1, limiar=float(np.quantile(p_m1, 0.8))),
        baselines=type("B", (), {"b0": FakeBase(np.full(len(df), df["y"].mean()), 0.5),
                                 "b1": FakeBase(p_b1, float(np.quantile(p_b1, 0.8)))})(),
        e1=_e1_sintetico(df),
        payloads={},
    )


def _fontes(df: pd.DataFrame, modelos: ev.Modelos | None = None) -> ev.Fontes:
    modelos = modelos if modelos is not None else _modelos(df)
    return ev.Fontes(populacao=lambda cfg: df.copy(), hash_dados=lambda cfg: {"ano": 2024},
                     modelos=lambda cfg: modelos, features=lambda d: d, selecao=_sel_fonte)


@pytest.fixture
def cfg(tmp_path) -> dict:
    base = load_config()
    return {**copy.deepcopy(base),
            "caminhos": {**base["caminhos"], "dados": str(tmp_path / "data"),
                         "relatorios": str(tmp_path / "reports"),
                         "modelos": str(tmp_path / "models")},
            "bootstrap": {"metricas": 20, "calibracao": 2000, "processos": 1}}


@pytest.fixture
def df():
    return _df_sintetico()


@pytest.fixture
def esperado(df, monkeypatch):
    esp = _esperado_de(df)
    monkeypatch.setattr(ev, "_ler_esperado_teste", lambda caminho=None: esp)
    return esp


# --- Guarda e carga do teste -----------------------------------------------------------------

def test_predizer_dentro_do_teste_aceita_so_2024(df):
    predicoes = ev.predizer(_modelos(df), df, dentro_do_teste=True)
    assert len(predicoes.probabilidades["M1"]) == len(df)


def test_predizer_dentro_do_teste_recusa_2022_e_mistura(df):
    misturado = pd.concat([df, _df_sintetico(n=10, ano=2022)], ignore_index=True)
    with pytest.raises(RuntimeError, match="só entram linhas de 2024"):
        ev.predizer(_modelos(misturado), misturado, dentro_do_teste=True)


def test_predizer_fora_do_teste_continua_recusando_2024(df):
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        ev.predizer(_modelos(df), df, dentro_do_teste=False)


def test_leitura_do_teste_so_vale_dentro_do_bloco(df):
    with guard.leitura_do_teste():
        guard.assert_dev_only(df)
    with pytest.raises(RuntimeError):
        guard.assert_dev_only(df)


def test_populacao_com_2022_e_recusada_antes_de_abrir_arquivo(cfg, monkeypatch):
    def nao_deve_abrir(*args, **kwargs):
        raise AssertionError("abriu arquivo")

    monkeypatch.setattr(dataset, "parquet_path", nao_deve_abrir)
    with guard.leitura_do_teste(), pytest.raises(
            RuntimeError, match="teste=True só carrega o ano de teste"):
        dataset.load_population(cfg, [2022], teste=True)


# --- População: conferência antes de qualquer cálculo ----------------------------------------

def test_conferir_populacao_bate_e_devolve_totais(df):
    totais = ev.conferir_populacao(df, _esperado_de(df))
    assert totais["casos"] == len(df)
    assert totais["eventos"] == int(df["y"].sum())


def test_conferir_populacao_recusa_casos_divergentes(df):
    esp = _esperado_de(df)
    esp["populacao_total"] += 1
    with pytest.raises(ValueError, match="casos"):
        ev.conferir_populacao(df, esp)


def test_conferir_populacao_recusa_regiao_divergente(df):
    esp = _esperado_de(df)
    esp["eventos_por_regiao"]["Norte"] += 1
    with pytest.raises(ValueError, match="eventos em Norte"):
        ev.conferir_populacao(df, esp)


def test_esperado_de_2024_tem_os_numeros_do_data_model():
    esp = ev._ler_esperado_teste()
    assert esp["populacao_total"] == 5_331_745
    assert esp["eventos_total"] == 11_338
    assert sum(esp["eventos_por_regiao"].values()) == 11_338
    assert esp["bootstrap"] == {"metricas": 1000, "calibracao": 2000}


def test_hash_do_parquet_diferente_do_manifesto_aborta(cfg):
    dados = Path(cfg["caminhos"]["dados"])
    dados.mkdir(parents=True)
    (dados / "parquet").mkdir()
    dataset.parquet_path(cfg, 2024).write_bytes(b"dado de teste")
    (dados / "manifest.json").write_text(json.dumps(
        {"2024": {"sha256_dbc": "a" * 64, "sha256_parquet": "0" * 64}}), encoding="utf-8")
    with pytest.raises(ValueError, match="diferente do manifesto"):
        ev._hash_dados_do_teste(cfg)


# --- Avaliação única: lacre, ordem de gravação, queda, aborto --------------------------------

def test_avaliacao_grava_resultados_e_lacre_por_ultimo(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    assert (pasta / "metricas.md").exists() and (pasta / "metricas.json").exists()
    lacre = json.loads((pasta / "LACRE.json").read_text(encoding="utf-8"))
    assert execucao.ordem[:3] == ["calculo_concluido", "gravado:metricas.md",
                                  "gravado:metricas.json"]
    assert execucao.ordem[-1] == "gravado:LACRE.json"
    assert execucao.ordem[3:5] == ["gravado:criterios.md", "gravado:erros.md"]  # T-5.3 e T-5.4
    assert all(e.startswith("gravado:") and e.endswith(".csv") for e in execucao.ordem[5:-1])
    assert lacre["relatorios"]["metricas.md"] == ev._sha256_texto(
        (pasta / "metricas.md").read_text(encoding="utf-8"))
    assert lacre["semente"] == cfg["seed"]
    assert lacre["commit"] and "hash_config" in lacre and "artefatos" in lacre


def test_segunda_avaliacao_levanta_erro_e_nao_mexe_no_lacre(cfg, df, esperado):
    ev.evaluate_test_once(cfg, fontes=_fontes(df))
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    antes = (pasta / "LACRE.json").read_text(encoding="utf-8")
    with pytest.raises(RuntimeError, match="teste já avaliado \\(R2\\)"):
        ev.evaluate_test_once(cfg, fontes=_fontes(df))
    assert (pasta / "LACRE.json").read_text(encoding="utf-8") == antes


def test_lacre_existente_recusa_antes_de_ler_qualquer_dado(cfg, df, esperado):
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    pasta.mkdir(parents=True)
    (pasta / "LACRE.json").write_text("{}", encoding="utf-8")

    def populacao_nao_deve_ser_lida(cfg):
        raise AssertionError("leu dados com lacre existente")

    fontes = ev.Fontes(populacao=populacao_nao_deve_ser_lida, hash_dados=lambda c: {},
                       modelos=lambda c: _modelos(df), features=lambda d: d, selecao=_sel_fonte)
    with pytest.raises(RuntimeError, match="teste já avaliado"):
        ev.evaluate_test_once(cfg, fontes=fontes)


def test_queda_entre_gravacoes_nao_deixa_lacre_e_permite_nova_execucao(cfg, df, esperado,
                                                                        monkeypatch):
    original = ev._gravar_atomico

    def cai_ao_gravar_json(caminho, texto):
        if caminho.name == ev.ARQ_JSON:
            raise OSError("queda simulada entre as gravações")
        original(caminho, texto)

    monkeypatch.setattr(ev, "_gravar_atomico", cai_ao_gravar_json)
    with pytest.raises(OSError, match="queda simulada"):
        ev.evaluate_test_once(cfg, fontes=_fontes(df))
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    assert not (pasta / "LACRE.json").exists()  # sem lacre: nova execução é permitida
    monkeypatch.setattr(ev, "_gravar_atomico", original)
    ev.evaluate_test_once(cfg, fontes=_fontes(df))
    assert (pasta / "LACRE.json").exists()


def test_populacao_divergente_aborta_sem_gravar_nada(cfg, df, esperado):
    esperado["populacao_total"] += 1
    with pytest.raises(ValueError, match="diverge de config/esperado.yaml"):
        ev.evaluate_test_once(cfg, fontes=_fontes(df))
    assert not (Path(cfg["caminhos"]["relatorios"]) / "teste").exists()


def test_linhas_de_outro_ano_abortam_sem_gravar_nada(cfg, df, esperado):
    misturado = pd.concat([df, _df_sintetico(n=5, ano=2023)], ignore_index=True)
    esperado["populacao_total"] = len(misturado)
    esperado["eventos_total"] = int(misturado["y"].sum())
    esperado["eventos_por_regiao"] = _esperado_de(misturado)["eventos_por_regiao"]
    with pytest.raises(RuntimeError, match="outro ano"):
        ev.evaluate_test_once(cfg, fontes=_fontes(misturado, _modelos(df)))
    assert not (Path(cfg["caminhos"]["relatorios"]) / "teste" / "LACRE.json").exists()


def test_nada_e_impresso_durante_a_avaliacao(cfg, df, esperado, capsys):
    ev.evaluate_test_once(cfg, fontes=_fontes(df))
    saida = capsys.readouterr()
    assert saida.out == "" and saida.err == ""


def test_avisos_fr03_sao_capturados_e_suprimidos_nao_impressos(capsys):
    with ev._capturar_avisos() as avisos:
        logging.getLogger("dengue_sinan.dataset").warning(
            "alerta FR-03 (%s): %s", 2024, {"alerta": "DT_SIN_PRI > DT_NOTIFIC", "linhas": 3})
        logging.getLogger("dengue_sinan.dataset").warning(
            "alerta FR-03 (%s): %s", 2024, {"alerta": "gestante com sexo M", "linhas": 40})
    assert avisos.alertas == [
        {"ano": 2024, "alerta": "DT_SIN_PRI > DT_NOTIFIC", "valor": "<10"},
        {"ano": 2024, "alerta": "gestante com sexo M", "valor": 40},
    ]
    assert capsys.readouterr().err == ""


# --- Semente de ponta a ponta (R8), ambiente antes da carga, porta, queda na gravação -------

def _cfg_em(cfg: dict, pasta: Path, seed: int | None = None) -> dict:
    novo = copy.deepcopy(cfg)
    novo["caminhos"]["relatorios"] = str(pasta)
    if seed is not None:
        novo["seed"] = seed
    return novo


def _json_do_teste(cfg: dict) -> dict:
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    return json.loads((pasta / "metricas.json").read_text(encoding="utf-8"))


def test_semente_do_config_vai_ate_o_json_e_define_os_ics(cfg, df, esperado, tmp_path):
    # R8 de ponta a ponta: um `seed=42` fixo dentro de _calcular não pode passar.
    resultados = {}
    for nome, seed in (("a1", 111), ("a2", 111), ("b", 222)):
        c = _cfg_em(cfg, tmp_path / nome, seed)
        ev.evaluate_test_once(c, fontes=_fontes(df))
        resultados[nome] = _json_do_teste(c)["analises"]["metricas"]
        lacre = json.loads((Path(c["caminhos"]["relatorios"]) / "teste" / "LACRE.json")
                           .read_text(encoding="utf-8"))
        assert lacre["semente"] == seed
        assert resultados[nome]["semente"] == seed  # (a) a semente do JSON é a do config
    assert resultados["a1"] == resultados["a2"]  # (b) mesma semente: mesmos ICs
    assert (resultados["a1"]["modelos"]["M1"]["pr_auc"]["ic95"]
            != resultados["b"]["modelos"]["M1"]["pr_auc"]["ic95"])  # outra semente: outros ICs
    assert resultados["a1"]["diferencas_pr_auc"] != resultados["b"]["diferencas_pr_auc"]


@pytest.mark.parametrize("outro", ["B0", "B1"])
def test_ic_da_diferenca_e_a_diferenca_das_distribuicoes_com_os_mesmos_sorteios(df, outro):
    # SC-01/SC-04: o IC de M1 − B é o dos quantis de dist[M1] − dist[B], reamostra a reamostra, e
    # cada dist[modelo][k] é a métrica da MESMA reamostra k (mesma sub-semente, mesmo sorteio).
    pred = ev.predizer(_modelos(df), df, dentro_do_teste=True)
    y = df["y"].to_numpy()
    n, seed = 12, 17
    res = ev.calcular_metricas(y, pred, seed=seed, n=n, processos=1)
    dist = res.distribuicoes
    dif = dist["M1/pr_auc"] - dist[f"{outro}/pr_auc"]
    ic = res.json["diferencas_pr_auc"][f"M1_menos_{outro}"]["ic95"]
    assert ic == pytest.approx(list(np.quantile(dif, ev.QUANTIS_IC)), abs=1e-12)
    celulas = metrics.agrupar_celulas(y, {m: pred.probabilidades[m] for m in ev.PROBABILISTICOS})
    sorteio = metrics.Sorteio(celulas.contagem, celulas.n_negativas)
    for k, semente in enumerate(metrics.sementes_das_reamostras(seed, n)):
        w = sorteio(metrics.fluxo(semente, 0))
        linhas = np.repeat(np.arange(len(celulas)), w.astype(int))
        y_rep = celulas.y[linhas]
        for nome in ("M1", outro):
            esperado_k = metrics.pr_auc(y_rep, celulas.colunas[nome][linhas])
            assert dist[f"{nome}/pr_auc"][k] == pytest.approx(esperado_k, abs=1e-12), (nome, k)


def test_ambiente_errado_aborta_antes_de_ler_2024_e_sem_gravar_nada(cfg, df, esperado):
    lido = []

    def populacao(c):
        lido.append(1)
        return df.copy()

    def ambiente_errado(c):
        return [verify.check("gpu", "T4", "sem GPU"), verify.check("ram_gib", 50, 50)]

    fontes = ev.Fontes(populacao=populacao, hash_dados=lambda c: {}, modelos=lambda c: _modelos(df),
                       features=lambda d: d, selecao=_sel_fonte, ambiente=ambiente_errado)
    with pytest.raises(RuntimeError, match=r"ambiente fora do exigido.*gpu"):
        ev.evaluate_test_once(cfg, fontes=fontes)
    assert lido == []  # nenhum dado de 2024 foi lido
    assert not (Path(cfg["caminhos"]["relatorios"]) / "teste").exists()  # nem relatório nem lacre


def test_ambiente_certo_e_registrado_no_relatorio_de_verificacao(cfg, df, esperado):
    ambiente = [verify.check("gpu", "T4", "T4"), verify.check("ram_gib", 50, 50)]
    fontes = ev.Fontes(populacao=lambda c: df.copy(), hash_dados=lambda c: {},
                       modelos=lambda c: _modelos(df), features=lambda d: d, selecao=_sel_fonte,
                       ambiente=lambda c: ambiente)
    execucao = ev.evaluate_test_once(cfg, fontes=fontes)
    checks = ev.checks_teste(cfg, execucao, esperado, ambiente=execucao.ambiente)
    assert [c["nome"] for c in checks if c["nome"] in ("gpu", "ram_gib")] == ["gpu", "ram_gib"]


def test_fonte_real_do_teste_confere_o_ambiente_com_verify_environment():
    assert ev.FONTES_TESTE.ambiente is verify.environment


def test_carga_de_2024_roda_com_a_porta_aberta_e_fecha_depois(cfg, df, esperado):
    vistos = []

    def populacao(c):
        vistos.append(guard.leitura_do_teste_aberta())
        return df.copy()

    fontes = ev.Fontes(populacao=populacao, hash_dados=lambda c: {}, modelos=lambda c: _modelos(df),
                       features=lambda d: d, selecao=_sel_fonte)
    ev.evaluate_test_once(cfg, fontes=fontes)
    assert vistos == [True]
    assert not guard.leitura_do_teste_aberta()


@pytest.mark.parametrize("falha_em", [ev.ARQ_MARKDOWN, ev.ARQ_JSON, ev.ARQ_LACRE])
def test_queda_na_gravacao_remove_o_que_esta_execucao_gravou(cfg, df, esperado, monkeypatch,
                                                              falha_em):
    original = ev._gravar_atomico

    def falha(caminho, texto):
        if caminho.name == falha_em:
            raise OSError("queda simulada")
        original(caminho, texto)

    monkeypatch.setattr(ev, "_gravar_atomico", falha)
    with pytest.raises(OSError, match="queda simulada"):
        ev.evaluate_test_once(cfg, fontes=_fontes(df))
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    assert not pasta.exists() or list(pasta.iterdir()) == []  # sem parciais, sem lacre
    monkeypatch.setattr(ev, "_gravar_atomico", original)
    ev.evaluate_test_once(cfg, fontes=_fontes(df))  # nova execução é permitida
    assert (pasta / ev.ARQ_LACRE).exists()


def test_limpeza_da_queda_nunca_apaga_um_lacre_existente(cfg, tmp_path, monkeypatch):
    from types import SimpleNamespace

    pasta = tmp_path / "teste"
    pasta.mkdir()
    (pasta / ev.ARQ_LACRE).write_text("lacre de outra execução", encoding="utf-8")
    original = ev._gravar_atomico

    def falha(caminho, texto):
        if caminho.name == ev.ARQ_JSON:
            raise OSError("queda")
        original(caminho, texto)

    monkeypatch.setattr(ev, "_gravar_atomico", falha)
    execucao = SimpleNamespace(markdown="md", json_texto="{}", ordem=[], commit="c",
                               arvore_limpa=True, payloads={}, casos=1, eventos=1, n_metricas=1,
                               tabelas_csv={}, arquivos_md={}, selecao=None)
    with pytest.raises(OSError):
        ev._escrever_teste(cfg, execucao, pasta, {"eventos_por_regiao": {}}, {})
    assert (pasta / ev.ARQ_LACRE).read_text(encoding="utf-8") == "lacre de outra execução"
    assert not (pasta / ev.ARQ_MARKDOWN).exists()  # o que ESTA execução gravou foi removido


def test_gravar_atomico_nao_deixa_temporario_quando_falha(tmp_path, monkeypatch):
    def falha(origem, destino):
        raise OSError("troca falhou")

    monkeypatch.setattr(os, "replace", falha)
    with pytest.raises(OSError, match="troca falhou"):
        ev._gravar_atomico(tmp_path / "x.json", "texto")
    assert list(tmp_path.iterdir()) == []


# --- Ensaio ----------------------------------------------------------------------------------

def test_ensaio_grava_so_em_ensaio_e_nao_cria_lacre(cfg):
    dev = _df_sintetico(n=2000, ano=2022)
    dev2 = _df_sintetico(n=1500, seed=8, ano=2023)
    dev = pd.concat([dev, dev2], ignore_index=True)
    modelos = _modelos(dev)
    fontes = ev.Fontes(populacao=lambda c: dev.copy(), hash_dados=lambda c: {},
                       modelos=lambda c: modelos, features=lambda d: d, selecao=_sel_fonte)
    ev.ensaiar_em_desenvolvimento(cfg, fontes=fontes)
    base = Path(cfg["caminhos"]["relatorios"])
    assert not (base / "teste").exists()
    md = (base / "ensaio" / "metricas.md").read_text(encoding="utf-8")
    js = json.loads((base / "ensaio" / "metricas.json").read_text(encoding="utf-8"))
    assert "ENSAIO, não é avaliação" in md
    assert js["aviso"].startswith("ENSAIO, não é avaliação")
    assert js["modo"] == "ensaio"


def test_ensaio_recusa_2024_no_conjunto(cfg):
    misturado = pd.concat([_df_sintetico(n=500, ano=2022), _df_sintetico(n=100, ano=2024)],
                          ignore_index=True)
    modelos = _modelos(misturado)
    fontes = ev.Fontes(populacao=lambda c: misturado.copy(), hash_dados=lambda c: {},
                       modelos=lambda c: modelos, features=lambda d: d, selecao=_sel_fonte)
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        ev.ensaiar_em_desenvolvimento(cfg, fontes=fontes)
    assert not (Path(cfg["caminhos"]["relatorios"]) / "ensaio").exists()


def test_ensaio_le_so_2022_2023_e_nao_grava_fluxograma(cfg, monkeypatch):
    chamadas = []
    dev = pd.concat([_df_sintetico(n=300, ano=2022), _df_sintetico(n=200, seed=2, ano=2023)],
                    ignore_index=True)

    def falso_fluxo(cfg_, anos, **kwargs):
        chamadas.append(list(anos))
        return dev.copy(), None, None

    def load_population_nao_deve_ser_usado(*args, **kwargs):
        raise AssertionError("o ensaio não pode gravar o fluxograma (load_population)")

    monkeypatch.setattr(dataset, "load_population_with_flow", falso_fluxo)
    monkeypatch.setattr(dataset, "load_population", load_population_nao_deve_ser_usado)
    fontes = ev.Fontes(populacao=ev._populacao_dev, hash_dados=lambda c: {},
                       modelos=lambda c: _modelos(dev), features=lambda d: d, selecao=_sel_fonte)
    ev.ensaiar_em_desenvolvimento(cfg, fontes=fontes)
    assert chamadas == [[2022, 2023]]


# --- Análises: ponto de extensão -------------------------------------------------------------

def _analise_de_brinquedo(recebidos: dict):
    def executar(ctx: ev.Contexto) -> ev.Saida:
        recebidos["n"] = len(ctx.df)
        recebidos["y"] = ctx.y.copy()
        recebidos["modelos"] = sorted(ctx.predicoes.probabilidades)
        tabela = pd.DataFrame({"categoria": ["a", "b"], "casos": [40, 60]})
        return ev.Saida(tabelas={"toy": tabela}, markdown="## Brinquedo\n\nOK.\n",
                        json={"total": 100})
    return ev.Analise("brinquedo", executar)


def test_analise_de_brinquedo_recebe_contexto_e_entra_no_json(cfg, df, esperado):
    recebidos: dict = {}
    execucao = ev.evaluate_test_once(
        cfg, fontes=_fontes(df),
        analises=[*ev.ANALISES_PADRAO, _analise_de_brinquedo(recebidos)])
    assert recebidos["n"] == len(df)
    assert np.array_equal(recebidos["y"], df["y"].to_numpy())
    assert recebidos["modelos"] == ["B0", "B1", "E1", "M1"]
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    js = json.loads((pasta / "metricas.json").read_text(encoding="utf-8"))
    assert js["analises"]["brinquedo"] == {"total": 100}
    assert "## Brinquedo" in (pasta / "metricas.md").read_text(encoding="utf-8")
    assert execucao.ordem[-1] == "gravado:LACRE.json"


def test_analise_com_tabela_acima_do_limite_e_recusada(df):
    def gigante(ctx):
        return ev.Saida(tabelas={"x": pd.DataFrame({"a": range(ev.LIMITE_LINHAS_TABELA + 1)})},
                        markdown="", json={})

    with pytest.raises(ValueError, match="agregado tem no máximo"):
        ev.executar_analises(_contexto(df), [ev.Analise("gigante", gigante)])


def test_analise_que_nao_devolve_saida_e_recusada(df):
    with pytest.raises(TypeError, match="não Saida"):
        ev.executar_analises(_contexto(df), [ev.Analise("ruim", lambda ctx: {"x": 1})])


def test_analise_com_nome_repetido_e_recusada(df):
    analise = ev.Analise("dup", lambda ctx: ev.Saida({}, "", {}))
    with pytest.raises(ValueError, match="análise repetida"):
        ev.executar_analises(_contexto(df), [analise, analise])


def _contexto(df: pd.DataFrame) -> ev.Contexto:
    modelos = _modelos(df)
    predicoes = ev.predizer(modelos, df, dentro_do_teste=True)
    return ev.Contexto(cfg=load_config(), modo="teste", y=df["y"].to_numpy(),
                       predicoes=predicoes, df=df, seed=1, n_metricas=5)


# --- Métricas: semente, pareamento, casos especiais, R7 -------------------------------------

def test_mesma_semente_reproduz_os_ics_e_outra_semente_muda(df):
    p = _modelos(df)
    pred = ev.predizer(p, df, dentro_do_teste=True)
    a = ev.calcular_metricas(df["y"], pred, seed=20261103, n=30, processos=1).json
    b = ev.calcular_metricas(df["y"], pred, seed=20261103, n=30, processos=1).json
    c = ev.calcular_metricas(df["y"], pred, seed=7, n=30, processos=1).json
    assert a == b
    assert a["modelos"]["M1"]["pr_auc"]["ic95"] != c["modelos"]["M1"]["pr_auc"]["ic95"]


def _estado(df: pd.DataFrame):
    """Estado do bootstrap (como em calcular_metricas) e os dados agrupados em células."""
    pred = ev.predizer(_modelos(df), df, dentro_do_teste=True)
    y = df["y"].to_numpy()
    estado, grandes, meta = ev._montar(y, pred)
    estado.pontos()
    celulas = metrics.agrupar_celulas(y, {n: pred.probabilidades[n] for n in ev.PROBABILISTICOS})
    return y, pred, estado, grandes, meta, celulas


@pytest.mark.parametrize("k", [0, 1])
def test_reamostra_bate_com_o_sklearn_nas_linhas_repetidas_do_mesmo_sorteio(df, k):
    # O sorteio de uma reamostra, expandido em linhas, dá as métricas do sklearn/statsmodels. Os
    # modelos usam o MESMO sorteio (D-53): a diferença pareada é a das mesmas linhas.
    y, pred, estado, _, _, celulas = _estado(df)
    semente = metrics.sementes_das_reamostras(3, 2)[k]
    valores, _ = estado.reamostra(semente)
    w = metrics.Sorteio(celulas.contagem, celulas.n_negativas)(metrics.fluxo(semente, 0))
    linhas = np.repeat(np.arange(len(celulas)), w.astype(int))
    y_rep = celulas.y[linhas]
    for nome in ("M1", "B1", "E1"):
        p_rep = celulas.colunas[nome][linhas]
        slope, intercepto = metrics.calibration_slope_intercept(y_rep, p_rep)
        assert valores[f"{nome}/pr_auc"] == pytest.approx(metrics.pr_auc(y_rep, p_rep), abs=1e-12)
        assert valores[f"{nome}/roc_auc"] == pytest.approx(metrics.roc_auc(y_rep, p_rep), abs=1e-12)
        assert valores[f"{nome}/brier"] == pytest.approx(metrics.brier(y_rep, p_rep), abs=1e-12)
        assert valores[f"{nome}/slope"] == pytest.approx(slope, rel=1e-5)
        assert valores[f"{nome}/intercepto"] == pytest.approx(intercepto, rel=1e-5, abs=1e-7)
    diferenca = valores["M1/pr_auc"] - valores["B1/pr_auc"]
    assert diferenca == pytest.approx(
        metrics.pr_auc(y_rep, celulas.colunas["M1"][linhas])
        - metrics.pr_auc(y_rep, celulas.colunas["B1"][linhas]), abs=1e-12)
    # B0 é constante: slope não definido; intercepto = logit(prevalência) − logit(p0) na reamostra.
    prevalencia = y_rep.mean()
    p0 = float(celulas.colunas["B0"][0])
    esperado = np.log(prevalencia / (1 - prevalencia)) - np.log(p0 / (1 - p0))
    assert "B0/slope" not in valores
    assert valores["B0/intercepto"] == pytest.approx(esperado, abs=1e-7)
    assert valores["B0/pr_auc"] == pytest.approx(prevalencia, abs=1e-12)


def test_reamostra_dos_limiares_bate_com_threshold_metrics_nas_linhas_repetidas(df):
    y, pred, estado, _, meta, _ = _estado(df)
    semente = metrics.sementes_das_reamostras(4, 1)[0]
    valores, _ = estado.reamostra(semente)
    marcados = {n: pred.probabilidades[n] >= pred.limiares[n] for n in ev.COM_LIMIAR}
    marcados[ev.NOME_B2] = pred.b2
    lim = metrics.agrupar_celulas(y, marcados)
    wl = metrics.Sorteio(lim.contagem, lim.n_negativas)(metrics.fluxo(semente, 1))
    linhas = np.repeat(np.arange(len(lim)), wl.astype(int))
    for nome in marcados:
        ref = metrics.threshold_metrics(lim.y[linhas], lim.colunas[nome][linhas].astype(float), 0.5)
        for k in ev.METRICAS_NO_LIMIAR:
            assert valores[f"{nome}/limiar_{k}"] == pytest.approx(ref[k], abs=1e-12), (nome, k)
    assert len(lim) <= 2 * 2 ** len(marcados)  # O(#células): no máximo 2 × 2^k


def test_reamostras_dependem_so_da_sub_semente_nao_do_bloco_nem_de_n(df):
    _, _, estado, _, _, _ = _estado(df)
    sementes = metrics.sementes_das_reamostras(11, 6)
    todas, _ = estado.bloco(sementes)
    primeiras, _ = estado.bloco(sementes[:2])
    ultima, _ = estado.bloco(sementes[5:])
    mais, _ = estado.bloco(metrics.sementes_das_reamostras(11, 60)[:6])
    for chave in todas:
        assert np.array_equal(todas[chave][:2], primeiras[chave])
        assert np.array_equal(todas[chave][5:], ultima[chave])
        assert np.array_equal(todas[chave], mais[chave])


def test_resultado_nao_muda_com_o_numero_de_processos_e_registra_quantos_foram(df):
    pred = ev.predizer(_modelos(df), df, dentro_do_teste=True)
    y = df["y"]
    um = ev.calcular_metricas(y, pred, seed=5, n=9, processos=1)
    dois = ev.calcular_metricas(y, pred, seed=5, n=9, processos=2)
    tres = ev.calcular_metricas(y, pred, seed=5, n=9, processos=3)
    assert um.json == dois.json == tres.json
    assert (um.processos, dois.processos, tres.processos) == (1, 2, 3)
    assert um.iteracoes_maximas == dois.iteracoes_maximas == tres.iteracoes_maximas


def test_reamostras_em_varios_processos_saem_na_mesma_ordem_e_com_os_mesmos_numeros(df):
    # O IC (quantis) não vê a ordem das reamostras: compara os arrays, reamostra a reamostra.
    pred = ev.predizer(_modelos(df), df, dentro_do_teste=True)
    y = df["y"].to_numpy()
    sementes = metrics.sementes_das_reamostras(9, 7)
    resultados = []
    for processos in (1, 2):
        estado, grandes, meta = ev._montar(y, pred)
        estado.pontos()
        resultados.append(metrics.rodar_reamostras(estado, grandes, meta, sementes, processos))
    (um, iteracoes_um), (dois, iteracoes_dois) = resultados
    assert um.keys() == dois.keys() and len(um["M1/pr_auc"]) == 7
    for chave in um:
        assert np.array_equal(um[chave], dois[chave]), chave
    assert iteracoes_um == iteracoes_dois


def test_processos_efetivos_usa_os_nucleos_por_padrao_e_nunca_passa_de_n():
    assert ev._processos_efetivos(None, 10_000) == (os.cpu_count() or 1)
    assert ev._processos_efetivos(99, 3) == 3
    assert ev._processos_efetivos(0, 5) == 1
    assert ev._processos_efetivos(2, 5) == 2


def test_execucao_registra_os_processos_do_config_e_o_check_os_lista(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    assert execucao.processos == 1
    nomes = {c["nome"]: c for c in ev.checks_teste(cfg, execucao, esperado, ambiente=[])}
    assert nomes["processos_bootstrap"]["obtido"] == 1


@pytest.mark.skipif(os.environ.get("DENGUE_TESTES_LENTOS") != "1",
                    reason="escala de 5,3 milhões de linhas: só com DENGUE_TESTES_LENTOS=1")
def test_escala_5_milhoes_com_1_e_2_processos_da_o_mesmo_resultado():
    import time

    n, eventos = 5_331_745, 11_338
    rng = np.random.default_rng(20261103)
    y = np.zeros(n, dtype=np.int64)
    y[rng.choice(n, eventos, replace=False)] = 1
    base = np.log(eventos / (n - eventos))

    def escore(forca):
        return np.clip(1 / (1 + np.exp(-(base + 0.9 * rng.standard_normal(n) + forca * y))),
                       1e-9, 1 - 1e-9)

    m1, b1, e1 = escore(1.0), escore(0.5), escore(0.3)
    pred = ev.Predicoes(
        probabilidades={"M1": m1, "B1": b1, "E1": e1, "B0": np.full(n, eventos / n)},
        b2=rng.random(n) < 0.12,
        limiares={"M1": float(np.quantile(m1, 0.97)), "B0": 0.5,
                  "B1": float(np.quantile(b1, 0.97))})
    tempos = {}
    resultados = {}
    for processos in (1, 2):
        inicio = time.perf_counter()
        resultados[processos] = ev.calcular_metricas(y, pred, seed=1, n=4, processos=processos)
        tempos[processos] = time.perf_counter() - inicio
    print(f"tempo total de 4 reamostras (inclui o preparo): {tempos}")
    assert resultados[1].json == resultados[2].json


def test_b0_nao_tem_slope_e_b2_so_tem_limiar(df):
    pred = ev.predizer(_modelos(df), df, dentro_do_teste=True)
    res = ev.calcular_metricas(df["y"], pred, seed=3, n=10, processos=1).json
    assert res["modelos"]["B0"]["slope"] is None
    assert "no_limiar" in res["modelos"]["B2"] and "pr_auc" not in res["modelos"]["B2"]
    assert res["modelos"]["E1"].get("no_limiar") is None


def test_json_nao_publica_contagem_de_1_a_9(df):
    pequeno = df.iloc[:400].copy()
    sorteio = np.random.default_rng(21).choice(400, size=4, replace=False)
    pequeno["y"] = 0
    pequeno.iloc[sorteio, pequeno.columns.get_loc("y")] = 1  # 4 eventos: R7 proíbe publicar
    pred = ev.predizer(_modelos(pequeno), pequeno, dentro_do_teste=True)
    res = ev.calcular_metricas(pequeno["y"], pred, seed=20261103, n=20, processos=1)
    assert res.json["eventos"] == "<10"
    assert artifacts.inteiros_pequenos(json.loads(json.dumps(res.json))) == []


def test_prever_e1_bate_com_o_risco_do_perfil_do_explain(df):
    e1 = _e1_sintetico(df)
    sem_ausente = df[(df[list(COMORBIDADES)] != "Ausente").all(axis=1)].head(25)
    risco = ev.prever_e1(e1, sem_ausente.reset_index(drop=True))
    for i, (_, linha) in enumerate(sem_ausente.iterrows()):
        marcadas = tuple(c for c in COMORBIDADES if linha[c] == "Sim")
        esperado = explain.risco_perfil(e1, linha["idade_anos"], linha["sexo"],
                                        int(linha["gestante"]), marcadas)["risco"]
        assert risco[i] == pytest.approx(esperado, rel=1e-9)


def test_prever_e1_recusa_covariavel_ausente(df):
    e1 = _e1_sintetico(df)
    ruim = df.head(5).copy()
    ruim.loc[ruim.index[0], "idade_anos"] = np.nan
    with pytest.raises(ValueError, match="covariáveis ausentes"):
        ev.prever_e1(e1, ruim)


# --- Carga dos modelos: divergência com o selecao.json ---------------------------------------

def _patch_carga(monkeypatch, sel, limiar_m1=0.1, nome_m1="xgboost"):
    from dengue_sinan import baselines_final, runner

    class Bl:
        b0 = FakeBase(np.zeros(3), 0.5)
        b1 = FakeBase(np.zeros(3), 0.5)

    m1 = FakeM1(np.zeros(3), limiar=limiar_m1, nome=nome_m1)
    monkeypatch.setattr(artifacts, "load_bundle",
                        lambda p: m1 if Path(p).name == "m1_final" else _e1_sintetico(
                            _df_sintetico(n=60)))
    monkeypatch.setattr(baselines_final, "carregar_baselines", lambda p: Bl())
    monkeypatch.setattr(runner, "_ler_json", lambda p: sel)
    monkeypatch.setattr(artifacts, "ler_metadados", lambda p: {"payload": {"x.bin": "0" * 64}})


def _sel(limiar=0.1, criterio=None, vencedor="xgboost"):
    from dengue_sinan import selecao
    return {"vencedor": vencedor, "criterio_limiar": criterio or selecao.CRITERIO_LIMIAR,
            "modelos": {"xgboost": {"limiar": limiar}}}


def test_carregar_modelos_recusa_limiar_que_diverge_do_selecao(cfg, monkeypatch):
    _patch_carga(monkeypatch, _sel(limiar=0.2), limiar_m1=0.1)
    with pytest.raises(ValueError, match="diverge do selecao.json"):
        ev.carregar_modelos(cfg)


def test_carregar_modelos_recusa_criterio_que_nao_e_o_d92(cfg, monkeypatch):
    _patch_carga(monkeypatch, _sel(criterio="maior F2 (antigo)"))
    with pytest.raises(ValueError, match="D-92"):
        ev.carregar_modelos(cfg)


def test_carregar_modelos_aceita_m1_que_bate_com_o_selecao(cfg, monkeypatch):
    _patch_carga(monkeypatch, _sel(limiar=0.1), limiar_m1=0.1)
    modelos = ev.carregar_modelos(cfg)
    assert set(modelos.payloads) == {"E1", "M1", "B1", "B0"}


# --- Verificação (D-64) ----------------------------------------------------------------------

def test_relatorio_de_verificacao_passa_quando_os_numeros_batem(cfg, df, esperado, tmp_path):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    checks = ev.checks_teste(cfg, execucao, esperado, ambiente=[])
    relatorio = verify.write_report("T-5.1", checks, tmp_path / "ver", cfg)
    assert json.loads(relatorio.read_text(encoding="utf-8"))["passou"] is True


def test_relatorio_reprova_quando_um_check_falha(cfg, df, esperado, tmp_path):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    errado = {**esperado, "populacao_total": esperado["populacao_total"] + 1}
    checks = ev.checks_teste(cfg, execucao, errado, ambiente=[])
    relatorio = verify.write_report("T-5.1", checks, tmp_path / "ver", cfg)
    dados = json.loads(relatorio.read_text(encoding="utf-8"))
    assert dados["passou"] is False
    assert [c["nome"] for c in dados["checks"] if not c["passou"]] == [
        "populacao_2024_igual_ao_esperado"]


def test_checks_incluem_ordem_de_gravacao_e_reamostras(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    nomes = {c["nome"]: c for c in ev.checks_teste(cfg, execucao, esperado, ambiente=[])}
    assert nomes["nada_gravado_antes_do_fim"]["passou"] is True
    assert nomes["reamostras_metricas_do_config"]["obtido"] == 20
    assert nomes["sem_contagens_de_1_a_9_no_json"]["passou"] is True
    assert "reamostras_calibracao_configuradas_para_t52" in nomes


def test_main_ensaio_roda_e_nao_cria_lacre(cfg, tmp_path, monkeypatch, capsys):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    dev = pd.concat([_df_sintetico(n=600, ano=2022), _df_sintetico(n=400, seed=2, ano=2023)],
                    ignore_index=True)
    modelos = _modelos(dev)
    monkeypatch.setattr(ev, "FONTES_ENSAIO", ev.Fontes(
        populacao=lambda c: dev.copy(), hash_dados=lambda c: {},
        modelos=lambda c: modelos, features=lambda d: d, selecao=_sel_fonte))
    assert ev.main(["--config", str(cfg_path), "--ensaio"]) == 0
    assert not (Path(cfg["caminhos"]["relatorios"]) / "teste").exists()
    assert "ensaio" in capsys.readouterr().out


def test_relatorio_registra_o_numero_de_vcpus(cfg, df, esperado):
    execucao = ev.evaluate_test_once(cfg, fontes=_fontes(df))
    nomes = {c["nome"]: c for c in ev.checks_teste(cfg, execucao, esperado, ambiente=[])}
    assert nomes["vcpus"]["obtido"] == (os.cpu_count() or 0)


# --- main: falha do relatório de verificação depois do lacre -----------------------------------

def _roda_main_do_teste(cfg, df, tmp_path, monkeypatch):
    cfg_path = tmp_path / "cfg.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg), encoding="utf-8")
    monkeypatch.setattr(ev, "FONTES_TESTE", _fontes(df))
    return ev.main(["--config", str(cfg_path)])


def test_falha_do_relatorio_depois_do_lacre_diz_a_verdade(cfg, df, esperado, tmp_path,
                                                          monkeypatch, caplog):
    def falha(*args, **kwargs):
        raise OSError("disco cheio")

    monkeypatch.setattr(verify, "write_report", falha)
    with caplog.at_level(logging.ERROR):
        codigo = _roda_main_do_teste(cfg, df, tmp_path, monkeypatch)
    assert codigo == 1
    assert (Path(cfg["caminhos"]["relatorios"]) / "teste" / ev.ARQ_LACRE).exists()
    texto = caplog.text
    assert "LACRE já foi gravado" in texto and "NÃO rode a avaliação de novo" in texto
    assert "gerar_verificacao_do_lacre" in texto
    assert "nenhum resultado foi gravado" not in texto  # era falso


def test_gerar_verificacao_do_lacre_nao_recalcula_nem_le_2024(cfg, df, esperado, tmp_path,
                                                              monkeypatch):
    ev.evaluate_test_once(cfg, fontes=_fontes(df))

    def proibido(*args, **kwargs):
        raise AssertionError("leu 2024 ou recalculou")

    monkeypatch.setattr(dataset, "load_population", proibido)
    monkeypatch.setattr(ev, "calcular_metricas", proibido)
    relatorio = ev.gerar_verificacao_do_lacre(cfg, ambiente=[])
    dados = json.loads(relatorio.read_text(encoding="utf-8"))
    nomes = {c["nome"]: c for c in dados["checks"]}
    assert dados["passou"] is True
    assert nomes["relatorios_conferem_com_o_lacre"]["passou"] is True
    assert nomes["verificacao_regenerada_do_lacre"]["obtido"] is True


def test_gerar_verificacao_do_lacre_reprova_se_um_relatorio_foi_alterado(cfg, df, esperado):
    ev.evaluate_test_once(cfg, fontes=_fontes(df))
    pasta = Path(cfg["caminhos"]["relatorios"]) / "teste"
    (pasta / ev.ARQ_MARKDOWN).write_text("adulterado", encoding="utf-8")
    dados = json.loads(ev.gerar_verificacao_do_lacre(cfg, ambiente=[]).read_text(encoding="utf-8"))
    assert dados["passou"] is False
    assert [c["nome"] for c in dados["checks"] if not c["passou"]] == [
        "relatorios_conferem_com_o_lacre"]


def test_gerar_verificacao_do_lacre_sem_lacre_levanta_erro(cfg):
    with pytest.raises(FileNotFoundError, match="sem LACRE.json"):
        ev.gerar_verificacao_do_lacre(cfg, ambiente=[])
