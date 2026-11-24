"""Orquestrador da comparação em 2025 (T-8.9): a cadeia inteira em um "mundo" temporário.

O mundo tem um repositório git com o manifesto commitado, worktrees de brinquedo (cada um um repo
git detached, com venv falso), artefatos falsos e dados SINTÉTICOS. Os três scripts de previsão
são stubs que gravam previsões de mentira, mas quem roda é o `comparar_executar` de verdade: porta,
exportador, subprocessos com a variável, alinhamento, métricas, lacre e figuras.

Nenhum dado real é lido; o integrado (fim do arquivo) roda os scripts reais e pula se faltar algo.
"""

import contextlib
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest
import yaml

from dengue_sinan import comparacao_entrada as ce
from dengue_sinan import comparacao_manifesto as cm
from dengue_sinan import comparar as cmp
from dengue_sinan import comparar_executar as cx
from dengue_sinan import comparar_graficos as cg
from dengue_sinan import dataset, guard
from dengue_sinan.config import load_config
from dengue_sinan.profiling import COMORBIDADES, SINAIS

REAMOSTRAS = 20
LINHAS = 800
RAIZ = cx.RAIZ

# Stub dos três scripts: grava p (ANO, LINHA, p; e1 também estimavel) e o JSON de conformidade,
# como os scripts reais. Registra no log (STUB_LOG) a porta e os argumentos; falha se STUB_FALHA
# for o próprio nome do script.
STUB = '''
import argparse, json, os, sys
from pathlib import Path
import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("--entrada", required=True)
ap.add_argument("--saida-dir")
ap.add_argument("--saida")
ap.add_argument("--worktree")
ap.add_argument("--manifesto")
ap.add_argument("--modelos", nargs="*")
a = ap.parse_args()
nome = Path(sys.argv[0]).name
log = os.environ.get("STUB_LOG")
if log:
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps({"script": nome, "porta": os.environ.get("DENGUE_PORTA_COMPARACAO"),
                            "argv": sys.argv[1:]}) + "\\n")
if os.environ.get("STUB_FALHA") == nome:
    print("falha simulada", file=sys.stderr)
    sys.exit(3)
ref = pd.read_parquet(a.entrada, columns=["ANO", "LINHA"])
ano = int(ref["ANO"].iloc[0])
pasta = Path(a.saida_dir) if a.saida_dir else Path(a.saida).parent
ids = a.modelos if a.saida_dir else ["__ID__"]
n = len(ref)
for i, mid in enumerate(ids):
    rng = np.random.default_rng(100 + i)
    p = 0.01 + 0.3 * rng.random(n)
    if mid == "m1_soneca" and os.environ.get("STUB_POUCOS_ALERTAS"):
        p = np.full(n, 0.001)
        p[:2] = 0.9
    quadro = pd.DataFrame({"ANO": ref["ANO"].to_numpy(), "LINHA": ref["LINHA"].to_numpy(), "p": p})
    if mid == "e1_main":
        est = (ref["LINHA"].to_numpy() % 7) != 0
        quadro["p"] = np.where(est, p, np.nan)
        quadro["estimavel"] = est
    nome_p = ("p_" + mid + "_" + str(ano) + ".parquet") if a.saida_dir else Path(a.saida).name
    quadro.to_parquet(pasta / nome_p, index=False)
    conf = {"r3_busca": {"com_correcao_de_desbalanceamento": False},
            "todas_no_dicionario_do_projeto": True,
            "anos_de_treino_dos_metadados": [2022, 2023]}
    (pasta / (Path(nome_p).stem + ".conformidade.json")).write_text(json.dumps(conf),
                                                                  encoding="utf-8")
'''


def _sha(conteudo: bytes) -> str:
    return hashlib.sha256(conteudo).hexdigest()


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", "-c", "user.name=teste", "-c", "user.email=teste@exemplo.invalid",
                    *args], cwd=cwd, check=True, capture_output=True)


def _git_saida(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True,
                          text=True).stdout.strip()


def _commit(cwd: Path, msg: str) -> str:
    _git(cwd, "add", "-A")
    _git(cwd, "commit", "-m", msg)
    return _git_saida(cwd, "rev-parse", "HEAD")


@dataclass
class Mundo:
    cfg: dict
    caminhos: cx.Caminhos
    manifesto: dict
    manifesto_path: Path
    repo: Path
    base: Path
    stubs: Path
    log: Path


@pytest.fixture
def mundo(tmp_path, monkeypatch) -> Mundo:
    monkeypatch.delenv(cx.PORTA_ENV, raising=False)
    monkeypatch.delenv("STUB_FALHA", raising=False)
    stubs = tmp_path / "stubs"
    stubs.mkdir()
    for nome, mid in (("prever_projeto.py", ""), ("prever_soneca.py", "m1_soneca"),
                      ("prever_lora.py", "m1_lora")):
        (stubs / nome).write_text(STUB.replace("__ID__", mid), encoding="utf-8")
    log = tmp_path / "stub.log"
    monkeypatch.setenv("STUB_LOG", str(log))

    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    worktrees, commits, blobs = {}, {}, {}
    for mid, pasta, cam, conteudo in (
            ("m1_soneca", "soneca", "reports/modelo_risco_dengue/artefatos/m1_congelado.joblib",
             b"ARTEFATO-SONECA"),
            ("m1_lora", "lora", "models/m1_final.joblib", b"ARTEFATO-LORA")):
        wt = tmp_path / "_comparacao" / pasta
        wt.mkdir(parents=True)
        _git(wt, "init")
        (wt / cam).parent.mkdir(parents=True, exist_ok=True)
        (wt / cam).write_bytes(conteudo)
        commits[mid] = _commit(wt, f"ramo {pasta}")
        _git(wt, "checkout", "--detach", "-q")
        venv = cx._python_do_venv(wt)
        venv.parent.mkdir(parents=True)
        venv.write_text("venv de teste", encoding="utf-8")
        worktrees[mid] = wt
        blobs[mid] = (cam, conteudo)

    locais = {"m1_main": ("models/m1_final/payload/m1.joblib", b"ARTEFATO-M1"),
              "e1_main": ("models/e1/payload/e1.npz", b"ARTEFATO-E1"),
              "b0_main": ("models/b0_final/payload/b0.json", b"ARTEFATO-B0"),
              "b1_main": ("models/b1_final/payload/b1.joblib", b"ARTEFATO-B1")}
    for cam, conteudo in locais.values():
        (repo / cam).parent.mkdir(parents=True, exist_ok=True)
        (repo / cam).write_bytes(conteudo)

    manifesto = copy.deepcopy(cm.carregar_manifesto())
    for m in manifesto["modelos"]:
        if m["id"] in locais:
            cam, conteudo = locais[m["id"]]
            m["artefato"]["caminho"] = cam
            m["artefato"]["sha256"] = _sha(conteudo)
        if m["id"] in blobs:
            cam, conteudo = blobs[m["id"]]
            m["artefato"]["caminho"] = cam
            m["artefato"]["sha256"] = _sha(conteudo)
            m["origem"]["commit"] = commits[m["id"]]
    manifesto["dados"]["sha256"] = _sha(b"DBC-2025-FALSO")
    manifest_path = repo / "config" / "comparacao" / "manifesto.yaml"
    manifest_path.parent.mkdir(parents=True)
    manifest_path.write_text(yaml.safe_dump(manifesto, allow_unicode=True, sort_keys=False),
                             encoding="utf-8")
    _commit(repo, "manifesto de teste")

    dados = tmp_path / "data"
    (dados / "raw").mkdir(parents=True)
    (dados / "raw" / "DENGBR25.dbc").write_bytes(b"DBC-2025-FALSO")
    caminhos = cx.Caminhos(
        raiz=repo, dados=dados, relatorios=tmp_path / "reports", worktrees=worktrees,
        pythons={"main": Path(sys.executable), **{m: Path(sys.executable) for m in worktrees}},
        scripts={"projeto": stubs / "prever_projeto.py",
                 "m1_soneca": stubs / "prever_soneca.py",
                 "m1_lora": stubs / "prever_lora.py"})
    cfg = load_config()
    cx.gerar_populacao_sintetica(cx.cfg_com_caminhos(cfg, caminhos), 2025, LINHAS,
                                 seed=cfg["seed"])
    return Mundo(cfg=cfg, caminhos=caminhos, manifesto=manifesto, manifesto_path=manifest_path,
                 repo=repo, base=tmp_path, stubs=stubs, log=log)


def _rodar(m: Mundo, **kw) -> dict:
    return cx.executar(m.cfg, kw.pop("manifesto", m.manifesto), m.caminhos,
                       caminho_manifesto=kw.pop("caminho_manifesto", m.manifesto_path),
                       processos=1, reamostras=REAMOSTRAS, **kw)


def _falhas_por_nome(checagens) -> set[str]:
    return {c.nome for c in checagens if not c.passou}


def _registro(m: Mundo) -> list[dict]:
    if not m.log.exists():
        return []
    return [json.loads(linha) for linha in m.log.read_text(encoding="utf-8").splitlines()]


# --- Checagens pré-execução ---------------------------------------------------------------------

def test_mundo_limpo_passa_em_todas_as_checagens(mundo):
    checagens = cx.checagens_pre_execucao(mundo.cfg, mundo.manifesto, mundo.caminhos,
                                          caminho_manifesto=mundo.manifesto_path)
    assert checagens[0].nome == "lacre_ausente"  # o lacre é o primeiro (R2)
    assert not cx._falhas(checagens), [c.como_dict() for c in checagens]


def test_lacre_presente_reprova_e_vem_primeiro(mundo):
    pasta = mundo.caminhos.agregados
    pasta.mkdir(parents=True)
    (pasta / cx.ARQ_LACRE).write_text("{}", encoding="utf-8")
    checagens = cx.checagens_pre_execucao(mundo.cfg, mundo.manifesto, mundo.caminhos,
                                          caminho_manifesto=mundo.manifesto_path)
    assert checagens[0].nome == "lacre_ausente" and not checagens[0].passou


def test_manifesto_alterado_sem_commit_recusa(mundo):
    mundo.manifesto_path.write_text(mundo.manifesto_path.read_text(encoding="utf-8") + "\n# x\n",
                                    encoding="utf-8")
    checagens = cx.checagens_pre_execucao(mundo.cfg, mundo.manifesto, mundo.caminhos,
                                          caminho_manifesto=mundo.manifesto_path)
    assert "arvore_git_limpa" in _falhas_por_nome(checagens)
    with pytest.raises(cx.ErroChecagem):
        _rodar(mundo)
    assert _registro(mundo) == []  # nenhum script rodou


def test_manifesto_sem_commit_recusa(mundo):
    sem_commit = mundo.repo / "config" / "comparacao" / "outro.yaml"
    sem_commit.write_text("x: 1\n", encoding="utf-8")
    checagens = cx.checagens_pre_execucao(mundo.cfg, mundo.manifesto, mundo.caminhos,
                                          caminho_manifesto=sem_commit)
    assert "manifesto_commitado_ancestral_do_head" in _falhas_por_nome(checagens)


def test_sha_de_artefato_local_divergente_recusa(mundo):
    (mundo.repo / "models/m1_final/payload/m1.joblib").write_bytes(b"ADULTERADO")
    with pytest.raises(cx.ErroChecagem) as erro:
        _rodar(mundo)
    assert "sha256_local:m1_main" in str(erro.value)


def test_sha_de_blob_de_branch_divergente_recusa(mundo):
    manifesto = copy.deepcopy(mundo.manifesto)
    for m in manifesto["modelos"]:
        if m["id"] == "m1_soneca":
            m["artefato"]["sha256"] = _sha(b"OUTRO")
    checagens = cx.checagens_pre_execucao(mundo.cfg, manifesto, mundo.caminhos,
                                          caminho_manifesto=mundo.manifesto_path)
    assert "sha256_blob:m1_soneca" in _falhas_por_nome(checagens)


def test_worktree_fora_do_commit_do_manifesto_recusa(mundo):
    manifesto = copy.deepcopy(mundo.manifesto)
    for m in manifesto["modelos"]:
        if m["id"] == "m1_lora":
            m["origem"]["commit"] = "0" * 40
    checagens = cx.checagens_pre_execucao(mundo.cfg, manifesto, mundo.caminhos,
                                          caminho_manifesto=mundo.manifesto_path)
    assert "worktree:m1_lora" in _falhas_por_nome(checagens)


def test_worktree_sem_venv_proprio_recusa(mundo):
    cx._python_do_venv(mundo.caminhos.worktrees["m1_soneca"]).unlink()
    checagens = cx.checagens_pre_execucao(mundo.cfg, mundo.manifesto, mundo.caminhos,
                                          caminho_manifesto=mundo.manifesto_path)
    assert "worktree:m1_soneca" in _falhas_por_nome(checagens)


def test_dbc_de_2025_com_sha_divergente_recusa(mundo):
    manifesto = copy.deepcopy(mundo.manifesto)
    manifesto["dados"]["sha256"] = _sha(b"OUTRO")
    checagens = cx.checagens_pre_execucao(mundo.cfg, manifesto, mundo.caminhos,
                                          caminho_manifesto=mundo.manifesto_path)
    assert "sha256_dbc_2025" in _falhas_por_nome(checagens)


def test_ano_do_config_diferente_do_manifesto_recusa(mundo):
    cfg = copy.deepcopy(mundo.cfg)
    cfg["ano_comparacao"] = 2026
    checagens = cx.checagens_pre_execucao(cfg, mundo.manifesto, mundo.caminhos,
                                          caminho_manifesto=mundo.manifesto_path)
    assert "ano_comparacao_do_config_igual_ao_manifesto" in _falhas_por_nome(checagens)


def test_porta_definida_no_ambiente_do_processo_recusa(mundo, monkeypatch):
    monkeypatch.setenv(cx.PORTA_ENV, "1")
    checagens = cx.checagens_pre_execucao(mundo.cfg, mundo.manifesto, mundo.caminhos,
                                          caminho_manifesto=mundo.manifesto_path)
    assert "porta_de_ambiente_fechada" in _falhas_por_nome(checagens)


def test_ensaio_nao_aplica_git_nem_dbc_real(mundo):
    (mundo.repo / "sujeira.txt").write_text("não commitado", encoding="utf-8")
    checagens = cx.checagens_pre_execucao(mundo.cfg, mundo.manifesto, mundo.caminhos,
                                          caminho_manifesto=mundo.manifesto_path, ensaio=True)
    nomes = {c.nome for c in checagens}
    assert "arvore_git_limpa" not in nomes and "sha256_dbc_2025" not in nomes
    assert not cx._falhas(checagens)


# --- Execução ----------------------------------------------------------------------------------

def test_execucao_completa_grava_agregados_lacre_figuras_e_relatorio(mundo):
    resumo = _rodar(mundo)
    agregados = mundo.caminhos.agregados
    lacre = json.loads((agregados / cx.ARQ_LACRE).read_text(encoding="utf-8"))
    assert resumo["passou"] is True
    assert lacre["aviso"] == cx.AVISO_LACRE
    assert lacre["status"] == cx.CONCLUIDO and lacre["sha256_entrada"]
    assert lacre["sha256_metricas"] == _sha((agregados / "metricas.json").read_bytes())
    assert lacre["sha256_dbc"] == _sha(b"DBC-2025-FALSO")
    assert set(lacre["sha256_previsoes"]) == {m["id"] for m in mundo.manifesto["modelos"]}
    assert len(list(agregados.glob("*.png"))) == len(cg.FIGURAS)
    relatorio = json.loads((mundo.caminhos.verificacao / "T-8.11.json").read_text("utf-8"))
    assert relatorio["tarefa"] == "T-8.11" and relatorio["passou"] is True
    assert relatorio["hash_dados"] == {"2025": _sha(b"DBC-2025-FALSO")}


def test_segunda_execucao_falha_antes_de_qualquer_leitura(mundo, monkeypatch):
    _rodar(mundo)
    chamadas = []
    monkeypatch.setattr(ce, "exportar_entrada", lambda *a, **k: chamadas.append(a))
    with pytest.raises(cx.ErroExecucao, match="única"):
        _rodar(mundo)
    assert chamadas == []


def test_variavel_da_porta_so_existe_no_subprocesso(mundo):
    assert cx.PORTA_ENV not in os.environ
    _rodar(mundo)
    assert cx.PORTA_ENV not in os.environ  # o processo do orquestrador não recebeu a porta
    registro = _registro(mundo)
    assert [r["script"] for r in registro] == ["prever_projeto.py", "prever_soneca.py",
                                               "prever_lora.py"]
    assert all(r["porta"] == "1" for r in registro)


@pytest.mark.parametrize("falhante,ja_rodaram", [
    ("prever_projeto.py", []),
    ("prever_soneca.py", ["prever_projeto.py"]),
    ("prever_lora.py", ["prever_projeto.py", "prever_soneca.py"]),
])
def test_script_que_falha_antes_das_metricas_nao_deixa_lacre_nem_agregados(
        mundo, monkeypatch, falhante, ja_rodaram):
    monkeypatch.setenv("STUB_FALHA", falhante)
    with pytest.raises(cx.ErroExecucao, match=falhante.replace(".py", "")):
        _rodar(mundo)
    assert cx.PORTA_ENV not in os.environ  # a falha no meio não vaza a porta
    agregados = mundo.caminhos.agregados
    assert not (agregados / cx.ARQ_LACRE).exists()
    assert not any((agregados / nome).exists() for nome in cx.ARQS_AGREGADOS)
    assert [r["script"] for r in _registro(mundo)] == ja_rodaram + [falhante]
    # sem lacre, uma nova tentativa é permitida (nada foi aceito)
    monkeypatch.delenv("STUB_FALHA")
    assert _rodar(mundo)["passou"] is True


def test_so_graficos_exige_lacre_e_hash_igual_e_nao_abre_a_porta(mundo, monkeypatch):
    with pytest.raises(cx.ErroExecucao, match="sem LACRE"):
        cx.regenerar_graficos(mundo.caminhos)
    _rodar(mundo)
    chamadas = []
    monkeypatch.setattr(ce, "exportar_entrada", lambda *a, **k: chamadas.append(a))
    figuras = cx.regenerar_graficos(mundo.caminhos)
    assert len(figuras) == len(cg.FIGURAS) and chamadas == []
    metricas = mundo.caminhos.agregados / "metricas.json"
    metricas.write_text(metricas.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(cx.ErroExecucao, match="não bate"):
        cx.regenerar_graficos(mundo.caminhos)


def test_nada_de_dados_entra_no_repositorio(mundo):
    _rodar(mundo)
    assert _git_saida(mundo.repo, "status", "--porcelain") == ""
    assert "parquet" not in _git_saida(mundo.repo, "ls-files")


def test_2024_nunca_entra_nas_chamadas(mundo, monkeypatch):
    anos = []
    original = ce.exportar_entrada

    def espiao(cfg, ano, destino, **kw):
        anos.append(ano)
        return original(cfg, ano, destino, **kw)

    monkeypatch.setattr(ce, "exportar_entrada", espiao)
    _rodar(mundo)
    assert anos == [2025]
    # só os nomes dos arquivos (o caminho do tmp_path contém o nome do teste, com "2024")
    nomes = [Path(arg).name for r in _registro(mundo) for arg in r["argv"]]
    assert nomes and not any("2024" in nome for nome in nomes)


def test_sem_confirmo_a_execucao_real_recusa_sem_ler(mundo, monkeypatch, capsys):
    monkeypatch.setattr(cx, "load_config", lambda: mundo.cfg)
    monkeypatch.setattr(cx, "caminhos_padrao", lambda cfg, **kw: mundo.caminhos)
    monkeypatch.setattr(cx, "executar", lambda *a, **k: pytest.fail("não deveria executar"))
    assert cx.main(["--manifesto", str(mundo.manifesto_path)]) == 2
    assert cx.CONFIRMO in capsys.readouterr().err


# --- Ensaio ------------------------------------------------------------------------------------

def test_ensaio_roda_a_cadeia_em_tmp_com_dados_sinteticos(mundo, tmp_path):
    manifesto, yaml_ensaio, caminhos, excluidos = cx.preparar_ensaio(
        mundo.cfg, mundo.manifesto_path, mundo.caminhos, tmp_path / "ensaio", linhas=LINHAS)
    assert excluidos == []
    resumo = cx.executar(mundo.cfg, manifesto, caminhos, caminho_manifesto=yaml_ensaio,
                         ensaio=True, processos=1, reamostras=REAMOSTRAS)
    assert resumo["passou"] is True and resumo["ensaio"] is True
    assert (caminhos.agregados / cx.ARQ_LACRE).is_file()
    lacre = json.loads((caminhos.agregados / cx.ARQ_LACRE).read_text(encoding="utf-8"))
    assert lacre["sha256_dbc"] is None  # ensaio: sem o .dbc real
    relatorio = json.loads((caminhos.verificacao / "T-8.9.json").read_text(encoding="utf-8"))
    assert relatorio["tarefa"] == "T-8.9" and relatorio["hash_dados"] == {}
    assert not (mundo.repo / "reports").exists()  # o projeto não recebe nada do ensaio


def test_ensaio_pula_modelo_local_sem_artefato_e_real_recusa(mundo, tmp_path):
    (mundo.repo / "models/b0_final/payload/b0.json").unlink()
    manifesto, yaml_ensaio, caminhos, excluidos = cx.preparar_ensaio(
        mundo.cfg, mundo.manifesto_path, mundo.caminhos, tmp_path / "ensaio", linhas=LINHAS)
    assert excluidos == ["b0_main"]
    assert "b0_main" not in [m["id"] for m in manifesto["modelos"]]
    resumo = cx.executar(mundo.cfg, manifesto, caminhos, caminho_manifesto=yaml_ensaio,
                         ensaio=True, processos=1, reamostras=REAMOSTRAS)
    assert resumo["passou"] is True
    # na execução real o mesmo artefato ausente reprova o go/no-go
    with pytest.raises(cx.ErroChecagem):
        _rodar(mundo, manifesto=mundo.manifesto)


def test_gerador_sintetico_tem_colunas_do_sinan_e_eventos(tmp_path):
    cfg = {"caminhos": {"dados": str(tmp_path / "data")}}
    caminho = cx.gerar_populacao_sintetica(cfg, 2025, 300, seed=1)
    df = pd.read_parquet(caminho)
    assert len(df) == 300
    assert set(dataset.POPULATION_COLUMNS) <= set(df.columns)
    assert set(COMORBIDADES + SINAIS) <= set(df.columns)
    assert ((df["CLASSI_FIN"] == "12") | (df["EVOLUCAO"] == "2")).sum() > 0


# --- Integração com os worktrees e os scripts reais (pula sem o ambiente) ----------------------

def test_ensaio_com_scripts_e_worktrees_reais(tmp_path):
    cfg = load_config()
    caminhos = cx.caminhos_padrao(cfg)
    faltas = []
    for mid in cx.EXTERNOS:
        if not caminhos.worktrees[mid].is_dir():
            faltas.append(f"worktree {caminhos.worktrees[mid]}")
        elif not cx._python_do_venv(caminhos.worktrees[mid]).is_file():
            faltas.append(f"venv de {mid}")
    if not caminhos.pythons["main"].is_file():
        faltas.append("venv da main")
    if not (RAIZ / "models/m1_final/payload/m1.joblib").is_file():
        faltas.append("artefato do M1")
    if faltas:
        pytest.skip("ensaio com scripts reais pulado: falta " + ", ".join(faltas))
    manifesto, yaml_ensaio, ensaio_caminhos, excluidos = cx.preparar_ensaio(
        cfg, cm.MANIFESTO_PADRAO, caminhos, tmp_path / "ensaio", linhas=cx.TAMANHO_ENSAIO)
    resumo = cx.executar(cfg, manifesto, ensaio_caminhos, caminho_manifesto=yaml_ensaio,
                         ensaio=True, processos=1, reamostras=REAMOSTRAS)
    assert resumo["passou"] is True
    assert (ensaio_caminhos.agregados / "metricas.json").is_file(), excluidos


# --- Lacre em duas fases e --retomar (T-8.9) ----------------------------------------------------

def _lacre(m: Mundo) -> dict:
    return json.loads((m.caminhos.agregados / cx.ARQ_LACRE).read_text(encoding="utf-8"))


def _quebra_escrita(*args, **kwargs):
    raise OSError("falha simulada na escrita dos agregados")


def _porta_proibida(*args, **kwargs):
    raise AssertionError("a porta de 2025 não pode ser aberta")


def _espia_retomada(monkeypatch) -> list:
    """Espia a retomada: a porta abre só em volta da leitura, nunca se lê o .dbc nem o parquet
    bruto, e exportar_entrada não é chamado. Devolve o registro de eventos."""
    eventos: list = []
    original_porta = guard.leitura_do_ano_de_comparacao
    original_calcular = cmp.calcular
    original_sha = cx._sha_arquivo

    @contextlib.contextmanager
    def porta():
        eventos.append("abre porta")
        with original_porta():
            yield
        eventos.append("fecha porta")

    def calcular(*a, **k):
        eventos.append(("calcular, porta aberta:", guard.leitura_da_comparacao_aberta()))
        return original_calcular(*a, **k)

    def sha(caminho, bloco=1 << 20):
        eventos.append(("sha", Path(caminho).name))
        return original_sha(caminho, bloco)

    monkeypatch.setattr(guard, "leitura_do_ano_de_comparacao", porta)
    monkeypatch.setattr(cmp, "calcular", calcular)
    monkeypatch.setattr(cx, "_sha_arquivo", sha)
    monkeypatch.setattr(ce, "exportar_entrada", _porta_proibida)
    return eventos


def _proibe_porta_e_exportacao(monkeypatch) -> None:
    monkeypatch.setattr(guard, "leitura_do_ano_de_comparacao", _porta_proibida)
    monkeypatch.setattr(ce, "exportar_entrada", _porta_proibida)


def _em_previsoes_geradas(m: Mundo, monkeypatch) -> None:
    """Deixa o mundo com o lacre em `previsoes_geradas`: a escrita dos agregados falha."""
    original = cmp.escrever_agregados
    monkeypatch.setattr(cmp, "escrever_agregados", _quebra_escrita)
    with pytest.raises(OSError):
        _rodar(m)
    monkeypatch.setattr(cmp, "escrever_agregados", original)
    assert _lacre(m)["status"] == cx.PREVISOES_GERADAS


def test_falha_na_escrita_deixa_fase_1_e_a_proxima_execucao_falha_sem_ler(mundo, monkeypatch):
    _em_previsoes_geradas(mundo, monkeypatch)
    chamadas = []
    monkeypatch.setattr(ce, "exportar_entrada", lambda *a, **k: chamadas.append(a))
    antes = len(_registro(mundo))
    with pytest.raises(cx.ErroExecucao, match="--retomar"):
        _rodar(mundo)
    assert chamadas == [] and len(_registro(mundo)) == antes  # nada foi lido nem rodado
    with pytest.raises(cx.ErroExecucao, match="previsoes_geradas"):
        cx.regenerar_graficos(mundo.caminhos)  # figuras só com status concluido


def test_ordem_das_fases(mundo, monkeypatch):
    ordem = []
    original_calcular = cmp.calcular
    original_gravar = cx._gravar_lacre
    original_escrever = cmp.escrever_agregados
    original_figuras = cg.gerar_graficos

    def calcular(*a, **k):
        ordem.append("calcular")
        return original_calcular(*a, **k)

    def gravar(caminho, dados):
        ordem.append(f"lacre:{dados['status']}")
        return original_gravar(caminho, dados)

    def escrever(pasta, resultado):
        assert _lacre(mundo)["status"] == cx.PREVISOES_GERADAS  # a fase 0 já está no disco
        ordem.append("agregados")
        return original_escrever(pasta, resultado)

    def figuras(dados, destino):
        ordem.append("figuras")
        return original_figuras(dados, destino)

    monkeypatch.setattr(cmp, "calcular", calcular)
    monkeypatch.setattr(cx, "_gravar_lacre", gravar)
    monkeypatch.setattr(cmp, "escrever_agregados", escrever)
    monkeypatch.setattr(cg, "gerar_graficos", figuras)
    resumo = _rodar(mundo)
    assert ordem == ["lacre:previsoes_geradas", "calcular", "agregados", "lacre:concluido",
                     "figuras"]
    assert resumo["ordem"] == ["agregados", "lacre_concluido", "figuras"]


@pytest.mark.parametrize("quebra", ["atualiza_lacre", "hash_metricas"])
def test_falha_na_fase_2_deixa_metricas_calculadas_e_retomar_conclui(mundo, monkeypatch, quebra):
    original_gravar, original_sha = cx._gravar_lacre, cx._sha_arquivo

    def gravar(caminho, dados):
        if quebra == "atualiza_lacre" and dados.get("status") == cx.CONCLUIDO:
            raise OSError("falha simulada ao atualizar o lacre")
        return original_gravar(caminho, dados)

    def sha(caminho, bloco=1 << 20):
        if quebra == "hash_metricas" and Path(caminho).name == "metricas.json":
            raise OSError("falha simulada no hash de metricas.json")
        return original_sha(caminho, bloco)

    monkeypatch.setattr(cx, "_gravar_lacre", gravar)
    monkeypatch.setattr(cx, "_sha_arquivo", sha)
    with pytest.raises(OSError):
        _rodar(mundo)
    assert _lacre(mundo)["status"] == cx.PREVISOES_GERADAS
    monkeypatch.setattr(cx, "_gravar_lacre", original_gravar)
    monkeypatch.setattr(cx, "_sha_arquivo", original_sha)
    with pytest.raises(cx.ErroExecucao, match="--retomar"):
        _rodar(mundo)
    resumo = cx.retomar(mundo.cfg, mundo.manifesto, mundo.caminhos,
                        caminho_manifesto=mundo.manifesto_path, processos=1)
    assert _lacre(mundo)["status"] == cx.CONCLUIDO and resumo["passou"]


def test_retomar_depois_de_escrita_parcial_da_o_mesmo_metricas_json(mundo, monkeypatch):
    _rodar(mundo)
    referencia = _sha((mundo.caminhos.agregados / "metricas.json").read_bytes())
    shutil.rmtree(mundo.caminhos.agregados)  # uma execução do zero, que vai falhar no meio
    original = cmp.escrever_agregados

    def parcial(pasta, resultado):
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "metricas.json").write_text("{", encoding="utf-8")
        raise OSError("disco cheio (simulado)")

    monkeypatch.setattr(cmp, "escrever_agregados", parcial)
    with pytest.raises(OSError):
        _rodar(mundo)
    monkeypatch.setattr(cmp, "escrever_agregados", original)
    _espia_retomada(monkeypatch)
    resumo = cx.retomar(mundo.cfg, mundo.manifesto, mundo.caminhos,
                        caminho_manifesto=mundo.manifesto_path, processos=1)
    assert _sha((mundo.caminhos.agregados / "metricas.json").read_bytes()) == referencia
    assert _lacre(mundo)["status"] == cx.CONCLUIDO
    assert resumo["passou"] is True


def test_retomar_recusa_previsao_com_sha_divergente(mundo, monkeypatch):
    _em_previsoes_geradas(mundo, monkeypatch)
    previsao = mundo.caminhos.comparacao / "p_m1_main_2025.parquet"
    previsao.write_bytes(previsao.read_bytes() + b"x")
    _proibe_porta_e_exportacao(monkeypatch)
    with pytest.raises(cx.ErroExecucao, match="divergente.*m1_main"):
        cx.retomar(mundo.cfg, mundo.manifesto, mundo.caminhos,
                   caminho_manifesto=mundo.manifesto_path, processos=1)
    assert _lacre(mundo)["status"] == cx.PREVISOES_GERADAS


def test_retomar_recusa_entrada_com_sha_divergente(mundo, monkeypatch):
    _em_previsoes_geradas(mundo, monkeypatch)
    entrada = mundo.caminhos.comparacao / "entrada_2025.parquet"
    entrada.write_bytes(entrada.read_bytes() + b"x")
    _proibe_porta_e_exportacao(monkeypatch)
    with pytest.raises(cx.ErroExecucao, match="divergente.*entrada"):
        cx.retomar(mundo.cfg, mundo.manifesto, mundo.caminhos,
                   caminho_manifesto=mundo.manifesto_path, processos=1)


def test_retomar_recusa_sem_lacre_e_lacre_concluido(mundo, monkeypatch):
    with pytest.raises(cx.ErroExecucao, match="não há LACRE"):
        cx.retomar(mundo.cfg, mundo.manifesto, mundo.caminhos,
                   caminho_manifesto=mundo.manifesto_path)
    _rodar(mundo)
    _proibe_porta_e_exportacao(monkeypatch)
    with pytest.raises(cx.ErroExecucao, match="concluido"):
        cx.retomar(mundo.cfg, mundo.manifesto, mundo.caminhos,
                   caminho_manifesto=mundo.manifesto_path)


def test_variavel_da_porta_nao_vaza_quando_a_cadeia_falha_no_meio(mundo, monkeypatch):
    monkeypatch.setenv("STUB_FALHA", "prever_lora.py")
    with pytest.raises(cx.ErroExecucao):
        _rodar(mundo)
    assert cx.PORTA_ENV not in os.environ


# --- Porta só em volta da leitura no retomar; R7 publicada ponta a ponta (T-8.9) -----------------

def test_retomar_abre_a_porta_so_em_volta_da_leitura_e_nao_le_dbc(mundo, monkeypatch):
    _em_previsoes_geradas(mundo, monkeypatch)
    eventos = _espia_retomada(monkeypatch)
    cx.retomar(mundo.cfg, mundo.manifesto, mundo.caminhos,
               caminho_manifesto=mundo.manifesto_path, processos=1)
    i_porta = eventos.index("abre porta")
    shas_antes = [e[1] for e in eventos[:i_porta] if isinstance(e, tuple) and e[0] == "sha"]
    assert "manifesto.yaml" in shas_antes and "entrada_2025.parquet" in shas_antes
    i_calc = eventos.index(("calcular, porta aberta:", False))
    assert eventos.index("fecha porta") < i_calc  # a porta fecha antes do cálculo
    nomes = [e[1] for e in eventos if isinstance(e, tuple) and e[0] == "sha"]
    assert "DENGBR25.dbc" not in nomes and "dengue_2025.parquet" not in nomes
    assert _lacre(mundo)["status"] == cx.CONCLUIDO


def _checa_r7(mundo) -> None:
    agregados = mundo.caminhos.agregados
    metricas = json.loads((agregados / "metricas.json").read_text(encoding="utf-8"))
    bloco = metricas["no_limiar_proprio"]["m1_soneca"]
    assert bloco["alertas"] == "<10"  # 2 alertas no limiar próprio saem suprimidos (R7)
    assert bloco["recall"]["valor"] is None and bloco["precisao"]["valor"] is None
    assert _lacre(mundo)["status"] == cx.CONCLUIDO
    assert len(list(agregados.glob("*.png"))) == len(cg.FIGURAS)


def test_r7_com_dois_alertas_no_limiar_proprio_passa_na_execucao(mundo, monkeypatch):
    monkeypatch.setenv("STUB_POUCOS_ALERTAS", "1")
    resumo = _rodar(mundo)
    assert resumo["passou"] is True
    _checa_r7(mundo)


def test_r7_com_dois_alertas_no_limiar_proprio_passa_no_retomar(mundo, monkeypatch):
    monkeypatch.setenv("STUB_POUCOS_ALERTAS", "1")
    _em_previsoes_geradas(mundo, monkeypatch)
    resumo = cx.retomar(mundo.cfg, mundo.manifesto, mundo.caminhos,
                        caminho_manifesto=mundo.manifesto_path, processos=1)
    assert resumo["passou"] is True
    _checa_r7(mundo)


# --- Conformidade no lacre, manifesto divergente, calcular quebrado, ensaio no retomar (T-8.9) ---

def test_lacre_de_fase_0_registra_sha_da_conformidade_de_cada_modelo(mundo, monkeypatch):
    _em_previsoes_geradas(mundo, monkeypatch)
    lacre = _lacre(mundo)
    assert set(lacre["sha256_conformidade"]) == {m["id"] for m in mundo.manifesto["modelos"]}
    conf = mundo.caminhos.comparacao / "p_m1_main_2025.conformidade.json"
    assert lacre["sha256_conformidade"]["m1_main"] == _sha(conf.read_bytes())


def test_retomar_recusa_conformidade_alterada_antes_da_porta(mundo, monkeypatch):
    _em_previsoes_geradas(mundo, monkeypatch)
    conf = mundo.caminhos.comparacao / "p_m1_main_2025.conformidade.json"
    conf.write_text(conf.read_text(encoding="utf-8").replace("false", "true"), encoding="utf-8")
    _proibe_porta_e_exportacao(monkeypatch)
    with pytest.raises(cx.ErroExecucao, match="divergente.*conformidade m1_main"):
        cx.retomar(mundo.cfg, mundo.manifesto, mundo.caminhos,
                   caminho_manifesto=mundo.manifesto_path, processos=1)
    assert _lacre(mundo)["status"] == cx.PREVISOES_GERADAS


def test_retomar_recusa_manifesto_divergente_antes_da_porta(mundo, monkeypatch):
    _em_previsoes_geradas(mundo, monkeypatch)
    mundo.manifesto_path.write_text(mundo.manifesto_path.read_text(encoding="utf-8") + "\n# x\n",
                                    encoding="utf-8")
    _proibe_porta_e_exportacao(monkeypatch)
    with pytest.raises(cx.ErroExecucao, match="divergente.*manifesto"):
        cx.retomar(mundo.cfg, mundo.manifesto, mundo.caminhos,
                   caminho_manifesto=mundo.manifesto_path, processos=1)
    assert _lacre(mundo)["status"] == cx.PREVISOES_GERADAS


def test_calcular_quebrado_deixa_previsoes_geradas_e_retomar_conclui(mundo, monkeypatch):
    original = cmp.calcular

    def quebrado(*args, **kwargs):
        raise RuntimeError("calcular quebrado (simulado)")

    monkeypatch.setattr(cmp, "calcular", quebrado)
    with pytest.raises(RuntimeError, match="calcular quebrado"):
        _rodar(mundo)
    assert _lacre(mundo)["status"] == cx.PREVISOES_GERADAS
    assert not (mundo.caminhos.agregados / "metricas.json").exists()
    chamadas = []
    monkeypatch.setattr(ce, "exportar_entrada", lambda *a, **k: chamadas.append(a))
    with pytest.raises(cx.ErroExecucao, match="--retomar"):
        _rodar(mundo)
    assert chamadas == []
    monkeypatch.setattr(cmp, "calcular", original)
    resumo = cx.retomar(mundo.cfg, mundo.manifesto, mundo.caminhos,
                        caminho_manifesto=mundo.manifesto_path, processos=1)
    assert _lacre(mundo)["status"] == cx.CONCLUIDO and resumo["passou"]


def test_retomar_de_ensaio_grava_o_relatorio_T_8_9(mundo, monkeypatch):
    _em_previsoes_geradas(mundo, monkeypatch)
    cx.retomar(mundo.cfg, mundo.manifesto, mundo.caminhos,
               caminho_manifesto=mundo.manifesto_path, processos=1, ensaio=True)
    assert (mundo.caminhos.verificacao / "T-8.9.json").is_file()
    assert not (mundo.caminhos.verificacao / "T-8.11.json").exists()
