from datetime import date, datetime, timezone
import unittest

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import BigInteger, create_engine, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.modulos.processos import notificacoes_router, peticoes_router, prazos_router
from app.modulos.processos.auth import UsuarioAtual
from app.modulos.processos.models import (
    Base,
    DocumentoDB,
    JuridicoDB,
    NotificacaoInternaDB,
    PermissaoProcessoDB,
    PeticaoComentarioDB,
    PeticaoDB,
    PeticaoProtocoloDB,
    PeticaoRevisorDB,
    PrazoDB,
    PrazoLembreteDB,
    ProcessoDB,
    SugestaoPrazoDB,
    UsuarioDB,
    VersaoPeticaoDB,
)
from app.modulos.processos.prazos_service import processar_lembretes_prazo
from app.modulos.processos.recursos_schemas import (
    PeticaoComentarioEntrada,
    PeticaoComentarioResolucao,
    PeticaoComentarioAtualizacao,
    PeticaoProtocoloEntrada,
    PeticaoRevisorEntrada,
    SugestaoPrazoConfirmacao,
)
from app.modulos.processos.schemas import MovimentacaoPublica
from app.modulos.processos.security import hash_password
from app.modulos.processos.sugestoes_prazo_service import sugerir_prazos_de_movimentacoes
from app.main import app


@compiles(BigInteger, "sqlite")
def _bigint_as_integer(_type, _compiler, **_kw):
    return "INTEGER"


class TestExtensoesBackendProcessual(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.sessao = self.Session()
        for usuario_id, nome in ((1, "Advogada Um"), (2, "Advogado Dois")):
            self.sessao.add(
                UsuarioDB(
                    id_usuario=usuario_id,
                    nome=nome,
                    username=f"advogado{usuario_id}",
                    email=None,
                    senha=hash_password("SenhaSeguraDeTeste!2026"),
                    primeiro_acesso=False,
                    ativo=True,
                    email_verificado=True,
                )
            )
            self.sessao.add(JuridicoDB(id_usuario=usuario_id, oab=f"OAB {usuario_id}"))
            self.sessao.add(
                PermissaoProcessoDB(
                    id_usuario=usuario_id,
                    id_processo=10,
                    nivel_acesso="edicao",
                )
            )
        self.sessao.add(
            ProcessoDB(
                id_processo=10,
                numero_processo="0000001-00.2026.8.19.0001",
                tribunal="TRT1",
                status="novo",
                data_abertura=date(2026, 1, 1),
                arquivado=False,
                dados_json={
                    "numero": "0000001-00.2026.8.19.0001",
                    "tribunal": "TRT1",
                    "partes": [],
                    "advogados": [],
                    "associados_mencionados": [],
                },
                triagem_json={
                    "relevancia": "revisar",
                    "justificativa": "Teste.",
                    "evidencias": [],
                    "confianca": 0.5,
                },
                criado_por="1",
            )
        )
        self.sessao.add_all(
            [
                PeticaoDB(
                    id_peticao=7,
                    id_processo=10,
                    id_usuario=1,
                    tipo="Manifestação",
                    descricao="Petição de teste",
                    status="aprovada",
                ),
                VersaoPeticaoDB(
                    id_versao=70,
                    id_peticao=7,
                    numero_versao=1,
                    conteudo="Texto aprovado",
                    id_usuario=1,
                ),
                DocumentoDB(
                    id_documento=80,
                    id_processo=10,
                    id_usuario=1,
                    nome="comprovante.pdf",
                    tipo="application/pdf",
                    local_armazenamento="documentos/comprovante.pdf",
                    tamanho=100,
                    hash_arquivo="abc",
                    id_peticao=None,
                ),
            ]
        )
        self.sessao.commit()
        self.advogada_um = self._usuario(1, "Advogada Um")
        self.advogado_dois = self._usuario(2, "Advogado Dois")

    def tearDown(self):
        self.sessao.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    @staticmethod
    def _usuario(usuario_id: int, nome: str) -> UsuarioAtual:
        return UsuarioAtual(
            id=str(usuario_id),
            nome=nome,
            username=f"advogado{usuario_id}",
            papel="advogado",
            primeiro_acesso=False,
        )

    def test_deadline_reminders_are_idempotent_daily_and_only_for_responsible(self):
        self.sessao.add_all(
            [
                PrazoDB(
                    id_prazo=11,
                    id_processo=10,
                    id_usuario=1,
                    descricao="Juntar manifestação",
                    data_vencimento=date(2026, 10, 28),
                    status="pendente",
                ),
                PrazoDB(
                    id_prazo=12,
                    id_processo=10,
                    id_usuario=1,
                    descricao="Apresentar resposta",
                    data_vencimento=date(2026, 10, 20),
                    status="pendente",
                ),
                PrazoDB(
                    id_prazo=13,
                    id_processo=10,
                    id_usuario=1,
                    descricao="Prazo de três dias",
                    data_vencimento=date(2026, 10, 24),
                    status="pendente",
                ),
                PrazoDB(
                    id_prazo=14,
                    id_processo=10,
                    id_usuario=1,
                    descricao="Prazo de um dia",
                    data_vencimento=date(2026, 10, 22),
                    status="pendente",
                ),
                PrazoDB(
                    id_prazo=15,
                    id_processo=10,
                    id_usuario=1,
                    descricao="Vence hoje",
                    data_vencimento=date(2026, 10, 21),
                    status="pendente",
                ),
            ]
        )
        self.sessao.commit()

        self.assertEqual(
            processar_lembretes_prazo(self.sessao, hoje=date(2026, 10, 21)),
            5,
        )
        self.assertEqual(
            processar_lembretes_prazo(self.sessao, hoje=date(2026, 10, 21)),
            0,
        )
        self.assertEqual(
            processar_lembretes_prazo(self.sessao, hoje=date(2026, 10, 22)),
            3,
        )
        self.assertEqual(
            self.sessao.scalar(
                select(PrazoLembreteDB.id_lembrete).where(
                    PrazoLembreteDB.id_prazo == 12,
                    PrazoLembreteDB.data_referencia == date(2026, 10, 22),
                )
            )
            is not None,
            True,
        )
        notificacoes = self.sessao.scalars(select(NotificacaoInternaDB)).all()
        self.assertEqual(len(notificacoes), 8)
        self.assertEqual({notificacao.id_usuario for notificacao in notificacoes}, {1})

        lista = notificacoes_router.listar_notificacoes(
            True, 50, 0, self.advogada_um, self.sessao
        )
        self.assertEqual(lista.nao_lidas, 8)
        notificacoes_router.marcar_como_lida(
            lista.itens[0].id_notificacao, self.advogada_um, self.sessao
        )
        atualizada = notificacoes_router.listar_notificacoes(
            True, 50, 0, self.advogada_um, self.sessao
        )
        self.assertEqual(atualizada.nao_lidas, 7)
        self.assertEqual(
            notificacoes_router.listar_notificacoes(
                True, 50, 0, self.advogado_dois, self.sessao
            ).nao_lidas,
            0,
        )

    def test_deadline_reminders_are_processed_in_batches(self):
        self.sessao.add_all(
            [
                PrazoDB(
                    id_prazo=id_prazo,
                    id_processo=10,
                    id_usuario=1,
                    descricao=f"Prazo {id_prazo}",
                    data_vencimento=date(2026, 10, 28),
                    status="pendente",
                )
                for id_prazo in range(100, 351)
            ]
        )
        self.sessao.commit()

        criados = processar_lembretes_prazo(self.sessao, hoje=date(2026, 10, 21))

        self.assertEqual(criados, 251)
        self.assertEqual(
            len(self.sessao.scalars(select(PrazoLembreteDB.id_lembrete)).all()),
            251,
        )

    def test_publication_suggestion_requires_explicit_deadline_confirmation(self):
        movimento = MovimentacaoPublica(
            texto="Intimação para manifestação sobre documentos",
            data_fonte=datetime(2026, 10, 20, tzinfo=timezone.utc),
            fonte_dados="djen",
            fonte_url="https://comunicaapi.pje.jus.br/api/v1/comunicacao/abcdefghij/certidao",
        )
        self.assertEqual(
            sugerir_prazos_de_movimentacoes(self.sessao, 10, [movimento]),
            1,
        )
        self.assertEqual(
            sugerir_prazos_de_movimentacoes(self.sessao, 10, [movimento]),
            0,
        )
        sugestao = self.sessao.scalar(select(SugestaoPrazoDB))
        self.assertEqual(sugestao.status, "pendente")
        self.assertIsNone(sugestao.id_prazo)

        prazo = prazos_router.confirmar_sugestao_prazo(
            10,
            sugestao.id_sugestao,
            SugestaoPrazoConfirmacao(data_vencimento=date(2026, 11, 20)),
            self.advogada_um,
            self.sessao,
        )
        self.assertEqual(prazo.data_vencimento, date(2026, 11, 20))
        self.assertEqual(sugestao.status, "confirmada")
        self.assertEqual(sugestao.id_prazo, prazo.id_prazo)
        with self.assertRaises(HTTPException) as erro:
            prazos_router.descartar_sugestao_prazo(
                10, sugestao.id_sugestao, self.advogada_um, self.sessao
            )
        self.assertEqual(erro.exception.status_code, 409)
        self.assertEqual(len(self.sessao.scalars(select(PrazoDB)).all()), 1)

    def test_same_publication_from_two_sources_creates_one_suggestion(self):
        instante = datetime(2026, 10, 20, tzinfo=timezone.utc)
        evento_datajud = MovimentacaoPublica(
            texto="Intimação para manifestação",
            data_fonte=instante,
            fonte_dados="datajud",
        )
        evento_djen = MovimentacaoPublica(
            texto="Intimação para manifestação",
            data_fonte=instante,
            fonte_dados="djen",
        )
        self.assertEqual(
            sugerir_prazos_de_movimentacoes(
                self.sessao,
                10,
                [evento_datajud, evento_djen],
            ),
            1,
        )
        sugestoes = self.sessao.scalars(select(SugestaoPrazoDB)).all()
        self.assertEqual(len(sugestoes), 1)

    def test_petition_review_and_manual_protocol_are_auditable(self):
        revisor = peticoes_router.atribuir_revisor_peticao(
            7,
            PeticaoRevisorEntrada(id_usuario=2),
            self.advogada_um,
            self.sessao,
        )
        self.assertEqual(revisor.id_usuario, 2)
        self.assertEqual(
            self.sessao.get(PeticaoRevisorDB, 7).id_usuario,
            2,
        )

        comentario = peticoes_router.criar_comentario_peticao(
            7,
            PeticaoComentarioEntrada(
                id_versao=70,
                conteudo="Confirmar o documento citado.",
            ),
            self.advogada_um,
            self.sessao,
        )
        comentario = peticoes_router.atualizar_comentario_peticao(
            comentario.id_comentario,
            PeticaoComentarioAtualizacao(conteudo="Revisar a referência documental."),
            self.advogada_um,
            self.sessao,
        )
        comentario = peticoes_router.resolver_comentario_peticao(
            comentario.id_comentario,
            PeticaoComentarioResolucao(resolvido=True),
            self.advogado_dois,
            self.sessao,
        )
        self.assertIsNotNone(comentario.resolvido_em)
        self.assertEqual(comentario.conteudo, "Revisar a referência documental.")
        self.assertEqual(
            len(
                peticoes_router.listar_comentarios_peticao(
                    7, 70, self.advogado_dois, self.sessao
                )
            ),
            1,
        )

        registro = peticoes_router.registrar_protocolo_peticao(
            7,
            PeticaoProtocoloEntrada(
                protocolado_em=datetime(2026, 10, 21, 12, tzinfo=timezone.utc),
                tribunal="TRT1",
                numero_protocolo="2026.000123",
                id_documento_comprovante=80,
            ),
            self.advogada_um,
            self.sessao,
        )
        self.assertEqual(registro.numero_protocolo, "2026.000123")
        self.assertEqual(self.sessao.get(PeticaoDB, 7).status, "protocolada")
        self.assertEqual(
            self.sessao.get(DocumentoDB, 80).id_peticao,
            7,
        )
        self.assertIsNotNone(self.sessao.scalar(select(PeticaoProtocoloDB)))

        with self.assertRaises(HTTPException) as erro:
            peticoes_router.registrar_protocolo_peticao(
                7,
                PeticaoProtocoloEntrada(
                    protocolado_em=datetime(2026, 10, 21, 12, tzinfo=timezone.utc),
                    tribunal="TRT1",
                    numero_protocolo="2026.000124",
                ),
                self.advogada_um,
                self.sessao,
            )
        self.assertEqual(erro.exception.status_code, 409)

    def test_protocol_fields_are_normalized_before_validation(self):
        with self.assertRaises(ValidationError):
            PeticaoProtocoloEntrada(
                protocolado_em=datetime(2026, 10, 21, 12, tzinfo=timezone.utc),
                tribunal="   ",
                numero_protocolo="   ",
            )
        with self.assertRaises(ValidationError):
            PeticaoProtocoloEntrada(
                protocolado_em=datetime(2026, 10, 21, 12, tzinfo=timezone.utc),
                tribunal="TRT1",
                numero_protocolo="   ",
                id_documento_comprovante=None,
            )
        with self.assertRaises(ValidationError):
            PeticaoProtocoloEntrada(
                protocolado_em=datetime(2026, 10, 21, 12, tzinfo=timezone.utc),
                tribunal="   ",
                numero_protocolo="2026.000125",
            )
        entrada = PeticaoProtocoloEntrada(
            protocolado_em=datetime(2026, 10, 21, 12, tzinfo=timezone.utc),
            tribunal=" TRT1 ",
            numero_protocolo="  2026.000123  ",
        )
        self.assertEqual(entrada.tribunal, "TRT1")
        self.assertEqual(entrada.numero_protocolo, "2026.000123")

    def test_cors_allows_put_for_review_assignment(self):
        cors = next(
            middleware
            for middleware in app.user_middleware
            if middleware.cls.__name__ == "CORSMiddleware"
        )
        self.assertIn("PUT", cors.kwargs["allow_methods"])

    def test_deadline_reassignment_notifies_new_responsible_and_skips_future(self):
        self.sessao.add_all(
            [
                PrazoDB(
                    id_prazo=21,
                    id_processo=10,
                    id_usuario=1,
                    descricao="Prazo iminente",
                    data_vencimento=date(2026, 10, 28),
                    status="pendente",
                ),
                PrazoDB(
                    id_prazo=22,
                    id_processo=10,
                    id_usuario=1,
                    descricao="Prazo distante",
                    data_vencimento=date(2027, 1, 1),
                    status="pendente",
                ),
            ]
        )
        self.sessao.commit()
        self.assertEqual(
            processar_lembretes_prazo(self.sessao, hoje=date(2026, 10, 21)),
            1,
        )

        prazo = self.sessao.get(PrazoDB, 21)
        prazo.id_usuario = 2
        self.sessao.commit()
        self.assertEqual(
            processar_lembretes_prazo(self.sessao, hoje=date(2026, 10, 21)),
            1,
        )
        lembretes = self.sessao.scalars(
            select(PrazoLembreteDB).where(PrazoLembreteDB.id_prazo == 21)
        ).all()
        self.assertEqual({lembrete.id_usuario for lembrete in lembretes}, {1, 2})
        self.assertEqual(
            self.sessao.scalar(
                select(PrazoLembreteDB.id_lembrete).where(
                    PrazoLembreteDB.id_prazo == 22
                )
            ),
            None,
        )

    def test_petition_comment_list_is_limited_and_offset(self):
        first = peticoes_router.criar_comentario_peticao(
            7,
            PeticaoComentarioEntrada(id_versao=70, conteudo="Primeiro comentário"),
            self.advogada_um,
            self.sessao,
        )
        second = peticoes_router.criar_comentario_peticao(
            7,
            PeticaoComentarioEntrada(id_versao=70, conteudo="Segundo comentário"),
            self.advogado_dois,
            self.sessao,
        )
        page = peticoes_router.listar_comentarios_peticao(
            7,
            70,
            self.advogado_dois,
            self.sessao,
            limite=1,
            deslocamento=1,
        )
        self.assertEqual(len(page), 1)
        self.assertEqual(page[0].id_comentario, second.id_comentario)
        self.assertNotEqual(page[0].id_comentario, first.id_comentario)
