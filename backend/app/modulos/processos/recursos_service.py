from __future__ import annotations

from hashlib import sha256
from io import BytesIO
import mimetypes
import os
from pathlib import Path
import re
import uuid
import zipfile

from docx import Document
from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
from xml.sax.saxutils import escape


_TIPOS_PERMITIDOS = {
    ".pdf",
    ".docx",
    ".doc",
    ".txt",
    ".png",
    ".jpg",
    ".jpeg",
}
_MIMETYPES = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".txt": "text/plain; charset=utf-8",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
_VARIAVEL_TEMPLATE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def limite_upload_bytes() -> int:
    try:
        limite_mb = int(os.getenv("SINDCOMB_MAX_UPLOAD_MB", "20"))
    except ValueError:
        limite_mb = 20
    return min(max(limite_mb, 1), 100) * 1024 * 1024


def validar_arquivo(nome_original: str, conteudo: bytes) -> tuple[str, str]:
    nome = (nome_original or "").replace("\\", "/").split("/")[-1]
    nome = re.sub(r"[\x00-\x1f\x7f]", "", nome).strip()
    extensao = Path(nome).suffix.lower()
    if not nome or len(nome) > 255:
        raise ValueError("Nome de arquivo inválido ou longo demais.")
    if extensao not in _TIPOS_PERMITIDOS:
        raise ValueError("Tipo de arquivo não permitido. Use PDF, DOC, DOCX, TXT, PNG ou JPEG.")
    if not conteudo:
        raise ValueError("O arquivo está vazio.")

    if extensao == ".pdf" and not conteudo.startswith(b"%PDF-"):
        raise ValueError("O conteúdo enviado não corresponde a um arquivo PDF.")
    if extensao == ".png" and not conteudo.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("O conteúdo enviado não corresponde a uma imagem PNG.")
    if extensao in {".jpg", ".jpeg"} and not conteudo.startswith(b"\xff\xd8\xff"):
        raise ValueError("O conteúdo enviado não corresponde a uma imagem JPEG.")
    if extensao == ".doc" and not conteudo.startswith(bytes.fromhex("D0CF11E0A1B11AE1")):
        raise ValueError("O conteúdo enviado não corresponde a um documento DOC.")
    if extensao == ".docx":
        try:
            with zipfile.ZipFile(BytesIO(conteudo)) as arquivo_zip:
                if "word/document.xml" not in arquivo_zip.namelist():
                    raise ValueError("O conteúdo enviado não corresponde a um documento DOCX.")
        except zipfile.BadZipFile as erro:
            raise ValueError("O documento DOCX está inválido.") from erro
    if extensao == ".txt":
        try:
            conteudo.decode("utf-8-sig")
        except UnicodeDecodeError as erro:
            raise ValueError("Arquivos TXT devem estar codificados em UTF-8.") from erro

    return nome, _MIMETYPES.get(extensao) or mimetypes.guess_type(nome)[0] or "application/octet-stream"


def salvar_arquivo(processo_id: int, nome: str, conteudo: bytes) -> tuple[str, str]:
    raiz = Path(os.getenv("SINDCOMB_STORAGE_DIR", "./storage")).expanduser().resolve()
    extensao = Path(nome).suffix.lower()
    relativo = Path("processos") / str(processo_id) / f"{uuid.uuid4().hex}{extensao}"
    destino = (raiz / relativo).resolve()
    if not destino.is_relative_to(raiz):
        raise ValueError("Caminho de armazenamento inválido.")
    destino.parent.mkdir(parents=True, exist_ok=True)
    temporario = destino.with_name(f".{destino.name}.tmp")
    try:
        temporario.write_bytes(conteudo)
        os.replace(temporario, destino)
    finally:
        temporario.unlink(missing_ok=True)
    return relativo.as_posix(), sha256(conteudo).hexdigest()


def caminho_arquivo(local_armazenamento: str) -> Path:
    raiz = Path(os.getenv("SINDCOMB_STORAGE_DIR", "./storage")).expanduser().resolve()
    caminho = (raiz / local_armazenamento).resolve()
    if not caminho.is_relative_to(raiz):
        raise ValueError("Caminho de arquivo inválido no banco de dados.")
    return caminho


def renderizar_modelo(conteudo: str, variaveis: dict[str, str]) -> str:
    """Substitui apenas variáveis conhecidas e mantém intactas as desconhecidas."""
    return _VARIAVEL_TEMPLATE.sub(lambda achado: variaveis.get(achado.group(1), achado.group(0)), conteudo)


def gerar_docx(conteudo: str) -> bytes:
    documento = Document()
    documento.core_properties.title = "Petição — SINDCOMB"
    for linha in conteudo.splitlines() or [""]:
        documento.add_paragraph(linha)
    saida = BytesIO()
    documento.save(saida)
    return saida.getvalue()


def gerar_pdf(conteudo: str) -> bytes:
    saida = BytesIO()
    documento = SimpleDocTemplate(
        saida,
        pagesize=A4,
        rightMargin=2.5 * cm,
        leftMargin=3.0 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm,
        title="Petição — SINDCOMB",
    )
    estilos = getSampleStyleSheet()
    corpo = ParagraphStyle(
        "CorpoPeticao",
        parent=estilos["BodyText"],
        fontName="Times-Roman",
        fontSize=12,
        leading=18,
        alignment=TA_JUSTIFY,
        textColor=colors.black,
        spaceAfter=8,
    )
    elementos = []
    for linha in conteudo.splitlines() or [""]:
        if not linha.strip():
            elementos.append(Spacer(1, 8))
        else:
            elementos.append(Paragraph(escape(linha), corpo))
    documento.build(elementos)
    return saida.getvalue()
