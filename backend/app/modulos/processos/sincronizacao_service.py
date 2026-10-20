"""Execução idempotente da sincronização processual manual e automática."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

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
    MovimentacaoRegistro,
    ProcessoRegistro,
    ResultadoSincronizacao,
    ResultadoTriagem,
)
from .status_service import classificar_interesse, interpretar_movimentacao

logger = logging.getLogger(__name__)


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
        consultados += 1

        try:
            if not alias:
                alias = alias_datajud_por_numero(processo.dados.numero)
            consulta = await consultar_por_numero(processo.dados.numero, alias)
            fontes_consultadas = consulta.fontes_consultadas
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

                movimento_novo = candidato.ultima_movimentacao

                if movimento_novo and movimento_novo != processo.dados.ultima_movimentacao:
                    interpretacao = await interpretar_movimentacao(movimento_novo)
                    triagem_modelo = await classificar_interesse(
                        processo.dados.model_copy(
                            update={**dados_update, "ultima_movimentacao": movimento_novo}
                        ).model_dump(mode="json")
                    )
                    dados_update["ultima_movimentacao"] = movimento_novo
                    movimento = MovimentacaoRegistro(
                        texto=movimento_novo,
                        resumo=interpretacao.resumo,
                        categoria=interpretacao.categoria,
                        requer_atencao=interpretacao.requer_atencao,
                        fonte_url=candidato.fonte_url,
                        fonte_dados=consulta.fonte,
                        registrada_por="DJEN/CNJ" if consulta.fonte == "djen" else "DataJud",
                    )
                    atualizado = salvar(
                        sessao,
                        processo.model_copy(
                            update={
                                "dados": processo.dados.model_copy(update=dados_update),
                                "triagem": ResultadoTriagem.model_validate(triagem_modelo.model_dump()),
                                "movimentacoes": [*processo.movimentacoes, movimento],
                            }
                        ),
                        commit=False,
                    )
                    enfileirar_notificacao_processo(
                        sessao,
                        atualizado,
                        "Nova movimentação processual",
                        f"{interpretacao.resumo}\n\nMovimentação: {movimento_novo}",
                    )
                    sessao.commit()
                    movimentos_novos += 1
                    atualizacoes = 1
                elif dados_update:
                    salvar(
                        sessao,
                        processo.model_copy(update={"dados": processo.dados.model_copy(update=dados_update)}),
                    )
                status_sync = "encontrado"

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
