from datetime import datetime, timezone
import asyncio
import unittest
from unittest.mock import AsyncMock, patch

import httpx

from app.modulos.processos import consulta_processual_service, datajud_service, djen_service
from app.modulos.processos import sincronizacao_service
from app.modulos.processos.consulta_processual_service import ConsultaProcessual
from app.modulos.processos.djen_service import ResultadoConsultaDJEN
from app.modulos.processos.schemas import (
    MovimentacaoPublica,
    MovimentacaoRegistro,
    ProcessoCandidato,
    ProcessoRegistro,
    ResultadoTriagem,
)


NUMERO = "0101504-67.2026.5.01.0266"
NUMERO_SEM_FORMATACAO = "01015046720265010266"


class TestDataJudMovements(unittest.TestCase):
    def test_extracts_dated_events_in_chronological_order(self):
        candidate = datajud_service.extrair_candidato_datajud(
            {
                "numeroProcesso": NUMERO_SEM_FORMATACAO,
                "movimentos": [
                    {
                        "dataHora": "2026-02-02T10:30:00",
                        "movimentoNacional": {"nome": "Conclusos para decisão"},
                    },
                    {
                        "dataHora": "2026-01-01T09:00:00Z",
                        "nome": "Distribuído",
                    },
                ],
            },
            NUMERO,
            "trt1",
        )

        self.assertEqual(
            [movimento.texto for movimento in candidate.movimentacoes_publicas],
            ["Distribuído", "Conclusos para decisão"],
        )
        self.assertEqual(candidate.movimentacoes_publicas[0].fonte_dados, "datajud")
        self.assertEqual(
            candidate.movimentacoes_publicas[1].data_fonte,
            datetime(2026, 2, 2, 10, 30, tzinfo=timezone.utc),
        )
        self.assertEqual(candidate.ultima_movimentacao, "Conclusos para decisão")
        self.assertNotIn("movimentacoes_publicas", candidate.model_dump())


class TestDJENMovements(unittest.IsolatedAsyncioTestCase):
    async def test_returns_all_exact_process_publications_with_source_dates_and_links(self):
        payload = {
            "items": [
                {
                    "numeroProcesso": NUMERO_SEM_FORMATACAO,
                    "dataDisponibilizacao": "2026-02-02",
                    "tipoComunicacao": "Intimação",
                    "nomeOrgao": "Vara do Trabalho",
                    "texto": "<p>Manifestação sobre documentos</p>",
                    "hash": "abcdefghij1234567890",
                },
                {
                    "numeroProcesso": NUMERO_SEM_FORMATACAO,
                    "dataDisponibilizacao": "2026-01-01",
                    "tipoComunicacao": "Despacho",
                    "nomeOrgao": "Vara do Trabalho",
                    "texto": "<p>Apresente documentos</p>",
                    "hash": "zyxwvutsrq1234567890",
                },
                {
                    "numeroProcesso": "00000000000000000000",
                    "dataDisponibilizacao": "2026-03-01",
                    "texto": "Outro processo",
                },
            ]
        }
        with patch.object(djen_service, "_consultar", new=AsyncMock(return_value=payload)):
            candidate = await djen_service.buscar_candidato_por_numero(NUMERO, "trt1")

        self.assertIsNotNone(candidate)
        assert candidate is not None
        self.assertEqual(
            [movimento.texto for movimento in candidate.movimentacoes_publicas],
            [
                "Despacho — Vara do Trabalho — Apresente documentos",
                "Intimação — Vara do Trabalho — Manifestação sobre documentos",
            ],
        )
        self.assertEqual(candidate.movimentacoes_publicas[0].fonte_dados, "djen")
        self.assertEqual(
            str(candidate.movimentacoes_publicas[1].fonte_url),
            "https://comunicaapi.pje.jus.br/api/v1/comunicacao/abcdefghij1234567890/certidao",
        )
        self.assertTrue(candidate.ultima_movimentacao.startswith("Disponibilizada em 2026-02-02"))

    async def test_paginates_results_and_reports_complete_coverage(self):
        primeira_pagina = [
            {
                "numeroProcesso": NUMERO_SEM_FORMATACAO,
                "dataDisponibilizacao": f"2026-01-{(indice % 28) + 1:02d}",
                "tipoComunicacao": "Intimação",
                "texto": f"Publicação {indice}",
            }
            for indice in range(50)
        ]
        segunda_pagina = [
            {
                "numeroProcesso": NUMERO_SEM_FORMATACAO,
                "dataDisponibilizacao": "2026-02-01",
                "tipoComunicacao": "Despacho",
                "texto": "Publicação adicional",
            }
        ]
        with (
            patch.object(djen_service, "_limite_paginas", return_value=3),
            patch.object(
                djen_service,
                "_consultar",
                new=AsyncMock(side_effect=[{"items": primeira_pagina}, {"items": segunda_pagina}]),
            ) as consultar,
        ):
            resultado = await djen_service.consultar_por_numero(NUMERO, "trt1")

        self.assertEqual(consultar.await_count, 2)
        self.assertEqual(resultado.publicacoes_consultadas, 51)
        self.assertEqual(resultado.paginas_consultadas, 2)
        self.assertFalse(resultado.limite_atingido)
        self.assertEqual(resultado.processo.cobertura_consulta["paginas_djen_consultadas"], 2)


class TestConsultaCombinada(unittest.IsolatedAsyncioTestCase):
    def _datajud_item(self):
        return {
            "numeroProcesso": NUMERO_SEM_FORMATACAO,
            "tribunal": "TRT1",
            "movimentos": [
                {
                    "dataHora": "2026-01-01T09:00:00Z",
                    "nome": "Distribuído",
                }
            ],
        }

    async def test_combines_datajud_and_djen_events(self):
        djen = ProcessoCandidato(
            numero=NUMERO,
            tribunal="TRT1",
            tribunal_alias="trt1",
            assunto="Publicação",
            ultima_movimentacao="Intimação",
            movimentacoes_publicas=[
                MovimentacaoPublica(
                    texto="Intimação",
                    data_fonte=datetime(2026, 2, 2, tzinfo=timezone.utc),
                    fonte_dados="djen",
                )
            ],
        )
        with (
            patch.object(
                consulta_processual_service,
                "buscar_datajud",
                new=AsyncMock(return_value=[self._datajud_item()]),
            ),
            patch.object(
                consulta_processual_service,
                "consultar_djen",
                new=AsyncMock(
                    return_value=ResultadoConsultaDJEN(
                        processo=djen,
                        publicacoes_consultadas=1,
                        paginas_consultadas=1,
                        limite_atingido=False,
                    )
                ),
            ),
        ):
            resultado = await consulta_processual_service.consultar_por_numero(NUMERO, "trt1")

        self.assertEqual(resultado.fontes_consultadas, ("datajud", "djen"))
        self.assertEqual(resultado.fonte, "datajud")
        self.assertEqual(
            [movimento.fonte_dados for movimento in resultado.processo.movimentacoes_publicas],
            ["datajud", "djen"],
        )
        self.assertEqual(resultado.processo.ultima_movimentacao, "Intimação")

    async def test_preserves_datajud_when_djen_is_temporarily_unavailable(self):
        with (
            patch.object(
                consulta_processual_service,
                "buscar_datajud",
                new=AsyncMock(return_value=[self._datajud_item()]),
            ),
            patch.object(
                consulta_processual_service,
                "consultar_djen",
                new=AsyncMock(side_effect=httpx.ConnectError("offline")),
            ),
        ):
            resultado = await consulta_processual_service.consultar_por_numero(NUMERO, "trt1")

        self.assertIsNotNone(resultado.processo)
        self.assertEqual(resultado.falhas_fontes, ("djen:ConnectError",))
        self.assertEqual(resultado.processo.movimentacoes_publicas[0].texto, "Distribuído")


class _SessaoSincronizacao:
    def __init__(self):
        self.adicionados = []
        self.commits = 0

    def add(self, registro):
        self.adicionados.append(registro)

    def commit(self):
        self.commits += 1

    def rollback(self):
        pass


class TestSincronizacaoMovimentacoes(unittest.IsolatedAsyncioTestCase):
    async def test_external_process_queries_use_bounded_concurrency(self):
        processos = [
            ProcessoRegistro(
                id=str(indice),
                dados=ProcessoCandidato(
                    numero=f"0000000000000000000{indice}",
                    tribunal="TRT1",
                    tribunal_alias="trt1",
                    assunto="Teste",
                ),
                triagem=ResultadoTriagem(
                    relevancia="revisar",
                    justificativa="Teste.",
                    confianca=0.5,
                ),
                criado_por="1",
            )
            for indice in range(1, 6)
        ]
        resultado_consulta = ConsultaProcessual(
            processo=None,
            fonte=None,
            fontes_consultadas=("datajud",),
            consultado_em=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
        concorrentes = 0
        max_concorrentes = 0

        async def consultar(_numero, _alias):
            nonlocal concorrentes, max_concorrentes
            concorrentes += 1
            max_concorrentes = max(max_concorrentes, concorrentes)
            await asyncio.sleep(0.01)
            concorrentes -= 1
            return resultado_consulta

        with (
            patch.dict(
                "os.environ",
                {"DATAJUD_API_KEY": "test", "SINDCOMB_SYNC_MAX_CONCURRENCY": "2"},
            ),
            patch.object(sincronizacao_service, "listar", return_value=processos),
            patch.object(sincronizacao_service, "consultar_por_numero", new=AsyncMock(side_effect=consultar)),
        ):
            resultado = await sincronizacao_service.sincronizar_processos(
                _SessaoSincronizacao()
            )

        self.assertEqual(resultado.processos_consultados, 5)
        self.assertEqual(max_concorrentes, 2)

    async def test_suggests_deadline_from_latest_movement_fallback(self):
        instante = datetime(2026, 3, 1, tzinfo=timezone.utc)
        processo = ProcessoRegistro(
            id="8",
            dados=ProcessoCandidato(
                numero=NUMERO,
                tribunal="TRT1",
                tribunal_alias="trt1",
                assunto="Ação trabalhista",
                ultima_movimentacao="Movimentação anterior",
            ),
            triagem=ResultadoTriagem(
                relevancia="revisar",
                justificativa="Revisar movimentação.",
                confianca=0.5,
            ),
            criado_por="1",
        )
        candidato = ProcessoCandidato(
            numero=NUMERO,
            tribunal="TRT1",
            tribunal_alias="trt1",
            assunto="Ação trabalhista",
            ultima_movimentacao="Intimação para manifestação",
            movimentacoes_publicas=[],
        )
        consulta = ConsultaProcessual(
            processo=candidato,
            fonte="djen",
            fontes_consultadas=("datajud", "djen"),
            consultado_em=instante,
        )
        sessao = _SessaoSincronizacao()

        async def interpretar(evento, fonte_padrao):
            return MovimentacaoRegistro(
                texto=evento.texto,
                resumo=evento.texto,
                categoria="intimacao",
                requer_atencao=True,
                fonte_dados=evento.fonte_dados or fonte_padrao,
                data_fonte=evento.data_fonte,
                registrada_por="DJEN/CNJ",
                registrada_em=instante,
            )

        with (
            patch.dict("os.environ", {"DATAJUD_API_KEY": "test"}),
            patch.object(sincronizacao_service, "listar", return_value=[processo]),
            patch.object(
                sincronizacao_service,
                "consultar_por_numero",
                new=AsyncMock(return_value=consulta),
            ),
            patch.object(
                sincronizacao_service,
                "interpretar_movimentacao_publica",
                new=AsyncMock(side_effect=interpretar),
            ),
            patch.object(
                sincronizacao_service,
                "classificar_interesse",
                new=AsyncMock(
                    return_value=ResultadoTriagem(
                        relevancia="revisar",
                        justificativa="Revisar movimentação.",
                        confianca=0.5,
                    )
                ),
            ),
            patch.object(
                sincronizacao_service,
                "salvar",
                side_effect=lambda _sessao, atualizado, **_kwargs: atualizado,
            ),
            patch.object(sincronizacao_service, "enfileirar_notificacao_processo"),
            patch.object(sincronizacao_service, "notificar_usuarios_do_processo"),
            patch.object(
                sincronizacao_service,
                "sugerir_prazos_de_movimentacoes",
            ) as sugerir,
        ):
            resultado = await sincronizacao_service.sincronizar_processos(sessao)

        self.assertEqual(resultado.processos_com_movimentacao_nova, 1)
        eventos_sugeridos = sugerir.call_args.args[2]
        self.assertEqual(len(eventos_sugeridos), 1)
        self.assertEqual(eventos_sugeridos[0].texto, "Intimação para manifestação")
        self.assertEqual(eventos_sugeridos[0].fonte_dados, "djen")

    async def test_imports_only_new_events_and_records_their_count(self):
        data_antiga = datetime(2026, 1, 1, tzinfo=timezone.utc)
        data_nova_1 = datetime(2026, 2, 1, tzinfo=timezone.utc)
        data_nova_2 = datetime(2026, 3, 1, tzinfo=timezone.utc)
        movimento_existente = MovimentacaoRegistro(
            texto="Distribuído",
            resumo="Distribuído",
            categoria="andamento",
            requer_atencao=False,
            fonte_dados="datajud",
            data_fonte=data_antiga,
            registrada_por="DataJud",
            registrada_em=data_antiga,
        )
        processo = ProcessoRegistro(
            id="7",
            dados=ProcessoCandidato(
                numero=NUMERO,
                tribunal="TRT1",
                tribunal_alias="trt1",
                assunto="Ação trabalhista",
                ultima_movimentacao="Distribuído",
            ),
            triagem=ResultadoTriagem(
                relevancia="revisar",
                justificativa="Revisão necessária.",
                confianca=0.5,
            ),
            criado_por="1",
            movimentacoes=[movimento_existente],
        )
        candidato = ProcessoCandidato(
            numero=NUMERO,
            tribunal="TRT1",
            tribunal_alias="trt1",
            assunto="Ação trabalhista",
            ultima_movimentacao="Sentença publicada",
            movimentacoes_publicas=[
                MovimentacaoPublica(
                    texto="Distribuído",
                    data_fonte=data_antiga,
                    fonte_dados="datajud",
                ),
                MovimentacaoPublica(
                    texto="Audiência realizada",
                    data_fonte=data_nova_1,
                    fonte_dados="datajud",
                ),
                MovimentacaoPublica(
                    texto="Sentença publicada",
                    data_fonte=data_nova_2,
                    fonte_dados="djen",
                ),
            ],
        )
        consulta = ConsultaProcessual(
            processo=candidato,
            fonte="datajud",
            fontes_consultadas=("datajud", "djen"),
            consultado_em=data_nova_2,
        )
        sessao = _SessaoSincronizacao()

        async def interpretar(evento, fonte_padrao):
            return MovimentacaoRegistro(
                texto=evento.texto,
                resumo=evento.texto,
                categoria="andamento",
                requer_atencao=False,
                fonte_dados=evento.fonte_dados or fonte_padrao,
                data_fonte=evento.data_fonte,
                registrada_por="DataJud",
                registrada_em=data_nova_2,
            )

        with (
            patch.dict("os.environ", {"DATAJUD_API_KEY": "test"}),
            patch.object(sincronizacao_service, "listar", return_value=[processo]),
            patch.object(
                sincronizacao_service,
                "consultar_por_numero",
                new=AsyncMock(return_value=consulta),
            ),
            patch.object(
                sincronizacao_service,
                "interpretar_movimentacao_publica",
                new=AsyncMock(side_effect=interpretar),
            ),
            patch.object(
                sincronizacao_service,
                "classificar_interesse",
                new=AsyncMock(
                    return_value=ResultadoTriagem(
                        relevancia="revisar",
                        justificativa="Revisão necessária.",
                        confianca=0.5,
                    )
                ),
            ),
            patch.object(
                sincronizacao_service,
                "salvar",
                side_effect=lambda _sessao, atualizado, **_kwargs: atualizado,
            ) as salvar,
            patch.object(sincronizacao_service, "enfileirar_notificacao_processo"),
            patch.object(sincronizacao_service, "notificar_usuarios_do_processo"),
        ):
            resultado = await sincronizacao_service.sincronizar_processos(sessao)

        self.assertEqual(resultado.processos_com_movimentacao_nova, 1)
        self.assertEqual(salvar.call_args.args[1].movimentacoes[-2].texto, "Audiência realizada")
        self.assertEqual(salvar.call_args.args[1].movimentacoes[-1].fonte_dados, "djen")
        self.assertEqual(sessao.adicionados[-1].quantidade_atualizacoes, 2)
