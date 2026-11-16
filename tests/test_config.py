from pathlib import Path

import pytest

from dengue_sinan.config import CONFIG_PADRAO, load_config

BASE = Path(__file__).resolve().parents[1] / "config" / "base.yaml"


def test_carrega_config_base_com_valores_do_plano():
    cfg = load_config(BASE)
    assert cfg["seed"] == 20261103
    assert cfg["anos_dev"] == [2022, 2023]
    assert cfg["ano_teste"] == 2024
    assert cfg["ordem_dobras"] == ["Sudeste", "Sul", "Centro-Oeste", "Nordeste", "Norte"]
    assert cfg["ambiente"] == {"gpu": "T4", "ram_min_gib": 50}
    assert cfg["caminhos"]["modelos"] == "models"


def test_caminho_padrao_aponta_para_o_base_yaml():
    assert CONFIG_PADRAO == BASE


def test_recusa_ano_de_teste_no_desenvolvimento(tmp_path):
    ruim = tmp_path / "ruim.yaml"
    ruim.write_text(
        "seed: 1\nanos_dev: [2023, 2024]\nano_teste: 2024\ncaminhos: {}\nambiente: {}\n", "utf-8")
    with pytest.raises(ValueError, match="R1"):
        load_config(ruim)


def test_recusa_arquivo_sem_chave_obrigatoria(tmp_path):
    incompleto = tmp_path / "incompleto.yaml"
    incompleto.write_text("seed: 1\n", "utf-8")
    with pytest.raises(ValueError, match="faltam"):
        load_config(incompleto)
