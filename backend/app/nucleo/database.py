from collections.abc import Generator
import logging
import os

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

logger = logging.getLogger(__name__)
ADMINISTRADOR_USERNAME = "adm_sindcomb"


class Base(DeclarativeBase):
    pass


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://sindcomb:dev-only-password@localhost:5432/sindcomb",
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


_EXTENSOES_POSTGRES = (
    "ALTER TABLE public.usuario ALTER COLUMN email DROP NOT NULL",
    "ALTER TABLE public.usuario ADD COLUMN IF NOT EXISTS email_verificado BOOLEAN NOT NULL DEFAULT FALSE",
    "ALTER TABLE public.usuario ADD COLUMN IF NOT EXISTS username VARCHAR(80)",
    "ALTER TABLE public.usuario ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE public.processo ADD COLUMN IF NOT EXISTS tribunal VARCHAR(120) NOT NULL DEFAULT 'desconhecido'",
    "ALTER TABLE public.processo ADD COLUMN IF NOT EXISTS tribunal_alias VARCHAR(20)",
    "ALTER TABLE public.processo ADD COLUMN IF NOT EXISTS dados_json JSON NOT NULL DEFAULT '{}'::json",
    "ALTER TABLE public.processo ADD COLUMN IF NOT EXISTS triagem_json JSON NOT NULL DEFAULT '{}'::json",
    "ALTER TABLE public.processo ADD COLUMN IF NOT EXISTS criado_por VARCHAR(200) NOT NULL DEFAULT ''",
    "ALTER TABLE public.processo ADD COLUMN IF NOT EXISTS criado_em TIMESTAMPTZ NOT NULL DEFAULT now()",
    "ALTER TABLE public.processo ADD COLUMN IF NOT EXISTS atualizado_em TIMESTAMPTZ NOT NULL DEFAULT now()",
    "ALTER TABLE public.linha_tempo ADD COLUMN IF NOT EXISTS dados_json JSON NOT NULL DEFAULT '{}'::json",
    "ALTER TABLE public.auditoria ADD COLUMN IF NOT EXISTS dados_json JSON NOT NULL DEFAULT '{}'::json",
    "ALTER TABLE public.comentario_processo ADD COLUMN IF NOT EXISTS editado_em TIMESTAMPTZ",
    "ALTER TABLE public.comentario_processo ADD COLUMN IF NOT EXISTS excluido_em TIMESTAMPTZ",
    "ALTER TABLE public.prazo_lembrete DROP CONSTRAINT IF EXISTS prazo_lembrete_idempotente_key",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_prazo_lembrete_destinatario ON public.prazo_lembrete (id_prazo, tipo, data_referencia, id_usuario)",
    # Preserva o histórico jurídico, removendo apenas a referência de autoria
    # quando um advogado é excluído pelo administrador.
    "ALTER TABLE public.peticao ALTER COLUMN id_usuario DROP NOT NULL",
    "ALTER TABLE public.prazo ALTER COLUMN id_usuario DROP NOT NULL",
    "ALTER TABLE public.peticao DROP CONSTRAINT IF EXISTS peticao_id_usuario_fkey",
    "ALTER TABLE public.peticao ADD CONSTRAINT peticao_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE SET NULL",
    "ALTER TABLE public.prazo DROP CONSTRAINT IF EXISTS prazo_id_usuario_fkey",
    "ALTER TABLE public.prazo ADD CONSTRAINT prazo_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE SET NULL",
    "CREATE INDEX IF NOT EXISTS ix_prazo_status_vencimento_id ON public.prazo (status, data_vencimento, id_prazo)",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_usuario_email_lower ON public.usuario (lower(email))",
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_usuario_username_lower ON public.usuario (lower(username)) WHERE username IS NOT NULL",
)


def _criar_administrador_inicial() -> None:
    from app.modulos.processos.models import (
        AdministradorDB,
        ConfiguracaoSistemaDB,
        UsuarioDB,
    )
    from app.modulos.processos.security import hash_password, verificar_password
    from app.nucleo.seguranca_config import validar_senha_administrativa_inicial

    with SessionLocal() as sessao:
        chave_bootstrap = "administrador_inicial_configurado"
        marcador = sessao.get(ConfiguracaoSistemaDB, chave_bootstrap)
        administradores = sessao.scalars(select(AdministradorDB.id_usuario)).all()

        def impedir_senha_conhecida_em_producao(usuario_id: int) -> None:
            if os.getenv("SINDCOMB_ENVIRONMENT", "development").strip().casefold() != "production":
                return
            conta = sessao.get(UsuarioDB, usuario_id)
            if conta is not None and verificar_password("adm123", conta.senha):
                raise RuntimeError(
                    "A senha administrativa conhecida de desenvolvimento ainda está ativa. "
                    "Atualize a credencial diretamente no PostgreSQL antes de usar produção."
                )

        if len(administradores) > 1:
            raise RuntimeError(
                "Mais de um administrador foi encontrado. Resolva os cadastros no PostgreSQL "
                "antes de iniciar a aplicação com o login administrativo fixo."
            )

        def fixar_identidade_admin(usuario_id: int) -> bool:
            conta = sessao.get(UsuarioDB, usuario_id)
            if conta is None:
                raise RuntimeError("O vínculo administrativo aponta para uma conta inexistente.")
            ocupante = sessao.scalar(
                select(UsuarioDB.id_usuario).where(
                    func.lower(UsuarioDB.username) == ADMINISTRADOR_USERNAME,
                    UsuarioDB.id_usuario != usuario_id,
                )
            )
            if ocupante is not None:
                raise RuntimeError(
                    f"O nome de usuário {ADMINISTRADOR_USERNAME} já pertence a outra conta."
                )
            alterada = (
                conta.username != ADMINISTRADOR_USERNAME
                or conta.primeiro_acesso
                or conta.email is not None
                or conta.email_verificado
            )
            conta.username = ADMINISTRADOR_USERNAME
            conta.email = None
            conta.email_verificado = False
            conta.primeiro_acesso = False
            return alterada

        if marcador is not None:
            if not administradores:
                raise RuntimeError(
                    "O bootstrap do administrador já foi concluído, mas a conta não existe. "
                    "A recuperação deve ser feita pelo operador diretamente no PostgreSQL."
                )
            impedir_senha_conhecida_em_producao(administradores[0])
            identidade_alterada = fixar_identidade_admin(administradores[0])
            if identidade_alterada:
                sessao.commit()
            logger.info("Bootstrap do administrador já concluído; nenhum novo administrador será criado.")
            return

        # Compatibilidade: sela a instalação em que o administrador já existia antes
        # da introdução do marcador persistente.
        if administradores:
            impedir_senha_conhecida_em_producao(administradores[0])
            fixar_identidade_admin(administradores[0])
            sessao.add(ConfiguracaoSistemaDB(chave=chave_bootstrap, valor="concluido"))
            sessao.commit()
            logger.info("Administrador existente detectado; bootstrap foi bloqueado permanentemente.")
            return

        senha = os.getenv("SINDCOMB_BOOTSTRAP_ADMIN_PASSWORD", "")
        if not senha:
            raise RuntimeError(
                "Defina SINDCOMB_BOOTSTRAP_ADMIN_PASSWORD para provisionar o administrador inicial."
            )
        validar_senha_administrativa_inicial(senha)

        usuario = UsuarioDB(
            nome="Administrador SINDCOMB",
            username=ADMINISTRADOR_USERNAME,
            email=None,
            senha=hash_password(senha),
            primeiro_acesso=False,
            ativo=True,
            email_verificado=False,
        )
        sessao.add(usuario)
        sessao.flush()
        sessao.add(AdministradorDB(id_usuario=usuario.id_usuario))
        sessao.add(ConfiguracaoSistemaDB(chave=chave_bootstrap, valor="concluido"))
        try:
            sessao.commit()
        except IntegrityError:
            sessao.rollback()
            # Duas instâncias podem iniciar juntas; a chave única do marcador
            # permite que apenas uma conclua o provisionamento.
            bootstrap_concluido = sessao.get(ConfiguracaoSistemaDB, chave_bootstrap)
            administrador_criado = sessao.scalars(
                select(AdministradorDB.id_usuario).limit(1)
            ).first()
            if bootstrap_concluido is None or administrador_criado is None:
                raise
            logger.info("Outra instância concluiu o bootstrap do administrador.")
            return
        logger.info("Administrador inicial provisionado; novos administradores não serão criados pela aplicação.")


def criar_tabelas() -> None:
    from app.modulos.processos import models as _models  # noqa: F401
    from app.modulos.processos.email_outbox import proteger_outbox_legada

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conexao:
        for comando in _EXTENSOES_POSTGRES:
            conexao.execute(text(comando))
    with SessionLocal() as sessao:
        proteger_outbox_legada(sessao)
    _criar_administrador_inicial()


def obter_sessao() -> Generator[Session, None, None]:
    sessao = SessionLocal()
    try:
        yield sessao
    finally:
        sessao.close()
