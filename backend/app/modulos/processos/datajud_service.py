import os
import re
from typing import Any

import httpx

DATAJUD_BASE_URL = "https://api-publica.datajud.cnj.jus.br"


async def buscar_por_numero(numero: str, tribunal_alias: str, limite: int = 10) -> list[dict[str, Any]]:
    """Consulta o processo pelo número CNJ em um endpoint público do DataJud."""
    api_key = os.getenv("DATAJUD_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("Configure DATAJUD_API_KEY do CNJ.")

    alias = tribunal_alias.strip().lower()
    if not re.fullmatch(r"[a-z0-9-]{2,20}", alias):
        raise ValueError("Alias de tribunal inválido.")
    numero_limpo = re.sub(r"\D", "", numero)
    if len(numero_limpo) != 20:
        raise ValueError("O número CNJ deve conter 20 dígitos.")

    url = f"{DATAJUD_BASE_URL}/api_publica_{alias}/_search"
    consulta = {
        "size": max(1, min(limite, 10)),
        "query": {"match": {"numeroProcesso": numero_limpo}},
    }
    headers = {"Authorization": f"APIKey {api_key}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=25.0) as client:
        resposta = await client.post(url, json=consulta, headers=headers)
        resposta.raise_for_status()
        payload = resposta.json()

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
            nome = ultimo.get("nome") or (ultimo.get("movimentoNacional") or {}).get("nome")
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
