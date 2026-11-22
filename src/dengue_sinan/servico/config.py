"""Configuração centralizada: arquivo `config/app.json` e variáveis de ambiente.

Ordem de prioridade: variável de ambiente > `config/app.json` > padrão. Nada aqui é segredo.
Variáveis: DENGUE_ARTEFATOS, DENGUE_M1, DENGUE_E1, DENGUE_LIMITE_REGISTROS e
DENGUE_APP_MODELO_SHA256 (pino opcional, ver `ConfigServico.m1_sha256`).
"""

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

from dengue_sinan.pipeline.contrato import RAIZ

CAMINHO_APP = RAIZ / "config" / "app.json"
LIMITE_PADRAO = 1000
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class ConfigServico:
    pasta_artefatos: Path
    m1: str | None  # identificador do artefato, ex.: "m1-perfil-2.0.0"; None = não configurado
    e1: str | None  # idem para o E1; None enquanto o E1 não existir
    limite_registros: int = LIMITE_PADRAO
    # Pino opcional: SHA-256 esperado de `modelo.joblib`, vindo de FORA da pasta do artefato.
    # O hash gravado em `metadados.json` só detecta corrupção (arquivo e metadados moram na mesma
    # pasta); o pino detecta troca do modelo por quem controla a pasta. `None` = sem pino.
    m1_sha256: str | None = None

    @classmethod
    def carregar(cls, caminho: Path = CAMINHO_APP, ambiente=None) -> "ConfigServico":
        env = os.environ if ambiente is None else ambiente
        bruto = {}
        if Path(caminho).is_file():
            bruto = json.loads(Path(caminho).read_text("utf-8"))
        pasta = Path(
            env.get("DENGUE_ARTEFATOS") or bruto.get("pasta_artefatos", "artefatos/modelos")
        )
        if not pasta.is_absolute():
            pasta = RAIZ / pasta
        limite = int(
            env.get("DENGUE_LIMITE_REGISTROS") or bruto.get("limite_registros", LIMITE_PADRAO)
        )
        if limite < 1:
            raise ValueError("limite_registros deve ser pelo menos 1")
        pino = env.get("DENGUE_APP_MODELO_SHA256") or bruto.get("m1_sha256")
        if pino is not None:
            pino = str(pino).strip().lower()
            if not _SHA256.match(pino):
                raise ValueError("DENGUE_APP_MODELO_SHA256 deve ter 64 caracteres hexadecimais")
        return cls(
            pasta_artefatos=pasta,
            m1=env.get("DENGUE_M1") or bruto.get("m1"),
            e1=env.get("DENGUE_E1") or bruto.get("e1"),
            limite_registros=limite,
            m1_sha256=pino,
        )
