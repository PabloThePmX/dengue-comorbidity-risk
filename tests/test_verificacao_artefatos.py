"""Checks da T-3.6 contra a seção `e1` de config/esperado.yaml (dados sintéticos, sem bundle).

A verificação completa (`executar`) precisa de `data/e1/` e do subprocesso sem statsmodels; aqui
testa-se só a comparação, que é a parte que não pode ter número escrito no código.
"""

from dengue_sinan import explain
from dengue_sinan import verificacao_artefatos as va


def _descricao(parametros: int = 44, pares: int = 15) -> dict:
    # Mesmo formato do e1.json: `colunas` tem o tamanho de `params` (artifacts.load_e1).
    return {"colunas": [f"c{i}" for i in range(parametros)],
            "pares_incluidos": [[f"a{i}", f"b{i}"] for i in range(pares)]}


def test_checks_passam_com_o_esperado_real_do_yaml():
    checks = va._checks_esperado_e1(explain.ler_esperado_e1(), _descricao())
    assert [c["nome"] for c in checks] == ["parametros_no_bundle", "pares_incluidos_no_bundle"]
    assert all(c["passou"] for c in checks)
    assert checks[0]["esperado"] == 44 and checks[1]["esperado"] == 15


def test_mudar_parametros_no_esperado_reprova_so_esse_check():
    esperado = {**explain.ler_esperado_e1(), "parametros": 45}
    checks = {c["nome"]: c for c in va._checks_esperado_e1(esperado, _descricao())}
    assert checks["parametros_no_bundle"]["passou"] is False
    assert checks["parametros_no_bundle"]["esperado"] == 45
    assert checks["pares_incluidos_no_bundle"]["passou"] is True


def test_mudar_pares_incluidos_no_esperado_reprova_so_esse_check():
    esperado = {**explain.ler_esperado_e1(), "pares_incluidos": 14}
    checks = {c["nome"]: c for c in va._checks_esperado_e1(esperado, _descricao())}
    assert checks["pares_incluidos_no_bundle"]["passou"] is False
    assert checks["parametros_no_bundle"]["passou"] is True


def test_bundle_com_outro_numero_de_parametros_reprova():
    checks = {c["nome"]: c for c in va._checks_esperado_e1(
        explain.ler_esperado_e1(), _descricao(parametros=43))}
    assert checks["parametros_no_bundle"]["passou"] is False
    assert checks["parametros_no_bundle"]["obtido"] == 43
