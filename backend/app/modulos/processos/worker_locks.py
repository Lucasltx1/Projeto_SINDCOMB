"""Locks Redis para impedir execuções duplicadas em múltiplos processos da API."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import logging
import os
from collections.abc import AsyncIterator

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


async def _renovar(lock, intervalo: int) -> None:
    while True:
        await asyncio.sleep(max(5, intervalo // 3))
        if not await lock.extend(intervalo, replace_ttl=True):
            raise RuntimeError("O lock distribuído foi perdido durante a execução.")


@asynccontextmanager
async def lock_distribuido(nome: str, *, timeout: int = 900) -> AsyncIterator[bool]:
    """Adquire lease Redis e renova-o enquanto a tarefa estiver em execução."""
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    cliente = Redis.from_url(url, decode_responses=True)
    lock = cliente.lock(f"sindcomb:lock:{nome}", timeout=timeout, blocking_timeout=0)
    adquirido = False
    tarefa_renovacao: asyncio.Task[None] | None = None
    try:
        adquirido = await lock.acquire(blocking=False)
    except RedisError as erro:
        logger.exception("Redis indisponível para adquirir o lock %s.", nome)
        await cliente.aclose()
        raise RuntimeError("Redis está indisponível para coordenar a sincronização.") from erro
    if adquirido:
        tarefa_renovacao = asyncio.create_task(_renovar(lock, timeout))
    try:
        yield adquirido
    finally:
        if tarefa_renovacao is not None:
            tarefa_renovacao.cancel()
            try:
                await tarefa_renovacao
            except asyncio.CancelledError:
                pass
            except (RedisError, RuntimeError):
                logger.warning("O lease Redis da tarefa %s expirou antes da liberação.", nome)
        if adquirido:
            try:
                await lock.release()
            except RedisError:
                logger.warning("Não foi possível liberar o lock Redis %s.", nome, exc_info=True)
        try:
            await cliente.aclose()
        except RedisError:
            logger.debug("Falha ao fechar a conexão Redis do lock %s.", nome, exc_info=True)
