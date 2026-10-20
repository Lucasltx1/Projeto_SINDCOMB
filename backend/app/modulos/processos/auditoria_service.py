"""Registro consistente de eventos e consultas paginadas de auditoria."""

from __future__ import annotations

import re

from sqlalchemy import desc, func, or_, select
from sqlalchemy.orm import Session

from .models import AuditoriaDB
from .schemas import AuditoriaEventoSaida, AuditoriaListaSaida

_CHAVE_SENSIVEL = re.compile(r"senha|password|token|secret|authorization|cookie|credential", re.I)


def _sanitizar_dados(valor: object) -> object:
    if isinstance(valor, dict):
        return {
            str(chave): "[REDACTED]" if _CHAVE_SENSIVEL.search(str(chave)) else _sanitizar_dados(item)
            for chave, item in valor.items()
        }
    if isinstance(valor, (list, tuple)):
        return [_sanitizar_dados(item) for item in valor]
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor
    return str(valor)


def registrar_evento(
    sessao: Session,
    *,
    operacao: str,
    descricao: str | None,
    usuario_id: int | None = None,
    processo_id: int | None = None,
    resultado: str = "sucesso",
    dados: dict[str, object] | None = None,
) -> AuditoriaDB:
    """Adiciona auditoria à transação atual; quem chama controla o commit."""
    evento = AuditoriaDB(
        id_usuario=usuario_id,
        id_processo=processo_id,
        tipo_operacao=operacao[:50],
        descricao=descricao,
        resultado=resultado[:30],
        dados_json=_sanitizar_dados(dados or {}),
    )
    sessao.add(evento)
    return evento


def _para_saida(evento: AuditoriaDB) -> AuditoriaEventoSaida:
    return AuditoriaEventoSaida(
        id=evento.id_auditoria,
        usuario_id=evento.id_usuario,
        processo_id=evento.id_processo,
        operacao=evento.tipo_operacao,
        descricao=evento.descricao,
        ocorrido_em=evento.data_hora,
        resultado=evento.resultado,
        dados=evento.dados_json or {},
    )


def _listar(
    sessao: Session,
    *,
    filtros: list,
    limite: int,
    deslocamento: int,
) -> AuditoriaListaSaida:
    total = sessao.scalar(select(func.count()).select_from(AuditoriaDB).where(*filtros)) or 0
    eventos = sessao.scalars(
        select(AuditoriaDB)
        .where(*filtros)
        .order_by(desc(AuditoriaDB.data_hora), desc(AuditoriaDB.id_auditoria))
        .limit(limite)
        .offset(deslocamento)
    ).all()
    return AuditoriaListaSaida(
        itens=[_para_saida(evento) for evento in eventos],
        total=total,
        limite=limite,
        deslocamento=deslocamento,
    )


def listar_auditoria_administrativa(
    sessao: Session,
    *,
    limite: int = 50,
    deslocamento: int = 0,
    usuario_id: int | None = None,
    operacao: str | None = None,
) -> AuditoriaListaSaida:
    """Lista somente eventos de conta; eventos processuais nunca aparecem ao admin.

    A whitelist também protege contra eventos de processo cuja FK tenha sido
    anulada por uma exclusão posterior do registro do processo.
    """
    filtros = [
        AuditoriaDB.id_processo.is_(None),
        or_(
            AuditoriaDB.tipo_operacao.like("auth.%"),
            AuditoriaDB.tipo_operacao.like("admin.%"),
        ),
    ]
    if usuario_id is not None:
        filtros.append(AuditoriaDB.id_usuario == usuario_id)
    if operacao:
        filtros.append(AuditoriaDB.tipo_operacao == operacao)
    return _listar(sessao, filtros=filtros, limite=limite, deslocamento=deslocamento)


def listar_auditoria_processo(
    sessao: Session,
    processo_id: int,
    *,
    limite: int = 50,
    deslocamento: int = 0,
) -> AuditoriaListaSaida:
    filtros = [AuditoriaDB.id_processo == processo_id]
    return _listar(sessao, filtros=filtros, limite=limite, deslocamento=deslocamento)
