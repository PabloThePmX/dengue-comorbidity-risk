"""Testes dos gráficos comparativos de 2025 (T-8.8) com agregados sintéticos que seguem o contrato
de specs/contracts/interfaces.md, seção "Comparação em 2025". Nenhum dado real é lido aqui."""

import ast
import copy
import json
import math
import struct
import subprocess
import sys
from pathlib import Path

import matplotlib.colors as mcolors
import pytest

from dengue_sinan import comparar_graficos as cg

PNG = b"\x89PNG\r\n\x1a\n"
RODAPE = ("Ano de comparação 2025; avaliação única (R2); só agregados (R7); IC bootstrap pareado; "
          "população principal = casos que o E1 estima (D-99)")

REF = "m1_main"
MODELOS = ["m1_main", "e1_main", "b1_main", "b0_main", "b2_regra", "m1_soneca", "m1_lora"]
CASOS = 480_000
EVENTOS = 1_650
PREV = EVENTOS / CASOS
PR_AUC = {"m1_main": 0.0342, "e1_main": 0.0301, "b1_main": 0.0278, "b0_main": PREV,
          "b2_regra": 0.0121, "m1_soneca": 0.0327, "m1_lora": 0.0309}
RECALL = {"m1_main": (0.30, 0.44, 0.54), "e1_main": (0.27, 0.40, 0.50),
          "b1_main": (0.25, 0.38, 0.48), "b0_main": (0.05, 0.10, 0.14),
          "b2_regra": (0.22, 0.33, 0.41), "m1_soneca": (0.29, 0.43, 0.53),
          "m1_lora": (0.28, 0.41, 0.51)}
ORC = ("0.05", "0.10", "0.14")
PREVISTOS = [0.0007, 0.0011, 0.0016, 0.0024, 0.0036, 0.0052, 0.0080, 0.0130, 0.0210, 0.0400]


def _ponto(valor: float, delta: float) -> dict:
    return {"valor": valor, "ic95": [round(valor - delta, 6), round(valor + delta, 6)]}


def _leitura(lo: float, hi: float) -> str:
    if lo > 0:
        return "melhor"
    if hi < 0:
        return "pior"
    return "sem diferença detectável"


def agregados_sinteticos() -> dict:
    """Agregados de mentira, no formato do contrato (`metricas.json`)."""
    metricas_principal = {}
    for m in MODELOS:
        metricas_principal[m] = {
            "pr_auc": _ponto(PR_AUC[m], 0.004),
            "roc_auc": _ponto(0.74, 0.01),
            "brier": _ponto(0.0034, 0.0001),
            "calibration_slope": _ponto(0.95, 0.06),
            "calibration_intercepto": _ponto(-0.02, 0.1),
            "obs_esp": _ponto(1.2, 0.08),
        }
    metricas_completa = {m: {k: None for k in metricas_principal[m]} if m == "e1_main"
                         else copy.deepcopy(metricas_principal[m]) for m in MODELOS}
    diferencas = {REF: None}  # a entrada da própria referência é null (convenção)
    for m in MODELOS:
        if m == REF:
            continue
        valor = round(PR_AUC[m] - PR_AUC[REF], 6)
        lo, hi = round(valor - 0.0035, 6), round(valor + 0.0035, 6)
        diferencas[m] = {"valor": valor, "ic95": [lo, hi], "leitura": _leitura(lo, hi)}
    orcamentos = {}
    for m in MODELOS:
        celulas = {}
        for b, rec in zip(ORC, RECALL[m], strict=True):
            frac = float(b)
            alertas = round(CASOS * frac)
            prec = rec * EVENTOS / alertas
            celulas[b] = {"alertas": alertas, "recall": _ponto(rec, 0.03),
                          "precisao": _ponto(prec, prec * 0.12)}
        orcamentos[m] = celulas
    no_limiar = {m: ({"limiar": 0.002, "alertas": 9_000, "recall": 0.2, "precisao": 0.03}
                     if m not in ("b0_main", "b2_regra") else None) for m in MODELOS}
    limiares = [round(0.001 + 0.0005 * k, 6) for k in range(99)]
    curvas = {
        "m1_main": [round(0.0015 * math.exp(-60 * t), 8) for t in limiares],
        "e1_main": [round(0.0013 * math.exp(-62 * t), 8) for t in limiares],
        "b1_main": [round(0.0012 * math.exp(-55 * t), 8) for t in limiares],
        "b0_main": [round(max(0.0, PREV - (1 - PREV) * t / (1 - t)), 8) for t in limiares],
        "b2_regra": [round(0.0011 - 0.12 * t, 8) for t in limiares],
        "m1_soneca": [round(0.0014 * math.exp(-58 * t), 8) for t in limiares],
        "m1_lora": [round(0.0013 * math.exp(-61 * t), 8) for t in limiares],
    }
    calibracao = {}
    for m in MODELOS:
        if m == "b2_regra":
            calibracao[m] = None
            continue
        calibracao[m] = [{"previsto": p, "observado": round(p * (0.95 + 0.02 * i), 6),
                          "ic95": [round(p * (0.95 + 0.02 * i) * 0.85, 6),
                                   round(p * (0.95 + 0.02 * i) * 1.15, 6)],
                          "casos": 48_000}
                         for i, p in enumerate(PREVISTOS)]
    conformidade = {}
    for m in MODELOS:
        conformidade[m] = {"r3_sem_correcao": True, "r4_variaveis_no_dicionario": True,
                           "treino_sem_ano_de_comparacao": True,
                           "versoes_diferentes_do_treino": False, "externo": False}
    conformidade["b2_regra"]["versoes_diferentes_do_treino"] = None
    for m in ("m1_soneca", "m1_lora"):
        conformidade[m]["versoes_diferentes_do_treino"] = True
        conformidade[m]["externo"] = True
    conformidade["m1_lora"]["r4_variaveis_no_dicionario"] = False
    return {
        "ano": 2025,
        "reamostras": 1000,
        "semente": 42,
        "modelos": list(MODELOS),
        "modelo_de_referencia": REF,
        "populacoes": {
            "principal": {"nome": "casos que o E1 estima", "casos": CASOS, "eventos": EVENTOS,
                          "prevalencia": PREV},
            "completa": {"nome": "população completa", "casos": 500_000, "eventos": 1_700,
                         "prevalencia": 0.0034},
        },
        "metricas": {"principal": metricas_principal, "completa": metricas_completa},
        "diferencas_pr_auc_vs_referencia": {"principal": diferencas},
        "orcamentos": {"principal": orcamentos},
        "no_limiar_proprio": no_limiar,
        "curva_decisao": {"limiares": limiares, **curvas},
        "calibracao": calibracao,
        "conformidade": conformidade,
    }


@pytest.fixture
def figuras(monkeypatch, tmp_path) -> dict:
    """Gera as seis figuras e guarda cada objeto Figure ANTES de salvar (sem olhar a imagem)."""
    capturadas = {}
    original = cg._salvar

    def espiar(figura, caminho):
        capturadas[caminho.name] = figura
        return original(figura, caminho)

    monkeypatch.setattr(cg, "_salvar", espiar)
    cg.gerar_graficos(agregados_sinteticos(), tmp_path / "figuras")
    return capturadas


def _texto_do_rodape(figura) -> str:
    return " ".join(" ".join(t.get_text() for t in figura.texts).split())


def _eixos_visiveis(figura):
    return [e for e in figura.axes if e.get_visible()]


# --- Arquivos ----------------------------------------------------------------------------------

def test_gera_as_seis_figuras_em_png_de_tamanho_razoavel(tmp_path):
    caminhos = cg.gerar_graficos(agregados_sinteticos(), tmp_path / "figuras")
    assert [c.name for c in caminhos] == list(cg.FIGURAS)
    assert len(cg.FIGURAS) == 6
    for caminho in caminhos:
        conteudo = caminho.read_bytes()
        assert conteudo.startswith(PNG) and len(conteudo) > 5_000, caminho.name
        largura, altura = struct.unpack(">II", conteudo[16:24])  # IHDR
        assert 600 <= largura <= 4000 and 300 <= altura <= 4000, (caminho.name, largura, altura)


# --- Título, eixos e rodapé (objetos do matplotlib, não a imagem) ------------------------------

def test_titulo_e_rotulos_dos_eixos_estao_nos_objetos(figuras):
    for nome, figura in figuras.items():
        assert any(e.get_title().strip() for e in _eixos_visiveis(figura)), nome
    for nome in (cg.ARQ_PR_AUC, cg.ARQ_DIFERENCAS, cg.ARQ_ORCAMENTOS, cg.ARQ_CALIBRACAO,
                 cg.ARQ_CURVA_DECISAO):
        for eixo in _eixos_visiveis(figuras[nome]):
            assert eixo.get_xlabel().strip() and eixo.get_ylabel().strip(), nome
    assert "PR-AUC" in figuras[cg.ARQ_PR_AUC].axes[0].get_title()
    assert "Curva de decisão" in figuras[cg.ARQ_CURVA_DECISAO].axes[0].get_title()


def test_rodape_obrigatorio_em_todas_as_figuras(figuras):
    assert len(figuras) == 6
    for nome, figura in figuras.items():
        assert RODAPE in _texto_do_rodape(figura), nome


def test_rotulos_em_ptbr_e_externos_marcados_no_eixo(figuras):
    rotulos = [t.get_text() for t in figuras[cg.ARQ_PR_AUC].axes[0].get_yticklabels()]
    assert "M1 (XGBoost, projeto)" in rotulos
    assert "M1 soneca (externo)" in rotulos and "M1 lora (externo)" in rotulos
    assert "M1 (XGBoost, projeto) (externo)" not in rotulos
    legenda = [t.get_text() for t in figuras[cg.ARQ_PR_AUC].legends[0].get_texts()]
    assert any("acaso" in t for t in legenda) and any("externo" in t for t in legenda)


def test_tabela_de_conformidade_mostra_sim_nao_e_nd_por_modelo(figuras):
    tabela = figuras[cg.ARQ_CONFORMIDADE].axes[0].tables[0]
    celulas = {k: c.get_text().get_text() for k, c in tabela.get_celld().items()}
    linha_do = {m: i + 1 for i, m in enumerate(MODELOS)}  # linha 0 é o cabeçalho
    assert celulas[(linha_do["m1_main"], 0)] == "sim"  # R3 sem correção
    assert celulas[(linha_do["m1_lora"], 1)] == "não"  # R4 desviada (dado sintético)
    assert celulas[(linha_do["b2_regra"], 3)] == "n/d"  # versões: não se aplica (coluna 3)
    assert celulas[(linha_do["m1_soneca"], 4)] == "sim"  # externo (coluna 4)
    assert celulas[(linha_do["m1_main"], 4)] == "não"


# --- Cores, marcadores e ordem -----------------------------------------------------------------

def test_cor_e_ordem_sao_as_mesmas_em_todas_as_figuras(figuras):
    estilos = cg.estilos_dos_modelos(agregados_sinteticos())
    esperado = {est["rotulo_completo"]: mcolors.to_hex(est["cor"]) for est in estilos.values()}
    for nome in (cg.ARQ_CURVA_DECISAO, cg.ARQ_ORCAMENTOS):
        for eixo in _eixos_visiveis(figuras[nome]):
            for linha in eixo.get_lines():
                rotulo = linha.get_label()
                if rotulo in esperado:
                    assert mcolors.to_hex(linha.get_color()) == esperado[rotulo], (nome, rotulo)
    ordem = [est["rotulo_completo"] for est in estilos.values()]
    linhas = [ln.get_label() for ln in figuras[cg.ARQ_CURVA_DECISAO].axes[0].get_lines()]
    assert [r for r in linhas if r in ordem] == ordem  # ordem do manifesto


def test_marcador_e_traco_distinguem_os_modelos_em_preto_e_branco():
    estilos = cg.estilos_dos_modelos(agregados_sinteticos())
    pares = {(e["marcador"], repr(e["traco"])) for e in estilos.values()}
    assert len(pares) == len(estilos)  # ninguém depende só da cor
    assert {e["cor"] for e in estilos.values()} == {cg.COR[m] for m in MODELOS}


def test_modelo_externo_tem_marcador_vazado_e_interno_nao(figuras):
    eixo = figuras[cg.ARQ_CURVA_DECISAO].axes[0]  # a curva é a figura com as linhas rotuladas
    por_rotulo = {ln.get_label(): ln for ln in eixo.get_lines()}
    for externo in ("M1 soneca (externo)", "M1 lora (externo)"):
        assert mcolors.to_hex(por_rotulo[externo].get_markerfacecolor()) == "#ffffff", externo
    interno = por_rotulo["M1 (XGBoost, projeto)"]
    assert mcolors.to_hex(interno.get_markerfacecolor()) == mcolors.to_hex(cg.COR["m1_main"])


def test_diferenca_colorida_pela_leitura(figuras):
    eixo = figuras[cg.ARQ_DIFERENCAS].axes[0]
    anotados = {t.get_text(): t.get_color() for t in eixo.texts}
    assert anotados  # uma anotação por modelo com diferença
    for texto, cor in anotados.items():
        leitura = texto.rsplit("(", 1)[1].rstrip(")")
        assert leitura in cg.LEITURAS
        assert mcolors.to_hex(cor) == mcolors.to_hex(cg.COR_LEITURA[leitura]), texto


# --- Valores null ------------------------------------------------------------------------------

def test_valores_null_nao_desenham_ponto_e_nao_quebram(tmp_path, monkeypatch):
    dados = agregados_sinteticos()
    dados["metricas"]["principal"]["e1_main"]["pr_auc"] = None
    dados["diferencas_pr_auc_vs_referencia"]["principal"]["b0_main"] = None
    dados["curva_decisao"]["e1_main"][3] = None
    dados["calibracao"]["e1_main"] = None
    dados["orcamentos"]["principal"]["e1_main"]["0.10"]["recall"] = None
    capturadas = {}
    original = cg._salvar

    def espiar(figura, caminho):
        capturadas[caminho.name] = figura
        return original(figura, caminho)

    monkeypatch.setattr(cg, "_salvar", espiar)
    cg.gerar_graficos(dados, tmp_path / "figuras")

    pr = capturadas[cg.ARQ_PR_AUC].axes[0]
    assert any("E1" in t.get_text() and "sem estimativa" in t.get_text()
               for t in pr.get_yticklabels())
    pontos = [ln for ln in pr.get_lines() if len(ln.get_xdata()) == 1]
    assert len(pontos) == len(MODELOS) - 1  # E1 não desenha ponto

    dif = capturadas[cg.ARQ_DIFERENCAS].axes[0]
    assert any("sem estimativa" in t.get_text() for t in dif.get_yticklabels())

    cal = capturadas[cg.ARQ_CALIBRACAO]
    assert any("sem caixa publicável" in t.get_text()
               for eixo in cal.axes for t in eixo.texts)
    assert all(RODAPE in _texto_do_rodape(f) for f in capturadas.values())


# --- Recusa de agregado fora do contrato -------------------------------------------------------

def _sem_curva(a):
    a.pop("curva_decisao")


def _caixa_com_9_casos(a):
    a["calibracao"]["m1_main"][0]["casos"] = 9


def _leitura_invalida(a):
    a["diferencas_pr_auc_vs_referencia"]["principal"]["e1_main"]["leitura"] = "empate"


def _referencia_fora(a):
    a["modelo_de_referencia"] = "m9_fora"


def _orcamento_faltando(a):
    a["orcamentos"]["principal"]["m1_main"].pop("0.14")


def _conformidade_sem_chave(a):
    a["conformidade"]["m1_main"].pop("r3_sem_correcao")


def _curva_sem_um_valor(a):
    a["curva_decisao"]["m1_main"].pop()


@pytest.mark.parametrize(("alteracao", "erro"), [
    (_sem_curva, "curva_decisao"),
    (_caixa_com_9_casos, "menos de 10 casos"),
    (_leitura_invalida, "leitura inválida"),
    (_referencia_fora, "modelo_de_referencia"),
    (_orcamento_faltando, "0.14"),
    (_conformidade_sem_chave, "conformidade de m1_main"),
    (_curva_sem_um_valor, "um valor por limiar"),
])
def test_agregado_fora_do_contrato_e_recusado_sem_criar_nada(tmp_path, alteracao, erro):
    dados = agregados_sinteticos()
    alteracao(dados)
    destino = tmp_path / "figuras"
    with pytest.raises(ValueError, match=erro):
        cg.gerar_graficos(dados, destino)
    assert not destino.exists()


def test_chave_de_topo_faltando_e_recusada(tmp_path):
    dados = agregados_sinteticos()
    del dados["semente"]
    with pytest.raises(ValueError, match="semente"):
        cg.gerar_graficos(dados, tmp_path / "f")


# --- Nada além dos agregados -------------------------------------------------------------------

def test_modulo_nao_importa_dados_nem_pandas_e_nao_cita_caminhos_de_dados():
    arvore = ast.parse(Path(cg.__file__).read_text(encoding="utf-8"))
    importados = set()
    for no in ast.walk(arvore):
        if isinstance(no, ast.Import):
            importados.update(a.name for a in no.names)
        elif isinstance(no, ast.ImportFrom):
            importados.add(no.module or "")
    proibidos = ("pandas", "pyarrow", "dengue_sinan.dataset", "dengue_sinan.guard",
                 "dengue_sinan.evaluate", "dengue_sinan.comparacao_entrada")
    assert not [i for i in importados for p in proibidos if i == p or i.startswith(p + ".")]
    textos = [no.value for no in ast.walk(arvore)
              if isinstance(no, ast.Constant) and isinstance(no.value, str)]
    assert not [t for t in textos if "parquet" in t.lower() or "data/" in t or "data\\" in t]


def test_roda_so_com_o_json_num_diretorio_vazio(tmp_path):
    json_path = tmp_path / "metricas.json"
    json_path.write_text(json.dumps(agregados_sinteticos()), encoding="utf-8")
    vazio = tmp_path / "vazio"
    vazio.mkdir()
    destino = tmp_path / "saida"
    codigo = ("import sys; from dengue_sinan import comparar_graficos as cg; "
              "assert cg.main(['--agregados', sys.argv[1], '--destino', sys.argv[2]]) == 0; "
              "print('BLOQUEADOS=' + '|'.join(m for m in ('pandas', 'pyarrow') "
              "if m in sys.modules))")
    saida = subprocess.run([sys.executable, "-c", codigo, str(json_path), str(destino)],
                           cwd=vazio, capture_output=True, text=True, check=True, timeout=300)
    assert [ln for ln in saida.stdout.splitlines() if ln.startswith("BLOQUEADOS=")] == [
        "BLOQUEADOS="]  # nenhum pandas nem pyarrow foi importado
    assert list(vazio.iterdir()) == []  # não escreve no diretório de trabalho
    assert len(list(destino.glob("*.png"))) == 6


# --- Convenções de interfaces.md (Convenções): caixas suprimidas, nulos e sinal --------------

def _gerar_capturando(monkeypatch, tmp_path, dados) -> dict:
    capturadas = {}
    original = cg._salvar

    def espiar(figura, caminho):
        capturadas[caminho.name] = figura
        return original(figura, caminho)

    monkeypatch.setattr(cg, "_salvar", espiar)
    cg.gerar_graficos(dados, tmp_path / "figuras")
    return capturadas


def _pontos_de_calibracao(eixo) -> int:
    """Pontos desenhados (linhas sem traço, como o plot das caixas) no painel de um modelo."""
    return sum(len(ln.get_xdata()) for ln in eixo.get_lines() if ln.get_linestyle() == "None")


def test_caixa_suprimida_e_caixa_sem_taxa_nao_viram_ponto(monkeypatch, tmp_path):
    dados = agregados_sinteticos()
    caixas = dados["calibracao"]["m1_main"]
    caixas[0] = {"previsto": None, "observado": None, "ic95": None, "casos": "<10"}  # R7
    caixas[1] = {"previsto": caixas[1]["previsto"], "observado": None, "ic95": None,
                 "casos": 40_000}  # casos >= 10 e eventos < 10: taxa suprimida
    figuras = _gerar_capturando(monkeypatch, tmp_path, dados)
    esperado = len(cg._caixas_publicaveis(caixas))
    assert esperado == len(caixas) - 2
    assert _pontos_de_calibracao(figuras[cg.ARQ_CALIBRACAO].axes[0]) == esperado
    assert all(RODAPE in _texto_do_rodape(f) for f in figuras.values())


def test_caixa_com_casos_numericos_menores_que_dez_ainda_e_recusada(tmp_path):
    dados = agregados_sinteticos()
    dados["calibracao"]["m1_main"][0]["casos"] = 3  # numérico: a convenção recusa
    with pytest.raises(ValueError, match="menos de 10 casos"):
        cg.gerar_graficos(dados, tmp_path / "f")


def test_casos_com_texto_que_nao_e_menos_de_dez_e_recusado(tmp_path):
    dados = agregados_sinteticos()
    dados["calibracao"]["m1_main"][0]["casos"] = "poucos"
    with pytest.raises(ValueError, match="inteiro ou"):
        cg.gerar_graficos(dados, tmp_path / "f")


def test_suprimida_com_valor_e_recusada(tmp_path):
    dados = agregados_sinteticos()
    dados["calibracao"]["m1_main"][0] = {"previsto": 0.001, "observado": None, "ic95": None,
                                         "casos": "<10"}
    with pytest.raises(ValueError, match="suprimida"):
        cg.gerar_graficos(dados, tmp_path / "f")


def test_diferenca_nula_vira_sem_estimativa_e_nao_quebra(monkeypatch, tmp_path):
    dados = agregados_sinteticos()
    dados["diferencas_pr_auc_vs_referencia"]["principal"]["b1_main"] = {
        "valor": None, "ic95": None, "leitura": None}
    figuras = _gerar_capturando(monkeypatch, tmp_path, dados)
    rotulos = [t.get_text() for t in figuras[cg.ARQ_DIFERENCAS].axes[0].get_yticklabels()]
    assert "B1 (logística simples) (sem estimativa)" in rotulos


def test_referencia_com_diferenca_nao_nula_e_recusada(tmp_path):
    dados = agregados_sinteticos()
    dados["diferencas_pr_auc_vs_referencia"]["principal"]["m1_main"] = {
        "valor": 0.0, "ic95": [-0.001, 0.001], "leitura": "sem diferença detectável"}
    with pytest.raises(ValueError, match="própria referência"):
        cg.gerar_graficos(dados, tmp_path / "f")


def test_leitura_que_nao_bate_com_o_ic_e_recusada(tmp_path):
    dados = agregados_sinteticos()
    # IC inferior > 0 pela convenção é "melhor"; rotular "pior" é contradição
    dados["diferencas_pr_auc_vs_referencia"]["principal"]["e1_main"] = {
        "valor": 0.01, "ic95": [0.002, 0.02], "leitura": "pior"}
    with pytest.raises(ValueError, match="não bate com o IC"):
        cg.gerar_graficos(dados, tmp_path / "f")


def test_modelo_inteiro_com_metricas_nulas_nao_quebra(monkeypatch, tmp_path):
    dados = agregados_sinteticos()
    dados["metricas"]["principal"]["b2_regra"] = None  # modelo sem métricas nesta população
    figuras = _gerar_capturando(monkeypatch, tmp_path, dados)
    rotulos = [t.get_text() for t in figuras[cg.ARQ_PR_AUC].axes[0].get_yticklabels()]
    assert "B2 (regra do protocolo) (sem estimativa)" in rotulos
