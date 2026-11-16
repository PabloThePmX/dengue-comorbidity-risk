"""Checks de qualidade do FR-03 (specs/data-model.md › Checks de qualidade).

Rodados sobre os dados **antes** do filtro de população. Os bloqueantes levantam ValueError com
a lista do que está errado; os alertas só são devolvidos para registro (não interrompem).
"""

import pandas as pd

from dengue_sinan.profiling import COMORBIDADES, GESTANTE_SIM, code, parse_date

# Domínios observados no profiling (specs/data-model.md › Codificação do alvo). Valor novo = falha.
DOMINIO_CLASSI_FIN = {"0", "8", "10", "11", "12"}  # + branco
DOMINIO_EVOLUCAO = {"0", "1", "2", "3", "4", "9"}  # + branco
IGNORADO = "9"
LIMITE_IGNORADO = 0.5


def check_columns(nomes: list[str], obrigatorias: list[str], ano: int) -> None:
    """Bloqueante: todas as colunas usadas existem no arquivo do ano."""
    faltando = [c for c in obrigatorias if c not in nomes]
    if faltando:
        raise ValueError(f"{ano}: faltam colunas {faltando}")


def check_domains(df: pd.DataFrame) -> None:
    """Bloqueante: CLASSI_FIN e EVOLUCAO só têm valores do domínio (ou branco)."""
    problemas = []
    for campo, dominio in (("CLASSI_FIN", DOMINIO_CLASSI_FIN), ("EVOLUCAO", DOMINIO_EVOLUCAO)):
        valores = code(df[campo]).dropna()
        fora = sorted(set(valores[~valores.isin(dominio)]))
        if fora:
            problemas.append(f"{campo} fora do domínio: {fora}")
    if problemas:
        raise ValueError("; ".join(problemas))


def quality_alerts(df: pd.DataFrame) -> list[dict]:
    """Alertas não bloqueantes: só registram. Cada item tem o tipo, o campo e a contagem."""
    alertas: list[dict] = []

    onset, notified = parse_date(df["DT_SIN_PRI"]), parse_date(df["DT_NOTIFIC"])
    both = onset.notna() & notified.notna()
    alertas.append({"alerta": "DT_SIN_PRI > DT_NOTIFIC",
                    "linhas": int((onset > notified)[both].sum())})

    gestante = code(df["CS_GESTANT"]).isin(GESTANTE_SIM)
    alertas.append({"alerta": "gestante com sexo M",
                    "linhas": int((gestante & (code(df["CS_SEXO"]) == "M")).sum())})

    uf = code(df["SG_UF"]).fillna("<branco>")
    for campo in COMORBIDADES:
        valores = code(df[campo])
        ignorado = (valores.isna() | (valores == IGNORADO)).astype(float)
        taxa = ignorado.groupby([df["ANO"], uf]).mean()
        alertas.append({"alerta": f"ignorado > 50% em {campo}, por UF e ano",
                        "grupos_uf_ano": int((taxa > LIMITE_IGNORADO).sum())})
    return alertas
