import pandas as pd
import pytest

from dengue_sinan import guard


def test_passa_com_anos_de_desenvolvimento():
    df = pd.DataFrame({"ANO": [2022, 2022, 2023], "y": [0, 1, 0]})
    guard.assert_dev_only(df)  # não levanta


def test_falha_com_uma_linha_de_2024():
    df = pd.DataFrame({"ANO": [2022, 2023, 2024], "y": [0, 0, 1]})
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        guard.assert_dev_only(df)


def test_falha_com_coluna_ano_categorica():
    df = pd.DataFrame({"ANO": pd.Categorical([2023, 2024])})
    with pytest.raises(RuntimeError, match="2024 é teste congelado"):
        guard.assert_dev_only(df)


def test_le_o_ano_de_teste_do_config(monkeypatch):
    # Se o ano de teste mudar no config, a guarda segue o config, não um 2024 fixo no código.
    monkeypatch.setattr(guard, "load_config", lambda: {"ano_teste": 2030})
    guard.assert_dev_only(pd.DataFrame({"ANO": [2024]}))  # 2024 agora é desenvolvimento
    with pytest.raises(RuntimeError, match="2030 é teste congelado"):
        guard.assert_dev_only(pd.DataFrame({"ANO": [2030]}))


def test_falha_sem_coluna_ano():
    with pytest.raises(ValueError, match="sem coluna ANO"):
        guard.assert_dev_only(pd.DataFrame({"y": [0, 1]}))
