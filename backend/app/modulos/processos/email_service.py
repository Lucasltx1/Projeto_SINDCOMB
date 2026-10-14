from email.message import EmailMessage
import logging
import os
import smtplib
import ssl
from typing import Sequence
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


def enviar_email(destinatarios: Sequence[str], assunto: str, corpo: str) -> bool:
    emails = list(dict.fromkeys(email.strip() for email in destinatarios if email.strip()))
    if not emails:
        return True

    host = os.getenv("SMTP_HOST", "").strip()
    remetente = os.getenv("SMTP_FROM", "").strip()
    if not host or not remetente:
        logger.warning("E-mail não enviado: SMTP_HOST e SMTP_FROM precisam estar configurados.")
        return False

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
                servidor.send_message(mensagem)
                enviados += 1
        return enviados == len(emails)
    except (OSError, smtplib.SMTPException, ValueError):
        logger.exception("Falha ao enviar e-mail pelo SMTP configurado.")
        return False


def enviar_verificacao_email(email: str, nome: str, token: str) -> bool:
    base_url = os.getenv("SINDCOMB_PUBLIC_API_URL", "http://localhost:8000").rstrip("/")
    query = urlencode({"token": token})
    link = f"{base_url}/api/v1/auth/verificar-email?{query}"
    corpo = (
        f"Olá, {nome}.\n\n"
        "Sua conta do Sistema de Acompanhamento Processual foi criada. "
        "Confirme seu endereço de e-mail pelo link abaixo:\n\n"
        f"{link}\n\n"
        "Após a confirmação, entre usando seu e-mail e a senha inicial informada pelo administrador. "
        "O sistema exigirá a troca da senha no primeiro acesso.\n\n"
        "Se você não esperava esta mensagem, ignore-a."
    )
    return enviar_email([email], "Confirme seu e-mail — SINDCOMB", corpo)