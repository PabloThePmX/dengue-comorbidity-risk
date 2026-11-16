"""Baselines B0, B1 e B2 (T-2.8, FR-04, spec › Baselines, R1, R3, R5, D-53, D-62).

- B0 (trivial): prevê a prevalência do **treino** de cada dobra para todos os casos da validação.
- B1 (logística simples): regressão logística **sem penalização**, dentro de um `Pipeline` (R5):
  spline da idade, sexo, gestante e as 7 comorbidades. Sem `n_comorbidades` (D-62) e sem pesos
  de classe (R3). Sem penalização para ter coeficientes interpretáveis (a penalização é do M1, R9).
- B2 (regra do protocolo): binária, não treina e não tem PR-AUC. `rule_b2` é função pura.

Dobras: as de T-2.3 (`folds.load_folds`, com o hash do `reports/verificacao/T-2.3.json`). Para
cada região de validação, o treino são as outras quatro (ajuste + parada). B1 não usa a validação
interna para parada: é uma logística de solver fixo, então o treino inteiro entra.

Toda função que treina ou prevê chama `guard.assert_dev_only` (R1). `rule_b2` não chama: é uma
regra sobre o frame de features que já passou pela guarda ao ser montado.
"""

from pathlib import Path

import mlflow
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer

from dengue_sinan import metrics, tracking
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.profiling import COMORBIDADES

COLUNA_IDADE = "idade_anos"
COLUNA_ALVO = "y"
COLUNA_ANO = "ANO"
COLUNA_REGIAO = "regiao"
VALIDACAO = "validacao"

# Nomes em ordem fixa: o B1 e a regra B2 leem só estas colunas (D-62: sem n_comorbidades).
CATEGORICAS_B1 = ["sexo", *COMORBIDADES]
COLUNAS_B1 = [COLUNA_IDADE, *CATEGORICAS_B1, "gestante"]
# Níveis explícitos, na ordem fixa. O primeiro de cada um vira a referência (drop="first"):
# sexo F e comorbidade "Não". Assim não há colinearidade com o intercepto.
NIVEIS_B1 = {"sexo": ["F", "M", "I"], **{c: ["Não", "Ausente", "Sim"] for c in COMORBIDADES}}

IDADE_MIN_ANOS = 2     # B2: abaixo de 24 meses
IDADE_MAX_ANOS = 65    # B2: acima de 65 anos (inclusive 65 não entra)
LIMIAR_REGRA = 0.5     # B2 é binária: p = 1 quando alto risco, 0 caso contrário
NOMES = ("B0", "B1", "B2")


def rule_b2(df: pd.DataFrame) -> np.ndarray:
    """Regra do protocolo (B2): True se o caso for de alto risco por **qualquer** critério.

    Critérios (spec › Baselines, mapeamento `[ASSUMPTION]`):
    - idade < 2 anos ou > 65 anos;
    - gestante = 1;
    - pelo menos uma das 7 comorbidades = Sim;
    - LACO = Sim ou PETEQUIA_N = Sim.

    Espera o frame de `dataset.build_feature_frame` (comorbidades e sinais em Sim/Não/Ausente).
    """
    idade = df[COLUNA_IDADE].to_numpy()
    alto = (idade < IDADE_MIN_ANOS) | (idade > IDADE_MAX_ANOS)
    alto |= df["gestante"].to_numpy() == 1
    alto |= (df[list(COMORBIDADES)] == "Sim").any(axis=1).to_numpy()
    alto |= (df["LACO"] == "Sim").to_numpy()
    alto |= (df["PETEQUIA_N"] == "Sim").to_numpy()
    return alto.astype(bool)


def fazer_pipeline_b1() -> Pipeline:
    """Pipeline do B1: spline da idade (5 nós, grau 3), one-hot das categóricas, gestante 0/1.

    `C=np.inf` é a forma de pedir logística sem penalização no sklearn 1.8+ (o argumento
    `penalty` está deprecado). Sem `class_weight` (R3). O pré-processamento só aprende no
    `fit` do treino da dobra (R5).
    """
    preprocessamento = ColumnTransformer(
        [
            ("idade", SplineTransformer(n_knots=5, degree=3), [COLUNA_IDADE]),
            ("categoricas", OneHotEncoder(
                categories=[NIVEIS_B1[c] for c in CATEGORICAS_B1],
                drop="first",
                handle_unknown="ignore",
                sparse_output=False,
                dtype=np.float32,
            ), CATEGORICAS_B1),
            ("gestante", "passthrough", ["gestante"]),
        ],
        sparse_threshold=0,
    )
    logistica = LogisticRegression(C=np.inf, solver="lbfgs", max_iter=1000)
    return Pipeline([("preprocessamento", preprocessamento), ("logistica", logistica)])


def ajustar_b1(df_treino: pd.DataFrame) -> Pipeline:
    """Ajusta o B1 só com o treino da dobra (R1, R5)."""
    assert_dev_only(df_treino)
    modelo = fazer_pipeline_b1()
    modelo.fit(df_treino[COLUNAS_B1], df_treino[COLUNA_ALVO].to_numpy())
    return modelo


def prever_b1(modelo: Pipeline, df_validacao: pd.DataFrame) -> np.ndarray:
    """Probabilidade de y = 1 do B1 para a validação da dobra."""
    assert_dev_only(df_validacao)
    return modelo.predict_proba(df_validacao[COLUNAS_B1])[:, 1].astype(float)


def prever_b0(df_treino: pd.DataFrame, df_validacao: pd.DataFrame) -> np.ndarray:
    """B0: prevalência do **treino** da dobra, repetida para cada caso da validação."""
    assert_dev_only(df_treino)
    assert_dev_only(df_validacao)
    prevalencia = float(df_treino[COLUNA_ALVO].mean())
    return np.full(len(df_validacao), prevalencia, dtype=float)


def metricas_probabilisticas(y, p) -> dict[str, float]:
    """PR-AUC, ROC-AUC, Brier e calibração (slope e intercept) de um modelo de probabilidade.

    Slope é indefinido quando `p` é constante (B0 numa dobra): a logística de calibração
    fica singular e o valor é lixo numérico. Nesse caso devolve NaN e não é registrado.
    """
    y_arr = np.asarray(y)
    p_arr = np.asarray(p, dtype=float)
    _slope, intercept = metrics.calibration_slope_intercept(y_arr, p_arr)
    slope = float(_slope) if np.ptp(p_arr) > 0 else float("nan")
    return {
        "pr_auc": metrics.pr_auc(y_arr, p_arr),
        "roc_auc": metrics.roc_auc(y_arr, p_arr),
        "brier": metrics.brier(y_arr, p_arr),
        "calibracao_slope": slope,
        "calibracao_intercept": float(intercept),
    }


def metricas_regra(y, flag) -> dict[str, float]:
    """Recall, precisão e F2 da regra B2 (binária). Sem PR-AUC: a regra não tem ranking."""
    t = metrics.threshold_metrics(np.asarray(y), np.asarray(flag, dtype=float), LIMIAR_REGRA)
    return {"recall": t["recall"], "precisao": t["precisao"], "f2": t["f2"]}


def _colunas_base(df: pd.DataFrame) -> list[str]:
    papeis = [c for c in df.columns if c.startswith("papel_")]
    pedidas = [COLUNA_ANO, COLUNA_REGIAO, COLUNA_ALVO, COLUNA_IDADE, "gestante", "LACO",
               "PETEQUIA_N", *CATEGORICAS_B1, *papeis]
    return list(dict.fromkeys(pedidas))  # sem repetir: as comorbidades já estão em CATEGORICAS_B1


def avaliar_dobras(cfg: dict, df: pd.DataFrame) -> dict[str, dict]:
    """Roda B0, B1 e B2 nas dobras de `cfg["ordem_dobras"]`.

    `df` é o frame de features (`build_feature_frame`) com `papel_<região>` (T-2.3). Devolve,
    por baseline: `por_dobra` (métricas de cada região), `oof` (métricas do OOF agrupado) e
    `oof_df` (ANO, regiao, y, p de todos os casos, uma vez cada).
    """
    assert_dev_only(df)
    base = df[_colunas_base(df)]
    por_dobra: dict[str, dict[str, dict]] = {"B0": {}, "B1": {}, "B2": {}}
    predicoes: dict[str, list[pd.DataFrame]] = {"B0": [], "B1": [], "B2": []}

    for regiao in cfg["ordem_dobras"]:
        papel = base[f"papel_{regiao}"].to_numpy()
        treino = base[papel != VALIDACAO]
        validacao = base[papel == VALIDACAO]
        if validacao.empty or treino.empty:
            raise ValueError(f"dobra {regiao} sem treino ou sem validação")
        y_val = validacao[COLUNA_ALVO].to_numpy()

        previsoes = {
            "B0": prever_b0(treino, validacao),
            "B1": prever_b1(ajustar_b1(treino), validacao),
            "B2": rule_b2(validacao).astype(float),
        }
        for nome, p in previsoes.items():
            if nome == "B2":
                por_dobra[nome][regiao] = metricas_regra(y_val, p)
            else:
                por_dobra[nome][regiao] = metricas_probabilisticas(y_val, p)
            predicoes[nome].append(pd.DataFrame({
                COLUNA_ANO: validacao[COLUNA_ANO].to_numpy(),
                COLUNA_REGIAO: regiao,
                COLUNA_ALVO: y_val,
                "p": p,
            }))

    resultados = {}
    for nome in ("B0", "B1", "B2"):
        oof_df = pd.concat(predicoes[nome], ignore_index=True)
        if nome == "B2":
            oof = metricas_regra(oof_df[COLUNA_ALVO], oof_df["p"])
        else:
            oof = metricas_probabilisticas(oof_df[COLUNA_ALVO], oof_df["p"])
        resultados[nome] = {"por_dobra": por_dobra[nome], "oof": oof, "oof_df": oof_df}
    return resultados


# --- MLflow (T-2.5) ----------------------------------------------------------------------------

PARAMS_B1 = {
    "B1.penalizacao": "nenhuma (C=inf)",
    "B1.solver": "lbfgs",
    "B1.max_iter": "1000",
    "B1.spline": "5 nos, grau 3",
    "B1.features": ",".join(COLUNAS_B1),
    "B1.pesos_de_classe": "nenhum (R3)",
}


def _sem_nan(metricas: dict[str, float]) -> dict[str, float]:
    """Slope indefinido (NaN) não vai para o MLflow; fica como '—' no relatório."""
    return {k: v for k, v in metricas.items() if not np.isnan(v)}


def registrar_mlflow(cfg: dict, resultados: dict[str, dict]) -> dict[str, str]:
    """Um run por baseline (B0, B1, B2): métricas por dobra, OOF agrupado e predições OOF.

    As predições vão para `data/oof` (fora do git, R7) por `tracking.log_oof_predictions`.
    Devolve {nome: run_id}.
    """
    ids: dict[str, str] = {}
    for nome in NOMES:
        r = resultados[nome]
        tags = {"baseline": nome, "tipo": "regra" if nome == "B2" else "modelo"}
        with tracking.start_run(cfg, nome, tags) as run:
            if nome == "B1":
                mlflow.log_params(PARAMS_B1)
            for regiao in cfg["ordem_dobras"]:
                tracking.log_fold_metrics(regiao, _sem_nan(r["por_dobra"][regiao]))
            tracking.log_fold_metrics("OOF", _sem_nan(r["oof"]))
            tracking.log_oof_predictions(cfg, nome, r["oof_df"])
            ids[nome] = run.info.run_id
    return ids


# --- Relatório (R7: só agregados) --------------------------------------------------------------

def _num(valor: float, casas: int) -> str:
    """Número em pt-BR; NaN vira '—' (slope de preditor constante)."""
    if valor is None or np.isnan(valor):
        return "—"
    return f"{valor:.{casas}f}".replace(".", ",")


def _contagem(valor: int, minimo: int) -> str:
    """Contagem publicada: abaixo de `minimo` vira '<minimo' (R7)."""
    return f"<{minimo}" if 0 < valor < minimo else f"{valor:,}".replace(",", " ")


def _eventos_por_dobra(oof_df: pd.DataFrame, ordem: list[str]) -> dict[str, int]:
    soma = oof_df.groupby(COLUNA_REGIAO)[COLUNA_ALVO].sum()
    return {regiao: int(soma[regiao]) for regiao in ordem}


def _tabela_probabilistica(resultado: dict, ordem: list[str], minimo: int) -> list[str]:
    eventos = _eventos_por_dobra(resultado["oof_df"], ordem)
    linhas = [
        "| Dobra (validação) | Eventos | PR-AUC | ROC-AUC | Brier | Slope | Intercept |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for regiao in ordem:
        m = resultado["por_dobra"][regiao]
        linhas.append(
            f"| {regiao} | {_contagem(eventos[regiao], minimo)} | {_num(m['pr_auc'], 5)} | "
            f"{_num(m['roc_auc'], 4)} | {_num(m['brier'], 5)} | "
            f"{_num(m['calibracao_slope'], 3)} | {_num(m['calibracao_intercept'], 3)} |")
    o = resultado["oof"]
    linhas.append(
        f"| **OOF agrupado** | {_contagem(sum(eventos.values()), minimo)} | "
        f"{_num(o['pr_auc'], 5)} | {_num(o['roc_auc'], 4)} | {_num(o['brier'], 5)} | "
        f"{_num(o['calibracao_slope'], 3)} | {_num(o['calibracao_intercept'], 3)} |")
    return linhas


def _tabela_regra(resultado: dict, ordem: list[str], minimo: int) -> list[str]:
    eventos = _eventos_por_dobra(resultado["oof_df"], ordem)
    linhas = [
        "| Dobra (validação) | Eventos | Recall | Precisão | F2 |",
        "|---|---:|---:|---:|---:|",
    ]
    for regiao in ordem:
        m = resultado["por_dobra"][regiao]
        linhas.append(f"| {regiao} | {_contagem(eventos[regiao], minimo)} | "
                      f"{_num(m['recall'], 4)} | {_num(m['precisao'], 4)} | {_num(m['f2'], 4)} |")
    o = resultado["oof"]
    linhas.append(f"| **OOF agrupado** | {_contagem(sum(eventos.values()), minimo)} | "
                  f"{_num(o['recall'], 4)} | {_num(o['precisao'], 4)} | {_num(o['f2'], 4)} |")
    return linhas


def escrever_relatorio(cfg: dict, resultados: dict[str, dict], caminho: Path,
                       hash_dobras: str) -> Path:
    """Grava `reports/baselines.md`: métricas de B0, B1 (por dobra e OOF) e B2 (regra)."""
    minimo = cfg["supressao_min_celula"]
    ordem = list(cfg["ordem_dobras"])
    partes = [
        "# Baselines B0, B1 e B2 (FR-04)",
        "",
        "Desenvolvimento 2022–23, com as dobras leave-one-region-out da T-2.3 (hash do conteúdo "
        f"`{hash_dobras[:16]}…`, semente {cfg['seed']}). O ano de teste não foi lido (R1). Cada "
        "dobra mede a região deixada de fora; o OOF agrupado junta as cinco predições, "
        "uma por caso.",
        "",
        "## B0 — prevalência do treino",
        "",
        *_tabela_probabilistica(resultados["B0"], ordem, minimo),
        "",
        "## B1 — logística sem penalização",
        "",
        "Spline da idade (5 nós), sexo, gestante e as 7 comorbidades. Sem `n_comorbidades` (D-62) "
        "e sem pesos de classe (R3).",
        "",
        *_tabela_probabilistica(resultados["B1"], ordem, minimo),
        "",
        "## B2 — regra do protocolo",
        "",
        "**B2 é uma regra, não um modelo:** não treina e não tem PR-AUC; por isso a tabela traz só "
        "recall, precisão e F2 no limiar da própria regra.",
        "",
        *_tabela_regra(resultados["B2"], ordem, minimo),
        "",
        "## Notas",
        "",
        "- Slope de B0 é indefinido (predição constante em cada dobra): aparece como —.",
        f"- Eventos abaixo de {minimo} são publicados como <{minimo} (R7).",
        "- Os números são agregados. Nenhuma linha individual sai deste relatório (R7).",
    ]
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text("\n".join(partes) + "\n", encoding="utf-8")
    return caminho
