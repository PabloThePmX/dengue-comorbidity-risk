"""Orquestrador da comparação em 2025 (T-8.9; D-97, D-98, D-99; R1, R2, R7).

Único módulo que abre a porta do ano de comparação para a cadeia inteira. O `comparar.py` não
importa `guard` (há teste estático); quem abre a porta é este módulo, só em volta da leitura.

Ordem, sem atalho (cada passo só roda se o anterior passou):
1. checagens pré-execução (go/no-go): lacre ausente, manifesto commitado e árvore limpa, SHA-256 dos
   artefatos locais e dos blobs das branches, worktrees isolados, `.dbc` e parquet de 2025, ano do
   config igual ao do manifesto e variável da porta fora do ambiente. Nenhuma linha de dado é lida.
2. abre `guard.leitura_do_ano_de_comparacao()` e exporta a entrada comum para `data/comparacao/`.
3. roda por subprocess, nesta ordem, `prever_projeto` (python do `.venv` da main), `prever_soneca` e
   `prever_lora` (python do venv de cada worktree). `DENGUE_PORTA_COMPARACAO=1` vai só ao ambiente
   do filho; o `os.environ` deste processo não muda.
4. confere as saídas (ANO, LINHA, p; conformidade), alinha com o `y` pela chave (ANO, LINHA) dentro
   da porta, calcula e grava os agregados em `reports/comparacao/`.
5. LACRE em duas fases (escritas atômicas). Fase 0, depois de todas as previsões existirem e
   passarem no formato e ANTES do `calcular`: status `previsoes_geradas`, com entrada, previsões,
   manifesto, artefatos, `.dbc` e semente. Fase 2, depois de `metricas.json` e os `.md`: status
   `concluido` e `sha256_metricas`. Falha de script antes da fase 0 não deixa nada. Depois dela,
   uma nova execução é recusada; `--retomar` recalcula das previsões gravadas (mesma semente,
   mesmo resultado), com a porta aberta só em volta da leitura da entrada e das previsões.
6. gera as figuras só dos agregados e grava `reports/verificacao/T-8.11.json` (D-64).

Se um script falhar antes das métricas, nada foi calculado: não há lacre nem agregados. Uma segunda
execução com o lacre presente falha antes de qualquer leitura (R2).

`--ensaio` roda a mesma cadeia num diretório temporário, com dados SINTÉTICOS no formato do SINAN e
o `ano_comparacao` do config (2025). Não se usa um ano sintético diferente porque a guarda
(`assert_dev_only`) lê o config padrão: um ano como 2099 seria recusado dentro da porta. Os
checks de git e do `.dbc` real não se aplicam ao ensaio e não entram nele.

Exemplos:

    .venv\\Scripts\\python.exe -m dengue_sinan.comparar_executar --so-checagens
    .venv\\Scripts\\python.exe -m dengue_sinan.comparar_executar --ensaio
    .venv\\Scripts\\python.exe -m dengue_sinan.comparar_executar --confirmo-execucao-unica-em-2025
"""

from __future__ import annotations

import argparse
import copy
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from dengue_sinan import comparacao_entrada as ce
from dengue_sinan import comparacao_manifesto as cm
from dengue_sinan import comparar as cmp
from dengue_sinan import comparar_graficos as cg
from dengue_sinan import dataset, guard, verify
from dengue_sinan.config import load_config
from dengue_sinan.profiling import COMORBIDADES, SINAIS

RAIZ = verify.REPO
PORTA_ENV = "DENGUE_PORTA_COMPARACAO"
CONFIRMO = "--confirmo-execucao-unica-em-2025"
TAREFA = "T-8.11"
TAREFA_ENSAIO = "T-8.9"
ARQ_LACRE = "LACRE.json"
ARQ_MANIFESTO_JSON = "manifesto.json"
ARQ_METRICAS = "metricas.json"
ARQS_AGREGADOS = ("metricas.json", "metricas.md", "diferencas.md", "orcamentos.md",
                  "conformidade.md")
AVISO_LACRE = "existir aqui impede nova avaliação (R2)"
MODELOS_DO_PROJETO = ("m1_main", "e1_main", "b0_main", "b1_main", "b2_regra")
# Modelos de outras branches: o script que roda cada um, no python do worktree dele.
EXTERNOS = {"m1_soneca": "prever_soneca.py", "m1_lora": "prever_lora.py"}
# Com menos linhas, a contagem de alertas no limiar próprio cai em 1 a 9 e a R7 do avaliador
# recusa (medido: 800 linhas dão 0 a 2 alertas). 200 mil dá centenas.
TAMANHO_ENSAIO = 200_000
COLUNAS_DA_SAIDA = ("ANO", "LINHA", "p")


class ErroChecagem(RuntimeError):
    """Go/no-go reprovado: nada foi lido de 2025."""

    def __init__(self, falhas: list[Checagem]) -> None:
        self.falhas = falhas
        nomes = "; ".join(f"{c.nome} ({c.detalhe})" for c in falhas)
        super().__init__(f"checagens pré-execução reprovadas: {nomes}")


class ErroExecucao(RuntimeError):
    """Falha durante a cadeia. Antes das métricas, não há lacre nem agregados."""


@dataclass(frozen=True)
class Checagem:
    nome: str
    passou: bool
    detalhe: str

    def como_dict(self) -> dict:
        return {"nome": self.nome, "passou": self.passou, "detalhe": self.detalhe}


@dataclass(frozen=True)
class Caminhos:
    """Tudo que a cadeia toca. Os testes trocam os scripts e os pythons; o CLI usa os padrões.

    `worktrees` e `pythons` são por id de modelo (`m1_soneca`, `m1_lora`); `pythons["main"]` é o
    `.venv` do projeto. Por padrão, `pythons` é o python do venv de cada worktree (o mesmo que a
    checagem (d) confere).
    """

    raiz: Path
    dados: Path
    relatorios: Path
    worktrees: dict[str, Path]
    pythons: dict[str, Path]
    scripts: dict[str, Path]

    @property
    def comparacao(self) -> Path:
        return self.dados / "comparacao"

    @property
    def agregados(self) -> Path:
        return self.relatorios / "comparacao"

    @property
    def verificacao(self) -> Path:
        return self.relatorios / "verificacao"


# --- Caminhos e utilitários ---------------------------------------------------------------------

def _python_do_venv(base: Path) -> Path:
    if os.name == "nt":
        return base / ".venv" / "Scripts" / "python.exe"
    return base / ".venv" / "bin" / "python"


def _absoluto(valor: str, raiz: Path) -> Path:
    caminho = Path(valor)
    return caminho if caminho.is_absolute() else (raiz / caminho).resolve()


def caminhos_padrao(cfg: dict, *, raiz: Path = RAIZ, soneca: Path | None = None,
                    lora: Path | None = None) -> Caminhos:
    """Caminhos reais: worktrees em `..\\_comparacao\\<branch>` ao lado do repositório (D-97 g)."""
    base = raiz.parent / "_comparacao"
    worktrees = {"m1_soneca": Path(soneca) if soneca else base / "soneca",
                 "m1_lora": Path(lora) if lora else base / "lora"}
    pythons = {"main": _python_do_venv(raiz),
               **{mid: _python_do_venv(wt) for mid, wt in worktrees.items()}}
    scripts = {"projeto": raiz / "scripts" / "comparacao" / "prever_projeto.py",
               **{mid: raiz / "scripts" / "comparacao" / nome for mid, nome in EXTERNOS.items()}}
    return Caminhos(raiz=raiz, dados=_absoluto(cfg["caminhos"]["dados"], raiz),
                    relatorios=_absoluto(cfg["caminhos"]["relatorios"], raiz),
                    worktrees=worktrees, pythons=pythons, scripts=scripts)


def cfg_com_caminhos(cfg: dict, caminhos: Caminhos) -> dict:
    """Cópia do config com `dados` e `relatorios` absolutos (os de `caminhos`)."""
    novo = copy.deepcopy(cfg)
    novo["caminhos"]["dados"] = str(caminhos.dados)
    novo["caminhos"]["relatorios"] = str(caminhos.relatorios)
    return novo


def _sha_arquivo(caminho: Path, bloco: int = 1 << 20) -> str:
    sha = hashlib.sha256()
    with open(caminho, "rb") as f:
        for pedaco in iter(lambda: f.read(bloco), b""):
            sha.update(pedaco)
    return sha.hexdigest()


def _git(args: list[str], cwd: Path) -> tuple[int, bytes]:
    """(código, stdout em bytes). Sem git ou sem a pasta, devolve falha, sem levantar."""
    try:
        resultado = subprocess.run(["git", *args], cwd=cwd, capture_output=True, timeout=300,
                                   check=False)
    except (OSError, subprocess.SubprocessError):
        return 1, b""
    return resultado.returncode, resultado.stdout


def _git_texto(args: list[str], cwd: Path) -> str:
    rc, saida = _git(args, cwd)
    return saida.decode("utf-8", errors="replace").strip() if rc == 0 else ""


def _sha_blob(repo: Path, commit: str, caminho: str) -> str | None:
    """SHA-256 do blob `commit:caminho` no git (`git show <ref>:<arquivo>`); None se não existe."""
    rc, conteudo = _git(["show", f"{commit}:{caminho}"], repo)
    return hashlib.sha256(conteudo).hexdigest() if rc == 0 else None


def estado_git(repo: Path) -> dict:
    """HEAD e se a árvore está limpa (registrados no lacre e no relatório)."""
    _, status = _git(["status", "--porcelain"], repo)
    return {"head": _git_texto(["rev-parse", "HEAD"], repo) or "desconhecido",
            "arvore_limpa": not status.strip()}


def _agora() -> str:
    return dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _gravar_json_atomico(caminho: Path, dados: dict) -> Path:
    """Escreve num temporário e troca pelo destino: nunca fica arquivo pela metade."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".tmp")
    texto = json.dumps(dados, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    try:
        temporario.write_text(texto, encoding="utf-8")
        os.replace(temporario, caminho)
    except BaseException:
        temporario.unlink(missing_ok=True)
        raise
    return caminho


# --- Checagens pré-execução (go/no-go) ---------------------------------------------------------

def _checar_git(repo: Path, caminho_manifesto: Path) -> list[Checagem]:
    _, status = _git(["status", "--porcelain"], repo)
    linhas = status.decode("utf-8", errors="replace").strip().splitlines()[:5]
    limpa = not status.strip()
    commit = _git_texto(["log", "-1", "--format=%H", "--", str(caminho_manifesto)], repo)
    ancestral = bool(commit) and _git(["merge-base", "--is-ancestor", commit, "HEAD"],
                                      repo)[0] == 0
    return [
        Checagem("arvore_git_limpa", limpa,
                 "limpa" if limpa else "não limpa: " + " | ".join(linhas)),
        Checagem("manifesto_commitado_ancestral_do_head", ancestral,
                 f"commit {commit[:10]}" if ancestral else "sem commit ancestral do HEAD"),
    ]


def _checar_ano(cfg: dict, manifesto: dict) -> Checagem:
    ano_cfg, ano_manifesto = cfg.get("ano_comparacao"), manifesto.get("ano_comparacao")
    return Checagem("ano_comparacao_do_config_igual_ao_manifesto",
                    ano_cfg is not None and ano_cfg == ano_manifesto,
                    f"config {ano_cfg}, manifesto {ano_manifesto}")


def _checar_artefatos_locais(manifesto: dict, raiz: Path) -> list[Checagem]:
    saida = []
    for m in manifesto["modelos"]:
        art = m["artefato"]
        if art is None or m["origem"]["branch"] != "main":
            continue
        caminho = raiz / art["caminho"]
        nome = f"sha256_local:{m['id']}"
        if not caminho.is_file():
            saida.append(Checagem(nome, False, f"{art['caminho']} ausente"))
            continue
        sha = _sha_arquivo(caminho)
        saida.append(Checagem(nome, sha == art["sha256"],
                              f"{sha[:12]} contra o manifesto {art['sha256'][:12]}"))
    return saida


def _checar_worktree(mid: str, commit: str, caminhos: Caminhos) -> Checagem:
    wt = caminhos.worktrees.get(mid)
    nome = f"worktree:{mid}"
    if wt is None or not wt.is_dir():
        return Checagem(nome, False, f"{wt}: pasta ausente")
    head = _git_texto(["rev-parse", "HEAD"], wt)
    detached = _git(["symbolic-ref", "-q", "HEAD"], wt)[0] != 0
    venv = _python_do_venv(wt)
    problemas = []
    if head != commit:
        problemas.append(f"HEAD {head[:10]} difere do commit do manifesto {commit[:10]}")
    if not detached:
        problemas.append("não está detached")
    if not venv.is_file():
        problemas.append(f"sem o python do venv próprio ({venv})")
    return Checagem(nome, not problemas,
                    "; ".join(problemas) or f"detached em {head[:10]}, venv próprio")


def _checar_branches(manifesto: dict, caminhos: Caminhos) -> list[Checagem]:
    saida = []
    for m in manifesto["modelos"]:
        if m["origem"]["branch"] == "main" or m["artefato"] is None:
            continue
        mid, commit = m["id"], m["origem"].get("commit", "")
        saida.append(_checar_worktree(mid, commit, caminhos))
        wt = caminhos.worktrees.get(mid)
        sha = _sha_blob(wt, commit, m["artefato"]["caminho"]) if wt and wt.is_dir() else None
        declarado = m["artefato"]["sha256"]
        saida.append(Checagem(f"sha256_blob:{mid}", sha == declarado,
                              f"blob {str(sha)[:12]} contra o manifesto {declarado[:12]}"))
    return saida


def _checar_dados(cfg: dict, manifesto: dict, caminhos: Caminhos) -> list[Checagem]:
    dados = manifesto["dados"]
    dbc = caminhos.dados / "raw" / dados["arquivo"]
    saida = []
    if not dbc.is_file():
        saida.append(Checagem("sha256_dbc_2025", False, f"{dbc} ausente"))
    else:
        sha = _sha_arquivo(dbc)  # única leitura de arquivo de 2025 permitida (T-8.9)
        saida.append(Checagem("sha256_dbc_2025", sha == dados["sha256"],
                              f"{sha[:12]} contra o manifesto {dados['sha256'][:12]}"))
    parquet = dataset.parquet_path(cfg_com_caminhos(cfg, caminhos), int(cfg["ano_comparacao"]))
    saida.append(Checagem("parquet_2025_existe", parquet.is_file(), str(parquet)))
    return saida


def checagens_pre_execucao(cfg: dict, manifesto: dict, caminhos: Caminhos, *,
                           caminho_manifesto: Path, ensaio: bool = False) -> list[Checagem]:
    """Go/no-go: lista de checagens (nome, passou, detalhe). Não abre a porta nem lê linha de dado.

    A primeira é o lacre, que vem antes de qualquer outra coisa (R2). No ensaio não entram as
    checagens de git e do `.dbc` real, que não se aplicam a um ano sintético.
    """
    lacre = caminhos.agregados / ARQ_LACRE
    checagens = [Checagem("lacre_ausente", not lacre.exists(),
                          f"{lacre} presente: avaliação já feita (R2)" if lacre.exists()
                          else "ausente")]
    if not ensaio:
        checagens += _checar_git(caminhos.raiz, Path(caminho_manifesto))
    checagens.append(_checar_ano(cfg, manifesto))
    checagens += _checar_artefatos_locais(manifesto, caminhos.raiz)
    checagens += _checar_branches(manifesto, caminhos)
    if not ensaio:
        checagens += _checar_dados(cfg, manifesto, caminhos)
    checagens.append(Checagem("porta_de_ambiente_fechada", PORTA_ENV not in os.environ,
                              f"{PORTA_ENV} não está definida no processo"))
    return checagens


def _falhas(checagens: list[Checagem]) -> list[Checagem]:
    return [c for c in checagens if not c.passou]


# --- Entrada sintética (só para o ensaio) -------------------------------------------------------

def gerar_populacao_sintetica(cfg: dict, ano: int, linhas: int, *, seed: int) -> Path:
    """Parquet do SINAN com `linhas` notificações fictícias, no lugar de `dengue_<ano>.parquet`.

    Todas as colunas de `POPULATION_COLUMNS` são texto, como no arquivo real. Cerca de 8% de
    eventos (grave ou óbito). Nenhum dado real é lido nem copiado.
    """
    rng = np.random.default_rng(seed)
    classi = rng.choice(["10", "11", "12"], size=linhas, p=[0.92, 0.03, 0.05])
    evolucao = np.where(rng.random(linhas) < 0.03, "2", "1")
    idade = rng.integers(0, 91, size=linhas)
    sintomas = np.where(rng.random(linhas) < 0.85, "2", "1")  # comorbidades e sinais raros
    inicio = pd.Timestamp(f"{ano}-01-01") + pd.to_timedelta(rng.integers(0, 300, linhas), "D")
    notificado = inicio + pd.to_timedelta(rng.integers(0, 10, linhas), "D")
    colunas: dict[str, object] = {
        "CLASSI_FIN": classi,
        "EVOLUCAO": evolucao,
        "NU_IDADE_N": [f"4{a:03d}" for a in idade],
        "ANO_NASC": [str(ano - a) for a in idade],
        "DT_SIN_PRI": inicio.strftime("%Y%m%d"),
        "DT_NOTIFIC": notificado.strftime("%Y%m%d"),
        "CS_SEXO": rng.choice(["F", "M"], size=linhas),
        "CS_GESTANT": ["5"] * linhas,
        "CS_RACA": ["4"] * linhas,
        "ID_MN_RESI": ["310620"] * linhas,
        "SG_UF": ["31"] * linhas,
    }
    for campo in (*COMORBIDADES, *SINAIS):
        colunas[campo] = sintomas
    tabela = pa.table({c: pa.array(list(np.asarray(v)), type=pa.string())
                       for c, v in colunas.items()})
    caminho = dataset.parquet_path(cfg, ano)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tabela, caminho)
    return caminho


def preparar_ensaio(cfg: dict, caminho_manifesto: Path, caminhos_reais: Caminhos, tmp: Path, *,
                    linhas: int = TAMANHO_ENSAIO) -> tuple[dict, Path, Caminhos, list[str]]:
    """Monta o ensaio em `tmp`: manifesto sem os modelos locais cujo artefato não existe (B0 e B1
    podem faltar enquanto o Programador não copia), manifesto em YAML, e a entrada sintética.

    Devolve (manifesto do ensaio, caminho do YAML dele, caminhos do ensaio, ids excluídos).
    """
    tmp.mkdir(parents=True, exist_ok=True)
    manifesto = cm.carregar_manifesto(caminho_manifesto, cfg)
    excluidos, modelos = [], []
    for m in manifesto["modelos"]:
        art = m["artefato"]
        if art and m["origem"]["branch"] == "main" and not (caminhos_reais.raiz / art["caminho"]
                                                             ).is_file():
            excluidos.append(m["id"])
            continue
        modelos.append(m)
    manifesto = {**manifesto, "modelos": modelos}
    yaml_ensaio = tmp / "manifesto.yaml"
    yaml_ensaio.write_text(yaml.safe_dump(manifesto, allow_unicode=True, sort_keys=False),
                           encoding="utf-8")
    caminhos = Caminhos(raiz=caminhos_reais.raiz, dados=tmp / "data", relatorios=tmp / "reports",
                        worktrees=caminhos_reais.worktrees, pythons=caminhos_reais.pythons,
                        scripts=caminhos_reais.scripts)
    gerar_populacao_sintetica(cfg_com_caminhos(cfg, caminhos), int(cfg["ano_comparacao"]),
                              linhas, seed=int(cfg["seed"]))
    return manifesto, yaml_ensaio, caminhos, excluidos


# --- Execução -----------------------------------------------------------------------------------

PREVISOES_GERADAS = "previsoes_geradas"
CONCLUIDO = "concluido"
COMANDO_RETOMAR = "python -m dengue_sinan.comparar_executar --retomar"


def _ler_lacre(caminho: Path) -> dict:
    return json.loads(caminho.read_text(encoding="utf-8"))


def _recusar_se_lacre(caminhos: Caminhos, ano: int) -> None:
    """Lacre existente recusa a execução antes de qualquer leitura (R2)."""
    caminho = caminhos.agregados / ARQ_LACRE
    if not caminho.exists():
        return
    try:
        status = _ler_lacre(caminho).get("status")
    except (OSError, ValueError):
        status = None
    if status == PREVISOES_GERADAS:
        raise ErroExecucao(
            f"{caminho} está em '{PREVISOES_GERADAS}': as previsões de {ano} já foram geradas "
            f"e a avaliação não foi concluída (R2). Nada de 2025 é lido nesta tentativa. "
            f"Recuperação: {COMANDO_RETOMAR}")
    raise ErroExecucao(f"{caminho} já existe (status {status!r}): a avaliação de {ano} é única "
                       "(R2). Nada foi lido.")


def _passos(ids: list[str], ano: int, entrada: Path, caminhos: Caminhos,
            caminho_manifesto: Path, manifesto_json: Path) -> list[tuple[str, list[str], str]]:
    """Comandos na ordem (nome, argv, python). Só os modelos que estão no manifesto."""
    passos = []
    projeto = [i for i in ids if i not in EXTERNOS]
    if projeto:
        passos.append((caminhos.scripts["projeto"].name, [
            str(caminhos.scripts["projeto"]), "--entrada", str(entrada),
            "--saida-dir", str(caminhos.comparacao), "--manifesto", str(caminho_manifesto),
            "--modelos", *projeto], str(caminhos.pythons["main"])))
    for mid in EXTERNOS:
        if mid in ids:
            passos.append((caminhos.scripts[mid].name, [
                str(caminhos.scripts[mid]), "--worktree", str(caminhos.worktrees[mid]),
                "--entrada", str(entrada),
                "--saida", str(caminhos.comparacao / f"p_{mid}_{ano}.parquet"),
                "--manifesto", str(manifesto_json)], str(caminhos.pythons[mid])))
    return passos


def _rodar_previsoes(passos, caminhos: Caminhos) -> None:
    # Só o subprocesso recebe a porta; o os.environ deste processo fica como estava (teste).
    ambiente = {**os.environ, PORTA_ENV: "1"}
    for nome, argv, python in passos:
        resultado = subprocess.run([python, *argv], cwd=caminhos.raiz, env=ambiente,
                                   capture_output=True, text=True, encoding="utf-8",
                                   errors="replace", check=False)
        if resultado.returncode != 0:
            trecho = resultado.stderr.strip()[-600:]
            raise ErroExecucao(f"{nome} falhou (código {resultado.returncode}); sem métricas, "
                               f"sem lacre e sem agregados. {trecho}")


def _conferir_saidas(ids: list[str], ano: int, pasta: Path) -> tuple[dict[str, Path], dict]:
    previsoes, conformidade = {}, {}
    for mid in ids:
        p = pasta / f"p_{mid}_{ano}.parquet"
        if not p.is_file():
            raise ErroExecucao(f"{mid}: a saída {p.name} não foi gravada")
        faltam = [c for c in COLUNAS_DA_SAIDA if c not in pq.read_schema(p).names]
        if faltam:
            raise ErroExecucao(f"{mid}: a saída {p.name} não tem as colunas {faltam}")
        conf = pasta / f"p_{mid}_{ano}.conformidade.json"
        if not conf.is_file():
            raise ErroExecucao(f"{mid}: falta o JSON de conformidade {conf.name}")
        previsoes[mid] = p
        conformidade[mid] = json.loads(conf.read_text(encoding="utf-8"))
    return previsoes, conformidade


def _sha_do_artefato(m: dict, caminhos: Caminhos) -> str:
    """SHA-256 real do artefato agora: arquivo local, ou blob do git para as branches."""
    if m["origem"]["branch"] == "main":
        return _sha_arquivo(caminhos.raiz / m["artefato"]["caminho"])
    return _sha_blob(caminhos.worktrees[m["id"]], m["origem"]["commit"],
                     m["artefato"]["caminho"]) or "indisponível"


def _gravar_lacre(caminho: Path, dados: dict) -> Path:
    """Única escrita do LACRE (duas fases). Atômica; os testes observam as chamadas daqui."""
    return _gravar_json_atomico(caminho, dados)


def _lacre_base(*, cfg: dict, ano: int, manifesto: dict, caminhos: Caminhos,
                caminho_manifesto: Path, entrada: Path, previsoes: dict[str, Path],
                sha_dbc: str | None, estado: dict, reamostras: int | None) -> dict:
    """Tudo que o lacre guarda antes das métricas: nada aqui depende do resultado."""
    artefatos = {m["id"]: _sha_do_artefato(m, caminhos) for m in manifesto["modelos"]
                 if m["artefato"] is not None}
    n = int(reamostras if reamostras is not None else manifesto["comparacao"]["bootstrap"])
    return {
        "ano": ano,
        "commit": estado["head"],
        "arvore_limpa": estado["arvore_limpa"],
        "sha256_manifesto": _sha_arquivo(caminho_manifesto),
        "sha256_entrada": _sha_arquivo(entrada),
        "sha256_artefatos": artefatos,
        "sha256_previsoes": {mid: _sha_arquivo(p) for mid, p in previsoes.items()},
        "sha256_dbc": sha_dbc,
        "semente": int(cfg["seed"]),
        "reamostras": n,
        "gravado_em_utc": _agora(),
        "aviso": AVISO_LACRE,
    }


def _gravar_relatorio(caminhos: Caminhos, tarefa: str, checks: list[dict], hash_dados: dict,
                      estado: dict) -> Path:
    relatorio = {
        "tarefa": tarefa,
        "gerado_em": _agora(),
        "commit": estado["head"],
        "ambiente": verify._ambiente_atual(),
        "hash_dados": hash_dados,
        "checks": checks,
        "passou": bool(checks) and all(c["passou"] for c in checks),
    }
    return _gravar_json_atomico(caminhos.verificacao / f"{tarefa}.json", relatorio)


def _fases_de_gravacao(caminhos: Caminhos, base: dict, resultado: dict, *, ensaio: bool) -> dict:
    """Agregados, fase 2 do lacre e figuras. A fase 0 (`previsoes_geradas`) já foi gravada pelo
    chamador.

    Se qualquer escrita falhar daqui em diante, o lacre fica em `previsoes_geradas` e a próxima
    execução é recusada, com o comando de recuperação (`--retomar`).
    """
    ordem: list[str] = []
    cmp.escrever_agregados(caminhos.agregados, resultado)
    ordem.append("agregados")
    metricas = caminhos.agregados / ARQ_METRICAS
    _gravar_lacre(caminhos.agregados / ARQ_LACRE,
                  {**base, "status": CONCLUIDO, "sha256_metricas": _sha_arquivo(metricas)})
    ordem.append("lacre_concluido")
    figuras = cg.gerar_graficos(json.loads(metricas.read_text(encoding="utf-8")),
                                caminhos.agregados)
    ordem.append("figuras")

    principal = resultado["populacoes"]["principal"]
    checks = [
        verify.check("checagens_pre_execucao_passaram", True, True),
        verify.check("alinhamento_sem_falta_nem_sobra", True, True),
        verify.check("lacre_antes_das_figuras", True,
                     ordem == ["agregados", "lacre_concluido", "figuras"]),
        verify.check("figuras_geradas", len(cg.FIGURAS), len(figuras)),
        verify.registro("casos_populacao_principal", principal["casos"]),
        verify.registro("eventos_populacao_principal", principal["eventos"]),
    ]
    ano = int(base["ano"])
    sha_dbc = base["sha256_dbc"]
    hash_dados = {str(ano): sha_dbc} if sha_dbc else {}
    relatorio = _gravar_relatorio(caminhos, TAREFA_ENSAIO if ensaio else TAREFA, checks,
                                  hash_dados, {"head": base["commit"]})
    return {"ano": ano, "ensaio": ensaio, "modelos": list(base["sha256_previsoes"]),
            "lacre": str(caminhos.agregados / ARQ_LACRE), "agregados": str(caminhos.agregados),
            "figuras": [str(f) for f in figuras], "relatorio": str(relatorio), "ordem": ordem,
            "passou": all(c["passou"] for c in checks), "populacao_principal": principal}


def executar(cfg: dict, manifesto: dict, caminhos: Caminhos, *, caminho_manifesto: Path,
             ensaio: bool = False, processos: int = 4, reamostras: int | None = None) -> dict:
    """A cadeia inteira em duas fases do lacre (ver o docstring do módulo).

    Antes da fase 0 (previsões gravadas e conferidas), nada é gravado em `reports/comparacao`:
    uma falha aí não deixa lacre nem agregados. Da fase 0 em diante, o lacre `previsoes_geradas`
    existe antes do `calcular`; uma falha exige `--retomar`, e não uma nova leitura de 2025.
    """
    ano = int(cfg["ano_comparacao"])
    _recusar_se_lacre(caminhos, ano)  # antes de qualquer checagem e de qualquer leitura (R2)
    falhas = _falhas(checagens_pre_execucao(cfg, manifesto, caminhos,
                                            caminho_manifesto=caminho_manifesto, ensaio=ensaio))
    if falhas:
        raise ErroChecagem(falhas)

    cfg_real = cfg_com_caminhos(cfg, caminhos)
    ids = [m["id"] for m in manifesto["modelos"]]
    entrada = caminhos.comparacao / f"entrada_{ano}.parquet"
    estado = estado_git(caminhos.raiz)
    # O SHA-256 do .dbc já foi conferido pela checagem (igual ao do manifesto): 2025 não se relê.
    sha_dbc = None if ensaio else manifesto["dados"]["sha256"]
    with guard.leitura_do_ano_de_comparacao():
        ce.exportar_entrada(cfg_real, ano, entrada, comparacao=True)
    manifesto_json = cm.exportar_json(caminhos.comparacao / ARQ_MANIFESTO_JSON,
                                      caminho_manifesto, cfg_real)
    for mid in ids:  # saídas antigas não podem mascarar um script que falhou agora
        for nome in (f"p_{mid}_{ano}.parquet", f"p_{mid}_{ano}.conformidade.json"):
            (caminhos.comparacao / nome).unlink(missing_ok=True)
    _rodar_previsoes(_passos(ids, ano, entrada, caminhos, caminho_manifesto, manifesto_json),
                     caminhos)
    previsoes, conformidade = _conferir_saidas(ids, ano, caminhos.comparacao)
    base = _lacre_base(cfg=cfg, ano=ano, manifesto=manifesto, caminhos=caminhos,
                       caminho_manifesto=caminho_manifesto, entrada=entrada,
                       previsoes=previsoes, sha_dbc=sha_dbc, estado=estado,
                       reamostras=reamostras)
    # Alinhamento (chave, faltas, sobras, NaN) antes da fase 0: não calcula métrica. Uma falha
    # aqui não deixa lacre; uma falha em calcular, depois da fase 0, é recuperável por --retomar.
    with guard.leitura_do_ano_de_comparacao():
        referencia = pd.read_parquet(entrada, columns=["ANO", "LINHA", "y"])
        guard.assert_dev_only(referencia)
        alinhado = cmp.alinhar(referencia, {mid: cmp.carregar_previsoes(p)
                                            for mid, p in previsoes.items()}, ano=ano)
    # Fase 0: previsões prontas, no formato e alinhadas; a partir daqui nada se perde.
    _gravar_lacre(caminhos.agregados / ARQ_LACRE, {**base, "status": PREVISOES_GERADAS})
    resultado = cmp.calcular(alinhado, manifesto, cfg_real, conformidade, reamostras=reamostras,
                             processos=processos, ano_esperado=ano)
    return _fases_de_gravacao(caminhos, base, resultado, ensaio=ensaio)


def _conformidade_das_previsoes(ids: list[str], ano: int, pasta: Path) -> dict:
    saida = {}
    for mid in ids:
        caminho = pasta / f"p_{mid}_{ano}.conformidade.json"
        if not caminho.is_file():
            raise ErroExecucao(f"--retomar: falta {caminho.name}")
        saida[mid] = json.loads(caminho.read_text(encoding="utf-8"))
    return saida


def retomar(cfg: dict, manifesto: dict, caminhos: Caminhos, *, caminho_manifesto: Path,
            processos: int = 4) -> dict:
    """Retoma a partir do lacre `previsoes_geradas`: confere o SHA-256 da entrada e das previsões
    contra o lacre, recalcula com a mesma semente (mesmo resultado) e fecha a fase 2. Não lê o .dbc
    nem o parquet bruto, não chama `exportar_entrada`, e abre a porta só em volta da leitura."""
    ano = int(cfg["ano_comparacao"])
    caminho_lacre = caminhos.agregados / ARQ_LACRE
    if not caminho_lacre.is_file():
        raise ErroExecucao("--retomar: não há LACRE.json. Sem lacre, nada foi calculado: use a "
                           "execução normal.")
    lacre = _ler_lacre(caminho_lacre)
    if lacre.get("status") == CONCLUIDO:
        raise ErroExecucao("--retomar recusado: o lacre já está 'concluido' (R2). Nada a "
                           "retomar; para as figuras, use --so-graficos.")
    if lacre.get("status") != PREVISOES_GERADAS:
        raise ErroExecucao(f"--retomar recusado: status do lacre desconhecido "
                           f"({lacre.get('status')!r}).")
    if lacre["ano"] != ano or lacre["semente"] != int(cfg["seed"]):
        raise ErroExecucao("--retomar recusado: o lacre é de outro ano ou de outra semente.")

    divergentes = []
    if _sha_arquivo(caminho_manifesto) != lacre["sha256_manifesto"]:
        divergentes.append("manifesto")
    entrada = caminhos.comparacao / f"entrada_{ano}.parquet"
    if not entrada.is_file() or _sha_arquivo(entrada) != lacre["sha256_entrada"]:
        divergentes.append("entrada")
    previsoes = {}
    for mid, sha in lacre["sha256_previsoes"].items():
        p = caminhos.comparacao / f"p_{mid}_{ano}.parquet"
        if not p.is_file() or _sha_arquivo(p) != sha:
            divergentes.append(f"previsão {mid}")
        previsoes[mid] = p
    if divergentes:
        raise ErroExecucao("--retomar recusado: SHA-256 divergente do lacre em "
                           + ", ".join(divergentes) + ". As saídas em data/comparacao não são as "
                           "que foram calculadas; não recalculo.")

    conformidade = _conformidade_das_previsoes(list(previsoes), ano, caminhos.comparacao)
    # A porta abre só em volta da leitura da entrada e das previsões (dados derivados de 2025),
    # depois da conferência de SHA-256 acima. O .dbc e o parquet bruto não são lidos, e
    # exportar_entrada não é chamado.
    with guard.leitura_do_ano_de_comparacao():
        referencia = pd.read_parquet(entrada, columns=["ANO", "LINHA", "y"])
        guard.assert_dev_only(referencia)
        alinhado = cmp.alinhar(referencia, {mid: cmp.carregar_previsoes(p)
                                            for mid, p in previsoes.items()}, ano=ano)
    resultado = cmp.calcular(alinhado, manifesto, cfg_com_caminhos(cfg, caminhos), conformidade,
                             reamostras=lacre["reamostras"], processos=processos, ano_esperado=ano)
    base = {k: v for k, v in lacre.items() if k not in ("status", "sha256_metricas")}
    return _fases_de_gravacao(caminhos, base, resultado, ensaio=False)


def regenerar_graficos(caminhos: Caminhos) -> list[Path]:
    """Figuras só dos agregados. Exige o lacre `concluido` e o SHA-256 de metricas.json igual ao do
    lacre. Não lê 2025 (não abre a porta)."""
    lacre_caminho = caminhos.agregados / ARQ_LACRE
    if not lacre_caminho.is_file():
        raise ErroExecucao("sem LACRE.json: não há avaliação feita para regenerar as figuras")
    lacre = _ler_lacre(lacre_caminho)
    if lacre.get("status") != CONCLUIDO:
        raise ErroExecucao(f"lacre em status {lacre.get('status')!r}: as figuras só saem de "
                           f"agregados concluídos (se estiver em '{PREVISOES_GERADAS}', "
                           "use --retomar)")
    metricas = caminhos.agregados / ARQ_METRICAS
    if _sha_arquivo(metricas) != lacre["sha256_metricas"]:
        raise ErroExecucao("metricas.json não bate com o SHA-256 do LACRE: não regenero as figuras")
    dados = json.loads(metricas.read_text(encoding="utf-8"))
    return cg.gerar_graficos(dados, caminhos.agregados)


def executar_ensaio(cfg: dict, caminho_manifesto: Path, caminhos_reais: Caminhos, *,
                    processos: int = 4, reamostras: int | None = None,
                    linhas: int = TAMANHO_ENSAIO) -> dict:
    """Ensaio em diretório temporário novo (não é apagado: fica para conferência)."""
    tmp = Path(tempfile.mkdtemp(prefix="ensaio_comparacao_"))
    manifesto, yaml_ensaio, caminhos, excluidos = preparar_ensaio(
        cfg, caminho_manifesto, caminhos_reais, tmp, linhas=linhas)
    resumo = executar(cfg, manifesto, caminhos, caminho_manifesto=yaml_ensaio, ensaio=True,
                      processos=processos, reamostras=reamostras)
    return {**resumo, "pasta": str(tmp), "excluidos_por_artefato_ausente": excluidos}


# --- CLI ----------------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Comparação em 2025: go/no-go, ensaio e execução "
                                 "única (T-8.9).")
    ap.add_argument("--so-checagens", action="store_true",
                    help="roda só o go/no-go e sai (não abre a porta)")
    ap.add_argument("--so-graficos", action="store_true",
                    help="regenera as figuras dos agregados (exige lacre; não lê 2025)")
    ap.add_argument("--retomar", action="store_true",
                    help="retoma um lacre em 'previsoes_geradas' (sem .dbc; porta só na leitura)")
    ap.add_argument("--ensaio", action="store_true",
                    help="a mesma cadeia com dados sintéticos em diretório temporário")
    ap.add_argument(CONFIRMO, action="store_true", dest="confirmo",
                    help="confirma a execução única em 2025 (R2)")
    ap.add_argument("--manifesto", type=Path, default=cm.MANIFESTO_PADRAO)
    ap.add_argument("--worktree-soneca", type=Path, default=None)
    ap.add_argument("--worktree-lora", type=Path, default=None)
    ap.add_argument("--processos", type=int, default=4)
    args = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):  # a saída JSON tem acentos; o console pode ser cp1252
        sys.stdout.reconfigure(encoding="utf-8")

    if sum([args.so_checagens, args.so_graficos, args.ensaio, args.retomar]) > 1:
        print("escolha um modo: --so-checagens, --so-graficos, --ensaio ou --retomar",
              file=sys.stderr)
        return 2
    cfg = load_config()
    caminhos = caminhos_padrao(cfg, soneca=args.worktree_soneca, lora=args.worktree_lora)
    try:
        if args.so_graficos:
            figuras = regenerar_graficos(caminhos)
            print(json.dumps({"figuras": [str(f) for f in figuras]}, ensure_ascii=False))
            return 0
        manifesto = cm.carregar_manifesto(args.manifesto, cfg)
        if args.retomar:
            resumo = retomar(cfg, manifesto, caminhos, caminho_manifesto=args.manifesto,
                             processos=args.processos)
            print(json.dumps(resumo, ensure_ascii=False, indent=2, default=str))
            return 0
        if args.so_checagens:
            checagens = checagens_pre_execucao(cfg, manifesto, caminhos,
                                               caminho_manifesto=args.manifesto)
            passou = not _falhas(checagens)
            print(json.dumps({"passou": passou,
                              "checagens": [c.como_dict() for c in checagens],
                              "git": estado_git(caminhos.raiz)}, ensure_ascii=False, indent=2))
            return 0 if passou else 1
        if not args.ensaio and not args.confirmo:
            print(f"execução real exige {CONFIRMO} (R2): a avaliação de 2025 é única. "
                  "Nada foi lido.", file=sys.stderr)
            return 2
        if args.ensaio:
            resumo = executar_ensaio(cfg, args.manifesto, caminhos, processos=args.processos)
        else:
            resumo = executar(cfg, manifesto, caminhos, caminho_manifesto=args.manifesto,
                              processos=args.processos)
    except (ErroChecagem, ErroExecucao) as erro:
        print(f"recusado: {erro}", file=sys.stderr)
        return 1
    print(json.dumps(resumo, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
