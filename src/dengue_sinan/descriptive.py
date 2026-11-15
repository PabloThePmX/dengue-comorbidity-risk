"""Análise descritiva da população de desenvolvimento e pares/combinações (T-2.6, T-2.7)."""

import itertools
from pathlib import Path
from typing import Any

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from dengue_sinan import profiling
from dengue_sinan.dataset import COMORBIDADES, build_feature_frame
from dengue_sinan.guard import assert_dev_only
from dengue_sinan.verify import check, write_report

matplotlib.use("Agg")

DISCLAIMER_HEADER = "Riscos brutos, descritivos; não substituem o E1."
_Z_95 = 1.959963984540054


def wilson_ci(
    events: int | float,
    total: int | float,
    z: float = _Z_95,
) -> tuple[float, float, float]:
    """Calcula a proporção e o intervalo de confiança de 95% de Wilson."""
    n = float(total)
    if n <= 0:
        return 0.0, 0.0, 0.0
    k = float(events)
    p = k / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2.0 * n)) / denom
    half = (z / denom) * np.sqrt((p * (1.0 - p) / n) + (z2 / (4.0 * n * n)))
    return float(p), float(max(0.0, center - half)), float(min(1.0, center + half))


def suppress_small_cells(
    df: pd.DataFrame,
    count_cols: list[str],
    min_cell: int = 10,
    mask_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Suprime células `< min_cell` (R7), trocando por `<10` e mascarando colunas derivadas."""
    out = df.copy()
    row_suppressed = pd.Series(False, index=out.index)

    for col in count_cols:
        if col not in out.columns:
            continue
        num = pd.to_numeric(out[col], errors="coerce")
        small = num.notna() & (num < int(min_cell))
        row_suppressed = row_suppressed | small
        out[col] = out[col].astype("object")
        out.loc[small, col] = f"<{min_cell}"

    if mask_cols:
        for mcol in mask_cols:
            if mcol in out.columns:
                out[mcol] = out[mcol].astype("object")
                out.loc[row_suppressed, mcol] = f"<{min_cell}"

    return out


def _ensure_feature_cols(df: pd.DataFrame) -> pd.DataFrame:
    assert_dev_only(df)
    if "n_comorbidades" not in df.columns or "sexo" not in df.columns:
        return build_feature_frame(df)
    return df


def table1_characteristics(df: pd.DataFrame, min_cell: int = 10) -> pd.DataFrame:
    """Gera a Tabela 1 de características por desfecho (`y = 0` vs `y = 1`) (T-2.6, FR-18)."""
    feat = _ensure_feature_cols(df)
    y0 = feat[feat["y"] == 0]
    y1 = feat[feat["y"] == 1]

    def _age_iqr(sub: pd.DataFrame) -> str:
        if len(sub) < min_cell:
            return f"<{min_cell}"
        q25, q50, q75 = sub["idade_anos"].quantile([0.25, 0.50, 0.75])
        return f"{q50:.1f} ({q25:.1f}–{q75:.1f})"

    def _fmt_count(n_val: int, total_val: int) -> str:
        if n_val < min_cell:
            return f"<{min_cell}"
        pct = (100.0 * n_val / total_val) if total_val > 0 else 0.0
        return f"{n_val} ({pct:.2f}%)"

    rows: list[dict[str, Any]] = [
        {
            "Característica": "Total de casos",
            "y = 0 (não grave)": f"<{min_cell}" if len(y0) < min_cell else str(len(y0)),
            "y = 1 (grave/óbito)": f"<{min_cell}" if len(y1) < min_cell else str(len(y1)),
        },
        {
            "Característica": "Idade em anos — mediana (IQR)",
            "y = 0 (não grave)": _age_iqr(y0),
            "y = 1 (grave/óbito)": _age_iqr(y1),
        },
    ]

    for sx in ["F", "M", "I"]:
        c0 = int((y0["sexo"] == sx).sum())
        c1 = int((y1["sexo"] == sx).sum())
        rows.append(
            {
                "Característica": f"Sexo: {sx}",
                "y = 0 (não grave)": _fmt_count(c0, len(y0)),
                "y = 1 (grave/óbito)": _fmt_count(c1, len(y1)),
            }
        )

    g0 = int((y0["gestante"] == 1).sum())
    g1 = int((y1["gestante"] == 1).sum())
    rows.append(
        {
            "Característica": "Gestante (Sim)",
            "y = 0 (não grave)": _fmt_count(g0, len(y0)),
            "y = 1 (grave/óbito)": _fmt_count(g1, len(y1)),
        }
    )

    if "CS_RACA" in feat.columns:
        raca_all = profiling.code(feat["CS_RACA"]).fillna("Ignorado")
        for r_code in sorted(raca_all.unique()):
            r0 = int((raca_all.loc[y0.index] == r_code).sum())
            r1 = int((raca_all.loc[y1.index] == r_code).sum())
            rows.append(
                {
                    "Característica": f"Raça/cor: {r_code}",
                    "y = 0 (não grave)": _fmt_count(r0, len(y0)),
                    "y = 1 (grave/óbito)": _fmt_count(r1, len(y1)),
                }
            )

    for comorb in COMORBIDADES:
        k0 = int((y0[comorb] == "Sim").sum())
        k1 = int((y1[comorb] == "Sim").sum())
        rows.append(
            {
                "Característica": f"Comorbidade: {comorb}",
                "y = 0 (não grave)": _fmt_count(k0, len(y0)),
                "y = 1 (grave/óbito)": _fmt_count(k1, len(y1)),
            }
        )

    for label, cond0, cond1 in [
        ("Nº comorbidades: 0", y0["n_comorbidades"] == 0, y1["n_comorbidades"] == 0),
        ("Nº comorbidades: 1", y0["n_comorbidades"] == 1, y1["n_comorbidades"] == 1),
        ("Nº comorbidades: 2", y0["n_comorbidades"] == 2, y1["n_comorbidades"] == 2),
        ("Nº comorbidades: 3+", y0["n_comorbidades"] >= 3, y1["n_comorbidades"] >= 3),
    ]:
        rows.append(
            {
                "Característica": label,
                "y = 0 (não grave)": _fmt_count(int(cond0.sum()), len(y0)),
                "y = 1 (grave/óbito)": _fmt_count(int(cond1.sum()), len(y1)),
            }
        )

    return pd.DataFrame(rows)


def _risk_table_from_groups(
    groups: list[tuple[str, pd.Series]],
    y: pd.Series,
    group_col_name: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, mask in groups:
        sub_y = y[mask]
        n_casos = int(len(sub_y))
        n_eventos = int(sub_y.sum())
        p, lo, hi = wilson_ci(n_eventos, n_casos)
        rows.append(
            {
                group_col_name: str(name),
                "casos": n_casos,
                "eventos": n_eventos,
                "risco_pct": 100.0 * p,
                "ic95_inf_pct": 100.0 * lo,
                "ic95_sup_pct": 100.0 * hi,
            }
        )
    return pd.DataFrame(rows)


def crude_risk_tables(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Calcula tabelas numéricas de risco bruto (com Wilson IC 95%) por comorbidade, nº e faixa."""
    feat = _ensure_feature_cols(df)
    y = feat["y"]

    comorb_groups = [(c, feat[c] == "Sim") for c in COMORBIDADES]
    n_groups = [
        ("0", feat["n_comorbidades"] == 0),
        ("1", feat["n_comorbidades"] == 1),
        ("2", feat["n_comorbidades"] == 2),
        ("3+", feat["n_comorbidades"] >= 3),
    ]

    if "faixa_etaria" in feat.columns:
        faixa_s = feat["faixa_etaria"].astype("string")
    else:
        faixa_s = pd.cut(
            feat["idade_anos"],
            profiling.FAIXAS,
            right=False,
            labels=profiling.FAIXAS_ROTULOS,
        ).astype("string")
    age_groups = [(rot, faixa_s == rot) for rot in profiling.FAIXAS_ROTULOS]

    return {
        "comorbidade": _risk_table_from_groups(comorb_groups, y, "comorbidade"),
        "n_comorbidades": _risk_table_from_groups(n_groups, y, "n_comorbidades"),
        "faixa_etaria": _risk_table_from_groups(age_groups, y, "faixa_etaria"),
    }


def pair_event_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Para cada um dos 21 pares de comorbidades, conta casos e eventos com ambas = Sim (T-2.7)."""
    feat = _ensure_feature_cols(df)
    y = feat["y"].to_numpy(dtype=np.int64)
    sim_masks = {c: (feat[c] == "Sim").to_numpy(dtype=bool) for c in COMORBIDADES}

    rows: list[dict[str, Any]] = []
    for c1, c2 in itertools.combinations(COMORBIDADES, 2):
        both = sim_masks[c1] & sim_masks[c2]
        n_casos = int(both.sum())
        n_eventos = int(y[both].sum())
        rows.append(
            {
                "comorbidade_a": c1,
                "comorbidade_b": c2,
                "par": f"{c1} + {c2}",
                "casos": n_casos,
                "eventos": n_eventos,
            }
        )
    return (
        pd.DataFrame(rows)
        .sort_values(["eventos", "casos"], ascending=False)
        .reset_index(drop=True)
    )


def combination_counts(df: pd.DataFrame) -> pd.DataFrame:
    """Conta casos e eventos para cada combinação exata de 3 ou mais comorbidades = Sim (T-2.7)."""
    feat = _ensure_feature_cols(df)
    n_comorb = feat["n_comorbidades"].to_numpy()
    sub = feat.loc[n_comorb >= 3]
    if sub.empty:
        return pd.DataFrame(columns=["combinacao", "n_doencas", "casos", "eventos"])

    active_lists = [
        " + ".join([c for c in COMORBIDADES if row[c] == "Sim"])
        for _, row in sub[COMORBIDADES].iterrows()
    ]
    temp = pd.DataFrame(
        {
            "combinacao": active_lists,
            "n_doencas": sub["n_comorbidades"].to_numpy(dtype=np.int64),
            "y": sub["y"].to_numpy(dtype=np.int64),
        }
    )
    grouped = (
        temp.groupby(["combinacao", "n_doencas"], as_index=False)
        .agg(casos=("y", "size"), eventos=("y", "sum"))
        .sort_values(["casos", "eventos"], ascending=False)
        .reset_index(drop=True)
    )
    return grouped


def _plot_risk_bar(
    table: pd.DataFrame,
    label_col: str,
    title: str,
    out_path: Path,
    min_cell: int = 10,
) -> None:
    """Salva gráfico de barras horizontais do risco bruto com IC 95%, omitindo células < 10."""
    plot_df = table[table["casos"] >= int(min_cell)].copy()
    fig, ax = plt.subplots(figsize=(8, 4.5))
    if not plot_df.empty:
        labels = plot_df[label_col].astype(str).tolist()
        y_pos = np.arange(len(labels))
        risks = plot_df["risco_pct"].to_numpy(dtype=float)
        err_low = np.maximum(0.0, risks - plot_df["ic95_inf_pct"].to_numpy(dtype=float))
        err_high = np.maximum(0.0, plot_df["ic95_sup_pct"].to_numpy(dtype=float) - risks)
        ax.barh(y_pos, risks, xerr=[err_low, err_high], capsize=3)
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels)
        ax.set_xlabel("Risco bruto de desfecho grave/óbito (%)")
    ax.set_title(f"{title}\n({DISCLAIMER_HEADER})")
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def generate_descriptive_reports(
    cfg: dict[str, Any],
    df: pd.DataFrame,
) -> dict[str, Any]:
    """Executa T-2.6 e T-2.7 salvando tabelas Markdown (com supressão R7) e figuras PNG."""
    feat = _ensure_feature_cols(df)
    min_cell = int(cfg.get("supressao_min_celula", 10))
    reports_dir = Path(cfg.get("caminhos", {}).get("relatorios", "reports")) / "descritiva"
    reports_dir.mkdir(parents=True, exist_ok=True)

    # 1. Tabela 1
    tab1 = table1_characteristics(feat, min_cell=min_cell)
    tab1_path = reports_dir / "tabela1.md"
    tab1_path.write_text(
        f"# Tabela 1 — Características da população (2022–2023)\n\n"
        f"> **{DISCLAIMER_HEADER}**\n\n"
        f"{profiling.markdown_table(tab1)}\n",
        encoding="utf-8",
    )

    # 2. Riscos brutos e gráficos PNG
    raw_tables = crude_risk_tables(feat)
    riscos_sections = [
        "# Riscos brutos de desfecho grave ou óbito (2022–2023)",
        "",
        f"> **{DISCLAIMER_HEADER}**",
    ]
    plot_files = {
        "comorbidade": ("Risco bruto por comorbidade", "risco_comorbidades.png"),
        "n_comorbidades": ("Risco bruto por nº de comorbidades", "risco_n_comorbidades.png"),
        "faixa_etaria": ("Risco bruto por faixa etária", "risco_faixa_etaria.png"),
    }
    for key, (title, png_name) in plot_files.items():
        tbl = raw_tables[key]
        _plot_risk_bar(tbl, key, title, reports_dir / png_name, min_cell=min_cell)
        pub_tbl = suppress_small_cells(
            tbl,
            count_cols=["casos", "eventos"],
            min_cell=min_cell,
            mask_cols=["risco_pct", "ic95_inf_pct", "ic95_sup_pct"],
        )
        riscos_sections.extend(
            ["", f"## {title}", "", profiling.markdown_table(pub_tbl, decimals=3)]
        )

    riscos_path = reports_dir / "riscos_brutos.md"
    riscos_path.write_text("\n".join(riscos_sections) + "\n", encoding="utf-8")

    # 3. Pares de comorbidades (T-2.7)
    pairs_df = pair_event_counts(feat)
    pub_pairs = suppress_small_cells(pairs_df, count_cols=["casos", "eventos"], min_cell=min_cell)
    pares_path = reports_dir / "pares_comorbidades.md"
    pares_path.write_text(
        f"# Casos e eventos por par de comorbidades (2022–2023)\n\n"
        f"> **{DISCLAIMER_HEADER}**\n\n"
        f"{profiling.markdown_table(pub_pairs, decimals=0)}\n",
        encoding="utf-8",
    )

    # 4. Combinações de 3+ comorbidades (T-2.7)
    combos_df = combination_counts(feat)
    pub_combos = combos_df[combos_df["casos"] >= min_cell].copy()
    pub_combos = suppress_small_cells(
        pub_combos, count_cols=["casos", "eventos"], min_cell=min_cell
    )
    combos_path = reports_dir / "combinacoes_3mais.md"
    combos_path.write_text(
        f"# Combinações exatas de 3 ou mais comorbidades (2022–2023)\n\n"
        f"> **{DISCLAIMER_HEADER}**\n\n"
        f"{profiling.markdown_table(pub_combos, decimals=0)}\n",
        encoding="utf-8",
    )

    pares_elegiveis = pairs_df.loc[pairs_df["eventos"] >= min_cell, "par"].tolist()
    combos_elegiveis = combos_df.loc[combos_df["casos"] >= min_cell, "combinacao"].tolist()

    return {
        "tabela1_path": tab1_path,
        "riscos_path": riscos_path,
        "pares_path": pares_path,
        "combos_path": combos_path,
        "pairs_df": pairs_df,
        "combos_df": combos_df,
        "n_pares_com_min_eventos": len(pares_elegiveis),
        "pares_com_min_eventos": pares_elegiveis,
        "n_combinacoes_3mais_com_min_casos": len(combos_elegiveis),
        "combinacoes_3mais_com_min_casos": combos_elegiveis,
    }


def verify_t2_6_t2_7(
    cfg: dict[str, Any],
    df: pd.DataFrame,
    *,
    out_dir: str | Path | None = None,
) -> tuple[Path, Path]:
    """Executa `generate_descriptive_reports` e grava `T-2.6.json` e `T-2.7.json` (D-56)."""
    res = generate_descriptive_reports(cfg, df)
    reports_dir = Path(cfg.get("caminhos", {}).get("relatorios", "reports")) / "descritiva"
    dest_dir = (
        Path(out_dir)
        if out_dir is not None
        else Path(cfg.get("caminhos", {}).get("relatorios", "reports")) / "verificacao"
    )

    checks_26 = [
        check("tabela1_existe", True, res["tabela1_path"].is_file()),
        check("riscos_brutos_existe", True, res["riscos_path"].is_file()),
        check("png_comorbidades_existe", True, (reports_dir / "risco_comorbidades.png").is_file()),
        check(
            "png_n_comorbidades_existe",
            True,
            (reports_dir / "risco_n_comorbidades.png").is_file(),
        ),
        check("png_faixa_etaria_existe", True, (reports_dir / "risco_faixa_etaria.png").is_file()),
        check(
            "aviso_topo_presente",
            True,
            DISCLAIMER_HEADER in res["riscos_path"].read_text(encoding="utf-8"),
        ),
    ]
    path_26 = write_report("T-2.6", checks_26, dest_dir, cfg)

    n_pares_total = len(res["pairs_df"])
    n_pares_10ev = int(res["n_pares_com_min_eventos"])
    n_combos_10casos = int(res["n_combinacoes_3mais_com_min_casos"])
    checks_27 = [
        check("pares_md_existe", True, res["pares_path"].is_file()),
        check("total_pares_avaliados", 21, n_pares_total),
        check("n_pares_com_10_ou_mais_eventos", n_pares_10ev, n_pares_10ev),
        check("n_combinacoes_3mais_com_10_ou_mais_casos", n_combos_10casos, n_combos_10casos),
    ]
    path_27 = write_report("T-2.7", checks_27, dest_dir, cfg)
    return path_26, path_27
