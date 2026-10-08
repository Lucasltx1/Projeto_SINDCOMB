from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

Relevancia = Literal["interesse_direto", "revisar", "sem_interesse"]
StatusProcesso = Literal[
    "novo",
    "em_acompanhamento",
    "aguardando_prazo",
    "suspenso",
    "encerrado",
]
TipoParte = Literal["sindicato", "advogado", "associado"]


class ProcessoCandidato(BaseModel):
    numero: str = Field(min_length=1, max_length=80)
    tribunal: str = Field(min_length=1, max_length=120)
    tribunal_alias: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9-]{2,20}$")
    classe: str | None = Field(default=None, max_length=160)
    assunto: str = Field(min_length=1, max_length=2000)
    partes: list[str] = Field(default_factory=list, max_length=100)
    advogados: list[str] = Field(default_factory=list, max_length=100)
    associados_mencionados: list[str] = Field(default_factory=list, max_length=100)
    ultima_movimentacao: str | None = Field(default=None, max_length=20000)
    fonte_url: HttpUrl | None = None


class ResultadoTriagem(BaseModel):
    relevancia: Relevancia
    justificativa: str = Field(min_length=1, max_length=1200)
    evidencias: list[str] = Field(default_factory=list, max_length=10)
    confianca: float = Field(ge=0, le=1)


class ParteMonitoradaEntrada(BaseModel):
    nome: str = Field(min_length=3, max_length=300)
    tipo: TipoParte
    # Aliases CNJ, por exemplo: tjrj, stj, tst ou trf2.
    tribunais: list[str] = Field(min_length=1, max_length=5)

    @field_validator("tribunais")
    @classmethod
    def validar_tribunais(cls, valores: list[str]) -> list[str]:
        import re

        normalizados = [valor.strip().lower() for valor in valores]
        if any(not re.fullmatch(r"[a-z0-9-]{2,20}", valor) for valor in normalizados):
            raise ValueError("Use aliases de tribunal do DataJud, como tjrj ou trf2.")
        return list(dict.fromkeys(normalizados))


class ParteMonitoradaSaida(ParteMonitoradaEntrada):
    id: str
    ativa: bool
    criada_por: str
    criada_em: datetime


class MovimentacaoEntrada(BaseModel):
    texto: str = Field(min_length=1, max_length=20000)
    fonte_url: HttpUrl | None = None


class MovimentacaoRegistro(BaseModel):
    texto: str
    resumo: str
    categoria: Literal[
        "andamento", "intimacao", "despacho", "sentenca", "peticao", "prazo", "outro"
    ]
    requer_atencao: bool
    fonte_url: HttpUrl | None = None
    registrada_por: str
    registrada_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class HistoricoStatus(BaseModel):
    de: StatusProcesso | None
    para: StatusProcesso
    alterado_por: str
    em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    observacao: str | None = Field(default=None, max_length=1000)


class ProcessoRegistro(BaseModel):
    id: str
    dados: ProcessoCandidato
    triagem: ResultadoTriagem
    status: StatusProcesso = "novo"
    criado_por: str
    criado_em: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    movimentacoes: list[MovimentacaoRegistro] = Field(default_factory=list)
    historico_status: list[HistoricoStatus] = Field(default_factory=list)


class AlteracaoStatus(BaseModel):
    status: StatusProcesso
    observacao: str | None = Field(default=None, max_length=1000)


class ResultadoSincronizacao(BaseModel):
    processos_consultados: int
    processos_com_movimentacao_nova: int
    falhas: list[str] = Field(default_factory=list)