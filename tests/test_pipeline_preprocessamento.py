"""Etapa 2 — o pré-processamento do treino e o da inferência são o mesmo."""

import pandas as pd
from conftest_sint import bruto_sintetico

from dengue_sinan.dataset import matriz_arvore, montar_features, montar_populacao
from dengue_sinan.pipeline.preprocessamento import matriz_modelo, normalizar_x, validar_registros

V = ["idade_anos", "sexo", "gestante"]


def test_matriz_da_inferencia_igual_a_do_treino():
    """Registros que vêm do contrato dão a mesma matriz que a preparação do treino."""
    x_treino = montar_features(montar_populacao(bruto_sintetico(n=3000), 2022))[V]
    registros = [
        {"idade_anos": a, "sexo": s, "gestante": int(g)}
        for a, s, g in zip(
            x_treino["idade_anos"], x_treino["sexo"], x_treino["gestante"], strict=True
        )
    ]
    x_inf, erros = validar_registros(registros, V)
    assert erros == []
    pd.testing.assert_frame_equal(
        matriz_modelo(x_treino, V).reset_index(drop=True),
        matriz_modelo(x_inf, V).reset_index(drop=True),
    )
    # e é exatamente a codificação ordinal sem estado que o ModeloM1 usa
    pd.testing.assert_frame_equal(
        matriz_modelo(x_treino, V), matriz_arvore(normalizar_x(x_treino, V))
    )


def test_ordem_das_colunas_e_a_do_modelo_mesmo_com_entrada_embaralhada():
    df = pd.DataFrame({"gestante": [0], "idade_anos": [33.0], "sexo": ["M"]})
    m = matriz_modelo(df, V)
    assert list(m.columns) == V
    assert m.iloc[0].tolist() == [33.0, 1, 0]  # M = código 1 em [F, M, I]


def test_tipos_e_categorias_ficam_fixos():
    x = normalizar_x(pd.DataFrame({"idade_anos": [1], "sexo": ["I"], "gestante": [True]}), V)
    assert x["idade_anos"].dtype == "float64" and x["gestante"].dtype == "int8"
    assert list(x["sexo"].cat.categories) == ["F", "M", "I"]


def test_entrada_com_poucas_categorias_nao_muda_os_codigos():
    a = matriz_modelo(pd.DataFrame({"idade_anos": [1.0], "sexo": ["I"], "gestante": [0]}), V)
    assert a["sexo"].iloc[0] == 2  # I é 2 mesmo sem F e M no lote
