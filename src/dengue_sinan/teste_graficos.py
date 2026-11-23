"""Gráficos da avaliação no teste (T-5.2, D-66): desenhados localmente a partir dos agregados.

Lê só `metricas.json` de `reports/teste/` (curvas, caixas e subgrupos já agregados, R7). Não carrega
modelo nem dados e não importa pandas. Antes de desenhar, confere o SHA-256 do `metricas.json`
contra o `LACRE.json`: um arquivo alterado ou trocado não vira gráfico.

Figuras (PNG, backend Agg):
- `decisao.png`: curva de decisão de M1, B1 e B2 com bandas de IC 95%, "tratar todos" e "ninguém";
  marca no M1 o limiar principal (D-92) e o F2 (secundário);
- `calibracao.png`: calibração por caixas de M1 e E1 com bandas, eixos logarítmicos (o risco é
  baixo) e a diagonal da calibração perfeita;
- `subgrupos_pr_auc.png` e `subgrupos_recall.png`: floresta dos subgrupos com IC 95% e aviso de IC
  largo. Legenda obrigatória nas de subgrupo: associação não é causa e diferenças de notificação
  não são diferenças de risco.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter, LogLocator, NullFormatter

ARQ_LACRE = "LACRE.json"
ARQ_JSON = "metricas.json"
ARQ_DECISAO_PNG = "decisao.png"
ARQ_CALIBRACAO_PNG = "calibracao.png"
ARQ_SUBGRUPOS_PR_AUC_PNG = "subgrupos_pr_auc.png"
ARQ_SUBGRUPOS_RECALL_PNG = "subgrupos_recall.png"
LEGENDA_SUBGRUPOS = ("Associação não é causa; diferenças de notificação não são diferenças de "
                     "risco.")
LEGENDA_GERAL = ("Avaliação única em 2024 (R2); só agregados (R7). Bandas e barras: IC 95% "
                 "(bootstrap).")
COR = {"M1": "#1b6ca8", "B1": "#d98324", "B2": "#4c9a5f", "E1": "#8a4fa3"}


def _sha256_texto(texto: str) -> str:
    return hashlib.sha256(texto.encode("utf-8")).hexdigest()


def carregar_agregados(pasta: str | Path) -> dict:
    """`metricas.json` de `pasta`, depois de conferir o SHA-256 dele com o `LACRE.json`. Levanta
    FileNotFoundError sem lacre e ValueError se o hash não bate ou se não é o JSON do teste."""
    pasta = Path(pasta)
    caminho_lacre = pasta / ARQ_LACRE
    if not caminho_lacre.exists():
        raise FileNotFoundError(f"sem {ARQ_LACRE} em {pasta}: só se desenha o que foi lacrado")
    lacre = json.loads(caminho_lacre.read_text(encoding="utf-8"))
    texto = (pasta / ARQ_JSON).read_text(encoding="utf-8")
    if _sha256_texto(texto) != lacre.get("relatorios", {}).get(ARQ_JSON):
        raise ValueError(f"{ARQ_JSON} em {pasta} não confere com o {ARQ_LACRE} (SHA-256): "
                         "arquivo alterado ou trocado")
    dados = json.loads(texto)
    if dados.get("modo") != "teste":
        raise ValueError(f"{ARQ_JSON} não é o da avaliação do teste")
    faltando = [a for a in ("metricas", "decisao", "calibracao", "subgrupos")
                if a not in dados.get("analises", {})]
    if faltando:
        raise ValueError(f"{ARQ_JSON} sem as análises: {', '.join(faltando)}")
    return dados


ORDEM_MODELOS = ("M1", "B1", "B2", "E1")


def _modelos_na_ordem(nomes) -> list[str]:
    """M1 primeiro (o JSON grava as chaves em ordem alfabética)."""
    return sorted(nomes, key=lambda n: (ORDEM_MODELOS.index(n) if n in ORDEM_MODELOS else 99, n))


def _legenda(figura: Figure, texto: str) -> None:
    """Legenda obrigatória no pé da figura, com espaço reservado (o layout não conta fig.text)."""
    figura.tight_layout(rect=(0, 0.06, 1, 1))
    figura.text(0.01, 0.015, texto, fontsize=8, color="#555555")


def _salvar(figura: Figure, caminho: Path) -> Path:
    FigureCanvasAgg(figura)
    figura.savefig(caminho, dpi=130)
    return caminho


def _figura_decisao(j: dict, saida: Path) -> Path:
    pct = [100 * t for t in j["limiares"]]
    figura = Figure(figsize=(8.5, 5.5))
    eixo = figura.add_subplot()
    topo = 0.0
    for nome in _modelos_na_ordem(j["curvas"]):
        curva = j["curvas"][nome]
        eixo.fill_between(pct, curva["ic_inf"], curva["ic_sup"], color=COR.get(nome), alpha=0.2,
                          linewidth=0)
        eixo.plot(pct, curva["nb"], color=COR.get(nome), label=nome)
        topo = max(topo, max(curva["ic_sup"]))
    eixo.plot(pct, j["tratar_todos"]["nb"], color="#777777", linestyle="--",
              label="tratar todos")
    eixo.axhline(0.0, color="#333333", linewidth=0.8, label="tratar ninguém")
    notas = []
    estilo = {"M1_principal": ("o", "limiar principal (recall ≥ B2, D-92)"),
              "M1_f2": ("s", "limiar F2 (secundário)")}
    for nome, ponto in j["pontos_marcados"].items():
        marcador, rotulo = estilo.get(nome, ("x", nome))
        if ponto["nb"] is not None and ponto["dentro_da_faixa"]:
            eixo.plot([100 * ponto["limiar"]], [ponto["nb"]["valor"]], marker=marcador,
                      color=COR["M1"], markeredgecolor="black", markersize=8, linestyle="none",
                      label=f"M1: {rotulo}")
        else:
            notas.append(f"{rotulo}: {100 * ponto['limiar']:.2f}%, fora do intervalo do gráfico")
    if topo > 0:
        eixo.set_ylim(-0.25 * topo, 1.15 * topo)  # "tratar todos" cai fora da escala útil
    eixo.set_xlabel("limiar de risco (%)")
    eixo.set_ylabel("net benefit")
    eixo.set_title("Curva de decisão no teste (2024)")
    eixo.legend(fontsize=8, loc="upper right")
    _legenda(figura, LEGENDA_GERAL + (" " + "; ".join(notas) + "." if notas else ""))
    return _salvar(figura, saida)


def _em_percentual(valor: float, _posicao=None) -> str:
    """Rótulo de um risco (fração) em %, com vírgula decimal e só os algarismos necessários."""
    return f"{100 * valor:.3g}".replace(".", ",") + "%"


def _eixo_log_em_percentual(eixo) -> None:
    """Eixos logarítmicos em %: só 1, 2 e 5 por década, sem rótulos nos ticks menores (a notação
    científica dos rótulos menores se sobrepunha quando a faixa tem menos de uma década)."""
    for lado in (eixo.xaxis, eixo.yaxis):
        lado.set_major_locator(LogLocator(base=10, subs=(1.0, 2.0, 5.0)))
        lado.set_major_formatter(FuncFormatter(_em_percentual))
        lado.set_minor_formatter(NullFormatter())


def _figura_calibracao(j: dict, saida: Path) -> Path:
    modelos = _modelos_na_ordem(j["modelos"])
    figura = Figure(figsize=(5.6 * len(modelos), 5.4))
    for i, nome in enumerate(modelos):
        eixo = figura.add_subplot(1, len(modelos), i + 1)
        caixas = [c for c in j["modelos"][nome]["caixas"]
                  if c["taxa_observada"] and c["taxa_observada"] > 0 and c["ic95"]]
        prev = [c["risco_previsto_medio"] for c in caixas]
        taxa = [c["taxa_observada"] for c in caixas]
        inf = [max(t - c["ic95"][0], 0.0) for t, c in zip(taxa, caixas, strict=True)]
        sup = [max(c["ic95"][1] - t, 0.0) for t, c in zip(taxa, caixas, strict=True)]
        if caixas:
            teto = max(max(prev), max(c["ic95"][1] for c in caixas))
            lim = (min(min(prev), min(taxa)) * 0.7, teto * 1.4)
            eixo.plot(lim, lim, color="#777777", linestyle="--", label="calibração perfeita")
            eixo.errorbar(prev, taxa, yerr=[inf, sup], fmt="o", color=COR.get(nome), capsize=3,
                          label=f"{nome}: caixas por quantil")
            eixo.set_xscale("log")
            eixo.set_yscale("log")
            eixo.set_xlim(lim)
            eixo.set_ylim(lim)
            _eixo_log_em_percentual(eixo)
        else:  # nenhuma caixa com taxa publicável (R7) ou todas com taxa zero: sem eixo log vazio
            eixo.text(0.5, 0.5, "sem caixa com taxa publicável", ha="center", va="center",
                      transform=eixo.transAxes)
            eixo.plot([], [], color="#777777", linestyle="--", label="calibração perfeita")
        g = j["modelos"][nome].get("global") or {}
        slope = (g.get("slope") or {}).get("valor")
        oe = (g.get("obs_esp") or {}).get("valor")
        partes = [f"{rotulo} {valor:.3f}".replace(".", ",")
                  for rotulo, valor in (("slope", slope), ("obs/esp", oe)) if valor is not None]
        extra = ", ".join(partes)
        eixo.set_title(f"Calibração de {nome}" + (f" ({extra})" if extra else ""), fontsize=10)
        eixo.set_xlabel("risco previsto médio da caixa")
        eixo.set_ylabel("taxa observada na caixa")
        # Legenda abaixo do eixo: dentro dele cobria pontos e barras de erro.
        eixo.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.17), ncol=2,
                    frameon=False)
    _legenda(figura, LEGENDA_GERAL + " Eixos logarítmicos; caixas com taxa suprimida ou zero "
                                     "não aparecem.")
    return _salvar(figura, saida)


def _linhas_floresta(j: dict, chave: str) -> list[dict]:
    """Uma linha por subgrupo: rótulo, métrica (valor e IC) e a referência da regra B2."""
    linhas = []
    for chave_dimensao in j.get("ordem_dimensoes", list(j["dimensoes"])):
        dimensao = j["dimensoes"][chave_dimensao]
        for rotulo in dimensao.get("ordem", list(dimensao["subgrupos"])):
            s = dimensao["subgrupos"][rotulo]
            m = s["metricas"]
            linhas.append({
                "dimensao": dimensao["nome"], "rotulo": rotulo, "largo": bool(s["aviso_ic_largo"]),
                "bloco": m[chave] if m else None,
                "b2": m.get("regra_b2_recall") if (m and chave == "recall") else None,
            })
    return linhas


def _figura_floresta(j: dict, chave: str, titulo: str, referencia: float | None,
                     saida: Path) -> Path:
    linhas = _linhas_floresta(j, chave)
    figura = Figure(figsize=(9, 0.28 * len(linhas) + 2.4))
    eixo = figura.add_subplot()
    nomes = []
    for i, linha in enumerate(linhas):
        y = len(linhas) - 1 - i
        nomes.append(f"{linha['dimensao']}: {linha['rotulo']}"
                     + (" (IC largo)" if linha["largo"] else "")
                     + ("" if linha["bloco"] else " (sem métricas)"))
        bloco = linha["bloco"]
        if bloco and bloco["valor"] is not None:
            cor = "#b5651d" if linha["largo"] else COR["M1"]
            if bloco["ic95"]:
                eixo.hlines(y, bloco["ic95"][0], bloco["ic95"][1], color=cor, linewidth=2)
            eixo.plot([bloco["valor"]], [y], "o", color=cor)
        b2 = linha["b2"]
        if b2 and b2["valor"] is not None:
            eixo.plot([b2["valor"]], [y], "D", markerfacecolor="none", color=COR["B2"],
                      markersize=5)
    eixo.set_yticks(range(len(linhas)), nomes[::-1], fontsize=7)
    if referencia is not None:
        eixo.axvline(referencia, color="#777777", linestyle="--", linewidth=1,
                     label="M1 em todo o teste")
    if chave == "recall":
        eixo.plot([], [], "D", markerfacecolor="none", color=COR["B2"], label="regra B2")
    if referencia is not None or chave == "recall":
        eixo.legend(fontsize=8, loc="lower right")
    eixo.set_xlabel(titulo + " (IC 95%)")
    eixo.set_title(f"{titulo} por subgrupo, M1 no limiar principal"
                   if chave == "recall" else f"{titulo} por subgrupo, M1")
    _legenda(figura, LEGENDA_SUBGRUPOS + " Laranja: IC largo, sem conclusões.")
    return _salvar(figura, saida)


def desenhar(pasta: str | Path, saida: str | Path | None = None) -> list[Path]:
    """Grava as quatro figuras em `saida` (padrão: a própria `pasta`) e devolve os caminhos.
    Levanta ValueError se o SHA-256 do `metricas.json` não bate com o lacre, e FileNotFoundError sem
    lacre. O lacre e o hash são conferidos ANTES de criar a pasta de saída: se falharem, nada é
    criado (nem um diretório vazio)."""
    pasta = Path(pasta)
    dados = carregar_agregados(pasta)
    destino = pasta if saida is None else Path(saida)
    destino.mkdir(parents=True, exist_ok=True)
    analises = dados["analises"]
    metricas_m1 = analises["metricas"]["modelos"]["M1"]
    return [
        _figura_decisao(analises["decisao"], destino / ARQ_DECISAO_PNG),
        _figura_calibracao(analises["calibracao"], destino / ARQ_CALIBRACAO_PNG),
        _figura_floresta(analises["subgrupos"], "pr_auc", "PR-AUC",
                         metricas_m1["pr_auc"]["valor"], destino / ARQ_SUBGRUPOS_PR_AUC_PNG),
        _figura_floresta(analises["subgrupos"], "recall", "Recall",
                         metricas_m1["no_limiar"]["recall"]["valor"],
                         destino / ARQ_SUBGRUPOS_RECALL_PNG),
    ]
