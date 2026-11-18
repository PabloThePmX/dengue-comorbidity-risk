"""Gravação e leitura de artefatos de modelo, com metadados e hashes.

Layout de `artefatos/modelos/<nome>-<versao>/`:
    modelo.joblib        motor treinado + calibrador (sem dados de treino)
    metadados.json       identificação, parâmetros, variáveis, ambiente, dados, hashes
    contrato.json        o que a inferência aceita e devolve
    avaliacao_dev.json   métricas de desenvolvimento (validação cruzada por região)

Nunca sobrescreve um artefato existente e recusa gravar em `reports/modelo_risco_dengue/`,
onde estão os artefatos históricos da v1.
"""

import hashlib
import json
from pathlib import Path

import joblib

from dengue_sinan.pipeline.contrato import RAIZ

ARQUIVOS = ("modelo.joblib", "contrato.json", "avaliacao_dev.json")
HISTORICO = (RAIZ / "reports" / "modelo_risco_dengue").resolve()


class ArtefatoInvalido(RuntimeError):
    """Artefato ausente, incompleto ou com hash diferente do registrado."""


def sha256_arquivo(caminho: Path, bloco: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        while pedaco := f.read(bloco):
            h.update(pedaco)
    return h.hexdigest()


def _escrever_json(obj, caminho: Path) -> None:
    caminho.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True, default=str) + "\n", "utf-8"
    )


def identificador(nome: str, versao: str) -> str:
    return f"{nome}-{versao}"


def salvar(
    pasta_base: Path,
    nome: str,
    versao: str,
    objeto,
    metadados: dict,
    contrato: dict,
    avaliacao: dict,
) -> Path:
    destino = (Path(pasta_base) / identificador(nome, versao)).resolve()
    if destino == HISTORICO or HISTORICO in destino.parents:
        raise PermissionError(f"recusado: {destino} está na área dos artefatos históricos da v1")
    if destino.exists():
        raise FileExistsError(
            f"{destino} já existe. Artefatos não são sobrescritos: mude `versao_modelo`."
        )
    destino.mkdir(parents=True)
    joblib.dump(objeto, destino / "modelo.joblib")
    _escrever_json(contrato, destino / "contrato.json")
    _escrever_json(avaliacao, destino / "avaliacao_dev.json")
    meta = dict(metadados)
    meta["identificador"] = identificador(nome, versao)
    meta["hashes_sha256"] = {a: sha256_arquivo(destino / a) for a in ARQUIVOS}
    _escrever_json(meta, destino / "metadados.json")
    return destino


def verificar(pasta: Path) -> dict:
    """Confere a presença e os hashes dos arquivos. Devolve os metadados."""
    pasta = Path(pasta)
    caminho_meta = pasta / "metadados.json"
    if not caminho_meta.is_file():
        raise ArtefatoInvalido(f"{caminho_meta} não existe")
    meta = json.loads(caminho_meta.read_text("utf-8"))
    for arquivo, esperado in meta.get("hashes_sha256", {}).items():
        caminho = pasta / arquivo
        if not caminho.is_file():
            raise ArtefatoInvalido(f"arquivo ausente no artefato: {arquivo}")
        if sha256_arquivo(caminho) != esperado:
            raise ArtefatoInvalido(f"hash diferente do registrado: {arquivo}")
    faltam = [a for a in ARQUIVOS if a not in meta.get("hashes_sha256", {})]
    if faltam:
        raise ArtefatoInvalido(f"metadados sem hash para: {faltam}")
    return meta


def carregar(pasta: Path) -> tuple[object, dict, dict]:
    """Verifica os hashes e carrega (objeto, metadados, contrato).

    O hash detecta corrupção e troca acidental. Não protege contra quem altera arquivo e
    metadados juntos: `joblib` executa código ao carregar, então só carregue artefatos de
    origem confiável.
    """
    meta = verificar(pasta)
    objeto = joblib.load(Path(pasta) / "modelo.joblib")
    contrato = json.loads((Path(pasta) / "contrato.json").read_text("utf-8"))
    return objeto, meta, contrato
