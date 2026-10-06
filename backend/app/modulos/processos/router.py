from fastapi import APIRouter, HTTPException
from openai import APIConnectionError, APIError
from pydantic import BaseModel, Field, ValidationError

from .status_service import interpretar_movimentacao

router = APIRouter(prefix="/api/v1/processos", tags=["Processos"])


class PedidoInterpretacao(BaseModel):
    texto_movimentacao: str = Field(min_length=1, max_length=20000)


@router.post("/interpretar-movimentacao")
async def interpretar(pedido: PedidoInterpretacao) -> dict[str, str | bool]:
    """Interpreta uma movimentação através do Qwen local."""
    try:
        resultado = await interpretar_movimentacao(pedido.texto_movimentacao)
    except APIConnectionError as erro:
        raise HTTPException(
            status_code=503,
            detail="O serviço local de ML está indisponível.",
        ) from erro
    except (APIError, ValidationError, ValueError) as erro:
        raise HTTPException(
            status_code=502,
            detail="Não foi possível obter uma interpretação válida da movimentação.",
        ) from erro
        return resultado.model_dump()
