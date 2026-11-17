"""Gráficos do SHAP global (T-4.8, D-66): desenhados localmente a partir dos agregados em texto.

Lê só `shap_importancia.csv`, `shap_interacoes.csv` e o manifesto JSON de `shap_global.py`. Não
carrega modelo nem dados. Antes de desenhar, confere o SHA-256 de cada CSV com o manifesto: um
arquivo alterado ou trocado não vira gráfico.

Legenda obrigatória em todo gráfico: o SHAP explica o modelo, não causa, e fica instável com
features correlacionadas (spec › Interpretabilidade e equidade; P6).
"""

from __future__ import annotations

import csv
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from dengue_sinan import shap_global

LEGENDA = "Explica o modelo, não causa; instável com features correlacionadas."
ARQ_IMPORTANCIA_PNG = "shap_importancia.png"
ARQ_INTERACOES_PNG = "shap_interacoes.png"


def _ler_importancia(caminho: Path) -> tuple[list[str], list[float]]:
    with open(caminho, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    return ([linha["feature"] for linha in linhas],
            [float(linha["media_abs_shap"]) for linha in linhas])


def _ler_interacoes(caminho: Path) -> tuple[list[str], list[list[float]]]:
    with open(caminho, encoding="utf-8") as f:
        linhas = list(csv.reader(f))
    nomes = linhas[0][1:]
    return nomes, [[float(v) for v in linha[1:]] for linha in linhas[1:]]


def _legenda(figura: Figure) -> None:
    """Legenda obrigatória no pé do gráfico, com espaço reservado (o layout não conta fig.text)."""
    figura.tight_layout(rect=(0, 0.05, 1, 1))
    figura.text(0.01, 0.015, LEGENDA, fontsize=8, color="#555555")


def _salvar(figura: Figure, caminho: Path) -> Path:
    FigureCanvasAgg(figura)
    figura.savefig(caminho, dpi=120)
    return caminho


def desenhar(out_dir: str | Path) -> list[Path]:
    """Grava `shap_importancia.png` (barras, média do |SHAP|) e `shap_interacoes.png` (mapa de
    calor, média do |interação|) em `out_dir`. Levanta ValueError se o SHA-256 não bater."""
    out = Path(out_dir)
    manifesto = shap_global.carregar_manifesto(out)
    if not shap_global.arquivos_conferem(out, manifesto):
        raise ValueError(f"agregados de SHAP em {out} não conferem com o manifesto (SHA-256)")

    feats, valores = _ler_importancia(out / shap_global.ARQ_IMPORTANCIA)
    ordem = sorted(range(len(feats)), key=lambda i: valores[i])  # menor no topo do gráfico
    figura = Figure(figsize=(8, 0.32 * len(feats) + 1.8))
    eixo = figura.add_subplot()
    eixo.barh([feats[i] for i in ordem], [valores[i] for i in ordem], color="#3b6ea5")
    eixo.set_xlabel(f"média do |SHAP| em {manifesto['unidade']}")
    eixo.set_title(f"SHAP global: {manifesto['modelo']}, amostra de {manifesto['n_amostra']}")
    _legenda(figura)
    caminho_imp = _salvar(figura, out / ARQ_IMPORTANCIA_PNG)

    nomes, matriz = _ler_interacoes(out / shap_global.ARQ_INTERACOES)
    figura = Figure(figsize=(8, 7.2))
    eixo = figura.add_subplot()
    imagem = eixo.imshow(matriz, cmap="viridis")
    figura.colorbar(imagem, ax=eixo, label="média do |interação SHAP|", fraction=0.046)
    eixo.set_xticks(range(len(nomes)), nomes, rotation=90, fontsize=7)
    eixo.set_yticks(range(len(nomes)), nomes, fontsize=7)
    eixo.set_title("Interações SHAP (diagonal = efeito principal)")
    _legenda(figura)
    caminho_int = _salvar(figura, out / ARQ_INTERACOES_PNG)
    return [caminho_imp, caminho_int]
