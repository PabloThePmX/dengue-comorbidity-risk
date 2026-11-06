import numpy as np
import pandas as pd
import pytest

from dengue_sinan.folds import dobras_loro, validacao_interna
from dengue_sinan.guard import assert_dev_only, assert_features_permitidas


def test_guard_bloqueia_2024():
    with pytest.raises(PermissionError):
        assert_dev_only(pd.DataFrame({"ANO": [2022, 2024]}))
    assert_dev_only(pd.DataFrame({"ANO": [2022, 2023]}))


def test_features_proibidas():
    with pytest.raises(ValueError):
        assert_features_permitidas(["idade_anos", "regiao"], ["idade_anos"])
    with pytest.raises(ValueError):
        assert_features_permitidas(["GRAV_PULSO"], ["idade_anos", "GRAV_PULSO"])
    assert_features_permitidas(["idade_anos"], ["idade_anos"])


def test_loro_disjunto_e_cobre_tudo():
    reg = pd.Series(["Norte", "Sul", "Sul", None, "Norte", "Sudeste"])
    dobras = dobras_loro(reg)
    assert {r for r, _, _ in dobras} == {"Norte", "Sul", "Sudeste"}
    testes = np.concatenate([te for _, _, te in dobras])
    assert sorted(testes) == [0, 1, 2, 4, 5]  # a linha sem região nunca é teste
    for _r, tr, te in dobras:
        assert not set(tr) & set(te)
        assert 3 in tr  # sem região: sempre no treino


def test_validacao_interna_estratificada():
    y = np.array([0] * 900 + [1] * 100)
    tr, va = validacao_interna(y, 0.10, seed=3)
    assert not set(tr) & set(va) and len(tr) + len(va) == 1000
    assert y[va].sum() == 10 and len(va) == 100
