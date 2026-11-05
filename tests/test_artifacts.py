import numpy as np
import pytest

from dengue_sinan.artifacts import load_bundle, save_bundle

_METADATA = {
    "commit": "abc123",
    "hashes_dados": {"2022": {"sha256_parquet": "123"}},
    "config": {"seed": 12},
    "data_treino": "2026-11-03",
    "metricas_validacao": {"pr_auc": 0.1},
    "features": ["idade_anos"],
    "versoes_bibliotecas": {"python": "3.13"},
}


def test_save_and_load_model_bundle(tmp_path):
    path = save_bundle({"coeficientes": np.array([0.1, 0.2])}, tmp_path / "model.joblib",
                       _METADATA)
    model, metadata = load_bundle(path)
    assert model["coeficientes"].tolist() == [0.1, 0.2]
    assert metadata == _METADATA


def test_save_bundle_requires_metadata(tmp_path):
    with pytest.raises(ValueError, match="metadados ausentes"):
        save_bundle({}, tmp_path / "invalid.joblib", {})
