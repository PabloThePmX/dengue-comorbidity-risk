"""Entrada comum dos modelos externos da comparação (D-97, desenho passo 1).

Exporta o quadro de features do projeto (`dataset.build_feature_frame` sobre a população) com
ANO, LINHA e y, para que cada modelo externo converta esse quadro para o contrato dele (adaptador)
e alinhe as previsões com o desfecho pela chave (ANO, LINHA).

Duas portas, sem atalho:
- `comparacao=False`: só anos de desenvolvimento. Recusa o ano de teste e o de comparação.
- `comparacao=True`: exige `guard.leitura_do_ano_de_comparacao()` aberta e só carrega o ano de
  comparação (R1, D-97).

O arquivo vai para `data/` (ignorada pelo git, R7). Ao lado, grava um JSON pequeno com os nomes
das features do projeto (dicionário de R4), que o script de previsão confere.
"""

import json
from pathlib import Path

from dengue_sinan import dataset, guard
from dengue_sinan.preprocess import FEATURES_PERMITIDAS
from dengue_sinan.profiling import COMORBIDADES, SINAIS

COLUNAS_FEATURES = [
    "idade_anos", "sexo", "gestante", *COMORBIDADES, "n_comorbidades", *SINAIS,
    "dias_ate_notificacao",
]
COLUNAS_CHAVE = ["ANO", "LINHA", "y"]


def caminho_metadados(destino: str | Path) -> Path:
    """JSON de conferência gravado ao lado da entrada (mesmo nome, extensão .json)."""
    return Path(destino).with_suffix(".json")


def exportar_entrada(cfg: dict, ano: int, destino: str | Path, *, comparacao: bool = False) -> Path:
    """Grava o quadro de features de um ano em Parquet e devolve o caminho."""
    destino = Path(destino)
    if "reports" in {p.lower() for p in destino.resolve().parts}:
        raise PermissionError("recusado: entrada com microdados não pode ir a reports/ "
                              f"({destino})")
    ano_teste = cfg["ano_teste"]
    ano_comparacao = cfg.get("ano_comparacao")
    if comparacao:
        # A porta é do chamador (o avaliador abre guard.leitura_do_ano_de_comparacao() depois do
        # manifesto commitado). Sem ela, load_population_with_flow recusa antes de abrir o arquivo.
        if ano != ano_comparacao:
            raise RuntimeError(f"comparacao=True só exporta o ano de comparação ({ano_comparacao}) "
                               f"(R1, D-97): recebi {ano}")
        populacao, _, _ = dataset.load_population_with_flow(cfg, [ano], comparacao=True)
        guard.assert_dev_only(populacao)  # dentro da porta: só o ano de comparação passa
        quadro = dataset.build_feature_frame(populacao)
    else:
        if ano in (ano_teste, ano_comparacao):
            raise RuntimeError(f"{ano} não é ano de desenvolvimento (R1, D-97): use "
                               "comparacao=True dentro da porta, ou um ano de desenvolvimento")
        # load_population_with_flow (e não load_population): não regrava reports/fluxograma.md.
        populacao, _, _ = dataset.load_population_with_flow(cfg, [ano])
        guard.assert_dev_only(populacao)
        quadro = dataset.build_feature_frame(populacao)

    saida = quadro[COLUNAS_FEATURES].copy()
    saida["ANO"] = populacao["ANO"].to_numpy()
    saida["LINHA"] = populacao["LINHA"].to_numpy()
    saida["y"] = populacao["y"].astype("int8").to_numpy()
    saida = saida[[*COLUNAS_FEATURES, *COLUNAS_CHAVE]].reset_index(drop=True)

    destino.parent.mkdir(parents=True, exist_ok=True)
    saida.to_parquet(destino, index=False)
    caminho_metadados(destino).write_text(
        json.dumps(
            {
                "ano": int(ano),
                "comparacao": bool(comparacao),
                "linhas": int(len(saida)),
                "eventos": int(saida["y"].sum()),
                "features_do_projeto": list(FEATURES_PERMITIDAS),
                "colunas": list(saida.columns),
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    return destino
