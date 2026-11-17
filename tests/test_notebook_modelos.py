"""Conferências do notebook de modelos (T-4.3b): JSON válido, sem saídas, instalação pelo lock e
nenhuma chamada de treino. O notebook só instala e dispara o runner; o trabalho fica em `src/`."""

import json
import re
from pathlib import Path

NOTEBOOK = Path(__file__).resolve().parents[1] / "notebooks" / "04_modelos.ipynb"
CHAMADA_DE_TREINO = re.compile(r"\b(run_all_models|tune|fit)\s*\(")


def _nb() -> dict:
    return json.loads(NOTEBOOK.read_text(encoding="utf-8"))


def _linhas_de_codigo() -> list[str]:
    linhas = []
    for celula in _nb()["cells"]:
        if celula["cell_type"] == "code":
            linhas.extend("".join(celula["source"]).splitlines())
    return linhas


def test_json_valido_e_nbformat_4():
    nb = _nb()
    assert nb["nbformat"] == 4
    assert nb["cells"]


def test_nenhuma_celula_de_codigo_tem_saida():
    for celula in _nb()["cells"]:
        if celula["cell_type"] == "code":
            assert celula["outputs"] == []
            assert celula["execution_count"] is None


def test_instalacao_do_ambiente_vem_do_lock():
    codigo = "\n".join(_linhas_de_codigo())
    assert "uv export --frozen" in codigo
    assert "pip install -q -r /content/requirements-lock.txt" in codigo


def test_instalacao_do_projeto_nao_resolve_dependencias():
    for linha in _linhas_de_codigo():
        if re.search(r"pip install -q -e \.", linha):
            assert "--no-deps" in linha, linha


def test_checa_versao_do_python_antes_de_instalar():
    codigo = "\n".join(_linhas_de_codigo())
    assert "assert sys.version_info[:2] == (3, 13)" in codigo
    assert codigo.index("assert sys.version_info") < codigo.index("uv export --frozen")


def test_notebook_nao_contem_chamada_de_treino():
    for linha in _linhas_de_codigo():
        assert not CHAMADA_DE_TREINO.search(linha), linha
