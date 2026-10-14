import asyncio
from datetime import datetime, timezone
import logging
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from openai import APIConnectionError, APIError
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .auth import (
    UsuarioAtual,
    exigir_acesso_processos,
    exigir_advogado,
)
from .datajud_service import buscar_por_numero, extrair_atualizacao, extrair_candidato_datajud
from .email_service import enviar_email
from .models import RegistroSincronizacao
from .numero_cnj import alias_datajud_por_numero, numero_cnj_sem_formatacao
from .repository import (
    adicionar,
    listar,
    listar_emails_envolvidos,
    obter,
    obter_por_numero,
    salvar,
)
from .schemas import (
    AlteracaoStatus,
    HistoricoStatus,
    MovimentacaoEntrada,
    MovimentacaoRegistro,
    ProcessoCandidato,
    ProcessoRegistro,
    Relevancia,
    ResultadoSincronizacao,
    ResultadoTriagem,
)
from .status_service import classificar_interesse, interpretar_movimentacao

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/processos", tags=["Processos"])


def _erro_ml(erro: Exception) -> HTTPException:
    if isinstance(erro, APIConnectionError):
        return HTTPException(status_code=503, detail="O serviço local de ML está indisponível.")
    return HTTPException(
        status_code=502,
        detail="Não foi possível obter uma resposta estruturada do modelo local.",
    )


def _assunto_notificacao(processo: ProcessoRegistro, evento: str) -> str:
    return f"SINDCOMB — {evento} no processo {processo.dados.numero}"


def _corpo_notificacao(processo: ProcessoRegistro, evento: str, detalhe: str) -> str:
    return (
        "O sistema de acompanhamento processual identificou uma atualização.\n\n"
        f"Processo: {processo.dados.numero}\n"
        f"Tribunal: {processo.dados.tribunal}\n"
        f"Evento: {evento}\n"
        f"Status atual: {processo.status}\n\n"
        f"Detalhes:\n{detalhe}\n"
    )


def _notificar(sessao: Session, processo: ProcessoRegistro, evento: str, detalhe: str) -> bool:
    destinatarios = listar_emails_envolvidos(sessao, processo.id)
    if not destinatarios:
        return True
    enviado = enviar_email(
        destinatarios,
        _assunto_notificacao(processo, evento),
        _corpo_notificacao(processo, evento, detalhe),
    )
    if not enviado:
        logger.warning("Notificação de atualização não enviada para o processo %s.", processo.id)
    return enviado


async def _notificar_async(
    sessao: Session,
    processo: ProcessoRegistro,
    evento: str,
    detalhe: str,
) -> bool:
    destinatarios = listar_emails_envolvidos(sessao, processo.id)
    if not destinatarios:
        return True
    enviado = await asyncio.to_thread(
        enviar_email,
        destinatarios,
        _assunto_notificacao(processo, evento),
        _corpo_notificacao(processo, evento, detalhe),
    )
    if not enviado:
        logger.warning("Notificação de atualização não enviada para o processo %s.", processo.id)
    return enviado


@router.get("", response_model=list[ProcessoRegistro])
def listar_processos(
    relevancia: Relevancia | None = Query(default=None),
    _usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> list[ProcessoRegistro]:
    """Advogados e visualizadores consultam os processos; administradores não têm acesso."""
    return listar(sessao, relevancia)


@router.post("/sincronizar", response_model=ResultadoSincronizacao)
async def sincronizar_datajud(
    _usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ResultadoSincronizacao:
    """Atualiza processos cadastrados consultando o DataJud pelo número CNJ."""
    processos = listar(sessao)
    if not processos:
        return ResultadoSincronizacao(processos_consultados=0, processos_com_movimentacao_nova=0)

    import os

    if not os.getenv("DATAJUD_API_KEY", "").strip():
        raise HTTPException(status_code=503, detail="Configure DATAJUD_API_KEY para consultar o DataJud.")

    consultados = movimentos_novos = 0
    falhas: list[str] = []
    aliases = {"tjrj": "tjrj", "trf2": "trf2", "trt1": "trt1", "stj": "stj", "tst": "tst"}
    for processo in processos:
        alias = (processo.dados.tribunal_alias or aliases.get(processo.dados.tribunal.lower(), "")).lower()
        if not alias:
            falhas.append(f"{processo.dados.numero}: informe tribunal_alias (por exemplo, tjrj).")
            continue
        consultados += 1
        encontrado = False
        erro_texto = None
        atualizacoes = 0
        try:
            fontes = await buscar_por_numero(processo.dados.numero, alias)
            if fontes:
                encontrado = True
                atualizacao = extrair_atualizacao(fontes[0])
                movimento_novo = atualizacao.get("ultima_movimentacao")
                dados_update: dict[str, object] = {}
                if atualizacao.get("classe"):
                    dados_update["classe"] = atualizacao["classe"]
                if atualizacao.get("assunto"):
                    dados_update["assunto"] = atualizacao["assunto"]

                if movimento_novo and movimento_novo != processo.dados.ultima_movimentacao:
                    try:
                        interpretacao = await interpretar_movimentacao(movimento_novo)
                        triagem_modelo = await classificar_interesse(
                            processo.dados.model_copy(
                                update={**dados_update, "ultima_movimentacao": movimento_novo}
                            ).model_dump(mode="json")
                        )
                    except (APIConnectionError, APIError, ValidationError, ValueError) as erro:
                        erro_texto = f"Falha na análise do agente ({type(erro).__name__})"
                        falhas.append(
                            f"{processo.dados.numero}: movimentação encontrada, mas a análise de IA falhou."
                        )
                    else:
                        dados_update["ultima_movimentacao"] = movimento_novo
                        movimento = MovimentacaoRegistro(
                            texto=movimento_novo,
                            resumo=interpretacao.resumo,
                            categoria=interpretacao.categoria,
                            requer_atencao=interpretacao.requer_atencao,
                            registrada_por="DataJud",
                        )
                        atualizado = processo.model_copy(
                            update={
                                "dados": processo.dados.model_copy(update=dados_update),
                                "triagem": ResultadoTriagem.model_validate(triagem_modelo.model_dump()),
                                "movimentacoes": [*processo.movimentacoes, movimento],
                            }
                        )
                        atualizado = salvar(sessao, atualizado)
                        movimentos_novos += 1
                        atualizacoes += 1
                        if not await _notificar_async(
                            sessao,
                            atualizado,
                            "Nova movimentação processual",
                            f"{interpretacao.resumo}\n\nMovimentação: {movimento_novo}",
                        ):
                            falhas.append(f"{processo.dados.numero}: movimentação salva, mas o e-mail falhou.")
                elif dados_update:
                    atualizado = salvar(
                        sessao,
                        processo.model_copy(update={"dados": processo.dados.model_copy(update=dados_update)}),
                    )
                    processo = atualizado

        except httpx.HTTPStatusError as erro:
            erro_texto = f"HTTP {erro.response.status_code}"
            falhas.append(f"{processo.dados.numero}: consulta DataJud falhou ({erro_texto}).")
        except (httpx.HTTPError, RuntimeError, ValueError) as erro:
            erro_texto = type(erro).__name__
            falhas.append(f"{processo.dados.numero}: consulta DataJud falhou ({erro_texto}).")

        status_sync = "falha" if erro_texto else ("encontrado" if encontrado else "nao_encontrado")
        sessao.add(
            RegistroSincronizacao(
                id_processo=int(processo.id),
                data_hora=datetime.now(timezone.utc),
                status=status_sync,
                descricao=f"numero={processo.dados.numero}; tribunal={alias}; erro={erro_texto or 'nenhum'}",
                quantidade_atualizacoes=atualizacoes,
            )
        )
        sessao.commit()

    return ResultadoSincronizacao(
        processos_consultados=consultados,
        processos_com_movimentacao_nova=movimentos_novos,
        falhas=falhas[:50],
    )


@router.post("/triagem", response_model=ProcessoRegistro, status_code=status.HTTP_201_CREATED)
async def cadastrar_para_triagem(
    dados: ProcessoCandidato,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ProcessoRegistro:
    """Advogado informa o número CNJ; DataJud localiza os dados para a triagem por IA."""
    existente = obter_por_numero(sessao, dados.numero)
    if existente:
        raise HTTPException(status_code=409, detail="Esse processo já está cadastrado.")

    try:
        tribunal_alias = alias_datajud_por_numero(dados.numero)
        fontes = await buscar_por_numero(dados.numero, tribunal_alias)
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro
    except RuntimeError as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro
    except httpx.HTTPStatusError as erro:
        logger.exception("DataJud respondeu com erro ao consultar processo.")
        raise HTTPException(
            status_code=502,
            detail=f"O DataJud recusou ou não concluiu a consulta (HTTP {erro.response.status_code}).",
        ) from erro
    except httpx.HTTPError as erro:
        logger.exception("Falha de comunicação com o DataJud.")
        raise HTTPException(status_code=502, detail="Não foi possível consultar o DataJud agora.") from erro

    numero_digitos = numero_cnj_sem_formatacao(dados.numero)
    fonte = next(
        (
            item
            for item in fontes
            if item.get("numeroProcesso")
            and numero_cnj_sem_formatacao(str(item["numeroProcesso"])) == numero_digitos
        ),
        None,
    )
    if fonte is None:
        raise HTTPException(
            status_code=404,
            detail="O processo não foi localizado no DataJud. Confira o número e tente novamente.",
        )

    dados = extrair_candidato_datajud(fonte, dados.numero, tribunal_alias)
    try:
        triagem_modelo = await classificar_interesse(dados.model_dump(mode="json"))
        movimentos: list[MovimentacaoRegistro] = []
        if dados.ultima_movimentacao:
            interpretacao = await interpretar_movimentacao(dados.ultima_movimentacao)
            movimentos.append(
                MovimentacaoRegistro(
                    texto=dados.ultima_movimentacao,
                    resumo=interpretacao.resumo,
                    categoria=interpretacao.categoria,
                    requer_atencao=interpretacao.requer_atencao,
                    fonte_url=dados.fonte_url,
                    registrada_por=usuario.id,
                )
            )
    except (APIConnectionError, APIError, ValidationError, ValueError) as erro:
        raise _erro_ml(erro) from erro

    registro = ProcessoRegistro(
        id="0",
        dados=dados,
        triagem=ResultadoTriagem.model_validate(triagem_modelo.model_dump()),
        criado_por=usuario.id,
        movimentacoes=movimentos,
        historico_status=[HistoricoStatus(de=None, para="novo", alterado_por=usuario.id, observacao="Cadastro inicial")],
    )
    return adicionar(sessao, registro)


@router.get("/{processo_id}", response_model=ProcessoRegistro)
def detalhar_processo(
    processo_id: str,
    _usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> ProcessoRegistro:
    processo = obter(sessao, processo_id)
    if processo is None:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    return processo


@router.post("/{processo_id}/movimentacoes", response_model=ProcessoRegistro)
async def registrar_movimentacao(
    processo_id: str,
    entrada: MovimentacaoEntrada,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ProcessoRegistro:
    """Registra uma movimentação e notifica por e-mail as partes vinculadas."""
    processo = obter(sessao, processo_id)
    if processo is None:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    try:
        interpretacao = await interpretar_movimentacao(entrada.texto)
    except (APIConnectionError, APIError, ValidationError, ValueError) as erro:
        raise _erro_ml(erro) from erro

    movimento = MovimentacaoRegistro(
        texto=entrada.texto,
        resumo=interpretacao.resumo,
        categoria=interpretacao.categoria,
        requer_atencao=interpretacao.requer_atencao,
        fonte_url=entrada.fonte_url,
        registrada_por=usuario.id,
    )
    dados_atualizados = processo.dados.model_copy(
        update={"ultima_movimentacao": entrada.texto, "fonte_url": entrada.fonte_url or processo.dados.fonte_url}
    )
    atualizado = salvar(
        sessao,
        processo.model_copy(
            update={"dados": dados_atualizados, "movimentacoes": [*processo.movimentacoes, movimento]}
        ),
    )
    _notificar(
        sessao,
        atualizado,
        "Nova movimentação processual",
        f"{interpretacao.resumo}\n\nMovimentação: {entrada.texto}",
    )
    return atualizado


@router.patch("/{processo_id}/status", response_model=ProcessoRegistro)
def alterar_status(
    processo_id: str,
    alteracao: AlteracaoStatus,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ProcessoRegistro:
    """Somente advogado altera status; partes vinculadas recebem aviso por e-mail."""
    processo = obter(sessao, processo_id)
    if processo is None:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    if processo.status == alteracao.status:
        return processo

    historico = HistoricoStatus(
        de=processo.status,
        para=alteracao.status,
        alterado_por=usuario.id,
        observacao=alteracao.observacao,
    )
    atualizado = salvar(
        sessao,
        processo.model_copy(
            update={
                "status": alteracao.status,
                "historico_status": [*processo.historico_status, historico],
            }
        ),
    )
    detalhe = f"Status anterior: {processo.status}\nNovo status: {atualizado.status}"
    if alteracao.observacao:
        detalhe += f"\nObservação: {alteracao.observacao}"
    _notificar(sessao, atualizado, "Status processual atualizado", detalhe)
    return atualizado


@router.post("/interpretar-movimentacao")
async def interpretar_avulsa(
    pedido: MovimentacaoEntrada,
    _usuario: UsuarioAtual = Depends(exigir_acesso_processos),
) -> dict[str, str | bool]:
    try:
        resultado = await interpretar_movimentacao(pedido.texto)
    except (APIConnectionError, APIError, ValidationError, ValueError) as erro:
        raise _erro_ml(erro) from erro
    return resultado.model_dump()
