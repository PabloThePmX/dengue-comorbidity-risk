import numpy as np
import pandas as pd
import pytest

from dengue_sinan.calibration import apply_calibrator, fit_calibrators
from dengue_sinan.selection import select_m1


def test_calibrators_return_probabilities_in_unit_interval():
    y = np.tile([0, 1], 100)
    probability = np.clip(0.1 + 0.7 * y + np.linspace(-0.02, 0.02, len(y)), 0, 1)

    calibrators = fit_calibrators(y, probability, seed=17)
    calibrated = {
        name: apply_calibrator(calibrator, probability)
        for name, calibrator in calibrators.items()
    }

    assert set(calibrated) == {"platt", "isotonic"}
    assert all(np.isfinite(values).all() for values in calibrated.values())
    assert all(((values >= 0) & (values <= 1)).all() for values in calibrated.values())


def test_selection_writes_aggregated_comparison_and_calibrator(tmp_path):
    y = np.tile([0, 1], 80)
    regions = np.tile(["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"], 32)
    probability = np.where(y == 1, 0.7, 0.1)
    oof = pd.DataFrame(
        {"y": y, "probabilidade": probability, "regiao": regions, "ANO": 2022}
    )
    result = {
        "elastic_net": {"oof": oof},
        "random_forest": {"oof": oof.assign(probabilidade=np.clip(probability + 0.01, 0, 1))},
    }
    baseline = pd.DataFrame(
        {
            "ANO": np.full(len(y), 2022),
            "y": y,
            "regiao": regions,
            "b0": np.full(len(y), y.mean()),
            "b1": np.full(len(y), y.mean()),
            "b2": np.zeros(len(y)),
        }
    )
    config = {
        "seed": 17,
        "ordem_dobras": ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"],
        "bootstrap": {"metricas": 5},
        "bootstrap_pareado": 5,
    }

    selected = select_m1(result, baseline, config, tmp_path)

    assert selected["modelo"] in result
    assert 0 <= selected["limiar"] <= 1
    assert (tmp_path / "m1" / "comparacao_oof.md").is_file()
    assert (tmp_path / "m1" / "comparacao_pareada.md").is_file()
    assert (tmp_path / "m1" / "calibrador.joblib").is_file()
    assert (tmp_path / "m1" / "calibradores" / "elastic_net.joblib").is_file()
    assert (tmp_path / "m1" / "calibradores" / "random_forest.joblib").is_file()


def test_selection_rejects_frozen_test_year(tmp_path):
    baseline = pd.DataFrame(
        {
            "ANO": [2022, 2024],
            "y": [0, 1],
            "regiao": ["Norte", "Norte"],
            "b0": [0.5, 0.5],
            "b1": [0.5, 0.5],
            "b2": [0, 1],
        }
    )

    results = {
        "elastic_net": {
            "oof": baseline.assign(probabilidade=[0.1, 0.9])
        }
    }

    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        select_m1(results, baseline, {}, tmp_path)
