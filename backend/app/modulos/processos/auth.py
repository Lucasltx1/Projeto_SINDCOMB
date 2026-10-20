from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
from typing import Literal

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .models import AdministradorDB, JuridicoDB, UsuarioDB

Papel = Literal["administrador", "advogado", "visualizador"]
_bearer = HTTPBearer(auto_error=False)
_COOKIE_SESSAO = "sindcomb_access_token"


class UsuarioAtual(BaseModel):
    id: str
    nome: str
    username: str | None = None
    email: str | None = None
    papel: Papel
    primeiro_acesso: bool


def _base64url_decode(valor: str) -> bytes:
    return base64.urlsafe_b64decode(valor + "=" * (-len(valor) % 4))


def criar_access_token(usuario: UsuarioDB, papel: Papel) -> str:
    segredo = os.getenv("SINDCOMB_AUTH_SECRET", "")
    if len(segredo) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configure SINDCOMB_AUTH_SECRET com pelo menos 32 caracteres.",
        )
    duracao = duracao_access_token_minutos()
    cabecalho = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": str(usuario.id_usuario),
        "papel": papel,
        "ver": usuario.token_version,
        "iat": int(time.time()),
        "exp": int(time.time()) + duracao * 60,
    }
    parte_cabecalho = base64.urlsafe_b64encode(
        json.dumps(cabecalho, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    parte_payload = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode()
    ).decode().rstrip("=")
    mensagem = f"{parte_cabecalho}.{parte_payload}"
    assinatura = hmac.new(segredo.encode(), mensagem.encode("ascii"), hashlib.sha256).digest()
    parte_assinatura = base64.urlsafe_b64encode(assinatura).decode().rstrip("=")
    return f"{mensagem}.{parte_assinatura}"


def duracao_access_token_minutos() -> int:
    try:
        minutos_configurados = int(os.getenv("SINDCOMB_ACCESS_TOKEN_MINUTES", "60"))
    except ValueError:
        minutos_configurados = 60
    return min(max(5, minutos_configurados), 60)


def criar_token_csrf(access_token: str) -> str:
    segredo = os.getenv("SINDCOMB_AUTH_SECRET", "").encode("utf-8")
    return base64.urlsafe_b64encode(
        hmac.new(segredo, b"csrf:" + access_token.encode("ascii"), hashlib.sha256).digest()
    ).decode("ascii").rstrip("=")


def obter_usuario_atual(
    request: Request = None,  # type: ignore[assignment]  # FastAPI injeta Request.
    credenciais: HTTPAuthorizationCredentials | None = Depends(_bearer),
    sessao: Session = Depends(obter_sessao),
) -> UsuarioAtual:
    token = (
        credenciais.credentials
        if credenciais is not None and credenciais.scheme.lower() == "bearer"
        else request.cookies.get(_COOKIE_SESSAO) if request is not None else None
    )
    usa_cookie = credenciais is None or credenciais.scheme.lower() != "bearer"
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticação obrigatória.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    segredo = os.getenv("SINDCOMB_AUTH_SECRET", "")
    if len(segredo) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configure SINDCOMB_AUTH_SECRET com pelo menos 32 caracteres.",
        )

    try:
        parte_cabecalho, parte_payload, parte_assinatura = token.split(".")
        cabecalho = json.loads(_base64url_decode(parte_cabecalho))
        payload = json.loads(_base64url_decode(parte_payload))
        assinatura_recebida = _base64url_decode(parte_assinatura)
        identificador = int(payload["sub"])
        versao_token = int(payload.get("ver", 0))
        expiracao = int(payload["exp"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError) as erro:
        raise HTTPException(status_code=401, detail="Token inválido.") from erro

    if cabecalho.get("alg") != "HS256":
        raise HTTPException(status_code=401, detail="Algoritmo do token não aceito.")

    mensagem = f"{parte_cabecalho}.{parte_payload}".encode("ascii")
    assinatura_esperada = hmac.new(segredo.encode(), mensagem, hashlib.sha256).digest()
    if not hmac.compare_digest(assinatura_recebida, assinatura_esperada):
        raise HTTPException(status_code=401, detail="Assinatura do token inválida.")
    if expiracao <= time.time():
        raise HTTPException(status_code=401, detail="Token expirado.")

    token_csrf = criar_token_csrf(token)
    if request is not None:
        request.state.csrf_token = token_csrf
    if usa_cookie and request is not None and request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        enviado = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(enviado, token_csrf):
            raise HTTPException(status_code=403, detail="Token CSRF ausente ou inválido.")

    usuario = sessao.get(UsuarioDB, identificador)
    if usuario is None or not usuario.ativo:
        raise HTTPException(status_code=401, detail="Usuário inativo ou inexistente.")
    if versao_token != usuario.token_version:
        raise HTTPException(status_code=401, detail="Sessão invalidada. Entre novamente.")
    eh_administrador = sessao.get(AdministradorDB, identificador) is not None
    if not eh_administrador and not usuario.email_verificado:
        raise HTTPException(status_code=403, detail="Confirme o e-mail antes de entrar.")

    if eh_administrador:
        papel: Papel = "administrador"
    elif sessao.get(JuridicoDB, identificador) is not None:
        papel = "advogado"
    else:
        papel = "visualizador"

    return UsuarioAtual(
        id=str(usuario.id_usuario),
        nome=usuario.nome,
        username=usuario.username,
        email=usuario.email,
        papel=papel,
        primeiro_acesso=usuario.primeiro_acesso,
    )


def exigir_usuario_com_senha_alterada(
    usuario: UsuarioAtual = Depends(obter_usuario_atual),
) -> UsuarioAtual:
    if usuario.primeiro_acesso:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "codigo": "alteracao_senha_obrigatoria",
                "mensagem": "Altere a senha inicial antes de usar o sistema.",
            },
        )
    return usuario


def exigir_advogado(
    usuario: UsuarioAtual = Depends(exigir_usuario_com_senha_alterada),
    sessao: Session = Depends(obter_sessao),
) -> UsuarioAtual:
    if usuario.papel != "advogado" or sessao.get(JuridicoDB, int(usuario.id)) is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente advogados podem cadastrar processos ou alterar status.",
        )
    return usuario


def exigir_acesso_processos(
    usuario: UsuarioAtual = Depends(exigir_usuario_com_senha_alterada),
) -> UsuarioAtual:
    if usuario.papel == "administrador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A conta administrativa não tem acesso às informações dos processos.",
        )
    return usuario


def exigir_administrador(
    usuario: UsuarioAtual = Depends(exigir_usuario_com_senha_alterada),
) -> UsuarioAtual:
    if usuario.papel != "administrador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Somente administradores podem gerenciar advogados e associados.",
        )
    return usuario
