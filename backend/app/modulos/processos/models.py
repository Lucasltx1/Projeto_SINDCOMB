from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.nucleo.database import Base


class ParteMonitorada(Base):
    __tablename__ = "partes_monitoradas"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    nome: Mapped[str] = mapped_column(String(300), index=True)
    tipo: Mapped[str] = mapped_column(String(30), index=True)
    tribunais: Mapped[list[str]] = mapped_column(JSON, default=list)
    ativa: Mapped[bool] = mapped_column(Boolean, default=True)
    criada_por: Mapped[str] = mapped_column(String(200))
    criada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ProcessoDB(Base):
    __tablename__ = "processos"
    __table_args__ = (UniqueConstraint("numero", "tribunal", name="uq_processo_numero_tribunal"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    numero: Mapped[str] = mapped_column(String(80), index=True)
    tribunal: Mapped[str] = mapped_column(String(120), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True)
    dados_json: Mapped[dict] = mapped_column(JSON)
    triagem_json: Mapped[dict] = mapped_column(JSON)
    movimentacoes_json: Mapped[list] = mapped_column(JSON, default=list)
    historico_status_json: Mapped[list] = mapped_column(JSON, default=list)
    criado_por: Mapped[str] = mapped_column(String(200))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )


class RegistroSincronizacao(Base):
    __tablename__ = "sincronizacoes_datajud"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    processo_id: Mapped[str] = mapped_column(String(36), index=True)
    numero: Mapped[str] = mapped_column(String(80))
    tribunal: Mapped[str] = mapped_column(String(40))
    consultada_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    encontrado: Mapped[bool] = mapped_column(Boolean, default=False)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
