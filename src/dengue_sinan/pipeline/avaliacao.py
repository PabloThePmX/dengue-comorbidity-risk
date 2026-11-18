"""Avaliação de desenvolvimento: discriminação e calibração, com escopo e limitações explícitos.

As métricas daqui vêm de dados de desenvolvimento (2022–2023). Não substituem nem se misturam
com o teste temporal histórico de 2024, que continua lacrado e fora do pipeline.
"""

import numpy as np

from dengue_sinan.metrics import brier, calibracao_resumo, pr_auc, roc_auc

LIMITACOES = [
    "Métricas de desenvolvimento (validação cruzada leave-one-region-out em 2022–2023); não são "
    "desempenho em dado futuro e não substituem o teste temporal histórico, que não foi usado.",
    "O ajuste do XGBoost é sensível à ordem das linhas, à ordem das colunas e à semente "
    "(parada antecipada com desfecho raro). Em ajustes alternativos da auditoria 1D, a PR-AUC "
    "calibrada variou entre 0,0254 e 0,0277 com o conjunto de 25 variáveis. Leia os valores como "
    "faixa, não como número exato.",
    "Só três variáveis de entrada (idade, sexo, gestante). Comorbidades, sintomas e atraso até "
    "a notificação ficam fora porque a auditoria não os classificou como seguros.",
    "Associação não é causalidade. A probabilidade não tem validade clínica demonstrada e não "
    "orienta conduta.",
    "ROC-AUC não é critério isolado: com desfecho raro, leia PR-AUC, Brier e calibração junto.",
]


def avaliar(y, p, escopo: str) -> dict:
    """Métricas pontuais e de calibração. `escopo` diz de onde vêm os dados."""
    y, p = np.asarray(y), np.asarray(p, dtype="float64")
    ok = ~np.isnan(p)
    y, p = y[ok], p[ok]
    if len(y) == 0 or y.min() == y.max():
        raise ValueError("avaliação exige as duas classes presentes")
    prev = float(y.mean())
    return {
        "escopo": escopo,
        "n": int(len(y)),
        "prevalencia": prev,
        "pr_auc": pr_auc(y, p),
        "roc_auc": roc_auc(y, p),
        "brier": brier(y, p),
        "brier_referencia_prevalencia": brier(y, np.full(len(y), prev)),
        "calibracao": calibracao_resumo(y, p),
    }


def montar_avaliacao(y, p_bruto, p_calibrado, pr_auc_por_dobra: dict, escopo: str) -> dict:
    return {
        "escopo": escopo,
        "e_teste_historico": False,
        "sem_calibrar": avaliar(y, p_bruto, escopo),
        "calibrado_validacao_cruzada": avaliar(y, p_calibrado, escopo),
        "pr_auc_por_dobra_sem_calibrar": pr_auc_por_dobra,
        "limitacoes": LIMITACOES,
    }
