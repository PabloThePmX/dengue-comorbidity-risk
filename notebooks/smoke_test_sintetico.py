"""Teste de fumaça do notebook com DADOS SINTÉTICOS (nunca são dados do SINAN).

Gera Parquets com o MESMO esquema de colunas de texto cru dos microdados (só as colunas que o
notebook lê), em uma pasta temporária, e executa `modelo_risco_dengue.ipynb` sobre eles. Serve
APENAS para verificar que o código roda de ponta a ponta, que o lacre do teste funciona e que o
E1 recupera efeitos conhecidos. Os números produzidos NÃO têm valor científico e não devem ser
citados em relatório. Uso:

    python notebooks/smoke_test_sintetico.py            # gera dados e executa o notebook
    python notebooks/smoke_test_sintetico.py --so-dados # só gera os dados
"""
# ruff: noqa: E501

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
COMORB = ["DIABETES", "HEMATOLOG", "HEPATOPAT", "RENAL", "HIPERTENSA", "ACIDO_PEPT", "AUTO_IMUNE"]
SINAIS = ["FEBRE", "MIALGIA", "CEFALEIA", "EXANTEMA", "VOMITO", "NAUSEA", "DOR_COSTAS",
          "CONJUNTVIT", "ARTRITE", "ARTRALGIA", "PETEQUIA_N", "LEUCOPENIA", "LACO", "DOR_RETRO"]
# Efeitos verdadeiros (log-odds) usados na simulação; o E1 deve recuperá-los.
EFEITOS = {"HIPERTENSA": 0.4, "DIABETES": 0.6, "RENAL": 1.2, "HEPATOPAT": 0.7, "HEMATOLOG": 0.5,
           "ACIDO_PEPT": 0.1, "AUTO_IMUNE": 0.3, "DIABETES:RENAL": 0.5, "VOMITO": 0.5,
           "PETEQUIA_N": 0.7, "idade_por_ano": 0.035}
REGIOES = {"Sudeste": ("3", 0.50), "Sul": ("4", 0.20), "Centro-Oeste": ("5", 0.15),
           "Nordeste": ("2", 0.10), "Norte": ("1", 0.05)}
UFS = {"1": [11, 12, 13, 14, 15, 16, 17], "2": [21, 22, 23, 24, 25, 26, 27, 28, 29],
       "3": [31, 32, 33, 35], "4": [41, 42, 43], "5": [50, 51, 52, 53]}


def _sim(n: int, ano: int, rng: np.random.Generator, deriva: float) -> pd.DataFrame:
    reg = rng.choice(list(REGIOES), p=[v[1] for v in REGIOES.values()], size=n)
    dig = np.array([REGIOES[r][0] for r in reg])
    uf = np.array([rng.choice(UFS[d]) for d in dig]) if n < 5000 else None
    if uf is None:  # vetorizado
        uf = np.empty(n, dtype=int)
        for d, ufs in UFS.items():
            m = dig == d
            uf[m] = rng.choice(ufs, size=m.sum())
    idade = np.clip(rng.gamma(2.2, 17, size=n), 0, 100).round().astype(int)
    idade_cod = np.char.add("4", np.char.zfill(idade.astype(str), 3)).astype(object)
    bebe = rng.random(n) < 0.01
    idade_cod[bebe] = "3" + np.char.zfill(rng.integers(1, 12, bebe.sum()).astype(str), 3)
    idade_anos = np.where(bebe, 0, idade)
    invalido = rng.random(n) < 0.002
    idade_cod[invalido] = "5018"
    sexo = rng.choice(["F", "M", "I"], p=[0.52, 0.478, 0.002], size=n)
    gest = np.where((sexo == "F") & (idade_anos > 15) & (idade_anos < 45) & (rng.random(n) < 0.04),
                    rng.choice(["1", "2", "3", "4"], size=n), rng.choice(["5", "6", "9"], size=n))
    com = {}
    pbase = {"HIPERTENSA": 0.02, "DIABETES": 0.01, "RENAL": 0.004, "HEPATOPAT": 0.005,
             "HEMATOLOG": 0.005, "ACIDO_PEPT": 0.006, "AUTO_IMUNE": 0.006}
    for c in COMORB:
        p = np.clip(pbase[c] * (1 + 6 * (idade_anos > 55)), 0, 0.5)
        if c == "RENAL":  # associação com diabetes (confusão realista entre comorbidades)
            p = p * (1 + 3 * (com["DIABETES"] == 1))
        com[c] = (rng.random(n) < p).astype(int)
    sint = {s: (rng.random(n) < (0.9 if s == "FEBRE" else 0.4)).astype(int) for s in SINAIS}
    atraso = np.minimum(rng.geometric(0.3, size=n) - 1, 60)
    logit = (-5.9 + deriva + EFEITOS["idade_por_ano"] * (idade_anos - 40)
             + sum(EFEITOS[c] * com[c] for c in COMORB)
             + EFEITOS["DIABETES:RENAL"] * com["DIABETES"] * com["RENAL"]
             + EFEITOS["VOMITO"] * sint["VOMITO"] + EFEITOS["PETEQUIA_N"] * sint["PETEQUIA_N"])
    grave = rng.random(n) < 1 / (1 + np.exp(-logit))
    obito_nao_12 = grave & (rng.random(n) < 0.3)
    classi = np.where(grave & ~obito_nao_12, "12", np.where(rng.random(n) < 0.05, "11", "10"))
    classi = np.where(~grave & (rng.random(n) < 0.08), "8", classi)
    evol = np.where(obito_nao_12, "2", np.where(rng.random(n) < 0.85, "1", "9"))
    evol = np.where(grave & (classi == "12"), rng.choice(["1", "2", "9"], p=[.6, .3, .1], size=n), evol)
    inicio = pd.to_datetime(f"{ano}-01-01") + pd.to_timedelta(rng.integers(0, 330, n), unit="D")
    df = pd.DataFrame({
        "CLASSI_FIN": classi, "EVOLUCAO": evol, "NU_IDADE_N": idade_cod,
        "ANO_NASC": (ano - idade_anos).astype(str), "DT_SIN_PRI": inicio.strftime("%Y%m%d"),
        "DT_NOTIFIC": (inicio + pd.to_timedelta(atraso, unit="D")).strftime("%Y%m%d"),
        "CS_SEXO": np.where(sexo == "I", "I", sexo), "CS_GESTANT": gest,
        "CS_RACA": rng.choice(["1", "2", "4", "9"], size=n), "SG_UF": uf.astype(str),
        "ID_MN_RESI": [f"{u}{rng.integers(1000, 9999)}" for u in uf] if n < 5000
        else np.char.add(uf.astype(str), rng.integers(1000, 9999, n).astype(str)),
        "ID_UNIDADE": rng.integers(2_000_000, 2_050_000, n).astype(str),
        "NDUPLIC_N": None, "CRITERIO": rng.choice(["1", "2"], size=n)})
    for c in COMORB:
        v = np.where(com[c] == 1, "1", "2").astype(object)
        v[rng.random(n) < 0.001] = None
        df[c] = v
    for s in SINAIS:
        v = np.where(sint[s] == 1, "1", "2").astype(object)
        v[rng.random(n) < 0.03] = None
        df[s] = v
    df["GRAV_PULSO"] = np.where((classi == "12") & (rng.random(n) < .9), "1", None)
    df["ALRM_VOM"] = np.where(np.isin(classi, ["11", "12"]), "1", None)
    return df


def gerar(pasta: Path, n_dev_por_ano: int = 90_000, n_teste: int = 120_000, seed: int = 7) -> Path:
    rng = np.random.default_rng(seed)
    (pasta / "parquet").mkdir(parents=True, exist_ok=True)
    manifesto = {}
    for ano, n, deriva in ((2022, n_dev_por_ano, 0.0), (2023, n_dev_por_ano, 0.0),
                           (2024, n_teste, 0.25)):
        df = _sim(n, ano, rng, deriva)
        caminho = pasta / "parquet" / f"dengue_{ano}.parquet"
        df.to_parquet(caminho, index=False)
        manifesto[str(ano)] = {"ano": ano, "arquivo": f"SINTETICO{ano}", "status_datasus": "SINTÉTICO",
                               "linhas": n, "parquet": caminho.name, "sintetico": True,
                               "sha256_dbc": "sintetico", "sha256_parquet": "sintetico",
                               "revisao_datasus_utc": "n/a"}
    (pasta / "manifest.json").write_text(json.dumps(manifesto, indent=2), "utf-8")
    return pasta


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--so-dados", action="store_true")
    ap.add_argument("--pasta", default=None)
    args = ap.parse_args()
    pasta = Path(args.pasta) if args.pasta else Path(tempfile.mkdtemp(prefix="dengue_sintetico_"))
    gerar(pasta)
    print("Dados SINTÉTICOS em", pasta)
    if args.so_dados:
        return
    env = {**os.environ, "DENGUE_DATA_DIR": str(pasta), "DENGUE_SMOKE": "1",
           "DENGUE_OUT_DIR": str(pasta / "saida")}
    nb = RAIZ / "notebooks" / "modelo_risco_dengue.ipynb"
    saida = pasta / "modelo_risco_dengue_SINTETICO_executado.ipynb"
    cmd = [sys.executable, "-m", "jupyter", "nbconvert", "--to", "notebook", "--execute",
           "--ExecutePreprocessor.timeout=3600", str(nb), "--output", str(saida)]
    print(" ".join(cmd))
    sys.exit(subprocess.call(cmd, env=env))


if __name__ == "__main__":
    main()
