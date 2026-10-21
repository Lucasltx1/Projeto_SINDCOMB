from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .auth import UsuarioAtual, exigir_acesso_processos, exigir_advogado
from .models import (
    AssociadoDB,
    DocumentoDB,
    JuridicoDB,
    ModeloPeticaoDB,
    PeticaoComentarioDB,
    PeticaoDB,
    PeticaoProtocoloDB,
    PeticaoRevisorDB,
    PermissaoProcessoDB,
    ProcessoAssociadoDB,
    ProcessoDB,
    UsuarioDB,
    VersaoPeticaoDB,
)
from .notificacoes_service import notificar_usuarios_do_processo
from .recursos_acesso import obter_processo_autorizado, registrar_auditoria
from .recursos_schemas import (
    ModeloPeticaoAtualizacao,
    ModeloPeticaoEntrada,
    ModeloPeticaoSaida,
    PeticaoComentarioAtualizacao,
    PeticaoComentarioEntrada,
    PeticaoComentarioResolucao,
    PeticaoComentarioSaida,
    PeticaoAtualizacao,
    PeticaoCriacao,
    PeticaoProtocoloEntrada,
    PeticaoProtocoloSaida,
    PeticaoRevisorEntrada,
    PeticaoRevisorSaida,
    PeticaoSaida,
    PeticaoStatusEntrada,
    VersaoPeticaoSaida,
)
from .recursos_service import gerar_docx, gerar_pdf, renderizar_modelo

router = APIRouter(tags=["Petições"])

_TRANSICOES_STATUS = {
    "rascunho": {"em_revisao"},
    "em_revisao": {"rejeitada", "aprovada"},
    "rejeitada": {"em_revisao"},
    "aprovada": set(),
    "protocolada": set(),
}


def _versao_atual(sessao: Session, peticao_id: int) -> VersaoPeticaoDB | None:
    return sessao.scalar(
        select(VersaoPeticaoDB)
        .where(VersaoPeticaoDB.id_peticao == peticao_id)
        .order_by(VersaoPeticaoDB.numero_versao.desc())
        .limit(1)
    )


def _saida_peticao(sessao: Session, peticao: PeticaoDB) -> PeticaoSaida:
    versao = _versao_atual(sessao, peticao.id_peticao)
    return PeticaoSaida(
        id_peticao=peticao.id_peticao,
        id_processo=peticao.id_processo,
        id_usuario=peticao.id_usuario,
        tipo=peticao.tipo,
        descricao=peticao.descricao,
        data_peticao=peticao.data_peticao,
        status=peticao.status,
        versao_atual=versao.numero_versao if versao else 0,
        conteudo=versao.conteudo if versao else "",
    )


def _saidas_peticoes(
    sessao: Session, peticoes: list[PeticaoDB]
) -> list[PeticaoSaida]:
    ids_peticoes = [peticao.id_peticao for peticao in peticoes]
    if not ids_peticoes:
        return []
    versoes = sessao.scalars(
        select(VersaoPeticaoDB)
        .where(VersaoPeticaoDB.id_peticao.in_(ids_peticoes))
        .order_by(VersaoPeticaoDB.id_peticao, VersaoPeticaoDB.numero_versao.desc())
    ).all()
    versao_por_peticao: dict[int, VersaoPeticaoDB] = {}
    for versao in versoes:
        versao_por_peticao.setdefault(versao.id_peticao, versao)
    return [
        PeticaoSaida(
            id_peticao=peticao.id_peticao,
            id_processo=peticao.id_processo,
            id_usuario=peticao.id_usuario,
            tipo=peticao.tipo,
            descricao=peticao.descricao,
            data_peticao=peticao.data_peticao,
            status=peticao.status,
            versao_atual=(
                versao_por_peticao[peticao.id_peticao].numero_versao
                if peticao.id_peticao in versao_por_peticao
                else 0
            ),
            conteudo=(
                versao_por_peticao[peticao.id_peticao].conteudo
                if peticao.id_peticao in versao_por_peticao
                else ""
            ),
        )
        for peticao in peticoes
    ]


def _peticao_autorizada(
    sessao: Session,
    peticao_id: int,
    usuario: UsuarioAtual,
    *,
    edicao: bool = False,
) -> PeticaoDB:
    peticao = sessao.get(PeticaoDB, peticao_id)
    if peticao is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Petição não encontrada.")
    obter_processo_autorizado(sessao, usuario, peticao.id_processo, edicao=edicao)
    return peticao


def _validar_revisor(
    sessao: Session, processo_id: int, usuario_id: int
) -> tuple[UsuarioDB, str]:
    linha = sessao.execute(
        select(UsuarioDB, JuridicoDB.oab)
        .join(JuridicoDB, JuridicoDB.id_usuario == UsuarioDB.id_usuario)
        .join(PermissaoProcessoDB, PermissaoProcessoDB.id_usuario == UsuarioDB.id_usuario)
        .where(
            UsuarioDB.id_usuario == usuario_id,
            UsuarioDB.ativo.is_(True),
            PermissaoProcessoDB.id_processo == processo_id,
            PermissaoProcessoDB.nivel_acesso.in_(("edicao", "total")),
        )
    ).first()
    if linha is None:
        raise HTTPException(
            status_code=422,
            detail="O revisor precisa ser advogado ativo autorizado a editar este processo.",
        )
    return linha


def _saida_comentario_peticao(
    sessao: Session,
    comentario: PeticaoComentarioDB,
    nome_autor: str | None = None,
    *,
    autor_carregado: bool = False,
) -> PeticaoComentarioSaida:
    autor = (
        None
        if autor_carregado or comentario.id_usuario is None
        else sessao.get(UsuarioDB, comentario.id_usuario)
    )
    return PeticaoComentarioSaida(
        id_comentario=comentario.id_comentario,
        id_peticao=comentario.id_peticao,
        id_versao=comentario.id_versao,
        id_usuario=comentario.id_usuario,
        autor=nome_autor if autor_carregado else autor.nome if autor else None,
        conteudo="[Comentário removido]" if comentario.excluido_em else comentario.conteudo,
        criado_em=comentario.criado_em,
        editado_em=comentario.editado_em,
        resolvido_em=comentario.resolvido_em,
        resolvido_por=comentario.resolvido_por,
        excluido_em=comentario.excluido_em,
    )


def _variaveis_modelo(
    sessao: Session,
    processo: ProcessoDB,
    usuario: UsuarioDB,
) -> dict[str, str]:
    dados = processo.dados_json or {}
    associados = sessao.scalars(
        select(AssociadoDB.nome)
        .join(ProcessoAssociadoDB, ProcessoAssociadoDB.id_associado == AssociadoDB.id_associado)
        .where(ProcessoAssociadoDB.id_processo == processo.id_processo)
        .order_by(AssociadoDB.nome)
    ).all()
    advogado = usuario.nome
    juridico = sessao.get(JuridicoDB, usuario.id_usuario)
    oab = juridico.oab if juridico else ""
    return {
        "processo_numero": processo.numero_processo,
        "processo_tribunal": processo.tribunal or "",
        "processo_classe": processo.tipo or "",
        "processo_assunto": processo.assunto or "",
        "associado_nome": "; ".join(associados),
        "advogado_nome": advogado,
        "advogado_oab": oab,
        "vara": str(dados.get("vara") or dados.get("orgao_julgador") or ""),
        "comarca": str(dados.get("comarca") or dados.get("municipio") or ""),
    }


@router.get("/api/v1/peticoes/modelos", response_model=list[ModeloPeticaoSaida])
def listar_modelos(
    _usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> list[ModeloPeticaoDB]:
    return list(
        sessao.scalars(
            select(ModeloPeticaoDB)
            .where(ModeloPeticaoDB.ativo.is_(True))
            .order_by(ModeloPeticaoDB.nome)
        ).all()
    )


@router.post(
    "/api/v1/peticoes/modelos",
    response_model=ModeloPeticaoSaida,
    status_code=status.HTTP_201_CREATED,
)
def criar_modelo(
    entrada: ModeloPeticaoEntrada,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ModeloPeticaoDB:
    modelo = ModeloPeticaoDB(
        nome=entrada.nome.strip(),
        tipo=entrada.tipo.strip(),
        conteudo=entrada.conteudo,
        criado_por=int(usuario.id),
    )
    sessao.add(modelo)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=None,
        operacao="criacao_modelo_peticao",
        descricao=f"Modelo de petição criado: {modelo.nome}.",
    )
    try:
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        raise HTTPException(status_code=409, detail="Já existe um modelo com este nome.") from erro
    sessao.refresh(modelo)
    return modelo


@router.patch("/api/v1/peticoes/modelos/{modelo_id}", response_model=ModeloPeticaoSaida)
def atualizar_modelo(
    modelo_id: int,
    entrada: ModeloPeticaoAtualizacao,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ModeloPeticaoDB:
    modelo = sessao.get(ModeloPeticaoDB, modelo_id)
    if modelo is None:
        raise HTTPException(status_code=404, detail="Modelo de petição não encontrado.")
    alteracoes = entrada.model_dump(exclude_unset=True)
    if any(valor is None for chave, valor in alteracoes.items() if chave != "ativo"):
        raise HTTPException(status_code=422, detail="Campos do modelo não podem ser definidos como nulos.")
    for campo, valor in alteracoes.items():
        setattr(modelo, campo, valor.strip() if isinstance(valor, str) else valor)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=None,
        operacao="alteracao_modelo_peticao",
        descricao=f"Modelo de petição atualizado: {modelo.nome}.",
        dados={"campos": sorted(alteracoes)},
    )
    try:
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        raise HTTPException(status_code=409, detail="Já existe um modelo com este nome.") from erro
    sessao.refresh(modelo)
    return modelo


@router.delete("/api/v1/peticoes/modelos/{modelo_id}", status_code=status.HTTP_204_NO_CONTENT)
def desativar_modelo(
    modelo_id: int,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> None:
    modelo = sessao.get(ModeloPeticaoDB, modelo_id)
    if modelo is None:
        raise HTTPException(status_code=404, detail="Modelo de petição não encontrado.")
    modelo.ativo = False
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=None,
        operacao="desativacao_modelo_peticao",
        descricao=f"Modelo de petição desativado: {modelo.nome}.",
    )
    sessao.commit()


@router.get("/api/v1/processos/{processo_id}/peticoes", response_model=list[PeticaoSaida])
def listar_peticoes(
    processo_id: int,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> list[PeticaoSaida]:
    obter_processo_autorizado(sessao, usuario, processo_id)
    peticoes = sessao.scalars(
        select(PeticaoDB)
        .where(PeticaoDB.id_processo == processo_id)
        .order_by(PeticaoDB.data_peticao.desc(), PeticaoDB.id_peticao.desc())
    ).all()
    return _saidas_peticoes(sessao, peticoes)


@router.post(
    "/api/v1/processos/{processo_id}/peticoes",
    response_model=PeticaoSaida,
    status_code=status.HTTP_201_CREATED,
)
def criar_peticao(
    processo_id: int,
    entrada: PeticaoCriacao,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> PeticaoSaida:
    processo, _ = obter_processo_autorizado(sessao, usuario, processo_id, edicao=True)
    conta = sessao.get(UsuarioDB, int(usuario.id))
    if conta is None:
        raise HTTPException(status_code=401, detail="Usuário não encontrado.")

    modelo = None
    if entrada.id_modelo is not None:
        modelo = sessao.get(ModeloPeticaoDB, entrada.id_modelo)
        if modelo is None or not modelo.ativo:
            raise HTTPException(status_code=404, detail="Modelo de petição não encontrado ou inativo.")
    conteudo_base = entrada.conteudo if entrada.conteudo is not None else modelo.conteudo
    conteudo = renderizar_modelo(conteudo_base, _variaveis_modelo(sessao, processo, conta))
    tipo = entrada.tipo.strip() if entrada.tipo else (modelo.tipo if modelo else "")
    if not tipo:
        raise HTTPException(status_code=422, detail="Informe o tipo da petição.")

    peticao = PeticaoDB(
        id_processo=processo_id,
        id_usuario=int(usuario.id),
        tipo=tipo,
        descricao=entrada.descricao,
        status="rascunho",
    )
    sessao.add(peticao)
    sessao.flush()
    versao = VersaoPeticaoDB(
        id_peticao=peticao.id_peticao,
        numero_versao=1,
        conteudo=conteudo,
        id_usuario=int(usuario.id),
    )
    sessao.add(versao)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=processo_id,
        operacao="criacao_peticao",
        descricao=f"Petição {peticao.id_peticao} criada como rascunho.",
        dados={"id_peticao": peticao.id_peticao, "versao": 1, "tipo": tipo},
    )
    sessao.commit()
    sessao.refresh(peticao)
    return _saida_peticao(sessao, peticao)


@router.get("/api/v1/peticoes/{peticao_id}", response_model=PeticaoSaida)
def obter_peticao(
    peticao_id: int,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> PeticaoSaida:
    peticao = _peticao_autorizada(sessao, peticao_id, usuario)
    return _saida_peticao(sessao, peticao)


@router.get("/api/v1/peticoes/{peticao_id}/versoes", response_model=list[VersaoPeticaoSaida])
def listar_versoes_peticao(
    peticao_id: int,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> list[VersaoPeticaoDB]:
    _peticao_autorizada(sessao, peticao_id, usuario)
    return list(
        sessao.scalars(
            select(VersaoPeticaoDB)
            .where(VersaoPeticaoDB.id_peticao == peticao_id)
            .order_by(VersaoPeticaoDB.numero_versao.desc())
        ).all()
    )


@router.patch("/api/v1/peticoes/{peticao_id}", response_model=PeticaoSaida)
def atualizar_peticao(
    peticao_id: int,
    entrada: PeticaoAtualizacao,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> PeticaoSaida:
    peticao = _peticao_autorizada(sessao, peticao_id, usuario, edicao=True)
    if peticao.status not in {"rascunho", "rejeitada"}:
        raise HTTPException(status_code=409, detail="Somente rascunhos ou petições rejeitadas podem ser editados.")
    alteracoes = entrada.model_dump(exclude_unset=True)
    if "conteudo" in alteracoes and alteracoes["conteudo"] is None:
        raise HTTPException(status_code=422, detail="O conteúdo da petição não pode ser nulo.")
    for campo in ("tipo", "descricao"):
        if campo in alteracoes:
            valor = alteracoes[campo]
            if campo == "tipo" and valor is None:
                raise HTTPException(status_code=422, detail="O tipo da petição não pode ser nulo.")
            setattr(peticao, campo, valor.strip() if isinstance(valor, str) else valor)

    conteudo = alteracoes.get("conteudo")
    if conteudo is not None:
        ultima = _versao_atual(sessao, peticao.id_peticao)
        if ultima is None or ultima.conteudo != conteudo:
            numero_versao = (ultima.numero_versao if ultima else 0) + 1
            sessao.add(
                VersaoPeticaoDB(
                    id_peticao=peticao.id_peticao,
                    numero_versao=numero_versao,
                    conteudo=conteudo,
                    id_usuario=int(usuario.id),
                )
            )
        else:
            numero_versao = ultima.numero_versao
    else:
        ultima = _versao_atual(sessao, peticao.id_peticao)
        numero_versao = ultima.numero_versao if ultima else 0

    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=peticao.id_processo,
        operacao="edicao_peticao",
        descricao=f"Petição {peticao.id_peticao} atualizada.",
        dados={"id_peticao": peticao.id_peticao, "versao": numero_versao, "campos": sorted(alteracoes)},
    )
    sessao.commit()
    sessao.refresh(peticao)
    return _saida_peticao(sessao, peticao)


@router.post("/api/v1/peticoes/{peticao_id}/status", response_model=PeticaoSaida)
def alterar_status_peticao(
    peticao_id: int,
    entrada: PeticaoStatusEntrada,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> PeticaoSaida:
    peticao = _peticao_autorizada(sessao, peticao_id, usuario, edicao=True)
    permitidos = _TRANSICOES_STATUS.get(peticao.status, set())
    if entrada.status not in permitidos:
        raise HTTPException(
            status_code=409,
            detail=f"Transição de status não permitida: {peticao.status} → {entrada.status}.",
        )
    status_anterior = peticao.status
    peticao.status = entrada.status
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=peticao.id_processo,
        operacao="alteracao_status_peticao",
        descricao=entrada.observacao or f"Status da petição {peticao.id_peticao} alterado.",
        dados={
            "id_peticao": peticao.id_peticao,
            "de": status_anterior,
            "para": entrada.status,
            "observacao": entrada.observacao,
        },
    )
    sessao.commit()
    sessao.refresh(peticao)
    return _saida_peticao(sessao, peticao)


@router.get(
    "/api/v1/peticoes/{peticao_id}/revisor",
    response_model=PeticaoRevisorSaida | None,
)
def obter_revisor_peticao(
    peticao_id: int,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> PeticaoRevisorSaida | None:
    _peticao_autorizada(sessao, peticao_id, usuario)
    linha = sessao.execute(
        select(PeticaoRevisorDB, UsuarioDB.nome, JuridicoDB.oab)
        .join(UsuarioDB, UsuarioDB.id_usuario == PeticaoRevisorDB.id_usuario)
        .join(JuridicoDB, JuridicoDB.id_usuario == UsuarioDB.id_usuario)
        .where(PeticaoRevisorDB.id_peticao == peticao_id)
    ).first()
    if linha is None:
        return None
    revisor, nome, oab = linha
    return PeticaoRevisorSaida(
        id_peticao=revisor.id_peticao,
        id_usuario=revisor.id_usuario,
        nome=nome,
        oab=oab,
        atribuido_por=revisor.atribuido_por,
        atribuido_em=revisor.atribuido_em,
    )


@router.put(
    "/api/v1/peticoes/{peticao_id}/revisor",
    response_model=PeticaoRevisorSaida,
)
def atribuir_revisor_peticao(
    peticao_id: int,
    entrada: PeticaoRevisorEntrada,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> PeticaoRevisorSaida:
    peticao = _peticao_autorizada(sessao, peticao_id, usuario, edicao=True)
    revisor, oab = _validar_revisor(sessao, peticao.id_processo, entrada.id_usuario)
    registro = sessao.get(PeticaoRevisorDB, peticao_id)
    if registro is None:
        registro = PeticaoRevisorDB(
            id_peticao=peticao_id,
            id_usuario=revisor.id_usuario,
            atribuido_por=int(usuario.id),
        )
        sessao.add(registro)
    else:
        registro.id_usuario = revisor.id_usuario
        registro.atribuido_por = int(usuario.id)
        registro.atribuido_em = datetime.now(timezone.utc)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=peticao.id_processo,
        operacao="revisor_peticao_atribuido",
        descricao=f"Revisor atribuído à petição {peticao_id}.",
        dados={"id_peticao": peticao_id, "id_revisor": revisor.id_usuario},
    )
    sessao.commit()
    sessao.refresh(registro)
    return PeticaoRevisorSaida(
        id_peticao=peticao_id,
        id_usuario=revisor.id_usuario,
        nome=revisor.nome,
        oab=oab,
        atribuido_por=registro.atribuido_por,
        atribuido_em=registro.atribuido_em,
    )


@router.delete(
    "/api/v1/peticoes/{peticao_id}/revisor",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remover_revisor_peticao(
    peticao_id: int,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> None:
    peticao = _peticao_autorizada(sessao, peticao_id, usuario, edicao=True)
    registro = sessao.get(PeticaoRevisorDB, peticao_id)
    if registro is None:
        return
    id_revisor = registro.id_usuario
    sessao.delete(registro)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=peticao.id_processo,
        operacao="revisor_peticao_removido",
        descricao=f"Revisor removido da petição {peticao_id}.",
        dados={"id_peticao": peticao_id, "id_revisor": id_revisor},
    )
    sessao.commit()


@router.get(
    "/api/v1/peticoes/{peticao_id}/comentarios",
    response_model=list[PeticaoComentarioSaida],
)
def listar_comentarios_peticao(
    peticao_id: int,
    id_versao: int | None = Query(default=None, ge=1),
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
    limite: Annotated[int, Query(ge=1, le=100)] = 50,
    deslocamento: Annotated[int, Query(ge=0)] = 0,
) -> list[PeticaoComentarioSaida]:
    _peticao_autorizada(sessao, peticao_id, usuario)
    consulta = (
        select(PeticaoComentarioDB, UsuarioDB.nome)
        .outerjoin(UsuarioDB, UsuarioDB.id_usuario == PeticaoComentarioDB.id_usuario)
        .where(PeticaoComentarioDB.id_peticao == peticao_id)
    )
    if id_versao is not None:
        versao = sessao.get(VersaoPeticaoDB, id_versao)
        if versao is None or versao.id_peticao != peticao_id:
            raise HTTPException(status_code=404, detail="Versão da petição não encontrada.")
        consulta = consulta.where(PeticaoComentarioDB.id_versao == id_versao)
    comentarios = sessao.execute(
        consulta.order_by(PeticaoComentarioDB.criado_em, PeticaoComentarioDB.id_comentario)
        .limit(limite)
        .offset(deslocamento)
    ).all()
    return [
        _saida_comentario_peticao(
            sessao,
            comentario,
            nome_autor,
            autor_carregado=True,
        )
        for comentario, nome_autor in comentarios
    ]


@router.post(
    "/api/v1/peticoes/{peticao_id}/comentarios",
    response_model=PeticaoComentarioSaida,
    status_code=status.HTTP_201_CREATED,
)
def criar_comentario_peticao(
    peticao_id: int,
    entrada: PeticaoComentarioEntrada,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> PeticaoComentarioSaida:
    peticao = _peticao_autorizada(sessao, peticao_id, usuario, edicao=True)
    versao = sessao.get(VersaoPeticaoDB, entrada.id_versao)
    if versao is None or versao.id_peticao != peticao_id:
        raise HTTPException(status_code=404, detail="Versão da petição não encontrada.")
    conteudo = entrada.conteudo.strip()
    if not conteudo:
        raise HTTPException(status_code=422, detail="O comentário não pode estar vazio.")
    comentario = PeticaoComentarioDB(
        id_peticao=peticao_id,
        id_versao=versao.id_versao,
        id_usuario=int(usuario.id),
        conteudo=conteudo,
    )
    sessao.add(comentario)
    sessao.flush()
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=peticao.id_processo,
        operacao="comentario_peticao_criado",
        descricao=f"Comentário adicionado à versão {versao.numero_versao} da petição {peticao_id}.",
        dados={
            "id_peticao": peticao_id,
            "id_versao": versao.id_versao,
            "id_comentario": comentario.id_comentario,
        },
    )
    notificar_usuarios_do_processo(
        sessao,
        peticao.id_processo,
        categoria="revisao_peticao",
        titulo="Novo comentário na revisão de petição",
        mensagem=f"{usuario.nome} comentou a versão {versao.numero_versao} da petição {peticao_id}.",
        chave=f"comentario-peticao:{comentario.id_comentario}",
        exceto_usuario_id=int(usuario.id),
    )
    sessao.commit()
    sessao.refresh(comentario)
    return _saida_comentario_peticao(sessao, comentario)


@router.patch(
    "/api/v1/peticoes/comentarios/{comentario_id}",
    response_model=PeticaoComentarioSaida,
)
def atualizar_comentario_peticao(
    comentario_id: int,
    entrada: PeticaoComentarioAtualizacao,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> PeticaoComentarioSaida:
    comentario = sessao.get(PeticaoComentarioDB, comentario_id)
    if comentario is None:
        raise HTTPException(status_code=404, detail="Comentário de petição não encontrado.")
    peticao = _peticao_autorizada(sessao, comentario.id_peticao, usuario, edicao=True)
    if comentario.id_usuario != int(usuario.id):
        raise HTTPException(status_code=403, detail="Somente o autor pode editar este comentário.")
    if comentario.excluido_em is not None:
        raise HTTPException(status_code=409, detail="O comentário já foi removido.")
    conteudo = entrada.conteudo.strip()
    if not conteudo:
        raise HTTPException(status_code=422, detail="O comentário não pode estar vazio.")
    comentario.conteudo = conteudo
    comentario.editado_em = datetime.now(timezone.utc)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=peticao.id_processo,
        operacao="comentario_peticao_editado",
        descricao=f"Comentário {comentario_id} editado.",
        dados={"id_comentario": comentario_id, "id_peticao": peticao.id_peticao},
    )
    sessao.commit()
    sessao.refresh(comentario)
    return _saida_comentario_peticao(sessao, comentario)


@router.delete(
    "/api/v1/peticoes/comentarios/{comentario_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def excluir_comentario_peticao(
    comentario_id: int,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> None:
    comentario = sessao.get(PeticaoComentarioDB, comentario_id)
    if comentario is None:
        raise HTTPException(status_code=404, detail="Comentário de petição não encontrado.")
    peticao = _peticao_autorizada(sessao, comentario.id_peticao, usuario, edicao=True)
    if comentario.id_usuario != int(usuario.id):
        raise HTTPException(status_code=403, detail="Somente o autor pode remover este comentário.")
    if comentario.excluido_em is not None:
        raise HTTPException(status_code=409, detail="O comentário já foi removido.")
    comentario.conteudo = "[Comentário removido]"
    comentario.excluido_em = datetime.now(timezone.utc)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=peticao.id_processo,
        operacao="comentario_peticao_removido",
        descricao=f"Comentário {comentario_id} removido.",
        dados={"id_comentario": comentario_id, "id_peticao": peticao.id_peticao},
    )
    sessao.commit()


@router.patch(
    "/api/v1/peticoes/comentarios/{comentario_id}/resolucao",
    response_model=PeticaoComentarioSaida,
)
def resolver_comentario_peticao(
    comentario_id: int,
    entrada: PeticaoComentarioResolucao,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> PeticaoComentarioSaida:
    comentario = sessao.get(PeticaoComentarioDB, comentario_id)
    if comentario is None:
        raise HTTPException(status_code=404, detail="Comentário de petição não encontrado.")
    peticao = _peticao_autorizada(sessao, comentario.id_peticao, usuario, edicao=True)
    if comentario.excluido_em is not None:
        raise HTTPException(status_code=409, detail="Não é possível resolver um comentário removido.")
    agora = datetime.now(timezone.utc)
    comentario.resolvido_em = agora if entrada.resolvido else None
    comentario.resolvido_por = int(usuario.id) if entrada.resolvido else None
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=peticao.id_processo,
        operacao="comentario_peticao_resolvido" if entrada.resolvido else "comentario_peticao_reaberto",
        descricao=f"Comentário {comentario_id} {'resolvido' if entrada.resolvido else 'reaberto'}.",
        dados={"id_comentario": comentario_id, "id_peticao": peticao.id_peticao},
    )
    sessao.commit()
    sessao.refresh(comentario)
    return _saida_comentario_peticao(sessao, comentario)


@router.get(
    "/api/v1/peticoes/{peticao_id}/protocolos",
    response_model=list[PeticaoProtocoloSaida],
)
def listar_protocolos_peticao(
    peticao_id: int,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> list[PeticaoProtocoloDB]:
    _peticao_autorizada(sessao, peticao_id, usuario)
    return list(
        sessao.scalars(
            select(PeticaoProtocoloDB)
            .where(PeticaoProtocoloDB.id_peticao == peticao_id)
            .order_by(PeticaoProtocoloDB.protocolado_em.desc(), PeticaoProtocoloDB.id_protocolo.desc())
        ).all()
    )


@router.post(
    "/api/v1/peticoes/{peticao_id}/protocolos",
    response_model=PeticaoProtocoloSaida,
    status_code=status.HTTP_201_CREATED,
)
def registrar_protocolo_peticao(
    peticao_id: int,
    entrada: PeticaoProtocoloEntrada,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> PeticaoProtocoloDB:
    peticao = _peticao_autorizada(sessao, peticao_id, usuario, edicao=True)
    if peticao.status != "aprovada":
        raise HTTPException(
            status_code=409,
            detail="Somente uma petição aprovada pode receber registro de protocolo.",
        )
    documento = None
    if entrada.id_documento_comprovante is not None:
        documento = sessao.get(DocumentoDB, entrada.id_documento_comprovante)
        if (
            documento is None
            or documento.id_processo != peticao.id_processo
            or documento.id_peticao not in {None, peticao_id}
        ):
            raise HTTPException(
                status_code=422,
                detail="O comprovante precisa ser um documento deste processo e não pode pertencer a outra petição.",
            )
        documento.id_peticao = peticao_id
    registro = PeticaoProtocoloDB(
        id_peticao=peticao_id,
        id_usuario=int(usuario.id),
        id_documento_comprovante=documento.id_documento if documento else None,
        numero_protocolo=entrada.numero_protocolo.strip() if entrada.numero_protocolo else None,
        tribunal=entrada.tribunal.strip(),
        protocolado_em=entrada.protocolado_em,
        observacao=entrada.observacao.strip() if entrada.observacao else None,
    )
    sessao.add(registro)
    sessao.flush()
    peticao.status = "protocolada"
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=peticao.id_processo,
        operacao="protocolo_peticao_registrado",
        descricao=f"Protocolo manual registrado para a petição {peticao_id}.",
        dados={
            "id_peticao": peticao_id,
            "id_protocolo": registro.id_protocolo,
            "numero_protocolo": registro.numero_protocolo,
            "tribunal": registro.tribunal,
            "protocolado_em": registro.protocolado_em.isoformat(),
            "id_documento_comprovante": registro.id_documento_comprovante,
            "origem": "registro_manual",
        },
    )
    sessao.commit()
    sessao.refresh(registro)
    return registro


@router.get("/api/v1/peticoes/{peticao_id}/exportar")
def exportar_peticao(
    peticao_id: int,
    formato: str,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> Response:
    if formato not in {"docx", "pdf"}:
        raise HTTPException(status_code=422, detail="Formato deve ser docx ou pdf.")
    peticao = _peticao_autorizada(sessao, peticao_id, usuario)
    versao = _versao_atual(sessao, peticao_id)
    if versao is None:
        raise HTTPException(status_code=404, detail="A petição ainda não possui conteúdo salvo.")

    if formato == "docx":
        conteudo = gerar_docx(versao.conteudo)
        media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    else:
        conteudo = gerar_pdf(versao.conteudo)
        media_type = "application/pdf"
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=peticao.id_processo,
        operacao="exportacao_peticao",
        descricao=f"Petição {peticao_id} exportada em {formato.upper()}.",
        dados={"id_peticao": peticao_id, "versao": versao.numero_versao, "formato": formato},
    )
    sessao.commit()
    return Response(
        content=conteudo,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="peticao_{peticao_id}_v{versao.numero_versao}.{formato}"',
            "X-Content-Type-Options": "nosniff",
        },
    )
