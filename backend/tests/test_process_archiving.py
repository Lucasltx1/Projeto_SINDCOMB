from datetime import date
import asyncio
import unittest

from fastapi import HTTPException
from sqlalchemy import BigInteger, select
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import create_engine

from app.modulos.processos import router as processos_router
from app.modulos.processos.auth import UsuarioAtual
from app.modulos.processos.models import (
    AuditoriaDB,
    Base,
    JuridicoDB,
    PermissaoProcessoDB,
    ProcessoDB,
    UsuarioDB,
)
from app.modulos.processos.repository import listar
from app.modulos.processos.recursos_acesso import obter_processo_autorizado
from app.modulos.processos.security import hash_password
from app.modulos.processos.schemas import AlteracaoStatus, MovimentacaoEntrada


@compiles(BigInteger, "sqlite")
def _bigint_as_integer(_type, _compiler, **_kw):
    return "INTEGER"


class TestArquivamentoProcessual(unittest.TestCase):
    def setUp(self):
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
                nome="Advogado de Teste",
                username="advogado.teste",
                email="advogado@example.com",
                senha=hash_password("SenhaSeguraDeTeste!2026"),
                primeiro_acesso=False,
                ativo=True,
                email_verificado=True,
            )
        )
        self.sessao.add(JuridicoDB(id_usuario=1, oab="OAB 12345"))
        self.sessao.add(
            ProcessoDB(
                id_processo=10,
                numero_processo="0000001-00.2026.8.19.0001",
                tribunal="Tribunal de Justiça",
                status="encerrado",
                data_abertura=date(2026, 1, 1),
                data_encerramento=date(2026, 5, 1),
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
        self.sessao.add(
            PermissaoProcessoDB(
                id_usuario=1,
                id_processo=10,
                nivel_acesso="edicao",
            )
        )
        self.sessao.commit()
        self.advogado = UsuarioAtual(
            id="1",
            nome="Advogado de Teste",
            username="advogado.teste",
            email="advogado@example.com",
            papel="advogado",
            primeiro_acesso=False,
        )

    def tearDown(self):
        self.sessao.close()
        Base.metadata.drop_all(self.engine)
        self.engine.dispose()

    def test_arquivar_remove_da_lista_ativa_e_grava_auditoria(self):
        resultado = processos_router.arquivar_processo(10, self.advogado, self.sessao)

        self.assertTrue(resultado.arquivado)
        self.assertEqual(listar(self.sessao), [])
        arquivados = listar(self.sessao, arquivado=True)
        self.assertEqual([processo.id for processo in arquivados], ["10"])
        evento = self.sessao.scalar(
            select(AuditoriaDB).where(AuditoriaDB.tipo_operacao == "processo_arquivado")
        )
        self.assertIsNotNone(evento)
        self.assertEqual(evento.id_processo, 10)
        self.assertEqual(evento.id_usuario, 1)

    def test_desarquivar_reativa_o_acompanhamento_e_audita(self):
        processos_router.arquivar_processo(10, self.advogado, self.sessao)
        resultado = processos_router.desarquivar_processo(10, self.advogado, self.sessao)

        self.assertFalse(resultado.arquivado)
        self.assertEqual([processo.id for processo in listar(self.sessao)], ["10"])
        operacoes = set(
            self.sessao.scalars(select(AuditoriaDB.tipo_operacao)).all()
        )
        self.assertEqual(operacoes, {"processo_arquivado", "processo_desarquivado"})

    def test_processo_arquivado_pode_ser_lido_mas_bloqueia_edicoes(self):
        processos_router.arquivar_processo(10, self.advogado, self.sessao)

        self.assertTrue(listar(self.sessao, arquivado=True)[0].arquivado)
        with self.assertRaises(HTTPException) as erro:
            obter_processo_autorizado(self.sessao, self.advogado, 10, edicao=True)

        self.assertEqual(erro.exception.status_code, 409)

    def test_somente_processo_encerrado_pode_ser_arquivado(self):
        processo = self.sessao.get(ProcessoDB, 10)
        processo.status = "em_acompanhamento"
        self.sessao.commit()

        with self.assertRaises(HTTPException) as erro:
            processos_router.arquivar_processo(10, self.advogado, self.sessao)

        self.assertEqual(erro.exception.status_code, 409)
        self.assertFalse(processo.arquivado)

    def test_usuario_com_acesso_somente_leitura_nao_pode_arquivar(self):
        permissao = self.sessao.scalar(select(PermissaoProcessoDB))
        permissao.nivel_acesso = "leitura"
        self.sessao.commit()
        advogado_sem_edicao = UsuarioAtual(**self.advogado.model_dump())

        with self.assertRaises(HTTPException) as erro:
            processos_router.arquivar_processo(10, advogado_sem_edicao, self.sessao)

        self.assertEqual(erro.exception.status_code, 403)
        self.assertFalse(self.sessao.get(ProcessoDB, 10).arquivado)

    def test_advogado_sem_permissao_no_processo_nao_pode_alterar_status(self):
        outro_advogado = UsuarioAtual(
            id="2",
            nome="Outro advogado",
            username="outro.advogado",
            email="outro@example.com",
            papel="advogado",
            primeiro_acesso=False,
        )

        with self.assertRaises(HTTPException) as erro:
            processos_router.alterar_status(
                "10", AlteracaoStatus(status="suspenso"), outro_advogado, self.sessao
            )

        self.assertEqual(erro.exception.status_code, 404)
        self.assertEqual(self.sessao.get(ProcessoDB, 10).status, "encerrado")

    def test_advogado_sem_permissao_nao_pode_registrar_movimentacao(self):
        outro_advogado = UsuarioAtual(
            id="2",
            nome="Outro advogado",
            username="outro.advogado",
            email="outro@example.com",
            papel="advogado",
            primeiro_acesso=False,
        )

        with self.assertRaises(HTTPException) as erro:
            asyncio.run(
                processos_router.registrar_movimentacao(
                    "10", MovimentacaoEntrada(texto="Movimentação não autorizada"), outro_advogado, self.sessao
                )
            )

        self.assertEqual(erro.exception.status_code, 404)
        self.assertEqual(self.sessao.get(ProcessoDB, 10).status, "encerrado")

    def test_lista_processos_filtra_por_permissao_do_usuario(self):
        outro_processo = ProcessoDB(
            id_processo=11,
            numero_processo="0000002-00.2026.8.19.0001",
            tribunal="Tribunal de Justiça",
            status="novo",
            data_abertura=date(2026, 1, 1),
            arquivado=False,
            dados_json={"numero": "0000002-00.2026.8.19.0001", "partes": [], "advogados": []},
            triagem_json={"relevancia": "revisar", "justificativa": "Teste.", "evidencias": [], "confianca": 0.5},
            criado_por="1",
        )
        self.sessao.add(outro_processo)
        self.sessao.commit()

        resultado_responsavel = processos_router.listar_processos(
            None, False, self.advogado, self.sessao
        )
        self.assertEqual([processo.id for processo in resultado_responsavel], ["10"])

        outro_advogado = UsuarioAtual(
            id="2",
            nome="Outro advogado",
            username="outro.advogado",
            email="outro@example.com",
            papel="advogado",
            primeiro_acesso=False,
        )

        resultado = processos_router.listar_processos(None, False, outro_advogado, self.sessao)

        self.assertEqual(resultado, [])

    def test_detalhe_processo_exige_permissao_especifica(self):
        outro_advogado = UsuarioAtual(
            id="2",
            nome="Outro advogado",
            username="outro.advogado",
            email="outro@example.com",
            papel="advogado",
            primeiro_acesso=False,
        )

        with self.assertRaises(HTTPException) as erro:
            processos_router.detalhar_processo("10", outro_advogado, self.sessao)

        self.assertEqual(erro.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
