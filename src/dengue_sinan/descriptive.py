"""Análise descritiva da população de desenvolvimento (T-2.6, FR-18, D-23, D-52, R7).

Só 2022–23: `dataset.load_population` recusa o ano de teste e `guard.assert_dev_only` confere de
novo. Duas saídas, com destinos diferentes:

- publicadas em `reports/descritiva/`: agregados, com células de 0 < n < 10 suprimidas (R7);
- internas, em `<caminhos.dados>/descritiva/`: contagens exatas de pares e de combinações de 3+.
  Ficam fora do git porque `data/` é ignorado (NFR-03). Servem à T-3.1 (interações do E1) e à
  tabela de perfis (T-3.5). Não são publicadas.

Os riscos brutos são descritivos: não substituem o E1 e não alimentam a tabela de perfis (FR-18).
"""

import itertools
from pathlib import Path

import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from dengue_sinan import dataset
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.profiling import COMORBIDADES, FAIXAS_ROTULOS, code, markdown_table

Z95 = 1.959963984540054  # quantil 97,5% da normal padrão: IC de 95%
NIVEIS_COMORBIDADE = ["Sim", "Não", "Ausente"]
NIVEIS_NCOMORB = ["0", "1", "2", "3 ou mais"]
NIVEIS_SEXO = ["M", "F", "I"]
NIVEIS_GESTANTE = ["Sim", "Não"]
RACA_ROTULOS = {"1": "Branca", "2": "Preta", "3": "Amarela", "4": "Parda", "5": "Indígena"}
NIVEIS_RACA = [*RACA_ROTULOS.values(), "Ignorado/em branco"]
PARES = list(itertools.combinations(COMORBIDADES, 2))  # 21 pares (D-52)
NOTA_RISCOS = "riscos brutos, descritivos; não substituem o E1"
# Limitação conhecida e aceita (decisão do Programador, Marco 2): sem números aqui (R7).
NOTA_SEXO = (
    "Sexo, no desfecho grave ou óbito: o “I” tem menos de 10 eventos e essa célula é suprimida; "
    "o “M” é suprimido como complemento; a soma M + I continua dedutível pelo total publicado "
    "(o total de eventos menos o de F), limitação conhecida e aceita para agregados de dados "
    "abertos. A análise de sexo de verdade vem do E1."
)


# --- Carga -----------------------------------------------------------------------------------

def carregar_desenvolvimento(cfg: dict) -> pd.DataFrame:
    """População de desenvolvimento com as colunas da análise.

    Os anos vêm de `cfg["anos_dev"]` (R1); `load_population` recusa 2024 antes de abrir arquivo.
    """
    populacao = dataset.load_population(cfg, list(cfg["anos_dev"]))
    assert_dev_only(populacao)
    df = dataset.build_feature_frame(populacao)
    df["gestante_rotulo"] = np.where(df["gestante"] == 1, "Sim", "Não")
    df["raca"] = code(df["CS_RACA"]).map(RACA_ROTULOS).fillna("Ignorado/em branco")
    df["ncomorb_grupo"] = np.minimum(df["n_comorbidades"], 3).map(
        {0: "0", 1: "1", 2: "2", 3: "3 ou mais"})
    return df


# --- Estatística e supressão (R7) -------------------------------------------------------------

def wilson_ci(k: int, n: int, z: float = Z95) -> tuple[float, float]:
    """IC de Wilson (score) para a proporção k/n. Devolve (inferior, superior); (nan, nan) se n=0.

    Por que Wilson e não o IC normal: com prevalência de ~0,16% e poucos eventos, o IC normal
    sai negativo e cobre mal. Wilson fica dentro de [0, 1] e mantém cobertura razoável.
    """
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    z2 = z * z
    centro = (p + z2 / (2 * n)) / (1 + z2 / n)
    meia = z * np.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    # Nos extremos o limite é exatamente 0 ou 1; a fórmula daria 0,9999999999999999 em n/n.
    inf = 0.0 if k == 0 else max(0.0, centro - meia)
    sup = 1.0 if k == n else min(1.0, centro + meia)
    return (inf, sup)


def _suprimidas(valores: list[int], minimo: int) -> list[bool]:
    """Quais células de um bloco não são publicadas (R7).

    Um bloco é um conjunto de células que somam o total. Primeiro suprime-se toda célula com
    0 < valor < minimo. Se só uma foi suprimida, suprime-se também a menor das outras (supressão
    complementar): sem ela, o total publicado daria o valor de volta por subtração.
    """
    mascara = [0 < v < minimo for v in valores]
    if sum(mascara) == 1:
        outras = [i for i, s in enumerate(mascara) if not s]
        mascara[min(outras, key=lambda i: valores[i])] = True
    return mascara


def _inteiro(n: int) -> str:
    return f"{int(n):,}".replace(",", " ")


def _decimal(x: float, casas: int = 1) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def _contar(rotulos: pd.Series, niveis: list[str]) -> pd.Series:
    """Nº de linhas por nível, com zeros, na ordem de `niveis`."""
    return rotulos.value_counts().reindex(niveis, fill_value=0)


def _salvar_interno(cfg: dict, nome: str, tabela: pd.DataFrame) -> Path:
    """Grava a contagem exata em `<caminhos.dados>/descritiva/` (fora do git, nunca em reports/)."""
    caminho = Path(cfg["caminhos"]["dados"]) / "descritiva" / nome
    caminho.parent.mkdir(parents=True, exist_ok=True)
    tabela.to_csv(caminho, index=False, encoding="utf-8")
    return caminho


# --- Tabela 1: características por desfecho ----------------------------------------------------

def tabela_caracteristicas(df: pd.DataFrame) -> pd.DataFrame:
    """Contagens exatas por variável, categoria e desfecho (y = 0 e y = 1).

    Interna: a publicação passa por `formatar_tabela1`, que aplica a supressão (R7).
    """
    blocos = [
        ("Sexo", "sexo", NIVEIS_SEXO),
        ("Gestante (CS_GESTANT 1–4; denominador: todo o grupo)", "gestante_rotulo",
         NIVEIS_GESTANTE),
        ("Raça/cor", "raca", NIVEIS_RACA),
        *[(c, c, NIVEIS_COMORBIDADE) for c in COMORBIDADES],
        ("Nº de comorbidades", "ncomorb_grupo", NIVEIS_NCOMORB),
    ]
    linhas = []
    for variavel, coluna, niveis in blocos:
        for desfecho in (0, 1):
            rotulos = df.loc[df["y"] == desfecho, coluna]
            total = len(rotulos)
            for categoria, n in _contar(rotulos, niveis).items():
                linhas.append({"variavel": variavel, "categoria": categoria, "y": desfecho,
                               "n": int(n), "total": total})
    return pd.DataFrame(linhas)


ROTULO_NAO_OU_AUSENTE = "Não ou ausente"
ROTULO_AMARELA_OU_INDIGENA = "Amarela ou indígena"


def agrupar_caracteristicas(caracteristicas: pd.DataFrame) -> pd.DataFrame:
    """Fusão só para EXIBIÇÃO (decisão do Programador): o E1 mantém os 3 níveis (D-07).

    Nas comorbidades, "Ausente" vai para "Não" (rótulo "Não ou ausente"). Em raça/cor, "Amarela"
    e "Indígena" viram "Amarela ou indígena". Os totais por desfecho não mudam.
    """
    out = caracteristicas.copy()
    out["categoria"] = out["categoria"].astype(object)
    comorb = out["variavel"].isin(COMORBIDADES)
    out.loc[comorb & out["categoria"].isin(["Não", "Ausente"]), "categoria"] = ROTULO_NAO_OU_AUSENTE
    raca = out["variavel"] == "Raça/cor"
    out.loc[raca & out["categoria"].isin(["Amarela", "Indígena"]), "categoria"] = (
        ROTULO_AMARELA_OU_INDIGENA)
    return (out.groupby(["variavel", "categoria", "y"], sort=False, as_index=False)
            .agg(n=("n", "sum"), total=("total", "first")))


def resumo_idade(df: pd.DataFrame) -> pd.DataFrame:
    """Mediana e quartis da idade em anos, por desfecho."""
    linhas = []
    for desfecho in (0, 1):
        idade = df.loc[df["y"] == desfecho, "idade_anos"]
        q1, mediana, q3 = idade.quantile([0.25, 0.5, 0.75])
        linhas.append({"y": desfecho, "total": len(idade), "q1": q1, "mediana": mediana,
                       "q3": q3})
    return pd.DataFrame(linhas)


def formatar_tabela1(caracteristicas: pd.DataFrame, idade: pd.DataFrame,
                     minimo: int) -> pd.DataFrame:
    """Tabela 1 publicável: n (%) por desfecho, com células < `minimo` suprimidas (R7)."""
    totais = {int(r.y): int(r.total) for r in idade.itertuples(index=False)}
    colunas = {0: "y = 0 (não grave)", 1: "y = 1 (grave ou óbito)"}
    saida: list[dict] = []

    def linha(variavel: str, categoria: str, textos: dict[int, str]) -> None:
        saida.append({"Variável": variavel, "Categoria": categoria,
                      colunas[0]: textos[0], colunas[1]: textos[1]})

    def suprimido_txt(total: int) -> str:
        return f"<{minimo}" if total < minimo else _inteiro(total)

    linha("Casos (n)", "", {d: suprimido_txt(totais[d]) for d in (0, 1)})
    linha("Idade (anos): mediana (Q1–Q3)", "", {
        r.y: (f"{r.mediana:.0f} ({r.q1:.0f}–{r.q3:.0f})" if r.total >= minimo else "—")
        for r in idade.itertuples(index=False)})
    for variavel, bloco in caracteristicas.groupby("variavel", sort=False):
        celulas: dict[tuple[int, str], str] = {}
        for desfecho in (0, 1):
            sub = bloco[bloco["y"] == desfecho]
            mascara = _suprimidas(sub["n"].tolist(), minimo)
            for r, suprimida in zip(sub.itertuples(index=False), mascara, strict=True):
                if suprimida:
                    texto = "—"
                else:
                    texto = f"{_inteiro(r.n)} ({_decimal(100 * r.n / r.total)}%)"
                celulas[(desfecho, r.categoria)] = texto
        for categoria in bloco["categoria"].unique():
            linha(variavel, categoria, {0: celulas[(0, categoria)], 1: celulas[(1, categoria)]})
    return pd.DataFrame(saida)


# --- Riscos brutos com IC de Wilson ------------------------------------------------------------

def tabela_riscos(df: pd.DataFrame) -> pd.DataFrame:
    """Casos, eventos, risco bruto e IC 95% de Wilson por nível de cada bloco.

    Blocos: cada comorbidade, nº de comorbidades (0, 1, 2, 3+) e faixa etária. Interna: a
    publicação passa por `formatar_riscos`, que aplica a supressão (R7).
    """
    blocos = [(c, c, NIVEIS_COMORBIDADE) for c in COMORBIDADES] + [
        ("Nº de comorbidades", "ncomorb_grupo", NIVEIS_NCOMORB),
        ("Faixa etária", "faixa_etaria", FAIXAS_ROTULOS),
    ]
    com_evento = df.loc[df["y"] == 1]
    linhas = []
    for bloco, coluna, niveis in blocos:
        casos = _contar(df[coluna], niveis)
        eventos = _contar(com_evento[coluna], niveis)
        for nivel in niveis:
            c, e = int(casos[nivel]), int(eventos[nivel])
            inf, sup = wilson_ci(e, c)
            linhas.append({"bloco": bloco, "nivel": nivel, "casos": c, "eventos": e,
                           "risco": e / c if c else float("nan"), "ic_inf": inf, "ic_sup": sup})
    return pd.DataFrame(linhas)


def agrupar_riscos(tab: pd.DataFrame) -> pd.DataFrame:
    """Fusão só para EXIBIÇÃO: nas comorbidades, "Não" + "Ausente" viram "Não ou ausente".

    Recalcula risco e IC de Wilson da linha fundida. Assim o "Sim" de cada comorbidade e o
    "Não ou ausente" têm 2 células, sem célula de evento pequena no Sim.
    """
    out = tab.copy()
    comorb = out["bloco"].isin(COMORBIDADES)
    out.loc[comorb & out["nivel"].eq("Ausente"), "nivel"] = "Não"
    out.loc[comorb & out["nivel"].eq("Não"), "nivel"] = ROTULO_NAO_OU_AUSENTE
    agregada = (out.groupby(["bloco", "nivel"], sort=False, as_index=False)
                .agg(casos=("casos", "sum"), eventos=("eventos", "sum")))
    casos, eventos = agregada["casos"], agregada["eventos"]
    agregada["risco"] = [e / c if c else float("nan") for c, e in zip(casos, eventos, strict=True)]
    limites = [wilson_ci(int(e), int(c)) for c, e in zip(casos, eventos, strict=True)]
    agregada["ic_inf"] = [lo for lo, _ in limites]
    agregada["ic_sup"] = [hi for _, hi in limites]
    return agregada


def ausentes_por_comorbidade(tab: pd.DataFrame, minimo: int) -> pd.DataFrame:
    """Casos e eventos com "Ausente" em cada comorbidade, para a nota de rodapé (R7).

    Os eventos desses casos já estão em "Não ou ausente". Contagens 1–9 viram "—".
    """
    linhas = []
    for r in tab[tab["bloco"].isin(COMORBIDADES) & tab["nivel"].eq("Ausente")].itertuples(
            index=False):
        linhas.append({
            "Comorbidade": r.bloco,
            "Casos com ausente": _inteiro(r.casos) if r.casos >= minimo else "—",
            "Eventos com ausente": (_inteiro(r.eventos) if r.eventos == 0 or r.eventos >= minimo
                                    else "—"),
        })
    return pd.DataFrame(linhas)


def _com_supressao(tab: pd.DataFrame, minimo: int) -> pd.DataFrame:
    """Marca, por bloco, o que sai (casos, eventos e risco/IC) segundo R7."""
    partes = []
    for _, sub in tab.groupby("bloco", sort=False):
        partes.append(sub.assign(
            suprime_casos=_suprimidas(sub["casos"].tolist(), minimo),
            suprime_eventos=_suprimidas(sub["eventos"].tolist(), minimo)))
    out = pd.concat(partes, ignore_index=True)
    out["mostra_risco"] = (~(out["suprime_casos"] | out["suprime_eventos"])) & (out["casos"] > 0)
    return out


def formatar_riscos(tab: pd.DataFrame, minimo: int) -> pd.DataFrame:
    """Tabela de riscos publicável. Risco e IC só aparecem se casos e eventos forem publicados."""
    marcada = _com_supressao(tab, minimo)
    linhas = []
    for r in marcada.itertuples(index=False):
        if r.mostra_risco:
            risco = f"{_decimal(100 * r.risco, 3)}%"
            ic = f"[{_decimal(100 * r.ic_inf, 3)}; {_decimal(100 * r.ic_sup, 3)}]"
        else:
            risco = ic = "—"
        linhas.append({
            "Grupo": r.bloco,
            "Nível": r.nivel,
            "Casos": "—" if r.suprime_casos else _inteiro(r.casos),
            "Eventos": "—" if r.suprime_eventos else _inteiro(r.eventos),
            "Risco bruto": risco,
            "IC 95% (Wilson)": ic,
        })
    return pd.DataFrame(linhas)


def _grafico_riscos(marcada: pd.DataFrame, caminho: Path, titulo: str) -> Path:
    """Gráfico de pontos com IC 95%. Só usa as linhas com risco publicável (R7).

    Usa Figure com canvas Agg explícito: não abre janela e não depende de pyplot nem de backend.
    """
    publicaveis = marcada[marcada["mostra_risco"]].reset_index(drop=True)
    fig = Figure(figsize=(8, 0.45 * max(len(publicaveis), 3) + 1.5))
    FigureCanvasAgg(fig)
    ax = fig.add_subplot()
    ax.set_title(titulo, fontsize=10)
    if not publicaveis.empty:
        posicao = np.arange(len(publicaveis))[::-1]
        risco = 100 * publicaveis["risco"].to_numpy()
        inf = 100 * publicaveis["ic_inf"].to_numpy()
        sup = 100 * publicaveis["ic_sup"].to_numpy()
        ax.errorbar(risco, posicao, xerr=[risco - inf, sup - risco], fmt="o", capsize=3)
        rotulos = [f"{r.bloco}: {r.nivel}" if r.bloco in COMORBIDADES else r.nivel
                   for r in publicaveis.itertuples(index=False)]
        ax.set_yticks(posicao, labels=rotulos)
    ax.set_xlabel("Risco bruto de y = 1 (%), IC 95% de Wilson")
    ax.grid(axis="x", alpha=0.3)
    fig.tight_layout()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(caminho, dpi=120)
    return caminho


# --- Pares e combinações (contagens internas, D-52) --------------------------------------------

def pair_event_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Para cada um dos 21 pares de comorbidades: casos e eventos com as DUAS = Sim.

    Contagem exata e interna. A publicação passa por `formatar_pares` (R7).
    """
    y = df["y"].to_numpy() == 1
    sim = {c: (df[c] == "Sim").to_numpy() for c in COMORBIDADES}
    linhas = []
    for a, b in PARES:
        ambas = sim[a] & sim[b]
        linhas.append({"comorbidade_1": a, "comorbidade_2": b,
                       "casos": int(ambas.sum()), "eventos": int((ambas & y).sum())})
    return pd.DataFrame(linhas)


def formatar_pares(pares: pd.DataFrame, minimo: int) -> pd.DataFrame:
    """Tabela de pares publicável: casos e eventos suprimidos se < `minimo` (R7).

    A coluna "Entra no E1" marca os pares com ≥ 10 eventos (interações reportadas, SC-05).
    """
    linhas = []
    for r in pares.itertuples(index=False):
        linhas.append({
            "Par": f"{r.comorbidade_1} + {r.comorbidade_2}",
            "Casos": f"<{minimo}" if 0 < r.casos < minimo else _inteiro(r.casos),
            "Eventos": f"<{minimo}" if 0 < r.eventos < minimo else _inteiro(r.eventos),
            "Entra no E1 (≥ 10 eventos)": "Sim" if r.eventos >= minimo else "Não",
        })
    return pd.DataFrame(linhas)


def combination_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Cada combinação EXATA de 3 ou mais comorbidades = Sim que aparece nos dados.

    "Exata": essas são Sim e todas as outras não são Sim (Não ou Ausente). Usa uma chave de 7
    bits por linha, então conta sem percorrer as combinações uma a uma. Interna (não publicada).
    """
    chave = np.zeros(len(df), dtype=np.int64)
    for i, c in enumerate(COMORBIDADES):
        chave |= (df[c] == "Sim").to_numpy().astype(np.int64) << i
    y = df["y"].to_numpy().astype(np.float64)
    tamanho = 2 ** len(COMORBIDADES)
    casos = np.bincount(chave, minlength=tamanho)
    eventos = np.bincount(chave, weights=y, minlength=tamanho)
    linhas = []
    for mascara in range(1, tamanho):
        k = bin(mascara).count("1")
        if k >= 3 and casos[mascara] > 0:
            nomes = [c for i, c in enumerate(COMORBIDADES) if mascara >> i & 1]
            linhas.append({"combinacao": " + ".join(nomes), "n_comorbidades": k,
                           "casos": int(casos[mascara]), "eventos": int(eventos[mascara])})
    return pd.DataFrame(linhas, columns=["combinacao", "n_comorbidades", "casos", "eventos"])


# --- Geração dos arquivos -----------------------------------------------------------------------

def _escrever_texto(caminho: Path, titulo: str, intro: str, corpo: str) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(f"# {titulo}\n\n{intro}\n\n{corpo}\n", encoding="utf-8")
    return caminho


def _escrever(caminho: Path, titulo: str, intro: str, tabela: pd.DataFrame) -> Path:
    return _escrever_texto(caminho, titulo, intro, markdown_table(tabela))


def gerar(cfg: dict) -> dict:
    """Gera os arquivos da T-2.6 com os anos de desenvolvimento.

    Publica em `reports/descritiva/` e grava as contagens internas em `data/descritiva/`.
    Devolve só agregados: os números que o Registro de execução pede.
    """
    minimo = cfg["supressao_min_celula"]
    pasta = Path(cfg["caminhos"]["relatorios"]) / "descritiva"
    df = carregar_desenvolvimento(cfg)

    aviso_r7 = (
        f"“—” = célula suprimida (R7): n entre 1 e {minimo - 1}, ou suprimida para completar o "
        "bloco (fallback: a supressão complementar não impede dedução por subtração dos totais, "
        "por isso só se usa onde ainda sobra célula pequena, hoje só em sexo)."
    )
    fusao = (
        "Exibição: nas comorbidades, “Não ou ausente” reúne “Não” e “Ausente” (o E1 mantém os 3 "
        "níveis, D-07); em raça/cor, “Amarela ou indígena” reúne as duas categorias. "
        f"{NOTA_SEXO}"
    )

    caracteristicas = tabela_caracteristicas(df)
    idade = resumo_idade(df)
    _escrever(
        pasta / "tabela1.md",
        "Tabela 1: características por desfecho (desenvolvimento 2022–23)",
        "População final (D-45), anos de `anos_dev`. y = 0: não grave; y = 1: dengue grave ou "
        "óbito pelo agravo (D-02). Cada célula é n (% do desfecho). Idade: mediana e quartis "
        f"dos casos do grupo. {fusao} {aviso_r7}",
        formatar_tabela1(agrupar_caracteristicas(caracteristicas), idade, minimo),
    )

    riscos = tabela_riscos(df)
    ausentes = ausentes_por_comorbidade(riscos, minimo)
    riscos_exibidos = agrupar_riscos(riscos)
    marcada = _com_supressao(riscos_exibidos, minimo)
    secoes = [
        ("Por comorbidade", riscos_exibidos["bloco"].isin(COMORBIDADES)),
        ("Por nº de comorbidades", riscos_exibidos["bloco"] == "Nº de comorbidades"),
        ("Por faixa etária", riscos_exibidos["bloco"] == "Faixa etária"),
    ]
    corpo = "\n\n".join(
        f"## {titulo}\n\n{markdown_table(formatar_riscos(riscos_exibidos[mascara], minimo))}"
        for titulo, mascara in secoes)
    corpo += (
        "\n\n## Nota: casos com ausente em cada comorbidade\n\n"
        "Os casos com comorbidade “Ausente” (campo em branco ou fora de 1/2) estão em "
        "“Não ou ausente”, e os eventos deles também. Contagens:\n\n"
        f"{markdown_table(ausentes)}"
    )
    _escrever_texto(
        pasta / "riscos_brutos.md",
        "Riscos brutos de y = 1 (descritivos)",
        f"**{NOTA_RISCOS}.** Risco = eventos / casos do grupo, com IC 95% de Wilson. {fusao} "
        f"{aviso_r7} Risco e IC da linha só aparecem se casos e eventos aparecem. Não entram na "
        "tabela de perfis (D-10, D-20).",
        corpo,
    )
    _grafico_riscos(marcada[marcada["bloco"].isin(COMORBIDADES)],
                    pasta / "riscos_comorbidades.png",
                    "Risco bruto por comorbidade (Sim e Não ou ausente)")
    _grafico_riscos(marcada[marcada["bloco"] == "Nº de comorbidades"],
                    pasta / "riscos_n_comorbidades.png",
                    "Risco bruto por nº de comorbidades")
    _grafico_riscos(marcada[marcada["bloco"] == "Faixa etária"],
                    pasta / "riscos_faixa_etaria.png", "Risco bruto por faixa etária")

    pares = pair_event_counts(df)
    combinacoes = combination_counts(df)
    _salvar_interno(cfg, "pares_comorbidades.csv", pares)
    _salvar_interno(cfg, "combinacoes_3_ou_mais.csv", combinacoes)
    _escrever(
        pasta / "pares_comorbidades.md",
        "Pares de comorbidades: casos e eventos com as duas = Sim",
        "21 pares das 7 comorbidades. Pares com ≥ 10 eventos são as interações reportadas no E1 "
        f"(SC-05, FR-05). Células com 0 < n < {minimo} são suprimidas (R7). A contagem completa "
        "fica em arquivo interno, fora do git, para a T-3.1.",
        formatar_pares(pares, minimo),
    )
    return {
        "casos_total": int(len(df)),
        "eventos_total": int(df["y"].sum()),
        "pares_com_10_eventos": int((pares["eventos"] >= minimo).sum()),
        "combinacoes_3_ou_mais_presentes": int(len(combinacoes)),
        "combinacoes_3_ou_mais_com_10_casos": int((combinacoes["casos"] >= minimo).sum()),
    }
