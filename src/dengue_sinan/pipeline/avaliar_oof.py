"""Orquestra a avaliação da Etapa 3.2: OOF → métricas → bootstrap → exportação agregada."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from dengue_sinan.etapa1 import sha256_arquivo
from dengue_sinan.pipeline import bootstrap, exportacao, metricas, oof
from dengue_sinan.pipeline.contrato import RAIZ
from dengue_sinan.pipeline.preparacao import carregar_agrupamento, carregar_preparado
from dengue_sinan.pipeline.treino import ConfigTreino, _ambiente, hash_dados

MODELOS = list(oof.MODELOS)


def _contagens(t: metricas.TabelaNiveis) -> pd.DataFrame:
    linhas = [
        {
            "regiao": r,
            "n_linhas": t.linhas_por_regiao[r],
            "n_eventos": t.eventos_por_regiao[r],
            "n_conglomerados": len(t.indice_regiao[r]),
            "prevalencia": t.eventos_por_regiao[r] / t.linhas_por_regiao[r],
        }
        for r in t.regioes
    ]
    return pd.DataFrame(linhas)


def executar(
    config_modelo: Path,
    config_avaliacao: Path,
    dados_preparados: Path,
    saida_agregada: Path | None = None,
    saida_local: Path | None = None,
) -> dict:
    cfg = ConfigTreino.de_arquivo(config_modelo)
    av = json.loads(Path(config_avaliacao).read_text("utf-8"))
    bs = av["bootstrap"]
    x, y, regiao, meta = carregar_preparado(dados_preparados, cfg.variaveis)
    cong = carregar_agrupamento(dados_preparados)  # nunca entra em x
    if not (len(x) == len(y) == len(regiao) == len(cong)):
        raise ValueError("tamanhos inconsistentes entre predições, região e conglomerado")
    tabela, info = oof.gerar_oof(x, y, regiao, meta, cfg, cong)
    destino_local = Path(saida_local or RAIZ / av["saida_local_oof"]) / av["versao_avaliacao"]
    if (destino_local / "oof_predicoes.parquet").exists():
        raise FileExistsError(f"{destino_local} já tem OOF; mude `versao_avaliacao`")
    caminho_oof = oof.salvar_oof_local(tabela, destino_local)
    t = metricas.montar_tabela(tabela, MODELOS)
    boot = bootstrap.executar_bootstrap(
        t, MODELOS, bs["replicacoes"], bs["seed"], bs["nivel"], referencia="m1"
    )
    tab = exportacao.tabelas(boot, MODELOS, t.regioes, _contagens(t))
    tamanhos = pd.Series(tabela.groupby("conglomerado").size())
    meta_av = {
        "versao_avaliacao": av["versao_avaliacao"],
        "gerado_em_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "modelo_avaliado": f"{cfg.nome_modelo}-{cfg.versao_modelo}",
        "escopo": "desenvolvimento 2022–2023, leave-one-region-out; sem validação externa",
        "variaveis_do_modelo": cfg.variaveis,
        "agrupamento": {
            "variavel": av["agrupamento"],
            "descricao": av["agrupamento_descricao"],
            "usado_como_preditor": False,
            "n_conglomerados": int(len(tamanhos)),
        },
        "dados": {
            "conjunto_preparado_sha256": sha256_arquivo(Path(dados_preparados)),
            "hash_conteudo_e_ordem_x_y": hash_dados(x, y),
            "n_linhas_conjunto": int(len(y)),
            "n_linhas_avaliadas": int(len(tabela)),
            "linhas_sem_regiao_excluidas": info["linhas_sem_regiao_excluidas"],
            "ordem_das_linhas": "a do conjunto preparado (2022 e depois 2023, como em montar_dev)",
            "oof_local_sha256": sha256_arquivo(caminho_oof),
            "oof_local": "armazenamento local ignorado pelo Git; não publicado",
        },
        "modelo": {
            "algoritmo": cfg.algoritmo,
            "params": cfg.params,
            "calibrador": cfg.calibrador,
            "seed": cfg.seed,
            "n_jobs": cfg.n_jobs,
            "paciencia": cfg.paciencia,
            "val_frac": cfg.val_frac,
            "max_iter": cfg.max_iter,
            "parametros_do_estimador_xgboost": info["dobras"][0]["parametros_estimador"],
        },
        "dobras": info["dobras"],
        "baselines": av["baselines"],
        "bootstrap": bs
        | {"variavel_de_agrupamento": av["agrupamento"], "estratificado_por": "regiao"},
        "metricas_calculadas": list(metricas.METRICAS),
        "modelos_avaliados": {m: oof.ROTULOS[m] for m in MODELOS},
        "ambiente": _ambiente(),
        "codigo": exportacao.hash_do_codigo(),
        "tamanho_dos_conglomerados": {  # só agregados, sem identificar município
            "mediana": float(tamanhos.median()),
            "maior_fracao_das_linhas": float(tamanhos.max() / tamanhos.sum()),
        },
    }
    diag = boot["diagnostico"] | {
        "conglomerados_por_regiao": {r: len(t.indice_regiao[r]) for r in t.regioes}
    }
    pasta = Path(saida_agregada or RAIZ / av["saida_agregada"])
    escritos = exportacao.gravar(tab, meta_av, diag, pasta)
    return {
        "oof_local": str(caminho_oof),
        "tabelas": [str(p) for p in escritos],
        "diagnostico": diag,
        "info_dobras": info,
    }
