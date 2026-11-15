import json

import mlflow
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline

from dengue_sinan.artifacts import save_bundle
from dengue_sinan.calibration import fit_calibrators
from dengue_sinan.download import sha256_file
from dengue_sinan.tracking import log_oof_predictions, register_final_model, start_run


def test_tracking_run_records_config_hashes_and_commit(tmp_path):
    data_dir = tmp_path / "data"
    (data_dir / "raw").mkdir(parents=True)
    (data_dir / "parquet").mkdir()
    (data_dir / "raw" / "DENGBR22.dbc").write_bytes(b"dbc")
    (data_dir / "parquet" / "dengue_2022.parquet").write_bytes(b"parquet")
    manifest_path = data_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {"2022": {"arquivo": "DENGBR22.dbc", "parquet": "parquet/dengue_2022.parquet"}}
        ),
        encoding="utf-8",
    )
    config = {
        "seed": 20261103,
        "anos_dev": [2022],
        "caminhos": {"dados": str(data_dir), "mlruns": str(tmp_path / "mlruns")},
    }

    run = start_run(config, "test-run", {"kind": "unit-test"})
    try:
        assert run.info.run_id
        client = mlflow.tracking.MlflowClient()
        logged = client.get_run(run.info.run_id)
        assert logged.data.params["seed"] == "20261103"
        assert logged.data.tags["git_commit"]
        artifacts = {item.path for item in client.list_artifacts(run.info.run_id)}
        assert {"config.json", "hashes_dados.json", "hardware.json"} <= artifacts
        hashes = client.download_artifacts(run.info.run_id, "hashes_dados.json")
        recorded = json.loads(open(hashes, encoding="utf-8").read())
        assert recorded["anos"]["2022"]["sha256_dbc"] == sha256_file(
            data_dir / "raw" / "DENGBR22.dbc"
        )
    finally:
        mlflow.end_run()


def test_oof_predictions_are_written_to_mlruns(tmp_path):
    config = {"caminhos": {"mlruns": str(tmp_path / "mlruns")}}
    mlflow.set_tracking_uri((tmp_path / "mlruns").as_uri())
    with mlflow.start_run():
        output = log_oof_predictions(
            pd.DataFrame({"y": [0, 1], "p": [0.1, 0.9]}), config, "model"
        )
    assert output.exists()
    assert pd.read_parquet(output)["p"].tolist() == [0.1, 0.9]


def test_final_bundle_is_registered_with_idempotent_validation_alias(tmp_path):
    data_dir = tmp_path / "data"
    (data_dir / "raw").mkdir(parents=True)
    (data_dir / "parquet").mkdir()
    (data_dir / "raw" / "DENGBR22.dbc").write_bytes(b"dbc")
    (data_dir / "parquet" / "dengue_2022.parquet").write_bytes(b"parquet")
    (data_dir / "manifest.json").write_text(
        json.dumps(
            {
                "2022": {
                    "arquivo": "DENGBR22.dbc",
                    "parquet": "parquet/dengue_2022.parquet",
                }
            }
        ),
        encoding="utf-8",
    )
    config = {
        "seed": 20261103,
        "anos_dev": [2022],
        "caminhos": {"dados": str(data_dir), "mlruns": str(tmp_path / "mlruns")},
    }
    features = pd.DataFrame({"idade_anos": [20, 40, 60, 80]})
    pipeline = Pipeline(
        [("modelo", DummyClassifier(strategy="constant", constant=1))]
    ).fit(features, [0, 0, 1, 1])
    calibrator = fit_calibrators([0, 0, 1, 1], [0.1, 0.2, 0.8, 0.9], 11)["platt"]
    bundle = {
        "pipeline": pipeline,
        "calibrador": calibrator,
        "limiar": 0.5,
        "metadados": {
            "modelo_versao": "m1-test",
            "modelo": "elastic_net",
            "hash_dobras": "fold-hash",
        },
        "melhores_pontos": {},
    }
    bundle_path = save_bundle(bundle, tmp_path / "m1_final.joblib")

    version = register_final_model(bundle, bundle_path, features, config)
    client = mlflow.MlflowClient()
    model_version = client.get_model_version_by_alias(
        "dengue-m1", "melhor-validacao"
    )
    registered_model = mlflow.pyfunc.load_model(
        "models:/dengue-m1@melhor-validacao"
    )
    prediction = registered_model.predict(features)
    same_version = register_final_model(bundle, bundle_path, features, config)

    assert str(model_version.version) == version
    assert same_version == version
    assert model_version.tags["modelo"] == "elastic_net"
    assert len(prediction) == len(features)
    assert prediction["modelo_versao"].tolist() == ["m1-test"] * len(features)