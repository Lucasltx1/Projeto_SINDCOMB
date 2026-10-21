from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .auth import UsuarioAtual, exigir_advogado
from .models import ComentarioProcessoDB, UsuarioDB
from .recursos_acesso import obter_processo_autorizado, registrar_auditoria
from .notificacoes_service import notificar_usuarios_do_processo
from .recursos_schemas import (
    ComentarioProcessoAtualizacao,
    ComentarioProcessoEntrada,
    ComentarioProcessoSaida,
)

router = APIRouter(prefix="/api/v1/processos", tags=["Comentários"])


@router.get("/{processo_id}/comentarios", response_model=list[ComentarioProcessoSaida])
def listar_comentarios(
    processo_id: int,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> list[ComentarioProcessoSaida]:
    obter_processo_autorizado(sessao, usuario, processo_id)
    linhas = sessao.execute(
        select(ComentarioProcessoDB, UsuarioDB.nome)
        .outerjoin(UsuarioDB, UsuarioDB.id_usuario == ComentarioProcessoDB.id_usuario)
        .where(ComentarioProcessoDB.id_processo == processo_id)
        .order_by(ComentarioProcessoDB.criado_em, ComentarioProcessoDB.id_comentario)
    ).all()
    return [
        ComentarioProcessoSaida(
            id_comentario=comentario.id_comentario,
            id_processo=comentario.id_processo,
            id_usuario=comentario.id_usuario,
            autor=nome,
            conteudo="[Comentário removido]" if comentario.excluido_em else comentario.conteudo,
            criado_em=comentario.criado_em,
            editado_em=comentario.editado_em,
            excluido_em=comentario.excluido_em,
        )
        for comentario, nome in linhas
    ]


@router.post(
    "/{processo_id}/comentarios",
    response_model=ComentarioProcessoSaida,
    status_code=201,
)
def criar_comentario(
    processo_id: int,
    entrada: ComentarioProcessoEntrada,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ComentarioProcessoSaida:
    obter_processo_autorizado(sessao, usuario, processo_id, edicao=True)
    comentario = ComentarioProcessoDB(
        id_processo=processo_id,
        id_usuario=int(usuario.id),
        conteudo=entrada.conteudo.strip(),
    )
    if not comentario.conteudo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="O comentário não pode estar vazio.",
        )

    sessao.add(comentario)
    sessao.flush()
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=processo_id,
        operacao="comentario_processo_criado",
        descricao="Comentário interno adicionado ao processo.",
        dados={"id_comentario": comentario.id_comentario},
    )
    notificar_usuarios_do_processo(
        sessao,
        processo_id,
        categoria="comentario_processo",
        titulo="Novo comentário no processo",
        mensagem=f"{usuario.nome} adicionou um comentário ao processo.",
        chave=f"comentario:{comentario.id_comentario}",
        exceto_usuario_id=int(usuario.id),
    )
    sessao.commit()
    sessao.refresh(comentario)
    autor = sessao.get(UsuarioDB, int(usuario.id))
    return ComentarioProcessoSaida(
        id_comentario=comentario.id_comentario,
        id_processo=comentario.id_processo,
        id_usuario=comentario.id_usuario,
        autor=autor.nome if autor else None,
        conteudo=comentario.conteudo,
        criado_em=comentario.criado_em,
        editado_em=comentario.editado_em,
        excluido_em=comentario.excluido_em,
    )


def _comentario_proprio(
    comentario_id: int,
    usuario: UsuarioAtual,
    sessao: Session,
) -> ComentarioProcessoDB:
    comentario = sessao.get(ComentarioProcessoDB, comentario_id)
    if comentario is None:
        raise HTTPException(status_code=404, detail="Comentário não encontrado.")
    obter_processo_autorizado(sessao, usuario, comentario.id_processo, edicao=True)
    if comentario.id_usuario != int(usuario.id):
        raise HTTPException(status_code=403, detail="Somente o autor pode alterar este comentário.")
    if comentario.excluido_em is not None:
        raise HTTPException(status_code=409, detail="O comentário já foi removido.")
    return comentario


@router.patch("/comentarios/{comentario_id}", response_model=ComentarioProcessoSaida)
def atualizar_comentario(
    comentario_id: int,
    entrada: ComentarioProcessoAtualizacao,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ComentarioProcessoSaida:
    comentario = _comentario_proprio(comentario_id, usuario, sessao)
    conteudo = entrada.conteudo.strip()
    if not conteudo:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="O comentário não pode estar vazio.",
        )
    comentario.conteudo = conteudo
    comentario.editado_em = datetime.now(timezone.utc)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=comentario.id_processo,
        operacao="comentario_processo_editado",
        descricao="Comentário interno editado pelo autor.",
        dados={"id_comentario": comentario.id_comentario},
    )
    sessao.commit()
    sessao.refresh(comentario)
    autor = sessao.get(UsuarioDB, int(usuario.id))
    return ComentarioProcessoSaida(
        id_comentario=comentario.id_comentario,
        id_processo=comentario.id_processo,
        id_usuario=comentario.id_usuario,
        autor=autor.nome if autor else None,
        conteudo=comentario.conteudo,
        criado_em=comentario.criado_em,
        editado_em=comentario.editado_em,
        excluido_em=comentario.excluido_em,
    )


@router.delete("/comentarios/{comentario_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_comentario(
    comentario_id: int,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> None:
    comentario = _comentario_proprio(comentario_id, usuario, sessao)
    comentario.conteudo = "[Comentário removido]"
    comentario.excluido_em = datetime.now(timezone.utc)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=comentario.id_processo,
        operacao="comentario_processo_removido",
        descricao="Comentário interno removido pelo autor.",
        dados={"id_comentario": comentario.id_comentario},
    )
    sessao.commit()
