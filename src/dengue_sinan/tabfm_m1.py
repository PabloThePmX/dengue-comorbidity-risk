"""TabFM do M1 (T-4.7, D-69, R1, R3, R5, R8).

Entra no `REGISTRO` de `cv.py` como `"tabfm"`; o laço não muda. O TabFM é um modelo de fundação
tabular **sem treino**: as linhas de treino entram como contexto na hora da predição (aprendizado
em contexto). Por isso o modelo não é iterativo (sem early stopping, R6) e não tem busca
(`busca.tabfm.sem_busca: true`, D-69). `melhor_ponto()` é None.

Contexto (plan › Restrições do TabFM): uma **subamostra estratificada** pelo alvo das linhas de
treino da dobra, com `max_num_rows` linhas (`config/base.yaml`, chave `tabfm`). A subamostra é
proporcional ao alvo, feita com a semente do config (R8). Sem peso de classe e sem correção de
desbalanceamento (R3): a proporção de positivos no contexto é a do treino.

Pré-processamento (R4, R5): `make_preprocessor("arvore")` dentro de um `Pipeline`, ajustado só com
o contexto, que sai do treino da dobra. [ASSUMPTION] a família "arvore" (codificação ordinal, sem
escala) é a que o TabFM recebe; o pacote não documenta o formato de entrada com categóricas.

Pacote: `tabfm` é importado **só** dentro de `ajustar` (import preguiçoso), para o módulo carregar
sem o pacote instalado. Sem o pacote, levanta `RuntimeError` com a instrução de instalação na sessão
do Colab (D-69). O pacote vem de um commit fixo da `main` do GitHub (`tabfm.commit_pacote`, D-90): o
commit instalado (`direct_url.json` do pip) tem que ser esse, senão a execução para. Os pesos são um
atributo do pacote (`tabfm.alias_pesos`), não um submódulo.
O `n_estimators` (ensembling de contextos) só é passado quando não é `null` no config; com `null`
vale o padrão do pacote.

Dispositivo: o README do pacote não expõe escolha de dispositivo, então o módulo só **registra**
o que o torch enxerga (`cuda` ou `cpu`); quem decide é o pacote.

MLflow (quando há um run ativo): commit do pacote, `max_num_rows`, `n_estimators`, dispositivo
(parâmetros) e tamanho e nº de positivos do contexto (métricas, por dobra).

Predição: uma probabilidade de y = 1 por linha, em blocos de `TAMANHO_BLOCO_PREDICAO` linhas
(memória). Contrato `ModeloM1` em `cv.py`.
"""

from __future__ import annotations

import importlib
import importlib.metadata
import json
import re
from typing import Any

import mlflow
import numpy as np
from sklearn.pipeline import Pipeline

from dengue_sinan.guard import assert_dev_only
from dengue_sinan.preprocess import make_preprocessor

NOME_PACOTE = "tabfm"
CHAVE_CONFIG = "tabfm"  # bloco do config/base.yaml
CHAVES_OBRIGATORIAS = ("commit_pacote", "alias_pesos", "max_num_rows", "n_estimators")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")  # SHA-1 completo, minúsculo (é o que o pip grava)
TAMANHO_BLOCO_PREDICAO = 65_536  # linhas por chamada de predição (memória)
# Nomes diferentes dos do config: o start_run já grava o config achatado, e o MLflow recusa mudar
# o valor de um parâmetro (aqui: n_estimators null no config e "padrao_do_pacote" no run).
PARAM_MLFLOW_COMMIT = "tabfm.commit_instalado"
PARAM_MLFLOW_MAX_LINHAS = "tabfm.contexto_max_linhas"
PARAM_MLFLOW_N_ESTIMATORS = "tabfm.n_estimators_efetivo"
PARAM_MLFLOW_DISPOSITIVO = "tabfm.dispositivo"
METRICA_MLFLOW_CONTEXTO = "tabfm.contexto_linhas"
METRICA_MLFLOW_POSITIVOS = "tabfm.contexto_positivos"


def _instrucao_instalacao(commit: str) -> str:
    """Comando que instala o `tabfm` do commit fixo (D-90). Sem dependências: o lock cobre."""
    return f'pip install --no-deps "git+https://github.com/google-research/tabfm.git@{commit}"'


def _carregar_pacote(alias_pesos: str, commit: str) -> tuple[Any, Any]:
    """Importa o pacote `tabfm` e pega os pesos `alias_pesos` como atributo dele (D-90).

    Import preguiçoso (D-69). Sem o pacote, levanta RuntimeError com a instrução de instalação do
    commit fixo, em vez do ImportError cru. O alias é atributo de `tabfm/__init__.py`, não
    submódulo: se o PyTorch não importar, o atributo não existe e o erro diz isso.
    """
    try:
        pacote = importlib.import_module(NOME_PACOTE)
    except ImportError as erro:
        raise RuntimeError(
            "TabFM não instalado. Ele só roda na sessão do Colab, do commit fixo do config "
            f"(tabfm.commit_pacote, D-69 e D-90): {_instrucao_instalacao(commit)}. "
            f"Erro original: {erro}"
        ) from erro
    if not hasattr(pacote, alias_pesos):
        raise RuntimeError(
            f"tabfm: o pacote instalado não expõe {alias_pesos!r} (tabfm.alias_pesos). Ou o commit "
            f"não é {commit}, ou o PyTorch não importou (D-90). Reinstale: "
            f"{_instrucao_instalacao(commit)}")
    return pacote, getattr(pacote, alias_pesos)


def _commit_instalado() -> str | None:
    """SHA do commit de onde o pip instalou o `tabfm`, pelo `direct_url.json` (PEP 610).

    None se o pacote não veio de git (ex.: PyPI). A versão não serve para isso: é '1.0.1' em todo
    commit da `main` (D-90).
    """
    try:
        distribuicao = importlib.metadata.distribution(NOME_PACOTE)
    except importlib.metadata.PackageNotFoundError as erro:
        raise RuntimeError("TabFM não instalado: sem metadados do pacote (D-69, D-90)") from erro
    origem = distribuicao.read_text("direct_url.json")
    if origem is None:
        return None
    vcs = json.loads(origem).get("vcs_info") or {}
    commit = vcs.get("commit_id")
    return commit if isinstance(commit, str) else None


def detectar_dispositivo() -> str:
    """"cuda" se o torch enxerga uma GPU, senão "cpu". Só registro (o pacote escolhe sozinho)."""
    import torch  # lazy: o módulo carrega sem torch por perto; o pacote PyTorch precisa dele

    return "cuda" if torch.cuda.is_available() else "cpu"


def _fixar_sementes(seed: int) -> None:
    """R8: sementes do torch e do numpy no início do ajuste. O pacote não documenta `random_state`,
    então o determinismo da escolha interna dele fica [VERIFY] na sessão do Colab."""
    import torch

    torch.manual_seed(seed)
    np.random.seed(seed)


def subamostra_estratificada(y, tamanho: int, seed: int) -> np.ndarray:
    """Posições (ordenadas) de um contexto de `tamanho` linhas, proporcional ao alvo `y`.

    Cota de cada classe = piso de (tamanho × contagem / n); as unidades que sobram vão para as
    classes de maior resto (método dos maiores restos), então o total é exatamente `tamanho`. O
    sorteio dentro de cada classe usa `default_rng(seed)` (R8). Se `tamanho` >= n, devolve tudo.
    """
    if tamanho < 1:
        raise ValueError(f"tamanho do contexto deve ser pelo menos 1, não {tamanho}")
    y = np.asarray(y)
    n = y.size
    if tamanho >= n:
        return np.arange(n)
    classes = np.unique(y)
    ideal = {c: tamanho * np.count_nonzero(y == c) / n for c in classes}
    cotas = {c: int(np.floor(ideal[c])) for c in classes}
    faltam = tamanho - sum(cotas.values())  # menor que o nº de classes
    for c in sorted(classes, key=lambda c: (-(ideal[c] - cotas[c]), c))[:faltam]:
        cotas[c] += 1
    rng = np.random.default_rng(seed)
    escolhidas = [rng.choice(np.flatnonzero(y == c), size=cotas[c], replace=False) for c in classes]
    return np.sort(np.concatenate(escolhidas))


class TabFMM1:
    """TabFM como `ModeloM1` (ver `cv.py`). Um objeto novo por dobra; sem busca, sem parada."""

    iterativo = False

    def __init__(self, params: dict[str, Any], cfg_tabfm: dict[str, Any], seed: int) -> None:
        if params:
            raise ValueError(
                f"tabfm não tem hiperparâmetros (sem_busca, D-69); recebi {sorted(params)}")
        faltando = [c for c in CHAVES_OBRIGATORIAS if c not in cfg_tabfm]
        if faltando:
            raise ValueError(f"config tabfm: faltam {faltando}")
        max_linhas = cfg_tabfm["max_num_rows"]
        if isinstance(max_linhas, bool) or not isinstance(max_linhas, int) or max_linhas < 1:
            raise ValueError(f"tabfm.max_num_rows deve ser inteiro >= 1, não {max_linhas!r}")
        n_est = cfg_tabfm["n_estimators"]
        if n_est is not None and (isinstance(n_est, bool) or not isinstance(n_est, int)
                                  or n_est < 1):
            raise ValueError(f"tabfm.n_estimators deve ser inteiro >= 1 ou null, não {n_est!r}")
        commit = cfg_tabfm["commit_pacote"]
        if not isinstance(commit, str) or not COMMIT_RE.fullmatch(commit):
            raise ValueError(
                "tabfm.commit_pacote deve ser o SHA-1 completo (40 hex minúsculos), "
                f"não {commit!r}")
        self._commit = commit
        self._alias = str(cfg_tabfm["alias_pesos"])
        self._max_linhas = max_linhas
        self._n_estimators = n_est
        self._seed = int(seed)  # R8
        self._pipeline: Pipeline | None = None
        self.contexto_linhas_: int | None = None
        self.contexto_positivos_: int | None = None

    def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None:
        if X_parada is not None or y_parada is not None:
            raise ValueError("tabfm não usa validação de parada (sem busca, sem early stopping)")
        assert_dev_only(X_treino)  # R1
        y = np.asarray(y_treino)
        pos = subamostra_estratificada(y, self._max_linhas, self._seed)  # R8
        X_ctx = X_treino.iloc[pos]
        y_ctx = y[pos]
        estimador = self._novo_estimador()
        _fixar_sementes(self._seed)
        # R5: o pré-processamento só aprende com o contexto, que sai do treino da dobra.
        self._pipeline = Pipeline([
            ("preprocessamento", make_preprocessor("arvore")),
            ("tabfm", estimador),
        ])
        self._pipeline.fit(X_ctx, y_ctx)
        if list(estimador.classes_) != [0, 1]:
            raise ValueError(f"tabfm: classes {list(estimador.classes_)}; esperado [0, 1]")
        self.contexto_linhas_ = int(pos.size)
        self.contexto_positivos_ = int((y_ctx == 1).sum())
        if mlflow.active_run() is not None:
            mlflow.log_param(PARAM_MLFLOW_COMMIT, self._commit)  # já conferido em _novo_estimador
            mlflow.log_param(PARAM_MLFLOW_MAX_LINHAS, self._max_linhas)
            mlflow.log_param(PARAM_MLFLOW_N_ESTIMATORS,
                             "padrao_do_pacote" if self._n_estimators is None
                             else self._n_estimators)
            mlflow.log_param(PARAM_MLFLOW_DISPOSITIVO, detectar_dispositivo())
            mlflow.log_metric(METRICA_MLFLOW_CONTEXTO, float(self.contexto_linhas_))
            mlflow.log_metric(METRICA_MLFLOW_POSITIVOS, float(self.contexto_positivos_))

    def _novo_estimador(self):
        """Carrega o pacote, confere o commit fixo (D-90) e cria o classificador do pacote."""
        pacote, pesos = _carregar_pacote(self._alias, self._commit)
        instalado = _commit_instalado()
        if instalado != self._commit:
            raise RuntimeError(
                f"tabfm: commit instalado "
                f"{instalado or 'desconhecido (não veio de git)'} != config {self._commit} "
                "(commit fixo, D-90). Reinstale: "
                f"{_instrucao_instalacao(self._commit)}")
        kwargs: dict[str, Any] = {"max_num_rows": self._max_linhas}
        if self._n_estimators is not None:
            kwargs["n_estimators"] = self._n_estimators
        return pacote.TabFMClassifier(model=pesos.load(), **kwargs)

    def prever_proba(self, X) -> np.ndarray:
        if self._pipeline is None:
            raise RuntimeError("chame ajustar antes de prever")
        assert_dev_only(X)  # R1
        partes = []
        for ini in range(0, len(X), TAMANHO_BLOCO_PREDICAO):
            bloco = X.iloc[ini:ini + TAMANHO_BLOCO_PREDICAO]
            partes.append(np.asarray(self._pipeline.predict_proba(bloco)[:, 1], dtype=float))
        p = np.concatenate(partes) if partes else np.empty(0, dtype=float)
        if not np.isfinite(p).all() or (p < 0).any() or (p > 1).any():
            raise ValueError("tabfm devolveu probabilidade fora de [0, 1] ou não finita")
        return p

    def melhor_ponto(self) -> int | None:
        return None


def construir_tabfm(params: dict[str, Any], cfg: dict) -> TabFMM1:
    """Entrada do `REGISTRO`: cria um TabFM novo (não ajustado), com a semente e o bloco `tabfm`."""
    if CHAVE_CONFIG not in cfg:
        raise ValueError(f"config: falta o bloco {CHAVE_CONFIG!r} (T-4.7, D-69)")
    return TabFMM1(params, cfg[CHAVE_CONFIG], seed=cfg["seed"])
