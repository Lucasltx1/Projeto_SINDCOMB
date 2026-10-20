from datetime import date, datetime, timezone
import re
import unicodedata

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from .models import (
    AdministradorDB,
    AssociadoDB,
    AssociadoNotificacaoDB,
    AuditoriaDB,
    DocumentoDB,
    EmailOutboxDB,
    JuridicoDB,
    LinhaTempoDB,
    ModeloPeticaoDB,
    NotificacaoDB,
    PermissaoProcessoDB,
    PeticaoDB,
    PrazoDB,
    ProcessoAssociadoDB,
    ProcessoDB,
    RegistroSincronizacao,
    UsuarioDB,
    UsuarioNotificacaoDB,
    VersaoPeticaoDB,
)
from .numero_cnj import numero_cnj_sem_formatacao
from .schemas import HistoricoStatus, MovimentacaoRegistro, ProcessoCandidato, ProcessoRegistro, ResultadoTriagem

_STATUS_VALIDOS = {"novo", "em_acompanhamento", "aguardando_prazo", "suspenso", "encerrado"}
_STATUS_LEGADO = {"ativo": "em_acompanhamento", "concluido": "encerrado", "concluído": "encerrado"}


def _id_numero(processo_id: str) -> int | None:
    try:
        return int(processo_id)
    except (TypeError, ValueError):
        return None


def _id_usuario(valor: str) -> int | None:
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def _normalizar_nome(valor: str) -> str:
    sem_acentos = unicodedata.normalize("NFKD", valor)
    return "".join(caractere for caractere in sem_acentos if not unicodedata.combining(caractere)).casefold().strip()


def _sanitizar_valor(valor: object, termos: dict[str, str]) -> tuple[object, bool]:
    """Remove nomes e contatos de JSON/textos sem apagar a estrutura histórica."""
    if isinstance(valor, dict):
        resultado: dict[str, object] = {}
        alterado = False
        for chave, item in valor.items():
            novo_item, mudou = _sanitizar_valor(item, termos)
            resultado[chave] = novo_item
            alterado = alterado or mudou
        return resultado, alterado
    if isinstance(valor, list):
        resultado_lista: list[object] = []
        alterado = False
        for item in valor:
            if isinstance(item, str) and _normalizar_nome(item) in termos:
                alterado = True
                continue
            novo_item, mudou = _sanitizar_valor(item, termos)
            resultado_lista.append(novo_item)
            alterado = alterado or mudou
        return resultado_lista, alterado
    if not isinstance(valor, str):
        return valor, False

    texto = valor
    normalizado = _normalizar_nome(texto)
    correspondencias = [chave for chave in termos if chave and chave in normalizado]
    if not correspondencias:
        return valor, False
    if normalizado in termos:
        return "[referência removida]", True

    for chave in sorted(correspondencias, key=len, reverse=True):
        termo_original = termos[chave]
        texto_novo = re.sub(
            re.escape(termo_original),
            "[referência removida]",
            texto,
            flags=re.IGNORECASE,
        )
        if texto_novo != texto:
            texto = texto_novo
    if texto == valor:
        texto = "[referência removida]"
    return texto, True


def limpar_referencias_pessoa(
    sessao: Session,
    referencias: list[str | None],
    id_usuario: int | None = None,
    id_associado: int | None = None,
) -> int:
    """Anonimiza dados e triagens associados a uma pessoa removida do cadastro."""
    termos = {
        normalizado: referencia.strip()
        for referencia in referencias
        if referencia and (normalizado := _normalizar_nome(referencia))
    }
    if not termos:
        return 0

    processos = sessao.scalars(select(ProcessoDB)).all()
    processos_por_id = {processo.id_processo: processo for processo in processos}
    processos_com_referencia: set[int] = set()
    registros_alterados = 0

    for processo in processos:
        processo_alterado = False
        dados_json, mudou_dados = _sanitizar_valor(processo.dados_json or {}, termos)
        if mudou_dados:
            processo.dados_json = dados_json
            processo_alterado = True
        triagem_json, mudou_triagem = _sanitizar_valor(processo.triagem_json or {}, termos)
        if mudou_triagem:
            processo_alterado = True
        assunto, mudou_assunto = _sanitizar_valor(processo.assunto or "", termos)
        if mudou_assunto:
            processo.assunto = str(assunto)
            processo_alterado = True
        tipo, mudou_tipo = _sanitizar_valor(processo.tipo or "", termos)
        if mudou_tipo:
            processo.tipo = str(tipo)
            processo_alterado = True
        if id_usuario is not None and processo.criado_por == str(id_usuario):
            processo.criado_por = "Usuário removido"
            processo_alterado = True

        if mudou_dados or mudou_triagem or mudou_assunto or mudou_tipo:
            processo.triagem_json = {
                "relevancia": "revisar",
                "justificativa": "Triagem invalidada após a remoção de uma referência do cadastro.",
                "evidencias": [],
                "confianca": 0.0,
            }
            processos_com_referencia.add(processo.id_processo)
        if processo_alterado:
            processo.atualizado_em = datetime.now(timezone.utc)
            registros_alterados += 1

    eventos = sessao.scalars(select(LinhaTempoDB)).all()
    for evento in eventos:
        mudou = False
        descricao, mudou_descricao = _sanitizar_valor(evento.descricao, termos)
        if mudou_descricao:
            evento.descricao = str(descricao)
            mudou = True
            processos_com_referencia.add(evento.id_processo)
        dados_evento, mudou_dados = _sanitizar_valor(evento.dados_json or {}, termos)
        if mudou_dados:
            evento.dados_json = dados_evento
            mudou = True
            processos_com_referencia.add(evento.id_processo)
        if id_usuario is not None and evento.id_usuario == id_usuario:
            evento.id_usuario = None
            dados_evento = dict(evento.dados_json or {})
            if dados_evento.get("registrada_por") == str(id_usuario):
                dados_evento["registrada_por"] = "Usuário removido"
                evento.dados_json = dados_evento
            mudou = True
        if mudou:
            registros_alterados += 1

    auditorias = sessao.scalars(select(AuditoriaDB)).all()
    for auditoria in auditorias:
        mudou = False
        descricao, mudou_descricao = _sanitizar_valor(auditoria.descricao or "", termos)
        if mudou_descricao:
            auditoria.descricao = str(descricao)
            mudou = True
            if auditoria.id_processo is not None:
                processos_com_referencia.add(auditoria.id_processo)
        dados_auditoria, mudou_dados = _sanitizar_valor(auditoria.dados_json or {}, termos)
        if mudou_dados:
            auditoria.dados_json = dados_auditoria
            mudou = True
            if auditoria.id_processo is not None:
                processos_com_referencia.add(auditoria.id_processo)
        if id_usuario is not None and auditoria.id_usuario == id_usuario:
            auditoria.id_usuario = None
            dados_auditoria = dict(auditoria.dados_json or {})
            if dados_auditoria.get("alterado_por") == str(id_usuario):
                dados_auditoria["alterado_por"] = "Usuário removido"
                auditoria.dados_json = dados_auditoria
            mudou = True
        if mudou:
            registros_alterados += 1

    sincronizacoes = sessao.scalars(select(RegistroSincronizacao)).all()
    for sincronizacao in sincronizacoes:
        descricao, mudou_descricao = _sanitizar_valor(sincronizacao.descricao or "", termos)
        if mudou_descricao:
            sincronizacao.descricao = str(descricao)
            if sincronizacao.id_processo is not None:
                processos_com_referencia.add(sincronizacao.id_processo)
            registros_alterados += 1

    notificacoes = sessao.scalars(select(NotificacaoDB)).all()
    for notificacao in notificacoes:
        mudou = False
        for campo in ("titulo", "mensagem"):
            valor = getattr(notificacao, campo)
            novo_valor, foi_alterado = _sanitizar_valor(valor, termos)
            if foi_alterado:
                setattr(notificacao, campo, novo_valor)
                mudou = True
        if mudou:
            prazo = sessao.get(PrazoDB, notificacao.id_prazo) if notificacao.id_prazo is not None else None
            if prazo is not None:
                processos_com_referencia.add(prazo.id_processo)
            registros_alterados += 1

    if id_usuario is not None:
        sessao.execute(
            delete(UsuarioNotificacaoDB).where(UsuarioNotificacaoDB.id_usuario == id_usuario)
        )
    if id_associado is not None:
        sessao.execute(
            delete(AssociadoNotificacaoDB).where(
                AssociadoNotificacaoDB.id_associado == id_associado
            )
        )

    registros_textuais = (
        (DocumentoDB, ("nome",), "id_usuario"),
        (PeticaoDB, ("tipo", "descricao"), "id_usuario"),
        (VersaoPeticaoDB, ("conteudo",), "id_usuario"),
        (ModeloPeticaoDB, ("nome", "tipo", "conteudo"), "criado_por"),
        (PrazoDB, ("descricao",), "id_usuario"),
    )
    for modelo, campos, campo_usuario in registros_textuais:
        for registro in sessao.scalars(select(modelo)).all():
            mudou = False
            conteudo_alterado = False
            for campo in campos:
                valor = getattr(registro, campo)
                if isinstance(valor, str):
                    novo_valor, foi_alterado = _sanitizar_valor(valor, termos)
                    if foi_alterado:
                        setattr(registro, campo, novo_valor)
                        mudou = True
                        conteudo_alterado = True
            if id_usuario is not None and getattr(registro, campo_usuario) == id_usuario:
                setattr(registro, campo_usuario, None)
                mudou = True
            if mudou:
                registros_alterados += 1
            if conteudo_alterado:
                processo_id = getattr(registro, "id_processo", None)
                if processo_id is None and isinstance(registro, VersaoPeticaoDB):
                    peticao = sessao.get(PeticaoDB, registro.id_peticao)
                    processo_id = peticao.id_processo if peticao is not None else None
                if processo_id is not None:
                    processos_com_referencia.add(processo_id)

    from .email_outbox import descriptografar_corpo_email, proteger_corpo_email

    for email in sessao.scalars(select(EmailOutboxDB)).all():
        mudou = False
        destinatario, destinatario_alterado = _sanitizar_valor(email.destinatario, termos)
        if destinatario_alterado:
            email.destinatario = str(destinatario)
            if email.status == "pendente":
                email.status = "cancelado"
            email.assunto = "[referência removida]"
            email.corpo = ""
            email.ultimo_erro = None
            mudou = True
        else:
            if email.status == "pendente":
                try:
                    corpo_aberto = descriptografar_corpo_email(email.corpo)
                except ValueError:
                    email.status = "cancelado"
                    email.corpo = ""
                    email.assunto = "[mensagem cancelada]"
                    email.ultimo_erro = "Mensagem protegida indisponível após anonimização."
                    mudou = True
                else:
                    corpo_sanitizado, corpo_alterado = _sanitizar_valor(corpo_aberto, termos)
                    if corpo_alterado:
                        email.corpo = proteger_corpo_email(str(corpo_sanitizado))
                        mudou = True
            else:
                # Os corpos enviados/cancelados já são apagados; esta limpeza cobre legados.
                if email.corpo:
                    try:
                        corpo_aberto = descriptografar_corpo_email(email.corpo)
                    except ValueError:
                        corpo_aberto = email.corpo
                    corpo_sanitizado, corpo_alterado = _sanitizar_valor(corpo_aberto, termos)
                    if corpo_alterado:
                        email.corpo = ""
                        mudou = True
            for campo in ("assunto", "ultimo_erro"):
                valor = getattr(email, campo)
                if isinstance(valor, str):
                    novo_valor, foi_alterado = _sanitizar_valor(valor, termos)
                    if foi_alterado:
                        setattr(email, campo, novo_valor)
                        mudou = True
        if mudou:
            registros_alterados += 1

    triagem_revisao = {
        "relevancia": "revisar",
        "justificativa": "Triagem invalidada após a remoção de uma referência do cadastro.",
        "evidencias": [],
        "confianca": 0.0,
    }
    for processo_id in processos_com_referencia:
        processo = processos_por_id.get(processo_id)
        if processo is not None and processo.triagem_json != triagem_revisao:
            processo.triagem_json = triagem_revisao
            processo.atualizado_em = datetime.now(timezone.utc)
            registros_alterados += 1

    return registros_alterados


def excluir_vinculos_advogado(sessao: Session, id_usuario: int) -> None:
    sessao.execute(
        delete(PermissaoProcessoDB).where(PermissaoProcessoDB.id_usuario == id_usuario)
    )


def excluir_vinculos_associado(sessao: Session, id_associado: int) -> None:
    sessao.execute(
        delete(ProcessoAssociadoDB).where(ProcessoAssociadoDB.id_associado == id_associado)
    )


def _status_api(valor: str) -> str:
    normalizado = valor.strip().lower()
    normalizado = _STATUS_LEGADO.get(normalizado, normalizado)
    return normalizado if normalizado in _STATUS_VALIDOS else "novo"


def _para_schema(sessao: Session, row: ProcessoDB) -> ProcessoRegistro:
    dados_json = row.dados_json or {}
    dados_json.setdefault("numero", row.numero_processo)
    dados_json.setdefault("tribunal", row.tribunal or "desconhecido")
    dados_json.setdefault("tribunal_alias", row.tribunal_alias)
    dados_json.setdefault("classe", row.tipo)
    dados_json.setdefault("assunto", row.assunto or "Assunto não informado")
    triagem_json = row.triagem_json or {
        "relevancia": "revisar",
        "justificativa": "Processo importado sem triagem contextual registrada.",
        "evidencias": [],
        "confianca": 0.0,
    }

    movimentos_db = sessao.scalars(
        select(LinhaTempoDB)
        .where(LinhaTempoDB.id_processo == row.id_processo)
        .order_by(LinhaTempoDB.data_hora, LinhaTempoDB.id_evento)
    ).all()
    movimentacoes = []
    for evento in movimentos_db:
        dados_evento = evento.dados_json or {}
        dados_evento.setdefault("texto", evento.descricao)
        dados_evento.setdefault("resumo", evento.descricao)
        dados_evento.setdefault("categoria", evento.tipo_evento if evento.tipo_evento in {
            "andamento", "intimacao", "despacho", "sentenca", "peticao", "prazo", "outro"
        } else "outro")
        dados_evento.setdefault("requer_atencao", False)
        dados_evento.setdefault("registrada_por", str(evento.id_usuario) if evento.id_usuario else "Sistema")
        dados_evento.setdefault("registrada_em", evento.data_hora)
        movimentacoes.append(MovimentacaoRegistro.model_validate(dados_evento))

    auditorias = sessao.scalars(
        select(AuditoriaDB)
        .where(
            AuditoriaDB.id_processo == row.id_processo,
            AuditoriaDB.tipo_operacao.in_(("status_inicial", "alteracao_status")),
        )
        .order_by(AuditoriaDB.data_hora, AuditoriaDB.id_auditoria)
    ).all()
    historico = []
    for auditoria in auditorias:
        dados_auditoria = auditoria.dados_json or {}
        if dados_auditoria:
            historico.append(HistoricoStatus.model_validate(dados_auditoria))

    return ProcessoRegistro.model_validate(
        {
            "id": str(row.id_processo),
            "dados": dados_json,
            "triagem": triagem_json,
            "status": _status_api(row.status),
            "arquivado": row.arquivado,
            "criado_por": row.criado_por or "sistema",
            "criado_em": row.criado_em,
            "movimentacoes": movimentacoes,
            "historico_status": historico,
        }
    )


def listar(
    sessao: Session,
    relevancia: str | None = None,
    arquivado: bool | None = False,
    *,
    usuario_id: int | None = None,
) -> list[ProcessoRegistro]:
    consulta = select(ProcessoDB)
    if usuario_id is not None:
        consulta = consulta.where(
            ProcessoDB.id_processo.in_(
                select(PermissaoProcessoDB.id_processo).where(
                    PermissaoProcessoDB.id_usuario == usuario_id
                )
            )
        )
    if arquivado is not None:
        consulta = consulta.where(ProcessoDB.arquivado.is_(arquivado))
    linhas = sessao.scalars(consulta.order_by(ProcessoDB.criado_em.desc())).all()
    registros = [_para_schema(sessao, linha) for linha in linhas]
    if relevancia:
        registros = [registro for registro in registros if registro.triagem.relevancia == relevancia]
    return registros


def obter(sessao: Session, processo_id: str) -> ProcessoRegistro | None:
    identificador = _id_numero(processo_id)
    if identificador is None:
        return None
    linha = sessao.get(ProcessoDB, identificador)
    return _para_schema(sessao, linha) if linha else None


def obter_por_numero(sessao: Session, numero: str) -> ProcessoRegistro | None:
    numero_digitos = numero_cnj_sem_formatacao(numero)
    linha = sessao.scalar(
        select(ProcessoDB).where(
            func.regexp_replace(ProcessoDB.numero_processo, "[^0-9]", "", "g") == numero_digitos
        )
    )
    return _para_schema(sessao, linha) if linha else None


def _associados_correspondentes(sessao: Session, dados: ProcessoCandidato) -> list[AssociadoDB]:
    nomes_mencionados = {
        _normalizar_nome(nome)
        for nome in [*dados.associados_mencionados, *dados.partes]
        if nome.strip()
    }
    if not nomes_mencionados:
        return []
    associados = sessao.scalars(select(AssociadoDB)).all()
    return [associado for associado in associados if _normalizar_nome(associado.nome) in nomes_mencionados]


def _advogados_correspondentes(sessao: Session, dados: ProcessoCandidato) -> list[UsuarioDB]:
    nomes_mencionados = {_normalizar_nome(nome) for nome in dados.advogados if nome.strip()}
    if not nomes_mencionados:
        return []
    pares = sessao.execute(
        select(UsuarioDB, JuridicoDB)
        .join(JuridicoDB, JuridicoDB.id_usuario == UsuarioDB.id_usuario)
        .where(UsuarioDB.ativo.is_(True))
    ).all()
    return [
        usuario
        for usuario, juridico in pares
        if _normalizar_nome(usuario.nome) in nomes_mencionados
        or _normalizar_nome(juridico.oab) in nomes_mencionados
    ]


def _adicionar_movimentacao(sessao: Session, processo_id: int, movimento: MovimentacaoRegistro) -> None:
    usuario_id = _id_usuario(movimento.registrada_por)
    origem = "automatico" if movimento.registrada_por.casefold() == "datajud" else "manual"
    sessao.add(
        LinhaTempoDB(
            id_processo=processo_id,
            id_usuario=usuario_id,
            data_hora=movimento.registrada_em,
            descricao=movimento.texto,
            tipo_evento=movimento.categoria,
            origem=origem,
            dados_json=movimento.model_dump(mode="json"),
        )
    )


def _adicionar_historico(sessao: Session, processo_id: int, historico: HistoricoStatus) -> None:
    sessao.add(
        AuditoriaDB(
            id_usuario=_id_usuario(historico.alterado_por),
            id_processo=processo_id,
            tipo_operacao="status_inicial" if historico.de is None else "alteracao_status",
            descricao=historico.observacao or f"Status alterado para {historico.para}.",
            data_hora=historico.em,
            resultado="sucesso",
            dados_json=historico.model_dump(mode="json"),
        )
    )


def adicionar(
    sessao: Session, processo: ProcessoRegistro, *, commit: bool = True
) -> ProcessoRegistro:
    linha = ProcessoDB(
        numero_processo=processo.dados.numero,
        tribunal=processo.dados.tribunal,
        tribunal_alias=processo.dados.tribunal_alias,
        tipo=processo.dados.classe,
        assunto=processo.dados.assunto,
        status=processo.status,
        data_encerramento=date.today() if processo.status == "encerrado" else None,
        arquivado=processo.arquivado,
        dados_json=processo.dados.model_dump(mode="json"),
        triagem_json=processo.triagem.model_dump(mode="json"),
        criado_por=processo.criado_por,
        criado_em=processo.criado_em,
    )
    sessao.add(linha)
    sessao.flush()

    for associado in _associados_correspondentes(sessao, processo.dados):
        sessao.add(
            ProcessoAssociadoDB(id_processo=linha.id_processo, id_associado=associado.id_associado)
        )

    usuario_criador = _id_usuario(processo.criado_por)
    ids_advogados = {usuario.id_usuario for usuario in _advogados_correspondentes(sessao, processo.dados)}
    if usuario_criador is not None:
        ids_advogados.add(usuario_criador)
    for id_usuario in ids_advogados:
        sessao.add(
            PermissaoProcessoDB(
                id_usuario=id_usuario,
                id_processo=linha.id_processo,
                # O dump do PostgreSQL restringe nivel_acesso a leitura/edicao/total.
                nivel_acesso="edicao",
            )
        )

    for movimento in processo.movimentacoes:
        _adicionar_movimentacao(sessao, linha.id_processo, movimento)
    for historico in processo.historico_status:
        _adicionar_historico(sessao, linha.id_processo, historico)

    if commit:
        sessao.commit()
        sessao.refresh(linha)
    else:
        sessao.flush()
    return _para_schema(sessao, linha)


def salvar(
    sessao: Session, processo: ProcessoRegistro, *, commit: bool = True
) -> ProcessoRegistro:
    identificador = _id_numero(processo.id)
    if identificador is None:
        return adicionar(sessao, processo, commit=commit)
    linha = sessao.get(ProcessoDB, identificador)
    if linha is None:
        return adicionar(sessao, processo, commit=commit)

    atual = _para_schema(sessao, linha)
    linha.numero_processo = processo.dados.numero
    linha.tribunal = processo.dados.tribunal
    linha.tribunal_alias = processo.dados.tribunal_alias
    linha.tipo = processo.dados.classe
    linha.assunto = processo.dados.assunto
    linha.status = processo.status
    linha.arquivado = processo.arquivado
    if processo.status == "encerrado":
        if atual.status != "encerrado" or linha.data_encerramento is None:
            linha.data_encerramento = date.today()
    else:
        linha.data_encerramento = None
    linha.dados_json = processo.dados.model_dump(mode="json")
    linha.triagem_json = processo.triagem.model_dump(mode="json")
    linha.atualizado_em = datetime.now(timezone.utc)

    for movimento in processo.movimentacoes[len(atual.movimentacoes):]:
        _adicionar_movimentacao(sessao, linha.id_processo, movimento)
    for historico in processo.historico_status[len(atual.historico_status):]:
        _adicionar_historico(sessao, linha.id_processo, historico)

    if commit:
        sessao.commit()
        sessao.refresh(linha)
    else:
        sessao.flush()
    return _para_schema(sessao, linha)


def listar_emails_envolvidos(sessao: Session, processo_id: str) -> list[str]:
    identificador = _id_numero(processo_id)
    if identificador is None:
        return []
    emails_associados = sessao.scalars(
        select(AssociadoDB.email)
        .join(ProcessoAssociadoDB, ProcessoAssociadoDB.id_associado == AssociadoDB.id_associado)
        .where(
            ProcessoAssociadoDB.id_processo == identificador,
            AssociadoDB.email.is_not(None),
        )
    ).all()
    emails_advogados = sessao.scalars(
        select(UsuarioDB.email)
        .join(PermissaoProcessoDB, PermissaoProcessoDB.id_usuario == UsuarioDB.id_usuario)
        .where(
            PermissaoProcessoDB.id_processo == identificador,
            UsuarioDB.ativo.is_(True),
            UsuarioDB.email.is_not(None),
            UsuarioDB.email_verificado.is_(True),
            ~UsuarioDB.id_usuario.in_(select(AdministradorDB.id_usuario)),
        )
    ).all()
    return list(dict.fromkeys(email.strip().lower() for email in [*emails_associados, *emails_advogados] if email and email.strip()))
