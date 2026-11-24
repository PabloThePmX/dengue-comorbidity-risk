"""R7 e NFR-03 (T-6.4): nenhum microdado vai para o git.

Lê `git ls-files` (o que de fato vai para o repositório) e aplica as regras de `motivo_de_bloqueio`.
É uma rede de segurança barata contra os erros prováveis (um parquet, um CSV com linhas de pessoas,
uma pasta data/ commitada). Não prova a ausência de microdados: .gitignore e revisão continuam
necessários.
"""

import subprocess
from pathlib import Path, PurePosixPath

import pytest

RAIZ = Path(__file__).resolve().parents[1]

# Extensões de dado ou de contêiner: nenhuma pode ser rastreada.
EXTENSOES_PROIBIDAS = {
    ".parquet", ".parq", ".feather", ".arrow",          # colunares: formato típico de microdado
    ".dbc", ".dbf", ".db", ".sqlite", ".sqlite3",       # DATASUS e bancos locais
    ".pkl", ".pickle", ".joblib", ".sav", ".dta",       # objetos Python e de outros softwares
    ".h5", ".hdf5", ".npy", ".npz",                     # arrays (npz só pela exceção abaixo)
    ".xlsx", ".xls", ".ods",                            # planilhas
    ".zip", ".gz", ".7z", ".rar", ".tar", ".xz", ".bz2",  # pacotes que podem esconder dados
}

# Exceções por caminho exato, cada uma com o motivo verificado.
EXCECOES_NPZ = {
    "models/e1/payload/e1.npz": (
        "coeficientes e covariância do E1 (params (44,), cov (44, 44); conferido com np.load em "
        "2026-11-23): nenhuma linha de pessoa"),
}

PASTAS_PROIBIDAS = {"data", "dados", "microdados", "raw"}
LIMITE_BYTES = 1_000_000          # maior arquivo rastreado hoje: relatorio.docx, ~487 KB
LIMITE_CSV_LINHAS = 1_000         # CSVs de reports/ têm de 3 a 51 linhas; microdados, milhares
LIMITE_CSV_BYTES = 50_000         # os maiores CSVs de reports/ têm ~12 KB


def motivo_de_bloqueio(caminho: str, tamanho: int, linhas: int | None) -> str | None:
    """Motivo para bloquear o arquivo rastreado, ou None se passa. `linhas` vale só para CSV."""
    p = PurePosixPath(caminho)
    if PASTAS_PROIBIDAS & set(p.parts[:-1]):
        return "pasta de dados rastreada"
    extensao = p.suffix.lower()
    if caminho in EXCECOES_NPZ:
        extensao = ""  # a exceção vale para o npz citado; o tamanho continua valendo
    if extensao in EXTENSOES_PROIBIDAS:
        return f"extensão de dado ({extensao})"
    if extensao == ".csv":
        if p.parts[0] != "reports":
            return "CSV fora de reports/ (só agregados em reports/ são permitidos)"
        if linhas is not None and linhas > LIMITE_CSV_LINHAS:
            return f"CSV com {linhas} linhas (limite de agregado: {LIMITE_CSV_LINHAS})"
        if tamanho > LIMITE_CSV_BYTES:
            return f"CSV com {tamanho} bytes (limite de agregado: {LIMITE_CSV_BYTES})"
    if tamanho > LIMITE_BYTES:
        return f"arquivo com {tamanho} bytes (limite: {LIMITE_BYTES})"
    return None


def _rastreados() -> list[str]:
    try:
        saida = subprocess.run(["git", "ls-files", "-z"], cwd=RAIZ, capture_output=True,
                               check=True, timeout=60)
    except (OSError, subprocess.SubprocessError) as erro:
        pytest.skip(f"git indisponível nesta cópia do projeto: {erro}")
    return [c for c in saida.stdout.decode("utf-8").split("\0") if c]


def test_nenhum_arquivo_rastreado_e_microdado():
    erros = []
    for caminho in _rastreados():
        arquivo = RAIZ / caminho
        if not arquivo.is_file():  # removido do disco e ainda no índice: não está no conteúdo
            continue
        linhas = None
        if arquivo.suffix.lower() == ".csv":
            linhas = arquivo.read_bytes().count(b"\n")
        motivo = motivo_de_bloqueio(caminho, arquivo.stat().st_size, linhas)
        if motivo:
            erros.append(f"{caminho}: {motivo}")
    assert not erros, "arquivos de dado rastreados pelo git (R7):\n" + "\n".join(erros)


def test_excecoes_apontam_para_arquivos_rastreados_de_verdade():
    rastreados = set(_rastreados())
    obsoletas = sorted(c for c in EXCECOES_NPZ if c not in rastreados)
    assert not obsoletas, f"exceções que não estão no git (remover da lista): {obsoletas}"


# --- O detector, testado com entradas sintéticas -----------------------------------------------

@pytest.mark.parametrize(("caminho", "tamanho", "linhas", "motivo_esperado"), [
    ("reports/teste/metricas.json", 124_940, None, None),
    ("reports/teste/subgrupos__subgrupos.csv", 11_883, 24, None),
    ("models/e1/payload/e1.npz", 20_000, None, None),
    ("models/e1/payload/outro.npz", 20_000, None, "extensão de dado"),
    ("data/sinan_2023.parquet", 10, None, "pasta de dados"),
    ("dados/microdados.csv", 10, 3, "pasta de dados"),
    ("src/dengue_sinan/extra.parquet", 10, None, "extensão de dado"),
    ("models/m1_final/payload/booster.joblib", 10, None, "extensão de dado"),
    ("reports/teste/linhas.dbf", 10, None, "extensão de dado"),
    ("reports/teste/microdados.csv", 900_000, 900_000, "CSV com"),
    ("reports/teste/pesado.csv", 60_000, 10, "bytes"),
    ("src/dengue_sinan/tabela.csv", 100, 3, "fora de reports/"),
    ("reports/gigante.docx", 2_000_000, None, "arquivo com"),
])
def test_detector_bloqueia_so_o_que_deve(caminho, tamanho, linhas, motivo_esperado):
    motivo = motivo_de_bloqueio(caminho, tamanho, linhas)
    if motivo_esperado is None:
        assert motivo is None, motivo
    else:
        assert motivo is not None and motivo_esperado in motivo, motivo
