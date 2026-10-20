"""Rate limits distribuidos para rotas de autenticação e chamadas de IA."""

from __future__ import annotations

import hashlib
import hmac
import os
import re

from fastapi import Request
from fastapi.responses import JSONResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError


_REGRAS: dict[tuple[str, str], tuple[int, int]] = {
    ("POST", "/api/v1/auth/login"): (10, 60),
    ("POST", "/api/v1/auth/alterar-senha"): (10, 900),
    ("POST", "/api/v1/auth/solicitar-recuperacao-senha"): (5, 900),
    ("POST", "/api/v1/auth/redefinir-senha"): (10, 900),
    ("POST", "/api/v1/auth/verificar-email"): (10, 900),
    ("GET", "/api/v1/auth/verificar-email"): (10, 900),
    ("POST", "/api/v1/processos/interpretar-movimentacao"): (20, 60),
    ("POST", "/api/v1/processos/triagem"): (5, 60),
    ("POST", "/api/v1/processos/sincronizar"): (2, 300),
}
_REGRAS_DINAMICAS: tuple[tuple[str, re.Pattern[str], tuple[int, int], str], ...] = (
    (
        "POST",
        re.compile(r"^/api/v1/processos/[1-9][0-9]*/movimentacoes$"),
        (20, 60),
        "/api/v1/processos/{id}/movimentacoes",
    ),
    (
        "POST",
        re.compile(r"^/api/v1/processos/[1-9][0-9]*/documentos$"),
        (5, 60),
        "/api/v1/processos/{id}/documentos",
    ),
    (
        "POST",
        re.compile(r"^/api/v1/admin/advogados/[1-9][0-9]*/reenviar-verificacao$"),
        (10, 900),
        "/api/v1/admin/advogados/{id}/reenviar-verificacao",
    ),
)

_INCREMENTAR_E_EXPIRAR = """
local atual = redis.call('INCR', KEYS[1])
if atual == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return {atual, redis.call('TTL', KEYS[1])}
"""


async def aplicar_rate_limit(request: Request, redis: Redis) -> JSONResponse | None:
    metodo = request.method.upper()
    caminho = request.url.path
    caminho_chave = caminho
    regra = _REGRAS.get((metodo, caminho))
    if regra is None:
        for metodo_regra, padrao, limite_janela, rota_chave in _REGRAS_DINAMICAS:
            if metodo_regra == metodo and padrao.fullmatch(caminho):
                regra = limite_janela
                caminho_chave = rota_chave
                break
    if regra is None:
        return None

    limite, janela = regra
    endereco = request.client.host if request.client else "desconhecido"
    segredo = os.getenv("SINDCOMB_AUTH_SECRET", "").encode("utf-8")
    identificador = hmac.new(segredo, endereco.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
    chave = f"sindcomb:rate-limit:{metodo.lower()}:{caminho_chave}:{identificador}"

    try:
        contagem, ttl = await redis.eval(_INCREMENTAR_E_EXPIRAR, 1, chave, janela)
    except RedisError:
        return JSONResponse(
            status_code=503,
            content={"detail": "O controle de segurança está temporariamente indisponível."},
            headers={"Cache-Control": "no-store"},
        )

    if int(contagem) > limite:
        return JSONResponse(
            status_code=429,
            content={"detail": "Muitas solicitações. Aguarde antes de tentar novamente."},
            headers={"Retry-After": str(max(1, int(ttl))), "Cache-Control": "no-store"},
        )
    return None
