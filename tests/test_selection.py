import numpy as np
import pandas as pd
from test_baselines import _development_frame

from dengue_sinan.baselines import run_baselines_loro
from dengue_sinan.selection import calibrate_and_select_m1


def test_oof_calibration_selects_model_and_writes_decision_report(tmp_path):
    frame = _development_frame()
    labels = frame["y"].to_numpy(dtype=np.int8)
    good = np.where(labels == 1, 0.8, 0.05)
    poor = np.where(labels == 1, 0.05, 0.8)
    runs = {}
    for model, probabilities, score in (
        ("elastic_net", good, 0.9),
        ("random_forest", poor, 0.1),
    ):
        path = tmp_path / f"{model}.parquet"
        pd.DataFrame({
            "y": labels,
            "probabilidade": probabilities,
            "regiao": frame["regiao"].astype("string"),
        }).to_parquet(path, index=False)
        runs[model] = {
            "oof_artifact": str(path),
            "mean_pr_auc": score,
            "fold_metrics": [
                {"regiao": region, "pr_auc": score}
                for region in ("Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul")
            ],
            "params": {"C": 1.0},
            "best_points": {region: None for region in (
                "Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"
            )},
            "oof_metrics": {"pr_auc": score},
        }

    selection = calibrate_and_select_m1(
        {"ano_teste": 2024, "caminhos": {"relatorios": str(tmp_path / "reports")}},
        frame,
        runs,
        run_baselines_loro(frame),
    )
    assert selection["modelo"] == "elastic_net"
    assert selection["threshold"] > 0
    assert (tmp_path / "reports" / "m1" / "comparacao_oof.md").is_file()
    assert (tmp_path / "reports" / "m1" / "selecao_m1.json").is_file()
    report = (tmp_path / "reports" / "m1" / "comparacao_oof.md").read_text(
        encoding="utf-8"
    )
    assert all(f"| {model} |" in report for model in ("B0", "B1", "B2"))
