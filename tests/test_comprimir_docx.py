"""Testes do pós-processamento que reduz as imagens do relatório (.docx)."""

from __future__ import annotations

import importlib.util
import io
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location(
    "comprimir_docx", RAIZ / "reports" / "relatorio" / "comprimir_docx.py"
)
comprimir = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(comprimir)


def _png(modo: str = "RGB", tamanho=(300, 200)) -> bytes:
    rng = np.random.default_rng(0)
    ruido = rng.integers(0, 256, size=(tamanho[1], tamanho[0], 3), dtype=np.uint8)
    im = Image.fromarray(ruido, "RGB").convert(modo)
    b = io.BytesIO()
    im.save(b, "PNG")
    return b.getvalue()


def _docx(caminho: Path, midia: dict[str, bytes]) -> None:
    with zipfile.ZipFile(caminho, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("word/document.xml", "<w:document>texto</w:document>")
        for nome, dados in midia.items():
            z.writestr(nome, dados)


def test_png_fica_menor_e_com_o_mesmo_tamanho_em_pixels():
    original = _png()
    novo = comprimir.comprimir_png(original)
    assert len(novo) < len(original)
    assert Image.open(io.BytesIO(novo)).size == (300, 200)


def test_png_com_transparencia_de_verdade_fica_como_esta():
    rng = np.random.default_rng(1)
    pixels = rng.integers(0, 256, size=(200, 300, 4), dtype=np.uint8)
    pixels[..., 3] = 128
    b = io.BytesIO()
    Image.fromarray(pixels, "RGBA").save(b, "PNG")
    assert comprimir.comprimir_png(b.getvalue()) == b.getvalue()


def test_png_rgba_totalmente_opaco_e_comprimido():
    original = _png("RGBA")  # alfa 255 em todos os pixels, como o matplotlib grava
    novo = comprimir.comprimir_png(original)
    assert len(novo) < len(original)


def test_docx_regravado_mantem_o_texto_e_reduz_so_o_png(tmp_path):
    entrada, saida = tmp_path / "in.docx", tmp_path / "out.docx"
    png = _png()
    _docx(entrada, {"word/media/a.png": png, "word/media/b.jpg": b"jpegbytes"})
    antes, depois = comprimir.comprimir_docx(entrada, saida)
    assert depois < antes
    with zipfile.ZipFile(saida) as z:
        assert z.read("word/document.xml") == b"<w:document>texto</w:document>"
        assert z.read("word/media/b.jpg") == b"jpegbytes"
        assert len(z.read("word/media/a.png")) < len(png)


def test_regravar_no_lugar_funciona(tmp_path):
    arquivo = tmp_path / "r.docx"
    _docx(arquivo, {"word/media/a.png": _png()})
    antes, depois = comprimir.comprimir_docx(arquivo, arquivo)
    assert depois < antes
    assert zipfile.is_zipfile(arquivo)
