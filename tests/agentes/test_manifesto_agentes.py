"""Testes do manifesto v2 em árvore fictícia. Não toca nos arquivos reais do projeto."""

import json
import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "agentes" / "scripts"))
import manifesto as M

POL_REAL = RAIZ / "agentes" / "estado" / "protegidos.json"
pytestmark = pytest.mark.skipif(not POL_REAL.exists(), reason="protegidos.json ausente")


@pytest.fixture
def arv(tmp_path):
    r = tmp_path / "proj"
    (r / "agentes" / "estado").mkdir(parents=True)
    shutil.copy(POL_REAL, r / "agentes" / "estado" / "protegidos.json")
    arqs = {
        "CLAUDE.md": "regras",
        "specs/spec.md": "spec",
        "agentes/decisoes/DECISOES.md": "decisoes",
        "agentes/estado/estado.json": "{}",
        "config/a.json": "{}",
        "src/x.py": "print(1)",
        "reports/modelo_risco_dengue/tabelas/or.csv": "a,b",
        "reports/modelo_risco_dengue/tabelas/teste_nri.csv": "SEGREDO-NRI",
        "reports/modelo_risco_dengue/LACRE_TESTE_2024.json": "{}",
        "reports/modelo_risco_dengue/tabelas/teste_2024_resultados.json": "SEGREDO-2024",
        "data/raw/DENGBR24.dbc": "SEGREDO-DBC",
        "data/processed/dev.parquet": "SEGREDO-PQ",
        "artefatos/oof/3.2.0/oof.parquet": "SEGREDO-OOF",
        "x/DENGBR24.csv": "SEGREDO-X",
        ".venv/lib/a.py": "v",
    }
    for rel, txt in arqs.items():
        f = r / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(txt)
    (r / "agentes" / "estado" / "manifesto_hashes.json").write_text(
        json.dumps(
            {
                "arquivos": {
                    "CLAUDE.md": {
                        "classe": "SOMENTE_HUMANO",
                        "bytes": 6,
                        "sha256": M.sha256_arquivo(r / "CLAUDE.md"),
                    }
                }
            }
        )
    )
    return r


def carregar(r):
    return M.Politica.carregar(r / "agentes" / "estado" / "protegidos.json")


def ler_nova(r, n):
    return json.loads(
        (
            r / "agentes" / "estado" / "manifestos" / f"manifesto-v{n:03d}.json"
        ).read_text()
    )


def test_gerar_cria_v002_e_nao_toca_no_legado(arv, capsys):
    leg = arv / "agentes" / "estado" / "manifesto_hashes.json"
    antes = leg.read_bytes()
    assert M.main(["gerar"], arv) == 0
    assert leg.read_bytes() == antes
    d = ler_nova(arv, 2)
    for k in (
        "gerado_em_utc",
        "python",
        "script_sha256",
        "protegidos_sha256",
        "politica_lib_sha256",
        "incluir_2024",
        "n_arquivos",
        "versao",
        "anterior",
    ):
        assert k in d["_meta"]
    assert d["_meta"]["versao"] == 2 and d["_meta"]["incluir_2024"] is False
    assert d["_meta"]["anterior"]["arquivo"] == "manifesto_hashes.json"
    assert d["_meta"]["n_arquivos"] == len(d["arquivos"])


def test_selecao_sem_flag(arv):
    M.main(["gerar"], arv)
    chaves = set(ler_nova(arv, 2)["arquivos"])
    assert "CLAUDE.md" in chaves and "specs/spec.md" in chaves
    assert "config/a.json" in chaves  # monitorar_hash
    assert "reports/modelo_risco_dengue/tabelas/or.csv" in chaves
    assert "reports/modelo_risco_dengue/tabelas/teste_nri.csv" in chaves
    assert "reports/modelo_risco_dengue/LACRE_TESTE_2024.json" in chaves
    assert "agentes/decisoes/DECISOES.md" not in chaves  # fora_do_manifesto
    assert "agentes/estado/estado.json" not in chaves
    assert "src/x.py" not in chaves
    for proibido in (
        "data/raw/DENGBR24.dbc",
        "data/processed/dev.parquet",
        "artefatos/oof/3.2.0/oof.parquet",
        "x/DENGBR24.csv",
        "reports/modelo_risco_dengue/tabelas/teste_2024_resultados.json",
        ".venv/lib/a.py",
    ):
        assert proibido not in chaves


def test_2024_so_com_flag_e_em_arquivo_local(arv):
    M.main(["gerar", "--incluir-2024"], arv)
    pasta = arv / "agentes" / "estado" / "manifestos"
    local = json.loads((pasta / "local-2024-v002.json").read_text())["arquivos"]
    assert set(local) == {
        "data/raw/DENGBR24.dbc",
        "x/DENGBR24.csv",
        "reports/modelo_risco_dengue/tabelas/teste_2024_resultados.json",
    }
    assert not (set(local) & set(ler_nova(arv, 2)["arquivos"]))
    assert "data/processed/dev.parquet" not in local  # microdados sem 2024 no nome
    assert "artefatos/oof/3.2.0/oof.parquet" not in local


def test_nunca_sobrescreve_e_cadeia(arv):
    M.main(["gerar"], arv)
    p2 = arv / "agentes" / "estado" / "manifestos" / "manifesto-v002.json"
    ant = p2.read_bytes()
    assert M.main(["gerar"], arv) == 0
    assert p2.read_bytes() == ant
    d3 = ler_nova(arv, 3)
    assert d3["_meta"]["anterior"] == {
        "arquivo": "manifesto-v002.json",
        "sha256": M.sha256_arquivo(p2),
    }
    assert M.main(["verificar"], arv) == 0


def test_cadeia_quebrada(arv, capsys):
    M.main(["gerar"], arv)
    M.main(["gerar"], arv)
    p2 = arv / "agentes" / "estado" / "manifestos" / "manifesto-v002.json"
    p2.write_text(p2.read_text() + " ")
    assert M.main(["verificar"], arv) == 1
    assert "CADEIA" in capsys.readouterr().out


def test_gravar_novo_recusa_existente(tmp_path):
    f = tmp_path / "m.json"
    f.write_text("x")
    with pytest.raises(FileExistsError):
        M._gravar_novo(f, {})
    assert f.read_text() == "x"


def test_verificar_detecta_alterado_ausente_novo(arv, capsys):
    M.main(["gerar"], arv)
    capsys.readouterr()
    (arv / "CLAUDE.md").write_text("mudou")
    (arv / "specs" / "spec.md").unlink()
    (arv / "specs" / "plan.md").write_text("novo")
    assert M.main(["verificar"], arv) == 1
    out = capsys.readouterr().out
    assert "ALTERADO: CLAUDE.md" in out
    assert "AUSENTE: specs/spec.md" in out
    assert "NOVO_EM_AREA_SOMENTE_HUMANO: specs/plan.md" in out
    assert "COMPROMETIDA" in out


def test_verificar_legado_v001(arv, capsys):
    # O legado só registra CLAUDE.md; os demais arquivos só-humanos da árvore são novos para ele.
    assert M.main(["verificar", "--versao", "1"], arv) == 1
    out = capsys.readouterr().out
    assert "NOVO_EM_AREA_SOMENTE_HUMANO: specs/spec.md" in out
    assert "ALTERADO" not in out
    (arv / "CLAUDE.md").write_text("mudou")
    assert M.main(["verificar", "--versao", "1"], arv) == 1
    assert "ALTERADO: CLAUDE.md" in capsys.readouterr().out


def test_verificar_classe_alterada_e_nao_verificado(arv, capsys):
    M.main(["gerar"], arv)
    p = arv / "agentes" / "estado" / "manifestos" / "manifesto-v002.json"
    d = json.loads(p.read_text())
    d["arquivos"]["CLAUDE.md"]["classe"] = "PRESERVADO"
    d["arquivos"]["data/processed/dev.parquet"] = {
        "classe": "X",
        "bytes": 1,
        "sha256": "0",
    }
    p.write_text(json.dumps(d))
    capsys.readouterr()
    M.main(["verificar", "--versao", "2"], arv)
    out = capsys.readouterr().out
    assert "CLASSE_ALTERADA: CLAUDE.md" in out
    assert "NAO_VERIFICADO: data/processed/dev.parquet" in out


def test_comparar(arv, capsys):
    M.main(["gerar"], arv)
    (arv / "CLAUDE.md").write_text("mudou")
    (arv / "specs" / "plan.md").write_text("novo")
    (arv / "specs" / "spec.md").unlink()
    M.main(["gerar"], arv)
    capsys.readouterr()
    assert M.main(["comparar", "2", "3"], arv) == 0
    out = capsys.readouterr().out
    assert "ALTERADO: CLAUDE.md" in out
    assert "ADICIONADO: specs/plan.md" in out
    assert "REMOVIDO: specs/spec.md" in out
    assert M.main(["comparar", "2", "9"], arv) == 2


def test_nao_imprime_conteudo(arv, capsys):
    M.main(["gerar", "--incluir-2024"], arv)
    M.main(["verificar", "--incluir-2024"], arv)
    M.main(["comparar", "1", "2"], arv)
    tudo = capsys.readouterr()
    assert "SEGREDO" not in tudo.out + tudo.err


def test_politica_invalida_falha_fechada(arv):
    (arv / "agentes" / "estado" / "protegidos.json").write_text("{ruim")
    assert M.main(["gerar"], arv) == 3
    assert not (arv / "agentes" / "estado" / "manifestos").exists()


def test_link_simbolico_ignorado(arv, capsys):
    (arv / "specs" / "ln.md").symlink_to(arv / "CLAUDE.md")
    M.main(["gerar"], arv)
    assert "specs/ln.md" not in ler_nova(arv, 2)["arquivos"]
    assert "link simbólico" in capsys.readouterr().err


def test_verificar_avisa_se_politica_mudou(arv, capsys):
    M.main(["gerar"], arv)
    p = arv / "agentes" / "estado" / "protegidos.json"
    d = json.loads(p.read_text())
    d["_aviso"] += " "
    p.write_text(json.dumps(d))
    capsys.readouterr()
    M.main(["verificar"], arv)
    assert "protegidos.json mudou" in capsys.readouterr().err


def test_consistencia_com_manifesto_real():
    """Os caminhos do manifesto real (v001) devem continuar com leitura != nunca na política v2."""
    arq = RAIZ / "agentes" / "estado" / "manifesto_hashes.json"
    if not arq.exists():
        pytest.skip("manifesto real ausente")
    pol = M.Politica.carregar(POL_REAL)
    nunca = [
        k
        for k in json.loads(arq.read_text("utf-8"))["arquivos"]
        if pol.avaliar(k).leitura == "nunca"
    ]
    assert nunca == []  # só compara strings de caminho
