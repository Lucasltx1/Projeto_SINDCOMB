from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .auth import UsuarioAtual, exigir_acesso_processos, exigir_advogado
from .models import (
    AssociadoDB,
    JuridicoDB,
    ModeloPeticaoDB,
    PeticaoDB,
    ProcessoAssociadoDB,
    ProcessoDB,
    UsuarioDB,
    VersaoPeticaoDB,
)
from .recursos_acesso import obter_processo_autorizado, registrar_auditoria
from .recursos_schemas import (
    ModeloPeticaoAtualizacao,
    ModeloPeticaoEntrada,
    ModeloPeticaoSaida,
    PeticaoAtualizacao,
    PeticaoCriacao,
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
    "aprovada": {"protocolada"},
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
    return [_saida_peticao(sessao, peticao) for peticao in peticoes]


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
