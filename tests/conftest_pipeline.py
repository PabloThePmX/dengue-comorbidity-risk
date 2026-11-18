"""Fixtures do pipeline com dados SINTÉTICOS (nunca são dados do SINAN)."""

import sys
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from conftest_sint import bruto_sintetico  # noqa: E402

from dengue_sinan.pipeline.contrato import RAIZ  # noqa: E402
from dengue_sinan.pipeline.preparacao import (  # noqa: E402
    carregar_preparado,
    preparar_dev,
    salvar_preparado,
)
from dengue_sinan.pipeline.treino import ConfigTreino, treinar_e_salvar  # noqa: E402


def config_rapida() -> ConfigTreino:
    cfg = ConfigTreino.de_arquivo(RAIZ / "config" / "treino_perfil.json")
    return replace(cfg, n_jobs=2, max_iter=60, paciencia=10)


@pytest.fixture(scope="session")
def mundo(tmp_path_factory):
    """Parquets sintéticos de 2022 e 2023 → conjunto preparado → artefato treinado."""
    base = tmp_path_factory.mktemp("pipeline")
    dados = base / "parquet"
    dados.mkdir()
    for ano, semente in ((2022, 1), (2023, 2)):
        bruto_sintetico(n=30_000, ano=ano, seed=semente).to_parquet(dados / f"dengue_{ano}.parquet")
    conjunto, registro = preparar_dev(dados)
    preparado = salvar_preparado(conjunto, base / "processed" / "dev.parquet")
    cfg = config_rapida()
    x, y, regiao, meta = carregar_preparado(preparado, cfg.variaveis)
    artefato = treinar_e_salvar(x, y, regiao, meta, cfg, base / "artefatos")
    return {
        "base": base,
        "dados": dados,
        "conjunto": conjunto,
        "preparado": preparado,
        "cfg": cfg,
        "x": x,
        "y": y,
        "regiao": regiao,
        "meta": meta,
        "artefato": artefato,
    }
