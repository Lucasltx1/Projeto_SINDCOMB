
from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PermissaoProcessoDB


def buscar_permissao_processo(
    sessao: Session,
    usuario_id: int,
    processo_id: int
) -> PermissaoProcessoDB | None:

    consulta = select(PermissaoProcessoDB).where(
        PermissaoProcessoDB.id_usuario == usuario_id,
        PermissaoProcessoDB.id_processo == processo_id
    )

    return sessao.scalar(consulta)




def verificar_permissao_processo(
    sessao: Session,
    usuario_id: int,
    processo_id: int,
    nivel_necessario: str = "leitura"
) -> bool:

    niveis = {
        "leitura": 1,
        "edicao": 2,
        "total": 3
    }

    if nivel_necessario not in niveis:
        raise ValueError("Nível de acesso inválido.")

    permissao = buscar_permissao_processo(
        sessao,
        usuario_id,
        processo_id
    )

    if permissao is None:
        return False

    nivel_usuario = niveis.get(permissao.nivel_acesso, 0)
    nivel_exigido = niveis[nivel_necessario]

    return nivel_usuario >= nivel_exigido
