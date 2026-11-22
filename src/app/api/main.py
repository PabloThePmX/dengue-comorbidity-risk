"""API HTTP do protótipo. Execução local:

    PYTHONPATH=src python -m app.api            # ou: uvicorn app.api.main:criar_app --factory

Documentação interativa em /docs (OpenAPI em /openapi.json). Nenhum dado de paciente é gravado
nem registrado em log: os logs trazem só método, rota, status, tempo e contagens.
A API só traduz HTTP: toda a lógica está em `dengue_sinan.servico` (via `app.servico`).
"""

import logging
import re
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app import VERSAO_APP
from app.api.limite_corpo import LimiteCorpo
from app.api.schemas import (
    PedidoPrever,
    Previsao,
    RespostaE1,
    RespostaErro,
    RespostaPrever,
    RespostaRelatorio,
    RespostaSaude,
    RespostaVersao,
)
from app.config import Config, carregar_config
from app.servico import (
    AVISO,
    EntradaInvalida,
    LoteGrande,
    ModeloIndisponivel,
    Servico,
    criar_servico,
    info_sistema,
)

log = logging.getLogger("app.api")
_ID_PEDIDO = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def _servico(request: Request) -> Servico:
    return request.app.state.servico


def _id_pedido(request: Request) -> str:
    """Eco do `X-Request-ID` só se for simples (A-Z a-z 0-9 _ -, até 64); senão, id novo."""
    recebido = request.headers.get("x-request-id", "")
    return recebido if _ID_PEDIDO.match(recebido) else uuid.uuid4().hex[:12]


def criar_app(config: Config | None = None, servico: Servico | None = None) -> FastAPI:
    """Fábrica da aplicação. `servico` permite injetar um serviço (testes); sem ele, o serviço
    da configuração é criado na partida, com verificação dos hashes (e do pino, se houver)."""
    cfg = config or carregar_config()
    logging.basicConfig(
        level=cfg.log_nivel, format="%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    @asynccontextmanager
    async def ciclo_de_vida(app: FastAPI):
        if app.state.servico is None:
            app.state.servico = criar_servico(cfg)
        else:
            app.state.servico.carregar()
        yield

    app = FastAPI(
        title="Dengue Comorbidity Risk: API do protótipo",
        version=VERSAO_APP,
        description=AVISO,
        lifespan=ciclo_de_vida,
    )
    app.state.cfg = cfg
    app.state.servico = servico
    app.add_middleware(LimiteCorpo, max_bytes=cfg.max_corpo_bytes)

    @app.middleware("http")
    async def registrar(request: Request, call_next):
        rid = _id_pedido(request)
        t0 = time.perf_counter()
        resposta = await call_next(request)
        resposta.headers["X-Request-ID"] = rid
        log.info(
            "%s %s -> %s em %.1f ms (id %s)",
            request.method,
            request.url.path,
            resposta.status_code,
            (time.perf_counter() - t0) * 1000,
            rid,
        )
        return resposta

    @app.exception_handler(EntradaInvalida)
    async def _erro_entrada(_: Request, e: EntradaInvalida):
        return JSONResponse(status_code=422, content={"detail": e.erros})

    @app.exception_handler(LoteGrande)
    async def _lote_grande(_: Request, e: LoteGrande):
        motivo = f"no máximo {e.limite} registros"
        return JSONResponse(
            status_code=422,
            content={"detail": [{"indice": None, "campo": "registros", "motivo": motivo}]},
        )

    @app.exception_handler(RequestValidationError)
    async def _erro_esquema(_: Request, e: RequestValidationError):
        itens = [
            {
                "indice": next((p for p in err["loc"] if isinstance(p, int)), None),
                "campo": ".".join(str(p) for p in err["loc"][1:]) or "(corpo)",
                "motivo": err["msg"],
            }
            for err in e.errors()
        ]
        return JSONResponse(status_code=422, content={"detail": itens})

    @app.exception_handler(ModeloIndisponivel)
    async def _sem_modelo(_: Request, e: ModeloIndisponivel):
        return JSONResponse(status_code=503, content={"detail": f"modelo indisponível: {e.motivo}"})

    @app.exception_handler(Exception)
    async def _erro_interno(request: Request, e: Exception):
        log.error("erro interno em %s %s: %s", request.method, request.url.path, type(e).__name__)
        return JSONResponse(status_code=500, content={"detail": "erro interno"})

    @app.get("/saude", response_model=RespostaSaude, responses={503: {"model": RespostaSaude}})
    def saude(request: Request):
        s = _servico(request)
        estado = s.saude()
        if estado["status"] != "ok":
            corpo = RespostaSaude(
                status="degradado",
                modelo_carregado=False,
                detalhe=s.info()["m1_motivo_indisponivel"] or "modelo não carregado",
            )
            return JSONResponse(status_code=503, content=corpo.model_dump())
        return RespostaSaude(
            status="ok",
            modelo_carregado=True,
            versao_modelo=s.info()["m1"]["identificador"],
            e1_disponivel=estado["e1"] == "disponivel",
        )

    @app.get("/versao", response_model=RespostaVersao, responses={503: {"model": RespostaErro}})
    def versao(request: Request):
        s = _servico(request)
        info = s.info()
        if info["m1"] is None:
            raise ModeloIndisponivel("M1", info["m1_motivo_indisponivel"] or "não carregado")
        e1 = info["e1"]
        return RespostaVersao(
            sistema=info_sistema(),
            modelo=info["m1"],
            e1={"disponivel": e1["status"] == "disponivel", "motivo": e1["motivo"]},
        )

    @app.get("/contrato", responses={503: {"model": RespostaErro}})
    def contrato(request: Request) -> dict:
        return _servico(request).contrato("m1")

    @app.get(
        "/relatorio",
        response_model=RespostaRelatorio,
        responses={503: {"model": RespostaErro}},
    )
    def relatorio(request: Request):
        """Relatório de desempenho e limitações, só com números gravados no artefato."""
        return _servico(request).relatorio()

    @app.post(
        "/prever",
        response_model=RespostaPrever,
        responses={422: {"model": RespostaErro}, 503: {"model": RespostaErro}},
    )
    def prever(pedido: PedidoPrever, request: Request):
        registros = [r.model_dump(exclude_unset=True) for r in pedido.registros]
        resp = _servico(request).prever_m1(registros)
        return RespostaPrever(
            versao_modelo=resp["versao_modelo"],
            previsoes=[
                Previsao(
                    indice=r["indice"],
                    probabilidade=r["probabilidade"],
                    status=r["status"],
                    erro=r["erro"] or "",
                    avisos=r["avisos"],
                )
                for r in resp["resultados"]
            ],
            alto_risco_motivo=resp["alto_risco_motivo"],
            aviso=resp["aviso"],
        )

    @app.post(
        "/e1/perfil",
        status_code=501,
        response_model=RespostaE1,
        responses={503: {"model": RespostaErro}},
    )
    def e1_perfil(request: Request):
        try:
            _servico(request).prever_e1([])
        except ModeloIndisponivel as e:
            return JSONResponse(status_code=501, content=RespostaE1(motivo=e.motivo).model_dump())
        raise RuntimeError("E1 sem integração com a API")  # pragma: no cover

    return app
