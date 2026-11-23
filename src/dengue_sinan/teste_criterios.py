"""Critérios de sucesso SC-01 a SC-04 no teste (T-5.4, D-36, D-92, D-93; R7, R8).

Lê o que a T-5.1 já calculou (`metricas.json`: diferenças pareadas de PR-AUC e o slope do M1) e só
calcula o que ela não tem: a diferença de recall e de precisão entre o M1 e a regra B2 (SC-02).
Não mexe no modelo, no calibrador, no peso nem no limiar (D-36).

- **SC-01**: o melhor M1 supera B0 em PR-AUC. Passa se o IC 95% da diferença pareada M1 − B0 não
  inclui 0 e fica acima dele (limite inferior > 0).
- **SC-02**: no limiar principal congelado (D-92), recall do M1 ≥ recall da B2 **e** precisão do M1
  > precisão da B2. Passa/falha pelas estimativas pontuais, como diz o spec; o relatório informa
  também se o IC da diferença sustenta cada parte (limite inferior ≥ 0 no recall; > 0 na precisão).
- **SC-03**: calibration slope do M1 entre 0,8 e 1,2, inclusive. Passa/falha pela estimativa; o
  relatório informa se o IC inteiro cabe no intervalo.
- **SC-04**: diferença de PR-AUC M1 − B1 reportada com IC 95%, qualquer que seja o sinal.
  "Reportado" = passou (valor e IC existem). Superar B1 é desejável, não condição.

**Sorteios do SC-02.** A diferença é por bootstrap sobre as mesmas células e os mesmos sorteios da
T-5.1: as células são (alvo, flag de M1, B0, B1 e B2), na mesma ordem, e cada reamostra usa a
sub-semente k e o fluxo 1 (`FLUXO_LIMIARES`). Assim recall e precisão de M1 e B2 de cada reamostra
são exatamente os da T-5.1, e a diferença é pareada com eles. (Com 4 flags são no máximo 2 × 16
células: custo desprezível.)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from dengue_sinan import metrics
from dengue_sinan import teste_analises as ta

FLUXO_LIMIARES = 1  # o mesmo fluxo das métricas no limiar da T-5.1 (`Reamostrador`, base + 1)
SLOPE_MIN = 0.8
SLOPE_MAX = 1.2
TEXTO_D36 = ("Se o teste sair pior que a validação, reportar como resultado (drift); é proibido "
             "voltar e trocar modelo, peso, calibrador ou limiar.")
CRITERIOS = ("sc01", "sc02", "sc03", "sc04")
CAMPOS = ("valor", "ic95", "criterio", "passou")
ROTULOS = {"sc01": "SC-01", "sc02": "SC-02", "sc03": "SC-03", "sc04": "SC-04"}


# --- SC-02: recall e precisão do M1 contra a regra B2 ----------------------------------------

def diferencas_no_limiar(y, marcados: dict[str, np.ndarray], *, seed: int, n: int,
                         m1: str = "M1", regra: str = "B2") -> dict:
    """Recall e precisão de `m1` e de `regra` no limiar, com IC 95%, e a diferença pareada.

    `marcados`: flag de alto risco de cada modelo ou regra, na ORDEM da T-5.1 (M1, B0, B1, B2): a
    ordem define as células, e com ela os sorteios coincidem com os da T-5.1. Devolve
    {"recall": {m1, regra, "diferenca"}, "precisao": {...}}, cada um com {"valor", "ic95"}.
    """
    if n < 1:
        raise ValueError("n: pelo menos uma reamostra")
    y_arr = np.asarray(y).astype(np.int64)
    celulas = metrics.agrupar_celulas(y_arr, {k: np.asarray(v, dtype=bool)
                                              for k, v in marcados.items()})
    limiarizados = {nome: metrics.Limiarizado(celulas.y, celulas.colunas[nome])
                    for nome in (m1, regra)}
    ponto = {nome: lim.metricas(celulas.contagem.astype(np.float64))
             for nome, lim in limiarizados.items()}
    sorteio = metrics.Sorteio(celulas.contagem, celulas.n_negativas)
    medidas = ("recall", "precisao")
    dist = {(nome, k): np.empty(n) for nome in limiarizados for k in medidas}
    for r, semente in enumerate(metrics.sementes_das_reamostras(seed, n)):
        w = sorteio(metrics.fluxo(semente, FLUXO_LIMIARES))
        for nome, lim in limiarizados.items():
            t = lim.metricas(w)
            for k in medidas:
                dist[(nome, k)][r] = t[k]
    saida: dict = {}
    for k in medidas:
        saida[k] = {
            m1: ta.com_ic(ponto[m1][k], dist[(m1, k)]),
            regra: ta.com_ic(ponto[regra][k], dist[(regra, k)]),
            "diferenca": ta.com_ic(ponto[m1][k] - ponto[regra][k],
                                   dist[(m1, k)] - dist[(regra, k)]),
        }
    saida["reamostras"] = ta.contagem_de_reamostras(n)  # o n que este cálculo usou de fato
    return saida


# --- Os quatro critérios ---------------------------------------------------------------------

def _inferior(bloco: dict | None) -> float | None:
    return bloco["ic95"][0] if bloco and bloco.get("ic95") else None


def avaliar_criterios(metricas: dict, sc02: dict, *, m1: str = "M1", regra: str = "B2") -> dict:
    """Os quatro critérios a partir do JSON da T-5.1 (`metricas`) e das diferenças da B2 (`sc02`).

    Cada critério tem `valor`, `ic95`, `criterio` e `passou`, mais campos de leitura. Só aritmética
    sobre números já agregados: não lê dado nem modelo.
    """
    d01 = metricas["diferencas_pr_auc"]["M1_menos_B0"]
    d04 = metricas["diferencas_pr_auc"]["M1_menos_B1"]
    slope = metricas["modelos"][m1]["slope"]
    rec, prec = sc02["recall"], sc02["precisao"]

    lo01 = _inferior(d01)
    sc01 = {
        "valor": d01["valor"], "ic95": d01["ic95"],
        "criterio": "o IC 95% da diferença de PR-AUC (M1 − B0) não inclui 0 e fica acima dele",
        "passou": bool(lo01 is not None and d01["valor"] is not None and lo01 > 0),
        "ic_inclui_zero": (None if d01["ic95"] is None
                           else bool(d01["ic95"][0] <= 0.0 <= d01["ic95"][1])),
    }

    recall_ok = rec[m1]["valor"] >= rec[regra]["valor"]
    precisao_ok = prec[m1]["valor"] > prec[regra]["valor"]
    lo_rec, lo_prec = _inferior(rec["diferenca"]), _inferior(prec["diferenca"])
    sc02_json = {
        "valor": {"recall_m1_menos_b2": rec["diferenca"]["valor"],
                  "precisao_m1_menos_b2": prec["diferenca"]["valor"]},
        "ic95": {"recall_m1_menos_b2": rec["diferenca"]["ic95"],
                 "precisao_m1_menos_b2": prec["diferenca"]["ic95"]},
        "criterio": ("no limiar principal congelado (D-92), recall do M1 ≥ recall da regra B2 e "
                     "precisão do M1 > precisão da B2 (estimativas pontuais)"),
        "passou": bool(recall_ok and precisao_ok),
        "recall_ok": bool(recall_ok), "precisao_ok": bool(precisao_ok),
        "reamostras_do_sc02": sc02["reamostras"],
        "ic_sustenta": {"recall": None if lo_rec is None else bool(lo_rec >= 0.0),
                        "precisao": None if lo_prec is None else bool(lo_prec > 0.0)},
        "detalhe": {"recall": rec, "precisao": prec},
    }

    valor03 = slope["valor"] if slope else None
    ic03 = slope["ic95"] if slope else None
    sc03 = {
        "valor": valor03, "ic95": ic03,
        "criterio": f"calibration slope do M1 entre {ta.num(SLOPE_MIN, 1)} e "
                    f"{ta.num(SLOPE_MAX, 1)}, inclusive (estimativa pontual)",
        "passou": bool(valor03 is not None and SLOPE_MIN <= valor03 <= SLOPE_MAX),
        "ic_dentro_do_intervalo": (None if ic03 is None else
                                   bool(SLOPE_MIN <= ic03[0] and ic03[1] <= SLOPE_MAX)),
    }

    lo04 = _inferior(d04)
    ic04 = d04["ic95"]
    sc04 = {
        "valor": d04["valor"], "ic95": ic04,
        "criterio": "diferença de PR-AUC (M1 − B1) reportada com IC 95%, qualquer que seja o sinal",
        "passou": bool(d04["valor"] is not None and ic04 is not None),
        "sentido": (None if ic04 is None else
                    "M1 acima do B1 (IC exclui 0)" if lo04 > 0 else
                    "M1 abaixo do B1 (IC exclui 0)" if ic04[1] < 0 else "IC inclui 0"),
        "superou_b1": bool(lo04 is not None and lo04 > 0),
        "nota": "superar o B1 é desejável, não condição do critério",
    }
    return {"sc01": sc01, "sc02": sc02_json, "sc03": sc03, "sc04": sc04,
            "texto_d36": TEXTO_D36, "reamostras": ta.contagem_de_reamostras(metricas["reamostras"]),
            "limiar_m1": metricas["modelos"][m1].get("limiar")}


# --- Tabela e markdown -----------------------------------------------------------------------

def _linha(criterio: str, medida: str, valor, ic, regra: str, passou: bool | None) -> dict:
    return {"criterio": criterio, "medida": medida, "valor": valor,
            "ic_inf": ic[0] if ic else None, "ic_sup": ic[1] if ic else None, "regra": regra,
            "resultado": "" if passou is None else ("passou" if passou else "falhou")}


def tabela_criterios(j: dict) -> pd.DataFrame:
    s1, s2, s3, s4 = j["sc01"], j["sc02"], j["sc03"], j["sc04"]
    linhas = [
        _linha("SC-01", "diferença de PR-AUC M1 − B0", s1["valor"], s1["ic95"], s1["criterio"],
               s1["passou"]),
        _linha("SC-02", "diferença de recall M1 − B2", s2["valor"]["recall_m1_menos_b2"],
               s2["ic95"]["recall_m1_menos_b2"], "recall do M1 ≥ recall da B2", s2["recall_ok"]),
        _linha("SC-02", "diferença de precisão M1 − B2", s2["valor"]["precisao_m1_menos_b2"],
               s2["ic95"]["precisao_m1_menos_b2"], "precisão do M1 > precisão da B2",
               s2["precisao_ok"]),
        _linha("SC-03", "calibration slope do M1", s3["valor"], s3["ic95"], s3["criterio"],
               s3["passou"]),
        _linha("SC-04", "diferença de PR-AUC M1 − B1", s4["valor"], s4["ic95"], s4["criterio"],
               s4["passou"]),
    ]
    return pd.DataFrame(linhas)


def _sim_nao(v: bool | None) -> str:
    return "—" if v is None else ("sim" if v else "não")


def _icv(valor, ic95, casas: int) -> str:
    return ta.ic_txt({"valor": valor, "ic95": ic95}, casas)


def _res(passou: bool) -> str:
    return "**passou**" if passou else "**falhou**"


def markdown_criterios(j: dict) -> str:
    s1, s2, s3, s4 = j["sc01"], j["sc02"], j["sc03"], j["sc04"]
    det = s2["detalhe"]
    dif_rec = _icv(s2["valor"]["recall_m1_menos_b2"], s2["ic95"]["recall_m1_menos_b2"], 4)
    dif_prec = _icv(s2["valor"]["precisao_m1_menos_b2"], s2["ic95"]["precisao_m1_menos_b2"], 5)
    resumo = ta.tabela_md(
        ["Critério", "Valor medido (IC 95%)", "Regra", "Resultado"],
        [["SC-01", _icv(s1["valor"], s1["ic95"], 6),
          "IC da diferença M1 − B0 sem 0 e acima dele", _res(s1["passou"])],
         ["SC-02", f"recall M1 − B2 = {dif_rec}; precisão M1 − B2 = {dif_prec}",
          "recall do M1 ≥ B2 e precisão do M1 > B2", _res(s2["passou"])],
         ["SC-03", _icv(s3["valor"], s3["ic95"], 3),
          f"slope entre {ta.num(SLOPE_MIN, 1)} e {ta.num(SLOPE_MAX, 1)}", _res(s3["passou"])],
         ["SC-04", _icv(s4["valor"], s4["ic95"], 6),
          "diferença M1 − B1 reportada com IC", _res(s4["passou"])]])
    ic_rec, ic_prec = s2["ic_sustenta"]["recall"], s2["ic_sustenta"]["precisao"]
    linhas = [
        f"> {j['texto_d36']}", "",
        "## Resumo", "", *resumo, "",
        "Passa/falha pela estimativa pontual, como o spec define. O IC é informado ao lado e as "
        f"leituras abaixo dizem se ele sustenta o resultado. Reamostras: {j['reamostras']}.", "",
        "## SC-01: M1 supera B0 em PR-AUC", "",
        f"- Diferença pareada (M1 − B0): {_icv(s1['valor'], s1['ic95'], 6)}.",
        f"- O IC inclui 0: {_sim_nao(s1['ic_inclui_zero'])}. Resultado: {_res(s1['passou'])}.", "",
        "## SC-02: recall e precisão do M1 contra a regra B2", "",
        f"- Limiar principal do M1 (congelado, D-92): {ta.num(j['limiar_m1'], 6)}.",
        f"- Recall: M1 {ta.ic_txt(det['recall']['M1'], 4)}; "
        f"B2 {ta.ic_txt(det['recall']['B2'], 4)}; "
        f"diferença {dif_rec}. Recall do M1 ≥ B2: {_sim_nao(s2['recall_ok'])}; o IC sustenta: "
        f"{_sim_nao(ic_rec)}.",
        f"- Precisão: M1 {ta.ic_txt(det['precisao']['M1'], 5)}; B2 "
        f"{ta.ic_txt(det['precisao']['B2'], 5)}; diferença {dif_prec}. Precisão do M1 > B2: "
        f"{_sim_nao(s2['precisao_ok'])}; o IC sustenta: {_sim_nao(ic_prec)}.",
        f"- Resultado: {_res(s2['passou'])}. Recall igual com precisão igual falha: a precisão "
        "do M1 precisa ser maior.", "",
        "## SC-03: calibration slope do M1", "",
        f"- Slope: {_icv(s3['valor'], s3['ic95'], 3)}.",
        f"- O IC inteiro cabe em [{ta.num(SLOPE_MIN, 1)}; {ta.num(SLOPE_MAX, 1)}]: "
        f"{_sim_nao(s3['ic_dentro_do_intervalo'])}. Resultado: {_res(s3['passou'])}.", "",
        "## SC-04: diferença de PR-AUC entre M1 e B1", "",
        f"- Diferença pareada (M1 − B1): {_icv(s4['valor'], s4['ic95'], 6)} "
        f"({s4['sentido'] or 'sem IC'}).",
        f"- {s4['nota'][:1].upper() + s4['nota'][1:]}. Reportado = passou: "
        f"{_res(s4['passou'])}.", "",
        "## Regra do teste", "",
        j["texto_d36"], "",
        "Nenhum modelo, peso, calibrador ou limiar foi alterado depois de ver o teste.", ""]
    return "\n".join(linhas)
