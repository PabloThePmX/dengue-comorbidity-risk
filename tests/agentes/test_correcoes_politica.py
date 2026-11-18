"""Regressão das correções C2 (escrita por papel), C3 (2024 em qualquer pasta), arquivos
só-humanos e arquivos novos em áreas só-humanas. Usa só nomes fictícios e árvores temporárias."""

import json
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


def esc(pol, rel, agente, existe=True, ficha=None, **kw):
    return pol.pode_escrever(
        rel, agente, existe, ficha=ficha if ficha is not None else [rel], **kw
    )


# ---------------------------------------------------------------- 1 e 2: Luigi e Peach em src/
@pytest.mark.parametrize("agente", ["luigi", "peach", "yoshi"])
@pytest.mark.parametrize(
    "rel",
    [
        "src/dengue_sinan/x.py",
        "tests/test_x.py",
        "config/a.json",
        "docs/x.md",
        "pyproject.toml",
        "uv.lock",
        "reports/etapa3/x.csv",
        "reports/etapa2/x.md",
    ],
)
def test_so_mario_usa_ficha_em_implementacao(pol, agente, rel):
    assert not esc(pol, rel, agente)[0]
    assert not esc(pol, rel, agente, existe=False)[0]


@pytest.mark.parametrize(
    "rel",
    [
        "src/dengue_sinan/x.py",
        "tests/test_x.py",
        "config/a.json",
        "docs/x.md",
        "pyproject.toml",
        "uv.lock",
        "reports/etapa3/x.csv",
    ],
)
def test_mario_continua_com_ficha_nos_arquivos_de_implementacao(pol, rel):
    assert esc(pol, rel, "mario")[0]
    assert not pol.pode_escrever(rel, "mario", True, ficha=[])[0]
    assert not pol.pode_escrever(rel, "mario", True, ficha=None)[0]


# ---------------------------------------------------------------- 3 e 4: Mario em estado e fichas
@pytest.mark.parametrize(
    "rel",
    [
        "agentes/estado/estado.json",
        "agentes/estado/autorizacao.json",
        "agentes/estado/limites.json",
        "agentes/estado/protegidos.json",
        "agentes/decisoes/DECISOES.md",
        "agentes/historico/execucoes.jsonl",
        "agentes/tarefas/E3/E3.3-T001.md",
        "agentes/tarefas/_modelo.md",
        "agentes/roadmap/ROADMAP.md",
        "agentes/scripts/politica_lib.py",
        "agentes/estado/manifestos/manifesto-v002.json",
        "tests/agentes/test_politica_lib.py",
    ],
)
def test_mario_nao_usa_ficha_em_estado_decisoes_registros_fichas_politica(pol, rel):
    assert not esc(pol, rel, "mario")[0]
    assert not esc(pol, rel, "mario", existe=False)[0]
    assert not esc(pol, rel, "mario", existe=True, antigo="a", novo="ab")[0]


def test_yoshi_so_as_permissoes_de_coordenacao(pol):
    assert pol.pode_escrever("agentes/estado/estado.json", "yoshi", True)[0]
    assert pol.pode_escrever("agentes/tarefas/E3/E3.3-T001.md", "yoshi", False)[0]
    assert pol.pode_escrever("agentes/roadmap/ROADMAP.md", "yoshi", True)[0]
    # constar na ficha não dá acesso a mais nada
    for rel in (
        "src/dengue_sinan/x.py",
        "config/a.json",
        "agentes/estado/autorizacao.json",
        "agentes/decisoes/DECISOES.md",
        ".gitignore",
        "tests/agentes/test_politica_lib.py",
    ):
        assert not esc(pol, rel, "yoshi")[0]
        assert not esc(pol, rel, "yoshi", existe=False)[0]


def test_registros_sem_hierarquia_simplista(pol):
    # criar: não sobrescreve, mesmo na ficha
    rel = "agentes/relatorios/e/ciclo-1/mario.md"
    assert pol.pode_escrever(rel, "mario", False)[0]
    assert not pol.pode_escrever(rel, "mario", True)[0]
    assert not esc(pol, "agentes/relatorios/e/ciclo-1/luigi.md", "mario", existe=False)[
        0
    ]
    # anexar: não vira modificar, e Mario não anexa o histórico
    h = "agentes/historico/execucoes.jsonl"
    assert pol.pode_escrever(h, "yoshi", True, antigo="a\n", novo="a\nb\n")[0]
    assert not pol.pode_escrever(h, "yoshi", True, antigo="a\n", novo="b\n")[0]
    assert not pol.pode_escrever(h, "mario", True, antigo="a\n", novo="a\nb\n")[0]
    # proposta de decisão: só Yoshi cria
    dp = "agentes/decisoes/propostas/DP-002.md"
    assert pol.pode_escrever(dp, "yoshi", False)[0]
    assert not pol.pode_escrever(dp, "mario", False)[0]
    assert not pol.pode_escrever(dp, "yoshi", True)[0]


def test_caminho_sem_regra_e_negado(pol):
    for rel in (
        "README.md",
        "outra_pasta/x.py",
        "novo_diretorio/a.txt",
        ".github/workflows/a.yml",
    ):
        assert pol.avaliar(rel).itens == []
        for ag in P.AGENTES:
            assert not esc(pol, rel, ag)[0]
            assert not esc(pol, rel, ag, existe=False)[0]


def test_ficha_nunca_anula_restricao_mais_forte(pol):
    for rel in (
        "specs/spec.md",
        "CLAUDE.md",
        "data/x.parquet",
        "x/dengue_2024.csv",
        "reports/modelo_risco_dengue/tabelas/teste_nri.csv",
        ".claude/settings.json",
        "reports/modelo_risco_dengue/LACRE_TESTE_2024.json",
    ):
        for ag in P.AGENTES:
            assert not esc(pol, rel, ag)[0]


def test_item_futuro_com_ficha_nao_afrouxa_humano():
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
                "via_ficha": ["mario"],
                "escritores": ["mario"],
            },
        ],
    }
    p = P.Politica.de_dicionario(bruto)
    assert not p.pode_escrever("a/x.md", "mario", True, ficha=["a/x.md"])[0]


def test_via_ficha_invalido_e_rejeitado():
    base = {
        "padrao": "a",
        "classe": "PRESERVADO",
        "leitura": "livre",
        "escrita": "ficha",
    }
    for v in (["*"], ["bowser"]):
        with pytest.raises(P.PoliticaInvalida):
            P.Politica.de_dicionario(
                {"versao_esquema": 2, "itens": [{**base, "via_ficha": v}]}
            )


# ---------------------------------------------------------------- 5: .gitignore e .python-version
@pytest.mark.parametrize("rel", [".gitignore", ".python-version", ".GITIGNORE"])
@pytest.mark.parametrize("agente", P.AGENTES)
def test_gitignore_e_python_version_so_humanos(pol, rel, agente):
    assert pol.avaliar(rel).classe == "SOMENTE_HUMANO"
    assert not esc(pol, rel, agente)[0]
    assert not esc(pol, rel, agente, existe=False)[0]


# ---------------------------------------------------------------- 6 e 7: 2024 em qualquer pasta
PASTAS = [
    "",
    "data/",
    "data/raw/",
    "reports/",
    "reports/etapa3/",
    "tmp/a/b/",
    "artefatos/x/",
    "src/",
]
EXTS = [
    "csv",
    "zip",
    "feather",
    "pkl",
    "pickle",
    "parquet",
    "dbc",
    "dbf",
    "gz",
    "tgz",
    "xlsx",
    "txt",
    "md",
    "png",
    "pdf",
    "tsv",
    "7z",
    "tar",
    "xls",
    "html",
    "log",
]
NOMES = [
    "dengue_2024",
    "DENGUE_2024",
    "Dengue_2024",
    "DENGBR24",
    "dengbr24",
    "dengue2024",
    "sinan_2024_final",
    "x2024y",
    "teste_2024",
    "avaliacao_2024",
]


@pytest.mark.parametrize("ext", EXTS)
def test_2024_em_pastas_e_extensoes_diferentes(pol, ext):
    for pasta in PASTAS:
        for nome in NOMES:
            rel = f"{pasta}{nome}.{ext}"
            av = pol.avaliar(rel)
            assert av.leitura == "nunca", rel
            assert "2024" in av.grupos, rel
            assert not pol.pode_ler(rel)[0]
            for ag in P.AGENTES:
                assert not esc(pol, rel, ag)[0]


@pytest.mark.parametrize(
    "rel",
    [
        "x/dengue_2024.csv.gz",
        "x/DENGBR24.DBC",
        "x/dados_2024",
        "x/2024/qualquer.coisa",
        "reports/teste_2024/saida.dat",
        "x/dengbr_24.csv",
        "x/resultados_2024.json",
        "x/metricas_2024.json",
        "x/avaliacao_teste_2024.json",
        "x/teste_2024_resultados.json",
        "x/predicoes_2024.json",
        "x/2024_final.json",
        "x/teste_final_2024.json",
    ],
)
def test_2024_outros_nomes_e_diretorios(pol, rel):
    assert pol.avaliar(rel).leitura == "nunca"


def test_2024_persiste_depois_de_mover(pol):
    original = "data/raw/DENGBR24.dbc"
    assert pol.avaliar(original).leitura == "nunca"
    for destino in (
        "backup/DENGBR24.dbc",
        "../fora/DENGBR24.dbc",
        "z/y/x/dengbr24.DBC",
    ):
        assert pol.avaliar(destino.replace("../", "")).leitura == "nunca"


def test_lacre_continua_somente_hash(pol):
    for rel in (
        "reports/modelo_risco_dengue/LACRE_TESTE_2024.json",
        "outra/pasta/LACRE_TESTE_2024.json",
        "outra/lacre_teste_2024.json",
    ):
        av = pol.avaliar(rel)
        assert "2024" not in av.grupos, rel
        assert av.leitura != "nunca", rel
    real = pol.avaliar("reports/modelo_risco_dengue/LACRE_TESTE_2024.json")
    assert (real.leitura, real.classe) == ("so_hash", "SOMENTE_HASH")
    assert {i.natureza for i in real.itens if i.natureza} == {"lacre_de_integridade"}
    assert not pol.pode_ler("reports/modelo_risco_dengue/LACRE_TESTE_2024.json")[0]


def test_nenhuma_regra_generica_captura_o_lacre(pol):
    lacre = "reports/modelo_risco_dengue/LACRE_TESTE_2024.json"
    for i in pol.itens:
        if i.leitura == "nunca":
            rx = P.glob_para_regex(i.padrao, "yoshi")
            assert not (rx and rx.fullmatch(lacre)), i.padrao


def test_nao_ha_falso_positivo_em_arquivos_comuns(pol):
    for rel in (
        "src/dengue_sinan/pipeline/oof.py",
        "reports/etapa3/relatorio_etapa3_2.md",
        "config/avaliacao_oof.json",
        "reports/modelo_risco_dengue/tabelas/or_comorbidades.csv",
        "tests/test_hash_lacre.py",
        "agentes/README.md",
        "specs/spec.md",
        "reports/modelo_risco_dengue/cache/oof_xgboost_1f0e98c1e71cf0aa.npz",
    ):
        assert pol.avaliar(rel).leitura != "nunca", rel


# ---------------------------------------------------------------- 9: ordem dos padrões
def test_ordem_nao_importa_com_novos_itens():
    import random

    bruto = json.loads(POL_REAL.read_text("utf-8"))
    amostra = [
        "x/dengue_2024.csv",
        "reports/modelo_risco_dengue/LACRE_TESTE_2024.json",
        ".gitignore",
        "tests/agentes/t.py",
        "tests/t.py",
        "src/a.py",
        "config/a.json",
        "agentes/estado/estado.json",
        "agentes/historico/execucoes.jsonl",
        "README.md",
    ]

    def foto(p):
        out = []
        for r in amostra:
            for ag in P.AGENTES:
                out.append(
                    (
                        r,
                        ag,
                        p.pode_escrever(r, ag, True, ficha=[r])[0],
                        p.avaliar(r).leitura,
                        p.avaliar(r).escrita,
                    )
                )
        return out

    ref = foto(P.Politica.de_dicionario(bruto))
    rng = random.Random(7)
    for _ in range(25):
        itens = list(bruto["itens"])
        rng.shuffle(itens)
        assert foto(P.Politica.de_dicionario({**bruto, "itens": itens})) == ref


# ---------------------------------------------------------------- 10: política ausente/inválida
def test_politica_ausente_ou_invalida_nega(tmp_path):
    (tmp_path / "src").mkdir()
    alvo = tmp_path / "src" / "a.py"
    alvo.write_text("x")
    ausente = tmp_path / "nao_existe.json"
    ruim = tmp_path / "ruim.json"
    ruim.write_text("{ruim")
    vazia = tmp_path / "vazia.json"
    vazia.write_text(json.dumps({"versao_esquema": 2, "itens": []}))
    antiga = tmp_path / "antiga.json"
    antiga.write_text(json.dumps({"versao_esquema": 1, "itens": [{"padrao": "**"}]}))
    for pol_ in (ausente, ruim, vazia, antiga):
        for ag in P.AGENTES:
            assert not P.pode_escrever_seguro(
                tmp_path, pol_, alvo, ag, ficha=["src/a.py"]
            )[0]
        assert not P.pode_ler_seguro(tmp_path, pol_, alvo)[0]


def test_seguro_com_politica_real_e_caminho_fora(tmp_path):
    raiz = RAIZ
    assert P.pode_escrever_seguro(
        raiz, POL_REAL, raiz / "src" / "novo.py", "mario", ficha=["src/novo.py"]
    )[0]
    assert not P.pode_escrever_seguro(
        raiz, POL_REAL, raiz / "src" / "novo.py", "luigi", ficha=["src/novo.py"]
    )[0]
    assert not P.pode_escrever_seguro(
        raiz, POL_REAL, tmp_path / "fora.py", "mario", ficha=["fora.py"]
    )[0]


# ---------------------------------------------------------------- 8: arquivos novos só-humanos
@pytest.fixture
def arv(tmp_path):
    r = tmp_path / "proj"
    (r / "agentes" / "estado").mkdir(parents=True)
    shutil.copy(POL_REAL, r / "agentes" / "estado" / "protegidos.json")
    for rel, txt in {
        "CLAUDE.md": "a",
        "specs/spec.md": "b",
        ".gitignore": "c",
        ".python-version": "3.13",
        "src/x.py": "d",
    }.items():
        f = r / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(txt)
    return r


@pytest.mark.parametrize(
    "novo",
    [
        "specs/plan.md",
        ".claude/settings.json",
        "agentes/scripts/outro.py",
        "agentes/criterios/x.md",
        "tests/agentes/test_novo.py",
        "agentes/estado/limites.json",
    ],
)
def test_arquivo_novo_em_area_somente_humano_reprova(arv, capsys, novo):
    assert M.main(["gerar"], arv) == 0
    assert M.main(["verificar"], arv) == 0
    capsys.readouterr()
    f = arv / novo
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text("novo")
    assert M.main(["verificar"], arv) == 1
    out = capsys.readouterr().out
    assert f"NOVO_EM_AREA_SOMENTE_HUMANO: {novo}" in out
    assert "não registrado em v001" in out
    assert "COMPROMETIDA" in out


def test_arquivo_novo_fora_de_area_humana_nao_reprova(arv, capsys):
    M.main(["gerar"], arv)
    (arv / "src" / "novo.py").write_text("x")
    capsys.readouterr()
    assert M.main(["verificar"], arv) == 0
    assert "NOVO_EM_AREA" not in capsys.readouterr().out


def test_gitignore_alterado_reprova(arv):
    M.main(["gerar"], arv)
    (arv / ".gitignore").write_text("mudou")
    assert M.main(["verificar"], arv) == 1


def test_v001_nao_e_tocada_pela_verificacao(arv):
    leg = arv / "agentes" / "estado" / "manifesto_hashes.json"
    leg.write_text(json.dumps({"arquivos": {}}))
    antes = leg.read_bytes()
    M.main(["verificar", "--versao", "1"], arv)
    M.main(["gerar"], arv)
    M.main(["verificar"], arv)
    assert leg.read_bytes() == antes
