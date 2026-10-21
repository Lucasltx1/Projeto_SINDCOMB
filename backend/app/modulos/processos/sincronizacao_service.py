"""Execução idempotente da sincronização processual manual e automática."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
import unicodedata

import httpx
from openai import APIConnectionError, APIError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .consulta_processual_service import consultar_por_numero
from .email_outbox import enfileirar_notificacao_processo
from .models import PermissaoProcessoDB, RegistroSincronizacao
from .numero_cnj import alias_datajud_por_numero
from .repository import listar, salvar
from .schemas import (
    MovimentacaoPublica,
    ProcessoRegistro,
    ResultadoSincronizacao,
    ResultadoTriagem,
)
from .status_service import classificar_interesse, interpretar_movimentacao_publica

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
    import os

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

    consultados = 0
    movimentos_novos = 0
    falhas: list[str] = []
    for processo in processos:
        alias = (processo.dados.tribunal_alias or "").strip().lower()
        erro_texto: str | None = None
        atualizacoes = 0
        encontrado = False
        fonte_encontrada: str | None = None
        fontes_consultadas: tuple[str, ...] = ("datajud",)
        falhas_fontes: tuple[str, ...] = ()
        consultados += 1

        try:
            if not alias:
                alias = alias_datajud_por_numero(processo.dados.numero)
            consulta = await consultar_por_numero(processo.dados.numero, alias)
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
