from pathlib import Path

from test_cv import _development_data

from dengue_sinan.shap_report import generate_global_shap


def test_global_shap_writes_summary_and_interaction_figures(tmp_path):
    data = _development_data(rows_per_region=20)
    results = {
        "random_forest": {
            "best_params": {
                "n_estimators": 5,
                "max_depth": 2,
                "min_samples_leaf": 2,
                "max_features": "sqrt",
                "max_samples": 0.8,
            },
            "best_points": {},
            "mean_pr_auc": 0.5,
        }
    }

    report = generate_global_shap(
        results, data, {"seed": 17}, tmp_path, sample_size=10
    )

    assert report["linhas"] == 10
    assert all(Path(path).is_file() for path in report["arquivos"])
