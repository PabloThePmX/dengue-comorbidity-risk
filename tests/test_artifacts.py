"""Testes da serialização de artefatos (T-3.6, FR-12, NFR-03, R7).

Nada aqui lê `data/`: os ajustes são sintéticos e os manifestos são de mentira, em `tmp_path`.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from dengue_sinan import artifacts, descriptive, explain, verify
from dengue_sinan.artifacts import ArtefatoInvalido, E1Leve, Tipo
from dengue_sinan.profiling import COMORBIDADES

SEED = 20261103
N = 40_000
RAIZ = Path(__file__).resolve().parents[1]
PERFIS = [
    (40, "F", 0, ()),
    (25, "M", 0, ("DIABETES",)),
    (63, "F", 0, ("HIPERTENSA", "DIABETES")),
    (30, "F", 1, ("HEMATOLOG", "RENAL")),
    (72, "M", 0, ("HEPATOPAT", "HIPERTENSA", "AUTO_IMUNE")),
    (12, "I", 0, ("ACIDO_PEPT",)),
]
PARES_INVENTADOS = [("DIABETES", "RENAL"), ("HIPERTENSA", "DIABETES")]
NOS_INVENTADOS = {"idade": [0.0, 15.0, 30.0, 45.0, 65.0, 90.0],
                  "idade_interacao": [0.0, 30.0, 60.0, 90.0]}

BLOQUEIO_STATSMODELS = """
import sys
class _Bloqueio:
    def find_spec(self, nome, caminho=None, alvo=None):
        if nome.split('.')[0] == 'statsmodels':
            raise ImportError('statsmodels bloqueado nesta prova')
        return None
sys.meta_path.insert(0, _Bloqueio())
"""


def _cfg(tmp_path: Path) -> dict:
    return {
        "seed": SEED,
        "anos_dev": [2022, 2023],
        "ano_teste": 2024,
        "supressao_min_celula": 10,
        "caminhos": {"dados": str(tmp_path / "data"), "relatorios": str(tmp_path / "reports"),
                     "modelos": str(tmp_path / "models")},
        "ambiente": {"gpu": None, "ram_min_gib": 12},
    }


def _manifesto(cfg: dict) -> None:
    """Manifesto de mentira com os hashes dos dois anos (só o formato importa aqui)."""
    pasta = Path(cfg["caminhos"]["dados"])
    pasta.mkdir(parents=True, exist_ok=True)
    manifesto = {
        str(ano): {"sha256_dbc": f"{ano}" * 16, "sha256_parquet": f"{ano + 1}" * 16}
        for ano in cfg["anos_dev"]
    }
    (pasta / "manifest.json").write_text(json.dumps(manifesto), encoding="utf-8")


def _metadados(cfg: dict, metricas: dict | None = None) -> dict:
    _manifesto(cfg)
    return {
        "config": cfg,
        "dados": artifacts.hashes_dados(cfg),
        "data_treino": "2026-11-16T12:00:00+00:00",
        "metricas_validacao": metricas or {"aviso": artifacts.AVISO_E1, "n_casos": 1000},
        "features": list(explain.CHAVES_PADRAO),
    }


def _populacao_sintetica(n: int = N) -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    idade = rng.uniform(0, 90, n)
    sexo = rng.choice(["F", "M", "I"], size=n, p=[0.5, 0.495, 0.005])
    gestante = ((sexo == "F") & (rng.uniform(size=n) < 0.05)).astype("int8")
    df = pd.DataFrame({"ANO": rng.choice([2022, 2023], size=n), "idade_anos": idade,
                       "sexo": sexo, "gestante": gestante})
    eta = -5.5 + 0.03 * idade + 0.2 * (sexo == "M") + 0.6 * gestante
    for c in COMORBIDADES:
        u = rng.uniform(size=n)
        valor = np.where(u < 0.01, "Ausente", np.where(u < 0.31, "Sim", "Não"))
        df[c] = pd.Categorical(valor, categories=["Sim", "Não", "Ausente"])
        eta = eta + 0.6 * (valor == "Sim")
    eta = eta + 0.5 * ((df["DIABETES"] == "Sim") & (df["RENAL"] == "Sim"))
    df["y"] = (rng.uniform(size=n) < 1 / (1 + np.exp(-eta))).astype("int8")
    return df


@pytest.fixture(scope="module")
def ajuste_sintetico(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("artefatos")
    cfg = _cfg(tmp)
    df = _populacao_sintetica()
    caminho = Path(cfg["caminhos"]["dados"]) / "descritiva" / "pares_comorbidades.csv"
    caminho.parent.mkdir(parents=True, exist_ok=True)
    descriptive.pair_event_counts(df).to_csv(caminho, index=False)
    return cfg, explain.ajustar_e1(cfg, df)


def _e1_inventado(seed: int = 7) -> E1Leve:
    """E1 com coeficientes e covariância inventados, com a mesma estrutura do E1 real."""
    linha = pd.DataFrame([{"idade_anos": 40.0, "sexo": "F", "gestante": 0,
                           **{c: "Não" for c in COMORBIDADES}}])
    colunas = list(explain.matriz_de_desenho(linha, NOS_INVENTADOS, PARES_INVENTADOS).columns)
    rng = np.random.default_rng(seed)
    k = len(colunas)
    a = rng.normal(size=(k, k))
    return E1Leve(
        params=rng.normal(0, 0.3, k),
        cov=a @ a.T / k * 1e-4 + 1e-5 * np.eye(k),
        colunas=colunas,
        nos=NOS_INVENTADOS,
        pares_incluidos=PARES_INVENTADOS,
        pares_excluidos=[("RENAL", "HIPERTENSA")],
        idade_referencia=explain.IDADE_REFERENCIA,
        features=list(explain.CHAVES_PADRAO),
    )


def _diferenca_maxima(a: dict, b: dict) -> float:
    return max(abs(float(a[k]) - float(b[k])) for k in a)


def _comparar(original, carregado, perfis=PERFIS) -> float:
    """Maior diferença absoluta entre risco, IC e razão de risco dos perfis."""
    diferencas = []
    for idade, sexo, gestante, comorbidades in perfis:
        diferencas.append(_diferenca_maxima(
            explain.risco_perfil(original, idade, sexo, gestante, comorbidades),
            explain.risco_perfil(carregado, idade, sexo, gestante, comorbidades)))
        diferencas.append(_diferenca_maxima(
            explain.razao_de_risco(original, idade, sexo, gestante, comorbidades),
            explain.razao_de_risco(carregado, idade, sexo, gestante, comorbidades)))
    return max(diferencas)


# --- Ida e volta (o "Pronto quando") -----------------------------------------------------------

def test_ida_e_volta_com_coeficientes_inventados_reproduz_risco_ic_e_razao(tmp_path):
    e1 = _e1_inventado()
    carregado = artifacts.load_bundle(artifacts.save_bundle(
        e1, tmp_path / "e1", _metadados(_cfg(tmp_path))))
    assert isinstance(carregado, E1Leve)
    assert _comparar(e1, carregado) < 1e-9
    assert carregado.colunas == e1.colunas
    assert carregado.pares_excluidos == e1.pares_excluidos


def test_ida_e_volta_do_ajuste_sintetico_reproduz_risco_ic_e_razao(ajuste_sintetico, tmp_path):
    cfg, e1 = ajuste_sintetico
    carregado = artifacts.load_bundle(artifacts.save_bundle(
        e1, tmp_path / "e1", _metadados(cfg)))
    assert _comparar(e1, carregado) < 1e-9
    for idade, sexo, gestante, comorbidades in PERFIS:
        original = explain.risco_perfil(e1, idade, sexo, gestante, comorbidades)
        novo = explain.risco_perfil(carregado, idade, sexo, gestante, comorbidades)
        assert novo["ic_inferior"] < novo["risco"] < novo["ic_superior"]
        assert _diferenca_maxima(original, novo) < 1e-9


def test_log_or_por_idade_tambem_reproduz_apos_a_carga(ajuste_sintetico, tmp_path):
    cfg, e1 = ajuste_sintetico
    carregado = artifacts.load_bundle(artifacts.save_bundle(
        e1, tmp_path / "e1", _metadados(cfg)))
    for comorbidade in ("DIABETES", "HIPERTENSA", "RENAL"):
        original = explain.log_or_na_idade(e1, comorbidade, 60)
        novo = explain.log_or_na_idade(carregado, comorbidade, 60)
        assert _diferenca_maxima(original, novo) < 1e-9


# --- Integridade -------------------------------------------------------------------------------

@pytest.mark.parametrize("arquivo", [artifacts.E1_NPZ, artifacts.E1_JSON])
def test_adulterar_um_byte_do_payload_faz_a_carga_falhar(tmp_path, arquivo):
    pasta = artifacts.save_bundle(_e1_inventado(), tmp_path / "e1", _metadados(_cfg(tmp_path)))
    alvo = pasta / artifacts.PASTA_PAYLOAD / arquivo
    dados = bytearray(alvo.read_bytes())
    dados[len(dados) // 2] ^= 0x01  # um bit no meio do arquivo
    alvo.write_bytes(bytes(dados))
    with pytest.raises(ArtefatoInvalido, match="SHA-256"):
        artifacts.load_bundle(pasta)


def test_arquivo_extra_no_payload_faz_a_carga_falhar(tmp_path):
    pasta = artifacts.save_bundle(_e1_inventado(), tmp_path / "e1", _metadados(_cfg(tmp_path)))
    (pasta / artifacts.PASTA_PAYLOAD / "modelo.pickle").write_bytes(b"x")
    with pytest.raises(ArtefatoInvalido, match="diferentes dos declarados"):
        artifacts.load_bundle(pasta)


def test_tipo_de_payload_desconhecido_levanta_erro_claro(tmp_path):
    pasta = artifacts.save_bundle(_e1_inventado(), tmp_path / "e1", _metadados(_cfg(tmp_path)))
    meta = json.loads((pasta / artifacts.NOME_METADATA).read_text(encoding="utf-8"))
    meta["tipo_payload"] = "joblib"
    (pasta / artifacts.NOME_METADATA).write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ArtefatoInvalido, match="tipo de payload desconhecido: 'joblib'"):
        artifacts.load_bundle(pasta)


def test_schema_de_versao_futura_levanta_erro(tmp_path):
    pasta = artifacts.save_bundle(_e1_inventado(), tmp_path / "e1", _metadados(_cfg(tmp_path)))
    meta = json.loads((pasta / artifacts.NOME_METADATA).read_text(encoding="utf-8"))
    meta["schema_version"] = artifacts.SCHEMA_VERSION + 1
    (pasta / artifacts.NOME_METADATA).write_text(json.dumps(meta), encoding="utf-8")
    with pytest.raises(ArtefatoInvalido, match="versão futura"):
        artifacts.load_bundle(pasta)


def test_objeto_sem_tipo_registrado_levanta_erro(tmp_path):
    with pytest.raises(TypeError, match="sem tipo de payload registrado"):
        artifacts.save_bundle({"a": 1}, tmp_path / "x", _metadados(_cfg(tmp_path)))


def test_save_recusa_metadados_sem_campo_obrigatorio_do_fr12(tmp_path):
    metadados = _metadados(_cfg(tmp_path))
    del metadados["data_treino"]
    with pytest.raises(ValueError, match="data_treino"):
        artifacts.save_bundle(_e1_inventado(), tmp_path / "e1", metadados)


def test_save_recusa_campo_reservado_nos_metadados(tmp_path):
    metadados = _metadados(_cfg(tmp_path))
    metadados["schema_version"] = 99
    with pytest.raises(ValueError, match="reservados"):
        artifacts.save_bundle(_e1_inventado(), tmp_path / "e1", metadados)


# --- Metadados (FR-12) -------------------------------------------------------------------------

def test_metadata_traz_todos_os_campos_do_fr12(ajuste_sintetico, tmp_path):
    cfg, e1 = ajuste_sintetico
    pasta = artifacts.save_bundle(e1, tmp_path / "e1", _metadados(cfg))
    meta = artifacts.ler_metadados(pasta)

    assert meta["schema_version"] == artifacts.SCHEMA_VERSION
    assert meta["versao_codigo"]["commit"] == verify.commit_atual()
    assert set(meta["bibliotecas"]) == {"python", "numpy", "pandas", "scipy", "statsmodels",
                                        "scikit-learn"}
    assert meta["bibliotecas"]["statsmodels"] is not None
    assert meta["config"] == cfg
    for ano in ("2022", "2023"):
        assert set(meta["dados"][ano]) == {"sha256_dbc", "sha256_parquet"}
    assert meta["data_treino"] == "2026-11-16T12:00:00+00:00"
    assert "sem validação externa" in meta["metricas_validacao"]["aviso"]
    assert "2024" in meta["metricas_validacao"]["aviso"]
    assert meta["features"] == explain.CHAVES_PADRAO
    assert meta["tipo_payload"] == "e1"
    assert meta["criado_em_utc"].endswith("+00:00")
    assert set(meta["payload"]) == {artifacts.E1_NPZ, artifacts.E1_JSON}
    for nome, sha in meta["payload"].items():
        assert artifacts._sha256(pasta / artifacts.PASTA_PAYLOAD / nome) == sha


def test_hashes_dados_leem_dbc_e_parquet_de_cada_ano(tmp_path):
    cfg = _cfg(tmp_path)
    _manifesto(cfg)
    dados = artifacts.hashes_dados(cfg)
    assert dados["2022"] == {"sha256_dbc": "2022" * 16, "sha256_parquet": "2023" * 16}


# --- Privacidade (NFR-03, R7) ------------------------------------------------------------------

def test_bundle_pequeno_sem_linhas_nem_contagens_pequenas(ajuste_sintetico, tmp_path):
    cfg, e1 = ajuste_sintetico
    pasta = artifacts.save_bundle(e1, tmp_path / "e1", _metadados(cfg))

    tamanho = sum(p.stat().st_size for p in pasta.rglob("*") if p.is_file())
    assert tamanho < 1_000_000

    k = len(e1.colunas)
    with np.load(pasta / artifacts.PASTA_PAYLOAD / artifacts.E1_NPZ) as npz:
        for nome in npz.files:
            arranjo = npz[nome]
            assert arranjo.size <= k * k, nome  # só parâmetros e covariância, nada por linha
            assert max(arranjo.shape) <= k

    texto = (pasta / artifacts.NOME_METADATA).read_text(encoding="utf-8")
    texto += (pasta / artifacts.PASTA_PAYLOAD / artifacts.E1_JSON).read_text(encoding="utf-8")
    assert "eventos_por_termo" not in texto
    assert artifacts.inteiros_pequenos(artifacts.ler_metadados(pasta)) == []
    descricao = json.loads((pasta / artifacts.PASTA_PAYLOAD / artifacts.E1_JSON).read_text(
        encoding="utf-8"))
    assert artifacts.inteiros_pequenos(descricao) == []


def test_verificador_de_contagens_pequenas_acusa_um_9_escondido():
    assert artifacts.inteiros_pequenos({"a": {"eventos": 9}}) == [("a", "eventos")]
    assert artifacts.inteiros_pequenos({"config": {"seed": 3}, "n": 10}) == []
    assert artifacts.inteiros_pequenos({"graus_de_liberdade": {"idade": 5}}) == []


# --- Carga sem statsmodels (demo) --------------------------------------------------------------

def _rodar_sem_statsmodels(codigo: str, *args: str) -> subprocess.CompletedProcess:
    ambiente = {**os.environ, "PYTHONPATH": str(RAIZ / "src")}
    return subprocess.run(
        [sys.executable, "-c", BLOQUEIO_STATSMODELS + codigo, *args],
        capture_output=True, text=True, timeout=120, env=ambiente, cwd=RAIZ,
    )


def test_bloqueio_de_statsmodels_realmente_bloqueia():
    # Controle: sem isto, a prova abaixo não provaria nada.
    resultado = _rodar_sem_statsmodels("import statsmodels.api\n")
    assert resultado.returncode != 0
    assert "statsmodels bloqueado" in resultado.stderr


def test_carga_e_risco_do_e1_funcionam_sem_statsmodels(tmp_path):
    e1 = _e1_inventado()
    pasta = artifacts.save_bundle(e1, tmp_path / "e1", _metadados(_cfg(tmp_path)))
    codigo = """
import json, sys
from dengue_sinan import artifacts, explain
e1 = artifacts.load_bundle(sys.argv[1])
r = explain.risco_perfil(e1, 40, 'F', 0, ('DIABETES', 'RENAL'))
rr = explain.razao_de_risco(e1, 40, 'F', 0, ('DIABETES', 'RENAL'))
print(json.dumps({'risco': r['risco'], 'ic': r['ic_inferior'], 'rr': rr['razao'],
                  'statsmodels_no_processo': 'statsmodels' in sys.modules}))
"""
    resultado = _rodar_sem_statsmodels(codigo, str(pasta))
    assert resultado.returncode == 0, resultado.stderr
    saida = json.loads(resultado.stdout.strip().splitlines()[-1])
    assert saida["statsmodels_no_processo"] is False
    esperado = explain.risco_perfil(e1, 40, "F", 0, ("DIABETES", "RENAL"))
    assert abs(saida["risco"] - esperado["risco"]) < 1e-9
    assert abs(saida["ic"] - esperado["ic_inferior"]) < 1e-9


# --- Ponto de extensão (M1) --------------------------------------------------------------------

def test_registrar_tipo_novo_faz_ida_e_volta_e_nome_repetido_falha(tmp_path, monkeypatch):
    monkeypatch.setattr(artifacts, "_TIPOS", dict(artifacts._TIPOS))

    def salvar(obj, pasta, metadados):
        (pasta / "dado.json").write_text(json.dumps(obj), encoding="utf-8")
        return ["dado.json"]

    def carregar(pasta):
        return json.loads((pasta / "dado.json").read_text(encoding="utf-8"))

    tipo = Tipo(nome="teste_lista", reconhece=lambda o: isinstance(o, list),
                salvar=salvar, carregar=carregar)
    artifacts.registrar_tipo(tipo)
    with pytest.raises(ValueError, match="já registrado"):
        artifacts.registrar_tipo(tipo)
    pasta = artifacts.save_bundle([1, 2, 3], tmp_path / "lista", _metadados(_cfg(tmp_path)))
    assert artifacts.load_bundle(pasta) == [1, 2, 3]
    assert artifacts.ler_metadados(pasta)["tipo_payload"] == "teste_lista"
