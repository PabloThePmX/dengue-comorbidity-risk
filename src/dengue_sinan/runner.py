"""Execução do M1 numa sessão única (T-4.3b, D-53, D-57, D-64, D-72, NFR-01, R1, R7, R8).

`run_all_models(cfg)` faz, nesta ordem:
1. carrega a população de desenvolvimento (2022–23) uma vez e recria as dobras com as funções da
   T-2.3 (`folds.save_folds`, que usa `loro_folds` e `inner_split`); o arquivo de dobras não vai
   para o git nem para o Drive (D-72), então é refeito aqui e comparado com o hash do T-2.3;
2. confere a **checagem inicial** (bloco `checagem_inicial` do relatório da sessão): Drive
   gravável, SQLite do Optuna abre no Drive, GPU e RAM (`verify.environment`), `sha256_dbc` de
   cada ano contra o T-2.3 e o hash das dobras contra o T-2.3. Se algum check falha, a função
   levanta `ChecagemInicialFalhou` **antes de treinar**;
3. para cada modelo de `cfg["ordem_modelos"]`: pula se `CONCLUIDO.json` tem o mesmo hash de
   dobras e de config; senão roda `tuning.tune` → `cv.run_loro` com os melhores parâmetros, grava
   OOF, métricas e parâmetros, e por último `CONCLUIDO.json`. Libera memória entre modelos;
4. no fim, os ganchos da seleção (T-4.9), do SHAP (T-4.8) e do retreino (T-4.10), nessa ordem.
   Gancho cujo módulo ainda não existe é pulado com aviso, e a sessão não fica `sessao_completa`.

Retomada: o que já está em `CONCLUIDO.json` não é refeito; a busca Optuna retoma pelo SQLite
(`tuning.py`). Gravações (relatório, OOF, JSON, dobras) vão para um arquivo temporário na mesma
pasta e trocam o definitivo com `os.replace` (troca atômica); em erro de E/S tentam de novo
(até 3 novas tentativas).

Onde ficam os arquivos: `<caminhos.dados>/m1/<modelo>/` (OOF, métricas, parâmetros e
`CONCLUIDO.json`) e `<caminhos.dados>/m1/sessao-m1.json` (relatório da sessão, D-57). Como
`caminhos.dados` aponta para o Drive na sessão do Colab, tudo sobrevive a uma queda. O relatório
fica no Drive, e não no clone, porque o clone some junto com o ambiente. Quem traz o relatório
para `reports/verificacao/` é o agente, pelo `verify.show_report` (D-64).

Entrada de segundo plano (D-64): `python -m dengue_sinan.runner --config <caminho>`. Devolve 0 se
a sessão terminou e 1 se `run_all_models` levantou erro; o log (stdout e stderr) vai para onde o
notebook redirecionar.

Hardware: `tracking.start_run` registra GPU, vCPUs e RAM em cada run do MLflow (T-2.5). A sessão
abre um run próprio (`sessao-m1`) que registra o hash das dobras, uma vez por sessão.
"""

from __future__ import annotations

import argparse
import copy
import gc
import hashlib
import importlib
import importlib.util
import json
import logging
import os
import shutil
import sys
import tempfile
import time
import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import pandas as pd
import yaml
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient

from dengue_sinan import cv, dataset, folds, search_space, tracking, tuning, verify
from dengue_sinan.config import load_config
from dengue_sinan.guard import assert_dev_only

logger = logging.getLogger(__name__)

TAREFA = "T-4.3b"
BLOCO_CHECAGEM = "checagem_inicial"
NOME_SESSAO = "sessao-m1"
NOME_RELATORIO = "sessao-m1.json"
PASTA_M1 = "m1"
ARQ_OOF = "oof.parquet"
ARQ_METRICAS = "metricas.json"
ARQ_PARAMETROS = "parametros.json"
ARQ_CONCLUIDO = "CONCLUIDO.json"
ARQ_DOBRAS = "dobras_dev.parquet"
ARQ_T23 = "T-2.3.json"
ARQ_CONFIG_SESSAO = "config_sessao.yaml"
ARQ_MANIFESTO = "manifest.json"

# T-4.3b: gravações no Drive tentam de novo até 3 vezes em erro de E/S (1 tentativa + 3 novas).
TENTATIVAS_E_S = 4
PAUSA_E_S_S = 5.0  # segundos entre tentativas; lido na hora da chamada (testes zeram)

# Tarefa de cada modelo (só para o relatório); modelo fora da lista não ganha tarefa.
TAREFA_DO_MODELO = {
    "random_forest": "T-4.4",
    "xgboost": "T-4.5",
    "catboost": "T-4.6",
    "elastic_net": "T-4.6b",
    "mlp": "T-4.6b",
    "tabfm": "T-4.7",
}


class ChecagemInicialFalhou(RuntimeError):
    """A checagem inicial reprovou: a sessão para antes de treinar (T-4.3b)."""


@dataclass(frozen=True)
class Gancho:
    """Ponto de extensão do fim da sessão.

    `alvo` é "modulo:funcao". A função recebe `(cfg, resultados)` e devolve a lista de checks do
    bloco `bloco` do relatório. Se o módulo ou a função ainda não existem, o gancho é pulado com
    aviso (T-4.9, T-4.8 e T-4.10 ainda não foram implementadas). `funcao`, se dada, substitui o
    `alvo` (só para os testes).
    """

    bloco: str
    tarefa: str
    alvo: str
    funcao: Callable[[dict, dict], list[dict]] | None = None


GANCHOS_PADRAO: tuple[Gancho, ...] = (
    Gancho("selecao", "T-4.9", "dengue_sinan.selecao:executar"),
    Gancho("shap", "T-4.8", "dengue_sinan.shap_global:executar_sessao"),
    Gancho("retreino", "T-4.10", "dengue_sinan.retreino:executar"),
)


# --- Caminhos ---------------------------------------------------------------------------------

def _caminho(cfg: dict, chave: str) -> Path:
    """`cfg["caminhos"][chave]`; relativo é a partir da raiz do repositório."""
    caminho = Path(cfg["caminhos"][chave])
    return caminho if caminho.is_absolute() else (verify.REPO / caminho).resolve()


def pasta_m1(cfg: dict) -> Path:
    """`<caminhos.dados>/m1`: OOF, métricas, marcadores e o relatório da sessão."""
    return _caminho(cfg, "dados") / PASTA_M1


def caminho_relatorio(cfg: dict) -> Path:
    """Relatório da sessão dos modelos (D-57), no Drive: `<caminhos.dados>/m1/sessao-m1.json`."""
    return pasta_m1(cfg) / NOME_RELATORIO


def _caminho_t23(cfg: dict) -> Path:
    return _caminho(cfg, "relatorios") / "verificacao" / ARQ_T23


def config_da_sessao(cfg: dict, pasta_drive: str | Path) -> Path:
    """Grava `<pasta_drive>/config_sessao.yaml`: o config com dados, mlruns e modelos no Drive.

    Os modelos vão para o Drive porque o `models/m1_final` é gravado durante a sessão (T-4.10);
    o clone some junto com o ambiente. O notebook chama esta função e passa o caminho devolvido à
    entrada `python -m`. O resto do config (seed, dobras, orçamentos) não muda.
    """
    pasta = Path(pasta_drive)
    nova = copy.deepcopy(cfg)
    nova["caminhos"] = {
        **cfg["caminhos"],
        "dados": str(pasta / "data"),
        "mlruns": str(pasta / "mlruns"),
        "modelos": str(pasta / "models"),
    }
    destino = pasta / ARQ_CONFIG_SESSAO
    texto = yaml.safe_dump(nova, allow_unicode=True, sort_keys=False)
    _gravar_atomico(destino, lambda tmp: tmp.write_text(texto, encoding="utf-8"))
    return destino


# --- Gravação atômica com novas tentativas (T-4.3b, item 7) -----------------------------------

_substituir = os.replace  # indireção para o teste simular falha de E/S


def _gravar_atomico(destino: Path, escrever: Callable[[Path], None]) -> None:
    """Chama `escrever(tmp)` num arquivo temporário e troca o `destino` com `os.replace`.

    O temporário fica numa pasta nova dentro da pasta do destino, com o mesmo nome do destino
    (assim `verify.update_session_report` deduz o nome da sessão certo). Erro de E/S repete a
    gravação inteira, até `TENTATIVAS_E_S` vezes. Outros erros não são repetidos.
    """
    destino = Path(destino)
    for tentativa in range(1, TENTATIVAS_E_S + 1):
        pasta_tmp: Path | None = None
        try:
            destino.parent.mkdir(parents=True, exist_ok=True)
            pasta_tmp = Path(tempfile.mkdtemp(dir=destino.parent, prefix=".tmp-"))
            tmp = pasta_tmp / destino.name
            escrever(tmp)
            _substituir(tmp, destino)
            return
        except OSError as erro:
            if tentativa == TENTATIVAS_E_S:
                raise
            logger.warning("erro de E/S ao gravar %s (tentativa %d de %d): %s",
                           destino, tentativa, TENTATIVAS_E_S, erro)
            time.sleep(PAUSA_E_S_S)
        finally:
            if pasta_tmp is not None:
                shutil.rmtree(pasta_tmp, ignore_errors=True)


def _para_json(valor: Any) -> Any:
    if isinstance(valor, np.generic):
        return valor.item()
    if isinstance(valor, Path):
        return str(valor)
    raise TypeError(f"{type(valor).__name__} não é serializável em JSON")


def _gravar_json(destino: Path, conteudo: dict) -> None:
    texto = json.dumps(conteudo, indent=2, ensure_ascii=False, default=_para_json) + "\n"
    _gravar_atomico(destino, lambda tmp: tmp.write_text(texto, encoding="utf-8"))


def _ler_json(caminho: Path) -> dict | None:
    """JSON de `caminho`, ou None se não existe ou não lê (um arquivo pela metade não vale)."""
    try:
        return json.loads(caminho.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _sha256(caminho: Path) -> str:
    sha = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            sha.update(bloco)
    return sha.hexdigest()


def _atualizar_relatorio(
    caminho: Path,
    bloco: str,
    checks: list[dict],
    cfg: dict,
    *,
    tarefa: str | None,
    sessao_completa: bool,
    hash_dobras: str,
) -> None:
    """Reescreve o relatório da sessão com o bloco `bloco` (D-57), de forma atômica.

    Copia o relatório atual para o temporário, passa por `verify.update_session_report` (que
    preserva os outros blocos) e acrescenta `hash_dobras` no topo.
    """
    def escrever(tmp: Path) -> None:
        if caminho.exists():
            shutil.copyfile(caminho, tmp)
        verify.update_session_report(tmp, bloco, checks, cfg, tarefa=tarefa,
                                     sessao_completa=sessao_completa)
        relatorio = json.loads(tmp.read_text(encoding="utf-8"))
        relatorio["hash_dobras"] = hash_dobras
        tmp.write_text(json.dumps(relatorio, indent=2, ensure_ascii=False) + "\n",
                       encoding="utf-8")

    _gravar_atomico(caminho, escrever)


# --- Dados, dobras e hash de config -----------------------------------------------------------

def _carregar_dados_de_desenvolvimento(cfg: dict) -> pd.DataFrame:
    """População de 2022–23 com as features do M1 (dicionário de features), índice 0..n-1."""
    populacao = dataset.load_population(cfg, list(cfg["anos_dev"]))
    return dataset.build_feature_frame(populacao).reset_index(drop=True)


def hash_config(cfg: dict) -> str:
    """SHA-256 do config inteiro (JSON com chaves ordenadas). Qualquer valor muda o hash."""
    texto = json.dumps(cfg, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _recriar_dobras(cfg: dict, df: pd.DataFrame) -> str:
    """Recria as dobras com as funções da T-2.3 e devolve o hash do conteúdo (D-72)."""
    caminho = _caminho(cfg, "dados") / "folds" / ARQ_DOBRAS
    resultado: dict[str, str] = {}

    def escrever(tmp: Path) -> None:
        resultado["hash"] = folds.save_folds(cfg, df, tmp)

    _gravar_atomico(caminho, escrever)
    h = resultado["hash"]
    folds.load_folds(caminho, h)  # releitura: recusa se o arquivo não bater com o hash
    return h


# --- Checagem inicial (bloco checagem_inicial, D-57) ------------------------------------------

def _gravavel(pasta: Path) -> bool:
    """Grava, relê e apaga um arquivo de teste na pasta do Drive."""
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        teste = pasta / f".teste-gravacao-{uuid.uuid4().hex}"
        teste.write_text("ok", encoding="utf-8")
        ok = teste.read_text(encoding="utf-8") == "ok"
        teste.unlink()
        return ok
    except OSError:
        return False


def _sha_dbc_do_manifesto(cfg: dict) -> dict:
    manifesto = _caminho(cfg, "dados") / ARQ_MANIFESTO
    return _ler_json(manifesto) or {}


def _checagem_inicial(
    cfg: dict, df: pd.DataFrame, hash_dobras: str, esperado_path: Path
) -> list[dict]:
    """Checks do bloco `checagem_inicial`. Nada aqui treina; tudo é leitura ou gravação de teste."""
    t23 = _ler_json(_caminho_t23(cfg)) or {}
    referencia_dbc = t23.get("hash_dados", {})
    referencia_dobras = next(
        (c["obtido"] for c in t23.get("checks", []) if c.get("nome") == "hash_conteudo_dobras"),
        "ausente no T-2.3",
    )
    esperado = yaml.safe_load(Path(esperado_path).read_text(encoding="utf-8"))["desenvolvimento"]
    manifesto = _sha_dbc_do_manifesto(cfg)

    checks = [verify.check("drive_gravavel", True, _gravavel(pasta_m1(cfg)))]
    checks.append(tuning.checar_sqlite_no_diretorio(tuning.pasta_optuna(cfg)))
    checks.extend(verify.environment(cfg))
    for ano in cfg["anos_dev"]:
        checks.append(verify.check(
            f"sha256_dbc_{ano}",
            referencia_dbc.get(str(ano), "ausente no T-2.3"),
            manifesto.get(str(ano), {}).get("sha256_dbc", "ausente no manifesto"),
        ))
    checks.append(verify.check("hash_conteudo_dobras", referencia_dobras, hash_dobras))
    checks.append(verify.check("casos_dev", esperado["populacao_total"], len(df)))
    checks.append(verify.check("eventos_dev", esperado["eventos_total"],
                               int(df["y"].sum())))
    return checks


def _registrar_sessao(cfg: dict, hash_dobras: str) -> None:
    """Um run no MLflow por sessão: o hardware sai do `tracking.start_run` (T-2.5)."""
    with tracking.start_run(cfg, NOME_SESSAO, tags={"etapa": TAREFA}):
        mlflow.log_param("sessao.hash_dobras", hash_dobras)


# --- Modelos ----------------------------------------------------------------------------------

def _concluido(pasta: Path, hash_dobras: str, hash_cfg: str) -> bool:
    """Marcador com o mesmo hash de dobras e de config e os arquivos no lugar (T-4.3b, item 2)."""
    marcador = _ler_json(pasta / ARQ_CONCLUIDO)
    return (
        marcador is not None
        and marcador.get("passou") is True
        and marcador.get("hash_dobras") == hash_dobras
        and marcador.get("hash_config") == hash_cfg
        and (pasta / ARQ_OOF).exists()
        and (pasta / ARQ_METRICAS).exists()
        and (pasta / ARQ_PARAMETROS).exists()
    )


def _alias_existe(modelo: str) -> bool:
    client = MlflowClient(tracking_uri=mlflow.get_tracking_uri())
    try:
        client.get_model_version_by_alias(
            tuning.nome_modelo_registrado(modelo), tuning.ALIAS_MELHOR)
    except MlflowException:
        return False
    return True


def _sem_busca(cfg: dict, modelo: str) -> bool:
    """True se o espaço do modelo diz `sem_busca: true` (TabFM, D-69). Modelo sem espaço no
    config não é sem busca: a `tune` acusa o erro, como antes."""
    espaco = search_space.load_search_space(cfg).get(modelo)
    return espaco is not None and espaco.sem_busca


def _checks_modelo(
    cfg: dict, modelo: str, n_linhas: int, resultado: dict, resumo: dict,
    tempo_busca_s: float, teto_s: float, iterativo: bool, sem_busca: bool = False,
) -> list[dict]:
    """Checks do bloco do modelo. Sem busca (`sem_busca`), não há tentativas nem alias a conferir:
    o tempo que vale para o teto é o da única execução do laço (`tempo_busca_s` recebe esse)."""
    dobras = list(cfg["ordem_dobras"])
    pr_por_dobra = resultado["pr_auc_por_dobra"]
    checks = [
        verify.check("oof_uma_linha_por_caso", n_linhas, len(resultado["oof"])),
        verify.check("oof_posicoes_unicas", n_linhas,
                     int(np.unique(resultado["posicoes"]).size)),
        verify.check("pr_auc_em_todas_as_dobras", len(dobras),
                     sum(1 for r in dobras if np.isfinite(pr_por_dobra.get(r, np.nan)))),
        verify.check("tempo_busca_dentro_do_teto", True, bool(tempo_busca_s <= teto_s)),
    ]
    if not sem_busca:
        checks += [
            verify.check("alias_melhor_validacao", True, _alias_existe(modelo)),
            verify.check("tentativa_concluida", True,
                         bool(resumo["tentativas_concluidas"] >= 1)),
            verify.check("tentativas_dentro_do_maximo", True, bool(
                resumo["tentativas_concluidas"] + resumo["tentativas_podadas"]
                + resumo["tentativas_falhas"] <= int(cfg["optuna"]["max_tentativas"][modelo]))),
        ]
    if iterativo:
        com_ponto = sum(1 for r in dobras if resultado["melhores_pontos"].get(r) is not None)
        checks.append(verify.check("melhor_ponto_em_todas_as_dobras", len(dobras), com_ponto))
    return checks


def _resumo_sem_busca(tempo_s: float) -> dict:
    """Mesmas chaves do resumo de `tuning.tune`, com zero tentativas: a seleção lê essas chaves."""
    return {
        "melhores_parametros": {},
        "melhor_tentativa": None,
        "sem_busca": True,
        "execucoes": 1,
        "t_cronometragem_s": float(tempo_s),
        "orcamento_s": 0.0,
        "subamostra": False,
        "tentativas_concluidas": 0,
        "tentativas_podadas": 0,
        "tentativas_falhas": 0,
    }


def _treinar_modelo(
    cfg: dict, modelo: str, df: pd.DataFrame, pasta: Path, hash_dobras: str, hash_cfg: str,
) -> tuple[dict, list[dict]]:
    """Busca (ou, sem busca, uma execução com parâmetros vazios), OOF final, arquivos do modelo e
    checks. Não grava `CONCLUIDO.json` (quem decide é `run_all_models`, depois do relatório)."""
    teto_s = float(cfg["orcamento_teto_min"][modelo]) * 60
    sem_busca = _sem_busca(cfg, modelo)
    if sem_busca:
        resumo = _resumo_sem_busca(0.0)
        melhores: dict = {}
        tempo_busca_s = 0.0
        teto_efetivo_s = teto_s  # sem busca, o teto vale para a única execução, sem folga
    else:
        inicio = time.perf_counter()
        resumo = tuning.tune(cfg, modelo, df)
        tempo_parede_s = time.perf_counter() - inicio  # inclui a cronometragem (não cobrada)
        melhores = resumo["melhores_parametros"]
        if melhores is None:
            # nenhuma tentativa concluiu (ex.: teto de tempo menor que uma dobra): sem OOF, o bloco
            # reprova o check `tentativa_concluida` e a sessão segue para o próximo modelo (T-4.3b)
            return _bloco_sem_tentativa(modelo, pasta, resumo)
        # o teto vale para o que o orçamento cobra (D-53: a cronometragem em subamostra não é
        # cobrada); a folga é uma dobra, a maior vista na busca, porque a poda é no fim da dobra
        tempo_busca_s = float(resumo["tempo_busca_total_s"])
        teto_efetivo_s = teto_s + float(resumo["maior_dobra_s"])

    inicio = time.perf_counter()
    resultado = cv.run_loro(cfg, modelo, melhores, df)
    tempo_treino_s = time.perf_counter() - inicio
    if sem_busca:
        resumo["t_cronometragem_s"] = tempo_treino_s
        tempo_busca_s = tempo_treino_s  # o teto vale para a única execução
        tempo_parede_s = tempo_treino_s
    iterativo = any(v is not None for v in resultado["melhores_pontos"].values())
    oof = resultado["oof"]
    metricas = {
        "modelo": modelo,
        "oof_pr_auc": float(resultado["oof_pr_auc"]),
        "pr_auc_media": float(resultado["pr_auc_media"]),
        "pr_auc_por_dobra": {k: float(v) for k, v in resultado["pr_auc_por_dobra"].items()},
        "melhores_pontos": {
            k: (None if v is None else int(v)) for k, v in resultado["melhores_pontos"].items()
        },
        "linhas_oof": int(len(oof)),
    }
    parametros = {
        "modelo": modelo,
        "melhores_parametros": melhores,
        "melhor_tentativa": resumo["melhor_tentativa"],
        "tuning": {k: v for k, v in resumo.items() if k != "melhores_parametros"},
        "hash_dobras": hash_dobras,
        "hash_config": hash_cfg,
    }

    def escrever_oof(tmp: Path) -> None:
        oof.to_parquet(tmp, index=False)

    _gravar_atomico(pasta / ARQ_OOF, escrever_oof)
    _gravar_json(pasta / ARQ_METRICAS, metricas)
    _gravar_json(pasta / ARQ_PARAMETROS, parametros)

    checks = _checks_modelo(cfg, modelo, len(df), resultado, resumo,
                            tempo_busca_s, teto_efetivo_s, iterativo, sem_busca=sem_busca)
    with tracking.start_run(cfg, f"final-{modelo}", tags={"modelo": modelo, "etapa": "T-4.3b"}):
        mlflow.log_metrics({
            "final.oof_pr_auc": metricas["oof_pr_auc"],
            "final.pr_auc_media": metricas["pr_auc_media"],
            "final.tempo_busca_s": float(tempo_busca_s),
            "final.tempo_busca_parede_s": float(tempo_parede_s),
            "final.tempo_treino_s": float(tempo_treino_s),
        })
        mlflow.log_param("final.sem_busca", str(sem_busca))
        mlflow.log_param("final.oof_sha256", _sha256(pasta / ARQ_OOF))

    resumo_sessao = {
        "modelo": modelo,
        "pulado": False,
        "metricas": metricas,
        "melhores_parametros": melhores,
        "pasta": str(pasta),
    }
    return resumo_sessao, checks  # o OOF e o resultado saem de escopo aqui


def _bloco_sem_tentativa(modelo: str, pasta: Path, resumo: dict) -> tuple[dict, list[dict]]:
    """Bloco de um modelo cuja busca não concluiu nenhuma tentativa: sem OOF nem métricas, com o
    check `tentativa_concluida` reprovado. Não grava arquivos do modelo nem `CONCLUIDO.json`."""
    checks = [verify.check("tentativa_concluida", True,
                           bool(resumo["tentativas_concluidas"] >= 1))]
    logger.warning("%s: a busca não concluiu nenhuma tentativa (podadas %s, falhas %s); "
                   "bloco reprovado, sem OOF, seguindo para o próximo modelo", modelo,
                   resumo["tentativas_podadas"], resumo["tentativas_falhas"])
    return {
        "modelo": modelo,
        "pulado": False,
        "metricas": None,
        "melhores_parametros": None,
        "pasta": str(pasta),
    }, checks


def _gravar_concluido(pasta: Path, modelo: str, hash_dobras: str, hash_cfg: str) -> None:
    """Último arquivo do modelo: marca que o modelo está pronto para ser pulado (T-4.3b)."""
    arquivos = [ARQ_OOF, ARQ_METRICAS, ARQ_PARAMETROS]
    _gravar_json(pasta / ARQ_CONCLUIDO, {
        "modelo": modelo,
        "passou": True,
        "concluido_em_utc": _agora(),
        "hash_dobras": hash_dobras,
        "hash_config": hash_cfg,
        "sha256": {nome: _sha256(pasta / nome) for nome in arquivos},
    })


def _liberar_memoria() -> None:
    """Entre modelos: coleta lixo e esvazia o cache da GPU, se o PyTorch estiver instalado."""
    gc.collect()
    try:
        import torch
    except ImportError:
        return
    if torch.cuda.is_available():
        torch.cuda.empty_cache()


def _agora() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


# --- Ganchos do fim da sessão -----------------------------------------------------------------

def _resolver(alvo: str) -> Callable[..., list[dict]] | None:
    """Função do gancho, ou None se o módulo ou a função ainda não existem."""
    modulo_nome, _, funcao = alvo.partition(":")
    if importlib.util.find_spec(modulo_nome) is None:
        return None
    atributo = getattr(importlib.import_module(modulo_nome), funcao, None)
    return atributo if callable(atributo) else None


def _executar_ganchos(
    cfg: dict, ganchos: Iterable[Gancho], resultados: dict, caminho: Path, hash_dobras: str
) -> None:
    ganchos = list(ganchos)
    completa = True
    for indice, gancho in enumerate(ganchos):
        funcao = gancho.funcao or _resolver(gancho.alvo)
        if funcao is None:
            completa = False
            logger.warning("gancho %s (%s) pulado: %s ainda não existe",
                           gancho.bloco, gancho.tarefa, gancho.alvo)
            continue
        checks = funcao(cfg, resultados)
        # sessao_completa só no último gancho e só se nenhum anterior foi pulado;
        # o `passou` geral do relatório ainda exige que todos os blocos passem.
        ultimo = indice == len(ganchos) - 1
        _atualizar_relatorio(caminho, gancho.bloco, checks, cfg, tarefa=gancho.tarefa,
                             sessao_completa=ultimo and completa, hash_dobras=hash_dobras)


# --- Sessão -----------------------------------------------------------------------------------

def run_all_models(
    cfg: dict,
    *,
    carregar_dados: Callable[[dict], pd.DataFrame] | None = None,
    ganchos: Sequence[Gancho] = GANCHOS_PADRAO,
    ao_concluir_modelo: Callable[[str], None] | None = None,
    esperado_path: Path | None = None,
) -> dict:
    """Roda a sessão dos modelos (ver o docstring do módulo). Devolve o resumo por modelo.

    `carregar_dados`, `ganchos`, `ao_concluir_modelo` e `esperado_path` existem para os testes
    (dados sintéticos, modelos baratos, queda simulada). Na sessão real ficam com o padrão.
    """
    if esperado_path is None:
        esperado_path = verify.REPO / "config" / "esperado.yaml"
    relatorio = caminho_relatorio(cfg)

    df = (carregar_dados or _carregar_dados_de_desenvolvimento)(cfg)
    assert_dev_only(df)  # R1
    hash_dobras = _recriar_dobras(cfg, df)
    hash_cfg = hash_config(cfg)

    checks = _checagem_inicial(cfg, df, hash_dobras, esperado_path)
    passou = all(c["passou"] for c in checks)
    _atualizar_relatorio(relatorio, BLOCO_CHECAGEM, checks, cfg, tarefa=TAREFA,
                         sessao_completa=False, hash_dobras=hash_dobras)
    if not passou:
        reprovados = [c["nome"] for c in checks if not c["passou"]]
        raise ChecagemInicialFalhou(f"checagem inicial reprovou {reprovados}: sem treino (T-4.3b)")

    _registrar_sessao(cfg, hash_dobras)
    resultados: dict[str, dict] = {}
    for modelo in cfg["ordem_modelos"]:
        pasta = pasta_m1(cfg) / modelo
        if _concluido(pasta, hash_dobras, hash_cfg):
            logger.info("%s: CONCLUIDO com as mesmas dobras e config; pulado", modelo)
            resultados[modelo] = {
                "modelo": modelo,
                "pulado": True,
                "metricas": _ler_json(pasta / ARQ_METRICAS),
                "melhores_parametros": (_ler_json(pasta / ARQ_PARAMETROS) or {}).get(
                    "melhores_parametros"),
                "pasta": str(pasta),
            }
            continue

        logger.info("%s: treino iniciado", modelo)
        resumo, checks = _treinar_modelo(cfg, modelo, df, pasta, hash_dobras, hash_cfg)
        resultados[modelo] = resumo
        _atualizar_relatorio(relatorio, modelo, checks, cfg,
                             tarefa=TAREFA_DO_MODELO.get(modelo),
                             sessao_completa=False, hash_dobras=hash_dobras)
        if all(c["passou"] for c in checks):
            _gravar_concluido(pasta, modelo, hash_dobras, hash_cfg)
        else:
            logger.warning("%s: checks reprovados; CONCLUIDO não gravado", modelo)
        _liberar_memoria()
        logger.info("%s: concluído (passou=%s)", modelo, all(c["passou"] for c in checks))
        if ao_concluir_modelo is not None:
            ao_concluir_modelo(modelo)

    del df
    _liberar_memoria()
    sem_oof = [m for m, r in resultados.items() if r.get("metricas") is None]
    if sem_oof:
        # os ganchos (seleção, SHAP, retreino) leem o OOF de todos os modelos: não rodam sem ele.
        # A sessão fica incompleta (passou=false pelo bloco reprovado; sem sessao_completa).
        logger.warning("ganchos pulados: modelos sem OOF %s", sem_oof)
        return resultados
    _executar_ganchos(cfg, ganchos, resultados, relatorio, hash_dobras)
    return resultados


# --- Entrada de linha de comando --------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    """`python -m dengue_sinan.runner --config <caminho>`: 0 se terminou, 1 se levantou erro."""
    parser = argparse.ArgumentParser(prog="python -m dengue_sinan.runner")
    parser.add_argument("--config", required=True, type=Path,
                        help="config YAML da sessão (ex.: o gerado por config_da_sessao)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        cfg = load_config(args.config)
        run_all_models(cfg)
    except Exception:
        logger.exception("sessão dos modelos falhou")
        return 1
    logger.info("sessão dos modelos terminou")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
