import logging
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.nucleo.database import obter_sessao
from .auth import UsuarioAtual, exigir_acesso_processos, exigir_advogado
from .models import DocumentoDB, PeticaoDB
from .recursos_acesso import obter_processo_autorizado, registrar_auditoria
from .recursos_schemas import DocumentoSaida
from .recursos_service import caminho_arquivo, limite_upload_bytes, salvar_arquivo, validar_arquivo

logger = logging.getLogger(__name__)
router = APIRouter(tags=["Documentos"])


@router.get("/api/v1/processos/{processo_id}/documentos", response_model=list[DocumentoSaida])
def listar_documentos(
    processo_id: int,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> list[DocumentoDB]:
    obter_processo_autorizado(sessao, usuario, processo_id)
    return list(
        sessao.scalars(
            select(DocumentoDB)
            .where(DocumentoDB.id_processo == processo_id)
            .order_by(DocumentoDB.data_upload.desc(), DocumentoDB.id_documento.desc())
        ).all()
    )


@router.post(
    "/api/v1/processos/{processo_id}/documentos",
    response_model=DocumentoSaida,
    status_code=status.HTTP_201_CREATED,
)
async def enviar_documento(
    processo_id: int,
    arquivo: UploadFile = File(...),
    id_peticao: int | None = Form(default=None),
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> DocumentoDB:
    obter_processo_autorizado(sessao, usuario, processo_id, edicao=True)
    limite = limite_upload_bytes()
    conteudo = await arquivo.read(limite + 1)
    if len(conteudo) > limite:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"O arquivo excede o limite de {limite // (1024 * 1024)} MB.",
        )
    try:
        nome, tipo = validar_arquivo(arquivo.filename or "", conteudo)
    except ValueError as erro:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(erro)) from erro

    if id_peticao is not None:
        peticao = sessao.get(PeticaoDB, id_peticao)
        if peticao is None or peticao.id_processo != processo_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Petição não encontrada neste processo.")

    local_armazenamento: str | None = None
    try:
        local_armazenamento, hash_arquivo = salvar_arquivo(processo_id, nome, conteudo)
        documento = DocumentoDB(
            id_processo=processo_id,
            id_usuario=int(usuario.id),
            nome=nome,
            tipo=tipo,
            local_armazenamento=local_armazenamento,
            tamanho=len(conteudo),
            hash_arquivo=hash_arquivo,
            id_peticao=id_peticao,
        )
        sessao.add(documento)
        registrar_auditoria(
            sessao,
            usuario_id=int(usuario.id),
            processo_id=processo_id,
            operacao="upload_documento",
            descricao=f"Documento enviado: {nome}.",
            dados={"nome": nome, "tamanho": len(conteudo), "sha256": hash_arquivo},
        )
        sessao.commit()
        sessao.refresh(documento)
        return documento
    except IntegrityError as erro:
        sessao.rollback()
        if local_armazenamento:
            caminho_arquivo(local_armazenamento).unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Já existe um documento associado a esta petição.",
        ) from erro
    except (OSError, ValueError) as erro:
        sessao.rollback()
        if local_armazenamento:
            try:
                caminho_arquivo(local_armazenamento).unlink(missing_ok=True)
            except (OSError, ValueError):
                logger.exception("Falha ao remover arquivo temporário do processo %s.", processo_id)
        logger.exception("Falha ao armazenar documento do processo %s.", processo_id)
        raise HTTPException(status_code=500, detail="Não foi possível armazenar o documento.") from erro


@router.get("/api/v1/documentos/{documento_id}/download")
def baixar_documento(
    documento_id: int,
    usuario: UsuarioAtual = Depends(exigir_acesso_processos),
    sessao: Session = Depends(obter_sessao),
) -> FileResponse:
    documento = sessao.get(DocumentoDB, documento_id)
    if documento is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado.")
    obter_processo_autorizado(sessao, usuario, documento.id_processo)
    try:
        caminho = caminho_arquivo(documento.local_armazenamento)
    except ValueError as erro:
        logger.error("Caminho de armazenamento inválido para o documento %s.", documento_id)
        raise HTTPException(status_code=500, detail="Localização do documento inválida.") from erro
    if not caminho.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Arquivo não encontrado no armazenamento.")

    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=documento.id_processo,
        operacao="download_documento",
        descricao=f"Documento baixado: {documento.nome}.",
        dados={"id_documento": documento_id},
    )
    sessao.commit()
    return FileResponse(
        path=Path(caminho),
        filename=documento.nome,
        media_type=documento.tipo or "application/octet-stream",
        headers={"X-Content-Type-Options": "nosniff"},
    )


@router.delete("/api/v1/documentos/{documento_id}", status_code=status.HTTP_204_NO_CONTENT)
def excluir_documento(
    documento_id: int,
    usuario: UsuarioAtual = Depends(exigir_advogado),
    sessao: Session = Depends(obter_sessao),
) -> None:
    documento = sessao.get(DocumentoDB, documento_id)
    if documento is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Documento não encontrado.")
    obter_processo_autorizado(sessao, usuario, documento.id_processo, edicao=True)
    try:
        caminho = caminho_arquivo(documento.local_armazenamento)
    except ValueError as erro:
        logger.error("Caminho de armazenamento inválido para o documento %s.", documento_id)
        raise HTTPException(status_code=500, detail="Localização do documento inválida.") from erro

    sessao.delete(documento)
    registrar_auditoria(
        sessao,
        usuario_id=int(usuario.id),
        processo_id=documento.id_processo,
        operacao="exclusao_documento",
        descricao=f"Documento excluído: {documento.nome}.",
        dados={"id_documento": documento_id},
    )
    try:
        sessao.commit()
    except IntegrityError as erro:
        sessao.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="O documento está vinculado a outro registro e não pode ser excluído.",
        ) from erro
    try:
        caminho.unlink(missing_ok=True)
    except OSError:
        logger.exception("Registro do documento %s removido, mas o arquivo físico não pôde ser apagado.", documento_id)
