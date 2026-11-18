"""Linha de comando: preparar, treinar, avaliar, prever.

python -m dengue_sinan.pipeline.cli preparar --data-dir data/parquet
python -m dengue_sinan.pipeline.cli treinar --config config/treino_perfil.json
python -m dengue_sinan.pipeline.cli avaliar --artefato artefatos/modelos/m1-perfil-2.0.0
python -m dengue_sinan.pipeline.cli prever --artefato <pasta> --entrada registros.json
"""

import argparse
import json
import sys
from pathlib import Path

PREPARADO = "data/processed/dev_2022_2023.parquet"
ARTEFATOS = "artefatos/modelos"


def _json(obj) -> str:
    return json.dumps(obj, indent=2, ensure_ascii=False, default=str)


def _preparar(a) -> int:
    from dengue_sinan.pipeline.preparacao import preparar_dev, salvar_preparado

    conjunto, registro = preparar_dev(a.data_dir)
    caminho = salvar_preparado(conjunto, a.saida)
    print(
        _json({"conjunto": str(caminho), "linhas": len(conjunto), "arquivos": registro["arquivos"]})
    )
    return 0


def _treinar(a) -> int:
    from dengue_sinan.etapa1 import sha256_arquivo
    from dengue_sinan.pipeline.preparacao import carregar_preparado
    from dengue_sinan.pipeline.treino import ConfigTreino, repetir_e_comparar, treinar_e_salvar

    cfg = ConfigTreino.de_arquivo(a.config)
    x, y, regiao, meta = carregar_preparado(a.dados, cfg.variaveis)
    if a.repetir_e_comparar:
        print(_json(repetir_e_comparar(x, y, regiao, meta, cfg)))
        return 0
    info = {"conjunto_preparado": {"caminho": a.dados, "sha256": sha256_arquivo(Path(a.dados))}}
    pasta = treinar_e_salvar(x, y, regiao, meta, cfg, a.saida, dados_info=info)
    print(_json({"artefato": str(pasta)}))
    return 0


def _avaliar(a) -> int:
    from dengue_sinan.pipeline import artefatos
    from dengue_sinan.pipeline.avaliacao import avaliar
    from dengue_sinan.pipeline.inferencia import carregar_modelo
    from dengue_sinan.pipeline.preparacao import carregar_preparado

    meta = artefatos.verificar(a.artefato)
    guardada = json.loads((Path(a.artefato) / "avaliacao_dev.json").read_text("utf-8"))
    saida = {"identificador": meta["identificador"], "avaliacao_guardada_no_treino": guardada}
    if a.dados:
        preditor = carregar_modelo(a.artefato)
        x, y, _, _ = carregar_preparado(a.dados, preditor.variaveis)
        reg = preditor.prever(x.to_dict("records"))
        saida["aplicacao_aos_dados_fornecidos"] = avaliar(
            y,
            reg["probabilidade"].to_numpy(),
            "modelo final aplicado a dados de desenvolvimento; se são os do treino é "
            "resubstituição, não estimativa de desempenho",
        )
    print(_json(saida))
    return 0


def _avaliar_oof(a) -> int:
    from dengue_sinan.pipeline.avaliar_oof import executar

    r = executar(Path(a.config_modelo), Path(a.config_avaliacao), Path(a.dados))
    print(
        _json(
            {
                "oof_local": r["oof_local"],
                "tabelas": r["tabelas"],
                "replicacoes_invalidas": r["diagnostico"]["replicacoes_invalidas_por_metrica"],
            }
        )
    )
    return 0


def _prever(a) -> int:
    import pandas as pd

    from dengue_sinan.pipeline.inferencia import EntradaInvalida, carregar_modelo

    caminho = Path(a.entrada)
    registros = (
        pd.read_csv(caminho) if caminho.suffix == ".csv" else json.loads(caminho.read_text("utf-8"))
    )
    try:
        saida = carregar_modelo(a.artefato).prever(registros, erros=a.erros)
    except EntradaInvalida as e:
        print(_json({"erro": str(e), "detalhes": e.erros}), file=sys.stderr)
        return 2
    print(saida.to_json(orient="records", force_ascii=False, indent=2))
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(
        prog="dengue_sinan.pipeline.cli",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = p.add_subparsers(dest="comando", required=True)
    s = sub.add_parser("preparar", help="gera o conjunto analítico de 2022–2023")
    s.add_argument("--data-dir", default="data/parquet")
    s.add_argument("--saida", default=PREPARADO)
    s.set_defaults(f=_preparar)
    s = sub.add_parser("treinar", help="treina e grava um artefato novo")
    s.add_argument("--config", default="config/treino_perfil.json")
    s.add_argument("--dados", default=PREPARADO)
    s.add_argument("--saida", default=ARTEFATOS)
    s.add_argument(
        "--repetir-e-comparar",
        action="store_true",
        help="treina duas vezes, compara e não grava artefato",
    )
    s.set_defaults(f=_treinar)
    s = sub.add_parser("avaliar", help="mostra a avaliação guardada; com --dados, aplica o modelo")
    s.add_argument("--artefato", required=True)
    s.add_argument("--dados")
    s.set_defaults(f=_avaliar)
    s = sub.add_parser("avaliar-oof", help="OOF do M1 e baselines, métricas e ICs por município")
    s.add_argument("--config-modelo", default="config/treino_perfil.json")
    s.add_argument("--config-avaliacao", default="config/avaliacao_oof.json")
    s.add_argument("--dados", default=PREPARADO)
    s.set_defaults(f=_avaliar_oof)
    s = sub.add_parser("prever", help="probabilidades para registros novos (json ou csv)")
    s.add_argument("--artefato", required=True)
    s.add_argument("--entrada", required=True)
    s.add_argument("--erros", choices=["levantar", "marcar"], default="levantar")
    s.set_defaults(f=_prever)
    a = p.parse_args(argv)
    return a.f(a)


if __name__ == "__main__":
    raise SystemExit(main())
