"""Testes do módulo de rastreamento no MLflow (T-2.5)."""

import json
from pathlib import Path

import mlflow
import pandas as pd

from dengue_sinan.tracking import log_fold_metrics, log_oof_predictions, start_run


def test_start_run_logs_config_hashes_and_commit(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    manifest = {
        "2022": {"sha256_dbc": "dbc22hash", "sha256_parquet": "pq22hash"},
        "2023": {"sha256_dbc": "dbc23hash", "sha256_parquet": "pq23hash"},
    }
    (data_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    mlruns_dir = tmp_path / "mlruns"
    cfg = {
        "seed": 20261103,
        "anos_dev": [2022, 2023],
        "caminhos": {"dados": str(data_dir), "mlruns": str(mlruns_dir)},
    }

    with start_run(cfg, "teste-run", tags={"fase": "2"}) as run:
        log_fold_metrics("Sudeste", {"pr_auc": 0.012, "brier": 0.002})
        oof_path = log_oof_predictions(
            pd.DataFrame({"y": [0, 1], "p": [0.1, 0.8]}),
            "modelo_teste",
            cfg,
        )
        run_id = run.info.run_id

    assert oof_path.is_file()
    client = mlflow.tracking.MlflowClient(tracking_uri=mlruns_dir.resolve().as_uri())
    fetched = client.get_run(run_id)
    assert fetched.data.params["seed"] == "20261103"
    assert fetched.data.params["manifest.2022.sha256_parquet"] == "pq22hash"
    assert fetched.data.params["manifest.2023.sha256_dbc"] == "dbc23hash"
    assert "git.commit" in fetched.data.params
    assert fetched.data.metrics["dobra.sudeste.pr_auc"] == 0.012
