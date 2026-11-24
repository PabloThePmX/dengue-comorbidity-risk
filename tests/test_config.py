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


def test_ano_de_comparacao_do_projeto_e_2025_e_nao_se_mistura_com_dev_nem_teste():
    cfg = load_config()
    assert cfg["ano_comparacao"] == 2025
    assert cfg["ano_comparacao"] not in cfg["anos_dev"]
    assert cfg["ano_comparacao"] != cfg["ano_teste"]


def test_ano_de_comparacao_em_anos_dev_ou_igual_ao_teste_e_recusado(tmp_path):
    base = "seed: 1\nanos_dev: [2022, 2023]\nano_teste: 2024\ncaminhos: {}\nambiente: {}\n"
    for ano, trecho in ((2023, "anos_dev"), (2024, "ano_teste")):
        arquivo = tmp_path / f"c{ano}.yaml"
        arquivo.write_text(base + f"ano_comparacao: {ano}\n", "utf-8")
        with pytest.raises(ValueError, match=trecho):
            load_config(arquivo)


def test_ano_de_comparacao_e_opcional(tmp_path):
    arquivo = tmp_path / "c.yaml"
    arquivo.write_text(
        "seed: 1\nanos_dev: [2022, 2023]\nano_teste: 2024\ncaminhos: {}\nambiente: {}\n", "utf-8")
    assert "ano_comparacao" not in load_config(arquivo)
