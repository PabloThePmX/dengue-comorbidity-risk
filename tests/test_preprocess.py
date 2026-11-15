import numpy as np
import pandas as pd

from dengue_sinan.dataset import COMORBIDITY_FEATURES, SYMPTOM_FEATURES
from dengue_sinan.preprocess import make_preprocessor


def _features(rows=40):
    rng = np.random.default_rng(42)
    frame = pd.DataFrame(
        {
            "idade_anos": rng.uniform(0, 100, rows),
            "sexo": rng.choice(["F", "M", "I"], rows),
            "gestante": rng.integers(0, 2, rows),
            "n_comorbidades": rng.integers(0, 8, rows),
            "dias_ate_notificacao": rng.uniform(0, 60, rows),
        }
    )
    for column in COMORBIDITY_FEATURES + SYMPTOM_FEATURES:
        frame[column] = rng.choice(["Sim", "Não", "Ausente"], rows)
    return frame


def test_linear_preprocessor_encodes_features_and_comorbidity_pairs():
    features = _features()
    preprocessor = make_preprocessor("linear", interacoes_comorbidades=True)
    transformed = preprocessor.fit_transform(features)
    names = preprocessor.get_feature_names_out()

    assert transformed.shape[0] == len(features)
    assert transformed.shape[1] == len(names)
    assert sum(name.startswith("interacoes_comorbidades__") for name in names) == 21
    assert np.isfinite(transformed).all()


def test_tree_preprocessor_handles_unseen_categories():
    train = _features()
    validation = _features(8)
    validation.loc[0, "sexo"] = "Novo"
    preprocessor = make_preprocessor("arvore").fit(train)

    transformed = preprocessor.transform(validation)

    assert transformed.shape == (
        len(validation),
        len(COMORBIDITY_FEATURES) + len(SYMPTOM_FEATURES) + 5,
    )
    assert np.isfinite(transformed).all()