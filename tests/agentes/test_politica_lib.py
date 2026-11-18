"""Testes da política v2 (agentes/scripts/politica_lib.py). Só caminhos fictícios; nada é lido."""

import json
import random
import sys
from pathlib import Path, PurePosixPath

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "agentes" / "scripts"))
import politica_lib as P

POL_REAL = RAIZ / "agentes" / "estado" / "protegidos.json"
pytestmark = pytest.mark.skipif(not POL_REAL.exists(), reason="protegidos.json ausente")


@pytest.fixture(scope="module")
def pol():
    return P.Politica.carregar(POL_REAL)


# ------------------------------------------------------------------ glob
@pytest.mark.skipif(
    not hasattr(PurePosixPath, "full_match"), reason="exige Python 3.13+"
)
@pytest.mark.parametrize(
    "padrao,rel",
    [
        ("data/**", "data/a.parquet"),
        ("data/**", "data/x/y/z.csv"),
        ("data/**", "data"),
        ("**/*.parquet", "a.parquet"),
        ("**/*.parquet", "x/y/a.PARQUET"),
        ("*.md", "a.md"),
        ("*.md", "d/a.md"),
        ("a/**/b", "a/b"),
        ("a/**/b", "a/x/y/b"),
        ("a/*/b", "a/b"),
        ("a/*/b", "a/x/b"),
        ("a/*/b", "a/x/y/b"),
        ("a?c", "abc"),
        ("a?c", "a/c"),
        ("**/*dengbr24*", "data/raw/DENGBR24.dbc"),
        ("data/**/*2024*", "data/2024.x"),
        ("data/**/*2024*", "data/a/b/x2024y"),
        ("a/**", "a/b"),
        ("a/**", "a"),
    ],
)
def test_glob_igual_ao_oraculo(padrao, rel):
    esperado = PurePosixPath(rel).full_match(padrao, case_sensitive=False)
    rx = P.glob_para_regex(padrao)
    assert bool(rx.fullmatch(rel)) == bool(esperado)


def test_glob_agente():
    assert P.glob_para_regex("r/{agente}.md") is None
    rx = P.glob_para_regex("r/*/ciclo-*/{agente}-rev*.md", "mario")
    assert rx.fullmatch("r/e/ciclo-1/mario-rev2.md")
    assert not rx.fullmatch("r/e/ciclo-1/luigi-rev2.md")


# ------------------------------------------------------------------ classificação (só strings)
@pytest.mark.parametrize(
    "rel,leitura,escrita",
    [
        (
            "reports/modelo_risco_dengue/tabelas/comparacao_ms_teste.csv",
            "so_hash",
            "humano",
        ),
        (
            "reports/modelo_risco_dengue/tabelas/teste_calibracao.csv",
            "so_hash",
            "humano",
        ),
        (
            "reports/modelo_risco_dengue/tabelas/teste_criterios_sucesso.csv",
            "so_hash",
            "humano",
        ),
        (
            "reports/modelo_risco_dengue/tabelas/teste_diferencas_pareadas.csv",
            "so_hash",
            "humano",
        ),
        (
            "reports/modelo_risco_dengue/tabelas/teste_discriminacao.csv",
            "so_hash",
            "humano",
        ),
        ("reports/modelo_risco_dengue/tabelas/teste_nri.csv", "so_hash", "humano"),
        (
            "reports/modelo_risco_dengue/tabelas/teste_reclassificacao.csv",
            "so_hash",
            "humano",
        ),
        (
            "reports/modelo_risco_dengue/tabelas/teste_subgrupos.csv",
            "so_hash",
            "humano",
        ),
        (
            "reports/modelo_risco_dengue/figuras/teste_dca_calibracao.png",
            "so_hash",
            "humano",
        ),
        ("reports/modelo_risco_dengue/cache/oof_xgboost_abc.npz", "so_hash", "humano"),
        ("reports/modelo_risco_dengue/LACRE_TESTE_2024.json", "so_hash", "humano"),
        (
            "reports/modelo_risco_dengue/tabelas/teste_2024_resultados.json",
            "nunca",
            "humano",
        ),
        ("reports/modelo_risco_dengue/tabelas/or_comorbidades.csv", "livre", "humano"),
        ("data/raw/x.dbc", "nunca", "humano"),
        ("data/processed/dev.parquet", "nunca", "humano"),
        ("outro/dir/qualquer.parquet", "nunca", "humano"),
        ("outro/DENGBR24.csv", "nunca", "humano"),
        ("artefatos/oof/3.2.0/oof.parquet", "nunca", "humano"),
        ("agentes/decisoes/DECISOES.md", "livre", "humano"),
        ("agentes/estado/autorizacao.json", "livre", "humano"),
        ("agentes/estado/protegidos.json", "livre", "humano"),
        (".claude/settings.json", "livre", "humano"),
        ("CLAUDE.md", "livre", "humano"),
        ("agentes/estado/estado.json", "livre", "ficha"),
        ("agentes/relatorios/e/ciclo-1/mario.md", "livre", "criar"),
        ("agentes/historico/execucoes.jsonl", "livre", "anexar"),
        ("src/dengue_sinan/x.py", "livre", "ficha"),
    ],
)
def test_classificacao(pol, rel, leitura, escrita):
    av = pol.avaliar(rel)
    assert (av.leitura, av.escrita) == (leitura, escrita), av.classe


def test_lacre_nao_vira_nunca(pol):
    av = pol.avaliar("reports/modelo_risco_dengue/LACRE_TESTE_2024.json")
    assert av.classe == "SOMENTE_HASH" and av.grupos == set()


def test_grupo_2024_permanente_e_sem_caixa(pol):
    for rel in (
        "x/DENGBR24.DBC",
        "data/a/2024_x.csv",
        "r/a/TESTE_2024_RESULTADOS.JSON",
    ):
        assert pol.avaliar(rel).leitura == "nunca"
        assert "2024" in pol.avaliar(rel).grupos


def test_ordem_dos_itens_nao_importa():
    bruto = json.loads(POL_REAL.read_text("utf-8"))
    amostra = [
        "reports/modelo_risco_dengue/tabelas/teste_nri.csv",
        "data/x.parquet",
        "reports/modelo_risco_dengue/LACRE_TESTE_2024.json",
        "config/a.json",
        "agentes/relatorios/e/ciclo-1/luigi.md",
        "reports/modelo_risco_dengue/tabelas/or.csv",
    ]
    ref = P.Politica.de_dicionario(bruto)
    esperado = [
        (a.leitura, a.escrita, a.classe)
        for a in (ref.avaliar(r, "luigi") for r in amostra)
    ]
    rng = random.Random(1)
    for _ in range(25):
        itens = list(bruto["itens"])
        rng.shuffle(itens)
        p = P.Politica.de_dicionario({**bruto, "itens": itens})
        obtido = [
            (a.leitura, a.escrita, a.classe)
            for a in (p.avaliar(r, "luigi") for r in amostra)
        ]
        assert obtido == esperado


def test_concessao_nao_anula_classe_mais_restritiva():
    bruto = {
        "versao_esquema": 2,
        "itens": [
            {
                "padrao": "a/**",
                "classe": "SOMENTE_HUMANO",
                "leitura": "livre",
                "escrita": "humano",
            },
            {
                "padrao": "a/x.md",
                "classe": "ESCRITA_CONTROLADA",
                "leitura": "livre",
                "escrita": "ficha",
                "escritores": ["mario"],
            },
        ],
    }
    p = P.Politica.de_dicionario(bruto)
    assert p.pode_escrever("a/x.md", "mario", existe=False)[0] is False


# ------------------------------------------------------------------ escrita por agente
def test_criar_nao_sobrescreve(pol):
    rel = "agentes/relatorios/e/ciclo-1/mario.md"
    assert pol.pode_escrever(rel, "mario", existe=False)[0]
    assert not pol.pode_escrever(rel, "mario", existe=True)[0]


def test_criar_so_o_proprio_nome(pol):
    rel = "agentes/relatorios/e/ciclo-1/mario.md"
    assert not pol.pode_escrever(rel, "luigi", existe=False)[0]
    assert pol.pode_escrever(
        "agentes/relatorios/e/ciclo-1/luigi-rev2.md", "luigi", existe=False
    )[0]
    assert pol.pode_escrever(
        "agentes/evidencias/e/ciclo-1/peach/sub/x.txt", "peach", existe=False
    )[0]
    assert not pol.pode_escrever(
        "agentes/evidencias/e/ciclo-1/luigi/x.txt", "peach", existe=False
    )[0]


def test_anexar(pol):
    rel = "agentes/historico/execucoes.jsonl"
    assert pol.pode_escrever(rel, "yoshi", True, antigo="a\n", novo="a\nb\n")[0]
    assert not pol.pode_escrever(rel, "yoshi", True, antigo="a\n", novo="b\n")[0]
    assert not pol.pode_escrever(rel, "yoshi", True, antigo="a\n", novo="a\n")[0]
    assert not pol.pode_escrever(rel, "mario", True, antigo="a\n", novo="a\nb\n")[0]


def test_ficha_e_concessao(pol):
    assert pol.pode_escrever("agentes/estado/estado.json", "yoshi", True)[0]
    assert not pol.pode_escrever("agentes/estado/estado.json", "mario", True)[0]
    assert pol.pode_escrever(
        "src/dengue_sinan/x.py", "mario", True, ficha=["src/dengue_sinan/x.py"]
    )[0]
    assert not pol.pode_escrever(
        "src/dengue_sinan/y.py", "mario", True, ficha=["src/dengue_sinan/x.py"]
    )[0]
    assert pol.pode_escrever(
        "src/dengue_sinan/y.py", "mario", True, ficha=["src/dengue_sinan/*.py"]
    )[0]
    assert not pol.pode_escrever("src/dengue_sinan/y.py", "mario", True, ficha=None)[0]


def test_config_exige_caminho_exato(pol):
    assert not pol.pode_escrever("config/a.json", "mario", True, ficha=["config/*"])[0]
    assert not pol.pode_escrever("uv.lock", "mario", True, ficha=["*.lock"])[0]
    assert pol.pode_escrever("config/a.json", "mario", True, ficha=["config/a.json"])[0]


@pytest.mark.parametrize(
    "rel",
    [
        "agentes/estado/autorizacao.json",
        "agentes/estado/protegidos.json",
        ".claude/hooks/x.py",
        "agentes/scripts/manifesto.py",
        "agentes/decisoes/DECISOES.md",
        "data/x.parquet",
        "reports/modelo_risco_dengue/tabelas/teste_nri.csv",
        "specs/spec.md",
    ],
)
@pytest.mark.parametrize("agente", P.AGENTES)
def test_ninguem_escreve_em_protegidos(pol, rel, agente):
    assert not pol.pode_escrever(rel, agente, False, ficha=[rel])[0]
    assert not pol.pode_escrever(rel, agente, True, ficha=[rel])[0]


def test_proposta_de_decisao_so_yoshi(pol):
    rel = "agentes/decisoes/propostas/DP-001.md"
    assert pol.pode_escrever(rel, "yoshi", False)[0]
    assert not pol.pode_escrever(rel, "mario", False)[0]
    assert not pol.pode_escrever(rel, "yoshi", True)[0]


def test_exclusao_sempre_negada(pol):
    for ag in P.AGENTES:
        assert not pol.pode_excluir("src/x.py", ag)[0]


def test_leitura(pol):
    assert pol.pode_ler("src/x.py")[0]
    assert not pol.pode_ler("data/a.parquet")[0]
    assert not pol.pode_ler("reports/modelo_risco_dengue/tabelas/teste_nri.csv")[0]
    assert not pol.pode_ler(None)[0]


def test_agente_desconhecido(pol):
    assert not pol.pode_escrever("src/x.py", "bowser", True, ficha=["src/x.py"])[0]


# ------------------------------------------------------------------ normalização
def test_relativo(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "f.txt").write_text("x")
    assert P.relativo(tmp_path, "a/f.txt") == "a/f.txt"
    assert P.relativo(tmp_path, tmp_path / "a" / ".." / "a" / "f.txt") == "a/f.txt"
    assert P.relativo(tmp_path, "../fora.txt") is None
    assert P.relativo(tmp_path, "/etc/passwd") is None


def test_symlink_para_fora_e_para_dentro(tmp_path):
    raiz = tmp_path / "raiz"
    fora = tmp_path / "fora"
    (raiz / "data").mkdir(parents=True)
    fora.mkdir()
    (raiz / "data" / "dev.parquet").write_text("x")
    (raiz / "atalho").symlink_to(raiz / "data" / "dev.parquet")
    (raiz / "saida").symlink_to(fora)
    assert (
        P.relativo(raiz, raiz / "atalho") == "data/dev.parquet"
    )  # não escapa da política
    assert P.relativo(raiz, raiz / "saida" / "a.txt") is None


# ------------------------------------------------------------------ falha fechada
def test_falha_fechada(tmp_path):
    with pytest.raises(P.PoliticaInvalida):
        P.Politica.carregar(tmp_path / "nao_existe.json")
    ruim = tmp_path / "r.json"
    ruim.write_text("{nao é json")
    with pytest.raises(P.PoliticaInvalida):
        P.Politica.carregar(ruim)
    for bruto in (
        {"versao_esquema": 1, "itens": []},
        {"versao_esquema": 2, "itens": []},
        {
            "versao_esquema": 2,
            "itens": [
                {"padrao": "a", "classe": "X", "leitura": "livre", "escrita": "humano"}
            ],
        },
        {
            "versao_esquema": 2,
            "itens": [
                {
                    "padrao": "a",
                    "classe": "PRESERVADO",
                    "leitura": "talvez",
                    "escrita": "humano",
                }
            ],
        },
        {
            "versao_esquema": 2,
            "itens": [
                {
                    "padrao": "a",
                    "classe": "PRESERVADO",
                    "leitura": "livre",
                    "escrita": "humano",
                    "escritores": ["bowser"],
                }
            ],
        },
        {
            "versao_esquema": 2,
            "itens": [
                {
                    "padrao": "a**b",
                    "classe": "PRESERVADO",
                    "leitura": "livre",
                    "escrita": "humano",
                }
            ],
        },
        {"versao_esquema": 2, "itens": [{"padrao": "a"}]},
    ):
        with pytest.raises(P.PoliticaInvalida):
            P.Politica.de_dicionario(bruto)
