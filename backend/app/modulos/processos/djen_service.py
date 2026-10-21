"""Cliente da consulta pública oficial do Diário de Justiça Eletrônico Nacional."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from html.parser import HTMLParser
import os
import re
from typing import Any
from urllib.parse import urlencode, urlparse

import httpx

from .numero_cnj import normalizar_numero_cnj, numero_cnj_sem_formatacao
from .schemas import MovimentacaoPublica, ProcessoCandidato

DJEN_API_BASE_URL = "https://comunicaapi.pje.jus.br/api/v1"


class _ExtratorTextoHTML(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.partes: list[str] = []

    def handle_data(self, data: str) -> None:
        texto = " ".join(data.split())
        if texto:
            self.partes.append(texto)


def _limpar_html(valor: Any) -> str | None:
    if not isinstance(valor, str) or not valor.strip():
        return None
    parser = _ExtratorTextoHTML()
    parser.feed(valor)
    texto = " ".join(parser.partes)
    return texto[:20000] or None


def _texto(item: dict[str, Any], *chaves: str) -> str | None:
    for chave in chaves:
        valor = item.get(chave)
        if isinstance(valor, str) and valor.strip():
            return valor.strip()
    return None


def _itens(payload: dict[str, Any]) -> list[dict[str, Any]]:
    for chave in ("items", "comunicacoes", "content"):
        valor = payload.get(chave)
        if isinstance(valor, list):
            return [item for item in valor if isinstance(item, dict)]
    return []


def _data(item: dict[str, Any]) -> datetime | None:
    valor = _texto(item, "dataDisponibilizacao", "data_disponibilizacao", "data")
    if not valor:
        return None
    texto = valor.strip()
    if texto.endswith("Z"):
        texto = f"{texto[:-1]}+00:00"
    try:
        resultado = datetime.fromisoformat(texto)
    except ValueError:
        return None
    if resultado.tzinfo is None:
        return resultado.replace(tzinfo=timezone.utc)
    return resultado.astimezone(timezone.utc)


def _url_oficial(item: dict[str, Any], numero_sem_mascara: str) -> str:
    """Prefere a certidão CNJ; aceita link externo somente em domínio .jus.br."""
    hash_comunicacao = _texto(item, "hash", "hashComunicacao")
    if hash_comunicacao and re.fullmatch(r"[A-Za-z0-9_-]{10,100}", hash_comunicacao):
        return f"{DJEN_API_BASE_URL}/comunicacao/{hash_comunicacao}/certidao"

    for chave in ("link", "url", "urlProcesso", "linkProcesso"):
        valor = item.get(chave)
        if isinstance(valor, dict):
            valor = valor.get("url") or valor.get("href")
        if not isinstance(valor, str):
            continue
        parsed = urlparse(valor)
        if parsed.scheme == "https" and parsed.hostname and parsed.hostname.endswith(".jus.br"):
            return valor

    return f"{DJEN_API_BASE_URL}/comunicacao?{urlencode({'numeroProcesso': numero_sem_mascara})}"


def _limite_tentativas() -> int:
    try:
        tentativas = int(os.getenv("SINDCOMB_SYNC_MAX_ATTEMPTS", "3"))
    except ValueError:
        tentativas = 3
    return min(max(tentativas, 1), 6)


def _atraso_base_segundos() -> int:
    try:
        atraso = int(os.getenv("SINDCOMB_SYNC_RETRY_BASE_SECONDS", "2"))
    except ValueError:
        atraso = 2
    return min(max(atraso, 1), 30)


async def _consultar(numero_sem_mascara: str) -> dict[str, Any]:
    url = f"{DJEN_API_BASE_URL}/comunicacao"
    parametros = {
        "numeroProcesso": numero_sem_mascara,
        "pagina": "1",
        "itensPorPagina": "50",
    }
    tentativas = _limite_tentativas()
    for tentativa in range(1, tentativas + 1):
        try:
            async with httpx.AsyncClient(timeout=25.0, follow_redirects=False) as cliente:
                resposta = await cliente.get(
                    url,
                    params=parametros,
                    headers={"Accept": "application/json"},
                )
            resposta.raise_for_status()
            payload = resposta.json()
            if not isinstance(payload, dict):
                raise ValueError("A API pública do DJEN retornou uma resposta JSON inválida.")
            return payload
        except httpx.HTTPStatusError as erro:
            retentavel = erro.response.status_code in {408, 429} or erro.response.status_code >= 500
            if not retentavel or tentativa == tentativas:
                raise
        except httpx.TransportError:
            if tentativa == tentativas:
                raise

        atraso = min(_atraso_base_segundos() * (2 ** (tentativa - 1)), 30)
        await asyncio.sleep(atraso)

    return {"items": []}


async def buscar_candidato_por_numero(
    numero: str,
    tribunal_alias: str,
) -> ProcessoCandidato | None:
    """Busca publicações públicas do CNJ e seleciona a mais recente do processo."""
    numero_formatado = normalizar_numero_cnj(numero)
    numero_sem_mascara = numero_cnj_sem_formatacao(numero_formatado)
    payload = await _consultar(numero_sem_mascara)
    comunicacoes = [
        item
        for item in _itens(payload)
        if _texto(item, "numeroProcesso", "numero_processo")
        and numero_cnj_sem_formatacao(
            _texto(item, "numeroProcesso", "numero_processo") or ""
        ) == numero_sem_mascara
    ]
    if not comunicacoes:
        return None

    comunicacoes.sort(
        key=lambda item: _data(item) or datetime.min.replace(tzinfo=timezone.utc)
    )
    movimentacoes: list[MovimentacaoPublica] = []
    chaves_vistas: set[tuple[str, str | None]] = set()
    for comunicacao in comunicacoes:
        tipo = _texto(comunicacao, "tipoComunicacao", "tipo_comunicacao", "meio")
        orgao = _texto(comunicacao, "nomeOrgao", "nome_orgao", "orgao")
        teor = _limpar_html(
            _texto(comunicacao, "texto", "teor", "conteudo", "descricao")
        )
        detalhes = [valor for valor in (tipo, orgao, teor) if valor]
        texto = " — ".join(detalhes) or "Publicação localizada no DJEN."
        data_fonte = _data(comunicacao)
        chave = (
            " ".join(texto.split()).casefold(),
            data_fonte.isoformat() if data_fonte else None,
        )
        if chave in chaves_vistas:
            continue
        chaves_vistas.add(chave)
        movimentacoes.append(
            MovimentacaoPublica(
                texto=texto[:20000],
                data_fonte=data_fonte,
                fonte_url=_url_oficial(comunicacao, numero_sem_mascara),
                fonte_dados="djen",
            )
        )

    ultima = comunicacoes[-1]
    movimentacao_recente = movimentacoes[-1] if movimentacoes else None
    data_publicacao = _data(ultima)
    texto_movimentacao = (
        movimentacao_recente.texto
        if movimentacao_recente
        else "Publicação localizada no DJEN."
    )
    if data_publicacao:
        texto_movimentacao = f"Disponibilizada em {data_publicacao.isoformat()} — {texto_movimentacao}"
    tribunal = _texto(ultima, "nomeTribunal", "tribunal", "siglaTribunal", "sigla_tribunal")
    if not tribunal:
        tribunal = f"Tribunal {tribunal_alias.upper()}"
    classe = _texto(ultima, "nomeClasse", "classe", "classeProcessual")
    assunto = _texto(ultima, "assunto") or "Publicação processual localizada no DJEN"

    return ProcessoCandidato(
        numero=numero_formatado,
        tribunal=tribunal[:120],
        tribunal_alias=tribunal_alias,
        classe=classe[:100] if classe else None,
        assunto=assunto[:2000],
        ultima_movimentacao=texto_movimentacao[:20000],
        movimentacoes_publicas=movimentacoes[-100:],
        fonte_url=(
            movimentacao_recente.fonte_url
            if movimentacao_recente
            else _url_oficial(ultima, numero_sem_mascara)
        ),
        data_ultima_verificacao_fonte=None,
    )
