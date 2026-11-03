"""Gera profiling/01_profiling.ipynb a partir do código testado em src/dengue_sinan.

O notebook precisa ser autocontido para rodar no Colab sem clonar o repositório. Em vez de
duplicar código à mão, este script copia os módulos de src/ para células. Regere sempre que
src/ mudar:

    uv run python profiling/build_notebook.py
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "dengue_sinan"
OUT = ROOT / "profiling" / "01_profiling.ipynb"


def module_source(name: str) -> str:
    """Código do módulo sem os imports internos do pacote (no notebook tudo é global)."""
    lines = (SRC / f"{name}.py").read_text("utf-8").splitlines()
    kept = [line for line in lines if not line.startswith("from dengue_sinan")]
    return f"# Copiado de src/dengue_sinan/{name}.py — não edite aqui; edite o módulo e regere.\n" \
        + "\n".join(kept)


def md(text: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": text.strip("\n")}


def code(text: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": text.strip("\n")}


CELLS = [
    md("""
# Profiling — SINAN Dengue 2022–2024

Executa o [roteiro de profiling](ROTEIRO.md) e gera `profiling/RESULTADOS.md` preenchido.

**No Colab:** *Ambiente de execução → Executar tudo*. O notebook monta o Google Drive e grava
tudo em `MyDrive/dengue-comorbidity-risk/` (dados, manifesto e `profiling/RESULTADOS.md`).
Na primeira execução, o download e a conversão de 2024 levam alguns minutos; nas seguintes,
os Parquets são reaproveitados se o arquivo do DataSUS não mudou.

**Local:** `uv run jupyter nbconvert --to notebook --execute --inplace profiling/01_profiling.ipynb`

Fonte: FTP oficial do DataSUS (D-05). Nenhum microdado sai do Drive/disco local; o
`RESULTADOS.md` só tem contagens agregadas.
"""),
    code("""
import subprocess
import sys
from pathlib import Path

IN_COLAB = "google.colab" in sys.modules
if IN_COLAB:
    # Mesmas versões do uv.lock (D-16).
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                           "pyreaddbc==2.0.4", "dbfread==2.0.7"])
    from google.colab import drive

    drive.mount("/content/drive")
    BASE = Path("/content/drive/MyDrive/dengue-comorbidity-risk")
else:
    BASE = Path.cwd().parent if Path.cwd().name == "profiling" else Path.cwd()

DATA_DIR = BASE / "data"
OUT_MD = BASE / "profiling" / "RESULTADOS.md"
ANOS = [2022, 2023, 2024]
DATA_DIR.mkdir(parents=True, exist_ok=True)
OUT_MD.parent.mkdir(parents=True, exist_ok=True)
print("Base:", BASE)
"""),
    md("## Código (copiado de `src/dengue_sinan`)"),
    code(module_source("features")),
    code(module_source("download")),
    code(module_source("profiling")),
    md("""
## Passo 0 — Download, conversão e manifesto

Baixa `DENGBR{AA}.dbc` de `FINAIS` (ou `PRELIM`, se não houver final), registra hash do `.dbc`,
data de revisão no DataSUS, hash do Parquet, linhas e versões em `data/manifest.json`.
"""),
    code("""
import json
import time

import pandas as pd
import pyarrow.parquet as pq

SECOES: dict[str, str] = {}   # seção do RESULTADOS.md → Markdown
RESUMO: dict[str, dict] = {}  # linha da tabela-resumo → {resultado, esperado, obs}

manifest = {}
for ano in ANOS:
    t0 = time.time()
    entry = fetch_year(ano, DATA_DIR)
    manifest[ano] = entry
    print(f"{ano}: {entry['linhas']:,} linhas, {entry['colunas']} colunas, "
          f"{entry['status_datasus']}, revisão {entry['revisao_datasus_utc'][:10]} "
          f"({time.time() - t0:.0f} s)")

manifest_table = pd.DataFrame({
    ano: {
        "arquivo": e["arquivo"],
        "status no DataSUS": e["status_datasus"],
        "revisão no DataSUS (UTC)": e["revisao_datasus_utc"][:19],
        "baixado em (UTC)": e["baixado_em_utc"][:19],
        "linhas": e["linhas"],
        "linhas no cabeçalho DBF": e["linhas_no_cabecalho_dbf"],
        "colunas": e["colunas"],
        "SHA-256 .dbc": e["sha256_dbc"][:16] + "…",
        "SHA-256 Parquet": e["sha256_parquet"][:16] + "…",
    } for ano, e in manifest.items()
})
env = next(iter(manifest.values()))["ambiente"]
SECOES["0. Manifesto dos dados"] = (
    markdown_table(manifest_table) + "\\n\\nHashes completos em `data/manifest.json`. Ambiente: "
    + ", ".join(f"{k} {v}" for k, v in env.items()) + "."
)
cols_by_year = {ano: set(e["nomes_colunas"]) for ano, e in manifest.items()}
common = set.intersection(*cols_by_year.values())
only = {ano: sorted(c - common) for ano, c in cols_by_year.items() if c - common}
SECOES["0. Manifesto dos dados"] += (
    f"\\n\\nColunas em comum nos {len(ANOS)} anos: {len(common)}. "
    + ("Colunas exclusivas: " + "; ".join(f"{a}: {', '.join(c)}" for a, c in only.items())
       if only else "Mesmo schema em todos os anos.")
)
RESUMO["0"] = {
    "item": "Hash, data e versão de cada Parquet", "secao": "§3.14",
    "resultado": "; ".join(f"{a}: {e['linhas']:,} linhas, {e['status_datasus']}"
                           for a, e in manifest.items()),
    "esperado": "sim" if all(e["linhas"] == e["linhas_no_cabecalho_dbf"]
                             for e in manifest.values()) else "revisar",
    "obs": "Linhas lidas = cabeçalho do DBF." if all(
        e["linhas"] == e["linhas_no_cabecalho_dbf"] for e in manifest.values())
        else "Linhas lidas ≠ cabeçalho do DBF (registros apagados?).",
}
manifest_table
"""),
    md("""
## Carga das colunas usadas

Só as colunas do roteiro, como `category`, para caber na RAM. `ALRM_*` e `GRAV_*` viram uma
flag "algum campo preenchido" já na carga (passo 7 e contingência do passo 1).
"""),
    code("""
import numpy as np

BASE_COLS = (CAMPOS_ALVO + COMORBIDADES + SINAIS
             + ["NU_IDADE_N", "ANO_NASC", "CS_SEXO", "CS_GESTANT", "CS_RACA", "CS_ESCOL_N",
                "SG_UF", "ID_MN_RESI", "SG_UF_NOT", "DT_NOTIFIC", "DT_SIN_PRI",
                "NDUPLIC_N", "TP_SISTEMA"])
# DT_NASC não é publicada nos microdados (anonimização); só ANO_NASC. Colunas ausentes
# aparecem em "Faltando" e as funções tratam como branco.
faltando = {}
partes = []
for ano in ANOS:
    path = DATA_DIR / manifest[ano]["parquet"]
    schema = pq.read_schema(path).names
    alarm = [c for c in schema if c.startswith("ALRM_")]
    grav = [c for c in schema if c.startswith("GRAV_")]
    usar = [c for c in BASE_COLS if c in schema]
    faltando[ano] = [c for c in BASE_COLS if c not in schema]
    tabela = pq.read_table(path, columns=usar + alarm + grav)
    parte = tabela.select(usar).to_pandas(strings_to_categorical=True)
    flags = tabela.select(alarm + grav).to_pandas()
    parte["ALRM_ANY"] = np.where(flags[alarm].notna().any(axis=1), "1", None) if alarm else None
    parte["GRAV_ANY"] = np.where(flags[grav].notna().any(axis=1), "1", None) if grav else None
    parte["ANO"] = ano
    partes.append(parte)
    del tabela, flags
    print(ano, "ALRM_*:", alarm)
    print(ano, "GRAV_*:", grav)

df = pd.concat(partes, ignore_index=True)
for col in df.columns:
    if df[col].dtype == object:
        df[col] = df[col].astype("category")
del partes
print("Faltando:", {a: c for a, c in faltando.items() if c} or "nenhuma")
print(f"{len(df):,} linhas carregadas")
"""),
    md("## Passo 1 — Códigos do alvo (BLOQUEANTE)"),
    code("""
partes_md = []
for campo in CAMPOS_ALVO:
    t = counts_by_year(df, campo)
    partes_md.append(f"**{campo}**\\n\\n" + markdown_table(t))
    display(t)
SECOES["1. Códigos do alvo"] = "\\n\\n".join(partes_md)

classi_vals = set(code(df["CLASSI_FIN"]).dropna().unique())
tem_novo = {"10", "11", "12"} <= classi_vals
# 1 = confirmado e 2 = descartado só existem no esquema de 2024; 8 = inconclusivo aparece junto
# com 10/11/12 nos arquivos reais (profiling de 2026-11-03), então não indica troca de esquema.
tem_esquema_2024 = bool({"1", "2"} & classi_vals)
por_ano = {ano: sorted(set(code(df.loc[df.ANO == ano, "CLASSI_FIN"]).dropna().unique()))
           for ano in ANOS}
BLOQUEIO = (not tem_novo) or tem_esquema_2024
RESUMO["1"] = {
    "item": "Valores de CLASSI_FIN/EVOLUCAO/CRITERIO por ano", "secao": "§3.6",
    "resultado": "; ".join(f"{a}: CLASSI_FIN ∈ {{{', '.join(v)}}}" for a, v in por_ano.items()),
    "esperado": "não — PARAR" if BLOQUEIO else "sim",
    "obs": ("Apareceram códigos 1/2 ou faltam 10/11/12: D-02 precisa ser redecidido."
            if BLOQUEIO else "10/11/12 presentes e 1/2 ausentes; D-02 vale."),
}
print("BLOQUEIO" if BLOQUEIO else "OK — 10/11/12 presentes", por_ano)

grav_by_class = alarm_filled_by_class(df, ["GRAV_ANY"]).rename(
    columns={"com algum ALRM_* preenchido": "com algum GRAV_* preenchido"})
SECOES["1. Códigos do alvo"] += (
    "\\n\\n**Contingência: algum `GRAV_*` preenchido, por `CLASSI_FIN`** (todos os anos)\\n\\n"
    + markdown_table(grav_by_class))
grav_by_class
"""),
    md("## Passo 2 — Fluxograma de exclusão (FR-02)"),
    code("""
flow = exclusion_flow(df)
reasons = exclusion_reasons(df)
SECOES["2. Fluxograma de exclusão"] = markdown_table(flow) + "".join(
    f"\\n\\n**{nome}**\\n\\n" + markdown_table(t) for nome, t in reasons.items())
final = flow.iloc[-1]
RESUMO["2"] = {
    "item": "Fluxograma de exclusão", "secao": "§3.6, FR-02",
    "resultado": "; ".join(f"{a}: {flow.loc[flow.index[0], a]:,} → {final[a]:,}" for a in ANOS),
    "esperado": "revisar", "obs": "Conferir motivos de saída no detalhe.",
}
display(flow)
for nome, t in reasons.items():
    print(nome); display(t)
"""),
    md("## Passo 3 — Prevalência e número de eventos"),
    code("""
pop = add_derived(df[population_mask(df)])
prev = prevalence_by_year(pop)
dev, test = pop[pop.ANO.isin([2022, 2023])], pop[pop.ANO == 2024]
por_regiao_dev = events_by(dev, "regiao")
sub_2024 = {
    "faixa etária": events_by(test, "faixa_etaria"),
    "sexo": events_by(test.assign(sexo=code(test["CS_SEXO"])), "sexo"),
    "gestante (1–4)": events_by(test, "gestante"),
    "região": events_by(test, "regiao"),
}
SECOES["3. Prevalência e eventos"] = (
    "**Prevalência por ano**\\n\\n" + markdown_table(prev, 2)
    + "\\n\\n**Eventos por região — desenvolvimento 2022–23 (dobras leave-one-region-out)**\\n\\n"
    + markdown_table(por_regiao_dev, 2)
    + "".join(f"\\n\\n**Teste 2024 — por {k}**\\n\\n" + markdown_table(v, 2)
              for k, v in sub_2024.items())
)
alertas = [f"{k}={i}" for k, v in sub_2024.items() for i in v.index[v["< 100 eventos"] != ""]]
alertas_dev = list(por_regiao_dev.index[por_regiao_dev["< 100 eventos"] != ""])
RESUMO["3a"] = {"item": "Prevalência de y por ano", "secao": "§3.7",
                "resultado": "; ".join(f"{a}: {r['prevalência (%)']:.2f}% "
                                       f"({int(r['eventos (y=1)']):,} eventos)"
                                       for a, r in prev.iterrows()),
                "esperado": "revisar", "obs": ""}
RESUMO["3b"] = {"item": "Eventos por região (2022–23)", "secao": "§3.8",
                "resultado": "mín. " + f"{int(por_regiao_dev['eventos (y=1)'].min()):,} eventos",
                "esperado": "não" if alertas_dev else "sim",
                "obs": ("< 100 eventos: " + ", ".join(map(str, alertas_dev))) if alertas_dev
                else "Todas as regiões com ≥ 100 eventos."}
RESUMO["3c"] = {"item": "Eventos por subgrupo (2024)", "secao": "§3.8, §3.12",
                "resultado": f"{len(alertas)} subgrupo(s) com < 100 eventos",
                "esperado": "não" if alertas else "sim",
                "obs": ", ".join(alertas)}
display(prev); display(por_regiao_dev)
for k, v in sub_2024.items():
    print(k); display(v)
"""),
    md("## Passo 4 — Comorbidades e o check de vazamento"),
    code("""
comorb_counts = domain_counts(df, COMORBIDADES)
comorb_outros = other_values(df, COMORBIDADES)
leak = absent_by_target(pop, COMORBIDADES)
SECOES["4. Comorbidades"] = (
    "**Valores por ano (todas as notificações)**\\n\\n" + markdown_table(comorb_counts)
    + "\\n\\n**Valores fora de 1/2 mais comuns**\\n\\n"
    + (markdown_table(comorb_outros) if len(comorb_outros) else "Nenhum.")
    + "\\n\\n**% Ausente × alvo (população final)**\\n\\n" + markdown_table(leak, 2)
)
pct_ausente = 100 * (~code(pop[COMORBIDADES[0]]).isin({"1", "2"})).mean()
RESUMO["4a"] = {"item": "Valores das comorbidades", "secao": "§3.7",
                "resultado": f"{COMORBIDADES[0]}: {pct_ausente:.1f}% ausente na população final",
                "esperado": "revisar",
                "obs": "Valores fora de 1/2: " + (", ".join(sorted(set(comorb_outros['valor'])))
                                                  if len(comorb_outros) else "nenhum")}
flagged = list(leak.index[leak["alerta (razão > 2)"] != ""])
RESUMO["4b"] = {"item": "% ausente × y (vazamento)", "secao": "§3.8",
                "resultado": f"razão y0/y1 entre {leak['razão y0/y1'].min():.2f} e "
                             f"{leak['razão y0/y1'].max():.2f}",
                "esperado": "não" if flagged else "sim",
                "obs": ("Razão > 2: " + ", ".join(flagged) + " → Q-06") if flagged else
                "Nenhuma comorbidade com razão > 2."}
display(comorb_counts); display(comorb_outros); display(leak)
"""),
    md("## Passo 5 — Idade"),
    code("""
age = age_summary(df)
units = age_unit_counts(df)
concord = age_vs_birth_year(df)
SECOES["5. Idade"] = (
    markdown_table(age, 2) + "\\n\\n**Unidade (1º dígito de NU_IDADE_N)**\\n\\n"
    + markdown_table(units)
    + "\\n\\n**Idade decodificada × (ano de DT_SIN_PRI − ANO_NASC)** — tolerância de 1 ano, "
    + "porque os microdados não trazem DT_NASC, só o ano de nascimento"
    + "\\n\\n" + markdown_table(concord, 2)
)
fora = int(age["fora de [0, 120]"].sum())
RESUMO["5"] = {"item": "Idade: decodificação e faixa", "secao": "§3.7, §3.9",
               "resultado": f"{concord['% concordância'].iloc[0]:.1f}% concordam com "
                            "ANO_NASC (±1 ano); "
                            f"{fora} fora de [0, 120]; "
                            f"{int(age['código inválido'].sum()):,} códigos inválidos; "
                            f"{int(age['recuperada por ANO_NASC'].sum()):,} recuperadas por "
                            f"ANO_NASC; {int(age['sem idade (excluída)'].sum()):,} sem idade",
               "esperado": "sim" if concord["% concordância"].iloc[0] > 95 else "revisar",
               "obs": "Idade inválida usa ano dos sintomas − ANO_NASC (D-50)."}
display(age); display(units); display(concord)
"""),
    md("## Passo 6 — Demografia"),
    code("""
demo = {c: counts_by_year(df, c) for c in ["CS_SEXO", "CS_GESTANT", "CS_RACA"]}
incons = demography_inconsistencies(df)
ign = ignored_share(df, ["CS_RACA", "CS_ESCOL_N"], ignored={"9"})
SECOES["6. Demografia"] = "".join(f"**{c}**\\n\\n" + markdown_table(t) + "\\n\\n"
                                  for c, t in demo.items()) + (
    "**Inconsistências**\\n\\n" + markdown_table(incons)
    + "\\n\\n**% ignorado (9) + branco — Q-05**\\n\\n" + markdown_table(ign, 1))
RESUMO["6"] = {"item": "Demografia e inconsistências", "secao": "§3.7",
               "resultado": f"gestante com sexo M: {int(incons['gestante com sexo M'].sum()):,}; "
                            f"raça ignorada/branco: "
                            + ", ".join(f"{a} {ign.loc['CS_RACA', a]:.0f}%" for a in ANOS),
               "esperado": "revisar", "obs": "Ver Q-05 (raça/escolaridade)."}
for c, t in demo.items():
    print(c); display(t)
display(incons); display(ign)
"""),
    md("## Passo 7 — Sinais clínicos e de alarme"),
    code("""
sinais = absent_share(df, [c for c in SINAIS if c in df.columns])
alarm = alarm_filled_by_class(df, ["ALRM_ANY"])
SECOES["7. Sinais clínicos e de alarme"] = (
    "**% ausente (branco ou ≠ 1/2) por ano**\\n\\n" + markdown_table(sinais, 1)
    + "\\n\\n**Algum `ALRM_*` preenchido, por `CLASSI_FIN`** (todos os anos)\\n\\n"
    + markdown_table(alarm, 1))
RESUMO["7a"] = {"item": "Sinais clínicos: % ausente", "secao": "§3.8",
                "resultado": f"entre {sinais.min().min():.1f}% e {sinais.max().max():.1f}%",
                "esperado": "revisar", "obs": ""}
pct10 = alarm.loc["10", "%"] if "10" in alarm.index else float("nan")
pct11 = alarm.loc["11", "%"] if "11" in alarm.index else float("nan")
# A restrição de M2 vale enquanto o preenchimento separar as classes (revela a classificação).
revela_classe = pct11 - pct10 > 50
RESUMO["7b"] = {"item": "ALRM_* preenchido por CLASSI_FIN", "secao": "§3.6",
                "resultado": f"algum ALRM_* preenchido: {pct10:.1f}% em CLASSI_FIN=10, "
                             f"{pct11:.1f}% em 11",
                "esperado": "sim" if revela_classe else "revisar",
                "obs": "Preenchimento revela a classe: restrição de M2 a 11/12 necessária."
                if revela_classe else "Preenchimento parecido entre classes: rever M2 (§3.6)."}
display(sinais); display(alarm)
"""),
    md("## Passo 8 — Datas"),
    code("""
delay = notification_delay(df)
ano_sint = date_year_vs_file(df, "DT_SIN_PRI")
ano_notif = date_year_vs_file(df, "DT_NOTIFIC")
SECOES["8. Datas"] = (
    "**Atraso sintomas → notificação (dias)**\\n\\n" + markdown_table(delay, 1)
    + "\\n\\n**Ano de DT_SIN_PRI × ano do arquivo**\\n\\n" + markdown_table(ano_sint)
    + "\\n\\n**Ano de DT_NOTIFIC × ano do arquivo**\\n\\n" + markdown_table(ano_notif))
RESUMO["8"] = {"item": "Atraso sintomas → notificação", "secao": "§3.9",
               "resultado": "; ".join(f"{a}: mediana {r['mediana']:.0f} d, p99 {r['p99']:.0f} d, "
                                      f"{int(r['> 60 dias']):,} > 60 d"
                                      for a, r in delay.iterrows()),
               "esperado": "revisar", "obs": "Ver também ano da data × ano do arquivo."}
display(delay); display(ano_sint); display(ano_notif)
"""),
    md("## Passo 9 — Duplicatas"),
    code("""
dups = duplicates(pop)
nduplic = counts_by_year(pop, "NDUPLIC_N") if "NDUPLIC_N" in pop else None
SECOES["9. Duplicatas"] = (
    "Chave: ANO_NASC + idade (os microdados não trazem DT_NASC) + CS_SEXO + ID_MN_RESI + "
    "DT_SIN_PRI, na população final. Sem a data completa de nascimento, a chave é mais fraca "
    "e tende a superestimar duplicatas.\\n\\n" + markdown_table(dups, 2)
    + ("\\n\\n**NDUPLIC_N (marcação de duplicidade do próprio SINAN), população final**\\n\\n"
       + markdown_table(nduplic) if nduplic is not None else ""))
RESUMO["9"] = {"item": "Duplicatas", "secao": "§3.6",
               "resultado": "; ".join(f"{a}: {r['% em grupo duplicado']:.2f}% em grupo duplicado"
                                      for a, r in dups.iterrows()),
               "esperado": "revisar",
               "obs": f"{int(dups['linhas em grupos com y conflitante'].sum()):,} linhas em grupos "
                      "com desfecho conflitante → Q-04. Chave sem DT_NASC (mais fraca)."}
display(dups)
if nduplic is not None:
    display(nduplic)
"""),
    md("""
## Passo 10 — Cobertura do Espírito Santo

População: Censo 2022 do IBGE (SIDRA, tabela 4709), usada para os três anos. Se a API falhar,
a tabela sai só com contagens.
"""),
    code("""
import urllib.request

UF_SIGLA = {"11": "RO", "12": "AC", "13": "AM", "14": "RR", "15": "PA", "16": "AP", "17": "TO",
            "21": "MA", "22": "PI", "23": "CE", "24": "RN", "25": "PB", "26": "PE", "27": "AL",
            "28": "SE", "29": "BA", "31": "MG", "32": "ES", "33": "RJ", "35": "SP", "41": "PR",
            "42": "SC", "43": "RS", "50": "MS", "51": "MT", "52": "GO", "53": "DF"}
try:
    url = "https://apisidra.ibge.gov.br/values/t/4709/n3/all/v/93/p/2022"
    with urllib.request.urlopen(url, timeout=60) as r:
        rows = json.load(r)[1:]
    populacao = pd.Series({row["D1C"]: int(row["V"]) for row in rows})
    fonte_pop = "IBGE, Censo 2022 (SIDRA 4709)"
except Exception as exc:  # sem internet ou API fora do ar
    populacao, fonte_pop = None, f"indisponível ({type(exc).__name__})"

uf = cases_by_uf(pop, populacao)
sistema = None
if "TP_SISTEMA" in pop:
    sistema = pd.crosstab(code(pop["SG_UF"]).map(UF_SIGLA).fillna(BRANCO),
                          code(pop["TP_SISTEMA"]).fillna(BRANCO))
    sistema = sistema.loc[[i for i in ["ES", "MG", "RJ", "BA"] if i in sistema.index]]
uf.index = [f"{i} ({UF_SIGLA.get(i, '?')})" for i in uf.index]
foco = uf[uf.index.str.contains(r"\\((?:ES|MG|RJ|BA)\\)")]
SECOES["10. Cobertura do Espírito Santo"] = (
    f"População: {fonte_pop}.\\n\\n**ES e vizinhos**\\n\\n" + markdown_table(foco, 1)
    + ("\\n\\n**TP_SISTEMA (sistema de origem) — ES e vizinhos, 2022–24**\\n\\n"
       + markdown_table(sistema) if sistema is not None else "")
    + "\\n\\n**Todas as UFs**\\n\\n" + markdown_table(uf, 1))
if populacao is not None:
    taxa = foco[[c for c in foco.columns if str(c).startswith("por 100 mil")]]
    es = taxa[taxa.index.str.contains("(ES)", regex=False)].iloc[0]
    viz = taxa[~taxa.index.str.contains("(ES)", regex=False)].median()
    res10 = "; ".join(f"{c[-4:]}: ES {es[c]:.0f} vs mediana vizinhos {viz[c]:.0f} /100 mil"
                      for c in taxa.columns)
else:
    res10 = "sem população; ver contagens"
RESUMO["10"] = {"item": "Cobertura do ES", "secao": "§3.7", "resultado": res10,
                "esperado": "revisar", "obs": f"População: {fonte_pop}."}
foco
"""),
    md("## Passo 11 — Memória"),
    code("""
import os

try:
    import psutil
    ram_total = psutil.virtual_memory().total / 2**30
    ram_livre = psutil.virtual_memory().available / 2**30
except ImportError:
    ram_total = ram_livre = float("nan")
mem_df = df.memory_usage(deep=True).sum() / 2**30
mem_pop = pop.memory_usage(deep=True).sum() / 2**30
SECOES["11. Memória"] = markdown_table(pd.DataFrame({
    "item": ["RAM total da sessão (GiB)", "RAM disponível agora (GiB)",
             f"DataFrame carregado ({len(df):,} linhas × {df.shape[1]} colunas, GiB)",
             f"População final ({len(pop):,} linhas, GiB)"],
    "valor": [ram_total, ram_livre, mem_df, mem_pop],
}).set_index("item"), 2) + f"\\n\\nAmbiente: {'Colab' if IN_COLAB else 'local'}."
RESUMO["11"] = {"item": "RAM e tamanho do DataFrame", "secao": "NFR-01",
                "resultado": f"RAM {ram_total:.1f} GiB; DataFrame {mem_df:.2f} GiB "
                             f"({'Colab' if IN_COLAB else 'local'})",
                "esperado": "sim" if mem_df < 0.25 * ram_total else "revisar", "obs": ""}
"""),
    md("## Gera `RESULTADOS.md`"),
    code("""
from datetime import datetime, timezone

ordem = ["0", "1", "2", "3a", "3b", "3c", "4a", "4b", "5", "6", "7a", "7b", "8", "9", "10", "11"]
linhas = ["| # | Item | Seção do spec | Resultado (número ou achado) | Dentro do esperado? "
          "| Observação |", "|---|---|---|---|---|---|"]
for k in ordem:
    r = RESUMO.get(k)
    if r:
        linhas.append(f"| {k} | {r['item']} | {r['secao']} | {r['resultado']} | {r['esperado']} "
                      f"| {r['obs']} |")
gerado = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
texto = "\\n".join([
    "# Resultados do profiling — SINAN Dengue 2022–2024",
    "",
    f"> Gerado automaticamente por `profiling/01_profiling.ipynb` em {gerado} "
    f"({'Colab' if IN_COLAB else 'local'}). Não edite à mão: rode o notebook de novo.",
    "> \\"Dentro do esperado?\\" = `sim`/`não` quando a regra é objetiva; `revisar` quando "
    "depende de julgamento.",
    "",
    "## Resumo",
    "",
    *linhas,
    "",
    *[f"## {titulo}\\n\\n{conteudo}\\n" for titulo, conteudo in SECOES.items()],
])
OUT_MD.write_text(texto, encoding="utf-8")
print("Gravado:", OUT_MD)
"""),
]


def main() -> None:
    notebook = {
        "cells": CELLS,
        "metadata": {
            "kernelspec": {"name": "python3", "display_name": "Python 3", "language": "python"},
            "language_info": {"name": "python"},
            "colab": {"provenance": []},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    for i, cell in enumerate(notebook["cells"]):
        cell["id"] = f"c{i:02d}"
    OUT.write_text(json.dumps(notebook, indent=1, ensure_ascii=False), encoding="utf-8")
    print("Gerado:", OUT)


if __name__ == "__main__":
    main()
