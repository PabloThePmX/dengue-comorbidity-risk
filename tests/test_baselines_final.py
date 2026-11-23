"""Testes do congelamento de B0 e B1 (T-5.0, D-93) com dados sintéticos (nenhum microdado real)."""

import copy
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from dengue_sinan import artifacts, baselines, dataset, metrics, selecao, verify
from dengue_sinan import baselines_final as bf
from dengue_sinan.config import load_config
from dengue_sinan.profiling import COMORBIDADES

CRITERIO = selecao.CRITERIO_LIMIAR
RECALL_ALVO = 0.6
ORDEM = load_config()["ordem_dobras"]


def _cfg(tmp_path: Path) -> dict:
    base = load_config()
    dados = tmp_path / "data"
    dados.mkdir()
    manifesto = {str(ano): {"sha256_dbc": "a" * 64, "sha256_parquet": "b" * 64}
                 for ano in base["anos_dev"]}
    (dados / "manifest.json").write_text(json.dumps(manifesto), encoding="utf-8")
    return {**copy.deepcopy(base), "caminhos": {
        **base["caminhos"], "dados": str(dados), "relatorios": str(tmp_path / "reports"),
        "modelos": str(tmp_path / "models"), "mlruns": str(tmp_path / "mlruns")}}


def _escrever_selecao(cfg: dict, recall_alvo=RECALL_ALVO) -> None:
    """selecao.json da T-4.9: critério, recall da B2 (alvo) e os candidatos (não usados aqui)."""
    pasta = bf.runner.pasta_m1(cfg)
    pasta.mkdir(parents=True, exist_ok=True)
    dados = {"tarefa": "T-4.9", "criterio_limiar": CRITERIO, "recall_alvo": recall_alvo,
             "modelos": {}}
    (pasta / selecao.NOME_SELECAO).write_text(json.dumps(dados), encoding="utf-8")


def _df(seed: int = 1, n: int = 3000, anos=(2022, 2023), prevalencia_alvo: float | None = None):
    """Casos com risco que sobe com a idade e com diabetes; ANO alternado entre os anos."""
    rng = np.random.default_rng(seed)
    idade = rng.uniform(0, 100, size=n)
    diabetes = rng.random(n) < 0.2
    logit = -4.5 + 0.03 * idade + 1.0 * diabetes
    y = (rng.random(n) < 1 / (1 + np.exp(-logit))).astype(int)
    if prevalencia_alvo is not None:
        y = np.zeros(n, dtype=int)
        y[: int(round(prevalencia_alvo * n))] = 1
    return pd.DataFrame({
        "idade_anos": idade, "sexo": np.where(np.arange(n) % 2, "M", "F"),
        "gestante": np.zeros(n, dtype="int8"), "LACO": "Não", "PETEQUIA_N": "Não",
        **{c: np.where(diabetes, "Sim", "Não") if c == "DIABETES" else "Não"
           for c in COMORBIDADES},
        "y": y, "ANO": np.array(anos)[np.arange(n) % len(anos)].astype("int64"),
    })


def _oof_sintetico(seed: int = 1, n_por_regiao: int = 900, anos=(2022, 2023)):
    """OOF de B0 e B1 com as mesmas linhas e a mesma ordem (ANO, região, y), como a T-2.8 grava."""
    rng = np.random.default_rng(seed)
    partes = []
    for regiao in ORDEM:
        idade = rng.uniform(0, 100, n_por_regiao)
        diabetes = rng.random(n_por_regiao) < 0.2
        p_b1 = 1 / (1 + np.exp(-(-4.0 + 0.03 * idade + 1.0 * diabetes)))
        y = (rng.random(n_por_regiao) < p_b1).astype("int8")
        partes.append(pd.DataFrame({
            "ANO": np.array(anos)[np.arange(n_por_regiao) % len(anos)].astype("int64"),
            "regiao": regiao, "y": y, "p_b1": p_b1, "p_b0": float(y.mean()),
        }))
    base = pd.concat(partes, ignore_index=True)
    oof_b0 = base[["ANO", "regiao", "y"]].assign(p=base["p_b0"].astype(float))
    oof_b1 = base[["ANO", "regiao", "y"]].assign(p=base["p_b1"].astype(float))
    return oof_b0, oof_b1


def _escrever_oofs(cfg: dict, oof_b0: pd.DataFrame, oof_b1: pd.DataFrame) -> None:
    pasta = bf.runner._caminho(cfg, "dados") / "oof"
    pasta.mkdir(parents=True, exist_ok=True)
    oof_b0.to_parquet(pasta / "oof_B0.parquet", index=False)
    oof_b1.to_parquet(pasta / "oof_B1.parquet", index=False)


def _fmt(valor: float) -> str:
    return f"{valor:.6f}".replace(".", ",")


def _texto_comparacao(lim_b0: float, lim_b1: float) -> str:
    """Relatório no formato de comparacao_oof.md, com a seção 3.1 (F2) que repete B0 e B1."""
    return "\n".join([
        "# Comparação OOF (sintético)",
        "",
        "## 1. PR-AUC",
        "",
        "| Modelo | PR-AUC |",
        "| --- | ---: |",
        "| B0 | 0,00149 |",
        "",
        "## 3. Métricas no limiar",
        "",
        "Limiar principal (D-92).",
        "",
        "| Modelo | Limiar | Recall | Precisão | F2 |",
        "| --- | ---: | ---: | ---: | ---: |",
        "| elastic_net | 0,002043 | 0,6946 | 0,0064 | 0,0307 |",
        f"| B0 | {_fmt(lim_b0)} | 1,0000 | 0,0016 | 0,0081 |",
        f"| B1 | {_fmt(lim_b1)} | 0,6843 | 0,0029 | 0,0142 |",
        "",
        "### 3.1 Ponto F2 (secundário, D-33)",
        "",
        "| Modelo | Limiar F2 | Recall | Precisão | F2 |",
        "| --- | ---: | ---: | ---: | ---: |",
        "| B0 | 0,001529 | 1,0000 | 0,0016 | 0,0081 |",
        "| B1 | 0,014346 | 0,1483 | 0,0266 | 0,0774 |",
        "",
        "## 4. Busca de hiperparâmetros",
        "",
        "| Modelo | Tentativas |",
        "| --- | ---: |",
        "| elastic_net | 3 |",
        "",
    ])


def _escrever_tabela(cfg: dict, lim_b0: float, lim_b1: float) -> Path:
    caminho = bf.runner._caminho(cfg, "relatorios") / "m1" / bf.ARQ_TABELA
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(_texto_comparacao(lim_b0, lim_b1), encoding="utf-8")
    return caminho


def _limiares_do_oof(cfg: dict) -> dict[str, float]:
    oofs, _ = bf.ler_oofs_baselines(cfg)
    return {n: bf.limiar_recalculado(oofs[n], RECALL_ALVO) for n in bf.NOMES_LIMIAR}


@pytest.fixture
def cfg(tmp_path):
    cfg = _cfg(tmp_path)
    _escrever_selecao(cfg)
    _escrever_oofs(cfg, *_oof_sintetico())
    lim = _limiares_do_oof(cfg)
    _escrever_tabela(cfg, lim["B0"], lim["B1"])  # tabela consistente com o OOF sintético
    return cfg


@pytest.fixture
def df_sintetico(monkeypatch):
    df = _df()
    monkeypatch.setattr(bf, "carregar_desenvolvimento", lambda cfg: df.copy())
    return df


def _congelar(cfg, destino=None):
    return bf.congelar_baselines(cfg, destino)


def _esperado_yaml(tmp_path: Path, casos: int, eventos: int) -> Path:
    caminho = tmp_path / "esperado.yaml"
    caminho.write_text(yaml.safe_dump({"desenvolvimento": {
        "populacao_total": casos, "eventos_total": eventos}}), encoding="utf-8")
    return caminho


def _falhas(relatorio: Path) -> list[str]:
    return [c["nome"] for c in json.loads(relatorio.read_text(encoding="utf-8"))["checks"]
            if not c["passou"]]


# --- Ajuste, recarga e B0 --------------------------------------------------------------------

def test_ajuste_e_recarga_reproduzem_as_predicoes(cfg, df_sintetico):
    cong = _congelar(cfg)
    carregados = bf.carregar_baselines(cong.raiz)
    assert np.array_equal(carregados.b1.predizer(cong.amostra), cong.p_b1)
    assert np.array_equal(carregados.b0.predizer(cong.amostra), cong.p_b0)


def test_b1_e_ajustado_em_todo_o_periodo_como_o_ajustar_b1(cfg, df_sintetico):
    cong = _congelar(cfg)
    carregados = bf.carregar_baselines(cong.raiz)
    referencia = baselines.ajustar_b1(df_sintetico)  # o mesmo ajuste, em todo o 2022–23
    assert np.allclose(carregados.b1.predizer(cong.amostra),
                       baselines.prever_b1(referencia, cong.amostra), rtol=0, atol=1e-12)


def test_b0_devolve_a_prevalencia_de_2022_2023_para_todas_as_linhas(cfg, monkeypatch):
    df = _df(prevalencia_alvo=0.1)
    monkeypatch.setattr(bf, "carregar_desenvolvimento", lambda cfg: df.copy())
    cong = _congelar(cfg)
    b0 = bf.carregar_baselines(cong.raiz).b0
    assert b0.prevalencia == pytest.approx(0.1)
    outro = _df(seed=9, n=57, prevalencia_alvo=0.5)  # outra prevalência: o B0 não muda
    assert np.array_equal(b0.predizer(outro), np.full(57, 0.1))


def test_b1_nao_e_calibrado_e_nao_tem_pesos_de_classe(cfg, df_sintetico):
    cong = _congelar(cfg)
    logistica = bf.carregar_baselines(cong.raiz).b1.modelo.named_steps["logistica"]
    assert logistica.class_weight is None
    assert np.isinf(logistica.C)


# --- Limiares: recalculados do OOF com recall_alvo (D-92) ------------------------------------

def test_limiar_gravado_e_o_threshold_for_min_recall_do_oof(cfg, df_sintetico):
    oof_b0, oof_b1 = _oof_sintetico()
    cong = _congelar(cfg)
    carregados = bf.carregar_baselines(cong.raiz)
    esperado_b1 = metrics.threshold_for_min_recall(oof_b1["y"].to_numpy(),
                                                   oof_b1["p"].to_numpy(), RECALL_ALVO)
    esperado_b0 = metrics.threshold_for_min_recall(oof_b0["y"].to_numpy(),
                                                   oof_b0["p"].to_numpy(), RECALL_ALVO)
    assert carregados.b1.limiar == esperado_b1
    assert carregados.b0.limiar == esperado_b0


def test_recall_no_limiar_recalculado_e_pelo_menos_o_alvo(cfg, df_sintetico):
    cong = _congelar(cfg)
    assert cong.recall_no_limiar["B1"] >= RECALL_ALVO
    assert cong.recall_no_limiar["B0"] >= RECALL_ALVO


@pytest.mark.parametrize("valor", [-0.1, 1.5, float("nan"), float("inf"), True, "0.6", None])
def test_recall_alvo_fora_de_0_1_ou_nao_numerico_levanta_erro(valor):
    with pytest.raises(ValueError, match="recall_alvo"):
        bf.recall_alvo_da_selecao({"recall_alvo": valor})


def test_recall_alvo_ausente_levanta_erro():
    with pytest.raises(ValueError, match="sem recall_alvo"):
        bf.recall_alvo_da_selecao({"criterio_limiar": CRITERIO})


def test_congelar_com_recall_alvo_invalido_nao_grava_nada(cfg, monkeypatch):
    _escrever_selecao(cfg, recall_alvo=1.5)
    monkeypatch.setattr(bf, "carregar_desenvolvimento", lambda cfg: _df())
    with pytest.raises(ValueError, match="recall_alvo"):
        _congelar(cfg)
    assert not (Path(cfg["caminhos"]["modelos"]) / bf.NOME_B1).exists()


def test_selecao_inexistente_levanta_erro(cfg, monkeypatch):
    (bf.runner.pasta_m1(cfg) / selecao.NOME_SELECAO).unlink()
    monkeypatch.setattr(bf, "carregar_desenvolvimento", lambda cfg: _df())
    with pytest.raises(FileNotFoundError, match="T-4.9"):
        _congelar(cfg)


def test_oof_ausente_levanta_erro(cfg, monkeypatch):
    (bf.runner._caminho(cfg, "dados") / "oof" / "oof_B0.parquet").unlink()
    monkeypatch.setattr(bf, "carregar_desenvolvimento", lambda cfg: _df())
    with pytest.raises(FileNotFoundError, match="OOF ausente"):
        _congelar(cfg)


def test_oof_de_b0_e_b1_fora_de_ordem_entre_si_levanta_erro(cfg, monkeypatch):
    oof_b0, oof_b1 = _oof_sintetico()
    _escrever_oofs(cfg, oof_b0, oof_b1.sample(frac=1, random_state=0))
    monkeypatch.setattr(bf, "carregar_desenvolvimento", lambda cfg: _df())
    with pytest.raises(ValueError, match="fora de ordem"):
        _congelar(cfg)


# --- R1: 2024 é recusado e nada é gravado ----------------------------------------------------

def test_dado_de_2024_e_recusado_no_ajuste_e_nada_e_gravado(cfg, monkeypatch):
    df = _df().assign(ANO=2024)
    monkeypatch.setattr(bf, "carregar_desenvolvimento", lambda cfg: df)
    with pytest.raises(RuntimeError, match="R1"):
        _congelar(cfg)
    assert not (Path(cfg["caminhos"]["modelos"]) / bf.NOME_B1).exists()
    assert not (Path(cfg["caminhos"]["modelos"]) / bf.NOME_B0).exists()


def test_oof_com_2024_e_recusado_pela_guarda_e_nada_e_gravado(cfg, monkeypatch):
    oof_b0, oof_b1 = _oof_sintetico()
    _escrever_oofs(cfg, oof_b0.assign(ANO=2024), oof_b1.assign(ANO=2024))
    monkeypatch.setattr(bf, "carregar_desenvolvimento", lambda cfg: _df())
    with pytest.raises(RuntimeError, match="R1"):
        _congelar(cfg)
    assert not (Path(cfg["caminhos"]["modelos"]) / bf.NOME_B1).exists()


def test_carregar_desenvolvimento_recusa_2024(cfg, monkeypatch):
    populacao = _df().assign(ANO=2024)
    monkeypatch.setattr(dataset, "load_population", lambda cfg, anos: populacao)
    monkeypatch.setattr(dataset, "build_feature_frame", lambda df: df)
    with pytest.raises(RuntimeError, match="R1"):
        bf.carregar_desenvolvimento(cfg)


# --- Tabela de comparacao_oof.md (conferência) ------------------------------------------------

def test_ler_limiares_da_tabela_pega_so_a_secao_3_e_converte_a_virgula(cfg):
    lim = _limiares_do_oof(cfg)
    tabela = bf.ler_limiares_da_tabela(bf.runner._caminho(cfg, "relatorios") / "m1" /
                                       bf.ARQ_TABELA)
    assert tabela["B0"] == pytest.approx(round(lim["B0"], 6), abs=1e-12)
    assert tabela["B1"] == pytest.approx(round(lim["B1"], 6), abs=1e-12)
    assert tabela["B1"] != 0.014346  # a linha da seção 3.1 (F2) não entra


@pytest.mark.parametrize("texto, mensagem", [
    ("# X\n\n## 1. Outra\n\n| B0 | 0,1 |\n", "sem a seção"),
    ("## 3. Métricas no limiar\n\n| B0 | 0,1 |\n", "sem linha de"),
    ("## 3. Métricas no limiar\n\n| B0 | 0,1 |\n| B0 | 0,2 |\n| B1 | 0,3 |\n",
     "repetida"),
])
def test_tabela_mal_formada_levanta_erro(cfg, texto, mensagem):
    caminho = bf.runner._caminho(cfg, "relatorios") / "m1" / bf.ARQ_TABELA
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8")
    with pytest.raises(ValueError, match=mensagem):
        bf.ler_limiares_da_tabela(caminho)


def test_tabela_ausente_levanta_erro_claro(tmp_path):
    with pytest.raises(FileNotFoundError, match="comparacao_oof.md"):
        bf.ler_limiares_da_tabela(tmp_path / "nao_existe" / bf.ARQ_TABELA)


# --- Artefato: adulteração e metadata --------------------------------------------------------

@pytest.mark.parametrize("nome, arquivo", [(bf.NOME_B1, bf.ARQ_B1), (bf.NOME_B0, bf.ARQ_B0)])
def test_artefato_adulterado_um_byte_e_recusado_pela_carga(cfg, df_sintetico, nome, arquivo):
    cong = _congelar(cfg)
    alvo = cong.raiz / nome / artifacts.PASTA_PAYLOAD / arquivo
    dados = bytearray(alvo.read_bytes())
    dados[len(dados) // 2] ^= 0x01
    alvo.write_bytes(bytes(dados))
    with pytest.raises(artifacts.ArtefatoInvalido, match="SHA-256"):
        bf.carregar_baselines(cong.raiz)


def test_metadata_fr12_e_bloco_baseline(cfg, df_sintetico):
    cong = _congelar(cfg)
    for nome, tipo in ((bf.NOME_B1, "b1"), (bf.NOME_B0, "b0")):
        meta = artifacts.ler_metadados(cong.raiz / nome)
        assert meta["tipo_payload"] == tipo
        for campo in ("schema_version", "criado_em_utc", "versao_codigo", "bibliotecas",
                      "payload", "config", "dados", "data_treino", "metricas_validacao",
                      "features"):
            assert campo in meta
        nome_base = nome.split("_")[0].upper()
        assert meta["baseline"]["calibrado"] is False
        assert meta["baseline"]["hash_selecao"] == cong.sha_selecao
        assert meta["baseline"]["hash_oof"] == cong.sha_oof[nome_base]
        assert meta["baseline"]["recall_alvo"] == RECALL_ALVO
        assert meta["metricas_validacao"]["limiar"] == cong.limiares[nome_base]
        assert artifacts.inteiros_pequenos(meta) == []  # R7


# --- Relatório de verificação (D-64) ---------------------------------------------------------

def test_executar_passa_quando_os_numeros_batem(cfg, df_sintetico, tmp_path):
    esperado = _esperado_yaml(tmp_path, len(df_sintetico), int(df_sintetico["y"].sum()))
    relatorio, medidas = bf.executar(cfg, esperado_path=esperado)
    assert relatorio.name == "T-5.0.json"
    dados = json.loads(relatorio.read_text(encoding="utf-8"))
    assert dados["tarefa"] == "T-5.0"
    assert dados["passou"] is True
    assert medidas["passou"] is True
    nomes = {c["nome"] for c in dados["checks"]}
    for obrigatorio in ("casos_2022_2023", "eventos_2022_2023", "so_anos_de_desenvolvimento",
                        "b1_predicoes_iguais_apos_carga", "b0_predicoes_iguais_apos_carga",
                        "limiar_b1_gravado_igual_recalculado",
                        "limiar_b1_recalculado_igual_tabela_comparacao_oof",
                        "limiar_b0_recalculado_igual_tabela_comparacao_oof",
                        "recall_b1_no_limiar_ge_recall_alvo", "b1_sha256_payload",
                        "b0_sha256_payload"):
        assert obrigatorio in nomes
    assert all(c["passou"] for c in dados["checks"])


def test_relatorio_reprova_quando_um_check_falha(cfg, df_sintetico, tmp_path):
    esperado = _esperado_yaml(tmp_path, len(df_sintetico) + 1, int(df_sintetico["y"].sum()))
    relatorio, medidas = bf.executar(cfg, esperado_path=esperado)
    assert medidas["passou"] is False
    assert _falhas(relatorio) == ["casos_2022_2023"]


def test_limiar_recalculado_que_diverge_da_tabela_reprova(cfg, df_sintetico, tmp_path):
    lim = _limiares_do_oof(cfg)
    _escrever_tabela(cfg, lim["B0"], lim["B1"] + 1e-4)  # a tabela não bate com o recalculado
    esperado = _esperado_yaml(tmp_path, len(df_sintetico), int(df_sintetico["y"].sum()))
    relatorio, medidas = bf.executar(cfg, esperado_path=esperado)
    assert medidas["passou"] is False
    assert _falhas(relatorio) == ["limiar_b1_recalculado_igual_tabela_comparacao_oof"]


def test_tabela_ausente_reprova_com_mensagem_clara(cfg, df_sintetico, tmp_path):
    (bf.runner._caminho(cfg, "relatorios") / "m1" / bf.ARQ_TABELA).unlink()
    esperado = _esperado_yaml(tmp_path, len(df_sintetico), int(df_sintetico["y"].sum()))
    relatorio, medidas = bf.executar(cfg, esperado_path=esperado)
    dados = json.loads(relatorio.read_text(encoding="utf-8"))
    assert medidas["passou"] is False
    assert "tabela_comparacao_oof_lida" in _falhas(relatorio)
    erro = next(c for c in dados["checks"] if c["nome"] == "erro_tabela_comparacao_oof")
    assert "comparacao_oof.md" in erro["obtido"]


def test_recall_abaixo_do_alvo_reprova(cfg, df_sintetico, tmp_path, monkeypatch):
    monkeypatch.setattr(bf, "limiar_recalculado", lambda oof, alvo: 0.9)  # quase ninguém passa
    esperado = _esperado_yaml(tmp_path, len(df_sintetico), int(df_sintetico["y"].sum()))
    relatorio, medidas = bf.executar(cfg, esperado_path=esperado)
    assert medidas["passou"] is False
    assert "recall_b1_no_limiar_ge_recall_alvo" in _falhas(relatorio)


def test_main_sai_com_1_quando_nao_passa(cfg, df_sintetico, tmp_path, monkeypatch):
    esperado = _esperado_yaml(tmp_path, len(df_sintetico) + 5, int(df_sintetico["y"].sum()))
    monkeypatch.setattr(bf, "ESPERADO_PADRAO", esperado)
    monkeypatch.setattr(bf, "load_config", lambda caminho: cfg)
    assert bf.main(["--config", str(tmp_path / "x.yaml")]) == 1


def test_gitignore_cobre_os_artefatos_do_t50():
    linhas = (verify.REPO / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "models/b1_final*" in linhas
    assert "models/b0_final*" in linhas


# --- Correção pendente da T-5.0 (T-5.1): tolerância da tabela e recall exatamente no alvo ---

def test_tolerancia_da_tabela_aceita_o_erro_maximo_do_arredondamento_a_6_casas():
    # Arredondar a 6 casas erra no máximo 5e-7. A tolerância precisa aceitar exatamente isso.
    rng = np.random.default_rng(4)
    valores = np.concatenate([rng.random(2000) * 0.05, [0.1234565, 0.0000005, 0.0021548546]])
    for valor in valores:
        arredondado = round(float(valor), 6)
        assert abs(arredondado - valor) <= bf.TOLERANCIA_TABELA, valor


def test_tolerancia_da_tabela_recusa_erro_acima_de_5e_7():
    tol = bf.TOLERANCIA_TABELA
    assert verify.check("limiar", 0.001, 0.001 + 5e-7, tol)["passou"]
    assert not verify.check("limiar", 0.001, 0.001 + 5e-7 + 1e-9, tol)["passou"]


def test_limiar_com_recall_exatamente_igual_ao_alvo_conta_sem_folga():
    # Caso de borda do B1: um limiar dá recall EXATAMENTE igual ao alvo (0,5 = 2 de 4 positivos).
    # Com `>=` o limiar é 0,5 (precisão 0,5, empate: o maior limiar). Com `>` seria 0,3.
    from types import SimpleNamespace
    oof = SimpleNamespace(
        y=np.array([1, 1, 1, 1, 0, 0, 0, 0, 0]),
        p=np.array([0.9, 0.5, 0.3, 0.1, 0.8, 0.6, 0.4, 0.2, 0.05]),
    )
    limiar = bf.limiar_recalculado(oof, 0.5)
    assert limiar == 0.5
    recall = metrics.threshold_metrics(oof.y, oof.p, limiar)["recall"]
    assert recall == 0.5
