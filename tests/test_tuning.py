import optuna
import pytest
from test_baselines import _development_frame

from dengue_sinan.tuning import _suggest_params, tune


def test_tuning_ranges_exclude_imbalance_correction_parameters():
    for model in ("elastic_net", "random_forest", "xgboost", "catboost", "mlp"):
        trial = optuna.create_study().ask()
        params = _suggest_params(trial, model)
        assert not {
            "class_weight",
            "scale_pos_weight",
            "is_unbalance",
            "auto_class_weights",
            "pos_weight",
        } & params.keys()


def test_tabfm_tuning_stops_before_creating_a_study():
    with pytest.raises(RuntimeError, match="T-4.7"):
        tune({"ano_teste": 2024}, "tabfm", _development_frame())
