"""Análises da T-5.2 sobre o teste: curva de decisão, calibração com bandas e subgrupos (D-93).

Funções puras sobre arrays: recebem `y`, as predições e a semente, e devolvem agregados (dicts e
DataFrames). Não leem dado, não gravam arquivo e não importam `evaluate` (é `evaluate` que as
registra como `Analise` em `ANALISES_PADRAO`). Nenhuma devolve linha individual (R7).

Bootstrap (D-53, D-93, R8). Sempre estratificado por alvo, com a semente do config e uma
sub-semente por reamostra (`metrics.sementes_das_reamostras`): a reamostra k usa a k-ésima, e o
resultado é o mesmo com 1, 2, 4 ou 8 processos. Cada análise usa o seu próprio fluxo da
sub-semente (`FLUXO_*`), então as análises não repetem os números aleatórias umas das outras.
Linhas com o mesmo alvo e a mesma "faixa" formam células, e a reamostra sorteia os pesos das
células (multinomial, equivalente ao sorteio de linhas): O(#células) por reamostra, e os mesmos
sorteios valem para todos os modelos de uma análise.

- **Curva de decisão** (D-39): células = (alvo, faixa de limiar de M1, faixa de limiar de B1, flag
  da regra B2). A "faixa de limiar" é quantos pontos da grade são ≤ ao risco previsto. Como a
  reamostra é estratificada por alvo, a prevalência é a mesma em toda reamostra: "tratar todos" não
  tem banda.
- **Calibração por caixas**: caixas por quantis do risco previsto de cada modelo (o nº de caixas é
  `CAIXAS_CALIBRACAO`); células = (alvo, caixa de M1, caixa de E1). A banda é a da taxa observada
  em cada caixa; o risco previsto médio da caixa é o da amostra original.
- **Subgrupos** (D-13, D-48): o bootstrap é feito DENTRO de cada subgrupo (estratificado por alvo),
  com `metrics.Reamostrador` no modo tolerante. **Política de reamostra sem convergência do ajuste
  do slope** (decisão provisória, a confirmar pelo Programador): a reamostra é descartada SÓ para o
  slope e o intercepto (as demais métricas não dependem do ajuste e usam todas as reamostras);
  conta-se quantas foram descartadas e a quantidade é reportada; se mais de `LIMITE_DESCARTE`
  (5%) das reamostras do subgrupo forem descartadas, o IC do slope e do intercepto sai como
  "indisponível" (nunca um número parcial). O ponto estimado também fica "indisponível" se o ajuste
  do subgrupo não convergir. Um erro de ajuste num subgrupo nunca aborta a avaliação.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np
import pandas as pd

from dengue_sinan import metrics
from dengue_sinan.descriptive import NIVEIS_RACA, RACA_ROTULOS
from dengue_sinan.profiling import MIN_EVENTOS, code
from dengue_sinan.teste_graficos import LEGENDA_SUBGRUPOS  # uma só fonte da legenda

QUANTIS_IC = (0.025, 0.975)
FLUXO_DECISAO = 2
FLUXO_CALIBRACAO = 3
FLUXO_SUBGRUPOS = 10  # cada subgrupo usa 2 fluxos: 10 + 2 × (posição fixa na lista de subgrupos)

# Calibração por caixas: 10 caixas por quantis do risco previsto. A regra do spec (spec › Tamanho do
# teste e das dobras) pede >= 100 eventos para estimar uma taxa com alguma precisão: com ~11 mil
# eventos em 5,3 milhões de casos, decis dão ~1.100 eventos por caixa em média, e as de menor risco
# ainda ficam perto de 100. Com 20 caixas as de baixo risco cairiam abaixo de 100 eventos e as
# bandas ficariam largas demais para ler. Caixas com < 100 eventos recebem aviso no relatório.
CAIXAS_CALIBRACAO = 10

MIN_EVENTOS_METRICAS = 10  # R7: com menos eventos o subgrupo sai sem métricas
MIN_EVENTOS_AVISO = MIN_EVENTOS  # 100 (spec › Tamanho do teste): abaixo, aviso de IC largo
LIMITE_DESCARTE = 0.05  # fração de reamostras sem convergência acima da qual o IC não sai
# Subgrupos que o spec nomeia (spec › Tamanho do teste): aviso por nome, além da regra geral.
SUBGRUPOS_COM_AVISO_NOMEADO = frozenset({
    ("sexo", "I"), ("sexo", "em branco"), ("gestante", "gestante"), ("regiao", "Norte")})
AVISO_IC_LARGO = "IC largo: poucos eventos; sem conclusões"
POLITICA_DESCARTE = (
    "Reamostra sem convergência do ajuste do slope: é descartada só para o slope e o "
    "intercepto; as demais métricas usam todas as reamostras. As descartadas são contadas e "
    f"reportadas. Se mais de {int(LIMITE_DESCARTE * 100)}% das reamostras do subgrupo forem "
    "descartadas, o IC do slope "
    "e do intercepto sai como indisponível. Se o ajuste da amostra do subgrupo não convergir, o "
    "ponto estimado também sai como indisponível. (Decisão provisória, a confirmar.)")

DIMENSOES = ("faixa_etaria", "sexo", "gestante", "regiao", "raca_cor")
NOMES_DIMENSOES = {"faixa_etaria": "Faixa etária", "sexo": "Sexo", "gestante": "Gestante",
                   "regiao": "Região de residência", "raca_cor": "Raça/cor"}
SEM_REGIAO = "sem região"
SEXOS = ("F", "M", "I", "em branco")
GESTANTE_ROTULOS = ("gestante", "não gestante")


# --- Números e texto -------------------------------------------------------------------------

def celula(valor: int) -> int | str:
    """R7: contagem de 1 a 9 vira "<10"; zero e valores grandes passam."""
    valor = int(valor)
    return "<10" if 0 < valor < 10 else valor


def contagem_de_reamostras(valor: int) -> int | str:
    """Contagem de REAMOSTRAS (não de casos). De 1 a 9 sai como texto, para o verificador sintático
    de R7 (`artifacts.inteiros_pequenos`) não a confundir com uma contagem de casos."""
    valor = int(valor)
    return str(valor) if 0 < valor < 10 else valor


def ic(valores) -> list[float] | None:
    """IC 95% percentílico ignorando NaN (reamostras descartadas); None se não sobrou nada."""
    v = np.asarray(valores, dtype=float)
    v = v[np.isfinite(v)]
    if v.size == 0:
        return None
    lo, hi = np.quantile(v, QUANTIS_IC)
    return [float(lo), float(hi)]


def _finito(valor) -> float | None:
    if valor is None:
        return None
    valor = float(valor)
    return valor if np.isfinite(valor) else None


def com_ic(valor, valores) -> dict:
    """{"valor", "ic95"}; NaN/None vira None (o JSON não tem NaN)."""
    return {"valor": _finito(valor), "ic95": ic(valores)}


def num(valor: float | None, casas: int) -> str:
    if valor is None:
        return "—"
    return f"{valor:.{casas}f}".replace(".", ",")


def ic_txt(bloco: dict | None, casas: int) -> str:
    """"valor (inf; sup)"; "—" sem bloco; "valor (IC indisponível)" se o IC não saiu."""
    if bloco is None:
        return "—"
    if bloco.get("valor") is None:
        return "indisponível"
    if not bloco.get("ic95"):
        return f"{num(bloco['valor'], casas)} (IC indisponível)"
    lo, hi = bloco["ic95"]
    return f"{num(bloco['valor'], casas)} ({num(lo, casas)}; {num(hi, casas)})"


def _tabela_md(cabecalho: list[str], linhas: list[list[str]]) -> list[str]:
    return ["| " + " | ".join(cabecalho) + " |", "|" + "---|" * len(cabecalho),
            *("| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas)]


tabela_md = _tabela_md  # uso público (os módulos das análises seguintes montam o markdown igual)


# --- Curva de decisão (D-39) -----------------------------------------------------------------

def grade_de_limiares(cfg: dict) -> np.ndarray:
    """`dca_limiares` do config: `passos` pontos igualmente espaçados de `min` a `max`."""
    c = cfg["dca_limiares"]
    return np.linspace(float(c["min"]), float(c["max"]), int(c["passos"]))


@dataclass(frozen=True)
class ResultadoDecisao:
    """Curvas de net benefit por reamostra (`dist`, array (n, pontos)) e na amostra (`pontos`).

    `uniao`: grade + limiares marcados, em ordem crescente; `idx_grade` e `idx_marcados` dizem em
    que posição de `uniao` cada um está. `json`: o agregado que vai para o relatório.
    """

    uniao: np.ndarray
    idx_grade: np.ndarray
    idx_marcados: dict[str, int]
    pontos: dict[str, np.ndarray]
    dist: dict[str, np.ndarray]
    json: dict


def curva_de_decisao(y, probs: dict[str, np.ndarray], regra: np.ndarray, grade: np.ndarray,
                     marcados: dict[str, float], *, seed: int, n: int,
                     nome_regra: str = "B2") -> ResultadoDecisao:
    """Net benefit (D-39) de cada modelo em `probs` (risco = a própria predição), da `regra`
    (decisão binária: as contagens são as mesmas em todo limiar) e de "tratar todos"/"ninguém".

    NB(t) = VP/n − FP/n × t/(1 − t), com "tratar" = risco ≥ t. `marcados`: limiares de operação
    (nome -> t) cujo NB também sai, com banda. Bandas: bootstrap estratificado por alvo, `n`
    reamostras, os MESMOS sorteios para todos os modelos e para a regra.
    """
    y_arr = np.asarray(y).astype(np.int64)
    grade = np.asarray(grade, dtype=float)
    if grade.ndim != 1 or grade.size == 0 or np.any((grade <= 0) | (grade >= 1)):
        raise ValueError("a grade de limiares precisa estar em (0, 1)")
    if n < 1:
        raise ValueError("n: pelo menos uma reamostra")
    # Limiares de operação fora de (0, 1) não têm net benefício definido: ficam sem ponto.
    no_dominio = {nome: t for nome, t in marcados.items() if 0.0 < t < 1.0}
    uniao = np.unique(np.concatenate([grade, list(no_dominio.values())]))
    idx_grade = np.searchsorted(uniao, grade)
    idx_marcados = {nome: int(np.searchsorted(uniao, t)) for nome, t in no_dominio.items()}
    razao = uniao / (1.0 - uniao)

    # Faixa de limiar de cada linha: nº de pontos de `uniao` <= risco (p >= u_j  <=>  faixa > j).
    faixas = {nome: np.searchsorted(uniao, np.asarray(p, dtype=float),
                                    side="right").astype(np.int16)
              for nome, p in probs.items()}
    celulas = metrics.agrupar_celulas(
        y_arr, {**faixas, nome_regra: np.asarray(regra, dtype=bool)})
    positivas = celulas.y == 1
    k_todas = {nome: celulas.colunas[nome].astype(np.int64) for nome in probs}
    k_pos = {nome: k[positivas] for nome, k in k_todas.items()}
    flag = celulas.colunas[nome_regra].astype(np.float64)
    n_pontos = len(uniao)

    def net_benefit(w: np.ndarray) -> dict[str, np.ndarray]:
        total = float(w.sum())
        saida: dict[str, np.ndarray] = {}
        w_pos = w[positivas]
        for nome in probs:
            vp_faixa = np.bincount(k_pos[nome], weights=w_pos, minlength=n_pontos + 1)
            todos_faixa = np.bincount(k_todas[nome], weights=w, minlength=n_pontos + 1)
            # casos com risco >= u_j são os de faixa >= j + 1: soma de sufixo.
            vp = np.cumsum(vp_faixa[::-1])[::-1][1:n_pontos + 1]
            marcados_j = np.cumsum(todos_faixa[::-1])[::-1][1:n_pontos + 1]
            saida[nome] = vp / total - (marcados_j - vp) / total * razao
        vp_regra = float(np.dot(w[positivas], flag[positivas]))
        fp_regra = float(np.dot(w, flag)) - vp_regra
        saida[nome_regra] = vp_regra / total - fp_regra / total * razao
        prevalencia = float(w_pos.sum()) / total
        saida["tratar_todos"] = prevalencia - (1.0 - prevalencia) * razao
        return saida

    pontos = net_benefit(celulas.contagem.astype(np.float64))
    sorteio = metrics.Sorteio(celulas.contagem, celulas.n_negativas)
    sementes = metrics.sementes_das_reamostras(seed, n)
    dist = {nome: np.empty((n, n_pontos)) for nome in pontos}
    for k, semente in enumerate(sementes):
        nb = net_benefit(sorteio(metrics.fluxo(semente, FLUXO_DECISAO)))
        for nome, v in nb.items():
            dist[nome][k] = v
    return ResultadoDecisao(uniao=uniao, idx_grade=idx_grade, idx_marcados=idx_marcados,
                            pontos=pontos, dist=dist, json={})


def decisao_em_json(res: ResultadoDecisao, grade: np.ndarray, marcados: dict[str, float], n: int,
                    nome_regra: str, fontes: dict[str, str]) -> dict:
    """Agregado da curva de decisão para o relatório (listas de floats; sem NaN)."""
    curvas: dict[str, dict] = {}
    for nome, valores in res.pontos.items():
        if nome == "tratar_todos":
            continue
        banda = np.quantile(res.dist[nome][:, res.idx_grade], QUANTIS_IC, axis=0)
        curvas[nome] = {"nb": [float(v) for v in valores[res.idx_grade]],
                        "ic_inf": [float(v) for v in banda[0]],
                        "ic_sup": [float(v) for v in banda[1]]}
    pontos_marcados: dict[str, dict] = {}
    for nome, t in marcados.items():
        if nome in res.idx_marcados:
            j = res.idx_marcados[nome]
            bloco = com_ic(res.pontos["M1"][j], res.dist["M1"][:, j])
            pontos_marcados[nome] = {"limiar": float(t), "modelo": "M1", "nb": bloco,
                                     "dentro_da_faixa": bool(grade.min() <= t <= grade.max()),
                                     "fonte": fontes.get(nome)}
        else:
            pontos_marcados[nome] = {"limiar": float(t), "modelo": "M1", "nb": None,
                                     "dentro_da_faixa": False, "fonte": fontes.get(nome),
                                     "motivo": "limiar fora de (0, 1): net benefit não definido"}
    return {
        "reamostras": int(n),
        "limiares": [float(t) for t in grade],
        "curvas": curvas,
        "tratar_todos": {"nb": [float(v) for v in res.pontos["tratar_todos"][res.idx_grade]],
                         "ic95": None,
                         "nota": "a reamostra é estratificada por alvo: a prevalência é fixa e "
                                 "'tratar todos' não tem banda"},
        "tratar_ninguem": {"nb": [0.0] * len(grade)},
        "regra": nome_regra,
        "pontos_marcados": pontos_marcados,
    }


def tabela_decisao(json_decisao: dict) -> pd.DataFrame:
    """Uma linha por limiar: NB de cada curva, com a banda, mais "tratar todos" e "ninguém"."""
    quadro: dict[str, list] = {"limiar": json_decisao["limiares"]}
    for nome, curva in json_decisao["curvas"].items():
        quadro[f"nb_{nome}"] = curva["nb"]
        quadro[f"nb_{nome}_inf"] = curva["ic_inf"]
        quadro[f"nb_{nome}_sup"] = curva["ic_sup"]
    quadro["nb_tratar_todos"] = json_decisao["tratar_todos"]["nb"]
    quadro["nb_tratar_ninguem"] = json_decisao["tratar_ninguem"]["nb"]
    return pd.DataFrame(quadro)


def markdown_decisao(j: dict) -> str:
    lim = j["limiares"]
    linhas = [
        "## Curva de decisão (net benefit, D-39)",
        "",
        f"Limiares de risco de {num(100 * lim[0], 1)}% a {num(100 * lim[-1], 1)}% "
        f"({len(lim)} pontos), com banda de IC 95% por bootstrap ({j['reamostras']} reamostras "
        "estratificadas por alvo, os mesmos sorteios para M1, B1 e a regra B2). M1 usa a "
        "probabilidade calibrada; B1, a predição bruta como risco. A regra B2 é uma decisão "
        "binária: tem as mesmas contagens de VP e FP em todo limiar. “Tratar todos” não tem banda "
        "porque a prevalência é fixa na reamostra estratificada.",
        "",
        "Net benefit em alguns limiares (a curva inteira está em `metricas.json` e no CSV):",
        "",
    ]
    escolhidos = sorted({0, len(lim) // 4, len(lim) // 2, (3 * len(lim)) // 4, len(lim) - 1})
    cab = ["Limiar", *(f"NB {nome}" for nome in j["curvas"]), "NB tratar todos"]
    corpo = []
    for i in escolhidos:
        corpo.append([f"{num(100 * lim[i], 2)}%",
                      *(f"{num(c['nb'][i], 6)} ({num(c['ic_inf'][i], 6)}; {num(c['ic_sup'][i], 6)})"
                        for c in j["curvas"].values()),
                      num(j["tratar_todos"]["nb"][i], 6)])
    linhas += _tabela_md(cab, corpo)
    linhas += ["", "Limiares de operação do M1 marcados na curva:", ""]
    corpo = []
    for nome, ponto in j["pontos_marcados"].items():
        fora = "" if ponto["dentro_da_faixa"] else " (fora do intervalo da curva)"
        corpo.append([nome, f"{num(ponto['limiar'], 6)}{fora}",
                      ic_txt(ponto["nb"], 6), ponto.get("fonte") or "—"])
    linhas += _tabela_md(["Ponto", "Limiar", "NB (IC 95%)", "Fonte do limiar"], corpo)
    linhas += ["", "O limiar principal é o congelado com o modelo (recall ≥ B2, D-92). O limiar "
                   "F2 é o ponto secundário (D-33) e vem do `selecao.json` da T-4.9; não é parte "
                   "do modelo congelado.", ""]
    return "\n".join(linhas)


# --- Calibração por caixas com bandas --------------------------------------------------------

@dataclass(frozen=True)
class ResultadoCalibracao:
    """Calibração por caixas de cada modelo. `dist[modelo]`: array (n, caixas) com a taxa observada
    de cada caixa em cada reamostra (NaN se a caixa ficou vazia). A caixa de cada linha não é
    guardada (R7); ficam as contagens e médias da amostra."""

    cortes: dict[str, np.ndarray]
    n_caixa: dict[str, np.ndarray]
    eventos_caixa: dict[str, np.ndarray]
    previsto_medio: dict[str, np.ndarray]
    dist: dict[str, np.ndarray]


def caixas_por_quantis(p: np.ndarray, caixas: int) -> tuple[np.ndarray, np.ndarray]:
    """(cortes, caixa de cada linha). Os cortes são quantis interiores tomados entre os VALORES de
    `p` (`inverted_cdf`, sem interpolar): assim nenhuma caixa fica vazia, e linhas empatadas no
    mesmo valor ficam na mesma caixa (o nº de caixas pode ser menor que o pedido). Caixa 0 = menor
    risco; a caixa é o nº de cortes <= p."""
    p = np.asarray(p, dtype=float)
    if caixas < 1:
        raise ValueError("caixas: pelo menos uma")
    cortes = np.unique(np.quantile(p, np.linspace(0.0, 1.0, caixas + 1)[1:-1],
                                   method="inverted_cdf"))
    if cortes.size and cortes[0] <= p.min():  # o 1º corte é o mínimo: a caixa 0 ficaria vazia
        cortes = cortes[1:]
    return cortes, np.searchsorted(cortes, p, side="right").astype(np.int16)


def calibracao_por_caixas(y, probs: dict[str, np.ndarray], *, caixas: int, seed: int,
                          n: int) -> ResultadoCalibracao:
    """Taxa observada por caixa com banda (bootstrap de `n` reamostras estratificadas por alvo).

    Cada reamostra sorteia, por classe, os pesos das células (alvo, caixa de cada modelo); os
    modelos compartilham o sorteio. A taxa da caixa é Σw·y / Σw na caixa.
    """
    y_arr = np.asarray(y).astype(np.int64)
    if n < 1:
        raise ValueError("n: pelo menos uma reamostra")
    cortes, caixa = {}, {}
    for nome, p in probs.items():
        cortes[nome], caixa[nome] = caixas_por_quantis(p, caixas)
    celulas = metrics.agrupar_celulas(y_arr, caixa)
    positivas = celulas.y == 1
    n_caixa, eventos, previsto = {}, {}, {}
    para_taxa: dict[str, tuple[np.ndarray, np.ndarray, int]] = {}
    for nome, p in probs.items():
        k = len(cortes[nome]) + 1
        n_caixa[nome] = np.bincount(caixa[nome], minlength=k).astype(np.int64)
        eventos[nome] = np.bincount(caixa[nome], weights=y_arr, minlength=k).astype(np.int64)
        soma = np.bincount(caixa[nome], weights=np.asarray(p, dtype=float), minlength=k)
        previsto[nome] = soma / np.maximum(n_caixa[nome], 1)
        para_taxa[nome] = (celulas.colunas[nome].astype(np.int64), positivas, k)

    def taxas(w: np.ndarray) -> dict[str, np.ndarray]:
        saida = {}
        for nome, (k_cel, pos, k) in para_taxa.items():
            w1 = np.bincount(k_cel[pos], weights=w[pos], minlength=k)
            w_todos = np.bincount(k_cel, weights=w, minlength=k)
            saida[nome] = np.divide(w1, w_todos, out=np.full(k, np.nan), where=w_todos > 0)
        return saida

    sorteio = metrics.Sorteio(celulas.contagem, celulas.n_negativas)
    sementes = metrics.sementes_das_reamostras(seed, n)
    dist = {nome: np.empty((n, len(cortes[nome]) + 1)) for nome in probs}
    for r, semente in enumerate(sementes):
        t = taxas(sorteio(metrics.fluxo(semente, FLUXO_CALIBRACAO)))
        for nome, v in t.items():
            dist[nome][r] = v
    return ResultadoCalibracao(cortes=cortes, n_caixa=n_caixa, eventos_caixa=eventos,
                               previsto_medio=previsto, dist=dist)


def calibracao_em_json(res: ResultadoCalibracao, n: int, globais: dict[str, dict]) -> dict:
    """Agregado por modelo: caixas (R7: n e eventos de 1 a 9 viram "<10" e a taxa daquela caixa não
    sai) e as métricas globais da T-5.1 (`globais`: slope, intercepto e obs/esp com IC)."""
    modelos: dict[str, dict] = {}
    for nome in res.n_caixa:
        linhas = []
        for b in range(len(res.n_caixa[nome])):
            casos, eventos = int(res.n_caixa[nome][b]), int(res.eventos_caixa[nome][b])
            suprimida = 0 < eventos < 10 or 0 < casos < 10
            avisos = []
            if eventos < MIN_EVENTOS_AVISO:
                avisos.append("menos de 100 eventos na caixa: banda larga")
            bloco = {
                "caixa": f"C{b + 1:02d}",
                "n": celula(casos),
                "eventos": celula(eventos),
                "risco_previsto_medio": float(res.previsto_medio[nome][b]),
                "taxa_observada": None if suprimida else (eventos / casos if casos else None),
                "ic95": None if suprimida else ic(res.dist[nome][:, b]),
                "aviso": "; ".join(avisos) or None,
            }
            if suprimida:
                bloco["motivo"] = "caixa com 1 a 9 eventos ou casos: taxa suprimida (R7)"
            linhas.append(bloco)
        modelos[nome] = {"global": globais.get(nome, {}), "caixas": linhas}
    return {
        "reamostras": int(n),
        "caixas_pedidas": CAIXAS_CALIBRACAO,
        "metodo": "caixas por quantis do risco previsto de cada modelo; taxa observada por caixa "
                  "com banda de bootstrap estratificado por alvo (mesmos sorteios para M1 e E1)",
        "modelos": modelos,
    }


def tabelas_calibracao(j: dict) -> dict[str, pd.DataFrame]:
    tabelas = {}
    for nome, m in j["modelos"].items():
        linhas = []
        for c in m["caixas"]:
            lo, hi = c["ic95"] if c["ic95"] else (None, None)
            linhas.append({"caixa": c["caixa"], "n": c["n"], "eventos": c["eventos"],
                           "risco_previsto_medio": c["risco_previsto_medio"],
                           "taxa_observada": c["taxa_observada"], "ic_inf": lo, "ic_sup": hi,
                           "aviso": c["aviso"] or ""})
        tabelas[f"calibracao_{nome}"] = pd.DataFrame(linhas)
    return tabelas


def markdown_calibracao(j: dict) -> str:
    linhas = [
        "## Calibração por caixas, com bandas (D-39)",
        "",
        f"Caixas por quantis do risco previsto ({j['caixas_pedidas']} pedidas: com ~11 mil eventos "
        "em 5,3 milhões de casos, cada caixa tem, em média, bem mais que os 100 eventos que o "
        "spec pede, e as de menor risco ainda ficam perto disso; com mais caixas as de baixo risco "
        "teriam banda larga demais). Banda de IC 95% da taxa observada por bootstrap "
        f"({j['reamostras']} reamostras, estratificadas por alvo, mesmos sorteios para M1 e E1). "
        "Caixas com menos de 100 eventos têm aviso; com 1 a 9 eventos a taxa é suprimida (R7).",
        "",
    ]
    for nome, m in j["modelos"].items():
        g = m["global"]
        linhas += [f"### {nome}", ""]
        if g:
            linhas += [f"Globais (da avaliação de métricas): slope {ic_txt(g.get('slope'), 3)}; "
                       f"intercepto {ic_txt(g.get('intercepto'), 3)}; observado/esperado "
                       f"{ic_txt(g.get('obs_esp'), 3)}.", ""]
        corpo = [[c["caixa"], c["n"], c["eventos"], num(c["risco_previsto_medio"], 6),
                  ic_txt({"valor": c["taxa_observada"], "ic95": c["ic95"]}, 6)
                  if c["taxa_observada"] is not None else "suprimida (R7)", c["aviso"] or ""]
                 for c in m["caixas"]]
        linhas += _tabela_md(["Caixa", "Casos", "Eventos", "Risco previsto médio",
                              "Taxa observada (IC 95%)", "Aviso"], corpo)
        linhas.append("")
    return "\n".join(linhas)


# --- Subgrupos (D-13, D-48) ------------------------------------------------------------------

@dataclass(frozen=True)
class Particao:
    """Uma dimensão de subgrupos: `rotulos` e o código (posição em `rotulos`) de cada linha;
    -1 = a linha não cabe em nenhum subgrupo (a partição fica marcada como incompleta)."""

    rotulos: tuple[str, ...]
    codigos: np.ndarray

    @property
    def completa(self) -> bool:
        return bool((self.codigos >= 0).all())


def rotulos_de_faixas(faixas) -> list[str]:
    """Rótulos das faixas etárias do config: [0, 5, 15] -> "0–4", "5–14", "15+"."""
    bordas = [int(b) for b in faixas]
    return [*(f"{a}–{b - 1}" for a, b in zip(bordas[:-1], bordas[1:], strict=True)),
            f"{bordas[-1]}+"]


def definir_particoes(df: pd.DataFrame, cfg: dict) -> dict[str, Particao]:
    """As cinco partições do spec (faixa etária, sexo, gestante, região, raça/cor). Lê de `df`:
    `idade_anos`, `CS_SEXO`, `gestante`, `regiao` e `CS_RACA` (os dois últimos nunca são feature:
    D-21, D-48). Sexo: F, M, I e em branco (o sexo "I" e o branco são subgrupos distintos).
    Raça/cor: as cinco categorias da ficha mais "Ignorado" (código 9, em branco ou fora do
    domínio)."""
    bordas = np.asarray(cfg["faixas"], dtype=float)
    idade = df["idade_anos"].to_numpy(dtype=float)
    faixa = np.searchsorted(bordas, idade, side="right") - 1
    faixa[~np.isfinite(idade)] = -1
    sexo_txt = code(df["CS_SEXO"]).fillna("").to_numpy(dtype=object)
    sexo = np.full(len(df), len(SEXOS) - 1, dtype=np.int64)
    for i, s in enumerate(SEXOS[:-1]):
        sexo[sexo_txt == s] = i
    gestante = np.where(df["gestante"].to_numpy() == 1, 0, 1)
    ordem = list(cfg["ordem_dobras"])
    regiao_cat = pd.Categorical(df["regiao"].astype("string"), categories=ordem)
    regiao = regiao_cat.codes.astype(np.int64)
    rotulos_regiao = tuple(ordem)
    if (regiao < 0).any():  # sem região (a UF e o município faltaram): subgrupo próprio
        regiao = np.where(regiao < 0, len(ordem), regiao)
        rotulos_regiao = (*ordem, SEM_REGIAO)
    raca_txt = code(df["CS_RACA"]).map(RACA_ROTULOS).fillna(NIVEIS_RACA[-1])
    raca = pd.Categorical(raca_txt, categories=NIVEIS_RACA).codes.astype(np.int64)
    return {
        "faixa_etaria": Particao(tuple(rotulos_de_faixas(cfg["faixas"])), faixa.astype(np.int64)),
        "sexo": Particao(SEXOS, sexo),
        "gestante": Particao(GESTANTE_ROTULOS, gestante.astype(np.int64)),
        "regiao": Particao(rotulos_regiao, regiao),
        "raca_cor": Particao(tuple(NIVEIS_RACA), raca),
    }


def aviso_de_subgrupo(dimensao: str, rotulo: str, eventos: int) -> str | None:
    """Aviso de IC largo: por nome (os do spec) e pela regra geral (< 100 eventos)."""
    motivos = []
    if (dimensao, rotulo) in SUBGRUPOS_COM_AVISO_NOMEADO:
        motivos.append("subgrupo com poucos eventos apontado no spec")
    if eventos < MIN_EVENTOS_AVISO:
        motivos.append(f"menos de {MIN_EVENTOS_AVISO} eventos")
    return f"{AVISO_IC_LARGO} ({'; '.join(motivos)})" if motivos else None


def _calibracao_do_subgrupo(ponto: dict, dist: dict[str, np.ndarray], n_reamostras: int) -> dict:
    """Slope, intercepto e obs/esp do subgrupo, com a política de reamostras descartadas."""
    descartadas = int(np.nansum(dist["M1/calibracao_descartada"]))
    fracao = descartadas / n_reamostras
    ic_disponivel = fracao <= LIMITE_DESCARTE
    indisponivel = bool(ponto.get("calibracao_indisponivel"))

    def bloco(chave: str) -> dict:
        valor = ponto.get(chave)
        if chave == "slope" and valor is None and not indisponivel:
            return {"valor": None, "ic95": None,
                    "motivo": "previsão constante no subgrupo: o slope não é definido"}
        if valor is None:
            return {"valor": None, "ic95": None,
                    "motivo": "indisponível: o ajuste da amostra do subgrupo não convergiu"}
        if f"M1/{chave}" not in dist:
            return {"valor": _finito(valor), "ic95": None, "motivo": "sem reamostras"}
        if not ic_disponivel:
            return {"valor": _finito(valor), "ic95": None,
                    "motivo": f"IC indisponível: mais de {int(LIMITE_DESCARTE * 100)}% das "
                              "reamostras sem convergência"}
        return com_ic(valor, dist[f"M1/{chave}"])

    return {"slope": bloco("slope"), "intercepto": bloco("intercepto"),
            "obs_esp": com_ic(ponto["obs_esp"], dist["M1/obs_esp"]),
            "reamostras_descartadas": contagem_de_reamostras(descartadas),
            "fracao_descartada": float(fracao)}


def _metricas_do_subgrupo(ponto: dict, lim: dict, dist: dict[str, np.ndarray],
                          n_reamostras: int) -> dict:
    return {
        "pr_auc": com_ic(ponto["pr_auc"], dist["M1/pr_auc"]),
        "recall": com_ic(lim["M1"]["recall"], dist["M1/limiar_recall"]),
        "precisao": com_ic(lim["M1"]["precisao"], dist["M1/limiar_precisao"]),
        "regra_b2_recall": com_ic(lim["B2"]["recall"], dist["B2/limiar_recall"]),
        "regra_b2_precisao": com_ic(lim["B2"]["precisao"], dist["B2/limiar_precisao"]),
        "calibracao": _calibracao_do_subgrupo(ponto, dist, n_reamostras),
    }


metricas_do_subgrupo = _metricas_do_subgrupo  # uso público (T-5.3 reaproveita a política)


def estado_do_subgrupo(y_sub, p_sub, regra_sub, limiar_m1: float,
                       fluxo_base: int) -> tuple[metrics.Reamostrador, dict, dict]:
    """Estado do bootstrap de um subgrupo: M1 (escore e flag no limiar principal) e a regra B2.
    Modo tolerante e sem ROC/Brier (ver `metrics.Reamostrador`); estratificado por alvo."""
    return metrics.montar_estado(
        y_sub, {"M1": p_sub}, {"M1": p_sub >= limiar_m1, "B2": regra_sub},
        completo=False, tolerante=True, fluxo_base=fluxo_base)


def analisar_subgrupos(df: pd.DataFrame, y, p_m1, regra_b2, limiar_m1: float, cfg: dict, *,
                       seed: int, n: int, processos: int | None) -> dict:
    """Métricas do M1 (e recall e precisão da regra B2) em cada subgrupo, com bootstrap DENTRO do
    subgrupo. Devolve o agregado do relatório (ver o topo do módulo para a política de descarte).

    Subgrupo com menos de `MIN_EVENTOS_METRICAS` eventos (ou sem não eventos) sai sem métricas.
    Todos os subgrupos com métricas compartilham o mesmo conjunto de processos e as mesmas
    sub-sementes; cada um usa o seu fluxo (`FLUXO_SUBGRUPOS + 2 × posição`).
    """
    y_arr = np.asarray(y).astype(np.int64)
    p = np.asarray(p_m1, dtype=float)
    regra = np.asarray(regra_b2, dtype=bool)
    particoes = definir_particoes(df, cfg)
    estados: dict[str, tuple] = {}
    pontos: dict[str, tuple[dict, dict]] = {}
    blocos: dict[str, dict[str, dict]] = {}
    chaves: dict[tuple[str, str], str] = {}
    ordinal = 0
    for dimensao in DIMENSOES:
        particao = particoes[dimensao]
        blocos[dimensao] = {}
        for codigo, rotulo in enumerate(particao.rotulos):
            indices = np.flatnonzero(particao.codigos == codigo)
            casos, eventos = len(indices), int(y_arr[indices].sum())
            bloco = {
                "n": celula(casos), "eventos": celula(eventos),
                "prevalencia": (eventos / casos if casos and (eventos == 0 or eventos >= 10)
                                else None),
                "aviso_ic_largo": aviso_de_subgrupo(dimensao, rotulo, eventos),
                "metricas": None,
            }
            blocos[dimensao][rotulo] = bloco
            if eventos < MIN_EVENTOS_METRICAS:
                bloco["motivo_sem_metricas"] = (
                    f"menos de {MIN_EVENTOS_METRICAS} eventos: sem métricas (R7)")
            elif casos - eventos == 0:
                bloco["motivo_sem_metricas"] = "sem não eventos: as métricas não são definidas"
            else:
                chave = f"s{ordinal:03d}"
                chaves[(dimensao, rotulo)] = chave
                estados[chave] = estado_do_subgrupo(
                    y_arr[indices], p[indices], regra[indices], limiar_m1,
                    FLUXO_SUBGRUPOS + 2 * ordinal)
                pontos[chave] = estados[chave][0].pontos()
            ordinal += 1
    sementes = metrics.sementes_das_reamostras(seed, n)
    dist = metrics.rodar_varios(estados, sementes, processos_efetivos(processos, n))
    for (dimensao, rotulo), chave in chaves.items():
        colunas, _ = dist[chave]
        ponto, lim = pontos[chave][0]["M1"], pontos[chave][1]
        blocos[dimensao][rotulo]["metricas"] = _metricas_do_subgrupo(ponto, lim, colunas, n)
    dimensoes = {}
    total = len(df)
    for dimensao in DIMENSOES:
        particao = particoes[dimensao]
        coberta = sum(int((particao.codigos == c).sum()) for c in range(len(particao.rotulos)))
        dimensoes[dimensao] = {"nome": NOMES_DIMENSOES[dimensao],
                               "particao_completa": bool(coberta == total and particao.completa),
                               "ordem": list(particao.rotulos),  # o JSON grava as chaves ordenadas
                               "subgrupos": blocos[dimensao]}
    return {"reamostras": int(n), "limiar_m1": float(limiar_m1),
            "politica_descarte": POLITICA_DESCARTE, "limite_descarte": LIMITE_DESCARTE,
            "min_eventos_metricas": MIN_EVENTOS_METRICAS, "min_eventos_aviso": MIN_EVENTOS_AVISO,
            "legenda": LEGENDA_SUBGRUPOS, "ordem_dimensoes": list(DIMENSOES),
            "dimensoes": dimensoes}


def processos_efetivos(processos: int | None, n: int) -> int:
    """Nº de processos do bootstrap (None = todos os núcleos), entre 1 e `n` reamostras. Fica fora
    do JSON: o resultado não depende dele."""
    disponivel = os.cpu_count() or 1
    return max(1, min(int(disponivel if processos is None else processos), n))


def tabela_subgrupos(j: dict) -> pd.DataFrame:
    """Uma linha por subgrupo (colunas escalares: viram CSV sem listas)."""
    linhas = []
    for dimensao, d in j["dimensoes"].items():
        for rotulo, s in d["subgrupos"].items():
            linha = {"dimensao": dimensao, "subgrupo": rotulo, "n": s["n"],
                     "eventos": s["eventos"], "prevalencia": s["prevalencia"],
                     "aviso_ic_largo": s["aviso_ic_largo"] or ""}
            m = s["metricas"]
            for chave in ("pr_auc", "recall", "precisao", "regra_b2_recall",
                          "regra_b2_precisao"):
                v = m[chave] if m else None
                linha[chave] = v["valor"] if v else None
                linha[f"{chave}_inf"] = v["ic95"][0] if v and v["ic95"] else None
                linha[f"{chave}_sup"] = v["ic95"][1] if v and v["ic95"] else None
            cal = m["calibracao"] if m else None
            for chave in ("slope", "intercepto", "obs_esp"):
                v = cal[chave] if cal else None
                linha[chave] = v["valor"] if v else None
                linha[f"{chave}_inf"] = v["ic95"][0] if v and v.get("ic95") else None
                linha[f"{chave}_sup"] = v["ic95"][1] if v and v.get("ic95") else None
            linha["reamostras_descartadas"] = cal["reamostras_descartadas"] if cal else None
            linhas.append(linha)
    return pd.DataFrame(linhas)


def markdown_subgrupos(j: dict) -> str:
    linhas = [
        "## Subgrupos (D-13, D-48)",
        "",
        f"> **{j['legenda']}**",
        "",
        f"Métricas do M1 no limiar principal ({num(j['limiar_m1'], 6)}), com IC 95% por bootstrap "
        f"DENTRO de cada subgrupo ({j['reamostras']} reamostras, estratificadas por alvo, semente "
        "do config); recall e precisão da regra B2 no mesmo subgrupo como referência. Subgrupo com "
        f"menos de {j['min_eventos_metricas']} eventos sai sem métricas e célula de 1 a 9 aparece "
        f"como <10 (R7). Aviso de IC largo: os subgrupos que o spec nomeia e todos com menos de "
        f"{j['min_eventos_aviso']} eventos.",
        "",
        f"**Política de reamostras sem convergência (decisão provisória).** "
        f"{j['politica_descarte']}",
        "",
    ]
    for d in j["dimensoes"].values():
        corpo, calib = [], []
        for rotulo, s in d["subgrupos"].items():
            m = s["metricas"]
            prev = "—" if s["prevalencia"] is None else num(100 * s["prevalencia"], 3) + "%"
            corpo.append([
                rotulo, s["n"], s["eventos"], prev,
                ic_txt(m["pr_auc"], 4) if m else "sem métricas",
                ic_txt(m["recall"], 3) if m else "—", ic_txt(m["precisao"], 4) if m else "—",
                ic_txt(m["regra_b2_recall"], 3) if m else "—",
                ic_txt(m["regra_b2_precisao"], 4) if m else "—",
                s["aviso_ic_largo"] or ""])
            if m:
                c = m["calibracao"]
                calib.append([rotulo, ic_txt(c["slope"], 3), ic_txt(c["intercepto"], 3),
                              ic_txt(c["obs_esp"], 3), c["reamostras_descartadas"]])
        linhas += [f"### {d['nome']}", ""]
        if not d["particao_completa"]:
            linhas += ["**Atenção: a partição não cobre todos os casos.**", ""]
        linhas += _tabela_md(["Subgrupo", "Casos", "Eventos", "Prevalência", "PR-AUC M1 (IC)",
                              "Recall M1 (IC)", "Precisão M1 (IC)", "Recall B2 (IC)",
                              "Precisão B2 (IC)", "Aviso"], corpo)
        if calib:
            linhas += ["", "Calibração do M1 no subgrupo:", ""]
            linhas += _tabela_md(["Subgrupo", "Slope (IC)", "Intercepto (IC)",
                                  "Observado/esperado (IC)", "Reamostras descartadas"], calib)
        linhas.append("")
    return "\n".join(linhas)
