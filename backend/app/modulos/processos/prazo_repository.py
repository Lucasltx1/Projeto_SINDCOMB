from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modulos.processos.models import PrazoDB
from app.modulos.processos.prazo_schemas import PrazoCriar, PrazoAtualizar

def buscar_prazo(sessao: Session, id_prazo: int) -> PrazoDB | None:

    return sessao.get(PrazoDB, id_prazo)

def listar_prazos(sessao: Session, id_processo: int) -> list[PrazoDB]:

    consulta = (
        select(PrazoDB)
        .where(PrazoDB.id_processo == id_processo)
        .order_by(PrazoDB.data_vencimento)
    )

    return list(sessao.scalars(consulta).all())


def criar_prazo(
    sessao: Session,
    dados: PrazoCriar,
    id_usuario: int
) -> PrazoDB:
    """Cadastra um novo prazo processual."""

    novo_prazo = PrazoDB(
        id_processo=dados.id_processo,
        id_usuario=id_usuario,
        descricao=dados.descricao,
        data_inicio=dados.data_inicio,
        data_vencimento=dados.data_vencimento,
        status="pendente"
    )

    sessao.add(novo_prazo)
    sessao.flush()

    return novo_prazo

def atualizar_prazo(
    sessao: Session,
    prazo: PrazoDB,
    dados: PrazoAtualizar
) -> PrazoDB:
    """Atualiza as informações de um prazo existente."""

    alteracoes = dados.model_dump(exclude_unset=True)

    # Impede que campos obrigatórios sejam apagados.
    for campo in ("descricao", "data_vencimento", "status"):
        if campo in alteracoes and alteracoes[campo] is None:
            raise ValueError(
                f"O campo '{campo}' não pode ser vazio."
            )

    # Considera as datas existentes e as novas.
    nova_data_inicio = alteracoes.get(
        "data_inicio", prazo.data_inicio
    )

    nova_data_vencimento = alteracoes.get(
        "data_vencimento", prazo.data_vencimento
    )

    # Verifica a ordem das datas.
    if (
        nova_data_inicio is not None
        and nova_data_inicio > nova_data_vencimento
    ):
        raise ValueError(
            "A data de início não pode ser posterior à data de vencimento."
        )

    # Aplica as alterações somente após validar.
    for campo, valor in alteracoes.items():
        setattr(prazo, campo, valor)

    sessao.flush()

    return prazo

def excluir_prazo(sessao: Session, prazo: PrazoDB) -> None:

    sessao.delete(prazo)
    sessao.flush()
