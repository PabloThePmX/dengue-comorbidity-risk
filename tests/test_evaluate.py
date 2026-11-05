import json

import numpy as np
import pandas as pd
import pytest

import dengue_sinan.evaluate as evaluate
from dengue_sinan.artifacts import save_bundle
from dengue_sinan.calibration import fit_calibrator
from dengue_sinan.explain import compact_e1, fit_e1
from dengue_sinan.profiling import COMORBIDADES, SINAIS


class ConstantModel:
    def __init__(self, probability):
        self.probability = probability

    def predict_proba(self, frame):
        return np.tile([1 - self.probability, self.probability], (len(frame), 1))


def _metadata():
    return {
        "commit": "abc123",
        "hashes_dados": {"2022": {"sha256_parquet": "hash"}},
        "config": {"seed": 12},
        "data_treino": "2026-11-03",
        "metricas_validacao": {"pr_auc": 0.1},
        "features": ["idade_anos"],
        "versoes_bibliotecas": {"python": "3.13"},
    }


def test_test_evaluation_sets_latch_and_refuses_a_second_run(tmp_path, monkeypatch):
    from test_explain import _e1_frame

    train = _e1_frame()
    pair_counts = pd.DataFrame([
        {"comorbidade_a": first, "comorbidade_b": second,
         "eventos": 20 if (first, second) == ("DIABETES", "HEMATOLOG") else 0}
        for index, first in enumerate(COMORBIDADES)
        for second in COMORBIDADES[index + 1:]
    ])
    e1 = compact_e1(fit_e1(train, pair_counts=pair_counts))
    data = tmp_path / "data"
    data.mkdir()
    (data / "manifest.json").write_text(json.dumps({
        "2024": {"sha256_parquet": "test-hash"},
    }), encoding="utf-8")
    models = tmp_path / "models"
    save_bundle(e1, models / "e1_final.joblib", _metadata())
    save_bundle(ConstantModel(0.1), models / "b1_final.joblib", _metadata())
    calibrator = fit_calibrator(train["y"], np.full(len(train), 0.2), "isotonic")
    save_bundle({
        "pipeline": ConstantModel(0.2),
        "calibrator": calibrator,
        "threshold": 0.5,
    }, models / "m1_final.joblib", {**_metadata(), "probabilidade_b0": 0.1})

    test_frame = train.iloc[:120].copy().reset_index(drop=True)
    test_frame["ANO"] = 2024
    test_frame["CS_GESTANT"] = np.where(test_frame["gestante"], "1", "6")
    test_frame["CS_RACA"] = "1"
    test_frame["DT_SIN_PRI"] = "20240110"
    test_frame["DT_NOTIFIC"] = "20240112"
    test_frame["ID_MN_RESI"] = "355030"
    test_frame["SG_UF"] = "35"
    for column in SINAIS:
        test_frame[column] = "2"
    loader_calls = []
    monkeypatch.setattr(
        evaluate, "load_population",
        lambda cfg, years: (loader_calls.append(years) or test_frame),
    )
    cfg = {
        "seed": 12,
        "ano_teste": 2024,
        "bootstrap": {"metricas": 2},
        "caminhos": {
            "dados": str(data),
            "modelos": str(models),
            "relatorios": str(tmp_path / "reports"),
        },
    }

    results = evaluate.evaluate_test_once(cfg)
    assert "M1" in results and loader_calls == [[2024]]
    latch = tmp_path / "reports" / "teste" / "LACRE.json"
    assert json.loads(latch.read_text(encoding="utf-8"))["status"] == "completed"
    assert (latch.parent / "metricas.md").is_file()
    with pytest.raises(RuntimeError, match="teste já avaliado"):
        evaluate.evaluate_test_once(cfg)
    assert loader_calls == [[2024]]
