"""Conferências do notebook de modelos (T-4.3b): JSON válido, sem saídas, instalação pelo lock e
nenhuma chamada de treino. O notebook só instala e dispara o runner; o trabalho fica em `src/`."""

import json
import re
from pathlib import Path

import pytest

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


def test_tabfm_instala_do_commit_fixo_do_config_sem_dependencias():
    """D-90: o tabfm vem do commit do config (o PyPI só tem a JAX), com --no-deps."""
    codigo = "\n".join(_linhas_de_codigo())
    assert "cfg['tabfm']['commit_pacote']" in codigo
    assert "git+https://github.com/google-research/tabfm.git@{commit_tabfm}" in codigo
    assert "tabfm==" not in codigo  # nada de PyPI
    (instalacao,) = [ln for ln in _linhas_de_codigo() if "{pacotes}" in ln]
    assert instalacao.startswith("!pip install") and "--no-deps" in instalacao


def test_notebook_nao_contem_chamada_de_treino():
    for linha in _linhas_de_codigo():
        assert not CHAMADA_DE_TREINO.search(linha), linha


# --- Célula de disparo e avisos (T-4.3b, incidente de 2026-11-17 no Colab) -------------------

def _celulas_de_codigo() -> list[str]:
    """Código de cada célula de código, na ordem do notebook (uma string por célula)."""
    return ["".join(c["source"]) for c in _nb()["cells"] if c["cell_type"] == "code"]


def _celula_de_disparo() -> str:
    (celula,) = [c for c in _celulas_de_codigo() if "subprocess.Popen(" in c]
    return celula


def test_disparo_usa_popen_em_processo_isolado_e_nao_bang_com_e_comercial():
    codigo = _celula_de_disparo()
    assert "subprocess.Popen(" in codigo
    assert "[sys.executable, '-m', 'dengue_sinan.runner', '--config', config_sessao]" in codigo
    for trecho in ("cwd=PASTA_REPO", "stderr=subprocess.STDOUT",
                   "stdin=subprocess.DEVNULL", "start_new_session=True"):
        assert trecho in codigo, trecho
    assert "open(LOG, 'a'" in codigo  # log aberto em modo de anexar
    for linha in _linhas_de_codigo():
        assert "nohup" not in linha, linha
        assert not re.search(r"^\s*!.*&\s*$", linha), linha


def test_disparo_confere_que_nao_ha_runner_vivo_antes_de_iniciar():
    codigo = _celula_de_disparo()
    assert "pgrep" in codigo and "assert not vivos" in codigo
    assert codigo.index("pgrep") < codigo.index("subprocess.Popen(")


def test_sys_path_recebe_o_src_logo_depois_da_instalacao_editavel():
    codigo = "\n".join(_linhas_de_codigo())
    linha = "sys.path.insert(0, f'{PASTA_REPO}/src')"
    assert linha in codigo
    assert codigo.index("pip install -q -e . --no-deps") < codigo.index(linha)
    assert codigo.index(linha) < codigo.index("from dengue_sinan import runner")


def test_uv_export_nao_imprime_o_lock_na_celula():
    linhas = _linhas_de_codigo()
    (i,) = [n for n, ln in enumerate(linhas) if "uv export --frozen" in ln]
    # o comando pode quebrar a linha com barra invertida; junta a continuação
    comando = linhas[i] + " " + linhas[i + 1].strip()
    assert " -q " in comando and "> /dev/null" in comando, comando


def test_aviso_sobre_interromper_fica_antes_do_disparo():
    celulas = _nb()["cells"]
    avisos = [i for i, c in enumerate(celulas)
              if c["cell_type"] == "markdown" and "Interromper" in "".join(c["source"])]
    assert len(avisos) == 1
    texto = "".join(celulas[avisos[0]]["source"])
    assert "Reiniciar sessão" in texto and "runner vivo" in texto
    disparo = [i for i, c in enumerate(celulas)
               if c["cell_type"] == "code" and "subprocess.Popen(" in "".join(c["source"])]
    assert avisos[0] < disparo[0]


def test_celula_de_disparo_executa_sem_segurar_a_saida(tmp_path, monkeypatch):
    """Roda a célula de verdade, com um `runner` falso no lugar do real: o Popen tem de devolver o
    controle na hora (não espera o filho) e o filho tem de rodar com o log como saída."""
    import subprocess
    import sys
    import time

    repo = tmp_path / "repo"
    (repo / "dengue_sinan").mkdir(parents=True)
    (repo / "dengue_sinan" / "__init__.py").write_text("", encoding="utf-8")
    (repo / "dengue_sinan" / "runner.py").write_text(
        "import sys, time\nprint('runner falso', sys.argv[1:], flush=True)\ntime.sleep(60)\n",
        encoding="utf-8")
    log = tmp_path / "logs" / "sessao.log"
    ambiente = {"PASTA_REPO": str(repo), "PASTA_DRIVE": str(tmp_path), "LOG": str(log),
                "config_sessao": "cfg.json", "os": __import__("os"), "sys": sys,
                "subprocess": subprocess}

    # pgrep só existe no Linux (Colab): aqui, sem ele, o teste fica com "nenhum runner vivo"
    real_run = subprocess.run
    def run_sem_runner(args, **kw):
        if args[:1] == ["pgrep"]:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="")
        return real_run(args, **kw)
    monkeypatch.setattr(subprocess, "run", run_sem_runner)

    inicio = time.monotonic()
    exec(compile(_celula_de_disparo(), "disparo", "exec"), ambiente)
    try:
        assert time.monotonic() - inicio < 20, "a célula ficou esperando o runner"
        assert ambiente["proc"].pid > 0
        # o filho escreve no log (saída herdada do arquivo, não da célula); espera até 30 s
        prazo = time.monotonic() + 30
        def escreveu() -> bool:
            return log.exists() and "runner falso" in log.read_text(encoding="utf-8")
        while time.monotonic() < prazo and not escreveu():
            time.sleep(0.2)
        assert escreveu()
    finally:
        ambiente["proc"].kill()
        ambiente["proc"].wait(timeout=30)


def test_disparo_recusa_se_ja_ha_runner_vivo(tmp_path, monkeypatch):
    import subprocess
    import sys

    def run_com_runner(args, **kw):
        return subprocess.CompletedProcess(args, 0, stdout="4242\n", stderr="")

    monkeypatch.setattr(subprocess, "run", run_com_runner)
    ambiente = {"PASTA_REPO": str(tmp_path), "PASTA_DRIVE": str(tmp_path),
                "LOG": str(tmp_path / "x.log"), "config_sessao": "cfg.json",
                "os": __import__("os"), "sys": sys, "subprocess": subprocess}
    with pytest.raises(AssertionError, match="já está vivo"):
        exec(compile(_celula_de_disparo(), "disparo", "exec"), ambiente)
    assert "proc" not in ambiente  # nada foi disparado
