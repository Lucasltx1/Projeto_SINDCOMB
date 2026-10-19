from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.nucleo.database import Base


class UsuarioDB(Base):
    __tablename__ = "usuario"
    __table_args__ = (UniqueConstraint("email", name="usuario_email_key"),)

    id_usuario: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    username: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    senha: Mapped[str] = mapped_column(Text)
    primeiro_acesso: Mapped[bool] = mapped_column(Boolean, default=True)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    email_verificado: Mapped[bool] = mapped_column(Boolean, default=False)


class AdministradorDB(Base):
    __tablename__ = "administrador"

    id_usuario: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuario.id_usuario", ondelete="CASCADE"),
        primary_key=True,
    )


class ConfiguracaoSistemaDB(Base):
    """Marcadores persistentes de configuração que não podem depender do .env."""

    __tablename__ = "configuracao_sistema"

    chave: Mapped[str] = mapped_column(String(100), primary_key=True)
    valor: Mapped[str] = mapped_column(Text)


class JuridicoDB(Base):
    __tablename__ = "juridico"
    __table_args__ = (UniqueConstraint("oab", name="juridico_oab_key"),)

    id_usuario: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuario.id_usuario", ondelete="CASCADE"),
        primary_key=True,
    )
    oab: Mapped[str] = mapped_column(String(30))


class AssociadoDB(Base):
    __tablename__ = "associado"
    __table_args__ = (UniqueConstraint("cpf", name="associado_cpf_key"),)

    id_associado: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    cpf: Mapped[str | None] = mapped_column(String(14), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telefone: Mapped[str | None] = mapped_column(String(25), nullable=True)


class ProcessoDB(Base):
    """Processo de negócio persistido na tabela canônica do esquema PostgreSQL."""

    __tablename__ = "processo"
    __table_args__ = (UniqueConstraint("numero_processo", name="processo_numero_processo_key"),)

    id_processo: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    numero_processo: Mapped[str] = mapped_column(String(50))
    tribunal: Mapped[str] = mapped_column(String(120), index=True)
    tribunal_alias: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tipo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    assunto: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="novo", index=True)
    data_abertura: Mapped[date] = mapped_column(Date, default=date.today)
    data_encerramento: Mapped[date | None] = mapped_column(Date, nullable=True)
    arquivado: Mapped[bool] = mapped_column(Boolean, default=False)
    dados_json: Mapped[dict] = mapped_column(JSON)
    triagem_json: Mapped[dict] = mapped_column(JSON)
    criado_por: Mapped[str] = mapped_column(String(200))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    atualizado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class PrazoDB(Base):
    """Representa um prazo processual no banco de dados."""

    __tablename__ = "prazo"

    id_prazo: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=True),
        primary_key=True
    )

    id_processo: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("processo.id_processo", ondelete="RESTRICT"),
        nullable=False
    )

    id_usuario: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuario.id_usuario", ondelete="RESTRICT"),
        nullable=False
    )

    descricao: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )

    data_inicio: Mapped[date | None] = mapped_column(
        Date,
        nullable=True
    )

    data_vencimento: Mapped[date] = mapped_column(
        Date,
        nullable=False
    )

    status: Mapped[str] = mapped_column(
        String(30),
        default="pendente",
        nullable=False
    )

class ProcessoAssociadoDB(Base):
    __tablename__ = "processo_associado"

    id_processo: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("processo.id_processo", ondelete="CASCADE"),
        primary_key=True,
    )
    id_associado: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("associado.id_associado", ondelete="RESTRICT"),
        primary_key=True,
    )


class PermissaoProcessoDB(Base):
    __tablename__ = "permissao_processo"
    __table_args__ = (
        UniqueConstraint("id_usuario", "id_processo", name="permissao_processo_id_usuario_id_processo_key"),
    )

    id_permissao: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_usuario: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuario.id_usuario", ondelete="RESTRICT"),
    )
    id_processo: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("processo.id_processo", ondelete="CASCADE"),
    )
    nivel_acesso: Mapped[str] = mapped_column(String(30), default="advogado")
    data_concessao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class LinhaTempoDB(Base):
    __tablename__ = "linha_tempo"

    id_evento: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_processo: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("processo.id_processo", ondelete="RESTRICT"),
        index=True,
    )
    id_usuario: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
        nullable=True,
    )
    data_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    descricao: Mapped[str] = mapped_column(Text)
    tipo_evento: Mapped[str] = mapped_column(String(50))
    origem: Mapped[str] = mapped_column(String(30))
    dados_json: Mapped[dict] = mapped_column(JSON, default=dict)


class AuditoriaDB(Base):
    __tablename__ = "auditoria"

    id_auditoria: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_usuario: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("usuario.id_usuario", ondelete="SET NULL"),
        nullable=True,
    )
    id_processo: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("processo.id_processo", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    tipo_operacao: Mapped[str] = mapped_column(String(50))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    resultado: Mapped[str] = mapped_column(String(30), default="sucesso")
    dados_json: Mapped[dict] = mapped_column(JSON, default=dict)


class RegistroSincronizacao(Base):
    __tablename__ = "sincronizacao"

    id_sincronizacao: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_processo: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("processo.id_processo", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    data_hora: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    status: Mapped[str] = mapped_column(String(30))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantidade_atualizacoes: Mapped[int] = mapped_column(default=0)


class TokenVerificacaoDB(Base):
    __tablename__ = "token_verificacao_usuario"
    __table_args__ = (UniqueConstraint("token_hash", name="token_verificacao_usuario_token_hash_key"),)

    id_token: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_usuario: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("usuario.id_usuario", ondelete="CASCADE"),
        index=True,
    )
    tipo: Mapped[str] = mapped_column(String(30))
    token_hash: Mapped[str] = mapped_column(String(64))
    expira_em: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
