"""Middleware ASGI que recusa corpo de requisição maior que o limite (HTTP 413).

Confere o `Content-Length` declarado e, para corpo sem tamanho declarado (chunked), conta os
bytes recebidos. Não guarda nem lê o conteúdo além de contar.
"""

import json


class CorpoGrande(Exception):  # noqa: N818 - exceção interna, nome de domínio
    """Corpo ultrapassou o limite durante a leitura."""


class LimiteCorpo:
    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def _responder(self, send, status: int, detalhe: str) -> None:
        corpo = json.dumps({"detail": detalhe}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(corpo)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": corpo})

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        declarado = dict(scope["headers"]).get(b"content-length")
        if declarado is not None:
            try:
                n = int(declarado)
            except ValueError:
                await self._responder(send, 400, "Content-Length inválido")
                return
            if n > self.max_bytes:
                await self._responder(send, 413, f"corpo maior que {self.max_bytes} bytes")
                return
        total = 0
        excedeu = False
        iniciou = False

        async def receive_limitado():
            nonlocal total, excedeu
            msg = await receive()
            if msg["type"] == "http.request":
                total += len(msg.get("body", b""))
                if total > self.max_bytes:
                    excedeu = True
                    raise CorpoGrande
            return msg

        async def send_filtrado(msg):
            # O framework pode transformar a exceção de leitura em 400; se o limite estourou,
            # a resposta é trocada por 413 e o resto da resposta original é descartado.
            nonlocal iniciou
            if excedeu:
                if not iniciou:
                    iniciou = True
                    await self._responder(send, 413, f"corpo maior que {self.max_bytes} bytes")
                return
            if msg["type"] == "http.response.start":
                iniciou = True
            await send(msg)

        try:
            await self.app(scope, receive_limitado, send_filtrado)
        except CorpoGrande:
            if not iniciou:
                await self._responder(send, 413, f"corpo maior que {self.max_bytes} bytes")
