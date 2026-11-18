"""Preparação dos dados: leitura dos Parquets de 2022–2023, população analítica e variáveis.

Reusa `etapa1.carregar_bruto_dev` (recusa 2024), `dataset.montar_populacao` (elegibilidade D-45)
e `dataset.montar_features`. Não há regra de preparação nova aqui. O conjunto analítico sai com
as variáveis autorizadas, o desfecho `y`, `ANO` e `regiao` (usada só nas dobras e nunca como
entrada).
"""

from pathlib import Path

import pandas as pd

from dengue_sinan.dataset import COLUNAS_BASE
from dengue_sinan.etapa1 import carregar_bruto_dev, montar_dev
from dengue_sinan.guard import ANOS_DEV, marcar_anos, verificar_dev
from dengue_sinan.pipeline.contrato import checar_variaveis, variaveis_autorizadas
from dengue_sinan.pipeline.preprocessamento import normalizar_x

COLUNAS_CHAVE = ["ANO", "regiao", "y"]
# Agrupamento para bootstrap por conglomerado (Etapa 3.2). NUNCA é variável do modelo.
COLUNA_CONGLOMERADO = "conglomerado"


def _proibir_relatorios(caminho: Path) -> None:
    partes = {p.lower() for p in Path(caminho).resolve().parts}
    if "reports" in partes:
        raise PermissionError(f"recusado: microdados não podem ser salvos em reports/ ({caminho})")


def conglomerado_municipal(pop: pd.DataFrame) -> pd.Series:
    """Município de residência (código IBGE de 6 dígitos); sem município, a UF como reserva.

    Mesma lógica da região (município primeiro, UF depois), então cada conglomerado fica numa
    única região. A UF só aparece como `UF:<código>` e cobre pouquíssimas linhas.
    """
    mun = pop["ID_MN_RESI"].astype("string").str.strip()
    uf = "UF:" + pop["SG_UF"].astype("string").str.strip()
    return mun.where(mun.str.fullmatch(r"\d{6}").fillna(False), uf).astype("string")


def preparar_dev(data_dir, anos=ANOS_DEV, variaveis: list[str] | None = None):
    """Devolve (conjunto analítico, registro dos arquivos lidos). Só 2022 e 2023."""
    variaveis = checar_variaveis(variaveis or variaveis_autorizadas())
    brutos, registro = carregar_bruto_dev(data_dir, anos=anos, colunas=COLUNAS_BASE)
    ausentes = {a: c for a, c in registro["colunas_ausentes"].items() if c}
    if ausentes:
        raise ValueError(f"colunas obrigatórias ausentes nos Parquets: {ausentes}")
    pop, x = montar_dev(brutos)
    del brutos  # as demais colunas de COLUNAS_BASE não são usadas além deste ponto
    conjunto = x[variaveis].copy()
    conjunto["y"] = pop["y"].astype("int8").to_numpy()
    conjunto["ANO"] = pop["ANO"].astype("int16").to_numpy()
    conjunto["regiao"] = pop["regiao"].astype("string").to_numpy()
    conjunto[COLUNA_CONGLOMERADO] = conglomerado_municipal(pop).to_numpy()
    registro["linhas_analiticas"] = int(len(conjunto))
    return conjunto, registro


def salvar_preparado(conjunto: pd.DataFrame, caminho) -> Path:
    caminho = Path(caminho)
    _proibir_relatorios(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    conjunto.to_parquet(caminho, index=False)
    return caminho


def carregar_preparado(caminho, variaveis: list[str]):
    """Lê o conjunto analítico e devolve (x, y, regiao, meta). Recusa qualquer ano fora de dev."""
    variaveis = checar_variaveis(variaveis)
    df = pd.read_parquet(caminho)
    faltam = [c for c in [*variaveis, *COLUNAS_CHAVE] if c not in df.columns]
    if faltam:
        raise ValueError(f"colunas ausentes no conjunto preparado: {faltam}")
    meta = df[["ANO"]].copy()
    verificar_dev(meta, meta=meta, contexto="preparacao.carregar_preparado")  # R1
    x = normalizar_x(df[variaveis], variaveis)
    marcar_anos(x, meta["ANO"].unique())
    regiao = df["regiao"].astype("string")
    marcar_anos(regiao, meta["ANO"].unique())
    return x, df["y"].to_numpy(), regiao, meta


def carregar_agrupamento(caminho) -> pd.Series:
    """Coluna de conglomerado do conjunto preparado. Serve só ao bootstrap, nunca ao modelo."""
    df = pd.read_parquet(caminho, columns=[COLUNA_CONGLOMERADO])
    return df[COLUNA_CONGLOMERADO].astype("string")
