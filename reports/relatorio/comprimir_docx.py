"""Passo depois de `gerar_docx.js`: reduz os PNG embutidos no .docx para paleta de 256 cores.

Motivo: o teste do R7 (`tests/test_dados_fora_do_git.py`) recusa arquivo rastreado com mais de
1.000.000 bytes, e as 12 figuras sem compressão deixam o relatório com ~1,2 MB. A paleta mantém o
tamanho em pixels e reduz a profundidade de cor (sem dithering). Até ~2% dos pixels mudam de cor,
nos contornos suavizados, o que não afeta a leitura de gráficos de linhas e barras.

Uso:
    python reports/relatorio/comprimir_docx.py [entrada.docx] [saida.docx]
Padrão: relatorio.docx, na pasta deste script, regravado no lugar. Um PNG só é trocado se ficar
menor.
"""

from __future__ import annotations

import io
import sys
import zipfile
from pathlib import Path

from PIL import Image

PADRAO = Path(__file__).with_name("relatorio.docx")


def comprimir_png(dados: bytes) -> bytes:
    """Devolve o PNG em paleta de 256 cores, ou o original se não ficar menor."""
    with Image.open(io.BytesIO(dados)) as im:
        # Transparência de verdade não cabe neste esquema: a imagem fica como está. O canal alfa
        # totalmente opaco (caso do matplotlib) é descartado.
        if "A" in im.getbands() and im.getchannel("A").getextrema()[0] < 255:
            return dados
        paleta = im.convert("RGB").quantize(
            256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
        )
    saida = io.BytesIO()
    paleta.save(saida, format="PNG", optimize=True)
    novo = saida.getvalue()
    return novo if len(novo) < len(dados) else dados


def comprimir_docx(entrada: Path, saida: Path) -> tuple[int, int]:
    """Regrava o .docx com os PNG de `word/media/` comprimidos. Devolve (antes, depois) em bytes."""
    antes = entrada.stat().st_size
    buffer = io.BytesIO()
    with zipfile.ZipFile(entrada) as origem, zipfile.ZipFile(
        buffer, "w", zipfile.ZIP_DEFLATED
    ) as destino:
        for item in origem.infolist():
            dados = origem.read(item.filename)
            if item.filename.startswith("word/media/") and item.filename.lower().endswith(".png"):
                dados = comprimir_png(dados)
            destino.writestr(item, dados)
    saida.write_bytes(buffer.getvalue())
    return antes, saida.stat().st_size


def main(argv: list[str]) -> int:
    entrada = Path(argv[1]) if len(argv) > 1 else PADRAO
    saida = Path(argv[2]) if len(argv) > 2 else entrada
    antes, depois = comprimir_docx(entrada, saida)
    print(f"OK {saida} {antes} -> {depois} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
