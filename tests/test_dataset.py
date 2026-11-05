import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from dengue_sinan.checks import REQUIRED_COLUMNS
from dengue_sinan.dataset import build_feature_frame, load_population


def _raw_record(**overrides):
    row = {column: "2" for column in REQUIRED_COLUMNS}
    row.update({
        "CLASSI_FIN": "10",
        "EVOLUCAO": "1",
        "NU_IDADE_N": "4030",
        "ANO_NASC": "1992",
        "DT_SIN_PRI": "20220110",
        "DT_NOTIFIC": "20220112",
        "CS_SEXO": "F",
        "CS_GESTANT": "6",
        "CS_RACA": "1",
        "ID_MN_RESI": "355030",
        "SG_UF": "35",
        "DIABETES": "1",
        "HEMATOLOG": "9",
        "PETEQUIA_N": "1",
        "LACO": "1",
        "LACO_N": "1",
        "PETEQUIAS": "1",
    })
    row.update(overrides)
    return row


def test_build_feature_frame_maps_categories_counts_comorbidities_and_caps_delay():
    frame = pd.DataFrame([
        _raw_record(DT_SIN_PRI="20220110", DT_NOTIFIC="20220401"),
        _raw_record(CS_SEXO="X", CS_GESTANT="1", DT_SIN_PRI="20220110",
                    DT_NOTIFIC="20220105", DIABETES="2", RENAL="1"),
    ])
    from dengue_sinan.profiling import add_derived

    features = build_feature_frame(add_derived(frame))
    assert features.loc[0, "DIABETES"] == "Sim"
    assert features.loc[0, "HEMATOLOG"] == "Ausente"
    assert features.loc[0, "n_comorbidades"] == 1
    assert features.loc[0, "dias_ate_notificacao"] == 60
    assert features.loc[1, "sexo"] == "I"
    assert features.loc[1, "gestante"] == 1
    assert features.loc[1, "dias_ate_notificacao"] == 0
    assert {"LACO", "PETEQUIA_N"} <= set(features.columns)
    assert not {"LACO_N", "PETEQUIAS"} & set(features.columns)


def test_load_population_reads_only_requested_year_and_writes_aggregate_flow(tmp_path):
    source = tmp_path / "parquet"
    source.mkdir()
    rows = [_raw_record(), _raw_record(CLASSI_FIN="8")]
    pq.write_table(pa.Table.from_pylist(rows), source / "dengue_2022.parquet")
    cfg = {"caminhos": {"dados": str(tmp_path), "relatorios": str(tmp_path / "reports")}}

    population = load_population(cfg, [2022])

    assert len(population) == 1
    assert population.loc[0, "y"] == 0
    assert population.loc[0, "regiao"] == "Sudeste"
    assert (tmp_path / "reports" / "fluxograma.md").is_file()
    assert not (source / "dengue_2024.parquet").exists()
