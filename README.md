# Projeto SINDCOMB

Sistema de Acompanhamento Processual do SINDCOMB, voltado para gestão operacional de processos, prazos, documentos, petições, notificações e acompanhamento jurídico/administrativo.

O projeto é composto por:
- Frontend em Next.js
- Backend em FastAPI
- Banco PostgreSQL
- Cache/limite de requisições com Redis
- Containerização com Docker Compose
- Integração opcional com modelo de IA (Qwen via vLLM)

## Visão geral

A aplicação permite:
- cadastrar e acompanhar processos
- visualizar prazos e alertas
- gerenciar documentos e petições
- registrar comentários e discussões por processo
- controlar autenticação e autorização
- sincronizar dados em background
- enviar notificações e e-mails
- consultar documentação técnica em `/docs` (API) e na pasta `docs/`

## Stack principal

- Frontend: Next.js 16, React 19, TypeScript, Tailwind CSS
- Backend: FastAPI, SQLAlchemy, Pydantic
- Banco: PostgreSQL 17
- Cache: Redis 7
- Infra: Docker Compose
- IA (opcional): Qwen via vLLM

## Estrutura do repositório

```text
.
├── backend/
│   ├── app/
│   │   ├── modulos/
│   │   ├── nucleo/
│   │   ├── background_worker.py
│   │   └── main.py
│   ├── database/
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── tests/
├── frontend/
│   ├── src/
│   ├── public/
│   ├── package.json
│   ├── README.md
│   └── Dockerfile
├── docs/
│   ├── auditoria-recuperacao-senha.md
│   ├── monitoramento-processos.md
│   └── seguranca-backend.md
├── .env.example
├── docker-compose.yml
├── README.md
├── LICENSE
└── .gitignore
```

## Requisitos

- Docker
- Docker Compose
- Node.js e Yarn (para desenvolvimento local do frontend)
- Python 3.11+ e uv (opcional, para desenvolvimento do backend)
- Variáveis de ambiente configuradas

## Configuração inicial

1. Clone o repositório:

```bash
git clone https://github.com/Lucasltx1/Projeto_SINDCOMB.git
cd Projeto_SINDCOMB
```

2. Crie o arquivo de ambiente a partir do exemplo:

```bash
cp .env.example .env
```

3. Ajuste as variáveis obrigatórias no arquivo `.env`, especialmente:

```env
SINDCOMB_ENVIRONMENT=development
SINDCOMB_AUTH_SECRET=chave-secreta-muito-segura
SINDCOMB_EMAIL_ENCRYPTION_KEY=chave-fernet
POSTGRES_PASSWORD=senhaboa
SINDCOMB_ML_API_KEY=chave-opcional-para-ml
```

> O projeto usa valores padrões em alguns casos, mas as variáveis mais sensíveis precisam ser definidas antes de subir os containers.

## Executando com Docker

Na raiz do projeto:

```bash
docker compose up --build
```

Isso iniciará:
- frontend em `http://localhost:3000`
- backend em `http://localhost:8000`
- PostgreSQL em rede interna do Compose
- Redis em rede interna do Compose

Para validar a API:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

Documentação da API:
- Swagger: `http://localhost:8000/docs`
- Redoc: `http://localhost:8000/redoc`

## Executando o backend localmente

Entre na pasta `backend` e instale as dependências:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r <(python - <<'PY'
import tomllib
with open('pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
print('\n'.join(data['project']['dependencies']))
PY
)
```

Ou, usando uv:

```bash
cd backend
uv sync
```

Depois execute:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Executando o frontend localmente

```bash
cd frontend
yarn install
yarn dev
```

A aplicação será servida em:
- `http://localhost:3000`

## IA / modelo de ML (opcional)

O ambiente Docker inclui um serviço `qwen-ml` com perfil `ml` para permitir integração com um modelo de linguagem. Para subir esse serviço:

```bash
docker compose --profile ml up -d qwen-ml
```

A configuração do backend usa:

```env
SINDCOMB_ML_BASE_URL=http://qwen-ml:8000/v1
SINDCOMB_ML_API_KEY=...
SINDCOMB_ML_MODEL=sindcomb-qwen
```

## Documentação adicional

- `docs/monitoramento-processos.md` — monitoramento e processos
- `docs/seguranca-backend.md` — segurança e boas práticas do backend
- `docs/auditoria-recuperacao-senha.md` — auditoria e recuperação de senha
- `backend/database/README.md` — esquema do PostgreSQL e procedimentos de bootstrap

## Variáveis principais de ambiente

Algumas variáveis importantes no Compose:

```env
SINDCOMB_ENVIRONMENT
SINDCOMB_AUTH_SECRET
SINDCOMB_EMAIL_ENCRYPTION_KEY
SINDCOMB_CORS_ORIGINS
SINDCOMB_PUBLIC_API_URL
SINDCOMB_PUBLIC_APP_URL
SINDCOMB_BOOTSTRAP_ADMIN_PASSWORD
POSTGRES_PASSWORD
DATABASE_URL
REDIS_URL
SINDCOMB_ML_API_KEY
SINDCOMB_ML_BASE_URL
SINDCOMB_ML_MODEL
SMTP_HOST
SMTP_PORT
SMTP_USERNAME
SMTP_PASSWORD
SMTP_FROM
```

## Observações

- O backend utiliza PostgreSQL e Redis em rede interna do Compose.
- A API expõe endpoints protegidos e mecanismos de rate limiting.
- Para produção, ajuste corretamente `SINDCOMB_ENVIRONMENT`, CORS, chaves secretas e URLs públicas.
- A pasta `docs/` concentra decisões de negócio, segurança e monitoramento da solução.

## Licença

Este projeto está sob a licença definida no arquivo `LICENSE`.

## Contribuição

Contribuições são bem-vindas. Para alterações, recomenda-se:
1. criar branch de trabalho
2. validar a aplicação localmente
3. subir alterações com testes/documentação relevantes

Se quiser, posso também montar uma versão mais "premium" do README com badges, arquitetura em ASCII, roadmap e instruções de deploy em produção.