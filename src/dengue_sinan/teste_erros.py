"""Análise de erros do M1 no teste (T-5.3, D-93; R1, R7, R8).

Funções puras sobre arrays e o DataFrame de features: não leem dado, não gravam arquivo e não
importam `evaluate` (é `evaluate` que as registra como `Analise`). Nada devolve linha individual
(R7): só contagens (1 a 9 viram "<10"), proporções, quantis e métricas com IC.

Três partes:

1. **Falsos negativos de maior risco** (`[ASSUMPTION]` do spec). São os eventos (y = 1) cujo risco
   calibrado do M1 fica abaixo do limiar principal congelado (D-92). Ordena-se do maior para o
   menor risco previsto e ficam os `N_FALSOS_NEGATIVOS` primeiros. **Empate:** vence a linha que
   vem antes na ordem de `df` (ordenação estável: no teste, a ordem do arquivo de 2024). Cada
   dimensão do perfil (faixa etária, sexo, gestante, nº de comorbidades, cada comorbidade, região
   e atraso até a notificação) é descrita em agregados e comparada com a de TODOS os eventos e a
   dos eventos detectados (verdadeiros positivos). O risco previsto do grupo sai por quantis (1%,
   mediana, 99%), nunca o valor de um caso. Com menos de `MIN_PERFIL` falsos negativos, o perfil
   não é publicado.

2. **Calibração por célula de comorbidade**: cada uma das 7 comorbidades (= Sim) e o nº de
   comorbidades (0, 1, 2, 3+). Observado/esperado e calibration-in-the-large (intercepto com
   offset logit(p)), com IC por bootstrap estratificado DENTRO da célula. As células se sobrepõem
   (quem tem duas comorbidades está em duas células): não são partição. Ordem: do maior desvio
   abs(ln(observado/esperado)) ao menor; células com menos de `ta.MIN_EVENTOS_METRICAS` eventos
   saem sem métricas. A política de reamostras sem convergência do ajuste é a da T-5.2
   (`teste_analises.POLITICA_DESCARTE`); o slope aparece como informação extra, com a mesma
   política.

3. **Espírito Santo à parte**: o estado usa outro sistema de origem (data-model › Espírito Santo).
   O ES é identificado pela UF de RESIDÊNCIA (município de residência; na falta dele, a UF), o
   mesmo critério da região; a UF de notificação não é lida. Métricas do M1 no ES e no resto do
   Brasil (PR-AUC, recall e precisão no limiar principal, observado/esperado) com IC, mais a taxa
   de eventos.

**Bootstrap (R8).** `metrics.rodar_varios`, um só conjunto de processos para todas as células e os
dois grupos. Cada célula tem o seu fluxo da sub-semente: `FLUXO_ERROS + 2 × posição` (cada estado
usa dois fluxos: escores e limiares). Os fluxos 0 e 1 são os da T-5.1; 2 e 3, os da curva de
decisão e da calibração; 10 em diante, os subgrupos; 100 em diante, esta análise (a dos critérios
reusa o 1, de propósito: ver `teste_criterios`). O resultado é o mesmo com 1, 2, 4 ou 8 processos.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from dengue_sinan import metrics
from dengue_sinan import teste_analises as ta
from dengue_sinan.profiling import COMORBIDADES, code, optional

N_FALSOS_NEGATIVOS = 100  # [ASSUMPTION] do spec: os 100 falsos negativos de maior risco previsto
MIN_PERFIL = 10  # R7: com menos falsos negativos que isso o perfil não é publicado
FLUXO_ERROS = 100
COD_UF_ES = "32"  # código IBGE da UF do Espírito Santo
PADRAO_IBGE = r"[1-5]\d(\d{4,5})?"  # o mesmo de `features.region_from_ibge`
QUANTIS_RISCO = (0.01, 0.5, 0.99)
ROTULOS_QUANTIS = ("q01", "mediana", "q99")
DIAS_BORDAS = (0, 2, 4, 7, 15)  # faixas do atraso até a notificação: 0–1, 2–3, 4–6, 7–14, 15+
SEM_DATA = "sem data"
ROTULOS_COMORBIDADES = ("0", "1", "2", "3+")
ROTULOS_CELULAS_N = ("0 comorbidades", "1 comorbidade", "2 comorbidades", "3 ou mais comorbidades")
GRUPOS_PERFIL = ("fn", "eventos", "detectados")
NOMES_GRUPOS = {"fn": "Falsos negativos de maior risco", "eventos": "Todos os eventos",
                "detectados": "Eventos detectados"}
CRITERIO_SELECAO = ("eventos (y = 1) com risco calibrado do M1 abaixo do limiar principal "
                    "congelado (D-92), do maior para o menor risco previsto")
REGRA_EMPATE = "empate de risco previsto: vence a linha que vem antes na ordem dos dados"
CRITERIO_ES = ("UF de residência = Espírito Santo (código IBGE 32): município de residência e, na "
               "falta dele, a UF de residência (o mesmo critério da região)")
LEGENDA = ("Associação não é causa; diferenças de notificação não são diferenças de risco. Só "
           "agregados (R7): contagens de 1 a 9 aparecem como <10 e, nelas, a proporção também sai.")


# --- Falsos negativos de maior risco ---------------------------------------------------------

def selecionar_falsos_negativos(y, p, limiar: float,
                                n: int = N_FALSOS_NEGATIVOS) -> tuple[np.ndarray, int]:
    """(posições dos `n` falsos negativos de maior risco previsto, total de falsos negativos).

    Falso negativo: y = 1 e p < limiar. Ordem: risco previsto decrescente; empate pela posição
    (ordenação estável). Com menos de `n` falsos negativos devolve todos. As posições são só para o
    cálculo de agregados: nunca vão para o relatório.
    """
    y_arr = np.asarray(y).astype(np.int64)
    p_arr = np.asarray(p, dtype=float)
    candidatos = np.flatnonzero((y_arr == 1) & (p_arr < limiar))
    ordem = np.argsort(-p_arr[candidatos], kind="stable")
    return candidatos[ordem[:n]], int(candidatos.size)


@dataclass(frozen=True)
class DimensaoPerfil:
    """Uma dimensão do perfil: `codigos[i]` é a posição de `rotulos` da linha i (-1 = fora)."""

    chave: str
    nome: str
    rotulos: tuple[str, ...]
    codigos: np.ndarray


def numero_de_comorbidades(df: pd.DataFrame) -> np.ndarray:
    """Quantas das 7 comorbidades são "Sim" em cada linha (a definição de `n_comorbidades`)."""
    total = np.zeros(len(df), dtype=np.int64)
    for c in COMORBIDADES:
        total += (df[c] == "Sim").to_numpy(dtype=bool)
    return total


def codigos_de_atraso(dias) -> tuple[tuple[str, ...], np.ndarray]:
    """Faixas de `dias_ate_notificacao` (`DIAS_BORDAS`) mais "sem data" para valor ausente."""
    bordas = np.asarray(DIAS_BORDAS, dtype=float)
    rotulos = [f"{int(a)}–{int(b) - 1}" for a, b in zip(bordas[:-1], bordas[1:], strict=True)]
    rotulos.append(f"{int(bordas[-1])}+")
    valores = np.asarray(dias, dtype=float)
    codigos = np.clip(np.searchsorted(bordas, valores, side="right") - 1, 0, None)
    codigos = np.where(np.isfinite(valores), codigos, len(rotulos)).astype(np.int64)
    return (*rotulos, SEM_DATA), codigos


def dimensoes_do_perfil(df: pd.DataFrame, cfg: dict) -> list[DimensaoPerfil]:
    """As dimensões do perfil, nesta ordem: faixa etária, sexo, gestante, nº de comorbidades, cada
    comorbidade (só a categoria "Sim"), região e atraso. Faixas e região vêm do config."""
    particoes = ta.definir_particoes(df, cfg)
    n_com = numero_de_comorbidades(df)
    dimensoes = [
        DimensaoPerfil("faixa_etaria", ta.NOMES_DIMENSOES["faixa_etaria"],
                       particoes["faixa_etaria"].rotulos, particoes["faixa_etaria"].codigos),
        DimensaoPerfil("sexo", ta.NOMES_DIMENSOES["sexo"], particoes["sexo"].rotulos,
                       particoes["sexo"].codigos),
        DimensaoPerfil("gestante", ta.NOMES_DIMENSOES["gestante"], particoes["gestante"].rotulos,
                       particoes["gestante"].codigos),
        DimensaoPerfil("n_comorbidades", "Número de comorbidades", ROTULOS_COMORBIDADES,
                       np.minimum(n_com, 3)),
    ]
    for c in COMORBIDADES:
        dimensoes.append(DimensaoPerfil(
            f"comorbidade_{c}", f"Comorbidade {c}", ("Sim",),
            np.where((df[c] == "Sim").to_numpy(dtype=bool), 0, -1).astype(np.int64)))
    dimensoes.append(DimensaoPerfil("regiao", ta.NOMES_DIMENSOES["regiao"],
                                    particoes["regiao"].rotulos, particoes["regiao"].codigos))
    rotulos_atraso, codigos_atraso = codigos_de_atraso(df["dias_ate_notificacao"].to_numpy())
    dimensoes.append(DimensaoPerfil("atraso", "Atraso até a notificação (dias)", rotulos_atraso,
                                    codigos_atraso))
    return dimensoes


def perfil_em_agregados(dimensoes: list[DimensaoPerfil],
                        grupos: dict[str, np.ndarray]) -> list[dict]:
    """Uma linha por (dimensão, categoria) com, para cada grupo, a contagem e a proporção (%) do
    grupo. R7: contagem de 1 a 9 vira "<10" e a proporção daquela célula não sai.

    `grupos`: nome -> posições das linhas do grupo (nomes em `GRUPOS_PERFIL`).
    """
    tamanho = {g: int(len(idx)) for g, idx in grupos.items()}
    linhas = []
    for d in dimensoes:
        contagens = {}
        for g, idx in grupos.items():
            cod = d.codigos[idx]
            contagens[g] = np.bincount(cod[cod >= 0], minlength=len(d.rotulos))
        for k, rotulo in enumerate(d.rotulos):
            linha: dict = {"dimensao": d.nome, "categoria": rotulo}
            for g in grupos:
                c = int(contagens[g][k])
                linha[f"{g}_n"] = ta.celula(c)
                linha[f"{g}_pct"] = (None if (0 < c < 10 or tamanho[g] == 0)
                                     else 100.0 * c / tamanho[g])
            linhas.append(linha)
    return linhas


def _falsos_negativos(df, y_arr, p, limiar, cfg, n_pedido: int) -> dict:
    escolhidos, total = selecionar_falsos_negativos(y_arr, p, limiar, n_pedido)
    eventos = np.flatnonzero(y_arr == 1)
    detectados = eventos[p[eventos] >= limiar]
    publicado = len(escolhidos) >= MIN_PERFIL
    bloco: dict = {
        "criterio_selecao": CRITERIO_SELECAO, "regra_empate": REGRA_EMPATE,
        "limiar": float(limiar), "total": ta.celula(total),
        "eventos": ta.celula(len(eventos)), "detectados": ta.celula(len(detectados)),
        "n_perfil": ta.celula(len(escolhidos)), "perfil_publicado": bool(publicado),
        "risco_previsto": None, "perfil": [],
    }
    if not publicado:
        bloco["motivo_sem_perfil"] = (f"menos de {MIN_PERFIL} falsos negativos: perfil não "
                                      "publicado (R7)")
        return bloco
    q = np.quantile(p[escolhidos], QUANTIS_RISCO)
    bloco["risco_previsto"] = {nome: float(v) for nome, v in zip(ROTULOS_QUANTIS, q, strict=True)}
    bloco["perfil"] = perfil_em_agregados(
        dimensoes_do_perfil(df, cfg),
        {"fn": escolhidos, "eventos": eventos, "detectados": detectados})
    return bloco


# --- Células de comorbidade e Espírito Santo -------------------------------------------------

def celulas_de_comorbidade(df: pd.DataFrame) -> list[tuple[str, str, np.ndarray]]:
    """(chave, rótulo, máscara) das 7 comorbidades (= Sim) e do nº de comorbidades (0, 1, 2, 3+).
    As células se sobrepõem."""
    celulas = [(f"comorbidade_{c}", f"{c} = Sim", (df[c] == "Sim").to_numpy(dtype=bool))
               for c in COMORBIDADES]
    n_com = numero_de_comorbidades(df)
    for k, rotulo in enumerate(ROTULOS_COMORBIDADES):
        mascara = (n_com >= 3) if k == 3 else (n_com == k)
        celulas.append((f"n_comorbidades_{rotulo}", ROTULOS_CELULAS_N[k], mascara))
    return celulas


def codigo_uf_residencia(df: pd.DataFrame) -> pd.Series:
    """Código IBGE (2 dígitos) da UF de residência: o do município (`ID_MN_RESI`) e, se ele faltar
    ou for malformado, o da UF (`SG_UF`). Falta nas duas = NA."""

    def _dois(coluna: str) -> pd.Series:
        texto = code(optional(df, coluna))
        bem_formado = texto.str.fullmatch(PADRAO_IBGE).fillna(False).astype(bool)
        return texto.where(bem_formado).str[:2]

    return _dois("ID_MN_RESI").combine_first(_dois("SG_UF"))


def mascara_espirito_santo(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """(é do ES, UF conhecida), por linha, pela UF de residência (`CRITERIO_ES`)."""
    uf = codigo_uf_residencia(df)
    return ((uf == COD_UF_ES).fillna(False).to_numpy(dtype=bool),
            uf.notna().to_numpy(dtype=bool))


def _aviso(eventos: int) -> str | None:
    return (f"{ta.AVISO_IC_LARGO} (menos de {ta.MIN_EVENTOS_AVISO} eventos)"
            if eventos < ta.MIN_EVENTOS_AVISO else None)


def _prevalencia(casos: int, eventos: int) -> float | None:
    return eventos / casos if casos and (eventos == 0 or eventos >= 10) else None


def _sem_metricas(eventos: int, casos: int) -> str | None:
    if eventos < ta.MIN_EVENTOS_METRICAS:
        return f"menos de {ta.MIN_EVENTOS_METRICAS} eventos: sem métricas (R7)"
    if casos - eventos == 0:
        return "sem não eventos: as métricas não são definidas"
    return None


def _entrada_comorbidade(rotulo: str, chave: str, casos: int, eventos: int, previsto: float,
                         calibracao: dict | None, motivo: str | None) -> dict:
    entrada: dict = {
        "celula": rotulo, "chave": chave, "n": ta.celula(casos), "eventos": ta.celula(eventos),
        "prevalencia": _prevalencia(casos, eventos),
        "risco_previsto_medio": float(previsto) if casos >= 10 else None,
        "aviso_ic_largo": _aviso(eventos), "metricas": None, "desvio_abs_log": None,
        "sentido": None, "ic_inclui_1": None,
    }
    if calibracao is None:
        entrada["motivo_sem_metricas"] = motivo
        return entrada
    entrada["metricas"] = calibracao
    oe = calibracao["obs_esp"]
    if oe["valor"] is not None and oe["valor"] > 0:
        entrada["desvio_abs_log"] = float(abs(np.log(oe["valor"])))
        entrada["sentido"] = ("o modelo subestima o risco (observado > esperado)"
                              if oe["valor"] > 1 else
                              "o modelo superestima o risco (observado < esperado)"
                              if oe["valor"] < 1 else "observado = esperado")
        if oe["ic95"]:
            entrada["ic_inclui_1"] = bool(oe["ic95"][0] <= 1.0 <= oe["ic95"][1])
    return entrada


def _ordenar_por_desvio(celulas: list[dict]) -> list[dict]:
    """Do maior desvio |ln(obs/esp)| ao menor; as sem métrica (ou sem desvio) vão ao fim, na ordem
    original. Ordenação estável: empate fica na ordem das células."""
    com = [c for c in celulas if c["desvio_abs_log"] is not None]
    sem = [c for c in celulas if c["desvio_abs_log"] is None]
    return sorted(com, key=lambda c: -c["desvio_abs_log"]) + sem


def _bloco_de_grupo(casos: int, eventos: int, metricas: dict | None, motivo: str | None) -> dict:
    bloco: dict = {"n": ta.celula(casos), "eventos": ta.celula(eventos),
                   "prevalencia": _prevalencia(casos, eventos), "aviso_ic_largo": _aviso(eventos),
                   "metricas": metricas}
    if metricas is None:
        bloco["motivo_sem_metricas"] = motivo
    return bloco


def analisar_erros(df: pd.DataFrame, y, p_m1, regra_b2, limiar_m1: float, cfg: dict, *,
                   seed: int, n: int, processos: int | None,
                   n_falsos_negativos: int = N_FALSOS_NEGATIVOS,
                   globais: dict | None = None) -> dict:
    """Agregado da análise de erros (ver o topo do módulo): `falsos_negativos`,
    `calibracao_comorbidades` e `espirito_santo`. `globais`: obs/esp global do M1 da T-5.1, só para
    referência no relatório."""
    y_arr = np.asarray(y).astype(np.int64)
    p = np.asarray(p_m1, dtype=float)
    regra = np.asarray(regra_b2, dtype=bool)
    if n < 1:
        raise ValueError("n: pelo menos uma reamostra")
    fn = _falsos_negativos(df, y_arr, p, limiar_m1, cfg, n_falsos_negativos)

    estados: dict[str, tuple] = {}
    pontos: dict[str, tuple[dict, dict]] = {}
    ordinal = 0

    def registrar(chave: str, indices: np.ndarray) -> str | None:
        """Cria o estado do grupo, se houver métricas a calcular; senão devolve o motivo."""
        nonlocal ordinal
        casos, eventos = len(indices), int(y_arr[indices].sum())
        motivo = _sem_metricas(eventos, casos)
        if motivo is None:
            estados[chave] = ta.estado_do_subgrupo(
                y_arr[indices], p[indices], regra[indices], limiar_m1, FLUXO_ERROS + 2 * ordinal)
            pontos[chave] = estados[chave][0].pontos()
        ordinal += 1
        return motivo

    celulas = celulas_de_comorbidade(df)
    motivos: dict[str, str | None] = {}
    contagens: dict[str, tuple[int, int, float]] = {}
    for chave, _, mascara in celulas:
        indices = np.flatnonzero(mascara)
        casos, eventos = len(indices), int(y_arr[indices].sum())
        contagens[chave] = (casos, eventos, float(p[indices].mean()) if casos else 0.0)
        motivos[chave] = registrar(f"c:{chave}", indices)
    es, uf_conhecida = mascara_espirito_santo(df)
    grupos_es = {"ES": np.flatnonzero(es), "resto_do_brasil": np.flatnonzero(~es)}
    motivos_es = {nome: registrar(f"g:{nome}", idx) for nome, idx in grupos_es.items()}

    sementes = metrics.sementes_das_reamostras(seed, n)
    dist = metrics.rodar_varios(estados, sementes, ta.processos_efetivos(processos, n))

    entradas = []
    for chave, rotulo, _ in celulas:
        casos, eventos, previsto = contagens[chave]
        calibracao = None
        if f"c:{chave}" in estados:
            colunas, _ = dist[f"c:{chave}"]
            calibracao = ta.metricas_do_subgrupo(
                pontos[f"c:{chave}"][0]["M1"], pontos[f"c:{chave}"][1], colunas, n)["calibracao"]
        entradas.append(_entrada_comorbidade(rotulo, chave, casos, eventos, previsto, calibracao,
                                             motivos[chave]))
    grupos_json = {}
    for nome, indices in grupos_es.items():
        metricas_g = None
        if f"g:{nome}" in estados:
            colunas, _ = dist[f"g:{nome}"]
            metricas_g = ta.metricas_do_subgrupo(
                pontos[f"g:{nome}"][0]["M1"], pontos[f"g:{nome}"][1], colunas, n)
        grupos_json[nome] = _bloco_de_grupo(len(indices), int(y_arr[indices].sum()), metricas_g,
                                            motivos_es[nome])
    eventos_es = int(y_arr[grupos_es["ES"]].sum())
    return {
        "reamostras": ta.contagem_de_reamostras(n), "limiar_m1": float(limiar_m1),
        "n_pedido": int(n_falsos_negativos), "legenda": LEGENDA,
        "falsos_negativos": fn,
        "calibracao_comorbidades": {
            "metodo": ("observado/esperado e calibration-in-the-large (intercepto com offset "
                       "logit(p)) por célula; IC 95% por bootstrap estratificado por alvo DENTRO "
                       "da célula; as células se sobrepõem"),
            "ordem": "do maior desvio |ln(observado/esperado)| ao menor; sem métrica ao fim",
            "politica_descarte": ta.POLITICA_DESCARTE, "limite_descarte": ta.LIMITE_DESCARTE,
            "obs_esp_global_m1": (globais or {}).get("obs_esp"),
            "celulas": _ordenar_por_desvio(entradas),
        },
        "espirito_santo": {
            "criterio_uf": CRITERIO_ES, "sem_uf_conhecida": ta.celula(int((~uf_conhecida).sum())),
            "aviso": ("poucos eventos no ES: IC largo, sem conclusões"
                      if eventos_es < ta.MIN_EVENTOS_AVISO else None),
            "nota_sistema": ("o ES usa o e-SUS Vigilância em Saúde desde 2020 e a origem do "
                             "registro difere (data-model › Espírito Santo): diferença de "
                             "preenchimento não é diferença de risco"),
            "grupos": grupos_json,
        },
    }


# --- Tabelas e markdown ----------------------------------------------------------------------

def tabela_perfil(j: dict) -> pd.DataFrame:
    return pd.DataFrame(j["falsos_negativos"]["perfil"],
                        columns=["dimensao", "categoria", *(f"{g}_{s}" for g in GRUPOS_PERFIL
                                                            for s in ("n", "pct"))])


def _colunas_ic(linha: dict, chave: str, bloco: dict | None) -> None:
    linha[chave] = bloco["valor"] if bloco else None
    linha[f"{chave}_inf"] = bloco["ic95"][0] if bloco and bloco.get("ic95") else None
    linha[f"{chave}_sup"] = bloco["ic95"][1] if bloco and bloco.get("ic95") else None


def tabela_comorbidades(j: dict) -> pd.DataFrame:
    """Uma linha por célula, na ordem do relatório (maior desvio primeiro)."""
    linhas = []
    for c in j["calibracao_comorbidades"]["celulas"]:
        cal = c["metricas"]
        linha = {"celula": c["celula"], "n": c["n"], "eventos": c["eventos"],
                 "prevalencia": c["prevalencia"], "risco_previsto_medio": c["risco_previsto_medio"]}
        for chave in ("obs_esp", "intercepto", "slope"):
            _colunas_ic(linha, chave, cal[chave] if cal else None)
        linha["reamostras_descartadas"] = cal["reamostras_descartadas"] if cal else None
        linha["desvio_abs_log"] = c["desvio_abs_log"]
        linha["aviso_ic_largo"] = c["aviso_ic_largo"] or ""
        linhas.append(linha)
    return pd.DataFrame(linhas)


def tabela_espirito_santo(j: dict) -> pd.DataFrame:
    linhas = []
    for nome, g in j["espirito_santo"]["grupos"].items():
        m = g["metricas"]
        linha = {"grupo": nome, "n": g["n"], "eventos": g["eventos"],
                 "prevalencia": g["prevalencia"]}
        for chave in ("pr_auc", "recall", "precisao", "regra_b2_recall", "regra_b2_precisao"):
            _colunas_ic(linha, chave, m[chave] if m else None)
        _colunas_ic(linha, "obs_esp", m["calibracao"]["obs_esp"] if m else None)
        linha["aviso_ic_largo"] = g["aviso_ic_largo"] or ""
        linhas.append(linha)
    return pd.DataFrame(linhas)


def tabelas_erros(j: dict) -> dict[str, pd.DataFrame]:
    return {"perfil_falsos_negativos": tabela_perfil(j),
            "calibracao_comorbidades": tabela_comorbidades(j),
            "espirito_santo": tabela_espirito_santo(j)}


def _contagem_e_pct(contagem, pct: float | None) -> str:
    """"12 (12,0%)"; célula suprimida (R7) sai só como "<10"."""
    return str(contagem) if pct is None else f"{contagem} ({ta.num(pct, 1)}%)"


def _md_falsos_negativos(j: dict) -> list[str]:
    fn = j["falsos_negativos"]
    linhas = [
        "## Falsos negativos de maior risco previsto", "",
        f"Falsos negativos: {fn['criterio_selecao']}. Ficam os {j['n_pedido']} de maior risco "
        f"previsto ([ASSUMPTION] do spec); {fn['regra_empate']}. Limiar principal do M1: "
        f"{ta.num(fn['limiar'], 6)}.", "",
        f"- Eventos: {fn['eventos']}; detectados (risco ≥ limiar): {fn['detectados']}; falsos "
        f"negativos no total: {fn['total']}; no perfil: {fn['n_perfil']}.",
    ]
    if not fn["perfil_publicado"]:
        return [*linhas, f"- {fn['motivo_sem_perfil']}", ""]
    r = fn["risco_previsto"]
    linhas += [
        f"- Risco previsto dos {fn['n_perfil']} do perfil (quantis; nenhum valor individual): "
        f"1% = {ta.num(r['q01'], 6)}; mediana = {ta.num(r['mediana'], 6)}; 99% = "
        f"{ta.num(r['q99'], 6)} (o mínimo e o máximo são aproximados por esses quantis).", "",
        "Perfil em agregados: cada coluna é a proporção do grupo na categoria. Compare os "
        "falsos negativos com todos os eventos e com os detectados para ver quem o modelo deixa "
        "passar. Células de 1 a 9 casos aparecem como <10, sem proporção.", ""]
    corpo = [[p["dimensao"], p["categoria"],
              *(_contagem_e_pct(p[f"{g}_n"], p[f"{g}_pct"]) for g in GRUPOS_PERFIL)]
             for p in fn["perfil"]]
    return [*linhas, *ta.tabela_md(
        ["Dimensão", "Categoria", *(NOMES_GRUPOS[g] for g in GRUPOS_PERFIL)], corpo), ""]


def _md_comorbidades(j: dict) -> list[str]:
    c = j["calibracao_comorbidades"]
    linhas = [
        "## Células de comorbidade com pior calibração", "",
        f"{c['metodo'][:1].upper() + c['metodo'][1:]}. {c['politica_descarte']} "
        f"Ordem: {c['ordem']}. "
        f"Reamostras: {j['reamostras']}.", ""]
    if c["obs_esp_global_m1"]:
        linhas += [f"Referência: observado/esperado global do M1 = "
                   f"{ta.ic_txt(c['obs_esp_global_m1'], 3)}.", ""]
    corpo = []
    for e in c["celulas"]:
        m = e["metricas"]
        corpo.append([
            e["celula"], e["n"], e["eventos"],
            ta.ic_txt(m["obs_esp"], 3) if m else "sem métricas",
            ta.ic_txt(m["intercepto"], 3) if m else "—",
            ta.ic_txt(m["slope"], 3) if m else "—",
            m["reamostras_descartadas"] if m else "—",
            e["sentido"] or "", e["aviso_ic_largo"] or ""])
    return [*linhas, *ta.tabela_md(
        ["Célula", "Casos", "Eventos", "Observado/esperado (IC)", "Intercepto (IC)",
         "Slope (IC)", "Reamostras descartadas", "Leitura", "Aviso"], corpo), ""]


def _md_espirito_santo(j: dict) -> list[str]:
    es = j["espirito_santo"]
    linhas = ["## Espírito Santo à parte", "",
              f"Critério: {es['criterio_uf']}. {es['nota_sistema']}.",
              f"Casos sem UF conhecida (no resto do Brasil): {es['sem_uf_conhecida']}.", ""]
    if es["aviso"]:
        linhas += [f"**Aviso: {es['aviso']}.**", ""]
    corpo = []
    for nome, g in es["grupos"].items():
        m = g["metricas"]
        prev = "—" if g["prevalencia"] is None else ta.num(100 * g["prevalencia"], 3) + "%"
        corpo.append([
            "Espírito Santo" if nome == "ES" else "Resto do Brasil", g["n"], g["eventos"], prev,
            ta.ic_txt(m["pr_auc"], 4) if m else "sem métricas",
            ta.ic_txt(m["recall"], 3) if m else "—", ta.ic_txt(m["precisao"], 4) if m else "—",
            ta.ic_txt(m["calibracao"]["obs_esp"], 3) if m else "—", g["aviso_ic_largo"] or ""])
    return [*linhas, *ta.tabela_md(
        ["Grupo", "Casos", "Eventos", "Taxa de eventos", "PR-AUC (IC)", "Recall (IC)",
         "Precisão (IC)", "Observado/esperado (IC)", "Aviso"], corpo), ""]


def markdown_erros(j: dict) -> str:
    return "\n".join([f"> {j['legenda']}", "", *_md_falsos_negativos(j), *_md_comorbidades(j),
                      *_md_espirito_santo(j)])
