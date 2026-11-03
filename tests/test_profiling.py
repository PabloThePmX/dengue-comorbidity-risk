import pandas as pd
import pytest

from dengue_sinan import profiling as pf


@pytest.fixture
def cases() -> pd.DataFrame:
    return pd.DataFrame({
        "ANO": [2022, 2022, 2022, 2022, 2023, 2023],
        "CLASSI_FIN": ["10", "12", "5", "11", "10", None],
        "EVOLUCAO": ["1", "1", "1", "9", "2", "1"],
        "DIABETES": ["1", "2", None, "1", "9", "2"],
    })


def test_target_is_severe_or_death(cases):
    assert pf.target(cases).tolist() == [0, 1, 0, 0, 1, 0]


def test_population_keeps_dengue_with_known_outcome(cases):
    assert pf.population_mask(cases).tolist() == [True, True, False, False, True, False]


def test_exclusion_flow_counts_per_year(cases):
    flow = pf.exclusion_flow(cases)
    assert flow[2022].tolist() == [4, 3, 2]
    assert flow[2023].tolist() == [2, 1, 1]


def test_counts_by_year_shows_blank():
    df = pd.DataFrame({"ANO": [2022, 2022], "X": ["1", None]})
    table = pf.counts_by_year(df, "X")
    assert table.loc[pf.BRANCO, 2022] == 1


def test_code_normalizes_float_text_and_blank():
    assert pf.code(pd.Series(["10.0", " 12 ", ""])).tolist()[:2] == ["10", "12"]
    assert pd.isna(pf.code(pd.Series([""])).iloc[0])


def test_absent_by_target_ratio(cases):
    pop = cases[pf.population_mask(cases)].assign(y=lambda d: pf.target(d))
    table = pf.absent_by_target(pop, ["DIABETES"])
    # y=0: DIABETES "1" → presente; y=1: "2" e "9" → 1 de 2 ausente.
    assert table.loc["DIABETES", "% ausente y=0"] == 0
    assert table.loc["DIABETES", "% ausente y=1"] == 50


def test_domain_counts_buckets_outside_values(cases):
    table = pf.domain_counts(cases, ["DIABETES"])
    assert table.loc[("DIABETES", "outros"), 2023] == 1
    assert table.loc[("DIABETES", pf.BRANCO), 2022] == 1


def test_notification_delay_flags_negative():
    df = pd.DataFrame({
        "ANO": [2022, 2022],
        "DT_SIN_PRI": ["20220110", "20220120"],
        "DT_NOTIFIC": ["20220112", "20220115"],
    })
    table = pf.notification_delay(df)
    assert table.loc[2022, "sintomas > notificação"] == 1
    assert table.loc[2022, "máx"] == 2


def test_duplicates_detects_conflicting_outcome():
    pop = pd.DataFrame({
        "ANO": [2022] * 3,
        "DT_NASC": ["19800101", "19800101", "19900101"],
        "NU_IDADE_N": ["4042", "4042", "4032"],
        "CS_SEXO": ["F", "F", "M"],
        "ID_MN_RESI": ["355030"] * 3,
        "DT_SIN_PRI": ["20220110"] * 3,
        "y": [0, 1, 0],
    })
    table = pf.duplicates(pop)
    assert table.loc[2022, "linhas em grupo duplicado"] == 2
    assert table.loc[2022, "linhas excedentes (remoção manteria 1)"] == 1
    assert table.loc[2022, "linhas em grupos com y conflitante"] == 2


def test_duplicates_without_dt_nasc_uses_birth_year_and_age():
    # Como nos microdados públicos: sem DT_NASC, só ANO_NASC.
    pop = pd.DataFrame({
        "ANO": [2022] * 3,
        "ANO_NASC": ["1980", "1980", "1980"],
        "NU_IDADE_N": ["4042", "4042", "4041"],
        "CS_SEXO": ["F", "F", "F"],
        "ID_MN_RESI": ["355030"] * 3,
        "DT_SIN_PRI": ["20220110"] * 3,
        "y": [0, 0, 0],
    })
    table = pf.duplicates(pop)
    assert table.loc[2022, "linhas em grupo duplicado"] == 2  # a 3ª tem outra idade


def test_age_vs_birth_year_tolerates_one_year():
    df = pd.DataFrame({
        "NU_IDADE_N": ["4041", "4042", "4030", "4040"],
        "ANO_NASC": ["1980", "1980", "1980", None],
        "DT_SIN_PRI": ["20220110"] * 4,  # 2022 − 1980 = 42
    })
    table = pf.age_vs_birth_year(df)
    assert table["linhas com ANO_NASC e idade"].iloc[0] == 3
    assert table["concordam (|dif| ≤ 1 ano)"].iloc[0] == 2  # 41 e 42 concordam; 30 não


def test_optional_missing_column_is_blank():
    df = pd.DataFrame({"A": [1, 2]})
    assert pf.optional(df, "DT_NASC").isna().all()
    assert len(pf.optional(df, "DT_NASC")) == 2


def test_markdown_table_formats_numbers():
    md = pf.markdown_table(pd.DataFrame({"a": [1234], "b": [0.5]}))
    assert "| 1 234 | 0.5 |" in md
