from email.message import EmailMessage
import logging
import os
import smtplib
import ssl
from typing import Sequence
from urllib.parse import quote, urlencode

logger = logging.getLogger(__name__)


def enviar_email_com_resultado(
    destinatarios: Sequence[str], assunto: str, corpo: str
) -> tuple[bool, str | None]:
    emails = list(dict.fromkeys(email.strip() for email in destinatarios if email.strip()))
    if not emails:
        return True, None

    host = os.getenv("SMTP_HOST", "").strip()
    remetente = os.getenv("SMTP_FROM", "").strip()
    if not host or not remetente:
        erro = "SMTP_HOST e SMTP_FROM precisam estar configurados."
        logger.warning("E-mail não enviado: %s", erro)
        return False, erro

    try:
        porta = int(os.getenv("SMTP_PORT", "587"))
        usar_ssl = os.getenv("SMTP_USE_SSL", "false").strip().lower() in {"1", "true", "yes"}
        usar_starttls = os.getenv("SMTP_STARTTLS", "true").strip().lower() in {"1", "true", "yes"}
        contexto = ssl.create_default_context()
        cliente_cls = smtplib.SMTP_SSL if usar_ssl else smtplib.SMTP
        cliente_args = {"context": contexto} if usar_ssl else {}
        enviados = 0
        with cliente_cls(host, porta, timeout=15, **cliente_args) as servidor:
            if usar_starttls and not usar_ssl:
                servidor.starttls(context=contexto)
            usuario_smtp = os.getenv("SMTP_USERNAME", "").strip()
            senha_smtp = os.getenv("SMTP_PASSWORD", "")
            if usuario_smtp:
                servidor.login(usuario_smtp, senha_smtp)
            for email in emails:
                mensagem = EmailMessage()
                mensagem["From"] = remetente
                mensagem["To"] = email
                mensagem["Subject"] = assunto
                mensagem.set_content(corpo)
                recusados = servidor.send_message(mensagem)
                if recusados:
                    raise smtplib.SMTPRecipientsRefused(recusados)
                enviados += 1
        if enviados == len(emails):
            return True, None
        return False, "O servidor SMTP confirmou apenas parte dos destinatários."
    except (OSError, smtplib.SMTPException, ValueError) as erro:
        logger.exception("Falha ao enviar e-mail pelo SMTP configurado.")
        return False, f"{type(erro).__name__}: {erro}"[:500]


def enviar_email(destinatarios: Sequence[str], assunto: str, corpo: str) -> bool:
    enviado, _erro = enviar_email_com_resultado(destinatarios, assunto, corpo)
    return enviado


def preparar_verificacao_email(email: str, nome: str, token: str) -> tuple[str, str]:
    base_url = os.getenv("SINDCOMB_PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    query = urlencode({"token": token})
    link = f"{base_url}/api/v1/auth/verificar-email?{query}"
    corpo = (
        f"Olá, {nome}.\n\n"
        "Sua conta do Sistema de Acompanhamento Processual foi criada. "
        "Confirme seu endereço de e-mail pelo link abaixo:\n\n"
        f"{link}\n\n"
        "Após a confirmação, acesse a tela de login e selecione ‘Esqueci minha senha’ "
        "para definir sua senha pessoal.\n\n"
        "Se você não esperava esta mensagem, ignore-a."
    )
    return "Confirme seu e-mail — SINDCOMB", corpo


def preparar_email_redefinicao_senha(nome: str, token: str) -> tuple[str, str]:
    base_url = os.getenv("SINDCOMB_PUBLIC_APP_URL", "http://localhost:3000").rstrip("/")
    link = f"{base_url}/redefinir-senha#token={quote(token, safe='')}"
    corpo = (
        f"Olá, {nome}.\n\n"
        "Recebemos uma solicitação para redefinir a senha da sua conta SINDCOMB.\n\n"
        f"Use este link para criar uma nova senha (válido por tempo limitado):\n{link}\n\n"
        "Se você não solicitou a recuperação, ignore esta mensagem. Sua senha atual continuará válida."
    )
    return "Redefinição de senha — SINDCOMB", corpo


def preparar_email_senha_alterada(nome: str) -> tuple[str, str]:
    return (
        "Senha alterada — SINDCOMB",
        (
            f"Olá, {nome}.\n\nA senha da sua conta SINDCOMB foi alterada. "
            "Se você não fez essa alteração, contate imediatamente o administrador do sistema."
        ),
    )


def enviar_verificacao_email(email: str, nome: str, token: str) -> bool:
    assunto, corpo = preparar_verificacao_email(email, nome, token)
    return enviar_email([email], assunto, corpo)
