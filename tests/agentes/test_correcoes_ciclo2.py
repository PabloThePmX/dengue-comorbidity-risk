"""Regressão do 2º ciclo: lacunas A1, A2, B1, B2 e B3 apontadas pela auditoria da Peach.
Só nomes fictícios e árvores temporárias."""

import shutil
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "agentes" / "scripts"))
import manifesto as M
import politica_lib as P

POL_REAL = RAIZ / "agentes" / "estado" / "protegidos.json"
pytestmark = pytest.mark.skipif(not POL_REAL.exists(), reason="protegidos.json ausente")


@pytest.fixture(scope="module")
def pol():
    return P.Politica.carregar(POL_REAL)


# ---------------------------------------------------------------- A1
LACUNAS_A1 = [
    "x/dengue_2024.joblib",
    "x/dengue_2024.jsonl",
    "x/dengue_2024.npy",
    "x/dengue_2024.npz",
    "x/dengue_2024.zst",
    "x/dengue_2024.csv.zst",
    "x/dengue_2024.pt",
    "x/dengue_2024.dat",
    "x/dengue_2024.bin",
    "x/dengue_2024.lz4",
    "x/dengue_2024.snappy",
    "x/dengue_2024.geoparquet",
    "x/dengue_2024.toml",
    "x/dengue_2024.cfg",
    "x/dengue_2024.parquet.bak",
    "x/dengue-2024.csv.bak",
    "x/dengue_2024.csv~",
    "x/modelo_2024.joblib",
    "x/relatorio_2024.json",
    "x/relatorio_teste_2024.json",
    "x/DENGUE 2024.csv",
    "x/tabela_2024.json",
    "x/comparacao_2024.json",
    "x/shap_2024.json",
    "x/2024_shap.json",
    "x/dengue_2024.tar.gz",
    "x/dengue_2024.tmp",
    "x/2024_teste_final.json",
]


@pytest.mark.parametrize("rel", LACUNAS_A1)
def test_a1_lacunas_de_2024_fechadas(pol, rel):
    av = pol.avaliar(rel)
    assert av.leitura == "nunca" and "2024" in av.grupos, rel
    assert not pol.pode_ler(rel)[0]


@pytest.mark.parametrize(
    "rel",
    [
        "tests/x_2024.json",
        "src/relatorio_2024.json",
        "src/x/dengue_2024.jsonl",
        "tests/x_2024.csv",
    ],
)
def test_a1_mario_nao_grava_2024_pela_ficha(pol, rel):
    for existe in (True, False):
        assert not pol.pode_escrever(rel, "mario", existe, ficha=[rel])[0]


# ---------------------------------------------------------------- A2
@pytest.mark.parametrize(
    "rel",
    [
        "reports/modelo_risco_dengue/LACRE_TESTE_2024.json",
        "outra/LACRE_TESTE_2024.json",
        "reports/modelo_risco_dengue/sub/LACRE_TESTE_2024.json",
        "a/b/c/lacre_teste_2024.JSON",
    ],
)
def test_a2_lacre_continua_so_hash_em_qualquer_pasta(pol, rel):
    av = pol.avaliar(rel)
    assert (av.leitura, av.escrita, av.classe) == (
        "so_hash",
        "humano",
        "SOMENTE_HASH",
    ), rel
    assert "2024" not in av.grupos
    assert not pol.pode_ler(rel)[0]
    for ag in P.AGENTES:
        assert not pol.pode_escrever(rel, ag, True, ficha=[rel])[0]


def test_a2_nenhuma_regra_nunca_captura_o_lacre_em_pastas_variadas(pol):
    for pasta in (
        "",
        "a/",
        "reports/",
        "reports/modelo_risco_dengue/",
        "x/y/z/",
        "data/"[:0],
    ):
        rel = f"{pasta}LACRE_TESTE_2024.json"
        for i in pol.itens:
            if i.leitura == "nunca":
                rx = P.glob_para_regex(i.padrao, "yoshi")
                assert not (rx and rx.fullmatch(rel)), (i.padrao, rel)


# ---------------------------------------------------------------- B1
@pytest.mark.parametrize(
    "rel",
    [
        "src/../.gitignore",
        "src/../agentes/estado/estado.json",
        "./src/a.py",
        "src//a.py",
        "/src/a.py",
        "src\\a.py",
        "",
        "..",
        ".",
        "src/./a.py",
        "src/a.py/",
        "src/\x00a.py",
    ],
)
def test_b1_pode_escrever_e_pode_ler_rejeitam_caminho_nao_normalizado(pol, rel):
    assert not pol.pode_escrever(rel, "mario", True, ficha=[rel])[0]
    assert not pol.pode_escrever(rel, "mario", False, ficha=[rel])[0]
    assert not pol.pode_ler(rel)[0]


def test_b1_rel_valido():
    assert P.rel_valido("src/a.py") and P.rel_valido(".gitignore")
    assert not P.rel_valido(None) and not P.rel_valido(3)


# ---------------------------------------------------------------- B2
@pytest.mark.parametrize(
    "rel",
    [
        "src/.gitignore",
        "docs/.gitignore",
        "tests/x/.gitignore",
        "config/.python-version",
        "src/.GITIGNORE",
        "src/.gitattributes",
        "reports/etapa3/.gitignore",
    ],
)
@pytest.mark.parametrize("agente", P.AGENTES)
def test_b2_arquivos_do_git_aninhados_sao_so_humanos(pol, rel, agente):
    assert pol.avaliar(rel).classe == "SOMENTE_HUMANO"
    for existe in (True, False):
        assert not pol.pode_escrever(rel, agente, existe, ficha=[rel])[0]


# ---------------------------------------------------------------- B3
@pytest.fixture
def arv(tmp_path):
    r = tmp_path / "proj"
    (r / "agentes" / "estado").mkdir(parents=True)
    shutil.copy(POL_REAL, r / "agentes" / "estado" / "protegidos.json")
    for rel, txt in {
        "CLAUDE.md": "a",
        "specs/spec.md": "b",
        ".gitignore": "c",
        "agentes/scripts/x.py": "d",
        "tests/agentes/t.py": "e",
        "src/x.py": "f",
    }.items():
        f = r / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(txt)
    assert M.main(["gerar"], r) == 0
    return r


@pytest.mark.parametrize(
    "novo",
    [
        "agentes/scripts/venv/evil.py",
        "agentes/scripts/node_modules/x.js",
        "agentes/scripts/.git/x",
        "agentes/scripts/__pycache__/x.py",
        "agentes/scripts/__pycache__/x.txt",
        "tests/agentes/__pycache__/x.py",
        "agentes/criterios/.venv/a.py",
        ".claude/node_modules/m.js",
        "agentes/scripts/.ruff_cache_falso/x",
    ],
)
def test_b3_arquivo_novo_em_pasta_ignorada_de_area_humana_reprova(arv, capsys, novo):
    capsys.readouterr()
    f = arv / novo
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("x")
    assert M.main(["verificar"], arv) == 1
    out = capsys.readouterr().out
    assert f"NOVO_EM_AREA_SOMENTE_HUMANO: {novo}" in out
    assert "arquivo novo" in out


def test_b3_link_simbolico_novo_em_area_humana_reprova(arv, capsys):
    (arv / "specs" / "plan.md").symlink_to(arv / "CLAUDE.md")
    (arv / "agentes" / "scripts" / "lnk").symlink_to(arv / "src")
    capsys.readouterr()
    assert M.main(["verificar"], arv) == 1
    out = capsys.readouterr().out
    assert "NOVO_EM_AREA_SOMENTE_HUMANO: specs/plan.md (link simbólico novo" in out
    assert (
        "NOVO_EM_AREA_SOMENTE_HUMANO: agentes/scripts/lnk (link simbólico novo" in out
    )


@pytest.mark.parametrize(
    "inerte",
    [
        "agentes/scripts/__pycache__/x.cpython-313.pyc",
        "tests/agentes/__pycache__/t.cpython-313.pyc",
        "agentes/scripts/.ruff_cache/a",
        "agentes/scripts/.pytest_cache/b",
        "src/__pycache__/x.pyc",
        "venv/lib/a.py",
        ".venv/lib/a.py",
        "node_modules/m.js",
        ".git/config",
    ],
)
def test_b3_itens_inertes_ou_fora_de_area_humana_nao_reprovam(arv, capsys, inerte):
    f = arv / inerte
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("x")
    capsys.readouterr()
    assert M.main(["verificar"], arv) == 0
    assert "NOVO_EM_AREA" not in capsys.readouterr().out


def test_b3_nao_le_conteudo(arv, capsys):
    f = arv / "agentes" / "scripts" / "venv" / "segredo.py"
    f.parent.mkdir(parents=True)
    f.write_text("SEGREDO-CONTEUDO")
    capsys.readouterr()
    M.main(["verificar"], arv)
    tudo = capsys.readouterr()
    assert "SEGREDO-CONTEUDO" not in tudo.out + tudo.err
