from __future__ import annotations

from datetime import datetime, timedelta, timezone
import re
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
import unittest

from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from cryptography.fernet import Fernet
from sqlalchemy import BigInteger, create_engine, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.modulos.processos import auth_router as auth_routes
from app.modulos.processos.auth import UsuarioAtual, criar_access_token, obter_usuario_atual
from app.modulos.processos.auth_service import (
    MENSAGEM_SOLICITACAO,
    redefinir_senha,
    solicitar_recuperacao_senha,
)
from app.modulos.processos.email_outbox import descriptografar_corpo_email
from app.modulos.processos.auditoria_service import (
    listar_auditoria_administrativa,
    listar_auditoria_processo,
    registrar_evento,
)
from app.modulos.processos.models import (
    AdministradorDB,
    AuditoriaDB,
    Base,
    EmailOutboxDB,
    TokenVerificacaoDB,
    UsuarioDB,
)
from app.modulos.processos.schemas import LoginEntrada, SolicitarRecuperacaoSenhaEntrada
from app.modulos.processos.security import hash_password, verificar_password


@compiles(BigInteger, "sqlite")
def _bigint_as_integer(_type, _compiler, **_kw):
    # SQLite só gera IDs autoincrementais para PRIMARY KEY INTEGER.
    return "INTEGER"


class TestAuditoriaERecuperacaoSenha(unittest.TestCase):
    def setUp(self):
        self._fernet_env = patch.dict(
            "os.environ",
            {"SINDCOMB_EMAIL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii")},
        )
        self._fernet_env.start()
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.sessao = self.Session()
        self.usuario = UsuarioDB(
            id_usuario=1,
            nome="Advogada de Teste",
            username="advogada.teste",
            email="advogada@example.com",
            senha=hash_password("SenhaAnteriorSegura!2026"),
            primeiro_acesso=True,
            ativo=True,
            email_verificado=True,
        )
        self.sessao.add(self.usuario)
        self.sessao.commit()

    def tearDown(self):
        self.sessao.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        self._fernet_env.stop()

    def test_hash_scrypt_usa_parametros_recomendados_e_valida_senhas_existentes(self):
        valor = "SenhaForteDeTeste!2026"
        hash_atual = hash_password(valor)
        partes = hash_atual.split("$")

        self.assertEqual(partes[:4], ["scrypt", str(1 << 14), "8", "5"])
        self.assertTrue(verificar_password(valor, hash_atual))

    def _solicitar_token(self) -> str:
        self.assertTrue(solicitar_recuperacao_senha(self.sessao, self.usuario.email))
        email = self.sessao.scalar(
            select(EmailOutboxDB).where(EmailOutboxDB.categoria == "recuperacao_senha")
        )
        self.assertIsNotNone(email)
        self.assertTrue(email.corpo.startswith("fernet:v1:"))
        corpo = descriptografar_corpo_email(email.corpo)
        link = re.search(r"https?://\S+", corpo)
        self.assertIsNotNone(link)
        return parse_qs(urlsplit(link.group(0)).fragment)["token"][0]

    def test_solicitacao_responde_mensagem_generica_para_contas_existentes_e_inexistentes(self):
        resposta_existente = auth_routes.solicitar_redefinicao_senha(
            SolicitarRecuperacaoSenhaEntrada(email=self.usuario.email), self.sessao
        )
        resposta_inexistente = auth_routes.solicitar_redefinicao_senha(
            SolicitarRecuperacaoSenhaEntrada(email="nao-existe@example.com"), self.sessao
        )

        self.assertEqual(resposta_existente, resposta_inexistente)
        self.assertEqual(resposta_existente["mensagem"], MENSAGEM_SOLICITACAO)

    def test_token_de_recuperacao_fica_hash_e_so_pode_ser_usado_uma_vez(self):
        token = self._solicitar_token()
        registro = self.sessao.scalar(
            select(TokenVerificacaoDB).where(TokenVerificacaoDB.tipo == "redefinicao_senha")
        )
        self.assertIsNotNone(registro)
        self.assertNotEqual(registro.token_hash, token)
        self.assertEqual(len(registro.token_hash), 64)

        sucesso = redefinir_senha(self.sessao, token, "SenhaNovaSegura!2026")
        repetido = redefinir_senha(self.sessao, token, "OutraSenhaSegura!2026")

        self.assertTrue(sucesso)
        self.assertFalse(repetido)
        self.assertTrue(verificar_password("SenhaNovaSegura!2026", self.usuario.senha))
        self.assertFalse(self.usuario.primeiro_acesso)
        self.assertEqual(self.usuario.token_version, 1)
        self.assertEqual(
            self.sessao.scalar(select(TokenVerificacaoDB).where(TokenVerificacaoDB.tipo == "redefinicao_senha")),
            None,
        )
        self.assertEqual(
            self.sessao.scalar(
                select(EmailOutboxDB.status).where(EmailOutboxDB.categoria == "recuperacao_senha")
            ),
            "cancelado",
        )
        email = self.sessao.scalar(
            select(EmailOutboxDB).where(EmailOutboxDB.categoria == "recuperacao_senha")
        )
        self.assertEqual(email.corpo, "")

    def test_repetir_solicitacao_no_intervalo_nao_cria_outro_email_ou_token(self):
        self.assertTrue(solicitar_recuperacao_senha(self.sessao, self.usuario.email))
        self.assertTrue(solicitar_recuperacao_senha(self.sessao, self.usuario.email))

        emails = self.sessao.scalars(
            select(EmailOutboxDB).where(EmailOutboxDB.categoria == "recuperacao_senha")
        ).all()
        tokens = self.sessao.scalars(
            select(TokenVerificacaoDB).where(TokenVerificacaoDB.tipo == "redefinicao_senha")
        ).all()
        self.assertEqual(len(emails), 1)
        self.assertEqual(len(tokens), 1)

    def test_redefinicao_invalida_sessoes_anteriores(self):
        token = self._solicitar_token()
        with patch.dict("os.environ", {"SINDCOMB_AUTH_SECRET": "x" * 40}):
            sessao_antiga = criar_access_token(self.usuario, "visualizador")
            credenciais = HTTPAuthorizationCredentials(scheme="Bearer", credentials=sessao_antiga)
            self.assertIsInstance(obter_usuario_atual(credenciais=credenciais, sessao=self.sessao), UsuarioAtual)

            redefinir_senha(self.sessao, token, "SenhaNovaSegura!2026")
            with self.assertRaises(HTTPException) as erro:
                obter_usuario_atual(credenciais=credenciais, sessao=self.sessao)

        self.assertEqual(erro.exception.status_code, 401)
        self.assertIn("invalidada", erro.exception.detail)

    def test_login_registra_sucesso_e_falha_sem_gravar_credenciais(self):
        with patch.dict("os.environ", {"SINDCOMB_AUTH_SECRET": "x" * 40}):
            resposta = auth_routes.login(
                LoginEntrada(usuario=self.usuario.email, senha="SenhaAnteriorSegura!2026"),
                self.sessao,
            )
            self.assertTrue(resposta.csrf_token)
            with self.assertRaises(HTTPException) as erro:
                auth_routes.login(
                    LoginEntrada(usuario=self.usuario.email, senha="senha-incorreta"),
                    self.sessao,
                )

        eventos = self.sessao.scalars(
            select(AuditoriaDB).where(AuditoriaDB.tipo_operacao.like("auth.login_%"))
        ).all()
        operacoes = {evento.tipo_operacao for evento in eventos}
        self.assertEqual(erro.exception.status_code, 401)
        self.assertEqual(operacoes, {"auth.login_succeeded", "auth.login_failed"})
        self.assertTrue(all("senha" not in str(evento.dados_json).lower() for evento in eventos))

    def test_conta_administrativa_nao_recebe_recuperacao(self):
        admin = UsuarioDB(
            id_usuario=2,
            nome="Administrador",
            username="adm_sindcomb",
            # Mesmo um registro legado incorreto com e-mail não deve habilitar
            # recuperação para a conta administrativa.
            email="admin@example.com",
            senha=hash_password("SenhaAdminFixa!2026"),
            primeiro_acesso=False,
            ativo=True,
            email_verificado=False,
        )
        self.sessao.add(admin)
        self.sessao.flush()
        self.sessao.add(AdministradorDB(id_usuario=admin.id_usuario))
        self.sessao.commit()

        self.assertFalse(solicitar_recuperacao_senha(self.sessao, admin.email))
        self.assertEqual(
            self.sessao.scalar(select(EmailOutboxDB).where(EmailOutboxDB.categoria == "recuperacao_senha")),
            None,
        )

    def test_token_expirado_nao_altera_a_senha(self):
        token = "token-de-testes-suficientemente-grande-para-validar"
        import hashlib

        self.sessao.add(
            TokenVerificacaoDB(
                id_usuario=self.usuario.id_usuario,
                tipo="redefinicao_senha",
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                expira_em=datetime.now(timezone.utc) - timedelta(minutes=1),
            )
        )
        self.sessao.commit()

        self.assertFalse(redefinir_senha(self.sessao, token, "SenhaNovaSegura!2026"))
        self.assertTrue(verificar_password("SenhaAnteriorSegura!2026", self.usuario.senha))

    def test_auditoria_remove_segredos_e_admin_nao_consulta_evento_processual(self):
        evento_seguro = registrar_evento(
            self.sessao,
            usuario_id=self.usuario.id_usuario,
            operacao="auth.password_changed",
            descricao="Senha atualizada.",
            dados={"access_token": "segredo", "meta": {"password": "outra"}, "sessoes_invalidadas": True},
        )
        evento_processo = AuditoriaDB(
            id_usuario=self.usuario.id_usuario,
            id_processo=None,  # Mesmo desvinculado, não deve vazar para a auditoria administrativa.
            tipo_operacao="process.status_changed",
            descricao="Movimentação confidencial do processo.",
            resultado="sucesso",
            dados_json={"processo": "0012345-67.2026.8.19.0001"},
        )
        self.sessao.add(evento_processo)
        self.sessao.commit()

        auditoria_admin = listar_auditoria_administrativa(self.sessao)
        auditoria_processo = listar_auditoria_processo(self.sessao, 99)

        self.assertEqual(auditoria_admin.total, 1)
        self.assertEqual(auditoria_admin.itens[0].id, evento_seguro.id_auditoria)
        self.assertEqual(auditoria_admin.itens[0].dados["access_token"], "[REDACTED]")
        self.assertEqual(auditoria_admin.itens[0].dados["meta"]["password"], "[REDACTED]")
        self.assertEqual(auditoria_processo.total, 0)


if __name__ == "__main__":
    unittest.main()
