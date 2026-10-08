from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

Papel = Literal["advogado", "visualizador"]
_bearer = HTTPBearer(auto_error=False)


class UsuarioAtual(BaseModel):
    id: str
    papel: Papel


def _base64url_decode(valor: str) -> bytes:
    return base64.urlsafe_b64decode(valor + "=" * (-len(valor) % 4))


def obter_usuario_atual(
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UsuarioAtual:
    """Valida JWT HS256 emitido pelo provedor de identidade da aplicação."""
    if credenciais is None or credenciais.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token Bearer obrigatório.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    segredo = os.getenv("SINDCOMB_AUTH_SECRET", "")
    if len(segredo) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configure SINDCOMB_AUTH_SECRET com pelo menos 32 caracteres.",
        )

    try:
        parte_cabecalho, parte_payload, parte_assinatura = credenciais.credentials.split(".")
        cabecalho = json.loads(_base64url_decode(parte_cabecalho))
        payload = json.loads(_base64url_decode(parte_payload))
        assinatura_recebida = _base64url_decode(parte_assinatura)
    except (ValueError, TypeError, json.JSONDecodeError) as erro:
        raise HTTPException(status_code=401, detail="Token inválido.") from erro

    if cabecalho.get("alg") != "HS256":
        raise HTTPException(status_code=401, detail="Algoritmo do token não aceito.")

    mensagem = f"{parte_cabecalho}.{parte_payload}".encode("ascii")
    assinatura_esperada = hmac.new(segredo.encode(), mensagem, hashlib.sha256).digest()
    if not hmac.compare_digest(assinatura_recebida, assinatura_esperada):
        raise HTTPException(status_code=401, detail="Assinatura do token inválida.")

    try:
        expiracao = int(payload["exp"])
        identificador = str(payload["sub"]).strip()
        papel = payload["papel"]
    except (KeyError, TypeError, ValueError) as erro:
        raise HTTPException(status_code=401, detail="Token sem claims obrigatórias.") from erro

    if expiracao <= time.time():
        raise HTTPException(status_code=401, detail="Token expirado.")
    if papel not in ("advogado", "visualizador") or not identificador:
        raise HTTPException(status_code=403, detail="Perfil de usuário inválido.")

    return UsuarioAtual(id=identificador, papel=papel)


def exigir_advogado(usuario: UsuarioAtual = Depends(obter_usuario_atual)) -> UsuarioAtual:
    if usuario.papel != "advogado":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente advogados podem cadastrar processos ou alterar status.",
        )
    return usuario
