"""Testes dos gráficos da avaliação no teste (T-5.2) com agregados sintéticos (sem microdado)."""

import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from test_evaluate import _df_sintetico, _esperado_de, _fontes

from dengue_sinan import evaluate as ev
from dengue_sinan import teste_analises as ta
from dengue_sinan import teste_graficos as tg
from dengue_sinan.config import load_config

PNG = b"\x89PNG\r\n\x1a\n"


@pytest.fixture(scope="module")
def pasta_lacrada(tmp_path_factory) -> Path:
    """Pasta `reports/teste/` de uma avaliação sintética de verdade (lacre e agregados reais)."""
    base = tmp_path_factory.mktemp("graficos")
    cfg_base = load_config()
    cfg = {**copy.deepcopy(cfg_base),
           "caminhos": {**cfg_base["caminhos"], "dados": str(base / "data"),
                        "relatorios": str(base / "reports"), "modelos": str(base / "models")},
           "bootstrap": {"metricas": 20, "calibracao": 2000, "processos": 1}}
    df = _df_sintetico(n=6000)
    df["y"] = (np.random.default_rng(3).random(len(df)) < 0.06).astype("int64")  # eventos de sobra
    esperado = _esperado_de(df)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(ev, "_ler_esperado_teste", lambda caminho=None: esperado)
        ev.evaluate_test_once(cfg, fontes=_fontes(df))
    return base / "reports" / "teste"


@pytest.fixture
def copia(pasta_lacrada, tmp_path) -> Path:
    destino = tmp_path / "teste"
    shutil.copytree(pasta_lacrada, destino)
    return destino


def _recolocar_hash(pasta: Path) -> None:
    """Regrava o lacre com o hash do `metricas.json` atual (simula um lacre coerente)."""
    lacre = json.loads((pasta / tg.ARQ_LACRE).read_text(encoding="utf-8"))
    texto = (pasta / tg.ARQ_JSON).read_text(encoding="utf-8")
    lacre["relatorios"][tg.ARQ_JSON] = hashlib.sha256(texto.encode("utf-8")).hexdigest()
    (pasta / tg.ARQ_LACRE).write_text(json.dumps(lacre), encoding="utf-8")


def test_desenha_as_quatro_figuras_em_png_a_partir_dos_agregados(copia, tmp_path):
    saida = tmp_path / "figuras"
    caminhos = tg.desenhar(copia, saida)
    assert [c.name for c in caminhos] == [tg.ARQ_DECISAO_PNG, tg.ARQ_CALIBRACAO_PNG,
                                          tg.ARQ_SUBGRUPOS_PR_AUC_PNG,
                                          tg.ARQ_SUBGRUPOS_RECALL_PNG]
    for caminho in caminhos:
        conteudo = caminho.read_bytes()
        assert conteudo.startswith(PNG) and len(conteudo) > 5_000, caminho.name


def test_desenha_na_propria_pasta_quando_nao_ha_destino(copia):
    caminhos = tg.desenhar(copia)
    assert all(c.parent == copia and c.exists() for c in caminhos)


def test_le_so_o_json_e_o_lacre_sem_markdown_csv_nem_dados(copia, tmp_path):
    for outro in list(copia.iterdir()):
        if outro.name not in (tg.ARQ_JSON, tg.ARQ_LACRE):
            outro.unlink()
    assert len(tg.desenhar(copia, tmp_path / "f")) == 4


def test_json_alterado_nao_vira_grafico_porque_o_sha256_nao_confere_com_o_lacre(copia, tmp_path):
    caminho = copia / tg.ARQ_JSON
    dados = json.loads(caminho.read_text(encoding="utf-8"))
    dados["analises"]["metricas"]["modelos"]["M1"]["pr_auc"]["valor"] = 0.99  # adulterado
    caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                       encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        tg.desenhar(copia, tmp_path / "f")
    assert not (tmp_path / "f" / tg.ARQ_DECISAO_PNG).exists()  # nada foi desenhado


def test_um_byte_a_mais_no_json_tambem_e_recusado(copia, tmp_path):
    caminho = copia / tg.ARQ_JSON
    caminho.write_text(caminho.read_text(encoding="utf-8") + " ", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        tg.carregar_agregados(copia)


def test_sem_lacre_nao_desenha(copia):
    (copia / tg.ARQ_LACRE).unlink()
    with pytest.raises(FileNotFoundError, match="LACRE"):
        tg.desenhar(copia)


# --- Fecho da T-5.2 (4): lacre e hash conferidos ANTES de criar a pasta de saída --------------

def test_sem_lacre_nao_cria_a_pasta_de_saida(copia, tmp_path):
    (copia / tg.ARQ_LACRE).unlink()
    saida = tmp_path / "figuras" / "novas"
    with pytest.raises(FileNotFoundError, match="LACRE"):
        tg.desenhar(copia, saida)
    assert not saida.exists() and not saida.parent.exists()  # nem diretório vazio, nem o pai


def test_json_alterado_nao_cria_a_pasta_de_saida(copia, tmp_path):
    caminho = copia / tg.ARQ_JSON
    caminho.write_text(caminho.read_text(encoding="utf-8") + " ", encoding="utf-8")
    saida = tmp_path / "figuras"
    with pytest.raises(ValueError, match="SHA-256"):
        tg.desenhar(copia, saida)
    assert not saida.exists()


def test_json_que_nao_e_do_teste_nao_cria_a_pasta_de_saida(copia, tmp_path):
    dados = json.loads((copia / tg.ARQ_JSON).read_text(encoding="utf-8"))
    dados["modo"] = "ensaio"
    (copia / tg.ARQ_JSON).write_text(json.dumps(dados), encoding="utf-8")
    _recolocar_hash(copia)
    saida = tmp_path / "figuras"
    with pytest.raises(ValueError, match="não é o da avaliação do teste"):
        tg.desenhar(copia, saida)
    assert not saida.exists()


def test_com_lacre_e_hash_corretos_cria_a_pasta_de_saida_e_as_figuras(copia, tmp_path):
    saida = tmp_path / "figuras" / "novas"
    assert len(tg.desenhar(copia, saida)) == 4 and saida.is_dir()


def test_json_que_nao_e_do_teste_ou_sem_as_analises_e_recusado(copia):
    dados = json.loads((copia / tg.ARQ_JSON).read_text(encoding="utf-8"))
    dados["modo"] = "ensaio"
    (copia / tg.ARQ_JSON).write_text(json.dumps(dados), encoding="utf-8")
    _recolocar_hash(copia)
    with pytest.raises(ValueError, match="não é o da avaliação do teste"):
        tg.carregar_agregados(copia)
    dados["modo"] = "teste"
    del dados["analises"]["subgrupos"]
    (copia / tg.ARQ_JSON).write_text(json.dumps(dados), encoding="utf-8")
    _recolocar_hash(copia)
    with pytest.raises(ValueError, match="sem as análises: subgrupos"):
        tg.carregar_agregados(copia)


@pytest.fixture
def figuras_capturadas(monkeypatch):
    """Intercepta `_salvar` para inspecionar cada Figure e a legenda escrita no pé."""
    figuras, legendas = {}, []
    salvar = tg._salvar
    legenda = tg._legenda

    def espiar_salvar(figura, caminho):
        figuras[caminho.name] = figura
        return salvar(figura, caminho)

    def espiar_legenda(figura, texto):
        legendas.append((figura, texto))
        return legenda(figura, texto)

    monkeypatch.setattr(tg, "_salvar", espiar_salvar)
    monkeypatch.setattr(tg, "_legenda", espiar_legenda)
    return figuras, legendas


def test_legenda_de_associacao_nao_e_causa_nas_figuras_de_subgrupo(copia, tmp_path,
                                                                    figuras_capturadas):
    figuras, legendas = figuras_capturadas
    tg.desenhar(copia, tmp_path / "f")
    por_figura = {id(f): t for f, t in legendas}
    for nome in (tg.ARQ_SUBGRUPOS_PR_AUC_PNG, tg.ARQ_SUBGRUPOS_RECALL_PNG):
        texto = por_figura[id(figuras[nome])]
        assert tg.LEGENDA_SUBGRUPOS in texto
        assert "Associação não é causa" in texto and "notificação" in texto
    assert tg.LEGENDA_SUBGRUPOS == ta.LEGENDA_SUBGRUPOS  # uma só fonte
    assert len(legendas) == 4  # toda figura tem legenda no pé


def test_floresta_tem_uma_linha_por_subgrupo_e_marca_ic_largo(copia, tmp_path, figuras_capturadas):
    figuras, _ = figuras_capturadas
    tg.desenhar(copia, tmp_path / "f")
    dados = tg.carregar_agregados(copia)
    total = sum(len(d["subgrupos"]) for d in dados["analises"]["subgrupos"]["dimensoes"].values())
    for nome in (tg.ARQ_SUBGRUPOS_PR_AUC_PNG, tg.ARQ_SUBGRUPOS_RECALL_PNG):
        rotulos = [r.get_text() for r in figuras[nome].axes[0].get_yticklabels()]
        assert len(rotulos) == total
        assert any("(IC largo)" in r for r in rotulos)  # pelo menos os nomeados do spec
        assert any("Norte" in r and "(IC largo)" in r for r in rotulos)
    sem_metricas = [r for r in rotulos if "(sem métricas)" in r]
    assert all("(IC largo)" in r for r in sem_metricas)  # sem métricas implica poucos eventos


def test_decisao_marca_os_pontos_e_calibracao_usa_eixos_log_com_diagonal(copia, tmp_path,
                                                                          figuras_capturadas):
    figuras, _ = figuras_capturadas
    tg.desenhar(copia, tmp_path / "f")
    legenda_decisao = [t.get_text() for t in figuras[tg.ARQ_DECISAO_PNG].axes[0].get_legend().texts]
    assert {"M1", "B1", "B2", "tratar todos", "tratar ninguém"} <= set(legenda_decisao)
    assert any("limiar F2" in t for t in legenda_decisao)  # o F2 sintético está dentro da curva
    eixos = figuras[tg.ARQ_CALIBRACAO_PNG].axes
    assert len(eixos) == 2  # M1 e E1
    for eixo in eixos:
        assert eixo.get_xscale() == "log" and eixo.get_yscale() == "log"
        assert "calibração perfeita" in [t.get_text() for t in eixo.get_legend().texts]


def test_ponto_marcado_fora_do_intervalo_vira_nota_na_legenda(copia, tmp_path, figuras_capturadas):
    _, legendas = figuras_capturadas
    dados = json.loads((copia / tg.ARQ_JSON).read_text(encoding="utf-8"))
    dados["analises"]["decisao"]["pontos_marcados"]["M1_principal"]["dentro_da_faixa"] = False
    (copia / tg.ARQ_JSON).write_text(json.dumps(dados), encoding="utf-8")
    _recolocar_hash(copia)
    tg.desenhar(copia, tmp_path / "f")
    assert any("fora do intervalo do gráfico" in texto for _, texto in legendas)


# --- Fecho da T-5.2 (3): calibracao.png sem rótulos sobrepostos e legenda fora dos dados ------

def _caixas(prev, taxa, folga=0.25) -> list[dict]:
    return [{"caixa": f"C{i:02d}", "n": 1000, "eventos": 100, "risco_previsto_medio": a,
             "taxa_observada": b, "ic95": [b * (1 - folga), b * (1 + folga)], "aviso": None}
            for i, (a, b) in enumerate(zip(prev, taxa, strict=True))]


def _json_calibracao(prev, taxa) -> dict:
    return {"modelos": {nome: {"global": {"slope": {"valor": 0.9, "ic95": [0.8, 1.0]},
                                          "obs_esp": {"valor": 1.1, "ic95": [1.0, 1.2]}},
                               "caixas": _caixas(prev, taxa)} for nome in ("M1", "E1")}}


FAIXAS_DE_RISCO = {
    "varias_decadas": ([0.0006, 0.001, 0.0016, 0.0025, 0.004, 0.0065, 0.011, 0.02, 0.035, 0.06],
                       [0.0007, 0.0011, 0.0015, 0.0028, 0.0042, 0.0061, 0.012, 0.019, 0.04, 0.07]),
    "menos_de_uma_decada": ([0.011, 0.012, 0.0125, 0.013, 0.0138, 0.0146, 0.0155, 0.0165, 0.0178,
                             0.019],
                            [0.0105, 0.0118, 0.013, 0.0128, 0.0141, 0.0150, 0.0149, 0.0170, 0.018,
                             0.0195]),
}


def _sobrepoe(a, b) -> bool:
    return a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1


@pytest.mark.parametrize("faixa", sorted(FAIXAS_DE_RISCO))
def test_calibracao_sem_rotulos_do_eixo_sobrepostos_e_legenda_fora_dos_dados(
        faixa, tmp_path, figuras_capturadas):
    figuras, _ = figuras_capturadas
    prev, taxa = FAIXAS_DE_RISCO[faixa]
    tg._figura_calibracao(_json_calibracao(prev, taxa), tmp_path / "calibracao.png")
    figura = figuras["calibracao.png"]
    figura.canvas.draw()
    renderizador = figura.canvas.get_renderer()
    for eixo in figura.axes:
        area = eixo.get_window_extent(renderizador)
        for lado in (eixo.get_xticklabels(), eixo.get_yticklabels()):
            visiveis = [t.get_window_extent(renderizador) for t in lado
                        if t.get_text() and t.get_visible()]
            assert len(visiveis) >= 2
            for i, a in enumerate(visiveis):
                for b in visiveis[i + 1:]:
                    assert not _sobrepoe(a, b), (faixa, lado[0].get_text())
        textos = [t.get_text() for t in eixo.get_xticklabels() if t.get_text()]
        assert all(t.endswith("%") for t in textos), textos  # em %, não em notação científica
        legenda = eixo.get_legend().get_window_extent(renderizador)
        assert legenda.y1 <= area.y0 + 1e-6  # abaixo do eixo: não cobre ponto nem barra
        assert not _sobrepoe(legenda, eixo.xaxis.label.get_window_extent(renderizador))
        for t in eixo.get_xticklabels():
            if t.get_text():
                assert not _sobrepoe(legenda, t.get_window_extent(renderizador))


def test_titulo_da_calibracao_usa_virgula_decimal_como_os_eixos(tmp_path, figuras_capturadas):
    figuras, _ = figuras_capturadas
    prev, taxa = FAIXAS_DE_RISCO["varias_decadas"]
    tg._figura_calibracao(_json_calibracao(prev, taxa), tmp_path / "calibracao.png")
    titulos = [e.get_title() for e in figuras["calibracao.png"].axes]
    assert titulos == ["Calibração de M1 (slope 0,900, obs/esp 1,100)",
                       "Calibração de E1 (slope 0,900, obs/esp 1,100)"]


def test_modulo_nao_importa_pandas_nem_carrega_modelo_ou_dados():
    codigo = ("import sys, dengue_sinan.teste_graficos; "
              "bloqueados = [m for m in ('pandas', 'torch', 'xgboost', 'catboost', 'pyarrow') "
              "if m in sys.modules]; "
              "print(','.join(bloqueados))")
    saida = subprocess.run([sys.executable, "-c", codigo], capture_output=True, text=True,
                           check=True, timeout=120)
    assert saida.stdout.strip() == ""


def test_floresta_segue_a_ordem_do_spec_mesmo_com_o_json_de_chaves_ordenadas(
        copia, tmp_path, figuras_capturadas):
    figuras, _ = figuras_capturadas
    tg.desenhar(copia, tmp_path / "f")
    rotulos = [r.get_text() for r in figuras[tg.ARQ_SUBGRUPOS_PR_AUC_PNG].axes[0].get_yticklabels()]
    de_cima_para_baixo = rotulos[::-1]
    faixas = [r for r in de_cima_para_baixo if r.startswith("Faixa etária")]
    esperado = ["0–4", "5–14", "15–39", "40–59", "60–79", "80+"]
    assert [r.split(": ")[1].split(" (")[0] for r in faixas] == esperado
    dimensoes = [r.split(":")[0] for r in de_cima_para_baixo]
    assert list(dict.fromkeys(dimensoes)) == ["Faixa etária", "Sexo", "Gestante",
                                              "Região de residência", "Raça/cor"]
