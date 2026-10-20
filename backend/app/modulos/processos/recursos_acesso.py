from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .auth import UsuarioAtual
from .auditoria_service import registrar_evento
from .models import PermissaoProcessoDB, ProcessoDB


def obter_processo_autorizado(
    sessao: Session,
    usuario: UsuarioAtual,
    processo_id: int,
    *,
    edicao: bool = False,
    permitir_arquivado: bool = False,
) -> tuple[ProcessoDB, PermissaoProcessoDB]:
    if usuario.papel == "administrador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="A conta administrativa não tem acesso às informações dos processos.",
        )

    processo = sessao.get(ProcessoDB, processo_id)
    if processo is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Processo não encontrado.")

    permissao = sessao.scalar(
        select(PermissaoProcessoDB).where(
            PermissaoProcessoDB.id_usuario == int(usuario.id),
            PermissaoProcessoDB.id_processo == processo_id,
        )
    )
    if permissao is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Processo não encontrado.",
        )

    if edicao:
        if usuario.papel != "advogado":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Somente advogados podem alterar documentos, petições e prazos.",
            )
        if permissao.nivel_acesso not in {"edicao", "total"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Sua permissão neste processo permite somente leitura.",
            )
        if processo.arquivado and not permitir_arquivado:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Este processo está arquivado. Desarquive-o antes de editar.",
            )
    return processo, permissao


def registrar_auditoria(
    sessao: Session,
    *,
    usuario_id: int,
    processo_id: int | None,
    operacao: str,
    descricao: str,
    dados: dict[str, object] | None = None,
) -> None:
    registrar_evento(
        sessao,
        usuario_id=usuario_id,
        processo_id=processo_id,
        operacao=operacao,
        descricao=descricao,
        dados=dados,
    )
