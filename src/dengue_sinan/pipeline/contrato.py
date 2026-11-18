"""Contrato de entrada e saída do modelo: campos, tipos, categorias e valores padrão.

É a única fonte da verdade para a validação. O treino converte os microdados para este
contrato e a inferência valida os registros contra ele; assim os dois usam as mesmas regras.
"""

import json
from dataclasses import dataclass
from pathlib import Path

SEXOS = ("F", "M", "I")  # mesma ordem de dataset.SEXOS; a ordem define o código ordinal
IDADE_MIN, IDADE_MAX = 0.0, 120.0  # população analítica: idade válida de 0 a 120 anos (D-45)

RAIZ = Path(__file__).resolve().parents[3]
CAMINHO_AUTORIZADAS = RAIZ / "config" / "variaveis_autorizadas.json"


@dataclass(frozen=True)
class Campo:
    nome: str
    tipo: str  # "numero" | "categoria" | "binario"
    obrigatorio: bool
    padrao: object | None
    categorias: tuple | None
    minimo: float | None
    maximo: float | None
    descricao: str

    def como_dict(self) -> dict:
        return {
            "nome": self.nome,
            "tipo": self.tipo,
            "obrigatorio": self.obrigatorio,
            "padrao_se_ausente": self.padrao,
            "categorias_aceitas": list(self.categorias) if self.categorias else None,
            "minimo": self.minimo,
            "maximo": self.maximo,
            "descricao": self.descricao,
        }


# Todos os campos que o pipeline sabe validar. Quais deles entram no modelo vem de
# config/variaveis_autorizadas.json e da configuração de treino.
CAMPOS: dict[str, Campo] = {
    "idade_anos": Campo(
        "idade_anos",
        "numero",
        True,
        None,
        None,
        IDADE_MIN,
        IDADE_MAX,
        "Idade em anos (fracionária aceita), de 0 a 120. Obrigatório; sem valor padrão.",
    ),
    "sexo": Campo(
        "sexo",
        "categoria",
        False,
        "I",
        SEXOS,
        None,
        None,
        "F, M ou I (ignorado). Ausente ou nulo vira I, como no treino.",
    ),
    "gestante": Campo(
        "gestante",
        "binario",
        False,
        0,
        (0, 1),
        None,
        None,
        "1 se gestante em qualquer trimestre ou com idade gestacional ignorada, 0 caso contrário. "
        "Ausente ou nulo vira 0, como no treino.",
    ),
}


def variaveis_autorizadas(caminho: Path = CAMINHO_AUTORIZADAS) -> list[str]:
    return list(json.loads(Path(caminho).read_text("utf-8"))["variaveis"])


def checar_variaveis(variaveis: list[str], autorizadas: list[str] | None = None) -> list[str]:
    """Recusa variável fora da lista autorizada, proibida (guard R4) ou sem regra de validação."""
    from dengue_sinan.guard import assert_features_permitidas

    autorizadas = autorizadas if autorizadas is not None else variaveis_autorizadas()
    variaveis = list(variaveis)
    if len(set(variaveis)) != len(variaveis):
        raise ValueError(f"variáveis repetidas: {variaveis}")
    assert_features_permitidas(variaveis, autorizadas)
    sem_regra = [v for v in variaveis if v not in CAMPOS]
    if sem_regra:
        raise ValueError(f"variáveis sem regra de validação no contrato: {sem_regra}")
    return variaveis


def contrato_de_entrada(variaveis: list[str]) -> dict:
    """Descrição legível por máquina do que o modelo aceita, na ordem do modelo."""
    return {
        "campos": [CAMPOS[v].como_dict() for v in variaveis],
        "campos_extras": "recusados",
        "registro_invalido": "levanta EntradaInvalida (padrão) ou devolve status=invalido e "
        "probabilidade nula, com erros='marcar'",
        "saida": {
            "probabilidade": "float em [0, 1]: probabilidade calibrada do desfecho (dengue grave "
            "ou óbito pelo agravo) em paciente notificado com dengue",
            "status": "ok | invalido",
            "erro": "texto vazio quando status=ok",
            "versao_modelo": "identificador do artefato usado",
        },
        "aviso": "Probabilidade de um modelo exploratório. Não é diagnóstico nem tem validade "
        "clínica demonstrada.",
    }
