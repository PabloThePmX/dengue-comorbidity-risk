"""Testes de carregamento da população e construção de features (T-2.1)."""

import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest
import yaml

from dengue_sinan.checks import REQUIRED_COLUMNS
from dengue_sinan.dataset import (
    build_feature_frame,
    load_dev_population,
    load_population,
    verify_t2_1,
)


def _make_row(**overrides: str | None) -> dict[str, str | None]:
    row: dict[str, str | None] = {col: "2" for col in REQUIRED_COLUMNS}
    row.update(
        {
            "CLASSI_FIN": "10",
            "EVOLUCAO": "1",
            "NU_IDADE_N": "4045",
            "ANO_NASC": "1977",
            "DT_SIN_PRI": "20220201",
            "DT_NOTIFIC": "20220204",
            "CS_SEXO": "F",
            "CS_GESTANT": "5",
            "CS_RACA": "1",
            "ID_MN_RESI": "355030",
            "SG_UF": "35",
        }
    )
    row.update(overrides)
    return row


def test_build_feature_frame_three_levels_comorbidity_count_and_delay_clip() -> None:
    df = pd.DataFrame(
        [
            _make_row(
                DIABETES="1",
                HIPERTENSA="1",
                RENAL="9",
                DT_SIN_PRI="20220101",
                DT_NOTIFIC="20220415",  # > 60 dias -> truncado em 60
                PETEQUIA_N="1",
                LACO="2",
            ),
            _make_row(
                CS_SEXO="I",
                CS_GESTANT="2",
                DIABETES="2",
                HIPERTENSA="2",
                RENAL=None,
                DT_SIN_PRI="20220110",
                DT_NOTIFIC="20220105",  # negativo -> truncado em 0
            ),
        ]
    )
    df["ANO"] = [2022, 2023]
    features = build_feature_frame(df)

    assert features.loc[0, "DIABETES"] == "Sim"
    assert features.loc[0, "HIPERTENSA"] == "Sim"
    assert features.loc[0, "RENAL"] == "Ausente"
    assert features.loc[0, "n_comorbidades"] == 2
    assert features.loc[0, "dias_ate_notificacao"] == 60.0
    assert features.loc[0, "sexo"] == "F"
    assert features.loc[0, "gestante"] == 0

    assert features.loc[1, "RENAL"] == "Ausente"
    assert features.loc[1, "n_comorbidades"] == 0
    assert features.loc[1, "dias_ate_notificacao"] == 0.0
    assert features.loc[1, "sexo"] == "I"
    assert features.loc[1, "gestante"] == 1


def test_load_population_and_verify_t2_1_synthetic(tmp_path: Path) -> None:
    parquet_dir = tmp_path / "data" / "parquet"
    parquet_dir.mkdir(parents=True)

    rows_2022 = [
        _make_row(CLASSI_FIN="10", EVOLUCAO="1"),  # válido, y=0
        _make_row(CLASSI_FIN="12", EVOLUCAO="9"),  # válido (grave), y=1
        _make_row(CLASSI_FIN="8", EVOLUCAO="1"),   # excluído no filtro 2
    ]
    rows_2023 = [
        _make_row(
            CLASSI_FIN="10",
            EVOLUCAO="2",
            DT_SIN_PRI="20230301",
            DT_NOTIFIC="20230302",
        ),  # válido, y=1
    ]
    pq.write_table(pa.Table.from_pylist(rows_2022), parquet_dir / "dengue_2022.parquet")
    pq.write_table(pa.Table.from_pylist(rows_2023), parquet_dir / "dengue_2023.parquet")

    cfg = {
        "anos_dev": [2022, 2023],
        "ano_teste": 2024,
        "caminhos": {
            "dados": str(tmp_path / "data"),
            "relatorios": str(tmp_path / "reports"),
        },
    }

    pop = load_population(cfg, [2022, 2023])
    assert len(pop) == 3
    assert int(pop["y"].sum()) == 2
    assert (tmp_path / "reports" / "fluxograma.md").is_file()

    expected_synthetic = {
        "casos_dev": 3,
        "eventos_dev": 2,
        "populacao_por_ano": {2022: 2, 2023: 1},
        "eventos_por_ano": {2022: 1, 2023: 1},
        "fluxograma_exclusao": {
            2022: {
                "1. Total baixado": 3,
                "2. CLASSI_FIN ∈ {10, 11, 12}": 2,
                "3. Rótulo conhecido (12, ou 10/11 com EVOLUCAO ∈ {1, 2})": 2,
                "4. Idade válida (0–120 anos)": 2,
            },
            2023: {
                "1. Total baixado": 1,
                "2. CLASSI_FIN ∈ {10, 11, 12}": 1,
                "3. Rótulo conhecido (12, ou 10/11 com EVOLUCAO ∈ {1, 2})": 1,
                "4. Idade válida (0–120 anos)": 1,
            },
        },
    }
    exp_file = tmp_path / "esperado_sintetico.yaml"
    exp_file.write_text(yaml.safe_dump(expected_synthetic), encoding="utf-8")

    report_path = verify_t2_1(cfg, expected_path=exp_file)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["passou"] is True


def test_training_loader_and_feature_builder_reject_test_year_2024(tmp_path: Path) -> None:
    cfg = {
        "anos_dev": [2022, 2023],
        "ano_teste": 2024,
        "caminhos": {"dados": str(tmp_path), "relatorios": str(tmp_path / "reports")},
    }
    with pytest.raises(RuntimeError, match=r"2024 é teste congelado \(R1\)"):
        load_dev_population(cfg, [2022, 2024])

    df_2024 = pd.DataFrame([_make_row()]).assign(ANO=2024)
    with pytest.raises(RuntimeError, match=r"2024 é teste congelado \(R1\)"):
        build_feature_frame(df_2024)
