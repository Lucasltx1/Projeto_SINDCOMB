"""Fila persistente de e-mails e política de novas tentativas."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
import logging
import os

from sqlalchemy import select, update
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet, InvalidToken

from app.nucleo.database import SessionLocal
from .email_service import enviar_email_com_resultado
from .models import EmailOutboxDB
from .repository import listar_emails_envolvidos
from .schemas import ProcessoRegistro

logger = logging.getLogger(__name__)
_PREFIXO_CORPO_PROTEGIDO = "fernet:v1:"


def _cifra_email() -> Fernet:
    chave = os.getenv("SINDCOMB_EMAIL_ENCRYPTION_KEY", "").strip()
    try:
        return Fernet(chave.encode("ascii"))
    except (ValueError, UnicodeError) as erro:
        raise RuntimeError("Configure uma SINDCOMB_EMAIL_ENCRYPTION_KEY válida.") from erro


def proteger_corpo_email(corpo: str) -> str:
    cifrado = _cifra_email().encrypt(corpo.encode("utf-8")).decode("ascii")
    return _PREFIXO_CORPO_PROTEGIDO + cifrado


def descriptografar_corpo_email(corpo_armazenado: str) -> str:
    if not corpo_armazenado.startswith(_PREFIXO_CORPO_PROTEGIDO):
        raise ValueError("O corpo do e-mail não está protegido; a mensagem não será enviada.")
    cifrado = corpo_armazenado[len(_PREFIXO_CORPO_PROTEGIDO):]
    try:
        return _cifra_email().decrypt(cifrado.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeError, ValueError) as erro:
        raise ValueError("Não foi possível abrir o corpo protegido do e-mail.") from erro


def proteger_outbox_legada(sessao: Session) -> int:
    """Cifra pendências antigas e apaga corpos já enviados/cancelados."""
    linhas = sessao.scalars(select(EmailOutboxDB)).all()
    alteradas = 0
    for linha in linhas:
        if linha.status == "pendente":
            if not linha.corpo.startswith(_PREFIXO_CORPO_PROTEGIDO):
                linha.corpo = proteger_corpo_email(linha.corpo)
                alteradas += 1
        elif linha.corpo:
            linha.corpo = ""
            linha.assunto = "[mensagem encerrada]"
            linha.ultimo_erro = None
            alteradas += 1
    if alteradas:
        sessao.commit()
    return alteradas


def _config_int(nome: str, padrao: int, minimo: int, maximo: int) -> int:
    try:
        valor = int(os.getenv(nome, str(padrao)))
    except ValueError:
        valor = padrao
    return min(max(valor, minimo), maximo)


def atraso_retentativa_segundos(tentativa: int) -> int:
    """Backoff exponencial com teto de uma hora."""
    base = _config_int("SINDCOMB_EMAIL_RETRY_BASE_SECONDS", 60, 1, 3600)
    maximo = _config_int("SINDCOMB_EMAIL_RETRY_MAX_SECONDS", 3600, base, 86400)
    return min(base * (2 ** max(0, tentativa - 1)), maximo)


def enfileirar_email(
    sessao: Session,
    destinatarios: list[str],
    assunto: str,
    corpo: str,
    *,
    categoria: str,
    processo_id: int | None = None,
) -> int:
    """Adiciona uma linha por destinatário; a transação fica a cargo do chamador."""
    emails = list(dict.fromkeys(email.strip().lower() for email in destinatarios if email.strip()))
    agora = datetime.now(timezone.utc)
    for email in emails:
        sessao.add(
            EmailOutboxDB(
                destinatario=email,
                assunto=assunto[:255],
                corpo=proteger_corpo_email(corpo),
                categoria=categoria[:50],
                id_processo=processo_id,
                status="pendente",
                tentativas=0,
                proxima_tentativa=agora,
            )
        )
    return len(emails)


def enfileirar_notificacao_processo(
    sessao: Session,
    processo: ProcessoRegistro,
    evento: str,
    detalhe: str,
) -> int:
    destinatarios = listar_emails_envolvidos(sessao, processo.id)
    if not destinatarios:
        return 0
    assunto = f"SINDCOMB — {evento} no processo {processo.dados.numero}"
    corpo = (
        "O sistema de acompanhamento processual identificou uma atualização.\n\n"
        f"Processo: {processo.dados.numero}\n"
        f"Tribunal: {processo.dados.tribunal}\n"
        f"Evento: {evento}\n"
        f"Status atual: {processo.status}\n\n"
        f"Detalhes:\n{detalhe}\n"
    )
    try:
        processo_id = int(processo.id)
    except (TypeError, ValueError):
        processo_id = None
    return enfileirar_email(
        sessao,
        destinatarios,
        assunto,
        corpo,
        categoria="atualizacao_processo",
        processo_id=processo_id,
    )


def cancelar_emails_pendentes(
    sessao: Session, destinatario: str | None, *, categoria: str | None = None
) -> None:
    if not destinatario:
        return
    filtros = [
        EmailOutboxDB.destinatario == destinatario.strip().lower(),
        EmailOutboxDB.status == "pendente",
    ]
    if categoria is not None:
        filtros.append(EmailOutboxDB.categoria == categoria)
    sessao.execute(
        update(EmailOutboxDB)
        .where(*filtros)
        .values(
            status="cancelado",
            corpo="",
            assunto="[mensagem cancelada]",
            ultimo_erro=("Mensagem de verificação substituída." if categoria else "Destinatário removido do cadastro."),
        )
    )


async def processar_email_outbox(limite: int = 20) -> tuple[int, int]:
    """Envia um lote de mensagens devidas e persiste sucesso/falha para retry."""
    limite = min(max(limite, 1), 100)
    enviados = falharam = 0
    max_tentativas = _config_int("SINDCOMB_EMAIL_MAX_ATTEMPTS", 8, 1, 20)
    for _ in range(limite):
        # Reserva somente o próximo item para o lease não vencer enquanto o lote espera.
        with SessionLocal() as sessao:
            agora = datetime.now(timezone.utc)
            linha = sessao.scalars(
                select(EmailOutboxDB)
                .where(
                    EmailOutboxDB.status == "pendente",
                    EmailOutboxDB.proxima_tentativa <= agora,
                )
                .order_by(EmailOutboxDB.proxima_tentativa, EmailOutboxDB.id_email)
                .with_for_update(skip_locked=True)
                .limit(1)
            ).first()
            if linha is None:
                break
            email_id = linha.id_email
            destinatario, assunto, corpo = linha.destinatario, linha.assunto, linha.corpo
            # Se o worker cair neste ponto, outro worker recupera a mensagem em cinco minutos.
            linha.proxima_tentativa = agora + timedelta(minutes=5)
            sessao.commit()

        try:
            corpo = descriptografar_corpo_email(corpo)
        except ValueError:
            with SessionLocal() as sessao:
                linha = sessao.get(EmailOutboxDB, email_id)
                if linha is not None and linha.status == "pendente":
                    linha.status = "cancelado"
                    linha.corpo = ""
                    linha.assunto = "[mensagem cancelada]"
                    linha.ultimo_erro = "Mensagem protegida indisponível; solicite um novo envio."
                    sessao.commit()
            logger.error("Mensagem %s cancelada porque não pôde ser descriptografada.", email_id)
            continue

        try:
            sucesso, erro_envio = await asyncio.to_thread(
                enviar_email_com_resultado,
                [destinatario],
                assunto,
                corpo,
            )
        except Exception as erro:  # Falhas inesperadas também ficam na fila para retry.
            sucesso = False
            erro_envio = f"{type(erro).__name__}: {erro}"[:500]
            logger.exception("Falha inesperada ao enviar o e-mail da fila %s.", email_id)

        with SessionLocal() as sessao:
            linha = sessao.get(EmailOutboxDB, email_id)
            if linha is None or linha.status != "pendente":
                continue
            if sucesso:
                linha.status = "enviado"
                linha.enviado_em = datetime.now(timezone.utc)
                linha.corpo = ""
                linha.assunto = "[mensagem enviada]"
                linha.ultimo_erro = None
                enviados += 1
            else:
                linha.tentativas += 1
                linha.ultimo_erro = (erro_envio or "Falha SMTP sem detalhe")[:500]
                falharam += 1
                if linha.tentativas >= max_tentativas:
                    linha.status = "falha_permanente"
                    linha.corpo = ""
                    linha.assunto = "[mensagem não enviada]"
                else:
                    linha.proxima_tentativa = datetime.now(timezone.utc) + timedelta(
                        seconds=atraso_retentativa_segundos(linha.tentativas)
                    )
            sessao.commit()

    return enviados, falharam
