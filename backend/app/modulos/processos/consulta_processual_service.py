"""Consulta fontes oficiais sem confundir falha com ausência de dados."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from .datajud_service import buscar_por_numero as buscar_datajud
from .datajud_service import extrair_candidato_datajud
from .djen_service import buscar_candidato_por_numero as buscar_djen
from .numero_cnj import numero_cnj_sem_formatacao
from .schemas import ProcessoCandidato

FonteProcessual = Literal["datajud", "djen"]


@dataclass(frozen=True)
class ConsultaProcessual:
    processo: ProcessoCandidato | None
    fonte: FonteProcessual | None
    fontes_consultadas: tuple[FonteProcessual, ...]
    consultado_em: datetime


async def consultar_por_numero(numero: str, tribunal_alias: str) -> ConsultaProcessual:
    """Consulta DataJud; se não localizar o CNJ, busca publicações no DJEN.

    Erros da primeira fonte são propagados. Uma falha do DataJud não é tratada
    como ausência de processo nem escondida por uma consulta complementar.
    O DJEN fornece publicações/comunicações, não o inteiro teor dos autos.
    """
    datajud_itens = await buscar_datajud(numero, tribunal_alias)
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

    if item_datajud is not None:
        agora = datetime.now(timezone.utc)
        processo = extrair_candidato_datajud(item_datajud, numero, tribunal_alias).model_copy(
            update={"origem_dados": "datajud", "consultado_em": agora}
        )
        return ConsultaProcessual(
            processo=processo,
            fonte="datajud",
            fontes_consultadas=("datajud",),
            consultado_em=agora,
        )

    processo_djen = await buscar_djen(numero, tribunal_alias)
    fontes_consultadas: tuple[FonteProcessual, ...] = ("datajud", "djen")
    agora = datetime.now(timezone.utc)
    if processo_djen is None:
        return ConsultaProcessual(
            processo=None,
            fonte=None,
            fontes_consultadas=fontes_consultadas,
            consultado_em=agora,
        )

    processo_djen = processo_djen.model_copy(
        update={"origem_dados": "djen", "consultado_em": agora}
    )
    return ConsultaProcessual(
        processo=processo_djen,
        fonte="djen",
        fontes_consultadas=fontes_consultadas,
        consultado_em=agora,
    )
