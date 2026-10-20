"""Limite de corpo HTTP aplicado antes do parser multipart do FastAPI."""

from __future__ import annotations

import json
import re
from tempfile import SpooledTemporaryFile
from typing import Any

from app.modulos.processos.recursos_service import limite_upload_bytes


_ROTA_UPLOAD = re.compile(r"^/api/v1/processos/[1-9][0-9]*/documentos$")
_SOBRECARGA_MULTIPART = 1024 * 1024
_TAMANHO_BLOCO = 64 * 1024
_LIMITE_SPOOL_MEMORIA = 1024 * 1024


async def _responder_corpo_grande(send: Any) -> None:
    corpo = json.dumps(
        {"detail": "O corpo da solicitação excede o limite permitido para este upload."},
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    await send(
        {
            "type": "http.response.start",
            "status": 413,
            "headers": [
                (b"content-type", b"application/json; charset=utf-8"),
                (b"content-length", str(len(corpo)).encode("ascii")),
                (b"cache-control", b"no-store"),
                (b"x-content-type-options", b"nosniff"),
            ],
        }
    )
    await send({"type": "http.response.body", "body": corpo})


class LimiteCorpoUploadMiddleware:
    """Limita uploads mesmo quando o cliente omite Content-Length ou usa chunks."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if (
            scope.get("type") != "http"
            or scope.get("method", "").upper() != "POST"
            or not _ROTA_UPLOAD.fullmatch(scope.get("path", ""))
        ):
            await self.app(scope, receive, send)
            return

        limite_corpo = limite_upload_bytes() + _SOBRECARGA_MULTIPART
        cabecalhos = dict(scope.get("headers", []))
        tamanho_declarado = cabecalhos.get(b"content-length")
        if tamanho_declarado is not None:
            try:
                if int(tamanho_declarado) > limite_corpo:
                    await _responder_corpo_grande(send)
                    return
            except ValueError:
                # Se o cabeçalho for inválido, o limite continua aplicado ao fluxo.
                pass

        with SpooledTemporaryFile(max_size=_LIMITE_SPOOL_MEMORIA, mode="w+b") as corpo:
            total = 0
            while True:
                mensagem = await receive()
                if mensagem["type"] == "http.disconnect":
                    return
                if mensagem["type"] != "http.request":
                    continue

                bloco = mensagem.get("body", b"")
                total += len(bloco)
                if total > limite_corpo:
                    await _responder_corpo_grande(send)
                    return
                corpo.write(bloco)
                if not mensagem.get("more_body", False):
                    break

            corpo.seek(0)
            enviado_corpo_vazio = False

            async def receber_replay() -> dict[str, Any]:
                nonlocal enviado_corpo_vazio
                if total == 0 and not enviado_corpo_vazio:
                    enviado_corpo_vazio = True
                    return {"type": "http.request", "body": b"", "more_body": False}

                bloco = corpo.read(_TAMANHO_BLOCO)
                if not bloco:
                    return {"type": "http.disconnect"}
                return {
                    "type": "http.request",
                    "body": bloco,
                    "more_body": corpo.tell() < total,
                }

            await self.app(scope, receber_replay, send)
