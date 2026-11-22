"""Esquemas de entrada e saída da API (OpenAPI).

Os esquemas só fixam estrutura e tipos (estritos: texto não vira número). As regras de valor
(intervalo, categorias, obrigatoriedade) são do contrato do pipeline e valem uma vez só, em
`dengue_sinan.pipeline.contrato`; registro com valor inválido volta com `status="invalido"`.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Registro(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        json_schema_extra={"examples": [{"idade_anos": 34, "sexo": "F", "gestante": 0}]},
    )

    idade_anos: float | int | None = Field(
        None, description="Idade em anos (0 a 120). Obrigatória; sem ela o registro é inválido."
    )
    sexo: str | None = Field(None, description="F, M ou I (ignorado). Ausente vira I.")
    gestante: bool | int | None = Field(
        None, description="1/true se gestante (qualquer trimestre), 0/false caso contrário."
    )


class PedidoPrever(BaseModel):
    registros: list[Registro] = Field(min_length=1, description="Um ou mais perfis.")


class Previsao(BaseModel):
    indice: int
    probabilidade: float | None = Field(None, ge=0.0, le=1.0)
    status: Literal["ok", "invalido"]
    erro: str = ""
    avisos: list[str] = Field(
        default_factory=list, description="Avisos de plausibilidade; não bloqueiam o cálculo."
    )


class RespostaPrever(BaseModel):
    versao_modelo: str
    previsoes: list[Previsao]
    alto_risco_motivo: str = Field(
        description="Nenhum limiar de decisão foi escolhido: a resposta não classifica ninguém."
    )
    aviso: str


class RespostaRelatorio(BaseModel):
    dados: dict
    texto: str


class RespostaSaude(BaseModel):
    status: Literal["ok", "degradado"]
    modelo_carregado: bool
    versao_modelo: str | None = None
    e1_disponivel: bool = False
    detalhe: str | None = None


class RespostaE1(BaseModel):
    status: Literal["indisponivel"] = "indisponivel"
    motivo: str


class RespostaVersao(BaseModel):
    sistema: dict
    modelo: dict
    e1: dict


class ErroItem(BaseModel):
    indice: int | None = None
    campo: str
    motivo: str


class RespostaErro(BaseModel):
    detail: str | list[ErroItem]
