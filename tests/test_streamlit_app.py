import importlib.util
from pathlib import Path

import numpy as np
import pytest
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from test_baselines import _development_frame

from dengue_sinan.dataset import build_feature_frame
from dengue_sinan.mlp import MLPClassifier
from dengue_sinan.preprocess import FEATURE_COLUMNS, make_preprocessor

_APP_PATH = Path(__file__).parents[1] / "app" / "streamlit_app.py"
_APP_SPEC = importlib.util.spec_from_file_location("dengue_streamlit_app", _APP_PATH)
_APP_MODULE = importlib.util.module_from_spec(_APP_SPEC)
_APP_SPEC.loader.exec_module(_APP_MODULE)
_e1_frame = _APP_MODULE._e1_frame
_m1_features = _APP_MODULE._m1_features
_top_factors = _APP_MODULE._top_factors


def _values(**updates):
    values = {
        "idade_anos": 42,
        "sexo": "F",
        "gestante": "nao",
        "dias_ate_atendimento": 3,
    }
    values.update(updates)
    return values


def test_e1_profile_builder_maps_domain_and_comorbidities():
    frame = _e1_frame(_values(diabetes="sim", renal_cronica="ignorado"))
    assert frame.loc[0, "idade_anos"] == 42
    assert frame.loc[0, "DIABETES"] == "1"
    assert frame.loc[0, "RENAL"] == "9"
    assert not frame.loc[0, "gestante"]


def test_m1_builder_emits_exact_model_features_and_notification_delay():
    values = _values(
        diabetes="sim",
        febre="sim",
        petéquias="nao",
        gestante="ignorado",
    )
    features = _m1_features(values)
    assert set(FEATURE_COLUMNS) <= set(features.columns)
    assert features.loc[0, "idade_anos"] == 42
    assert features.loc[0, "DIABETES"] == "Sim"
    assert features.loc[0, "FEBRE"] == "Sim"
    assert features.loc[0, "dias_ate_notificacao"] == 3
    assert features.loc[0, "gestante"] == 0


@pytest.mark.parametrize("age", [-1, 121, True])
def test_demo_rejects_invalid_age(age):
    with pytest.raises(ValueError, match="idade_anos"):
        _e1_frame(_values(idade_anos=age))


def test_m1_requires_notification_delay():
    values = _values()
    values.pop("dias_ate_atendimento")
    with pytest.raises(ValueError, match="obrigatório para M1"):
        _m1_features(values)


@pytest.mark.parametrize("family", ["random_forest", "mlp"])
def test_demo_explains_five_factors_for_supported_model_families(family):
    source = _development_frame()
    labels = source["y"].to_numpy()
    features = build_feature_frame(source)[FEATURE_COLUMNS]
    preprocessor = make_preprocessor("arvore" if family == "random_forest" else "linear")
    transformed = preprocessor.fit_transform(features, labels)
    if family == "random_forest":
        estimator = RandomForestClassifier(n_estimators=5, random_state=4).fit(
            transformed, labels
        )
        bundle = {"modelo": family}
    else:
        estimator = MLPClassifier(
            hidden_layers=(4,),
            batch_size=64,
            epochs=2,
            patience=1,
            seed=4,
            device="cpu",
        ).fit(transformed, labels)
        background = np.stack([
            transformed[labels == value].mean(axis=0) for value in (0, 1)
        ]).astype(np.float32)
        bundle = {
            "modelo": family,
            "explainer": _APP_MODULE.shap.GradientExplainer(
                estimator.model_,
                _APP_MODULE.torch.as_tensor(background, dtype=_APP_MODULE.torch.float32),
            ),
        }
    if family == "random_forest":
        bundle["explainer"] = _APP_MODULE.shap.TreeExplainer(estimator)
    pipeline = Pipeline([("preprocess", preprocessor), ("model", estimator)])
    bundle["pipeline"] = pipeline
    explained = _top_factors(bundle, features.iloc[:1])
    assert len(explained) == 5
    assert set(explained["Direção"]) <= {"Aumentou", "Reduziu"}
