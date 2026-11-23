"""Avaliação final no teste (T-5.1 e T-5.2; FR-09, D-36, D-39, D-93; R1, R2, R7, R8).

Roda uma vez, em 2024, com os artefatos congelados (E1, M1, B0, B1) e a regra B2. Ordem:

1. Se `reports/teste/LACRE.json` existir, recusa antes de ler qualquer dado (R2).
2. Carrega 2024 com `dataset.load_population(cfg, [ano_teste], teste=True)`: é a única leitura do
   teste. Os avisos de qualidade (FR-03) são capturados, não impressos.
3. Confere população, eventos e eventos por região com `config/esperado.yaml › teste` **antes** de
   qualquer cálculo. Divergência levanta erro, e nada é gravado.
4. Carrega os artefatos e prevê dentro de `guard.leitura_do_teste()`, a única porta que deixa o
   wrapper de cada modelo aceitar 2024.
5. Roda as análises em memória. Nenhum resultado é impresso nem gravado nesta etapa.
6. Só depois de tudo calculado grava `metricas.md`, `metricas.json` e, por último, `LACRE.json`,
   cada um por troca atômica. Queda no meio deixa a pasta sem lacre, e uma nova execução é
   permitida (D-93).

**Ponto de extensão (T-5.2 a T-5.4).** Uma `Analise(nome, executar)` recebe um `Contexto` (cfg, `y`,
predições por modelo, limiares, o DataFrame de features avaliado) e devolve uma `Saida`: tabelas
agregadas (até `LIMITE_LINHAS_TABELA` linhas), um trecho de markdown em pt-BR e um dict que entra
no `metricas.json` sob o nome da análise. A análise não grava nada: quem grava é este módulo.
Toda análise nova entra em `ANALISES_PADRAO`. A saída inteira passa por `inteiros_pequenos` (R7)
antes de qualquer gravação. Cada tabela vira um CSV (`<analise>__<tabela>.csv`) ao lado do markdown
e do JSON, e o `LACRE.json` guarda o SHA-256 de todos os arquivos gravados e o do `selecao.json`.

Análises, na ordem: `metricas` (T-5.1), `decisao`, `calibracao` e `subgrupos` (T-5.2; o cálculo está
em `teste_analises.py`), `erros` (T-5.3, `teste_erros.py`) e `criterios` (T-5.4,
`teste_criterios.py`; lê `Contexto.anteriores`, não recalcula o que a `metricas` já calculou).
`erros` e `criterios` pedem `Saida.arquivo`: o markdown deles vai para `erros.md` e `criterios.md`
(com os CSVs; o `LACRE.json` guarda o SHA-256 de todos), e o `metricas.md` só aponta para eles.

A curva de decisão marca o limiar F2, lido do `selecao.json` da T-4.9 e
validado (número em [0, 1]) ANTES de ler 2024. A calibração reaproveita slope, intercepto e
observado/esperado da análise `metricas` (via `Contexto.anteriores`). Os subgrupos precisam de
`CS_SEXO`, `CS_RACA`, `regiao`, `gestante` e `idade_anos` em `Contexto.df` (nenhum é feature: D-21,
D-48), e `build_feature_frame` já os preserva.

**Ensaio.** `ensaiar_em_desenvolvimento(cfg)` roda o mesmo pipeline em 2022–23 (com
`assert_dev_only`), sem tocar 2024, sem lacre, e grava só em `reports/ensaio/`,
com a marca "ENSAIO, não é avaliação".
As predições são **em amostra**: os modelos foram ajustados nesses mesmos anos. Os números são
otimistas e servem para achar erros e medir tempo.

**Bootstrap (D-53, D-93).** Estratificado por alvo, com a semente do config (R8) e uma sub-semente
por reamostra (`SeedSequence(seed).spawn(n)`): o resultado é o mesmo com 1, 2, 4 ou 8 processos.
Linhas com o mesmo alvo e as mesmas predições formam células, e cada reamostra sorteia os pesos das
células (multinomial, equivalente ao sorteio de linhas). Os mesmos pesos valem para todos os
modelos, e a diferença de PR-AUC é pareada. PR-AUC e ROC leem só os positivos e os negativos entre
eles; Brier é uma média ponderada; slope e intercepto saem de Newton com pesos e início quente
(`metrics.Calibracao`); as métricas no limiar saem de contagens de (alvo, flags de cada modelo).
O cálculo roda em processos (`cfg["bootstrap"]["processos"]`, padrão `os.cpu_count()`), com os
arrays grandes em memória compartilhada (`metrics.rodar_reamostras`; os subgrupos usam
`metrics.rodar_varios`, um só conjunto de processos para todos). As bandas de calibração têm
`bootstrap.calibracao` reamostras (2.000).

**Ambiente (D-64).** A avaliação final roda no Colab com GPU T4 e RAM alta, o mesmo ambiente do
Marco 4 (`ambiente` em `config/base.yaml`: GPU T4, RAM ≥ 50 GiB). O check de ambiente da
verificação (`verify.environment`) é mantido como está e não é afrouxado. O bootstrap é
CPU-bound: o nº de vCPUs e o de processos usados são registrados no relatório de execução.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import math
import os
import subprocess
import sys
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import yaml

from dengue_sinan import (
    artifacts,
    baselines,
    dataset,
    explain,
    guard,
    metrics,
    runner,
    selecao,
    teste_analises,
    teste_criterios,
    teste_erros,
    verify,
)
from dengue_sinan.config import load_config

logger = logging.getLogger(__name__)

TAREFA = "T-5.1"  # a verificação (D-64) da T-5.2 a T-5.4 vai no mesmo relatório
PASTA_TESTE = "teste"
PASTA_ENSAIO = "ensaio"
ARQ_LACRE = "LACRE.json"
ARQ_MARKDOWN = "metricas.md"
ARQ_JSON = "metricas.json"
PROBABILISTICOS = ("M1", "B0", "B1", "E1")
COM_LIMIAR = ("M1", "B0", "B1")  # B2 é regra: entra pela flag, com o limiar 0,5 (baselines)
NOME_B2 = "B2"
LIMIAR_B2 = 0.5  # o mesmo de baselines.LIMIAR_REGRA
PARES_DIFERENCA = (("M1", "B0"), ("M1", "B1"))  # SC-01 (M1 − B0) e SC-04 (M1 − B1)
LIMITE_LINHAS_TABELA = 1000  # agregados: uma análise que devolva mais que isso está errada (R7)
COLUNAS_ESTRUTURAIS: frozenset[str] = frozenset()  # colunas de inteiros que não são contagens
QUANTIS_IC = teste_analises.QUANTIS_IC
ESPERADO_PADRAO = verify.REPO / "config" / "esperado.yaml"
METRICAS_NO_LIMIAR = metrics.METRICAS_NO_LIMIAR
AVISO_TESTE = ("Avaliação única em 2024 (R2). Este arquivo é o resultado do teste: não há nova "
               "avaliação com o mesmo lacre. Só agregados (R7); células de 1 a 9 aparecem "
               "como <10.")
AVISO_ENSAIO = ("ENSAIO, não é avaliação. Predições em amostra em 2022–23 (os modelos foram "
                "ajustados nesses anos): números otimistas. Não usar para SC-01 a SC-04.")


# --- Avisos de qualidade capturados (sem impressão antes do fim) ----------------------------

class _ColetorDeAvisos(logging.Handler):
    """Guarda os avisos FR-03 como (ano, nome do alerta, valor suprimido), sem propagar."""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.alertas: list[dict] = []

    def emit(self, record: logging.LogRecord) -> None:
        args = record.args if isinstance(record.args, tuple) else ()
        if len(args) == 2 and isinstance(args[1], dict):
            ano, alerta = args
            valores = [v for k, v in alerta.items() if k != "alerta"]
            valor = int(valores[0]) if valores else 0
            self.alertas.append({"ano": int(ano), "alerta": str(alerta.get("alerta")),
                                 "valor": _celula(valor)})


@contextmanager
def _capturar_avisos() -> Iterator[_ColetorDeAvisos]:
    """Enquanto o bloco roda, os avisos de `dengue_sinan.*` vão para o coletor e não para o
    terminal: o relatório é o único lugar onde aparecem (D-93, R7)."""
    coletor = _ColetorDeAvisos()
    raiz = logging.getLogger("dengue_sinan")
    propagacao = raiz.propagate
    raiz.addHandler(coletor)
    raiz.propagate = False
    try:
        yield coletor
    finally:
        raiz.removeHandler(coletor)
        raiz.propagate = propagacao


_celula = teste_analises.celula  # R7: contagem de 1 a 9 vira "<10"; zero e valores grandes passam


# --- Gravação atômica, pastas e lacre --------------------------------------------------------

def _gravar_atomico(caminho: Path, texto: str) -> None:
    """Escreve num temporário e troca pelo destino: nunca fica arquivo pela metade."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_name(caminho.name + ".tmp")
    try:
        temporario.write_text(texto, encoding="utf-8")
        os.replace(temporario, caminho)
    except BaseException:
        temporario.unlink(missing_ok=True)
        raise


def _sha256_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def _pasta_do_teste(cfg: dict) -> Path:
    return runner._caminho(cfg, "relatorios") / PASTA_TESTE


def _pasta_do_ensaio(cfg: dict) -> Path:
    return runner._caminho(cfg, "relatorios") / PASTA_ENSAIO


def _arvore_limpa() -> bool | None:
    """True se `git status --porcelain` não lista nada; None se não der para saber."""
    try:
        saida = subprocess.run(["git", "status", "--porcelain"], cwd=verify.REPO,
                               capture_output=True, text=True, timeout=60, check=True)
    except (OSError, subprocess.SubprocessError):
        return None
    return saida.stdout.strip() == ""


# --- Modelos congelados ----------------------------------------------------------------------

@dataclass(frozen=True)
class Modelos:
    """O que a avaliação usa. `m1`: ModeloFinal (`prever_proba`, `limiar`, `nome`); `baselines`:
    B0 e B1 (`predizer`, `limiar`); `e1`: E1Leve; `payloads`: pasta e SHA-256 de cada artefato."""

    m1: Any
    baselines: Any
    e1: Any
    payloads: dict = field(default_factory=dict)


def carregar_modelos(cfg: dict) -> Modelos:
    """Carrega E1, M1, B0 e B1 de `caminhos.modelos`, conferindo os SHA-256 (artifacts).

    Confere também o M1 contra o `selecao.json` da T-4.9: mesmo vencedor, mesmo limiar, e o
    critério D-92 (o limiar do modelo congelado é o de recall ≥ B2, não o F2).
    """
    from dengue_sinan import baselines_final, retreino  # noqa: F401  registram os tipos

    pasta = runner._caminho(cfg, "modelos")
    e1 = artifacts.load_bundle(pasta / "e1")
    m1 = artifacts.load_bundle(pasta / "m1_final")
    bl = baselines_final.carregar_baselines(pasta)

    sel = runner._ler_json(runner.pasta_m1(cfg) / selecao.NOME_SELECAO)
    if sel is None:
        raise FileNotFoundError(f"sem {selecao.NOME_SELECAO}: a T-4.9 precisa rodar antes")
    if sel.get("criterio_limiar") != selecao.CRITERIO_LIMIAR:
        raise ValueError("selecao.json com outro critério de limiar (D-92): não avalie")
    if m1.nome != sel["vencedor"] or m1.limiar != float(sel["modelos"][m1.nome]["limiar"]):
        raise ValueError("M1 congelado diverge do selecao.json (vencedor ou limiar)")

    payloads = {}
    for nome, pasta_nome in (("E1", "e1"), ("M1", "m1_final"), ("B1", "b1_final"),
                             ("B0", "b0_final")):
        caminho = pasta / pasta_nome
        payloads[nome] = {"pasta": str(caminho),
                          "sha256_payload": artifacts.ler_metadados(caminho)["payload"]}
    return Modelos(m1=m1, baselines=bl, e1=e1, payloads=payloads)


def prever_e1(e1: Any, df: pd.DataFrame) -> np.ndarray:
    """Risco do E1 para cada linha de `df`. O E1 só depende do padrão de covariáveis: prevê uma
    vez por padrão e devolve às linhas."""
    chaves = list(explain.CHAVES_PADRAO)
    if df[chaves].isna().any().any():
        raise ValueError("há covariáveis ausentes no E1 (a população deveria excluí-las)")
    codigo = df.groupby(chaves, observed=True, sort=False).ngroup().to_numpy()
    _, primeiros = np.unique(codigo, return_index=True)  # códigos 0..k-1, na ordem dos códigos
    padroes = df.iloc[primeiros][chaves].reset_index(drop=True)
    X = explain.matriz_de_desenho(padroes, e1.nos, e1.pares_incluidos)
    if set(X.columns) != set(e1.colunas):
        raise ValueError("o desenho do E1 não bate com as colunas do artefato")
    eta = X[list(e1.colunas)].to_numpy(dtype=float) @ np.asarray(e1.params, dtype=float)
    return (1.0 / (1.0 + np.exp(-eta)))[codigo]


@dataclass(frozen=True)
class Predicoes:
    """Predições alinhadas às linhas de `df`: probabilidades (M1, B0, B1, E1), flag da B2 e os
    limiares do modelo congelado (M1, B0, B1)."""

    probabilidades: dict[str, np.ndarray]
    b2: np.ndarray
    limiares: dict[str, float]


def predizer(modelos: Modelos, df: pd.DataFrame, *, dentro_do_teste: bool) -> Predicoes:
    """Prevê com os modelos congelados. `dentro_do_teste=True` só na avaliação de 2024."""

    def _wrappers() -> dict[str, np.ndarray]:
        return {"M1": modelos.m1.prever_proba(df),
                "B0": modelos.baselines.b0.predizer(df),
                "B1": modelos.baselines.b1.predizer(df)}

    if dentro_do_teste:
        with guard.leitura_do_teste():
            probs = _wrappers()
    else:
        probs = _wrappers()
    probs["E1"] = prever_e1(modelos.e1, df)
    for nome, p in probs.items():
        p_arr = np.asarray(p, dtype=float)
        if p_arr.shape != (len(df),) or not np.isfinite(p_arr).all():
            raise ValueError(f"{nome}: predição com tamanho errado ou valor não finito")
    limiares = {"M1": float(modelos.m1.limiar), "B0": float(modelos.baselines.b0.limiar),
                "B1": float(modelos.baselines.b1.limiar)}
    return Predicoes(probabilidades={k: np.asarray(v, dtype=float) for k, v in probs.items()},
                     b2=np.asarray(baselines.rule_b2(df), dtype=bool), limiares=limiares)


# --- selecao.json (limiar F2 da curva de decisão) -------------------------------------------

def validar_limiar_f2(conteudo: dict) -> float:
    """`limiar_f2` do `selecao.json`: precisa ser um número finito em [0, 1] (não booleano). Levanta
    ValueError antes de qualquer leitura de 2024 se faltar ou se for inválido."""
    valor = conteudo.get("limiar_f2") if isinstance(conteudo, dict) else None
    if (isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor)
            or not 0.0 <= valor <= 1.0):
        raise ValueError("selecao.json sem `limiar_f2` válido (número em [0, 1]): a curva de "
                         "decisão não pode marcar o ponto F2")
    return float(valor)


def carregar_selecao(cfg: dict) -> dict:
    """Lê `<dados>/m1/selecao.json` (T-4.9) e devolve {"conteudo", "sha256", "caminho"}. O SHA-256 é
    o dos bytes do arquivo e vai para o `LACRE.json`."""
    caminho = runner.pasta_m1(cfg) / selecao.NOME_SELECAO
    if not caminho.exists():
        raise FileNotFoundError(f"sem {selecao.NOME_SELECAO} em {caminho.parent}: a T-4.9 precisa "
                                "rodar antes (o limiar F2 da curva de decisão vem dele)")
    conteudo_bytes = caminho.read_bytes()
    return {"conteudo": json.loads(conteudo_bytes.decode("utf-8")),
            "sha256": hashlib.sha256(conteudo_bytes).hexdigest(), "caminho": str(caminho)}


# --- População: conferência antes de qualquer cálculo ----------------------------------------

def _ler_esperado_teste(caminho: Path = ESPERADO_PADRAO) -> dict:
    return yaml.safe_load(caminho.read_text(encoding="utf-8"))["teste"]


def conferir_populacao(pop: pd.DataFrame, esperado: dict) -> dict:
    """Confere casos, eventos e eventos por região de 2024 com `esperado` (data-model).

    Levanta ValueError com os totais divergentes. Quem chama não grava nada. Devolve os totais
    observados (agregados) quando bate.
    """
    casos = int(len(pop))
    eventos = int(pop["y"].sum())
    regioes = (pop.loc[pop["y"] == 1, "regiao"].astype("string").fillna("<sem região>")
               .value_counts())
    por_regiao = {str(k): int(v) for k, v in regioes.items()}
    erros = []
    if casos != esperado["populacao_total"]:
        erros.append(f"casos {casos} (esperado {esperado['populacao_total']})")
    if eventos != esperado["eventos_total"]:
        erros.append(f"eventos {eventos} (esperado {esperado['eventos_total']})")
    for regiao, valor in esperado["eventos_por_regiao"].items():
        if por_regiao.get(regiao, 0) != valor:
            erros.append(f"eventos em {regiao} {por_regiao.get(regiao, 0)} (esperado {valor})")
    if set(por_regiao) - set(esperado["eventos_por_regiao"]):
        erros.append("eventos em região fora do esperado")
    if erros:
        raise ValueError("população de 2024 diverge de config/esperado.yaml (data-model › Tamanho "
                         "e prevalência): " + "; ".join(erros) + ". Nada foi gravado (D-93).")
    return {"casos": casos, "eventos": eventos, "eventos_por_regiao": por_regiao}


def _hash_dados_do_teste(cfg: dict) -> dict:
    """SHA-256 do parquet de 2024 e do .dbc, conferidos com `data/manifest.json` (D-46)."""
    ano = cfg["ano_teste"]
    manifesto = json.loads((runner._caminho(cfg, "dados") / "manifest.json").read_text(
        encoding="utf-8"))
    registro = manifesto[str(ano)]
    sha_arquivo = runner._sha256(dataset.parquet_path(cfg, ano))
    if sha_arquivo != registro["sha256_parquet"]:
        raise ValueError(f"parquet de {ano} diferente do manifesto: dado alterado (D-46)")
    return {"ano": ano, "sha256_dbc": registro["sha256_dbc"], "sha256_parquet": sha_arquivo}


# --- Métricas (a análise 1; as análises seguintes reusam os mesmos blocos) -------------------

_ic = teste_analises.ic
_com_ic = teste_analises.com_ic


@dataclass(frozen=True)
class ResultadoMetricas:
    casos: int
    eventos: int
    json: dict
    iteracoes_maximas: int  # registro para a verificação (não vai para o JSON: R7)
    processos: int = 1  # processos do bootstrap (registro: não entra no JSON, que não depende dele)
    # Distribuição por reamostra de cada "modelo/métrica" (agregados, não vão para os arquivos):
    # permite conferir o pareamento e os ICs reamostra a reamostra.
    distribuicoes: dict = field(default_factory=dict)


def _processos_efetivos(processos: int | None, n: int) -> int:
    """`processos` pedido (None = todos os núcleos), no mínimo 1 e no máximo `n` reamostras."""
    disponivel = os.cpu_count() or 1
    return max(1, min(int(disponivel if processos is None else processos), n))


def _flags(predicoes: Predicoes) -> dict[str, np.ndarray]:
    """Flag de alto risco de M1, B0, B1 (probabilidade >= limiar congelado) e da regra B2, NESTA
    ordem: a ordem define as células do bootstrap, e a análise dos critérios reusa os sorteios da
    T-5.1."""
    probs = predicoes.probabilidades
    marcados = {nome: probs[nome] >= predicoes.limiares[nome] for nome in COM_LIMIAR}
    marcados[NOME_B2] = np.asarray(predicoes.b2, dtype=bool)
    return marcados


def _montar(y_arr: np.ndarray, predicoes: Predicoes) -> tuple[metrics.Reamostrador, dict, dict]:
    """Agrupa as linhas em células e prepara o estado do bootstrap no processo principal
    (`metrics.montar_estado`, o mesmo que os subgrupos da T-5.2 usam).

    Devolve o estado, os vetores grandes (os que vão para a memória compartilhada) e os pequenos
    (`meta`, picklável).
    """
    probs = predicoes.probabilidades
    return metrics.montar_estado(y_arr, {nome: probs[nome] for nome in PROBABILISTICOS},
                                 _flags(predicoes))


def calcular_metricas(y, predicoes: Predicoes, *, seed: int, n: int,
                      processos: int | None = None) -> ResultadoMetricas:
    """Métricas do Plano de avaliação com IC 95% por bootstrap de `n` reamostras.

    Para M1, B0, B1 e E1: PR-AUC, ROC-AUC, Brier, calibration slope e intercepto. Para M1, B0 e
    B1 e para a regra B2: acurácia, precisão, recall, F1 e F2 no limiar. Diferenças de PR-AUC
    pareadas (M1 − B0 e M1 − B1). B0 prevê uma constante: o slope não é definido e fica `None`.

    Intercepto = calibração-no-grande (logística com offset logit(p), como
    `calibration_slope_intercept`).
    Slope = coeficiente de logit(p) numa logística com intercepto livre.

    Bootstrap (D-53, D-93): estratificado por alvo, com sub-semente própria por reamostra
    (`SeedSequence(seed).spawn(n)`), os mesmos sorteios para todos os modelos. As linhas idênticas
    viram células, e o sorteio é multinomial sobre elas (`metrics.agrupar_celulas`, `Sorteio`).
    `processos`: nº de processos do cálculo (None = `os.cpu_count()`); o resultado não depende dele.
    """
    if n < 1:
        raise ValueError("n: pelo menos uma reamostra")
    y_arr = np.asarray(y).astype(np.int64)
    processos = _processos_efetivos(processos, n)
    estado, grandes, meta = _montar(y_arr, predicoes)
    pontos, limiar_pontos = estado.pontos()
    iteracoes_pontos = max(max(c.iteracoes_slope, c.iteracoes_intercepto)
                           for c in estado.calibracoes.values())
    sementes = metrics.sementes_das_reamostras(seed, n)
    dist, iteracoes = metrics.rodar_reamostras(estado, grandes, meta, sementes, processos)
    iteracoes = max(iteracoes, iteracoes_pontos)

    modelos_json: dict[str, Any] = {}
    for nome in PROBABILISTICOS:
        ponto = pontos[nome]
        bloco: dict[str, Any] = {
            "tipo": "probabilidade calibrada" if nome == "M1" else "probabilidade",
            "pr_auc": _com_ic(ponto["pr_auc"], dist[f"{nome}/pr_auc"]),
            "roc_auc": _com_ic(ponto["roc_auc"], dist[f"{nome}/roc_auc"]),
            "brier": _com_ic(ponto["brier"], dist[f"{nome}/brier"]),
            "intercepto": _com_ic(ponto["intercepto"], dist[f"{nome}/intercepto"]),
            "obs_esp": _com_ic(ponto["obs_esp"], dist[f"{nome}/obs_esp"]),
        }
        if ponto["slope"] is None:
            bloco["slope"] = None
            bloco["slope_motivo"] = "previsão constante: o slope não é definido"
        else:
            bloco["slope"] = _com_ic(ponto["slope"], dist[f"{nome}/slope"])
        if nome in COM_LIMIAR:
            bloco["limiar"] = predicoes.limiares[nome]
            bloco["no_limiar"] = _bloco_no_limiar(nome, limiar_pontos, dist)
        modelos_json[nome] = bloco
    modelos_json[NOME_B2] = {"tipo": "regra (flag)", "limiar": LIMIAR_B2,
                             "no_limiar": _bloco_no_limiar(NOME_B2, limiar_pontos, dist)}

    diferencas = {}
    for a, b in PARES_DIFERENCA:
        diferencas[f"{a}_menos_{b}"] = _com_ic(pontos[a]["pr_auc"] - pontos[b]["pr_auc"],
                                               dist[f"{a}/pr_auc"] - dist[f"{b}/pr_auc"])

    json_resultado = {
        "casos": _celula(len(y_arr)),
        "eventos": _celula(int(y_arr.sum())),
        "semente": int(seed),
        "reamostras": int(n),
        "modelos": modelos_json,
        "diferencas_pr_auc": diferencas,
    }
    return ResultadoMetricas(casos=len(y_arr), eventos=int(y_arr.sum()), json=json_resultado,
                             iteracoes_maximas=int(iteracoes), processos=processos,
                             distribuicoes=dist)


def _bloco_no_limiar(nome: str, pontos: dict, dist: dict) -> dict:
    ponto = pontos[nome]
    bloco: dict[str, Any] = {k: _com_ic(ponto[k], dist[f"{nome}/limiar_{k}"])
                             for k in METRICAS_NO_LIMIAR}
    bloco["alertas"] = _celula(int(ponto["marcados"]))
    bloco["eventos_capturados"] = _celula(int(ponto["vp"]))
    return bloco


# --- Pontos de extensão: análises -----------------------------------------------------------

@dataclass(frozen=True)
class Contexto:
    """O que uma análise recebe. `df` são as linhas avaliadas (2024 no teste; 2022–23 no ensaio).
    Uma análise lê, não grava e não devolve linha de `df` (R7). `registros` recebe medidas de
    execução para a verificação (não vai para os arquivos)."""

    cfg: dict
    modo: str  # "teste" ou "ensaio"
    y: np.ndarray
    predicoes: Predicoes
    df: pd.DataFrame
    seed: int
    n_metricas: int
    registros: dict = field(default_factory=dict)
    processos: int | None = None  # processos do bootstrap (None = os.cpu_count())
    # `selecao.json` da T-4.9 (`carregar_selecao`): "conteudo", "sha256" e "caminho". Preenchido
    # pela avaliação e pelo ensaio; a análise da curva de decisão lê `limiar_f2` daqui.
    selecao: dict | None = None
    # Saídas das análises que já rodaram (na ordem de `ANALISES_PADRAO`): a calibração reaproveita
    # slope, intercepto e obs/esp da análise "metricas" em vez de recalculá-los.
    anteriores: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Saida:
    """O que uma análise devolve: tabelas agregadas, trecho de markdown e dict para o JSON."""

    tabelas: dict[str, pd.DataFrame]
    markdown: str
    json: dict
    # Nome de um arquivo markdown próprio (ex.: "erros.md"). Sem ele, o trecho entra no metricas.md.
    arquivo: str | None = None


@dataclass(frozen=True)
class Analise:
    nome: str
    executar: Callable[[Contexto], Saida]


def _validar_saida(nome: str, saida: Saida) -> None:
    if not isinstance(saida, Saida):
        raise TypeError(f"análise {nome!r} devolveu {type(saida).__name__}, não Saida")
    for tabela_nome, tabela in saida.tabelas.items():
        if not isinstance(tabela, pd.DataFrame):
            raise TypeError(f"{nome}/{tabela_nome}: a tabela precisa ser DataFrame")
        if len(tabela) > LIMITE_LINHAS_TABELA:
            raise ValueError(f"{nome}/{tabela_nome}: {len(tabela)} linhas; o agregado tem no "
                             f"máximo {LIMITE_LINHAS_TABELA} (R7)")
        pequenos = _inteiros_pequenos_na_tabela(tabela)
        if pequenos:
            raise ValueError(f"{nome}/{tabela_nome}: contagem de 1 a 9 na coluna {pequenos[0]!r} "
                             "(R7): use <10")
    if not isinstance(saida.markdown, str):
        raise TypeError(f"{nome}: o markdown precisa ser texto")
    if saida.arquivo is not None and (
            not saida.arquivo.endswith(".md") or Path(saida.arquivo).name != saida.arquivo
            or saida.arquivo == ARQ_MARKDOWN):
        raise ValueError(f"{nome}: `arquivo` precisa ser um nome simples .md, diferente de "
                         f"{ARQ_MARKDOWN}")
    json.dumps(saida.json, default=str)  # falha se houver objeto que não vira JSON


def _inteiros_pequenos_na_tabela(tabela: pd.DataFrame) -> list[str]:
    """Colunas com inteiro de 1 a 9 (R7: uma contagem assim vira "<10"). Colunas de ponto
    flutuante e texto não contam; `COLUNAS_ESTRUTURAIS` lista as de inteiros que não são casos."""
    achadas = []
    for coluna in tabela.columns:
        if coluna in COLUNAS_ESTRUTURAIS:
            continue
        valores = tabela[coluna].tolist()
        if any(isinstance(v, (int, np.integer)) and not isinstance(v, bool) and 1 <= v <= 9
               for v in valores):
            achadas.append(str(coluna))
    return achadas


def analise_metricas(ctx: Contexto) -> Saida:
    """Análise 1 (T-5.1): métricas do Plano de avaliação com IC e diferenças pareadas."""
    res = calcular_metricas(ctx.y, ctx.predicoes, seed=ctx.seed, n=ctx.n_metricas,
                            processos=ctx.processos)
    ctx.registros["iteracoes_newton_maximas"] = res.iteracoes_maximas
    ctx.registros["processos_bootstrap"] = res.processos
    return Saida(tabelas={"metricas": _tabela_resumo(res.json)},
                 markdown=_md_metricas(res.json), json=res.json)


def _limiar_f2(ctx: Contexto) -> tuple[float, str]:
    """`limiar_f2` do `selecao.json` (T-4.9) e o SHA-256 do arquivo. Levanta ValueError se a
    seleção não veio ou se `limiar_f2` não é um número em [0, 1]."""
    if ctx.selecao is None:
        raise ValueError("a curva de decisão precisa do selecao.json (limiar F2): "
                         "o contexto veio sem seleção")
    return validar_limiar_f2(ctx.selecao["conteudo"]), ctx.selecao["sha256"]


def analise_decisao(ctx: Contexto) -> Saida:
    """Análise 2 (T-5.2): curva de decisão (D-39) de M1, B1 e da regra B2, com "tratar todos" e
    "ninguém", em `dca_limiares` do config. Marca no M1 o limiar principal (congelado com o modelo,
    recall >= B2, D-92) e o limiar F2 (secundário, do `selecao.json`). Bandas de IC 95%
    (`bootstrap.metricas` reamostras, células por faixa de limiar, mesmos sorteios para todos)."""
    limiar_f2, sha_selecao = _limiar_f2(ctx)
    grade = teste_analises.grade_de_limiares(ctx.cfg)
    probs = ctx.predicoes.probabilidades
    marcados = {"M1_principal": float(ctx.predicoes.limiares["M1"]), "M1_f2": limiar_f2}
    res = teste_analises.curva_de_decisao(
        ctx.y, {"M1": probs["M1"], "B1": probs["B1"]}, ctx.predicoes.b2, grade, marcados,
        seed=ctx.seed, n=ctx.n_metricas, nome_regra=NOME_B2)
    j = teste_analises.decisao_em_json(
        res, grade, marcados, ctx.n_metricas, NOME_B2,
        {"M1_principal": "limiar congelado com o modelo (D-92)",
         "M1_f2": "limiar_f2 do selecao.json (T-4.9)"})
    j["limiar_f2"] = limiar_f2
    j["selecao_sha256"] = sha_selecao
    return Saida(tabelas={"curva_decisao": teste_analises.tabela_decisao(j)},
                 markdown=teste_analises.markdown_decisao(j), json=j)


def analise_calibracao(ctx: Contexto) -> Saida:
    """Análise 3 (T-5.2): curva de calibração por caixas, com bandas (`bootstrap.calibracao`
    reamostras), para M1 e E1. Slope, intercepto e observado/esperado globais vêm da análise
    "metricas" (T-5.1), sem recálculo."""
    n = int(ctx.cfg["bootstrap"]["calibracao"])
    probs = ctx.predicoes.probabilidades
    res = teste_analises.calibracao_por_caixas(
        ctx.y, {"M1": probs["M1"], "E1": probs["E1"]}, caixas=teste_analises.CAIXAS_CALIBRACAO,
        seed=ctx.seed, n=n)
    anterior = ctx.anteriores.get("metricas")
    globais = {}
    if anterior is not None:
        for nome in ("M1", "E1"):
            bloco = anterior.json["modelos"][nome]
            globais[nome] = {k: bloco.get(k) for k in ("slope", "intercepto", "obs_esp")}
    j = teste_analises.calibracao_em_json(res, n, globais)
    return Saida(tabelas=teste_analises.tabelas_calibracao(j),
                 markdown=teste_analises.markdown_calibracao(j), json=j)


def analise_subgrupos(ctx: Contexto) -> Saida:
    """Análise 4 (T-5.2): M1 (e a regra B2, como referência) por faixa etária, sexo, gestante,
    região e raça/cor, com IC por bootstrap dentro de cada subgrupo. Política de reamostras sem
    convergência e avisos de IC largo: ver `teste_analises`."""
    j = teste_analises.analisar_subgrupos(
        ctx.df, ctx.y, ctx.predicoes.probabilidades["M1"], ctx.predicoes.b2,
        float(ctx.predicoes.limiares["M1"]), ctx.cfg, seed=ctx.seed, n=ctx.n_metricas,
        processos=ctx.processos)
    ctx.registros["processos_subgrupos"] = teste_analises.processos_efetivos(
        ctx.processos, ctx.n_metricas)
    return Saida(tabelas={"subgrupos": teste_analises.tabela_subgrupos(j)},
                 markdown=teste_analises.markdown_subgrupos(j), json=j)


ARQ_ERROS = "erros.md"
ARQ_CRITERIOS = "criterios.md"


def analise_erros(ctx: Contexto) -> Saida:
    """Análise 5 (T-5.3): os 100 falsos negativos de maior risco em agregados, calibração por célula
    de comorbidade e Espírito Santo à parte. Vai para `erros.md`. Ver `teste_erros`."""
    anterior = ctx.anteriores.get("metricas")
    globais = None if anterior is None else {
        "obs_esp": anterior.json["modelos"]["M1"]["obs_esp"]}
    j = teste_erros.analisar_erros(
        ctx.df, ctx.y, ctx.predicoes.probabilidades["M1"], ctx.predicoes.b2,
        float(ctx.predicoes.limiares["M1"]), ctx.cfg, seed=ctx.seed, n=ctx.n_metricas,
        processos=ctx.processos, globais=globais)
    ctx.registros["processos_erros"] = teste_analises.processos_efetivos(
        ctx.processos, ctx.n_metricas)
    return Saida(tabelas=teste_erros.tabelas_erros(j), markdown=teste_erros.markdown_erros(j),
                 json=j, arquivo=ARQ_ERROS)


def analise_criterios(ctx: Contexto) -> Saida:
    """Análise 6 (T-5.4): SC-01 a SC-04. Lê a análise `metricas` (diferenças de PR-AUC e slope,
    sem recalcular) e calcula só a diferença de recall e precisão contra a B2. Vai para
    `criterios.md`."""
    anterior = ctx.anteriores.get("metricas")
    if anterior is None:
        raise ValueError("a análise 'criterios' lê a análise 'metricas': ela precisa rodar antes "
                         "(ordem de ANALISES_PADRAO)")
    sc02 = teste_criterios.diferencas_no_limiar(
        ctx.y, _flags(ctx.predicoes), seed=ctx.seed, n=ctx.n_metricas)
    j = teste_criterios.avaliar_criterios(anterior.json, sc02)
    return Saida(tabelas={"criterios": teste_criterios.tabela_criterios(j)},
                 markdown=teste_criterios.markdown_criterios(j), json=j, arquivo=ARQ_CRITERIOS)


ANALISES_PADRAO: list[Analise] = [
    Analise("metricas", analise_metricas),
    Analise("decisao", analise_decisao),
    Analise("calibracao", analise_calibracao),
    Analise("subgrupos", analise_subgrupos),
    Analise("erros", analise_erros),
    Analise("criterios", analise_criterios),
]


def executar_analises(ctx: Contexto, analises: list[Analise]) -> dict[str, Saida]:
    """Roda as análises em ordem e valida cada saída. Nada é gravado aqui. Cada saída fica em
    `ctx.anteriores` para as análises seguintes, e o tempo de cada uma em `ctx.registros`."""
    saidas: dict[str, Saida] = {}
    tempos: dict[str, float] = ctx.registros.setdefault("tempos_analises", {})
    for analise in analises:
        if analise.nome in saidas:
            raise ValueError(f"análise repetida: {analise.nome}")
        inicio = time.perf_counter()
        saida = analise.executar(ctx)
        _validar_saida(analise.nome, saida)
        tempos[analise.nome] = round(time.perf_counter() - inicio, 3)
        saidas[analise.nome] = saida
        ctx.anteriores[analise.nome] = saida
    return saidas


# --- Relatórios ------------------------------------------------------------------------------

_num = teste_analises.num
_ic_txt = teste_analises.ic_txt


def _tabela_resumo(json_res: dict) -> pd.DataFrame:
    linhas = []
    for nome, bloco in json_res["modelos"].items():
        for chave in ("pr_auc", "roc_auc", "brier", "slope", "intercepto", "obs_esp"):
            if bloco.get(chave) is not None:
                linhas.append({"modelo": nome, "metrica": chave, **bloco[chave]})
        for chave in METRICAS_NO_LIMIAR:
            if "no_limiar" in bloco:
                linhas.append({"modelo": nome, "metrica": f"no_limiar_{chave}",
                               **bloco["no_limiar"][chave]})
    for par, bloco in json_res["diferencas_pr_auc"].items():
        linhas.append({"modelo": par, "metrica": "diferenca_pr_auc", **bloco})
    return pd.DataFrame(linhas)


def _md_metricas(json_res: dict) -> str:
    linhas = [
        "## Métricas de probabilidade (IC 95% por bootstrap)",
        "",
        "| Modelo | PR-AUC | ROC-AUC | Brier | Calibration slope | Intercepto | Obs/esp |",
        "|---|---|---|---|---|---|---|",
    ]
    for nome in PROBABILISTICOS:
        b = json_res["modelos"][nome]
        slope = ("não definido (previsão constante)" if b["slope"] is None
                 else _ic_txt(b["slope"], 3))
        linhas.append(f"| {nome} | {_ic_txt(b['pr_auc'], 6)} | {_ic_txt(b['roc_auc'], 4)} | "
                      f"{_ic_txt(b['brier'], 6)} | {slope} | {_ic_txt(b['intercepto'], 3)} | "
                      f"{_ic_txt(b['obs_esp'], 3)} |")
    linhas += [
        "",
        "## Métricas no limiar (IC 95%)",
        "",
        "| Modelo | Limiar | Acurácia | Precisão | Recall | F1 | F2 | Alertas | "
        "Eventos capturados |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for nome in (*COM_LIMIAR, NOME_B2):
        b = json_res["modelos"][nome]
        nl = b["no_limiar"]
        linhas.append(f"| {nome} | {_num(b.get('limiar'), 6)} | {_ic_txt(nl['acuracia'], 4)} | "
                      f"{_ic_txt(nl['precisao'], 5)} | {_ic_txt(nl['recall'], 4)} | "
                      f"{_ic_txt(nl['f1'], 5)} | {_ic_txt(nl['f2'], 5)} | "
                      f"{nl['alertas']} | {nl['eventos_capturados']} |")
    linhas += ["", "## Diferença de PR-AUC (pareada, mesmos sorteios)", "",
               "| Comparação | Diferença (IC 95%) |", "|---|---|"]
    for par, bloco in json_res["diferencas_pr_auc"].items():
        linhas.append(f"| {par.replace('_menos_', ' − ')} | {_ic_txt(bloco, 6)} |")
    linhas += ["",
               "Calibration slope de B0 não é definido: a previsão é a mesma para todos os casos. "
               "E1 é inferência (associação): não tem limiar, só métricas de probabilidade.", ""]
    return "\n".join(linhas)


def montar_markdown(execucao: Execucao) -> str:
    if execucao.modo == "teste":
        partes = ["# Avaliação final no teste: avaliação única em 2024 (R2)", "", AVISO_TESTE, ""]
    else:
        partes = ["# Ensaio do pipeline de avaliação em 2022–23", "", f"> **{AVISO_ENSAIO}**", ""]
    partes += ["## Dados", "",
               f"- Casos: {_celula(execucao.casos)}; eventos: {_celula(execucao.eventos)} "
               f"(prevalência {_num(100.0 * execucao.eventos / execucao.casos, 3)}%).", ""]
    if execucao.alertas:
        partes += ["Alertas de qualidade FR-03 disparados (valor < 10 aparece como <10):", ""]
        partes += [f"- {a['ano']}: {a['alerta']}: {a['valor']}" for a in execucao.alertas]
        partes.append("")
    for nome, saida in execucao.saidas.items():
        if saida.arquivo is None:
            partes += [saida.markdown, ""]
        else:
            partes += [f"## Análise `{nome}`", "", f"O resultado está em `{saida.arquivo}`.", ""]
    partes += ["---", "Gerado pelo pipeline de avaliação (T-5.1). Só agregados; sem linhas "
               "individuais (R7)."]
    return "\n".join(partes) + "\n"


def montar_markdown_arquivo(execucao: Execucao, nome: str, saida: Saida) -> str:
    """Markdown de uma análise com arquivo próprio (`erros.md`, `criterios.md`): título, aviso do
    modo (teste ou ensaio) e o trecho da análise."""
    titulos = {"erros": "Análise de erros do M1 no teste (T-5.3)",
               "criterios": "Critérios de sucesso SC-01 a SC-04 (T-5.4)"}
    titulo = titulos.get(nome, f"Análise {nome}")
    if execucao.modo == "teste":
        cabecalho = [f"# {titulo}", "", AVISO_TESTE, ""]
    else:
        cabecalho = [f"# {titulo}: ensaio em 2022–23", "", f"> **{AVISO_ENSAIO}**", ""]
    return "\n".join([*cabecalho, saida.markdown, "", "---",
                      "Só agregados; sem linhas individuais (R7)."]) + "\n"


def montar_json(execucao: Execucao) -> dict:
    return {
        "aviso": AVISO_TESTE if execucao.modo == "teste" else AVISO_ENSAIO,
        "modo": execucao.modo,
        "ano": execucao.ano,
        "casos": _celula(execucao.casos),
        "eventos": _celula(execucao.eventos),
        "alertas_fr03": execucao.alertas,
        "analises": {nome: saida.json for nome, saida in execucao.saidas.items()},
    }


# --- Execução --------------------------------------------------------------------------------

@dataclass
class Execucao:
    modo: str
    ano: int
    casos: int
    eventos: int
    alertas: list[dict]
    saidas: dict[str, Saida]
    seed: int
    n_metricas: int
    iteracoes_maximas: int
    tempos: dict[str, float]
    anos_lidos: list[int]
    eventos_por_regiao: dict[str, int]
    payloads: dict
    commit: str
    arvore_limpa: bool | None
    ordem: list[str] = field(default_factory=list)
    markdown: str = ""
    json_texto: str = ""
    processos: int = 1  # processos do bootstrap (registro da execução; não entra nos relatórios)
    ambiente: list = field(default_factory=list)  # checks do ambiente, conferidos antes da carga
    selecao: dict | None = None  # {"sha256", "limiar_f2"} do selecao.json lido (vai para o lacre)
    tabelas_csv: dict[str, str] = field(default_factory=dict)  # arquivo -> texto CSV (T-5.2)
    arquivos_md: dict[str, str] = field(default_factory=dict)  # erros.md, criterios.md (T-5.3/5.4)
    tempos_analises: dict[str, float] = field(default_factory=dict)
    registros: dict = field(default_factory=dict)  # medidas de execução (não vão aos arquivos)


@dataclass(frozen=True)
class Fontes:
    """De onde vêm a população e os modelos. Padrão: os reais; os testes trocam por sintéticos."""

    populacao: Callable[[dict], pd.DataFrame]
    hash_dados: Callable[[dict], dict]
    modelos: Callable[[dict], Modelos]
    features: Callable[[pd.DataFrame], pd.DataFrame] = dataset.build_feature_frame
    # Confere o ambiente (D-64) ANTES de ler 2024: devolve os checks de `verify.environment`. O
    # padrão não confere nada (testes sintéticos); `FONTES_TESTE` usa a conferência real.
    ambiente: Callable[[dict], list[dict]] = lambda cfg: []  # noqa: E731
    # `selecao.json` da T-4.9 (dict com "conteudo" e "sha256"): o limiar F2 da curva de decisão. É
    # lido e validado ANTES de ler 2024. Os testes sintéticos trocam por uma seleção falsa.
    selecao: Callable[[dict], dict] = carregar_selecao


def _populacao_teste(cfg: dict) -> pd.DataFrame:
    return dataset.load_population(cfg, [cfg["ano_teste"]], teste=True)


def _populacao_dev(cfg: dict) -> pd.DataFrame:
    # Sem escrita: o fluxograma de 2022–23 não é tocado pelo ensaio (só reports/ensaio).
    return dataset.load_population_with_flow(cfg, list(cfg["anos_dev"]))[0]


FONTES_TESTE = Fontes(populacao=_populacao_teste, hash_dados=_hash_dados_do_teste,
                      modelos=carregar_modelos, ambiente=verify.environment)
FONTES_ENSAIO = Fontes(populacao=_populacao_dev, hash_dados=lambda cfg: {},
                       modelos=carregar_modelos)


def _csv_das_tabelas(saidas: dict[str, Saida]) -> dict[str, str]:
    """Texto CSV de cada tabela agregada (`<analise>__<tabela>.csv`), em memória até o fim."""
    return {f"{nome}__{tabela}.csv": quadro.to_csv(index=False, lineterminator="\n")
            for nome, saida in saidas.items() for tabela, quadro in saida.tabelas.items()}


def _calcular(cfg: dict, df: pd.DataFrame, modelos: Modelos, *, modo: str,
              dentro_do_teste: bool, analises: list[Analise], tempos: dict,
              ordem: list[str], alertas: list[dict], selecao_lida: dict | None = None
              ) -> Execucao:
    """Predições e análises em memória. Não imprime nem grava nada."""
    inicio = time.perf_counter()
    predicoes = predizer(modelos, df, dentro_do_teste=dentro_do_teste)
    tempos["predicao_s"] = round(time.perf_counter() - inicio, 3)
    registros: dict[str, Any] = {}
    ctx = Contexto(cfg=cfg, modo=modo, y=df["y"].to_numpy(), predicoes=predicoes, df=df,
                   seed=int(cfg["seed"]), n_metricas=int(cfg["bootstrap"]["metricas"]),
                   registros=registros, processos=cfg["bootstrap"].get("processos"),
                   selecao=selecao_lida)
    inicio = time.perf_counter()
    saidas = executar_analises(ctx, analises)
    tempos["analises_s"] = round(time.perf_counter() - inicio, 3)
    ordem.append("calculo_concluido")
    regioes = (df.loc[df["y"] == 1, "regiao"].astype("string").fillna("<sem região>")
               .value_counts())
    execucao = Execucao(
        modo=modo, ano=int(cfg["ano_teste"]), casos=int(len(df)), eventos=int(df["y"].sum()),
        alertas=alertas, saidas=saidas, seed=int(cfg["seed"]),
        n_metricas=int(cfg["bootstrap"]["metricas"]),
        iteracoes_maximas=int(registros.get("iteracoes_newton_maximas", 0)), tempos=tempos,
        anos_lidos=sorted(int(a) for a in df["ANO"].unique()),
        eventos_por_regiao={str(k): int(v) for k, v in regioes.items()},
        payloads=modelos.payloads, commit=verify.commit_atual(), arvore_limpa=_arvore_limpa(),
        ordem=ordem, processos=int(registros.get("processos_bootstrap", 1)),
        selecao=(None if selecao_lida is None else
                 {"sha256": selecao_lida["sha256"],
                  "limiar_f2": validar_limiar_f2(selecao_lida["conteudo"])}),
        tabelas_csv=_csv_das_tabelas(saidas),
        tempos_analises=dict(registros.get("tempos_analises", {})), registros=registros,
    )
    execucao.markdown = montar_markdown(execucao)
    execucao.arquivos_md = {saida.arquivo: montar_markdown_arquivo(execucao, nome, saida)
                            for nome, saida in saidas.items() if saida.arquivo is not None}
    execucao.json_texto = json.dumps(montar_json(execucao), ensure_ascii=False, indent=2,
                                     sort_keys=True) + "\n"
    return execucao


def evaluate_test_once(cfg: dict, *, fontes: Fontes | None = None,
                       analises: list[Analise] | None = None) -> Execucao:
    """Avaliação única em 2024 (T-5.1). Erro antes de ler qualquer dado se o lacre existir.

    Grava `metricas.md`, `metricas.json` e, por último, `LACRE.json`. Qualquer erro antes de gravar
    deixa a pasta sem lacre, e a próxima execução é permitida.
    """
    pasta = _pasta_do_teste(cfg)
    if (pasta / ARQ_LACRE).exists():
        raise RuntimeError("teste já avaliado (R2)")
    fontes = FONTES_TESTE if fontes is None else fontes
    analises = ANALISES_PADRAO if analises is None else analises
    ambiente = fontes.ambiente(cfg)  # antes de ler qualquer dado de 2024 (D-64)
    reprovados = [c["nome"] for c in ambiente if not c["passou"]]
    if reprovados:
        raise RuntimeError("ambiente fora do exigido (D-64): " + ", ".join(reprovados)
                           + ". Nada foi lido nem gravado.")
    selecao_lida = fontes.selecao(cfg)  # antes de ler 2024: sem limiar F2 válido, nada é lido
    validar_limiar_f2(selecao_lida["conteudo"])
    tempos: dict[str, float] = {}
    inicio = time.perf_counter()
    with _capturar_avisos() as avisos, guard.leitura_do_teste():  # só aqui a carga de 2024 abre
        pop = fontes.populacao(cfg)
    tempos["carga_s"] = round(time.perf_counter() - inicio, 3)
    totais = conferir_populacao(pop, _ler_esperado_teste())  # antes de qualquer cálculo
    dados_hash = fontes.hash_dados(cfg)
    modelos = fontes.modelos(cfg)
    df = fontes.features(pop).reset_index(drop=True)
    del pop
    if sorted(int(a) for a in df["ANO"].unique()) != [int(cfg["ano_teste"])]:
        raise RuntimeError("a avaliação recebeu linhas de outro ano (R1)")
    execucao = _calcular(cfg, df, modelos, modo="teste", dentro_do_teste=True,
                         analises=analises, tempos=tempos, ordem=[], alertas=avisos.alertas,
                         selecao_lida=selecao_lida)
    execucao.ambiente = ambiente
    _escrever_teste(cfg, execucao, pasta, totais, dados_hash)
    return execucao


def ensaiar_em_desenvolvimento(cfg: dict, *, fontes: Fontes | None = None,
                               analises: list[Analise] | None = None) -> Execucao:
    """Ensaio do pipeline em 2022–23: erros e tempo antes do teste. Não é avaliação (ver topo)."""
    fontes = FONTES_ENSAIO if fontes is None else fontes
    analises = ANALISES_PADRAO if analises is None else analises
    selecao_lida = fontes.selecao(cfg)
    validar_limiar_f2(selecao_lida["conteudo"])
    tempos: dict[str, float] = {}
    inicio = time.perf_counter()
    with _capturar_avisos() as avisos:
        pop = fontes.populacao(cfg)
    tempos["carga_s"] = round(time.perf_counter() - inicio, 3)
    modelos = fontes.modelos(cfg)
    df = fontes.features(pop).reset_index(drop=True)
    del pop
    guard.assert_dev_only(df)  # R1: o ensaio é só de desenvolvimento
    execucao = _calcular(cfg, df, modelos, modo="ensaio", dentro_do_teste=False,
                         analises=analises, tempos=tempos, ordem=[], alertas=avisos.alertas,
                         selecao_lida=selecao_lida)
    _escrever_ensaio(cfg, execucao)
    return execucao


def _escrever_teste(cfg: dict, execucao: Execucao, pasta: Path, totais: dict,
                    dados_hash: dict) -> None:
    """Grava os resultados e, por último, o lacre. Só chamada depois de tudo calculado.

    Se a gravação falhar no meio, remove (melhor esforço) o que ESTA execução gravou e relança o
    erro: a pasta fica sem resultados parciais e sem lacre. Nunca apaga um lacre que já existia.
    """
    gravados: list[Path] = []
    try:
        hashes = {}
        arquivos = [(ARQ_MARKDOWN, execucao.markdown), (ARQ_JSON, execucao.json_texto),
                    *sorted(execucao.arquivos_md.items()), *sorted(execucao.tabelas_csv.items())]
        for nome, texto in arquivos:
            _gravar_atomico(pasta / nome, texto)
            gravados.append(pasta / nome)
            execucao.ordem.append(f"gravado:{nome}")
            hashes[nome] = _sha256_texto(texto)
        lacre = {
            "aviso": "Lacre do teste (R2): existir aqui impede nova avaliação. Não apague.",
            "tarefa": TAREFA,
            "gravado_em_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
            "commit": execucao.commit,
            "arvore_limpa": execucao.arvore_limpa,
            "semente": int(cfg["seed"]),
            "hash_config": runner.hash_config(cfg),
            "reamostras": int(execucao.n_metricas),
            "artefatos": execucao.payloads,
            "selecao": execucao.selecao,
            "dados": {**dados_hash, "casos": execucao.casos, "eventos": execucao.eventos,
                      "eventos_por_regiao": totais["eventos_por_regiao"]},
            "relatorios": hashes,
        }
        _gravar_atomico(pasta / ARQ_LACRE,
                        json.dumps(lacre, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        execucao.ordem.append(f"gravado:{ARQ_LACRE}")
    except BaseException:
        for caminho in gravados:
            try:
                caminho.unlink(missing_ok=True)
            except OSError:  # melhor esforço: o erro original é o que importa
                logger.warning("não consegui remover %s", caminho)
        raise


def _escrever_ensaio(cfg: dict, execucao: Execucao) -> None:
    """Ensaio: só `reports/ensaio/`. Não toca `reports/teste/` nem cria lacre."""
    pasta = _pasta_do_ensaio(cfg)
    for nome, texto in ((ARQ_MARKDOWN, execucao.markdown), (ARQ_JSON, execucao.json_texto),
                        *sorted(execucao.arquivos_md.items()),
                        *sorted(execucao.tabelas_csv.items())):
        _gravar_atomico(pasta / nome, texto)
        execucao.ordem.append(f"gravado:ensaio/{nome}")


# --- Verificação (D-64) e linha de comando ---------------------------------------------------

def checks_teste(cfg: dict, execucao: Execucao, esperado: dict, *,
                 ambiente: list[dict] | None = None) -> list[dict]:
    """Checks do relatório `reports/verificacao/T-5.1.json`. Esperados vêm de `esperado.yaml`."""
    checks = [
        verify.check("populacao_2024_igual_ao_esperado", esperado["populacao_total"],
                     execucao.casos),
        verify.check("eventos_2024_igual_ao_esperado", esperado["eventos_total"],
                     execucao.eventos),
    ]
    for regiao, valor in esperado["eventos_por_regiao"].items():
        checks.append(verify.check(f"eventos_2024_{_nome_check(regiao)}_igual_ao_esperado",
                                   valor, execucao.eventos_por_regiao.get(regiao, 0)))
    checks += [
        verify.check("so_2024_lido_na_avaliacao", True,
                     execucao.anos_lidos == [int(cfg["ano_teste"])]),
        verify.check("artefatos_sha256_conferidos", True,
                     all(_sha_do_payload_confere(v) for v in execucao.payloads.values())),
        verify.check("nada_gravado_antes_do_fim", True,
                     execucao.ordem[:1] == ["calculo_concluido"]
                     and execucao.ordem[-1] == f"gravado:{ARQ_LACRE}"
                     and all(e.startswith("gravado") for e in execucao.ordem[1:])),
        verify.check("reamostras_metricas_do_config", esperado["bootstrap"]["metricas"],
                     execucao.n_metricas),
        verify.check("reamostras_calibracao_configuradas_para_t52",
                     esperado["bootstrap"]["calibracao"], cfg["bootstrap"]["calibracao"]),
        verify.check("semente_do_config", int(cfg["seed"]), execucao.seed),
        verify.check("sem_contagens_de_1_a_9_no_json", True,
                     artifacts.inteiros_pequenos(json.loads(execucao.json_texto)) == []),
        verify.registro("iteracoes_newton_maximas", execucao.iteracoes_maximas),
        verify.registro("alertas_fr03_disparados", len(execucao.alertas)),
        verify.registro("tempo_carga_s", execucao.tempos.get("carga_s", 0.0)),
        verify.registro("tempo_predicao_s", execucao.tempos.get("predicao_s", 0.0)),
        verify.registro("tempo_analises_s", execucao.tempos.get("analises_s", 0.0)),
        verify.registro("arvore_limpa", bool(execucao.arvore_limpa)),
        verify.registro("vcpus", int(os.cpu_count() or 0)),
        verify.registro("processos_bootstrap", int(execucao.processos)),
    ]
    checks += _checks_t52(cfg, execucao, esperado)
    checks += _checks_t53_t54(execucao)
    if ambiente:
        checks += ambiente
    return checks


def _checks_t52(cfg: dict, execucao: Execucao, esperado: dict) -> list[dict]:
    """Checks da T-5.2 (curva de decisão, calibração com bandas, subgrupos), lidos do JSON."""
    analises = json.loads(execucao.json_texto).get("analises", {})
    decisao, calibracao = analises.get("decisao", {}), analises.get("calibracao", {})
    subgrupos = analises.get("subgrupos", {})
    dca = cfg["dca_limiares"]
    limiares = decisao.get("limiares", [])
    na_faixa = bool(limiares) and all(
        dca["min"] - 1e-12 <= t <= dca["max"] + 1e-12 for t in limiares)
    f2 = decisao.get("limiar_f2")
    f2_lido = (execucao.selecao is not None and f2 == execucao.selecao["limiar_f2"]
               and decisao.get("selecao_sha256") == execucao.selecao["sha256"])
    dimensoes = subgrupos.get("dimensoes", {})
    particoes_ok = (set(dimensoes) == set(teste_analises.DIMENSOES)
                    and all(d["particao_completa"] and d["subgrupos"] for d in dimensoes.values()))
    descartadas = [s["metricas"]["calibracao"]["reamostras_descartadas"]
                   for d in dimensoes.values() for s in d["subgrupos"].values() if s["metricas"]]
    tabelas_ok = all(_inteiros_pequenos_na_tabela(t) == []
                     for saida in execucao.saidas.values() for t in saida.tabelas.values())
    checks = [
        verify.check("curva_decisao_com_os_limiares_do_config", int(dca["passos"]),
                     len(limiares)),
        verify.check("curva_decisao_dentro_de_dca_min_e_max", True, na_faixa),
        verify.check("bandas_de_calibracao_com_as_reamostras_do_config",
                     esperado["bootstrap"]["calibracao"], calibracao.get("reamostras")),
        verify.check("reamostras_dos_subgrupos_do_config", esperado["bootstrap"]["metricas"],
                     subgrupos.get("reamostras")),
        verify.check("limiar_f2_lido_do_selecao_json", True, bool(f2_lido)),
        verify.check("subgrupos_presentes_por_particao", True, particoes_ok),
        verify.check("politica_de_reamostras_descartadas_registrada", True,
                     bool(subgrupos.get("politica_descarte"))
                     and subgrupos.get("limite_descarte") == teste_analises.LIMITE_DESCARTE),
        verify.check("sem_contagens_de_1_a_9_nas_tabelas", True, tabelas_ok),
        verify.registro("subgrupos_com_reamostras_descartadas",
                        sum(1 for d in descartadas if d != 0)),
    ]
    checks += [verify.registro(f"tempo_analise_{nome}_s", t)
               for nome, t in sorted(execucao.tempos_analises.items())]
    return checks


def _checks_t53_t54(execucao: Execucao) -> list[dict]:
    """Checks da T-5.3 (análise de erros) e da T-5.4 (critérios), lidos do JSON gravado."""
    analises = json.loads(execucao.json_texto).get("analises", {})
    erros, criterios = analises.get("erros", {}), analises.get("criterios", {})
    fn = erros.get("falsos_negativos", {})
    total = fn.get("total")
    pedido = teste_erros.N_FALSOS_NEGATIVOS
    esperado_fn = pedido if (isinstance(total, int) and total >= pedido) else total
    fn_ok = (erros.get("n_pedido") == pedido and fn.get("n_perfil") == esperado_fn
             and fn.get("n_perfil") is not None)
    grupos = erros.get("espirito_santo", {}).get("grupos", {})
    es_ok = (set(grupos) == {"ES", "resto_do_brasil"}
             and bool(erros.get("espirito_santo", {}).get("criterio_uf")))
    tabelas_ok = all(_inteiros_pequenos_na_tabela(t) == []
                     for nome in ("erros", "criterios") if nome in execucao.saidas
                     for t in execucao.saidas[nome].tabelas.values())
    n_config = str(execucao.n_metricas)  # reamostras pequenas saem como texto (R7)
    n_ok = (str(erros.get("reamostras")) == n_config
            and str(criterios.get("sc02", {}).get("reamostras_do_sc02")) == n_config)
    criterios_ok = all(
        c in criterios and all(campo in criterios[c] for campo in teste_criterios.CAMPOS)
        for c in teste_criterios.CRITERIOS)
    return [
        verify.check("erros_com_n_falsos_negativos_do_config", True, bool(fn_ok)),
        verify.check("erros_sem_contagens_de_1_a_9", True,
                     artifacts.inteiros_pequenos(erros) == [] and bool(erros) and tabelas_ok),
        verify.check("criterios_sc01_a_sc04_presentes", True, bool(criterios_ok)),
        verify.check("espirito_santo_a_parte_presente", True, bool(es_ok)),
        verify.check("reamostras_dos_erros_e_do_sc02_do_config", True, bool(n_ok)),
        *(verify.registro(f"{c}_passou", criterios[c]["passou"])
          for c in teste_criterios.CRITERIOS if c in criterios and "passou" in criterios[c]),
    ]


def _nome_check(regiao: str) -> str:
    return regiao.lower().replace("-", "_").replace(" ", "_")


def _sha_do_payload_confere(info: dict) -> bool:
    pasta = Path(info["pasta"])
    return all(runner._sha256(pasta / "payload" / arq) == sha
               for arq, sha in info["sha256_payload"].items())


def gerar_verificacao_do_lacre(cfg: dict, *, ambiente: list[dict] | None = None) -> Path:
    """Gera `reports/verificacao/T-5.1.json` de uma avaliação JÁ lacrada, sem recalcular nada e
    sem ler 2024 (use se `write_report` falhou depois do lacre; não rode a avaliação de novo).

    Lê `LACRE.json` (população, eventos, artefatos, semente, reamostras, hashes dos relatórios) e
    confere os hashes de `metricas.md` e `metricas.json`. Medidas que só existiam na execução
    (tempos, iterações do Newton, ordem de gravação, anos lidos) não são recalculadas: a ordem e
    os anos vêm do próprio lacre, e o relatório marca `verificacao_regenerada_do_lacre`.
    """
    pasta = _pasta_do_teste(cfg)
    caminho_lacre = pasta / ARQ_LACRE
    if not caminho_lacre.exists():
        raise FileNotFoundError("sem LACRE.json: não há avaliação lacrada para verificar")
    lacre = json.loads(caminho_lacre.read_text(encoding="utf-8"))
    hashes_ok = all(
        _sha256_texto((pasta / nome).read_text(encoding="utf-8")) == sha
        for nome, sha in lacre["relatorios"].items())
    dados = lacre["dados"]
    execucao = Execucao(
        modo="teste", ano=int(dados.get("ano", cfg["ano_teste"])), casos=int(dados["casos"]),
        eventos=int(dados["eventos"]), alertas=[], saidas={}, seed=int(lacre["semente"]),
        n_metricas=int(lacre["reamostras"]), iteracoes_maximas=0, tempos={},
        anos_lidos=[int(dados.get("ano", cfg["ano_teste"]))],
        eventos_por_regiao=dict(dados["eventos_por_regiao"]),
        payloads=lacre["artefatos"], commit=lacre["commit"], arvore_limpa=lacre["arvore_limpa"],
        ordem=["calculo_concluido", f"gravado:{ARQ_MARKDOWN}", f"gravado:{ARQ_JSON}",
               f"gravado:{ARQ_LACRE}"],
        markdown=(pasta / ARQ_MARKDOWN).read_text(encoding="utf-8"),
        json_texto=(pasta / ARQ_JSON).read_text(encoding="utf-8"),
        processos=0, ambiente=verify.environment(cfg) if ambiente is None else ambiente,
        selecao=lacre.get("selecao"))
    checks = checks_teste(cfg, execucao, _ler_esperado_teste(), ambiente=execucao.ambiente)
    checks += [verify.check("relatorios_conferem_com_o_lacre", True, hashes_ok),
               verify.registro("verificacao_regenerada_do_lacre", True)]
    return verify.write_report(TAREFA, checks, runner._caminho(cfg, "relatorios") / "verificacao",
                               cfg)


def main(argv: list[str] | None = None) -> int:
    """`python -m dengue_sinan.evaluate --config <yaml> [--ensaio]`. 0 se passou, 1 se não.

    O resumo só é impresso no fim, com agregados. Sem `--ensaio`, grava também
    `reports/verificacao/T-5.1.json`.
    """
    parser = argparse.ArgumentParser(prog="python -m dengue_sinan.evaluate")
    parser.add_argument("--config", required=True, type=Path,
                        help="config YAML (ex.: config/base.yaml)")
    parser.add_argument("--ensaio", action="store_true",
                        help="ensaio em 2022–23: não toca 2024 nem o lacre")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s")
    try:
        cfg = load_config(args.config)
        if args.ensaio:
            execucao = ensaiar_em_desenvolvimento(cfg)
            passou = True
            resumo = {"modo": "ensaio (não é avaliação)", "casos": _celula(execucao.casos),
                      "tempos_s": execucao.tempos, "tempos_analises_s": execucao.tempos_analises,
                      "pasta": str(_pasta_do_ensaio(cfg))}
        else:
            execucao = evaluate_test_once(cfg)
            try:
                checks = checks_teste(cfg, execucao, _ler_esperado_teste(),
                                      ambiente=execucao.ambiente)
                relatorio = verify.write_report(
                    TAREFA, checks, runner._caminho(cfg, "relatorios") / "verificacao", cfg)
                passou = json.loads(relatorio.read_text(encoding="utf-8"))["passou"]
            except Exception:
                logger.exception(
                    "a avaliação terminou e o LACRE já foi gravado (R2), mas o relatório de "
                    "verificação falhou. NÃO rode a avaliação de novo: ela seria recusada. Gere "
                    "só o relatório com evaluate.gerar_verificacao_do_lacre(cfg), a partir dos "
                    "resultados gravados")
                return 1
            resumo = {"modo": "avaliação única em 2024 (R2)", "casos": _celula(execucao.casos),
                      "eventos": _celula(execucao.eventos), "passou_verificacao": passou,
                      "tempos_s": execucao.tempos, "tempos_analises_s": execucao.tempos_analises,
                      "relatorio": str(relatorio)}
    except Exception:
        logger.exception("avaliação não concluída: nenhum resultado foi gravado")
        return 1
    print(json.dumps(resumo, indent=2, ensure_ascii=False))
    return 0 if passou else 1


if __name__ == "__main__":
    sys.exit(main())
