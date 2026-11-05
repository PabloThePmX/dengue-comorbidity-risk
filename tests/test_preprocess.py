import pandas as pd
import pytest

from dengue_sinan.preprocess import (
    CATBOOST_CATEGORICAL_INDICES,
    FEATURE_COLUMNS,
    make_preprocessor,
)


def _features():
    rows = []
    for index in range(10):
        row = {
            "idade_anos": float(20 + index),
            "gestante": index % 2,
            "n_comorbidades": index % 3,
            "dias_ate_notificacao": float(index),
            "sexo": "F" if index % 2 else "M",
        }
        row.update({
            column: ("Sim" if index % 3 == 0 else "Ausente" if index == 1 else "Não")
            for column in FEATURE_COLUMNS
            if column not in row and column not in {
                "idade_anos", "gestante", "n_comorbidades", "dias_ate_notificacao",
            }
        })
        rows.append(row)
    frame = pd.DataFrame(rows, columns=FEATURE_COLUMNS)
    frame["UF_PROIBIDA"] = "SP"
    frame["ANO"] = 2022
    return frame


@pytest.mark.parametrize("family", ["linear", "arvore", "catboost"])
def test_preprocessors_fit_train_and_transform_validation(family):
    features = _features()
    preprocessor = make_preprocessor(family)
    train = features.iloc[:8][FEATURE_COLUMNS]
    validation = features.iloc[8:][FEATURE_COLUMNS]
    transformed_train = preprocessor.fit_transform(train)
    transformed_validation = preprocessor.transform(validation)
    assert transformed_train.shape[1] == transformed_validation.shape[1]
    assert transformed_validation.shape[0] == 2
    assert "UF_PROIBIDA" not in preprocessor.get_feature_names_out()


def test_elastic_net_preprocessor_appends_only_21_comorbidity_interactions():
    features = _features()[FEATURE_COLUMNS]
    transformed = make_preprocessor("linear", interactions=True).fit_transform(features)
    base = make_preprocessor("linear").fit_transform(features)
    assert transformed.shape[1] == base.shape[1] + 21


def test_catboost_categorical_indices_match_feature_layout():
    assert CATBOOST_CATEGORICAL_INDICES[0] == 4
    assert CATBOOST_CATEGORICAL_INDICES[-1] == len(FEATURE_COLUMNS) - 1
