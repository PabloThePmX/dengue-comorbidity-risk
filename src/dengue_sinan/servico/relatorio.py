"""Relatório automático de desempenho e limitações de um artefato.

Só lê `metadados.json` e `avaliacao_dev.json` já gravados e verificados por hash. Cada número
do texto vem desses arquivos: nada é recalculado nem estimado aqui. O relatório diz de onde vêm
as métricas e o que elas NÃO são.
"""

import json
from pathlib import Path

from dengue_sinan.servico import registro

AVISO = (
    "Projeto acadêmico. Não é ferramenta clínica nem substitui avaliação médica. "
    "A probabilidade vem de um modelo exploratório sem validade clínica demonstrada."
)


def _num(v, casas: int = 4) -> str:
    return "não informado" if v is None else f"{v:.{casas}f}".replace(".", ",")


def montar(pasta: Path) -> dict:
    """Devolve {'dados': {...}, 'texto': 'markdown'}; levanta ArtefatoInvalido se não confere."""
    pasta = Path(pasta)
    meta = registro.verificar(pasta)
    av = json.loads((pasta / "avaliacao_dev.json").read_text("utf-8"))
    cal = av.get("calibrado_validacao_cruzada", {})
    bruto = av.get("sem_calibrar", {})
    dados = {
        "identificador": meta["identificador"],
        "algoritmo": meta.get("algoritmo"),
        "calibrador": meta.get("calibrador"),
        "variaveis": meta.get("variaveis_de_entrada"),
        "anos_desenvolvimento": meta.get("anos_desenvolvimento"),
        "n_linhas": meta.get("n_linhas"),
        "prevalencia_desenvolvimento": meta.get("prevalencia_desenvolvimento"),
        "escopo_das_metricas": av.get("escopo"),
        "e_teste_historico": av.get("e_teste_historico"),
        "calibrado": {k: cal.get(k) for k in ("pr_auc", "roc_auc", "brier")},
        "sem_calibrar": {k: bruto.get(k) for k in ("pr_auc", "roc_auc", "brier")},
        "brier_referencia_prevalencia": cal.get("brier_referencia_prevalencia"),
        "limitacoes": av.get("limitacoes") or meta.get("limitacoes") or [],
        "aviso": AVISO,
    }
    linhas = [
        f"# Relatório do modelo {dados['identificador']}",
        "",
        f"**Aviso:** {AVISO}",
        "",
        "## O que é este modelo",
        f"- Algoritmo: {dados['algoritmo']}; calibração: {dados['calibrador']}.",
        f"- Variáveis de entrada: {', '.join(dados['variaveis'] or [])}.",
        f"- Dados de desenvolvimento: anos {dados['anos_desenvolvimento']}, "
        f"{dados['n_linhas']} linhas, prevalência do desfecho "
        f"{_num(dados['prevalencia_desenvolvimento'], 5)}.",
        "",
        "## Desempenho de desenvolvimento (números gravados no artefato)",
        f"- Escopo: {dados['escopo_das_metricas']}.",
        f"- É o teste temporal histórico? {'sim' if dados['e_teste_historico'] else 'não'}.",
        f"- Calibrado: PR-AUC {_num(cal.get('pr_auc'))}; ROC-AUC {_num(cal.get('roc_auc'))}; "
        f"Brier {_num(cal.get('brier'), 6)} (referência pela prevalência: "
        f"{_num(cal.get('brier_referencia_prevalencia'), 6)}).",
        f"- Sem calibrar: PR-AUC {_num(bruto.get('pr_auc'))}; "
        f"ROC-AUC {_num(bruto.get('roc_auc'))}; "
        f"Brier {_num(bruto.get('brier'), 6)}.",
        "- Estes números são de validação cruzada em dados de desenvolvimento. Não são desempenho "
        "em dado futuro e este relatório não afirma que o modelo está validado.",
        "",
        "## Limitações registradas",
        *[f"- {t}" for t in dados["limitacoes"]],
        "",
    ]
    return {"dados": dados, "texto": "\n".join(linhas)}
