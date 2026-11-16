"""Dados sintéticos de população para os testes de T-2.1 (nenhum microdado real)."""

from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from dengue_sinan import dataset as ds
from dengue_sinan.profiling import COMORBIDADES, SINAIS


def linha(**campos) -> dict:
    """Notificação de dengue 10, evolução cura, 40 anos, sem comorbidades; campos sobrescrevem."""
    base = {c: None for c in ds.POPULATION_COLUMNS}
    base.update({"CLASSI_FIN": "10", "EVOLUCAO": "1", "NU_IDADE_N": "4040",
                 "ANO_NASC": "1982", "DT_SIN_PRI": "20220110", "DT_NOTIFIC": "20220112",
                 "CS_SEXO": "F", "CS_GESTANT": "5", "CS_RACA": "4", "ID_MN_RESI": "310620",
                 "SG_UF": "31", **{c: "2" for c in COMORBIDADES + SINAIS}})
    base.update(campos)
    return base


def gravar(cfg: dict, ano: int, linhas: list[dict], colunas=None) -> Path:
    colunas = colunas or ds.POPULATION_COLUMNS
    tabela = pa.table({c: pa.array([reg.get(c) for reg in linhas], type=pa.string())
                       for c in colunas})
    caminho = ds.parquet_path(cfg, ano)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tabela, caminho)
    return caminho


def cfg_sintetico(tmp_path: Path) -> dict:
    return {
        "anos_dev": [2022, 2023],
        "ano_teste": 2024,
        "caminhos": {"dados": str(tmp_path / "data"), "relatorios": str(tmp_path / "reports")},
        "supressao_min_celula": 10,
    }


def dados_sinteticos(cfg: dict) -> dict:
    """2022 com 7 linhas cobrindo cada regra de exclusão; 2023 com uma linha comum.

    População: 4 em 2022 (linhas 1, 2, 3 e 7) e 1 em 2023; eventos: 2 (linhas 2 e 3).
    """
    gravar(cfg, 2022, [
        linha(),                                                  # 1. entra, y = 0
        linha(CLASSI_FIN="12", EVOLUCAO=None),                    # 2. grave, entra, y = 1
        linha(EVOLUCAO="2"),                                      # 3. óbito, entra, y = 1
        linha(CLASSI_FIN="8"),                                    # 4. sai no filtro 2
        linha(CLASSI_FIN="11", EVOLUCAO="9"),                     # 5. sai no filtro 3
        linha(NU_IDADE_N="4407", ANO_NASC=None),                  # 6. sai no filtro 4
        linha(DT_SIN_PRI="20220101", DT_NOTIFIC="20220110",
              DIABETES="1", HIPERTENSA="1"),                      # 7. entra, 9 dias de atraso
    ])
    gravar(cfg, 2023, [linha()])                                  # entra, y = 0
    return cfg
