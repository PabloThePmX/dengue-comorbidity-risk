"""Exportador da entrada comum da comparação (D-97): portas de 2024 e 2025, com dados sintéticos."""

import json

import pandas as pd
import pytest
from populacao_sintetica import cfg_sintetico, dados_sinteticos, gravar, linha

from dengue_sinan import comparacao_entrada as ce
from dengue_sinan import guard
from dengue_sinan.preprocess import FEATURES_PERMITIDAS


@pytest.fixture
def cfg(tmp_path) -> dict:
    cfg = cfg_sintetico(tmp_path)
    cfg["ano_comparacao"] = 2025
    dados_sinteticos(cfg)
    gravar(cfg, 2024, [linha(), linha(EVOLUCAO="2")])  # existe, mas nunca pode ser exportado
    gravar(cfg, 2025, [linha(), linha(CLASSI_FIN="12", EVOLUCAO="2")])  # sintético, não é real
    return cfg


def test_exporta_ano_de_desenvolvimento_com_chaves_e_features(cfg, tmp_path):
    destino = ce.exportar_entrada(cfg, 2022, tmp_path / "entrada_2022.parquet")
    df = pd.read_parquet(destino)
    assert list(df["LINHA"]) == [0, 1, 2, 6]  # linhas do Parquet que sobreviveram à população
    assert set(df["ANO"]) == {2022}
    assert {"idade_anos", "sexo", "dias_ate_notificacao", "n_comorbidades"} <= set(df.columns)
    assert df["y"].sum() == 2


def test_nao_regrava_o_fluxograma_do_projeto(cfg, tmp_path):
    ce.exportar_entrada(cfg, 2022, tmp_path / "entrada_2022.parquet")
    assert not (tmp_path / "reports" / "fluxograma.md").exists()


def test_json_ao_lado_traz_o_dicionario_do_projeto(cfg, tmp_path):
    destino = ce.exportar_entrada(cfg, 2022, tmp_path / "entrada_2022.parquet")
    meta = json.loads(ce.caminho_metadados(destino).read_text(encoding="utf-8"))
    assert meta["features_do_projeto"] == list(FEATURES_PERMITIDAS)
    assert meta["ano"] == 2022 and meta["comparacao"] is False


def test_desenvolvimento_recusa_2024_antes_de_ler(cfg, tmp_path):
    with pytest.raises(RuntimeError, match="2024"):
        ce.exportar_entrada(cfg, 2024, tmp_path / "x.parquet")
    assert not (tmp_path / "x.parquet").exists()


def test_desenvolvimento_recusa_2025(cfg, tmp_path):
    with pytest.raises(RuntimeError, match="2025"):
        ce.exportar_entrada(cfg, 2025, tmp_path / "x.parquet")
    assert not (tmp_path / "x.parquet").exists()


def test_comparacao_sem_a_porta_aberta_e_recusada(cfg, tmp_path):
    with pytest.raises(RuntimeError, match="leitura_do_ano_de_comparacao"):
        ce.exportar_entrada(cfg, 2025, tmp_path / "x.parquet", comparacao=True)
    assert not (tmp_path / "x.parquet").exists()


def test_comparacao_dentro_da_porta_exporta_so_2025(cfg, tmp_path):
    with guard.leitura_do_ano_de_comparacao():
        destino = ce.exportar_entrada(cfg, 2025, tmp_path / "entrada_2025.parquet",
                                      comparacao=True)
    df = pd.read_parquet(destino)
    assert set(df["ANO"]) == {2025}
    assert len(df) == 2
    meta = json.loads(ce.caminho_metadados(destino).read_text(encoding="utf-8"))
    assert meta["comparacao"] is True


def test_comparacao_recusa_outro_ano_mesmo_com_a_porta_aberta(cfg, tmp_path):
    with guard.leitura_do_ano_de_comparacao(), pytest.raises(RuntimeError, match="2025"):
        ce.exportar_entrada(cfg, 2022, tmp_path / "x.parquet", comparacao=True)


def test_comparacao_recusa_2024_mesmo_com_a_porta_de_comparacao(cfg, tmp_path):
    with guard.leitura_do_ano_de_comparacao(), pytest.raises(RuntimeError):
        ce.exportar_entrada(cfg, 2024, tmp_path / "x.parquet", comparacao=True)


def test_recusa_destino_dentro_de_reports(cfg, tmp_path):
    with pytest.raises(PermissionError, match="reports"):
        ce.exportar_entrada(cfg, 2022, tmp_path / "reports" / "x.parquet")
