"""Consulta fontes oficiais sem confundir falha com ausência de dados."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal

import httpx

from .datajud_service import buscar_por_numero as buscar_datajud
from .datajud_service import extrair_candidato_datajud
from .djen_service import consultar_por_numero as consultar_djen
from .numero_cnj import numero_cnj_sem_formatacao
from .schemas import MovimentacaoPublica, ProcessoCandidato

FonteProcessual = Literal["datajud", "djen"]


@dataclass(frozen=True)
class ConsultaProcessual:
    processo: ProcessoCandidato | None
    fonte: FonteProcessual | None
    fontes_consultadas: tuple[FonteProcessual, ...]
    consultado_em: datetime
    falhas_fontes: tuple[str, ...] = ()
    cobertura_consulta: dict[str, int | bool] = field(default_factory=dict)


async def consultar_por_numero(numero: str, tribunal_alias: str) -> ConsultaProcessual:
    """Consulta DataJud e complementa os movimentos com publicações do DJEN.

    Erros da primeira fonte são propagados. Uma falha do DataJud não é tratada
    como ausência de processo nem escondida por uma consulta complementar. Se
    o DataJud localizar o processo e o DJEN falhar, preserva os dados do DataJud
    e informa a falha parcial para o histórico da sincronização.
    O DJEN fornece publicações/comunicações, não o inteiro teor dos autos.
    """
    datajud_itens = await buscar_datajud(numero, tribunal_alias)
    cobertura_datajud: dict[str, int | bool] = {
        "resultados_datajud_consultados": len(datajud_itens),
        "limite_datajud_resultados_atingido": len(datajud_itens) >= 10,
    }
    numero_alvo = numero_cnj_sem_formatacao(numero)
    item_datajud = next(
        (
            item
            for item in datajud_itens
            if item.get("numeroProcesso")
            and numero_cnj_sem_formatacao(str(item["numeroProcesso"])) == numero_alvo
        ),
        None,
    )

    processo_datajud = (
        extrair_candidato_datajud(item_datajud, numero, tribunal_alias)
        if item_datajud is not None
        else None
    )
    consulta_djen = None
    try:
        consulta_djen = await consultar_djen(numero, tribunal_alias)
        processo_djen = consulta_djen.processo
    except (httpx.HTTPError, ValueError) as erro:
        if processo_datajud is None:
            raise
        agora = datetime.now(timezone.utc)
        cobertura = {**cobertura_datajud, **processo_datajud.cobertura_consulta}
        processo = processo_datajud.model_copy(
            update={
                "origem_dados": "datajud",
                "consultado_em": agora,
                "cobertura_consulta": cobertura,
            }
        )
        return ConsultaProcessual(
            processo=processo,
            fonte="datajud",
            fontes_consultadas=("datajud", "djen"),
            consultado_em=agora,
            falhas_fontes=(f"djen:{type(erro).__name__}",),
            cobertura_consulta=cobertura,
        )

    agora = datetime.now(timezone.utc)
    cobertura_djen: dict[str, int | bool] = (
        {
            "publicacoes_djen_consultadas": consulta_djen.publicacoes_consultadas,
            "paginas_djen_consultadas": consulta_djen.paginas_consultadas,
            "limite_djen_atingido": consulta_djen.limite_atingido,
        }
        if consulta_djen is not None
        else {}
    )
    if processo_datajud is None and processo_djen is None:
        return ConsultaProcessual(
            processo=None,
            fonte=None,
            fontes_consultadas=("datajud", "djen"),
            consultado_em=agora,
            cobertura_consulta={**cobertura_datajud, **cobertura_djen},
        )

    if processo_datajud is None:
        processo = processo_djen.model_copy(
            update={
                "origem_dados": "djen",
                "consultado_em": agora,
                "cobertura_consulta": {
                    **cobertura_datajud,
                    **cobertura_djen,
                    **processo_djen.cobertura_consulta,
                },
            }
        )
        fonte: FonteProcessual = "djen"
    elif processo_djen is None:
        processo = processo_datajud.model_copy(
            update={
                "origem_dados": "datajud",
                "consultado_em": agora,
                "cobertura_consulta": {
                    **cobertura_datajud,
                    **cobertura_djen,
                    **processo_datajud.cobertura_consulta,
                },
            }
        )
        fonte = "datajud"
    else:
        eventos: dict[tuple[str, str | None], MovimentacaoPublica] = {}
        eventos_consultados = [
            *processo_datajud.movimentacoes_publicas,
            *processo_djen.movimentacoes_publicas,
        ]
        for evento in eventos_consultados:
            chave = (
                " ".join(evento.texto.split()).casefold(),
                evento.data_fonte.isoformat() if evento.data_fonte else None,
            )
            eventos.setdefault(chave, evento)
        movimentacoes = sorted(
            eventos.values(),
            key=lambda evento: evento.data_fonte or datetime.min.replace(tzinfo=timezone.utc),
        )[-100:]
        mais_recente = movimentacoes[-1] if movimentacoes else None
        processo = processo_datajud.model_copy(
            update={
                "origem_dados": "datajud",
                "consultado_em": agora,
                "movimentacoes_publicas": movimentacoes,
                "cobertura_consulta": {
                    **cobertura_datajud,
                    **cobertura_djen,
                    **processo_datajud.cobertura_consulta,
                    **(processo_djen.cobertura_consulta if processo_djen else {}),
                },
                "ultima_movimentacao": (
                    processo_djen.ultima_movimentacao
                    if mais_recente and mais_recente.fonte_dados == "djen"
                    else processo_datajud.ultima_movimentacao
                ),
                "fonte_url": (
                    next(
                        (
                            evento.fonte_url
                            for evento in reversed(movimentacoes)
                            if evento.fonte_url
                        ),
                        processo_datajud.fonte_url,
                    )
                    if movimentacoes else processo_datajud.fonte_url
                ),
            }
        )
        fonte = "datajud"

    return ConsultaProcessual(
        processo=processo,
        fonte=fonte,
        fontes_consultadas=("datajud", "djen"),
        consultado_em=agora,
        cobertura_consulta=processo.cobertura_consulta,
    )
