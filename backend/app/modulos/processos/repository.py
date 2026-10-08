from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import ParteMonitorada, ProcessoDB
from .schemas import ProcessoRegistro


def _para_schema(row: ProcessoDB) -> ProcessoRegistro:
    return ProcessoRegistro.model_validate(
        {
            "id": row.id,
            "dados": row.dados_json,
            "triagem": row.triagem_json,
            "status": row.status,
            "criado_por": row.criado_por,
            "criado_em": row.criado_em,
            "movimentacoes": row.movimentacoes_json or [],
            "historico_status": row.historico_status_json or [],
        }
    )


def listar(sessao: Session, relevancia: str | None = None) -> list[ProcessoRegistro]:
    linhas = sessao.scalars(select(ProcessoDB).order_by(ProcessoDB.criado_em.desc())).all()
    registros = [_para_schema(linha) for linha in linhas]
    if relevancia:
        registros = [registro for registro in registros if registro.triagem.relevancia == relevancia]
    return registros


def obter(sessao: Session, processo_id: str) -> ProcessoRegistro | None:
    linha = sessao.get(ProcessoDB, processo_id)
    return _para_schema(linha) if linha else None


def obter_por_numero(sessao: Session, numero: str, tribunal: str) -> ProcessoRegistro | None:
    linha = sessao.scalar(
        select(ProcessoDB).where(ProcessoDB.numero == numero, ProcessoDB.tribunal == tribunal)
    )
    return _para_schema(linha) if linha else None


def adicionar(sessao: Session, processo: ProcessoRegistro) -> ProcessoRegistro:
    linha = ProcessoDB(
        id=processo.id,
        numero=processo.dados.numero,
        tribunal=processo.dados.tribunal,
        status=processo.status,
        dados_json=processo.dados.model_dump(mode="json"),
        triagem_json=processo.triagem.model_dump(mode="json"),
        movimentacoes_json=[item.model_dump(mode="json") for item in processo.movimentacoes],
        historico_status_json=[item.model_dump(mode="json") for item in processo.historico_status],
        criado_por=processo.criado_por,
        criado_em=processo.criado_em,
    )
    sessao.add(linha)
    sessao.commit()
    return processo


def salvar(sessao: Session, processo: ProcessoRegistro) -> ProcessoRegistro:
    linha = sessao.get(ProcessoDB, processo.id)
    if linha is None:
        return adicionar(sessao, processo)
    linha.status = processo.status
    linha.dados_json = processo.dados.model_dump(mode="json")
    linha.triagem_json = processo.triagem.model_dump(mode="json")
    linha.movimentacoes_json = [item.model_dump(mode="json") for item in processo.movimentacoes]
    linha.historico_status_json = [item.model_dump(mode="json") for item in processo.historico_status]
    sessao.commit()
    return processo


def listar_partes(sessao: Session, somente_ativas: bool = False) -> list[ParteMonitorada]:
    consulta = select(ParteMonitorada).order_by(ParteMonitorada.nome)
    if somente_ativas:
        consulta = consulta.where(ParteMonitorada.ativa.is_(True))
    return list(sessao.scalars(consulta).all())


def obter_parte(sessao: Session, parte_id: str) -> ParteMonitorada | None:
    return sessao.get(ParteMonitorada, parte_id)


def adicionar_parte(sessao: Session, parte: ParteMonitorada) -> ParteMonitorada:
    sessao.add(parte)
    sessao.commit()
    sessao.refresh(parte)
    return parte
