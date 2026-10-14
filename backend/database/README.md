# Banco de dados PostgreSQL do SINDCOMB

`001_postgresql_schema.sql` é o esquema PostgreSQL 17.11 exportado do banco que foi modelado no Supabase. Supabase foi apenas a origem do dump; a aplicação usa PostgreSQL autogerenciado no Docker Compose.

O dump contém 16 tabelas e nenhuma linha de dados. O Compose monta o arquivo em `/docker-entrypoint-initdb.d`, executado automaticamente quando o volume `postgres_data` está vazio. O backend complementa o esquema com os campos necessários para autenticação, triagem de processos e auditoria, usando as tabelas `usuario`, `juridico`, `associado`, `processo`, `processo_associado`, `permissao_processo`, `linha_tempo`, `auditoria` e `sincronizacao`.

Na inicialização, o backend também permite `NULL` em `usuario.email` e remove esse dado da conta administrativa antiga, se houver. A conta fixa `adm_sindcomb` não tem e-mail/contato; o e-mail continua obrigatório nos cadastros de advogados pela API.

Para volume existente, primeiro aplique o esquema exportado uma vez, se as tabelas ainda não existirem:

```powershell
docker compose up -d postgres
docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -U sindcomb -d sindcomb -f /docker-entrypoint-initdb.d/001_postgresql_schema.sql
```

Depois reinicie o backend. No início, ele cria as tabelas auxiliares ausentes e adiciona as colunas de extensão de forma idempotente. Não apague `postgres_data` para aplicar essas mudanças.

A aplicação e o backend falam com o PostgreSQL pela rede interna do Compose em `postgres:5432`; a porta não precisa ser publicada no host.
