"""Inferência com um artefato já treinado. Não treina, não ajusta e não lê dados de treino.

Importa só `artefatos`, `contrato` e `preprocessamento`. Uso:

    preditor = carregar_modelo("artefatos/modelos/m1-perfil-2.0.0")
    preditor.prever([{"idade_anos": 34, "sexo": "F", "gestante": 0}])
"""

from pathlib import Path

import numpy as np
import pandas as pd

from dengue_sinan.pipeline import artefatos
from dengue_sinan.pipeline.preprocessamento import (
    EntradaInvalida,
    matriz_modelo,
    validar_registros,
)

__all__ = ["EntradaInvalida", "Preditor", "carregar_modelo"]


class Preditor:
    def __init__(self, objeto: dict, metadados: dict, contrato: dict):
        self._motor = objeto["motor"]
        self._calibrador = objeto["calibrador"]
        self.variaveis: list[str] = list(objeto["variaveis"])
        self.metadados = metadados
        self.contrato = contrato
        self.versao = metadados["identificador"]

    def prever(self, registros, erros: str = "levantar") -> pd.DataFrame:
        """Probabilidades na ordem dos registros.

        erros="levantar" (padrão): qualquer registro inválido levanta `EntradaInvalida`.
        erros="marcar": registro inválido sai com status="invalido", probabilidade nula e o
        motivo em `erro`. Campos desconhecidos sempre levantam.
        """
        if erros not in ("levantar", "marcar"):
            raise ValueError("erros deve ser 'levantar' ou 'marcar'")
        x_ok, lista = validar_registros(registros, self.variaveis)
        if lista and erros == "levantar":
            raise EntradaInvalida(lista)
        n = len(x_ok) + len({e["indice"] for e in lista})
        saida = pd.DataFrame(
            {
                "probabilidade": np.full(n, np.nan),
                "status": "invalido",
                "erro": "",
                "versao_modelo": self.versao,
            },
        )
        for e in lista:
            antigo = saida.at[e["indice"], "erro"]
            saida.at[e["indice"], "erro"] = f"{antigo}; " * bool(antigo) + (
                f"{e['campo']}: {e['motivo']}"
            )
        if len(x_ok):
            bruto = self._motor.predict_proba(matriz_modelo(x_ok, self.variaveis))[:, 1]
            p = np.clip(self._calibrador.prever(bruto), 0.0, 1.0)
            saida.loc[x_ok.index, "probabilidade"] = p
            saida.loc[x_ok.index, "status"] = "ok"
        return saida


def carregar_modelo(pasta) -> Preditor:
    """Verifica os hashes do artefato e o carrega."""
    objeto, meta, contrato = artefatos.carregar(Path(pasta))
    return Preditor(objeto, meta, contrato)
