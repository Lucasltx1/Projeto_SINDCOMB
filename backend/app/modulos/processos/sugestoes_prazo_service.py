from __future__ import annotations

import hashlib
import re

from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .models import SugestaoPrazoDB
from .schemas import MovimentacaoPublica

_INDICIOS_PRAZO = re.compile(
    r"\b(intima(?:ção|cao|do)|prazo|manifest(?:ar|ação|acao)|"
    r"apresent(?:ar|ação|acao)|contestação|contestacao|recurso|embargos)\b",
    re.IGNORECASE,
)


def sugerir_prazos_de_movimentacoes(
    sessao: Session,
    processo_id: int,
    movimentacoes: list[MovimentacaoPublica],
) -> int:
    candidatas = []
    for movimento in movimentacoes:
        fonte = movimento.fonte_dados
        if fonte is None or not _INDICIOS_PRAZO.search(movimento.texto):
            continue
        chave_base = "\n".join(
            (
                movimento.data_fonte.isoformat() if movimento.data_fonte else "",
                " ".join(movimento.texto.split()).casefold(),
            )
        )
        candidatas.append(
            {
                "id_processo": processo_id,
                "chave_evento": hashlib.sha256(chave_base.encode("utf-8")).hexdigest(),
                "texto_fonte": movimento.texto,
                "data_publicacao": movimento.data_fonte,
                "fonte": fonte,
                "fonte_url": str(movimento.fonte_url) if movimento.fonte_url else None,
            }
        )
    if not candidatas:
        return 0

    dialeto = sessao.get_bind().dialect.name
    if dialeto == "postgresql":
        comando = postgresql_insert(SugestaoPrazoDB).values(candidatas)
        resultado = sessao.execute(
            comando.on_conflict_do_nothing(
                index_elements=["id_processo", "chave_evento"]
            )
        )
        return resultado.rowcount or 0
    if dialeto == "sqlite":
        comando = sqlite_insert(SugestaoPrazoDB).values(candidatas)
        resultado = sessao.execute(
            comando.on_conflict_do_nothing(
                index_elements=["id_processo", "chave_evento"]
            )
        )
        return resultado.rowcount or 0

    sessao.add_all(SugestaoPrazoDB(**candidata) for candidata in candidatas)
    return len(candidatas)
