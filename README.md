# SINDCOMB — Sistema de Acompanhamento Processual

Sistema para apoiar as equipes administrativa e jurídica do SINDCOMB no acompanhamento de processos, prazos, documentos, petições e notificações.

O repositório contém uma aplicação web, uma API e serviços de infraestrutura executados com Docker Compose.

## Funcionalidades

- Acompanhamento de processos.
- Gerenciamento de prazos, documentos e petições.
- Comentários compartilhados por processo.
- Autenticação e administração de usuários.
- Notificações e envio de e-mails.
- Tarefas em segundo plano para sincronizações e processamento de e-mails.
- Integração opcional com um modelo de linguagem local via vLLM.

## Tecnologias

| Componente | Tecnologias |
| --- | --- |
| Frontend | Next.js 16, React 19, TypeScript |
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Pydantic |
| Banco de dados | PostgreSQL 17 |
| Cache e suporte a rate limiting | Redis 7 |
| Execução e serviços | Docker Compose |
| Modelo de linguagem opcional | Qwen via vLLM |

## Estrutura do repositório

```text
.
├── backend/
│   ├── app/
│   │   ├── modulos/       # Módulos da API
│   │   ├── nucleo/        # Infraestrutura compartilhada
│   │   ├── background_worker.py
│   │   └── main.py        # Aplicação FastAPI
│   ├── database/          # Esquema e documentação do banco
│   ├── tests/             # Testes do backend
│   ├── Dockerfile
│   └── pyproject.toml
├── docs/                  # Documentação técnica e funcional
├── frontend/
│   ├── src/
│   ├── public/
│   ├── Dockerfile
│   └── package.json
├── .env.example
├── docker-compose.yml
└── README.md
```

## Pré-requisitos

Para executar a aplicação completa:

- Docker Engine ou Docker Desktop com Docker Compose.
- Git.

Para desenvolvimento local sem Docker, também serão necessários:

- Python 3.11 ou superior e `uv` para o backend.
- Node.js e Yarn 4 para o frontend.
- PostgreSQL e Redis acessíveis pelo ambiente local.

## Configuração com Docker Compose

### 1. Clonar o repositório

```bash
git clone https://github.com/Lucasltx1/Projeto_SINDCOMB.git
cd Projeto_SINDCOMB
```

### 2. Criar e configurar o arquivo de ambiente

Crie `.env` a partir do exemplo incluído:

```bash
cp .env.example .env
```

No Windows PowerShell, use:

```powershell
Copy-Item .env.example .env
```

Revise o `.env.example` e preencha os valores necessários. O Compose exige, entre outros, valores para:

- `SINDCOMB_ENVIRONMENT`
- `SINDCOMB_AUTH_SECRET`
- `SINDCOMB_EMAIL_ENCRYPTION_KEY`
- `POSTGRES_PASSWORD`
- `SINDCOMB_ML_API_KEY`

Configure também as variáveis de SMTP se o ambiente precisar enviar e-mails. Não use valores de exemplo, senhas fracas ou chaves compartilhadas em produção. Não versione o arquivo `.env`.

### 3. Iniciar a aplicação

Na raiz do repositório:

```bash
docker compose up --build
```

Para iniciar os serviços em segundo plano:

```bash
docker compose up --build -d
```

O Compose inicia o frontend, o backend, o PostgreSQL e o Redis. O PostgreSQL e o Redis ficam em redes internas do Compose; suas portas não são publicadas no host.

Acesse:

- Aplicação web: <http://localhost:3000>
- API: <http://localhost:8000>
- Swagger da API: <http://localhost:8000/docs>
- ReDoc da API: <http://localhost:8000/redoc>

A documentação interativa da API fica desativada quando `SINDCOMB_ENVIRONMENT=production`.

### 4. Verificar o estado da API

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

`/health` verifica a disponibilidade da API. `/ready` também verifica as dependências PostgreSQL e Redis.

### 5. Encerrar

```bash
docker compose down
```

Para remover também os volumes persistentes — incluindo dados do banco e arquivos enviados — use o comando abaixo **somente se tiver certeza de que deseja apagar esses dados**:

```bash
docker compose down --volumes
```

## Testes do backend

O Compose define um serviço de testes com perfil `tests`. Para executá-lo:

```bash
docker compose --profile tests run --rm backend-tests
```

## Desenvolvimento local

### Backend

O caminho recomendado para instalar as dependências é usar `uv` e o arquivo de lock:

```bash
cd backend
uv sync
```

Configure as variáveis necessárias para o ambiente local e inicie a API:

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

A API local estará disponível em <http://localhost:8000>. O backend precisa conseguir acessar PostgreSQL e Redis; configure as URLs de conexão de acordo com os serviços disponíveis no seu ambiente.

### Frontend

```bash
cd frontend
yarn install
yarn dev
```

A aplicação de desenvolvimento estará disponível em <http://localhost:3000>. Para validar os tipos:

```bash
yarn typecheck
```

Outros scripts disponíveis em `frontend/package.json`:

```bash
yarn build
yarn start
```

## Modelo de linguagem opcional

O Compose disponibiliza o serviço `qwen-ml` no perfil `ml`. Essa configuração requer suporte a GPU NVIDIA e os recursos necessários para executar o modelo.

Para iniciar o serviço junto com os serviços padrão do projeto:

```bash
docker compose --profile ml up --build
```

O backend usa o endereço interno `http://qwen-ml:8000/v1` e o nome de modelo `sindcomb-qwen`, conforme configurado no Compose. Defina `SINDCOMB_ML_API_KEY` no `.env`.

## Banco de dados

O esquema inicial está em `backend/database/001_postgresql_schema.sql`. Em uma instalação nova, o Compose o executa automaticamente quando o volume de dados do PostgreSQL é criado pela primeira vez.

Se já existir um volume de banco, os scripts de inicialização do PostgreSQL não são reaplicados automaticamente. Consulte [`backend/database/README.md`](backend/database/README.md) antes de aplicar ou atualizar o esquema. Faça backup dos dados antes de qualquer operação de migração.

## Documentação adicional

- [`docs/monitoramento-processos.md`](docs/monitoramento-processos.md) — documentação de monitoramento de processos.
- [`docs/seguranca-backend.md`](docs/seguranca-backend.md) — configuração e recomendações de segurança do backend.
- [`docs/auditoria-recuperacao-senha.md`](docs/auditoria-recuperacao-senha.md) — auditoria e recuperação de senha.
- [`backend/database/README.md`](backend/database/README.md) — esquema e procedimentos do banco de dados.

## Segurança e produção

Antes de disponibilizar o sistema em produção:

- Use segredos fortes, únicos e armazenados fora do repositório.
- Defina `SINDCOMB_ENVIRONMENT=production`.
- Configure `SINDCOMB_CORS_ORIGINS` com as origens autorizadas, em vez de manter origens de desenvolvimento.
- Configure corretamente as URLs públicas da API e da aplicação.
- Configure SMTP se o envio de e-mails for necessário.
- Use HTTPS e revise as configurações de proxy, rede, backups e persistência.
- Não publique portas ou serviços internos sem uma necessidade explícita.
- Consulte [`docs/seguranca-backend.md`](docs/seguranca-backend.md) para orientações adicionais.

## Licença

Consulte o arquivo [`LICENSE`](LICENSE) para informações sobre a licença do projeto.
