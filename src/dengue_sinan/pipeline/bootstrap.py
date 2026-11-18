"""Bootstrap por conglomerado (município), estratificado por região.

Em cada réplica, para cada região, sorteiam-se com reposição tantos municípios quantos a região
tem, e todas as linhas de um município sorteado entram juntas (multiplicidade = nº de sorteios).
As cinco dobras LORO ficam fixas: a incerteza vem de quais municípios compõem cada região.

Limitações (ver relatório): municípios muito desiguais em tamanho, dependência entre municípios
vizinhos (surtos regionais) que o bootstrap por município não captura, e o fato de o modelo de
cada dobra ser ajustado uma única vez (a variação do ajuste não entra neste intervalo).
"""

import numpy as np

from dengue_sinan.pipeline.metricas import (
    METRICAS,
    TabelaNiveis,
    metricas_todas,
)


def pesos_bootstrap(t: TabelaNiveis, replicacoes: int, seed: int) -> np.ndarray:
    """Matriz (B, C) de multiplicidades inteiras. Mesma semente, mesma matriz."""
    rng = np.random.default_rng(seed)
    pesos = np.zeros((replicacoes, len(t.conglomerados)), dtype="float64")
    for r in t.regioes:  # ordem fixa das regiões
        idx = t.indice_regiao[r]
        pesos[:, idx] = rng.multinomial(
            len(idx), np.full(len(idx), 1.0 / len(idx)), size=replicacoes
        )
    return pesos


def intervalo(valores: np.ndarray, nivel: float = 0.95) -> dict:
    """Intervalo percentil sobre as réplicas válidas; réplicas sem a métrica ficam de fora."""
    v = np.asarray(valores, dtype="float64")
    validas = v[np.isfinite(v)]
    out = {"n_replicacoes": int(len(v)), "n_validas": int(len(validas))}
    if len(validas) < 2:
        return out | {"ic_inf": np.nan, "ic_sup": np.nan, "ep_bootstrap": np.nan}
    a = (1 - nivel) / 2
    inf, sup = np.quantile(validas, [a, 1 - a])
    return out | {
        "ic_inf": float(inf),
        "ic_sup": float(sup),
        "ep_bootstrap": float(validas.std(ddof=1)),
    }


def executar_bootstrap(
    t: TabelaNiveis,
    modelos: list[str],
    replicacoes: int,
    seed: int,
    nivel: float = 0.95,
    referencia: str = "m1",
    lote: int = 250,
) -> dict:
    """Estimativas pontuais, ICs por métrica/escopo e diferenças `referencia − baseline`."""
    pontual = metricas_todas(t, modelos)
    pesos = pesos_bootstrap(t, replicacoes, seed)
    rep = {}
    for ini in range(0, replicacoes, lote):
        parcial = metricas_todas(t, modelos, pesos[ini : ini + lote])
        for chave, mets in parcial.items():
            destino = rep.setdefault(chave, {k: [] for k in (*METRICAS, "n", "eventos")})
            for k in destino:
                destino[k].append(mets[k])
    rep = {c: {k: np.concatenate(v) for k, v in m.items()} for c, m in rep.items()}
    resultado = []
    for (modelo, escopo), mets in rep.items():
        for metrica in METRICAS:
            ic = intervalo(mets[metrica], nivel)
            resultado.append(
                {
                    "modelo": modelo,
                    "escopo": escopo,
                    "metrica": metrica,
                    "estimativa": float(pontual[(modelo, escopo)][metrica][0]),
                    **ic,
                }
            )
    diferencas = []
    if referencia in modelos:
        for outro in (m for m in modelos if m != referencia):
            for escopo in {e for (_, e) in rep}:
                for metrica in ("pr_auc", "roc_auc", "brier", "bss"):
                    d = rep[(referencia, escopo)][metrica] - rep[(outro, escopo)][metrica]
                    est = (
                        pontual[(referencia, escopo)][metrica] - pontual[(outro, escopo)][metrica]
                    )[0]
                    diferencas.append(
                        {
                            "comparacao": f"{referencia} − {outro}",
                            "escopo": escopo,
                            "metrica": metrica,
                            "estimativa": float(est),
                            **intervalo(d, nivel),
                        }
                    )
    meio = replicacoes // 2
    estab = []
    for mets in rep.values():
        for metrica in ("pr_auc", "roc_auc", "brier"):
            a, b = intervalo(mets[metrica][:meio], nivel), intervalo(mets[metrica][meio:], nivel)
            largura = (a["ic_sup"] - a["ic_inf"] + b["ic_sup"] - b["ic_inf"]) / 2
            if np.isfinite(largura) and largura > 0:
                estab.append(
                    max(abs(a["ic_inf"] - b["ic_inf"]), abs(a["ic_sup"] - b["ic_sup"])) / largura
                )
    invalidas = {
        f"{m}|{e}|{k}": int(np.sum(~np.isfinite(v[k])))
        for (m, e), v in rep.items()
        for k in METRICAS
        if np.any(~np.isfinite(v[k]))
    }
    return {
        "pontual": pontual,
        "resultado": resultado,
        "diferencas": diferencas,
        "diagnostico": {
            "replicacoes": replicacoes,
            "seed": seed,
            "nivel": nivel,
            "replicacoes_invalidas_por_metrica": invalidas,
            "estabilidade_entre_metades_max_relativa_a_largura": (
                float(max(estab)) if estab else None
            ),
        },
    }
