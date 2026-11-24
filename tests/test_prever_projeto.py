"""Script de previsão dos modelos do projeto (D-97, T-8.6): regra de entrada, ordem, ausências,
E1 (estimabilidade e paridade), B2, B0 e B1 sintéticos no formato real e uma fumaça.

Nada aqui lê 2024 ou 2025 de verdade. A fumaça usa só a amostra de 2022 (pula se não existir).
O M1 real não carrega neste ambiente (XGBoost 3.4.1; Registro de problemas de 2026-11-24): o
teste dele é `xfail` estrito, para o bloqueio ficar visível e virar teste passando quando resolvido.
"""

import importlib.util
import json
from itertools import combinations
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from app import servico
from dengue_sinan import artifacts, baselines, comparacao_manifesto, guard
from dengue_sinan.config import load_config
from dengue_sinan.preprocess import FEATURES_PERMITIDAS
from dengue_sinan.profiling import COMORBIDADES, SINAIS

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "scripts" / "comparacao" / "prever_projeto.py"
MANIFESTO = RAIZ / "config" / "comparacao" / "manifesto.yaml"
AMOSTRA_2022 = RAIZ / "data" / "comparacao" / "smoke_2022" / "amostra_2022.parquet"
E1_JSON = RAIZ / "models" / "e1" / "payload" / "e1.json"
CFG = load_config()


def _carregar_script():
    spec = importlib.util.spec_from_file_location("prever_projeto", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


pp = _carregar_script()


# ------------------------------------------------------------------ fixtures e helpers
@pytest.fixture
def espiao_carga(monkeypatch):
    """Troca `carregar` por um que registra a chamada e falha: nenhum artefato é carregado."""
    chamadas = []

    def _carregar(plano):
        chamadas.append(plano.id)
        raise AssertionError(f"carregar({plano.id}) não deveria ser chamado")

    monkeypatch.setattr(pp, "carregar", _carregar)
    return chamadas


@pytest.fixture
def sem_porta(monkeypatch):
    monkeypatch.delenv(pp.PORTA_ENV, raising=False)


@pytest.fixture
def com_porta(monkeypatch):
    monkeypatch.setenv(pp.PORTA_ENV, "1")


def _quadro(ano: int, n: int = 60) -> pd.DataFrame:
    """Quadro com as colunas de `build_feature_frame` (categorias Sim/Não, como o projeto)."""
    i = np.arange(n)
    dados: dict = {
        "idade_anos": (30 + i % 50).astype("float64"),
        "sexo": np.array(["F", "M", "I"])[i % 3],
        "gestante": np.zeros(n, dtype="int8"),
    }
    marcas = np.zeros((n, len(COMORBIDADES)), dtype="int8")
    for j, c in enumerate(COMORBIDADES):
        marcas[:, j] = (i + j) % 7 == 0
        dados[c] = np.where(marcas[:, j] == 1, "Sim", "Não")
    dados["n_comorbidades"] = marcas.sum(axis=1).astype("int8")
    for k, s in enumerate(SINAIS):
        dados[s] = np.where((i + k) % 4 == 0, "Sim", "Não")
    dados["dias_ate_notificacao"] = (i % 60).astype("int64")
    dados["ANO"] = np.full(n, ano, dtype="int64")
    dados["LINHA"] = i.astype("int64")
    return pd.DataFrame(dados)


def _gravar_entrada(tmp_path: Path, quadro: pd.DataFrame, ano_sidecar: int | None = None) -> Path:
    entrada = tmp_path / "entrada.parquet"
    quadro.to_parquet(entrada, index=False)
    sidecar = {
        "ano": int(ano_sidecar if ano_sidecar is not None else quadro["ANO"].iloc[0]),
        "comparacao": False,
        "linhas": int(len(quadro)),
        "features_do_projeto": list(FEATURES_PERMITIDAS),
    }
    entrada.with_suffix(".json").write_text(json.dumps(sidecar), encoding="utf-8")
    return entrada


def _colunas() -> list[str]:
    return [*FEATURES_PERMITIDAS, "ANO", "LINHA"]


def _manifesto() -> dict:
    return comparacao_manifesto.carregar_manifesto(MANIFESTO, CFG)


def _e1_pares_excluidos() -> list[tuple[str, str]]:
    dados = json.loads(E1_JSON.read_text(encoding="utf-8"))
    return [tuple(p) for p in dados["pares_excluidos"]]


# ------------------------------------------------------------------ constantes e manifesto
def test_constantes_espelham_o_config():
    assert CFG["ano_teste"] == 2024
    assert CFG["ano_comparacao"] == 2025
    assert pp.PORTA_ENV == "DENGUE_PORTA_COMPARACAO"


def test_modelos_do_script_estao_no_manifesto():
    ids = {m["id"] for m in _manifesto()["modelos"]}
    assert set(pp.MODELOS) <= ids
    assert set(pp.OPCIONAIS) == {"b0_main", "b1_main"}


def test_artefatos_do_manifesto_batem_com_os_caminhos_do_script():
    por_id = {m["id"]: m for m in _manifesto()["modelos"]}
    assert por_id["m1_main"]["artefato"]["caminho"] == "models/m1_final/payload/m1.joblib"
    assert por_id["e1_main"]["artefato"]["caminho"] == "models/e1/payload/e1.npz"
    assert por_id["b0_main"]["artefato"]["caminho"] == "models/b0_final/payload/b0.json"
    assert por_id["b1_main"]["artefato"]["caminho"] == "models/b1_final/payload/b1.joblib"
    assert por_id["b2_regra"]["artefato"] is None


# ------------------------------------------------------------------ regra de entrada (R1, R2)
@pytest.mark.parametrize("porta", [False, True])
def test_recusa_2024_sempre_mesmo_com_a_porta(porta):
    with pytest.raises(PermissionError, match="2024"):
        pp.checar_anos({2024}, 2024, 2025, porta)
    with pytest.raises(PermissionError, match="2024"):
        pp.checar_anos({2022, 2024}, 2024, 2025, porta)


def test_recusa_2025_sem_a_variavel_de_ambiente():
    with pytest.raises(PermissionError, match="DENGUE_PORTA_COMPARACAO=1"):
        pp.checar_anos({2025}, 2024, 2025, porta_aberta=False)


def test_aceita_2025_com_a_porta_e_anos_de_desenvolvimento():
    pp.checar_anos({2025}, 2024, 2025, porta_aberta=True)
    pp.checar_anos({2022}, 2024, 2025, porta_aberta=False)
    pp.checar_anos({2022, 2023}, 2024, 2025, porta_aberta=False)


def test_entrada_de_um_ano_so():
    assert pp.ano_unico({2022}) == 2022
    with pytest.raises(SystemExit, match="um ano só"):
        pp.ano_unico({2022, 2025})


def test_2024_recusado_antes_da_carga(tmp_path, sem_porta, espiao_carga):
    entrada = _gravar_entrada(tmp_path, _quadro(2024))
    with pytest.raises(PermissionError, match="2024"):
        pp.main(["--entrada", str(entrada), "--saida-dir", str(tmp_path / "out")])
    assert espiao_carga == []
    assert not (tmp_path / "out").exists()


def test_2025_sem_porta_recusado_antes_da_carga(tmp_path, sem_porta, espiao_carga):
    entrada = _gravar_entrada(tmp_path, _quadro(2025))
    with pytest.raises(PermissionError, match="DENGUE_PORTA_COMPARACAO"):
        pp.main(["--entrada", str(entrada), "--saida-dir", str(tmp_path / "out")])
    assert espiao_carga == []


def test_sha_divergente_recusa_antes_da_carga(tmp_path, sem_porta, espiao_carga, monkeypatch):
    monkeypatch.setattr(pp, "sha256_arquivo", lambda _p: "0" * 64)
    entrada = _gravar_entrada(tmp_path, _quadro(2022))
    with pytest.raises(SystemExit, match="SHA-256"):
        pp.main(["--entrada", str(entrada), "--saida-dir", str(tmp_path / "out")])
    assert espiao_carga == []


def test_sidecar_com_outro_ano_recusado_antes_da_carga(tmp_path, sem_porta, espiao_carga):
    entrada = _gravar_entrada(tmp_path, _quadro(2022), ano_sidecar=2023)
    with pytest.raises(SystemExit, match="anos diferentes"):
        pp.main(["--entrada", str(entrada), "--saida-dir", str(tmp_path / "out")])
    assert espiao_carga == []


# ------------------------------------------------------------------ artefatos ausentes e SHA
def test_b0_e_b1_ausentes_sao_pulados_sem_erro(tmp_path):
    planos = pp.planejar(_manifesto(), ["b0_main", "b1_main"], raiz=tmp_path)
    assert all(not p.presente for p in planos)
    pp.conferir_sha(planos)  # não levanta: ausente não tem SHA a conferir


def test_modelo_obrigatorio_ausente_recusa(tmp_path):
    with pytest.raises(SystemExit, match="m1_main: artefato ausente"):
        pp.planejar(_manifesto(), ["m1_main"], raiz=tmp_path)


def test_b0_presente_com_sha_divergente_recusa(tmp_path):
    (tmp_path / "models" / "b0_final" / "payload").mkdir(parents=True)
    (tmp_path / "models" / "b0_final" / "payload" / "b0.json").write_text("{}", encoding="utf-8")
    planos = pp.planejar(_manifesto(), ["b0_main"], raiz=tmp_path)
    with pytest.raises(SystemExit, match="SHA-256"):
        pp.conferir_sha(planos)


def test_b2_nao_tem_artefato():
    planos = pp.planejar(_manifesto(), ["b2_regra"], raiz=RAIZ)
    assert planos[0].arquivo is None and planos[0].presente is True


# ------------------------------------------------------------------ guarda da porta (R1, D-97)
class _B0Espiao:
    """Stand-in do B0: registra se a porta de comparação estava aberta na hora da previsão."""

    def __init__(self):
        self.porta_aberta_na_previsao: list[bool] = []

    def predizer(self, df):
        self.porta_aberta_na_previsao.append(guard.leitura_da_comparacao_aberta())
        return np.zeros(len(df))


def test_previsao_de_2025_roda_dentro_da_porta(tmp_path):
    entrada = _gravar_entrada(tmp_path, _quadro(2025))
    espiao = _B0Espiao()
    res = pp.prever_entrada(entrada, {"b0_main": espiao}, _colunas(), 2025, 2025)
    assert espiao.porta_aberta_na_previsao == [True]
    assert len(res["b0_main"]["p"]) == 60
    assert guard.leitura_da_comparacao_aberta() is False  # a porta fecha ao sair


def test_previsao_de_2022_nao_abre_a_porta(tmp_path):
    entrada = _gravar_entrada(tmp_path, _quadro(2022))
    espiao = _B0Espiao()
    pp.prever_entrada(entrada, {"b0_main": espiao}, _colunas(), 2022, 2025)
    assert espiao.porta_aberta_na_previsao == [False]


# ------------------------------------------------------------------ validação de p
def test_nan_recusado_fora_do_e1():
    with pytest.raises(ValueError, match="NaN"):
        pp.validar_p("b0_main", np.array([0.1, np.nan]), None)


def test_p_fora_de_zero_um_recusado():
    with pytest.raises(ValueError, match="fora de"):
        pp.validar_p("m1_main", np.array([0.1, 1.5]), None)


def test_e1_aceita_nan_so_onde_nao_estima():
    p = np.array([0.1, np.nan, 0.4])
    pp.validar_p("e1_main", p, np.array([True, False, True]))  # não levanta
    with pytest.raises(ValueError, match="estimada"):
        pp.validar_p("e1_main", p, np.array([True, True, True]))


# ------------------------------------------------------------------ E1: estimabilidade
def test_mascara_e1_bate_com_o_servico_em_todas_as_128_combinacoes():
    """Mesma regra de `servico._sem_estimativa`, em todos os subconjuntos de comorbidades."""
    excluidos = _e1_pares_excluidos()
    subconjuntos = [s for r in range(len(COMORBIDADES) + 1)
                    for s in combinations(COMORBIDADES, r)]
    df = pd.DataFrame([{c: ("Sim" if c in s else "Não") for c in COMORBIDADES}
                       for s in subconjuntos])
    mascara = pp.mascara_e1(df, excluidos)
    e1_falso = SimpleNamespace(pares_excluidos=excluidos)
    esperado = [servico._sem_estimativa(e1_falso, s) is None for s in subconjuntos]
    assert mascara.tolist() == esperado


def test_e1_real_marca_5_ou_mais_e_par_excluido_como_nao_estimado():
    e1 = _carregar_e1_real()
    excl = e1.pares_excluidos[0]
    linhas = [
        {c: "Sim" for c in COMORBIDADES},  # 7 comorbidades: sem estimativa
        {c: ("Sim" if c in excl else "Não") for c in COMORBIDADES},  # par excluído
        {c: "Não" for c in COMORBIDADES},  # sem comorbidade: estimado
    ]
    df = pd.DataFrame(linhas)
    df["idade_anos"] = [40.0, 40.0, 40.0]
    df["sexo"] = ["F", "F", "F"]
    df["gestante"] = np.array([0, 0, 0], dtype="int8")
    df["ANO"] = 2022
    df["LINHA"] = [0, 1, 2]
    p, estimavel = pp.prever_bloco("e1_main", e1, df)
    assert estimavel.tolist() == [False, False, True]
    assert np.isnan(p[0]) and np.isnan(p[1])
    assert np.isfinite(p[2]) and 0 <= p[2] <= 1


def _carregar_e1_real():
    if not (RAIZ / "models" / "e1" / "metadata.json").is_file():
        pytest.skip("models/e1 ausente")
    return artifacts.load_bundle(RAIZ / "models" / "e1")


def test_e1_paridade_com_a_rota_do_evaluate_na_amostra_2022():
    """Mesmas probabilidades que `evaluate.prever_e1` (rota direta) nas linhas estimadas (1e-12)."""
    if not AMOSTRA_2022.is_file():
        pytest.skip("amostra de 2022 ausente (smoke_2022)")
    from dengue_sinan import evaluate

    e1 = _carregar_e1_real()
    df = pd.read_parquet(AMOSTRA_2022)
    p, estimavel = pp.prever_bloco("e1_main", e1, df.assign(ANO=2022))
    direta = evaluate.prever_e1(e1, df)
    assert estimavel.sum() > 0
    assert np.nanmax(np.abs(p[estimavel] - direta[estimavel])) <= 1e-12


# ------------------------------------------------------------------ M1: encanamento e bloqueio
def test_m1_recebe_as_features_do_modelo_mais_ano():
    class _M1Falso:
        features = ["idade_anos", "sexo", "gestante"]

        def __init__(self):
            self.colunas_recebidas: list[str] = []

        def prever_proba(self, X):
            self.colunas_recebidas = list(X.columns)
            return np.full(len(X), 0.25)

    bloco = _quadro(2022, n=5)
    m1 = _M1Falso()
    p, est = pp.prever_bloco("m1_main", m1, bloco)
    assert m1.colunas_recebidas == ["idade_anos", "sexo", "gestante", "ANO"]
    assert est is None and p.tolist() == [0.25] * 5


PASTA_M1 = RAIZ / "models" / "m1_final"
PARIDADE_M1 = RAIZ / "reports" / "verificacao" / "paridade-m1-demo.json"


def _carregar_m1_real():
    """Carrega o M1 congelado pelo mesmo contorno da demo (XGBoost 3.4.1 não lê a carga normal;
    ver Registro de problemas de 2026-11-24 e `app.servico.carregar_bundle_m1`)."""
    if not (PASTA_M1 / "payload" / "m1.joblib").is_file():
        pytest.skip("models/m1_final ausente")
    from app import servico

    return servico.carregar_bundle_m1(PASTA_M1)


def test_m1_real_carrega_pelo_contorno_e_confere_a_paridade_do_colab():
    """Hash do `get_dump` das árvores e limiar iguais aos medidos no Colab (paridade de T-6.1)."""
    import hashlib

    modelo = _carregar_m1_real()
    assert modelo.limiar == 0.0021548546241191616  # igual ao manifesto (exato)
    dump = modelo.modelo._estimador.get_booster().get_dump(dump_format="json")
    assert len(dump) == 419
    sha = hashlib.sha256("\n".join(dump).encode("utf-8")).hexdigest()
    if PARIDADE_M1.is_file():
        esperado = json.loads(PARIDADE_M1.read_text(encoding="utf-8"))["colab"]
        assert sha == esperado["sha256_get_dump_json"]


@pytest.mark.skipif(not AMOSTRA_2022.is_file(), reason="amostra de 2022 ausente (smoke_2022)")
def test_m1_paridade_com_a_rota_do_evaluate_na_amostra_2022():
    """Mesmas probabilidades que `ModeloFinal.prever_proba(df)` (rota do evaluate), 1e-12."""
    modelo = _carregar_m1_real()
    df = pd.read_parquet(AMOSTRA_2022)
    p, est = pp.prever_bloco("m1_main", modelo, df)
    direta = np.asarray(modelo.prever_proba(df), dtype=float)
    assert est is None
    assert np.nanmax(np.abs(p - direta)) <= 1e-12
    pp.validar_p("m1_main", p, None)  # sem NaN e em [0, 1]


# ------------------------------------------------------------------ B2: regra e features
def test_b2_usa_so_as_features_do_teste():
    """As mesmas colunas que `baselines.rule_b2` lê no teste de 2024: resto do quadro não entra."""
    base = _quadro(2022, n=40)
    referencia = baselines.rule_b2(base)
    for coluna in base.columns:
        if coluna in pp.FEATURES_B2:
            continue
        alterado = base.copy()
        alterado[coluna] = alterado[coluna].astype("object")
        alterado[coluna] = "xx"
        assert (baselines.rule_b2(alterado) == referencia).all(), coluna


def test_b2_lista_de_features_e_exatamente_a_que_a_regra_le():
    faltando = dict(_quadro(2022, n=3).iloc[0])
    for coluna in pp.FEATURES_B2:
        incompleto = pd.DataFrame([{k: v for k, v in faltando.items() if k != coluna}])
        with pytest.raises(KeyError):
            baselines.rule_b2(incompleto)


def test_b2_criterios_do_protocolo():
    base = {c: "Não" for c in COMORBIDADES}
    base.update({"idade_anos": 30.0, "gestante": np.int8(0), "LACO": "Não", "PETEQUIA_N": "Não"})
    casos = [
        ({}, False),
        ({"idade_anos": 1.0}, True),
        ({"idade_anos": 65.0}, False),
        ({"idade_anos": 66.0}, True),
        ({"gestante": np.int8(1)}, True),
        ({"DIABETES": "Sim"}, True),
        ({"LACO": "Sim"}, True),
        ({"PETEQUIA_N": "Sim"}, True),
        ({"DIABETES": "Ausente"}, False),
    ]
    for ajuste, esperado in casos:
        df = pd.DataFrame([{**base, **ajuste}])
        assert bool(baselines.rule_b2(df)[0]) is esperado, ajuste


def test_b2_no_script_devolve_0_ou_1():
    bloco = _quadro(2022, n=40)
    p, est = pp.prever_bloco("b2_regra", None, bloco)
    assert est is None
    assert set(np.unique(p)) <= {0.0, 1.0}
    assert (p == baselines.rule_b2(bloco).astype(float)).all()


# ------------------------------------------------- B0 e B1 sintéticos (formato real)
METADADOS_SINTETICOS = {
    "config": {"anos_dev": [2022, 2023], "ano_teste": 2024},
    "dados": {"sintetico": True},
    "data_treino": "2026-11-24",
    "metricas_validacao": {},
    "features": list(FEATURES_PERMITIDAS),
}


def test_b0_sintetico_gravado_pelo_save_bundle_prevê_constante(tmp_path):
    from dengue_sinan.baselines_final import B0Final  # importar registra o tipo b0

    pasta = artifacts.save_bundle(B0Final(prevalencia=0.02, limiar=0.01),
                                  tmp_path / "b0_final", METADADOS_SINTETICOS)
    obj = artifacts.load_bundle(pasta)
    p, est = pp.prever_bloco("b0_main", obj, _quadro(2022, n=10))
    assert est is None
    assert np.allclose(p, 0.02)
    pp.validar_p("b0_main", p, None)


def test_b1_sintetico_gravado_pelo_save_bundle_prevê_sem_nan(tmp_path):
    from dengue_sinan.baselines_final import B1Final  # importar registra o tipo b1

    treino = _quadro(2022, n=300)
    treino["y"] = (np.arange(300) % 9 == 0).astype("int8")
    modelo = baselines.ajustar_b1(treino)
    pasta = artifacts.save_bundle(B1Final(modelo=modelo, limiar=0.01), tmp_path / "b1_final",
                                  METADADOS_SINTETICOS)
    obj = artifacts.load_bundle(pasta)
    bloco = _quadro(2022, n=50)
    p, est = pp.prever_bloco("b1_main", obj, bloco)
    pp.validar_p("b1_main", p, None)
    assert np.allclose(p, obj.modelo.predict_proba(bloco[baselines.COLUNAS_B1])[:, 1])


# ------------------------------------------------------------------ conformidade (R3, R7)
def test_correcao_de_desbalanceamento_so_com_valor_que_corrige():
    achados = pp.correcao_de_desbalanceamento({
        "xgb__scale_pos_weight": 3.0, "clf__class_weight": None, "x": 1,
        "clf__is_unbalance": False, "outro__pos_weight": 1.0,
    })
    assert achados == {"xgb__scale_pos_weight": "3.0"}


def test_checar_dicionario_lista_o_que_falta():
    assert pp.checar_dicionario(["a", "b"], ["a", "c"]) == ["b"]
    assert pp.checar_dicionario(["a"], ["a"]) == []


# ------------------------------------------------------------------ integração de fumaça (2022)
@pytest.mark.skipif(not AMOSTRA_2022.is_file(), reason="amostra de 2022 ausente (smoke_2022)")
def test_fumaca_2022_e1_b2_e_pulo_de_b0_b1(tmp_path, sem_porta, capsys):
    """Encanamento sem 2024 e 2025 e sem métrica: E1 real, B2 e o pulo de B0 e B1 (se ausentes)."""
    saida = tmp_path / "out"
    rc = pp.main(["--entrada", str(AMOSTRA_2022), "--saida-dir", str(saida),
                  "--modelos", "e1_main", "b0_main", "b1_main", "b2_regra"])
    assert rc == 0
    erro = capsys.readouterr().err
    resumo = json.loads((saida / "prever_projeto_2022.resumo.json").read_text(encoding="utf-8"))
    modelos = resumo["modelos"]

    for mid in ("b0_main", "b1_main"):
        arquivo = RAIZ / pp.modelo_do_manifesto(_manifesto(), mid)["artefato"]["caminho"]
        if arquivo.is_file():
            assert modelos[mid]["status"] == "ok"
        else:
            assert modelos[mid]["status"] == "ausente"
            assert f"AVISO {mid}" in erro
            assert not (saida / f"p_{mid}_2022.parquet").exists()

    assert modelos["b2_regra"]["status"] == "ok"
    e1 = pd.read_parquet(saida / "p_e1_main_2022.parquet")
    assert e1["ANO"].eq(2022).all()
    assert e1["LINHA"].is_unique and len(e1) == 5000
    assert e1.loc[~e1["estimavel"], "p"].isna().all()
    assert e1.loc[e1["estimavel"], "p"].notna().all()
    b2 = pd.read_parquet(saida / "p_b2_regra_2022.parquet")
    assert b2["p"].isin([0.0, 1.0]).all() and not b2["p"].isna().any()
    assert b2["ANO"].eq(2022).all()


@pytest.mark.skipif(not AMOSTRA_2022.is_file(), reason="amostra de 2022 ausente (smoke_2022)")
def test_conformidade_so_nomes_parametros_e_agregados(tmp_path, sem_porta):
    saida = tmp_path / "out"
    pp.main(["--entrada", str(AMOSTRA_2022), "--saida-dir", str(saida),
             "--modelos", "e1_main", "b2_regra"])
    conf = json.loads((saida / "p_e1_main_2022.conformidade.json").read_text(encoding="utf-8"))
    assert conf["previsoes"]["linhas"] == 5000
    assert {"estimaveis", "nao_estimaveis", "fracao_nao_estimavel"} <= set(conf["previsoes"])
    assert conf["variaveis_fora_do_dicionario_do_projeto"] == []
    # R7: nenhum valor por linha no JSON; listas são nomes de variáveis ou de pares, nunca linhas
    def _listas(valor):
        if isinstance(valor, list):
            yield valor
            for item in valor:
                yield from _listas(item)
        elif isinstance(valor, dict):
            for item in valor.values():
                yield from _listas(item)

    assert all(len(lista) <= 30 for lista in _listas(conf))
