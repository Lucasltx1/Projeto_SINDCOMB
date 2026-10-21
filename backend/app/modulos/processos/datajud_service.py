import asyncio
import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx

from .numero_cnj import numero_cnj_sem_formatacao
from .schemas import MovimentacaoPublica, ProcessoCandidato

DATAJUD_BASE_URL = "https://api-publica.datajud.cnj.jus.br"


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


async def buscar_por_numero(numero: str, tribunal_alias: str, limite: int = 10) -> list[dict[str, Any]]:
    """Consulta o processo pelo número CNJ em um endpoint público do DataJud."""
    api_key = os.getenv("DATAJUD_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Configure DATAJUD_API_KEY do CNJ.")

    alias = tribunal_alias.strip().lower()
    if not re.fullmatch(r"[a-z0-9-]{2,20}", alias):
        raise ValueError("Alias de tribunal inválido.")
    numero_limpo = numero_cnj_sem_formatacao(numero)

    url = f"{DATAJUD_BASE_URL}/api_publica_{alias}/_search"
    consulta = {
        "size": max(1, min(limite, 10)),
        "query": {"match": {"numeroProcesso": numero_limpo}},
    }
    headers = {"Authorization": f"APIKey {api_key}", "Content-Type": "application/json"}

    limite_tentativas = _limite_tentativas()
    for tentativa in range(1, limite_tentativas + 1):
        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                resposta = await client.post(url, json=consulta, headers=headers)
                resposta.raise_for_status()
                payload = resposta.json()
            break
        except httpx.HTTPStatusError as erro:
            retentavel = erro.response.status_code in {408, 429} or erro.response.status_code >= 500
            if not retentavel or tentativa == limite_tentativas:
                raise
        except httpx.TransportError:
            if tentativa == limite_tentativas:
                raise
        base = _atraso_base_segundos()
        await asyncio.sleep(min(base * (2 ** (tentativa - 1)), 30))

    hits = (payload.get("hits") or {}).get("hits") or []
    return [item["_source"] for item in hits if isinstance(item, dict) and isinstance(item.get("_source"), dict)]


def extrair_atualizacao(fonte: dict[str, Any]) -> dict[str, str | None]:
    """Extrai campos opcionais do esquema público do DataJud."""
    classe = fonte.get("classe") or {}
    if isinstance(classe, dict):
        classe = classe.get("nome") or classe.get("descricao")

    assuntos = fonte.get("assuntos") or fonte.get("assunto") or []
    if isinstance(assuntos, dict):
        assuntos = [assuntos]
    if isinstance(assuntos, list):
        assunto = "; ".join(
            str(item.get("nome") or item.get("descricao") or item.get("codigo") or "")
            if isinstance(item, dict) else str(item)
            for item in assuntos
        ).strip("; ")
    else:
        assunto = str(assuntos)

    movimentos = fonte.get("movimentos") or fonte.get("movimento") or []
    if isinstance(movimentos, dict):
        movimentos = [movimentos]
    movimento_recente = None
    if isinstance(movimentos, list) and movimentos:
        validos = [item for item in movimentos if isinstance(item, dict)]
        if validos:
            ultimo = max(validos, key=lambda item: str(item.get("dataHora") or ""))
            movimento_nacional = ultimo.get("movimentoNacional")
            nome_nacional = movimento_nacional.get("nome") if isinstance(movimento_nacional, dict) else None
            nome = ultimo.get("nome") or nome_nacional
            complemento = ultimo.get("complemento") or ultimo.get("complementosTabelados")
            if isinstance(complemento, list):
                complemento = "; ".join(
                    str(c.get("nome") or c.get("descricao") or "") for c in complemento if isinstance(c, dict)
                )
            movimento_recente = " — ".join(str(valor) for valor in (nome, complemento) if valor)

    return {
        "classe": str(classe) if classe else None,
        "assunto": assunto or None,
        "ultima_movimentacao": movimento_recente,
    }


def extrair_movimentacoes_publicas(
    fonte: dict[str, Any], limite: int = 100
) -> list[MovimentacaoPublica]:
    movimentos = fonte.get("movimentos") or fonte.get("movimento") or []
    if isinstance(movimentos, dict):
        movimentos = [movimentos]
    if not isinstance(movimentos, list):
        return []

    resultado: list[MovimentacaoPublica] = []
    chaves_vistas: set[tuple[str, str | None]] = set()
    for movimento in movimentos:
        if not isinstance(movimento, dict):
            continue

        movimento_nacional = movimento.get("movimentoNacional")
        nome_nacional = (
            movimento_nacional.get("nome")
            if isinstance(movimento_nacional, dict)
            else None
        )
        nome = movimento.get("nome") or nome_nacional
        complemento = movimento.get("complemento") or movimento.get("complementosTabelados")
        if isinstance(complemento, list):
            complemento = "; ".join(
                str(item.get("nome") or item.get("descricao") or "")
                for item in complemento
                if isinstance(item, dict)
            )
        texto = " — ".join(str(valor).strip() for valor in (nome, complemento) if valor)
        if not texto:
            continue

        data_fonte = _data_hora(movimento.get("dataHora") or movimento.get("data"))
        data_chave = data_fonte.isoformat() if data_fonte else None
        chave = (" ".join(texto.split()).casefold(), data_chave)
        if chave in chaves_vistas:
            continue
        chaves_vistas.add(chave)
        resultado.append(
            MovimentacaoPublica(
                texto=texto[:20000],
                data_fonte=data_fonte,
                fonte_dados="datajud",
            )
        )

    resultado.sort(key=lambda item: item.data_fonte or datetime.min.replace(tzinfo=timezone.utc))
    return resultado[-max(1, min(limite, 100)):]


def _data_hora(valor: Any) -> datetime | None:
    if not isinstance(valor, str) or not valor.strip():
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


def extrair_candidato_datajud(
    fonte: dict[str, Any], numero_formatado: str, tribunal_alias: str
) -> ProcessoCandidato:
    """Converte os metadados públicos encontrados em dados para a triagem do sistema."""
    atualizacao = extrair_atualizacao(fonte)
    partes: list[str] = []
    advogados: list[str] = []

    partes_fonte = fonte.get("partes") or []
    if isinstance(partes_fonte, dict):
        partes_fonte = [partes_fonte]
    if isinstance(partes_fonte, list):
        for parte in partes_fonte:
            if not isinstance(parte, dict):
                continue
            nome_parte = parte.get("nome") or parte.get("nomeParte")
            if nome_parte:
                partes.append(str(nome_parte).strip())
            representantes = parte.get("representantes") or parte.get("advogados") or []
            if isinstance(representantes, dict):
                representantes = [representantes]
            if isinstance(representantes, list):
                for representante in representantes:
                    if isinstance(representante, dict):
                        nome_advogado = representante.get("nome") or representante.get("nomeAdvogado")
                        if nome_advogado:
                            advogados.append(str(nome_advogado).strip())

    tribunal = str(fonte.get("tribunal") or tribunal_alias.upper()).strip()
    return ProcessoCandidato(
        numero=numero_formatado,
        tribunal=tribunal,
        tribunal_alias=tribunal_alias,
        classe=atualizacao["classe"],
        assunto=atualizacao["assunto"] or "Assunto não informado",
        partes=list(dict.fromkeys(nome for nome in partes if nome)),
        advogados=list(dict.fromkeys(nome for nome in advogados if nome)),
        associados_mencionados=list(dict.fromkeys(nome for nome in partes if nome)),
        ultima_movimentacao=atualizacao["ultima_movimentacao"],
        movimentacoes_publicas=extrair_movimentacoes_publicas(fonte),
    )
