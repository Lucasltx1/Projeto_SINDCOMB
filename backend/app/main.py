from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import asyncio
import logging
import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.modulos.processos.auth_router import admin_router, auth_router
from app.modulos.processos.comentarios_router import router as comentarios_router
from app.modulos.processos.documentos_router import router as documentos_router
from app.modulos.processos.peticoes_router import router as peticoes_router
from app.modulos.processos.prazos_router import router as prazos_router
from app.modulos.processos.router import router as processos_router
from app.background_worker import executar_workers
from app.nucleo.database import criar_tabelas, engine
from app.nucleo.limite_corpo_upload import LimiteCorpoUploadMiddleware
from app.nucleo.rate_limit import aplicar_rate_limit
from app.nucleo.seguranca_config import validar_configuracao_seguranca

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    validar_configuracao_seguranca()
    redis = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"), decode_responses=True)
    _app.state.rate_limit_redis = redis
    try:
        # Bootstrap PostgreSQL, migra a outbox e inicia os workers.
        criar_tabelas()
        trabalhador = asyncio.create_task(executar_workers(), name="sindcomb-background-workers")
        try:
            yield
        finally:
            trabalhador.cancel()
            try:
                await trabalhador
            except asyncio.CancelledError:
                logger.info("Workers de sincronização e e-mail encerrados.")
    finally:
        await redis.aclose()


_ambiente = os.getenv("SINDCOMB_ENVIRONMENT", "development").strip().casefold()
_origens_configuradas = os.getenv("SINDCOMB_CORS_ORIGINS", "").strip()
_origens_permitidas = (
    [origem.strip() for origem in _origens_configuradas.split(",") if origem.strip()]
    if _origens_configuradas
    else ["http://localhost:3000", "http://127.0.0.1:3000"]
)
_documentacao_ativa = _ambiente != "production"


app = FastAPI(
    title="Sistema de Acompanhamento Processual — SINDCOMB",
    description=(
        "API interna para apoiar a equipe administrativa e o setor jurídico "
        "no acompanhamento de processos, prazos, documentos e notificações."
    ),
    version="0.3.0",
    lifespan=lifespan,
    docs_url="/docs" if _documentacao_ativa else None,
    redoc_url="/redoc" if _documentacao_ativa else None,
    openapi_url="/openapi.json" if _documentacao_ativa else None,
)

# Limita o upload antes do parser multipart. O CORS e o rate limit registrados
# abaixo ficam externos a esta camada e processam também respostas 413.
app.add_middleware(LimiteCorpoUploadMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origens_permitidas,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-CSRF-Token"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    redis = getattr(request.app.state, "rate_limit_redis", None)
    if redis is not None:
        resposta_limitador = await aplicar_rate_limit(request, redis)
        if resposta_limitador is not None:
            return resposta_limitador
    resposta = await call_next(request)
    resposta.headers.setdefault("X-Content-Type-Options", "nosniff")
    resposta.headers.setdefault("X-Frame-Options", "DENY")
    resposta.headers.setdefault("Referrer-Policy", "no-referrer")
    resposta.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if _ambiente == "production":
        resposta.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    if request.url.path.startswith("/api/v1/"):
        resposta.headers["Cache-Control"] = "no-store"
    return resposta


@app.get("/health", tags=["Sistema"], summary="Verifica a saúde da API")
def health_check() -> dict[str, str]:
    return {"status": "ok", "sistema": "sindcomb-api", "banco": "postgresql"}


@app.get("/ready", tags=["Sistema"], summary="Verifica banco e Redis")
async def readiness_check(request: Request) -> dict[str, str]:
    try:
        with engine.connect() as conexao:
            conexao.execute(text("SELECT 1"))
        await request.app.state.rate_limit_redis.ping()
    except (SQLAlchemyError, RedisError) as erro:
        logger.exception("Falha na verificação de prontidão da API.")
        raise HTTPException(status_code=503, detail="Dependência indisponível.") from erro
    return {"status": "ok", "banco": "postgresql", "cache": "redis"}


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(comentarios_router)
app.include_router(processos_router)
app.include_router(documentos_router)
app.include_router(peticoes_router)
app.include_router(prazos_router)
