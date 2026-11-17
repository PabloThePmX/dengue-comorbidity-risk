"""Bloco `shap` do relatório de sessão `sessao-m1.json` (T-4.8, D-57, R7).

Confere os agregados gravados por `shap_global.gravar_shap_global` com `verify.check`, sem digitar
valores esperados: o que é esperado vem da config (tamanho da amostra, supressão de células) ou do
próprio modelo (nº de colunas que o pré-processador lê). Só agregados entram no relatório (R7).
"""

from __future__ import annotations

import csv
from pathlib import Path

from dengue_sinan import shap_global, verify

BLOCO = "shap"
SESSAO_PADRAO = "sessao-m1.json"


def _linhas_csv(caminho: Path) -> int:
    """Nº de linhas de dados (sem o cabeçalho)."""
    with open(caminho, encoding="utf-8") as f:
        return max(sum(1 for _ in csv.reader(f)) - 1, 0)


def _sem_arquivo_por_linha(out_dir: Path, manifesto: dict) -> bool:
    """Só os CSV esperados existem, e nenhum tem mais linhas que o nº de features + cabeçalho."""
    csvs = sorted(p.name for p in out_dir.glob("*.csv"))
    if csvs != sorted(shap_global.ARQUIVOS_DADOS):
        return False
    teto = manifesto["n_features"] + 1
    return all(_linhas_csv(out_dir / nome) <= teto for nome in csvs)


def checks(manifesto: dict, out_dir: str | Path, cfg: dict) -> list[dict]:
    """Checks do bloco `shap` a partir do manifesto e da pasta de agregados (função pura de
    leitura: não roda o SHAP)."""
    out = Path(out_dir)
    p = manifesto["n_features"]
    medidas = manifesto["medidas"]
    tolerancia = shap_global.TOLERANCIA_IDENTIDADE
    return [
        verify.check("agregados_gravados", True, shap_global.arquivos_conferem(out, manifesto)),
        verify.check("n_features_modelo", manifesto["n_colunas_entrada"], p),
        verify.check("n_features_importancia", p,
                     _linhas_csv(out / shap_global.ARQ_IMPORTANCIA)),
        verify.check("n_features_interacoes", p,
                     _linhas_csv(out / shap_global.ARQ_INTERACOES)),
        verify.check("amostra_tamanho", int(cfg["shap"]["amostra"]), manifesto["n_amostra"]),
        verify.check("aditividade_erro_max", 0.0, medidas["erro_aditividade"],
                     tolerancia=tolerancia),
        verify.check("soma_coerente_erro_max", 0.0, medidas["erro_soma"], tolerancia=tolerancia),
        verify.check("simetria_erro_max", 0.0, medidas["erro_simetria"], tolerancia=tolerancia),
        verify.check("positivos_na_amostra_minimo", True,
                     manifesto["n_positivos_amostra"] >= int(cfg["supressao_min_celula"])),
        verify.check("sem_arquivo_por_linha", True, _sem_arquivo_por_linha(out, manifesto)),
    ]


def escrever_bloco_shap(caminho_sessao: str | Path, manifesto: dict, out_dir: str | Path,
                        cfg: dict) -> Path:
    """Cria ou reescreve o bloco `shap` do relatório de sessão, sem apagar os outros blocos."""
    return verify.update_session_report(
        Path(caminho_sessao), BLOCO, checks(manifesto, out_dir, cfg), cfg,
        tarefa=shap_global.TAREFA)
