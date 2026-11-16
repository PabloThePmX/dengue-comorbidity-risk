import hashlib
import json

import pandas as pd
import pytest

from dengue_sinan import verify


def _cfg(tmp_path, anos=(2022, 2023), gpu="T4", ram_min=50):
    return {
        "anos_dev": list(anos),
        "caminhos": {"dados": str(tmp_path / "data")},
        "ambiente": {"gpu": gpu, "ram_min_gib": ram_min},
    }


def test_check_passa_e_falha_com_tolerancia_zero():
    ok = verify.check("casos_dev", 2453208, 2453208)
    ruim = verify.check("eventos_dev", 3985, 3984)
    assert ok == {"nome": "casos_dev", "esperado": 2453208, "obtido": 2453208,
                  "tolerancia": 0, "passou": True}
    assert ruim["passou"] is False


def test_check_respeita_tolerancia_e_compara_texto_e_booleano():
    assert verify.check("media", 1.0, 1.04, tolerancia=0.05)["passou"] is True
    assert verify.check("media", 1.0, 1.06, tolerancia=0.05)["passou"] is False
    assert verify.check("gpu", "T4", "T4")["passou"] is True
    assert verify.check("gpu", "T4", "L4")["passou"] is False
    # True não é 1: tipos diferentes nunca passam
    assert verify.check("flag", True, 1)["passou"] is False


@pytest.mark.parametrize("obtido", [[1, 2, 3], (1, 2), pd.DataFrame({"a": [1]}), None])
def test_check_recusa_valor_que_nao_e_agregado(obtido):
    with pytest.raises(TypeError, match="R7"):
        verify.check("x", 1, obtido)


def test_write_report_grava_formato_do_contrato_e_le_de_volta(tmp_path):
    cfg = _cfg(tmp_path)
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "manifest.json").write_text(
        json.dumps({"2022": {"sha256_dbc": "aa"}, "2023": {"sha256_dbc": "bb"}}), "utf-8")
    checks = [verify.check("casos_dev", 10, 10), verify.check("eventos_dev", 3, 3)]

    caminho = verify.write_report("T-2.1", checks, tmp_path / "out", cfg)

    assert caminho == tmp_path / "out" / "T-2.1.json"
    lido = json.loads(caminho.read_text("utf-8"))
    assert lido["tarefa"] == "T-2.1"
    assert lido["checks"] == checks
    assert lido["passou"] is True
    assert lido["hash_dados"] == {"2022": "aa", "2023": "bb"}
    assert set(lido) >= {"tarefa", "gerado_em", "commit", "ambiente", "hash_dados", "checks",
                         "passou"}


def test_write_report_passou_false_se_algum_check_falha_ou_sem_checks(tmp_path):
    cfg = _cfg(tmp_path)
    misto = [verify.check("a", 1, 1), verify.check("b", 1, 2)]
    lido = json.loads(verify.write_report("T-2.1", misto, tmp_path, cfg).read_text("utf-8"))
    assert lido["passou"] is False
    vazio = json.loads(verify.write_report("T-2.2", [], tmp_path, cfg).read_text("utf-8"))
    assert vazio["passou"] is False


def test_write_report_recusa_id_de_tarefa_que_nao_e_id(tmp_path):
    with pytest.raises(ValueError):
        verify.write_report("../fora", [], tmp_path, _cfg(tmp_path))


def test_update_session_report_preserva_outros_blocos_e_recalcula_passou(tmp_path):
    cfg = _cfg(tmp_path)
    caminho = tmp_path / "sessao-m1.json"
    ok = [verify.check("n", 1, 1)]
    ruim = [verify.check("n", 1, 2)]

    verify.update_session_report(caminho, "checagem_inicial", ok, cfg, tarefa="T-4.3b")
    verify.update_session_report(caminho, "elastic_net", ruim, cfg, tarefa="T-4.6b")
    final = verify.update_session_report(caminho, "retreino", ok, cfg, tarefa="T-4.10",
                                         sessao_completa=True)

    lido = json.loads(final.read_text("utf-8"))
    nomes = [b["bloco"] for b in lido["blocos"]]
    assert nomes == ["checagem_inicial", "elastic_net", "retreino"]
    assert lido["passou"] is False  # elastic_net falhou

    # reescrever um bloco não apaga os outros e pode corrigir o geral
    verify.update_session_report(caminho, "elastic_net", ok, cfg, tarefa="T-4.6b",
                                 sessao_completa=True)
    lido = json.loads(caminho.read_text("utf-8"))
    assert [b["bloco"] for b in lido["blocos"]] == ["checagem_inicial", "retreino",
                                                    "elastic_net"]
    assert lido["passou"] is True


def test_update_session_report_sem_sessao_completa_nao_passa(tmp_path):
    cfg = _cfg(tmp_path)
    caminho = verify.update_session_report(tmp_path / "s.json", "a", [verify.check("n", 1, 1)],
                                           cfg)
    assert json.loads(caminho.read_text("utf-8"))["passou"] is False


def test_show_report_imprime_e_devolve_o_sha256_dos_bytes(tmp_path, capsys):
    arquivo = tmp_path / "T-2.1.json"
    arquivo.write_bytes(b'{"passou": true}\n')

    sha = verify.show_report(arquivo)

    assert sha == hashlib.sha256(arquivo.read_bytes()).hexdigest()
    saida = capsys.readouterr().out
    assert '{"passou": true}' in saida
    assert sha in saida


def test_environment_reprova_ram_abaixo_do_minimo(tmp_path):
    cfg = _cfg(tmp_path, gpu="T4", ram_min=50)
    checks = verify.environment(cfg, gpu_nome="Tesla T4", ram_gib=15.9, vcpus=4)
    por_nome = {c["nome"]: c for c in checks}
    assert por_nome["ram_gib"]["passou"] is False
    assert por_nome["gpu"]["passou"] is True
    assert por_nome["vcpus"]["obtido"] == 4


def test_environment_aprova_ram_suficiente_e_reprova_gpu_errada(tmp_path):
    cfg = _cfg(tmp_path, gpu="T4", ram_min=50)
    por_nome = {c["nome"]: c for c in verify.environment(
        cfg, gpu_nome="NVIDIA L4", ram_gib=53.0, vcpus=8)}
    assert por_nome["ram_gib"]["passou"] is True
    assert por_nome["gpu"]["passou"] is False


def test_environment_sem_gpu_exigida_aceita_cpu(tmp_path):
    cfg = _cfg(tmp_path, gpu=None, ram_min=12)
    por_nome = {c["nome"]: c for c in verify.environment(
        cfg, gpu_nome=None, ram_gib=12.7, vcpus=2)}
    assert por_nome["gpu"]["passou"] is True
    assert por_nome["ram_gib"]["passou"] is True
