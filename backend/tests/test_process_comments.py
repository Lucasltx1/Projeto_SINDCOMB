import asyncio
from datetime import date, datetime, timezone
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import HTTPException
from sqlalchemy import BigInteger, create_engine, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.modulos.processos import comentarios_router, router as processos_router
from app.modulos.processos.auth import UsuarioAtual
from app.modulos.processos.consulta_processual_service import ConsultaProcessual
from app.modulos.processos.models import (
    AuditoriaDB,
    Base,
    ComentarioProcessoDB,
    JuridicoDB,
    PermissaoProcessoDB,
    ProcessoDB,
    UsuarioDB,
)
from app.modulos.processos.recursos_schemas import (
    ComentarioProcessoAtualizacao,
    ComentarioProcessoEntrada,
)
from app.modulos.processos.repository import obter
from app.modulos.processos.schemas import ProcessoCandidato
from app.modulos.processos.status_service import ResultadoTriagemModelo
from app.modulos.processos.security import hash_password


@compiles(BigInteger, "sqlite")
def _bigint_as_integer(_type, _compiler, **_kw):
    return "INTEGER"


class TestComentariosProcessuais(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, autoflush=False, expire_on_commit=False)
        self.sessao = self.Session()
        for usuario_id, nome in ((1, "Advogado Um"), (2, "Advogado Dois"), (3, "Somente Leitura")):
            self.sessao.add(
                UsuarioDB(
                    id_usuario=usuario_id,
                    nome=nome,
                    username=f"advogado{usuario_id}",
                    email=f"advogado{usuario_id}@example.com",
                    senha=hash_password("SenhaSeguraDeTeste!2026"),
                    primeiro_acesso=False,
                    ativo=True,
                    email_verificado=True,
                )
            )
            self.sessao.add(JuridicoDB(id_usuario=usuario_id, oab=f"OAB {usuario_id}"))
        self.sessao.add(
            ProcessoDB(
                id_processo=10,
                numero_processo="0000001-00.2026.8.19.0001",
                tribunal="Tribunal de Justiça",
                status="novo",
                data_abertura=date(2026, 1, 1),
                arquivado=False,
                dados_json={
                    "numero": "0000001-00.2026.8.19.0001",
                    "tribunal": "Tribunal de Justiça",
                    "partes": [],
                    "advogados": [],
                    "associados_mencionados": [],
                },
                triagem_json={
                    "relevancia": "revisar",
                    "justificativa": "Registro de teste.",
                    "evidencias": [],
                    "confianca": 0.5,
                },
                criado_por="1",
            )
        )
        self.sessao.add_all(
            [
                PermissaoProcessoDB(id_usuario=1, id_processo=10, nivel_acesso="edicao"),
                PermissaoProcessoDB(id_usuario=3, id_processo=10, nivel_acesso="leitura"),
            ]
        )
        self.sessao.commit()
        self.advogado_um = self._usuario(1, "Advogado Um")
        self.advogado_dois = self._usuario(2, "Advogado Dois")
        self.leitor = UsuarioAtual(
            id="3",
            nome="Somente Leitura",
            username="advogado3",
            email="advogado3@example.com",
            papel="advogado",
            primeiro_acesso=False,
        )
        comentarios_router.criar_comentario(
            10,
            ComentarioProcessoEntrada(conteudo="Verificar documento juntado."),
            self.advogado_um,
            self.sessao,
        )

    @staticmethod
    def _usuario(usuario_id, nome):
        return UsuarioAtual(
            id=str(usuario_id),
            nome=nome,
            username=f"advogado{usuario_id}",
            email=f"advogado{usuario_id}@example.com",
            papel="advogado",
            primeiro_acesso=False,
        )

    def tearDown(self):
        self.sessao.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_comment_is_visible_to_another_authorized_lawyer(self):
        self.sessao.add(
            PermissaoProcessoDB(id_usuario=2, id_processo=10, nivel_acesso="edicao")
        )
        self.sessao.commit()
        response = comentarios_router.listar_comentarios(
            10, self.advogado_dois, self.sessao
        )
        self.assertEqual(response[0].conteudo, "Verificar documento juntado.")
        self.assertEqual(response[0].autor, "Advogado Um")

    def test_only_process_readers_can_list_comments(self):
        with self.assertRaises(HTTPException) as erro:
            comentarios_router.listar_comentarios(
                10, self.advogado_dois, self.sessao
            )
        self.assertEqual(erro.exception.status_code, 404)

    def test_read_only_permission_can_list_but_cannot_create_comments(self):
        self.assertEqual(
            len(comentarios_router.listar_comentarios(10, self.leitor, self.sessao)),
            1,
        )
        with self.assertRaises(HTTPException) as erro:
            comentarios_router.criar_comentario(
                10,
                ComentarioProcessoEntrada(conteudo="Tentativa sem edição."),
                self.leitor,
                self.sessao,
            )
        self.assertEqual(erro.exception.status_code, 403)

    def test_empty_after_trim_is_rejected(self):
        with self.assertRaises(HTTPException) as erro:
            comentarios_router.criar_comentario(
                10,
                ComentarioProcessoEntrada(conteudo="   "),
                self.advogado_um,
                self.sessao,
            )
        self.assertEqual(erro.exception.status_code, 422)

    def test_author_can_edit_and_soft_delete_comment_with_tombstone(self):
        self.sessao.add(
            PermissaoProcessoDB(id_usuario=2, id_processo=10, nivel_acesso="edicao")
        )
        self.sessao.commit()
        comentario = self.sessao.scalar(
            select(ComentarioProcessoDB).where(
                ComentarioProcessoDB.id_processo == 10
            )
        )
        atualizado = comentarios_router.atualizar_comentario(
            comentario.id_comentario,
            ComentarioProcessoAtualizacao(conteudo="Revisar a publicação."),
            self.advogado_um,
            self.sessao,
        )
        self.assertEqual(atualizado.conteudo, "Revisar a publicação.")
        self.assertIsNotNone(atualizado.editado_em)

        with self.assertRaises(HTTPException) as erro:
            comentarios_router.atualizar_comentario(
                comentario.id_comentario,
                ComentarioProcessoAtualizacao(conteudo="Alteração de outro autor."),
                self.advogado_dois,
                self.sessao,
            )
        self.assertEqual(erro.exception.status_code, 403)

        comentarios_router.excluir_comentario(
            comentario.id_comentario,
            self.advogado_um,
            self.sessao,
        )
        resposta = comentarios_router.listar_comentarios(
            10,
            self.advogado_dois,
            self.sessao,
        )
        self.assertEqual(resposta[0].conteudo, "[Comentário removido]")
        self.assertIsNotNone(resposta[0].excluido_em)

    def test_triage_of_existing_process_shares_its_comments_with_registering_lawyer(self):
        existente = obter(self.sessao, "10")
        candidato = ProcessoCandidato(
            numero=existente.dados.numero,
            tribunal=existente.dados.tribunal,
            tribunal_alias="tjrj",
            assunto=existente.dados.assunto,
        )
        consulta = ConsultaProcessual(
            processo=candidato,
            fonte="datajud",
            fontes_consultadas=("datajud", "djen"),
            consultado_em=datetime.now(timezone.utc),
        )

        with (
            patch.object(processos_router, "alias_datajud_por_numero", return_value="tjrj"),
            patch.object(
                processos_router,
                "consultar_por_numero",
                new=AsyncMock(return_value=consulta),
            ),
            patch.object(
                processos_router,
                "classificar_interesse",
                new=AsyncMock(
                    return_value=ResultadoTriagemModelo(
                        relevancia="revisar",
                        justificativa="Revisar vínculo.",
                        evidencias=[],
                        confianca=0.5,
                    )
                ),
            ),
            patch.object(
                processos_router,
                "obter_por_numero",
                side_effect=lambda _sessao, _numero: obter(self.sessao, "10"),
            ),
        ):
            asyncio.run(
                processos_router.cadastrar_para_triagem(
                    candidato,
                    self.advogado_dois,
                    self.sessao,
                )
            )

        permissao = self.sessao.scalar(
            select(PermissaoProcessoDB).where(
                PermissaoProcessoDB.id_usuario == 2,
                PermissaoProcessoDB.id_processo == 10,
            )
        )
        self.assertIsNotNone(permissao)
        comentarios = comentarios_router.listar_comentarios(
            10, self.advogado_dois, self.sessao
        )
        self.assertEqual(comentarios[0].conteudo, "Verificar documento juntado.")
        self.assertEqual(comentarios[0].autor, "Advogado Um")

    def test_existing_read_only_permission_is_not_upgraded_by_duplicate_registration(self):
        changed = processos_router.conceder_acesso_edicao_se_ausente(
            self.sessao,
            usuario_id=3,
            processo_id=10,
        )
        permissao = self.sessao.scalar(
            select(PermissaoProcessoDB).where(
                PermissaoProcessoDB.id_usuario == 3,
                PermissaoProcessoDB.id_processo == 10,
            )
        )
        self.assertFalse(changed)
        self.assertEqual(permissao.nivel_acesso, "leitura")

    def test_comment_creation_audits_metadata_without_copying_comment_body(self):
        evento = self.sessao.scalar(
            select(AuditoriaDB).where(
                AuditoriaDB.tipo_operacao == "comentario_processo_criado"
            )
        )
        self.assertIsNotNone(evento)
        self.assertNotIn("Verificar documento juntado.", str(evento.dados_json))
        self.assertEqual(self.sessao.query(ComentarioProcessoDB).count(), 1)
