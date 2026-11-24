"""Script de previsão do m1_lora (D-97): isolamento, regra de entrada, carga, adaptador e paridade.

Nada aqui lê dado real nem carrega o artefato fora do worktree: o teste de integração pula com
motivo quando o venv do worktree da branch não existe ou não importa o que o script precisa.
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
SCRIPT = RAIZ / "scripts" / "comparacao" / "prever_lora.py"
MANIFESTO = RAIZ / "config" / "comparacao" / "manifesto.yaml"
WORKTREE = RAIZ.parent / "_comparacao" / "lora"  # fora do repositório (D-97 g)


def _carregar_script():
    spec = importlib.util.spec_from_file_location("prever_lora", SCRIPT)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


pl = _carregar_script()


@pytest.fixture
def sha_declarado() -> str:
    with open(MANIFESTO, encoding="utf-8") as f:
        m = yaml.safe_load(f)
    return next(x for x in m["modelos"] if x["id"] == "m1_lora")["artefato"]["sha256"]


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
    return pl.main(["--worktree", str(tmp_path), "--entrada", str(entrada),
                    "--saida", str(tmp_path / "s.parquet"), "--manifesto", str(MANIFESTO)])


@pytest.fixture
def interprete_ok(monkeypatch):
    """Testes de regra rodam fora do venv do worktree: dispensa só a checagem de interpretador."""
    monkeypatch.setattr(pl, "checar_interpretador", lambda *a: None)


# ------------------------------------------------------------------ constantes e manifesto
def test_constantes_espelham_o_config_e_o_manifesto():
    with open(CONFIG_PADRAO, encoding="utf-8") as f:
        assert yaml.safe_load(f)["ano_teste"] == pl.ANO_TESTE == 2024
    with open(MANIFESTO, encoding="utf-8") as f:
        m = yaml.safe_load(f)
    modelo = next(x for x in m["modelos"] if x["id"] == pl.MODELO)
    assert pl.MODELO == "m1_lora"
    assert modelo["artefato"]["caminho"] == pl.ARTEFATO_DO_MODELO
    assert modelo["origem"]["commit"] == "af96e97b01d6c21700229d833c5e0a6e0f656f11"


# ------------------------------------------------------------------ isolamento do interpretador
def test_interpretador_do_worktree_passa(tmp_path):
    venv = tmp_path / ".venv"
    venv.mkdir()
    pl.checar_interpretador(tmp_path, str(venv))  # não levanta


def test_interpretador_de_fora_do_worktree_e_recusado(tmp_path):
    with pytest.raises(SystemExit, match="interpretador fora do venv"):
        pl.checar_interpretador(tmp_path, sys.prefix)


def test_main_recusa_interpretador_de_fora_antes_de_qualquer_carga(tmp_path, load_espiao):
    # Sem o monkeypatch: o python de teste não é o venv do worktree falso, então para na checagem.
    entrada = _entrada_com_anos(tmp_path, [2022])
    with pytest.raises(SystemExit, match="interpretador fora do venv"):
        _rodar_main(tmp_path, entrada)
    assert load_espiao == []


# ------------------------------------------------------------------ regra de entrada (R1, R2)
@pytest.mark.parametrize("porta", [False, True])
def test_recusa_2024_sempre_mesmo_com_a_porta_de_comparacao(porta):
    with pytest.raises(PermissionError, match="2024"):
        pl.checar_anos({2024}, 2025, porta)
    with pytest.raises(PermissionError, match="2024"):
        pl.checar_anos({2022, 2024}, 2025, porta)


def test_recusa_2025_sem_a_variavel_de_ambiente():
    with pytest.raises(PermissionError, match="DENGUE_PORTA_COMPARACAO=1"):
        pl.checar_anos({2025}, 2025, porta_aberta=False)


def test_aceita_2025_com_a_porta_definida():
    pl.checar_anos({2025}, 2025, porta_aberta=True)  # não levanta


def test_aceita_anos_de_desenvolvimento():
    pl.checar_anos({2022}, 2025, porta_aberta=False)
    pl.checar_anos({2022, 2023}, 2025, porta_aberta=False)


def test_2024_recusado_antes_do_joblib_load(tmp_path, monkeypatch, sha_declarado, load_espiao,
                                            interprete_ok):
    monkeypatch.setattr(pl, "sha256_arquivo", lambda _p: sha_declarado)
    monkeypatch.delenv("DENGUE_PORTA_COMPARACAO", raising=False)
    entrada = _entrada_com_anos(tmp_path, [2024])
    with pytest.raises(PermissionError, match="2024"):
        _rodar_main(tmp_path, entrada)
    assert load_espiao == []
    assert not (tmp_path / "s.parquet").exists()


def test_2025_sem_porta_recusado_antes_do_joblib_load(tmp_path, monkeypatch, sha_declarado,
                                                      load_espiao, interprete_ok):
    monkeypatch.setattr(pl, "sha256_arquivo", lambda _p: sha_declarado)
    monkeypatch.delenv("DENGUE_PORTA_COMPARACAO", raising=False)
    entrada = _entrada_com_anos(tmp_path, [2025])
    with pytest.raises(PermissionError, match="DENGUE_PORTA_COMPARACAO"):
        _rodar_main(tmp_path, entrada)
    assert load_espiao == []


def test_sha_divergente_para_sem_carregar(tmp_path, monkeypatch, load_espiao, interprete_ok):
    monkeypatch.setattr(pl, "sha256_arquivo", lambda _p: "0" * 64)
    with pytest.raises(SystemExit, match="SHA-256"):
        _rodar_main(tmp_path, _entrada_com_anos(tmp_path, [2022]))
    assert load_espiao == []


# ------------------------------- restauração de remendos e nomes em __main__ após a carga (D-97 g)
class _BSplineFalso:
    """Stand-in do BSpline: o remendo da branch troca __setstate__ enquanto a carga roda."""

    def __setstate__(self, estado):  # pragma: no cover - não é chamado nos testes
        raise AssertionError("não deveria ser chamado")


def _setstate_original():
    return _BSplineFalso.__dict__["__setstate__"]


def test_setstate_do_scipy_e_restaurado_depois_da_carga():
    original = _setstate_original()
    criados: list[str] = []
    with pl.remendos_restaurados(criados, classe_scipy=_BSplineFalso):
        _BSplineFalso.__setstate__ = lambda self, s: None  # o remendo da carga
    assert _BSplineFalso.__dict__["__setstate__"] is original


def test_setstate_criado_pela_carga_e_removido():
    class Sem:
        pass

    criados: list[str] = []
    with pl.remendos_restaurados(criados, classe_scipy=Sem):
        Sem.__setstate__ = lambda self, s: None
    assert "__setstate__" not in Sem.__dict__


def test_setstate_e_restaurado_mesmo_se_a_carga_falhar():
    original = _setstate_original()
    criados: list[str] = []
    with pytest.raises(RuntimeError):
        with pl.remendos_restaurados(criados, classe_scipy=_BSplineFalso):
            _BSplineFalso.__setstate__ = lambda self, s: None
            raise RuntimeError("falha na carga")
    assert _BSplineFalso.__dict__["__setstate__"] is original


def test_nomes_criados_em_main_sao_listados_e_removidos(monkeypatch):
    import __main__

    monkeypatch.delattr(__main__, "ClasseDaCargaFalsa", raising=False)
    criados: list[str] = []
    with pl.remendos_restaurados(criados, classe_scipy=_BSplineFalso):
        __main__.ClasseDaCargaFalsa = object()
    assert criados == ["ClasseDaCargaFalsa"]
    assert not hasattr(__main__, "ClasseDaCargaFalsa")


def test_nomes_de_main_que_mudaram_voltam_ao_valor_anterior(monkeypatch):
    import __main__

    monkeypatch.setattr(__main__, "NomeDoTeste", "ANTERIOR", raising=False)
    criados: list[str] = []
    with pl.remendos_restaurados(criados, classe_scipy=_BSplineFalso):
        __main__.NomeDoTeste = "TROCADO"
    assert __main__.NomeDoTeste == "ANTERIOR"
    assert criados == []


# ------------------------------------------------------------------------- adaptador
def test_adaptador_cobre_exatamente_o_dicionario_do_projeto():
    assert set(pl.ADAPTADOR) == set(FEATURES_PERMITIDAS)


def test_categorias_do_script_seguem_o_quadro_comum_da_main():
    # dataset._tres_niveis da main: Sim, Não, Ausente; build_feature_frame: F, M, I. A branch usa
    # Não, Sim, Ausente, mas o one-hot casa por valor (paridade com a rota nativa, diferença 0,0).
    assert pl.NIVEL3 == ("Sim", "Não", "Ausente")
    assert pl.SEXO_CATEGORIAS == ("F", "M", "I")


def test_listas_do_script_espelham_o_projeto():
    assert tuple(pl.COMORBIDADES) == tuple(COMORBIDADES)
    assert tuple(pl.SINAIS) == tuple(SINAIS)


def _quadro(n=3) -> pd.DataFrame:
    base = {
        "idade_anos": [34.0, 70.5, 5.0][:n],
        "sexo": ["M", "F", "I"][:n],
        "gestante": [0, 1, 0][:n],
        "n_comorbidades": [0, 2, 1][:n],
        "dias_ate_notificacao": [9.0, 0.0, 60.0][:n],
    }
    for c in [*pl.COMORBIDADES, *pl.SINAIS]:
        base[c] = ["Sim", "Não", "Ausente"][:n]
    return pd.DataFrame(base)


def test_adaptar_dtypes_e_codigos_da_branch():
    x = pl.adaptar(_quadro(), list(pl.ADAPTADOR))
    assert list(x["sexo"].cat.categories) == ["F", "M", "I"]
    assert list(x["sexo"].cat.codes) == [1, 0, 2]          # M, F, I
    assert list(x["DIABETES"].cat.categories) == ["Sim", "Não", "Ausente"]
    assert list(x["FEBRE"].cat.codes) == [0, 1, 2]         # Sim, Não, Ausente
    assert x["idade_anos"].dtype == "float64"
    assert x["dias_ate_notificacao"].dtype == "float64"
    assert x["gestante"].dtype == "int8"
    assert x["n_comorbidades"].dtype == "int8"


def test_adaptar_segue_a_ordem_pedida_pelo_modelo():
    pedido = ["FEBRE", "idade_anos", "sexo"]
    assert list(pl.adaptar(_quadro(), pedido).columns) == pedido


def test_recusa_nan_em_variavel_numerica():
    # O SplineTransformer da branch usa handle_missing='error': NaN não passa, então recusa aqui.
    q = _quadro()
    q.loc[0, "dias_ate_notificacao"] = None
    with pytest.raises(ValueError, match="dias_ate_notificacao"):
        pl.adaptar(q, ["dias_ate_notificacao"])


@pytest.mark.parametrize("valor", [2, -1, None])
def test_recusa_gestante_fora_do_dominio_ou_nula(valor):
    q = _quadro()
    q.loc[0, "gestante"] = valor
    with pytest.raises(ValueError, match="gestante"):
        pl.adaptar(q, ["gestante"])


def test_recusa_n_comorbidades_acima_de_sete():
    q = _quadro()
    q.loc[0, "n_comorbidades"] = 8
    with pytest.raises(ValueError, match="n_comorbidades"):
        pl.adaptar(q, ["n_comorbidades"])


def test_recusa_categoria_fora_do_contrato():
    q = _quadro()
    q.loc[0, "FEBRE"] = "Talvez"
    with pytest.raises(ValueError, match="FEBRE"):
        pl.adaptar(q, ["FEBRE"])
    q = _quadro()
    q.loc[0, "sexo"] = "X"
    with pytest.raises(ValueError, match="sexo"):
        pl.adaptar(q, ["sexo"])


def test_recusa_variavel_sem_regra_e_coluna_ausente():
    with pytest.raises(ValueError, match="sem regra"):
        pl.adaptar(_quadro(), ["UF"])
    with pytest.raises(ValueError, match="sem as colunas"):
        pl.adaptar(_quadro().drop(columns=["RENAL"]), ["DIABETES", "RENAL"])


def test_checar_dicionario_lista_o_que_nao_e_do_projeto():
    assert pl.checar_dicionario(["idade_anos", "UF"], list(FEATURES_PERMITIDAS)) == ["UF"]


def test_correcao_de_desbalanceamento_so_conta_valor_que_corrige():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import Pipeline

    sem = Pipeline([("clf", LogisticRegression(penalty=None, solver="lbfgs"))])
    assert pl.correcao_de_desbalanceamento(sem) == {}
    com = Pipeline([("clf", LogisticRegression(class_weight="balanced"))])
    assert "clf__class_weight" in pl.correcao_de_desbalanceamento(com)


def test_adaptar_converte_o_quadro_real_do_projeto(tmp_path):
    """Pelo caminho do exportador: o quadro de build_feature_frame vira o contrato da branch."""
    cfg = cfg_sintetico(tmp_path)
    dados_sinteticos(cfg)
    pop = dataset.load_population(cfg, [2022, 2023])  # sintético: não grava nada real
    quadro = dataset.build_feature_frame(pop)
    x = pl.adaptar(quadro, list(pl.ADAPTADOR))
    # 2022 entra com 4 linhas (sintéticas 1, 2, 3 e 7); a 4ª (índice 3) é a linha 7.
    linha7 = x.iloc[3]  # DIABETES e HIPERTENSA em Sim, 9 dias de atraso
    assert linha7["DIABETES"] == "Sim" and linha7["HIPERTENSA"] == "Sim"
    assert linha7["n_comorbidades"] == 2
    assert linha7["dias_ate_notificacao"] == 9.0
    assert set(ce.COLUNAS_FEATURES) <= set(quadro.columns)


def test_manifesto_json_exportado_do_yaml_validado_e_lido_pelo_script(tmp_path):
    import json

    caminho = cm.exportar_json(tmp_path / "m.json", MANIFESTO)
    lido = pl.ler_manifesto(caminho)
    assert lido == json.loads(caminho.read_text(encoding="utf-8"))
    com_yaml = pl.ler_manifesto(MANIFESTO)  # a main tem PyYAML; o JSON deve trazer o mesmo SHA
    assert (pl.modelo_do_manifesto(lido)["artefato"]["sha256"]
            == pl.modelo_do_manifesto(com_yaml)["artefato"]["sha256"])
    assert lido["ano_comparacao"] == 2025


# ------------------------------------------------ integração e paridade (pula sem o worktree)
_IMPORTA_O_NECESSARIO = (
    "import sys; sys.path.insert(0, sys.argv[1]); "
    "import dengue_sinan.runner, dengue_sinan.artifacts, scipy.interpolate, pyarrow, joblib"
)


def _venv_do_worktree_pronto() -> bool:
    """O venv do worktree existe e importa o pacote da branch (runner, artifacts, scipy)."""
    python = WORKTREE / ".venv" / "Scripts" / "python.exe"
    if not python.exists():
        return False
    res = subprocess.run([str(python), "-c", _IMPORTA_O_NECESSARIO, str(WORKTREE / "src")],
                         capture_output=True, timeout=600)
    return res.returncode == 0


# Rota nativa do bundle, escrita à mão e independente do adaptador do script. Roda no python do
# worktree. Recebe: worktree, entrada, saída. Usa o load_bundle da própria branch.
ROTA_NATIVA = r'''
import sys
from pathlib import Path
import numpy as np
import pandas as pd

worktree, entrada, saida = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
sys.path.insert(0, str(worktree / "src"))
from dengue_sinan.artifacts import load_bundle

b = load_bundle(worktree / "models/m1_final.joblib")
m = b["model"]

COMORBS = ["DIABETES", "HEMATOLOG", "HEPATOPAT", "RENAL", "HIPERTENSA", "ACIDO_PEPT", "AUTO_IMUNE"]
SINAIS = ["FEBRE", "MIALGIA", "CEFALEIA", "EXANTEMA", "VOMITO", "NAUSEA", "DOR_COSTAS",
          "CONJUNTVIT", "ARTRITE", "ARTRALGIA", "PETEQUIA_N", "LEUCOPENIA", "LACO", "DOR_RETRO"]
a = pd.read_parquet(entrada)
x = pd.DataFrame(index=range(len(a)))
x["idade_anos"] = a["idade_anos"].astype("float64").to_numpy()
x["gestante"] = a["gestante"].astype("int8").to_numpy()
x["n_comorbidades"] = a["n_comorbidades"].astype("int8").to_numpy()
x["dias_ate_notificacao"] = a["dias_ate_notificacao"].astype("float64").to_numpy()
x["sexo"] = pd.Categorical(a["sexo"].astype(str).to_numpy(), categories=["F", "M", "I"])
for c in COMORBS + SINAIS:
    x[c] = pd.Categorical(a[c].astype(str).to_numpy(), categories=["Sim", "Não", "Ausente"])
x = x[list(m.feature_cols)]
p = np.asarray(m.predict_proba(x), dtype="float64")[:, 1]
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
                    reason="worktree da branch feat/lora sem .venv completo (D-97 g): "
                           "o Programador cria com uv sync --frozen no terminal dele")
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
