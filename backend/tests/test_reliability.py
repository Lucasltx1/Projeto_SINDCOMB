from datetime import datetime, timezone
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import httpx
from cryptography.fernet import Fernet

from app.modulos.processos import datajud_service, email_outbox, email_service


class _RespostaDataJud:
    def __init__(self, status_code=200, payload=None):
        self.status_code = status_code
        self.payload = payload or {"hits": {"hits": []}}
        self.request = httpx.Request("POST", "https://datajud.test")

    def raise_for_status(self):
        if self.status_code >= 400:
            resposta = httpx.Response(self.status_code, request=self.request)
            raise httpx.HTTPStatusError("DataJud error", request=self.request, response=resposta)

    def json(self):
        return self.payload


class _ClienteDataJud:
    def __init__(self, resultado):
        self.resultado = resultado

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def post(self, *_args, **_kwargs):
        if isinstance(self.resultado, Exception):
            raise self.resultado
        return self.resultado


class TestDataJudRetry(unittest.IsolatedAsyncioTestCase):
    async def test_retries_transient_network_failure_then_succeeds(self):
        payload = {"hits": {"hits": [{"_source": {"numeroProcesso": "00000000000000000001"}}]}}
        clients = [
            _ClienteDataJud(httpx.ConnectError("offline")),
            _ClienteDataJud(_RespostaDataJud(payload=payload)),
        ]
        with (
            patch.dict(os.environ, {"DATAJUD_API_KEY": "test", "SINDCOMB_SYNC_MAX_ATTEMPTS": "3"}),
            patch.object(datajud_service.httpx, "AsyncClient", side_effect=clients) as client_factory,
            patch.object(datajud_service.asyncio, "sleep", new=AsyncMock()),
        ):
            resultado = await datajud_service.buscar_por_numero("00000000000000000001", "tjrj")

        self.assertEqual(len(resultado), 1)
        self.assertEqual(client_factory.call_count, 2)

    async def test_does_not_retry_permanent_client_error(self):
        client = _ClienteDataJud(_RespostaDataJud(status_code=401))
        with (
            patch.dict(os.environ, {"DATAJUD_API_KEY": "test", "SINDCOMB_SYNC_MAX_ATTEMPTS": "3"}),
            patch.object(datajud_service.httpx, "AsyncClient", return_value=client) as client_factory,
            patch.object(datajud_service.asyncio, "sleep", new=AsyncMock()) as sleep,
        ):
            with self.assertRaises(httpx.HTTPStatusError):
                await datajud_service.buscar_por_numero("00000000000000000001", "tjrj")

        self.assertEqual(client_factory.call_count, 1)
        sleep.assert_not_awaited()


class _FakeSession:
    def __init__(self, row=None, rows=None):
        self.row = row
        self.rows = rows or []
        self.added = []
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def scalars(self, _statement):
        return SimpleNamespace(
            all=lambda: self.rows,
            first=lambda: self.rows[0] if self.rows else None,
        )

    def get(self, _model, _identifier):
        return self.row

    def add(self, row):
        self.added.append(row)

    def commit(self):
        self.commits += 1


class TestEmailOutbox(unittest.IsolatedAsyncioTestCase):
    def test_enqueues_one_normalized_row_per_unique_recipient(self):
        sessao = _FakeSession()
        with patch.dict(os.environ, {"SINDCOMB_EMAIL_ENCRYPTION_KEY": Fernet.generate_key().decode()}):
            quantidade = email_outbox.enfileirar_email(
                sessao,
                [" User@Example.com ", "user@example.com", "second@example.com"],
                "Assunto",
                "Corpo",
                categoria="teste",
            )

        self.assertEqual(quantidade, 2)
        self.assertEqual([row.destinatario for row in sessao.added], ["user@example.com", "second@example.com"])
        self.assertTrue(all(row.status == "pendente" and row.tentativas == 0 for row in sessao.added))
        self.assertTrue(all(row.corpo.startswith("fernet:v1:") for row in sessao.added))

    def test_retry_backoff_is_exponential_and_capped(self):
        with patch.dict(
            os.environ,
            {"SINDCOMB_EMAIL_RETRY_BASE_SECONDS": "10", "SINDCOMB_EMAIL_RETRY_MAX_SECONDS": "30"},
        ):
            self.assertEqual(email_outbox.atraso_retentativa_segundos(1), 10)
            self.assertEqual(email_outbox.atraso_retentativa_segundos(2), 20)
            self.assertEqual(email_outbox.atraso_retentativa_segundos(4), 30)

    async def test_failed_delivery_is_persisted_for_retry(self):
        encryption_key = Fernet.generate_key().decode()
        row = SimpleNamespace(
            id_email=7,
            destinatario="person@example.com",
            assunto="Aviso",
            corpo="",
            status="pendente",
            tentativas=0,
            proxima_tentativa=datetime.now(timezone.utc),
            enviado_em=None,
            ultimo_erro=None,
        )
        sessions = [_FakeSession(rows=[row]), _FakeSession(row=row), _FakeSession(rows=[])]
        with (
            patch.object(email_outbox, "SessionLocal", side_effect=sessions),
            patch.object(
                email_outbox.asyncio,
                "to_thread",
                new=AsyncMock(return_value=(False, "SMTP indisponível")),
            ),
            patch.dict(os.environ, {"SINDCOMB_EMAIL_MAX_ATTEMPTS": "8"}),
            patch.dict(os.environ, {"SINDCOMB_EMAIL_ENCRYPTION_KEY": encryption_key}),
        ):
            row.corpo = email_outbox.proteger_corpo_email("Corpo")
            enviados, falhas = await email_outbox.processar_email_outbox()

        self.assertEqual((enviados, falhas), (0, 1))
        self.assertEqual(row.status, "pendente")
        self.assertEqual(row.tentativas, 1)
        self.assertEqual(row.ultimo_erro, "SMTP indisponível")
        self.assertGreater(row.proxima_tentativa, datetime.now(timezone.utc))

    async def test_marks_message_permanent_after_attempt_limit(self):
        encryption_key = Fernet.generate_key().decode()
        row = SimpleNamespace(
            id_email=8,
            destinatario="person@example.com",
            assunto="Aviso",
            corpo="",
            status="pendente",
            tentativas=0,
            proxima_tentativa=datetime.now(timezone.utc),
            enviado_em=None,
            ultimo_erro=None,
        )
        sessions = [_FakeSession(rows=[row]), _FakeSession(row=row), _FakeSession(rows=[])]
        with (
            patch.object(email_outbox, "SessionLocal", side_effect=sessions),
            patch.object(email_outbox.asyncio, "to_thread", new=AsyncMock(return_value=(False, "SMTP rejeitou"))),
            patch.dict(os.environ, {"SINDCOMB_EMAIL_MAX_ATTEMPTS": "1"}),
            patch.dict(os.environ, {"SINDCOMB_EMAIL_ENCRYPTION_KEY": encryption_key}),
        ):
            row.corpo = email_outbox.proteger_corpo_email("Corpo")
            enviados, falhas = await email_outbox.processar_email_outbox()

        self.assertEqual((enviados, falhas), (0, 1))
        self.assertEqual(row.status, "falha_permanente")
        self.assertEqual(row.tentativas, 1)
        self.assertEqual(row.corpo, "")

    async def test_successful_delivery_erases_message_content(self):
        encryption_key = Fernet.generate_key().decode()
        row = SimpleNamespace(
            id_email=9,
            destinatario="person@example.com",
            assunto="Aviso privado",
            corpo="",
            status="pendente",
            tentativas=0,
            proxima_tentativa=datetime.now(timezone.utc),
            enviado_em=None,
            ultimo_erro=None,
        )
        sessions = [_FakeSession(rows=[row]), _FakeSession(row=row), _FakeSession(rows=[])]
        with (
            patch.object(email_outbox, "SessionLocal", side_effect=sessions),
            patch.object(email_outbox.asyncio, "to_thread", new=AsyncMock(return_value=(True, None))),
            patch.dict(os.environ, {"SINDCOMB_EMAIL_ENCRYPTION_KEY": encryption_key}),
        ):
            row.corpo = email_outbox.proteger_corpo_email("Conteúdo confidencial")
            enviados, falhas = await email_outbox.processar_email_outbox()

        self.assertEqual((enviados, falhas), (1, 0))
        self.assertEqual(row.status, "enviado")
        self.assertEqual(row.corpo, "")
        self.assertEqual(row.assunto, "[mensagem enviada]")

    def test_sender_reports_missing_smtp_configuration(self):
        with patch.dict(os.environ, {"SMTP_HOST": "", "SMTP_FROM": ""}):
            sucesso, erro = email_service.enviar_email_com_resultado(
                ["person@example.com"], "Assunto", "Corpo"
            )
        self.assertFalse(sucesso)
        self.assertIn("SMTP_HOST", erro or "")


if __name__ == "__main__":
    unittest.main()
