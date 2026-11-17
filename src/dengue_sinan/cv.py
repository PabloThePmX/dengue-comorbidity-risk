"""Laço de validação leave-one-region-out com early stopping (T-4.2, R1, R3, R5, R6, R8, FR-22).

`run_loro` percorre as dobras de `folds.loro_folds` (uma por região, na ordem de `ordem_dobras`).
Em cada dobra:
1. separa o treino (4 regiões) e a validação (a região deixada de fora);
2. se o modelo é iterativo, separa a validação interna do treino com `folds.inner_split` (R6);
3. ajusta o modelo (iterativo: parada antecipada na validação interna, nunca na região de fora);
4. guarda o melhor ponto (`melhor_ponto`) e usa o modelo naquele ponto (FR-22);
5. prediz a região de validação (OOF).

O laço não sabe qual modelo roda: ele só fala com o contrato `ModeloM1` abaixo. Novos modelos
entram no `REGISTRO` (T-4.4 a T-4.7); o laço não muda.

Contrato `ModeloM1` (um objeto novo por dobra, criado por `construir_modelo`):
- `iterativo: bool`. False: `ajustar` recebe só o treino inteiro (`X_parada` é None). True: o laço
  passa o treino sem a validação interna em `X_treino` e a validação interna em `X_parada`.
- `ajustar(X_treino, y_treino, X_parada=None, y_parada=None)`: X são `DataFrame` com o índice
  original (posições de `df`); quem ajusta é o próprio modelo, dentro de um `Pipeline` (R5).
- `prever_proba(X) -> ndarray`: probabilidade de y = 1, uma por linha de X, finita e em [0, 1].
- `melhor_ponto() -> int | None`: nº de árvores ou de épocas do melhor ponto; None se não
  for iterativo. Depois de `ajustar`, `prever_proba` já usa esse ponto.

Orientações para as próximas tarefas (valem para quem implementar):
- CatBoost: `allow_writing_files=False`, senão ele cria a pasta `catboost_info/` no diretório
  de trabalho. Métrica de parada: `eval_metric="PRAUC"`.
- XGBoost: métrica de parada `eval_metric="aucpr"`; sem `scale_pos_weight` (R3).
- LogisticRegression (elastic net, T-4.6b): o argumento `penalty` está deprecado no sklearn 1.9 e
  é recusado pelo construtor; use `C` e `l1_ratio`. Com `solver="saga"` e `l1_ratio` perto de 0,99
  o `max_iter` pode não bastar (ConvergenceWarning, registrado no MLflow).
- Sem pesos de classe em nenhum modelo (R3). Sementes vêm de `cfg["seed"]` (R8).
- Paciência: 50 rodadas nas árvores (`early_stopping_rounds` em `busca:`) e 10 épocas no MLP
  (`paciencia_epocas` em `busca:`).

Modelo registrado nesta tarefa: `"b1"`, a logística sem penalização de T-2.8. Usa o mesmo
pipeline de `baselines.fazer_pipeline_b1` e as mesmas `COLUNAS_B1`, para reproduzir o B1 da
T-2.8 exatamente. Não usa o pré-processador de `preprocess.py`: ele tem outras features
(`n_comorbidades`, sintomas, dias), o que mudaria o B1. Não é iterativo: sem early stopping, usa
o treino inteiro das 4 regiões, como o B1 da T-2.8.

Memória (~2,45 M de linhas): cada dobra cria subconjuntos com `df.iloc` só durante a dobra; eles
são apagados e há `gc.collect()` ao fim da dobra. A predição OOF guarda ANO, região, y e p, que
é o formato de `tracking.log_oof_predictions`.
"""

from __future__ import annotations

import gc
from collections.abc import Callable
from typing import Any, Protocol

import numpy as np
import pandas as pd

from dengue_sinan import baselines, folds, metrics
from dengue_sinan.catboost_m1 import construir_catboost
from dengue_sinan.elastic_net_m1 import construir_elastic_net
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.mlp import construir_mlp
from dengue_sinan.random_forest import construir_random_forest
from dengue_sinan.tabfm_m1 import construir_tabfm
from dengue_sinan.xgboost_m1 import construir_xgboost

COLUNA_ALVO = "y"
COLUNA_REGIAO = "regiao"
COLUNA_ANO = "ANO"


class ModeloM1(Protocol):
    """Contrato que o laço usa. Ver a docstring do módulo."""

    iterativo: bool

    def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None: ...

    def prever_proba(self, X) -> np.ndarray: ...

    def melhor_ponto(self) -> int | None: ...


class ModeloB1:
    """Logística sem penalização (T-2.8), como modelo do contrato. Não é iterativo (sem R6)."""

    iterativo = False

    def __init__(self) -> None:
        self._pipeline = None

    def ajustar(self, X_treino, y_treino, X_parada=None, y_parada=None) -> None:
        if X_parada is not None or y_parada is not None:
            raise ValueError("b1 não usa validação de parada (T-2.8)")
        assert_dev_only(X_treino)  # R1
        self._pipeline = baselines.fazer_pipeline_b1()
        self._pipeline.fit(X_treino[baselines.COLUNAS_B1], np.asarray(y_treino))

    def prever_proba(self, X) -> np.ndarray:
        if self._pipeline is None:
            raise RuntimeError("chame ajustar antes de prever")
        assert_dev_only(X)  # R1
        return self._pipeline.predict_proba(X[baselines.COLUNAS_B1])[:, 1].astype(float)

    def melhor_ponto(self) -> int | None:
        return None


def _construir_b1(params: dict[str, Any], cfg: dict) -> ModeloB1:
    if params:
        raise ValueError(f"b1 não tem hiperparâmetros; recebi {sorted(params)}")
    return ModeloB1()


# Registro de modelos do M1. As tarefas T-4.5 a T-4.7 acrescentam uma entrada cada.
REGISTRO: dict[str, Callable[[dict[str, Any], dict], ModeloM1]] = {
    "b1": _construir_b1,
    "random_forest": construir_random_forest,  # T-4.4
    "xgboost": construir_xgboost,  # T-4.5
    "catboost": construir_catboost,  # T-4.6
    "elastic_net": construir_elastic_net,  # T-4.6b
    "mlp": construir_mlp,  # T-4.6b
    "tabfm": construir_tabfm,  # T-4.7
}


def construir_modelo(nome: str, params: dict[str, Any], cfg: dict) -> ModeloM1:
    """Cria um modelo novo (não ajustado) do registro. Levanta ValueError se o nome não existe."""
    if nome not in REGISTRO:
        raise ValueError(f"modelo {nome!r} não registrado; use um de {sorted(REGISTRO)}")
    return REGISTRO[nome](dict(params), cfg)


def _probabilidades(p, esperado: int) -> np.ndarray:
    """Confere o retorno de `prever_proba`: uma probabilidade finita em [0, 1] por linha."""
    arr = np.asarray(p, dtype=float)
    if arr.shape != (esperado,):
        raise ValueError(f"prever_proba devolveu {arr.shape}, esperado ({esperado},)")
    if not np.isfinite(arr).all() or (arr < 0).any() or (arr > 1).any():
        raise ValueError("prever_proba devolveu valor fora de [0, 1] ou não finito")
    return arr


def run_loro(
    cfg: dict,
    familia: str,
    params: dict[str, Any],
    df: pd.DataFrame,
    ao_fim_da_dobra: Callable[[str, int, float], None] | None = None,
) -> dict:
    """Roda o laço leave-one-region-out de um modelo do registro (T-4.2).

    `familia` é o nome do modelo no `REGISTRO` (ex.: "b1"); o nome do parâmetro segue o spec.
    `df` precisa de `ANO`, `regiao`, `y` e as features do modelo, e de índice 0..n-1 (as posições
    são o identificador de cada linha). Não é copiado por dobra: cada dobra só pega subconjuntos.

    `ao_fim_da_dobra(regiao, indice, pr_auc)` (T-4.3, opcional): chamado depois de cada dobra, com
    `indice` = posição da dobra (0 a 4) e a PR-AUC dela. Serve à poda e à cronometragem do Optuna;
    pode levantar `optuna.TrialPruned`, que sai daqui sem ser engolida. Sem o gancho, nada muda.

    Devolve:
    - `oof`: DataFrame com ANO, regiao, y, p de todas as linhas, uma vez cada (formato de
      `tracking.log_oof_predictions`);
    - `posicoes`: posição em `df` de cada linha de `oof`, na mesma ordem;
    - `oof_pr_auc`: PR-AUC do OOF agrupado;
    - `pr_auc_por_dobra`: PR-AUC de cada região deixada de fora;
    - `pr_auc_media`: média das PR-AUC das dobras;
    - `melhores_pontos`: por região, o melhor ponto do modelo (None se não for iterativo).
    """
    assert_dev_only(df)  # R1
    if not df.index.equals(pd.RangeIndex(len(df))):
        raise ValueError("df precisa de índice 0..n-1: o laço identifica cada linha pela posição")

    y = df[COLUNA_ALVO].to_numpy()
    anos = df[COLUNA_ANO].to_numpy()
    blocos: list[pd.DataFrame] = []
    posicoes: list[np.ndarray] = []
    pr_por_dobra: dict[str, float] = {}
    melhores_pontos: dict[str, int | None] = {}

    for indice, (regiao, pos_treino, pos_validacao) in enumerate(folds.loro_folds(cfg, df)):
        modelo = construir_modelo(familia, params, cfg)
        if modelo.iterativo:
            # R6: a validação interna sai só das 4 regiões de treino, nunca da região de fora.
            pos_ajuste, pos_parada = folds.inner_split(
                pos_treino, y, cfg["validacao_interna_frac"], cfg["seed"])
            modelo.ajustar(df.iloc[pos_ajuste], y[pos_ajuste],
                           df.iloc[pos_parada], y[pos_parada])
            del pos_ajuste, pos_parada
        else:
            modelo.ajustar(df.iloc[pos_treino], y[pos_treino])

        melhor = modelo.melhor_ponto()
        if modelo.iterativo and melhor is None:
            raise ValueError(f"modelo {familia!r} é iterativo e não informou melhor_ponto")
        melhores_pontos[regiao] = melhor

        y_val = y[pos_validacao]
        p = _probabilidades(modelo.prever_proba(df.iloc[pos_validacao]), len(pos_validacao))
        pr_por_dobra[regiao] = metrics.pr_auc(y_val, p)
        blocos.append(pd.DataFrame({
            COLUNA_ANO: anos[pos_validacao],
            COLUNA_REGIAO: regiao,
            COLUNA_ALVO: y_val,
            "p": p,
        }))
        posicoes.append(pos_validacao)

        del modelo, y_val, p
        gc.collect()
        if ao_fim_da_dobra is not None:
            ao_fim_da_dobra(regiao, indice, pr_por_dobra[regiao])

    oof = pd.concat(blocos, ignore_index=True)
    return {
        "familia": familia,
        "oof": oof,
        "posicoes": np.concatenate(posicoes),
        "oof_pr_auc": metrics.pr_auc(oof[COLUNA_ALVO], oof["p"]),
        "pr_auc_por_dobra": pr_por_dobra,
        "pr_auc_media": float(np.mean(list(pr_por_dobra.values()))),
        "melhores_pontos": melhores_pontos,
    }
