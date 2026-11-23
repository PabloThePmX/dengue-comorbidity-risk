"""Serviço da demo (T-6.1): E1 e M1 no app batem com as chamadas diretas, SHAP, B2, painel,
artefato ausente e privacidade (NFR-03: sem gravação, sem log, sem rede).

E1 real (`models/e1`, versionado). M1 real (`models/m1_final`, fora do git): os testes que o
exigem são pulados se ele não existir; os demais usam um M1 sintético pequeno.
"""

import json
import logging
import re
import shutil
import socket
from pathlib import Path

import numpy as np
import pytest
from app_sintetico import bruta, frame_do_contrato, m1_sintetico

from app import entrada, servico
from dengue_sinan import artifacts, baselines, explain, retreino, shap_global
from dengue_sinan.profiling import COMORBIDADES

RAIZ = Path(__file__).resolve().parents[1]
TEM_M1 = any((RAIZ / "models" / nome / "metadata.json").is_file() for nome in servico.NOMES_M1)
precisa_m1 = pytest.mark.skipif(not TEM_M1, reason="models/m1_final não existe nesta instalação "
                                                    "(fora do git, D-85)")

PERFIS_REFERENCIA = [
    (40, "F", 0, ()),
    (60, "F", 0, ("DIABETES", "HIPERTENSA")),
    (30, "M", 0, ("RENAL",)),
    (28, "F", 1, ("HIPERTENSA",)),
    (75, "M", 0, ("DIABETES", "RENAL", "HEMATOLOG")),
]


@pytest.fixture(scope="module")
def artefatos():
    return servico.carregar_artefatos()


@pytest.fixture(scope="module")
def e1(artefatos):
    assert artefatos.e1 is not None, artefatos.erro_e1
    return artefatos.e1


@pytest.fixture(scope="module")
def m1_real(artefatos):
    if artefatos.m1 is None:
        pytest.skip(artefatos.erro_m1)
    return artefatos.m1


@pytest.fixture(scope="module")
def m1_sint():
    return m1_sintetico(limiar=0.4)


def _perfil(idade, sexo, gestante, comorbidades) -> entrada.Perfil:
    return entrada.Perfil(idade, sexo, gestante, tuple(comorbidades))


# --- E1 ----------------------------------------------------------------------------------------

@pytest.mark.parametrize(("idade", "sexo", "gestante", "marcadas"), PERFIS_REFERENCIA)
def test_risco_do_e1_no_app_bate_com_a_chamada_direta_de_explain(e1, idade, sexo, gestante,
                                                                 marcadas):
    res = servico.avaliar_perfil(e1, _perfil(idade, sexo, gestante, marcadas))
    direto = explain.risco_perfil(e1, idade, sexo, gestante, marcadas)
    base = explain.risco_perfil(e1, idade, sexo, gestante, ())
    razao = explain.razao_de_risco(e1, idade, sexo, gestante, marcadas)
    assert res.estimavel and res.motivo is None
    assert res.risco == direto["risco"]
    assert res.ic == (direto["ic_inferior"], direto["ic_superior"])
    assert res.risco_base == base["risco"]
    assert res.razao == razao["razao"]
    assert res.ic_razao == (razao["ic_inferior"], razao["ic_superior"])
    assert res.faixa == servico.faixa_etaria(idade)


@pytest.mark.parametrize(("idade", "sexo", "gestante", "marcadas"), PERFIS_REFERENCIA)
def test_ic_do_e1_e_o_metodo_delta_na_escala_do_logit(e1, idade, sexo, gestante, marcadas):
    """IC = expit(η ± 1,96·EP): simétrico no logit em torno do risco (e não na escala do risco)."""
    res = servico.avaliar_perfil(e1, _perfil(idade, sexo, gestante, marcadas))
    logit = lambda p: np.log(p / (1 - p))  # noqa: E731
    inf, sup = res.ic
    assert inf < res.risco < sup
    assert logit(res.risco) - logit(inf) == pytest.approx(logit(sup) - logit(res.risco), rel=1e-9)
    erro = explain.risco_perfil(e1, idade, sexo, gestante, marcadas)["erro_logit"]
    assert logit(sup) - logit(res.risco) == pytest.approx(explain.Z95 * erro, rel=1e-9)


def test_comparacao_sem_comorbidades_e_odds_das_marcadas(e1):
    res = servico.avaliar_perfil(e1, _perfil(60, "F", 0, ("DIABETES", "HIPERTENSA")))
    assert res.risco > res.risco_base
    assert res.razao > 1
    assert [o["comorbidade"] for o in res.odds] == ["DIABETES", "HIPERTENSA"]
    for o in res.odds:
        lo = explain.log_or_na_idade(e1, o["comorbidade"], 60)
        assert o["or"] == pytest.approx(np.exp(lo["estimativa"]))
        assert o["ic_inferior"] < o["or"] < o["ic_superior"]
    sem = servico.avaliar_perfil(e1, _perfil(60, "F", 0, ()))
    assert sem.odds == [] and sem.razao == pytest.approx(1.0) and sem.risco == sem.risco_base


def test_5_ou_mais_comorbidades_e_par_excluido_viram_dados_insuficientes_sem_numero(e1):
    cinco = servico.avaliar_perfil(e1, _perfil(50, "F", 0, COMORBIDADES[:5]))
    assert not cinco.estimavel and cinco.risco is None and cinco.razao is None
    assert "dados insuficientes" in cinco.motivo and "5+" in cinco.motivo
    todas = servico.avaliar_perfil(e1, _perfil(50, "F", 0, COMORBIDADES))
    assert not todas.estimavel
    quatro = servico.avaliar_perfil(e1, _perfil(50, "F", 0, COMORBIDADES[:4]))
    assert quatro.estimavel and explain.NOTA_COMBINACAO in quatro.avisos
    par_excluido = ("DIABETES", "ACIDO_PEPT")
    assert frozenset(par_excluido) in {frozenset(p) for p in e1.pares_excluidos}
    sem = servico.avaliar_perfil(e1, _perfil(50, "F", 0, par_excluido))
    assert not sem.estimavel and "dados insuficientes" in sem.motivo
    assert servico.avaliar_perfil(e1, _perfil(50, "F", 0, ("DIABETES", "RENAL"))).estimavel


def test_avisos_do_perfil_trio_e_padrao_suspeito(e1):
    trio = servico.avaliar_perfil(e1, _perfil(75, "M", 0, ("DIABETES", "RENAL", "HEMATOLOG")))
    assert explain.NOTA_TRIO in trio.avisos
    assert explain.AVISO_PADRAO in trio.avisos  # HEMATOLOG + RENAL (D-77)
    par = servico.avaliar_perfil(e1, _perfil(75, "M", 0, ("DIABETES", "RENAL")))
    assert par.avisos == []


def test_faixa_etaria_usa_as_faixas_do_config():
    assert [servico.faixa_etaria(i) for i in (0, 4, 5, 14, 15, 39, 40, 59, 60, 79, 80, 120)] == [
        "0–4", "0–4", "5–14", "5–14", "15–39", "15–39", "40–59", "40–59", "60–79", "60–79",
        "80+", "80+"]


# --- M1 ----------------------------------------------------------------------------------------

CASOS_M1 = [
    bruta(idade=25, sexo="M"),
    bruta(idade=70, sexo="F", sim=("hipertensao", "diabetes", "febre", "vomito"), dias=1),
    bruta(idade=8, sexo="M", sim=("febre", "cefaleia", "petequia_n"), ignorado=("laco",), dias=6),
    bruta(idade=33, sexo="F", gestante="sim", sim=("febre", "mialgia", "nausea"), dias=0),
    bruta(idade=55, sexo="F", sim=("renal_cronica", "hepatopatia", "dor_retro"), dias=12),
]


@precisa_m1
def test_risco_e_alto_risco_do_m1_no_app_batem_com_o_modelo_final_direto(m1_real):
    altos = []
    for bruto in CASOS_M1:
        res = servico.avaliar_caso(m1_real, entrada.validar_caso(bruto))
        direto = float(m1_real.prever_proba(frame_do_contrato(bruto))[0])  # frame feito à mão
        assert res.risco == pytest.approx(direto, rel=1e-9, abs=1e-12)
        assert 0 < res.risco < 1
        assert res.limiar == m1_real.limiar
        assert res.alto_risco == (direto >= m1_real.limiar)
        altos.append(res.alto_risco)
    assert any(altos) and not all(altos)  # o conjunto cobre os dois lados do limiar


def test_alto_risco_e_risco_maior_ou_igual_ao_limiar_do_artefato(m1_sint):
    """Limiar do artefato, não uma constante: com 3 limiares diferentes, o corte acompanha."""
    caso = entrada.validar_caso(CASOS_M1[1])
    risco = servico.avaliar_caso(m1_sint, caso).risco
    for limiar, esperado in [(risco - 1e-6, True), (risco, True), (risco + 1e-6, False)]:
        final = retreino.ModeloFinal(**{**m1_sint.__dict__, "limiar": limiar})
        res = servico.avaliar_caso(final, caso)
        assert res.alto_risco is esperado and res.limiar == limiar


def _margem_do_xgboost(final, X):
    _, pre, estimador, n = shap_global._componentes(final.modelo)
    import xgboost as xgb

    dm = xgb.DMatrix(np.asarray(pre.transform(X), dtype=np.float32))
    return float(estimador.get_booster().predict(dm, output_margin=True,
                                                 iteration_range=(0, n))[0])


def _verificar_shap(final, bruto):
    caso = entrada.validar_caso(bruto)
    X = frame_do_contrato(bruto)
    contrib, base = servico.contribuicoes(final, X)
    margem = _margem_do_xgboost(final, X)
    # aditividade do TreeSHAP: valor base + soma das contribuições = log-odds previsto
    assert base + contrib.sum() == pytest.approx(margem, abs=1e-4)
    cru = float(final.modelo.prever_proba(X)[0])  # independente do SHAP
    assert margem == pytest.approx(np.log(cru / (1 - cru)), abs=1e-4)
    assert np.allclose(contrib, retreino.shap_local(final, X))  # as contribuições do `retreino`

    res = servico.avaliar_caso(final, caso)
    assert len(res.fatores) == servico.N_FATORES
    absolutos = [abs(f.contribuicao) for f in res.fatores]
    assert absolutos == sorted(absolutos, reverse=True)  # ordenados por |contribuição|
    assert min(absolutos) >= np.sort(np.abs(contrib))[-servico.N_FATORES] - 1e-12
    assert res.valor_base == pytest.approx(base)
    assert res.log_odds == pytest.approx(margem, abs=1e-4)
    mostradas = sum(f.contribuicao for f in res.fatores)
    assert base + mostradas + res.outros_fatores == pytest.approx(margem, abs=1e-4)
    assert {f.campo for f in res.fatores} <= set(final.features)
    # o risco calibrado é o Platt aplicado ao cru
    assert res.risco == pytest.approx(float(final.calibrador.aplicar(cru)), rel=1e-9)
    assert all(f.aumenta == (f.contribuicao > 0) for f in res.fatores)


@pytest.mark.parametrize("bruto", CASOS_M1)
def test_fatores_somam_com_o_valor_base_o_log_odds_e_vem_ordenados_modelo_sintetico(m1_sint,
                                                                                     bruto):
    _verificar_shap(m1_sint, bruto)


@precisa_m1
@pytest.mark.parametrize("bruto", CASOS_M1)
def test_fatores_somam_com_o_valor_base_o_log_odds_e_vem_ordenados_modelo_real(m1_real, bruto):
    _verificar_shap(m1_real, bruto)


def test_valor_mostrado_de_cada_fator_e_o_que_foi_informado(m1_sint):
    bruto = bruta(idade=70, sexo="F", sim=("hipertensao", "febre"), ignorado=("laco",), dias=9)
    caso = entrada.validar_caso(bruto)
    valores = {c: servico._valor_do_fator(caso, c) for c in m1_sint.features}
    assert valores["idade_anos"] == "70 anos" and valores["dias_ate_notificacao"] == "9 dias"
    assert valores["HIPERTENSA"] == "Sim" and valores["LACO"] == "Ignorado"
    assert valores["DIABETES"] == "Não" and valores["n_comorbidades"] == "1"
    assert valores["sexo"] == "Feminino" and valores["gestante"] == "Não"


# Casos da regra B2 escritos à mão: (entrada, deve cair no grupo B).
CASOS_B2 = [
    (bruta(idade=30, sexo="M"), False),
    (bruta(idade=30, sexo="M", ignorado=("diabetes", "laco", "petequia_n")), False),
    (bruta(idade=65, sexo="M"), False),  # 65 não entra
    (bruta(idade=66, sexo="M"), True),
    (bruta(idade=2, sexo="M"), False),  # 2 anos completos não entra
    (bruta(idade=1, sexo="M"), True),
    (bruta(idade=0, sexo="F"), True),
    (bruta(idade=30, sexo="F", gestante="sim"), True),
    (bruta(idade=30, sexo="F", gestante="ignorado"), False),
    (bruta(idade=30, sexo="M", sim=("autoimune",)), True),
    (bruta(idade=30, sexo="M", sim=("laco",)), True),
    (bruta(idade=30, sexo="M", sim=("petequia_n",)), True),
    (bruta(idade=30, sexo="M", sim=("febre", "mialgia", "vomito")), False),
]


@pytest.mark.parametrize(("bruto", "esperado"), CASOS_B2)
def test_regra_b2_do_app_bate_com_a_regra_do_protocolo_e_com_o_caso_escrito_a_mao(
        m1_sint, bruto, esperado):
    res = servico.avaliar_caso(m1_sint, entrada.validar_caso(bruto))
    assert res.grupo_b_b2 is esperado
    assert bool(baselines.rule_b2(frame_do_contrato(bruto))[0]) is esperado


# --- Artefatos ausentes e painel ---------------------------------------------------------------

def test_sem_m1_final_a_triagem_vira_mensagem_e_o_e1_segue(tmp_path):
    shutil.copytree(RAIZ / "models" / "e1", tmp_path / "e1")
    a = servico.carregar_artefatos(tmp_path, tmp_path / "sem_relatorios")
    assert a.e1 is not None and a.erro_e1 is None
    assert a.m1 is None and a.erro_m1 == servico.MSG_M1_AUSENTE
    assert "não está disponível nesta instalação" in a.erro_m1
    assert a.painel is None


def test_pasta_vazia_nao_derruba_a_carga(tmp_path):
    a = servico.carregar_artefatos(tmp_path, tmp_path)
    assert a.e1 is None and a.erro_e1 == servico.MSG_E1_AUSENTE
    assert a.m1 is None and a.erro_m1


def test_artefato_adulterado_vira_mensagem_sem_expor_caminho(tmp_path):
    shutil.copytree(RAIZ / "models" / "e1", tmp_path / "e1")
    npz = tmp_path / "e1" / "payload" / "e1.npz"
    npz.write_bytes(npz.read_bytes() + b"x")
    a = servico.carregar_artefatos(tmp_path, tmp_path)
    assert a.e1 is None and "ArtefatoInvalido" in a.erro_e1 and str(tmp_path) not in a.erro_e1


def test_caminho_vem_da_variavel_de_ambiente_ou_do_config(monkeypatch, tmp_path):
    monkeypatch.setenv(servico.ENV_MODELOS, str(tmp_path / "m"))
    monkeypatch.setenv(servico.ENV_RELATORIOS, str(tmp_path / "r"))
    assert servico.pasta_modelos() == tmp_path / "m"
    assert servico.pasta_relatorios() == tmp_path / "r"
    monkeypatch.delenv(servico.ENV_MODELOS)
    monkeypatch.delenv(servico.ENV_RELATORIOS)
    assert servico.pasta_modelos() == RAIZ / "models"
    assert servico.pasta_relatorios() == RAIZ / "reports"


def _metricas_sinteticas(**ajustes) -> dict:
    d = {
        "casos": 2_000_000, "eventos": 4_000,
        "analises": {
            "metricas": {"modelos": {
                "M1": {"limiar": 0.0031, "obs_esp": {"valor": 1.25},
                       "no_limiar": {"alertas": 300_000, "precisao": {"valor": 0.0123},
                                     "recall": {"valor": 0.7}}},
                "E1": {"obs_esp": {"valor": 1.1}},
            }},
            "criterios": {"sc02": {"passou": False, "detalhe": {
                "recall": {"B2": {"valor": 0.72},
                           "diferenca": {"valor": -0.02, "ic95": [-0.03, -0.01]}},
                "precisao": {"B2": {"valor": 0.0061}}}}},
        },
    }
    d.update(ajustes)
    return d


def _gravar_painel(pasta: Path, conteudo: dict | str) -> Path:
    arquivo = pasta / "teste" / "metricas.json"
    arquivo.parent.mkdir(parents=True)
    arquivo.write_text(conteudo if isinstance(conteudo, str) else json.dumps(conteudo),
                       encoding="utf-8")
    return pasta


def test_painel_vem_do_arquivo_formatado_em_pt_br(tmp_path):
    p = servico.ler_painel(_gravar_painel(tmp_path, _metricas_sinteticas()))
    texto = "\n".join(servico.linhas_painel(p))
    assert "2.000.000 casos, 4.000" in texto
    assert "cerca de 15% dos casos" in texto  # 300 mil de 2 milhões
    assert "0,31%" not in texto and "0,3100%" in texto  # limiar do arquivo, 4 casas
    assert "1,23% evoluíram" in texto  # precisão do arquivo
    assert "recall no limiar foi 70%" in texto
    assert "cerca de 25% maior que o previsto" in texto and "subestimou" in texto
    assert "estimativa possivelmente baixa" in texto and "piso" not in texto
    assert "desfecho conhecido" in texto
    assert "cerca de 10% maior" in texto  # E1
    assert "SC-02" in texto and "não atendido" in texto
    assert "-2,0 ponto percentual" in texto and "-3,0 a -1,0" in texto
    assert "1,23% contra 0,61% da B2" in texto


def test_legenda_do_alto_risco_vem_da_precisao_do_arquivo(tmp_path):
    p = servico.ler_painel(_gravar_painel(tmp_path, _metricas_sinteticas()))  # precisão 1,23%
    legenda = servico.legenda_alto_risco(p)
    assert legenda.startswith("No teste de 2024, cerca de 99% dos casos marcados assim")
    assert "baixa precisão, não um diagnóstico" in legenda
    d = _metricas_sinteticas()
    d["analises"]["metricas"]["modelos"]["M1"]["no_limiar"]["precisao"]["valor"] = 0.25
    outra = servico.legenda_alto_risco(servico.ler_painel(_gravar_painel(tmp_path / "o", d)))
    assert "cerca de 75% dos casos" in outra
    assert servico.legenda_alto_risco(None) == (
        "É um sinal de triagem de baixa precisão, não um diagnóstico.")


def test_painel_com_modelo_superestimando_nao_diz_estimativa_baixa(tmp_path):
    d = _metricas_sinteticas()
    d["analises"]["metricas"]["modelos"]["M1"]["obs_esp"]["valor"] = 0.8
    texto = "\n".join(servico.linhas_painel(servico.ler_painel(_gravar_painel(tmp_path, d))))
    assert "superestimou" in texto and "possivelmente baixa" not in texto and "20% menor" in texto


@pytest.mark.parametrize("conteudo", ["{não é json", "[]", "{}", json.dumps({"casos": 0})])
def test_painel_ausente_ou_malformado_some_sem_erro(tmp_path, conteudo):
    assert servico.ler_painel(tmp_path) is None
    assert servico.ler_painel(_gravar_painel(tmp_path, conteudo)) is None


def test_painel_real_bate_com_o_json_do_teste():
    arquivo = RAIZ / "reports" / "teste" / "metricas.json"
    if not arquivo.is_file():
        pytest.skip("reports/teste/metricas.json não existe")
    d = json.loads(arquivo.read_text(encoding="utf-8"))
    m1 = d["analises"]["metricas"]["modelos"]["M1"]
    p = servico.ler_painel(RAIZ / "reports")
    assert p.casos == d["casos"] and p.limiar == m1["limiar"]
    assert p.fracao_alto_risco == pytest.approx(m1["no_limiar"]["alertas"] / d["casos"])
    assert p.recall == m1["no_limiar"]["recall"]["valor"]
    assert p.obs_esp_m1 == m1["obs_esp"]["valor"] > 1
    texto = "\n".join(servico.linhas_painel(p))
    assert "subestimou o risco em 2024" in texto and "possivelmente baixa" in texto


# --- Compatibilidade do joblib em GPU com o XGBoost sem GPU ------------------------------------

def test_leitura_tolerante_do_booster_recupera_as_arvores_quando_a_desserializacao_falha():
    import pickle

    import xgboost as xgb

    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 3))
    y = (X[:, 0] + rng.normal(size=200) > 0).astype(int)
    clf = xgb.XGBClassifier(n_estimators=7, max_depth=2, device="cpu").fit(X, y)
    esperado = clf.predict_proba(X)[:, 1]
    blob = pickle.dumps(clf)
    original = xgb.Booster.__setstate__

    def falha(self, estado):
        raise xgb.core.XGBoostError("input stream corrupted")

    xgb.Booster.__setstate__ = falha  # a leitura completa falha, como no joblib congelado
    try:
        with pytest.raises(xgb.core.XGBoostError):
            pickle.loads(blob)
        with servico._booster_com_leitura_tolerante():  # embrulha o `__setstate__` instalado
            carregado = pickle.loads(blob)
        with pytest.raises(xgb.core.XGBoostError):  # fora do bloco, a falha volta
            pickle.loads(blob)
    finally:
        xgb.Booster.__setstate__ = original
    assert xgb.Booster.__setstate__ is original  # restaurado
    assert carregado.get_booster().num_boosted_rounds() == 7
    assert np.allclose(carregado.predict_proba(X)[:, 1], esperado, atol=1e-6)


@precisa_m1
def test_m1_real_carrega_pelo_servico_com_as_arvores_e_o_limiar_do_metadata(m1_real):
    pasta = next(RAIZ / "models" / n for n in servico.NOMES_M1
                 if (RAIZ / "models" / n / "metadata.json").is_file())
    meta = artifacts.ler_metadados(pasta)
    assert m1_real.limiar == meta["m1"]["limiar"]
    assert m1_real.modelo.melhor_ponto() + 1 == meta["m1"]["iteracoes_finais"]
    assert len(m1_real.features) == 26


# --- Privacidade (NFR-03) ----------------------------------------------------------------------

def _escritas(monkeypatch) -> list:
    """Registra toda tentativa de abrir arquivo para escrita enquanto o teste roda."""
    import builtins
    import io
    import os

    registro = []
    abrir = builtins.open

    def espia(arquivo, modo="r", *a, **k):
        if isinstance(modo, str) and any(c in modo for c in "wax+"):
            registro.append(("open", str(arquivo), modo))
        return abrir(arquivo, modo, *a, **k)

    def espia_os(caminho, flags, *a, **k):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND):
            registro.append(("os.open", str(caminho), flags))
        return os_open(caminho, flags, *a, **k)

    os_open = os.open
    monkeypatch.setattr(builtins, "open", espia)
    monkeypatch.setattr(io, "open", espia)
    monkeypatch.setattr(os, "open", espia_os)
    return registro


def _sem_rede(monkeypatch):
    """Recusa conexão a qualquer endereço que não seja a própria máquina (o asyncio do Windows
    usa um par de sockets locais; isso não é rede)."""
    conectar, conectar_ex = socket.socket.connect, socket.socket.connect_ex

    def so_local(original):
        def verificar(self, endereco, *a, **k):
            host = endereco[0] if isinstance(endereco, tuple) else endereco
            if host not in ("127.0.0.1", "::1", "localhost"):
                raise AssertionError(f"a demo não pode abrir conexão de rede (NFR-03): {host}")
            return original(self, endereco, *a, **k)
        return verificar

    monkeypatch.setattr(socket.socket, "connect", so_local(conectar))
    monkeypatch.setattr(socket.socket, "connect_ex", so_local(conectar_ex))


SENTINELA = dict(idade=103, dias=59)


def _usar_servico(e1, m1):
    bruto = bruta(idade=SENTINELA["idade"], sexo="F", dias=SENTINELA["dias"],
                  sim=("diabetes", "febre"))
    servico.avaliar_caso(m1, entrada.validar_caso(bruto))
    servico.avaliar_perfil(e1, _perfil(SENTINELA["idade"], "F", 0, ("DIABETES",)))
    with pytest.raises(entrada.EntradaInvalida):
        entrada.validar_caso({**bruto, "idade_anos": 121})


def test_uso_do_servico_nao_grava_em_disco_nem_loga_a_entrada_nem_abre_rede(
        monkeypatch, caplog, capsys, e1, m1_sint):
    _usar_servico(e1, m1_sint)  # aquecimento: imports e caches preguiçosos fora da medição
    escritas = _escritas(monkeypatch)
    _sem_rede(monkeypatch)
    caplog.set_level(logging.DEBUG)
    _usar_servico(e1, m1_sint)
    assert escritas == []
    textos = [r.getMessage() for r in caplog.records]
    assert not [t for t in textos if re.search(r"\b103\b|\b59\b|idade_anos|DIABETES", t)]
    saida = capsys.readouterr()
    assert not re.search(r"\b103\b|\b59\b", saida.out + saida.err)


def test_modulos_da_demo_nao_importam_logging_nem_clientes_de_rede():
    for nome in ("entrada", "servico", "streamlit_app"):
        fonte = (RAIZ / "src" / "app" / f"{nome}.py").read_text(encoding="utf-8")
        importados = set(re.findall(r"^\s*(?:import|from)\s+([\w.]+)", fonte, flags=re.M))
        assert not importados & {"logging", "requests", "urllib", "http", "socket", "smtplib",
                                 "sqlite3", "shelve", "pickle"}, nome
        assert "print(" not in fonte and "open(" not in fonte.replace("st.", ""), nome
