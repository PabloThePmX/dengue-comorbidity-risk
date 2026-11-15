import pandas as pd
import pyarrow as pa

from dengue_sinan.dataset import FEATURE_COLUMNS, build_feature_frame, load_population
from dengue_sinan.profiling import COMORBIDADES, SINAIS, add_derived


def _raw_frame(rows=20):
    data = {column: ["2"] * rows for column in COMORBIDADES + SINAIS}
    data.update(
        {
            "CLASSI_FIN": ["10"] * rows,
            "EVOLUCAO": ["1"] * rows,
            "NU_IDADE_N": ["4018"] * rows,
            "ANO_NASC": ["2004"] * rows,
            "DT_SIN_PRI": ["20220101"] * rows,
            "DT_NOTIFIC": ["20220102"] * rows,
            "CS_SEXO": ["F"] * rows,
            "CS_GESTANT": ["5"] * rows,
            "CS_RACA": ["1"] * rows,
            "ID_MN_RESI": ["355030"] * rows,
            "SG_UF": ["35"] * rows,
        }
    )
    return pd.DataFrame(data)


def test_build_feature_frame_levels_counts_and_clips_days():
    raw = _raw_frame(4)
    raw.loc[0, "DIABETES"] = "1"
    raw.loc[1, "DIABETES"] = "9"
    raw.loc[2, "DIABETES"] = "2"
    raw.loc[0, "DT_NOTIFIC"] = "20220315"
    raw.loc[1, "DT_NOTIFIC"] = "20211231"
    raw = add_derived(raw)

    features = build_feature_frame(raw)
    assert features.columns.tolist() == FEATURE_COLUMNS
    assert features["diabetes"].tolist() == ["Sim", "Ausente", "Não", "Não"]
    assert features["n_comorbidades"].tolist() == [1, 0, 0, 0]
    assert features["dias_ate_notificacao"].iloc[0] == 60
    assert features["dias_ate_notificacao"].iloc[1] == 0


def test_load_population_reads_only_requested_year_and_writes_aggregated_flow(
    tmp_path, monkeypatch
):
    raw = _raw_frame()
    expected_columns = raw.columns.tolist()
    calls = []

    def fake_read_table(path, columns):
        calls.append((path, columns))
        return pa.Table.from_pandas(raw[columns], preserve_index=False)

    monkeypatch.setattr("dengue_sinan.dataset.pq.read_table", fake_read_table)
    config = {
        "caminhos": {"dados": str(tmp_path), "relatorios": str(tmp_path / "reports")}
    }

    population = load_population(config, [2022])

    assert len(population) == len(raw)
    assert population["y"].sum() == 0
    assert calls[0][0] == tmp_path / "parquet" / "dengue_2022.parquet"
    assert set(calls[0][1]) == set(expected_columns)
    flow = (tmp_path / "reports" / "fluxograma.md").read_text(encoding="utf-8")
    assert "Contagens agregadas por ano" in flow
    assert "2024" not in flow