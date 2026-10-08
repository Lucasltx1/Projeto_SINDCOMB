from datetime import datetime, timezone
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from openai import APIConnectionError, APIError
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .auth import UsuarioAtual, exigir_advogado, obter_usuario_atual
from .datajud_service import buscar_por_numero, extrair_atualizacao
from .models import ParteMonitorada, RegistroSincronizacao
from .repository import (
    adicionar,
    adicionar_parte,
    listar,
    listar_partes,
    obter,
    obter_parte,
    obter_por_numero,
    salvar,
)
from .schemas import (
    AlteracaoStatus,
    HistoricoStatus,
    MovimentacaoEntrada,
    MovimentacaoRegistro,
    ParteMonitoradaEntrada,
    ParteMonitoradaSaida,
    ProcessoCandidato,
    ProcessoRegistro,
    Relevancia,
    ResultadoSincronizacao,
    ResultadoTriagem,
)
from .status_service import classificar_interesse, interpretar_movimentacao

router = APIRouter(prefix="/api/v1/processos", tags=["Processos"])


def _erro_ml(erro: Exception) -> HTTPException:
    if isinstance(erro, APIConnectionError):
        return HTTPException(status_code=503, detail="O serviço local de ML está indisponível.")
    return HTTPException(status_code=502, detail="Não foi possível obter uma resposta estruturada do modelo local.")


def _parte_saida(parte: ParteMonitorada) -> ParteMonitoradaSaida:
    return ParteMonitoradaSaida(
        id=parte.id,
        nome=parte.nome,
        tipo=parte.tipo,
        tribunais=parte.tribunais,
        ativa=parte.ativa,
        criada_por=parte.criada_por,
        criada_em=parte.criada_em,
    )


@router.get("", response_model=list[ProcessoRegistro])
def listar_processos(
    relevancia: Relevancia | None = Query(default=None),
    _usuario: UsuarioAtual = Depends(obter_usuario_atual),
    sessao: Session = Depends(obter_sessao),
) -> list[ProcessoRegistro]:
    """Advogados e usuários de leitura consultam os mesmos processos."""
    return listar(sessao, relevancia)


@router.post("/partes-monitoradas", response_model=ParteMonitoradaSaida, status_code=201)
def cadastrar_parte_monitorada(
    entrada: ParteMonitoradaEntrada,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ParteMonitoradaSaida:
    """Cadastra SINDCOMB, advogado ou associado para busca no DataJud."""
    existente = sessao.scalar(
        select(ParteMonitorada).where(func.lower(ParteMonitorada.nome) == entrada.nome.lower())
    )
    if existente:
        raise HTTPException(status_code=409, detail="Já existe uma parte monitorada com esse nome.")
    parte = ParteMonitorada(
        id=str(uuid4()),
        nome=entrada.nome.strip(),
        tipo=entrada.tipo,
        tribunais=entrada.tribunais,
        ativa=True,
        criada_por=usuario.id,
    )
    return _parte_saida(adicionar_parte(sessao, parte))


@router.get("/partes-monitoradas", response_model=list[ParteMonitoradaSaida])
def consultar_partes_monitoradas(
    _usuario: UsuarioAtual = Depends(obter_usuario_atual),
    sessao: Session = Depends(obter_sessao),
) -> list[ParteMonitoradaSaida]:
    return [_parte_saida(parte) for parte in listar_partes(sessao)]


@router.post("/sincronizar", response_model=ResultadoSincronizacao)
async def sincronizar_datajud(
    _usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ResultadoSincronizacao:
    """Atualiza processos já cadastrados consultando o DataJud pelo número CNJ."""
    processos = listar(sessao)
    sessao.commit()
    if not processos:
        return ResultadoSincronizacao(processos_consultados=0, processos_com_movimentacao_nova=0)

    import os
    if not os.getenv("DATAJUD_API_KEY", "").strip():
        raise HTTPException(status_code=503, detail="Configure DATAJUD_API_KEY para consultar o DataJud.")

    consultados = movimentos_novos = 0
    falhas: list[str] = []
    aliases = {"tjrj": "tjrj", "trf2": "trf2", "trt1": "trt1", "stj": "stj", "tst": "tst"}
    for processo in processos:
        alias = (processo.dados.tribunal_alias or aliases.get(processo.dados.tribunal.lower(), "")).lower()
        if not alias:
            falhas.append(f"{processo.dados.numero}: informe tribunal_alias (por exemplo, tjrj).")
            continue
        consultados += 1
        encontrado = False
        erro_texto = None
        try:
            fontes = await buscar_por_numero(processo.dados.numero, alias)
            if fontes:
                encontrado = True
                fonte = fontes[0]
                atualizacao = extrair_atualizacao(fonte)
                movimento_novo = atualizacao.get("ultima_movimentacao")
                dados_update: dict[str, object] = {}
                if atualizacao.get("classe"):
                    dados_update["classe"] = atualizacao["classe"]
                if atualizacao.get("assunto"):
                    dados_update["assunto"] = atualizacao["assunto"]

                if movimento_novo and movimento_novo != processo.dados.ultima_movimentacao:
                    try:
                        interpretacao = await interpretar_movimentacao(movimento_novo)
                        triagem_modelo = await classificar_interesse(
                            processo.dados.model_copy(
                                update={**dados_update, "ultima_movimentacao": movimento_novo}
                            ).model_dump(mode="json")
                        )
                    except (APIConnectionError, APIError, ValidationError, ValueError) as erro:
                        falhas.append(f"{processo.dados.numero}: movimentação encontrada, mas IA falhou ({type(erro).__name__}).")
                    else:
                        dados_update["ultima_movimentacao"] = movimento_novo
                        movimento = MovimentacaoRegistro(
                            texto=movimento_novo,
                            resumo=interpretacao.resumo,
                            categoria=interpretacao.categoria,
                            requer_atencao=interpretacao.requer_atencao,
                            registrada_por="DataJud",
                        )
                        atualizado = processo.model_copy(
                            update={
                                "dados": processo.dados.model_copy(update=dados_update),
                                "triagem": ResultadoTriagem.model_validate(triagem_modelo.model_dump()),
                                "movimentacoes": [*processo.movimentacoes, movimento],
                            }
                        )
                        salvar(sessao, atualizado)
                        movimentos_novos += 1
                elif dados_update:
                    salvar(sessao, processo.model_copy(update={"dados": processo.dados.model_copy(update=dados_update)}))
        except httpx.HTTPStatusError as erro:
            erro_texto = f"HTTP {erro.response.status_code}"
            falhas.append(f"{processo.dados.numero}: consulta DataJud falhou ({erro_texto}).")
        except (httpx.HTTPError, RuntimeError, ValueError) as erro:
            erro_texto = type(erro).__name__
            falhas.append(f"{processo.dados.numero}: consulta DataJud falhou ({erro_texto}).")

        sessao.add(
            RegistroSincronizacao(
                id=str(uuid4()),
                processo_id=processo.id,
                numero=processo.dados.numero,
                tribunal=alias,
                consultada_em=datetime.now(timezone.utc),
                encontrado=encontrado,
                erro=erro_texto,
            )
        )
        sessao.commit()

    return ResultadoSincronizacao(
        processos_consultados=consultados,
        processos_com_movimentacao_nova=movimentos_novos,
        falhas=falhas[:50],
    )

@router.post("/triagem", response_model=ProcessoRegistro, status_code=status.HTTP_201_CREATED)
async def cadastrar_para_triagem(
    dados: ProcessoCandidato,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ProcessoRegistro:
    """Advogado cadastra um processo; Qwen faz triagem contextual e resume a última movimentação."""
    existente = obter_por_numero(sessao, dados.numero, dados.tribunal)
    if existente:
        raise HTTPException(status_code=409, detail="Esse processo já está cadastrado para o tribunal informado.")
    try:
        triagem_modelo = await classificar_interesse(dados.model_dump(mode="json"))
        movimentos: list[MovimentacaoRegistro] = []
        if dados.ultima_movimentacao:
            interpretacao = await interpretar_movimentacao(dados.ultima_movimentacao)
            movimentos.append(
                MovimentacaoRegistro(
                    texto=dados.ultima_movimentacao,
                    resumo=interpretacao.resumo,
                    categoria=interpretacao.categoria,
                    requer_atencao=interpretacao.requer_atencao,
                    fonte_url=dados.fonte_url,
                    registrada_por=usuario.id,
                )
            )
    except (APIConnectionError, APIError, ValidationError, ValueError) as erro:
        raise _erro_ml(erro) from erro

    registro = ProcessoRegistro(
        id=str(uuid4()),
        dados=dados,
        triagem=ResultadoTriagem.model_validate(triagem_modelo.model_dump()),
        criado_por=usuario.id,
        movimentacoes=movimentos,
        historico_status=[HistoricoStatus(de=None, para="novo", alterado_por=usuario.id, observacao="Cadastro inicial")],
    )
    return adicionar(sessao, registro)


@router.get("/{processo_id}", response_model=ProcessoRegistro)
def detalhar_processo(
    processo_id: str,
    _usuario: UsuarioAtual = Depends(obter_usuario_atual),
    sessao: Session = Depends(obter_sessao),
) -> ProcessoRegistro:
    processo = obter(sessao, processo_id)
    if processo is None:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    return processo


@router.post("/{processo_id}/movimentacoes", response_model=ProcessoRegistro)
async def registrar_movimentacao(
    processo_id: str,
    entrada: MovimentacaoEntrada,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ProcessoRegistro:
    """Anexa uma movimentação; não altera automaticamente o status do processo."""
    processo = obter(sessao, processo_id)
    if processo is None:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    try:
        interpretacao = await interpretar_movimentacao(entrada.texto)
    except (APIConnectionError, APIError, ValidationError, ValueError) as erro:
        raise _erro_ml(erro) from erro

    movimento = MovimentacaoRegistro(
        texto=entrada.texto,
        resumo=interpretacao.resumo,
        categoria=interpretacao.categoria,
        requer_atencao=interpretacao.requer_atencao,
        fonte_url=entrada.fonte_url,
        registrada_por=usuario.id,
    )
    dados_atualizados = processo.dados.model_copy(
        update={"ultima_movimentacao": entrada.texto, "fonte_url": entrada.fonte_url or processo.dados.fonte_url}
    )
    atualizado = processo.model_copy(
        update={"dados": dados_atualizados, "movimentacoes": [*processo.movimentacoes, movimento]}
    )
    return salvar(sessao, atualizado)


@router.patch("/{processo_id}/status", response_model=ProcessoRegistro)
def alterar_status(
    processo_id: str,
    alteracao: AlteracaoStatus,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> ProcessoRegistro:
    processo = obter(sessao, processo_id)
    if processo is None:
        raise HTTPException(status_code=404, detail="Processo não encontrado.")
    if processo.status == alteracao.status:
        return processo

    historico = HistoricoStatus(
        de=processo.status,
        para=alteracao.status,
        alterado_por=usuario.id,
        observacao=alteracao.observacao,
    )
    atualizado = processo.model_copy(
        update={"status": alteracao.status, "historico_status": [*processo.historico_status, historico]}
    )
    return salvar(sessao, atualizado)


@router.post("/interpretar-movimentacao")
async def interpretar_avulsa(
    pedido: MovimentacaoEntrada,
    _usuario: UsuarioAtual = Depends(obter_usuario_atual),
) -> dict[str, str | bool]:
    try:
        resultado = await interpretar_movimentacao(pedido.texto)
    except (APIConnectionError, APIError, ValidationError, ValueError) as erro:
        raise _erro_ml(erro) from erro
    return resultado.model_dump()
