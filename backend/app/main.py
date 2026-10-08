from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.modulos.processos.router import router as processos_router
from app.nucleo.database import criar_tabelas


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    # Bootstrap do esqueleto. Em produção, substituir por migrações Alembic.
    criar_tabelas()
    yield


app = FastAPI(
    title="Sistema de Acompanhamento Processual — SINDCOMB",
    description=(
        "API interna para apoiar a equipe administrativa e o setor jurídico "
        "no acompanhamento de processos, prazos, documentos e notificações."
    ),
    version="0.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["Sistema"], summary="Verifica a saúde da API")
def health_check() -> dict[str, str]:
    return {"status": "ok", "sistema": "sindcomb-api"}


app.include_router(processos_router)
