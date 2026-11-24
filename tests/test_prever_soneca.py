"""Script de previsão da soneca (D-97): isolamento, regra de entrada, carga, adaptador e paridade.

Nada aqui lê dado real nem carrega o artefato fora do worktree: o teste de integração pula com
motivo quando o venv do worktree da branch não existe ou não está completo.
"""

import importlib.util
import subprocess
import sys
import types
from pathlib import Path

import pandas as pd
import pytest
import yaml
from populacao_sintetica import cfg_sintetico, dados_sinteticos, gravar, linha

from dengue_sinan import comparacao_entrada as ce
from dengue_sinan import comparacao_manifesto as cm
from dengue_sinan import dataset
from dengue_sinan.config import CONFIG_PADRAO
from dengue_sinan.preprocess import FEATURES_PERMITIDAS
from dengue_sinan.profiling import COMORBIDADES, SINAIS

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT = RAIZ / "scripts" / "comparacao" / "prever_soneca.py"
MANIFESTO = RAIZ / "config" / "comparacao" / "manifesto.yaml"
WORKTREE = RAIZ.parent / "_comparacao" / "soneca"  # fora do repositório (D-97 g)


def _carregar_script():
    spec = importlib.util.spec_from_file_location("prever_soneca", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


ps = _carregar_script()


@pytest.fixture
def sha_declarado() -> str:
    with open(MANIFESTO, encoding="utf-8") as f:
        m = yaml.safe_load(f)
    return next(x for x in m["modelos"] if x["id"] == "m1_soneca")["artefato"]["sha256"]


@pytest.fixture
def load_espiao(monkeypatch):
    """Substitui joblib por um módulo cujo load registra a chamada e levanta erro."""
    chamadas = []

    def _load(*args, **kwargs):
        chamadas.append(args)
        raise AssertionError("joblib.load não deveria ser chamado")

    falso = types.SimpleNamespace(load=_load)
    monkeypatch.setitem(sys.modules, "joblib", falso)
    return chamadas


def _entrada_com_anos(tmp_path, anos) -> Path:
    entrada = tmp_path / "entrada.parquet"
    pd.DataFrame({"ANO": anos, "LINHA": list(range(len(anos)))}).to_parquet(entrada, index=False)
    entrada.with_suffix(".json").write_text('{"features_do_projeto": []}', encoding="utf-8")
    return entrada


def _rodar_main(tmp_path, entrada):
    return ps.main(["--worktree", str(tmp_path), "--entrada", str(entrada),
                    "--saida", str(tmp_path / "s.parquet"), "--manifesto", str(MANIFESTO)])


@pytest.fixture
def interprete_ok(monkeypatch):
    """Testes de regra rodam fora do venv do worktree: dispensa só a checagem de interpretador."""
    monkeypatch.setattr(ps, "checar_interpretador", lambda *a: None)


# ------------------------------------------------------------------ isolamento do interpretador
def test_interpretador_do_worktree_passa(tmp_path):
    venv = tmp_path / ".venv"
    venv.mkdir()
    ps.checar_interpretador(tmp_path, str(venv))  # não levanta


def test_interpretador_de_fora_do_worktree_e_recusado(tmp_path):
    with pytest.raises(SystemExit, match="interpretador fora do venv"):
        ps.checar_interpretador(tmp_path, sys.prefix)


def test_main_recusa_interpretador_de_fora_antes_de_qualquer_carga(tmp_path, load_espiao):
    # Sem o monkeypatch: o python de teste não é o venv do worktree falso, então para na checagem.
    entrada = _entrada_com_anos(tmp_path, [2022])
    with pytest.raises(SystemExit, match="interpretador fora do venv"):
        _rodar_main(tmp_path, entrada)
    assert load_espiao == []


# ------------------------------------------------------------------ regra de entrada (R1, R2)
def test_ano_de_teste_do_script_espelha_o_config():
    with open(CONFIG_PADRAO, encoding="utf-8") as f:
        assert yaml.safe_load(f)["ano_teste"] == ps.ANO_TESTE == 2024


@pytest.mark.parametrize("porta", [False, True])
def test_recusa_2024_sempre_mesmo_com_a_porta_de_comparacao(porta):
    with pytest.raises(PermissionError, match="2024"):
        ps.checar_anos({2024}, 2025, porta)
    with pytest.raises(PermissionError, match="2024"):
        ps.checar_anos({2022, 2024}, 2025, porta)


def test_recusa_2025_sem_a_variavel_de_ambiente():
    with pytest.raises(PermissionError, match="DENGUE_PORTA_COMPARACAO=1"):
        ps.checar_anos({2025}, 2025, porta_aberta=False)


def test_aceita_2025_com_a_porta_definida():
    ps.checar_anos({2025}, 2025, porta_aberta=True)  # não levanta


def test_aceita_anos_de_desenvolvimento():
    ps.checar_anos({2022}, 2025, porta_aberta=False)
    ps.checar_anos({2022, 2023}, 2025, porta_aberta=False)


def test_2024_recusado_antes_do_joblib_load(tmp_path, monkeypatch, sha_declarado, load_espiao,
                                            interprete_ok):
    monkeypatch.setattr(ps, "sha256_arquivo", lambda _p: sha_declarado)
    monkeypatch.delenv("DENGUE_PORTA_COMPARACAO", raising=False)
    entrada = _entrada_com_anos(tmp_path, [2024])
    with pytest.raises(PermissionError, match="2024"):
        _rodar_main(tmp_path, entrada)
    assert load_espiao == []
    assert not (tmp_path / "s.parquet").exists()


def test_2025_sem_porta_recusado_antes_do_joblib_load(tmp_path, monkeypatch, sha_declarado,
                                                      load_espiao, interprete_ok):
    monkeypatch.setattr(ps, "sha256_arquivo", lambda _p: sha_declarado)
    monkeypatch.delenv("DENGUE_PORTA_COMPARACAO", raising=False)
    entrada = _entrada_com_anos(tmp_path, [2025])
    with pytest.raises(PermissionError, match="DENGUE_PORTA_COMPARACAO"):
        _rodar_main(tmp_path, entrada)
    assert load_espiao == []


def test_sha_divergente_para_sem_carregar(tmp_path, monkeypatch, load_espiao, interprete_ok):
    monkeypatch.setattr(ps, "sha256_arquivo", lambda _p: "0" * 64)
    with pytest.raises(SystemExit, match="SHA-256"):
        _rodar_main(tmp_path, _entrada_com_anos(tmp_path, [2022]))
    assert load_espiao == []


# --------------------------------------------- restauração do __main__ após a carga (D-97 g)
def _modelos_falsos():
    return types.SimpleNamespace(ModeloM1="M1", ModeloB1="B1", Calibrador="C")


def test_classes_do_artefato_sao_restauradas_depois_da_carga(monkeypatch):
    import __main__

    monkeypatch.setattr(__main__, "ModeloM1", "ANTERIOR", raising=False)
    with ps.classes_do_artefato(_modelos_falsos()):
        assert __main__.ModeloM1 == "M1"
    assert __main__.ModeloM1 == "ANTERIOR"


def test_classes_ausentes_sao_removidas_depois_da_carga(monkeypatch):
    import __main__

    for nome in ps.CLASSES_DO_ARTEFATO:
        monkeypatch.delattr(__main__, nome, raising=False)
    with ps.classes_do_artefato(_modelos_falsos()):
        assert __main__.ModeloB1 == "B1"
    assert not hasattr(__main__, "ModeloB1")


def test_classes_sao_restauradas_mesmo_se_a_carga_falhar(monkeypatch):
    import __main__

    for nome in ps.CLASSES_DO_ARTEFATO:
        monkeypatch.delattr(__main__, nome, raising=False)
    with pytest.raises(RuntimeError):
        with ps.classes_do_artefato(_modelos_falsos()):
            raise RuntimeError("falha na carga")
    assert not hasattr(__main__, "ModeloM1")


# ------------------------------------------------------------------------- adaptador
def test_adaptador_cobre_exatamente_o_dicionario_do_projeto():
    assert set(ps.ADAPTADOR) == set(FEATURES_PERMITIDAS)


def test_ordem_das_categorias_e_a_da_branch():
    # dataset.SEXOS = F, M, I e dataset.NIVEIS = Não, Sim, Ausente: o código ordinal depende disso.
    assert ps.SEXO_CATEGORIAS == ("F", "M", "I")
    assert ps.NIVEL3 == ("Não", "Sim", "Ausente")


def _quadro(n=3) -> pd.DataFrame:
    base = {
        "idade_anos": [34.0, 70.5, 5.0][:n],
        "sexo": ["M", "F", "I"][:n],
        "gestante": [0, 1, 0][:n],
        "n_comorbidades": [0, 2, 1][:n],
        "dias_ate_notificacao": [None, 9.0, 0.0][:n],
    }
    for c in [*ps.ADAPTADOR]:
        if c not in base:
            base[c] = ["Não", "Sim", "Ausente"][:n]
    return pd.DataFrame(base)


def test_adaptar_codifica_como_a_branca_e_preserva_nan():
    x = ps.adaptar(_quadro(), list(ps.ADAPTADOR))
    assert list(x["sexo"].cat.categories) == ["F", "M", "I"]
    assert list(x["sexo"].cat.codes) == [1, 0, 2]          # M, F, I
    assert list(x["FEBRE"].cat.codes) == [0, 1, 2]         # Não, Sim, Ausente
    assert x["dias_ate_notificacao"].isna().iloc[0]
    assert x["idade_anos"].dtype == "float64"
    assert x["gestante"].dtype == "int8"


def test_adaptar_segue_a_ordem_pedida_pelo_modelo():
    pedido = ["FEBRE", "idade_anos", "sexo"]
    assert list(ps.adaptar(_quadro(), pedido).columns) == pedido


def test_adaptar_recusa_categoria_fora_do_contrato():
    q = _quadro()
    q.loc[0, "FEBRE"] = "Talvez"
    with pytest.raises(ValueError, match="FEBRE"):
        ps.adaptar(q, ["FEBRE"])


def test_adaptar_recusa_sexo_fora_do_contrato_e_nulo_em_inteiro():
    q = _quadro()
    q.loc[0, "sexo"] = "X"
    with pytest.raises(ValueError, match="sexo"):
        ps.adaptar(q, ["sexo"])
    q = _quadro()
    q.loc[0, "gestante"] = None
    with pytest.raises(ValueError, match="gestante"):
        ps.adaptar(q, ["gestante"])


def test_adaptar_recusa_variavel_sem_regra_e_coluna_ausente():
    with pytest.raises(ValueError, match="sem regra"):
        ps.adaptar(_quadro(), ["UF"])
    with pytest.raises(ValueError, match="sem as colunas"):
        ps.adaptar(_quadro().drop(columns=["RENAL"]), ["DIABETES", "RENAL"])


def test_checar_dicionario_lista_o_que_nao_e_do_projeto():
    assert ps.checar_dicionario(["idade_anos", "UF"], list(FEATURES_PERMITIDAS)) == ["UF"]


def test_adaptador_converte_o_quadro_real_do_projeto(tmp_path):
    """Pelo caminho do exportador: o quadro de build_feature_frame vira o contrato da branch."""
    cfg = cfg_sintetico(tmp_path)
    dados_sinteticos(cfg)
    pop = dataset.load_population(cfg, [2022, 2023])  # sintético: não grava nada real
    quadro = dataset.build_feature_frame(pop)
    x = ps.adaptar(quadro, list(ps.ADAPTADOR))
    # 2022 entra com 4 linhas (sintéticas 1, 2, 3 e 7); a 4ª (índice 3) é a linha 7.
    linha7 = x.iloc[3]  # DIABETES e HIPERTENSA em Sim, 9 dias de atraso
    assert linha7["DIABETES"] == "Sim" and linha7["HIPERTENSA"] == "Sim"
    assert linha7["n_comorbidades"] == 2
    assert linha7["dias_ate_notificacao"] == 9.0
    assert set(ce.COLUNAS_FEATURES) <= set(quadro.columns)


def test_manifesto_json_exportado_do_yaml_validado_e_lido_pelo_script(tmp_path):
    import json

    caminho = cm.exportar_json(tmp_path / "m.json", MANIFESTO)
    lido = ps.ler_manifesto(caminho)
    assert lido == json.loads(caminho.read_text(encoding="utf-8"))
    com_yaml = ps.ler_manifesto(MANIFESTO)  # a main tem PyYAML; o JSON deve trazer o mesmo SHA
    assert (ps.modelo_do_manifesto(lido)["artefato"]["sha256"]
            == ps.modelo_do_manifesto(com_yaml)["artefato"]["sha256"])
    assert lido["ano_comparacao"] == 2025


# ------------------------------------------------ integração e paridade (pula sem o worktree)
def _venv_do_worktree_pronto() -> bool:
    """O venv do worktree existe e importa o que o script precisa (xgboost, sklearn, scipy)."""
    python = WORKTREE / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        return False
    res = subprocess.run([str(python), "-c", "import xgboost, sklearn, scipy.sparse, pyarrow"],
                         capture_output=True, timeout=300)
    return res.returncode == 0


# Rota nativa do bundle, escrita à mão e independente do adaptador do script. Roda no python do
# worktree. Recebe: worktree, entrada, saída.
ROTA_NATIVA = r'''
import sys
from pathlib import Path
import __main__
import joblib
import numpy as np
import pandas as pd

worktree, entrada, saida = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
sys.path.insert(0, str(worktree / "src"))
from dengue_sinan import modelos

for nome in ("ModeloM1", "ModeloB1", "Calibrador"):
    setattr(__main__, nome, getattr(modelos, nome))
b = joblib.load(worktree / "reports/modelo_risco_dengue/artefatos/m1_congelado.joblib")

COMORBS = ["DIABETES", "HEMATOLOG", "HEPATOPAT", "RENAL", "HIPERTENSA", "ACIDO_PEPT", "AUTO_IMUNE"]
SINAIS = ["FEBRE", "MIALGIA", "CEFALEIA", "EXANTEMA", "VOMITO", "NAUSEA", "DOR_COSTAS",
          "CONJUNTVIT", "ARTRITE", "ARTRALGIA", "PETEQUIA_N", "DOR_RETRO", "LEUCOPENIA", "LACO"]
a = pd.read_parquet(entrada)
x = pd.DataFrame(index=range(len(a)))
x["idade_anos"] = a["idade_anos"].astype("float64").to_numpy()
x["sexo"] = pd.Categorical(a["sexo"].astype(str).to_numpy(), categories=["F", "M", "I"])
x["gestante"] = a["gestante"].astype("int8").to_numpy()
for c in COMORBS + SINAIS:
    x[c] = pd.Categorical(a[c].astype(str).to_numpy(), categories=["Não", "Sim", "Ausente"])
x["n_comorbidades"] = a["n_comorbidades"].astype("int8").to_numpy()
x["dias_ate_notificacao"] = a["dias_ate_notificacao"].astype("float64").to_numpy()
x = x[list(b["features"])]
p = np.asarray(b["calibrador"].prever(b["m1"].prever(x)), dtype="float64")
pd.DataFrame({"LINHA": a["LINHA"].to_numpy(), "p_nativo": p}).to_parquet(saida, index=False)
'''


def _lote_sintetico(n: int) -> list[dict]:
    """n notificações sintéticas variadas (sexo, comorbidades, sintomas, idade, atraso)."""
    linhas = []
    for i in range(n):
        campos = {
            "CS_SEXO": ["F", "M", "I"][i % 3],
            "CS_GESTANT": ["1", "5"][i % 2],
            "NU_IDADE_N": f"40{20 + i % 50:02d}",
            "EVOLUCAO": ["1", "2"][i % 2],
            "DT_SIN_PRI": "20220110",
            "DT_NOTIFIC": f"202201{10 + i % 15:02d}",
        }
        for j, c in enumerate(COMORBIDADES):
            campos[c] = ["1", "2", None][(i + j) % 3]
        for j, s in enumerate(SINAIS):
            campos[s] = ["1", "2", "9"][(i + j) % 3]
        linhas.append(linha(**campos))
    return linhas


@pytest.mark.skipif(not _venv_do_worktree_pronto(),
                    reason="worktree da branch feat/soneca sem .venv completo (D-97 g)")
def test_paridade_do_script_com_a_rota_nativa_do_bundle(tmp_path):
    cfg = cfg_sintetico(tmp_path)
    gravar(cfg, 2022, _lote_sintetico(60))
    entrada = ce.exportar_entrada(cfg, 2022, tmp_path / "entrada_2022.parquet")
    n = len(pd.read_parquet(entrada))
    assert n >= 30, "o lote sintético deveria ter dezenas de linhas na população"

    python = WORKTREE / ".venv" / "Scripts" / "python.exe"
    manifesto_json = cm.exportar_json(tmp_path / "manifesto.json", MANIFESTO)
    saida = tmp_path / "previsoes.parquet"
    res = subprocess.run(
        [str(python), str(SCRIPT), "--worktree", str(WORKTREE), "--entrada", str(entrada),
         "--saida", str(saida), "--manifesto", str(manifesto_json)],
        capture_output=True, text=True, timeout=600, env=_ambiente_sem_porta(),
    )
    assert res.returncode == 0, res.stderr[-2000:]

    nativa_py = tmp_path / "rota_nativa.py"
    nativa_py.write_text(ROTA_NATIVA, encoding="utf-8")
    nativa_out = tmp_path / "nativa.parquet"
    res2 = subprocess.run(
        [str(python), str(nativa_py), str(WORKTREE), str(entrada), str(nativa_out)],
        capture_output=True, text=True, timeout=600,
    )
    assert res2.returncode == 0, res2.stderr[-2000:]

    script = pd.read_parquet(saida)
    nativa = pd.read_parquet(nativa_out)
    assert len(script) == n and len(nativa) == n
    m = script.merge(nativa, on="LINHA", how="inner")
    assert len(m) == n
    assert not m["p"].isna().any()
    assert (m["p"].between(0, 1)).all()
    assert ((m["p"] - m["p_nativo"]).abs() < 1e-12).all()


def _ambiente_sem_porta() -> dict:
    import os

    return {k: v for k, v in os.environ.items() if k != "DENGUE_PORTA_COMPARACAO"}
