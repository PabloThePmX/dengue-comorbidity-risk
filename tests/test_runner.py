import json

import numpy as np
import pandas as pd
import pytest
from test_cv import _development_data

import dengue_sinan.runner as runner
from dengue_sinan.folds import save_folds
from dengue_sinan.verify import check_result


class FixedPipeline:
    def predict_proba(self, features):
        probability = np.full(len(features), 0.8)
        return np.column_stack((1 - probability, probability))


def test_runner_rejects_2024_before_loading_population(monkeypatch):
    def unexpected_load(*args, **kwargs):
        raise AssertionError("Dados não devem ser carregados.")

    monkeypatch.setattr(runner, "load_population", unexpected_load)

    with pytest.raises(ValueError, match="exatamente os anos 2022 e 2023"):
        runner.run_all_models({"anos_dev": [2022, 2024]})


def test_runner_resumes_completed_models_after_simulated_interruption(tmp_path, monkeypatch):
    data = _development_data(rows_per_region=20)
    data.loc[data.index % 2 == 0, "ANO"] = 2023
    reports = tmp_path / "reports"
    m1 = tmp_path / "m1"
    mlruns = tmp_path / "mlruns"
    data_dir = tmp_path / "data"
    (data_dir / "parquet").mkdir(parents=True)
    for year in (2022, 2023):
        (data_dir / "parquet" / f"dengue_{year}.parquet").write_bytes(b"fixture")
    (data_dir / "manifest.json").write_text(
        json.dumps(
            {
                str(year): {"parquet": f"parquet/dengue_{year}.parquet"}
                for year in (2022, 2023)
            }
        ),
        encoding="utf-8",
    )
    order = ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"]
    _, fold_hash = save_folds(data, m1 / "dobras.npz", order)
    verification_dir = reports / "verificacao"
    verification_dir.mkdir(parents=True)
    (verification_dir / "T-2.3.json").write_text(
        json.dumps(
            {
                "passou": True,
                "checks": [check_result("hash_dobras", fold_hash, fold_hash)],
            }
        ),
        encoding="utf-8",
    )
    config = {
        "seed": 17,
        "anos_dev": [2022, 2023],
        "ordem_dobras": order,
        "ordem_modelos": ["elastic_net", "random_forest"],
        "validacao_interna_frac": 0.1,
        "orcamento_teto_min": {"elastic_net": 10, "random_forest": 10},
        "orcamento_piso_min": 1,
        "bootstrap": {"metricas": 5},
        "bootstrap_pareado": 5,
        "optuna": {},
        "caminhos": {
            "dados": str(data_dir),
            "mlruns": str(mlruns),
            "relatorios": str(reports),
            "modelos": str(tmp_path / "models"),
            "m1": str(m1),
            "dobras": str(m1 / "dobras.npz"),
        },
    }

    monkeypatch.setattr(runner, "load_population", lambda cfg, years: data.copy())
    monkeypatch.setattr(runner, "_expected_counts", lambda cfg: (len(data), int(data["y"].sum())))
    baseline = data[["ANO", "regiao", "y"]].copy()
    baseline["b0"] = float(data["y"].mean())
    baseline["b1"] = float(data["y"].mean())
    baseline["b2"] = 0
    monkeypatch.setattr(runner, "run_baselines", lambda df: (pd.DataFrame(), baseline))

    tuning_calls = []

    def fake_tune(cfg, model, df, **kwargs):
        tuning_calls.append(model)
        return {
            "best_params": {"C": 1.0, "l1_ratio": 0.5}
            if model == "elastic_net"
            else {"n_estimators": 20},
            "budget_seconds": 600,
            "n_pruned": 0,
            "n_completed": 1,
            "sample_limit": None,
        }

    def fake_loro(cfg, model, params, df, **kwargs):
        probability = np.where(df["y"].to_numpy() == 1, 0.8, 0.1)
        return {
            "modelo": model,
            "oof": pd.DataFrame(
                {
                    "ANO": df["ANO"].to_numpy(),
                    "regiao": df["regiao"].to_numpy(),
                    "y": df["y"].to_numpy(),
                    "probabilidade": probability,
                }
            ),
            "fold_metrics": pd.DataFrame(
                {
                    "regiao": cfg["ordem_dobras"],
                    "pr_auc": [1.0] * len(cfg["ordem_dobras"]),
                    "brier": [0.1] * len(cfg["ordem_dobras"]),
                }
            ),
            "mean_pr_auc": 1.0,
            "best_points": {},
        }

    monkeypatch.setattr(runner, "tune", fake_tune)
    monkeypatch.setattr(runner, "run_loro", fake_loro)

    def fake_shap(results, df, cfg, report_dir):
        output = tmp_path / "shap"
        output.mkdir(exist_ok=True)
        files = [output / "global.png", output / "interactions.png"]
        for path in files:
            path.write_bytes(b"plot")
        return {"arquivos": [str(path) for path in files]}

    monkeypatch.setattr(runner, "generate_global_shap", fake_shap)
    monkeypatch.setattr(
        runner,
        "fit_final_pipeline",
        lambda *args: (FixedPipeline(), {"params": True}, None),
    )
    monkeypatch.setattr(runner, "_measure_local_shap", lambda *args: 0.1)

    with pytest.raises(RuntimeError, match="Interrupção simulada"):
        runner.run_all_models(config, fail_after_model=1, log_mlflow=False)
    assert tuning_calls == ["elastic_net"]
    assert (m1 / "elastic_net" / "CONCLUIDO.json").is_file()

    result = runner.run_all_models(config, log_mlflow=False)

    assert tuning_calls == ["elastic_net", "random_forest"]
    assert result["modelo"] in {"elastic_net", "random_forest"}
    report = json.loads((verification_dir / "sessao-m1.json").read_text(encoding="utf-8"))
    assert report["sessao_completa"]
    assert {block["bloco"] for block in report["blocos"]} >= {
        "elastic_net",
        "random_forest",
        "selecao",
        "shap",
        "retreino",
    }
    assert report["passou"]

    changed_order = order[::-1]
    _, changed_hash = save_folds(data, m1 / "dobras.npz", changed_order)
    config["ordem_dobras"] = changed_order
    (verification_dir / "T-2.3.json").write_text(
        json.dumps(
            {
                "passou": True,
                "checks": [check_result("hash_dobras", changed_hash, changed_hash)],
            }
        ),
        encoding="utf-8",
    )
    runner.run_all_models(config, log_mlflow=False)

    assert tuning_calls == [
        "elastic_net",
        "random_forest",
        "elastic_net",
        "random_forest",
    ]
