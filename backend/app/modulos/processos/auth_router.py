from datetime import datetime, timedelta, timezone
import hashlib
import html
import logging
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .auth import (
    UsuarioAtual,
    criar_access_token,
    exigir_administrador,
    obter_usuario_atual,
)
from .email_service import enviar_verificacao_email
from .models import (
    AdministradorDB,
    AssociadoDB,
    AuditoriaDB,
    JuridicoDB,
    TokenVerificacaoDB,
    UsuarioDB,
)
from .repository import (
    excluir_vinculos_advogado,
    excluir_vinculos_associado,
    limpar_referencias_pessoa,
)
from .schemas import (
    AdvogadoAtualizacao,
    AdvogadoCriacao,
    AdvogadoCriadoSaida,
    AdvogadoSaida,
    AssociadoAtualizacao,
    AssociadoCriacao,
    AssociadoSaida,
    AlteracaoSenhaEntrada,
    LoginEntrada,
    LoginSaida,
    UsuarioPerfil,
    VerificacaoEmailEntrada,
)
from .security import hash_password, verificar_password

logger = logging.getLogger(__name__)
auth_router = APIRouter(prefix="/api/v1/auth", tags=["Autenticação"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["Administração"])


def _papel(sessao: Session, usuario: UsuarioDB) -> str:
    if sessao.get(AdministradorDB, usuario.id_usuario) is not None:
        return "administrador"
    if sessao.get(JuridicoDB, usuario.id_usuario) is not None:
        return "advogado"
    return "visualizador"


def _perfil(sessao: Session, usuario: UsuarioDB) -> UsuarioPerfil:
    return UsuarioPerfil(
        id=str(usuario.id_usuario),
        nome=usuario.nome,
        username=usuario.username,
        email=usuario.email,
        papel=_papel(sessao, usuario),
        primeiro_acesso=usuario.primeiro_acesso,
    )


def _novo_token_verificacao(sessao: Session, usuario_id: int) -> str:
    sessao.query(TokenVerificacaoDB).filter(
        TokenVerificacaoDB.id_usuario == usuario_id,
        TokenVerificacaoDB.tipo == "email",
    ).delete(synchronize_session=False)
    token = secrets.token_urlsafe(36)
    horas = max(1, int(os.getenv("SINDCOMB_EMAIL_VERIFICATION_HOURS", "24")))
    sessao.add(
        TokenVerificacaoDB(
            id_usuario=usuario_id,
            tipo="email",
            token_hash=hashlib.sha256(token.encode("utf-8")).hexdigest(),
            expira_em=datetime.now(timezone.utc) + timedelta(hours=horas),
        )
    )
    sessao.commit()
    return token


def _advogado_saida(usuario: UsuarioDB, juridico: JuridicoDB) -> AdvogadoSaida:
    return AdvogadoSaida(
        id=str(usuario.id_usuario),
        nome=usuario.nome,
        email=usuario.email,
        oab=juridico.oab,
        ativo=usuario.ativo,
        email_verificado=usuario.email_verificado,
        primeiro_acesso=usuario.primeiro_acesso,
    )


def _associado_saida(associado: AssociadoDB) -> AssociadoSaida:
    return AssociadoSaida(
        id=associado.id_associado,
        nome=associado.nome,
        cpf=associado.cpf,
        email=associado.email,
        telefone=associado.telefone,
    )


@auth_router.post("/login", response_model=LoginSaida, response_model_exclude_none=True)
def login(entrada: LoginEntrada, sessao: Session = Depends(obter_sessao)) -> LoginSaida:
    if "@" in entrada.usuario:
        usuario = sessao.scalar(
            select(UsuarioDB).where(func.lower(UsuarioDB.email) == entrada.usuario)
        )
        if usuario is not None and sessao.get(AdministradorDB, usuario.id_usuario) is not None:
            usuario = None
    else:
        usuario = sessao.scalar(
            select(UsuarioDB).where(func.lower(UsuarioDB.username) == entrada.usuario)
        )
    if usuario is None or not usuario.ativo or not verificar_password(entrada.senha, usuario.senha):
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")
    administrador = sessao.get(AdministradorDB, usuario.id_usuario) is not None
    if not administrador and not usuario.email_verificado:
        raise HTTPException(status_code=403, detail="Confirme o e-mail antes de entrar.")

    papel = _papel(sessao, usuario)
    return LoginSaida(
        access_token=criar_access_token(usuario, papel),
        usuario=_perfil(sessao, usuario),
        alterar_senha_no_primeiro_acesso=usuario.primeiro_acesso,
    )


@auth_router.get("/me", response_model=UsuarioPerfil, response_model_exclude_none=True)
def meu_perfil(
    usuario: UsuarioAtual = Depends(obter_usuario_atual),
) -> UsuarioPerfil:
    return UsuarioPerfil(**usuario.model_dump())


@auth_router.get("/verificar-email", response_class=HTMLResponse)
def pagina_verificacao_email(token: str = Query(min_length=32, max_length=200)) -> HTMLResponse:
    token_seguro = html.escape(token)
    pagina = f"""<!doctype html>
<html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Confirmar e-mail — SINDCOMB</title>
<body style="font-family:system-ui,sans-serif;max-width:38rem;margin:4rem auto;padding:0 1rem;color:#172033">
<h1>Confirmação de e-mail</h1>
<p>Clique no botão para confirmar o e-mail da sua conta SINDCOMB.</p>
<button id="confirmar" style="padding:.75rem 1rem;cursor:pointer">Confirmar e-mail</button>
<p id="resultado" role="status"></p><span id="token" hidden>{token_seguro}</span>
<script>
document.getElementById('confirmar').addEventListener('click', async () => {{
  const destino = document.getElementById('resultado');
  destino.textContent = 'Confirmando…';
  try {{
    const resposta = await fetch('/api/v1/auth/verificar-email', {{
      method: 'POST', headers: {{'Content-Type': 'application/json'}},
      body: JSON.stringify({{token: document.getElementById('token').textContent}})
    }});
    const dados = await resposta.json();
    destino.textContent = resposta.ok ? dados.mensagem : (dados.detail || 'Não foi possível confirmar.');
  }} catch {{ destino.textContent = 'Não foi possível conectar ao sistema.'; }}
}});
</script></body></html>"""
    return HTMLResponse(pagina, headers={"Cache-Control": "no-store"})


@auth_router.post("/verificar-email")
def verificar_email(
    entrada: VerificacaoEmailEntrada,
    sessao: Session = Depends(obter_sessao),
) -> dict[str, str]:
    hash_token = hashlib.sha256(entrada.token.encode("utf-8")).hexdigest()
    token = sessao.scalar(
        select(TokenVerificacaoDB).where(
            TokenVerificacaoDB.token_hash == hash_token,
            TokenVerificacaoDB.tipo == "email",
        )
    )
    agora = datetime.now(timezone.utc)
    if token is None or token.expira_em <= agora:
        if token is not None:
            sessao.delete(token)
            sessao.commit()
        raise HTTPException(status_code=400, detail="Link inválido ou expirado. Solicite novo envio ao administrador.")

    usuario = sessao.get(UsuarioDB, token.id_usuario)
    if usuario is None or not usuario.ativo:
        sessao.delete(token)
        sessao.commit()
        raise HTTPException(status_code=400, detail="A conta não está disponível.")
    if sessao.get(AdministradorDB, usuario.id_usuario) is not None:
        sessao.delete(token)
        sessao.commit()
        raise HTTPException(status_code=400, detail="A conta administrativa não usa verificação de e-mail.")
    usuario.email_verificado = True
    sessao.delete(token)
    sessao.commit()
    return {"mensagem": "E-mail confirmado. Agora você pode entrar com seu e-mail e a senha inicial."}


@auth_router.post("/alterar-senha", response_model=LoginSaida)
def alterar_senha(
    entrada: AlteracaoSenhaEntrada,
    usuario_atual: UsuarioAtual = Depends(obter_usuario_atual),
    sessao: Session = Depends(obter_sessao),
) -> LoginSaida:
    usuario = sessao.get(UsuarioDB, int(usuario_atual.id))
    if usuario is not None and sessao.get(AdministradorDB, usuario.id_usuario) is not None:
        raise HTTPException(
            status_code=403,
            detail="A senha da conta administrativa é fixa e não pode ser alterada pela aplicação.",
        )
    if usuario is None or not verificar_password(entrada.senha_atual, usuario.senha):
        raise HTTPException(status_code=400, detail="A senha atual está incorreta.")
    if entrada.senha_atual == entrada.nova_senha:
        raise HTTPException(status_code=400, detail="A nova senha deve ser diferente da atual.")
    usuario.senha = hash_password(entrada.nova_senha)
    usuario.primeiro_acesso = False
    sessao.commit()
    papel = _papel(sessao, usuario)
    return LoginSaida(
        access_token=criar_access_token(usuario, papel),
        usuario=_perfil(sessao, usuario),
        alterar_senha_no_primeiro_acesso=False,
    )


@admin_router.get("/advogados", response_model=list[AdvogadoSaida])
def listar_advogados(
    _admin: UsuarioAtual = Depends(exigir_administrador),
    sessao: Session = Depends(obter_sessao),
) -> list[AdvogadoSaida]:
    pares = sessao.execute(
        select(UsuarioDB, JuridicoDB)
        .join(JuridicoDB, JuridicoDB.id_usuario == UsuarioDB.id_usuario)
        .order_by(UsuarioDB.nome)
    ).all()
    return [_advogado_saida(usuario, juridico) for usuario, juridico in pares]


@admin_router.post("/advogados", response_model=AdvogadoCriadoSaida, status_code=status.HTTP_201_CREATED)
def criar_advogado(
    entrada: AdvogadoCriacao,
    _admin: UsuarioAtual = Depends(exigir_administrador),
    sessao: Session = Depends(obter_sessao),
) -> AdvogadoCriadoSaida:
    senha_inicial = os.getenv("SINDCOMB_SENHA_INICIAL", "")
    if len(senha_inicial) < 12:
        raise HTTPException(
            status_code=503,
            detail="Configure SINDCOMB_SENHA_INICIAL com pelo menos 12 caracteres antes de cadastrar advogados.",
        )
    duplicado = sessao.scalar(
        select(UsuarioDB).where(func.lower(UsuarioDB.email) == entrada.email)
    )
    if duplicado:
        raise HTTPException(status_code=409, detail="Já existe uma conta com esse e-mail.")
    oab_existente = sessao.scalar(select(JuridicoDB).where(func.lower(JuridicoDB.oab) == entrada.oab.lower()))
    if oab_existente:
        raise HTTPException(status_code=409, detail="Já existe um advogado cadastrado com essa OAB.")

    usuario = UsuarioDB(
        nome=entrada.nome,
        email=entrada.email,
        senha=hash_password(senha_inicial),
        primeiro_acesso=True,
        ativo=True,
        email_verificado=False,
    )
    sessao.add(usuario)
    try:
        sessao.flush()
        juridico = JuridicoDB(id_usuario=usuario.id_usuario, oab=entrada.oab)
        sessao.add(juridico)
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        raise HTTPException(status_code=409, detail="E-mail ou OAB já cadastrado.") from erro

    token = _novo_token_verificacao(sessao, usuario.id_usuario)
    email_enviado = enviar_verificacao_email(usuario.email, usuario.nome, token)
    return AdvogadoCriadoSaida(
        **_advogado_saida(usuario, juridico).model_dump(),
        email_verificacao_enviado=email_enviado,
    )


@admin_router.patch("/advogados/{usuario_id}", response_model=AdvogadoSaida)
def atualizar_advogado(
    usuario_id: int,
    entrada: AdvogadoAtualizacao,
    _admin: UsuarioAtual = Depends(exigir_administrador),
    sessao: Session = Depends(obter_sessao),
) -> AdvogadoSaida:
    usuario = sessao.get(UsuarioDB, usuario_id)
    juridico = sessao.get(JuridicoDB, usuario_id)
    if usuario is None or juridico is None:
        raise HTTPException(status_code=404, detail="Advogado não encontrado.")

    alteracoes = entrada.model_dump(exclude_unset=True)
    if "oab" in alteracoes and alteracoes["oab"] is not None:
        existe = sessao.scalar(
            select(JuridicoDB).where(
                func.lower(JuridicoDB.oab) == alteracoes["oab"].lower(),
                JuridicoDB.id_usuario != usuario_id,
            )
        )
        if existe:
            raise HTTPException(status_code=409, detail="A OAB informada já está cadastrada.")
    if "nome" in alteracoes and alteracoes["nome"] is not None:
        usuario.nome = alteracoes["nome"]
    if "oab" in alteracoes and alteracoes["oab"] is not None:
        juridico.oab = alteracoes["oab"]
    if "ativo" in alteracoes and alteracoes["ativo"] is not None:
        usuario.ativo = alteracoes["ativo"]
    sessao.commit()
    return _advogado_saida(usuario, juridico)


@admin_router.delete("/advogados/{usuario_id}")
def excluir_advogado(
    usuario_id: int,
    admin: UsuarioAtual = Depends(exigir_administrador),
    sessao: Session = Depends(obter_sessao),
) -> dict[str, str]:
    usuario = sessao.get(UsuarioDB, usuario_id)
    juridico = sessao.get(JuridicoDB, usuario_id)
    if usuario is None or juridico is None:
        raise HTTPException(status_code=404, detail="Advogado não encontrado.")
    if sessao.get(AdministradorDB, usuario_id) is not None:
        raise HTTPException(
            status_code=409,
            detail="Esta conta também é administradora; remova primeiro o vínculo de administrador.",
        )

    limpar_referencias_pessoa(
        sessao,
        [usuario.nome, usuario.email, juridico.oab],
        id_usuario=usuario_id,
    )
    excluir_vinculos_advogado(sessao, usuario_id)
    sessao.add(
        AuditoriaDB(
            id_usuario=int(admin.id),
            tipo_operacao="exclusao_advogado",
            descricao="Cadastro de advogado excluído; referências e vínculos associados foram removidos.",
            data_hora=datetime.now(timezone.utc),
            resultado="sucesso",
            dados_json={},
        )
    )
    sessao.delete(juridico)
    sessao.delete(usuario)
    try:
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        raise HTTPException(status_code=409, detail="Não foi possível excluir este advogado.") from erro
    return {"mensagem": "Cadastro do advogado excluído com sucesso."}


@admin_router.post("/advogados/{usuario_id}/reenviar-verificacao")
def reenviar_verificacao_advogado(
    usuario_id: int,
    _admin: UsuarioAtual = Depends(exigir_administrador),
    sessao: Session = Depends(obter_sessao),
) -> dict[str, bool]:
    usuario = sessao.get(UsuarioDB, usuario_id)
    if usuario is None or sessao.get(JuridicoDB, usuario_id) is None:
        raise HTTPException(status_code=404, detail="Advogado não encontrado.")
    if usuario.email_verificado:
        raise HTTPException(status_code=409, detail="O e-mail deste advogado já foi confirmado.")
    token = _novo_token_verificacao(sessao, usuario.id_usuario)
    return {"email_verificacao_enviado": enviar_verificacao_email(usuario.email, usuario.nome, token)}


@admin_router.get("/associados", response_model=list[AssociadoSaida])
def listar_associados(
    _admin: UsuarioAtual = Depends(exigir_administrador),
    sessao: Session = Depends(obter_sessao),
) -> list[AssociadoSaida]:
    associados = sessao.scalars(select(AssociadoDB).order_by(AssociadoDB.nome)).all()
    return [_associado_saida(associado) for associado in associados]


@admin_router.post("/associados", response_model=AssociadoSaida, status_code=status.HTTP_201_CREATED)
def criar_associado(
    entrada: AssociadoCriacao,
    _admin: UsuarioAtual = Depends(exigir_administrador),
    sessao: Session = Depends(obter_sessao),
) -> AssociadoSaida:
    associado = AssociadoDB(**entrada.model_dump())
    sessao.add(associado)
    try:
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        raise HTTPException(status_code=409, detail="CPF já cadastrado.") from erro
    sessao.refresh(associado)
    return _associado_saida(associado)


@admin_router.patch("/associados/{associado_id}", response_model=AssociadoSaida)
def atualizar_associado(
    associado_id: int,
    entrada: AssociadoAtualizacao,
    _admin: UsuarioAtual = Depends(exigir_administrador),
    sessao: Session = Depends(obter_sessao),
) -> AssociadoSaida:
    associado = sessao.get(AssociadoDB, associado_id)
    if associado is None:
        raise HTTPException(status_code=404, detail="Associado não encontrado.")
    for campo, valor in entrada.model_dump(exclude_unset=True).items():
        setattr(associado, campo, valor)
    try:
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        raise HTTPException(status_code=409, detail="CPF já cadastrado.") from erro
    return _associado_saida(associado)


@admin_router.delete("/associados/{associado_id}")
def excluir_associado(
    associado_id: int,
    admin: UsuarioAtual = Depends(exigir_administrador),
    sessao: Session = Depends(obter_sessao),
) -> dict[str, str]:
    associado = sessao.get(AssociadoDB, associado_id)
    if associado is None:
        raise HTTPException(status_code=404, detail="Associado não encontrado.")

    limpar_referencias_pessoa(
        sessao,
        [associado.nome, associado.email, associado.cpf, associado.telefone],
    )
    excluir_vinculos_associado(sessao, associado_id)
    sessao.add(
        AuditoriaDB(
            id_usuario=int(admin.id),
            tipo_operacao="exclusao_associado",
            descricao="Cadastro de associado excluído; referências e vínculos associados foram removidos.",
            data_hora=datetime.now(timezone.utc),
            resultado="sucesso",
            dados_json={},
        )
    )
    sessao.delete(associado)
    try:
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        raise HTTPException(status_code=409, detail="Não foi possível excluir este associado.") from erro
    return {"mensagem": "Cadastro do associado excluído com sucesso."}
