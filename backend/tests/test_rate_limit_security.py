from __future__ import annotations

import os
from unittest.mock import patch
import unittest

from cryptography.fernet import Fernet
from fastapi import Request
from redis.exceptions import RedisError

from app.nucleo.rate_limit import aplicar_rate_limit
from app.nucleo.seguranca_config import validar_configuracao_seguranca, validar_senha_administrativa_inicial


class _RedisContador:
    def __init__(self):
        self.contagem = 0

    async def eval(self, _script, _num_keys, _chave, _janela):
        self.contagem += 1
        return [self.contagem, 37]


class _RedisIndisponivel:
    async def eval(self, *_args):
        raise RedisError("unavailable")


def _request(method="POST", path="/api/v1/auth/login"):
    return Request(
        {
            "type": "http",
            "http_version": "1.1",
            "method": method,
            "scheme": "http",
            "path": path,
            "raw_path": path.encode(),
            "query_string": b"",
            "headers": [],
            "client": ("203.0.113.10", 12345),
            "server": ("testserver", 80),
        }
    )


class TestRateLimitESegredos(unittest.IsolatedAsyncioTestCase):
    async def test_login_bloqueia_depois_do_limite(self):
        redis = _RedisContador()
        with patch.dict(os.environ, {"SINDCOMB_AUTH_SECRET": "jwt-segredo-unico-de-testes-2026"}):
            for _ in range(10):
                self.assertIsNone(await aplicar_rate_limit(_request(), redis))
            resposta = await aplicar_rate_limit(_request(), redis)

        self.assertEqual(resposta.status_code, 429)
        self.assertEqual(resposta.headers["Retry-After"], "37")

    async def test_redis_indisponivel_falha_fechado(self):
        resposta = await aplicar_rate_limit(_request(), _RedisIndisponivel())
        self.assertEqual(resposta.status_code, 503)

    async def test_troca_de_senha_tambem_tem_limite(self):
        redis = _RedisContador()
        request = _request(path="/api/v1/auth/alterar-senha")
        for _ in range(10):
            self.assertIsNone(await aplicar_rate_limit(request, redis))
        resposta = await aplicar_rate_limit(request, redis)
        self.assertEqual(resposta.status_code, 429)

    async def test_triagem_com_ia_tem_limite_proprio(self):
        redis = _RedisContador()
        request = _request(path="/api/v1/processos/triagem")
        for _ in range(5):
            self.assertIsNone(await aplicar_rate_limit(request, redis))
        resposta = await aplicar_rate_limit(request, redis)
        self.assertEqual(resposta.status_code, 429)

    def test_configuracao_recusa_segredo_de_exemplo_e_exige_chave_fernet(self):
        ambiente = {
            "SINDCOMB_AUTH_SECRET": "CHANGE-ME-this-is-not-a-secret-value",
            "SINDCOMB_EMAIL_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
            "SINDCOMB_ENVIRONMENT": "development",
        }
        with patch.dict(os.environ, ambiente, clear=False):
            with self.assertRaises(RuntimeError):
                validar_configuracao_seguranca()

    def test_senha_administrativa_inicial_nao_aceita_valor_curto(self):
        with self.assertRaises(RuntimeError):
            validar_senha_administrativa_inicial("adm123")


if __name__ == "__main__":
    unittest.main()
