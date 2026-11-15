"""Testes unitários dos utilitários de ambiente e empacotamento do Colab."""

import zipfile
from pathlib import Path

from dengue_sinan.colab import prepare_colab_project, sync_and_package_reports


def test_prepare_colab_project_and_package_reports(tmp_path: Path) -> None:
    drive_root = tmp_path / "drive_project"
    cfg = prepare_colab_project(
        drive_root=drive_root,
        anos_necessarios=(2022, 2023),
        auto_download=False,
    )
    assert Path(cfg["caminhos"]["dados"]) == drive_root / "data"
    assert (drive_root / "reports" / "verificacao").is_dir()
    assert (drive_root / "models").is_dir()
    assert (drive_root / "optuna").is_dir()

    verif_file = drive_root / "reports" / "verificacao" / "T-2.1.json"
    verif_file.write_text('{"tarefa": "T-2.1", "passou": true}\n', encoding="utf-8")

    local_rep = tmp_path / "local_reports"
    zip_out = tmp_path / "out.zip"
    res_zip = sync_and_package_reports(cfg, local_reports_dir=local_rep, zip_path=zip_out)

    assert res_zip.is_file()
    assert (local_rep / "verificacao" / "T-2.1.json").is_file()
    with zipfile.ZipFile(res_zip, "r") as zf:
        assert "reports/verificacao/T-2.1.json" in zf.namelist()
