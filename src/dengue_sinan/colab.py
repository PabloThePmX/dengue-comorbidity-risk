"""Utilitários de preparação de ambiente, pastas do Drive e empacotamento no Google Colab."""

import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

from dengue_sinan.config import load_config
from dengue_sinan.download import fetch_year
from dengue_sinan.tracking import hardware_info
from dengue_sinan.verify import _git_commit


def prepare_colab_project(
    *,
    config_path: str | Path = "config/base.yaml",
    drive_root: str | Path | None = None,
    anos_necessarios: tuple[int, ...] = (2022, 2023),
    auto_download: bool = True,
) -> dict[str, Any]:
    """Configura diretórios do projeto no Google Drive (ou raiz local) e verifica os Parquets."""
    cfg = load_config(config_path)

    in_colab = "google.colab" in sys.modules
    if drive_root is not None:
        root = Path(drive_root)
    elif in_colab:
        from google.colab import drive  # type: ignore[import-not-found]

        drive.mount("/content/drive")
        root = Path("/content/drive/MyDrive/dengue-comorbidity-risk")
    else:
        root = Path(".").resolve()

    caminhos = {
        "dados": str(root / "data"),
        "m1": str(root / "m1"),
        "modelos": str(root / "models"),
        "mlruns": str(root / "mlruns"),
        "optuna": str(root / "optuna"),
        "relatorios": str(root / "reports"),
    }
    cfg["caminhos"] = caminhos

    for p_str in caminhos.values():
        Path(p_str).mkdir(parents=True, exist_ok=True)
    (Path(caminhos["relatorios"]) / "verificacao").mkdir(parents=True, exist_ok=True)
    (Path(caminhos["dados"]) / "parquet").mkdir(parents=True, exist_ok=True)

    data_dir = Path(caminhos["dados"])
    for ano in anos_necessarios:
        pq_file = data_dir / "parquet" / f"dengue_{int(ano)}.parquet"
        if not pq_file.is_file() and auto_download:
            print(f"[Colab Setup] Baixando e convertendo SINAN {ano} para {pq_file}...")
            fetch_year(int(ano), data_dir)

    hw = hardware_info()
    commit = _git_commit()
    print(
        f"[Ambiente pronto] commit={commit[:7]} | gpu={hw.get('hardware.gpu', 'CPU')} | "
        f"vCPUs={hw.get('hardware.vcpus', '1')} | "
        f"RAM={hw.get('hardware.ram_gib', '0')} GiB | raiz={root}"
    )
    return cfg


def sync_and_package_reports(
    cfg: dict[str, Any],
    *,
    local_reports_dir: str | Path = "reports",
    zip_path: str | Path = "reports_colab_verificacao.zip",
) -> Path:
    """Sincroniza relatórios do Drive para `reports/` local e gera um `.zip` para download."""
    drive_reports = Path(cfg.get("caminhos", {}).get("relatorios", "reports")).resolve()
    local_rep = Path(local_reports_dir).resolve()
    local_rep.mkdir(parents=True, exist_ok=True)

    if drive_reports != local_rep and drive_reports.is_dir():
        for src_file in drive_reports.rglob("*"):
            if src_file.is_file():
                rel = src_file.relative_to(drive_reports)
                dest = local_rep / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest)

    target_zip = Path(zip_path).resolve()
    source_root = drive_reports if drive_reports.is_dir() else local_rep
    with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(source_root.rglob("*")):
            if file_path.is_file():
                arcname = Path("reports") / file_path.relative_to(source_root)
                zf.write(file_path, arcname.as_posix())

    return target_zip
