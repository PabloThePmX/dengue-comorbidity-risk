"""Adaptador do contrato da especificação (CLI/Streamlit) para o contrato real do modelo.

A especificação (§3.15) prevê `gestante` como sim/nao/ignorado, comorbidades, sintomas e dias até
o atendimento. O modelo M1 v2 só aceita `idade_anos`, `sexo` e `gestante` (decisão do usuário,
config/variaveis_autorizadas.json). Este adaptador converte o que dá e DECLARA o que ficou de fora:
nada é descartado em silêncio e nenhuma variável nova passa a entrar no modelo.
"""

CAMPOS_MODELO = ("idade_anos", "sexo", "gestante")
# Campos do contrato da especificação que o M1 v2 não usa (R4: fora da lista autorizada).
CAMPOS_SPEC_NAO_USADOS = (
    "diabetes",
    "hematologica",
    "hepatopatia",
    "renal_cronica",
    "hipertensao",
    "acido_peptica",
    "autoimune",
    "dias_ate_atendimento",
)
SIM_NAO = {"sim": 1, "nao": 0, "não": 0, "ignorado": 0}
SEXO = {"M": "M", "F": "F", "I": "I", "ignorado": "I"}


def adaptar(registro: dict) -> tuple[dict, list[str], list[str]]:
    """Devolve (registro_para_o_modelo, campos_ignorados, erros).

    `id_caso` é livre e não vai ao modelo. Campo desconhecido é erro (evita erro de digitação
    passar como se fosse variável usada). Campos da especificação que o modelo não usa são
    listados em `campos_ignorados`.
    """
    if not isinstance(registro, dict):
        return {}, [], ["registro deve ser um dicionário"]
    erros: list[str] = []
    ignorados: list[str] = []
    saida: dict = {}
    for chave, valor in registro.items():
        if chave == "id_caso":
            continue
        if chave == "idade_anos":
            saida[chave] = valor
        elif chave == "sexo":
            if valor is None:
                saida[chave] = None
            elif isinstance(valor, str) and valor in SEXO:
                saida[chave] = SEXO[valor]
            else:
                erros.append("sexo: use M, F ou ignorado")
        elif chave == "gestante":
            if valor is None:
                saida[chave] = None
            elif isinstance(valor, str) and valor.lower() in SIM_NAO:
                saida[chave] = SIM_NAO[valor.lower()]
            elif isinstance(valor, bool | int) and valor in (0, 1):
                saida[chave] = int(valor)
            else:
                erros.append("gestante: use sim, nao ou ignorado")
        elif chave in CAMPOS_SPEC_NAO_USADOS:
            ignorados.append(chave)
        else:
            erros.append(f"{chave}: campo desconhecido")
    return saida, sorted(ignorados), erros
