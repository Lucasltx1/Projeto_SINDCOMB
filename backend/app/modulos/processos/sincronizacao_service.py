"""Execução idempotente da sincronização processual manual e automática."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone
import hashlib
import logging
import os
import re
import unicodedata

import httpx
from openai import APIConnectionError, APIError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .consulta_processual_service import ConsultaProcessual, consultar_por_numero
from .email_outbox import enfileirar_notificacao_processo
from .models import PermissaoProcessoDB, RegistroSincronizacao
from .notificacoes_service import notificar_usuarios_do_processo
from .numero_cnj import alias_datajud_por_numero
from .repository import listar, salvar
from .schemas import (
    MovimentacaoPublica,
    ProcessoRegistro,
    ResultadoSincronizacao,
    ResultadoTriagem,
)
from .status_service import classificar_interesse, interpretar_movimentacao_publica
from .sugestoes_prazo_service import sugerir_prazos_de_movimentacoes

logger = logging.getLogger(__name__)
_PREFIXO_DATA_DJEN = re.compile(r"^disponibilizada em .+? — ", re.IGNORECASE)


def _normalizar_texto_movimentacao(texto: str) -> str:
    sem_data = _PREFIXO_DATA_DJEN.sub("", texto.strip())
    normalizado = unicodedata.normalize("NFKD", sem_data.casefold())
    sem_acentos = "".join(
        caractere
        for caractere in normalizado
        if not unicodedata.combining(caractere)
    )
    return " ".join(sem_acentos.split())


def _chave_movimentacao(movimento: MovimentacaoPublica) -> tuple[str, str | None]:
    return (
        _normalizar_texto_movimentacao(movimento.texto),
        movimento.data_fonte.isoformat() if movimento.data_fonte else None,
    )


async def sincronizar_processos(
    sessao: Session,
    *,
    usuario_id: int | None = None,
) -> ResultadoSincronizacao:
    """Consulta processos; chamadas de advogado são limitadas aos seus processos editáveis."""
    if not os.getenv("DATAJUD_API_KEY", "").strip():
        raise RuntimeError("Configure DATAJUD_API_KEY para consultar o DataJud.")

    processos = listar(sessao)
    if usuario_id is not None:
        ids_autorizados = set(
            sessao.scalars(
                select(PermissaoProcessoDB.id_processo).where(
                    PermissaoProcessoDB.id_usuario == usuario_id,
                    PermissaoProcessoDB.nivel_acesso.in_(("edicao", "total")),
                )
            ).all()
        )
        processos = [processo for processo in processos if int(processo.id) in ids_autorizados]

    try:
        limite_concorrencia = int(os.getenv("SINDCOMB_SYNC_MAX_CONCURRENCY", "3"))
    except ValueError:
        limite_concorrencia = 3
    limite_concorrencia = min(max(limite_concorrencia, 1), 5)
    semaforo = asyncio.Semaphore(limite_concorrencia)

    async def consultar_limitado(
        processo: ProcessoRegistro,
    ) -> tuple[str, ConsultaProcessual | None, Exception | None]:
        alias = (processo.dados.tribunal_alias or "").strip().lower()
        try:
            if not alias:
                alias = alias_datajud_por_numero(processo.dados.numero)
            async with semaforo:
                consulta = await consultar_por_numero(processo.dados.numero, alias)
            return alias, consulta, None
        except Exception as erro:
            return alias, None, erro

    async def iterar_consultas() -> AsyncIterator[
        tuple[ProcessoRegistro, tuple[str, ConsultaProcessual | None, Exception | None]]
    ]:
        for inicio in range(0, len(processos), limite_concorrencia):
            lote = processos[inicio : inicio + limite_concorrencia]
            consultas = await asyncio.gather(
                *(consultar_limitado(processo) for processo in lote)
            )
            for processo, resultado in zip(lote, consultas):
                yield processo, resultado

    consultados = 0
    movimentos_novos = 0
    falhas: list[str] = []
    async for processo, (alias, consulta, erro_consulta) in iterar_consultas():
        erro_texto: str | None = None
        atualizacoes = 0
        encontrado = False
        fonte_encontrada: str | None = None
        eventos_novos_disponiveis = 0
        fontes_consultadas: tuple[str, ...] = ("datajud",)
        falhas_fontes: tuple[str, ...] = ()
        consultados += 1

        try:
            if erro_consulta is not None:
                raise erro_consulta
            assert consulta is not None
            fontes_consultadas = consulta.fontes_consultadas
            falhas_fontes = consulta.falhas_fontes
            candidato = consulta.processo
            fonte_encontrada = consulta.fonte
            if candidato is None:
                status_sync = "nao_encontrado"
            else:
                encontrado = True
                dados_update: dict[str, object] = {
                    "origem_dados": consulta.fonte,
                    "consultado_em": consulta.consultado_em,
                    "data_ultima_verificacao_fonte": candidato.data_ultima_verificacao_fonte,
                    "fonte_url": candidato.fonte_url,
                    "cobertura_consulta": consulta.cobertura_consulta or candidato.cobertura_consulta,
                }
                if candidato.tribunal:
                    dados_update["tribunal"] = candidato.tribunal
                if candidato.classe:
                    dados_update["classe"] = candidato.classe
                if candidato.assunto != "Assunto não informado":
                    dados_update["assunto"] = candidato.assunto

                eventos_publicos = list(candidato.movimentacoes_publicas)
                if not eventos_publicos and candidato.ultima_movimentacao:
                    eventos_publicos.append(
                        MovimentacaoPublica(
                            texto=candidato.ultima_movimentacao,
                            fonte_url=candidato.fonte_url,
                            fonte_dados=consulta.fonte,
                        )
                    )
                sugerir_prazos_de_movimentacoes(
                    sessao,
                    int(processo.id),
                    eventos_publicos,
                )

                chaves_existentes = {
                    _chave_movimentacao(
                        MovimentacaoPublica(
                            texto=movimento.texto,
                            data_fonte=movimento.data_fonte,
                            fonte_dados=movimento.fonte_dados,
                        )
                    )
                    for movimento in processo.movimentacoes
                }
                textos_legados_sem_data = {
                    _normalizar_texto_movimentacao(movimento.texto)
                    for movimento in processo.movimentacoes
                    if movimento.data_fonte is None
                    and movimento.fonte_dados in {"datajud", "djen"}
                }
                novos_por_chave: dict[tuple[str, str | None], MovimentacaoPublica] = {}
                for evento in eventos_publicos:
                    chave = _chave_movimentacao(evento)
                    if chave in chaves_existentes:
                        continue
                    if chave[1] is not None and chave[0] in textos_legados_sem_data:
                        continue
                    novos_por_chave.setdefault(chave, evento)

                eventos_novos_disponiveis = len(novos_por_chave)
                eventos_recentes = sorted(
                    novos_por_chave.values(),
                    key=lambda evento: evento.data_fonte or datetime.min.replace(tzinfo=timezone.utc),
                    reverse=True,
                )[:10]
                eventos_recentes.sort(
                    key=lambda evento: evento.data_fonte or datetime.min.replace(tzinfo=timezone.utc)
                )
                novos_movimentos = [
                    await interpretar_movimentacao_publica(evento, consulta.fonte or "datajud")
                    for evento in eventos_recentes
                ]

                movimento_novo = candidato.ultima_movimentacao
                triagem = processo.triagem
                if movimento_novo and movimento_novo != processo.dados.ultima_movimentacao:
                    triagem_modelo = await classificar_interesse(
                        processo.dados.model_copy(
                            update={**dados_update, "ultima_movimentacao": movimento_novo}
                        ).model_dump(mode="json")
                    )
                    triagem = ResultadoTriagem.model_validate(triagem_modelo.model_dump())
                    dados_update["ultima_movimentacao"] = movimento_novo

                atualizado = salvar(
                    sessao,
                    processo.model_copy(
                        update={
                            "dados": processo.dados.model_copy(update=dados_update),
                            "triagem": triagem,
                            "movimentacoes": [*processo.movimentacoes, *novos_movimentos],
                        }
                    ),
                    commit=False,
                )
                if novos_movimentos:
                    resumo_notificacao = "\n\n".join(
                        f"{movimento.data_fonte.isoformat() + ' — ' if movimento.data_fonte else ''}"
                        f"Fonte: {movimento.fonte_dados or 'não informada'}\n"
                        f"{movimento.resumo}\nMovimentação: {movimento.texto}"
                        for movimento in novos_movimentos
                    )
                    enfileirar_notificacao_processo(
                        sessao,
                        atualizado,
                        "Novas movimentações processuais",
                        resumo_notificacao,
                    )
                    chave_eventos = hashlib.sha256(
                        "\n".join(
                            f"{evento.data_fonte.isoformat() if evento.data_fonte else ''}:"
                            f"{evento.fonte_dados or ''}:{_normalizar_texto_movimentacao(evento.texto)}"
                            for evento in eventos_recentes
                        ).encode("utf-8")
                    ).hexdigest()
                    notificar_usuarios_do_processo(
                        sessao,
                        int(processo.id),
                        categoria="movimentacao_processual",
                        titulo="Nova movimentação processual",
                        mensagem=resumo_notificacao[:10000],
                        chave=f"movimentacoes:{chave_eventos}",
                    )
                    movimentos_novos += 1
                    atualizacoes = len(novos_movimentos)
                sessao.commit()
                status_sync = "encontrado"
                if falhas_fontes:
                    erro_texto = "; ".join(falhas_fontes)
                    falhas.append(
                        f"{processo.dados.numero}: consulta parcial; fonte(s) indisponível(is): "
                        f"{','.join(falhas_fontes)}."
                    )

        except httpx.HTTPStatusError as erro:
            sessao.rollback()
            erro_texto = f"HTTP {erro.response.status_code}"
            falhas.append(f"{processo.dados.numero}: consulta processual falhou ({erro_texto}).")
            status_sync = "falha"
        except (httpx.HTTPError, APIConnectionError, APIError, ValidationError, RuntimeError, ValueError) as erro:
            sessao.rollback()
            erro_texto = f"{type(erro).__name__}: {erro}"[:400]
            falhas.append(f"{processo.dados.numero}: sincronização falhou ({type(erro).__name__}).")
            status_sync = "falha"
        except Exception as erro:
            sessao.rollback()
            logger.exception("Erro inesperado ao sincronizar o processo %s.", processo.id)
            erro_texto = f"Erro interno: {type(erro).__name__}"[:400]
            falhas.append(f"{processo.dados.numero}: sincronização falhou (erro interno).")
            status_sync = "falha"

        sessao.add(
            RegistroSincronizacao(
                id_processo=int(processo.id),
                data_hora=datetime.now(timezone.utc),
                status=status_sync,
                descricao=(
                    f"numero={processo.dados.numero}; tribunal={alias}; "
                    f"encontrado={encontrado}; fonte={fonte_encontrada or 'nenhuma'}; "
                    f"fontes_consultadas={','.join(fontes_consultadas)}; "
                    f"fontes_com_falha={','.join(falhas_fontes) or 'nenhuma'}; "
                    f"cobertura={consulta.cobertura_consulta if encontrado and consulta else {}}; "
                    f"eventos_novos_disponiveis={eventos_novos_disponiveis}; "
                    f"erro={erro_texto or 'nenhum'}"
                ),
                quantidade_atualizacoes=atualizacoes,
            )
        )
        sessao.commit()

    return ResultadoSincronizacao(
        processos_consultados=consultados,
        processos_com_movimentacao_nova=movimentos_novos,
        falhas=falhas[:50],
    )
