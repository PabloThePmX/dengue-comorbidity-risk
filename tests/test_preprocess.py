"""Testes unitários do pré-processamento por família (T-4.1, R4, R5)."""

import numpy as np
import pandas as pd
import pytest

from dengue_sinan.dataset import (
    COMORBIDADES,
    SINAIS,
    build_feature_frame,
)
from dengue_sinan.preprocess import (
    CATEGORICAL_FEATURES,
    FORBIDDEN_FEATURES,
    NUMERIC_FEATURES,
    assert_allowed_features,
    get_catboost_cat_indices,
    make_preprocessor,
)


def _synthetic_population(n: int = 80) -> pd.DataFrame:
    rng = np.random.default_rng(20261103)
    data: dict[str, object] = {
        "ANO": rng.choice([2022, 2023], size=n),
        "CLASSI_FIN": ["10"] * n,
        "EVOLUCAO": ["1"] * n,
        "NU_IDADE_N": [str(4000 + int(a)) for a in rng.integers(5, 85, size=n)],
        "ANO_NASC": ["1980"] * n,
        "DT_SIN_PRI": ["2023-03-01"] * n,
        "DT_NOTIFIC": ["2023-03-04"] * n,
        "CS_SEXO": rng.choice(["F", "M", "I"], size=n),
        "CS_GESTANT": rng.choice(["5", "6", "1"], size=n),
        "CS_RACA": ["1"] * n,
        "ID_MN_RESI": ["355030"] * n,
        "SG_UF": ["35"] * n,
        "PETEQUIAS": ["1"] * n,
        "LACO_N": ["1"] * n,
        "ALRM_HIPOT": ["1"] * n,
    }
    for col in (*COMORBIDADES, *SINAIS):
        data[col] = rng.choice(["1", "2", ""], size=n, p=[0.2, 0.75, 0.05])
    raw = pd.DataFrame(data)
    raw["y"] = rng.binomial(1, 0.1, size=n).astype(np.int8)
    raw["idade_anos"] = rng.uniform(5, 85, size=n)
    raw["idade_de_ano_nasc"] = False
    raw["faixa_etaria"] = "20-39"
    raw["regiao"] = "Sudeste"
    raw["gestante"] = np.int8(0)
    return build_feature_frame(raw)


def test_make_preprocessor_linear_and_elastic_net() -> None:
    feat = _synthetic_population(80)
    train_df = feat.iloc[:60]
    val_df = feat.iloc[60:]

    ct_lin = make_preprocessor("linear")
    X_tr = ct_lin.fit_transform(train_df)
    X_va = ct_lin.transform(val_df)
    assert X_tr.shape[0] == 60
    assert X_va.shape[0] == 20
    assert X_tr.shape[1] == X_va.shape[1]

    ct_en = make_preprocessor("elastic_net")
    X_tr_en = ct_en.fit_transform(train_df)
    X_va_en = ct_en.transform(val_df)
    # Elastic net tem +28 colunas de PolynomialFeatures(degree=2, interaction_only=True)
    assert X_tr_en.shape[1] == X_tr.shape[1] + 28
    assert X_va_en.shape[1] == X_tr_en.shape[1]

    names = ct_en.get_feature_names_out()
    for name in names:
        base_col = str(name).split("__")[-1]
        for forbidden in FORBIDDEN_FEATURES:
            assert base_col != forbidden and not base_col.startswith(f"{forbidden}_")


def test_make_preprocessor_arvore_and_catboost() -> None:
    feat = _synthetic_population(60)
    train_df = feat.iloc[:40]
    val_df = feat.iloc[40:].copy()
    # Categoria nova na validação não quebra OrdinalEncoder
    val_df["sexo"] = val_df["sexo"].astype("object")
    val_df.iloc[0, val_df.columns.get_loc("sexo")] = "Desconhecido"

    ct_tree = make_preprocessor("arvore")
    X_tr = ct_tree.fit_transform(train_df)
    X_va = ct_tree.transform(val_df)
    assert X_tr.shape == (40, len(NUMERIC_FEATURES) + len(CATEGORICAL_FEATURES))
    assert X_va.shape == (20, len(NUMERIC_FEATURES) + len(CATEGORICAL_FEATURES))

    ct_cb = make_preprocessor("catboost")
    X_cb = ct_cb.fit_transform(train_df)
    assert X_cb.shape == (40, len(NUMERIC_FEATURES) + len(CATEGORICAL_FEATURES))
    cat_idx = get_catboost_cat_indices()
    assert len(cat_idx) == len(CATEGORICAL_FEATURES)


def test_assert_allowed_features_rejects_forbidden() -> None:
    assert_allowed_features(["idade_anos", "PETEQUIA_N", "LACO"])
    with pytest.raises(ValueError, match="Colunas proibidas"):
        assert_allowed_features(["idade_anos", "PETEQUIAS"])
    with pytest.raises(ValueError, match="Colunas proibidas"):
        assert_allowed_features(["LACO_N"])
