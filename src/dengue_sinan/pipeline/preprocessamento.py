"""Validação de registros e transformação em matriz do modelo.

As mesmas funções servem ao treino e à inferência: `normalizar_x` fixa tipos, categorias e ordem
das colunas, e `matriz_modelo` aplica a codificação ordinal sem estado (`dataset.matriz_arvore`).
Nada aqui lê dados de treino nem guarda estado ajustado.
"""

import numbers

import numpy as np
import pandas as pd

from dengue_sinan.dataset import matriz_arvore
from dengue_sinan.pipeline.contrato import CAMPOS, SEXOS, checar_variaveis


class EntradaInvalida(ValueError):
    """Registros fora do contrato. `erros` lista {indice, campo, motivo} de cada problema."""

    def __init__(self, erros: list[dict]):
        self.erros = erros
        resumo = "; ".join(
            f"linha {e['indice']}: {e['campo']}: {e['motivo']}"
            if e["indice"] is not None
            else f"{e['campo']}: {e['motivo']}"
            for e in erros[:5]
        )
        extra = f" (+{len(erros) - 5} erros)" if len(erros) > 5 else ""
        super().__init__(f"entrada inválida: {resumo}{extra}")


def _ausente(v) -> bool:
    return v is None or (isinstance(v, float) and np.isnan(v)) or v is pd.NA or v is pd.NaT


def _para_dataframe(registros) -> pd.DataFrame:
    if isinstance(registros, pd.DataFrame):
        return registros.reset_index(drop=True)
    if isinstance(registros, dict):
        raise EntradaInvalida(
            [
                {
                    "indice": None,
                    "campo": "(entrada)",
                    "motivo": "esperada uma lista de registros, recebido um único dicionário",
                }
            ]
        )
    try:
        lista = list(registros)
    except TypeError:
        raise EntradaInvalida(
            [{"indice": None, "campo": "(entrada)", "motivo": "esperada uma lista de registros"}]
        ) from None
    if not all(isinstance(r, dict) for r in lista):
        raise EntradaInvalida(
            [
                {
                    "indice": None,
                    "campo": "(entrada)",
                    "motivo": "cada registro deve ser um dicionário",
                }
            ]
        )
    chaves = {k for r in lista for k in r}
    return pd.DataFrame(lista, columns=sorted(chaves) if chaves else [], dtype=object)


def _checar_campo(campo, valor):
    """Devolve (valor_limpo, motivo_do_erro). Tipos estritos: texto não vira número."""
    if _ausente(valor):
        if campo.obrigatorio:
            return None, "campo obrigatório ausente ou nulo"
        return campo.padrao, None
    if campo.tipo == "numero":
        if isinstance(valor, bool | np.bool_) or not isinstance(valor, numbers.Real):
            return None, f"tipo inválido ({type(valor).__name__}); esperado número"
        v = float(valor)
        if not np.isfinite(v) or not campo.minimo <= v <= campo.maximo:
            return None, f"fora do intervalo [{campo.minimo:g}, {campo.maximo:g}]"
        return v, None
    if campo.tipo == "categoria":
        if not isinstance(valor, str) or valor not in campo.categorias:
            return None, f"categoria inválida; aceitas: {list(campo.categorias)}"
        return valor, None
    if isinstance(valor, numbers.Real) and float(valor) in (0.0, 1.0):  # inclui bool e 1.0
        return int(valor), None
    return None, "valor inválido; aceitos: 0, 1, false, true"


def validar_registros(registros, variaveis: list[str]) -> tuple[pd.DataFrame, list[dict]]:
    """Valida contra o contrato. Devolve (linhas válidas, erros por linha).

    Problemas de esquema (campo desconhecido, entrada que não é lista de dicionários) sempre
    levantam `EntradaInvalida`: indicam erro de quem chama, não de um registro.
    """
    variaveis = checar_variaveis(variaveis)
    df = _para_dataframe(registros)
    extras = sorted(set(df.columns) - set(variaveis))
    if extras:
        raise EntradaInvalida(
            [{"indice": None, "campo": c, "motivo": "campo não aceito pelo modelo"} for c in extras]
        )
    limpas: dict[str, list] = {v: [] for v in variaveis}
    erros: list[dict] = []
    com_erro = np.zeros(len(df), dtype=bool)
    for v in variaveis:
        campo = CAMPOS[v]
        coluna = df[v].tolist() if v in df.columns else [None] * len(df)
        for i, valor in enumerate(coluna):
            limpo, motivo = _checar_campo(campo, valor)
            limpas[v].append(limpo)
            if motivo:
                erros.append({"indice": i, "campo": v, "motivo": motivo})
                com_erro[i] = True
    x = pd.DataFrame(limpas, index=df.index, columns=variaveis)
    return x.loc[~com_erro], erros


def normalizar_x(x: pd.DataFrame, variaveis: list[str]) -> pd.DataFrame:
    """Fixa ordem das colunas, tipos e categorias. Treino e inferência passam por aqui."""
    variaveis = list(variaveis)
    faltam = [v for v in variaveis if v not in x.columns]
    if faltam:
        raise ValueError(f"colunas ausentes na matriz: {faltam}")
    out = pd.DataFrame(index=x.index)
    for v in variaveis:
        s = x[v]
        if v == "idade_anos":
            out[v] = s.astype("float64")
        elif v == "sexo":
            out[v] = pd.Categorical(s.astype(object), categories=list(SEXOS))
        elif v == "gestante":
            out[v] = s.astype("int8")
        else:
            raise ValueError(f"sem regra de normalização para {v}")
    out.attrs.update(x.attrs)
    return out


def matriz_modelo(x: pd.DataFrame, variaveis: list[str]) -> pd.DataFrame:
    """Matriz numérica que o motor recebe, com as colunas na ordem de `variaveis`."""
    return matriz_arvore(normalizar_x(x, variaveis))
