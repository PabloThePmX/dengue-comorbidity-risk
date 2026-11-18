"""Etapa 1C — o verificador do hash do lacre lê só bytes e explica a divergência de CRLF."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "reports/etapa1/j2_reproducao_v1/verificar_hash_lacre.py"


def _carregar():
    spec = importlib.util.spec_from_file_location("verif", SCRIPT)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _montar(tmp_path, crlf: bool):
    (tmp_path / "tabelas").mkdir()
    obj = {"b": 1, "a": [0.5, "ção"], "n": None}
    txt = json.dumps(obj, indent=2, ensure_ascii=False, default=float)
    escrito = txt.replace("\n", "\r\n") if crlf else txt
    h = hashlib.sha256(txt.replace("\n", "\r\n").encode()).hexdigest()
    (tmp_path / "LACRE_TESTE_2024.json").write_text(json.dumps({"sha256_resultados": h}), "utf-8")
    (tmp_path / "tabelas" / "teste_2024_resultados.json").write_bytes(txt.encode("utf-8"))
    return escrito


def test_explica_divergencia_por_crlf(tmp_path):
    _montar(tmp_path, crlf=False)
    r = _carregar().investigar(tmp_path)
    assert r["explica_a_divergencia"] and r["arquivo_atual_tem_CRLF"] is False
    assert r["variantes_que_reproduzem_o_hash_do_lacre"][0]["quebra_de_linha"] == "CRLF"


def test_nao_inventa_explicacao_quando_o_conteudo_difere(tmp_path):
    _montar(tmp_path, crlf=False)
    (tmp_path / "tabelas" / "teste_2024_resultados.json").write_text('{"x": 1}', "utf-8")
    r = _carregar().investigar(tmp_path)
    assert (
        r["explica_a_divergencia"] is False and r["variantes_que_reproduzem_o_hash_do_lacre"] == []
    )


def test_nao_altera_arquivos(tmp_path):
    _montar(tmp_path, crlf=False)
    antes = {p: p.read_bytes() for p in tmp_path.rglob("*.json")}
    _carregar().investigar(tmp_path)
    assert antes == {p: p.read_bytes() for p in tmp_path.rglob("*.json")}


@pytest.mark.skipif(
    not (RAIZ / "reports/modelo_risco_dengue/LACRE_TESTE_2024.json").exists(),
    reason="sem artefatos",
)
def test_artefatos_historicos_reais_confirmam_o_crlf():
    r = _carregar().investigar()
    assert r["explica_a_divergencia"] is True
