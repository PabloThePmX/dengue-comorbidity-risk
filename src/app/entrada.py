"""Entrada de casos da demo: validação e tradução para as features (T-6.1, FR-11, D-61).

Funções puras, sem Streamlit e sem leitura de arquivo. A tabela de tradução é a coluna "Vira a
feature" de [contracts › Entrada de casos](../../specs/contracts/interfaces.md#entrada-de-casos):

- `idade_anos` e `dias_ate_notificacao`: números inteiros, iguais nas features;
- `sexo`: `M` → M, `F` → F;
- `gestante`: `sim` → 1; `nao` e `ignorado` → 0;
- as 7 comorbidades e os 14 sintomas: `sim` → Sim, `nao` → Não, `ignorado` → Ausente, nas colunas
  de nome em maiúsculas do dicionário de features;
- `n_comorbidades` não é entrada: é o nº de comorbidades com `sim`.

Entrada fora do domínio levanta `EntradaInvalida` com mensagens em pt-BR (uma por problema).
Nada aqui grava, registra em log ou guarda a entrada (NFR-03).
"""

from __future__ import annotations

import functools
from collections.abc import Mapping
from dataclasses import dataclass

import pandas as pd

from dengue_sinan.config import load_config
from dengue_sinan.profiling import COMORBIDADES, SINAIS

IDADE_MIN, IDADE_MAX = 0, 120
DIAS_MIN, DIAS_MAX = 0, 60
SEXOS = ("M", "F")
NIVEIS_ENTRADA = ("sim", "nao", "ignorado")
NIVEIS_PERFIL = ("sim", "nao")  # a aba Perfil só marca ou não marca a comorbidade

# Nome da entrada (contrato) -> campo da feature (dicionário de features).
CAMPOS_COMORBIDADES = {
    "diabetes": "DIABETES",
    "hematologica": "HEMATOLOG",
    "hepatopatia": "HEPATOPAT",
    "renal_cronica": "RENAL",
    "hipertensao": "HIPERTENSA",
    "acido_peptica": "ACIDO_PEPT",
    "autoimune": "AUTO_IMUNE",
}
CAMPOS_SINAIS = {
    "febre": "FEBRE",
    "mialgia": "MIALGIA",
    "cefaleia": "CEFALEIA",
    "exantema": "EXANTEMA",
    "vomito": "VOMITO",
    "nausea": "NAUSEA",
    "dor_costas": "DOR_COSTAS",
    "conjuntvit": "CONJUNTVIT",
    "artrite": "ARTRITE",
    "artralgia": "ARTRALGIA",
    "dor_retro": "DOR_RETRO",
    "petequia_n": "PETEQUIA_N",
    "leucopenia": "LEUCOPENIA",
    "laco": "LACO",
}
NIVEL_DA_FEATURE = {"sim": "Sim", "nao": "Não", "ignorado": "Ausente"}

# Rótulos da tela (pt-BR) por campo de feature.
ROTULOS_COMORBIDADES = {
    "DIABETES": "Diabetes",
    "HEMATOLOG": "Doença hematológica",
    "HEPATOPAT": "Hepatopatia",
    "RENAL": "Doença renal crônica",
    "HIPERTENSA": "Hipertensão",
    "ACIDO_PEPT": "Doença ácido-péptica",
    "AUTO_IMUNE": "Doença autoimune",
}
ROTULOS_SINAIS = {
    "FEBRE": "Febre",
    "MIALGIA": "Dor muscular (mialgia)",
    "CEFALEIA": "Dor de cabeça",
    "EXANTEMA": "Manchas na pele (exantema)",
    "VOMITO": "Vômito",
    "NAUSEA": "Náusea",
    "DOR_COSTAS": "Dor nas costas",
    "CONJUNTVIT": "Conjuntivite",
    "ARTRITE": "Artrite",
    "ARTRALGIA": "Dor nas articulações",
    "DOR_RETRO": "Dor atrás dos olhos",
    "PETEQUIA_N": "Petéquias",
    "LEUCOPENIA": "Leucopenia",
    "LACO": "Prova do laço positiva",
}
ROTULOS_FEATURES = {
    **ROTULOS_COMORBIDADES,
    **ROTULOS_SINAIS,
    "idade_anos": "Idade",
    "sexo": "Sexo",
    "gestante": "Gestante",
    "dias_ate_notificacao": "Dias até a notificação",
    "n_comorbidades": "Número de comorbidades",
}


@functools.lru_cache(maxsize=1)
def _ano_de_desenvolvimento() -> int:
    """Último ano de desenvolvimento do config, lido uma vez (a consulta não relê o YAML)."""
    return int(load_config()["anos_dev"][-1])


class EntradaInvalida(ValueError):
    """Entrada fora do domínio. `erros` traz uma mensagem em pt-BR por problema."""

    def __init__(self, erros: list[str]) -> None:
        self.erros = list(erros)
        super().__init__("; ".join(self.erros))


@dataclass(frozen=True)
class Perfil:
    """Perfil da aba Perfil (E1): idade, sexo, gestação e as comorbidades marcadas (campos)."""

    idade_anos: int
    sexo: str
    gestante: int
    comorbidades: tuple[str, ...]  # campos de feature (ex.: "DIABETES"), na ordem do dicionário


@dataclass(frozen=True)
class Caso:
    """Caso da aba Triagem (M1), já traduzido: níveis `Sim`/`Não`/`Ausente` por campo."""

    idade_anos: int
    sexo: str
    gestante: int
    comorbidades: dict[str, str]  # campo -> Sim | Não | Ausente
    sinais: dict[str, str]
    dias_ate_notificacao: int

    @property
    def n_comorbidades(self) -> int:
        return sum(1 for nivel in self.comorbidades.values() if nivel == "Sim")

    @property
    def marcadas(self) -> tuple[str, ...]:
        return tuple(c for c in COMORBIDADES if self.comorbidades[c] == "Sim")

    def para_frame(self) -> pd.DataFrame:
        """Uma linha com as colunas do dicionário de features (o que `build_feature_frame`
        devolve para os campos que o M1 lê), mais `ANO`.

        `ANO` existe só porque o `prever_proba` dos modelos confere o ano contra o teste
        congelado (R1) e falha sem a coluna. O pré-processador a ignora (R4): usa o último ano de
        desenvolvimento do config, nunca o ano de teste.
        """
        linha: dict[str, object] = {
            "ANO": _ano_de_desenvolvimento(),
            "idade_anos": float(self.idade_anos),
            "sexo": self.sexo,
            "gestante": self.gestante,
            "n_comorbidades": self.n_comorbidades,
            "dias_ate_notificacao": self.dias_ate_notificacao,
        }
        linha.update(self.comorbidades)
        linha.update(self.sinais)
        df = pd.DataFrame([linha])
        df["gestante"] = df["gestante"].astype("int8")
        for campo in [*COMORBIDADES, *SINAIS]:
            df[campo] = pd.Categorical(df[campo], categories=["Sim", "Não", "Ausente"])
        return df


# --- Validação ---------------------------------------------------------------------------------

def _inteiro(valor: object) -> int | None:
    """Inteiro de verdade (ou float sem parte fracionária). bool não conta como número."""
    if isinstance(valor, bool):
        return None
    if isinstance(valor, int):
        return valor
    if isinstance(valor, float) and valor.is_integer():
        return int(valor)
    return None


def _validar_numero(bruta: Mapping, campo: str, rotulo: str, minimo: int, maximo: int,
                    erros: list[str]) -> int | None:
    if campo not in bruta:
        erros.append(f"{rotulo}: campo obrigatório ausente.")
        return None
    valor = _inteiro(bruta[campo])
    if valor is None:
        erros.append(f"{rotulo}: informe um número inteiro entre {minimo} e {maximo}.")
        return None
    if not minimo <= valor <= maximo:
        erros.append(f"{rotulo}: {valor} está fora do intervalo de {minimo} a {maximo}.")
        return None
    return valor


def _validar_nivel(bruta: Mapping, campo: str, rotulo: str, validos: tuple[str, ...],
                   erros: list[str]) -> str | None:
    if campo not in bruta:
        erros.append(f"{rotulo}: campo obrigatório ausente.")
        return None
    valor = bruta[campo]
    if not isinstance(valor, str) or valor not in validos:
        opcoes = ", ".join(f"'{v}'" for v in validos)
        erros.append(f"{rotulo}: valor inválido, use {opcoes}.")
        return None
    return valor


def _validar_base(bruta: Mapping, niveis: tuple[str, ...], erros: list[str]):
    """Idade, sexo, gestação e comorbidades. Devolve (idade, sexo, gestante, comorbidades)."""
    idade = _validar_numero(bruta, "idade_anos", "Idade", IDADE_MIN, IDADE_MAX, erros)
    sexo = _validar_nivel(bruta, "sexo", "Sexo", SEXOS, erros)
    gestacao = _validar_nivel(bruta, "gestante", "Gestante", NIVEIS_ENTRADA, erros)
    if gestacao == "sim" and sexo is not None and sexo != "F":
        erros.append("Gestante: só é possível com sexo F.")
    comorbidades: dict[str, str] = {}
    for campo, feature in CAMPOS_COMORBIDADES.items():
        nivel = _validar_nivel(bruta, campo, ROTULOS_COMORBIDADES[feature], niveis, erros)
        if nivel is not None:
            comorbidades[feature] = nivel
    return idade, sexo, gestacao, comorbidades


def validar_perfil(bruta: Mapping) -> Perfil:
    """Valida a entrada da aba Perfil (`idade_anos`, `sexo`, `gestante`, as 7 comorbidades com
    `sim` ou `nao`) e devolve o `Perfil`. Levanta `EntradaInvalida`."""
    erros: list[str] = []
    idade, sexo, gestacao, comorbidades = _validar_base(bruta, NIVEIS_PERFIL, erros)
    if erros:
        raise EntradaInvalida(erros)
    return Perfil(
        idade_anos=idade,
        sexo=sexo,
        gestante=1 if gestacao == "sim" else 0,
        comorbidades=tuple(c for c in COMORBIDADES if comorbidades[c] == "sim"),
    )


def validar_caso(bruta: Mapping) -> Caso:
    """Valida a entrada da aba Triagem (colunas de "Entrada de casos", sem `id_caso`) e a traduz
    para as features (D-61). Levanta `EntradaInvalida`."""
    erros: list[str] = []
    idade, sexo, gestacao, comorbidades = _validar_base(bruta, NIVEIS_ENTRADA, erros)
    sinais: dict[str, str] = {}
    for campo, feature in CAMPOS_SINAIS.items():
        nivel = _validar_nivel(bruta, campo, ROTULOS_SINAIS[feature], NIVEIS_ENTRADA, erros)
        if nivel is not None:
            sinais[feature] = nivel
    dias = _validar_numero(bruta, "dias_ate_notificacao", "Dias até a notificação",
                           DIAS_MIN, DIAS_MAX, erros)
    if erros:
        raise EntradaInvalida(erros)
    return Caso(
        idade_anos=idade,
        sexo=sexo,
        gestante=1 if gestacao == "sim" else 0,  # `nao` e `ignorado` viram 0
        comorbidades={c: NIVEL_DA_FEATURE[comorbidades[c]] for c in COMORBIDADES},
        sinais={s: NIVEL_DA_FEATURE[sinais[s]] for s in SINAIS},
        dias_ate_notificacao=dias,
    )
