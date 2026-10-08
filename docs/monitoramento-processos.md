# Monitoramento inicial de processos

## Escopo

- Advogado cadastra processo ou parte monitorada pela API.
- O Qwen faz uma triagem contextual (`interesse_direto`, `revisar`, `sem_interesse`) e resume movimentações.
- A API grava processos, partes, movimentações e histórico no PostgreSQL.
- Advogado pode criar, anexar movimentações, sincronizar e alterar status. Perfil `visualizador` só consulta.
- A integração pública do DataJud sincroniza processos já cadastrados pelo número CNJ. Ela não descobre novos processos por nome de parte.

## Configuração local

1. Copie `.env.example` para `.env` (ou passe o arquivo com `docker compose --env-file`).
2. Preencha `DATAJUD_API_KEY` com a chave publicada pelo CNJ. O CNJ pode atualizar a chave.
3. Defina `SINDCOMB_AUTH_SECRET` com pelo menos 32 caracteres aleatórios.
4. Inicie o backend, PostgreSQL e Redis pelo Compose. O backend cria as tabelas iniciais ao subir; este bootstrap deve virar migração Alembic antes de produção.

A API do DataJud só disponibiliza metadados públicos e movimentações. Os registros podem estar incompletos, atrasados ou anonimizados; confirme decisões e prazos na fonte oficial.

## Endpoints principais

Todos exigem `Authorization: Bearer <JWT>` com claims `sub`, `papel` (`advogado` ou `visualizador`) e `exp`. Não existe endpoint de login/emissão de token ainda; o token deve vir do provedor de identidade da aplicação.

- `POST /api/v1/processos/triagem` — somente advogado; cadastra processo com número, tribunal, assunto, partes, advogados, associados e movimentação opcional. Envia o contexto ao Qwen.
- `POST /api/v1/processos/partes-monitoradas` — somente advogado; registra nome, tipo e aliases de tribunais para integração futura com fonte autorizada que suporte pesquisa por parte.
- `POST /api/v1/processos/sincronizar` — somente advogado; consulta o DataJud pelos números dos processos já cadastrados. Use `tribunal_alias` como `tjrj`, `trt1`, `trf2`, `stj` etc.
- `GET /api/v1/processos` e `GET /api/v1/processos/{id}` — advogado ou visualizador.
- `PATCH /api/v1/processos/{id}/status` — somente advogado; registra autor, data e status anterior.
- `POST /api/v1/processos/{id}/movimentacoes` — somente advogado; resume nova movimentação sem alterar automaticamente o status.

A sincronização é acionada manualmente por esse endpoint. A busca por nomes de partes no DataJud público e uma rotina periódica não estão implementadas; dependem de fonte autorizada e definição de frequência.
