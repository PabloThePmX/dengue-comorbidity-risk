import json

import mlflow
import pandas as pd

from dengue_sinan.tracking import log_fold_metrics, log_oof_predictions, start_run


def test_mlflow_run_records_provenance_and_oof_outside_git(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    (data / "manifest.json").write_text(json.dumps({
        "2022": {"sha256_dbc": "dbc22", "sha256_parquet": "pq22"},
        "2023": {"sha256_dbc": "dbc23", "sha256_parquet": "pq23"},
    }), encoding="utf-8")
    cfg = {
        "seed": 12,
        "anos_dev": [2022, 2023],
        "caminhos": {"dados": str(data), "mlruns": str(tmp_path / "mlruns")},
    }

    with start_run(cfg, "test-run", {"model": "unit"}):
        log_fold_metrics("Norte", {"pr_auc": 0.5})
        path = log_oof_predictions(
            cfg, "test-run", pd.Series([0, 1]), pd.Series([0.2, 0.8]),
            pd.Series(["Norte", "Sul"]),
        )

    assert path.is_file()
    assert path.parent.name == "oof"
    assert len(pd.read_parquet(path)) == 2
    assert len(mlflow.search_runs()) >= 1
