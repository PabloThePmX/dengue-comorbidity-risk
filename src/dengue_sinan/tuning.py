"""Busca retomável de hiperparâmetros com Optuna e orçamento por modelo."""

import time
from collections.abc import Mapping
from pathlib import Path

import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler

from dengue_sinan.cv import run_loro
from dengue_sinan.tracking import start_run

_MODELS = {"elastic_net", "random_forest", "xgboost", "catboost", "mlp"}


def _suggest_params(trial: optuna.Trial, modelo: str) -> dict:
    if modelo == "elastic_net":
        return {
            "C": trial.suggest_float("C", 1e-3, 10, log=True),
            "l1_ratio": trial.suggest_float("l1_ratio", 0, 1),
        }
    if modelo == "random_forest":
        return {
            "n_estimators": trial.suggest_int("n_estimators", 200, 800),
            "max_depth": trial.suggest_categorical(
                "max_depth", [None, *range(4, 21)]
            ),
            "min_samples_leaf": trial.suggest_int("min_samples_leaf", 10, 500, log=True),
            "max_features": trial.suggest_categorical("max_features", ["sqrt", 0.3, 0.5]),
            "max_samples": trial.suggest_float("max_samples", 0.05, 0.3),
        }
    if modelo == "xgboost":
        return {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 10),
            "min_child_weight": trial.suggest_float("min_child_weight", 1, 100, log=True),
            "subsample": trial.suggest_float("subsample", 0.5, 1),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1),
            "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 200, 2000),
        }
    if modelo == "catboost":
        return {
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "depth": trial.suggest_int("depth", 4, 10),
            "l2_leaf_reg": trial.suggest_float("l2_leaf_reg", 1, 30, log=True),
            "iterations": trial.suggest_int("iterations", 300, 3000),
        }
    if modelo == "mlp":
        shape = trial.suggest_categorical("hidden_layer_sizes", ["64", "128", "128,64"])
        return {
            "hidden_layer_sizes": tuple(int(width) for width in shape.split(",")),
            "dropout": trial.suggest_float("dropout", 0, 0.3),
            "weight_decay": trial.suggest_float("weight_decay", 1e-6, 1e-2, log=True),
            "learning_rate": trial.suggest_float("learning_rate", 1e-4, 1e-2, log=True),
            "batch_size": trial.suggest_categorical("batch_size", [1024, 4096]),
            "max_epochs": 200,
            "patience": 10,
        }
    raise ValueError(f"Modelo sem espaço de busca aprovado: {modelo}")


def _default_params(modelo: str) -> dict:
    defaults = {
        "elastic_net": {"C": 1.0, "l1_ratio": 0.5},
        "random_forest": {
            "n_estimators": 400,
            "max_depth": 10,
            "min_samples_leaf": 50,
            "max_features": "sqrt",
            "max_samples": 0.1,
        },
        "xgboost": {
            "learning_rate": 0.05,
            "max_depth": 5,
            "min_child_weight": 1.0,
            "subsample": 0.8,
            "colsample_bytree": 0.8,
            "reg_lambda": 1.0,
            "n_estimators": 500,
        },
        "catboost": {
            "learning_rate": 0.05,
            "depth": 6,
            "l2_leaf_reg": 3.0,
            "iterations": 800,
        },
        "mlp": {
            "hidden_layer_sizes": "128",
            "dropout": 0.1,
            "weight_decay": 1e-4,
            "learning_rate": 1e-3,
            "batch_size": 1024,
        },
    }
    values = defaults[modelo].copy()
    if modelo == "mlp":
        values.update({"max_epochs": 200, "patience": 10})
    return values


def _config(cfg: dict | str | Path) -> dict:
    if isinstance(cfg, Mapping):
        return dict(cfg)
    from dengue_sinan.config import load_config

    return load_config(cfg)


def tune(
    cfg: dict | str | Path,
    modelo: str,
    df,
    *,
    n_trials: int | None = None,
    log_mlflow: bool = True,
    fold_assignments: list | None = None,
) -> dict:
    """Executa ou retoma a busca; o SQLite fica em armazenamento persistente."""
    if modelo not in _MODELS:
        raise ValueError(f"Modelo desconhecido ou bloqueado: {modelo}")
    config = _config(cfg)
    model_config = config["optuna"]
    trial_limit = int(n_trials or model_config["max_tentativas"][modelo])
    seed = int(config["seed"])
    optuna_dir = Path(config["caminhos"]["mlruns"]) / "optuna"
    optuna_dir.mkdir(parents=True, exist_ok=True)
    database = (optuna_dir / f"{modelo}.db").resolve().as_posix()
    study = optuna.create_study(
        direction="maximize",
        sampler=TPESampler(seed=seed),
        pruner=MedianPruner(
            n_startup_trials=int(model_config.get("poda_tentativas_iniciais", 5)),
            n_warmup_steps=int(model_config.get("poda_dobras_aquecimento", 2)),
        ),
        storage=f"sqlite:///{database}",
        study_name=modelo,
        load_if_exists=True,
    )

    initial_trial_count = len(study.trials)
    started = time.perf_counter()

    def objective(trial, sample_limit=None):
        options = {
            "trial": trial,
            "sample_limit": sample_limit,
        }
        if fold_assignments is not None:
            options["fold_assignments"] = fold_assignments
        return run_loro(
            config,
            modelo,
            _suggest_params(trial, modelo),
            df,
            **options,
        )["mean_pr_auc"]

    if not study.trials:
        study.enqueue_trial(_default_params(modelo))
        study.optimize(lambda trial: objective(trial), n_trials=1)
    completed = [trial for trial in study.trials if trial.value is not None]
    if not completed:
        raise RuntimeError(f"A busca de {modelo} não concluiu nenhuma tentativa utilizável.")
    benchmark_seconds = max(completed[0].duration.total_seconds(), 1.0)
    time_spent = time.perf_counter() - started

    ceiling = int(config["orcamento_teto_min"][modelo]) * 60
    floor = int(config["orcamento_piso_min"]) * 60
    budget = max(floor, min(ceiling, benchmark_seconds * trial_limit))
    sample_limit = None
    if benchmark_seconds * 3 > ceiling:
        sample_limit = max(1000, int(len(df) * ceiling / (3 * benchmark_seconds)))

    added_trials = len(study.trials) - initial_trial_count
    remaining = max(0, trial_limit - added_trials)
    remaining_seconds = max(1.0, budget - time_spent)
    if remaining:
        study.optimize(
            lambda trial: objective(trial, sample_limit),
            n_trials=remaining,
            timeout=remaining_seconds,
        )

    time_spent = time.perf_counter() - started
    completed = [trial for trial in study.trials if trial.value is not None]
    if not completed:
        raise RuntimeError(f"A busca de {modelo} não concluiu nenhuma tentativa utilizável.")
    best = study.best_trial
    best_params = dict(best.params)
    if modelo == "mlp":
        best_params["hidden_layer_sizes"] = tuple(
            int(width) for width in best_params["hidden_layer_sizes"].split(",")
        )
        best_params.update({"max_epochs": 200, "patience": 10})
    if log_mlflow:
        import mlflow

        with start_run(config, f"tuning-{modelo}", include_hardware=False):
            mlflow.log_params({"modelo": modelo, "study": modelo})
            mlflow.log_metrics(
                {
                    "tempo_busca_segundos": float(time_spent),
                    "tempo_benchmark_segundos": float(benchmark_seconds),
                    "orcamento_segundos": float(budget),
                    "tentativas_concluidas": len(completed),
                    "tentativas_podadas": sum(
                        trial.state == optuna.trial.TrialState.PRUNED for trial in study.trials
                    ),
                    "pr_auc_melhor": float(best.value),
                    "limite_subamostra": int(sample_limit or len(df)),
                }
            )
            mlflow.log_dict(best_params, "melhores_parametros.json")
    return {
        "modelo": modelo,
        "best_params": best_params,
        "best_value": float(best.value),
        "study_name": modelo,
        "n_trials": len(study.trials),
        "n_completed": len(completed),
        "n_pruned": sum(
            trial.state == optuna.trial.TrialState.PRUNED for trial in study.trials
        ),
        "benchmark_seconds": float(benchmark_seconds),
        "budget_seconds": float(budget),
        "sample_limit": sample_limit,
        "database": database,
    }
