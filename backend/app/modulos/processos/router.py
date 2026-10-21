import logging
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from openai import APIConnectionError, APIError
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .auditoria_service import listar_auditoria_processo
from .auth import (
    UsuarioAtual,
    exigir_acesso_processos,
    exigir_advogado,
)
from .consulta_processual_service import consultar_por_numero
from .email_outbox import enfileirar_notificacao_processo
from .models import PermissaoProcessoDB, RegistroSincronizacao
from .numero_cnj import alias_datajud_por_numero
from .recursos_acesso import obter_processo_autorizado, registrar_auditoria
from .recursos_schemas import SincronizacaoSaida
from .repository import (
    adicionar,
    conceder_acesso_edicao_se_ausente,
    listar,
    obter,
    obter_por_numero,
    salvar,
)
from .schemas import (
    AlteracaoStatus,
    AuditoriaListaSaida,
    HistoricoStatus,
    MovimentacaoEntrada,
    MovimentacaoPublica,
    MovimentacaoRegistro,
    ProcessoCandidato,
    ProcessoRegistro,
    Relevancia,
    ResultadoSincronizacao,
    ResultadoTriagem,
    TriagemSolicitacaoSaida,
)
from .sincronizacao_service import sincronizar_processos
from .worker_locks import lock_distribuido
from .status_service import (
    classificar_interesse,
    interpretar_movimentacao,
    interpretar_movimentacao_publica,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/processos", tags=["Processos"])


def _erro_ml(erro: Exception) -> HTTPException:
    if isinstance(erro, APIConnectionError):
        return HTTPException(status_code=503, detail="O serviço local de ML está indisponível.")
    return HTTPException(
        status_code=502,
        detail="Não foi possível obter uma resposta estruturada do modelo local.",
    )


def _notificar(sessao: Session, processo: ProcessoRegistro, evento: str, detalhe: str) -> None:
    enfileirar_notificacao_processo(sessao, processo, evento, detalhe)


@router.get("", response_model=list[ProcessoRegistro])
def listar_processos(
    relevancia: Relevancia | None = Query(default=None),
    arquivado: bool = Query(default=False),
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> list[ProcessoRegistro]:
    """Lista apenas os processos aos quais o usuário possui permissão."""
    return listar(
        sessao,
        relevancia,
        arquivado=arquivado,
        usuario_id=int(usuario.id),
    )


@router.post("/sincronizar", response_model=ResultadoSincronizacao)
async def sincronizar_processos_provedores(
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ResultadoSincronizacao:
    """Atualiza pelos provedores configurados e limita a execução aos processos editáveis."""
    try:
        async with lock_distribuido("sincronizacao-processual") as adquirido:
            if not adquirido:
                raise HTTPException(status_code=409, detail="Já existe uma sincronização em andamento.")
            return await sincronizar_processos(sessao, usuario_id=int(usuario.id))
    except RuntimeError as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro


@router.post("/triagem", response_model=TriagemSolicitacaoSaida)
async def cadastrar_para_triagem(
    dados: ProcessoCandidato,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> TriagemSolicitacaoSaida:
    """Recebe a solicitação sem revelar se o processo já era acompanhado."""
    resposta_generica = TriagemSolicitacaoSaida(
        mensagem=(
            "Solicitação processada. Se o processo puder ser incluído no acompanhamento, "
            "ele aparecerá na sua lista."
        )
    )

    try:
        tribunal_alias = alias_datajud_por_numero(dados.numero)
    except ValueError as erro:
        raise HTTPException(status_code=422, detail=str(erro)) from erro

    try:
        consulta = await consultar_por_numero(dados.numero, tribunal_alias)
    except RuntimeError as erro:
        raise HTTPException(status_code=503, detail=str(erro)) from erro
    except httpx.HTTPStatusError as erro:
        logger.exception("Um provedor processual respondeu com erro ao consultar processo.")
        raise HTTPException(
            status_code=502,
            detail=f"Um provedor de consulta recusou ou não concluiu a busca (HTTP {erro.response.status_code}).",
        ) from erro
    except httpx.HTTPError as erro:
        logger.exception("Falha de comunicação com os provedores processuais.")
        raise HTTPException(status_code=502, detail="Não foi possível consultar os provedores agora.") from erro
    except ValueError as erro:
        logger.exception("Um provedor processual retornou dados inválidos.")
        raise HTTPException(status_code=502, detail="Um provedor retornou dados processuais inválidos.") from erro
    if consulta.falhas_fontes:
        logger.warning(
            "Triagem processual concluída parcialmente; fontes indisponíveis: %s",
            ",".join(consulta.falhas_fontes),
        )

    if consulta.processo is None:
        return resposta_generica

    dados = consulta.processo
    try:
        triagem_modelo = await classificar_interesse(dados.model_dump(mode="json"))
        eventos_publicos = dados.movimentacoes_publicas
        if not eventos_publicos and dados.ultima_movimentacao:
            eventos_publicos = [
                MovimentacaoPublica(
                    texto=dados.ultima_movimentacao,
                    fonte_url=dados.fonte_url,
                    fonte_dados=dados.origem_dados,
                )
            ]
        eventos_recentes = sorted(
            eventos_publicos,
            key=lambda evento: evento.data_fonte or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )[:10]
        movimentos = [
            await interpretar_movimentacao_publica(evento, dados.origem_dados or "datajud")
            for evento in sorted(
                eventos_recentes,
                key=lambda evento: evento.data_fonte or datetime.min.replace(tzinfo=timezone.utc),
            )
        ]
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
    processo_existente = obter_por_numero(sessao, dados.numero)
    if processo_existente is None:
        try:
            adicionar(sessao, registro)
        except IntegrityError as erro:
            sessao.rollback()
            restricao = getattr(getattr(erro.orig, "diag", None), "constraint_name", None)
            if restricao != "processo_numero_processo_key":
                raise
            logger.info("Cadastro concorrente de processo CNJ já inserido; resposta genérica mantida.")
    else:
        usuario_id = int(usuario.id)
        try:
            acesso_concedido = conceder_acesso_edicao_se_ausente(
                sessao,
                usuario_id=usuario_id,
                processo_id=int(processo_existente.id),
            )
            if acesso_concedido:
                registrar_auditoria(
                    sessao,
                    usuario_id=usuario_id,
                    processo_id=int(processo_existente.id),
                    operacao="acesso_processo_compartilhado",
                    descricao="Advogado vinculado a processo já cadastrado.",
                )
                sessao.commit()
        except IntegrityError as erro:
            restricao = getattr(getattr(erro.orig, "diag", None), "constraint_name", None)
            if restricao != "permissao_processo_id_usuario_id_processo_key":
                raise
            sessao.rollback()
            acesso_existente = sessao.scalar(
                select(PermissaoProcessoDB).where(
                    PermissaoProcessoDB.id_usuario == usuario_id,
                    PermissaoProcessoDB.id_processo == int(processo_existente.id),
                )
            )
            if acesso_existente is None:
                raise
    return resposta_generica


@router.get("/{processo_id}", response_model=ProcessoRegistro)
def detalhar_processo(
    processo_id: str,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> ProcessoRegistro:
    processo = obter(sessao, processo_id)
    if processo is None:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    obter_processo_autorizado(sessao, usuario, int(processo.id))
    return processo


@router.get("/{processo_id}/sincronizacoes", response_model=list[SincronizacaoSaida])
def listar_sincronizacoes_processo(
    processo_id: int,
    limite: int = Query(default=20, ge=1, le=100),
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> list[RegistroSincronizacao]:
    obter_processo_autorizado(sessao, usuario, processo_id)
    return list(
        sessao.scalars(
            select(RegistroSincronizacao)
            .where(RegistroSincronizacao.id_processo == processo_id)
            .order_by(RegistroSincronizacao.data_hora.desc())
            .limit(limite)
        ).all()
    )


@router.get("/{processo_id}/auditoria", response_model=AuditoriaListaSaida)
def listar_auditoria_de_processo(
    processo_id: int,
    limite: int = Query(default=50, ge=1, le=100),
    deslocamento: int = Query(default=0, ge=0),
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> AuditoriaListaSaida:
    """Lista o histórico só para usuários com permissão de leitura no processo."""
    obter_processo_autorizado(sessao, usuario, processo_id)
    return listar_auditoria_processo(
        sessao,
        processo_id,
        limite=limite,
        deslocamento=deslocamento,
    )


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
    obter_processo_autorizado(
        sessao, usuario, int(processo.id), edicao=True, permitir_arquivado=True
    )
    if processo.arquivado:
        raise HTTPException(status_code=409, detail="Desarquive o processo antes de registrar movimentações.")
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
        fonte_dados="manual",
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
        commit=False,
    )
    _notificar(
        sessao,
        atualizado,
        "Nova movimentação processual",
        f"{interpretacao.resumo}\n\nMovimentação: {entrada.texto}",
    )
    sessao.commit()
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
    obter_processo_autorizado(
        sessao, usuario, int(processo.id), edicao=True, permitir_arquivado=True
    )
    if processo.arquivado:
        raise HTTPException(status_code=409, detail="Desarquive o processo antes de alterar o status.")
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
        commit=False,
    )
    detalhe = f"Status anterior: {processo.status}\nNovo status: {atualizado.status}"
    if alteracao.observacao:
        detalhe += f"\nObservação: {alteracao.observacao}"
    _notificar(sessao, atualizado, "Status processual atualizado", detalhe)
    sessao.commit()
    return atualizado


@router.post("/{processo_id}/arquivar", response_model=ProcessoRegistro)
def arquivar_processo(
    processo_id: int,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ProcessoRegistro:
    """Arquiva explicitamente um processo encerrado; exige permissão de edição."""
    processo, _permissao = obter_processo_autorizado(
        sessao, usuario, processo_id, edicao=True, permitir_arquivado=True
    )
    if processo.arquivado:
        return obter(sessao, str(processo_id))
    if processo.status != "encerrado":
        raise HTTPException(
            status_code=409,
            detail="Somente processos com status encerrado podem ser arquivados.",
        )

    processo.arquivado = True
    processo.atualizado_em = datetime.now(timezone.utc)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=processo.id_processo,
        operacao="processo_arquivado",
        descricao="Processo arquivado pelo advogado responsável.",
        dados={"status": processo.status},
    )
    sessao.commit()
    return obter(sessao, str(processo_id))


@router.post("/{processo_id}/desarquivar", response_model=ProcessoRegistro)
def desarquivar_processo(
    processo_id: int,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ProcessoRegistro:
    """Reativa o acompanhamento; apenas advogado com permissão de edição pode fazê-lo."""
    processo, _permissao = obter_processo_autorizado(
        sessao, usuario, processo_id, edicao=True, permitir_arquivado=True
    )
    if not processo.arquivado:
        return obter(sessao, str(processo_id))

    processo.arquivado = False
    processo.atualizado_em = datetime.now(timezone.utc)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=processo.id_processo,
        operacao="processo_desarquivado",
        descricao="Processo desarquivado pelo advogado responsável.",
        dados={"status": processo.status},
    )
    sessao.commit()
    return obter(sessao, str(processo_id))


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
