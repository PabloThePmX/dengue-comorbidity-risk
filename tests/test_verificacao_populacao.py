import json
from pathlib import Path

import pytest
import yaml
from populacao_sintetica import cfg_sintetico, dados_sinteticos

from dengue_sinan import verificacao_populacao as vp

# Esperado para o conjunto sintético de populacao_sintetica.dados_sinteticos.
ESPERADO = {
    "desenvolvimento": {
        "anos": [2022, 2023],
        "populacao_por_ano": {2022: 4, 2023: 1},
        "eventos_por_ano": {2022: 2, 2023: 0},
        "populacao_total": 5,
        "eventos_total": 2,
        "eventos_por_regiao": {"Centro-Oeste": 0, "Nordeste": 0, "Norte": 0,
                               "Sudeste": 2, "Sul": 0},
    },
    "fluxograma": {
        2022: {"total_baixado": 7, "classi_fin_10_11_12": 6, "rotulo_conhecido": 5,
               "idade_valida": 4},
        2023: {"total_baixado": 1, "classi_fin_10_11_12": 1, "rotulo_conhecido": 1,
               "idade_valida": 1},
    },
}


def _esperado(tmp_path: Path, esperado: dict) -> Path:
    caminho = tmp_path / "esperado.yaml"
    caminho.write_text(yaml.safe_dump(esperado), encoding="utf-8")
    return caminho


def test_executar_passa_quando_bate_com_esperado(tmp_path):
    cfg = dados_sinteticos(cfg_sintetico(tmp_path))
    saida = vp.executar(cfg, _esperado(tmp_path, ESPERADO))
    assert saida == tmp_path / "reports" / "verificacao" / "T-2.1.json"
    relatorio = json.loads(saida.read_text(encoding="utf-8"))
    assert relatorio["passou"] is True
    nomes = {c["nome"] for c in relatorio["checks"]}
    assert {"casos_desenvolvimento", "eventos_regiao_Sudeste", "fluxo_2022_idade_valida"} <= nomes


def test_executar_reprova_quando_um_numero_difere(tmp_path):
    cfg = dados_sinteticos(cfg_sintetico(tmp_path))
    errado = {**ESPERADO, "desenvolvimento": {**ESPERADO["desenvolvimento"], "eventos_total": 3}}
    relatorio = json.loads(vp.executar(cfg, _esperado(tmp_path, errado)).read_text("utf-8"))
    assert relatorio["passou"] is False
    falhou = [c["nome"] for c in relatorio["checks"] if not c["passou"]]
    assert falhou == ["eventos_desenvolvimento"]


def test_executar_recusa_anos_diferentes_do_esperado(tmp_path):
    cfg = dados_sinteticos(cfg_sintetico(tmp_path))
    cfg["anos_dev"] = [2022]
    with pytest.raises(ValueError, match="difere do esperado"):
        vp.executar(cfg, _esperado(tmp_path, ESPERADO))
