from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select, update
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .auth import UsuarioAtual, exigir_acesso_processos
from .models import NotificacaoInternaDB, PermissaoProcessoDB
from .recursos_schemas import NotificacaoInternaSaida, NotificacoesListaSaida

router = APIRouter(prefix="/api/v1/notificacoes", tags=["Notificações"])


def _notificacoes_visiveis(usuario_id: int):
    processo_autorizado = select(PermissaoProcessoDB.id_processo).where(
        PermissaoProcessoDB.id_usuario == usuario_id
    )
    return or_(
        NotificacaoInternaDB.id_processo.is_(None),
        NotificacaoInternaDB.id_processo.in_(processo_autorizado),
    )


@router.get("", response_model=NotificacoesListaSaida)
def listar_notificacoes(
    somente_nao_lidas: bool = False,
    limite: int = Query(default=50, ge=1, le=100),
    deslocamento: int = Query(default=0, ge=0),
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> NotificacoesListaSaida:
    usuario_id = int(usuario.id)
    filtros = [
        NotificacaoInternaDB.id_usuario == usuario_id,
        _notificacoes_visiveis(usuario_id),
    ]
    if somente_nao_lidas:
        filtros.append(NotificacaoInternaDB.lida_em.is_(None))
    itens = sessao.scalars(
        select(NotificacaoInternaDB)
        .where(*filtros)
        .order_by(NotificacaoInternaDB.criado_em.desc(), NotificacaoInternaDB.id_notificacao.desc())
        .limit(limite)
        .offset(deslocamento)
    ).all()
    total = sessao.scalar(
        select(func.count()).select_from(NotificacaoInternaDB).where(*filtros)
    ) or 0
    nao_lidas = sessao.scalar(
        select(func.count()).select_from(NotificacaoInternaDB).where(
            NotificacaoInternaDB.id_usuario == usuario_id,
            NotificacaoInternaDB.lida_em.is_(None),
            _notificacoes_visiveis(usuario_id),
        )
    ) or 0
    return NotificacoesListaSaida(
        itens=itens,
        total=total,
        nao_lidas=nao_lidas,
        limite=limite,
        deslocamento=deslocamento,
    )


@router.patch("/{notificacao_id}/ler", response_model=NotificacaoInternaSaida)
def marcar_como_lida(
    notificacao_id: int,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> NotificacaoInternaDB:
    usuario_id = int(usuario.id)
    notificacao = sessao.scalar(
        select(NotificacaoInternaDB).where(
            NotificacaoInternaDB.id_notificacao == notificacao_id,
            NotificacaoInternaDB.id_usuario == usuario_id,
            _notificacoes_visiveis(usuario_id),
        )
    )
    if notificacao is None:
        raise HTTPException(status_code=404, detail="Notificação não encontrada.")
    if notificacao.lida_em is None:
        notificacao.lida_em = datetime.now(timezone.utc)
        sessao.commit()
        sessao.refresh(notificacao)
    return notificacao


@router.post("/ler-todas", status_code=status.HTTP_204_NO_CONTENT)
def marcar_todas_como_lidas(
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> None:
    sessao.execute(
        update(NotificacaoInternaDB)
        .where(
            NotificacaoInternaDB.id_usuario == int(usuario.id),
            NotificacaoInternaDB.lida_em.is_(None),
            _notificacoes_visiveis(int(usuario.id)),
        )
        .values(lida_em=datetime.now(timezone.utc))
        .execution_options(synchronize_session=False)
    )
    sessao.commit()
