from __future__ import annotations

from datetime import date
import os
from unittest.mock import patch
import unittest

from cryptography.fernet import Fernet
from sqlalchemy import BigInteger, create_engine
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.modulos.processos.email_outbox import (
    descriptografar_corpo_email,
    proteger_corpo_email,
    proteger_outbox_legada,
)
from app.modulos.processos.models import (
    AssociadoDB,
    AssociadoNotificacaoDB,
    Base,
    DocumentoDB,
    EmailOutboxDB,
    ModeloPeticaoDB,
    NotificacaoDB,
    PeticaoDB,
    PrazoDB,
    ProcessoDB,
    UsuarioDB,
    UsuarioNotificacaoDB,
    VersaoPeticaoDB,
)
from app.modulos.processos.repository import limpar_referencias_pessoa
from app.modulos.processos.security import hash_password


@compiles(BigInteger, "sqlite")
def _bigint_as_integer(_type, _compiler, **_kw):
    return "INTEGER"


class TestLimpezaDeReferencias(unittest.TestCase):
    def setUp(self):
        self._fernet_env = patch.dict(
            os.environ,
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
        self.sessao.add(
            UsuarioDB(
                id_usuario=1,
                nome="Maria Silva",
                username="maria.silva",
                email="maria@example.com",
                senha=hash_password("SenhaForteDeTeste!2026"),
                primeiro_acesso=False,
                ativo=True,
                email_verificado=True,
            )
        )
        self.sessao.add(
            AssociadoDB(
                id_associado=2,
                nome="Maria Silva",
                cpf="123.456.789-00",
                email="maria@example.com",
            )
        )
        self.sessao.add(
            ProcessoDB(
                id_processo=10,
                numero_processo="0000001-00.2026.8.19.0001",
                tribunal="Tribunal de Justiça",
                status="em_acompanhamento",
                data_abertura=date(2026, 1, 1),
                arquivado=False,
                dados_json={"numero": "0000001-00.2026.8.19.0001", "partes": ["Maria Silva"]},
                triagem_json={
                    "relevancia": "interesse_direto",
                    "justificativa": "Maria Silva consta como parte.",
                    "evidencias": ["Maria Silva"],
                    "confianca": 0.9,
                },
                criado_por="1",
            )
        )
        self.sessao.add_all(
            [
                DocumentoDB(
                    id_documento=30,
                    id_processo=10,
                    id_usuario=1,
                    nome="Petição de Maria Silva.pdf",
                    local_armazenamento="processos/10/file.pdf",
                ),
                PeticaoDB(
                    id_peticao=40,
                    id_processo=10,
                    id_usuario=1,
                    tipo="Petição de Maria Silva",
                    descricao="Documento preparado por Maria Silva",
                ),
                VersaoPeticaoDB(
                    id_versao=50,
                    id_peticao=40,
                    numero_versao=1,
                    id_usuario=1,
                    conteudo="Maria Silva, parte interessada.",
                ),
                ModeloPeticaoDB(
                    id_modelo=60,
                    nome="Modelo Maria Silva",
                    tipo="petição",
                    conteudo="Representante: Maria Silva",
                    criado_por=1,
                ),
                PrazoDB(
                    id_prazo=70,
                    id_processo=10,
                    id_usuario=1,
                    descricao="Prazo para Maria Silva",
                    data_vencimento=date(2026, 12, 1),
                    status="pendente",
                ),
                NotificacaoDB(
                    id_notificacao=80,
                    titulo="Prazo de Maria Silva",
                    mensagem="Maria Silva precisa revisar o prazo.",
                    id_prazo=70,
                ),
                UsuarioNotificacaoDB(id_usuario=1, id_notificacao=80),
                AssociadoNotificacaoDB(id_associado=2, id_notificacao=80),
                EmailOutboxDB(
                    destinatario="colega@example.com",
                    assunto="Atualização de Maria Silva",
                    corpo=proteger_corpo_email("O processo de Maria Silva foi atualizado."),
                    categoria="atualizacao_processo",
                    status="pendente",
                ),
                EmailOutboxDB(
                    destinatario="maria@example.com",
                    assunto="Atualização de processo",
                    corpo=proteger_corpo_email("Seu processo foi atualizado."),
                    categoria="atualizacao_processo",
                    status="pendente",
                ),
            ]
        )
        self.sessao.commit()

    def tearDown(self):
        self.sessao.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()
        self._fernet_env.stop()

    def test_remove_referencias_textuais_e_cancela_email_da_pessoa(self):
        quantidade = limpar_referencias_pessoa(
            self.sessao,
            ["Maria Silva", "maria@example.com"],
            id_usuario=1,
            id_associado=2,
        )

        self.assertGreater(quantidade, 0)
        self.assertNotIn("Maria Silva", str(self.sessao.get(ProcessoDB, 10).dados_json))
        self.assertEqual(self.sessao.get(DocumentoDB, 30).id_usuario, None)
        self.assertNotIn("Maria Silva", self.sessao.get(DocumentoDB, 30).nome)
        self.assertEqual(self.sessao.get(PeticaoDB, 40).id_usuario, None)
        self.assertNotIn("Maria Silva", self.sessao.get(PeticaoDB, 40).descricao)
        self.assertNotIn("Maria Silva", self.sessao.get(VersaoPeticaoDB, 50).conteudo)
        self.assertNotIn("Maria Silva", self.sessao.get(ModeloPeticaoDB, 60).conteudo)
        self.assertNotIn("Maria Silva", self.sessao.get(PrazoDB, 70).descricao)
        notificacao = self.sessao.get(NotificacaoDB, 80)
        self.assertNotIn("Maria Silva", notificacao.titulo + notificacao.mensagem)
        self.assertIsNone(self.sessao.get(UsuarioNotificacaoDB, (1, 80)))
        self.assertIsNone(self.sessao.get(AssociadoNotificacaoDB, (2, 80)))

        emails = self.sessao.query(EmailOutboxDB).order_by(EmailOutboxDB.id_email).all()
        self.assertNotIn("Maria Silva", descriptografar_corpo_email(emails[0].corpo))
        self.assertEqual(emails[1].status, "cancelado")
        self.assertEqual(emails[1].corpo, "")
        self.assertNotEqual(emails[1].destinatario, "maria@example.com")
        self.assertEqual(
            self.sessao.get(ProcessoDB, 10).triagem_json["relevancia"],
            "revisar",
        )

    def test_migracao_cifra_pendencias_legadas_e_apaga_corpos_encerrados(self):
        pendente = EmailOutboxDB(
            destinatario="colega@example.com",
            assunto="Atualização privada",
            corpo="Corpo legado com informações processuais",
            categoria="atualizacao_processo",
            status="pendente",
        )
        enviado = EmailOutboxDB(
            destinatario="colega@example.com",
            assunto="Atualização privada",
            corpo="Corpo já enviado",
            categoria="atualizacao_processo",
            status="enviado",
        )
        self.sessao.add_all([pendente, enviado])
        self.sessao.commit()

        alteradas = proteger_outbox_legada(self.sessao)

        self.assertEqual(alteradas, 2)
        self.assertTrue(pendente.corpo.startswith("fernet:v1:"))
        self.assertEqual(descriptografar_corpo_email(pendente.corpo), "Corpo legado com informações processuais")
        self.assertEqual(enviado.corpo, "")


if __name__ == "__main__":
    unittest.main()
