# Auditoria e recuperação de senha

## Recuperação

- `POST /api/v1/auth/solicitar-recuperacao-senha` recebe `{ "email": "..." }` e sempre retorna a mesma resposta, sem confirmar se o endereço está cadastrado.
- `POST /api/v1/auth/redefinir-senha` recebe `{ "token": "...", "nova_senha": "..." }`. A senha precisa ter de 12 a 128 caracteres.
- O link enviado por e-mail abre `/redefinir-senha`; o token fica no fragmento da URL (`#token=...`) e é removido do endereço depois que a página o lê.
- Tokens duram uma hora por padrão, são de uso único e têm apenas o hash SHA-256 na tabela de tokens. Os corpos da outbox são cifrados com Fernet enquanto pendentes e apagados após envio/cancelamento/falha permanente. A troca da senha invalida sessões anteriores.
- O administrador fixo (`adm_sindcomb`) não tem e-mail e não pode usar recuperação de senha.
- A solicitação usa a fila persistente de e-mail já existente. Configure `SMTP_HOST`, `SMTP_FROM` e as demais variáveis SMTP para que as mensagens sejam entregues. `SINDCOMB_PUBLIC_APP_URL` deve apontar para o endereço acessível pelo usuário.
- A API aplica limites por IP via Redis: login (10/minuto), pedido de recuperação (5/15 minutos), redefinição/verificação (10/15 minutos). O Redis precisa estar disponível para essas rotas.

## Auditoria

Eventos de autenticação, troca/recuperação de senha e administração de advogados/associados são gravados na tabela `auditoria`. Valores de senha, token e outras credenciais são removidos dos metadados do evento. O endpoint `GET /api/v1/admin/auditoria` pagina os eventos de conta e filtra operações; eventos vinculados a processos ou com nomes de operações processuais nunca são mostrados ao administrador. Advogados e usuários autorizados podem consultar o histórico de auditoria de um processo em `GET /api/v1/processos/{processo_id}/auditoria`.

## Testes automatizados

Os testes de auditoria e recuperação usam SQLite em memória. Para executá-los junto com os testes de confiabilidade do backend no Docker:

```powershell
docker compose --env-file .env --profile tests run --rm backend-tests
```

O perfil de testes não inicia nem altera o PostgreSQL de desenvolvimento.
