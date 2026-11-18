"""Pipeline de ML (Etapa 2): preparação, treino, avaliação, artefatos e inferência.

Treino e inferência são separados: `inferencia` só importa `contrato`, `preprocessamento` e
`artefatos`; nunca importa `preparacao`, `treino` nem leitores de dados.
"""
