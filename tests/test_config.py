"""Testes do carregamento de configuração (T-2.0)."""

from pathlib import Path

import pytest

from dengue_sinan.config import load_config, load_expected


def test_load_base_config() -> None:
    cfg = load_config(Path("config/base.yaml"))
    assert cfg["seed"] == 20261103
    assert cfg["anos_dev"] == [2022, 2023]
    assert cfg["ano_teste"] == 2024
    assert cfg["dias_notificacao_max"] == 60
    assert cfg["faixas"] == [0, 5, 15, 40, 60, 80]
    assert cfg["ordem_modelos"] == [
        "elastic_net",
        "xgboost",
        "catboost",
        "mlp",
        "random_forest",
        "tabfm",
    ]
    assert cfg["ordem_dobras"] == ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"]


def test_load_expected_has_no_test_year_2024() -> None:
    esp = load_expected(Path("config/esperado.yaml"))
    assert esp["casos_dev"] == 2453208
    assert esp["eventos_dev"] == 3985
    assert 2024 not in esp["populacao_por_ano"]
    assert "2024" not in esp["populacao_por_ano"]
    assert 2024 not in esp["fluxograma_exclusao"]


def test_load_config_rejects_non_mapping(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("- item1\n- item2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="esperado mapeamento YAML"):
        load_config(bad)
