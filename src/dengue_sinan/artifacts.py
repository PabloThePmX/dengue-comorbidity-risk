"""Artefatos serializados com metadados (FR-12, T-3.6).

Um artefato é uma PASTA:

    <caminho>/metadata.json   FR-12 e mais: versões, hashes, config, métricas, SHA-256 do payload
    <caminho>/payload/        os arquivos do modelo; o tipo do payload define quais são

O tipo E1 não usa pickle: `e1.npz` (coeficientes e covariância) e `e1.json` (colunas, nós,
pares, IDADE_REFERENCIA, graus de liberdade e features). A carga não importa statsmodels, então
a demo calcula o risco só com numpy e pandas.

Carregar recusa o artefato se o schema for de uma versão futura, se o tipo não estiver
registrado, se faltar ou sobrar arquivo no payload ou se algum SHA-256 não bater.

Ponto de extensão para o M1 (T-4.10): `registrar_tipo(Tipo(...))` com um codec próprio (por
exemplo, o joblib do Pipeline). O hash e as versões entram no metadata do mesmo jeito.

Privacidade (NFR-03, R7): o bundle não traz linhas nem contagens por termo. `gerar_bundle_e1`
lê o E1 de `data/e1/` (fora do git) e grava só parâmetros, covariância e totais.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import importlib.metadata as importlib_metadata
import json
import platform
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from dengue_sinan import verify

SCHEMA_VERSION = 1
NOME_METADATA = "metadata.json"
PASTA_PAYLOAD = "payload"
E1_NPZ = "e1.npz"
E1_JSON = "e1.json"
# Campos que o chamador tem de dar (FR-12). O save acrescenta versão, commit e bibliotecas.
CAMPOS_OBRIGATORIOS = ("config", "dados", "data_treino", "metricas_validacao", "features")
CAMPOS_RESERVADOS = ("schema_version", "tipo_payload", "criado_em_utc", "versao_codigo",
                     "bibliotecas", "payload")
BIBLIOTECAS = ("numpy", "pandas", "scipy", "statsmodels", "scikit-learn")
AVISO_E1 = ("sem validação externa: E1 é inferência (explicativo, sem dobras); calibração em "
            "2024 só na T-5")


class ArtefatoInvalido(ValueError):
    """Artefato que não pode ser carregado: schema futuro, tipo desconhecido, arquivo faltando
    ou SHA-256 que não bate."""


# --- Registro de tipos de payload --------------------------------------------------------------

@dataclass(frozen=True)
class Tipo:
    """Codec de um tipo de payload.

    `salvar(obj, pasta, metadados)` grava os arquivos em `pasta` e devolve os nomes gravados.
    `carregar(pasta)` devolve o objeto. `reconhece(obj)` diz se o codec serve ao objeto.
    """

    nome: str
    reconhece: Callable[[object], bool]
    salvar: Callable[[object, Path, dict], list[str]]
    carregar: Callable[[Path], object]


_TIPOS: dict[str, Tipo] = {}


def registrar_tipo(tipo: Tipo) -> None:
    """Registra um tipo de payload. Nome repetido levanta erro (não sobrescreve em silêncio)."""
    if tipo.nome in _TIPOS:
        raise ValueError(f"tipo de payload já registrado: {tipo.nome!r}")
    _TIPOS[tipo.nome] = tipo


def _tipo_do_objeto(obj: object) -> Tipo:
    for tipo in _TIPOS.values():
        if tipo.reconhece(obj):
            return tipo
    raise TypeError(f"objeto sem tipo de payload registrado: {type(obj).__name__}")


# --- E1 (tipo "e1") ----------------------------------------------------------------------------

ATRIBUTOS_E1 = ("params", "cov", "colunas", "nos", "pares_incluidos", "pares_excluidos",
                "idade_referencia")
NOS_E1 = ("idade", "idade_interacao")


@dataclass(frozen=True)
class E1Leve:
    """E1 para previsão e IC, sem statsmodels. Tem os atributos que `explain.risco_perfil`,
    `razao_de_risco` e `log_or_na_idade` leem de `E1Ajustado`."""

    params: np.ndarray
    cov: np.ndarray
    colunas: list[str]
    nos: dict[str, list[float]]
    pares_incluidos: list[tuple[str, str]]
    pares_excluidos: list[tuple[str, str]]
    idade_referencia: int
    features: list[str]


def _reconhece_e1(obj: object) -> bool:
    return all(hasattr(obj, atributo) for atributo in ATRIBUTOS_E1)


def _salvar_e1(obj: object, pasta: Path, metadados: dict) -> list[str]:
    params = np.asarray(obj.params, dtype=float)
    cov = np.asarray(obj.cov, dtype=float)
    colunas = [str(c) for c in obj.colunas]
    k = len(colunas)
    if params.shape != (k,) or cov.shape != (k, k):
        raise ValueError(f"E1 inconsistente: {k} colunas, params {params.shape}, "
                         f"cov {cov.shape}")
    nos = {nome: [float(x) for x in valores] for nome, valores in obj.nos.items()}
    if set(nos) != set(NOS_E1):
        raise ValueError(f"nós do E1 devem ser {NOS_E1}, recebi {sorted(nos)}")
    np.savez(pasta / E1_NPZ, params=params, cov=cov)
    _gravar_json(pasta / E1_JSON, {
        "colunas": colunas,
        "nos": nos,
        "pares_incluidos": [list(p) for p in obj.pares_incluidos],
        "pares_excluidos": [list(p) for p in obj.pares_excluidos],
        "idade_referencia": int(obj.idade_referencia),
        "graus_de_liberdade": {nome: len(v) - 1 for nome, v in nos.items()},
        "features": [str(f) for f in metadados["features"]],
    })
    return [E1_NPZ, E1_JSON]


def _carregar_e1(pasta: Path) -> E1Leve:
    with np.load(pasta / E1_NPZ, allow_pickle=False) as npz:
        params = np.array(npz["params"], dtype=float)
        cov = np.array(npz["cov"], dtype=float)
    descricao = json.loads((pasta / E1_JSON).read_text(encoding="utf-8"))
    colunas = list(descricao["colunas"])
    k = len(colunas)
    if params.shape != (k,) or cov.shape != (k, k):
        raise ArtefatoInvalido(f"E1: {k} colunas não batem com params {params.shape} e "
                               f"cov {cov.shape}")
    nos = {nome: [float(x) for x in valores] for nome, valores in descricao["nos"].items()}
    if set(nos) != set(NOS_E1):
        raise ArtefatoInvalido(f"E1: nós devem ser {NOS_E1}, recebi {sorted(nos)}")
    if {nome: len(v) - 1 for nome, v in nos.items()} != descricao["graus_de_liberdade"]:
        raise ArtefatoInvalido("E1: graus de liberdade não batem com os nós")
    return E1Leve(
        params=params,
        cov=cov,
        colunas=colunas,
        nos=nos,
        pares_incluidos=[tuple(p) for p in descricao["pares_incluidos"]],
        pares_excluidos=[tuple(p) for p in descricao["pares_excluidos"]],
        idade_referencia=int(descricao["idade_referencia"]),
        features=list(descricao["features"]),
    )


TIPO_E1 = Tipo(nome="e1", reconhece=_reconhece_e1, salvar=_salvar_e1, carregar=_carregar_e1)
registrar_tipo(TIPO_E1)


# --- Gravação e carga --------------------------------------------------------------------------

def _gravar_json(caminho: Path, conteudo: dict) -> None:
    texto = json.dumps(conteudo, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    caminho.write_text(texto, encoding="utf-8")


def _sha256(caminho: Path) -> str:
    digest = hashlib.sha256()
    with caminho.open("rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1 << 20), b""):
            digest.update(bloco)
    return digest.hexdigest()


def versoes_bibliotecas() -> dict[str, str | None]:
    """Versão do Python e das bibliotecas do modelo, lidas sem importá-las (None se ausentes)."""
    versoes: dict[str, str | None] = {"python": platform.python_version()}
    for nome in BIBLIOTECAS:
        try:
            versoes[nome] = importlib_metadata.version(nome)
        except importlib_metadata.PackageNotFoundError:
            versoes[nome] = None
    return versoes


def save_bundle(obj: object, caminho: str | Path, metadados: dict) -> Path:
    """Grava `obj` em `caminho/` (metadata.json + payload/). Devolve a pasta.

    `metadados` traz os campos de `CAMPOS_OBRIGATORIOS`. O save acrescenta `schema_version`,
    o commit (`verify.commit_atual`), o instante UTC, as versões das bibliotecas, o tipo do
    payload e o SHA-256 de cada arquivo do payload. Sobrescreve o payload anterior.
    """
    faltam = [campo for campo in CAMPOS_OBRIGATORIOS if campo not in metadados]
    if faltam:
        raise ValueError(f"metadados sem os campos obrigatórios (FR-12): {faltam}")
    reservados = [campo for campo in CAMPOS_RESERVADOS if campo in metadados]
    if reservados:
        raise ValueError(f"campos reservados ao save, não passe: {reservados}")
    tipo = _tipo_do_objeto(obj)

    pasta = Path(caminho)
    payload = pasta / PASTA_PAYLOAD
    if payload.exists():
        shutil.rmtree(payload)  # só a subpasta do payload: nada de arquivos fora dela
    payload.mkdir(parents=True)
    arquivos = tipo.salvar(obj, payload, metadados)
    if sorted(arquivos) != sorted(p.name for p in payload.iterdir()):
        raise ValueError("o codec gravou arquivos diferentes dos que declarou")

    _gravar_json(pasta / NOME_METADATA, {
        **metadados,
        "schema_version": SCHEMA_VERSION,
        "tipo_payload": tipo.nome,
        "criado_em_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "versao_codigo": {"commit": verify.commit_atual()},
        "bibliotecas": versoes_bibliotecas(),
        "payload": {nome: _sha256(payload / nome) for nome in sorted(arquivos)},
    })
    return pasta


def ler_metadados(caminho: str | Path) -> dict:
    """Lê o metadata.json e recusa schema ausente, inválido ou de uma versão futura."""
    arquivo = Path(caminho) / NOME_METADATA
    if not arquivo.exists():
        raise ArtefatoInvalido(f"sem {NOME_METADATA} em {caminho}")
    try:
        meta = json.loads(arquivo.read_text(encoding="utf-8"))
    except json.JSONDecodeError as erro:
        raise ArtefatoInvalido(f"{NOME_METADATA} não é JSON válido") from erro
    versao = meta.get("schema_version")
    if isinstance(versao, bool) or not isinstance(versao, int):
        raise ArtefatoInvalido("schema_version ausente ou inválido")
    if versao > SCHEMA_VERSION:
        raise ArtefatoInvalido(f"schema_version {versao} é de uma versão futura; este código lê "
                               f"até {SCHEMA_VERSION}")
    return meta


def load_bundle(caminho: str | Path) -> object:
    """Carrega o artefato. Recusa tipo desconhecido, payload com arquivo faltando ou sobrando e
    qualquer SHA-256 que não bata (o payload foi adulterado ou corrompido)."""
    pasta = Path(caminho)
    meta = ler_metadados(pasta)
    nome = meta.get("tipo_payload")
    if nome not in _TIPOS:
        raise ArtefatoInvalido(f"tipo de payload desconhecido: {nome!r}")
    declarados = meta.get("payload")
    if not isinstance(declarados, dict) or not declarados:
        raise ArtefatoInvalido("metadata sem o payload declarado")
    if any(Path(arquivo).name != arquivo for arquivo in declarados):
        raise ArtefatoInvalido("nome de arquivo do payload inválido")

    payload = pasta / PASTA_PAYLOAD
    presentes = (sorted(p.name for p in payload.iterdir() if p.is_file())
                 if payload.is_dir() else [])
    if presentes != sorted(declarados):
        raise ArtefatoInvalido(f"arquivos do payload {presentes} diferentes dos declarados "
                               f"{sorted(declarados)}")
    for arquivo, esperado in declarados.items():
        if _sha256(payload / arquivo) != esperado:
            raise ArtefatoInvalido(f"SHA-256 de {arquivo} não bate: artefato adulterado ou "
                                   "corrompido")
    return _TIPOS[nome].carregar(payload)


# --- Privacidade (NFR-03, R7) ------------------------------------------------------------------

# Inteiros de 1 a 9 que não são contagens: versão do schema, graus de liberdade das splines e,
# no M1 (T-4.10), nº de árvores ou épocas do retreino e os melhores pontos por dobra (são
# iterações do treino, não casos).
CAMINHOS_INTEIROS_PERMITIDOS = (("schema_version",), ("graus_de_liberdade", "idade"),
                                ("graus_de_liberdade", "idade_interacao"),
                                ("m1", "iteracoes_finais"), ("m1", "melhores_pontos"))


def inteiros_pequenos(valor: object, caminho: tuple = ()) -> list[tuple]:
    """Caminhos de inteiros de 1 a 9 em `valor`. Um inteiro desses pode ser uma contagem
    de 1–9 casos, que R7 proíbe publicar. Ignora `config` (seed, anos e faixas) e os campos
    estruturais de `CAMINHOS_INTEIROS_PERMITIDOS`."""
    achados: list[tuple] = []
    if isinstance(valor, dict):
        for chave, sub in valor.items():
            if chave != "config":
                achados += inteiros_pequenos(sub, (*caminho, chave))
    elif isinstance(valor, list):
        for sub in valor:
            achados += inteiros_pequenos(sub, caminho)
    elif isinstance(valor, int) and not isinstance(valor, bool) and 1 <= valor <= 9:
        achados.append(caminho)
    return [c for c in achados if c not in CAMINHOS_INTEIROS_PERMITIDOS]


# --- Geração do bundle real a partir de data/e1/ -----------------------------------------------

def hashes_dados(cfg: dict) -> dict:
    """SHA-256 do .dbc e do parquet de cada ano de desenvolvimento, do `data/manifest.json`."""
    manifesto = Path(cfg["caminhos"]["dados"]) / "manifest.json"
    registros = json.loads(manifesto.read_text(encoding="utf-8"))
    return {
        str(ano): {
            "sha256_dbc": registros[str(ano)]["sha256_dbc"],
            "sha256_parquet": registros[str(ano)]["sha256_parquet"],
        }
        for ano in cfg["anos_dev"]
    }


def metadados_e1(cfg: dict, e1: object) -> dict:
    """Campos FR-12 do E1. Só totais e parâmetros: nenhuma contagem por termo (R7)."""
    from dengue_sinan import explain  # local: o gerador lê o ajuste salvo pelo explain

    ajuste = Path(cfg["caminhos"]["dados"]) / "e1" / explain.NOME_METADADOS
    instante = dt.datetime.fromtimestamp(ajuste.stat().st_mtime, dt.UTC)
    return {
        "config": cfg,
        "dados": hashes_dados(cfg),
        "data_treino": instante.isoformat(timespec="seconds"),
        "metricas_validacao": {
            "aviso": AVISO_E1,
            "log_verossimilhanca": float(e1.log_verossimilhanca),
            "n_casos": int(e1.n_casos),
            "n_eventos": int(e1.n_eventos),
            "n_padroes_covariaveis": int(e1.n_padroes),
            "convergiu": bool(e1.resultados.converged),
            "tempo_ajuste_s": float(e1.tempo_ajuste_s),
        },
        "features": list(explain.CHAVES_PADRAO),
    }


def gerar_bundle_e1(cfg: dict, destino: str | Path | None = None) -> Path:
    """Lê o E1 de `data/e1/` (com statsmodels, sem recarregar os casos) e grava o bundle em
    `caminhos.modelos/e1` (ou em `destino`)."""
    from dengue_sinan import explain  # local: o pickle do ajuste é do statsmodels

    e1 = explain.load_e1(cfg)
    pasta = Path(destino) if destino is not None else Path(cfg["caminhos"]["modelos"]) / "e1"
    return save_bundle(e1, pasta, metadados_e1(cfg, e1))
