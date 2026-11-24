"""Textos do modo Normal da demo (D-96): linguagem simples, sem termos de estatística ou de IA.

São funções puras, sem Streamlit, para testar o texto sem abrir a tela. Os números vêm sempre
de `app.servico` (modelos e agregados do teste); aqui só se escolhe como dizê-los. O modo Pro
continua com os rótulos técnicos de `app.streamlit_app`.
"""

from __future__ import annotations

import math

from app import servico

MODO_NORMAL = "normal"
MODO_PRO = "pro"
MODOS = {MODO_NORMAL: "Normal (linguagem simples)",
         MODO_PRO: "Pro (detalhes estatísticos e do modelo)"}

ABA_PERFIL = "Perfil"
ABA_TRIAGEM = "Triagem"

COMO_LER = (
    "Este número é uma estimativa feita por um programa de computador a partir de casos de dengue "
    "notificados no Brasil em 2022 e 2023. Ele mostra como grupos de pessoas parecidas costumaram "
    "evoluir. Não diz o que vai acontecer com uma pessoa em particular, não é um diagnóstico e não "
    "indica tratamento. Com sintomas ou dúvidas, procure um serviço de saúde."
)
NAO_E_CAUSA = (
    "Os fatores abaixo mostram o que o programa levou em conta neste caso: contribuição no modelo, "
    "não causa. Eles não provam que algo causou ou vai causar a doença."
)
SEM_ESTIMATIVA = (
    "Não há dados suficientes para estimar o risco com esta combinação de condições, porque poucos "
    "casos parecidos foram vistos."
)
EXPLICACAO_INDISPONIVEL = "A explicação por fator não está disponível para este modelo."
ABA_INDISPONIVEL = "Esta parte do programa não está disponível nesta instalação."


def um_em(fracao: float) -> str:
    """Risco como frase de frequência: "cerca de 1 em 620" (dois algarismos significativos)."""
    if fracao <= 0:
        return "praticamente nenhum caso"
    if fracao >= 0.1:
        return f"cerca de {round(100 * fracao)} em cada 100"
    n = 1 / fracao
    n = round(n, 1 - math.floor(math.log10(n)))
    return f"cerca de 1 em {servico.inteiro(int(n))}"


def frase_risco(fracao: float) -> str:
    return (f"Entre pessoas com dengue confirmada e este perfil, {um_em(fracao)} evolui para a "
            "forma grave ou morre pela doença.")


def frase_comparacao(risco: float, risco_base: float, razao: float, tem_comorbidade: bool) -> str:
    if not tem_comorbidade:
        return "Nenhuma condição marcada: este é o próprio perfil de comparação."
    base = (f"Para alguém da mesma idade e sexo, sem nenhuma dessas condições, o risco estimado "
            f"seria {um_em(risco_base)}.")
    if razao >= 1.1:
        return f"{base} O risco deste perfil é cerca de {servico.numero(razao, 1)} vezes maior."
    if razao <= 0.9:
        return (f"{base} O risco deste perfil é cerca de {servico.numero(1 / razao, 1)} vezes "
                "menor, mas essa diferença pode ser acaso.")
    return f"{base} A diferença é pequena."


def efeito(aumenta: bool) -> str:
    return "aumenta o risco neste caso" if aumenta else "diminui o risco neste caso"


def aviso_subestimado(painel: servico.PainelTeste | None) -> str | None:
    """Aviso de que o risco mostrado pode estar abaixo do real, quando o teste mostrou isso."""
    if painel is None or painel.obs_esp_m1 <= 1:
        return None
    return ("Em 2024, ano de epidemia, o programa subestimou o risco: houve mais casos graves "
            "do que o previsto. O risco mostrado aqui pode estar abaixo do real.")


def linhas_painel(p: servico.PainelTeste) -> list[str]:
    """O que o teste de 2024 mostrou, em palavras simples e com os números do arquivo."""
    quase_todos = servico.porcentagem(1 - p.precisao, 0)
    linhas = [
        f"Testamos o programa em 2024, com {servico.inteiro(p.casos)} casos de dengue, dos quais "
        f"{servico.inteiro(p.eventos)} ficaram graves ou morreram. O programa apontou cerca de "
        f"{servico.porcentagem(p.fracao_alto_risco, 0)} dos casos como mais preocupantes e "
        f"encontrou cerca de {servico.porcentagem(p.recall, 0)} dos que de fato ficaram graves.",
        f"Mas cerca de {quase_todos} dos apontados não ficaram graves. Por isso o resultado serve "
        "para pensar em grupos, e não para decidir sobre uma pessoa.",
    ]
    aviso = aviso_subestimado(p)
    if aviso:
        linhas.append(aviso)
    if not p.sc02_passou:
        linhas.append("Uma regra usada hoje nos serviços de saúde encontrou um pouco mais dos "
                      "casos graves do que o programa. O programa não alcançou essa regra, e isso "
                      "foi registrado como resultado do trabalho.")
    return linhas
