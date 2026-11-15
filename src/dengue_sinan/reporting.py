"""Utilitários mínimos para gerar relatórios sem dependências opcionais."""

import pandas as pd


def markdown_table(table: pd.DataFrame) -> str:
    """Renderiza uma tabela simples em Markdown."""
    columns = [str(column) for column in table.columns]
    rows = []
    for row in table.itertuples(index=False, name=None):
        rows.append([("" if pd.isna(value) else str(value)).replace("|", r"\|") for value in row])
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
        *("| " + " | ".join(row) + " |" for row in rows),
    ]
    return "\n".join(lines)
