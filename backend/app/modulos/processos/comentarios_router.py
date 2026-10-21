from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .auth import UsuarioAtual, exigir_advogado
from .models import ComentarioProcessoDB, UsuarioDB
from .recursos_acesso import obter_processo_autorizado, registrar_auditoria
from .recursos_schemas import ComentarioProcessoEntrada, ComentarioProcessoSaida

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
            conteudo=comentario.conteudo,
            criado_em=comentario.criado_em,
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
    )
