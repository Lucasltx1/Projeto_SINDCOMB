"""Casos de uso de recuperação de senha com token de uso único."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import os
import secrets

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .auditoria_service import registrar_evento
from .email_outbox import cancelar_emails_pendentes, enfileirar_email
from .email_service import preparar_email_redefinicao_senha, preparar_email_senha_alterada
from .models import AdministradorDB, TokenVerificacaoDB, UsuarioDB
from .security import hash_password, verificar_password

TIPO_TOKEN_REDEFINICAO = "redefinicao_senha"
MENSAGEM_SOLICITACAO = (
    "Se houver uma conta elegível para este e-mail, enviaremos instruções para redefinir a senha."
)


def _horas_expiracao() -> int:
    try:
        valor = int(os.getenv("SINDCOMB_PASSWORD_RESET_HOURS", "1"))
    except ValueError:
        valor = 1
    return min(max(valor, 1), 24)


def _cooldown_segundos() -> int:
    try:
        valor = int(os.getenv("SINDCOMB_PASSWORD_RESET_COOLDOWN_SECONDS", "60"))
    except ValueError:
        valor = 60
    return min(max(valor, 30), 3600)


def _data_utc(valor: datetime) -> datetime:
    return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor.astimezone(timezone.utc)


def solicitar_recuperacao_senha(sessao: Session, email: str) -> bool:
    """Enfileira instruções só para contas ativas/verificadas; não revela se o e-mail existe."""
    agora = datetime.now(timezone.utc)
    usuario = sessao.scalar(
        select(UsuarioDB)
        .where(func.lower(UsuarioDB.email) == email.strip().lower())
        .with_for_update()
    )
    if (
        usuario is None
        or not usuario.ativo
        or not usuario.email_verificado
        or sessao.get(AdministradorDB, usuario.id_usuario) is not None
    ):
        # Mantém rastreabilidade sem registrar o endereço informado nem indicar
        # ao solicitante se a conta existe.
        registrar_evento(
            sessao,
            operacao="auth.password_reset_requested",
            descricao="Solicitação de recuperação sem conta elegível.",
            resultado="ignorado",
        )
        sessao.commit()
        return False

    cooldown = agora - timedelta(seconds=_cooldown_segundos())
    token_recente = sessao.scalar(
        select(TokenVerificacaoDB.id_token)
        .where(
            TokenVerificacaoDB.id_usuario == usuario.id_usuario,
            TokenVerificacaoDB.tipo == TIPO_TOKEN_REDEFINICAO,
            TokenVerificacaoDB.criado_em >= cooldown,
        )
        .limit(1)
    )
    if token_recente is not None:
        return True

    sessao.execute(
        delete(TokenVerificacaoDB).where(
            TokenVerificacaoDB.id_usuario == usuario.id_usuario,
            TokenVerificacaoDB.tipo == TIPO_TOKEN_REDEFINICAO,
        )
    )
    cancelar_emails_pendentes(sessao, usuario.email, categoria="recuperacao_senha")

    token_plano = secrets.token_urlsafe(36)
    token_hash = hashlib.sha256(token_plano.encode("utf-8")).hexdigest()
    sessao.add(
        TokenVerificacaoDB(
            id_usuario=usuario.id_usuario,
            tipo=TIPO_TOKEN_REDEFINICAO,
            token_hash=token_hash,
            expira_em=agora + timedelta(hours=_horas_expiracao()),
        )
    )
    assunto, corpo = preparar_email_redefinicao_senha(usuario.nome, token_plano)
    enfileirado = enfileirar_email(
        sessao,
        [usuario.email],
        assunto,
        corpo,
        categoria="recuperacao_senha",
    )
    registrar_evento(
        sessao,
        usuario_id=usuario.id_usuario,
        operacao="auth.password_reset_requested",
        descricao="Solicitação de recuperação de senha registrada.",
        resultado="sucesso" if enfileirado else "falha",
    )
    sessao.commit()
    return enfileirado > 0


def redefinir_senha(sessao: Session, token_plano: str, nova_senha: str) -> bool:
    """Valida, consome o token, muda a credencial e invalida sessões antigas."""
    hash_token = hashlib.sha256(token_plano.encode("utf-8")).hexdigest()
    token = sessao.scalar(
        select(TokenVerificacaoDB)
        .where(
            TokenVerificacaoDB.token_hash == hash_token,
            TokenVerificacaoDB.tipo == TIPO_TOKEN_REDEFINICAO,
        )
        .with_for_update()
    )
    agora = datetime.now(timezone.utc)
    if token is None:
        return False
    if _data_utc(token.expira_em) <= agora:
        sessao.delete(token)
        sessao.commit()
        return False

    usuario = sessao.get(UsuarioDB, token.id_usuario)
    if (
        usuario is None
        or not usuario.ativo
        or not usuario.email_verificado
        or sessao.get(AdministradorDB, token.id_usuario) is not None
    ):
        sessao.delete(token)
        sessao.commit()
        return False
    if verificar_password(nova_senha, usuario.senha):
        raise ValueError("A nova senha deve ser diferente da senha atual.")

    usuario.senha = hash_password(nova_senha)
    usuario.primeiro_acesso = False
    usuario.token_version += 1
    sessao.execute(
        delete(TokenVerificacaoDB).where(
            TokenVerificacaoDB.id_usuario == usuario.id_usuario,
            TokenVerificacaoDB.tipo == TIPO_TOKEN_REDEFINICAO,
        )
    )
    cancelar_emails_pendentes(sessao, usuario.email, categoria="recuperacao_senha")
    assunto, corpo = preparar_email_senha_alterada(usuario.nome)
    enfileirar_email(
        sessao,
        [usuario.email],
        assunto,
        corpo,
        categoria="senha_alterada",
    )
    registrar_evento(
        sessao,
        usuario_id=usuario.id_usuario,
        operacao="auth.password_reset_completed",
        descricao="Senha redefinida por link de recuperação; sessões anteriores invalidadas.",
        dados={"sessoes_invalidadas": True},
    )
    sessao.commit()
    return True
