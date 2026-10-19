from datetime import date
from pydantic import BaseModel, Field, model_validator
from typing import Literal

class PrazoCriar(BaseModel):
    
    id_processo: int
    descricao: str = Field(min_length=1)
    data_inicio: date | None = None
    data_vencimento: date
    @model_validator(mode="after")
    def validar_datas(self):
        if self.data_inicio is not None:
            if self.data_inicio > self.data_vencimento:
                raise ValueError(
                    "A data de início não pode ser posterior à data de vencimento."
                )

        return self

class PrazoResposta(BaseModel):
    """Representa os dados de um prazo retornados pela API."""

    id_prazo: int
    id_processo: int
    id_usuario: int
    descricao: str
    data_inicio: date | None
    data_vencimento: date
    status: Literal["pendente", "concluido"]

    model_config = {"from_attributes": True}

class PrazoAtualizar(BaseModel):
    """Valida os dados para atualizar um prazo existente."""

    descricao: str | None = Field(default=None, min_length=1)
    data_inicio: date | None = None
    data_vencimento: date | None = None
    status: Literal["pendente", "concluido"] | None = None
