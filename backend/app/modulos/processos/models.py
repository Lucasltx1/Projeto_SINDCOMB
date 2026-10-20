from datetime import date, datetime, timezone

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Identity,
    Integer,
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
    token_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


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


class EmailOutboxDB(Base):
    """Fila persistente para envio e novas tentativas de e-mail."""

    __tablename__ = "email_outbox"
    __table_args__ = (
        Index("ix_email_outbox_status_next", "status", "proxima_tentativa"),
    )

    id_email: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    destinatario: Mapped[str] = mapped_column(String(255))
    assunto: Mapped[str] = mapped_column(String(255))
    corpo: Mapped[str] = mapped_column(Text)
    categoria: Mapped[str] = mapped_column(String(50), default="processo")
    id_processo: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("processo.id_processo", ondelete="SET NULL"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(30), default="pendente", index=True)
    tentativas: Mapped[int] = mapped_column(Integer, default=0)
    proxima_tentativa: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    enviado_em: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ultimo_erro: Mapped[str | None] = mapped_column(Text, nullable=True)


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


class DocumentoDB(Base):
    """Metadados de um arquivo associado a um processo ou a uma petição."""

    __tablename__ = "documento"

    id_documento: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_processo: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("processo.id_processo", ondelete="RESTRICT"), index=True
    )
    id_usuario: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuario.id_usuario", ondelete="SET NULL"), nullable=True
    )
    nome: Mapped[str] = mapped_column(String(255))
    tipo: Mapped[str | None] = mapped_column(String(100), nullable=True)
    data_upload: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    local_armazenamento: Mapped[str] = mapped_column(Text)
    tamanho: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    hash_arquivo: Mapped[str | None] = mapped_column(String(128), nullable=True)
    id_peticao: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("peticao.id_peticao", ondelete="RESTRICT"), nullable=True, unique=True
    )


class PeticaoDB(Base):
    """Cadastro da petição; o conteúdo de cada edição fica em VersaoPeticaoDB."""

    __tablename__ = "peticao"

    id_peticao: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_processo: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("processo.id_processo", ondelete="RESTRICT"), index=True
    )
    id_usuario: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuario.id_usuario", ondelete="SET NULL"), nullable=True
    )
    tipo: Mapped[str] = mapped_column(String(100))
    descricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_peticao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[str] = mapped_column(String(30), default="rascunho", index=True)


class VersaoPeticaoDB(Base):
    """Snapshot imutável do conteúdo de uma versão da petição."""

    __tablename__ = "versao_peticao"
    __table_args__ = (
        UniqueConstraint("id_peticao", "numero_versao", name="versao_peticao_numero_key"),
    )

    id_versao: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_peticao: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("peticao.id_peticao", ondelete="CASCADE"), index=True
    )
    numero_versao: Mapped[int] = mapped_column(BigInteger)
    conteudo: Mapped[str] = mapped_column(Text)
    id_usuario: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuario.id_usuario", ondelete="SET NULL"), nullable=True
    )
    data_versao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class ModeloPeticaoDB(Base):
    """Modelo reutilizável com variáveis no formato {{nome_da_variavel}}."""

    __tablename__ = "modelo_peticao"
    __table_args__ = (UniqueConstraint("nome", name="modelo_peticao_nome_key"),)

    id_modelo: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    nome: Mapped[str] = mapped_column(String(150))
    tipo: Mapped[str] = mapped_column(String(100))
    conteudo: Mapped[str] = mapped_column(Text)
    ativo: Mapped[bool] = mapped_column(Boolean, default=True)
    criado_por: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuario.id_usuario", ondelete="SET NULL"), nullable=True
    )
    criado_em: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PrazoDB(Base):
    """Prazo vinculado a processo e advogado responsável."""

    __tablename__ = "prazo"

    id_prazo: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    id_processo: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("processo.id_processo", ondelete="RESTRICT"), index=True
    )
    id_usuario: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("usuario.id_usuario", ondelete="SET NULL"), nullable=True, index=True
    )
    descricao: Mapped[str] = mapped_column(Text)
    data_inicio: Mapped[date | None] = mapped_column(Date, nullable=True)
    data_vencimento: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(30), default="pendente", index=True)


class NotificacaoDB(Base):
    """Registro legado de notificação do esquema PostgreSQL importado."""

    __tablename__ = "notificacao"

    id_notificacao: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    titulo: Mapped[str] = mapped_column(String(200))
    mensagem: Mapped[str] = mapped_column(Text)
    data_criacao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    status_leitura: Mapped[str] = mapped_column(String(20), default="nao_aplicavel")
    data_envio_email: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    id_prazo: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("prazo.id_prazo", ondelete="SET NULL"), nullable=True
    )


class UsuarioNotificacaoDB(Base):
    __tablename__ = "usuario_notificacao"

    id_usuario: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("usuario.id_usuario", ondelete="CASCADE"), primary_key=True
    )
    id_notificacao: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("notificacao.id_notificacao", ondelete="CASCADE"), primary_key=True
    )
    data_leitura: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_leitura: Mapped[str] = mapped_column(String(20), default="nao_lida")


class AssociadoNotificacaoDB(Base):
    __tablename__ = "associado_notificacao"

    id_associado: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("associado.id_associado", ondelete="CASCADE"), primary_key=True
    )
    id_notificacao: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("notificacao.id_notificacao", ondelete="CASCADE"), primary_key=True
    )
    data_envio_email: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status_envio: Mapped[str] = mapped_column(String(20), default="pendente")
