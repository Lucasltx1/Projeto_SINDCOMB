from datetime import datetime, timedelta, timezone
import hashlib
import html
import logging
import os
import secrets

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import HTMLResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .auditoria_service import listar_auditoria_administrativa, registrar_evento
from .auth_service import (
    MENSAGEM_SOLICITACAO,
    redefinir_senha as concluir_redefinicao_senha,
    solicitar_recuperacao_senha,
)
from .auth import (
    UsuarioAtual,
    criar_access_token,
    criar_token_csrf,
    duracao_access_token_minutos,
    exigir_administrador,
    obter_usuario_atual,
)
from .email_service import preparar_verificacao_email
from .email_outbox import cancelar_emails_pendentes, enfileirar_email
from .models import (
    AdministradorDB,
    AssociadoDB,
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
    AuditoriaListaSaida,
    CsrfTokenSaida,
    LoginEntrada,
    LoginSaida,
    RedefinirSenhaEntrada,
    SolicitarRecuperacaoSenhaEntrada,
    UsuarioPerfil,
    VerificacaoEmailEntrada,
)
from .security import hash_password, verificar_password

logger = logging.getLogger(__name__)
auth_router = APIRouter(prefix="/api/v1/auth", tags=["Autenticação"])
admin_router = APIRouter(prefix="/api/v1/admin", tags=["Administração"])
_COOKIE_SESSAO = "sindcomb_access_token"


def _definir_cookie_sessao(response: Response | None, token: str) -> None:
    if response is None:
        return
    producao = os.getenv("SINDCOMB_ENVIRONMENT", "development").strip().casefold() == "production"
    response.set_cookie(
        key=_COOKIE_SESSAO,
        value=token,
        max_age=duracao_access_token_minutos() * 60,
        path="/api/v1",
        secure=producao,
        httponly=True,
        samesite="strict",
    )


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
    try:
        horas_configuradas = int(os.getenv("SINDCOMB_EMAIL_VERIFICATION_HOURS", "24"))
    except ValueError:
        horas_configuradas = 24
    horas = min(max(1, horas_configuradas), 168)
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


@auth_router.post("/login", response_model=LoginSaida)
def login(
    entrada: LoginEntrada,
    sessao: Session = Depends(obter_sessao),
    response: Response = None,  # type: ignore[assignment]
) -> LoginSaida:
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
        registrar_evento(
            sessao,
            usuario_id=usuario.id_usuario if usuario is not None else None,
            operacao="auth.login_failed",
            descricao="Tentativa de autenticação não concluída.",
            resultado="falha",
            dados={"metodo": "email" if "@" in entrada.usuario else "username"},
        )
        sessao.commit()
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")
    administrador = sessao.get(AdministradorDB, usuario.id_usuario) is not None
    if not administrador and not usuario.email_verificado:
        registrar_evento(
            sessao,
            usuario_id=usuario.id_usuario,
            operacao="auth.login_blocked_email_unverified",
            descricao="Autenticação bloqueada porque o e-mail ainda não foi confirmado.",
            resultado="bloqueado",
        )
        sessao.commit()
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos.")

    papel = _papel(sessao, usuario)
    registrar_evento(
        sessao,
        usuario_id=usuario.id_usuario,
        operacao="auth.login_succeeded",
        descricao="Autenticação concluída.",
        dados={"papel": papel},
    )
    sessao.commit()
    token = criar_access_token(usuario, papel)
    _definir_cookie_sessao(response, token)
    return LoginSaida(
        csrf_token=criar_token_csrf(token),
        usuario=_perfil(sessao, usuario),
        alterar_senha_no_primeiro_acesso=usuario.primeiro_acesso,
    )


@auth_router.get("/me", response_model=UsuarioPerfil, response_model_exclude_none=True)
def meu_perfil(
    usuario: UsuarioAtual = Depends(obter_usuario_atual),
) -> UsuarioPerfil:
    return UsuarioPerfil(**usuario.model_dump())


@auth_router.get("/csrf", response_model=CsrfTokenSaida)
def obter_token_csrf(
    request: Request,
    _usuario: UsuarioAtual = Depends(obter_usuario_atual),
) -> CsrfTokenSaida:
    return CsrfTokenSaida(csrf_token=request.state.csrf_token)


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
            registrar_evento(
                sessao,
                usuario_id=token.id_usuario,
                operacao="auth.email_verification_expired",
                descricao="Tentativa de confirmação com link expirado.",
                resultado="falha",
            )
            sessao.delete(token)
            sessao.commit()
        raise HTTPException(status_code=400, detail="Link inválido ou expirado. Solicite novo envio ao administrador.")

    usuario = sessao.get(UsuarioDB, token.id_usuario)
    if usuario is None or not usuario.ativo:
        registrar_evento(
            sessao,
            usuario_id=token.id_usuario,
            operacao="auth.email_verification_unavailable_account",
            descricao="Confirmação recusada porque a conta não está disponível.",
            resultado="falha",
        )
        sessao.delete(token)
        sessao.commit()
        raise HTTPException(status_code=400, detail="A conta não está disponível.")
    if sessao.get(AdministradorDB, usuario.id_usuario) is not None:
        registrar_evento(
            sessao,
            usuario_id=usuario.id_usuario,
            operacao="auth.email_verification_admin_rejected",
            descricao="Conta administrativa não participa da verificação por e-mail.",
            resultado="bloqueado",
        )
        sessao.delete(token)
        sessao.commit()
        raise HTTPException(status_code=400, detail="A conta administrativa não usa verificação de e-mail.")
    usuario.email_verificado = True
    sessao.delete(token)
    registrar_evento(
        sessao,
        usuario_id=usuario.id_usuario,
        operacao="auth.email_verified",
        descricao="Endereço de e-mail confirmado.",
    )
    sessao.commit()
    return {
        "mensagem": (
            "E-mail confirmado. Use ‘Esqueci minha senha’ na tela de login para criar "
            "sua senha pessoal."
        )
    }


@auth_router.post("/alterar-senha", response_model=LoginSaida)
def alterar_senha(
    entrada: AlteracaoSenhaEntrada,
    usuario_atual: UsuarioAtual = Depends(obter_usuario_atual),
    sessao: Session = Depends(obter_sessao),
    response: Response = None,  # type: ignore[assignment]
) -> LoginSaida:
    usuario = sessao.get(UsuarioDB, int(usuario_atual.id))
    if usuario is not None and sessao.get(AdministradorDB, usuario.id_usuario) is not None:
        registrar_evento(
            sessao,
            usuario_id=usuario.id_usuario,
            operacao="auth.admin_password_change_blocked",
            descricao="Alteração da senha administrativa bloqueada pela política do sistema.",
            resultado="bloqueado",
        )
        sessao.commit()
        raise HTTPException(
            status_code=403,
            detail="A senha da conta administrativa é fixa e não pode ser alterada pela aplicação.",
        )
    if usuario is None or not verificar_password(entrada.senha_atual, usuario.senha):
        registrar_evento(
            sessao,
            usuario_id=int(usuario_atual.id),
            operacao="auth.password_change_failed",
            descricao="Tentativa de alteração de senha com credencial atual inválida.",
            resultado="falha",
        )
        sessao.commit()
        raise HTTPException(status_code=400, detail="A senha atual está incorreta.")
    if entrada.senha_atual == entrada.nova_senha:
        registrar_evento(
            sessao,
            usuario_id=usuario.id_usuario,
            operacao="auth.password_change_failed",
            descricao="A senha nova informada é igual à senha atual.",
            resultado="falha",
        )
        sessao.commit()
        raise HTTPException(status_code=400, detail="A nova senha deve ser diferente da atual.")
    usuario.senha = hash_password(entrada.nova_senha)
    usuario.primeiro_acesso = False
    usuario.token_version += 1
    registrar_evento(
        sessao,
        usuario_id=usuario.id_usuario,
        operacao="auth.password_changed",
        descricao="Senha alterada; sessões anteriores invalidadas.",
        dados={"sessoes_invalidadas": True},
    )
    sessao.commit()
    papel = _papel(sessao, usuario)
    token = criar_access_token(usuario, papel)
    _definir_cookie_sessao(response, token)
    return LoginSaida(
        csrf_token=criar_token_csrf(token),
        usuario=_perfil(sessao, usuario),
        alterar_senha_no_primeiro_acesso=False,
    )


@auth_router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(
    response: Response,
    usuario_atual: UsuarioAtual = Depends(obter_usuario_atual),
    sessao: Session = Depends(obter_sessao),
) -> None:
    usuario = sessao.get(UsuarioDB, int(usuario_atual.id))
    if usuario is not None:
        usuario.token_version += 1
        registrar_evento(
            sessao,
            usuario_id=usuario.id_usuario,
            operacao="auth.logout",
            descricao="Sessão encerrada e tokens anteriores invalidados.",
            dados={"sessoes_invalidadas": True},
        )
        sessao.commit()
    producao = os.getenv("SINDCOMB_ENVIRONMENT", "development").strip().casefold() == "production"
    response.delete_cookie(
        key=_COOKIE_SESSAO,
        path="/api/v1",
        secure=producao,
        httponly=True,
        samesite="strict",
    )


@auth_router.post("/solicitar-recuperacao-senha", status_code=status.HTTP_202_ACCEPTED)
def solicitar_redefinicao_senha(
    entrada: SolicitarRecuperacaoSenhaEntrada,
    sessao: Session = Depends(obter_sessao),
) -> dict[str, str]:
    solicitar_recuperacao_senha(sessao, entrada.email)
    return {"mensagem": MENSAGEM_SOLICITACAO}


@auth_router.post("/redefinir-senha")
def redefinir_senha(
    entrada: RedefinirSenhaEntrada,
    sessao: Session = Depends(obter_sessao),
    response: Response = None,  # type: ignore[assignment]
) -> dict[str, str]:
    try:
        concluida = concluir_redefinicao_senha(sessao, entrada.token, entrada.nova_senha)
    except ValueError as erro:
        raise HTTPException(status_code=400, detail=str(erro)) from erro
    if not concluida:
        raise HTTPException(status_code=400, detail="Link inválido, expirado ou indisponível.")
    if response is not None:
        producao = os.getenv("SINDCOMB_ENVIRONMENT", "development").strip().casefold() == "production"
        response.delete_cookie(
            key=_COOKIE_SESSAO,
            path="/api/v1",
            secure=producao,
            httponly=True,
            samesite="strict",
        )
    return {"mensagem": "Senha redefinida. Entre novamente com a nova senha."}


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


@admin_router.get("/auditoria", response_model=AuditoriaListaSaida)
def listar_auditoria_admin(
    limite: int = Query(default=50, ge=1, le=100),
    deslocamento: int = Query(default=0, ge=0),
    usuario_id: int | None = Query(default=None, gt=0),
    operacao: str | None = Query(default=None, min_length=1, max_length=50),
    _admin: UsuarioAtual = Depends(exigir_administrador),
    sessao: Session = Depends(obter_sessao),
) -> AuditoriaListaSaida:
    """Admin vê auditoria de contas; eventos vinculados a processos são sempre excluídos."""
    return listar_auditoria_administrativa(
        sessao,
        limite=limite,
        deslocamento=deslocamento,
        usuario_id=usuario_id,
        operacao=operacao,
    )


@admin_router.post("/advogados", response_model=AdvogadoCriadoSaida, status_code=status.HTTP_201_CREATED)
def criar_advogado(
    entrada: AdvogadoCriacao,
    _admin: UsuarioAtual = Depends(exigir_administrador),
    sessao: Session = Depends(obter_sessao),
) -> AdvogadoCriadoSaida:
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
        # Segredo aleatório nunca exposto: após confirmar o e-mail, o advogado
        # define uma senha pessoal pelo fluxo de recuperação.
        senha=hash_password(secrets.token_urlsafe(48)),
        primeiro_acesso=True,
        ativo=True,
        email_verificado=False,
    )
    sessao.add(usuario)
    try:
        sessao.flush()
        juridico = JuridicoDB(id_usuario=usuario.id_usuario, oab=entrada.oab)
        sessao.add(juridico)
        registrar_evento(
            sessao,
            usuario_id=int(_admin.id),
            operacao="admin.lawyer_created",
            descricao="Cadastro de advogado criado.",
            dados={"campos": ["nome", "email", "oab"]},
        )
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        raise HTTPException(status_code=409, detail="E-mail ou OAB já cadastrado.") from erro

    cancelar_emails_pendentes(sessao, usuario.email, categoria="verificacao_email")
    token = _novo_token_verificacao(sessao, usuario.id_usuario)
    assunto, corpo = preparar_verificacao_email(usuario.email, usuario.nome, token)
    email_enviado = enfileirar_email(
        sessao,
        [usuario.email],
        assunto,
        corpo,
        categoria="verificacao_email",
    ) > 0
    sessao.commit()
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
    registrar_evento(
        sessao,
        usuario_id=int(_admin.id),
        operacao="admin.lawyer_updated",
        descricao="Cadastro de advogado atualizado.",
        dados={"campos_alterados": sorted(alteracoes)},
    )
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
    cancelar_emails_pendentes(sessao, usuario.email)
    excluir_vinculos_advogado(sessao, usuario_id)
    registrar_evento(
        sessao,
        usuario_id=int(admin.id),
        operacao="admin.lawyer_deleted",
        descricao="Cadastro de advogado excluído; referências e vínculos associados foram removidos.",
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
    cancelar_emails_pendentes(sessao, usuario.email, categoria="verificacao_email")
    token = _novo_token_verificacao(sessao, usuario.id_usuario)
    assunto, corpo = preparar_verificacao_email(usuario.email, usuario.nome, token)
    enfileirado = enfileirar_email(
        sessao,
        [usuario.email],
        assunto,
        corpo,
        categoria="verificacao_email",
    ) > 0
    registrar_evento(
        sessao,
        usuario_id=int(_admin.id),
        operacao="admin.lawyer_verification_resent",
        descricao="Link de verificação de e-mail reenfileirado.",
        dados={"email_enfileirado": enfileirado},
    )
    sessao.commit()
    return {"email_verificacao_enviado": enfileirado}


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
        registrar_evento(
            sessao,
            usuario_id=int(_admin.id),
            operacao="admin.associate_created",
            descricao="Cadastro de associado criado.",
            dados={"campos": sorted(entrada.model_dump())},
        )
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
        registrar_evento(
            sessao,
            usuario_id=int(_admin.id),
            operacao="admin.associate_updated",
            descricao="Cadastro de associado atualizado.",
            dados={"campos_alterados": sorted(entrada.model_dump(exclude_unset=True))},
        )
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
        id_associado=associado_id,
    )
    cancelar_emails_pendentes(sessao, associado.email)
    excluir_vinculos_associado(sessao, associado_id)
    registrar_evento(
        sessao,
        usuario_id=int(admin.id),
        operacao="admin.associate_deleted",
        descricao="Cadastro de associado excluído; referências e vínculos associados foram removidos.",
    )
    sessao.delete(associado)
    try:
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        raise HTTPException(status_code=409, detail="Não foi possível excluir este associado.") from erro
    return {"mensagem": "Cadastro do associado excluído com sucesso."}
