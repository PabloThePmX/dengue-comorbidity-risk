import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")
from conftest_sint import bruto_sintetico  # noqa: E402

from dengue_sinan.dataset import (
    FEATURES_M1,
    adicionar_pares,
    checar_dominios_alvo,  # noqa: E402
    completos_para_e1,
    matriz_arvore,
    montar_features,
    montar_populacao,
    tres_niveis,
)


def test_tres_niveis():
    r = tres_niveis(pd.Series(["1", "2", None, "9", "", "1.0"], dtype="object"))
    assert list(r) == ["Sim", "Não", "Ausente", "Ausente", "Ausente", "Sim"]


def test_populacao_e_features():
    pop = montar_populacao(bruto_sintetico(), 2022)
    assert set(pop["y"].unique()) <= {0, 1} and pop["y"].sum() > 0
    x = montar_features(pop)
    assert list(x.columns) == FEATURES_M1
    assert x["dias_ate_notificacao"].between(0, 60).all()
    soma = sum(
        (x[c] == "Sim").astype(int)
        for c in [
            "DIABETES",
            "HEMATOLOG",
            "HEPATOPAT",
            "RENAL",
            "HIPERTENSA",
            "ACIDO_PEPT",
            "AUTO_IMUNE",
        ]
    )
    assert (soma == x["n_comorbidades"]).all()
    assert len(adicionar_pares(x).columns) == len(x.columns) + 21
    m = matriz_arvore(x)
    assert m["RENAL"].isin([0, 1, 2]).all()
    assert completos_para_e1(pop, x).dtype == bool


def test_populacao_exclui_rotulo_desconhecido():
    raw = bruto_sintetico()
    pop = montar_populacao(raw, 2022)
    # dengue grave (12) entra com qualquer evolução; 10/11 só com evolução 1/2
    assert set(pop["CLASSI_FIN"].astype(str)) <= {"10", "11", "12"}
    leves = pop[pop["CLASSI_FIN"].astype(str) != "12"]
    assert set(leves["EVOLUCAO"].astype(str)) <= {"1", "2"}


def test_check_bloqueante_classi_fin_1():
    raw = bruto_sintetico(n=500)
    raw.loc[0, "CLASSI_FIN"] = "1"  # código do dicionário de 2024: muda a definição do alvo
    with pytest.raises(ValueError, match="CLASSI_FIN"):
        checar_dominios_alvo(raw, 2022)
    assert checar_dominios_alvo(bruto_sintetico(n=500), 2022)["ano"] == 2022


def test_nan_atraso_arvore():
    x = montar_features(montar_populacao(bruto_sintetico(n=2000), 2022))
    x.loc[x.index[0], "dias_ate_notificacao"] = np.nan
    assert matriz_arvore(x, dias_nan=-1.0)["dias_ate_notificacao"].iloc[0] == -1.0
