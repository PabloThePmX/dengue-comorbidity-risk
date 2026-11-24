"""Manifesto da comparação em 2025 (D-97): o arquivo do projeto e as regras de validação."""

import copy

import pytest
import yaml

from dengue_sinan.comparacao_manifesto import MANIFESTO_PADRAO, carregar_manifesto

CFG = {"ano_teste": 2024, "ano_comparacao": 2025}


def _escrever(tmp_path, m) -> str:
    arquivo = tmp_path / "m.yaml"
    arquivo.write_text(yaml.safe_dump(m, allow_unicode=True), encoding="utf-8")
    return str(arquivo)


@pytest.fixture
def base():
    with open(MANIFESTO_PADRAO, encoding="utf-8") as f:
        return yaml.safe_load(f)


def test_o_manifesto_do_projeto_e_valido_e_nenhum_modelo_viu_2025():
    m = carregar_manifesto()
    assert m["ano_comparacao"] == 2025
    assert all(2025 not in x["treino_anos"] for x in m["modelos"])


def test_o_conjunto_traz_o_projeto_e_as_branches_com_modelo_e_deixa_o_ricardo_de_fora():
    m = carregar_manifesto()
    ids = {x["id"] for x in m["modelos"]}
    assert {"m1_main", "e1_main", "b0_main", "b1_main", "b2_regra", "m1_soneca",
            "m1_lora"} <= ids
    assert [x["id"] for x in m["fora_do_conjunto"]] == ["m1_ricardo"]
    assert "m1_ricardo" not in ids


def test_modelos_externos_tem_commit_e_artefato_com_sha256():
    m = carregar_manifesto()
    for x in m["modelos"]:
        if x["origem"]["branch"] != "main":
            assert len(x["origem"]["commit"]) == 40
            assert len(x["artefato"]["sha256"]) == 64


def test_previsoes_por_caso_ficam_fora_do_git():
    m = carregar_manifesto()
    assert m["saidas"]["previsoes_por_caso"].startswith("data/")  # data/ é ignorada (R7)


def test_recusa_modelo_treinado_em_2025(tmp_path, base):
    ruim = copy.deepcopy(base)
    ruim["modelos"][0]["treino_anos"] = [2022, 2025]
    with pytest.raises(ValueError, match="treinado em 2025"):
        carregar_manifesto(_escrever(tmp_path, ruim), CFG)


def test_recusa_sha256_invalido(tmp_path, base):
    ruim = copy.deepcopy(base)
    ruim["modelos"][0]["artefato"]["sha256"] = "abc"
    with pytest.raises(ValueError, match="SHA-256"):
        carregar_manifesto(_escrever(tmp_path, ruim), CFG)


def test_recusa_ids_repetidos(tmp_path, base):
    ruim = copy.deepcopy(base)
    ruim["modelos"].append(copy.deepcopy(ruim["modelos"][0]))
    with pytest.raises(ValueError, match="repetidos"):
        carregar_manifesto(_escrever(tmp_path, ruim), CFG)


def test_recusa_ano_diferente_do_config(tmp_path, base):
    with pytest.raises(ValueError, match="difere do config"):
        carregar_manifesto(_escrever(tmp_path, base), {"ano_teste": 2024, "ano_comparacao": 2030})


def test_recusa_modelo_sem_chave_obrigatoria(tmp_path, base):
    ruim = copy.deepcopy(base)
    del ruim["modelos"][0]["treino_anos"]
    with pytest.raises(ValueError, match="sem as chaves"):
        carregar_manifesto(_escrever(tmp_path, ruim), CFG)


def test_recusa_modelo_dentro_e_fora_do_conjunto(tmp_path, base):
    ruim = copy.deepcopy(base)
    ruim["fora_do_conjunto"].append({"id": "m1_main", "motivo": "x"})
    with pytest.raises(ValueError, match="dentro e fora"):
        carregar_manifesto(_escrever(tmp_path, ruim), CFG)


def test_o_manifesto_do_projeto_declara_o_dbc_de_2025():
    m = carregar_manifesto()
    assert m["dados"]["arquivo"] == "DENGBR25.dbc"
    assert m["dados"]["ano"] == 2025
    assert len(m["dados"]["sha256"]) == 64


def test_recusa_manifesto_sem_a_chave_dados(tmp_path, base):
    ruim = copy.deepcopy(base)
    del ruim["dados"]
    with pytest.raises(ValueError, match="falta a chave `dados`"):
        carregar_manifesto(_escrever(tmp_path, ruim), CFG)


@pytest.mark.parametrize("campo,valor,erro", [
    ("ano", 2024, "difere do ano de comparação"),
    ("arquivo", "DENGBR24.dbc", "não é o .dbc de 2025"),
    ("sha256", "abc", "SHA-256 válido"),
])
def test_recusa_dados_fora_do_formato(tmp_path, base, campo, valor, erro):
    ruim = copy.deepcopy(base)
    ruim["dados"][campo] = valor
    with pytest.raises(ValueError, match=erro):
        carregar_manifesto(_escrever(tmp_path, ruim), CFG)
