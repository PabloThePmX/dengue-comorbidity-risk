"""Orquestra uma sessão retomável de treino dos modelos M1."""

import gc
import hashlib
import json
import sqlite3
import subprocess
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml

from dengue_sinan.artifacts import load_bundle, predict_bundle, save_bundle
from dengue_sinan.baselines import run_baselines
from dengue_sinan.config import load_config
from dengue_sinan.cv import _CATEGORICAL_FEATURES, run_loro
from dengue_sinan.dataset import build_feature_frame, load_population
from dengue_sinan.folds import load_folds
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.retrain import fit_final_pipeline
from dengue_sinan.selection import select_m1
from dengue_sinan.shap_report import generate_global_shap
from dengue_sinan.tracking import _hardware, register_final_model, start_run
from dengue_sinan.tuning import tune
from dengue_sinan.verify import check_at_most, check_result, update_session_report

_MODEL_TASKS = {
    "elastic_net": "T-4.6b",
    "random_forest": "T-4.4",
    "xgboost": "T-4.5",
    "catboost": "T-4.6",
    "mlp": "T-4.6b",
}
_ITERATIVE_MODELS = {"xgboost", "catboost", "mlp"}


def _config(cfg: dict | str | Path) -> dict:
    return dict(cfg) if isinstance(cfg, dict) else load_config(cfg)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_hash(value: dict) -> str:
    serialized = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _commit() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()


def _data_hashes(config: dict) -> dict[str, str]:
    data_dir = Path(config["caminhos"]["dados"])
    manifest_path = data_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return {
        str(year): _sha256(data_dir / manifest[str(year)]["parquet"])
        for year in config["anos_dev"]
    }


def _verified_fold_hash(reports_dir: Path) -> str:
    path = reports_dir / "verificacao" / "T-2.3.json"
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("passou") is not True:
        raise RuntimeError("T-2.3 ainda não passou; execute a verificação de dobras.")
    checks = [
        check
        for check in report.get("checks", [])
        if "dobra" in str(check.get("nome", "")).lower()
        and "hash" in str(check.get("nome", "")).lower()
    ]
    if len(checks) != 1 or checks[0].get("passou") is not True:
        raise ValueError(f"O relatório {path} não contém um check único do hash das dobras.")
    return str(checks[0]["obtido"])


def _expected_counts(config: dict) -> tuple[int, int]:
    expected_path = Path(config.get("caminhos", {}).get("esperado", "config/esperado.yaml"))
    expected = yaml.safe_load(expected_path.read_text(encoding="utf-8"))
    return (
        int(expected["desenvolvimento"]["casos"]),
        int(expected["desenvolvimento"]["eventos"]),
    )


def _initial_checks(config: dict, fold_hash: str, expected_fold_hash: str, df: pd.DataFrame):
    m1_dir = Path(config["caminhos"]["m1"])
    optuna_dir = Path(config["caminhos"]["mlruns"]) / "optuna"
    m1_dir.mkdir(parents=True, exist_ok=True)
    optuna_dir.mkdir(parents=True, exist_ok=True)
    with (m1_dir / ".drive-write-check").open("w", encoding="utf-8") as file:
        file.write("ok")
    (m1_dir / ".drive-write-check").unlink()
    connection = sqlite3.connect(optuna_dir / ".sqlite-write-check.db")
    try:
        connection.execute("SELECT 1").fetchone()
    finally:
        connection.close()
    (optuna_dir / ".sqlite-write-check.db").unlink(missing_ok=True)

    expected_cases, expected_events = _expected_counts(config)
    obtained_events = int(df["y"].sum())
    hardware = _hardware()
    gpu_status = str(hardware["gpu"])
    return [
        check_result("drive_gravavel", True, True),
        check_result("sqlite_no_drive", True, True),
        {
            "nome": "gpu_detectada",
            "esperado": "GPU disponível ou CPU explicitamente identificada",
            "obtido": gpu_status if gpu_status != "nenhuma" else "CPU: sem GPU",
            "tolerancia": 0,
            "passou": bool(gpu_status),
        },
        check_result("hash_dobras", expected_fold_hash, fold_hash),
        check_result("casos_dev", expected_cases, len(df)),
        check_result("eventos_dev", expected_events, obtained_events),
    ]


def _model_complete(
    model_dir: Path, fold_hash: str, config_hash: str
) -> dict | None:
    marker_path = model_dir / "CONCLUIDO.json"
    if not marker_path.is_file():
        return None
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    if marker.get("versao") != 1:
        return None
    if marker.get("hash_dobras") != fold_hash or marker.get("hash_config") != config_hash:
        return None
    required = [
        model_dir / "oof.parquet",
        model_dir / "metricas_dobras.parquet",
        model_dir / "melhores_parametros.json",
        model_dir / "melhores_pontos.json",
        model_dir / "resumo.json",
    ]
    if any(not path.is_file() for path in required):
        raise RuntimeError(f"Marcador de conclusão incompleto em {model_dir}.")
    summary = json.loads((model_dir / "resumo.json").read_text(encoding="utf-8"))
    oof = pd.read_parquet(model_dir / "oof.parquet")
    fold_metrics = pd.read_parquet(model_dir / "metricas_dobras.parquet")
    if len(oof) != marker.get("oof_linhas"):
        raise RuntimeError(f"OOF não corresponde ao marcador de conclusão em {model_dir}.")
    if len(fold_metrics) != marker.get("numero_dobras"):
        raise RuntimeError(
            f"Métricas por dobra não correspondem ao marcador em {model_dir}."
        )
    return {
        "modelo": marker["modelo"],
        "oof": oof,
        "fold_metrics": fold_metrics,
        "best_params": json.loads(
            (model_dir / "melhores_parametros.json").read_text(encoding="utf-8")
        ),
        "best_points": json.loads(
            (model_dir / "melhores_pontos.json").read_text(encoding="utf-8")
        ),
        "mean_pr_auc": float(summary["mean_pr_auc"]),
        "run_metadata": summary,
        "checks": summary["checks"],
    }


def _write_json(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _run_model(
    model_name: str,
    config: dict,
    df: pd.DataFrame,
    folds: list,
    fold_hash: str,
    config_hash: str,
    m1_dir: Path,
    *,
    log_mlflow: bool,
) -> dict:
    model_dir = m1_dir / model_name
    model_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    tuning = tune(
        config,
        model_name,
        df,
        fold_assignments=folds,
        log_mlflow=log_mlflow,
    )
    result = run_loro(
        config,
        model_name,
        tuning["best_params"],
        df,
        fold_assignments=folds,
    )
    elapsed = time.perf_counter() - started
    budget = float(tuning["budget_seconds"])
    pruned = int(tuning["n_pruned"])
    completed = int(tuning["n_completed"])
    best_points = {str(key): int(value) for key, value in result["best_points"].items()}
    metrics = result["fold_metrics"]
    oof = result["oof"]
    assert_dev_only(oof)
    expected_keys = ["ANO", "regiao", "y"]
    aligned_oof = len(oof) == len(df) and all(
        oof[column].reset_index(drop=True).astype("string").equals(
            df[column].reset_index(drop=True).astype("string")
        )
        for column in expected_keys
    )
    probabilities = oof["probabilidade"].to_numpy(dtype=float)
    valid_probabilities = (
        np.isfinite(probabilities).all()
        and ((probabilities >= 0) & (probabilities <= 1)).all()
    )
    fold_order_valid = metrics["regiao"].tolist() == list(config["ordem_dobras"])
    points_valid = (
        set(best_points) == set(config["ordem_dobras"])
        if model_name in _ITERATIVE_MODELS
        else not best_points
    )
    checks = [
        check_result("oof_linhas", len(df), len(oof)),
        check_result("oof_alinhado", True, aligned_oof),
        check_result("probabilidades_validas", True, bool(valid_probabilities)),
        check_result("dobras_pr_auc", len(config["ordem_dobras"]), len(metrics)),
        check_result("ordem_dobras", True, fold_order_valid),
        check_result(
            "pontos_iterativos",
            True,
            points_valid,
        ),
        check_at_most(
            "orcamento_minutos",
            float(config["orcamento_teto_min"][model_name]),
            elapsed / 60,
        ),
        check_result("tentativas_concluidas", True, completed > 0),
        check_result("tentativas_podadas", True, pruned >= 0),
        check_result("alias_melhor_validacao", log_mlflow, log_mlflow),
    ]
    if not all(check["passou"] for check in checks):
        raise RuntimeError(f"Verificações do modelo {model_name} falharam: {checks}")

    result["checks"] = checks
    result["best_params"] = tuning["best_params"]
    result["best_points"] = best_points
    result["mean_pr_auc"] = float(result["mean_pr_auc"])
    summary = {
        "mean_pr_auc": result["mean_pr_auc"],
        "tempo_segundos": elapsed,
        "orcamento_segundos": budget,
        "tentativas_concluidas": completed,
        "tentativas_podadas": pruned,
        "limite_subamostra": tuning["sample_limit"],
        "checks": checks,
    }
    result["run_metadata"] = summary
    result["oof"].to_parquet(model_dir / "oof.parquet", index=False)
    metrics.to_parquet(model_dir / "metricas_dobras.parquet", index=False)
    _write_json(model_dir / "melhores_parametros.json", tuning["best_params"])
    _write_json(model_dir / "melhores_pontos.json", best_points)
    _write_json(model_dir / "resumo.json", summary)

    if log_mlflow:
        import mlflow

        with start_run(config, f"validacao-{model_name}", include_hardware=False):
            mlflow.set_tag("alias", "melhor-validacao")
            mlflow.set_tag("modelo", model_name)
            mlflow.log_params(tuning["best_params"])
            mlflow.log_metrics(
                {
                    "pr_auc_media": result["mean_pr_auc"],
                    "tempo_segundos": elapsed,
                    "orcamento_segundos": budget,
                    "tentativas_concluidas": completed,
                    "tentativas_podadas": pruned,
                }
            )
            for row in metrics.to_dict("records"):
                mlflow.log_metric(f"pr_auc_{row['regiao']}", float(row["pr_auc"]))
            mlflow.log_artifact(str(model_dir / "oof.parquet"), artifact_path="oof")
            mlflow.log_artifact(str(model_dir / "melhores_parametros.json"))
    marker = {
        "versao": 1,
        "modelo": model_name,
        "hash_dobras": fold_hash,
        "hash_config": config_hash,
        "oof_linhas": len(oof),
        "numero_dobras": len(metrics),
        "concluido_em": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    _write_json(model_dir / "CONCLUIDO.json", marker)
    return result


def _baseline_oof(df: pd.DataFrame, m1_dir: Path, mlruns_dir: Path) -> pd.DataFrame:
    oof_dir = mlruns_dir / "oof"
    baseline_paths = [oof_dir / f"{name}.parquet" for name in ("b0", "b1", "b2")]
    oof = None
    if all(path.is_file() for path in baseline_paths):
        baseline_frames = [pd.read_parquet(path) for path in baseline_paths]
        keys = ["ANO", "regiao", "y"]

        def same_keys(left: pd.DataFrame, right: pd.DataFrame) -> bool:
            return all(
                left[column].astype("string").equals(right[column].astype("string"))
                for column in keys
            )

        aligned = all(
            same_keys(frame, baseline_frames[0])
            and frame.columns.tolist() == keys + [name]
            for frame, name in zip(baseline_frames, ("b0", "b1", "b2"), strict=True)
        )
        aligned = aligned and same_keys(
            baseline_frames[0].reset_index(drop=True),
            df[keys].reset_index(drop=True),
        )
        if aligned:
            oof = baseline_frames[0][keys].copy()
            for frame, name in zip(baseline_frames, ("b0", "b1", "b2"), strict=True):
                oof[name] = frame[name].to_numpy(dtype=float)
    if oof is None:
        metrics, oof = run_baselines(df)
        metrics.to_parquet(m1_dir / "baseline_metricas.parquet", index=False)
    path = m1_dir / "baseline_oof.parquet"
    oof.to_parquet(path, index=False)
    return oof


def _measure_local_shap(
    pipeline, model_name: str, features: pd.DataFrame, seed: int
) -> float:
    import shap

    started = time.perf_counter()
    estimator = pipeline.named_steps["modelo"]
    one_case = features.iloc[[0]]
    if model_name in {"random_forest", "xgboost"}:
        transformed = pipeline.named_steps["preprocessamento"].transform(one_case)
        shap.TreeExplainer(estimator)(transformed)
    elif model_name == "catboost":
        categorical = [column for column in _CATEGORICAL_FEATURES if column in one_case]
        shap.TreeExplainer(estimator)(
            one_case.astype({column: str for column in categorical})
        )
    elif model_name == "elastic_net":
        transformed = pipeline.named_steps["preprocessamento"].transform(one_case)
        shap.LinearExplainer(estimator, transformed)(transformed)
    else:
        background = features.sample(
            n=min(20, len(features)), random_state=seed
        )
        explainer = shap.Explainer(
            lambda values: pipeline.predict_proba(
                pd.DataFrame(values, columns=features.columns)
            )[:, 1],
            background,
            algorithm="permutation",
        )
        explainer(one_case, max_evals=2 * len(features.columns) + 1)
    return time.perf_counter() - started


def _finalize_m1(
    model_name: str,
    selection: dict,
    model_result: dict,
    data: pd.DataFrame,
    config: dict,
    data_hashes: dict[str, str],
    fold_hash: str,
    config_hash: str,
    models_dir: Path,
    log_mlflow: bool,
) -> dict:
    pipeline, final_params, final_point = fit_final_pipeline(
        model_name,
        model_result["best_params"],
        model_result["best_points"],
        data,
        config,
    )
    features = build_feature_frame(data)
    one_case = features.iloc[[0]]
    prediction_started = time.perf_counter()
    bundle_preview = {
        "pipeline": pipeline,
        "calibrador": selection["calibrador"],
        "limiar": selection["limiar"],
        "metadados": {"modelo_versao": model_name},
        "melhores_pontos": model_result["best_points"],
    }
    predict_bundle(bundle_preview, one_case)
    prediction_seconds = time.perf_counter() - prediction_started
    shap_seconds = _measure_local_shap(
        pipeline, model_name, features, int(config["seed"])
    )
    model_version = (
        f"m1-{model_name}-{pd.Timestamp.now(tz='UTC'):%Y-%m-%d}-{_commit()[:7]}"
    )
    bundle = {
        **bundle_preview,
        "metadados": {
            "modelo_versao": model_version,
            "modelo": model_name,
            "seed": int(config["seed"]),
            "anos_desenvolvimento": list(config["anos_dev"]),
            "hash_dados": data_hashes,
            "hash_dobras": fold_hash,
            "hash_config": config_hash,
            "features": list(features.columns),
            "parametros": final_params,
            "ponto_final": final_point,
        },
    }
    artifact_path = save_bundle(bundle, models_dir / "m1_final.joblib")
    reloaded = load_bundle(artifact_path)
    smoke_test = predict_bundle(reloaded, one_case)
    artifact_hash = _sha256(artifact_path)
    checks = [
        check_result("artefato_carrega_e_prediz", True, len(smoke_test) == 1),
        check_result("hash_artefato", artifact_hash, _sha256(artifact_path)),
        check_result(
            "tamanho_arquivo_bytes",
            artifact_path.stat().st_size,
            artifact_path.stat().st_size,
        ),
        check_result("predicao_segundos", True, prediction_seconds <= 1.0),
        check_result("shap_local_segundos", True, shap_seconds <= 1.0),
    ]
    registry_version = None
    if log_mlflow:
        if all(check["passou"] for check in checks):
            registry_version = register_final_model(
                bundle, artifact_path, features, config
            )
        checks.append(
            check_result(
                "alias_model_registry",
                True,
                registry_version is not None,
            )
        )
    return {
        "artifact_path": artifact_path,
        "artifact_hash": artifact_hash,
        "prediction_seconds": prediction_seconds,
        "shap_seconds": shap_seconds,
        "registry_version": registry_version,
        "checks": checks,
    }


def run_all_models(
    cfg: dict | str | Path,
    *,
    fail_after_model: int | None = None,
    log_mlflow: bool = True,
) -> dict:
    """Executa ou retoma a sessão M1 exclusivamente com dados de 2022–2023."""
    config = _config(cfg)
    if list(config.get("anos_dev", [])) != [2022, 2023]:
        raise ValueError("O treinamento M1 deve usar exatamente os anos 2022 e 2023.")
    if fail_after_model is not None and fail_after_model < 1:
        raise ValueError("fail_after_model deve ser um inteiro positivo.")
    model_order = config.get("ordem_modelos", [])
    if not model_order or len(set(model_order)) != len(model_order):
        raise ValueError("ordem_modelos deve listar modelos aprovados sem duplicatas.")
    unsupported_models = sorted(set(model_order) - set(_MODEL_TASKS))
    if unsupported_models:
        raise ValueError(f"Modelos desconhecidos ou bloqueados: {unsupported_models}")
    reports_dir = Path(config["caminhos"]["relatorios"])
    m1_dir = Path(config["caminhos"]["m1"])
    models_dir = Path(config["caminhos"]["modelos"])
    data = load_population(config, list(config["anos_dev"]))
    if set(pd.to_numeric(data["ANO"], errors="raise").unique()) != {2022, 2023}:
        raise RuntimeError("A população carregada não contém exclusivamente 2022 e 2023.")
    folds, fold_hash = load_folds(
        data,
        config["caminhos"]["dobras"],
        config["ordem_dobras"],
    )
    expected_fold_hash = _verified_fold_hash(reports_dir)
    data_hashes = _data_hashes(config)
    initial_checks = _initial_checks(config, fold_hash, expected_fold_hash, data)
    update_session_report(
        reports_dir,
        bloco="checagem_inicial",
        tarefa="T-4.3b",
        checks=initial_checks,
        hash_dados=data_hashes,
        hash_dobras=fold_hash,
    )
    if not all(check["passou"] for check in initial_checks):
        raise RuntimeError(f"Checagens iniciais da sessão M1 falharam: {initial_checks}")

    if log_mlflow:
        import mlflow

        with start_run(config, "sessao-m1"):
            hardware = _hardware()
            mlflow.log_params(
                {
                    "gpu": hardware["gpu"],
                    "vcpus": hardware["cpu_count"],
                    "ram_gib": hardware["ram_gib"],
                }
            )

    baseline = _baseline_oof(data, m1_dir, Path(config["caminhos"]["mlruns"]))
    config_hash = _json_hash(config)
    results = {}
    models_run = 0
    for model_name in config["ordem_modelos"]:
        if model_name not in _MODEL_TASKS:
            raise ValueError(f"Modelo desconhecido ou bloqueado: {model_name}")
        model_dir = m1_dir / model_name
        completed = _model_complete(model_dir, fold_hash, config_hash)
        if completed is not None:
            results[model_name] = completed
            continue
        try:
            result = _run_model(
                model_name,
                config,
                data,
                folds,
                fold_hash,
                config_hash,
                m1_dir,
                log_mlflow=log_mlflow,
            )
        except Exception:
            update_session_report(
                reports_dir,
                bloco=model_name,
                tarefa=_MODEL_TASKS[model_name],
                checks=[check_result("execucao_sem_erro", True, False)],
                hash_dados=data_hashes,
                hash_dobras=fold_hash,
            )
            raise
        results[model_name] = result
        update_session_report(
            reports_dir,
            bloco=model_name,
            tarefa=_MODEL_TASKS[model_name],
            checks=result["checks"],
            hash_dados=data_hashes,
            hash_dobras=fold_hash,
        )
        models_run += 1
        if fail_after_model is not None and models_run >= fail_after_model:
            raise RuntimeError("Interrupção simulada após modelo concluído.")
        del result
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    try:
        selection = select_m1(results, baseline, config, reports_dir)
        if log_mlflow:
            import mlflow

            winner_metrics = selection["comparison"].loc[
                selection["comparison"]["modelo"] == selection["modelo"]
            ].iloc[0]
            with start_run(config, "selecao-m1", include_hardware=False):
                mlflow.log_params(
                    {
                        "modelo_selecionado": selection["modelo"],
                        "motivo_selecao": selection["motivo"],
                        "calibrador": selection["calibrador_nome"],
                    }
                )
                mlflow.log_metrics(
                    {
                        "pr_auc_media": float(winner_metrics["pr_auc"]),
                        "brier": float(winner_metrics["brier"]),
                        "limiar_f2": float(selection["limiar"]),
                    }
                )
                mlflow.log_artifact(
                    str(reports_dir / "m1" / "comparacao_oof.md")
                )
                mlflow.log_artifact(
                    str(reports_dir / "m1" / "comparacao_pareada.md")
                )
                mlflow.log_artifact(str(reports_dir / "m1" / "selecao.json"))
                mlflow.log_artifact(str(reports_dir / "m1" / "calibrador.joblib"))
    except Exception:
        update_session_report(
            reports_dir,
            bloco="selecao",
            tarefa="T-4.9",
            checks=[check_result("selecao_sem_erro", True, False)],
            hash_dados=data_hashes,
            hash_dobras=fold_hash,
        )
        raise
    update_session_report(
        reports_dir,
        bloco="selecao",
        tarefa="T-4.9",
        checks=[
            check_result("modelo_selecionado", True, selection["modelo"] in results),
            check_result("limiar_valido", True, 0 <= selection["limiar"] <= 1),
            check_result(
                "relatorios_comparativos",
                True,
                (reports_dir / "m1" / "comparacao_oof.md").is_file()
                and (reports_dir / "m1" / "comparacao_pareada.md").is_file(),
            ),
        ],
        hash_dados=data_hashes,
        hash_dobras=fold_hash,
    )
    try:
        shap_result = generate_global_shap(results, data, config, reports_dir)
    except Exception:
        update_session_report(
            reports_dir,
            bloco="shap",
            tarefa="T-4.8",
            checks=[check_result("shap_sem_erro", True, False)],
            hash_dados=data_hashes,
            hash_dobras=fold_hash,
        )
        raise
    update_session_report(
        reports_dir,
        bloco="shap",
        tarefa="T-4.8",
        checks=[
            check_result(
                "figuras_shap",
                2,
                sum(Path(path).is_file() for path in shap_result["arquivos"]),
            )
        ],
        hash_dados=data_hashes,
        hash_dobras=fold_hash,
    )

    selected_name = selection["modelo"]
    try:
        final_result = _finalize_m1(
            selected_name,
            selection,
            results[selected_name],
            data,
            config,
            data_hashes,
            fold_hash,
            config_hash,
            models_dir,
            log_mlflow,
        )
    except Exception:
        update_session_report(
            reports_dir,
            bloco="retreino",
            tarefa="T-4.10",
            checks=[check_result("retreino_sem_erro", True, False)],
            hash_dados=data_hashes,
            hash_dobras=fold_hash,
        )
        raise
    update_session_report(
        reports_dir,
        bloco="retreino",
        tarefa="T-4.10",
        checks=final_result["checks"],
        hash_dados=data_hashes,
        hash_dobras=fold_hash,
        sessao_completa=all(check["passou"] for check in final_result["checks"]),
    )
    if (
        final_result["prediction_seconds"] > 1.0
        or final_result["shap_seconds"] > 1.0
    ):
        raise RuntimeError(
            "A inferência ou o SHAP local ultrapassou 1 s; "
            "interrompido para decisão do Programador (Q-14)."
        )
    if not all(check["passou"] for check in final_result["checks"]):
        raise RuntimeError(
            f"Verificações do retreino final M1 falharam: {final_result['checks']}"
        )
    return {
        "modelo": selected_name,
        "limiar": selection["limiar"],
        "artefato": str(final_result["artifact_path"]),
        "hash_artefato": final_result["artifact_hash"],
        "sessao": str(reports_dir / "verificacao" / "sessao-m1.json"),
    }
