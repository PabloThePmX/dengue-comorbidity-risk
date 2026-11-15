"""Busca de hiperparâmetros com Optuna, cronometragem e poda (T-4.0, T-4.3, D-43, D-53)."""

import time
from pathlib import Path
from typing import Any

import mlflow
import numpy as np
import optuna
import pandas as pd
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler
from optuna.trial import TrialState

from dengue_sinan.cv import run_loro
from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.tracking import hardware_info, start_run

optuna.logging.set_verbosity(optuna.logging.WARNING)

HIDDEN_ARCH_MAP: dict[str, tuple[int, ...]] = {
    "64": (64,),
    "128": (128,),
    "128_64": (128, 64),
}


def default_trial_params(modelo: str) -> dict[str, Any]:
    """Parâmetros padrão da 1ª tentativa enfileirada para cronometragem (D-53)."""
    m = modelo.strip().lower()
    if m in {"elastic_net", "elasticnet"}:
        return {"C": 1.0, "l1_ratio": 0.5}
    if m in {"random_forest", "rf"}:
        return {
            "n_estimators": 200,
            "use_max_depth": True,
            "max_depth": 10,
            "min_samples_leaf": 50,
            "max_features": "sqrt",
            "max_samples": 0.10,
        }
    if m in {"xgboost", "xgb"}:
        return {
            "learning_rate": 0.05,
            "max_depth": 6,
            "min_child_weight": 10.0,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_lambda": 1.0,
        }
    if m == "catboost":
        return {
            "learning_rate": 0.05,
            "depth": 6,
            "l2_leaf_reg": 3.0,
        }
    if m == "mlp":
        return {
            "arch": "64",
            "dropout": 0.1,
            "weight_decay": 1e-4,
            "lr": 1e-3,
            "batch_size": 1024,
        }
    return {}


def sample_params(trial: optuna.Trial, modelo: str, cfg: dict[str, Any]) -> dict[str, Any]:
    """Sorteia hiperparâmetros segundo o espaço de busca de T-4.0 (sem pesos de classe — R3)."""
    m = modelo.strip().lower()
    fast_cfg = cfg.get("modo_teste_rapido", False)

    if m in {"elastic_net", "elasticnet"}:
        return {
            "C": trial.suggest_float("C", 1e-3, 10.0, log=True),
            "l1_ratio": trial.suggest_float("l1_ratio", 0.0, 1.0),
            "max_iter": 200 if fast_cfg else 500,
        }

    if m in {"random_forest", "rf"}:
        use_depth = trial.suggest_categorical("use_max_depth", [True, False])
        max_depth = trial.suggest_int("max_depth", 4, 20) if use_depth else None
        n_est = (
            trial.suggest_int("n_estimators", 20, 40)
            if fast_cfg
            else trial.suggest_int("n_estimators", 200, 800)
        )
        return {
            "n_estimators": n_est,
            "max_depth": max_depth,
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 10, 500, log=True),
            "max_features": trial.suggest_categorical("max_features", ["sqrt", 0.3, 0.5]),
            "max_samples": trial.suggest_float("max_samples", 0.05, 0.30),
        }

    if m in {"xgboost", "xgb"}:
        import torch

        dev = "cuda" if torch.cuda.is_available() and not fast_cfg else "cpu"
        return {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "min_child_weight": trial.suggest_float("min_child_weight", 1.0, 100.0, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
            "n_estimators": 30 if fast_cfg else 2000,
            "early_stopping_rounds": 5 if fast_cfg else 50,
            "tree_method": "hist",
            "device": dev,
        }

    if m == "catboost":
        import torch

        task_type = "GPU" if torch.cuda.is_available() and not fast_cfg else "CPU"
        return {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "depth": trial.suggest_int("depth", 4, 10),
            "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1.0, 30.0, log=True),
            "iterations": 30 if fast_cfg else 3000,
            "early_stopping_rounds": 5 if fast_cfg else 50,
            "task_type": task_type,
        }

    if m == "mlp":
        arch_key = trial.suggest_categorical("arch", ["64", "128", "128_64"])
        return {
            "hidden_layers": HIDDEN_ARCH_MAP[str(arch_key)],
            "dropout": trial.suggest_float("dropout", 0.0, 0.3),
            "weight_decay": trial.suggest_float("weight_decay", 1e-6, 1e-2, log=True),
            "lr": trial.suggest_float("lr", 1e-4, 1e-2, log=True),
            "batch_size": trial.suggest_categorical("batch_size", [1024, 4096]),
            "max_epochs": 15 if fast_cfg else 200,
            "patience": 3 if fast_cfg else 10,
        }

    return {}


def resolve_best_params(
    best_trial_params: dict[str, Any],
    modelo: str,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    """Reconstrói o dicionário completo de parâmetros do modelo a partir de `study.best_params`."""
    m = modelo.strip().lower()
    fast_cfg = cfg.get("modo_teste_rapido", False)
    p = dict(best_trial_params)

    if m in {"elastic_net", "elasticnet"}:
        p.setdefault("max_iter", 200 if fast_cfg else 500)
        return p

    if m in {"random_forest", "rf"}:
        use_depth = p.pop("use_max_depth", True)
        if not use_depth:
            p["max_depth"] = None
        return p

    if m in {"xgboost", "xgb"}:
        import torch

        p.setdefault("n_estimators", 30 if fast_cfg else 2000)
        p.setdefault("early_stopping_rounds", 5 if fast_cfg else 50)
        p.setdefault("tree_method", "hist")
        p.setdefault("device", "cuda" if torch.cuda.is_available() and not fast_cfg else "cpu")
        return p

    if m == "catboost":
        import torch

        p.setdefault("iterations", 30 if fast_cfg else 3000)
        p.setdefault("early_stopping_rounds", 5 if fast_cfg else 50)
        p.setdefault("task_type", "GPU" if torch.cuda.is_available() and not fast_cfg else "CPU")
        return p

    if m == "mlp":
        arch_key = str(p.pop("arch", "64"))
        p["hidden_layers"] = HIDDEN_ARCH_MAP.get(arch_key, (64,))
        p.setdefault("max_epochs", 15 if fast_cfg else 200)
        p.setdefault("patience", 3 if fast_cfg else 10)
        return p

    return p


def stratified_fold_subsample(df: pd.DataFrame, frac: float, seed: int) -> pd.DataFrame:
    """Subamostra estratificada por `(regiao, y)` mantendo a mesma prevalência (T-4.3, R3)."""
    if frac >= 1.0:
        return df
    rng = np.random.default_rng(int(seed))
    chosen_indices: list[np.ndarray] = []
    for (_, _), group in df.groupby(["regiao", "y"], observed=False):
        idx = group.index.to_numpy()
        if len(idx) == 0:
            continue
        k = max(1, int(round(len(idx) * float(frac))))
        picked = rng.choice(idx, size=min(k, len(idx)), replace=False)
        chosen_indices.append(picked)
    all_idx = np.concatenate(chosen_indices)
    all_idx.sort()
    return df.loc[all_idx].reset_index(drop=True)


def tune(
    cfg: dict[str, Any],
    modelo: str,
    df: pd.DataFrame,
    *,
    fold_df: pd.DataFrame | None = None,
    n_trials_override: int | None = None,
) -> dict[str, Any]:
    """Executa busca retomável com Optuna em SQLite, cronometragem e registro MLflow (T-4.3)."""
    assert_dev_only(df)
    m = modelo.strip().lower()
    seed = int(cfg.get("seed", 20261103))
    feat = build_feature_frame(df) if "n_comorbidades" not in df.columns else df

    if m == "tabfm":
        return {
            "modelo": m,
            "best_params": {},
            "best_value": 0.0,
            "n_concluidas": 0,
            "n_podadas": 0,
            "tempo_cronometragem_s": 0.0,
            "orcamento_s": 0.0,
            "tempo_gasto_s": 0.0,
            "subamostra_frac": 1.0,
            "db_path": None,
        }

    opt_cfg = cfg.get("optuna", {})
    piso_s = float(opt_cfg.get("piso_min", 10)) * 60.0
    teto_map = opt_cfg.get("teto_por_modelo_min", {})
    teto_s = float(teto_map.get(m, 30)) * 60.0
    max_map = opt_cfg.get("max_tentativas", {})
    target_trials = (
        int(n_trials_override)
        if n_trials_override is not None
        else int(max_map.get(m, 20))
    )

    n_startup = int(opt_cfg.get("poda_tentativas_iniciais", 5))
    n_warmup = int(opt_cfg.get("poda_dobras_aquecimento", 2))

    optuna_dir = Path(cfg.get("caminhos", {}).get("optuna", "optuna")).resolve()
    optuna_dir.mkdir(parents=True, exist_ok=True)
    db_path = optuna_dir / f"{m}.db"
    storage_url = f"sqlite:///{db_path.as_posix()}"

    sampler = TPESampler(seed=seed)
    pruner = MedianPruner(n_startup_trials=n_startup, n_warmup_steps=n_warmup)
    study = optuna.create_study(
        direction="maximize",
        sampler=sampler,
        pruner=pruner,
        storage=storage_url,
        study_name=m,
        load_if_exists=True,
    )

    tune_df = feat
    tune_fold_df = fold_df
    subamostra_frac = 1.0

    def _objective(trial: optuna.Trial) -> float:
        params = sample_params(trial, m, cfg)
        res = run_loro(cfg, m, params, tune_df, fold_df=tune_fold_df, trial=trial)
        trial.set_user_attr("melhores_pontos", res["melhores_pontos"])
        trial.set_user_attr("pr_auc_por_dobra", res["pr_auc_por_dobra"])
        return float(res["pr_auc_media"])

    t_start_total = time.perf_counter()
    existing_finished = [
        t for t in study.trials if t.state in (TrialState.COMPLETE, TrialState.PRUNED)
    ]

    # Cronometragem da 1ª tentativa se o estudo estiver vazio (D-53)
    if len(existing_finished) == 0 and target_trials >= 1:
        defaults = default_trial_params(m)
        if defaults:
            study.enqueue_trial(defaults)
        t0 = time.perf_counter()
        study.optimize(_objective, n_trials=1)
        t_first = max(0.01, time.perf_counter() - t0)
        study.set_user_attr("tempo_cronometragem_s", float(t_first))
    else:
        t_first = float(study.user_attrs.get("tempo_cronometragem_s", 1.0))

    orcamento_s = float(max(piso_s, min(teto_s, t_first * target_trials)))
    study.set_user_attr("orcamento_s", orcamento_s)

    # Regra D-53: se 3t > teto, busca em subamostra estratificada pelo alvo de cada dobra
    if 3.0 * t_first > teto_s:
        subamostra_frac = float(max(0.05, min(0.5, teto_s / (3.5 * t_first))))
        tune_df = stratified_fold_subsample(feat, subamostra_frac, seed)
        tune_fold_df = None
        study.set_user_attr("subamostra_frac", subamostra_frac)

    done_now = len(
        [t for t in study.trials if t.state in (TrialState.COMPLETE, TrialState.PRUNED)]
    )
    remaining_trials = max(0, target_trials - done_now)
    elapsed_so_far = time.perf_counter() - t_start_total
    remaining_timeout = max(1.0, orcamento_s - elapsed_so_far)

    if remaining_trials > 0:
        study.optimize(_objective, n_trials=remaining_trials, timeout=remaining_timeout)

    tempo_gasto_s = float(time.perf_counter() - t_start_total)
    completed_trials = [t for t in study.trials if t.state == TrialState.COMPLETE]
    pruned_trials = [t for t in study.trials if t.state == TrialState.PRUNED]

    best_trial = study.best_trial
    best_params = resolve_best_params(best_trial.params, m, cfg)
    best_value = float(best_trial.value or 0.0)

    # Registra no MLflow com alias melhor-validacao apenas na melhor tentativa (FR-22)
    with start_run(
        cfg,
        f"tune-{m}",
        tags={
            "modelo": m,
            "alias": "melhor-validacao",
            "best_trial_number": str(best_trial.number),
        },
    ) as run:
        mlflow.log_params({f"best.{k}": str(v) for k, v in best_params.items()})
        mlflow.log_params(hardware_info())
        mlflow.log_metrics(
            {
                "pr_auc_media_melhor": best_value,
                "tempo_cronometragem_s": t_first,
                "orcamento_s": orcamento_s,
                "tempo_gasto_s": tempo_gasto_s,
                "n_tentativas_concluidas": float(len(completed_trials)),
                "n_tentativas_podadas": float(len(pruned_trials)),
                "subamostra_frac": subamostra_frac,
            }
        )
        run_id = run.info.run_id

    return {
        "modelo": m,
        "best_params": best_params,
        "best_value": best_value,
        "best_trial_number": int(best_trial.number),
        "n_concluidas": len(completed_trials),
        "n_podadas": len(pruned_trials),
        "tempo_cronometragem_s": t_first,
        "orcamento_s": orcamento_s,
        "tempo_gasto_s": tempo_gasto_s,
        "subamostra_frac": subamostra_frac,
        "db_path": db_path,
        "mlflow_run_id": run_id,
    }
