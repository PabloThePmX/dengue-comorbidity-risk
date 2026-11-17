"""Testes do bloco `shap` do sessao-m1 (T-4.8) e do desenho local dos gráficos (dados sintéticos).

Uma execução pequena do SHAP global (XGBoost, CPU) gera os agregados; os testes mexem neles para
ver que a verificação reprova o que deve reprovar.
"""

import json

import pytest
from test_shap_global import cfg_teste, frame, xgb_ajustado

from dengue_sinan import shap_global, shap_graficos, verificacao_shap


@pytest.fixture(scope="module")
def execucao(tmp_path_factory):
    """Agregados gravados de um XGBoost pequeno, reaproveitados pelos testes deste arquivo."""
    base = tmp_path_factory.mktemp("shap")
    df = frame(n=600)
    cfg = cfg_teste(base, amostra=300)
    res = shap_global.calcular_shap_global(xgb_ajustado(df), df, cfg)
    out = base / "reports" / "shap"
    manifesto = shap_global.gravar_shap_global(res, out, cfg)
    return cfg, out, manifesto


def _reprovados(checks):
    return [c["nome"] for c in checks if not c["passou"]]


def test_bloco_passa_quando_os_agregados_estao_integros(execucao):
    cfg, out, manifesto = execucao
    checks = verificacao_shap.checks(manifesto, out, cfg)
    nomes = {c["nome"] for c in checks}
    assert {"agregados_gravados", "n_features_modelo", "soma_coerente_erro_max",
            "aditividade_erro_max", "sem_arquivo_por_linha"} <= nomes
    assert _reprovados(checks) == []


def test_bloco_reprova_csv_alterado(execucao, tmp_path):
    cfg, out, manifesto = execucao
    copia = tmp_path / "shap"
    copia.mkdir()
    for p in out.iterdir():
        (copia / p.name).write_bytes(p.read_bytes())
    with open(copia / shap_global.ARQ_IMPORTANCIA, "a", encoding="utf-8") as f:
        f.write("extra,extra,0\n")
    assert "agregados_gravados" in _reprovados(verificacao_shap.checks(manifesto, copia, cfg))


def test_bloco_reprova_arquivo_por_linha_extra(execucao, tmp_path):
    cfg, out, manifesto = execucao
    copia = tmp_path / "shap"
    copia.mkdir()
    for p in out.iterdir():
        (copia / p.name).write_bytes(p.read_bytes())
    (copia / "casos.csv").write_text("LINHA,y\n1,0\n", encoding="utf-8")
    assert "sem_arquivo_por_linha" in _reprovados(verificacao_shap.checks(manifesto, copia, cfg))


def test_bloco_reprova_erro_de_identidade_acima_da_tolerancia(execucao):
    cfg, out, manifesto = execucao
    ruim = json.loads(json.dumps(manifesto))
    ruim["medidas"]["erro_aditividade"] = 0.5
    assert "aditividade_erro_max" in _reprovados(verificacao_shap.checks(ruim, out, cfg))


def test_bloco_reprova_amostra_diferente_da_config(execucao):
    cfg, out, manifesto = execucao
    outra = dict(cfg, shap={"amostra": 999})
    assert "amostra_tamanho" in _reprovados(verificacao_shap.checks(manifesto, out, outra))


def test_escreve_o_bloco_shap_no_sessao_sem_apagar_outros_blocos(execucao, tmp_path):
    cfg, out, manifesto = execucao
    sessao = tmp_path / "sessao-m1.json"
    sessao.write_text(json.dumps({"sessao": "sessao-m1", "blocos": [
        {"bloco": "checagem_inicial", "checks": [], "passou": True}]}), encoding="utf-8")
    verificacao_shap.escrever_bloco_shap(sessao, manifesto, out, cfg)
    dados = json.loads(sessao.read_text(encoding="utf-8"))
    nomes = [b["bloco"] for b in dados["blocos"]]
    assert nomes == ["checagem_inicial", "shap"]
    bloco = dados["blocos"][1]
    assert bloco["tarefa"] == "T-4.8"
    assert bloco["passou"] is True
    assert dados["passou"] is False  # sessão ainda não completa: só o fim da sessão diz "passou"


def test_desenho_le_so_os_agregados_e_grava_os_dois_graficos(execucao, tmp_path):
    cfg, out, manifesto = execucao
    copia = tmp_path / "shap"
    copia.mkdir()
    for nome in [*shap_global.ARQUIVOS_DADOS, shap_global.ARQ_MANIFESTO]:
        (copia / nome).write_bytes((out / nome).read_bytes())  # sem modelo e sem dados
    caminhos = shap_graficos.desenhar(copia)
    assert [p.name for p in caminhos] == [shap_graficos.ARQ_IMPORTANCIA_PNG,
                                          shap_graficos.ARQ_INTERACOES_PNG]
    for p in caminhos:
        assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_desenho_recusa_agregado_alterado(execucao, tmp_path):
    _, out, _ = execucao
    copia = tmp_path / "shap"
    copia.mkdir()
    for nome in [*shap_global.ARQUIVOS_DADOS, shap_global.ARQ_MANIFESTO]:
        (copia / nome).write_bytes((out / nome).read_bytes())
    with open(copia / shap_global.ARQ_INTERACOES, "a", encoding="utf-8") as f:
        f.write("x,0\n")
    with pytest.raises(ValueError, match="SHA-256"):
        shap_graficos.desenhar(copia)


def test_legenda_obrigatoria_nos_dois_graficos(execucao, tmp_path, monkeypatch):
    _, out, _ = execucao
    copia = tmp_path / "shap"
    copia.mkdir()
    for nome in [*shap_global.ARQUIVOS_DADOS, shap_global.ARQ_MANIFESTO]:
        (copia / nome).write_bytes((out / nome).read_bytes())
    figuras = []
    original = shap_graficos._salvar

    def espiar(figura, caminho):
        figuras.append(figura)
        return original(figura, caminho)

    monkeypatch.setattr(shap_graficos, "_salvar", espiar)
    shap_graficos.desenhar(copia)
    assert len(figuras) == 2
    assert shap_graficos.LEGENDA == (
        "Explica o modelo, não causa; instável com features correlacionadas.")
    for figura in figuras:
        assert shap_graficos.LEGENDA in [t.get_text() for t in figura.texts]
