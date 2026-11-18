"""Etapa 2 — treino, artefatos, inferência, reprodutibilidade e guardas R1/R4."""

import json
import subprocess
import sys
from dataclasses import replace

import numpy as np
import pytest
from conftest_pipeline import config_rapida, mundo  # noqa: F401

from dengue_sinan.etapa1 import carregar_bruto_dev
from dengue_sinan.pipeline import artefatos
from dengue_sinan.pipeline.contrato import RAIZ
from dengue_sinan.pipeline.inferencia import EntradaInvalida, carregar_modelo
from dengue_sinan.pipeline.preparacao import carregar_preparado, salvar_preparado
from dengue_sinan.pipeline.treino import ConfigTreino, repetir_e_comparar, treinar, treinar_e_salvar

REG = [{"idade_anos": 30, "sexo": "F", "gestante": 0}, {"idade_anos": 80, "sexo": "M"}]


# ----------------------------------------------------------------------------- artefato
def test_artefato_tem_os_arquivos_e_metadados_exigidos(mundo):  # noqa: F811
    pasta = mundo["artefato"]
    assert {p.name for p in pasta.iterdir()} == {
        "modelo.joblib",
        "metadados.json",
        "contrato.json",
        "avaliacao_dev.json",
    }
    m = json.loads((pasta / "metadados.json").read_text("utf-8"))
    for chave in (
        "versao_modelo",
        "algoritmo",
        "params",
        "variaveis_de_entrada",
        "tipos_esperados",
        "preprocessamento",
        "ambiente",
        "anos_desenvolvimento",
        "data_treinamento_utc",
        "hashes_sha256",
        "reprodutibilidade",
        "limitacoes",
        "dados",
    ):
        assert chave in m
    assert m["anos_desenvolvimento"] == [2022, 2023]
    assert m["variaveis_de_entrada"] == ["idade_anos", "sexo", "gestante"]
    assert "scikit-learn" in m["ambiente"] and "xgboost" in m["ambiente"]
    av = json.loads((pasta / "avaliacao_dev.json").read_text("utf-8"))
    assert av["e_teste_historico"] is False and "calibracao" in av["calibrado_validacao_cruzada"]


def test_hash_adulterado_e_detectado(mundo, tmp_path):  # noqa: F811
    copia = tmp_path / "a"
    copia.mkdir()
    for p in mundo["artefato"].iterdir():
        (copia / p.name).write_bytes(p.read_bytes())
    carregar_modelo(copia)  # íntegro
    with (copia / "modelo.joblib").open("ab") as f:
        f.write(b"x")
    with pytest.raises(artefatos.ArtefatoInvalido, match="hash"):
        carregar_modelo(copia)


def test_artefato_incompleto_e_recusado(mundo, tmp_path):  # noqa: F811
    copia = tmp_path / "b"
    copia.mkdir()
    (copia / "metadados.json").write_bytes((mundo["artefato"] / "metadados.json").read_bytes())
    with pytest.raises(artefatos.ArtefatoInvalido, match="ausente"):
        carregar_modelo(copia)


def test_nao_sobrescreve_artefato_existente(mundo):  # noqa: F811
    with pytest.raises(FileExistsError):
        treinar_e_salvar(
            mundo["x"],
            mundo["y"],
            mundo["regiao"],
            mundo["meta"],
            mundo["cfg"],
            mundo["artefato"].parent,
        )


def test_recusa_gravar_na_area_historica_da_v1():
    with pytest.raises(PermissionError, match="históricos"):
        artefatos.salvar(
            RAIZ / "reports" / "modelo_risco_dengue" / "artefatos", "m", "1", {}, {}, {}, {}
        )


# ----------------------------------------------------------------------------- inferência
def test_previsao_com_registros_validos(mundo):  # noqa: F811
    p = carregar_modelo(mundo["artefato"]).prever(REG)
    assert p["status"].tolist() == ["ok", "ok"]
    assert p["probabilidade"].between(0, 1).all()
    assert (p["versao_modelo"] == "m1-perfil-2.0.0").all()


def test_ordem_dos_registros_e_preservada(mundo):  # noqa: F811
    m = carregar_modelo(mundo["artefato"])
    direto = m.prever(REG)["probabilidade"].to_numpy()
    invertido = m.prever(REG[::-1])["probabilidade"].to_numpy()[::-1]
    assert np.array_equal(direto, invertido)


def test_ordem_das_chaves_no_registro_nao_importa(mundo):  # noqa: F811
    m = carregar_modelo(mundo["artefato"])
    a = m.prever([{"idade_anos": 30, "sexo": "F", "gestante": 0}])
    b = m.prever([{"gestante": 0, "sexo": "F", "idade_anos": 30}])
    assert a["probabilidade"].iloc[0] == b["probabilidade"].iloc[0]


def test_registro_invalido_levanta_por_padrao(mundo):  # noqa: F811
    m = carregar_modelo(mundo["artefato"])
    with pytest.raises(EntradaInvalida) as e:
        m.prever([{"idade_anos": 30}, {"idade_anos": 500}])
    assert e.value.erros[0]["indice"] == 1


def test_modo_marcar_devolve_nulo_so_no_invalido(mundo):  # noqa: F811
    m = carregar_modelo(mundo["artefato"])
    p = m.prever([{"idade_anos": "x", "sexo": "Z"}, {"idade_anos": 30}], erros="marcar")
    assert p["status"].tolist() == ["invalido", "ok"]
    assert np.isnan(p["probabilidade"].iloc[0]) and "idade_anos" in p["erro"].iloc[0]
    assert "sexo" in p["erro"].iloc[0]
    assert 0 <= p["probabilidade"].iloc[1] <= 1


def test_campo_extra_levanta_mesmo_no_modo_marcar(mundo):  # noqa: F811
    with pytest.raises(EntradaInvalida):
        carregar_modelo(mundo["artefato"]).prever(
            [{"idade_anos": 3, "HOSPITALIZ": "1"}], erros="marcar"
        )


def test_inferencia_nao_ajusta_o_modelo(mundo):  # noqa: F811
    m = carregar_modelo(mundo["artefato"])
    antes = m.prever(REG)["probabilidade"].to_numpy()
    for _ in range(3):
        m.prever([{"idade_anos": i} for i in range(0, 100, 7)])
    assert np.array_equal(antes, m.prever(REG)["probabilidade"].to_numpy())


def test_inferencia_roda_sem_dados_de_treino_e_sem_modulos_de_treino(mundo, tmp_path):  # noqa: F811
    """Subprocesso em outra pasta, sem Parquets: só o artefato. Confere os módulos importados."""
    codigo = (
        "import sys, json\n"
        "from dengue_sinan.pipeline.inferencia import carregar_modelo\n"
        f"m = carregar_modelo({str(mundo['artefato'])!r})\n"
        "p = m.prever([{'idade_anos': 30, 'sexo': 'F'}])\n"
        "proibidos = ['dengue_sinan.pipeline.treino', 'dengue_sinan.pipeline.preparacao',\n"
        "             'dengue_sinan.etapa1', 'dengue_sinan.download', 'dengue_sinan.explain']\n"
        "print(json.dumps({'ok': p['status'].tolist(),\n"
        "                  'importados': [s for s in proibidos if s in sys.modules]}))\n"
    )
    saida = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
        env={**__import__("os").environ, "PYTHONPATH": str(RAIZ / "src")},
    )
    r = json.loads(saida.stdout.strip().splitlines()[-1])
    assert r == {"ok": ["ok"], "importados": []}


# ----------------------------------------------------------------------------- guardas
def test_treino_recusa_dado_de_2024(mundo):  # noqa: F811
    meta = mundo["meta"].copy()
    meta.loc[meta.index[:5], "ANO"] = 2024
    with pytest.raises(PermissionError, match="R1"):
        treinar(mundo["x"], mundo["y"], mundo["regiao"], meta, mundo["cfg"])


def test_config_com_2024_e_recusada(mundo):  # noqa: F811
    with pytest.raises(PermissionError, match="R1"):
        replace(mundo["cfg"], anos_desenvolvimento=[2022, 2023, 2024]).validar()


def test_config_com_variavel_nao_autorizada_e_recusada(mundo):  # noqa: F811
    with pytest.raises((ValueError, PermissionError)):
        replace(mundo["cfg"], variaveis=["idade_anos", "DIABETES"]).validar()


def test_carregar_preparado_recusa_ano_2024(mundo, tmp_path):  # noqa: F811
    df = mundo["conjunto"].copy()
    df.loc[df.index[:3], "ANO"] = 2024
    caminho = salvar_preparado(df, tmp_path / "x.parquet")
    with pytest.raises(PermissionError, match="R1"):
        carregar_preparado(caminho, mundo["cfg"].variaveis)


def test_leitura_dos_parquets_recusa_2024(mundo):  # noqa: F811
    with pytest.raises(PermissionError):
        carregar_bruto_dev(mundo["dados"], anos=(2023, 2024))


def test_nao_salva_microdados_em_reports(mundo):  # noqa: F811
    with pytest.raises(PermissionError, match="reports"):
        salvar_preparado(mundo["conjunto"], RAIZ / "reports" / "etapa2" / "nao_pode.parquet")
    assert not (RAIZ / "reports" / "etapa2" / "nao_pode.parquet").exists()


def test_conjunto_preparado_nao_tem_variavel_fora_da_lista(mundo):  # noqa: F811
    assert set(mundo["conjunto"].columns) == {
        "idade_anos",
        "sexo",
        "gestante",
        "y",
        "ANO",
        "regiao",
        # Etapa 3.2: identificador de agrupamento só para o bootstrap por conglomerado.
        # `carregar_preparado` não o devolve e ele nunca entra na matriz de preditores.
        "conglomerado",
    }


# ----------------------------------------------------------------------------- reprodutibilidade
def test_mesmos_insumos_reproduzem_o_treino(mundo):  # noqa: F811
    r = repetir_e_comparar(mundo["x"], mundo["y"], mundo["regiao"], mundo["meta"], mundo["cfg"])
    assert r["oof_identico"] and r["oof_calibrado_identico"] and r["iteracoes_identicas"]
    assert r["n_arvores_final"][0] == r["n_arvores_final"][1]


def test_hash_dos_dados_depende_da_ordem_das_linhas(mundo):  # noqa: F811
    from dengue_sinan.pipeline.treino import hash_dados

    x, y = mundo["x"], mundo["y"]
    h1 = hash_dados(x, y)
    assert h1 == hash_dados(x, y)
    idx = np.random.default_rng(0).permutation(len(x))
    assert h1 != hash_dados(x.iloc[idx], y[idx])


def test_configuracao_padrao_do_repositorio_e_valida():
    cfg = ConfigTreino.de_arquivo(RAIZ / "config" / "treino_perfil.json")
    assert cfg.variaveis == ["idade_anos", "sexo", "gestante"] and cfg.algoritmo == "xgboost"
    assert cfg.params["max_depth"] == 3 and cfg.seed == 20261103  # herdados da v1


def test_avaliacao_separa_desenvolvimento_do_teste_historico(mundo):  # noqa: F811
    av = json.loads((mundo["artefato"] / "avaliacao_dev.json").read_text("utf-8"))
    assert "2022–2023" in av["escopo"] and av["e_teste_historico"] is False
    assert av["limitacoes"] and not any("2024" in k for k in av["calibrado_validacao_cruzada"])


# ----------------------------------------------------------------------------- CLI de ponta a ponta
def test_cli_preparar_treinar_prever(mundo, tmp_path, capsys):  # noqa: F811
    from dengue_sinan.pipeline.cli import main

    cfg = tmp_path / "cfg.json"
    base = json.loads((RAIZ / "config" / "treino_perfil.json").read_text("utf-8"))
    cfg.write_text(
        json.dumps(
            {**base, "max_iter": 40, "paciencia": 5, "n_jobs": 2, "versao_modelo": "teste-cli"}
        ),
        "utf-8",
    )
    prep = tmp_path / "p.parquet"
    assert main(["preparar", "--data-dir", str(mundo["dados"]), "--saida", str(prep)]) == 0
    assert (
        main(
            [
                "treinar",
                "--config",
                str(cfg),
                "--dados",
                str(prep),
                "--saida",
                str(tmp_path / "art"),
            ]
        )
        == 0
    )
    art = tmp_path / "art" / "m1-perfil-teste-cli"
    entrada = tmp_path / "in.json"
    entrada.write_text(json.dumps(REG), "utf-8")
    capsys.readouterr()
    assert main(["prever", "--artefato", str(art), "--entrada", str(entrada)]) == 0
    saida = json.loads(capsys.readouterr().out)
    assert [r["status"] for r in saida] == ["ok", "ok"]
    entrada.write_text(json.dumps([{"idade_anos": "abc"}]), "utf-8")
    assert main(["prever", "--artefato", str(art), "--entrada", str(entrada)]) == 2
    assert main(["avaliar", "--artefato", str(art)]) == 0


def test_pacote_nao_tem_caminho_absoluto_da_maquina():
    for p in (RAIZ / "src" / "dengue_sinan" / "pipeline").glob("*.py"):
        texto = p.read_text("utf-8")
        assert "/home/" not in texto and "C:\\" not in texto, p.name
