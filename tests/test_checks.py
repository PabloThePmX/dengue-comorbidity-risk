import pandas as pd
import pytest

from dengue_sinan import checks
from dengue_sinan.profiling import COMORBIDADES


def _df(n: int = 1, **colunas) -> pd.DataFrame:
    """Uma linha padrão (dengue 10, evolução cura) repetida n vezes; colunas podem sobrescrever."""
    base = {"ANO": 2022, "CLASSI_FIN": "10", "EVOLUCAO": "1", "CS_SEXO": "F",
            "CS_GESTANT": "5", "SG_UF": "31", "DT_SIN_PRI": "20220110",
            "DT_NOTIFIC": "20220112", **{c: "2" for c in COMORBIDADES}}
    base.update(colunas)
    return pd.DataFrame({c: [v] * n if not isinstance(v, list) else v
                         for c, v in base.items()})


def test_check_columns_bloqueia_coluna_faltando():
    with pytest.raises(ValueError, match="DIABETES"):
        checks.check_columns(["CLASSI_FIN"], ["CLASSI_FIN", "DIABETES"], 2022)
    checks.check_columns(["CLASSI_FIN", "DIABETES"], ["CLASSI_FIN", "DIABETES"], 2022)


def test_check_domains_aceita_dominio_e_branco():
    checks.check_domains(_df(2, CLASSI_FIN=["0", "8"], EVOLUCAO=["9", None]))


def test_check_domains_bloqueia_valor_novo_em_classi_fin():
    # "1" (confirmado, codificação de 2024) não aparece nos públicos: falha.
    with pytest.raises(ValueError, match="CLASSI_FIN"):
        checks.check_domains(_df(CLASSI_FIN="1"))


def test_check_domains_bloqueia_evolucao_fora_do_dominio():
    with pytest.raises(ValueError, match="EVOLUCAO"):
        checks.check_domains(_df(EVOLUCAO="7"))


def test_alertas_contam_sem_levantar():
    df = _df(DT_SIN_PRI="20220115", DT_NOTIFIC="20220110", CS_GESTANT="1", CS_SEXO="M")
    por_nome = {a["alerta"]: a for a in checks.quality_alerts(df)}
    assert por_nome["DT_SIN_PRI > DT_NOTIFIC"]["linhas"] == 1
    assert por_nome["gestante com sexo M"]["linhas"] == 1


def test_alerta_de_ignorado_passa_de_metade_numa_uf_e_ano():
    df = pd.DataFrame({
        "ANO": [2022, 2022, 2022, 2022],
        "SG_UF": ["31", "31", "31", "35"],
        "DIABETES": ["9", None, "1", "9"],
        **{c: ["2"] * 4 for c in COMORBIDADES if c != "DIABETES"},
        "CLASSI_FIN": ["10"] * 4, "EVOLUCAO": ["1"] * 4, "CS_SEXO": ["F"] * 4,
        "CS_GESTANT": ["5"] * 4, "DT_SIN_PRI": ["20220110"] * 4, "DT_NOTIFIC": ["20220112"] * 4,
    })
    por_nome = {a["alerta"]: a for a in checks.quality_alerts(df)}
    # UF 31: 2 de 3 ignorados (> 50%); UF 35: 1 de 1 ignorado. Dois grupos UF × ano.
    assert por_nome["ignorado > 50% em DIABETES, por UF e ano"]["grupos_uf_ano"] == 2
