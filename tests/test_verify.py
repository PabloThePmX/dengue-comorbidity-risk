"""Testes do módulo de verificação automatizada (T-2.0, D-56, D-57)."""

import json
from pathlib import Path

import pandas as pd
import pytest

from dengue_sinan.verify import check, update_session_report, write_report


def test_check_pass_and_fail() -> None:
    c_pass = check("casos_dev", 2453208, 2453208)
    assert c_pass == {
        "nome": "casos_dev",
        "esperado": 2453208,
        "obtido": 2453208,
        "tolerancia": 0,
        "passou": True,
    }

    c_fail = check("eventos_dev", 3985, 3900)
    assert c_fail["passou"] is False

    c_tol = check("pr_auc", 0.015, 0.0154, tolerancia=0.001)
    assert c_tol["passou"] is True


def test_write_report_roundtrip(tmp_path: Path) -> None:
    checks = [
        check("casos_dev", 2453208, 2453208),
        check("eventos_dev", 3985, 3985),
    ]
    out_file = write_report("T-2.1", checks, tmp_path)
    assert out_file == tmp_path / "T-2.1.json"

    loaded = json.loads(out_file.read_text(encoding="utf-8"))
    assert loaded["tarefa"] == "T-2.1"
    assert loaded["checks"] == checks
    assert loaded["passou"] is True


@pytest.mark.parametrize(
    "bad_value",
    [
        [1, 2, 3],
        {"a": 1},
        pd.DataFrame({"x": [1, 2]}),
        pd.Series([1, 2]),
    ],
)
def test_check_rejects_non_scalar_obtido(bad_value: object) -> None:
    with pytest.raises(TypeError, match="só agregados"):
        check("invalido", 10, bad_value)


def test_update_session_report_preserves_other_blocks(tmp_path: Path) -> None:
    session_file = tmp_path / "sessao-m1.json"

    update_session_report(
        session_file,
        "checagem_inicial",
        [check("gpu_ok", True, True)],
        sessao_completa=False,
    )
    first_read = json.loads(session_file.read_text(encoding="utf-8"))
    assert len(first_read["blocos"]) == 1
    assert first_read["blocos"][0]["bloco"] == "checagem_inicial"
    assert first_read["blocos"][0]["passou"] is True
    assert first_read["passou"] is False  # sessao_completa ainda False

    update_session_report(
        session_file,
        "elastic_net",
        [check("linhas_oof", 2453208, 2453208)],
        sessao_completa=True,
    )
    second_read = json.loads(session_file.read_text(encoding="utf-8"))
    assert [b["bloco"] for b in second_read["blocos"]] == ["checagem_inicial", "elastic_net"]
    assert second_read["passou"] is True

    # Reescrever o 1º bloco com falha preserva o 2º e atualiza o "passou" geral para False
    update_session_report(
        session_file,
        "checagem_inicial",
        [check("gpu_ok", True, False)],
    )
    third_read = json.loads(session_file.read_text(encoding="utf-8"))
    assert [b["bloco"] for b in third_read["blocos"]] == ["checagem_inicial", "elastic_net"]
    assert third_read["blocos"][0]["passou"] is False
    assert third_read["blocos"][1]["passou"] is True
    assert third_read["passou"] is False
