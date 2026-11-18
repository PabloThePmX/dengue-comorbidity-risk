"""Etapa 1B — J7 (busca determinística) e J8 (guarda R1 obrigatória). Só dados sintéticos."""

import json
import warnings

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("sklearn")
pytest.importorskip("statsmodels")
from conftest_sint import bruto_sintetico  # noqa: E402

from dengue_sinan import modelos as MD  # noqa: E402
from dengue_sinan.dataset import (  # noqa: E402
    empilhar_populacoes,
    montar_features,
    montar_populacao,
)
from dengue_sinan.guard import (  # noqa: E402
    anos_marcados,
    marcar_anos,
    verificar_dev,
)

PARAMS_EN = {"C": 0.1, "l1_ratio": 0.5, "max_iter": 100}


@pytest.fixture(scope="module")
def dev():
    p22 = montar_populacao(bruto_sintetico(n=15_000, ano=2022, seed=11), 2022)
    p23 = montar_populacao(bruto_sintetico(n=15_000, ano=2023, seed=12), 2023)
    pop = empilhar_populacoes([p22, p23])
    return pop, montar_features(pop)


@pytest.fixture(scope="module")
def teste_2024():
    pop = montar_populacao(bruto_sintetico(n=8_000, ano=2024, seed=13), 2024)
    return pop, montar_features(pop)


# ------------------------------------------------------------------ marca viaja com os dados
def test_marca_de_origem_propaga_por_montagem_e_fatiamento(dev, teste_2024):
    pop, x = dev
    assert anos_marcados(pop) == {2022, 2023}
    assert anos_marcados(x) == {2022, 2023}
    assert anos_marcados(x.iloc[:100]) == {2022, 2023}
    assert anos_marcados(pop["regiao"]) == {2022, 2023}
    assert anos_marcados(teste_2024[1]) == {2024}


# ------------------------------------------------------------------ 1. bloquear 2024
def test_2024_e_bloqueado_em_todos_os_caminhos_de_desenvolvimento(teste_2024):
    pop, x = teste_2024
    y = pop["y"].to_numpy()
    reg = pop["regiao"]
    p = np.full(len(y), 0.01)
    chamadas = {
        "cv_oof": lambda: MD.cv_oof("elastic_net", PARAMS_EN, x, y, reg, seed=1),
        "busca_deterministica": lambda: MD.busca_deterministica(
            "elastic_net", [PARAMS_EN], x, y, reg, seed=1, max_configs=1
        ),
        "busca_hiperparametros": lambda: MD.busca_hiperparametros(
            "elastic_net", [PARAMS_EN], x, y, reg, 1, 10.0
        ),
        "calibrar_cruzado": lambda: MD.calibrar_cruzado(p, y, reg, "platt"),
        "escolher_calibrador": lambda: MD.escolher_calibrador(p, y, reg),
        "ajustar_final": lambda: MD.ajustar_final("elastic_net", PARAMS_EN, x, y, 1, None),
        "ModeloM1.ajustar": lambda: MD.ModeloM1("elastic_net", PARAMS_EN, 1).ajustar(x, y),
        "ModeloB1.ajustar": lambda: MD.ModeloB1().ajustar(x, y),
        "oof_b1": lambda: MD.oof_b1(x, y, reg),
        "oof_b0": lambda: MD.oof_b0(y, reg),
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        for nome, chamar in chamadas.items():
            with pytest.raises(PermissionError, match="R1"):
                chamar()
            assert nome  # mensagem de falha mostra qual caminho quebrou


def test_2024_misturado_ao_desenvolvimento_e_bloqueado(dev, teste_2024):
    misto = empilhar_populacoes([dev[0], teste_2024[0]])
    assert anos_marcados(misto) == {2022, 2023, 2024}
    with pytest.raises(PermissionError, match="R1"):
        verificar_dev(montar_features(misto))


# ------------------------------------------------------------------ 2. metadados incompatíveis
def test_metadados_incompativeis_sao_bloqueados(dev):
    pop, x = dev
    meta_2024 = pd.DataFrame({"ANO": np.full(len(x), 2024)})
    with pytest.raises(PermissionError, match="incompat"):  # marca dev, meta diz 2024
        verificar_dev(x, meta=meta_2024)
    with pytest.raises(PermissionError, match="incompat"):  # tamanhos diferentes
        verificar_dev(x, meta=pop[["ANO"]].iloc[:10])
    with pytest.raises(PermissionError, match="ANO"):  # meta sem a coluna ANO
        verificar_dev(x, meta=pd.DataFrame({"outra": range(len(x))}))
    assert verificar_dev(x, meta=pop[["ANO"]]) == {2022, 2023}


def test_sem_origem_declarada_falha_por_padrao(dev):
    pop, x = dev
    nu = x.copy()
    nu.attrs.clear()
    with pytest.raises(PermissionError, match="não declarada"):
        verificar_dev(nu)
    assert verificar_dev(nu, exigir_metadados=False) == set()
    assert verificar_dev(marcar_anos(nu, [2022])) == {2022}
    # `meta` com ANO substitui a marca
    assert verificar_dev(nu.iloc[:5].copy(), meta=pop[["ANO"]].iloc[:5]) == {2022}


def test_ano_fora_de_anos_dev_e_bloqueado(dev):
    _, x = dev
    nu = marcar_anos(x.copy(), [2021])
    with pytest.raises(PermissionError, match="R1"):
        verificar_dev(nu)


# ------------------------------------------------------------------ 3. chamadas obrigatórias
def test_guarda_e_chamada_por_dentro_das_funcoes(dev, monkeypatch):
    """Falha se alguém remover `verificar_dev` de um caminho de desenvolvimento (regressão)."""
    pop, x = dev
    y = pop["y"].to_numpy()
    reg = pop["regiao"]
    p = np.full(len(y), 0.01)
    visto = []
    original = MD.verificar_dev

    def espia(*a, **k):
        visto.append(k.get("contexto", ""))
        return original(*a, **k)

    monkeypatch.setattr(MD, "verificar_dev", espia)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        MD.calibrar_cruzado(p, y, reg, "platt")
        MD.escolher_calibrador(p, y, reg)
        MD.oof_b0(y, reg)
        MD.ModeloB1().ajustar(x, y)
        MD.ajustar_final("elastic_net", PARAMS_EN, x, y, 1, None)
    contextos = " | ".join(visto)
    for esperado in (
        "calibrar_cruzado",
        "escolher_calibrador",
        "oof_b0",
        "ModeloB1.ajustar",
        "ajustar_final",
        "ModeloM1.ajustar",
    ):
        assert esperado in contextos, f"guarda ausente em {esperado}"


# ------------------------------------------------------------------ 4. fluxos legítimos
def test_fluxo_legitimo_de_desenvolvimento_continua_funcionando(dev):
    pop, x = dev
    y = pop["y"].to_numpy()
    reg = pop["regiao"]
    r = MD.cv_oof("elastic_net", PARAMS_EN, x, y, reg, seed=1)
    ok = reg.notna().to_numpy()
    assert not np.isnan(r["oof"][ok]).any()
    assert not np.isnan(MD.oof_b1(x, y, reg)[ok]).any()
    tipo, tab = MD.escolher_calibrador(np.nan_to_num(r["oof"], nan=0.001), y, reg)
    assert tipo in {"nenhum", "platt", "isotonica"} and len(tab) == 3
    # `meta` explícita também vale (compatível com o uso da versão 1: x_meta com ANO)
    m = MD.ajustar_final("elastic_net", PARAMS_EN, x, y, 1, None, x_meta=pop[["ANO"]])
    assert m.prever(x.iloc[:10]).shape == (10,)


# ------------------------------------------------------------------ J7: busca determinística
GRADE = [
    {"C": 1.0, "l1_ratio": 0.5, "max_iter": 100},
    {"C": 0.1, "l1_ratio": 0.5, "max_iter": 100},
    {"C": 0.01, "l1_ratio": 0.5, "max_iter": 100},
]


def test_busca_deterministica_registra_e_nao_depende_do_relogio(dev, tmp_path, monkeypatch):
    pop, x = dev
    y = pop["y"].to_numpy()
    reg = pop["regiao"]
    import time as _t

    # relógio absurdo: se a busca consultasse o tempo para cortar a grade, o resultado mudaria
    monkeypatch.setattr(_t, "time", lambda: 1e12)
    a = MD.busca_deterministica(
        "elastic_net", GRADE, x, y, reg, seed=7, max_configs=2, registro_dir=tmp_path / "a"
    )
    monkeypatch.undo()
    b = MD.busca_deterministica(
        "elastic_net", GRADE, x, y, reg, seed=7, max_configs=2, registro_dir=tmp_path / "b"
    )
    assert a["tabela"]["status"].tolist() == ["executada", "executada", "nao_executada"]
    assert a["configs_avaliadas"] == 2 and a["configs_na_grade"] == 3
    pd.testing.assert_series_equal(
        a["tabela"]["pr_auc_media"], b["tabela"]["pr_auc_media"], check_names=False
    )
    assert a["melhor"]["config"] == b["melhor"]["config"]
    assert a["hash_grade"] == b["hash_grade"]

    grade = json.loads((tmp_path / "b" / "grade.json").read_text("utf-8"))
    assert grade["max_configs"] == 2 and grade["semente"] == 7
    assert [c["params"] for c in grade["configuracoes"]] == GRADE  # ordem declarada
    assert "PR-AUC" in grade["criterio_selecao"] and "menor índice" in grade["criterio_selecao"]
    exec_ = json.loads((tmp_path / "b" / "execucao.json").read_text("utf-8"))
    assert [e["status"] for e in exec_["configuracoes"]] == [
        "executada",
        "executada",
        "nao_executada",
    ]
    assert "motivo" in exec_["configuracoes"][2]
    assert (tmp_path / "b" / "execucao.csv").exists()


def test_busca_exige_limite_explicito_e_grade_valida(dev):
    pop, x = dev
    y, reg = pop["y"].to_numpy(), pop["regiao"]
    with pytest.raises(ValueError, match="max_configs"):
        MD.busca_deterministica("elastic_net", GRADE, x, y, reg, seed=1, max_configs=0)
    with pytest.raises(ValueError, match="grade"):
        MD.busca_deterministica("elastic_net", [], x, y, reg, seed=1, max_configs=1)


def test_busca_desempata_pelo_menor_indice(dev, monkeypatch):
    pop, x = dev
    y, reg = pop["y"].to_numpy(), pop["regiao"]
    fixo = {"oof": np.zeros(len(y)), "pr_auc_media": 0.5, "melhor_iter": [1], "tempo_s": 0.0}
    monkeypatch.setattr(MD, "cv_oof", lambda *a, **k: dict(fixo))
    r = MD.busca_deterministica("elastic_net", GRADE, x, y, reg, seed=1, max_configs=3)
    assert r["melhor"]["config"] == 0


def test_busca_antiga_emite_aviso_de_depreciacao(dev):
    pop, x = dev
    y, reg = pop["y"].to_numpy(), pop["regiao"]
    with pytest.warns(DeprecationWarning):
        MD.busca_hiperparametros("elastic_net", GRADE[:1], x, y, reg, 1, 100.0)
