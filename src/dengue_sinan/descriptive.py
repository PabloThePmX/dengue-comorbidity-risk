"""Análise descritiva da população de desenvolvimento (FR-18). Só agregados."""

import numpy as np
import pandas as pd

from dengue_sinan.metrics import _wilson
from dengue_sinan.profiling import COMORBIDADES, FAIXAS_ROTULOS, code

MINIMO = 10  # supressão de célula pequena (NFR-03, SC-05)


def _fmt_n(n: int, total: int) -> str:
    if n < MINIMO:
        return "<10"
    return f"{n:,} ({100 * n / total:.1f}%)".replace(",", " ")


def tabela_caracteristicas(pop: pd.DataFrame, x: pd.DataFrame) -> pd.DataFrame:
    """\"Tabela 1\": características por desfecho (y = 0 × y = 1). Contagens < 10 viram \"<10\"."""
    y = pop["y"].to_numpy()
    grupos = {"Total": np.ones(len(pop), bool), "y = 0": y == 0, "y = 1": y == 1}
    n_com = x["n_comorbidades"].clip(upper=3).astype(int).astype(str).replace({"3": "3+"})
    raca = code(pop["CS_RACA"]).fillna("branco")
    blocos = [
        ("Faixa etária", pop["faixa_etaria"].astype("string")),
        ("Sexo", x["sexo"].astype("string")),
        ("Gestante (CS_GESTANT 1–4)", pop["gestante"].map({True: "sim", False: "não"})),
        ("Raça/cor (CS_RACA; 9 = ignorado)", raca.astype("string")),
        ("Nº de comorbidades", n_com.astype("string")),
    ]
    linhas = []
    idade = pop["idade_anos"]
    linha = {"variável": "Idade (anos)", "categoria": "mediana [IQR]"}
    for nome, m in grupos.items():
        q = idade[m].quantile([0.25, 0.5, 0.75]).to_numpy()
        linha[nome] = f"{q[1]:.1f} [{q[0]:.1f}–{q[2]:.1f}]"
    linhas.append(linha)
    for titulo, serie in blocos:
        ordem = (
            FAIXAS_ROTULOS if titulo == "Faixa etária" else sorted(serie.dropna().unique(), key=str)
        )
        for cat in ordem:
            linha = {"variável": titulo, "categoria": cat}
            for nome, m in grupos.items():
                linha[nome] = _fmt_n(int(((serie == cat).to_numpy() & m).sum()), int(m.sum()))
            linhas.append(linha)
    for c in COMORBIDADES:
        linha = {"variável": "Comorbidade (Sim)", "categoria": c}
        for nome, m in grupos.items():
            linha[nome] = _fmt_n(int(((x[c] == "Sim").to_numpy() & m).sum()), int(m.sum()))
        linhas.append(linha)
    return pd.DataFrame(linhas)


def risco_bruto(grupo: pd.Series, y: pd.Series, minimo: int = MINIMO) -> pd.DataFrame:
    """Risco bruto de y = 1 por categoria, com IC 95% de Wilson. Eventos < `minimo` → suprimido."""
    d = pd.DataFrame({"g": grupo.astype("string").to_numpy(), "y": np.asarray(y)}).dropna()
    t = d.groupby("g")["y"].agg(eventos="sum", casos="size")
    t["risco_%"] = 100 * t["eventos"] / t["casos"]
    lo, hi = _wilson(t["eventos"], t["casos"])
    t["ic95_inf_%"], t["ic95_sup_%"] = 100 * lo, 100 * hi
    t["suprimido"] = t["eventos"] < minimo
    t.loc[t["suprimido"], ["eventos", "risco_%", "ic95_inf_%", "ic95_sup_%"]] = np.nan
    t.index.name = "categoria"
    return t.reset_index()


def riscos_brutos(pop: pd.DataFrame, x: pd.DataFrame) -> dict[str, pd.DataFrame]:
    y = pop["y"]
    por_comorb = []
    for c in COMORBIDADES:
        t = risco_bruto(x[c].where(x[c].isin(["Sim", "Não"])), y)
        t.insert(0, "comorbidade", c)
        por_comorb.append(t)
    n_com = x["n_comorbidades"].clip(upper=3).astype(int).astype(str).replace({"3": "3+"})
    faixa = risco_bruto(pop["faixa_etaria"], y)
    faixa["_o"] = faixa["categoria"].map({r: i for i, r in enumerate(FAIXAS_ROTULOS)})
    return {
        "por_comorbidade": pd.concat(por_comorb, ignore_index=True),
        "por_n_comorbidades": risco_bruto(n_com, y),
        "por_faixa_etaria": faixa.sort_values("_o").drop(columns="_o"),
    }
