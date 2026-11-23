"""Guarda contra uso do teste (T-2.2, R1): recusa dados do ano de teste no desenvolvimento.

O ano de teste vem de `config/base.yaml` (chave `ano_teste`), nunca de uma constante no código.

A previsão do teste (T-5.1) passa pelos wrappers dos modelos, que chamam `assert_dev_only` em
`prever_proba`. Por isso há um bloco explícito, `leitura_do_teste()`, usado só por
`evaluate.py`: dentro dele, `assert_dev_only` aceita um DataFrame **só** com o ano de teste e
continua recusando qualquer outro ano. Fora dele, a regra é a de sempre.
"""

import threading
from collections.abc import Iterator
from contextlib import contextmanager

import pandas as pd

from dengue_sinan.config import load_config

# Estado da porta por thread: outra thread, com a porta fechada, continua recusando o ano de teste
# enquanto esta está dentro do bloco.
_ESTADO = threading.local()


def leitura_do_teste_aberta() -> bool:
    """True se a thread atual está dentro de `leitura_do_teste()`."""
    return getattr(_ESTADO, "ativa", False)


@contextmanager
def leitura_do_teste() -> Iterator[None]:
    """Libera a previsão do ano de teste (R2) só dentro do bloco.

    Chame apenas em volta da predição da avaliação final. Dentro do bloco, `assert_dev_only`
    exige que todas as linhas sejam do ano de teste: 2022–23 continua recusado.
    """
    anterior = leitura_do_teste_aberta()
    _ESTADO.ativa = True
    try:
        yield
    finally:
        _ESTADO.ativa = anterior


def assert_dev_only(df: pd.DataFrame) -> None:
    """Levanta RuntimeError se alguma linha de `df` for do ano de teste (R1).

    Chame no início de toda função de treino, tuning, calibração, limiar e seleção. Sem coluna
    `ANO` não há como conferir, então também falha (ValueError), e não passa em silêncio.
    Dentro de `leitura_do_teste()`, o caso é o inverso: só passa se **todas** as linhas forem do
    ano de teste, e um DataFrame vazio é recusado (não há o que provar).
    """
    if "ANO" not in df.columns:
        raise ValueError("df sem coluna ANO: não é possível conferir o teste congelado (R1)")
    ano_teste = load_config()["ano_teste"]
    do_teste = df["ANO"] == ano_teste
    if leitura_do_teste_aberta():
        if len(df) == 0:
            raise RuntimeError("dentro da leitura do teste um DataFrame vazio é recusado (R1)")
        if not do_teste.all():
            raise RuntimeError(f"dentro da leitura do teste só entram linhas de {ano_teste} "
                               "(R1): há linhas de outros anos")
        return
    if do_teste.any():
        raise RuntimeError(f"{ano_teste} é teste congelado (R1)")
