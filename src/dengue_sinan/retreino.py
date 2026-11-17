"""Retreino final e congelamento do M1 (T-4.10, FR-12, FR-22, D-37, D-69, D-70, NFR-06).

Gancho `dengue_sinan.retreino:executar` do fim da sessão (`runner.GANCHOS_PADRAO`). Recebe
`(cfg, resultados)` e devolve os checks do bloco `retreino` do `sessao-m1.json`. Faz, nesta ordem:

1. Lê o vencedor, o limiar e o tipo do calibrador de `<dados>/m1/selecao.json` (T-4.9) e o
   calibrador de `<dados>/m1/<modelo>/`. Nada disso é reajustado (T-4.10).
2. Carrega 2022–23 (R1: `assert_dev_only`) e treina o vencedor em **todo** o período com os
   hiperparâmetros de `parametros.json`. Modelos iterativos: nº de árvores (XGBoost, CatBoost) ou
   de épocas (MLP) = **mediana** dos 5 melhores pontos das dobras, sem early stopping (D-37).
3. Grava `ModeloFinal` (modelo + calibrador + limiar + features) com `artifacts.save_bundle` em
   `<modelos>/m1_final` (FR-12). Depois de gravar, **carrega o que foi gravado** e mede: tamanho,
   tempo de predição de um caso e tempo do SHAP local, contra o limite de NFR-06 (1 s).
4. Modelo da demo (D-69, D-70): se o vencedor não cumpre os três critérios (não é TabFM, consulta
   em até 1 s e SHAP local viável), treina os candidatos na ordem do PR-AUC médio e grava o
   primeiro que cumpre em `<modelos>/m1_demo`. O vencedor continua sendo o M1 avaliado no teste.

Privacidade (R7, NFR-03): o artefato traz modelo, calibrador, limiar, nomes das features e um
vetor de médias para o fundo do SHAP do MLP (agregado, não linha). Nenhuma linha e nenhuma contagem
por nível: `artifacts.inteiros_pequenos` confere o metadado.

Leitura de atributos privados dos wrappers (`_pipeline`, `_estimador`): a mesma concessão de
`shap_global._componentes`, porque a explicação local depende do formato de cada modelo.

Para carregar um `m1_final` ou `m1_demo`, importe este módulo antes de `artifacts.load_bundle`:
é aqui que o tipo `m1` é registrado (o artefato é um joblib de `ModeloFinal`).
"""

from __future__ import annotations

import datetime as dt
import functools
import logging
import shutil
import statistics
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import shap
import torch
import yaml

from dengue_sinan import artifacts, cv, preprocess, runner, selecao, shap_global, verify
from dengue_sinan.catboost_m1 import CatBoostM1
from dengue_sinan.elastic_net_m1 import ElasticNetM1
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.mlp import MLPM1
from dengue_sinan.random_forest import RandomForestM1
from dengue_sinan.xgboost_m1 import XGBoostM1

logger = logging.getLogger(__name__)

TAREFA = "T-4.10"
BLOCO = "retreino"
TABFM = "tabfm"
NOME_FINAL = "m1_final"
NOME_DEMO = "m1_demo"
PASTA_TENTATIVAS = "_demo_tentativas"  # candidatos da demo ficam aqui até um ser promovido
ARQ_PAYLOAD = "m1.joblib"
COLUNA_ALVO = "y"
COLUNA_ANO = "ANO"
LIMITE_CONSULTA_S = 1.0  # NFR-06 e SC-06: a demo responde em < 1 s por consulta
REPETICOES_TEMPO = 5  # o tempo reportado é a mediana de 5 medições, depois de um aquecimento
AMOSTRA_CONFERENCIA = 2000  # linhas (em memória) para conferir as predições depois da carga
TOLERANCIA_RECARGA = 1e-9  # predições depois da carga iguais às de antes do salvamento (T-4.10)
# De `melhor_ponto` para a contagem usada no retreino. XGBoost e CatBoost guardam o índice da
# última árvore (0-based), então a contagem é índice + 1. O MLP guarda a época (1-based).
DESLOCAMENTO_PONTO = {"xgboost": 1, "catboost": 1, "mlp": 0}


# --- Artefato --------------------------------------------------------------------------------

@dataclass(frozen=True)
class ModeloFinal:
    """O que o artefato guarda: o modelo ajustado em 2022–23, calibrador e limiar da T-4.9.

    `prever_proba` devolve o risco calibrado. `referencia_shap` é o vetor de médias das features
    transformadas, usado como fundo do `GradientExplainer` do MLP (só agregado, R7); é None nos
    outros modelos.
    """

    nome: str
    modelo: Any  # wrapper de `cv.REGISTRO`, ajustado com nº fixo de iterações
    calibrador: selecao.Calibrador
    limiar: float
    features: list[str]
    referencia_shap: np.ndarray | None = None

    def prever_proba(self, X) -> np.ndarray:
        return self.calibrador.aplicar(self.modelo.prever_proba(X))


def _salvar_m1(obj: ModeloFinal, pasta: Path, metadados: dict) -> list[str]:
    """Codec do tipo `m1`: joblib do objeto (que contém o Pipeline do wrapper). A rede do MLP
    vai para a CPU antes, para o artefato carregar na demo, que não tem GPU."""
    if hasattr(obj.modelo, "para_cpu"):
        obj.modelo.para_cpu()
    joblib.dump(obj, pasta / ARQ_PAYLOAD, compress=3)
    return [ARQ_PAYLOAD]


def _carregar_m1(pasta: Path) -> ModeloFinal:
    return joblib.load(pasta / ARQ_PAYLOAD)


TIPO_M1 = artifacts.Tipo(
    nome="m1",
    reconhece=lambda obj: isinstance(obj, ModeloFinal),
    salvar=_salvar_m1,
    carregar=_carregar_m1,
)
artifacts.registrar_tipo(TIPO_M1)


# --- Regra de contagem (D-37) ----------------------------------------------------------------

def contagem_final(nome: str, pontos: Sequence[int | None]) -> int:
    """Nº de árvores ou épocas do retreino: a mediana dos melhores pontos das dobras (D-37).

    Exige um ponto por dobra e nº ímpar de dobras (com 5, a mediana é um dos pontos observados).
    """
    if nome not in DESLOCAMENTO_PONTO:
        raise ValueError(f"{nome}: sem regra de contagem (só modelos iterativos)")
    if not pontos or any(p is None for p in pontos):
        raise ValueError(f"{nome}: falta o melhor ponto de alguma dobra")
    if len(pontos) % 2 == 0:
        raise ValueError("a mediana dos melhores pontos precisa de nº ímpar de dobras")
    return int(statistics.median(pontos)) + DESLOCAMENTO_PONTO[nome]


def treinar_final(cfg: dict, nome: str, params: dict, df: pd.DataFrame,
                  pontos: Sequence[int | None]) -> tuple[Any, int | None]:
    """Treina o modelo em todo `df` (2022–23). Devolve (wrapper ajustado, nº de iterações ou None).

    Iterativo: `fixar_iteracoes` com a mediana e `ajustar` sem validação de parada. Não iterativo
    (RF, elastic net, TabFM): `ajustar` com o treino inteiro, como em `cv.run_loro`.
    """
    modelo = cv.construir_modelo(nome, params, cfg)
    iteracoes = None
    if modelo.iterativo:
        iteracoes = contagem_final(nome, pontos)
        modelo.fixar_iteracoes(iteracoes)
    modelo.ajustar(df, df[COLUNA_ALVO].to_numpy())
    return modelo, iteracoes


def _referencia_mlp(modelo: MLPM1, df: pd.DataFrame) -> np.ndarray:
    """Médias das features transformadas no treino: fundo de um GradientExplainer com uma linha."""
    pre = modelo._pipeline.named_steps["preprocessamento"]
    medias = np.asarray(pre.transform(df).mean(axis=0), dtype=np.float64).ravel()
    return medias


# --- Explicação local (TreeSHAP, pesos do elastic net, GradientExplainer) --------------------

def _linha_da_classe_positiva(valores, p: int) -> np.ndarray:
    """Valores de uma linha, na classe positiva, qualquer que seja o formato devolvido pelo shap."""
    v = valores[-1] if isinstance(valores, list) else valores
    v = np.asarray(v)
    if v.ndim == 3:  # (linhas, colunas, saídas)
        v = v[..., -1]
    if v.size != p:
        raise ValueError(f"shap devolveu {v.size} valores para {p} colunas")
    return v.reshape(p).astype(float)


def shap_local(final: ModeloFinal, X: pd.DataFrame) -> np.ndarray:
    """Contribuição de cada coluna de entrada (log-odds do modelo) para a predição de UMA linha.

    Árvores: TreeSHAP exato (XGBoost e CatBoost pela rota nativa de `shap_global`; RF pelo
    `shap.TreeExplainer`). Elastic net: coeficiente × valor (linear). MLP: `GradientExplainer`.
    TabFM: sem explicação local (levanta ValueError; D-69).
    """
    m = final.modelo
    if isinstance(m, (XGBoostM1, CatBoostM1)):
        tipo, pre, estimador, n_arvores = shap_global._componentes(m)
        X_t = pre.transform(X)
        p = X_t.shape[1]
        if tipo == "xgboost":
            contrib, _, _ = shap_global._lote_xgboost(estimador.get_booster(), X_t, n_arvores)
        else:  # o CatBoost precisa de uma cópia encurtada (`shrink`) até o melhor ponto
            copia = estimador.copy()
            copia.shrink(ntree_end=n_arvores)
            cat = preprocess.indices_cat_features_catboost(pre)
            contrib, _, _ = shap_global._lote_catboost(copia, X_t, cat)
        return np.asarray(contrib[0, :p], dtype=float)  # sem a coluna do viés
    if isinstance(m, RandomForestM1):
        pre = m._pipeline.named_steps["preprocessamento"]
        X_t = np.asarray(pre.transform(X), dtype=float)
        valores = shap.TreeExplainer(m._pipeline.named_steps["floresta"]).shap_values(X_t)
        return _linha_da_classe_positiva(valores, X_t.shape[1])
    if isinstance(m, ElasticNetM1):
        pre = m._pipeline.named_steps["preprocessamento"]
        X_t = pre.transform(X)
        X_t = np.asarray(X_t.toarray() if hasattr(X_t, "toarray") else X_t, dtype=float)[0]
        return np.asarray(m._estimador.coef_[0], dtype=float) * X_t
    if isinstance(m, MLPM1):
        if final.referencia_shap is None:
            raise ValueError("MLP sem vetor de referência para o SHAP (artefato incompleto)")
        pre = m._pipeline.named_steps["preprocessamento"]
        X_t = pre.transform(X)
        X_t = np.asarray(X_t.toarray() if hasattr(X_t, "toarray") else X_t, dtype=np.float32)
        fundo = torch.tensor(final.referencia_shap[None, :], dtype=torch.float32)
        explicador = shap.GradientExplainer(m._estimador._rede, fundo)
        valores = explicador.shap_values(torch.tensor(X_t, dtype=torch.float32))
        return _linha_da_classe_positiva(valores, X_t.shape[1])
    raise ValueError(f"sem SHAP local para {type(m).__name__} (D-69: TabFM não vai à demo)")


# --- Medição (NFR-06) ------------------------------------------------------------------------

@dataclass(frozen=True)
class Medicao:
    nome: str
    bytes_payload: int
    bytes_pasta: int
    tempo_predicao_s: float
    shap_viavel: bool
    tempo_shap_s: float | None
    erro_shap: str | None

    @property
    def tempo_consulta_s(self) -> float:
        """Tempo de uma consulta da aba Triagem: predição mais SHAP local."""
        return self.tempo_predicao_s + (self.tempo_shap_s or 0.0)


def razoes_fora_da_demo(medicao: Medicao) -> list[str]:
    """Motivos pelos quais o modelo não serve à demo (D-70). Lista vazia = cumpre os três."""
    razoes = []
    if medicao.nome == TABFM:
        razoes.append("TabFM não pode ir à demo (licença não comercial, D-69)")
    if not medicao.shap_viavel:
        razoes.append(f"SHAP local inviável ({medicao.erro_shap})")
    if medicao.shap_viavel and medicao.tempo_consulta_s > LIMITE_CONSULTA_S:
        razoes.append(f"{medicao.tempo_consulta_s:.3f} s por consulta, acima de 1 s (NFR-06)")
    return razoes


def cumpre_demo(medicao: Medicao) -> bool:
    return not razoes_fora_da_demo(medicao)


def ordem_demo(modelos: dict[str, dict], ordem_modelos: Sequence[str], vencedor: str) -> list[str]:
    """Candidatos à demo, do melhor PR-AUC médio ao pior, sem o vencedor e sem o TabFM (D-69)."""
    candidatos = [m for m in ordem_modelos if m != vencedor and m != TABFM]
    return sorted(candidatos,
                  key=lambda m: (-modelos[m]["pr_auc_media"], list(ordem_modelos).index(m)))


def _tempo_mediano(fn: Callable[[], object]) -> float:
    fn()  # aquecimento: primeira chamada carrega caches e cria explicadores
    tempos = []
    for _ in range(REPETICOES_TEMPO):
        inicio = time.perf_counter()
        fn()
        tempos.append(time.perf_counter() - inicio)
    return float(statistics.median(tempos))


def _tamanho_pasta(pasta: Path) -> int:
    return sum(arq.stat().st_size for arq in pasta.rglob("*") if arq.is_file())


def medir(carregado: ModeloFinal, pasta: Path, X_um: pd.DataFrame) -> Medicao:
    """Mede o artefato já carregado de `pasta` com uma linha de entrada (o que a demo faz)."""
    tempo_predicao = _tempo_mediano(lambda: carregado.prever_proba(X_um))
    try:
        tempo_shap = _tempo_mediano(lambda: shap_local(carregado, X_um))
        viavel, erro = True, None
    except Exception as erro_shap:  # o SHAP local é opcional: a falha vira medida, não aborta
        logger.warning("SHAP local de %s inviável: %s", carregado.nome, type(erro_shap).__name__)
        tempo_shap, viavel, erro = None, False, type(erro_shap).__name__
    return Medicao(
        nome=carregado.nome,
        bytes_payload=(pasta / "payload" / ARQ_PAYLOAD).stat().st_size,
        bytes_pasta=_tamanho_pasta(pasta),
        tempo_predicao_s=tempo_predicao,
        shap_viavel=viavel,
        tempo_shap_s=tempo_shap,
        erro_shap=erro,
    )


# --- Congelamento ----------------------------------------------------------------------------

@dataclass(frozen=True)
class Congelado:
    """Fatos de um modelo gravado e recarregado: o que vai para os checks do bloco."""

    nome: str
    papel: str  # "final" (vencedor) ou "demo"
    pasta: Path
    iteracoes: int | None
    medicao: Medicao
    carga_ok: bool
    diferenca_maxima: float
    sha256_no_metadata: str
    sha256_no_arquivo: str
    limiar: float
    limiar_selecao: float
    calibrador_ok: bool
    sem_contagens: bool
    features_ok: bool


def _com_tentativas(fn: Callable[[], None]) -> None:
    """Repete a gravação em erro de E/S, como as outras gravações no Drive (T-4.3b, item 7)."""
    for tentativa in range(1, runner.TENTATIVAS_E_S + 1):
        try:
            fn()
            return
        except OSError as erro:
            if tentativa == runner.TENTATIVAS_E_S:
                raise
            logger.warning("erro de E/S ao gravar o artefato (tentativa %d de %d): %s",
                           tentativa, runner.TENTATIVAS_E_S, erro)
            time.sleep(runner.PAUSA_E_S_S)


def _agora() -> str:
    return dt.datetime.now(dt.UTC).isoformat(timespec="seconds")


def metadados_m1(cfg: dict, nome: str, papel: str, sel: dict, metricas: dict, iteracoes,
                 pontos: list, features: list[str], limiar: float, calibrador_tipo: str,
                 hash_dobras) -> dict:
    """Campos FR-12 do M1 mais o bloco `m1`. Só métricas da validação (2022–23) e agregados."""
    return {
        "config": cfg,
        "dados": artifacts.hashes_dados(cfg),
        "data_treino": _agora(),
        "metricas_validacao": {
            "aviso": "validação fora da dobra em 2022–23; o teste de 2024 só entra na T-5.1 (R1)",
            "oof_pr_auc": float(metricas["oof_pr_auc"]),
            "pr_auc_media": float(metricas["pr_auc_media"]),
            "pr_auc_por_dobra": {k: float(v) for k, v in metricas["pr_auc_por_dobra"].items()},
            "brier_calibrado": float(sel["modelos"][nome]["brier_calibrado"]),
            "limiar": float(limiar),
        },
        "features": list(features),
        "m1": {
            "papel": papel,
            "modelo": nome,
            "tarefa": TAREFA,
            "calibrador": calibrador_tipo,
            "limiar": float(limiar),
            "iteracoes_finais": iteracoes,
            "melhores_pontos": pontos,
            "hash_dobras": hash_dobras,
            "motivo_selecao": sel["motivo"],
        },
    }


def _ler_treino(pasta: Path) -> tuple[dict, dict]:
    parametros = runner._ler_json(pasta / runner.ARQ_PARAMETROS)
    metricas = runner._ler_json(pasta / runner.ARQ_METRICAS)
    if parametros is None or metricas is None:
        raise FileNotFoundError(f"sem {runner.ARQ_PARAMETROS} ou {runner.ARQ_METRICAS} em {pasta}")
    return parametros["melhores_parametros"], metricas


def _congelar(cfg: dict, nome: str, df: pd.DataFrame, resultados: dict, sel: dict,
              pasta: Path, papel: str, hash_dobras) -> Congelado:
    """Treina `nome` em todo 2022–23, grava em `pasta`, recarrega e mede."""
    params, metricas = _ler_treino(Path(resultados[nome]["pasta"]))
    pontos = [metricas["melhores_pontos"].get(r) for r in cfg["ordem_dobras"]]
    modelo, iteracoes = treinar_final(cfg, nome, params, df, pontos)

    # Calibrador e limiar vêm da T-4.9: carregados, conferidos e nunca reajustados.
    pasta_cal = runner.pasta_m1(cfg) / nome
    calibrador = selecao.carregar_calibrador(pasta_cal)  # confere o SHA-256 gravado
    info_cal = runner._ler_json(pasta_cal / selecao.ARQ_CALIBRADOR_JSON) or {}
    calibrador_ok = (calibrador.tipo == sel["modelos"][nome]["calibrador"]
                     and info_cal.get("sha256") == runner._sha256(
                         pasta_cal / info_cal.get("arquivo", "")))
    limiar_selecao = float(sel["modelos"][nome]["limiar"])

    pre = modelo._pipeline.named_steps["preprocessamento"]
    features = preprocess.colunas_do_preprocessor(pre)
    try:
        preprocess.validar_preprocessor(pre)  # R4
        features_ok = True
    except ValueError:
        features_ok = False
    referencia = _referencia_mlp(modelo, df) if nome == "mlp" else None
    final = ModeloFinal(nome=nome, modelo=modelo, calibrador=calibrador,
                        limiar=limiar_selecao, features=features, referencia_shap=referencia)

    amostra = df.iloc[:AMOSTRA_CONFERENCIA]
    if hasattr(modelo, "para_cpu"):
        modelo.para_cpu()  # antes da conferência: a comparação é CPU contra CPU
    p_antes = final.prever_proba(amostra)

    metadados = metadados_m1(cfg, nome, papel, sel, metricas, iteracoes, pontos, features,
                             limiar_selecao, calibrador.tipo, hash_dobras)
    _com_tentativas(functools.partial(artifacts.save_bundle, final, pasta, metadados))
    del modelo, final

    carregado = artifacts.load_bundle(pasta)
    # O calibrador que foi para dentro do bundle tem de ser o da T-4.9, byte a byte nos números:
    # relido do disco agora e comparado com o carregado, e não só pelo SHA do arquivo.
    sonda = np.linspace(0.001, 0.999, 201)
    da_selecao = selecao.carregar_calibrador(pasta_cal)
    calibrador_ok = calibrador_ok and _mesmo_calibrador(carregado.calibrador, da_selecao, sonda)
    p_depois = carregado.prever_proba(amostra)
    finitas = bool(np.isfinite(p_depois).all() and ((p_depois >= 0) & (p_depois <= 1)).all())
    diferenca = float(np.max(np.abs(p_depois - p_antes))) if len(amostra) else 0.0

    meta = artifacts.ler_metadados(pasta)
    medicao = medir(carregado, pasta, df.iloc[:1])
    return Congelado(
        nome=nome,
        papel=papel,
        pasta=pasta,
        iteracoes=iteracoes,
        medicao=medicao,
        carga_ok=finitas,
        diferenca_maxima=diferenca,
        sha256_no_metadata=meta["payload"][ARQ_PAYLOAD],
        sha256_no_arquivo=runner._sha256(pasta / "payload" / ARQ_PAYLOAD),
        limiar=float(carregado.limiar),
        limiar_selecao=limiar_selecao,
        calibrador_ok=calibrador_ok,
        sem_contagens=artifacts.inteiros_pequenos(meta) == [],
        features_ok=features_ok,
    )


def _mesmo_calibrador(a: selecao.Calibrador, b: selecao.Calibrador, sonda: np.ndarray) -> bool:
    """Mesmo tipo, mesmas chaves, mesmos números e a mesma saída numa grade de probabilidades."""
    return (a.tipo == b.tipo and sorted(a.arrays) == sorted(b.arrays)
            and all(np.array_equal(a.arrays[k], b.arrays[k]) for k in b.arrays)
            and np.array_equal(a.aplicar(sonda), b.aplicar(sonda)))


def _promover(origem: Path, destino: Path) -> None:
    """Põe a pasta `origem` no lugar de `destino` (que é substituído)."""
    if destino.exists():
        shutil.rmtree(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(origem), str(destino))


def _checks_congelado(c: Congelado, prefixo: str) -> list[dict]:
    checks = [
        verify.check(f"{prefixo}_carrega_e_prediz", True, c.carga_ok),
        verify.check(f"{prefixo}_predicoes_iguais_apos_carga", True,
                     c.diferenca_maxima <= TOLERANCIA_RECARGA),
        verify.check(f"{prefixo}_sha256_payload", c.sha256_no_metadata, c.sha256_no_arquivo),
        verify.check(f"{prefixo}_limiar_da_selecao", c.limiar_selecao, c.limiar),
        verify.check(f"{prefixo}_calibrador_da_selecao", True, c.calibrador_ok),
        verify.check(f"{prefixo}_sem_contagens_por_nivel", True, c.sem_contagens),
        verify.check(f"{prefixo}_features_sem_proibidas", True, c.features_ok),
        verify.registro(f"{prefixo}_tamanho_payload_bytes", c.medicao.bytes_payload),
        verify.registro(f"{prefixo}_tamanho_pasta_bytes", c.medicao.bytes_pasta),
        verify.registro(f"{prefixo}_tempo_predicao_um_caso_s",
                        round(c.medicao.tempo_predicao_s, 6)),
        verify.registro(f"{prefixo}_shap_local_viavel", c.medicao.shap_viavel),
    ]
    if c.iteracoes is not None:
        checks.append(verify.registro(f"{prefixo}_iteracoes_finais", c.iteracoes))
    if c.medicao.tempo_shap_s is not None:
        checks.append(verify.registro(f"{prefixo}_tempo_shap_um_caso_s",
                                      round(c.medicao.tempo_shap_s, 6)))
    return checks


# --- Gancho ----------------------------------------------------------------------------------

def executar(cfg: dict, resultados: dict) -> list[dict]:
    """Gancho `retreino` do runner (T-4.10). Devolve os checks do bloco `retreino`.

    Grava `<modelos>/m1_final` e, se preciso, `<modelos>/m1_demo`. Levanta erro se a seleção não
    existe ou se algum dado de fora de 2022–23 chega (R1); a sessão para e nada é gravado.
    """
    raiz = runner.pasta_m1(cfg)
    sel = runner._ler_json(raiz / selecao.NOME_SELECAO)
    if sel is None:
        raise FileNotFoundError(f"sem {selecao.NOME_SELECAO} em {raiz}: a seleção (T-4.9) "
                                "precisa rodar antes do retreino")
    vencedor = sel["vencedor"]
    esperado = yaml.safe_load(
        (verify.REPO / "config" / "esperado.yaml").read_text(encoding="utf-8"))["desenvolvimento"]

    df = runner._carregar_dados_de_desenvolvimento(cfg)
    assert_dev_only(df)  # R1
    hash_dobras = (runner._ler_json(runner.caminho_relatorio(cfg)) or {}).get("hash_dobras")
    checks = [
        verify.check("casos_treino_2022_2023", esperado["populacao_total"], len(df)),
        verify.check("eventos_treino_2022_2023", esperado["eventos_total"],
                     int(df[COLUNA_ALVO].sum())),
        verify.check("anos_do_treino_no_desenvolvimento", True, bool(
            {int(a) for a in df[COLUNA_ANO].unique()} <= {int(a) for a in cfg["anos_dev"]})),
    ]

    modelos = runner._caminho(cfg, "modelos")
    final = _congelar(cfg, vencedor, df, resultados, sel, modelos / NOME_FINAL, "final",
                      hash_dobras)
    checks += _checks_congelado(final, "m1_final")
    checks.append(verify.registro("vencedor", vencedor))

    demo: Congelado | None = None
    if cumpre_demo(final.medicao):
        demo = final
        motivo = f"o vencedor ({vencedor}) cumpre os três critérios da demo (D-70)"
    else:
        motivo = "; ".join(razoes_fora_da_demo(final.medicao))
        tentativas = modelos / PASTA_TENTATIVAS
        for candidato in ordem_demo(sel["modelos"], list(cfg["ordem_modelos"]), vencedor):
            c = _congelar(cfg, candidato, df, resultados, sel,
                          tentativas / candidato, "demo", hash_dobras)
            logger.info("demo: %s %s", candidato,
                        "cumpre" if cumpre_demo(c.medicao) else "não cumpre")
            if cumpre_demo(c.medicao):
                demo = c
                motivo = (f"{vencedor} não cumpre ({motivo}); {candidato} é o melhor candidato "
                          "que cumpre os três (D-70)")
                break
        if demo is not None:
            _promover(demo.pasta, modelos / NOME_DEMO)
            demo = replace(demo, pasta=modelos / NOME_DEMO)
        shutil.rmtree(tentativas, ignore_errors=True)

    if demo is not None and demo.papel == "demo":
        checks += _checks_congelado(demo, "m1_demo")
    if demo is not None:
        checks.append(verify.maximo("demo_tempo_consulta_ate_1s", LIMITE_CONSULTA_S,
                                    round(demo.medicao.tempo_consulta_s, 6)))
    checks.append(verify.check("modelo_demo_definido", True, demo is not None))
    checks.append(verify.registro("modelo_demo", demo.nome if demo else "nenhum"))
    checks.append(verify.registro("motivo_demo", motivo))
    logger.info("retreino: final=%s demo=%s", vencedor, demo.nome if demo else None)
    return checks
