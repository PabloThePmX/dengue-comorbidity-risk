"""Guarda contra uso do teste (T-2.2, R1): recusa dados do ano de teste no desenvolvimento.

O ano de teste vem de `config/base.yaml` (chave `ano_teste`), nunca de uma constante no código.

A previsão do teste (T-5.1) passa pelos wrappers dos modelos, que chamam `assert_dev_only` em
`prever_proba`. Por isso há um bloco explícito, `leitura_do_teste()`, usado só por
`evaluate.py`: dentro dele, `assert_dev_only` aceita um DataFrame **só** com o ano de teste e
continua recusando qualquer outro ano. Fora dele, a regra é a de sempre.

O ano de comparação (`ano_comparacao`, 2025, D-97) tem porta própria,
`leitura_do_ano_de_comparacao()`, com a mesma disciplina: fora dela o ano é recusado; dentro
dela só ele é aceito; as duas portas juntas não valem. A chave é opcional no config: sem ela,
nada muda.
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


def leitura_da_comparacao_aberta() -> bool:
    """True se a thread atual está dentro de `leitura_do_ano_de_comparacao()`."""
    return getattr(_ESTADO, "comparacao", False)


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


@contextmanager
def leitura_do_ano_de_comparacao() -> Iterator[None]:
    """Libera a leitura e a previsão do ano de comparação (R1, R2, D-97) só dentro do bloco.

    Chame apenas em volta da avaliação comparativa, depois de o manifesto estar commitado. Dentro
    do bloco, `assert_dev_only` exige que todas as linhas sejam do ano de comparação.
    """
    anterior = leitura_da_comparacao_aberta()
    _ESTADO.comparacao = True
    try:
        yield
    finally:
        _ESTADO.comparacao = anterior


def assert_dev_only(df: pd.DataFrame) -> None:
    """Levanta RuntimeError se alguma linha de `df` for do ano de teste (R1).

    Chame no início de toda função de treino, tuning, calibração, limiar e seleção. Sem coluna
    `ANO` não há como conferir, então também falha (ValueError), e não passa em silêncio.
    Dentro de `leitura_do_teste()`, o caso é o inverso: só passa se **todas** as linhas forem do
    ano de teste, e um DataFrame vazio é recusado (não há o que provar).
    """
    if "ANO" not in df.columns:
        raise ValueError("df sem coluna ANO: não é possível conferir o teste congelado (R1)")
    cfg = load_config()
    ano_teste = cfg["ano_teste"]
    ano_comparacao = cfg.get("ano_comparacao")
    if leitura_do_teste_aberta() and leitura_da_comparacao_aberta():
        raise RuntimeError("as duas portas (teste e comparação) estão abertas ao mesmo tempo (R1)")
    if leitura_da_comparacao_aberta():
        if ano_comparacao is None:
            raise RuntimeError("leitura do ano de comparação sem `ano_comparacao` no config (R1)")
        if len(df) == 0:
            raise RuntimeError("dentro da leitura da comparação um DataFrame vazio é recusado (R1)")
        if not (df["ANO"] == ano_comparacao).all():
            raise RuntimeError(f"dentro da leitura da comparação só entram linhas de "
                               f"{ano_comparacao} (R1, D-97): há linhas de outros anos")
        return
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
    if ano_comparacao is not None and (df["ANO"] == ano_comparacao).any():
        raise RuntimeError(f"{ano_comparacao} é ano de comparação congelado (R1, D-97)")
