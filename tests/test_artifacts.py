import numpy as np
import pandas as pd

from dengue_sinan.artifacts import load_bundle, predict_bundle, save_bundle
from dengue_sinan.calibration import fit_calibrators


class FixedPipeline:
    def predict_proba(self, features):
        probability = np.full(len(features), 0.8)
        return np.column_stack((1 - probability, probability))


def test_bundle_round_trip_predicts_calibrated_risk(tmp_path):
    labels = np.array([0, 0, 1, 1])
    bundle = {
        "pipeline": FixedPipeline(),
        "calibrador": fit_calibrators(labels, [0.1, 0.2, 0.7, 0.9], 11)["platt"],
        "limiar": 0.5,
        "metadados": {"modelo_versao": "m1-test"},
        "melhores_pontos": {},
    }

    path = save_bundle(bundle, tmp_path / "m1_final.joblib")
    prediction = predict_bundle(load_bundle(path), pd.DataFrame({"idade_anos": [55]}))

    assert prediction.loc[0, "alto_risco"]
    assert prediction.loc[0, "modelo_versao"] == "m1-test"
    assert 0 <= prediction.loc[0, "risco"] <= 1
