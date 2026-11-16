"""Verificação da T-2.1 (Marco 2, no PC local, D-66): grava reports/verificacao/T-2.1.json.

Compara população, eventos, por ano e por região, e cada etapa do fluxograma com
config/esperado.yaml (valores copiados do profiling, nunca escritos aqui).
"""

from pathlib import Path

import yaml

from dengue_sinan import dataset, verify

ESPERADO_PADRAO = Path(__file__).resolve().parents[2] / "config" / "esperado.yaml"
ETAPAS_FLUXO = ["total_baixado", "classi_fin_10_11_12", "rotulo_conhecido", "idade_valida"]


def executar(cfg: dict, esperado_path: Path = ESPERADO_PADRAO) -> Path:
    """Carrega o desenvolvimento, confere com o esperado e grava o relatório T-2.1."""
    esperado = yaml.safe_load(Path(esperado_path).read_text(encoding="utf-8"))
    dev = esperado["desenvolvimento"]
    anos = cfg["anos_dev"]
    if anos != dev["anos"]:
        raise ValueError(f"anos_dev {anos} difere do esperado {dev['anos']}")

    pop, flow, reasons = dataset.load_population_with_flow(cfg, anos)
    dataset.write_fluxograma(cfg, flow, reasons)

    checks = [
        verify.check("casos_desenvolvimento", dev["populacao_total"], len(pop)),
        verify.check("eventos_desenvolvimento", dev["eventos_total"], int(pop["y"].sum())),
    ]
    for ano in anos:
        do_ano = pop[pop["ANO"] == ano]
        checks.append(verify.check(f"casos_{ano}", dev["populacao_por_ano"][ano], len(do_ano)))
        checks.append(verify.check(f"eventos_{ano}", dev["eventos_por_ano"][ano],
                                   int(do_ano["y"].sum())))
    for regiao, eventos in dev["eventos_por_regiao"].items():
        obtido = int(pop.loc[pop["regiao"] == regiao, "y"].sum())
        checks.append(verify.check(f"eventos_regiao_{regiao}", eventos, obtido))
    for ano in anos:
        for i, etapa in enumerate(ETAPAS_FLUXO):
            checks.append(verify.check(f"fluxo_{ano}_{etapa}",
                                       esperado["fluxograma"][ano][etapa],
                                       int(flow.iloc[i][ano])))
    return verify.write_report("T-2.1", checks, Path(cfg["caminhos"]["relatorios"])
                               / "verificacao", cfg)
