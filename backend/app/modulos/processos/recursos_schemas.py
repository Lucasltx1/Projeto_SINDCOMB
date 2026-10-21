from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


StatusPeticao = Literal["rascunho", "em_revisao", "rejeitada", "aprovada", "protocolada"]
StatusPrazo = Literal["pendente", "concluido", "cancelado"]


class DocumentoSaida(BaseModel):
    id_documento: int
    id_processo: int
    id_usuario: int | None
    nome: str
    tipo: str | None
    data_upload: datetime
    tamanho: int | None
    hash_arquivo: str | None
    id_peticao: int | None

    model_config = ConfigDict(from_attributes=True)


class ComentarioProcessoEntrada(BaseModel):
    conteudo: str = Field(min_length=1, max_length=5000)


class ComentarioProcessoAtualizacao(BaseModel):
    conteudo: str = Field(min_length=1, max_length=5000)


class ComentarioProcessoSaida(BaseModel):
    id_comentario: int
    id_processo: int
    id_usuario: int | None
    autor: str | None
    conteudo: str
    criado_em: datetime
    editado_em: datetime | None = None
    excluido_em: datetime | None = None


class ModeloPeticaoEntrada(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    tipo: str = Field(min_length=2, max_length=100)
    conteudo: str = Field(min_length=1, max_length=200_000)


class ModeloPeticaoAtualizacao(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    tipo: str | None = Field(default=None, min_length=2, max_length=100)
    conteudo: str | None = Field(default=None, min_length=1, max_length=200_000)
    ativo: bool | None = None


class ModeloPeticaoSaida(BaseModel):
    id_modelo: int
    nome: str
    tipo: str
    conteudo: str
    ativo: bool
    criado_por: int | None
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class PeticaoCriacao(BaseModel):
    tipo: str | None = Field(default=None, min_length=2, max_length=100)
    descricao: str | None = Field(default=None, max_length=5_000)
    conteudo: str | None = Field(default=None, min_length=1, max_length=200_000)
    id_modelo: int | None = None

    @model_validator(mode="after")
    def exigir_conteudo_ou_modelo(self):
        if self.conteudo is None and self.id_modelo is None:
            raise ValueError("Informe o conteúdo da petição ou selecione um modelo.")
        if self.id_modelo is None and self.tipo is None:
            raise ValueError("Informe o tipo da petição.")
        return self


class PeticaoAtualizacao(BaseModel):
    tipo: str | None = Field(default=None, min_length=2, max_length=100)
    descricao: str | None = Field(default=None, max_length=5_000)
    conteudo: str | None = Field(default=None, min_length=1, max_length=200_000)


class PeticaoStatusEntrada(BaseModel):
    status: Literal["em_revisao", "rejeitada", "aprovada"]
    observacao: str | None = Field(default=None, max_length=2_000)


class PeticaoRevisorEntrada(BaseModel):
    id_usuario: int


class PeticaoRevisorSaida(BaseModel):
    id_peticao: int
    id_usuario: int
    nome: str
    oab: str
    atribuido_por: int | None
    atribuido_em: datetime


class PeticaoComentarioEntrada(BaseModel):
    id_versao: int
    conteudo: str = Field(min_length=1, max_length=5000)


class PeticaoComentarioAtualizacao(BaseModel):
    conteudo: str = Field(min_length=1, max_length=5000)


class PeticaoComentarioResolucao(BaseModel):
    resolvido: bool


class PeticaoComentarioSaida(BaseModel):
    id_comentario: int
    id_peticao: int
    id_versao: int
    id_usuario: int | None
    autor: str | None
    conteudo: str
    criado_em: datetime
    editado_em: datetime | None
    resolvido_em: datetime | None
    resolvido_por: int | None
    excluido_em: datetime | None


class PeticaoProtocoloEntrada(BaseModel):
    protocolado_em: datetime
    tribunal: str = Field(min_length=2, max_length=120)
    numero_protocolo: str | None = Field(default=None, max_length=200)
    id_documento_comprovante: int | None = None
    observacao: str | None = Field(default=None, max_length=2000)

    @field_validator("tribunal")
    @classmethod
    def normalizar_tribunal(cls, valor: str) -> str:
        normalizado = valor.strip()
        if not normalizado:
            raise ValueError("Informe o tribunal.")
        return normalizado

    @field_validator("numero_protocolo", "observacao")
    @classmethod
    def normalizar_campos_opcionais(cls, valor: str | None) -> str | None:
        normalizado = valor.strip() if valor is not None else None
        return normalizado or None

    @model_validator(mode="after")
    def exigir_identificador_ou_comprovante(self):
        if not self.numero_protocolo and self.id_documento_comprovante is None:
            raise ValueError("Informe o número do protocolo ou anexe o documento comprovante.")
        if self.protocolado_em.tzinfo is None:
            raise ValueError("A data do protocolo precisa incluir fuso horário.")
        return self


class PeticaoProtocoloSaida(BaseModel):
    id_protocolo: int
    id_peticao: int
    id_usuario: int | None
    id_documento_comprovante: int | None
    numero_protocolo: str | None
    tribunal: str
    protocolado_em: datetime
    observacao: str | None
    registrado_em: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificacaoInternaSaida(BaseModel):
    id_notificacao: int
    id_processo: int | None
    categoria: str
    titulo: str
    mensagem: str
    criado_em: datetime
    lida_em: datetime | None

    model_config = ConfigDict(from_attributes=True)


class NotificacoesListaSaida(BaseModel):
    itens: list[NotificacaoInternaSaida]
    total: int
    nao_lidas: int
    limite: int
    deslocamento: int


class SugestaoPrazoSaida(BaseModel):
    id_sugestao: int
    id_processo: int
    texto_fonte: str
    data_publicacao: datetime | None
    fonte: str
    fonte_url: str | None
    status: Literal["pendente", "confirmada", "descartada"]
    criado_em: datetime
    revisado_em: datetime | None
    revisado_por: int | None
    id_prazo: int | None

    model_config = ConfigDict(from_attributes=True)


class SugestaoPrazoConfirmacao(BaseModel):
    data_vencimento: date
    descricao: str | None = Field(default=None, max_length=5000)
    id_usuario_responsavel: int | None = None


class VersaoPeticaoSaida(BaseModel):
    id_versao: int
    id_peticao: int
    numero_versao: int
    conteudo: str
    id_usuario: int | None
    data_versao: datetime

    model_config = ConfigDict(from_attributes=True)


class PeticaoSaida(BaseModel):
    id_peticao: int
    id_processo: int
    id_usuario: int | None
    tipo: str
    descricao: str | None
    data_peticao: datetime
    status: StatusPeticao
    versao_atual: int
    conteudo: str


class PrazoCriacao(BaseModel):
    descricao: str = Field(min_length=1, max_length=5_000)
    data_inicio: date | None = None
    data_vencimento: date
    id_usuario_responsavel: int | None = None

    @model_validator(mode="after")
    def validar_datas(self):
        if self.data_inicio is not None and self.data_inicio > self.data_vencimento:
            raise ValueError("A data de início não pode ser posterior ao vencimento.")
        return self


class PrazoAtualizacao(BaseModel):
    descricao: str | None = Field(default=None, min_length=1, max_length=5_000)
    data_inicio: date | None = None
    data_vencimento: date | None = None
    status: StatusPrazo | None = None
    id_usuario_responsavel: int | None = None


class PrazoSaida(BaseModel):
    id_prazo: int
    id_processo: int
    id_usuario: int | None
    descricao: str
    data_inicio: date | None
    data_vencimento: date
    status: StatusPrazo
    atrasado: bool
    dias_restantes: int


class ResponsavelPrazoSaida(BaseModel):
    id_usuario: int
    nome: str
    oab: str


class SincronizacaoSaida(BaseModel):
    id_sincronizacao: int
    id_processo: int | None
    data_hora: datetime
    status: str
    descricao: str | None
    quantidade_atualizacoes: int

    model_config = ConfigDict(from_attributes=True)
