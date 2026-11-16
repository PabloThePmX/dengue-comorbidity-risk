"""Verificação da T-2.3 (Marco 2, no PC local, D-66): grava reports/verificacao/T-2.3.json.

Confere os eventos por região (cada dobra de validação) com config/esperado.yaml, o hash do
conteúdo das dobras (D-72) e que a releitura confere o hash. Os sha256_dbc de cada ano vêm do
data/manifest.json pelo próprio verify.write_report (campo hash_dados).
"""

from pathlib import Path

import yaml

from dengue_sinan import dataset, folds, verify

ESPERADO_PADRAO = Path(__file__).resolve().parents[2] / "config" / "esperado.yaml"


def executar(cfg: dict, esperado_path: Path = ESPERADO_PADRAO) -> Path:
    """Carrega o desenvolvimento, monta as dobras duas vezes e grava o relatório T-2.3."""
    esperado = yaml.safe_load(Path(esperado_path).read_text(encoding="utf-8"))
    dev = esperado["desenvolvimento"]
    anos = cfg["anos_dev"]
    if anos != dev["anos"]:
        raise ValueError(f"anos_dev {anos} difere do esperado {dev['anos']}")

    pop, _flow, _reasons = dataset.load_population_with_flow(cfg, anos)

    pasta = Path(cfg["caminhos"]["dados"]) / "folds"
    caminho = pasta / "dobras_dev.parquet"
    caminho_repetido = pasta / "dobras_dev_reexecucao.parquet"
    h1 = folds.save_folds(cfg, pop, caminho)
    h2 = folds.save_folds(cfg, pop, caminho_repetido)  # segunda execução, mesma semente (D-72)
    caminho_repetido.unlink()
    lido = folds.load_folds(caminho, h1)  # recusa o arquivo se o hash não bater

    checks = [
        verify.check("casos_em_validacao", dev["populacao_total"], len(lido)),
        verify.check("eventos_em_validacao", dev["eventos_total"],
                     int(pop["y"].sum())),
    ]
    for regiao, eventos in dev["eventos_por_regiao"].items():
        obtido = int(pop.loc[pop["regiao"] == regiao, "y"].sum())
        checks.append(verify.check(f"eventos_validacao_{regiao}", eventos, obtido))
    # Mesmo conteúdo em duas execuções: esperado = a 2ª, obtido = a 1ª.
    checks.append(verify.check("hash_conteudo_dobras", h2, h1))
    checks.append(verify.check("releitura_confere_hash", True, folds.folds_hash(lido) == h1))
    return verify.write_report("T-2.3", checks, Path(cfg["caminhos"]["relatorios"])
                               / "verificacao", cfg)
