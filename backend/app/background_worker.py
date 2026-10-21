"""Workers leves de sincronização periódica e envio da fila de e-mails."""

from __future__ import annotations

import asyncio
import logging
import os
import time

from app.modulos.processos.email_outbox import processar_email_outbox
from app.modulos.processos.prazos_service import processar_lembretes_prazo
from app.modulos.processos.sincronizacao_service import sincronizar_processos
from app.modulos.processos.worker_locks import lock_distribuido
from app.nucleo.database import SessionLocal

logger = logging.getLogger(__name__)


def _inteiro_ambiente(nome: str, padrao: int, minimo: int, maximo: int) -> int:
    try:
        valor = int(os.getenv(nome, str(padrao)))
    except ValueError:
        valor = padrao
    return min(max(valor, minimo), maximo)


async def _executar_sincronizacao_automatica() -> bool:
    async with lock_distribuido("sincronizacao-processual") as adquirido:
        if not adquirido:
            return False
        with SessionLocal() as sessao:
            resultado = await sincronizar_processos(sessao)
    if resultado.falhas:
        logger.warning(
            "Sincronização processual concluiu com %s falha(s); %s processo(s) tiveram movimentação nova.",
            len(resultado.falhas),
            resultado.processos_com_movimentacao_nova,
        )
        return True
    logger.info(
        "Sincronização processual: %s processo(s) consultado(s), %s movimentação(ões) nova(s).",
        resultado.processos_consultados,
        resultado.processos_com_movimentacao_nova,
    )
    return False


async def executar_workers() -> None:
    """Loop iniciado no lifespan da API; a fila usa DB leases e a sync usa Redis lock."""
    intervalo_sync = _inteiro_ambiente("SINDCOMB_SYNC_INTERVAL_MINUTES", 60, 5, 1440) * 60
    intervalo_falha = _inteiro_ambiente("SINDCOMB_SYNC_FAILURE_RETRY_MINUTES", 5, 1, 60) * 60
    atraso_inicio = _inteiro_ambiente("SINDCOMB_SYNC_INITIAL_DELAY_SECONDS", 30, 0, 3600)
    intervalo_worker = _inteiro_ambiente("SINDCOMB_WORKER_POLL_SECONDS", 15, 5, 300)
    proxima_sync = time.monotonic() + atraso_inicio
    proxima_verificacao_prazos = time.monotonic() + atraso_inicio
    intervalo_lembretes = _inteiro_ambiente(
        "SINDCOMB_DEADLINE_REMINDER_INTERVAL_SECONDS", 300, 60, 3600
    )

    while True:
        try:
            enviados, falhas = await processar_email_outbox()
            if enviados or falhas:
                logger.info("Fila de e-mails: %s enviado(s), %s tentativa(s) falha(s).", enviados, falhas)
        except Exception:
            logger.exception("Falha ao processar a fila persistente de e-mails.")

        agora = time.monotonic()
        if agora >= proxima_verificacao_prazos:
            try:
                async with lock_distribuido("lembretes-prazo", timeout=300) as adquirido:
                    if adquirido:
                        with SessionLocal() as sessao:
                            quantidade = processar_lembretes_prazo(sessao)
                        if quantidade:
                            logger.info("Lembretes de prazo registrados: %s.", quantidade)
            except Exception:
                logger.exception("Falha ao processar lembretes de prazo.")
            proxima_verificacao_prazos = time.monotonic() + intervalo_lembretes

        if agora >= proxima_sync:
            if not os.getenv("DATAJUD_API_KEY", "").strip():
                logger.warning("Sincronização automática suspensa: DATAJUD_API_KEY não configurada.")
                proxima_sync = agora + intervalo_sync
            else:
                try:
                    teve_falha = await _executar_sincronizacao_automatica()
                    proxima_sync = time.monotonic() + (intervalo_falha if teve_falha else intervalo_sync)
                except Exception:
                    logger.exception("Falha inesperada na sincronização processual automática.")
                    proxima_sync = time.monotonic() + intervalo_falha

        await asyncio.sleep(intervalo_worker)
