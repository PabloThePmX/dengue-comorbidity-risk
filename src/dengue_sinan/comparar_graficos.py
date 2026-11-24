"""Gráficos comparativos de 2025 (T-8.8, D-97, D-99).

Desenha seis figuras em PNG a partir só de `metricas.json` (agregados, R7). O formato está fixado em
specs/contracts/interfaces.md, seção "Comparação em 2025". Este módulo não lê previsões, dados
brutos nem o manifesto: o que entra é o agregado já calculado por `comparar.py`.

Antes de desenhar, o agregado é validado contra o contrato. Um agregado fora dele é recusado com
ValueError, inclusive uma caixa de calibração com menos de 10 casos (R7), e nada é criado em disco.

Figuras (`gerar_graficos`):
- `pr_auc.png`: PR-AUC com IC 95% por modelo, população principal, com a prevalência como acaso;
- `diferencas_pr_auc.png`: diferença de PR-AUC contra o M1 com IC (forest plot), colorida pela
  leitura;
- `orcamentos.png`: recall e precisão nos orçamentos de alertas (5%, 10%, 14%), um painel por
  métrica;
- `calibracao.png`: caixas por quantil, um painel por modelo, eixos logarítmicos, mesma escala;
- `curva_decisao.png`: benefício líquido de todos os modelos, com "tratar todos" e
  "tratar ninguém";
- `conformidade.png`: tabela visual de R3, R4, treino sem 2025, versões e externo, por modelo.

Estilo: a cor é fixa por id do modelo; marcador e traço também, para o gráfico ler em preto e
branco; externos têm marcador vazado e "(externo)" no rótulo.
"""

from __future__ import annotations

import argparse
import json
import math
import textwrap
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

ARQ_PR_AUC = "pr_auc.png"
ARQ_DIFERENCAS = "diferencas_pr_auc.png"
ARQ_ORCAMENTOS = "orcamentos.png"
ARQ_CALIBRACAO = "calibracao.png"
ARQ_CURVA_DECISAO = "curva_decisao.png"
ARQ_CONFORMIDADE = "conformidade.png"
FIGURAS = (ARQ_PR_AUC, ARQ_DIFERENCAS, ARQ_ORCAMENTOS, ARQ_CALIBRACAO, ARQ_CURVA_DECISAO,
           ARQ_CONFORMIDADE)

CHAVES_DO_CONTRATO = ("ano", "reamostras", "semente", "modelos", "modelo_de_referencia",
                      "populacoes", "metricas", "diferencas_pr_auc_vs_referencia", "orcamentos",
                      "no_limiar_proprio", "curva_decisao", "calibracao", "conformidade")
METRICAS_POR_MODELO = ("pr_auc", "roc_auc", "brier", "calibration_slope",
                       "calibration_intercepto", "obs_esp")
ORCAMENTOS = ("0.05", "0.10", "0.14")
LEITURAS = ("melhor", "pior", "sem diferença detectável")
CHAVES_CONFORMIDADE = ("r3_sem_correcao", "r4_variaveis_no_dicionario",
                       "treino_sem_ano_de_comparacao", "versoes_diferentes_do_treino", "externo")
MIN_CASOS_CAIXA = 10

RODAPE_BASE = ("Ano de comparação {ano}; avaliação única (R2); só agregados (R7); IC bootstrap "
               "pareado; população principal = casos que o E1 estima (D-99)")

# Rótulos e cores fixos por id do manifesto (mesmo mapa em todas as figuras).
ROTULO = {
    "m1_main": "M1 (XGBoost, projeto)",
    "e1_main": "E1 (logística explicativa)",
    "b1_main": "B1 (logística simples)",
    "b0_main": "B0 (prevalência)",
    "b2_regra": "B2 (regra do protocolo)",
    "m1_soneca": "M1 soneca",
    "m1_lora": "M1 lora",
}
COR = {
    "m1_main": "#1b6ca8",
    "e1_main": "#8a4fa3",
    "b1_main": "#d98324",
    "b0_main": "#7f7f7f",
    "b2_regra": "#4c9a5f",
    "m1_soneca": "#b03a2e",
    "m1_lora": "#17a2a2",
}
# Marcador e traço por id: distinguem os modelos em preto e branco.
ESTILO = {
    "m1_main": ("o", "-"),
    "e1_main": ("s", "--"),
    "b1_main": ("^", "-."),
    "b0_main": ("v", ":"),
    "b2_regra": ("D", (0, (3, 1, 1, 1))),
    "m1_soneca": ("P", (0, (5, 2))),
    "m1_lora": ("X", (0, (1, 1))),
}
_COR_EXTRA = ("#5d6d7e", "#a04000", "#196f3d", "#7d3c98")
_MARCADOR_EXTRA = ("*", "p", "<", ">")
_TRACO_EXTRA = ("-", "--", ":", "-.")
COR_LEITURA = {"melhor": "#2e7d32", "pior": "#c62828", "sem diferença detectável": "#616161"}
COR_CONFORMIDADE = {"sim": "#d4edda", "não": "#f8d7da", "n/d": "#e9ecef", "neutro": "#d6e4f0"}
COR_CINZA = "#555555"


# --- Contrato ----------------------------------------------------------------------------------

def _exigir(condicao: bool, mensagem: str) -> None:
    if not condicao:
        raise ValueError(f"metricas.json fora do contrato (interfaces.md, Comparação em 2025): "
                         f"{mensagem}")


def _numero(valor) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def _checar_ponto(objeto, onde: str, com_leitura: bool = False) -> None:
    """`{"valor", "ic95"}` (e `leitura`, nas diferenças) ou null."""
    if objeto is None:
        return
    chaves = ("valor", "ic95", "leitura") if com_leitura else ("valor", "ic95")
    _exigir(isinstance(objeto, dict) and all(c in objeto for c in chaves),
            f"{onde} deve ser {{{', '.join(chaves)}}} ou null")
    _exigir(objeto["valor"] is None or _numero(objeto["valor"]), f"{onde}: valor não numérico")


def validar(agregados: dict) -> None:
    """Recusa o agregado se ele não segue o contrato. Não altera nada."""
    faltando = [c for c in CHAVES_DO_CONTRATO if c not in agregados]
    _exigir(not faltando, f"faltam as chaves {', '.join(faltando)}")
    _exigir(isinstance(agregados["ano"], int) and not isinstance(agregados["ano"], bool),
            "ano deve ser inteiro")
    _exigir(_numero(agregados["reamostras"]) and _numero(agregados["semente"]),
            "reamostras e semente devem ser números")
    modelos = agregados["modelos"]
    _exigir(isinstance(modelos, list) and len(modelos) > 0 and len(set(modelos)) == len(modelos),
            "modelos deve ser lista não vazia, sem repetição")
    ref = agregados["modelo_de_referencia"]
    _exigir(ref in modelos, f"modelo_de_referencia {ref!r} não está em modelos")

    principal = "principal"
    populacoes = agregados["populacoes"]
    _exigir(isinstance(populacoes, dict) and principal in populacoes,
            "falta a população principal")
    _exigir(_numero(populacoes[principal].get("prevalencia")),
            "populacoes.principal sem prevalencia numérica")

    metricas = agregados["metricas"]
    _exigir(principal in metricas, "metricas sem a população principal")
    for m in modelos:
        _exigir(m in metricas[principal], f"metricas[principal] sem o modelo {m}")
        bloco = metricas[principal][m]
        if bloco is None:  # modelo inteiro sem métricas: vale o mesmo que todas indisponíveis
            continue
        for chave in METRICAS_POR_MODELO:
            _exigir(chave in bloco, f"metricas[principal][{m}] sem {chave}")
            _checar_ponto(bloco[chave], f"metricas[principal][{m}][{chave}]")

    orcamentos = agregados["orcamentos"]
    _exigir(principal in orcamentos, "orcamentos sem a população principal")
    for m in modelos:
        _exigir(m in orcamentos[principal], f"orcamentos[principal] sem o modelo {m}")
        celulas = orcamentos[principal][m] or {}
        for b in ORCAMENTOS:
            if not celulas:
                break
            _exigir(b in celulas, f"orcamentos[principal][{m}] sem o orçamento {b}")
            _exigir(isinstance(celulas[b].get("alertas"), int),
                    f"orcamentos[principal][{m}][{b}] sem alertas inteiro")
            alertas = celulas[b]["alertas"]
            _exigir(not 0 < alertas < MIN_CASOS_CAIXA,
                    f"orcamentos[principal][{m}][{b}]: {alertas} alertas (1 a 9 não saem, R7)")
            for metrica in ("recall", "precisao"):
                _checar_ponto(celulas[b].get(metrica),
                          f"orcamentos[principal][{m}][{b}][{metrica}]")

    diferencas = agregados["diferencas_pr_auc_vs_referencia"]
    _exigir(principal in diferencas, "diferencas sem a população principal")
    dif_pop = diferencas[principal]
    _exigir(ref in dif_pop and dif_pop[ref] is None,
            "a entrada da própria referência em diferencas deve ser null")
    for m in modelos:
        if m == ref:
            continue
        _exigir(m in dif_pop, f"diferencas[principal] sem o modelo {m}")
        dif = dif_pop[m]
        _checar_ponto(dif, f"diferencas[principal][{m}]", com_leitura=True)
        if dif is not None and dif["valor"] is not None:
            _exigir(dif["leitura"] in LEITURAS, f"leitura inválida em {m}: {dif['leitura']!r}")
            if dif["ic95"] is not None:  # convenção: "melhor" se o IC inferior > 0, "pior" se o
                ic = dif["ic95"]         # superior < 0 (interfaces.md, Convenções)
                esperada = ("melhor" if ic[0] > 0 else "pior" if ic[1] < 0
                            else "sem diferença detectável")
                _exigir(dif["leitura"] == esperada,
                        f"leitura de {m} ({dif['leitura']}) não bate com o IC {ic}")

    nlp = agregados["no_limiar_proprio"]
    _exigir(all(m in nlp for m in modelos), "no_limiar_proprio sem algum modelo")

    calibracao = agregados["calibracao"]
    for m in modelos:
        _exigir(m in calibracao, f"calibracao sem o modelo {m}")
        caixas = calibracao[m]
        if caixas is None:
            continue
        _exigir(isinstance(caixas, list), f"calibracao[{m}] deve ser lista ou null")
        for c in caixas:
            _exigir(all(k in c for k in ("previsto", "observado", "ic95", "casos")),
                    f"caixa de calibração de {m} sem campos obrigatórios")
            casos = c["casos"]
            if casos == "<10":  # suprimida (R7): quem desenha ignora; sem valores
                _exigir(all(c[k] is None for k in ("previsto", "observado", "ic95")),
                        f"caixa suprimida de {m} com valores (R7)")
                continue
            _exigir(isinstance(casos, int) and not isinstance(casos, bool),
                    f"caixa de calibração de {m}: casos deve ser inteiro ou \"<10\"")
            _exigir(casos >= MIN_CASOS_CAIXA,
                    f"caixa de calibração de {m} com {casos} casos: menos de "
                    f"{MIN_CASOS_CAIXA} casos é suprimido (R7); a caixa suprimida traz "
                    "casos \"<10\"")
            if c["observado"] is None:  # sem taxa, não há IC (R7)
                _exigir(c["ic95"] is None, f"IC sem taxa observada em {m}")

    curva = agregados["curva_decisao"]
    _exigir(isinstance(curva.get("limiares"), list) and len(curva["limiares"]) > 0,
            "curva_decisao sem limiares")
    for m in modelos:
        _exigir(m in curva and len(curva[m]) == len(curva["limiares"]),
                f"curva_decisao de {m} sem um valor por limiar")

    conformidade = agregados["conformidade"]
    for m in modelos:
        _exigir(m in conformidade and all(k in conformidade[m] for k in CHAVES_CONFORMIDADE),
                f"conformidade de {m} sem as chaves {', '.join(CHAVES_CONFORMIDADE)}")


# --- Estilo e formatação -----------------------------------------------------------------------

def estilos_dos_modelos(agregados: dict) -> dict[str, dict]:
    """Cor, marcador, traço e rótulo de cada modelo. Ids fora do mapa fixo recebem estilo pela
    posição no manifesto, que é a mesma em todas as figuras."""
    saida = {}
    for pos, modelo in enumerate(agregados["modelos"]):
        marcador, traco = ESTILO.get(modelo, (_MARCADOR_EXTRA[pos % len(_MARCADOR_EXTRA)],
                                              _TRACO_EXTRA[pos % len(_TRACO_EXTRA)]))
        externo = bool(agregados["conformidade"][modelo]["externo"])
        rotulo = ROTULO.get(modelo, modelo)
        saida[modelo] = {
            "cor": COR.get(modelo, _COR_EXTRA[pos % len(_COR_EXTRA)]),
            "marcador": marcador,
            "traco": traco,
            "rotulo": rotulo,
            "externo": externo,
            "rotulo_completo": rotulo + (" (externo)" if externo else ""),
        }
    return saida


def _nan(valor) -> float:
    return float("nan") if valor is None else float(valor)


def _ponto(metrica) -> tuple[float, float, float] | None:
    """(valor, inf, sup) de `{valor, ic95}`; None quando o modelo não estima (null)."""
    if metrica is None or metrica.get("valor") is None:
        return None
    ic = metrica.get("ic95") or [None, None]
    return float(metrica["valor"]), _nan(ic[0]), _nan(ic[1])


def _metrica(bloco_modelo: dict | None, chave: str) -> dict | None:
    """Métrica de um modelo; None quando o bloco do modelo inteiro é null."""
    return None if bloco_modelo is None else bloco_modelo.get(chave)


def _caixas_publicaveis(caixas: list[dict] | None) -> list[dict]:
    """Caixas que viram ponto. Caixa suprimida (casos "<10", R7) e caixa sem taxa observada ou com
    taxa zero (não cabe em escala log) são ignoradas, sem erro."""
    return [c for c in (caixas or [])
            if c["casos"] != "<10" and c["previsto"] is not None and c["observado"] is not None
            and c["observado"] > 0]


def _num(valor: float, casas: int) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _pct(valor: float) -> str:
    """Fração em %, com vírgula decimal e só os algarismos necessários."""
    return f"{100 * valor:.3g}".replace(".", ",") + "%"


def _decimal_ptbr(lado) -> None:
    """Rótulos numéricos de um eixo com vírgula decimal, como no resto do texto."""
    lado.set_major_formatter(FuncFormatter(lambda v, _p: f"{v:g}".replace(".", ",")))


def _alertas_texto(n: int) -> str:
    return f"{n:,}".replace(",", ".") + " alertas"


def _rodape(agregados: dict, extra: str = "") -> str:
    base = RODAPE_BASE.format(ano=agregados["ano"]) + "."
    refs = f"Reamostras: {agregados['reamostras']}; semente: {agregados['semente']}."
    return " ".join(p for p in (base, refs, extra) if p)


def _acabamento(figura: Figure, rodape: str, handles=(), ncol: int = 4,
                ajustar: bool = True) -> None:
    """Layout, legenda comum abaixo dos eixos e rodapé obrigatório no pé da figura.

    O espaço do rodapé e da legenda é reservado antes de `tight_layout`, porque ele não conta
    textos e legendas soltos da figura."""
    altura = figura.get_figheight()
    linhas = textwrap.wrap(rodape, width=int(72 * figura.get_figwidth() / 4.6))
    h_rodape = len(linhas) * 0.17 / altura
    h_legenda = math.ceil(len(handles) / ncol) * 0.27 / altura if handles else 0.0
    reserva = 0.03 + h_rodape + h_legenda + (0.02 if handles else 0.0)
    if ajustar:
        figura.tight_layout(rect=(0, reserva, 1, 1))
    if handles:
        figura.legend(handles=list(handles), loc="upper center",
                      bbox_to_anchor=(0.5, reserva - 0.01), ncol=ncol, fontsize=8, frameon=False)
    figura.text(0.01, 0.012, "\n".join(linhas), fontsize=8, color=COR_CINZA, va="bottom",
                linespacing=1.2)


def _salvar(figura: Figure, caminho: Path) -> Path:
    FigureCanvasAgg(figura)
    figura.savefig(caminho, dpi=130)
    return caminho


def _proxy_externo() -> Line2D:
    return Line2D([], [], marker="o", linestyle="none", markerfacecolor="white",
                  markeredgecolor="#333333", color="#333333",
                  label="externo (marcador vazado)")


def _ponto_com_ic(eixo, valor: float, lo: float, hi: float, pos: float, est: dict,
                  *, horizontal: bool, cor: str | None = None) -> None:
    """IC como segmento e o ponto no meio. Horizontal: x = valor, y = pos (forest plot)."""
    cor = cor or est["cor"]
    mfc = "white" if est["externo"] else cor
    if horizontal:
        if math.isfinite(lo) and math.isfinite(hi):
            eixo.hlines(pos, lo, hi, color=cor, linewidth=1.8)
        xs, ys = [valor], [pos]
    else:
        if math.isfinite(lo) and math.isfinite(hi):
            eixo.vlines(pos, lo, hi, color=cor, linewidth=1.8)
        xs, ys = [pos], [valor]
    eixo.plot(xs, ys, linestyle="none", marker=est["marcador"], markerfacecolor=mfc,
              markeredgecolor=cor, color=cor, markersize=7)


# --- Figuras -----------------------------------------------------------------------------------

def _figura_pr_auc(agregados: dict, estilos: dict) -> Figure:
    modelos = agregados["modelos"]
    n = len(modelos)
    pr = agregados["metricas"]["principal"]
    figura = Figure(figsize=(9, 0.55 * n + 2.6))
    eixo = figura.add_subplot()
    rotulos = []
    maior = 0.0
    for i, modelo in enumerate(modelos):
        y = n - 1 - i
        est = estilos[modelo]
        ponto = _ponto(_metrica(pr[modelo], "pr_auc"))
        if ponto is None:
            rotulos.append(est["rotulo_completo"] + " (sem estimativa)")
            continue
        valor, lo, hi = ponto
        rotulos.append(est["rotulo_completo"])
        maior = max(maior, valor, hi if math.isfinite(hi) else valor)
        _ponto_com_ic(eixo, valor, lo, hi, y, est, horizontal=True)
    eixo.set_yticks(range(n), rotulos[::-1])
    eixo.set_ylim(-0.6, n - 0.4)
    eixo.set_xlim(0, maior * 1.2 if maior > 0 else 1)
    _decimal_ptbr(eixo.xaxis)
    prev = agregados["populacoes"]["principal"]["prevalencia"]
    eixo.axvline(prev, color=COR_CINZA, linestyle=":", linewidth=1.2)
    eixo.set_title("PR-AUC com IC 95% por modelo (população principal)")
    eixo.set_xlabel("PR-AUC (IC 95%, bootstrap pareado)")
    eixo.set_ylabel("modelo")
    handles = [Line2D([], [], color=COR_CINZA, linestyle=":",
                      label=f"acaso (prevalência {_pct(prev)})")]
    if any(estilos[m]["externo"] for m in modelos):
        handles.append(_proxy_externo())
    _acabamento(figura, _rodape(agregados), handles, ncol=len(handles))
    return figura


def _figura_diferencas(agregados: dict, estilos: dict) -> Figure:
    ref = agregados["modelo_de_referencia"]
    modelos = [m for m in agregados["modelos"] if m != ref]
    difs = agregados["diferencas_pr_auc_vs_referencia"]["principal"]
    n = len(modelos)
    figura = Figure(figsize=(9.5, 0.6 * n + 2.6))
    eixo = figura.add_subplot()
    rotulos = []
    presentes = set()
    for i, modelo in enumerate(modelos):
        y = n - 1 - i
        est = estilos[modelo]
        dif = difs[modelo]
        if dif is None or dif["valor"] is None:  # indisponível: sem ponto, sem IC
            rotulos.append(est["rotulo_completo"] + " (sem estimativa)")
            continue
        rotulos.append(est["rotulo_completo"])
        presentes.add(dif["leitura"])
        cor = COR_LEITURA[dif["leitura"]]
        valor = float(dif["valor"])
        lo, hi = ((_nan(dif["ic95"][0]), _nan(dif["ic95"][1])) if dif["ic95"] is not None
                  else (float("nan"), float("nan")))
        _ponto_com_ic(eixo, valor, lo, hi, y, est, horizontal=True, cor=cor)
        extremo = hi if math.isfinite(hi) else valor
        eixo.annotate(f"{_num(valor, 4)} ({dif['leitura']})", (extremo, y), xytext=(8, 0),
                      textcoords="offset points", va="center", fontsize=8, color=cor)
    eixo.set_yticks(range(n), rotulos[::-1])
    eixo.set_ylim(-0.6, n - 0.4)
    eixo.axvline(0, color=COR_CINZA, linestyle="--", linewidth=1)
    eixo.margins(x=0.3)
    _decimal_ptbr(eixo.xaxis)
    eixo.set_title(f"Diferença de PR-AUC contra o {ROTULO.get(ref, ref)} "
                   "(população principal)")
    eixo.set_xlabel("diferença de PR-AUC contra o M1 (IC 95%, pareado)")
    eixo.set_ylabel("modelo")
    handles = [Line2D([], [], marker="s", linestyle="none", color=COR_LEITURA[leitura],
                      label=leitura)
               for leitura in LEITURAS if leitura in presentes]
    if any(estilos[m]["externo"] for m in modelos):
        handles.append(_proxy_externo())
    _acabamento(figura, _rodape(agregados, "Cor: leitura do IC pareado."), handles,
                ncol=max(1, len(handles)))
    return figura


def _figura_orcamentos(agregados: dict, estilos: dict) -> Figure:
    modelos = agregados["modelos"]
    orc = agregados["orcamentos"]["principal"]
    n = len(modelos)
    figura = Figure(figsize=(10.5, 5.2))
    eixos = figura.subplots(1, 2)
    rotulos_x = []
    for b in ORCAMENTOS:
        alertas = next((orc[m][b]["alertas"] for m in modelos if orc.get(m)), None)
        texto = _pct(float(b))
        rotulos_x.append(texto if alertas is None else f"{texto}\n{_alertas_texto(alertas)}")
    for eixo, metrica, titulo in zip(eixos, ("recall", "precisao"),
                                     ("Recall (sensibilidade)", "Precisão"), strict=True):
        for pos, modelo in enumerate(modelos):
            est = estilos[modelo]
            desloc = (pos - (n - 1) / 2) * (0.5 / max(n - 1, 1))
            xs, ys = [], []
            for j, b in enumerate(ORCAMENTOS):
                celula = (orc.get(modelo) or {}).get(b)
                ponto = _ponto(celula[metrica]) if celula else None
                if ponto is None:
                    continue
                valor, lo, hi = ponto
                x = j + desloc
                if math.isfinite(lo) and math.isfinite(hi):
                    eixo.vlines(x, lo, hi, color=est["cor"], linewidth=1.0)
                xs.append(x)
                ys.append(valor)
            if xs:
                eixo.plot(xs, ys, color=est["cor"], linestyle=est["traco"], linewidth=1.1,
                          marker=est["marcador"],
                          markerfacecolor="white" if est["externo"] else est["cor"],
                          markeredgecolor=est["cor"], markersize=6,
                          label=est["rotulo_completo"])
        eixo.set_xticks(range(len(ORCAMENTOS)), rotulos_x)
        eixo.set_xlim(-0.5, len(ORCAMENTOS) - 0.5)
        eixo.set_ylim(bottom=0)
        eixo.yaxis.set_major_formatter(FuncFormatter(lambda v, _p: _pct(v)))
        eixo.set_title(titulo)
        eixo.set_xlabel("orçamento de alertas (% dos casos de maior risco)")
        eixo.set_ylabel("proporção")
    handles, _ = eixos[0].get_legend_handles_labels()
    if any(estilos[m]["externo"] for m in modelos):
        handles.append(_proxy_externo())
    _acabamento(figura, _rodape(agregados, "Recall: fração dos eventos entre os alertas; "
                                           "precisão: fração dos alertas que são eventos."),
                handles, ncol=min(n, 4))
    return figura


def _figura_calibracao(agregados: dict, estilos: dict) -> Figure:
    modelos = agregados["modelos"]
    cal = agregados["calibracao"]
    pr = agregados["metricas"]["principal"]
    cols = min(3, len(modelos))
    rows = math.ceil(len(modelos) / cols)

    todos = []
    for m in modelos:
        for c in _caixas_publicaveis(cal[m]):
            todos.extend([c["previsto"], c["observado"]] + list(c["ic95"] or []))
    todos = [v for v in todos if v is not None and v > 0]
    if todos:
        lim = (min(todos) * 0.7, max(todos) * 1.4)
    else:
        lim = (1e-4, 1e-2)

    figura = Figure(figsize=(5.0 * cols, 4.6 * rows + 0.8))
    eixos = figura.subplots(rows, cols, squeeze=False).flatten()
    handles = [Line2D([], [], color="#777777", linestyle="--", label="calibração perfeita")]
    for ax, m in zip(eixos, modelos, strict=False):
        est = estilos[m]
        caixas = _caixas_publicaveis(cal[m])
        ax.plot(lim, lim, color="#777777", linestyle="--", linewidth=1)
        if caixas:
            xs = [c["previsto"] for c in caixas]
            ys = [c["observado"] for c in caixas]
            for c in caixas:
                if c["ic95"] is not None:
                    lo = max(c["ic95"][0], lim[0])
                    ax.vlines(c["previsto"], lo, c["ic95"][1], color=est["cor"], linewidth=1.2)
            ax.plot(xs, ys, linestyle="none", marker=est["marcador"],
                    markerfacecolor="white" if est["externo"] else est["cor"],
                    markeredgecolor=est["cor"], markersize=6)
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_xlim(lim)
            ax.set_ylim(lim)
            _eixo_log_em_percentual(ax)
            handles.append(Line2D([], [], linestyle="none", marker=est["marcador"],
                                  markerfacecolor="white" if est["externo"] else est["cor"],
                                  markeredgecolor=est["cor"], color=est["cor"],
                                  label=est["rotulo_completo"]))
        else:  # mesma escala logarítmica dos demais painéis, sem caixas
            ax.set_xscale("log")
            ax.set_yscale("log")
            ax.set_xlim(lim)
            ax.set_ylim(lim)
            _eixo_log_em_percentual(ax)
            ax.text(0.5, 0.5, "sem caixa publicável\n(modelo não estima a população)",
                    ha="center", va="center", transform=ax.transAxes, fontsize=9)
        slope = (_metrica(pr[m], "calibration_slope") or {}).get("valor")
        obs_esp = (_metrica(pr[m], "obs_esp") or {}).get("valor")
        partes = []
        if slope is not None:
            partes.append(f"inclinação {_num(slope, 3)}")
        if obs_esp is not None:
            partes.append(f"obs/esp {_num(obs_esp, 3)}")
        titulo = f"Calibração de {est['rotulo_completo']}"
        ax.set_title(titulo + (f"\n({'; '.join(partes)})" if partes else ""), fontsize=10)
        ax.set_xlabel("risco previsto médio da caixa")
        ax.set_ylabel("taxa observada na caixa")
    for ax in eixos[len(modelos):]:
        ax.set_visible(False)
    total = sum(len(cal[m] or []) for m in modelos)
    publicaveis = sum(len(_caixas_publicaveis(cal[m])) for m in modelos)
    _acabamento(figura, _rodape(agregados, "Eixos logarítmicos; barras: IC 95%. Caixas sem "
                                           "ponto (taxa suprimida pelo R7 ou zero): "
                                           f"{total - publicaveis} de {total}."),
                handles, ncol=min(4, len(handles)))
    return figura


def _eixo_log_em_percentual(eixo) -> None:
    """Eixos logarítmicos em % com 1, 2 e 5 por década (igual a teste_graficos)."""
    for lado in (eixo.xaxis, eixo.yaxis):
        lado.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
        lado.set_major_formatter(FuncFormatter(lambda v, _p: _pct(v)))
        lado.set_minor_formatter(NullFormatter())


def _figura_curva_decisao(agregados: dict, estilos: dict) -> Figure:
    modelos = agregados["modelos"]
    curva = agregados["curva_decisao"]
    limiares = curva["limiares"]
    x = [100 * t for t in limiares]
    prev = agregados["populacoes"]["principal"]["prevalencia"]
    figura = Figure(figsize=(9, 5.8))
    eixo = figura.add_subplot()
    topo = 0.0
    for m in modelos:
        est = estilos[m]
        ys = [_nan(v) for v in curva[m]]
        eixo.plot(x, ys, color=est["cor"], linestyle=est["traco"], linewidth=1.5,
                  marker=est["marcador"],
                  markerfacecolor="white" if est["externo"] else est["cor"],
                  markeredgecolor=est["cor"], markersize=5, markevery=max(1, len(x) // 10),
                  label=est["rotulo_completo"])
        finitos = [v for v in ys if math.isfinite(v)]
        if finitos:
            topo = max(topo, max(finitos))
    tratar_todos = [prev - (1 - prev) * t / (1 - t) for t in limiares]
    eixo.plot(x, tratar_todos, color="#777777", linestyle="--", linewidth=1.2,
              label="tratar todos")
    eixo.axhline(0.0, color="#333333", linewidth=0.8, label="tratar ninguém")
    if topo > 0:
        eixo.set_ylim(-0.25 * topo, 1.15 * topo)
    eixo.set_xlim(min(x), max(x))
    _decimal_ptbr(eixo.xaxis)
    _decimal_ptbr(eixo.yaxis)
    eixo.set_title("Curva de decisão (população principal)")
    eixo.set_xlabel("limiar de risco (%)")
    eixo.set_ylabel("benefício líquido (net benefit)")
    handles, _ = eixo.get_legend_handles_labels()
    if any(estilos[m]["externo"] for m in modelos):
        handles.append(_proxy_externo())
    _acabamento(figura, _rodape(agregados, "Eixo vertical cortado no fundo para manter a escala "
                                           "útil."), handles, ncol=min(4, len(handles)))
    return figura


def _sim_nao(valor) -> str:
    if valor is None:
        return "n/d"
    return "sim" if valor else "não"


def _figura_conformidade(agregados: dict, estilos: dict) -> Figure:
    modelos = agregados["modelos"]
    conf = agregados["conformidade"]
    colunas = ["R3: sem correção de\ndesbalanceamento", "R4: variáveis\nno dicionário",
               "Treino sem 2025", "Versões iguais\nàs do treino", "Externo\n(outra branch)"]
    linhas, cores, rotulos = [], [], []
    for m in modelos:
        c = conf[m]
        versoes = None if c["versoes_diferentes_do_treino"] is None \
            else not c["versoes_diferentes_do_treino"]
        valores = [_sim_nao(c["r3_sem_correcao"]), _sim_nao(c["r4_variaveis_no_dicionario"]),
                   _sim_nao(c["treino_sem_ano_de_comparacao"]), _sim_nao(versoes),
                   "sim" if c["externo"] else "não"]
        linhas.append(valores)
        cores.append([COR_CONFORMIDADE[v] if i < 4 else COR_CONFORMIDADE["neutro"]
                      for i, v in enumerate(valores)])
        rotulos.append(estilos[m]["rotulo_completo"])
    figura = Figure(figsize=(11, 0.6 * len(modelos) + 2.4))
    eixo = figura.add_subplot()
    eixo.axis("off")
    tabela = eixo.table(cellText=linhas, rowLabels=rotulos, colLabels=colunas,
                        cellColours=cores, loc="center", cellLoc="center")
    tabela.auto_set_font_size(False)
    tabela.set_fontsize(9)
    tabela.scale(1, 1.9)
    eixo.set_title("Conformidade por modelo (R3, R4, treino sem 2025, versões e externo)")
    _acabamento(figura, _rodape(agregados, "sim = conforme; não = desvio; n/d = sem "
                                           "informação ou não se aplica. Externo: modelo de "
                                           "outra branch, carregado em ambiente isolado."),
                ajustar=True)
    return figura


# --- Entrada -----------------------------------------------------------------------------------

def gerar_graficos(agregados: dict, destino: Path) -> list[Path]:
    """Valida `agregados` (recusa fora do contrato, sem criar nada) e grava as seis figuras em
    `destino`. Devolve os caminhos na ordem de `FIGURAS`."""
    validar(agregados)
    destino = Path(destino)
    destino.mkdir(parents=True, exist_ok=True)
    estilos = estilos_dos_modelos(agregados)
    figuras = (
        (ARQ_PR_AUC, _figura_pr_auc(agregados, estilos)),
        (ARQ_DIFERENCAS, _figura_diferencas(agregados, estilos)),
        (ARQ_ORCAMENTOS, _figura_orcamentos(agregados, estilos)),
        (ARQ_CALIBRACAO, _figura_calibracao(agregados, estilos)),
        (ARQ_CURVA_DECISAO, _figura_curva_decisao(agregados, estilos)),
        (ARQ_CONFORMIDADE, _figura_conformidade(agregados, estilos)),
    )
    return [_salvar(figura, destino / nome) for nome, figura in figuras]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Gráficos comparativos de 2025 (T-8.8), só a partir de metricas.json.")
    parser.add_argument("--agregados", type=Path, required=True,
                        help="caminho do metricas.json (reports/comparacao/metricas.json)")
    parser.add_argument("--destino", type=Path, required=True,
                        help="pasta onde gravar os PNG (reports/comparacao)")
    args = parser.parse_args(argv)
    agregados = json.loads(args.agregados.read_text(encoding="utf-8"))
    for caminho in gerar_graficos(agregados, args.destino):
        print(caminho)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
