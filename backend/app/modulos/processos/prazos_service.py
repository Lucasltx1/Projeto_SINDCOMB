from __future__ import annotations

from datetime import date, datetime, timedelta
import logging
import os

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from .email_outbox import enfileirar_email
from .models import (
    AdministradorDB,
    JuridicoDB,
    PrazoDB,
    PrazoLembreteDB,
    PermissaoProcessoDB,
    ProcessoDB,
    UsuarioDB,
)
from .notificacoes_service import notificar_usuarios

logger = logging.getLogger(__name__)


def _hoje_local() -> date:
    try:
        from zoneinfo import ZoneInfo

        fuso = ZoneInfo(os.getenv("SINDCOMB_TIMEZONE", "America/Sao_Paulo"))
    except (ValueError, KeyError) as erro:
        raise RuntimeError("SINDCOMB_TIMEZONE contém um fuso horário inválido.") from erro
    return datetime.now(fuso).date()


def _registrar_lembrete(
    sessao: Session,
    *,
    prazo: PrazoDB,
    usuario: UsuarioDB,
    processo: ProcessoDB,
    hoje: date,
    tipo: str,
    texto_momento: str,
) -> bool:
    valores = {
        "id_prazo": prazo.id_prazo,
        "id_usuario": usuario.id_usuario,
        "tipo": tipo,
        "data_referencia": prazo.data_vencimento if tipo != "atrasado" else hoje,
    }
    dialeto = sessao.get_bind().dialect.name
    if dialeto == "postgresql":
        comando = postgresql_insert(PrazoLembreteDB).values(**valores)
        resultado = sessao.execute(
            comando.on_conflict_do_nothing(
                index_elements=["id_prazo", "tipo", "data_referencia", "id_usuario"]
            )
        )
        if not resultado.rowcount:
            return False
    elif dialeto == "sqlite":
        comando = sqlite_insert(PrazoLembreteDB).values(**valores)
        resultado = sessao.execute(
            comando.on_conflict_do_nothing(
                index_elements=["id_prazo", "tipo", "data_referencia", "id_usuario"]
            )
        )
        if not resultado.rowcount:
            return False
    else:
        existente = sessao.scalar(
            select(PrazoLembreteDB.id_lembrete).where(
                PrazoLembreteDB.id_prazo == prazo.id_prazo,
                PrazoLembreteDB.tipo == tipo,
                PrazoLembreteDB.data_referencia == valores["data_referencia"],
                PrazoLembreteDB.id_usuario == usuario.id_usuario,
            )
        )
        if existente is not None:
            return False
        sessao.add(PrazoLembreteDB(**valores))

    chave = f"prazo:{prazo.id_prazo}:{tipo}:{valores['data_referencia'].isoformat()}"
    mensagem = (
        f"O prazo “{prazo.descricao}” do processo {processo.numero_processo} "
        f"{texto_momento} (vencimento: {prazo.data_vencimento.isoformat()})."
    )
    notificar_usuarios(
        sessao,
        [usuario.id_usuario],
        categoria="lembrete_prazo",
        titulo="Lembrete de prazo processual",
        mensagem=mensagem,
        processo_id=processo.id_processo,
        chave=chave,
    )
    if usuario.email and usuario.email_verificado:
        if os.getenv("SINDCOMB_EMAIL_ENCRYPTION_KEY", "").strip():
            enfileirar_email(
                sessao,
                [usuario.email],
                f"SINDCOMB — lembrete de prazo do processo {processo.numero_processo}",
                mensagem,
                categoria="lembrete_prazo",
                processo_id=processo.id_processo,
            )
        else:
            logger.warning(
                "Lembrete do prazo %s registrado na caixa interna; e-mail não enfileirado "
                "porque SINDCOMB_EMAIL_ENCRYPTION_KEY não está configurada.",
                prazo.id_prazo,
            )
    return True


def processar_lembretes_prazo(sessao: Session, *, hoje: date | None = None) -> int:
    """Registra uma vez os lembretes diários do advogado responsável."""
    data_atual = hoje or _hoje_local()
    tamanho_lote = 250
    ultimo_id = 0
    criados = 0
    while True:
        linhas = sessao.execute(
            select(PrazoDB, UsuarioDB, ProcessoDB)
            .join(UsuarioDB, UsuarioDB.id_usuario == PrazoDB.id_usuario)
            .join(JuridicoDB, JuridicoDB.id_usuario == UsuarioDB.id_usuario)
            .join(ProcessoDB, ProcessoDB.id_processo == PrazoDB.id_processo)
            .join(
                PermissaoProcessoDB,
                (PermissaoProcessoDB.id_usuario == UsuarioDB.id_usuario)
                & (PermissaoProcessoDB.id_processo == PrazoDB.id_processo),
            )
            .where(
                PrazoDB.id_prazo > ultimo_id,
                PrazoDB.status == "pendente",
                UsuarioDB.ativo.is_(True),
                PermissaoProcessoDB.nivel_acesso.in_(("edicao", "total")),
                ~UsuarioDB.id_usuario.in_(select(AdministradorDB.id_usuario)),
                PrazoDB.data_vencimento <= data_atual + timedelta(days=7),
            )
            .order_by(PrazoDB.id_prazo)
            .limit(tamanho_lote)
        ).all()
        if not linhas:
            break

        for prazo, usuario, processo in linhas:
            dias = (prazo.data_vencimento - data_atual).days
            if dias in {7, 3, 1}:
                tipo = f"{dias}_dias"
                momento = f"vence em {dias} dia(s)"
            elif dias == 0:
                tipo = "vence_hoje"
                momento = "vence hoje"
            elif dias < 0:
                tipo = "atrasado"
                momento = f"está atrasado há {abs(dias)} dia(s)"
            else:
                continue
            if _registrar_lembrete(
                sessao,
                prazo=prazo,
                usuario=usuario,
                processo=processo,
                hoje=data_atual,
                tipo=tipo,
                texto_momento=momento,
            ):
                criados += 1
        ultimo_id = linhas[-1][0].id_prazo
        sessao.commit()
    return criados
