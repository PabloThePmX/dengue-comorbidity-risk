"""Busca de hiperparâmetros com Optuna (T-4.3, D-43, D-53, NFR-01, R1, R3, R8, FR-22).

`tune(cfg, modelo, df)` roda a busca de um modelo do registro e é retomável. Um SQLite por modelo,
em `<caminhos.dados>/optuna/<modelo>.db` (no Colab, o Drive; fora do git), com dois estudos:
- `<modelo>`: o estudo principal, com só as tentativas comparáveis da busca (TPE e poda);
- `<modelo>__cronometragem`: o estudo à parte da cronometragem (ver abaixo).

Passos (D-53):
1. **Retomada**: tentativas deixadas em "rodando" por uma sessão que morreu viram falha antes de
   qualquer coisa, para não travar a busca nem contar no orçamento.
2. **Cronometragem**: a 1ª tentativa (o ponto de partida de `busca.<modelo>.primeira_tentativa`)
   roda com os dados completos, sem poda, e o tempo `t` é a soma das 5 dobras (gancho
   `ao_fim_da_dobra` de `cv.run_loro`). Ela roda no estudo de cronometragem. A decisão de orçamento
   fica como `user_attrs` do estudo principal: se ela existe, a cronometragem **não é repetida**.
3. **Orçamento**: `calcular_orcamento` (fórmula abaixo). Se `3t` não cabe no teto, a busca vai para
   a **subamostra estratificada** por (região, alvo), que mantém a prevalência de cada dobra (R3).
4. **Busca**: `study.optimize` até o nº de tentativas do config ou o tempo restante do orçamento.
   Cada dobra reporta a PR-AUC acumulada (`trial.report`) e pode podar a tentativa. Limites de
   tempo, checados no fim de cada dobra (inclusive a 1ª), só na busca (não na cronometragem):
   - **orçamento da busca**: a tentativa é podada se o tempo gasto nela passou do que restava do
     orçamento quando ela começou (`fim_busca`, o instante em que o orçamento acaba);
   - **limite por tentativa**: `FATOR_LIMITE_TENTATIVA · fracao · t` (3 × o custo de referência de
     uma tentativa no conjunto da busca). Motivo gravado em `user_attrs["motivo_poda"]`.
   A poda por tempo acontece ao fim de cada dobra anterior à última (D-89). Uma dobra não pode
   ser interrompida (o saga é caixa-preta): a tentativa só passa do orçamento ou do limite na
   última dobra, e por no máximo o tempo dela (a folga do check é `maior_dobra_s`).
5. **Melhor tentativa**: vai ao registro de modelos `m1-<modelo>`, alias `melhor-validacao`.
   Uma tentativa pior ou igual nunca move o alias.

Fórmula do orçamento (segundos; `teto` e `piso` vêm de `orcamento_teto_min` e `orcamento_piso_min`):
- `subamostra = 3t > teto`;
- `fracao = teto / (3t)` se houver subamostra, senão `1`;
- `orcamento = max(piso, min(teto, fracao · t · max_tentativas))`.
Com subamostra, `fracao · t = teto / 3`, então o orçamento é o teto (`max_tentativas ≥ 3`).

Cronometragem e subamostra:
- **Sem subamostra** (3t ≤ teto): a tentativa cronometrada, com o ponto de partida nos dados
  completos, é copiada para o estudo principal como a 1ª tentativa normal (comparável; conta no
  orçamento). Não há repetição de custo.
- **Com subamostra**: a tentativa de dados completos fica só no estudo de cronometragem. O estudo
  principal começa só com as tentativas da busca: o ponto de partida é enfileirado para rodar na
  subamostra. O orçamento de busca é o teto inteiro (a cronometragem não é cobrada).
- Escolhas registradas no relatório da tarefa; o tempo da cronometragem vai ao MLflow.

Retomada: `user_attrs["cronometragem"]` no estudo principal diz que a cronometragem já foi feita
(`t`, orçamento, subamostra, `numero_tentativa` — `None` com subamostra). Sem ele, a cronometragem
roda de novo, mas reaproveita a tentativa já medida no estudo de cronometragem, se existir.
Janela conhecida: se a sessão morrer entre copiar a tentativa para o estudo principal e gravar
`user_attrs`, a cópia pode ser feita duas vezes (uma tentativa a mais, idêntica).
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable
from pathlib import Path

import mlflow
import numpy as np
import optuna
import pandas as pd
from mlflow.exceptions import MlflowException
from mlflow.tracking import MlflowClient
from optuna.pruners import MedianPruner, NopPruner
from optuna.samplers import TPESampler
from optuna.storages import RDBStorage
from optuna.trial import TrialState

from dengue_sinan import cv, tracking, verify
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.search_space import EspacoModelo, load_search_space, sugerir

COLUNA_ALVO = "y"
COLUNA_REGIAO = "regiao"
ALIAS_MELHOR = "melhor-validacao"  # FR-22
ATRIBUTO_CRONOMETRAGEM = "cronometragem"  # user attr do estudo principal: a decisão de orçamento
SUFIXO_CRONOMETRAGEM = "__cronometragem"
NOME_ARTEFATO = "melhor_tentativa.json"
FATOR_LIMITE_TENTATIVA = 3.0  # limite por tentativa = fator · fracao · t (ver docstring do módulo)
MOTIVO_ORCAMENTO = "orcamento_busca"
MOTIVO_LIMITE = "limite_tentativa"


# --- Caminhos, estudos e retomada ------------------------------------------------------------

def pasta_optuna(cfg: dict) -> Path:
    """`<caminhos.dados>/optuna`: os estudos ficam na pasta de dados, fora do git."""
    base = Path(cfg["caminhos"]["dados"])
    base = base if base.is_absolute() else (verify.REPO / base).resolve()
    return base / "optuna"


def _url_sqlite(caminho: Path) -> str:
    return f"sqlite:///{caminho.resolve().as_posix()}"


def nome_modelo_registrado(modelo: str) -> str:
    return f"m1-{modelo}"


def _abrir_estudo(cfg: dict, modelo: str, nome: str, pruner) -> optuna.Study:
    """Abre (ou retoma) um estudo `nome` no SQLite do modelo (D-43)."""
    pasta = pasta_optuna(cfg)
    pasta.mkdir(parents=True, exist_ok=True)
    return optuna.create_study(
        study_name=nome,
        storage=_url_sqlite(pasta / f"{modelo}.db"),
        direction="maximize",
        sampler=TPESampler(seed=cfg["seed"]),  # R8
        pruner=pruner,
        load_if_exists=True,
    )


def criar_estudo(cfg: dict, modelo: str) -> optuna.Study:
    """Estudo principal do modelo: só as tentativas comparáveis da busca."""
    pruner = MedianPruner(
        n_startup_trials=cfg["optuna"]["poda_tentativas_iniciais"],
        # a poda só vale a partir da 2ª dobra concluída (step = dobras concluídas)
        n_warmup_steps=cfg["optuna"]["poda_dobras_aquecimento"],
    )
    return _abrir_estudo(cfg, modelo, modelo, pruner)


def criar_estudo_cronometragem(cfg: dict, modelo: str) -> optuna.Study:
    """Estudo à parte da cronometragem (dados completos). Não tem poda: mede as 5 dobras."""
    return _abrir_estudo(cfg, modelo, f"{modelo}{SUFIXO_CRONOMETRAGEM}", NopPruner())


def marcar_interrompidas(estudo: optuna.Study) -> int:
    """Tentativas em "rodando" (sessão morta no meio, D-64) viram falha. Devolve quantas foram."""
    rodando = estudo.get_trials(deepcopy=False, states=(TrialState.RUNNING,))
    for trial in rodando:
        estudo.tell(trial.number, state=TrialState.FAIL)
    return len(rodando)


# --- Orçamento e subamostra ------------------------------------------------------------------

def calcular_orcamento(t_s: float, max_tentativas: int, piso_s: float, teto_s: float) -> dict:
    """Orçamento de busca em segundos e a decisão de subamostra (D-53). Fórmula no docstring."""
    if t_s <= 0:
        raise ValueError(f"tempo da cronometragem deve ser positivo, não {t_s}")
    if max_tentativas < 1:
        raise ValueError("max_tentativas deve ser ≥ 1")
    subamostra = 3 * t_s > teto_s
    fracao = teto_s / (3 * t_s) if subamostra else 1.0
    t_efetivo = fracao * t_s
    orcamento = max(piso_s, min(teto_s, t_efetivo * max_tentativas))
    return {
        "t_s": float(t_s),
        "orcamento_s": float(orcamento),
        "subamostra": bool(subamostra),
        "fracao": float(fracao),
    }


def subamostra_estratificada(df: pd.DataFrame, fracao: float, seed: int) -> pd.DataFrame:
    """Subamostra de `fracao` das linhas, estratificada por (região, alvo): a prevalência de cada
    dobra se mantém (R3: sem peso de classe). Pelo menos 1 linha por estrato. Sorteio com a semente
    do config (R8). Devolve com índice 0..n-1, como `cv.run_loro` exige."""
    if not 0 < fracao <= 1:
        raise ValueError(f"fracao deve estar em (0, 1], não {fracao}")
    if fracao == 1:
        return df.reset_index(drop=True)
    rng = np.random.default_rng(seed)
    regiao = df[COLUNA_REGIAO].astype(str).to_numpy()
    alvo = df[COLUNA_ALVO].to_numpy()
    escolhidas = []
    for nome in sorted(set(regiao)):
        for classe in (0, 1):
            posicoes = np.flatnonzero((regiao == nome) & (alvo == classe))
            if posicoes.size == 0:
                continue
            k = max(1, int(round(posicoes.size * fracao)))
            escolhidas.append(rng.choice(posicoes, size=k, replace=False))
    return df.iloc[np.sort(np.concatenate(escolhidas))].reset_index(drop=True)


# --- Objetivo --------------------------------------------------------------------------------

def _motivo_de_poda(
    agora: float, inicio_tentativa: float, fim_busca: float | None, limite_s: float | None,
) -> str | None:
    """Por que a tentativa deve ser podada por tempo, ou None. O orçamento tem prioridade.

    `agora > fim_busca` é o mesmo que "o gasto da tentativa passou do restante do orçamento que
    havia quando ela começou" (restante = fim_busca − início da tentativa).
    """
    if fim_busca is not None and agora > fim_busca:
        return MOTIVO_ORCAMENTO
    if limite_s is not None and agora - inicio_tentativa > limite_s:
        return MOTIVO_LIMITE
    return None


def _objetivo(
    cfg: dict, modelo: str, espaco: EspacoModelo, df: pd.DataFrame, podar: bool,
    fim_busca: float | None = None, limite_tentativa_s: float | None = None,
) -> Callable[[optuna.Trial], float]:
    """Função objetivo: uma tentativa = `cv.run_loro` com os parâmetros sorteados.

    Após cada dobra reporta a PR-AUC acumulada (média até ali) com `step` = dobras concluídas e,
    se `podar`, (1) poda a tentativa por tempo, se ela passou do orçamento que restava na busca
    (`fim_busca`, instante do `perf_counter`) ou do `limite_tentativa_s`, só ao fim das dobras
    anteriores à última (D-89); (2) poda pelo MedianPruner. Guarda o tempo de cada dobra. A
    cronometragem não tem limites (`podar=False`).
    """
    def objetivo(trial: optuna.Trial) -> float:
        valores = sugerir(trial, espaco)
        params = {**espaco.fixos, **valores}
        instante = [time.perf_counter()]
        inicio_tentativa = instante[0]
        tempos: list[float] = []
        prs: list[float] = []

        def ao_fim_da_dobra(regiao: str, indice: int, pr_auc: float) -> None:
            agora = time.perf_counter()
            tempos.append(agora - instante[0])
            instante[0] = agora
            prs.append(pr_auc)
            trial.report(float(np.mean(prs)), step=indice + 1)
            # a última dobra é poupada da poda por tempo (D-89): a tentativa que já terminou
            # todas as dobras fica COMPLETE, mesmo que tenha passado do orçamento ou do limite
            ultima = indice == len(cfg["ordem_dobras"]) - 1
            if podar and not ultima:
                motivo = _motivo_de_poda(agora, inicio_tentativa, fim_busca, limite_tentativa_s)
                if motivo is not None:
                    trial.set_user_attr("tempo_dobras_s", [float(x) for x in tempos])
                    trial.set_user_attr("motivo_poda", motivo)
                    raise optuna.TrialPruned(f"{motivo} após {indice + 1} dobra(s)")
            if podar and trial.should_prune():
                raise optuna.TrialPruned(f"podada após {indice + 1} dobra(s)")

        resultado = cv.run_loro(cfg, modelo, params, df, ao_fim_da_dobra=ao_fim_da_dobra)
        trial.set_user_attr("pr_auc_por_dobra", {
            k: float(v) for k, v in resultado["pr_auc_por_dobra"].items()
        })
        trial.set_user_attr("melhores_pontos", {
            k: (None if v is None else int(v)) for k, v in resultado["melhores_pontos"].items()
        })
        trial.set_user_attr("tempo_dobras_s", [float(x) for x in tempos])
        return float(resultado["pr_auc_media"])

    return objetivo


# --- Cronometragem, busca e melhor tentativa -------------------------------------------------

def _espaco(cfg: dict, modelo: str) -> EspacoModelo:
    espacos = load_search_space(cfg)
    if modelo not in espacos:
        raise ValueError(f"modelo {modelo!r} não está em ordem_modelos")
    espaco = espacos[modelo]
    if espaco.sem_busca:
        raise ValueError(f"{modelo} não tem busca (sem_busca: true, D-69)")
    return espaco


def _segundos(trial: optuna.trial.FrozenTrial) -> float:
    """Tempo gasto numa tentativa. Tentativa copiada da cronometragem não tem `duration` (o
    `create_trial` não grava), então usa a soma das dobras; as demais, a duração do Optuna."""
    tempos = trial.user_attrs.get("tempo_dobras_s")
    if tempos:
        return float(sum(tempos))
    if trial.duration is not None:
        return trial.duration.total_seconds()
    return 0.0


def _cronometrar(
    cfg: dict, estudo: optuna.Study, espaco: EspacoModelo, df: pd.DataFrame,
    max_tentativas: int, piso_s: float, teto_s: float,
) -> None:
    """Mede a 1ª tentativa (dados completos, sem poda), decide o orçamento e grava a decisão."""
    modelo = espaco.modelo
    estudo_cron = criar_estudo_cronometragem(cfg, modelo)
    marcar_interrompidas(estudo_cron)
    medidas = estudo_cron.get_trials(deepcopy=False, states=(TrialState.COMPLETE,))
    if medidas:  # medida em sessão anterior: não repete
        trial = medidas[0]
    else:
        em_espera = [
            t.number for t in estudo_cron.get_trials(deepcopy=False, states=(TrialState.WAITING,))
        ]
        numero_novo = len(estudo_cron.get_trials(deepcopy=False))
        estudo_cron.enqueue_trial(dict(espaco.primeira_tentativa))
        estudo_cron.optimize(_objetivo(cfg, modelo, espaco, df, podar=False), n_trials=1)
        # o Optuna roda a tentativa em espera de menor número (sobra de sessão anterior, se houver)
        executada = min([*em_espera, numero_novo])
        trial = {t.number: t for t in estudo_cron.get_trials(deepcopy=False)}[executada]
    tempos = trial.user_attrs.get("tempo_dobras_s")
    if trial.state != TrialState.COMPLETE or not tempos:
        raise RuntimeError(f"cronometragem não terminou (estado {trial.state.name})")

    decisao = calcular_orcamento(sum(tempos), max_tentativas, piso_s, teto_s)
    if decisao["subamostra"]:
        # fora da comparação: a busca em subamostra começa pelo mesmo ponto, na mesma escala
        numero = None
        estudo.enqueue_trial(dict(espaco.primeira_tentativa))
    else:
        # comparável: a tentativa medida vira a 1ª do estudo principal (sem nova execução)
        numero = len(estudo.get_trials(deepcopy=False))
        estudo.add_trial(optuna.trial.create_trial(
            state=TrialState.COMPLETE,
            value=trial.value,
            params=trial.params,
            distributions=trial.distributions,
            user_attrs=trial.user_attrs,
            intermediate_values=trial.intermediate_values,
        ))
    estudo.set_user_attr(ATRIBUTO_CRONOMETRAGEM, {
        **decisao,
        "numero_tentativa": numero,
        "teto_s": float(teto_s),
        "piso_s": float(piso_s),
        "tempos_dobras_s": [float(x) for x in tempos],
    })


def _melhor(estudo: optuna.Study) -> optuna.trial.FrozenTrial | None:
    completas = estudo.get_trials(deepcopy=False, states=(TrialState.COMPLETE,))
    if not completas:
        return None
    return max(completas, key=lambda t: (t.value, -t.number))  # empate: a mais antiga


def registrar_melhor_tentativa(
    modelo: str, numero: int, valor: float, run_id: str
) -> bool:
    """Põe a tentativa no registro `m1-<modelo>` com o alias `melhor-validacao` (FR-22).

    Só move o alias se a tentativa tiver PR-AUC estritamente maior que a atual. Devolve True se
    criou uma versão nova e moveu o alias. O artefato `melhor_tentativa.json` deve estar no run.
    """
    client = MlflowClient(tracking_uri=mlflow.get_tracking_uri())
    nome = nome_modelo_registrado(modelo)
    try:
        client.get_registered_model(nome)
    except MlflowException:
        client.create_registered_model(nome)
    try:
        atual = client.get_model_version_by_alias(nome, ALIAS_MELHOR)
    except MlflowException:
        atual = None
    if atual is not None and float(atual.tags["pr_auc"]) >= float(valor):
        return False  # pior ou igual não sobrescreve
    versao = client.create_model_version(
        nome,
        source=f"runs:/{run_id}/{NOME_ARTEFATO}",
        run_id=run_id,
        tags={"trial_number": str(numero), "pr_auc": repr(float(valor)), "study_name": modelo},
    )
    client.set_registered_model_alias(nome, ALIAS_MELHOR, versao.version)
    return True


def tune(cfg: dict, modelo: str, df: pd.DataFrame) -> dict:
    """Roda (ou retoma) a busca Optuna de um modelo e devolve o resumo (T-4.3).

    `df` são as linhas de 2022–23 com `ANO`, `regiao`, `y` e as features, índice 0..n-1.
    Devolve `melhores_parametros` (com os `fixos`, prontos para `cv.run_loro`) e os números da
    busca. Grava tudo no MLflow (run `tune-<modelo>`).
    """
    assert_dev_only(df)  # R1
    espaco = _espaco(cfg, modelo)
    max_tentativas = int(cfg["optuna"]["max_tentativas"][modelo])
    teto_s = float(cfg["orcamento_teto_min"][modelo]) * 60
    piso_s = float(cfg["orcamento_piso_min"]) * 60

    estudo = criar_estudo(cfg, modelo)
    interrompidas = marcar_interrompidas(estudo)
    inicio = time.perf_counter()
    tags = {"modelo": modelo, "etapa": "T-4.3"}
    with tracking.start_run(cfg, f"tune-{modelo}", tags=tags) as run:
        if ATRIBUTO_CRONOMETRAGEM not in estudo.user_attrs:
            _cronometrar(cfg, estudo, espaco, df, max_tentativas, piso_s, teto_s)
        cron = estudo.user_attrs[ATRIBUTO_CRONOMETRAGEM]

        # sem subamostra usa o próprio df (sem cópia): run_loro já exige índice 0..n-1
        df_busca = (
            subamostra_estratificada(df, cron["fracao"], cfg["seed"]) if cron["subamostra"] else df
        )
        finalizadas = [
            t for t in estudo.trials if t.state in (TrialState.COMPLETE, TrialState.PRUNED)
        ]
        gasto_s = sum(_segundos(t) for t in finalizadas)
        restantes = max_tentativas - len(finalizadas)
        tempo_restante = cron["orcamento_s"] - gasto_s
        # limite por tentativa: 3 × o custo de referência de uma tentativa na busca (fracao · t)
        limite_tentativa_s = FATOR_LIMITE_TENTATIVA * cron["fracao"] * cron["t_s"]
        if restantes > 0 and tempo_restante > 0:
            fim_busca = time.perf_counter() + tempo_restante
            estudo.optimize(
                _objetivo(cfg, modelo, espaco, df_busca, podar=True,
                          fim_busca=fim_busca, limite_tentativa_s=limite_tentativa_s),
                n_trials=restantes,
                timeout=tempo_restante,
            )

        concluidas = [t for t in estudo.trials if t.state == TrialState.COMPLETE]
        podadas = [t for t in estudo.trials if t.state == TrialState.PRUNED]
        falhas = [t for t in estudo.trials if t.state == TrialState.FAIL]
        gasto_total_s = sum(
            _segundos(t) for t in estudo.trials
            if t.state in (TrialState.COMPLETE, TrialState.PRUNED)
        )
        melhor = _melhor(estudo)
        melhores = {**espaco.fixos, **melhor.params} if melhor is not None else None
        # maior dobra vista na busca: uma tentativa que cruza o fim do orçamento pode passar dele
        # por no máximo uma dobra (a poda é no fim da dobra), então esse é o tamanho da folga
        maior_dobra_s = max(
            (max(t.user_attrs["tempo_dobras_s"]) for t in estudo.trials
             if t.state in (TrialState.COMPLETE, TrialState.PRUNED)
             and t.user_attrs.get("tempo_dobras_s")),
            default=0.0,
        )

        mlflow.log_params({
            "tuning.modelo": modelo,
            "tuning.subamostra": str(cron["subamostra"]),
            "tuning.fracao": f"{cron['fracao']:.6f}",
            "tuning.linhas_busca": str(len(df_busca)),
            "tuning.prevalencia_busca": f"{float(df_busca[COLUNA_ALVO].mean()):.6f}",
            "tuning.cronometragem_numero": str(cron["numero_tentativa"]),
            "tuning.interrompidas_na_retomada": str(interrompidas),
            "tuning.melhor_tentativa": "" if melhor is None else str(melhor.number),
        })
        mlflow.log_metrics({
            "tuning.t_cronometragem_s": cron["t_s"],
            "tuning.orcamento_s": cron["orcamento_s"],
            "tuning.teto_s": teto_s,
            "tuning.piso_s": piso_s,
            "tuning.max_tentativas": float(max_tentativas),
            "tuning.limite_tentativa_s": float(limite_tentativa_s),
            "tuning.podadas_por_orcamento": float(sum(
                1 for t in podadas if t.user_attrs.get("motivo_poda") == MOTIVO_ORCAMENTO)),
            "tuning.podadas_por_limite": float(sum(
                1 for t in podadas if t.user_attrs.get("motivo_poda") == MOTIVO_LIMITE)),
            "tuning.tentativas_concluidas": float(len(concluidas)),
            "tuning.tentativas_podadas": float(len(podadas)),
            "tuning.tentativas_falhas": float(len(falhas)),
            "tuning.tempo_busca_total_s": float(gasto_total_s),
            "tuning.tempo_sessao_s": float(time.perf_counter() - inicio),
        })

        alias_atualizado = False
        if melhor is not None:
            payload = {
                "modelo": modelo,
                "trial_number": melhor.number,
                "pr_auc": float(melhor.value),
                "params": melhores,
                "pr_auc_por_dobra": melhor.user_attrs.get("pr_auc_por_dobra"),
                "melhores_pontos": melhor.user_attrs.get("melhores_pontos"),
            }
            mlflow.log_dict(payload, NOME_ARTEFATO)
            mlflow.log_metric("tuning.melhor_pr_auc", float(melhor.value))
            alias_atualizado = registrar_melhor_tentativa(
                modelo, melhor.number, float(melhor.value), run.info.run_id
            )
        mlflow.log_param("tuning.alias_atualizado", str(alias_atualizado))

    return {
        "modelo": modelo,
        "run_id": run.info.run_id,
        "t_cronometragem_s": cron["t_s"],
        "orcamento_s": cron["orcamento_s"],
        "subamostra": cron["subamostra"],
        "fracao": cron["fracao"],
        "linhas_busca": len(df_busca),
        "tentativas_concluidas": len(concluidas),
        "tentativas_podadas": len(podadas),
        "tentativas_falhas": len(falhas),
        "interrompidas_na_retomada": interrompidas,
        "tempo_busca_total_s": gasto_total_s,
        "maior_dobra_s": maior_dobra_s,
        "melhor_tentativa": None if melhor is None else melhor.number,
        "melhor_pr_auc": None if melhor is None else float(melhor.value),
        "melhores_parametros": melhores,
        "alias_atualizado": alias_atualizado,
    }


# --- Checagem do SQLite no Drive (T-4.3b, [VERIFY]) ------------------------------------------

def checar_sqlite_no_diretorio(pasta: str | Path) -> dict:
    """Cria, grava e reabre um estudo SQLite em `pasta`; devolve um check no formato de `verify`.

    É a checagem inicial da T-4.3b: se o SQLite não abrir no Drive, a sessão para antes de treinar.
    Apaga o arquivo de teste no fim.
    """
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"_checagem_{uuid.uuid4().hex}.db"
    url = _url_sqlite(caminho)
    valor = 0.25
    obtido = "ok"
    storage = None
    try:
        storage = RDBStorage(url)
        estudo = optuna.create_study(study_name="checagem", storage=storage, direction="maximize")
        estudo.optimize(lambda trial: valor, n_trials=1)
        estudo.set_user_attr("gravado", "ok")
        storage.engine.dispose()
        storage = RDBStorage(url)
        reaberto = optuna.load_study(study_name="checagem", storage=storage)
        ok = (
            len(reaberto.trials) == 1
            and reaberto.trials[0].value == valor
            and reaberto.user_attrs.get("gravado") == "ok"
        )
        if not ok:
            obtido = "dados diferentes ao reabrir"
    except Exception as erro:  # o motivo entra no relatório; o check reprova
        obtido = f"erro: {type(erro).__name__}"
    finally:
        if storage is not None:
            storage.engine.dispose()
        caminho.unlink(missing_ok=True)
    return verify.check("sqlite_abre_no_diretorio", "ok", obtido)
