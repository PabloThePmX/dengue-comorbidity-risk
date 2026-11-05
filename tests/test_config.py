import pytest

from dengue_sinan.config import load_config


def test_load_config_reads_base_file(tmp_path):
    path = tmp_path / "config.yaml"
    path.write_text(
        "seed: 10\nanos_dev: [2022, 2023]\nano_teste: 2024\ncaminhos: {dados: data}\n",
        encoding="utf-8",
    )
    assert load_config(path)["seed"] == 10


@pytest.mark.parametrize(
    "content",
    ["[]", "seed: 1\n", "seed: 1\nanos_dev: [2024]\nano_teste: 2024\ncaminhos: {}\n"],
)
def test_load_config_rejects_invalid_structure(tmp_path, content):
    path = tmp_path / "invalid.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(path)
