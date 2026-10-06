"""Ponto de entrada da API do Sistema de Acompanhamento Processual SINDCOMB.

Mantenha aqui a montagem da aplicação e a configuração global. As regras de
negócio devem ficar organizadas nos módulos do backend.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.modulos.processos.router import router as processos_router

app = FastAPI(
    title="Sistema de Acompanhamento Processual — SINDCOMB",
    description=(
        "API interna para apoiar a equipe administrativa e o setor jurídico "
        "no acompanhamento de processos, prazos, documentos e notificações."
    ),
    version="0.1.0",
)

# Permite que o frontend Next.js local se comunique com a API durante o
# desenvolvimento. Em outros ambientes, configure as origens permitidas.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", tags=["Sistema"], summary="Verifica a saúde da API")
def health_check() -> dict[str, str]:
    """Endpoint simples para health checks locais e do Docker Compose."""
    return {"status": "ok", "sistema": "sindcomb-api"}


# Próximo passo: importar e registrar aqui os routers dos módulos, por exemplo:
# app.include_router(processos_router, prefix="/api/v1")
# app.include_router(associados_router, prefix="/api/v1")
# app.include_router(prazos_router, prefix="/api/v1")
# app.include_router(notificacoes_router, prefix="/api/v1")

app.include_router(processos_router)