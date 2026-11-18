"""Guardas contra uso indevido do teste (R1, R2) e contra features proibidas (R4, §3.8)."""

import numpy as np
import pandas as pd

ANOS_DEV = (2022, 2023)
# Chave de `DataFrame.attrs` / `Series.attrs` com os anos de origem dos dados (etapa 1B, J8).
# O pandas propaga `attrs` em iloc, filtros, cópias e seleção de coluna; assim a marca viaja com
# os dados e a proteção não depende só de quem chama a função.
CHAVE_ANOS = "anos_origem"
ANO_TESTE = 2024

# Campos que NUNCA podem virar feature (revisão de vazamento, §3.8; regra R4 da constituição).
FEATURES_PROIBIDAS_PREFIXOS = ("ALRM_", "GRAV_", "RESUL_", "DT_")
FEATURES_PROIBIDAS = {
    "CLASSI_FIN",
    "EVOLUCAO",
    "CRITERIO",
    "HOSPITALIZ",
    "ANO",
    "regiao",
    "SG_UF",
    "ID_MN_RESI",
    "ID_UNIDADE",
    "ID_MUNICIP",
    "SG_UF_NOT",
    "CS_RACA",
    "CS_ESCOL_N",
    "faixa_etaria",
    "y",
    "PETEQUIAS",
    "LACO_N",
    "NU_ANO",
    "SEM_NOT",
    "SEM_PRI",
    "NDUPLIC_N",
    "TP_SISTEMA",
    "idade_de_ano_nasc",
    "ANO_NASC",
}


def assert_dev_only(df: pd.DataFrame, coluna: str = "ANO") -> None:
    """Falha se o DataFrame tiver qualquer linha do ano de teste (R1).

    Toda função que treina, ajusta, calibra, escolhe limiar ou seleciona modelo chama isto.
    """
    anos = pd.to_numeric(df[coluna], errors="coerce").dropna().astype(int).unique()
    if ANO_TESTE in set(anos.tolist()):
        raise PermissionError(
            f"R1: dados de {ANO_TESTE} (teste congelado) não podem entrar em treino, tuning, "
            f"calibração, limiar ou seleção. Anos recebidos: {sorted(anos.tolist())}."
        )


def assert_features_permitidas(colunas: list[str], permitidas: list[str]) -> None:
    """Falha se alguma coluna de X estiver fora da lista fechada do data-model §D (R4)."""
    fora = [c for c in colunas if c not in set(permitidas)]
    proibidas = [
        c for c in colunas if c in FEATURES_PROIBIDAS or c.startswith(FEATURES_PROIBIDAS_PREFIXOS)
    ]
    if fora or proibidas:
        raise ValueError(f"R4: features fora da lista fechada: {sorted(set(fora + proibidas))}")


# ------------------------------------------------------------------------------ guarda por dados
def marcar_anos(obj, anos):
    """Registra em `obj.attrs` os anos de origem dos dados. Devolve o próprio objeto."""
    obj.attrs[CHAVE_ANOS] = sorted({int(a) for a in anos})
    return obj


def anos_marcados(*objetos) -> set[int] | None:
    """União dos anos marcados nos objetos; `None` se nenhum objeto tiver marca."""
    anos: set[int] = set()
    achou = False
    for o in objetos:
        marca = getattr(o, "attrs", {}).get(CHAVE_ANOS)
        if marca is not None:
            achou = True
            anos |= {int(a) for a in marca}
    return anos if achou else None


def _anos_da_meta(meta) -> set[int]:
    if isinstance(meta, pd.DataFrame):
        if "ANO" not in meta.columns:
            raise PermissionError("R1: metadados sem a coluna ANO; não prova que é só dev.")
        col = meta["ANO"]
    else:
        col = pd.Series(meta)
    return set(pd.to_numeric(col, errors="coerce").dropna().astype(int).unique().tolist())


def verificar_dev(
    *objetos, meta=None, contexto: str = "", exigir_metadados: bool = True
) -> set[int]:
    """Guarda R1 obrigatória em todo caminho de desenvolvimento (J8).

    Procura a origem dos dados na marca `attrs` dos `objetos` (X, região, ...) e, se houver, em
    `meta` (DataFrame com ANO). Falha (PermissionError) quando:
      - qualquer ano for o do teste (2024) ou estiver fora de ANOS_DEV;
      - a marca e `meta` divergem (metadados incompatíveis) ou `meta` tiver outro tamanho;
      - não houver nenhuma origem declarada e `exigir_metadados` for True (padrão).
    Devolve o conjunto de anos verificado.
    """
    onde = f" ({contexto})" if contexto else ""
    marca = anos_marcados(*objetos)
    anos_meta = None
    if meta is not None:
        anos_meta = _anos_da_meta(meta)
        for o in objetos:
            if isinstance(o, pd.DataFrame | pd.Series | np.ndarray) and len(o) != len(meta):
                raise PermissionError(
                    f"R1{onde}: metadados incompatíveis: {len(meta)} linhas em `meta` contra "
                    f"{len(o)} nos dados."
                )
    if marca is not None and anos_meta is not None and marca != anos_meta:
        raise PermissionError(
            f"R1{onde}: metadados incompatíveis: marca dos dados {sorted(marca)} ≠ ANO em `meta` "
            f"{sorted(anos_meta)}."
        )
    anos = marca if marca is not None else anos_meta
    if anos is None:
        if exigir_metadados:
            raise PermissionError(
                f"R1{onde}: origem dos dados (ano) não declarada. Construa os dados com "
                "montar_populacao/montar_features, use guard.marcar_anos ou passe `meta` com ANO."
            )
        return set()
    fora = sorted(anos - set(ANOS_DEV))
    if ANO_TESTE in anos or fora:
        raise PermissionError(
            f"R1{onde}: dados de {fora or [ANO_TESTE]} (teste congelado ou fora de ANOS_DEV) não "
            f"podem entrar em treino, tuning, calibração, limiar ou seleção. Anos: {sorted(anos)}."
        )
    return anos
