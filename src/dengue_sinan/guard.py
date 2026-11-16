"""Guarda contra uso do teste (T-2.2, R1): recusa dados do ano de teste no desenvolvimento.

O ano de teste vem de `config/base.yaml` (chave `ano_teste`), nunca de uma constante no código.
"""

import pandas as pd

from dengue_sinan.config import load_config


def assert_dev_only(df: pd.DataFrame) -> None:
    """Levanta RuntimeError se alguma linha de `df` for do ano de teste (R1).

    Chame no início de toda função de treino, tuning, calibração, limiar e seleção. Sem coluna
    `ANO` não há como conferir, então também falha (ValueError), e não passa em silêncio.
    """
    if "ANO" not in df.columns:
        raise ValueError("df sem coluna ANO: não é possível conferir o teste congelado (R1)")
    ano_teste = load_config()["ano_teste"]
    if (df["ANO"] == ano_teste).any():
        raise RuntimeError(f"{ano_teste} é teste congelado (R1)")
