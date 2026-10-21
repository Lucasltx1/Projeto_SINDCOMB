from __future__ import annotations

from sqlalchemy import literal, select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .models import (
    AdministradorDB,
    NotificacaoInternaDB,
    PermissaoProcessoDB,
    UsuarioDB,
)


def notificar_usuarios(
    sessao: Session,
    usuario_ids: list[int],
    *,
    categoria: str,
    titulo: str,
    mensagem: str,
    processo_id: int | None = None,
    chave: str,
) -> int:
    destinatarios = list(dict.fromkeys(usuario_ids))
    if not destinatarios:
        return 0

    valores = [
        {
            "id_usuario": usuario_id,
            "id_processo": processo_id,
            "categoria": categoria[:50],
            "titulo": titulo[:200],
            "mensagem": mensagem,
            "chave_deduplicacao": chave[:200],
        }
        for usuario_id in destinatarios
    ]
    dialeto = sessao.get_bind().dialect.name
    if dialeto == "postgresql":
        comando = postgresql_insert(NotificacaoInternaDB).values(valores)
        comando = comando.on_conflict_do_nothing(
            index_elements=["id_usuario", "chave_deduplicacao"]
        )
        resultado = sessao.execute(comando)
        return resultado.rowcount or 0
    if dialeto == "sqlite":
        comando = sqlite_insert(NotificacaoInternaDB).values(valores)
        comando = comando.on_conflict_do_nothing(
            index_elements=["id_usuario", "chave_deduplicacao"]
        )
        resultado = sessao.execute(comando)
        return resultado.rowcount or 0

    existentes = set(
        sessao.scalars(
            select(NotificacaoInternaDB.id_usuario).where(
                NotificacaoInternaDB.id_usuario.in_(destinatarios),
                NotificacaoInternaDB.chave_deduplicacao == chave,
            )
        ).all()
    )
    novos = [valor for valor in valores if valor["id_usuario"] not in existentes]
    sessao.add_all(NotificacaoInternaDB(**valor) for valor in novos)
    return len(novos)


def notificar_usuarios_do_processo(
    sessao: Session,
    processo_id: int,
    *,
    categoria: str,
    titulo: str,
    mensagem: str,
    chave: str,
    exceto_usuario_id: int | None = None,
) -> int:
    consulta = (
        select(PermissaoProcessoDB.id_usuario)
        .join(UsuarioDB, UsuarioDB.id_usuario == PermissaoProcessoDB.id_usuario)
        .where(
            PermissaoProcessoDB.id_processo == processo_id,
            UsuarioDB.ativo.is_(True),
            ~UsuarioDB.id_usuario.in_(select(AdministradorDB.id_usuario)),
        )
    )
    if exceto_usuario_id is not None:
        consulta = consulta.where(PermissaoProcessoDB.id_usuario != exceto_usuario_id)
    consulta = consulta.distinct().with_only_columns(
        PermissaoProcessoDB.id_usuario,
        literal(processo_id),
        literal(categoria[:50]),
        literal(titulo[:200]),
        literal(mensagem),
        literal(chave[:200]),
    )
    colunas_destino = [
        "id_usuario",
        "id_processo",
        "categoria",
        "titulo",
        "mensagem",
        "chave_deduplicacao",
    ]
    dialeto = sessao.get_bind().dialect.name
    if dialeto == "postgresql":
        comando = postgresql_insert(NotificacaoInternaDB).from_select(
            colunas_destino, consulta
        )
        comando = comando.on_conflict_do_nothing(
            index_elements=["id_usuario", "chave_deduplicacao"]
        )
        resultado = sessao.execute(comando)
        return resultado.rowcount or 0
    if dialeto == "sqlite":
        comando = sqlite_insert(NotificacaoInternaDB).from_select(
            colunas_destino, consulta
        )
        comando = comando.on_conflict_do_nothing(
            index_elements=["id_usuario", "chave_deduplicacao"]
        )
        resultado = sessao.execute(comando)
        return resultado.rowcount or 0

    usuario_ids = list(sessao.scalars(consulta.with_only_columns(PermissaoProcessoDB.id_usuario)).all())
    return notificar_usuarios(
        sessao,
        usuario_ids,
        categoria=categoria,
        titulo=titulo,
        mensagem=mensagem,
        processo_id=processo_id,
        chave=chave,
    )
