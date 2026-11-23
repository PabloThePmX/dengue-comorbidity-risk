"""Congelamento de B0 e B1 antes do teste (T-5.0, D-93, FR-12, R1, R3, R5, R7, P4).

Roda uma vez, numa sessão só com 2022–23 (R1). Faz, nesta ordem:

1. Carrega a população de desenvolvimento (`dataset.load_population` com `anos_dev`) e a guarda
   `assert_dev_only`. Nenhum dado de 2024 entra aqui.
2. Recalcula os limiares de B0 e B1 das OOF da T-2.8 (`<dados>/oof/oof_B0.parquet` e
   `oof_B1.parquet`, lidas com `selecao._ler_oof`, guarda R1 incluída) com
   `metrics.threshold_for_min_recall` e o `recall_alvo` de `<dados>/m1/selecao.json` (D-92,
   predição bruta, sem calibração). É reprodução do mesmo cálculo da T-4.9, não reajuste. O
   relatório confere cada limiar com a tabela "Métricas no limiar" de
   `reports/m1/comparacao_oof.md` (tolerância 5e-7) e confere que o recall no limiar é >= o alvo.
3. Ajusta o B1 em **todo** 2022–23 com `baselines.ajustar_b1` (o mesmo pipeline do OOF da T-2.8:
   sem penalização, sem pesos de classe). Calcula a prevalência do B0 nesse período.
4. Grava os dois com `artifacts.save_bundle` em `<modelos>/b1_final/` e `<modelos>/b0_final/`.

B0 e B1 não são calibrados: a predição é a probabilidade bruta do modelo.

`carregar_baselines(destino)` devolve `Baselines`, com `b0` e `b1`; cada um tem `predizer(df)`
(probabilidade bruta) e `limiar`. `predizer` não consulta a guarda de 2024: a T-5.1 precisa prever
o teste, como `retreino.ModeloFinal.prever_proba` faz. A regra B2 continua sem artefato
(`baselines.rule_b2`).

Entrada de linha de comando: `python -m dengue_sinan.baselines_final --config <yaml>`. Grava
`reports/verificacao/T-5.0.json` (D-64) e sai com 0 se `passou`, 1 se não.

Privacidade (R7): os artefatos trazem parâmetros, prevalência, limiares e totais do ajuste. A
amostra de conferência fica só na memória e nunca é gravada.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import math
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.pipeline import Pipeline

from dengue_sinan import artifacts, baselines, dataset, metrics, runner, selecao, verify
from dengue_sinan.config import load_config
from dengue_sinan.guard import assert_dev_only

logger = logging.getLogger(__name__)

TAREFA = "T-5.0"
NOME_B0 = "b0_final"
NOME_B1 = "b1_final"
ARQ_B1 = "b1.joblib"
ARQ_B0 = "b0.json"
NOMES_LIMIAR = ("B0", "B1")
ESPERADO_PADRAO = verify.REPO / "config" / "esperado.yaml"
AMOSTRA_CONFERENCIA = 2000  # linhas (só em memória) para conferir a recarga
TOLERANCIA_RECARGA = 0.0  # a recarga na mesma máquina tem de dar a mesma predição, bit a bit
TOLERANCIA_TABELA = 5e-7 + 1e-12  # tabela com 6 casas: erro máximo 5e-7; 1e-12 é o ruído do float
ARQ_TABELA = "comparacao_oof.md"  # em `<relatorios>/m1/`
SECAO_TABELA = "## 3. Métricas no limiar"
CAMPOS_FR12 = (*artifacts.CAMPOS_OBRIGATORIOS, "schema_version", "tipo_payload", "criado_em_utc",
               "versao_codigo", "bibliotecas", "payload")
AVISO_BASELINE = ("ajuste em todo 2022–23, sem validação de parada nem calibração; limiar "
                  "recalculado do OOF (D-92); métricas de validação no OOF da T-2.8 (R1)")


# --- Validação numérica ----------------------------------------------------------------------

def validar_fracao(valor: Any, nome: str) -> float:
    """Número finito em [0, 1] (limiar, recall ou prevalência). Outro valor levanta erro."""
    if isinstance(valor, bool) or not isinstance(valor, int | float):
        raise ValueError(f"{nome} não é número: {valor!r}")
    numero = float(valor)
    if not math.isfinite(numero) or not 0.0 <= numero <= 1.0:
        raise ValueError(f"{nome} fora de [0, 1]: {numero}")
    return numero


# --- Limiares de B0 e B1: recalculados do OOF (D-93, D-92) -----------------------------------

def recall_alvo_da_selecao(sel: dict) -> float:
    """`recall_alvo` do `selecao.json` (recall da B2 no OOF): alvo do limiar (D-92)."""
    if "recall_alvo" not in sel:
        raise ValueError("selecao.json sem recall_alvo (D-92)")
    return validar_fracao(sel["recall_alvo"], "recall_alvo")


def ler_oofs_baselines(cfg: dict) -> tuple[dict[str, selecao._Oof], dict[str, str]]:
    """OOF de B0 e B1 (T-2.8), lidos como a T-4.9 lê (`selecao._ler_oof`: guarda R1 e regiões).

    Confere que B0 e B1 têm as mesmas linhas na mesma ordem (ANO, região, y), que é o
    pareamento que a seleção exige. Devolve (oofs, SHA-256 de cada arquivo).
    """
    pasta = runner._caminho(cfg, "dados") / "oof"
    ordem = list(cfg["ordem_dobras"])
    caminhos = {nome: pasta / f"oof_{nome}.parquet" for nome in NOMES_LIMIAR}
    oofs = {nome: selecao._ler_oof(caminhos[nome], ordem) for nome in NOMES_LIMIAR}
    b0, b1 = oofs["B0"], oofs["B1"]
    if not (np.array_equal(b0.ano, b1.ano) and np.array_equal(b0.dobra, b1.dobra)
            and np.array_equal(b0.y, b1.y)):
        raise ValueError("oof_B0 e oof_B1 com linhas fora de ordem entre si")
    return oofs, {nome: runner._sha256(caminhos[nome]) for nome in NOMES_LIMIAR}


def limiar_recalculado(oof: selecao._Oof, recall_alvo: float) -> float:
    """Limiar D-92 na predição bruta do OOF: precisão máxima com recall >= `recall_alvo`."""
    return validar_fracao(metrics.threshold_for_min_recall(oof.y, oof.p, recall_alvo),
                          "limiar recalculado")


def ler_limiares_da_tabela(caminho: Path) -> dict[str, float]:
    """Coluna Limiar das linhas B0 e B1 da seção "Métricas no limiar" de comparacao_oof.md.

    Números com vírgula decimal (pt-BR). Seção ou linha ausente, ou linha repetida, levanta
    ValueError. Arquivo ausente levanta FileNotFoundError.
    """
    if not caminho.exists():
        raise FileNotFoundError(f"sem {ARQ_TABELA} em {caminho.parent}: o relatório da T-4.9 "
                                "precisa estar no checkout (ele é versionado no git)")
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    inicio = next((i for i, linha in enumerate(linhas) if linha.startswith(SECAO_TABELA)), None)
    if inicio is None:
        raise ValueError(f"{ARQ_TABELA}: sem a seção '{SECAO_TABELA}'")
    valores: dict[str, float] = {}
    for linha in linhas[inicio + 1:]:
        if linha.startswith("#"):  # fim da seção: a 3.1 (F2, D-33) repete B0 e B1 com outro limiar
            break
        celulas = [c.strip() for c in linha.split("|")]  # celulas[0] é antes da 1ª barra
        if len(celulas) > 2 and celulas[1] in NOMES_LIMIAR:
            if celulas[1] in valores:
                raise ValueError(f"{ARQ_TABELA}: linha {celulas[1]} repetida na seção")
            valores[celulas[1]] = float(celulas[2].replace(",", "."))
    faltam = [nome for nome in NOMES_LIMIAR if nome not in valores]
    if faltam:
        raise ValueError(f"{ARQ_TABELA}: sem linha de {faltam} na seção '{SECAO_TABELA}'")
    return valores


# --- Tipos de payload (registro em artifacts, como o M1) -------------------------------------

@dataclass(frozen=True)
class B1Final:
    """B1 ajustado em 2022–23 com o limiar recalculado do OOF. Probabilidade bruta, sem calibrar."""

    modelo: Pipeline
    limiar: float

    def predizer(self, df: pd.DataFrame) -> np.ndarray:
        return self.modelo.predict_proba(df[baselines.COLUNAS_B1])[:, 1].astype(float)


@dataclass(frozen=True)
class B0Final:
    """B0: prevalência de 2022–23 para todo caso, com o limiar recalculado do OOF."""

    prevalencia: float
    limiar: float

    def predizer(self, df: pd.DataFrame) -> np.ndarray:
        return np.full(len(df), self.prevalencia, dtype=float)


def _salvar_b1(obj: B1Final, pasta: Path, metadados: dict) -> list[str]:
    joblib.dump({"modelo": obj.modelo, "limiar": obj.limiar}, pasta / ARQ_B1, compress=3)
    return [ARQ_B1]


def _carregar_b1(pasta: Path) -> B1Final:
    conteudo = joblib.load(pasta / ARQ_B1)
    if (not isinstance(conteudo, dict) or set(conteudo) != {"modelo", "limiar"}
            or not isinstance(conteudo["modelo"], Pipeline)):
        raise artifacts.ArtefatoInvalido("b1: payload fora do formato esperado")
    try:
        limiar = validar_fracao(conteudo["limiar"], "limiar de B1")
    except ValueError as erro:
        raise artifacts.ArtefatoInvalido(str(erro)) from erro
    return B1Final(modelo=conteudo["modelo"], limiar=limiar)


def _salvar_b0(obj: B0Final, pasta: Path, metadados: dict) -> list[str]:
    texto = json.dumps({"prevalencia": obj.prevalencia, "limiar": obj.limiar},
                       ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (pasta / ARQ_B0).write_text(texto, encoding="utf-8")
    return [ARQ_B0]


def _carregar_b0(pasta: Path) -> B0Final:
    conteudo = json.loads((pasta / ARQ_B0).read_text(encoding="utf-8"))
    if not isinstance(conteudo, dict) or set(conteudo) != {"prevalencia", "limiar"}:
        raise artifacts.ArtefatoInvalido("b0: payload fora do formato esperado")
    try:
        prevalencia = validar_fracao(conteudo["prevalencia"], "prevalência de B0")
        limiar = validar_fracao(conteudo["limiar"], "limiar de B0")
    except ValueError as erro:
        raise artifacts.ArtefatoInvalido(str(erro)) from erro
    return B0Final(prevalencia=prevalencia, limiar=limiar)


TIPO_B1 = artifacts.Tipo(nome="b1", reconhece=lambda obj: isinstance(obj, B1Final),
                         salvar=_salvar_b1, carregar=_carregar_b1)
TIPO_B0 = artifacts.Tipo(nome="b0", reconhece=lambda obj: isinstance(obj, B0Final),
                         salvar=_salvar_b0, carregar=_carregar_b0)
artifacts.registrar_tipo(TIPO_B1)
artifacts.registrar_tipo(TIPO_B0)


@dataclass(frozen=True)
class Baselines:
    """B0 e B1 congelados. Para a T-5.1: `b0.predizer(df)`, `b1.predizer(df)`, `.limiar`."""

    b0: B0Final
    b1: B1Final


def carregar_baselines(destino: str | Path) -> Baselines:
    """Carrega `<destino>/b0_final` e `<destino>/b1_final`, conferindo os SHA-256 (artifacts)."""
    raiz = Path(destino)
    b0 = artifacts.load_bundle(raiz / NOME_B0)
    b1 = artifacts.load_bundle(raiz / NOME_B1)
    if not isinstance(b0, B0Final) or not isinstance(b1, B1Final):
        raise artifacts.ArtefatoInvalido("pasta de baselines com tipo inesperado")
    return Baselines(b0=b0, b1=b1)


# --- Ajuste e gravação -----------------------------------------------------------------------

@dataclass(frozen=True)
class Congelamento:
    """O que `congelar_baselines` gravou e o que a conferência precisa (só agregados, R7)."""

    raiz: Path
    anos: tuple[int, ...]
    n_casos: int
    n_eventos: int
    prevalencia: float
    limiares: dict[str, float]  # recalculados do OOF (D-92)
    recall_alvo: float
    recall_no_limiar: dict[str, float]
    criterio_limiar: str
    sha_selecao: str
    sha_oof: dict[str, str]
    caminho_tabela: Path  # comparacao_oof.md, usado na conferência
    tempo_ajuste_b1_s: float
    amostra: pd.DataFrame  # só na memória: não é gravada (R7)
    p_b1: np.ndarray  # predição do B1 na amostra, antes da gravação
    p_b0: np.ndarray  # predição do B0 na amostra, antes da gravação


def carregar_desenvolvimento(cfg: dict) -> pd.DataFrame:
    """População de 2022–23 com as features de `dataset.build_feature_frame` (R1: guarda)."""
    populacao = dataset.load_population(cfg, list(cfg["anos_dev"]))
    df = dataset.build_feature_frame(populacao).reset_index(drop=True)
    assert_dev_only(df)
    return df


def _ler_selecao(cfg: dict) -> tuple[dict, str]:
    """`selecao.json` da T-4.9 e o SHA-256 dos bytes dele (vai para o metadata)."""
    caminho = runner.pasta_m1(cfg) / selecao.NOME_SELECAO
    if not caminho.exists():
        raise FileNotFoundError(f"sem {selecao.NOME_SELECAO} em {caminho}: a T-4.9 precisa rodar")
    return json.loads(caminho.read_text(encoding="utf-8")), runner._sha256(caminho)


def _agora() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def _metadados(cfg: dict, nome: str, features: list[str], limiar: float, criterio: str,
               sha_selecao: str, sha_oof: str, recall_alvo: float, n_casos: int,
               n_eventos: int) -> dict:
    """Campos FR-12 e o bloco `baseline`. Só totais e parâmetros: nenhuma contagem por termo."""
    return {
        "config": cfg,
        "dados": artifacts.hashes_dados(cfg),
        "data_treino": _agora(),
        "metricas_validacao": {
            "aviso": AVISO_BASELINE,
            "limiar": limiar,
            "criterio_limiar": criterio,
            "n_casos_ajuste": n_casos,
            "n_eventos_ajuste": n_eventos,
        },
        "features": list(features),
        "baseline": {
            "nome": nome,
            "tarefa": TAREFA,
            "limiar_origem": (f"recalculado de oof_{nome}.parquet com threshold_for_min_recall "
                              f"(D-92); recall_alvo de {selecao.NOME_SELECAO}"),
            "recall_alvo": recall_alvo,
            "hash_oof": sha_oof,
            "hash_selecao": sha_selecao,
            "calibrado": False,
            "pesos_de_classe": None,
        },
    }


def congelar_baselines(cfg: dict, destino: str | Path | None = None) -> Congelamento:
    """Recalcula os limiares, ajusta B1 e calcula B0 em 2022–23 e grava os dois em `destino`.

    `destino` padrão: `caminhos.modelos`. Confere antes de ajustar: população só de anos de
    desenvolvimento (R1, guarda em `selecao._ler_oof`), `recall_alvo` e OOF válidos. Se algo
    falhar, nada é gravado.
    """
    raiz = Path(destino) if destino is not None else runner._caminho(cfg, "modelos")
    df = carregar_desenvolvimento(cfg)  # R1
    sel, sha_selecao = _ler_selecao(cfg)
    recall_alvo = recall_alvo_da_selecao(sel)
    oofs, sha_oof = ler_oofs_baselines(cfg)  # antes de treinar: falha cedo
    limiares = {nome: limiar_recalculado(oofs[nome], recall_alvo) for nome in NOMES_LIMIAR}
    recall_no_limiar = {
        nome: metrics.threshold_metrics(oofs[nome].y, oofs[nome].p, limiares[nome])["recall"]
        for nome in NOMES_LIMIAR
    }
    criterio = str(sel.get("criterio_limiar", ""))

    inicio = time.perf_counter()
    b1 = B1Final(modelo=baselines.ajustar_b1(df), limiar=limiares["B1"])  # R1, R3, R5
    tempo_ajuste = time.perf_counter() - inicio
    prevalencia = float(df[baselines.COLUNA_ALVO].mean())
    b0 = B0Final(prevalencia=prevalencia, limiar=limiares["B0"])

    amostra = df.iloc[:AMOSTRA_CONFERENCIA]
    p_b1 = b1.predizer(amostra)
    p_b0 = b0.predizer(amostra)
    n_casos = len(df)
    n_eventos = int(df[baselines.COLUNA_ALVO].sum())
    anos = tuple(sorted(int(a) for a in df[baselines.COLUNA_ANO].unique()))

    artifacts.save_bundle(b1, raiz / NOME_B1, _metadados(
        cfg, "B1", baselines.COLUNAS_B1, b1.limiar, criterio, sha_selecao, sha_oof["B1"],
        recall_alvo, n_casos, n_eventos))
    artifacts.save_bundle(b0, raiz / NOME_B0, _metadados(
        cfg, "B0", [], b0.limiar, criterio, sha_selecao, sha_oof["B0"], recall_alvo,
        n_casos, n_eventos))

    return Congelamento(
        raiz=raiz, anos=anos, n_casos=n_casos, n_eventos=n_eventos, prevalencia=prevalencia,
        limiares=limiares, recall_alvo=recall_alvo, recall_no_limiar=recall_no_limiar,
        criterio_limiar=criterio, sha_selecao=sha_selecao, sha_oof=sha_oof,
        caminho_tabela=runner._caminho(cfg, "relatorios") / "m1" / ARQ_TABELA,
        tempo_ajuste_b1_s=tempo_ajuste, amostra=amostra, p_b1=p_b1, p_b0=p_b0,
    )


# --- Verificação (D-64) ----------------------------------------------------------------------

def _maior_diferenca(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.max(np.abs(np.asarray(a) - np.asarray(b)))) if len(a) else 0.0


def conferir(cfg: dict, cong: Congelamento, esperado: dict) -> list[dict]:
    """Checks do bloco T-5.0. `esperado` é a seção `desenvolvimento` de config/esperado.yaml."""
    try:
        carregados = carregar_baselines(cong.raiz)
    except artifacts.ArtefatoInvalido as erro:
        return [verify.check("baselines_carregam", True, False),
                verify.registro("erro_carga", type(erro).__name__)]

    checks = [
        verify.check("casos_2022_2023", esperado["populacao_total"], cong.n_casos),
        verify.check("eventos_2022_2023", esperado["eventos_total"], cong.n_eventos),
        verify.check("so_anos_de_desenvolvimento", True,
                     set(cong.anos) <= {int(a) for a in cfg["anos_dev"]}),
        verify.check("b1_predicoes_iguais_apos_carga", 0.0,
                     _maior_diferenca(cong.p_b1, carregados.b1.predizer(cong.amostra)),
                     TOLERANCIA_RECARGA),
        verify.check("b0_predicoes_iguais_apos_carga", 0.0,
                     _maior_diferenca(cong.p_b0, carregados.b0.predizer(cong.amostra)),
                     TOLERANCIA_RECARGA),
        verify.check("b0_prevalencia_igual_ao_ajuste", cong.prevalencia,
                     carregados.b0.prevalencia, TOLERANCIA_RECARGA),
        verify.check("limiar_b1_gravado_igual_recalculado", cong.limiares["B1"],
                     carregados.b1.limiar, TOLERANCIA_RECARGA),
        verify.check("limiar_b0_gravado_igual_recalculado", cong.limiares["B0"],
                     carregados.b0.limiar, TOLERANCIA_RECARGA),
        verify.check("recall_b1_no_limiar_ge_recall_alvo", True,
                     bool(cong.recall_no_limiar["B1"] >= cong.recall_alvo)),
        verify.check("recall_b0_no_limiar_ge_recall_alvo", True,
                     bool(cong.recall_no_limiar["B0"] >= cong.recall_alvo)),
        verify.check("criterio_limiar_d92", selecao.CRITERIO_LIMIAR, cong.criterio_limiar),
    ]
    try:
        tabela = ler_limiares_da_tabela(cong.caminho_tabela)
    except (FileNotFoundError, ValueError) as erro:
        checks += [verify.check("tabela_comparacao_oof_lida", True, False),
                   verify.registro("erro_tabela_comparacao_oof", str(erro))]
    else:
        checks += [
            verify.check(f"limiar_{nome.lower()}_recalculado_igual_tabela_comparacao_oof",
                         tabela[nome], cong.limiares[nome], TOLERANCIA_TABELA)
            for nome in NOMES_LIMIAR
        ]
    for nome, pasta, arquivo, tipo in (
        ("b1", cong.raiz / NOME_B1, ARQ_B1, "b1"),
        ("b0", cong.raiz / NOME_B0, ARQ_B0, "b0"),
    ):
        meta = artifacts.ler_metadados(pasta)
        checks += [
            verify.check(f"{nome}_tipo_payload", tipo, meta["tipo_payload"]),
            verify.check(f"{nome}_metadata_fr12_completo", True,
                         all(campo in meta for campo in CAMPOS_FR12)),
            verify.check(f"{nome}_sha256_payload", meta["payload"][arquivo],
                         runner._sha256(pasta / artifacts.PASTA_PAYLOAD / arquivo)),
            verify.check(f"{nome}_sem_contagens_de_1_a_9", True,
                         artifacts.inteiros_pequenos(meta) == []),
        ]
    checks += [
        verify.registro("prevalencia_b0_2022_2023", cong.prevalencia),
        verify.registro("tempo_ajuste_b1_s", round(cong.tempo_ajuste_b1_s, 3)),
    ]
    return checks


def executar(cfg: dict, destino: str | Path | None = None,
             esperado_path: Path | None = None) -> tuple[Path, dict]:
    """Congela, confere e grava `reports/verificacao/T-5.0.json`. Devolve (relatório, medidas)."""
    caminho_esperado = esperado_path if esperado_path is not None else ESPERADO_PADRAO
    esperado = yaml.safe_load(caminho_esperado.read_text(encoding="utf-8"))["desenvolvimento"]
    cong = congelar_baselines(cfg, destino)
    checks = conferir(cfg, cong, esperado)
    relatorio = verify.write_report(TAREFA, checks,
                                    runner._caminho(cfg, "relatorios") / "verificacao", cfg)
    medidas = {
        "pasta": str(cong.raiz),
        "casos": cong.n_casos,
        "eventos": cong.n_eventos,
        "prevalencia_b0": cong.prevalencia,
        "limiares": cong.limiares,
        "passou": json.loads(relatorio.read_text(encoding="utf-8"))["passou"],
    }
    return relatorio, medidas


def main(argv: Sequence[str] | None = None) -> int:
    """`python -m dengue_sinan.baselines_final --config <yaml>`: 0 se passou, 1 se não."""
    parser = argparse.ArgumentParser(prog="python -m dengue_sinan.baselines_final")
    parser.add_argument("--config", required=True, type=Path,
                        help="config YAML da sessão (ex.: config/base.yaml)")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    try:
        cfg = load_config(args.config)
        _, medidas = executar(cfg)
    except Exception:
        logger.exception("congelamento dos baselines falhou")
        return 1
    print(json.dumps(medidas, indent=2, ensure_ascii=False))
    return 0 if medidas["passou"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
