"""Download dos microdados SINAN-Dengue direto do FTP do DataSUS (D-05)."""

import datetime as dt
import ftplib
import hashlib
import json
import platform
import tempfile
from importlib import metadata
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
import pyreaddbc
from dbfread import DBF

FTP_HOST = "ftp.datasus.gov.br"
# Ordem de busca: arquivo final primeiro; preliminar só se o final não existir.
FTP_DIRS = {
    "final": "/dissemin/publicos/SINAN/DADOS/FINAIS",
    "preliminar": "/dissemin/publicos/SINAN/DADOS/PRELIM",
}
DBF_ENCODING = "iso-8859-1"
CHUNK_ROWS = 200_000


def remote_name(year: int) -> str:
    """Nome do arquivo anual de dengue no FTP (ex.: 2022 → DENGBR22.dbc)."""
    return f"DENGBR{year % 100:02d}.dbc"


def sha256_file(path: Path, block_size: int = 1 << 20) -> str:
    """SHA-256 lendo o arquivo em blocos, sem carregá-lo inteiro na memória."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(block_size):
            digest.update(block)
    return digest.hexdigest()


def _locate(ftp: ftplib.FTP, name: str) -> tuple[str, str, int, str]:
    """Acha o arquivo em FINAIS ou PRELIM; devolve (status, dir, tamanho, data de revisão)."""
    for status, directory in FTP_DIRS.items():
        try:
            size = ftp.size(f"{directory}/{name}")
        except ftplib.error_perm:
            continue
        mdtm = ftp.sendcmd(f"MDTM {directory}/{name}").split()[1]
        modified = dt.datetime.strptime(mdtm[:14], "%Y%m%d%H%M%S").replace(tzinfo=dt.UTC)
        return status, directory, size, modified.isoformat()
    raise FileNotFoundError(f"{name} não encontrado em {list(FTP_DIRS.values())}")


def download_dbc(year: int, dest_dir: Path) -> dict:
    """Baixa o .dbc de um ano e devolve os metadados de procedência."""
    name = remote_name(year)
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / name
    with ftplib.FTP(FTP_HOST, timeout=120) as ftp:
        ftp.login()
        ftp.voidcmd("TYPE I")
        status, directory, size, modified = _locate(ftp, name)
        if not (target.exists() and target.stat().st_size == size):
            partial = target.with_suffix(".part")
            with open(partial, "wb") as f:
                ftp.retrbinary(f"RETR {directory}/{name}", f.write, blocksize=1 << 20)
            partial.replace(target)
    if target.stat().st_size != size:
        raise OSError(f"{name}: tamanho local {target.stat().st_size} ≠ remoto {size}")
    return {
        "ano": year,
        "arquivo": name,
        "url": f"ftp://{FTP_HOST}{directory}/{name}",
        "status_datasus": status,
        "revisao_datasus_utc": modified,
        "baixado_em_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "tamanho_dbc_bytes": size,
        "sha256_dbc": sha256_file(target),
    }


def _column_to_arrow(raw: np.ndarray, length: int) -> pa.Array:
    """Bytes de largura fixa → texto sem espaços nas pontas; vazio vira nulo.

    Caminho rápido para colunas só ASCII (quase todas no SINAN): os bytes viram um array Arrow
    sem cópia, e ASCII é UTF-8 válido. Com algum byte ≥ 0x80, decodifica latin-1 em Python.
    """
    raw = np.ascontiguousarray(raw)
    if (raw.view(np.uint8) < 0x80).all():
        fixed = pa.FixedSizeBinaryArray.from_buffers(
            pa.binary(length), len(raw), [None, pa.py_buffer(raw.view(np.uint8))])
        text = pc.utf8_trim_whitespace(pc.cast(pc.cast(fixed, pa.binary()), pa.string()))
    else:
        text = pa.array([v.decode(DBF_ENCODING).strip() for v in raw.tolist()], type=pa.string())
    return pc.if_else(pc.equal(text, ""), pa.scalar(None, pa.string()), text)


def iter_dbf_tables(dbf_path: Path, chunk_rows: int = CHUNK_ROWS):
    """Lê o DBF em blocos de registros de tamanho fixo (numpy), como tabelas Arrow de texto.

    Equivalente a `dbfread.DBF(raw=True)` (pula registros apagados), mas vetorizado: o
    `dbfread` monta um dict por registro em Python e leva ~6 min só para 2022. Saída conferida
    célula a célula contra o `dbfread` no arquivo de 2022 (1,4 mi linhas × 121 colunas).
    """
    table = DBF(str(dbf_path), raw=True, encoding=DBF_ENCODING)
    header = table.header
    fields = [(f.name, f.length) for f in table.fields]
    dtype = np.dtype([("_deleted", "S1")] + [(name, f"S{length}") for name, length in fields])
    if dtype.itemsize != header.recordlen:
        raise ValueError(f"registro de {header.recordlen} bytes, campos somam {dtype.itemsize}")
    with open(dbf_path, "rb") as f:
        f.seek(header.headerlen)
        remaining = header.numrecords
        while remaining > 0:
            block = np.fromfile(f, dtype=dtype, count=min(chunk_rows, remaining))
            if len(block) == 0:
                raise OSError(f"DBF terminou antes do esperado: faltam {remaining} registros")
            remaining -= len(block)
            block = block[block["_deleted"] != b"*"]
            yield pa.table({name: _column_to_arrow(block[name], length) for name, length in fields})


def dbc_to_parquet(dbc_path: Path, parquet_path: Path, chunk_rows: int = CHUNK_ROWS) -> dict:
    """Converte .dbc → Parquet, todas as colunas como texto (valores crus, sem reinterpretação).

    Grava em blocos, para caber na RAM do Colab mesmo com 2024.
    """
    with tempfile.TemporaryDirectory() as tmp:
        dbf_path = Path(tmp) / dbc_path.with_suffix(".dbf").name
        pyreaddbc.dbc2dbf(str(dbc_path), str(dbf_path))
        header_rows = DBF(str(dbf_path), raw=True).header.numrecords
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        rows, writer = 0, None
        try:
            for chunk in iter_dbf_tables(dbf_path, chunk_rows):
                if writer is None:
                    writer = pq.ParquetWriter(parquet_path, chunk.schema, compression="zstd")
                    fields = chunk.schema.names
                writer.write_table(chunk)
                rows += chunk.num_rows
        finally:
            if writer is not None:
                writer.close()
    return {
        "linhas": rows,
        "linhas_no_cabecalho_dbf": header_rows,
        "colunas": len(fields),
        "nomes_colunas": fields,
        "sha256_parquet": sha256_file(parquet_path),
    }


def environment_info() -> dict:
    """Versões que entram no manifesto (NFR-02)."""
    packages = ["pyreaddbc", "dbfread", "pyarrow", "pandas"]
    return {
        "python": platform.python_version(),
        **{pkg: metadata.version(pkg) for pkg in packages},
    }


def fetch_year(year: int, data_dir: Path) -> dict:
    """Baixa, converte e registra um ano. Reaproveita o Parquet se o .dbc não mudou."""
    raw_dir, parquet_dir = data_dir / "raw", data_dir / "parquet"
    manifest_path = data_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text("utf-8")) if manifest_path.exists() else {}

    entry = download_dbc(year, raw_dir)
    parquet_path = parquet_dir / f"dengue_{year}.parquet"
    previous = manifest.get(str(year), {})
    reusable = (
        parquet_path.exists()
        and previous.get("sha256_dbc") == entry["sha256_dbc"]
        and previous.get("sha256_parquet") == sha256_file(parquet_path)
    )
    if reusable:
        entry.update({k: previous[k] for k in ("linhas", "linhas_no_cabecalho_dbf", "colunas",
                                               "nomes_colunas", "sha256_parquet")})
    else:
        entry.update(dbc_to_parquet(raw_dir / entry["arquivo"], parquet_path))
    entry["parquet"] = parquet_path.relative_to(data_dir).as_posix()
    entry["ambiente"] = environment_info()

    manifest[str(year)] = entry
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), "utf-8")
    return entry
