from pathlib import Path

import pytest

from dengue_sinan.config import load_config


def test_load_base_config():
    root = Path(__file__).resolve().parents[1]
    config = load_config(root / "config" / "base.yaml")

    assert config["seed"] == 20261103
    assert config["anos_dev"] == [2022, 2023]
    assert config["ano_teste"] == 2024
    assert config["caminhos"]["relatorios"] == "reports"


@pytest.mark.parametrize("contents", ["", "null", "- item"])
def test_load_config_requires_mapping(tmp_path, contents):
    path = tmp_path / "invalid.yaml"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError, match="mapa YAML"):
        load_config(path)