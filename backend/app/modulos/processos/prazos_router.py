from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .auth import UsuarioAtual, exigir_acesso_processos, exigir_advogado
from .models import JuridicoDB, PermissaoProcessoDB, PrazoDB, UsuarioDB
from .recursos_acesso import obter_processo_autorizado, registrar_auditoria
from .recursos_schemas import (
    PrazoAtualizacao,
    PrazoCriacao,
    PrazoSaida,
    ResponsavelPrazoSaida,
    StatusPrazo,
)

router = APIRouter(tags=["Prazos"])


def _saida_prazo(prazo: PrazoDB) -> PrazoSaida:
    hoje = date.today()
    dias_restantes = (prazo.data_vencimento - hoje).days
    return PrazoSaida(
        id_prazo=prazo.id_prazo,
        id_processo=prazo.id_processo,
        id_usuario=prazo.id_usuario,
        descricao=prazo.descricao,
        data_inicio=prazo.data_inicio,
        data_vencimento=prazo.data_vencimento,
        status=prazo.status,
        atrasado=prazo.status == "pendente" and dias_restantes < 0,
        dias_restantes=dias_restantes,
    )


def _validar_responsavel(sessao: Session, processo_id: int, usuario_id: int) -> None:
    responsavel = sessao.scalar(
        select(JuridicoDB.id_usuario)
        .join(UsuarioDB, UsuarioDB.id_usuario == JuridicoDB.id_usuario)
        .join(PermissaoProcessoDB, PermissaoProcessoDB.id_usuario == JuridicoDB.id_usuario)
        .where(
            JuridicoDB.id_usuario == usuario_id,
            UsuarioDB.ativo.is_(True),
            PermissaoProcessoDB.id_processo == processo_id,
            PermissaoProcessoDB.nivel_acesso.in_(("edicao", "total")),
        )
    )
    if responsavel is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="O responsável precisa ser um advogado ativo autorizado a editar este processo.",
        )


@router.get("/api/v1/prazos", response_model=list[PrazoSaida])
def listar_prazos_do_usuario(
    status_prazo: StatusPrazo | None = Query(default=None, alias="status"),
    somente_atrasados: bool = False,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> list[PrazoSaida]:
    consulta = (
        select(PrazoDB)
        .join(PermissaoProcessoDB, PermissaoProcessoDB.id_processo == PrazoDB.id_processo)
        .where(PermissaoProcessoDB.id_usuario == int(usuario.id))
        .order_by(PrazoDB.data_vencimento, PrazoDB.id_prazo)
    )
    if status_prazo is not None:
        consulta = consulta.where(PrazoDB.status == status_prazo)
    if somente_atrasados:
        consulta = consulta.where(PrazoDB.status == "pendente", PrazoDB.data_vencimento < date.today())
    prazos = sessao.scalars(consulta.distinct()).all()
    return [_saida_prazo(prazo) for prazo in prazos]


@router.get("/api/v1/processos/{processo_id}/prazos", response_model=list[PrazoSaida])
def listar_prazos_processo(
    processo_id: int,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> list[PrazoSaida]:
    obter_processo_autorizado(sessao, usuario, processo_id)
    prazos = sessao.scalars(
        select(PrazoDB)
        .where(PrazoDB.id_processo == processo_id)
        .order_by(PrazoDB.data_vencimento, PrazoDB.id_prazo)
    ).all()
    return [_saida_prazo(prazo) for prazo in prazos]


@router.get(
    "/api/v1/processos/{processo_id}/prazos/responsaveis",
    response_model=list[ResponsavelPrazoSaida],
)
def listar_responsaveis_prazo(
    processo_id: int,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> list[ResponsavelPrazoSaida]:
    obter_processo_autorizado(sessao, usuario, processo_id)
    linhas = sessao.execute(
        select(UsuarioDB.id_usuario, UsuarioDB.nome, JuridicoDB.oab)
        .join(JuridicoDB, JuridicoDB.id_usuario == UsuarioDB.id_usuario)
        .join(PermissaoProcessoDB, PermissaoProcessoDB.id_usuario == UsuarioDB.id_usuario)
        .where(
            PermissaoProcessoDB.id_processo == processo_id,
            PermissaoProcessoDB.nivel_acesso.in_(("edicao", "total")),
            UsuarioDB.ativo.is_(True),
        )
        .order_by(UsuarioDB.nome)
    ).all()
    return [
        ResponsavelPrazoSaida(id_usuario=id_usuario, nome=nome, oab=oab)
        for id_usuario, nome, oab in linhas
    ]


@router.post(
    "/api/v1/processos/{processo_id}/prazos",
    response_model=PrazoSaida,
    status_code=status.HTTP_201_CREATED,
)
def criar_prazo(
    processo_id: int,
    entrada: PrazoCriacao,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> PrazoSaida:
    obter_processo_autorizado(sessao, usuario, processo_id, edicao=True)
    responsavel_id = entrada.id_usuario_responsavel or int(usuario.id)
    _validar_responsavel(sessao, processo_id, responsavel_id)
    prazo = PrazoDB(
        id_processo=processo_id,
        id_usuario=responsavel_id,
        descricao=entrada.descricao.strip(),
        data_inicio=entrada.data_inicio,
        data_vencimento=entrada.data_vencimento,
        status="pendente",
    )
    sessao.add(prazo)
    sessao.flush()
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=processo_id,
        operacao="criacao_prazo",
        descricao=f"Prazo {prazo.id_prazo} criado.",
        dados={
            "id_prazo": prazo.id_prazo,
            "responsavel": responsavel_id,
            "data_vencimento": prazo.data_vencimento.isoformat(),
        },
    )
    sessao.commit()
    sessao.refresh(prazo)
    return _saida_prazo(prazo)


@router.patch("/api/v1/prazos/{prazo_id}", response_model=PrazoSaida)
def atualizar_prazo(
    prazo_id: int,
    entrada: PrazoAtualizacao,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> PrazoSaida:
    prazo = sessao.get(PrazoDB, prazo_id)
    if prazo is None:
        raise HTTPException(status_code=404, detail="Prazo não encontrado.")
    obter_processo_autorizado(sessao, usuario, prazo.id_processo, edicao=True)

    alteracoes = entrada.model_dump(exclude_unset=True)
    if "id_usuario_responsavel" in alteracoes:
        responsavel_id = alteracoes["id_usuario_responsavel"]
        if responsavel_id is None:
            raise HTTPException(status_code=422, detail="O prazo precisa ter um advogado responsável.")
        _validar_responsavel(sessao, prazo.id_processo, responsavel_id)
        alteracoes["id_usuario"] = alteracoes.pop("id_usuario_responsavel")

    if "data_vencimento" in alteracoes and alteracoes["data_vencimento"] is None:
        raise HTTPException(status_code=422, detail="Informe a data de vencimento.")
    if "status" in alteracoes and alteracoes["status"] is None:
        raise HTTPException(status_code=422, detail="Informe o status do prazo.")

    nova_data_inicio = alteracoes.get("data_inicio", prazo.data_inicio)
    nova_data_vencimento = alteracoes.get("data_vencimento", prazo.data_vencimento)
    if nova_data_inicio is not None and nova_data_inicio > nova_data_vencimento:
        raise HTTPException(
            status_code=422,
            detail="A data de início não pode ser posterior à data de vencimento.",
        )
    if "descricao" in alteracoes:
        if alteracoes["descricao"] is None:
            raise HTTPException(status_code=422, detail="A descrição do prazo não pode ser nula.")
        alteracoes["descricao"] = alteracoes["descricao"].strip()

    antes = {
        "descricao": prazo.descricao,
        "data_inicio": prazo.data_inicio.isoformat() if prazo.data_inicio else None,
        "data_vencimento": prazo.data_vencimento.isoformat(),
        "status": prazo.status,
        "id_usuario": prazo.id_usuario,
    }
    for campo, valor in alteracoes.items():
        setattr(prazo, campo, valor)
    depois = {
        campo: (valor.isoformat() if isinstance(valor, date) else valor)
        for campo, valor in {
            "descricao": prazo.descricao,
            "data_inicio": prazo.data_inicio,
            "data_vencimento": prazo.data_vencimento,
            "status": prazo.status,
            "id_usuario": prazo.id_usuario,
        }.items()
    }
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=prazo.id_processo,
        operacao="alteracao_prazo",
        descricao=f"Prazo {prazo.id_prazo} atualizado.",
        dados={"id_prazo": prazo.id_prazo, "antes": antes, "depois": depois},
    )
    try:
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        raise HTTPException(status_code=409, detail="Não foi possível atualizar o prazo.") from erro
    sessao.refresh(prazo)
    return _saida_prazo(prazo)


@router.delete("/api/v1/prazos/{prazo_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_prazo(
    prazo_id: int,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> None:
    prazo = sessao.get(PrazoDB, prazo_id)
    if prazo is None:
        raise HTTPException(status_code=404, detail="Prazo não encontrado.")
    obter_processo_autorizado(sessao, usuario, prazo.id_processo, edicao=True)
    processo_id = prazo.id_processo
    sessao.delete(prazo)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=processo_id,
        operacao="exclusao_prazo",
        descricao=f"Prazo {prazo_id} excluído.",
        dados={"id_prazo": prazo_id},
    )
    sessao.commit()
