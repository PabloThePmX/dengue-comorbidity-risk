"""Busca de hiperparâmetros Optuna, retomável em SQLite."""

import json
import time
from pathlib import Path

import mlflow
import optuna
import pandas as pd
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler

from dengue_sinan.cv import run_loro
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.tracking import (
    log_fold_metrics,
    log_oof_predictions,
    start_run,
)


def _suggest_params(trial: optuna.Trial, model: str) -> dict:
    if model == "elastic_net":
        return {
            "C": trial.suggest_float("C", 1e-3, 10, log=True),
            "l1_ratio": trial.suggest_float("l1_ratio", 0, 1),
        }
    if model == "random_forest":
        return {
            "n_estimators": trial.suggest_int("n_estimators", 200, 800),
            "max_depth": trial.suggest_categorical("max_depth", [None, *range(4, 21)]),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 10, 500, log=True),
            "max_features": trial.suggest_categorical("max_features", ["sqrt", 0.3, 0.5]),
        }
    if model == "xgboost":
        return {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "min_child_weight": trial.suggest_float("min_child_weight", 1, 100, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 200, 2000),
        }
    if model == "catboost":
        return {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "depth": trial.suggest_int("depth", 4, 10),
            "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1, 30, log=True),
            "iterations": trial.suggest_int("iterations", 200, 3000),
        }
    if model == "mlp":
        layers = trial.suggest_categorical("hidden_layers", ["64", "128", "128_64"])
        return {
            "hidden_layers": tuple(map(int, layers.split("_"))),
            "dropout": trial.suggest_float("dropout", 0, 0.3),
            "weight_decay": trial.suggest_float("weight_decay", 1e-6, 1e-2, log=True),
            "lr": trial.suggest_float("lr", 1e-4, 1e-2, log=True),
            "batch_size": trial.suggest_categorical("batch_size", [1024, 4096]),
            "epochs": 200,
        }
    if model == "tabfm":
        raise RuntimeError(
            "TabFM bloqueado até aprovação das verificações de model card da T-4.7."
        )
    raise ValueError(f"modelo desconhecido: {model}")


def tune(cfg: dict, modelo: str, df):
    """Otimiza PR-AUC média LORO, com estudo retomável e orçamento por modelo."""
    assert_dev_only(df, int(cfg.get("ano_teste", 2024)))
    if modelo == "tabfm":
        raise RuntimeError(
            "TabFM bloqueado até aprovação das verificações de model card da T-4.7."
        )
    budgets = cfg["orcamento_min"]
    if modelo not in budgets:
        raise ValueError(f"orcamento_min não define o modelo {modelo}")
    base = Path(cfg["caminhos"]["mlruns"]).parent / "optuna"
    base.mkdir(parents=True, exist_ok=True)
    database = base / f"{modelo}.db"
    storage = f"sqlite:///{database.as_posix()}"
    study = optuna.create_study(
        direction="maximize",
        sampler=TPESampler(seed=int(cfg["seed"])),
        pruner=MedianPruner(),
        storage=storage,
        study_name=modelo,
        load_if_exists=True,
    )
    started = time.monotonic()
    timeout = int(budgets[modelo]) * 60
    with start_run(cfg, f"tuning-{modelo}", {"modelo": modelo}):
        def objective(trial: optuna.Trial) -> float:
            params = _suggest_params(trial, modelo)
            result = run_loro(cfg, modelo, params, df, trial=trial)
            trial.set_user_attr("best_points", result["best_points"])
            return result["mean_pr_auc"]

        study.optimize(
            objective,
            n_trials=int(cfg.get("optuna", {}).get("max_tentativas", 50)),
            timeout=timeout,
        )
        completed = [trial for trial in study.trials
                     if trial.state == optuna.trial.TrialState.COMPLETE]
        if not completed:
            raise RuntimeError(
                f"nenhuma tentativa completa para {modelo}; revise o erro e o orçamento "
                "antes de continuar"
            )
        best = study.best_trial
        best_params = dict(best.params)
        if modelo == "mlp":
            best_params["hidden_layers"] = tuple(
                map(int, best_params["hidden_layers"].split("_"))
            )
        selected_result = run_loro(cfg, modelo, best_params, df)
        for row in selected_result["fold_metrics"].to_dict(orient="records"):
            region = row.pop("regiao")
            log_fold_metrics(region, row)
        oof_path = log_oof_predictions(
            cfg,
            modelo,
            df["y"],
            pd.Series(selected_result["oof"], index=df.index),
            df["regiao"],
        )
        mlflow.set_tag("alias", "melhor-validacao")
        for region, point in selected_result["best_points"].items():
            if point is not None:
                mlflow.log_param(f"best_point.{region}", point)
        mlflow.log_params({f"best.{key}": str(value) for key, value in best.params.items()})
        mlflow.log_metrics({
            "best_pr_auc": selected_result["mean_pr_auc"],
            "tempo_segundos": time.monotonic() - started,
            "tentativas_concluidas": len(completed),
            "tentativas_podadas": sum(
                trial.state == optuna.trial.TrialState.PRUNED for trial in study.trials
            ),
        })
        best_config = {
            "modelo": modelo,
            "params": best_params,
            "mean_pr_auc": selected_result["mean_pr_auc"],
            "oof_metrics": selected_result["oof_metrics"],
            "fold_metrics": selected_result["fold_metrics"].to_dict(orient="records"),
            "best_points": selected_result["best_points"],
            "study": str(database),
            "oof_artifact": str(oof_path),
        }
        config_path = base / f"{modelo}_melhor_validacao.json"
        config_path.write_text(json.dumps(best_config, indent=2), encoding="utf-8")
        mlflow.log_artifact(str(config_path), artifact_path="modelos")
    return best_config
