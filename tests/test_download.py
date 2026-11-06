import struct
from pathlib import Path

import pytest
from dbfread import DBF

from dengue_sinan.download import iter_dbf_tables, remote_name, sha256_file

FIELDS = [("CLASSI_FIN", 2), ("NOME_MUN", 8), ("NU_IDADE_N", 4)]
RECORDS = [
    (b" ", ["10", "São José", "4018"]),
    (b"*", ["12", "Apagado", "4050"]),  # registro apagado: deve sumir
    (b" ", ["", "  Itu", "3009"]),  # vazio e espaço à esquerda
    (b" ", ["5", "", ""]),
]


def write_dbf(path: Path) -> None:
    """dBase III mínimo: cabeçalho, descritores de campo, registros e marcador de fim."""
    record_len = 1 + sum(length for _, length in FIELDS)
    header_len = 32 + 32 * len(FIELDS) + 1
    header = struct.pack("<B3BIHH20x", 0x03, 126, 11, 2, len(RECORDS), header_len, record_len)
    descriptors = b"".join(
        name.encode("ascii").ljust(11, b"\0") + b"C" + b"\0" * 4 + bytes([length, 0]) + b"\0" * 14
        for name, length in FIELDS
    )
    body = b"".join(
        flag + b"".join(v.encode("iso-8859-1").ljust(length)
                        for v, (_, length) in zip(values, FIELDS, strict=True))
        for flag, values in RECORDS
    )
    path.write_bytes(header + descriptors + b"\r" + body + b"\x1a")


@pytest.fixture
def dbf_path(tmp_path: Path) -> Path:
    path = tmp_path / "mini.dbf"
    write_dbf(path)
    return path


def test_reader_matches_dbfread(dbf_path):
    expected = [
        {k: (v.decode("iso-8859-1").strip() or None) for k, v in record.items()}
        for record in DBF(str(dbf_path), raw=True)
    ]
    rows = [row for table in iter_dbf_tables(dbf_path, chunk_rows=2) for row in table.to_pylist()]
    assert rows == expected


def test_reader_skips_deleted_and_handles_blanks(dbf_path):
    rows = [row for table in iter_dbf_tables(dbf_path) for row in table.to_pylist()]
    assert [r["CLASSI_FIN"] for r in rows] == ["10", None, "5"]
    assert rows[0]["NOME_MUN"] == "São José"
    assert rows[1]["NOME_MUN"] == "Itu"
    assert rows[2]["NU_IDADE_N"] is None


def test_remote_name_uses_two_digit_year():
    assert remote_name(2022) == "DENGBR22.dbc"
    assert remote_name(2005) == "DENGBR05.dbc"


def test_sha256_file_known_value(tmp_path):
    path = tmp_path / "x.txt"
    path.write_bytes(b"abc")
    assert sha256_file(path) == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    )
