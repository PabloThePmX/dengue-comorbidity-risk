"""Cálculos do roteiro de profiling (profiling/ROTEIRO.md). Funções puras sobre DataFrames.

Convenção: os campos chegam como texto cru do DBF; branco = NaN.
"""

import numpy as np
import pandas as pd

from dengue_sinan.features import decode_age_years, region_from_ibge

COMORBIDADES = ["DIABETES", "HEMATOLOG", "HEPATOPAT", "RENAL", "HIPERTENSA", "ACIDO_PEPT",
                "AUTO_IMUNE"]
SINAIS = ["FEBRE", "MIALGIA", "CEFALEIA", "EXANTEMA", "VOMITO", "NAUSEA", "DOR_COSTAS",
          "CONJUNTVIT", "ARTRITE", "ARTRALGIA", "PETEQUIA_N", "LEUCOPENIA", "LACO", "DOR_RETRO"]
CAMPOS_ALVO = ["CLASSI_FIN", "EVOLUCAO", "CRITERIO"]
CLASSI_DENGUE = {"10", "11", "12"}
EVOLUCAO_CONHECIDA = {"1", "2"}
GESTANTE_SIM = {"1", "2", "3", "4"}
FAIXAS = [0, 5, 15, 40, 60, 80, np.inf]
FAIXAS_ROTULOS = ["0–4", "5–14", "15–39", "40–59", "60–79", "80+"]
MIN_EVENTOS = 100
BRANCO = "<branco>"


def code(series: pd.Series) -> pd.Series:
    """Texto normalizado: sem espaços e sem sufixo ".0" de números lidos como float."""
    text = series.astype("string").str.strip().str.replace(r"\.0$", "", regex=True)
    return text.mask(text == "")


def optional(df: pd.DataFrame, column: str) -> pd.Series:
    """Coluna que pode não existir nos microdados públicos; ausente = toda em branco.

    Ex.: `DT_NASC` não é publicada (anonimização); só `ANO_NASC`. Campos essenciais (alvo,
    comorbidades) devem ser acessados direto, para falhar alto se sumirem.
    """
    if column in df:
        return df[column]
    return pd.Series(pd.NA, index=df.index, dtype="string")


def parse_date(series: pd.Series) -> pd.Series:
    """Datas do DBF (AAAAMMDD) ou ISO; inválidas viram NaT."""
    text = code(series)
    compact = pd.to_datetime(text, format="%Y%m%d", errors="coerce")
    iso = pd.to_datetime(text, format="%Y-%m-%d", errors="coerce")
    return compact.fillna(iso)


def counts_by_year(df: pd.DataFrame, column: str, year: str = "ANO") -> pd.DataFrame:
    """Contagem de cada valor (inclusive branco) por ano. Linhas = valores, colunas = anos."""
    values = code(df[column]).fillna(BRANCO)
    table = pd.crosstab(values, df[year])
    table.index.name = column
    return table


def target(df: pd.DataFrame) -> pd.Series:
    """y = 1 se dengue grave (CLASSI_FIN = 12) ou óbito pelo agravo (EVOLUCAO = 2) — D-02."""
    severe = code(df["CLASSI_FIN"]).isin({"12"})
    death = code(df["EVOLUCAO"]).isin({"2"})
    return (severe | death).astype("int8")


def population_mask(df: pd.DataFrame) -> pd.Series:
    """População de D-06: dengue (10/11/12) com evolução conhecida (cura ou óbito pelo agravo)."""
    classi_ok = code(df["CLASSI_FIN"]).isin(CLASSI_DENGUE)
    evolucao_ok = code(df["EVOLUCAO"]).isin(EVOLUCAO_CONHECIDA)
    return classi_ok & evolucao_ok


def exclusion_flow(df: pd.DataFrame, year: str = "ANO") -> pd.DataFrame:
    """Fluxograma de exclusão (FR-02): linhas restantes após cada filtro, por ano."""
    classi_ok = code(df["CLASSI_FIN"]).isin(CLASSI_DENGUE)
    evolucao_ok = code(df["EVOLUCAO"]).isin(EVOLUCAO_CONHECIDA)
    steps = {
        "1. Total baixado": pd.Series(True, index=df.index),
        "2. CLASSI_FIN ∈ {10, 11, 12}": classi_ok,
        "3. EVOLUCAO ∈ {1, 2}": classi_ok & evolucao_ok,
    }
    flow = pd.DataFrame({name: mask.groupby(df[year]).sum() for name, mask in steps.items()}).T
    flow.columns.name = year
    return flow


def exclusion_reasons(df: pd.DataFrame, year: str = "ANO") -> dict[str, pd.DataFrame]:
    """Quem saiu em cada filtro, por valor do campo — para ver se casos graves saem por branco."""
    classi = code(df["CLASSI_FIN"])
    classi_ok = classi.isin(CLASSI_DENGUE)
    evolucao_out = df[classi_ok & ~code(df["EVOLUCAO"]).isin(EVOLUCAO_CONHECIDA)]
    return {
        "Removidos no filtro 2 (CLASSI_FIN)": counts_by_year(df[~classi_ok], "CLASSI_FIN", year),
        "Removidos no filtro 3 (EVOLUCAO), por EVOLUCAO": counts_by_year(evolucao_out, "EVOLUCAO",
                                                                        year),
        "Removidos no filtro 3 (EVOLUCAO), por CLASSI_FIN": counts_by_year(evolucao_out,
                                                                          "CLASSI_FIN", year),
    }


def add_derived(df: pd.DataFrame) -> pd.DataFrame:
    """Colunas derivadas usadas em vários passos: y, idade, faixa, região, gestante."""
    out = df.copy()
    out["y"] = target(out)
    out["idade_anos"] = decode_age_years(out["NU_IDADE_N"])
    out["faixa_etaria"] = pd.cut(out["idade_anos"], FAIXAS, right=False, labels=FAIXAS_ROTULOS)
    # Região pelo município de residência; se faltar, pela UF de residência.
    regiao = region_from_ibge(optional(out, "ID_MN_RESI")).astype("string")
    out["regiao"] = regiao.combine_first(region_from_ibge(optional(out, "SG_UF")).astype("string"))
    out["gestante"] = code(out["CS_GESTANT"]).isin(GESTANTE_SIM)
    return out


def prevalence_by_year(pop: pd.DataFrame, year: str = "ANO") -> pd.DataFrame:
    """Casos, eventos (y = 1) e prevalência por ano."""
    grouped = pop.groupby(year)["y"]
    table = pd.DataFrame({"casos": grouped.size(), "eventos (y=1)": grouped.sum()})
    table["prevalência (%)"] = 100 * table["eventos (y=1)"] / table["casos"]
    return table


def events_by(pop: pd.DataFrame, column: str) -> pd.DataFrame:
    """Casos e eventos por categoria, com alerta para < 100 eventos (§3.8)."""
    grouped = pop.groupby(pop[column].astype("string").fillna(BRANCO), observed=True)["y"]
    table = pd.DataFrame({"casos": grouped.size(), "eventos (y=1)": grouped.sum()})
    table["prevalência (%)"] = 100 * table["eventos (y=1)"] / table["casos"]
    table["< 100 eventos"] = np.where(table["eventos (y=1)"] < MIN_EVENTOS, "⚠️", "")
    table.index.name = column
    return table


def domain_counts(df: pd.DataFrame, columns: list[str], year: str = "ANO",
                  valid: tuple[str, ...] = ("1", "2")) -> pd.DataFrame:
    """Para campos 1/2: contagem de 1, 2, branco e outros valores, por campo e ano."""
    rows = []
    for column in columns:
        values = code(df[column])
        bucket = pd.Series(np.where(values.isin(valid), values, "outros"), index=df.index)
        bucket = bucket.where(values.notna(), BRANCO)
        counts = pd.crosstab(bucket, df[year])
        for value, row in counts.iterrows():
            rows.append({"campo": column, "valor": value, **row.to_dict()})
    return pd.DataFrame(rows).set_index(["campo", "valor"]).fillna(0).astype(int)


def other_values(df: pd.DataFrame, columns: list[str], valid: tuple[str, ...] = ("1", "2"),
                 top: int = 5) -> pd.DataFrame:
    """Quais valores fora do domínio aparecem (ex.: 9), para documentar a divergência."""
    rows = []
    for column in columns:
        values = code(df[column])
        outside = values[values.notna() & ~values.isin(valid)]
        for value, n in outside.value_counts().head(top).items():
            rows.append({"campo": column, "valor": value, "linhas": int(n)})
    return pd.DataFrame(rows, columns=["campo", "valor", "linhas"])


def absent_by_target(pop: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    """% "Ausente" (branco ou ≠ 1/2) por campo, separado por y — check de vazamento (§3.8)."""
    rows = []
    for column in columns:
        absent = ~code(pop[column]).isin({"1", "2"})
        share = absent.groupby(pop["y"]).mean() * 100
        p0, p1 = share.get(0, np.nan), share.get(1, np.nan)
        rows.append({
            "campo": column,
            "% ausente y=0": p0,
            "% ausente y=1": p1,
            "razão y0/y1": p0 / p1 if p1 else np.nan,
        })
    table = pd.DataFrame(rows).set_index("campo")
    table["alerta (razão > 2)"] = np.where(table["razão y0/y1"] > 2, "⚠️", "")
    return table


def age_summary(df: pd.DataFrame, year: str = "ANO") -> pd.DataFrame:
    """Resumo da idade decodificada por ano: nulos, fora de [0, 120], quantis."""
    age = decode_age_years(df["NU_IDADE_N"])
    grouped = age.groupby(df[year])
    raw_blank = code(df["NU_IDADE_N"]).isna().groupby(df[year]).sum()
    return pd.DataFrame({
        "linhas": grouped.size(),
        "NU_IDADE_N em branco": raw_blank,
        "código inválido": age.isna().groupby(df[year]).sum() - raw_blank,
        "fora de [0, 120]": ((age < 0) | (age > 120)).groupby(df[year]).sum(),
        "mín": grouped.min(),
        "p50": grouped.median(),
        "p99": grouped.quantile(0.99),
        "máx": grouped.max(),
    })


def age_unit_counts(df: pd.DataFrame, year: str = "ANO") -> pd.DataFrame:
    """Distribuição do 1º dígito de NU_IDADE_N (unidade), para conferir a regra."""
    unit = code(df["NU_IDADE_N"]).str[0].fillna(BRANCO)
    table = pd.crosstab(unit, df[year])
    table.index.name = "unidade (1º dígito)"
    return table


def age_vs_birth_year(df: pd.DataFrame, tolerance_years: float = 1.0) -> pd.DataFrame:
    """Compara a idade decodificada com ano(DT_SIN_PRI) − ANO_NASC.

    Os microdados públicos não trazem DT_NASC, só o ano; sem dia e mês, a conta erra até
    1 ano para mais ou para menos, daí a tolerância padrão de 1 ano.
    """
    decoded = decode_age_years(df["NU_IDADE_N"])
    birth_year = pd.to_numeric(code(optional(df, "ANO_NASC")), errors="coerce")
    computed = parse_date(df["DT_SIN_PRI"]).dt.year - birth_year
    both = decoded.notna() & computed.notna()
    diff = (decoded - computed).abs()[both]
    return pd.DataFrame({
        "linhas com ANO_NASC e idade": [int(both.sum())],
        f"concordam (|dif| ≤ {tolerance_years:g} ano)": [int((diff <= tolerance_years).sum())],
        "% concordância": [100 * (diff <= tolerance_years).mean() if len(diff) else np.nan],
        "dif. p99 (anos)": [diff.quantile(0.99) if len(diff) else np.nan],
    })


def demography_inconsistencies(df: pd.DataFrame, year: str = "ANO") -> pd.DataFrame:
    """Gestante com sexo M e gestante com < 10 anos, por ano."""
    pregnant = code(df["CS_GESTANT"]).isin(GESTANTE_SIM)
    male = code(df["CS_SEXO"]) == "M"
    young = decode_age_years(df["NU_IDADE_N"]) < 10
    return pd.DataFrame({
        "gestante (1–4)": pregnant.groupby(df[year]).sum(),
        "gestante com sexo M": (pregnant & male).groupby(df[year]).sum(),
        "gestante com < 10 anos": (pregnant & young).groupby(df[year]).sum(),
    })


def ignored_share(df: pd.DataFrame, columns: list[str], ignored: set[str],
                  year: str = "ANO") -> pd.DataFrame:
    """% de ignorado (códigos dados) + branco por campo e ano (Q-05)."""
    rows = {}
    for column in columns:
        values = code(df[column])
        rows[column] = (values.isna() | values.isin(ignored)).groupby(df[year]).mean() * 100
    return pd.DataFrame(rows).T


def absent_share(df: pd.DataFrame, columns: list[str], year: str = "ANO") -> pd.DataFrame:
    """% ausente (branco ou ≠ 1/2) por campo e ano."""
    return pd.DataFrame({
        column: (~code(df[column]).isin({"1", "2"})).groupby(df[year]).mean() * 100
        for column in columns
    }).T


def alarm_filled_by_class(df: pd.DataFrame, alarm_columns: list[str]) -> pd.DataFrame:
    """% de linhas com algum ALRM_* preenchido, por valor de CLASSI_FIN (§3.6, M2)."""
    filled = pd.concat([code(df[c]).notna() for c in alarm_columns], axis=1).any(axis=1)
    classi = code(df["CLASSI_FIN"]).fillna(BRANCO)
    table = pd.DataFrame({
        "linhas": filled.groupby(classi).size(),
        "com algum ALRM_* preenchido": filled.groupby(classi).sum(),
    })
    table["%"] = 100 * table["com algum ALRM_* preenchido"] / table["linhas"]
    table.index.name = "CLASSI_FIN"
    return table


def notification_delay(df: pd.DataFrame, year: str = "ANO") -> pd.DataFrame:
    """Atraso sintomas → notificação, em dias, por ano (passo 8)."""
    onset, notified = parse_date(df["DT_SIN_PRI"]), parse_date(df["DT_NOTIFIC"])
    delay = (notified - onset).dt.days
    grouped = delay.groupby(df[year])
    return pd.DataFrame({
        "com as duas datas": grouped.count(),
        "sintomas > notificação": (delay < 0).groupby(df[year]).sum(),
        "mediana": grouped.median(),
        "p95": grouped.quantile(0.95),
        "p99": grouped.quantile(0.99),
        "máx": grouped.max(),
        "> 60 dias": (delay > 60).groupby(df[year]).sum(),
    })


def date_year_vs_file(df: pd.DataFrame, column: str, year: str = "ANO") -> pd.DataFrame:
    """Ano civil de uma data × ano do arquivo — define qual data marca o ano do split."""
    date_year = parse_date(df[column]).dt.year.astype("Int64").astype("string").fillna(BRANCO)
    table = pd.crosstab(date_year, df[year])
    table.index.name = f"ano de {column}"
    return table


def duplicates(pop: pd.DataFrame, year: str = "ANO") -> pd.DataFrame:
    """Duplicatas pela chave composta do roteiro (passo 9), com desfechos conflitantes.

    Chave: nascimento + sexo + município de residência + data dos sintomas. Nascimento usa
    DT_NASC se existir, senão ANO_NASC + idade (os públicos só têm o ano), senão a idade.
    """
    idade = "idade:" + code(pop["NU_IDADE_N"]).fillna(BRANCO)
    ano_nasc = code(optional(pop, "ANO_NASC"))
    birth = code(optional(pop, "DT_NASC")).fillna("ano:" + ano_nasc + "|" + idade).fillna(idade)
    key = (birth + "|" + code(pop["CS_SEXO"]).fillna(BRANCO) + "|"
           + code(optional(pop, "ID_MN_RESI")).fillna(BRANCO) + "|"
           + code(pop["DT_SIN_PRI"]).fillna(BRANCO))
    group_size = key.map(key.value_counts())
    in_dup = group_size > 1
    y_spread = pop["y"].groupby(key).transform("nunique")
    return pd.DataFrame({
        "linhas": pop.groupby(year).size(),
        "linhas em grupo duplicado": in_dup.groupby(pop[year]).sum(),
        "% em grupo duplicado": 100 * in_dup.groupby(pop[year]).mean(),
        "linhas excedentes (remoção manteria 1)": (in_dup & key.duplicated()).groupby(
            pop[year]).sum(),
        "linhas em grupos com y conflitante": (y_spread > 1).groupby(pop[year]).sum(),
    })


def cases_by_uf(pop: pd.DataFrame, population: pd.Series | None = None,
                year: str = "ANO") -> pd.DataFrame:
    """Casos confirmados por UF de residência e ano; por 100 mil hab. se houver população."""
    uf = code(pop["SG_UF"]).fillna(BRANCO)
    table = pd.crosstab(uf, pop[year])
    table.index.name = "SG_UF (residência)"
    if population is not None:
        rate = table.div(population.reindex(table.index), axis=0) * 100_000
        table = table.join(rate.add_prefix("por 100 mil — "))
    return table


def markdown_table(table: pd.DataFrame, decimals: int = 1) -> str:
    """Tabela Markdown sem dependências extras (tabulate)."""
    frame = table.reset_index() if not isinstance(table.index, pd.RangeIndex) else table

    def fmt(value) -> str:
        if isinstance(value, float | np.floating):
            return "" if np.isnan(value) else f"{value:,.{decimals}f}".replace(",", " ")
        if isinstance(value, int | np.integer):
            return f"{value:,}".replace(",", " ")
        return str(value)

    header = "| " + " | ".join(str(c) for c in frame.columns) + " |"
    rule = "|" + "|".join("---" for _ in frame.columns) + "|"
    body = ["| " + " | ".join(fmt(v) for v in row) + " |" for row in frame.itertuples(index=False)]
    return "\n".join([header, rule, *body])
