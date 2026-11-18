"""Etapa 2 — validação de entradas e contrato."""

import numpy as np
import pandas as pd
import pytest

from dengue_sinan.pipeline.contrato import CAMPOS, checar_variaveis, contrato_de_entrada
from dengue_sinan.pipeline.preprocessamento import EntradaInvalida, validar_registros

V = ["idade_anos", "sexo", "gestante"]


def test_registro_valido_completo():
    x, erros = validar_registros([{"idade_anos": 34, "sexo": "F", "gestante": 1}], V)
    assert erros == [] and list(x.columns) == V
    assert x.iloc[0].tolist() == [34.0, "F", 1]


def test_opcionais_ausentes_ou_nulos_viram_o_padrao_do_treino():
    x, erros = validar_registros(
        [{"idade_anos": 5}, {"idade_anos": 5, "sexo": None, "gestante": np.nan}], V
    )
    assert erros == []
    assert x["sexo"].tolist() == ["I", "I"] and x["gestante"].tolist() == [0, 0]


@pytest.mark.parametrize(
    ("registro", "campo"),
    [
        ({"sexo": "F"}, "idade_anos"),  # obrigatório ausente
        ({"idade_anos": None}, "idade_anos"),
        ({"idade_anos": "34"}, "idade_anos"),  # texto não vira número
        ({"idade_anos": True}, "idade_anos"),
        ({"idade_anos": -1}, "idade_anos"),
        ({"idade_anos": 121}, "idade_anos"),
        ({"idade_anos": float("inf")}, "idade_anos"),
        ({"idade_anos": 30, "sexo": "f"}, "sexo"),  # maiúsculas e minúsculas contam
        ({"idade_anos": 30, "sexo": "X"}, "sexo"),
        ({"idade_anos": 30, "sexo": 1}, "sexo"),
        ({"idade_anos": 30, "gestante": 2}, "gestante"),
        ({"idade_anos": 30, "gestante": "sim"}, "gestante"),
    ],
)
def test_registro_invalido_gera_erro_no_campo(registro, campo):
    _, erros = validar_registros([registro], V)
    assert [e["campo"] for e in erros] == [campo] and erros[0]["indice"] == 0


def test_fronteiras_da_idade_sao_aceitas():
    x, erros = validar_registros([{"idade_anos": 0}, {"idade_anos": 120}, {"idade_anos": 0.5}], V)
    assert erros == [] and len(x) == 3


def test_erros_apontam_a_linha_e_as_validas_seguem():
    x, erros = validar_registros([{"idade_anos": 30}, {"idade_anos": "x"}, {"idade_anos": 40}], V)
    assert [e["indice"] for e in erros] == [1]
    assert x.index.tolist() == [0, 2]


def test_campo_desconhecido_ou_proibido_levanta_sempre():
    with pytest.raises(EntradaInvalida, match="DIABETES"):
        validar_registros([{"idade_anos": 30, "DIABETES": "Sim"}], V)
    with pytest.raises(EntradaInvalida, match="CLASSI_FIN"):
        validar_registros([{"idade_anos": 30, "CLASSI_FIN": "12"}], V)


@pytest.mark.parametrize("entrada", [{"idade_anos": 30}, 42, ["texto"]])
def test_entrada_que_nao_e_lista_de_registros_levanta(entrada):
    with pytest.raises(EntradaInvalida):
        validar_registros(entrada, V)


def test_dataframe_com_float_e_nan_funciona():
    df = pd.DataFrame({"idade_anos": [30.0, 40.0], "gestante": [1.0, np.nan]})
    x, erros = validar_registros(df, V)
    assert erros == [] and x["gestante"].tolist() == [1, 0]


def test_lista_vazia_devolve_vazio():
    x, erros = validar_registros([], V)
    assert len(x) == 0 and erros == []


@pytest.mark.parametrize(
    "variaveis",
    [
        ["idade_anos", "DIABETES"],
        ["idade_anos", "idade_anos"],
        ["idade_anos", "CLASSI_FIN"],
        ["idade_anos", "ANO"],
    ],
)
def test_variaveis_fora_da_lista_autorizada_sao_recusadas(variaveis):
    with pytest.raises((ValueError, PermissionError)):
        checar_variaveis(variaveis)


def test_contrato_lista_campos_na_ordem_com_obrigatoriedade():
    c = contrato_de_entrada(V)
    assert [f["nome"] for f in c["campos"]] == V
    assert [f["obrigatorio"] for f in c["campos"]] == [True, False, False]
    assert c["campos"][1]["categorias_aceitas"] == ["F", "M", "I"]
    assert CAMPOS["idade_anos"].minimo == 0 and CAMPOS["idade_anos"].maximo == 120
