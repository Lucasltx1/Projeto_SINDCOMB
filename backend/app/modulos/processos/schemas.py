from datetime import datetime, timezone
import re
from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, HttpUrl, field_validator

from .numero_cnj import normalizar_numero_cnj

Relevancia = Literal["interesse_direto", "revisar", "sem_interesse"]
StatusProcesso = Literal[
    "novo",
    "em_acompanhamento",
    "aguardando_prazo",
    "suspenso",
    "encerrado",
]
TipoParte = Literal["sindicato", "advogado", "associado"]


class MovimentacaoPublica(BaseModel):
    texto: str = Field(min_length=1, max_length=20000)
    data_fonte: datetime | None = None
    fonte_url: HttpUrl | None = None
    fonte_dados: Literal["datajud", "djen"] | None = None


class ProcessoCandidato(BaseModel):
    numero: str = Field(min_length=1, max_length=50)
    tribunal: str = Field(default="Tribunal não identificado", min_length=1, max_length=120)
    tribunal_alias: str | None = Field(default=None, pattern=r"^[a-zA-Z0-9-]{2,20}$")
    classe: str | None = Field(default=None, max_length=100)
    assunto: str = Field(default="Assunto não informado", min_length=1, max_length=2000)
    partes: list[str] = Field(default_factory=list, max_length=100)
    advogados: list[str] = Field(default_factory=list, max_length=100)
    associados_mencionados: list[str] = Field(default_factory=list, max_length=100)
    ultima_movimentacao: str | None = Field(default=None, max_length=20000)
    movimentacoes_publicas: list[MovimentacaoPublica] = Field(
        default_factory=list, max_length=100, exclude=True
    )
    fonte_url: HttpUrl | None = None
    origem_dados: Literal["datajud", "djen"] | None = None
    consultado_em: datetime | None = None
    data_ultima_verificacao_fonte: datetime | None = None

    @field_validator("numero")
    @classmethod
    def formatar_numero_cnj(cls, valor: str) -> str:
        return normalizar_numero_cnj(valor)


class ResultadoTriagem(BaseModel):
    relevancia: Relevancia
    justificativa: str = Field(min_length=1, max_length=1200)
    evidencias: list[str] = Field(default_factory=list, max_length=10)
    confianca: float = Field(ge=0, le=1)


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
    fonte_dados: Literal["datajud", "djen", "manual"] | None = None
    data_fonte: datetime | None = None
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
    arquivado: bool = False
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


class TriagemSolicitacaoSaida(BaseModel):
    mensagem: str


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _normalizar_email(valor: str) -> str:
    email = valor.strip().lower()
    if len(email) > 255 or not _EMAIL_RE.fullmatch(email):
        raise ValueError("Informe um endereço de e-mail válido.")
    return email


class LoginEntrada(BaseModel):
    usuario: str = Field(
        min_length=3,
        max_length=255,
        validation_alias=AliasChoices("usuario", "email"),
    )
    senha: str = Field(min_length=1, max_length=128)

    @field_validator("usuario")
    @classmethod
    def validar_usuario(cls, valor: str) -> str:
        valor = valor.strip()
        if "@" in valor:
            return _normalizar_email(valor)
        if not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}", valor):
            raise ValueError("Informe um e-mail válido ou um nome de usuário válido.")
        return valor.casefold()


class AlteracaoSenhaEntrada(BaseModel):
    senha_atual: str = Field(min_length=1, max_length=128)
    nova_senha: str = Field(min_length=12, max_length=128)


class SolicitarRecuperacaoSenhaEntrada(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    model_config = ConfigDict(extra="forbid")

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor: str) -> str:
        return _normalizar_email(valor)


class RedefinirSenhaEntrada(BaseModel):
    token: str = Field(min_length=32, max_length=200)
    nova_senha: str = Field(min_length=12, max_length=128)
    model_config = ConfigDict(extra="forbid")


class VerificacaoEmailEntrada(BaseModel):
    token: str = Field(min_length=32, max_length=200)


class UsuarioPerfil(BaseModel):
    id: str
    nome: str
    username: str | None = None
    email: str | None = None
    papel: Literal["administrador", "advogado", "visualizador"]
    primeiro_acesso: bool


class LoginSaida(BaseModel):
    csrf_token: str
    usuario: UsuarioPerfil
    alterar_senha_no_primeiro_acesso: bool


class CsrfTokenSaida(BaseModel):
    csrf_token: str


class AuditoriaEventoSaida(BaseModel):
    id: int
    usuario_id: int | None = None
    processo_id: int | None = None
    operacao: str
    descricao: str | None = None
    ocorrido_em: datetime
    resultado: str
    dados: dict[str, object] = Field(default_factory=dict)


class AuditoriaListaSaida(BaseModel):
    itens: list[AuditoriaEventoSaida]
    total: int
    limite: int
    deslocamento: int


class AdvogadoCriacao(BaseModel):
    nome: str = Field(min_length=3, max_length=150)
    email: str = Field(min_length=3, max_length=255)
    oab: str = Field(min_length=3, max_length=30)
    model_config = ConfigDict(extra="forbid")

    @field_validator("nome", "oab")
    @classmethod
    def limpar_texto(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O campo não pode ficar vazio.")
        return valor

    @field_validator("email")
    @classmethod
    def validar_email(cls, valor: str) -> str:
        return _normalizar_email(valor)


class AdvogadoAtualizacao(BaseModel):
    nome: str | None = Field(default=None, min_length=3, max_length=150)
    oab: str | None = Field(default=None, min_length=3, max_length=30)
    ativo: bool | None = None
    model_config = ConfigDict(extra="forbid")

    @field_validator("nome", "oab")
    @classmethod
    def limpar_texto_opcional(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip()
        if not valor:
            raise ValueError("O campo não pode ficar vazio.")
        return valor


class AdvogadoSaida(BaseModel):
    id: str
    nome: str
    email: str
    oab: str
    ativo: bool
    email_verificado: bool
    primeiro_acesso: bool


class AssociadoCriacao(BaseModel):
    nome: str = Field(min_length=2, max_length=150)
    cpf: str | None = Field(default=None, max_length=14)
    email: str | None = Field(default=None, max_length=255)
    telefone: str | None = Field(default=None, max_length=25)
    model_config = ConfigDict(extra="forbid")

    @field_validator("nome")
    @classmethod
    def validar_nome(cls, valor: str) -> str:
        valor = valor.strip()
        if not valor:
            raise ValueError("O nome não pode ficar vazio.")
        return valor

    @field_validator("email")
    @classmethod
    def validar_email_opcional(cls, valor: str | None) -> str | None:
        return _normalizar_email(valor) if valor else None

    @field_validator("cpf", "telefone")
    @classmethod
    def limpar_opcionais(cls, valor: str | None) -> str | None:
        return valor.strip() or None if valor is not None else None


class AssociadoAtualizacao(BaseModel):
    nome: str | None = Field(default=None, min_length=2, max_length=150)
    cpf: str | None = Field(default=None, max_length=14)
    email: str | None = Field(default=None, max_length=255)
    telefone: str | None = Field(default=None, max_length=25)
    model_config = ConfigDict(extra="forbid")

    @field_validator("nome")
    @classmethod
    def limpar_nome_opcional(cls, valor: str | None) -> str | None:
        if valor is None:
            return None
        valor = valor.strip()
        if not valor:
            raise ValueError("O nome não pode ficar vazio.")
        return valor

    @field_validator("email")
    @classmethod
    def validar_email_opcional(cls, valor: str | None) -> str | None:
        return _normalizar_email(valor) if valor else None


class AssociadoSaida(BaseModel):
    id: int
    nome: str
    cpf: str | None
    email: str | None
    telefone: str | None


class AdvogadoCriadoSaida(AdvogadoSaida):
    email_verificacao_enviado: bool
