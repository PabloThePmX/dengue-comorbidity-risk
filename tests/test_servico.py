"""Camada de serviço: usa SÓ dados sintéticos (fixture `mundo`, nunca dados do SINAN)."""

import json
import logging
import re
import shutil
from pathlib import Path

import pytest
from conftest_pipeline import config_rapida, mundo  # noqa: F401

from dengue_sinan.pipeline.inferencia import EntradaInvalida
from dengue_sinan.servico import (
    ConfigServico,
    LoteGrande,
    ModeloIndisponivel,
    Servico,
    adaptador_spec,
    registro,
    relatorio,
)

OK = {"idade_anos": 30, "sexo": "F", "gestante": 0}


@pytest.fixture
def servico(mundo):  # noqa: F811
    pasta = mundo["artefato"].parent
    return Servico(ConfigServico(pasta, mundo["artefato"].name, None, limite_registros=50))


# ------------------------------------------------------------------ saúde e informações
def test_saude_info_e_contrato(servico):
    assert servico.saude() == {"status": "ok", "m1": "disponivel", "e1": "indisponivel"}
    info = servico.info()
    assert info["m1"]["hashes_conferidos"] is True
    assert info["m1"]["variaveis"] == ["idade_anos", "sexo", "gestante"]
    assert info["e1"]["status"] == "indisponivel" and "E1" in info["e1"]["motivo"]
    assert "Não é ferramenta clínica" in info["aviso"]
    assert [c["nome"] for c in servico.contrato()["campos"]] == info["m1"]["variaveis"]


def test_sem_artefato_o_servico_fica_degradado_e_nao_inventa(tmp_path):
    s = Servico(ConfigServico(tmp_path, None, None))
    assert s.saude()["status"] == "degradado"
    with pytest.raises(ModeloIndisponivel):
        s.prever_m1([OK])
    assert s.info()["m1"] is None and s.info()["m1_motivo_indisponivel"]


def test_artefato_adulterado_nao_carrega(mundo, tmp_path):  # noqa: F811
    destino = tmp_path / mundo["artefato"].name
    shutil.copytree(mundo["artefato"], destino)
    with open(destino / "modelo.joblib", "ab") as f:
        f.write(b"x")
    s = Servico(ConfigServico(tmp_path, destino.name, None))
    assert s.saude()["status"] == "degradado"
    with pytest.raises(ModeloIndisponivel) as e:
        s.prever_m1([OK])
    assert "hash" in e.value.motivo


# ------------------------------------------------------------------------- predição
def test_prever_m1_ok_invalido_e_sem_limiar(servico):
    r = servico.prever_m1([OK, {"idade_anos": -3}, {"idade_anos": 80, "sexo": "M"}])
    s = [x["status"] for x in r["resultados"]]
    assert s == ["ok", "invalido", "ok"]
    ok = r["resultados"][0]
    assert 0.0 <= ok["probabilidade"] <= 1.0 and ok["alto_risco"] is None
    assert r["resultados"][1]["probabilidade"] is None and r["resultados"][1]["erro"]
    assert "limiar" in r["alto_risco_motivo"]
    assert r["versao_modelo"] == servico.info()["m1"]["identificador"]


def test_prever_m1_e_deterministico(servico):
    a = servico.prever_m1([OK] * 5)
    b = servico.prever_m1([OK] * 5)
    assert a == b


def test_campo_desconhecido_e_entrada_errada_levantam(servico):
    with pytest.raises(EntradaInvalida):
        servico.prever_m1([{"idade_anos": 30, "diabetes": "sim"}])
    with pytest.raises(EntradaInvalida):
        servico.prever_m1({"idade_anos": 30})


def test_lista_vazia_e_limite_de_lote(servico):
    assert servico.prever_m1([])["resultados"] == []
    with pytest.raises(LoteGrande):
        servico.prever_m1([OK] * 51)


def test_avisos_de_plausibilidade_nao_bloqueiam(servico):
    r = servico.prever_m1([{"idade_anos": 30, "sexo": "M", "gestante": 1}])
    assert r["resultados"][0]["status"] == "ok" and r["resultados"][0]["avisos"]


def test_e1_nunca_e_inventado(servico):
    with pytest.raises(ModeloIndisponivel) as e:
        servico.prever_e1([OK])
    assert e.value.modelo == "E1"
    with pytest.raises(ModeloIndisponivel):
        servico.contrato("e1")


def test_e1_encontrado_mas_sem_formato_continua_indisponivel(mundo, tmp_path):  # noqa: F811
    shutil.copytree(mundo["artefato"], tmp_path / mundo["artefato"].name)
    (tmp_path / "e1-perfil-0.1.0").mkdir()
    s = Servico(ConfigServico(tmp_path, mundo["artefato"].name, None))
    est = s.estado_e1()
    assert est["status"] == "indisponivel" and "e1-perfil-0.1.0" in est["motivo"]


# --------------------------------------------------------------- contrato da especificação
def test_adaptador_converte_e_declara_o_que_ignora():
    reg, ign, err = adaptador_spec.adaptar(
        {"id_caso": "a", "idade_anos": 40, "sexo": "F", "gestante": "sim", "diabetes": "sim"}
    )
    assert reg == {"idade_anos": 40, "sexo": "F", "gestante": 1}
    assert ign == ["diabetes"] and err == []
    reg, _, _ = adaptador_spec.adaptar({"idade_anos": 40, "sexo": "ignorado", "gestante": "nao"})
    assert reg["sexo"] == "I" and reg["gestante"] == 0


def test_adaptador_recusa_campo_desconhecido_e_valor_errado():
    _, _, err = adaptador_spec.adaptar(
        {"idade_anos": 40, "febre_alta": "sim", "gestante": "talvez"}
    )
    assert any("febre_alta" in e for e in err) and any("gestante" in e for e in err)


def test_prever_pelo_contrato_da_spec(servico):
    r = servico.prever_m1_spec(
        [
            {
                "id_caso": "c1",
                "idade_anos": 70,
                "sexo": "M",
                "gestante": "nao",
                "hipertensao": "sim",
            },
            {"id_caso": "c2", "idade_anos": 20, "sexo": "X"},
        ]
    )
    a, b = r["resultados"]
    assert a["id_caso"] == "c1" and a["status"] == "ok"
    assert a["campos_ignorados_pelo_modelo"] == ["hipertensao"]
    assert any("não influenciam" in t for t in a["avisos"])
    assert b["status"] == "invalido" and b["probabilidade"] is None


def test_hipertensao_nao_muda_a_probabilidade(servico):
    base = {"idade_anos": 70, "sexo": "M", "gestante": "nao"}
    p0 = servico.prever_m1_spec([base])["resultados"][0]["probabilidade"]
    p1 = servico.prever_m1_spec([{**base, "hipertensao": "sim"}])["resultados"][0]["probabilidade"]
    assert p0 == p1


# ----------------------------------------------------------------------------- relatório
def test_relatorio_so_reproduz_numeros_dos_metadados(servico, mundo):  # noqa: F811
    rel = servico.relatorio()
    av = json.loads((mundo["artefato"] / "avaliacao_dev.json").read_text("utf-8"))
    cal = av["calibrado_validacao_cruzada"]
    assert rel["dados"]["calibrado"]["pr_auc"] == cal["pr_auc"]
    assert rel["dados"]["e_teste_historico"] is False
    texto = rel["texto"]
    assert "não afirma que o modelo está validado" in texto
    assert relatorio.AVISO in texto
    numeros = re.findall(r"\d+,\d+", texto)
    permitidos = set()
    for v in (
        cal["pr_auc"],
        cal["roc_auc"],
        cal["brier"],
        cal["brier_referencia_prevalencia"],
        av["sem_calibrar"]["pr_auc"],
        av["sem_calibrar"]["roc_auc"],
        av["sem_calibrar"]["brier"],
    ):
        for casas in (4, 6):
            permitidos.add(f"{v:.{casas}f}".replace(".", ","))
    prev = rel["dados"]["prevalencia_desenvolvimento"]
    permitidos.add(f"{prev:.5f}".replace(".", ","))
    for frase in rel["dados"]["limitacoes"]:  # números citados nas limitações vêm do artefato
        permitidos.update(re.findall(r"\d+,\d+", frase))
    sobra = [n for n in numeros if n not in permitidos]
    assert sobra == [], f"números no texto que não vêm dos metadados: {sobra}"


# ---------------------------------------------------------------- registro e configuração
def test_registro_lista_ordena_e_compara(mundo, tmp_path):  # noqa: F811
    for nome in ("m1-perfil-2.0.0", "m1-perfil-2.10.0", "e1-perfil-0.1.0", "lixo"):
        (tmp_path / nome).mkdir()
    ids = [a["identificador"] for a in registro.listar(tmp_path)]
    assert ids == ["e1-perfil-0.1.0", "m1-perfil-2.0.0", "m1-perfil-2.10.0"]
    assert registro.mais_recente(tmp_path, "m1") == "m1-perfil-2.10.0"
    assert registro.mais_recente(tmp_path, "zz") is None
    tabela = registro.comparar(mundo["artefato"].parent, [mundo["artefato"].name])
    assert tabela[0]["e_teste_historico"] is False and tabela[0]["pr_auc"] is not None


def test_configuracao_prioriza_o_ambiente(tmp_path):
    arq = tmp_path / "app.json"
    arq.write_text(json.dumps({"pasta_artefatos": "x", "m1": "m1-a-1.0.0", "limite_registros": 7}))
    c = ConfigServico.carregar(arq, ambiente={})
    assert c.m1 == "m1-a-1.0.0" and c.limite_registros == 7
    c = ConfigServico.carregar(
        arq, ambiente={"DENGUE_M1": "m1-b-2.0.0", "DENGUE_LIMITE_REGISTROS": "9"}
    )
    assert c.m1 == "m1-b-2.0.0" and c.limite_registros == 9
    with pytest.raises(ValueError):
        ConfigServico.carregar(arq, ambiente={"DENGUE_LIMITE_REGISTROS": "0"})


# --------------------------------------------------------------------------- garantias
def test_log_nao_guarda_o_conteudo_das_entradas(servico, caplog):
    with caplog.at_level(logging.DEBUG, logger="dengue_sinan.servico"):
        servico.prever_m1([{"idade_anos": 31.337, "sexo": "F", "gestante": 0}])
    assert "31.337" not in caplog.text and "idade_anos" not in caplog.text


def test_servico_nao_importa_treino_nem_preparacao():
    pasta = Path(__file__).resolve().parents[1] / "src" / "dengue_sinan" / "servico"
    proibidos = ("preparacao", "pipeline.treino", "etapa1", "download", "dataset", "pyarrow")
    for arq in pasta.glob("*.py"):
        for linha in arq.read_text("utf-8").splitlines():
            if linha.startswith(("import ", "from ")):
                assert not any(p in linha for p in proibidos), (arq.name, linha)


# ------------------------------------------------------------ robustez do carregamento
def test_pasta_historica_e_recusada_sem_derrubar(tmp_path):
    from dengue_sinan.pipeline.artefatos import HISTORICO

    s = Servico(ConfigServico(HISTORICO.parent, HISTORICO.name, None))
    assert s.saude()["status"] == "degradado"


def test_erro_inesperado_na_carga_vira_degradado(servico, monkeypatch):
    import dengue_sinan.servico.nucleo as n

    def quebra(*a, **k):
        raise KeyError("exec")

    monkeypatch.setattr(n, "carregar_preditor", quebra, raising=False)
    s = Servico(servico.config)
    assert s.saude()["status"] in ("ok", "degradado")  # não propaga a exceção


def test_pino_errado_recusa(mundo):  # noqa: F811
    pasta = mundo["artefato"].parent
    cfg = ConfigServico(pasta, mundo["artefato"].name, None, m1_sha256="0" * 64)
    s = Servico(cfg)
    assert s.saude()["status"] == "degradado"
    assert (
        "pino" in s.info()["m1_motivo_indisponivel"].lower() or s.info()["m1_motivo_indisponivel"]
    )
