import json

import numpy as np
from test_baselines import _development_frame

from dengue_sinan.artifacts import load_bundle
from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.folds import REGIONS
from dengue_sinan.training import train_final_m1


class IdentityCalibrator:
    def transform(self, probabilities):
        return np.asarray(probabilities)


def test_final_m1_retrains_on_dev_and_saves_predictive_bundle(tmp_path):
    frame = _development_frame()
    frame.loc[:99, "ANO"] = 2023
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    manifest = {
        str(year): {"sha256_dbc": f"dbc-{year}", "sha256_parquet": f"parquet-{year}"}
        for year in (2022, 2023)
    }
    (data_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    models_dir = tmp_path / "models"
    config = {
        "seed": 42,
        "anos_dev": [2022, 2023],
        "ano_teste": 2024,
        "caminhos": {"dados": str(data_dir), "modelos": str(models_dir)},
    }

    path = train_final_m1(
        config,
        frame,
        "random_forest",
        {"n_estimators": 10, "min_samples_leaf": 2, "max_features": "sqrt"},
        IdentityCalibrator(),
        0.4,
        dict(zip(REGIONS, (4, 6, 8, 10, 12), strict=True)),
        {"pr_auc": 0.2},
    )
    model, metadata = load_bundle(path)
    assert model["numero_iteracoes_final"] == 8
    assert model["threshold"] == 0.4
    assert metadata["hashes_dados"] == {
        str(year): {
            "sha256_dbc": f"dbc-{year}",
            "sha256_parquet": f"parquet-{year}",
        }
        for year in (2022, 2023)
    }
    assert len(metadata["code_sha256"]) == 64
    assert model["pipeline"].predict_proba(build_feature_frame(frame).iloc[:2]).shape == (2, 2)
    assert path.with_suffix(path.suffix + ".sha256").is_file()
    diagnostics = json.loads(
        path.with_suffix(path.suffix + ".diagnostico.json").read_text(encoding="utf-8")
    )
    assert diagnostics["tamanho_bytes"] == path.stat().st_size
    assert diagnostics["predicao_20_perfis_segundos"] < 1
