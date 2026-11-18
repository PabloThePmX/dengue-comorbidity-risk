"""Baselines, candidatos de M1, validação leave-one-region-out, calibração e retreino final.

Regras da constituição respeitadas aqui: sem correção de desbalanceamento (R3, D-38); nada de
UF/região/ano em X (R4); todo ajuste dentro da dobra de treino (R5); early stopping só na
validação interna das regiões de treino (R6); semente única (R8).
"""

import hashlib
import json
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

from dengue_sinan.dataset import (
    ACHADOS,
    NIVEIS,
    PARES,
    SEXOS,
    SINTOMAS,
    adicionar_pares,
    matriz_arvore,
)
from dengue_sinan.folds import dobras_loro, validacao_interna
from dengue_sinan.guard import verificar_dev
from dengue_sinan.metrics import brier
from dengue_sinan.profiling import COMORBIDADES

try:  # opcional: sem XGBoost, usa HistGradientBoosting (mesma família, scikit-learn puro)
    import xgboost as xgb
except ImportError:  # pragma: no cover
    xgb = None

_VERSAO_SK = tuple(int(v) for v in sklearn.__version__.split(".")[:2])


# ------------------------------------------------------------------------------ baselines
def b2_flag(x: pd.DataFrame) -> np.ndarray:
    """B2 — regra do protocolo do MS (grupo B), só com critérios que existem na ficha (§3.10).

    [ASSUMPTION] do spec: idade < 24 meses ou > 65 anos; gestante; ≥ 1 das 7 comorbidades = Sim;
    prova do laço positiva (LACO = Sim) ou petéquias (PETEQUIA_N = Sim). Não cobre DPOC, asma,
    obesidade, outras cardiopatias nem risco social (ausentes da ficha).
    """
    idade = x["idade_anos"].to_numpy()
    flag = (idade < 2.0) | (idade > 65.0) | (x["gestante"].to_numpy() == 1)
    flag |= x["n_comorbidades"].to_numpy() >= 1
    flag |= (x["LACO"] == "Sim").to_numpy() | (x["PETEQUIA_N"] == "Sim").to_numpy()
    return np.asarray(flag, dtype=bool)


def preprocessador_linear(perfil: bool, pares: bool) -> ColumnTransformer:
    """ColumnTransformer da família linear; `perfil=True` → só o perfil, sem sintomas."""
    cats = ["sexo", *COMORBIDADES] + ([] if perfil else [*SINTOMAS, *ACHADOS])
    niveis = [SEXOS] + [NIVEIS] * (len(cats) - 1)
    numericas = ["n_comorbidades"] + ([] if perfil else ["dias_ate_notificacao"])
    binarias = ["gestante"] + ([f"ix_{a}_{b}" for a, b in PARES] if pares else [])
    return ColumnTransformer(
        [
            (
                "idade",
                SplineTransformer(n_knots=5, degree=3, knots="quantile", include_bias=False),
                ["idade_anos"],
            ),
            ("cat", OneHotEncoder(categories=niveis, handle_unknown="ignore"), cats),
            (
                "num",
                Pipeline([("imp", SimpleImputer(strategy="median")), ("esc", StandardScaler())]),
                numericas,
            ),
            ("bin", "passthrough", binarias),
        ],
        sparse_threshold=1.0,
    )


def logreg_sem_penalizacao(max_iter: int = 1000) -> LogisticRegression:
    return LogisticRegression(C=np.inf, solver="lbfgs", max_iter=max_iter)


def logreg_elastic_net(
    C: float, l1_ratio: float, seed: int, max_iter: int = 300
) -> LogisticRegression:
    kw = {
        "solver": "saga",
        "C": C,
        "l1_ratio": l1_ratio,
        "max_iter": max_iter,
        "tol": 1e-3,
        "random_state": seed,
    }
    if _VERSAO_SK < (1, 8):  # nas versões novas, l1_ratio ∈ (0, 1) já implica elastic net
        kw["penalty"] = "elasticnet"
    return LogisticRegression(**kw)


class ModeloB1:
    """B1 — logística simples (efeitos principais: idade em spline, sexo, gestação...)."""

    def __init__(self):
        self.pipe = Pipeline(
            [
                ("prep", preprocessador_linear(perfil=True, pares=False)),
                ("clf", logreg_sem_penalizacao()),
            ]
        )

    def ajustar(self, x, y, meta=None):
        verificar_dev(x, meta=meta, contexto="ModeloB1.ajustar")  # R1 (J8)
        self.pipe.fit(x, np.asarray(y))
        return self

    def prever(self, x) -> np.ndarray:
        return self.pipe.predict_proba(x)[:, 1]


def oof_b0(y: np.ndarray, regiao: pd.Series, meta=None) -> np.ndarray:
    """B0 — prevê a prevalência do treino da dobra para todos."""
    verificar_dev(regiao, meta=meta, contexto="oof_b0")  # R1 (J8)
    y = np.asarray(y)
    oof = np.full(len(y), np.nan)
    for _, tr, te in dobras_loro(regiao):
        oof[te] = y[tr].mean()
    return oof


def oof_b1(x: pd.DataFrame, y: np.ndarray, regiao: pd.Series, meta=None) -> np.ndarray:
    verificar_dev(x, regiao, meta=meta, contexto="oof_b1")  # R1 (J8)
    y = np.asarray(y)
    oof = np.full(len(y), np.nan)
    for _, tr, te in dobras_loro(regiao):
        oof[te] = ModeloB1().ajustar(x.iloc[tr], y[tr]).prever(x.iloc[te])
    return oof


# ------------------------------------------------------------------------------ candidatos de M1
class ModeloM1:
    """Interface única dos candidatos: ajustar(x, y, n_fixo=None) / prever(x) / melhor_.

    `x` é o DataFrame de features (lista fechada). As transformações sem estado (ordinal para
    árvores, pares para a linear) ficam aqui dentro; as com estado (spline, escala, imputação)
    ficam num Pipeline ajustado só com o treino (R5).
    """

    def __init__(
        self,
        nome: str,
        params: dict,
        seed: int,
        paciencia: int = 50,
        val_frac: float = 0.10,
        max_iter: int = 1000,
        device: str = "cpu",
        n_jobs: int = -1,
    ):
        self.nome, self.params, self.seed = nome, dict(params), seed
        self.paciencia, self.val_frac, self.max_iter = paciencia, val_frac, max_iter
        self.device, self.n_jobs = device, n_jobs
        self.melhor_ = None
        self.motor_ = None

    def _matriz(self, x):
        if self.nome == "elastic_net":
            return adicionar_pares(x)
        return matriz_arvore(x, dias_nan=-1.0 if self.nome == "random_forest" else None)

    def ajustar(self, x: pd.DataFrame, y, n_fixo: int | None = None, meta=None):
        verificar_dev(x, meta=meta, contexto=f"ModeloM1.ajustar[{self.nome}]")  # R1 (J8)
        y = np.asarray(y)
        m = self._matriz(x)
        if self.nome == "elastic_net":
            clf = logreg_elastic_net(
                self.params["C"],
                self.params["l1_ratio"],
                self.seed,
                self.params.get("max_iter", 300),
            )
            self.motor_ = Pipeline(
                [("prep", preprocessador_linear(perfil=False, pares=True)), ("clf", clf)]
            ).fit(m, y)
            self.melhor_ = int(getattr(clf, "n_iter_", [0])[0])
        elif self.nome == "random_forest":
            self.motor_ = RandomForestClassifier(
                n_estimators=self.params["n_estimators"],
                min_samples_leaf=self.params["min_samples_leaf"],
                max_features=self.params["max_features"],
                max_samples=self.params["max_samples"],
                n_jobs=self.n_jobs,
                random_state=self.seed,
            ).fit(m, y)
            self.melhor_ = self.params["n_estimators"]
        elif self.nome == "xgboost" and xgb is not None:
            self._ajustar_xgb(m, y, n_fixo)
        elif self.nome in ("xgboost", "hgb"):
            self._ajustar_hgb(m, y, n_fixo)
        else:
            raise ValueError(f"candidato desconhecido: {self.nome}")
        return self

    def _ajustar_xgb(self, m, y, n_fixo):
        p = self.params
        base = {
            "learning_rate": p["learning_rate"],
            "max_depth": p["max_depth"],
            "min_child_weight": p["min_child_weight"],
            "subsample": p["subsample"],
            "colsample_bytree": p["colsample_bytree"],
            "reg_lambda": p["reg_lambda"],
            "tree_method": "hist",
            "n_jobs": self.n_jobs,
            "random_state": self.seed,
            "device": self.device,
            "eval_metric": "aucpr",
        }
        if n_fixo is None:  # early stopping na validação interna das regiões de treino (R6)
            tr, va = validacao_interna(y, self.val_frac, self.seed)
            clf = xgb.XGBClassifier(
                n_estimators=self.max_iter, early_stopping_rounds=self.paciencia, **base
            )
            clf.fit(m.iloc[tr], y[tr], eval_set=[(m.iloc[va], y[va])], verbose=False)
            self.melhor_ = int(clf.best_iteration) + 1
        else:  # retreino final: nº de árvores = mediana dos melhores pontos (D-37)
            clf = xgb.XGBClassifier(n_estimators=int(n_fixo), **base).fit(m, y)
            self.melhor_ = int(n_fixo)
        self.motor_ = clf

    def _ajustar_hgb(self, m, y, n_fixo):
        p = self.params
        clf = HistGradientBoostingClassifier(
            learning_rate=p["learning_rate"],
            max_depth=p["max_depth"],
            min_samples_leaf=max(int(p.get("min_child_weight", 20)), 20),
            l2_regularization=p["reg_lambda"],
            max_iter=self.max_iter if n_fixo is None else int(n_fixo),
            early_stopping=n_fixo is None,
            scoring="average_precision",
            validation_fraction=self.val_frac,
            n_iter_no_change=self.paciencia,
            random_state=self.seed,
        )
        self.motor_ = clf.fit(m, y)
        self.melhor_ = int(clf.n_iter_)

    def prever(self, x: pd.DataFrame) -> np.ndarray:
        return self.motor_.predict_proba(self._matriz(x))[:, 1]


def rotulo_boosting() -> str:
    return "xgboost" if xgb is not None else "hgb"


# ------------------------------------------------------------------------------ validação LORO
def cv_oof(
    nome: str, params: dict, x: pd.DataFrame, y, regiao: pd.Series, seed: int, meta=None, **kw
) -> dict:
    """Predições fora da dobra (leave-one-region-out): treina em 4 regiões, prediz a 5ª (FR-17).

    R1 (J8): `verificar_dev` roda aqui, em todo caminho, sem depender de quem chama.
    """
    verificar_dev(x, regiao, meta=meta, contexto="cv_oof")
    y = np.asarray(y)
    oof = np.full(len(y), np.nan)
    info = {"pr_auc_dobra": {}, "melhor_iter": [], "tempo_s": 0.0}
    t0 = time.time()
    for r, tr, te in dobras_loro(regiao):
        mod = ModeloM1(nome, params, seed, **kw).ajustar(x.iloc[tr], y[tr])
        oof[te] = mod.prever(x.iloc[te])
        info["pr_auc_dobra"][r] = float(average_precision_score(y[te], oof[te]))
        info["melhor_iter"].append(mod.melhor_)
    info["tempo_s"] = time.time() - t0
    info["pr_auc_media"] = float(np.mean(list(info["pr_auc_dobra"].values())))
    return {"oof": oof, **info}


def _chave_cache(nome, params, assinatura) -> str:
    texto = json.dumps({"n": nome, "p": params, "a": assinatura}, sort_keys=True, default=str)
    return hashlib.sha1(texto.encode()).hexdigest()[:16]


def busca_hiperparametros(
    nome: str,
    grade: list[dict],
    x,
    y,
    regiao,
    seed: int,
    orcamento_s: float,
    cache_dir: Path | None = None,
    assinatura: dict | None = None,
    meta=None,
    **kw,
) -> dict:
    """Busca em grade pré-declarada, critério = PR-AUC média nas dobras (spec §3.11).

    A 1ª configuração é a de referência e sempre roda; as demais param ao estourar o orçamento
    de tempo do modelo. Cada configuração concluída é guardada em cache (busca retomável).

    DEPRECIADA (J7): o corte por tempo faz a grade avaliada depender da máquina. Use
    `busca_deterministica` em experimentos novos. Mantida só para reproduzir a versão 1.
    """
    warnings.warn(
        "busca_hiperparametros corta a grade por tempo (não determinístico); "
        "use busca_deterministica.",
        DeprecationWarning,
        stacklevel=2,
    )
    verificar_dev(x, regiao, meta=meta, contexto="busca_hiperparametros")  # R1 (J8)
    registros, melhores, t0 = [], None, time.time()
    for i, params in enumerate(grade):
        if i > 0 and time.time() - t0 > orcamento_s:
            break
        arq = None
        if cache_dir is not None:
            cache_dir.mkdir(parents=True, exist_ok=True)
            arq = cache_dir / f"oof_{nome}_{_chave_cache(nome, params, assinatura)}.npz"
        if arq is not None and arq.exists():
            z = np.load(arq, allow_pickle=True)
            res = {"oof": z["oof"], **json.loads(str(z["info"]))}
            res["do_cache"] = True
        else:
            res = cv_oof(nome, params, x, y, regiao, seed, meta=meta, **kw)
            res["do_cache"] = False
            if arq is not None:
                info = {k: v for k, v in res.items() if k not in ("oof", "do_cache")}
                np.savez(arq, oof=res["oof"], info=json.dumps(info))
        registros.append(
            {
                "config": i,
                **{f"p_{k}": v for k, v in params.items()},
                "pr_auc_media": res["pr_auc_media"],
                "tempo_s": round(res["tempo_s"], 1),
                "do_cache": res["do_cache"],
            }
        )
        if melhores is None or res["pr_auc_media"] > melhores["pr_auc_media"]:
            melhores = {**res, "params": params, "config": i}
    return {
        "tabela": pd.DataFrame(registros),
        "melhor": melhores,
        "configs_avaliadas": len(registros),
        "configs_na_grade": len(grade),
        "tempo_total_s": time.time() - t0,
    }


CRITERIO_SELECAO_BUSCA = (
    "Maior PR-AUC média das dobras LORO entre as configurações executadas; empate exato "
    "→ menor índice na grade declarada (a 1ª é a de referência). O tempo de execução "
    "só é registrado e nunca entra na decisão."
)


def _hash_grade(grade: list[dict]) -> str:
    texto = json.dumps(grade, sort_keys=True, default=str)
    return hashlib.sha256(texto.encode()).hexdigest()


def busca_deterministica(
    nome: str,
    grade: list[dict],
    x,
    y,
    regiao,
    seed: int,
    max_configs: int,
    registro_dir: Path | None = None,
    cache_dir: Path | None = None,
    assinatura: dict | None = None,
    meta=None,
    **kw,
) -> dict:
    """Busca em grade determinística (J7): limite explícito, ordem fixa, tudo registrado.

    - Avalia as `max_configs` primeiras configurações da grade, na ordem declarada (a 1ª é a de
      referência). Nada depende do relógio nem da máquina.
    - Antes de rodar grava `grade.json` (grade completa, hash, semente, limite, critério); depois
      grava `execucao.json` e `execucao.csv` (cada configuração: executada ou não, e por quê).
    - Seleção: ver `CRITERIO_SELECAO_BUSCA`. R1 verificada (J8). Não amplia a grade sozinha.
    """
    if not grade:
        raise ValueError("grade vazia: declare ao menos a configuração de referência.")
    if not isinstance(max_configs, int) or max_configs < 1:
        raise ValueError("max_configs deve ser um inteiro >= 1 (limite explícito de configs).")
    verificar_dev(x, regiao, meta=meta, contexto="busca_deterministica")
    hash_grade = _hash_grade(grade)
    n_exec = min(max_configs, len(grade))
    registro = {
        "modelo": nome,
        "semente": seed,
        "max_configs": max_configs,
        "n_configs_na_grade": len(grade),
        "hash_grade": hash_grade,
        "criterio_selecao": CRITERIO_SELECAO_BUSCA,
        "configuracoes": [{"config": i, "params": p} for i, p in enumerate(grade)],
    }
    if registro_dir is not None:
        registro_dir = Path(registro_dir)
        registro_dir.mkdir(parents=True, exist_ok=True)
        (registro_dir / "grade.json").write_text(
            json.dumps(registro, indent=2, default=str, ensure_ascii=False), "utf-8"
        )

    linhas, melhor = [], None
    for i, params in enumerate(grade):
        if i >= n_exec:
            linhas.append(
                {
                    "config": i,
                    "status": "nao_executada",
                    "motivo": f"fora do limite max_configs={max_configs}",
                    "params": params,
                }
            )
            continue
        arq = None
        if cache_dir is not None:
            cache_dir = Path(cache_dir)
            cache_dir.mkdir(parents=True, exist_ok=True)
            arq = cache_dir / f"oof_{nome}_{_chave_cache(nome, params, assinatura)}.npz"
        if arq is not None and arq.exists():
            z = np.load(arq, allow_pickle=True)
            res = {"oof": z["oof"], **json.loads(str(z["info"]))}
            res["do_cache"] = True
        else:
            res = cv_oof(nome, params, x, y, regiao, seed, meta=meta, **kw)
            res["do_cache"] = False
            if arq is not None:
                info = {k: v for k, v in res.items() if k not in ("oof", "do_cache")}
                np.savez(arq, oof=res["oof"], info=json.dumps(info))
        linhas.append(
            {
                "config": i,
                "status": "executada",
                "motivo": "",
                "params": params,
                "pr_auc_media": res["pr_auc_media"],
                "tempo_s": round(res["tempo_s"], 1),
                "do_cache": res["do_cache"],
            }
        )
        if melhor is None or res["pr_auc_media"] > melhor["pr_auc_media"]:  # '>' → menor índice
            melhor = {**res, "params": params, "config": i}

    tabela = pd.DataFrame(linhas)
    saida = {
        "tabela": tabela,
        "melhor": melhor,
        "configs_avaliadas": n_exec,
        "configs_na_grade": len(grade),
        "hash_grade": hash_grade,
        "criterio_selecao": CRITERIO_SELECAO_BUSCA,
    }
    if registro_dir is not None:
        (registro_dir / "execucao.json").write_text(
            json.dumps(
                {
                    **{k: registro[k] for k in ("modelo", "semente", "max_configs", "hash_grade")},
                    "criterio_selecao": CRITERIO_SELECAO_BUSCA,
                    "melhor_config": None if melhor is None else melhor["config"],
                    "configuracoes": linhas,
                },
                indent=2,
                default=str,
                ensure_ascii=False,
            ),
            "utf-8",
        )
        tabela.assign(params=tabela["params"].map(lambda d: json.dumps(d, sort_keys=True))).to_csv(
            registro_dir / "execucao.csv", index=False
        )
    return saida


# ------------------------------------------------------------------------------ calibração
class Calibrador:
    """Calibração isotônica ou de Platt (FR-08). Ajustada só em predições fora da dobra."""

    def __init__(self, tipo: str):
        self.tipo = tipo
        self.modelo = None

    def ajustar(self, p, y):
        p, y = np.asarray(p, dtype="float64"), np.asarray(y)
        if self.tipo == "isotonica":
            self.modelo = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(p, y)
        elif self.tipo == "platt":
            self.modelo = logreg_sem_penalizacao().fit(self._logit(p)[:, None], y)
        elif self.tipo != "nenhum":
            raise ValueError(self.tipo)
        return self

    @staticmethod
    def _logit(p):
        p = np.clip(p, 1e-9, 1 - 1e-9)
        return np.log(p / (1 - p))

    def prever(self, p) -> np.ndarray:
        p = np.asarray(p, dtype="float64")
        if self.tipo == "isotonica":
            return self.modelo.predict(p)
        if self.tipo == "platt":
            return self.modelo.predict_proba(self._logit(p)[:, None])[:, 1]
        return p


def calibrar_cruzado(p_oof, y, regiao: pd.Series, tipo: str, meta=None) -> np.ndarray:
    """Calibração cruzada por região: o calibrador de cada dobra NÃO vê essa região."""
    verificar_dev(regiao, meta=meta, contexto="calibrar_cruzado")  # R1 (J8)
    p_oof, y = np.asarray(p_oof, dtype="float64"), np.asarray(y)
    out = np.full(len(y), np.nan)
    for _, tr, te in dobras_loro(regiao):
        ok = tr[~np.isnan(p_oof[tr])]
        out[te] = Calibrador(tipo).ajustar(p_oof[ok], y[ok]).prever(p_oof[te])
    return out


def escolher_calibrador(p_oof, y, regiao, tipos=("nenhum", "platt", "isotonica"), meta=None):
    """Escolhe o tipo pelo menor Brier com calibração cruzada (só dados de desenvolvimento)."""
    verificar_dev(regiao, meta=meta, contexto="escolher_calibrador")  # R1 (J8)
    linhas = []
    for t in tipos:
        pc = calibrar_cruzado(p_oof, y, regiao, t, meta=meta)
        ok = ~np.isnan(pc)
        linhas.append({"calibrador": t, "brier_cruzado": brier(np.asarray(y)[ok], pc[ok])})
    tab = pd.DataFrame(linhas)
    return tab.sort_values("brier_cruzado").iloc[0]["calibrador"], tab


# ------------------------------------------------------------------------------ seleção
ORDEM_SIMPLICIDADE = ["elastic_net", "random_forest", "xgboost", "hgb"]


def selecionar_modelo(resumo: pd.DataFrame, tolerancia: float = 0.005) -> tuple[str, str]:
    """Regra do spec (§3.11): maior PR-AUC média; empate (< 0,005) → menor Brier; senão o simples.

    `resumo`: colunas modelo, pr_auc_media, brier. Devolve (modelo, justificativa).
    """
    r = resumo.sort_values("pr_auc_media", ascending=False).reset_index(drop=True)
    topo = r[r["pr_auc_media"] >= r.loc[0, "pr_auc_media"] - tolerancia]
    if len(topo) == 1:
        return str(topo.iloc[0]["modelo"]), "maior PR-AUC média nas dobras"
    topo = topo.sort_values("brier")
    if topo.iloc[0]["brier"] < topo.iloc[1]["brier"]:
        return str(topo.iloc[0]["modelo"]), "empate de PR-AUC (< 0,005): desempatou o menor Brier"
    simples = sorted(topo["modelo"], key=ORDEM_SIMPLICIDADE.index)[0]
    return str(simples), "empate de PR-AUC e Brier: o modelo mais simples"


def ajustar_final(
    nome: str,
    params: dict,
    x,
    y,
    seed: int,
    n_iter_mediano: int | None,
    x_meta: pd.DataFrame | None = None,
    **kw,
):
    """Retreino em todo o desenvolvimento 2022–23 (D-37). Falha se `x_meta` tiver 2024 (R1)."""
    # R1 (J8): obrigatória. Sem marca em `x` nem `x_meta` com ANO, falha (antes só rodava se
    # o chamador passasse x_meta).
    verificar_dev(x, meta=x_meta, contexto="ajustar_final")
    n_fixo = n_iter_mediano if nome in ("xgboost", "hgb") else None
    return ModeloM1(nome, params, seed, **kw).ajustar(x, y, n_fixo=n_fixo, meta=x_meta)
