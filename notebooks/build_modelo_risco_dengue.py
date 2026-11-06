"""Gera notebooks/modelo_risco_dengue.ipynb a partir do código testado em src/dengue_sinan.

Mesmo padrão de profiling/build_notebook.py: o notebook precisa rodar no Colab sem clonar o
repositório, então este script COPIA os módulos de src/ para células (sem os imports internos).
Edite os módulos (ou este script) e regere:

    python notebooks/build_modelo_risco_dengue.py
"""
# ruff: noqa: E501

import ast
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
SRC = RAIZ / "src" / "dengue_sinan"
SAIDA = RAIZ / "notebooks" / "modelo_risco_dengue.ipynb"
MODULOS = ["features", "download", "profiling", "guard", "dataset", "folds", "metrics",
           "descriptive", "explain", "modelos"]


def fonte_modulo(nome: str) -> str:
    """Código do módulo sem os imports `from dengue_sinan...` (no notebook tudo é global)."""
    texto = (SRC / f"{nome}.py").read_text("utf-8")
    linhas = texto.splitlines()
    remover = set()
    for no in ast.parse(texto).body:
        if isinstance(no, ast.ImportFrom) and (no.module or "").startswith("dengue_sinan"):
            remover.update(range(no.lineno - 1, no.end_lineno))
    mantidas = [ln for i, ln in enumerate(linhas) if i not in remover]
    return f"# Copiado de src/dengue_sinan/{nome}.py — não edite aqui; edite o módulo e regere.\n" \
        + "\n".join(mantidas)


def md(texto: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": texto.strip("\n")}


def cod(texto: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": texto.strip("\n")}


CELULAS: list[dict] = []

# ============================================================================ 1. Contexto
CELULAS.append(md(r'''
# Risco de dengue grave ou óbito por perfil de comorbidades — SINAN/DataSUS 2022–2024

**Notebook `modelo_risco_dengue.ipynb`** — gerado por `notebooks/build_modelo_risco_dengue.py` a
partir do código testado de `src/dengue_sinan/`. Não edite as células de código copiadas: edite o
módulo e regere.

> **Projeto acadêmico.** Este material não é ferramenta clínica, não substitui a avaliação médica nem
> os protocolos oficiais do Ministério da Saúde (MS), e **nenhuma associação aqui é causal**.

## 1. Contextualização e objetivos

Fonte única do objetivo: `specs/goal.md`. Em resumo, para um **caso confirmado de dengue no Brasil**
(SINAN/DataSUS, 2022–2024), estimar a probabilidade de evoluir para **dengue grave ou óbito pelo
agravo**.

| Eixo | Pergunta | Instrumento principal |
|---|---|---|
| **Principal — associação** | Quais comorbidades e combinações se associam a maior risco, ajustando por idade e sexo? | Logística **sem penalização** com interações (E1): OR, RERI/AP, IC 95%, Benjamini-Hochberg |
| **Secundário — predição** | Qual o risco individual **no primeiro atendimento**? | Candidatos M1 (elastic net, Random Forest, gradiente boosting), validação leave-one-region-out, calibração |
| **Comparação** | O ML acrescenta algo à regra do MS? | Regra do grupo B do protocolo (B2) nos **mesmos pacientes e desfechos**; curva de decisão, reclassificação |

**Definições (spec §3.6)**

- *População:* `CLASSI_FIN` ∈ {10, 11, 12} **e** rótulo conhecido (12 com qualquer evolução; 10/11 só
  com `EVOLUCAO` ∈ {1, 2}) **e** idade válida em [0, 120] (com *fallback* por `ANO_NASC`).
- *Desfecho:* `y = 1` se `CLASSI_FIN = 12` (dengue grave) **ou** `EVOLUCAO = 2` (óbito pelo agravo).
- *Momento da predição:* notificação (primeiro atendimento). Nada posterior entra como variável.
- *Divisão:* desenvolvimento 2022–2023 (validação **leave-one-region-out**); teste **2024**, congelado
  e usado **uma única vez** (lacre).

### Decisões e conflitos entre o enunciado da tarefa e os artefatos do projeto

Pela regra de precedência (constituição > spec > roteiro > arquitetura > boas práticas), valeu o
projeto. Os conflitos relevantes e a decisão tomada:

| # | Enunciado pede | Projeto determina | Decisão |
|---|---|---|---|
| 1 | Tratar o desbalanceamento nos dados de treino | **R3/D-38: nenhuma correção** (sem pesos de classe, SMOTE, subamostragem); recall via limiar; calibração depois | **Segue o projeto.** Prevalência natural (~0,2%) preservada; limiar escolhido pelo F2 em predições fora da dobra |
| 2 | Validação temporal, cruzada e teste independente | Desenvolvimento 2022–23 com leave-one-region-out; teste 2024 | **Segue o projeto**, que já cumpre os três |
| 3 | Modelos "como Random Forest e Gradient Boosting" | Seis candidatos obrigatórios (inclui CatBoost, MLP, TabFM) | **Parcial.** Aqui: elastic net, RF e gradient boosting (XGBoost; HistGradientBoosting se ausente). CatBoost, MLP e TabFM exigem dependências/GPU ainda não aprovadas (tarefa T-2.0) e **ficam pendentes** |
| 4 | AUROC e AUPRC | PR-AUC é a métrica primária (D-09) | Reporta-se **ambas**; seleção por PR-AUC |
| 5 | "Outras condições disponíveis" | Só as 7 comorbidades da ficha; asma, DPOC e obesidade (que o protocolo cita) **não existem** na ficha | Limitação registrada |
| 6 | Otimizar hiperparâmetros | Espaço de busca é a pergunta aberta **Q-08**, reservada ao Programador; Optuna/MLflow não estão instalados | **Grade pequena e declarada** (`[ASSUMPTION]`, configurável), critério PR-AUC média nas dobras. **Precisa de aprovação** |
| 7 | Dependências | Adicionar ao `pyproject.toml` exige aprovação (T-2.0) | **`pyproject.toml` não foi alterado.** A célula de configuração instala o que faltar com `pip` |

Marcadores do projeto: `[ASSUMPTION]` = inferência a confirmar; `[VERIFY]` = fato a conferir nos dados.
'''))

# ============================================================================ 2. Configuração
CELULAS.append(md(r'''
## 2. Configuração e dependências

- **Local:** `jupyter nbconvert --to notebook --execute --inplace notebooks/modelo_risco_dengue.ipynb`
  (ou abra no Jupyter) a partir da raiz do repositório.
- **Colab:** *Ambiente de execução → Executar tudo*. O Drive é montado e tudo fica em
  `MyDrive/dengue-comorbidity-risk/` (dados em `data/`, saídas em `reports/modelo_risco_dengue/`).
- **Dados:** os microdados **não** vão no repositório (NFR-03). Se `data/parquet/dengue_{ano}.parquet`
  não existir, o notebook baixa do FTP oficial do DataSUS (D-05) e grava o manifesto com SHA-256.
- **Variáveis de ambiente opcionais:** `DENGUE_DATA_DIR`, `DENGUE_OUT_DIR`, `DENGUE_BASE`;
  `DENGUE_SMOKE=1` reduz orçamentos (**só** para o teste de fumaça com dados sintéticos).
- **Tempo:** o desenvolvimento usa ~2,45 milhões de linhas. O elastic net (saga) e o Random Forest
  são os mais lentos; os orçamentos de tempo por modelo estão em `CONFIG["ORCAMENTO_S"]`.
  `[VERIFY]` o tempo real em dados reais ainda não foi medido.
'''))

CELULAS.append(cod(r'''
import importlib.util
import os
import subprocess
import sys
import warnings

PACOTES = {"sklearn": "scikit-learn", "statsmodels": "statsmodels", "pyarrow": "pyarrow",
           "matplotlib": "matplotlib", "scipy": "scipy", "patsy": "patsy", "joblib": "joblib",
           "pyreaddbc": "pyreaddbc==2.0.4", "dbfread": "dbfread==2.0.7"}
OPCIONAIS = {"xgboost": "xgboost", "shap": "shap"}  # sem eles há alternativas (ver seções 14 e 16)


def _faltam(pacotes):
    return [pip for mod, pip in pacotes.items() if importlib.util.find_spec(mod) is None]


if _faltam(PACOTES):
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *_faltam(PACOTES)])
if _faltam(OPCIONAIS):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", *_faltam(OPCIONAIS)])
    except subprocess.CalledProcessError:
        print("Aviso: pacote opcional não instalado:", _faltam(OPCIONAIS))

warnings.filterwarnings("ignore", category=RuntimeWarning, module="statsmodels")
warnings.filterwarnings("ignore", category=FutureWarning)
'''))

CELULAS.append(cod(r'''
import hashlib
import json
import time
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

IN_COLAB = "google.colab" in sys.modules
SMOKE = os.environ.get("DENGUE_SMOKE") == "1"

if IN_COLAB and not os.environ.get("DENGUE_DATA_DIR"):
    from google.colab import drive

    drive.mount("/content/drive")
    BASE = Path("/content/drive/MyDrive/dengue-comorbidity-risk")
else:
    _aqui = Path.cwd()
    BASE = Path(os.environ.get("DENGUE_BASE", _aqui.parent if _aqui.name == "notebooks" else _aqui))
DATA_DIR = Path(os.environ.get("DENGUE_DATA_DIR", BASE / "data"))
OUT_DIR = Path(os.environ.get("DENGUE_OUT_DIR", BASE / "reports" / "modelo_risco_dengue"))
for sub in ("tabelas", "figuras", "cache", "artefatos"):
    (OUT_DIR / sub).mkdir(parents=True, exist_ok=True)

CONFIG = {
    "SEED": 20261103,                  # semente única (R8)
    "ANOS_DEV": [2022, 2023],
    "ANO_TESTE": 2024,
    "BAIXAR_SE_AUSENTE": True,
    "MIN_CELULA": 10,                  # supressão de célula pequena (NFR-03, SC-05)
    "MIN_EVENTOS_SUBGRUPO": 100,       # abaixo disso: aviso de IC largo (§3.8)
    "VALIDACAO_INTERNA_FRAC": 0.10,    # early stopping só aqui (R6)
    "PACIENCIA_BOOSTING": 50,
    "MAX_ITER_BOOSTING": 1000,
    "BOOT": 1000,                      # reamostras bootstrap (métricas e diferenças pareadas)
    "BOOT_SUBGRUPO": 200,
    "DCA_LIMIARES": (0.001, 0.05, 50),  # faixa de risco plausível para triagem [ASSUMPTION]
    "SHAP_AMOSTRA": 50_000,
    "SHAP_INTERACAO_AMOSTRA": 3_000,
    "ORCAMENTO_S": {"elastic_net": 1800, "random_forest": 2400, "xgboost": 1800},
    "EN_MAX_ITER": 300,
    "RF_MAX_AMOSTRAS": 0.25,
    "DEVICE": "cpu",                   # "cuda" acelera o XGBoost no Colab com GPU
    "N_JOBS": -1,
    "IDADE_REF": None,                 # None = idade mediana dos eventos (referência de RERI/ranking)
    "SENSIBILIDADE_DUPLICATAS": True,
}
if SMOKE:  # só no teste de fumaça com dados sintéticos
    CONFIG.update(BOOT=60, BOOT_SUBGRUPO=30, SHAP_AMOSTRA=2_000, SHAP_INTERACAO_AMOSTRA=300,
                  ORCAMENTO_S={"elastic_net": 60, "random_forest": 60, "xgboost": 60}, EN_MAX_ITER=100,
                  MAX_ITER_BOOSTING=200, N_JOBS=1)

_rf = CONFIG["RF_MAX_AMOSTRAS"]
_rf_n = 40 if SMOKE else 200
# Grades pequenas e DECLARADAS (Q-08 pendente: [ASSUMPTION], a aprovar pelo Programador).
# A 1ª configuração de cada modelo é a de referência e sempre roda.
GRADES = {
    "elastic_net": [{"C": 1.0, "l1_ratio": 0.5}, {"C": 0.1, "l1_ratio": 0.5},
                    {"C": 0.01, "l1_ratio": 0.5}, {"C": 0.1, "l1_ratio": 0.1}],
    "random_forest": [
        {"n_estimators": _rf_n, "min_samples_leaf": 100, "max_features": "sqrt", "max_samples": _rf},
        {"n_estimators": _rf_n, "min_samples_leaf": 30, "max_features": "sqrt", "max_samples": _rf},
        {"n_estimators": _rf_n, "min_samples_leaf": 300, "max_features": "sqrt", "max_samples": _rf},
        {"n_estimators": _rf_n, "min_samples_leaf": 100, "max_features": 0.5, "max_samples": _rf}],
    "xgboost": [
        {"max_depth": 4, "learning_rate": 0.05, "min_child_weight": 5, "subsample": 0.8,
         "colsample_bytree": 0.8, "reg_lambda": 1.0},
        {"max_depth": 3, "learning_rate": 0.05, "min_child_weight": 5, "subsample": 0.8,
         "colsample_bytree": 0.8, "reg_lambda": 1.0},
        {"max_depth": 6, "learning_rate": 0.05, "min_child_weight": 20, "subsample": 0.8,
         "colsample_bytree": 0.8, "reg_lambda": 1.0},
        {"max_depth": 4, "learning_rate": 0.05, "min_child_weight": 50, "subsample": 0.8,
         "colsample_bytree": 0.8, "reg_lambda": 10.0}],
}
if SMOKE:
    GRADES = {k: v[:2] for k, v in GRADES.items()}
np.random.seed(CONFIG["SEED"])
plt.rcParams.update({"figure.dpi": 110, "axes.grid": True, "grid.alpha": 0.25})
print("Base:", BASE, "| dados:", DATA_DIR, "| saídas:", OUT_DIR)
if SMOKE:
    print("*** MODO DE FUMAÇA (DENGUE_SMOKE=1): orçamentos reduzidos. Se os dados forem sintéticos, "
          "NENHUM número deste notebook tem valor científico. ***")
'''))

CELULAS.append(md("### Código do projeto (copiado de `src/dengue_sinan/`)\n\n"
                  "Módulos reaproveitados do Marco 1 (`features`, `download`, `profiling`) e módulos "
                  "novos deste notebook (`guard`, `dataset`, `folds`, `metrics`, `descriptive`, "
                  "`explain`, `modelos`), todos com testes em `tests/`."))
for _m in MODULOS:
    CELULAS.append(cod(fonte_modulo(_m)))

CELULAS.append(cod(r'''
import importlib.metadata as _md
import platform
import sklearn

def _v(pacote):
    try:
        return _md.version(pacote)
    except _md.PackageNotFoundError:
        return "ausente"

AMBIENTE = {"python": platform.python_version(), "sistema": platform.platform(),
            **{p: _v(p) for p in ["numpy", "pandas", "pyarrow", "scikit-learn", "statsmodels", "scipy",
                                  "xgboost", "shap", "matplotlib", "patsy"]}}
BOOSTING = rotulo_boosting()
print(json.dumps(AMBIENTE, indent=1, ensure_ascii=False))
print("Gradient boosting usado:", "XGBoost" if BOOSTING == "xgboost" else "HistGradientBoosting (XGBoost ausente)")

RESULTADOS: dict = {}   # agregados exportáveis (nunca linhas individuais — R7)


def salvar_tabela(df: pd.DataFrame, nome: str) -> pd.DataFrame:
    # trava de segurança: tabelas exportadas são agregadas (R7/NFR-03)
    if len(df) > 5000:
        raise ValueError(f"{nome}: {len(df)} linhas — parece nível de registro; só agregados saem.")
    df.to_csv(OUT_DIR / "tabelas" / f"{nome}.csv", index=False, encoding="utf-8")
    return df


def salvar_figura(fig, nome: str):
    fig.savefig(OUT_DIR / "figuras" / f"{nome}.png", bbox_inches="tight", dpi=130)
    plt.show()


def grafico_floresta(df, rotulo, est, lo, hi, titulo, nome, ref=1.0):
    d = df.reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(7, 0.45 * len(d) + 1.4))
    y = np.arange(len(d))[::-1]
    ax.errorbar(d[est], y, xerr=[d[est] - d[lo], d[hi] - d[est]], fmt="o", color="#1f4e79", capsize=3)
    ax.axvline(ref, color="grey", ls="--")
    ax.set_yticks(y, d[rotulo])
    ax.set_xscale("log")
    ax.set_title(titulo)
    ax.set_xlabel("Razão de chances (escala log) — associação, não causalidade")
    salvar_figura(fig, nome)
'''))

# ============================================================================ 3. Carregamento
CELULAS.append(md(r'''
## 3. Carregamento dos dados

Só os anos de **desenvolvimento (2022–2023)** são lidos agora. **2024 (teste) só é lido na seção 16**,
dentro da avaliação única (R1/R2). Colunas: lista fechada de features + campos do alvo + colunas de
**auditoria** (`GRAV_*`, `ALRM_*`, `ID_UNIDADE`, `NDUPLIC_N`, `CRITERIO`) que **nunca** entram em `X`.
Os Parquets guardam texto cru; strings viram categorias para caber na RAM do Colab.
'''))
CELULAS.append(cod(r'''
import gc

import pyarrow.parquet as pq


def caminho_parquet(ano: int) -> Path:
    return DATA_DIR / "parquet" / f"dengue_{ano}.parquet"


def garantir_dados(anos):
    faltando = [a for a in anos if not caminho_parquet(a).exists()]
    if not faltando:
        return
    if not CONFIG["BAIXAR_SE_AUSENTE"]:
        raise FileNotFoundError(f"Parquets ausentes para {faltando} em {DATA_DIR / 'parquet'}.")
    for a in faltando:  # FTP oficial do DataSUS (D-05); o 2024 leva alguns minutos
        t0 = time.time()
        e = fetch_year(a, DATA_DIR)
        print(f"{a}: {e['linhas']:,} linhas baixadas e convertidas ({time.time() - t0:.0f} s)")


def ler_ano(ano: int) -> pd.DataFrame:
    esquema = pq.read_schema(caminho_parquet(ano)).names
    faltam = [c for c in COLUNAS_BASE if c not in esquema]
    if faltam:  # check bloqueante (FR-03)
        raise ValueError(f"Colunas essenciais ausentes em {ano}: {faltam}")
    auditoria = [c for c in COLUNAS_AUDITORIA if c in esquema]
    extras = [c for c in esquema if c.startswith(("GRAV_", "ALRM_"))]
    tabela = pq.read_table(caminho_parquet(ano), columns=COLUNAS_BASE + auditoria + extras)
    df = tabela.to_pandas(strings_to_categorical=True)
    df["ANO"] = ano  # ano do arquivo = ano do split (D-46)
    return df


def assinatura_dados(anos):
    mf = DATA_DIR / "manifest.json"
    manifesto = json.loads(mf.read_text("utf-8")) if mf.exists() else {}
    return {str(a): {"sha256_parquet": manifesto.get(str(a), {}).get("sha256_parquet"),
                     "revisao_datasus_utc": manifesto.get(str(a), {}).get("revisao_datasus_utc"),
                     "bytes": caminho_parquet(a).stat().st_size} for a in anos}


garantir_dados(CONFIG["ANOS_DEV"])
raw = {a: ler_ano(a) for a in CONFIG["ANOS_DEV"]}
for a, d in raw.items():
    assert_dev_only(d)  # R1: nada de 2024 aqui
ASSINATURA_DEV = assinatura_dados(CONFIG["ANOS_DEV"])
print(pd.DataFrame({a: {"linhas": len(d), "colunas lidas": d.shape[1],
                        "SHA-256 do Parquet": (ASSINATURA_DEV[str(a)]["sha256_parquet"] or "n/d")[:16],
                        "revisão DataSUS": ASSINATURA_DEV[str(a)]["revisao_datasus_utc"] or "n/d"}
                    for a, d in raw.items()}).to_string())
'''))

# ============================================================================ 4. Qualidade
CELULAS.append(md(r'''
## 4. Inspeção e qualidade dos dados

Checks **bloqueantes** (FR-03): domínio de `CLASSI_FIN` e `EVOLUCAO`. Se aparecerem os códigos 1/2/8 do
dicionário de 2024 (ou qualquer valor novo) em `CLASSI_FIN`, a definição do alvo (D-02) precisa ser
redecidida e o notebook **para**. Os demais itens são **alertas** (registram, não interrompem).

**Consistência da classificação de dengue grave e óbito:** cruzamos `CLASSI_FIN × EVOLUCAO` e
conferimos se os campos de gravidade (`GRAV_*`) acompanham `CLASSI_FIN = 12`. Esses campos são só
**auditoria**: definem o rótulo e não podem ser features.
'''))
CELULAS.append(cod(r'''
dominios = [checar_dominios_alvo(raw[a], a) for a in CONFIG["ANOS_DEV"]]  # levanta ValueError se falhar
print("Domínios de CLASSI_FIN/EVOLUCAO conferidos (check bloqueante OK):")
print(pd.DataFrame(dominios).to_string(index=False))

raw_dev = empilhar_populacoes([raw[a] for a in CONFIG["ANOS_DEV"]])
sem = "<branco>"
cruz = pd.crosstab(code(raw_dev["CLASSI_FIN"]).fillna(sem), code(raw_dev["EVOLUCAO"]).fillna(sem))
cruz.index.name, cruz.columns.name = "CLASSI_FIN", "EVOLUCAO"
print("\nCLASSI_FIN × EVOLUCAO (todas as notificações do desenvolvimento):")
display(cruz)
cols_grav = [c for c in raw_dev.columns if c.startswith("GRAV_")]
cols_alrm = [c for c in raw_dev.columns if c.startswith("ALRM_")]
aud = pd.concat({"algum GRAV_* preenchido": alarm_filled_by_class(raw_dev, cols_grav)["%"],
                 "algum ALRM_* preenchido": alarm_filled_by_class(raw_dev, cols_alrm)["%"]}, axis=1)
print("% de linhas com campos de gravidade/alarme preenchidos, por CLASSI_FIN (auditoria):")
display(aud.round(1))
salvar_tabela(cruz.reset_index(), "qualidade_classi_x_evolucao")
salvar_tabela(aud.reset_index(), "qualidade_grav_alrm_por_classi")
'''))
CELULAS.append(cod(r'''
tabs = {}
tabs["Comorbidades: valores (1, 2, branco, outros)"] = domain_counts(raw_dev, COMORBIDADES)
tabs["% ausente (branco ou ≠ 1/2) — comorbidades e sinais"] = absent_share(raw_dev, COMORBIDADES + SINAIS)
tabs["Idade decodificada por ano"] = age_summary(raw_dev)
tabs["Idade decodificada × (ano dos sintomas − ANO_NASC)"] = age_vs_birth_year(raw_dev)
tabs["Atraso sintomas → notificação (dias)"] = notification_delay(raw_dev)
tabs["Inconsistências demográficas"] = demography_inconsistencies(raw_dev)
for titulo, t in tabs.items():
    print(f"\n### {titulo}")
    display(t.round(2))
salvar_tabela(tabs["Idade decodificada por ano"].reset_index(), "qualidade_idade")
salvar_tabela(tabs["Atraso sintomas → notificação (dias)"].reset_index(), "qualidade_atraso_notificacao")
'''))

# ============================================================================ 5-6. População
CELULAS.append(md(r'''
## 5. Limpeza e preparação

Decisões (todas do spec; nenhuma é feita "no escuro"):

- **Texto cru → códigos:** `code()` remove espaços e o sufixo `.0` de números lidos como float; branco = nulo.
- **Idade:** `NU_IDADE_N` decodificado (1º dígito = unidade); se inválido ou fora de [0, 120], usa
  *ano dos sintomas − `ANO_NASC`* (D-50); sem nenhum dos dois, o caso sai e é contado no fluxograma.
- **Comorbidades e sintomas:** 1 → Sim, 2 → Não, qualquer outro valor (branco, 9) → **Ausente** (D-07).
- **Atraso até a notificação:** truncado em [0, 60] dias `[ASSUMPTION]`; ausente permanece nulo.
- **Duplicidades:** **não removidas** (D-47): não há identificador pessoal e a chave composta marca de
  17% a 42% como "duplicada", o que é implausível. Reportamos a taxa e rodamos uma **análise de
  sensibilidade** com chave mais estrita (seção 11).
- **Dados ausentes:** não há imputação de comorbidades; "Ausente" é categoria. O atraso ausente é
  imputado **dentro do pipeline de treino** (mediana da dobra) ou tratado nativamente pelas árvores.

## 6. Definição da população e dos desfechos
'''))
CELULAS.append(cod(r'''
fluxo = exclusion_flow(raw_dev)
motivos = exclusion_reasons(raw_dev)
print("Fluxograma de exclusão (FR-02), desenvolvimento:")
display(fluxo)
for titulo, t in motivos.items():
    print(f"\n{titulo}")
    display(t)
salvar_tabela(fluxo.reset_index(), "fluxograma_exclusao_dev")

pop = empilhar_populacoes([montar_populacao(raw[a], a) for a in CONFIG["ANOS_DEV"]])
n_raw = len(raw_dev)
del raw, raw_dev
gc.collect()
assert_dev_only(pop)

prev = prevalence_by_year(pop)
reg_ev = events_by(pop, "regiao")
print(f"\nPopulação de desenvolvimento: {len(pop):,} casos de {n_raw:,} notificações; "
      f"{int(pop['y'].sum()):,} eventos ({100 * pop['y'].mean():.3f}%).")
display(prev.round(3))
display(reg_ev.round(3))
sem_regiao = int(pop["regiao"].isna().sum())
print(f"Casos sem região de residência identificável: {sem_regiao:,} "
      f"(ficam sempre no treino; não pertencem a nenhuma dobra de teste).")
salvar_tabela(prev.reset_index(), "prevalencia_por_ano_dev")
salvar_tabela(reg_ev.reset_index(), "eventos_por_regiao_dev")
RESULTADOS["populacao_dev"] = {"casos": int(len(pop)), "eventos": int(pop["y"].sum()),
                               "prevalencia": float(pop["y"].mean()), "sem_regiao": sem_regiao}
'''))
CELULAS.append(cod(r'''
# Conferência com os valores do profiling (RESULTADOS.md, 3ª execução). Só números de 2022–23 (R1).
# O DataSUS revisa arquivos "finais": divergência é ALERTA (compare o hash do Parquet), não erro.
ESPERADO = {"casos": {2022: 1_148_299, 2023: 1_304_909}, "eventos": {2022: 1_869, 2023: 2_116},
            "eventos_regiao": {"Centro-Oeste": 736, "Nordeste": 582, "Norte": 121, "Sudeste": 1_736,
                               "Sul": 810}}
checks = []
for a in CONFIG["ANOS_DEV"]:
    checks.append((f"casos {a}", ESPERADO["casos"][a], int((pop["ANO"] == a).sum())))
    checks.append((f"eventos {a}", ESPERADO["eventos"][a], int(pop.loc[pop["ANO"] == a, "y"].sum())))
for r, n in ESPERADO["eventos_regiao"].items():
    checks.append((f"eventos {r}", n, int(pop.loc[pop["regiao"] == r, "y"].sum())))
conf = pd.DataFrame(checks, columns=["item", "esperado (profiling)", "obtido"])
conf["confere"] = conf["esperado (profiling)"] == conf["obtido"]
display(conf)
if not conf["confere"].all():
    print("⚠️ Há divergência com o profiling. Provável revisão do arquivo no DataSUS; "
          "confira o SHA-256 em data/manifest.json antes de comparar resultados.")
salvar_tabela(conf, "conferencia_profiling")

# Duplicatas (alerta, D-47): chave composta sem DT_NASC (mais fraca, tende a superestimar)
dup = duplicates(pop)
print("\nDuplicatas pela chave composta (ANO_NASC + idade + sexo + município + DT_SIN_PRI):")
display(dup.round(2))
salvar_tabela(dup.reset_index(), "duplicatas_dev")
'''))

# ============================================================================ 7. Features
CELULAS.append(md(r'''
## 7. Engenharia de atributos

**Lista fechada** (data-model §D; regra R4): idade (anos), sexo, gestação, 7 comorbidades
(Sim/Não/Ausente), nº de comorbidades, 12 sintomas + `LEUCOPENIA` e `LACO` (item 33 da ficha) e dias até
a notificação. Tudo o que não existe **no primeiro atendimento**, ou é proxy do rótulo, fica de fora:

| Grupo | Decisão | Motivo |
|---|---|---|
| `CLASSI_FIN`, `EVOLUCAO`, `DT_OBITO`, `DT_ENCERRA` | **fora** | são o rótulo ou derivados dele |
| `GRAV_*` (sinais de gravidade) | **fora sempre** | definem "dengue grave" (seria o próprio rótulo) |
| `ALRM_*` (sinais de alarme) | **fora** | só habilitados para `CLASSI_FIN` 11/12: o preenchimento revela a classe |
| `HOSPITALIZ`, `DT_INTERNA` | **fora** | posteriores à triagem; quase um desfecho; circulares com a conduta |
| Exames (sorologia, NS1, PCR, isolamento…), `CRITERIO` | **fora** | chegam dias depois / definidos no encerramento |
| Campos da antiga febre hemorrágica (`PETEQUIAS`, `LACO_N`, `PLAQ_MENOR`…) | **fora** | critérios de gravidade (proxy do rótulo). *Atenção:* `PETEQUIA_N` e `LACO` (item 33) **entram** |
| UF/região/município, unidade notificadora | **fora como feature** | incompatível com leave-one-region-out (D-21); unidade é proxy de gravidade. Região só serve de dobra/subgrupo |
| Raça/cor, escolaridade | **fora como feature** | 16–54% de ignorado (D-48); raça/cor é **subgrupo** de equidade |
| Ano, semana epidemiológica | **fora** | com split temporal o modelo não extrapola um ano nunca visto |

O pré-processamento **com estado** (spline, escala, imputação) fica em `Pipeline` e é ajustado só no
treino de cada dobra (R5). A codificação das árvores é um mapeamento fixo (sem estado): não há como vazar.
'''))
CELULAS.append(cod(r'''
x = montar_features(pop)
assert_features_permitidas(list(x.columns), FEATURES_M1)  # R4: nada fora da lista fechada
y = pop["y"].to_numpy()
regiao = pop["regiao"]
assert len(x) == len(y) == len(regiao)

dic = pd.DataFrame({"feature": FEATURES_M1,
                    "tipo": [("contínua" if c in ("idade_anos", "dias_ate_notificacao")
                              else "inteira" if c == "n_comorbidades"
                              else "binária" if c == "gestante" else "categórica (3 níveis)"
                              if c != "sexo" else "categórica (M/F/I)") for c in FEATURES_M1]})
print(f"{x.shape[1]} features em X. Dicionário:")
display(dic.T)
salvar_tabela(dic, "dicionario_de_features")

# Vazamento por completude da ficha (§3.8): "Ausente" não pode marcar o desfecho
aus = absent_by_target(pop, COMORBIDADES)
print("\n% 'Ausente' por desfecho (população final) — vazamento por completude:")
display(aus.round(3))
if (aus["razão y0/y1"] > 2).any():
    print("⚠️ Alguma comorbidade com razão > 2: rodar análise de sensibilidade (Q-06).")
salvar_tabela(aus.reset_index(), "vazamento_completude")

# Triagem univariada de vazamento: PR-AUC de cada feature sozinha (taxa por categoria, EM AMOSTRA).
# Um valor próximo de 1 indicaria um proxy do rótulo. Serve de alarme, não de seleção.
tri = []
for c in FEATURES_M1:
    s = x[c]
    if c in ("idade_anos", "dias_ate_notificacao"):
        s = pd.qcut(s.rank(method="first"), 20, labels=False)
    taxa = pd.Series(y).groupby(np.asarray(s.astype("object"))).transform("mean").to_numpy()
    tri.append({"feature": c, "PR-AUC univariada": pr_auc(y, taxa), "ROC-AUC univariada": roc_auc(y, taxa)})
tri = pd.DataFrame(tri).sort_values("PR-AUC univariada", ascending=False)
display(tri.head(8).round(4))
print(f"Prevalência (PR-AUC de referência de um preditor sem informação): {y.mean():.4f}")
if (tri["ROC-AUC univariada"] > 0.90).any():
    print("⚠️ Feature com ROC-AUC univariada > 0,90: investigar possível proxy do rótulo.")
salvar_tabela(tri, "triagem_vazamento_univariada")
'''))

# ============================================================================ 8. Exploratória
CELULAS.append(md(r'''
## 8. Análise exploratória e descritiva

Só dados de **desenvolvimento** (FR-18). Células com < 10 eventos não são publicadas
(aparecem como `<10` ou ficam em branco). Os riscos brutos são **descritivos**: não substituem o
modelo ajustado (E1) e não incorporam confusão por idade.
'''))
CELULAS.append(cod(r'''
t1 = tabela_caracteristicas(pop, x)
print("Tabela 1 — características por desfecho (n e % da coluna):")
display(t1)
salvar_tabela(t1, "tabela1_caracteristicas")

rb = riscos_brutos(pop, x)
for nome, t in rb.items():
    salvar_tabela(t, f"risco_bruto_{nome}")

fig, eixos = plt.subplots(1, 3, figsize=(14, 3.8))
t = rb["por_faixa_etaria"].dropna(subset=["risco_%"])
eixos[0].bar(t["categoria"], t["risco_%"], yerr=[t["risco_%"] - t["ic95_inf_%"], t["ic95_sup_%"] - t["risco_%"]],
             color="#1f4e79", capsize=3)
eixos[0].set_title("Risco bruto por faixa etária"); eixos[0].set_ylabel("% com dengue grave/óbito")
t = rb["por_n_comorbidades"].dropna(subset=["risco_%"])
eixos[1].bar(t["categoria"], t["risco_%"], yerr=[t["risco_%"] - t["ic95_inf_%"], t["ic95_sup_%"] - t["risco_%"]],
             color="#8c2d04", capsize=3)
eixos[1].set_title("Risco bruto por nº de comorbidades")
t = rb["por_comorbidade"]; t = t[t["categoria"] == "Sim"].dropna(subset=["risco_%"])
eixos[2].barh(t["comorbidade"], t["risco_%"], xerr=[t["risco_%"] - t["ic95_inf_%"], t["ic95_sup_%"] - t["risco_%"]],
              color="#2a6f4f", capsize=3)
eixos[2].set_title("Risco bruto entre quem tem a comorbidade")
fig.suptitle("Riscos brutos (descritivos, sem ajuste)", y=1.03)
salvar_figura(fig, "riscos_brutos")
'''))

# ============================================================================ 9. Associações
CELULAS.append(md(r'''
## 9. Análise de associações epidemiológicas

**Modelo explicativo E1** (objetivo principal): regressão logística **sem penalização** (para ter IC),
ajustada por idade (spline cúbico, 5 nós nos quantis da população), sexo e gestação. É uma análise de
**casos completos** (sexo M/F e nenhuma comorbidade "Ausente"), para evitar níveis esparsos; B1/M1
usam todas as linhas. O ajuste é feito sobre padrões de covariáveis agrupados (binomial agrupado),
equivalente ao ajuste linha a linha.

Nesta seção, por comorbidade: **OR bruto** (Woolf), **OR ajustado por idade, sexo e gestação** (uma
comorbidade por vez) e **OR mutuamente ajustado** (as 7 juntas, sem interações). Com milhões de linhas
quase tudo é "significativo": **interprete o tamanho do efeito e o IC, não o p-valor**. Todas as razões de
chances são **associações**, sujeitas a confundimento residual (ex.: hipertensão correlaciona com idade e
doença renal) e a viés de notificação; **não são efeitos causais**.
'''))
CELULAS.append(cod(r'''
agg, exclusao_e1 = agregar_e1(pop, x)
nos = nos_da_idade(x["idade_anos"])
IDADE_REF = CONFIG["IDADE_REF"] or float(pop.loc[pop["y"] == 1, "idade_anos"].median())
print("Casos completos para o E1:", exclusao_e1)
print("Nós do spline de idade (anos):", nos, "| idade de referência (mediana dos eventos):", IDADE_REF)

tor = tabela_or_comorbidades(agg, nos)
colunas = ["comorbidade", "casos_expostos", "eventos_expostos", "OR_bruto", "bruto_ic95_inf", "bruto_ic95_sup",
           "OR_aj_idade_sexo", "aj_idade_sexo_ic95_inf", "aj_idade_sexo_ic95_sup",
           "OR_aj_mutuo", "aj_mutuo_ic95_inf", "aj_mutuo_ic95_sup"]
display(tor[colunas].round(2))
salvar_tabela(tor[colunas], "or_comorbidades")
grafico_floresta(tor, "comorbidade", "OR_aj_idade_sexo", "aj_idade_sexo_ic95_inf", "aj_idade_sexo_ic95_sup",
                 "OR ajustado por idade, sexo e gestação (uma comorbidade por vez)", "or_ajustado_idade_sexo")
RESULTADOS["e1_casos_completos"] = exclusao_e1
'''))

# ============================================================================ 10. Combinações
CELULAS.append(md(r'''
## 10. Análise de combinações de comorbidades

E1 completo: efeitos principais + **interações 2 a 2** entre comorbidades + interação
comorbidade × idade (spline) para **hipertensão e diabetes** `[ASSUMPTION]`. Só entram os pares com
**≥ 10 eventos** na célula combinada. Para cada par:

- **OR da interação** (escala multiplicativa) e seu p-valor, com correção de **Benjamini-Hochberg** (FDR 5%);
- **RERI** e **AP** (escala aditiva), com IC 95% pelo método delta, na idade de referência. RERI > 0 indica
  que a combinação acrescenta risco **além da soma** dos efeitos; o OR aproxima o RR (desfecho raro).

A **tabela de perfis** dá o risco absoluto estimado (padronizado pela população de cada faixa etária)
por perfil exato de comorbidades. Combinações de 3+ vêm da **soma dos efeitos** (sem interações de 3ª ordem).
Células com < 10 eventos não saem.
'''))
CELULAS.append(cod(r'''
tabela_pares = pares_com_eventos(agg)
pares_e1 = [(r.A, r.B) for r in tabela_pares.itertuples() if r.entra_no_E1]
print(f"{len(pares_e1)} de {len(tabela_pares)} pares têm ≥ {MIN_EVENTOS_CELULA} eventos e entram no E1.")
display(tabela_pares)
salvar_tabela(tabela_pares, "pares_eventos")

m_e1 = ajustar_e1(agg, nos, pares_e1)
m_sem_pares = ajustar_e1(agg, nos, [], interacao_idade=INTERACAO_IDADE)
m_sem_idade = ajustar_e1(agg, nos, pares_e1, interacao_idade=())
lrt_pares = teste_razao_verossimilhanca(m_e1, m_sem_pares)
lrt_idade = teste_razao_verossimilhanca(m_e1, m_sem_idade)
print("Razão de verossimilhança — bloco de interações entre pares:", {k: round(v, 4) for k, v in lrt_pares.items()})
print("Razão de verossimilhança — bloco comorbidade × idade:", {k: round(v, 4) for k, v in lrt_idade.items()})

ti = tabela_interacoes(m_e1, agg, IDADE_REF)
cols_i = ["A", "B", "eventos_celula", "OR_interacao", "ic95_inf", "ic95_sup", "p_valor", "p_BH",
          "RERI", "RERI_ic95_inf", "RERI_ic95_sup", "AP", "AP_ic95_inf", "AP_ic95_sup"]
display(ti[cols_i].round(3))
salvar_tabela(ti[cols_i], "interacoes_pares_reri_ap")
if len(ti):
    ti["par"] = ti["A"] + " × " + ti["B"]
    grafico_floresta(ti, "par", "OR_interacao", "ic95_inf", "ic95_sup",
                     "OR da interação multiplicativa entre pares (E1)", "or_interacao_pares")
    fig, ax = plt.subplots(figsize=(7, 0.45 * len(ti) + 1.4))
    yy = np.arange(len(ti))[::-1]
    ax.errorbar(ti["RERI"], yy, xerr=[ti["RERI"] - ti["RERI_ic95_inf"], ti["RERI_ic95_sup"] - ti["RERI"]],
                fmt="o", color="#8c2d04", capsize=3)
    ax.axvline(0, color="grey", ls="--"); ax.set_yticks(yy, ti["par"])
    ax.set_title(f"RERI (interação aditiva), idade {IDADE_REF:.0f} anos"); ax.set_xlabel("RERI")
    salvar_figura(fig, "reri_pares")
RESULTADOS["e1_lrt"] = {"pares": lrt_pares, "idade": lrt_idade}
'''))
CELULAS.append(cod(r'''
perfis = tabela_perfis(m_e1, agg)
pct = ["risco_estimado", "ic95_inf", "ic95_sup"]
vis = perfis.copy()
vis[pct] = (100 * vis[pct]).round(3)
print("Tabela de perfis (risco em %; padronizado por faixa etária; E1):")
display(vis.round(2))
salvar_tabela(perfis, "tabela_de_perfis")

faixa_graf = "60–79" if (perfis["faixa_etaria"] == "60–79").any() else perfis["faixa_etaria"].iloc[0]
g = perfis[perfis["faixa_etaria"] == faixa_graf].sort_values("risco_estimado")
fig, ax = plt.subplots(figsize=(7, 0.4 * len(g) + 1.5))
ax.barh(g["perfil"], 100 * g["risco_estimado"],
        xerr=[100 * (g["risco_estimado"] - g["ic95_inf"]), 100 * (g["ic95_sup"] - g["risco_estimado"])],
        color="#1f4e79", capsize=3)
ax.set_xlabel("Risco estimado de dengue grave/óbito (%)")
ax.set_title(f"Perfis de comorbidades — faixa {faixa_graf} anos (E1; associação, não causalidade)")
salvar_figura(fig, "perfis_risco")
'''))

# ============================================================================ 11. Ajustes por idade e sexo
CELULAS.append(md(r'''
## 11. Ajustes por idade e sexo, ranking e análise de sensibilidade

- **Heterogeneidade por idade:** como hipertensão e diabetes interagem com a idade, o "efeito" depende
  da idade. Mostramos o OR de cada comorbidade (demais ausentes) em idades de referência.
- **Ranking (FR-19):** pelo **OR do E1** na idade de referência (e **só** dele, R10: nunca por SHAP ou
  importância de árvore). Comorbidades com IC 95% sobrepostos ficam como **"sem ordem definida"**.
- **Sensibilidade (D-47):** reajusta o E1 removendo duplicatas por uma chave **mais estrita** (+ unidade
  notificadora + data de notificação) para ver se os OR mudam.
'''))
CELULAS.append(cod(r'''
idades = [5, 20, 40, 60, 80]
linhas = []
for c in COMORBIDADES:
    for ida in idades:
        r = or_com_ic(m_e1, {c}, ida)
        linhas.append({"comorbidade": c, "idade": ida, "OR": r["OR"], "ic95_inf": r["ic95_inf"],
                       "ic95_sup": r["ic95_sup"]})
or_idade = pd.DataFrame(linhas)
display(or_idade.pivot(index="comorbidade", columns="idade", values="OR").round(2))
salvar_tabela(or_idade, "or_por_idade_e1")

fig, ax = plt.subplots(figsize=(7, 4))
for c in COMORBIDADES:
    d = or_idade[or_idade["comorbidade"] == c]
    ax.plot(d["idade"], d["OR"], marker="o", label=c, lw=2.2 if c in INTERACAO_IDADE else 1)
ax.axhline(1, color="grey", ls="--"); ax.set_yscale("log"); ax.legend(fontsize=7, ncol=2)
ax.set_xlabel("idade (anos)"); ax.set_ylabel("OR (log)")
ax.set_title("OR por comorbidade segundo a idade (linhas grossas: interação com idade no E1)")
salvar_figura(fig, "or_por_idade")

rank = ranking_comorbidades(m_e1, IDADE_REF)
print(f"Ranking de comorbidades pelo OR do E1 na idade de referência ({IDADE_REF:.0f} anos):")
display(rank.drop(columns=["log_or", "se"]).round(2))
salvar_tabela(rank.drop(columns=["log_or", "se"]), "ranking_comorbidades")
RESULTADOS["ranking_comorbidades"] = rank[["posicao", "comorbidade", "OR"]].round(3).to_dict("records")
'''))
CELULAS.append(cod(r'''
def chave_estrita(df):
    partes = [code(df[c]).fillna("<b>") for c in
              ("ID_UNIDADE", "DT_NOTIFIC", "DT_SIN_PRI", "ID_MN_RESI", "CS_SEXO", "ANO_NASC", "NU_IDADE_N")
              if c in df.columns]
    chave = partes[0]
    for p in partes[1:]:
        chave = chave + "|" + p
    return chave


if CONFIG["SENSIBILIDADE_DUPLICATAS"] and "ID_UNIDADE" in pop.columns:
    manter = ~chave_estrita(pop).duplicated().to_numpy()
    pop_s, x_s = pop[manter].reset_index(drop=True), x[manter].reset_index(drop=True)
    agg_s, _ = agregar_e1(pop_s, x_s)
    tp_s = pares_com_eventos(agg_s)
    pares_s = [(r.A, r.B) for r in tp_s.itertuples() if r.entra_no_E1]
    m_s = ajustar_e1(agg_s, nos_da_idade(x_s["idade_anos"]), pares_s)
    base = {c: or_com_ic(m_e1, {c}, IDADE_REF) for c in COMORBIDADES}
    sens = {c: or_com_ic(m_s, {c}, IDADE_REF) for c in COMORBIDADES}
    sens_t = pd.DataFrame({"comorbidade": COMORBIDADES,
                           "OR (análise principal)": [base[c]["OR"] for c in COMORBIDADES],
                           "OR (sem duplicatas da chave estrita)": [sens[c]["OR"] for c in COMORBIDADES]})
    sens_t["variação relativa (%)"] = 100 * (sens_t.iloc[:, 2] / sens_t.iloc[:, 1] - 1)
    print(f"Chave estrita: {int((~manter).sum()):,} linhas removidas de {len(pop):,} "
          f"({100 * (~manter).mean():.1f}%), {int(pop.loc[~manter, 'y'].sum())} eventos.")
    display(sens_t.round(2))
    salvar_tabela(sens_t, "sensibilidade_duplicatas")
    del pop_s, x_s, agg_s, m_s
    gc.collect()
else:
    print("Análise de sensibilidade de duplicatas não executada (desligada ou sem ID_UNIDADE).")
'''))

# ============================================================================ 12. Preparação ML
CELULAS.append(md(r'''
## 12. Preparação dos dados para ML

- **Unidade:** uma notificação confirmada. **Alvo:** `y` (grave ou óbito). **Features:** `X` da seção 7.
- **Prevalência natural, sem correção de desbalanceamento** (R3/D-38). Não há `class_weight`,
  `scale_pos_weight`, SMOTE nem subamostragem: corrigir o desbalanceamento não melhora AUROC/AUPRC e
  **piora a calibração** (van den Goorbergh et al., JAMIA 2022). O recall é controlado pelo **limiar**
  (F2, que pesa mais o recall, coerente com o custo maior do falso negativo — D-14/D-33) e as
  probabilidades são **calibradas depois**, em predições fora da dobra.
- **Sem vazamento:** `X` só tem a lista fechada; ano/região/unidade ficam fora; pré-processamento com
  estado dentro de `Pipeline`; early stopping só na validação interna (10% das regiões de **treino**).
'''))
CELULAS.append(cod(r'''
PROIBIDOS_R3 = ("class_weight", "scale_pos_weight", "is_unbalance", "auto_class_weights", "pos_weight",
                "sample_weight")
for nome_m, grade in GRADES.items():
    for p in grade:
        assert not any(k in PROIBIDOS_R3 for k in p), f"R3: correção de desbalanceamento em {nome_m}: {p}"
assert_dev_only(pop[["ANO"]])
assert_features_permitidas(list(x.columns), FEATURES_M1)
ok_oof = ~regiao.isna().to_numpy()  # linhas com região (as demais ficam só no treino)
b2_dev = b2_flag(x)
print(f"X: {x.shape[0]:,} linhas × {x.shape[1]} features | eventos: {int(y.sum()):,} "
      f"({100 * y.mean():.3f}%) | B2 sinaliza {100 * b2_dev.mean():.1f}% da população de desenvolvimento")
'''))

# ============================================================================ 13. Split
CELULAS.append(md(r'''
## 13. Separação e validação dos conjuntos

| Etapa | Dados | Uso |
|---|---|---|
| Desenvolvimento | 2022–2023, todas as regiões | **Leave-one-region-out** (5 dobras): treina em 4 regiões, prediz a 5ª |
| Tuning | predições fora da dobra | hiperparâmetros pela **PR-AUC média** das 5 dobras |
| Calibração e limiar | predições fora da dobra, agrupadas | calibrador (isotônica/Platt) e limiar (máx. F2) |
| Early stopping | 10% estratificado das regiões **de treino** | nunca a região deixada de fora (R6) |
| Modelo final | 2022–2023 completo | retreino; nº de árvores = mediana dos melhores pontos (D-37) |
| **Teste congelado** | **2024** | avaliado **uma única vez**, depois do congelamento; lacre em disco (R2) |

Por que região: mede a robustez geográfica (diferenças de notificação e de sistema) e é a validação
"interna-externa"; 2024 acrescenta a validação **temporal** (outro ano epidêmico, possível mudança de
sorotipo/distribuição). A comparação é pareada: todos os modelos preveem **as mesmas linhas** nas **mesmas dobras**.
'''))
CELULAS.append(cod(r'''
dobras = dobras_loro(regiao)
tab_dobras = pd.DataFrame([{"região deixada de fora": r, "casos de treino": len(tr), "casos fora da dobra": len(te),
                            "eventos fora da dobra": int(y[te].sum()),
                            "< 100 eventos": "⚠️" if y[te].sum() < CONFIG["MIN_EVENTOS_SUBGRUPO"] else ""}
                           for r, tr, te in dobras])
display(tab_dobras)
salvar_tabela(tab_dobras, "dobras_loro")
if (tab_dobras["eventos fora da dobra"] < CONFIG["MIN_EVENTOS_SUBGRUPO"]).any():
    print("⚠️ Dobra com < 100 eventos: a calibração dessa região terá IC largo (§3.8).")
'''))

# ============================================================================ 14. Treinamento
CELULAS.append(md(r'''
## 14. Treinamento e otimização dos modelos

**Baselines (obrigatórios, FR-04):** B0 (prevalência do treino), B1 (logística de efeitos principais) e B2
(regra do grupo B do protocolo do MS, avaliada nas seções 15, 17 e 18).

**Candidatos de M1** (mesmas linhas, dobras e semente — comparação justa):

1. **Logística elastic net** (L1+L2, `saga`): features de M1 + as 21 interações entre comorbidades.
   Só para predição; o E1 continua sem penalização para ter IC.
2. **Random Forest** (`max_samples` reduz custo e memória sem distorcer probabilidades).
3. **Gradient boosting:** XGBoost (`aucpr`, early stopping na validação interna) ou
   HistGradientBoosting se XGBoost não estiver instalado.

**Busca de hiperparâmetros:** grade **pequena e declarada** (célula de configuração; `[ASSUMPTION]`,
Q-08 pendente de aprovação), critério = PR-AUC média nas 5 dobras, com orçamento de tempo por modelo
(a 1ª configuração sempre roda) e **cache em disco** (retomável se o Colab cair). **Pendentes do spec:**
CatBoost, MLP (PyTorch) e TabFM, que dependem de pacotes/GPU ainda não aprovados (T-2.0).
'''))
CELULAS.append(cod(r'''
t0 = time.time()
oof_B0 = oof_b0(y, regiao)
oof_B1 = oof_b1(x, y, regiao)
print(f"Baselines B0 e B1 nas 5 dobras: {time.time() - t0:.0f} s | PR-AUC fora da dobra: "
      f"B0 {pr_auc(y[ok_oof], oof_B0[ok_oof]):.4f} | B1 {pr_auc(y[ok_oof], oof_B1[ok_oof]):.4f}")

ASSIN = {"dados": ASSINATURA_DEV, "n": int(len(y)), "eventos": int(y.sum()), "seed": CONFIG["SEED"],
         "boosting": BOOSTING, "paciencia": CONFIG["PACIENCIA_BOOSTING"],
         "val": CONFIG["VALIDACAO_INTERNA_FRAC"], "max_iter": CONFIG["MAX_ITER_BOOSTING"]}
CANDIDATOS = ["elastic_net", "random_forest", "xgboost"]
busca = {}
for nome in CANDIDATOS:
    grade = [({**p, "max_iter": CONFIG["EN_MAX_ITER"]} if nome == "elastic_net" else p) for p in GRADES[nome]]
    busca[nome] = busca_hiperparametros(
        nome, grade, x, y, regiao, CONFIG["SEED"], CONFIG["ORCAMENTO_S"][nome],
        cache_dir=OUT_DIR / "cache", assinatura=ASSIN, paciencia=CONFIG["PACIENCIA_BOOSTING"],
        val_frac=CONFIG["VALIDACAO_INTERNA_FRAC"], max_iter=CONFIG["MAX_ITER_BOOSTING"],
        device=CONFIG["DEVICE"], n_jobs=CONFIG["N_JOBS"])
    b = busca[nome]
    print(f"\n{nome}: {b['configs_avaliadas']}/{b['configs_na_grade']} configurações em "
          f"{b['tempo_total_s']:.0f} s (orçamento {CONFIG['ORCAMENTO_S'][nome]} s)")
    display(b["tabela"].round(4))
    salvar_tabela(b["tabela"], f"busca_{nome}")
'''))
CELULAS.append(cod(r'''
# Calibração (FR-08, FR-17): tipo escolhido pelo menor Brier com calibração CRUZADA POR REGIÃO,
# para as métricas de desenvolvimento não ficarem otimistas. O calibrador final usa todas as OOF.
oof_raw = {n: busca[n]["melhor"]["oof"] for n in CANDIDATOS}
cal_tipo, oof_cal = {}, {}
for n in CANDIDATOS:
    cal_tipo[n], tab_cal = escolher_calibrador(oof_raw[n], y, regiao)
    oof_cal[n] = calibrar_cruzado(oof_raw[n], y, regiao, cal_tipo[n])
    print(n, "→ calibrador:", cal_tipo[n], "|", tab_cal.round(6).to_dict("records"))

resumo = pd.DataFrame([{"modelo": n, "pr_auc_media": busca[n]["melhor"]["pr_auc_media"],
                        "brier": brier(y[ok_oof], oof_cal[n][ok_oof]), "calibrador": cal_tipo[n],
                        "config": busca[n]["melhor"]["params"]} for n in CANDIDATOS])
SELECIONADO, MOTIVO = selecionar_modelo(resumo)
print(f"\nModelo M1 selecionado: {SELECIONADO} — {MOTIVO} (regra de §3.11; sem olhar 2024)")
display(resumo.round(5))
salvar_tabela(resumo.assign(config=resumo["config"].astype(str)), "selecao_m1")
RESULTADOS["selecao_m1"] = {"modelo": SELECIONADO, "motivo": MOTIVO, "boosting": BOOSTING,
                            "params": busca[SELECIONADO]["melhor"]["params"],
                            "calibrador": cal_tipo[SELECIONADO]}
'''))

# ============================================================================ 15. Avaliação dev
CELULAS.append(md(r'''
## 15. Avaliação e calibração (desenvolvimento, predições fora da dobra)

Métricas **pooled** sobre as predições fora da dobra (cada paciente é previsto por um modelo que **não viu
a região dele**). As probabilidades dos candidatos usam calibração **cruzada por região**; o B1 é a
logística simples sem recalibração. Calibração: *slope* ideal = 1, intercepto (CITL) ideal = 0, O:E ideal = 1.
Estas são métricas de **desenvolvimento** (ligeiramente otimistas, pois tuning e calibração compartilham as
mesmas predições); o número que vale é o do teste de 2024.
'''))
CELULAS.append(cod(r'''
def linha_metricas(nome, p, tem_cal=True):
    ok = ok_oof
    d = {"modelo": nome, "PR-AUC (pooled)": pr_auc(y[ok], p[ok]), "ROC-AUC": roc_auc(y[ok], p[ok]),
         "Brier": brier(y[ok], p[ok])}
    if tem_cal:
        c = calibracao_resumo(y[ok], p[ok])
        d.update({"slope": c["slope"], "intercepto (CITL)": c["intercepto_citl"], "O:E": c["O:E"]})
    return d


linhas = [linha_metricas("B0 (prevalência)", oof_B0, tem_cal=False), linha_metricas("B1 (logística simples)", oof_B1)]
linhas += [linha_metricas(f"{n} (calibrado)", oof_cal[n]) for n in CANDIDATOS]
for l, n in zip(linhas[2:], CANDIDATOS):
    l["PR-AUC (média das dobras)"] = busca[n]["melhor"]["pr_auc_media"]
met_dev = pd.DataFrame(linhas)
display(met_dev.round(4))
salvar_tabela(met_dev, "metricas_dev_oof")

# Limiar e comparação com a regra do MS nos MESMOS pacientes (dev, fora da dobra)
sel_raw = oof_raw[SELECIONADO]
cal_final = Calibrador(cal_tipo[SELECIONADO]).ajustar(sel_raw[ok_oof], y[ok_oof])
p_dev = cal_final.prever(np.where(np.isnan(sel_raw), 0.0, sel_raw))   # calibrador final (o do teste)
p_dev_cv = oof_cal[SELECIONADO]                                       # calibração cruzada (honesta)
LIM_F2, _ = melhor_limiar_f2(y[ok_oof], p_dev[ok_oof])
LIM_B1, _ = melhor_limiar_f2(y[ok_oof], oof_B1[ok_oof])
met_b2 = metricas_limiar(y[ok_oof], b2_dev[ok_oof])
LIM_SENS = limiar_para_sensibilidade(y[ok_oof], p_dev[ok_oof], met_b2["sensibilidade"])
LIM_FRAC = limiar_para_fracao(y[ok_oof], p_dev[ok_oof], met_b2["pct_sinalizados"])
flags_dev = {"B0 (ninguém)": np.zeros(len(y), bool), "B2 — regra do MS": b2_dev,
             "B1 no limiar F2": oof_B1 >= LIM_B1, "M1 no limiar F2": p_dev >= LIM_F2,
             "M1 com a mesma sensibilidade de B2": p_dev >= LIM_SENS,
             "M1 sinalizando a mesma fração de B2": p_dev >= LIM_FRAC}
lim_dev = pd.DataFrame([{"classificador": k, **metricas_limiar(y[ok_oof], f[ok_oof])} for k, f in flags_dev.items()])
display(lim_dev.round(4))
salvar_tabela(lim_dev, "metricas_limiar_dev")
print(f"Limiares (calibrados, só dev): F2 de M1 = {LIM_F2:.5f} | F2 de B1 = {LIM_B1:.5f} | "
      f"sensibilidade de B2 → {LIM_SENS:.5f} | fração de B2 → {LIM_FRAC:.5f}")
RESULTADOS["dev"] = {"limiar_f2_m1": LIM_F2, "limiar_f2_b1": LIM_B1, "limiar_sens_b2": LIM_SENS,
                     "limiar_frac_b2": LIM_FRAC, "metricas_oof": met_dev.round(5).to_dict("records")}
'''))
CELULAS.append(cod(r'''
# Matrizes de confusão (dev) e por região (robustez geográfica)
fig, eixos = plt.subplots(1, 3, figsize=(12, 3.3))
for ax, (nome, f) in zip(eixos, [("B2 — regra do MS", flags_dev["B2 — regra do MS"]),
                                 ("M1 no limiar F2", flags_dev["M1 no limiar F2"]),
                                 ("M1 com a sensibilidade de B2", flags_dev["M1 com a mesma sensibilidade de B2"])]):
    m = metricas_limiar(y[ok_oof], f[ok_oof])
    mat = np.array([[m["TN"], m["FP"]], [m["FN"], m["TP"]]])
    ax.imshow(np.log10(mat + 1), cmap="Blues")
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{mat[i, j]:,}".replace(",", " "), ha="center", va="center", fontsize=9)
    ax.set_xticks([0, 1], ["previsto 0", "previsto 1"]); ax.set_yticks([0, 1], ["real 0", "real 1"])
    ax.set_title(nome, fontsize=9); ax.grid(False)
fig.suptitle("Matrizes de confusão — desenvolvimento (fora da dobra)", y=1.04)
salvar_figura(fig, "matrizes_confusao_dev")

reg_linhas = []
for r, tr, te in dobras:
    ev = int(y[te].sum())
    d = {"região": r, "casos": len(te), "eventos": ev, "prevalência_%": 100 * y[te].mean(),
         "PR-AUC M1": pr_auc(y[te], p_dev_cv[te]), "PR-AUC B1": pr_auc(y[te], oof_B1[te]),
         "ROC-AUC M1": roc_auc(y[te], p_dev_cv[te])}
    if ev >= CONFIG["MIN_EVENTOS_SUBGRUPO"]:
        d["slope M1"] = calibracao_resumo(y[te], p_dev_cv[te])["slope"]
    else:
        d["aviso"] = "< 100 eventos: IC largo"
    reg_linhas.append(d)
por_regiao = pd.DataFrame(reg_linhas)
display(por_regiao.round(4))
salvar_tabela(por_regiao, "metricas_por_regiao_dev")
'''))
CELULAS.append(cod(r'''
from sklearn.metrics import precision_recall_curve

fig, eixos = plt.subplots(1, 3, figsize=(15, 4.2))
for nome, p in [(f"M1 ({SELECIONADO})", p_dev_cv), ("B1", oof_B1)]:
    pr, rc, _ = precision_recall_curve(y[ok_oof], p[ok_oof])
    eixos[0].plot(rc, pr, label=f"{nome} (AP={pr_auc(y[ok_oof], p[ok_oof]):.3f})")
m2 = metricas_limiar(y[ok_oof], b2_dev[ok_oof])
eixos[0].scatter([m2["sensibilidade"]], [m2["VPP"]], color="red", zorder=5, label="B2 — regra do MS")
eixos[0].axhline(y[ok_oof].mean(), color="grey", ls="--", label="B0 (prevalência)")
eixos[0].set_xlabel("recall"); eixos[0].set_ylabel("precisão"); eixos[0].legend(fontsize=7)
eixos[0].set_title("Curva precisão–recall (dev, fora da dobra)")

for nome, p in [(f"M1 ({SELECIONADO})", p_dev_cv), ("B1", oof_B1)]:
    cc = curva_calibracao(y[ok_oof], p[ok_oof])
    eixos[1].errorbar(cc["p_medio"], cc["taxa_observada"],
                      yerr=[cc["taxa_observada"] - cc["ic95_inf"], cc["ic95_sup"] - cc["taxa_observada"]],
                      marker="o", capsize=2, label=nome)
lim = max(cc["p_medio"].max(), cc["taxa_observada"].max()) * 1.1
eixos[1].plot([0, lim], [0, lim], "k--", lw=1)
eixos[1].set_xscale("symlog", linthresh=1e-3); eixos[1].set_yscale("symlog", linthresh=1e-3)
eixos[1].set_xlabel("risco previsto médio (decil)"); eixos[1].set_ylabel("taxa observada")
eixos[1].set_title("Calibração (dev, decis)"); eixos[1].legend(fontsize=7)

lims = np.linspace(*CONFIG["DCA_LIMIARES"][:2], CONFIG["DCA_LIMIARES"][2])
dca_dev = {"M1": curva_decisao(y[ok_oof], p=p_dev_cv[ok_oof], limiares=lims),
           "B1": curva_decisao(y[ok_oof], p=oof_B1[ok_oof], limiares=lims),
           "B2": curva_decisao(y[ok_oof], flag=b2_dev[ok_oof], limiares=lims)}
for k, d in dca_dev.items():
    eixos[2].plot(d["limiar"], d["net_benefit"], label=k)
eixos[2].plot(lims, net_benefit_todos(y[ok_oof].mean(), lims), "k:", label="tratar todos")
eixos[2].axhline(0, color="grey", label="tratar ninguém")
eixos[2].set_xlabel("limiar de risco"); eixos[2].set_ylabel("benefício líquido")
eixos[2].set_title("Curva de decisão (dev)"); eixos[2].legend(fontsize=7)
salvar_figura(fig, "avaliacao_dev_pr_calibracao_dca")
'''))

# ============================================================================ 16. Interpretabilidade
CELULAS.append(md(r'''
## 16. Interpretabilidade e congelamento

**Três coisas diferentes (não confundir):**

| Conceito | Ferramenta | O que diz | O que **não** diz |
|---|---|---|---|
| **Associação estatística** | OR do E1 (seções 9–11) | quanto, em média e ajustado por idade/sexo, o risco difere entre quem tem e quem não tem a condição | que a condição *causa* o desfecho (confundimento residual, viés de notificação) |
| **Importância preditiva** | SHAP / permutação do M1 | quanto cada variável contribui **para a saída do modelo** | associação ajustada nem causa; com variáveis correlacionadas a atribuição é instável |
| **Causalidade** | — | **nada neste notebook a estima** | — |

SHAP explica o **modelo**, não o mundo. Abaixo: importância global (e interações) do melhor modelo de
**árvore**, numa subamostra estratificada **do desenvolvimento**, e a comparação com o ranking pelo OR
(que continua sendo a única fonte do ranking de comorbidades, R10).

Depois, o **congelamento**: retreino em todo o desenvolvimento, serialização com SHA-256 e metadados
(FR-12). **Daqui em diante nada é escolhido pelo teste (R1/R2).**
'''))
CELULAS.append(cod(r'''
import joblib
from scipy.stats import spearmanr

dev_meta = pop[["ANO"]]
n_iter_mediano = int(np.median(busca[SELECIONADO]["melhor"]["melhor_iter"]))
kw_modelo = dict(paciencia=CONFIG["PACIENCIA_BOOSTING"], val_frac=CONFIG["VALIDACAO_INTERNA_FRAC"],
                 max_iter=CONFIG["MAX_ITER_BOOSTING"], device=CONFIG["DEVICE"], n_jobs=CONFIG["N_JOBS"])
t0 = time.time()
M1_FINAL = ajustar_final(SELECIONADO, busca[SELECIONADO]["melhor"]["params"], x, y, CONFIG["SEED"],
                         n_iter_mediano, x_meta=dev_meta, **kw_modelo)
B1_FINAL = ModeloB1().ajustar(x, y)
print(f"Retreino final de M1 ({SELECIONADO}) e B1 em todo o desenvolvimento: {time.time() - t0:.0f} s "
      f"| nº de árvores/épocas = mediana dos melhores pontos das dobras: {n_iter_mediano}")

# Melhor modelo de árvore para o SHAP (o selecionado, se for de árvore)
arvores = [n for n in ("xgboost", "random_forest") if n in busca]
nome_arvore = SELECIONADO if SELECIONADO in arvores else max(arvores, key=lambda n: busca[n]["melhor"]["pr_auc_media"])
if nome_arvore == SELECIONADO:
    M_ARVORE = M1_FINAL
else:
    M_ARVORE = ajustar_final(nome_arvore, busca[nome_arvore]["melhor"]["params"], x, y, CONFIG["SEED"],
                             int(np.median(busca[nome_arvore]["melhor"]["melhor_iter"])), x_meta=dev_meta,
                             **kw_modelo)
print("Modelo de árvore usado na interpretabilidade:", nome_arvore)


def amostra_estratificada(y_, n, seed):
    rng = np.random.default_rng(seed)
    idx = []
    for classe in (0, 1):
        pos = np.flatnonzero(y_ == classe)
        k = min(len(pos), max(1, int(round(n * len(pos) / len(y_)))))
        idx.append(rng.choice(pos, size=k, replace=False))
    return np.sort(np.concatenate(idx))
'''))
CELULAS.append(cod(r'''
try:
    import shap
except ImportError:
    shap = None

n_shap = CONFIG["SHAP_AMOSTRA"] if nome_arvore == "xgboost" else min(CONFIG["SHAP_AMOSTRA"], 5_000)
idx_s = amostra_estratificada(y, n_shap, CONFIG["SEED"])
Xs = matriz_arvore(x.iloc[idx_s], dias_nan=-1.0 if nome_arvore == "random_forest" else None)
imp = None
if shap is not None:
    expl = shap.TreeExplainer(M_ARVORE.motor_)
    sv = expl.shap_values(Xs)
    if isinstance(sv, list):
        sv = sv[1]
    sv = np.asarray(sv)
    if sv.ndim == 3:
        sv = sv[:, :, -1]
    imp = pd.DataFrame({"feature": Xs.columns, "mean_abs_shap": np.abs(sv).mean(axis=0)})
    metodo_imp = "SHAP (|valor| médio, em log-odds)"
    fig = plt.figure(figsize=(8, 5))
    shap.summary_plot(sv, Xs, show=False, max_display=15)
    plt.title(f"SHAP — {nome_arvore} (subamostra estratificada de {len(idx_s):,} casos do desenvolvimento)")
    salvar_figura(plt.gcf(), "shap_resumo")
else:  # alternativa: importância por permutação (queda de PR-AUC), na mesma subamostra
    rng = np.random.default_rng(CONFIG["SEED"])
    xa, ya = x.iloc[idx_s].reset_index(drop=True), y[idx_s]
    base = pr_auc(ya, M_ARVORE.prever(xa))
    linhas = []
    for c in x.columns:
        perda = []
        for _ in range(3):
            xp = xa.copy()
            xp[c] = xp[c].sample(frac=1, random_state=int(rng.integers(1e9))).reset_index(drop=True)  # mantém o dtype
            perda.append(base - pr_auc(ya, M_ARVORE.prever(xp)))
        linhas.append({"feature": c, "mean_abs_shap": float(np.mean(perda))})
    imp = pd.DataFrame(linhas)
    metodo_imp = "permutação (queda de PR-AUC) — SHAP não instalado"
imp = imp.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)
print("Importância preditiva (", metodo_imp, "):")
display(imp.head(15).round(5))
salvar_tabela(imp, "importancia_preditiva")

# Interações SHAP (FR-13, SHOULD): só XGBoost, subamostra menor por custo O(n·F²)
if shap is not None and nome_arvore == "xgboost":
    k = min(CONFIG["SHAP_INTERACAO_AMOSTRA"], len(Xs))
    iv = np.abs(expl.shap_interaction_values(Xs.iloc[:k]))
    F = len(Xs.columns)
    pares_iv = [{"A": Xs.columns[i], "B": Xs.columns[j], "mean_abs_interacao": iv[:, i, j].mean() * 2}
                for i in range(F) for j in range(i + 1, F)]
    tab_iv = pd.DataFrame(pares_iv).sort_values("mean_abs_interacao", ascending=False).head(10)
    print(f"Maiores interações SHAP entre pares (subamostra de {k:,} linhas):")
    display(tab_iv.round(5))
    salvar_tabela(tab_iv, "shap_interacoes")

# Importância preditiva ≠ associação: comparação (só descritiva) com o ranking pelo OR do E1
comp = rank[["comorbidade", "OR"]].merge(imp.rename(columns={"feature": "comorbidade"}), on="comorbidade")
comp["posição_OR"] = comp["OR"].rank(ascending=False)
comp["posição_importância"] = comp["mean_abs_shap"].rank(ascending=False)
rho = spearmanr(comp["posição_OR"], comp["posição_importância"])[0] if len(comp) > 2 else np.nan
display(comp.round(4))
print(f"Correlação de postos (Spearman) entre OR e importância preditiva: {rho:.2f}. "
      "Diferenças são esperadas: respondem a perguntas diferentes (associação ajustada × contribuição ao modelo).")
salvar_tabela(comp, "or_vs_importancia")
'''))

# ============================================================================ Congelamento
CELULAS.append(cod(r'''
import subprocess as _sp

try:
    COMMIT = _sp.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=BASE, timeout=10).stdout.strip() or None
except Exception:
    COMMIT = None

BUNDLE = {"m1": M1_FINAL, "calibrador": cal_final, "limiar_f2": LIM_F2, "limiar_sens_b2": LIM_SENS,
          "limiar_frac_b2": LIM_FRAC, "b1": B1_FINAL, "limiar_b1_f2": LIM_B1, "modelo": SELECIONADO,
          "features": FEATURES_M1, "prevalencia_dev": float(y.mean())}
caminho_bundle = OUT_DIR / "artefatos" / "m1_congelado.joblib"
joblib.dump(BUNDLE, caminho_bundle)
SHA_BUNDLE = sha256_file(caminho_bundle)
META = {"congelado_em_utc": pd.Timestamp.now("UTC").isoformat(timespec="seconds"), "sha256_modelo": SHA_BUNDLE,
        "commit_git": COMMIT, "seed": CONFIG["SEED"], "ambiente": AMBIENTE, "assinatura_dados_dev": ASSINATURA_DEV,
        "config": json.loads(json.dumps(CONFIG, default=list)), "grades": GRADES, "selecao": RESULTADOS["selecao_m1"],
        "metricas_validacao": RESULTADOS["dev"],
        "e1": {"rhs": m_e1.rhs, "nos": list(nos), "pares": [list(p) for p in pares_e1],
               "coeficientes": {k: float(v) for k, v in m_e1.beta.items()}}}
(OUT_DIR / "artefatos" / "m1_congelado_metadados.json").write_text(
    json.dumps(META, indent=2, ensure_ascii=False, default=str), "utf-8")
print("Modelo congelado:", caminho_bundle.name, "| SHA-256:", SHA_BUNDLE[:20], "…")
print("Limiares congelados:", {k: round(BUNDLE[k], 6) for k in ("limiar_f2", "limiar_sens_b2", "limiar_frac_b2", "limiar_b1_f2")})
'''))

# ============================================================================ Teste único
CELULAS.append(md(r'''
### Avaliação única no teste (2024)

**Lacre (R2):** antes de ler 2024 grava-se `LACRE_TESTE_2024.json` com o SHA-256 do modelo congelado.
Se uma execução anterior **terminou**, esta célula **falha**. (Se uma execução for interrompida antes de
gravar os resultados, o lacre fica `em_andamento` e o número de tentativas interrompidas é registrado.)
Apagar o lacre à mão invalida a afirmação de "uso único" e **deve ser declarado** no relatório.

Tudo o que depende de 2024 é calculado **dentro de uma única função**, que carrega o modelo **do disco** (o
que foi congelado) e guarda só agregados. As seções 17 e 18 apenas apresentam o resultado.
'''))
CELULAS.append(cod(r'''
LACRE = OUT_DIR / "LACRE_TESTE_2024.json"


def abrir_lacre(sha):
    estado = {"tentativas_interrompidas": 0}
    if LACRE.exists():
        estado = json.loads(LACRE.read_text("utf-8"))
        if estado.get("status") == "concluido":
            raise RuntimeError(
                "R2 violada: o teste de 2024 já foi avaliado (lacre concluído em "
                f"{estado.get('concluido_em')}). Usar o teste mais de uma vez torna o resultado otimista. "
                "Apagar o lacre invalida a afirmação de uso único e deve ser declarado no relatório.")
        estado["tentativas_interrompidas"] = estado.get("tentativas_interrompidas", 0) + 1
    estado.update(status="em_andamento", iniciado_em=pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
                  sha256_modelo_congelado=sha)
    LACRE.write_text(json.dumps(estado, indent=2), "utf-8")
    return estado


def fechar_lacre(estado, sha_resultados):
    estado.update(status="concluido", concluido_em=pd.Timestamp.now("UTC").isoformat(timespec="seconds"),
                  sha256_resultados=sha_resultados)
    LACRE.write_text(json.dumps(estado, indent=2), "utf-8")


def _suprimir(df, col_n, minimo=CONFIG["MIN_CELULA"]):
    d = df.copy()
    d[col_n] = d[col_n].where(d[col_n] >= minimo, np.nan)
    return d


def avaliar_teste_uma_vez():
    B = CONFIG["BOOT"]
    sd = CONFIG["SEED"]
    b = joblib.load(caminho_bundle)
    assert sha256_file(caminho_bundle) == SHA_BUNDLE, "O modelo em disco não é o que foi congelado."
    garantir_dados([CONFIG["ANO_TESTE"]])
    raw24 = ler_ano(CONFIG["ANO_TESTE"])
    dominios24 = checar_dominios_alvo(raw24, CONFIG["ANO_TESTE"])  # check bloqueante também em 2024
    pop24 = montar_populacao(raw24, CONFIG["ANO_TESTE"])
    del raw24
    gc.collect()
    x24, y24 = montar_features(pop24), pop24["y"].to_numpy()
    assert_features_permitidas(list(x24.columns), FEATURES_M1)

    # --- predições do que foi congelado (nada é reajustado aqui)
    p_m1 = b["calibrador"].prever(b["m1"].prever(x24))
    p_b1 = b["b1"].prever(x24)
    p_b0 = np.full(len(y24), b["prevalencia_dev"])
    f_b2 = b2_flag(x24)
    flags = {"b2": f_b2, "m1_f2": p_m1 >= b["limiar_f2"], "m1_sens": p_m1 >= b["limiar_sens_b2"],
             "m1_frac": p_m1 >= b["limiar_frac_b2"], "b1_f2": p_b1 >= b["limiar_b1_f2"]}

    res = {"n": int(len(y24)), "eventos": int(y24.sum()), "prevalencia": float(y24.mean()),
           "dominios": dominios24}
    # --- métricas pontuais (exatas)
    scores = {"m1": p_m1, "b1": p_b1, "b0": p_b0}
    res["discriminacao"] = {k: {"pr_auc": pr_auc(y24, v), "roc_auc": roc_auc(y24, v), "brier": brier(y24, v)}
                            for k, v in scores.items()}
    res["calibracao"] = {"m1": calibracao_resumo(y24, p_m1), "b1": calibracao_resumo(y24, p_b1)}
    res["limiar"] = {k: metricas_limiar(y24, f) for k, f in flags.items()}
    res["limiar"]["b0"] = metricas_limiar(y24, np.zeros(len(y24), bool))

    # --- bootstrap pareado (mesmas reamostras para todos os modelos)
    tab = agregar(y24, scores, flags)
    bt = bootstrap_metricas(tab, B=B, seed=sd)
    ic = {k: ic95(v) for k, v in bt.items()}
    res["ic95"] = {k: list(v) for k, v in ic.items()}
    dif = {"PR-AUC M1 − B1": bt["pr_auc[m1]"] - bt["pr_auc[b1]"],
           "PR-AUC M1 − B0": bt["pr_auc[m1]"] - bt["pr_auc[b0]"],
           "ROC-AUC M1 − B1": bt["roc_auc[m1]"] - bt["roc_auc[b1]"],
           "Brier M1 − B1": bt["brier[m1]"] - bt["brier[b1]"],
           "F2-limiar: sensibilidade M1 − B2": bt["sensibilidade[m1_f2]"] - bt["sensibilidade[b2]"],
           "F2-limiar: VPP M1 − B2": bt["VPP[m1_f2]"] - bt["VPP[b2]"],
           "mesma sensibilidade: VPP M1 − B2": bt["VPP[m1_sens]"] - bt["VPP[b2]"],
           "mesma sensibilidade: especificidade M1 − B2": bt["especificidade[m1_sens]"] - bt["especificidade[b2]"],
           "mesma sensibilidade: % sinalizados M1 − B2": bt["pct_sinalizados[m1_sens]"] - bt["pct_sinalizados[b2]"],
           "mesma fração sinalizada: sensibilidade M1 − B2": bt["sensibilidade[m1_frac]"] - bt["sensibilidade[b2]"]}
    pont = {"PR-AUC M1 − B1": res["discriminacao"]["m1"]["pr_auc"] - res["discriminacao"]["b1"]["pr_auc"],
            "PR-AUC M1 − B0": res["discriminacao"]["m1"]["pr_auc"] - res["discriminacao"]["b0"]["pr_auc"],
            "ROC-AUC M1 − B1": res["discriminacao"]["m1"]["roc_auc"] - res["discriminacao"]["b1"]["roc_auc"],
            "Brier M1 − B1": res["discriminacao"]["m1"]["brier"] - res["discriminacao"]["b1"]["brier"],
            "F2-limiar: sensibilidade M1 − B2": res["limiar"]["m1_f2"]["sensibilidade"] - res["limiar"]["b2"]["sensibilidade"],
            "F2-limiar: VPP M1 − B2": res["limiar"]["m1_f2"]["VPP"] - res["limiar"]["b2"]["VPP"],
            "mesma sensibilidade: VPP M1 − B2": res["limiar"]["m1_sens"]["VPP"] - res["limiar"]["b2"]["VPP"],
            "mesma sensibilidade: especificidade M1 − B2": res["limiar"]["m1_sens"]["especificidade"] - res["limiar"]["b2"]["especificidade"],
            "mesma sensibilidade: % sinalizados M1 − B2": res["limiar"]["m1_sens"]["pct_sinalizados"] - res["limiar"]["b2"]["pct_sinalizados"],
            "mesma fração sinalizada: sensibilidade M1 − B2": res["limiar"]["m1_frac"]["sensibilidade"] - res["limiar"]["b2"]["sensibilidade"]}
    res["diferencas"] = {k: {"estimativa": float(pont[k]), "ic95_inf": ic95(v)[0], "ic95_sup": ic95(v)[1]}
                         for k, v in dif.items()}
    res["nri"] = {}
    for rot, col in (("M1 no limiar F2", "f_m1_f2"), ("M1 com a sensibilidade de B2", "f_m1_sens"),
                     ("M1 com a fração sinalizada de B2", "f_m1_frac")):
        p0, am = nri_bootstrap(tab, col, "f_b2", B=B, seed=sd)
        res["nri"][rot] = {"NRI": p0, "ic95_inf": ic95(am)[0], "ic95_sup": ic95(am)[1]}

    # --- reclassificação B2 × M1 (contagens; células < 10 suprimidas)
    cr = pd.DataFrame({"y": y24, "B2": f_b2, "M1": flags["m1_f2"]}).groupby(["y", "B2", "M1"]).size().rename("n").reset_index()
    res["reclassificacao"] = _suprimir(cr, "n").to_dict("records")

    # --- subgrupos (D-13, D-48): PR-AUC com IC, recall no limiar F2 de M1 e de B2
    raca = code(pop24["CS_RACA"]).fillna("branco").map(
        {"1": "branca", "2": "preta", "3": "amarela", "4": "parda", "5": "indígena", "9": "ignorada"}).fillna("outra/branco")
    grupos = [("faixa etária", pop24["faixa_etaria"].astype("string")), ("sexo", x24["sexo"].astype("string")),
              ("gestante", pop24["gestante"].map({True: "sim", False: "não"})), ("região", pop24["regiao"].astype("string")),
              ("raça/cor", raca)]
    sub = []
    for gnome, serie in grupos:
        for cat in sorted(serie.dropna().unique(), key=str):
            m = (serie == cat).to_numpy()
            ev = int(y24[m].sum())
            if m.sum() < CONFIG["MIN_CELULA"] or ev < 2:
                sub.append({"grupo": gnome, "categoria": cat, "casos": int(m.sum()), "eventos": ev if ev >= CONFIG["MIN_CELULA"] else np.nan,
                            "aviso": "poucos eventos: sem métricas"})
                continue
            tab_s = agregar(y24[m], {"m1": p_m1[m]})
            bt_s = bootstrap_metricas(tab_s, B=CONFIG["BOOT_SUBGRUPO"], seed=sd)
            lo, hi = ic95(bt_s["pr_auc[m1]"])
            fl = flags["m1_f2"][m]
            linha = {"grupo": gnome, "categoria": cat, "casos": int(m.sum()), "eventos": ev if ev >= CONFIG["MIN_CELULA"] else np.nan,
                     "prevalência_%": 100 * y24[m].mean(), "PR-AUC M1": pr_auc(y24[m], p_m1[m]),
                     "ic95_inf": lo, "ic95_sup": hi, "recall M1 (F2)": float((fl & (y24[m] == 1)).sum() / ev),
                     "recall B2": float((f_b2[m] & (y24[m] == 1)).sum() / ev)}
            if ev >= CONFIG["MIN_EVENTOS_SUBGRUPO"]:
                linha["slope M1"] = calibracao_resumo(y24[m], p_m1[m])["slope"]
            else:
                linha["aviso"] = "< 100 eventos: IC largo, sem conclusões"
            sub.append(linha)
    res["subgrupos"] = sub

    # --- utilidade clínica (curva de decisão) e calibração
    lims = np.linspace(*CONFIG["DCA_LIMIARES"][:2], CONFIG["DCA_LIMIARES"][2])
    res["dca"] = {"limiar": lims.tolist(), "M1": curva_decisao(y24, p=p_m1, limiares=lims)["net_benefit"].tolist(),
                  "B1": curva_decisao(y24, p=p_b1, limiares=lims)["net_benefit"].tolist(),
                  "B2": curva_decisao(y24, flag=f_b2, limiares=lims)["net_benefit"].tolist(),
                  "todos": net_benefit_todos(float(y24.mean()), lims).tolist()}
    pf = {}
    for rot, f in (("M1 F2", flags["m1_f2"]),):
        pf[rot] = float(metricas_limiar(y24, f)["sensibilidade"])
    res["calibracao_curva"] = {k: curva_calibracao(y24, v).to_dict("list") for k, v in (("M1", p_m1), ("B1", p_b1))}
    res["pr_curva_pontos"] = {"M1": [res["limiar"]["m1_f2"]["sensibilidade"], res["limiar"]["m1_f2"]["VPP"]],
                              "B2": [res["limiar"]["b2"]["sensibilidade"], res["limiar"]["b2"]["VPP"]]}

    # --- E1 em 2024: checagem de calibração (casos completos)
    ok24 = completos_para_e1(pop24, x24).to_numpy()
    d24 = pd.DataFrame({"idade": x24["idade_anos"].round(2), "sexo_M": (x24["sexo"] == "M").astype(int),
                        "gestante": x24["gestante"].astype(int),
                        **{c: (x24[c] == "Sim").astype(int) for c in COMORBIDADES}})[ok24]
    p_e1 = prever_e1(m_e1, d24)
    res["e1_2024"] = {"casos": int(ok24.sum()), "calibracao": calibracao_resumo(y24[ok24], p_e1),
                      "pr_auc": pr_auc(y24[ok24], p_e1), "roc_auc": roc_auc(y24[ok24], p_e1),
                      "curva": curva_calibracao(y24[ok24], p_e1).to_dict("list")}

    # --- análise de erros (agregada): falsos negativos × verdadeiros positivos no limiar F2
    fn = (~flags["m1_f2"]) & (y24 == 1)
    tp_ = flags["m1_f2"] & (y24 == 1)
    n_com = x24["n_comorbidades"].clip(upper=3).astype(int).astype(str).replace({"3": "3+"})
    ordem_fn = np.flatnonzero(fn)[np.argsort(p_m1[fn])[:100]]  # os 100 FN de menor risco previsto
    mask100 = np.zeros(len(y24), bool)
    mask100[ordem_fn] = True
    erros = []
    for rot, serie in (("faixa etária", pop24["faixa_etaria"].astype("string")), ("nº de comorbidades", n_com.astype("string")),
                       ("região", pop24["regiao"].astype("string"))):
        for cat in sorted(serie.dropna().unique(), key=str):
            m = (serie == cat).to_numpy()
            erros.append({"variável": rot, "categoria": cat, "FN": int((fn & m).sum()), "VP": int((tp_ & m).sum()),
                          "100 FN de menor risco previsto": int((mask100 & m).sum())})
    res["erros"] = _suprimir(_suprimir(_suprimir(pd.DataFrame(erros), "FN"), "VP"), "100 FN de menor risco previsto").to_dict("records")
    res["erros_resumo"] = {"FN": int(fn.sum()), "VP": int(tp_.sum()),
                           "atraso_mediano_FN": float(np.nanmedian(x24.loc[fn, "dias_ate_notificacao"])) if fn.any() else np.nan,
                           "atraso_mediano_VP": float(np.nanmedian(x24.loc[tp_, "dias_ate_notificacao"])) if tp_.any() else np.nan}
    res["conferencia_profiling_2024"] = {"casos_esperado": 5_331_745, "casos_obtido": res["n"],
                                         "eventos_esperado": 11_338, "eventos_obtido": res["eventos"]}
    return res
'''))
CELULAS.append(cod(r'''
estado_lacre = abrir_lacre(SHA_BUNDLE)
TESTE = avaliar_teste_uma_vez()          # se falhar aqui, o lacre fica 'em_andamento' (não 'concluido')
arq_res = OUT_DIR / "tabelas" / "teste_2024_resultados.json"
arq_res.write_text(json.dumps(TESTE, indent=2, ensure_ascii=False, default=float), "utf-8")
fechar_lacre(estado_lacre, sha256_file(arq_res))
RESULTADOS["teste"] = {k: TESTE[k] for k in ("n", "eventos", "prevalencia", "discriminacao", "calibracao")}
print("Avaliação do teste de 2024 CONCLUÍDA e lacrada. Resultados nas seções 17 e 18.")
print("Lacre:", LACRE.name, "→", json.loads(LACRE.read_text("utf-8"))["status"])
'''))

# ============================================================================ 17. Comparação MS
CELULAS.append(md(r'''
## 17. Comparação com a estratificação do Ministério da Saúde

**B2** = "alto risco" se o caso cumprir **qualquer** critério do grupo B do protocolo do MS (6ª ed., 2024)
que exista na ficha `[ASSUMPTION]`: idade < 24 meses ou > 65 anos; gestante; ≥ 1 das 7 comorbidades;
prova do laço positiva ou petéquias. **Não cobre** DPOC, asma, obesidade, outras cardiopatias nem risco
social (não existem na ficha): a regra real é mais ampla que a avaliada aqui. É uma regra **binária**, então
a comparação é no **limiar** (sensibilidade, especificidade, VPP, VPN, % sinalizados), não em AUC.

Comparamos nos **mesmos pacientes e desfechos**, em duas condições: (i) desenvolvimento, fora da dobra
(seção 15, com limiares só do desenvolvimento); (ii) **teste 2024**, com limiares **congelados**. M1 é
avaliado em três pontos de operação: o limiar do F2, a **mesma sensibilidade** de B2 e a **mesma fração
sinalizada** de B2 (limiares derivados só do desenvolvimento).
'''))
CELULAS.append(cod(r'''
def ic_txt(chave, fmt="{:.3f}"):
    lo, hi = TESTE["ic95"][chave]
    return f"[{fmt.format(lo)}–{fmt.format(hi)}]"


rotulos = {"b0": "B0 (ninguém)", "b2": "B2 — regra do MS", "b1_f2": "B1 no limiar F2", "m1_f2": "M1 no limiar F2",
           "m1_sens": "M1 com a sensibilidade de B2 (dev)", "m1_frac": "M1 com a fração sinalizada de B2 (dev)"}
linhas = []
for k, rot in rotulos.items():
    m = TESTE["limiar"][k]
    linha = {"classificador": rot, "TP": m["TP"], "FP": m["FP"], "FN": m["FN"], "TN": m["TN"]}
    for met, chave in (("sensibilidade", "sensibilidade"), ("especificidade", "especificidade"), ("VPP", "VPP"),
                       ("VPN", "VPN"), ("% sinalizados", "pct_sinalizados")):
        linha[met] = m[chave]
        if f"{chave}[{k}]" in TESTE["ic95"]:
            linha[f"{met} IC95%"] = ic_txt(f"{chave}[{k}]", "{:.4f}")
    linha["F2"] = m["F2"]
    linhas.append(linha)
comp_ms = pd.DataFrame(linhas)
print(f"Teste 2024: {TESTE['n']:,} casos, {TESTE['eventos']:,} eventos ({100 * TESTE['prevalencia']:.3f}%). "
      "Limiares congelados no desenvolvimento.")
display(comp_ms.round(4))
salvar_tabela(comp_ms, "comparacao_ms_teste")

print("\nMesmos pacientes, desenvolvimento (fora da dobra) — para comparar com o teste:")
display(lim_dev.round(4))
'''))
CELULAS.append(cod(r'''
fig, eixos = plt.subplots(1, 3, figsize=(15, 4.2))
d = TESTE["dca"]
eixos[0].plot(d["limiar"], d["M1"], label="M1"); eixos[0].plot(d["limiar"], d["B1"], label="B1")
eixos[0].plot(d["limiar"], d["B2"], label="B2 — regra do MS"); eixos[0].plot(d["limiar"], d["todos"], "k:", label="tratar todos")
eixos[0].axhline(0, color="grey", label="tratar ninguém")
eixos[0].set_xlabel("limiar de risco"); eixos[0].set_ylabel("benefício líquido")
eixos[0].set_title("Curva de decisão — teste 2024"); eixos[0].legend(fontsize=7)

for k, rot in (("M1", "M1"), ("B1", "B1")):
    cc = pd.DataFrame(TESTE["calibracao_curva"][k])
    eixos[1].errorbar(cc["p_medio"], cc["taxa_observada"],
                      yerr=[cc["taxa_observada"] - cc["ic95_inf"], cc["ic95_sup"] - cc["taxa_observada"]],
                      marker="o", capsize=2, label=rot)
lim = max(cc["p_medio"].max(), cc["taxa_observada"].max()) * 1.1
eixos[1].plot([0, lim], [0, lim], "k--", lw=1)
eixos[1].set_xscale("symlog", linthresh=1e-3); eixos[1].set_yscale("symlog", linthresh=1e-3)
eixos[1].set_xlabel("risco previsto médio (decil)"); eixos[1].set_ylabel("taxa observada")
eixos[1].set_title("Calibração — teste 2024 (decis)"); eixos[1].legend(fontsize=7)

ce = pd.DataFrame(TESTE["e1_2024"]["curva"])
eixos[2].errorbar(ce["p_medio"], ce["taxa_observada"],
                  yerr=[ce["taxa_observada"] - ce["ic95_inf"], ce["ic95_sup"] - ce["taxa_observada"]],
                  marker="o", capsize=2, color="#8c2d04")
lim = max(ce["p_medio"].max(), ce["taxa_observada"].max()) * 1.1
eixos[2].plot([0, lim], [0, lim], "k--", lw=1)
eixos[2].set_xscale("symlog", linthresh=1e-3); eixos[2].set_yscale("symlog", linthresh=1e-3)
eixos[2].set_title("E1 (só perfil) — calibração em 2024"); eixos[2].set_xlabel("risco previsto"); eixos[2].set_ylabel("observado")
salvar_figura(fig, "teste_dca_calibracao")

disc = pd.DataFrame(TESTE["discriminacao"]).T.rename_axis("modelo").reset_index()
for k in ("pr_auc", "roc_auc", "brier"):
    disc[f"{k} IC95%"] = [ic_txt(f"{k}[{m}]", "{:.4f}") for m in disc["modelo"]]
cal = pd.DataFrame(TESTE["calibracao"]).T.rename_axis("modelo").reset_index()
print("Discriminação e calibração — teste 2024 (IC 95% por bootstrap estratificado):")
display(disc)
display(cal)
e1 = TESTE["e1_2024"]
print(f"E1 em 2024 ({e1['casos']:,} casos completos): slope {e1['calibracao']['slope']:.3f}, "
      f"intercepto {e1['calibracao']['intercepto_citl']:.3f}, O:E {e1['calibracao']['O:E']:.3f}, "
      f"ROC-AUC {e1['roc_auc']:.3f}")
salvar_tabela(disc, "teste_discriminacao"); salvar_tabela(cal, "teste_calibracao")

sub = pd.DataFrame(TESTE["subgrupos"])
print("\nSubgrupos no teste (idade, sexo, gestação, região, raça/cor). Aviso = poucos eventos → IC largo:")
display(sub.round(4))
salvar_tabela(sub, "teste_subgrupos")
'''))

# ============================================================================ 18. Valor incremental
CELULAS.append(md(r'''
## 18. Avaliação do valor incremental

Pergunta: **o ML acrescenta algo** além (a) de um modelo simples de perfil (B1) e (b) da regra do MS (B2)?

- **vs B1:** diferença **pareada** de PR-AUC/ROC-AUC/Brier (mesmas reamostras; IC 95% bootstrap).
- **vs B2:** diferenças de VPP, especificidade e % sinalizados **na mesma sensibilidade**, e de sensibilidade na
  **mesma fração sinalizada**; **NRI categórico** (quanto M1 reclassifica corretamente pacientes que B2 classifica).
- **Utilidade clínica:** curva de decisão (benefício líquido).
- **Critérios de sucesso do spec (SC-01 a SC-04, `[ASSUMPTION]`):** abaixo, em tabela. Resultado
  negativo (M1 não supera B1/B2) é **resultado válido** e é reportado como tal.
'''))
CELULAS.append(cod(r'''
dif = pd.DataFrame(TESTE["diferencas"]).T.rename_axis("contraste").reset_index()
dif["IC95% exclui 0?"] = np.where((dif["ic95_inf"] > 0) | (dif["ic95_sup"] < 0), "sim", "não")
print("Diferenças pareadas no teste 2024 (M1 − comparador):")
display(dif.round(4))
salvar_tabela(dif, "teste_diferencas_pareadas")

nri = pd.DataFrame(TESTE["nri"]).T.rename_axis("M1 versus B2").reset_index()
print("NRI categórico (M1 como modelo novo, B2 como regra antiga); > 0 = reclassificação líquida a favor de M1:")
display(nri.round(4))
salvar_tabela(nri, "teste_nri")

rc = pd.DataFrame(TESTE["reclassificacao"])
rc["B2"] = rc["B2"].map({True: "alto risco", False: "baixo risco"})
rc["M1 (F2)"] = rc.pop("M1").map({True: "alto risco", False: "baixo risco"})
rc["desfecho"] = rc.pop("y").map({1: "evento (grave/óbito)", 0: "sem evento"})
print("Reclassificação B2 × M1 (contagens; células < 10 suprimidas):")
display(rc[["desfecho", "B2", "M1 (F2)", "n"]])
salvar_tabela(rc[["desfecho", "B2", "M1 (F2)", "n"]], "teste_reclassificacao")

# Critérios de sucesso (spec; [ASSUMPTION]) — avaliados, não impostos
d = TESTE["diferencas"]
m1, b2 = TESTE["limiar"]["m1_f2"], TESTE["limiar"]["b2"]
sc = pd.DataFrame([
    {"critério": "SC-01: PR-AUC de M1 > B0, IC95% da diferença sem 0",
     "resultado": f"Δ = {d['PR-AUC M1 − B0']['estimativa']:.4f} "
                  f"[{d['PR-AUC M1 − B0']['ic95_inf']:.4f}; {d['PR-AUC M1 − B0']['ic95_sup']:.4f}]",
     "atendido": bool(d["PR-AUC M1 − B0"]["ic95_inf"] > 0)},
    {"critério": "SC-02: no limiar F2, recall de M1 ≥ recall de B2 com precisão maior",
     "resultado": f"recall {m1['sensibilidade']:.3f} vs {b2['sensibilidade']:.3f}; "
                  f"precisão {m1['VPP']:.4f} vs {b2['VPP']:.4f}",
     "atendido": bool(m1["sensibilidade"] >= b2["sensibilidade"] and m1["VPP"] > b2["VPP"])},
    {"critério": "SC-03: calibration slope de M1 entre 0,8 e 1,2",
     "resultado": f"slope = {TESTE['calibracao']['m1']['slope']:.3f}",
     "atendido": bool(0.8 <= TESTE["calibracao"]["m1"]["slope"] <= 1.2)},
    {"critério": "SC-04: ΔPR-AUC (M1 − B1) reportada com IC (qualquer sinal)",
     "resultado": f"Δ = {d['PR-AUC M1 − B1']['estimativa']:.4f} "
                  f"[{d['PR-AUC M1 − B1']['ic95_inf']:.4f}; {d['PR-AUC M1 − B1']['ic95_sup']:.4f}]",
     "atendido": True}])
display(sc)
salvar_tabela(sc, "teste_criterios_sucesso")
RESULTADOS["criterios_sucesso"] = sc.to_dict("records")
'''))

# ============================================================================ 19. Discussão
CELULAS.append(md(r'''
## 19. Discussão, limitações e conclusões

A célula seguinte **gera o resumo a partir dos números efetivamente calculados** nesta execução (nada é
escrito de memória). O texto interpretativo é condicional ao que os ICs permitem afirmar.
'''))
CELULAS.append(cod(r'''
d = TESTE["diferencas"]
dis = TESTE["discriminacao"]
linhas = [
    f"**População:** desenvolvimento {RESULTADOS['populacao_dev']['casos']:,} casos "
    f"({RESULTADOS['populacao_dev']['eventos']:,} eventos, {100 * RESULTADOS['populacao_dev']['prevalencia']:.2f}%); "
    f"teste 2024 {TESTE['n']:,} casos ({TESTE['eventos']:,} eventos, {100 * TESTE['prevalencia']:.2f}%).",
    f"**Modelo M1 selecionado no desenvolvimento:** {SELECIONADO} ({MOTIVO}); calibração {cal_tipo[SELECIONADO]}.",
    f"**Teste 2024 — PR-AUC:** M1 {dis['m1']['pr_auc']:.4f} {ic_txt('pr_auc[m1]', '{:.4f}')}, "
    f"B1 {dis['b1']['pr_auc']:.4f}, B0 {dis['b0']['pr_auc']:.4f} (= prevalência). "
    f"ΔPR-AUC M1 − B1 = {d['PR-AUC M1 − B1']['estimativa']:.4f} "
    f"[{d['PR-AUC M1 − B1']['ic95_inf']:.4f}; {d['PR-AUC M1 − B1']['ic95_sup']:.4f}].",
]
if d["PR-AUC M1 − B1"]["ic95_inf"] > 0:
    linhas.append("→ O IC da diferença **exclui 0 a favor de M1**: há evidência de ganho de discriminação sobre a logística de perfil.")
elif d["PR-AUC M1 − B1"]["ic95_sup"] < 0:
    linhas.append("→ O IC da diferença **exclui 0 a favor de B1**: M1 foi pior que a logística simples (resultado válido).")
else:
    linhas.append("→ O IC da diferença **inclui 0**: não há evidência de que M1 supere a logística simples de perfil.")
s_m1, s_b2 = TESTE["limiar"]["m1_f2"], TESTE["limiar"]["b2"]
linhas.append(f"**M1 (limiar F2) × regra do MS (B2):** sensibilidade {s_m1['sensibilidade']:.3f} × {s_b2['sensibilidade']:.3f}; "
              f"VPP {s_m1['VPP']:.4f} × {s_b2['VPP']:.4f}; % sinalizados {100 * s_m1['pct_sinalizados']:.1f}% × "
              f"{100 * s_b2['pct_sinalizados']:.1f}%.")
dv = d["mesma sensibilidade: % sinalizados M1 − B2"]
linhas.append(f"**Na mesma sensibilidade de B2**, M1 sinaliza {100 * dv['estimativa']:+.1f} p.p. de pacientes "
              f"(IC95% {100 * dv['ic95_inf']:+.1f} a {100 * dv['ic95_sup']:+.1f}); negativo = menos pacientes para a mesma captura.")
linhas.append(f"**Calibração em 2024:** slope de M1 = {TESTE['calibracao']['m1']['slope']:.2f}, "
              f"O:E = {TESTE['calibracao']['m1']['O:E']:.2f} (ideal 1); a diferença de prevalência entre desenvolvimento e "
              "teste é um indício de deriva temporal.")
print("\n".join("- " + l for l in linhas))
RESULTADOS["resumo_texto"] = linhas
'''))
CELULAS.append(md(r'''
### Limitações (a serem discutidas no relatório)

- **Notificação e subnotificação:** o SINAN registra casos notificados/confirmados; casos leves são subnotificados e
  a notificação varia por UF e ano. O Espírito Santo usa outro sistema desde 2020 (provável sub-representação).
- **Rótulo:** `CLASSI_FIN` e `EVOLUCAO` vêm do encerramento pela vigilância (critério clínico-epidemiológico,
  variação de qualidade entre UFs). Óbitos são investigados, o que pode deixar suas fichas mais completas; o check de
  completude (seção 7) não mostrou vazamento por "Ausente", mas **outros** vieses de investigação são possíveis.
- **Alvo estrito:** "grave ou óbito pelo agravo" é mais estrito que o "casos graves" do MS (alarme + grave) e que o
  alvo do pré-projeto (hospitalização/alarme), por ser circular com a conduta (hospitalização) e intermediário (alarme).
- **Comorbidades só as 7 da ficha:** asma, DPOC, obesidade e outras cardiopatias (citadas no protocolo) **não existem**
  na ficha; "Não" pode significar "não investigado". `LEUCOPENIA` "Não" pode significar "hemograma não feito".
- **Duplicidades:** sem identificador pessoal, a chave composta marca 17–42% como duplicada (implausível); não removemos
  e testamos sensibilidade com chave estrita. Notificações duplicadas podem cair em treino e validação.
- **Região e tempo:** poucos eventos no Norte (dobra e subgrupo); 2024 foi um ano epidêmico com prevalência maior que
  2022–23 (deriva); a regra B2 é uma **aproximação** do protocolo (só critérios disponíveis na ficha).
- **Associação ≠ causalidade;** OR são ajustados só por idade, sexo e gestação (confundimento residual: condição
  socioeconômica, acesso, sorotipo, hábitos de busca por atendimento). OR ≈ RR só porque o desfecho é raro.
- **Pendências do spec:** CatBoost, MLP e TabFM não foram treinados; a grade de hiperparâmetros é uma **proposta
  (Q-08)**; não há MLflow/Optuna; revisão por profissional de saúde (FR-21) ainda não feita; ICs de calibração
  de subgrupos pequenos são largos.
- **Uso:** o modelo **não substitui** avaliação clínica nem protocolos; não é ferramenta clínica validada.
'''))
CELULAS.append(cod(r'''
# Exportação final: só agregados (R7). Manifesto da execução para reprodutibilidade (NFR-02).
RESULTADOS["ambiente"] = AMBIENTE
RESULTADOS["commit_git"] = COMMIT
RESULTADOS["sha256_modelo_congelado"] = SHA_BUNDLE
RESULTADOS["seed"] = CONFIG["SEED"]
RESULTADOS["fumaca"] = SMOKE
(OUT_DIR / "resultados.json").write_text(json.dumps(RESULTADOS, indent=2, ensure_ascii=False, default=float), "utf-8")
print("Arquivos exportados em", OUT_DIR)
for pasta in ("tabelas", "figuras", "artefatos"):
    print(f"  {pasta}/: {len(list((OUT_DIR / pasta).glob('*')))} arquivos")
if SMOKE:
    print("\n*** EXECUÇÃO DE FUMAÇA: números sem valor científico se os dados forem sintéticos. ***")
'''))

# ============================================================================ gravação
def main() -> None:
    nb = {"cells": CELULAS, "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python"}}, "nbformat": 4, "nbformat_minor": 5}
    for i, c in enumerate(nb["cells"]):
        c["id"] = f"c{i:03d}"
    SAIDA.write_text(json.dumps(nb, ensure_ascii=False, indent=1) + "\n", "utf-8")
    print(f"{SAIDA.relative_to(RAIZ)}: {len(CELULAS)} células")


if __name__ == "__main__":
    main()
