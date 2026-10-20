# Configuração segura do backend

## Segredos locais

1. Copie `.env.example` para `.env` e nunca versione o arquivo `.env`.
2. Gere valores diferentes para `SINDCOMB_AUTH_SECRET`, `SINDCOMB_ML_API_KEY` e `POSTGRES_PASSWORD`:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

3. Gere `SINDCOMB_EMAIL_ENCRYPTION_KEY` com:

   ```powershell
   python -c "import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"
   ```

4. Configure `SINDCOMB_BOOTSTRAP_ADMIN_PASSWORD` com uma senha aleatória de pelo menos 16 caracteres antes do primeiro bootstrap. A conta `adm_sindcomb` não pode redefini-la pela API.
5. Confira o Compose sem iniciar containers:

   ```powershell
   docker compose --env-file .env config
   ```

6. Inicie a aplicação:

   ```powershell
   docker compose --env-file .env up --build
   ```

O `.env.example` contém marcadores inválidos para autenticação; o backend recusa iniciar enquanto eles não forem substituídos. Uma inicialização existente mantém a senha já persistida do administrador. Antes de usar `SINDCOMB_ENVIRONMENT=production`, troque diretamente no PostgreSQL uma senha administrativa de desenvolvimento que ainda esteja ativa. A API bloqueia esse caso na inicialização de produção.

## Produção

- Use `SINDCOMB_ENVIRONMENT=production`, URLs públicas HTTPS, origens HTTPS explícitas em `SINDCOMB_CORS_ORIGINS` e senhas exclusivas para PostgreSQL, JWT, ML e criptografia de e-mail.
- O JWT é entregue em cookie `HttpOnly`, `SameSite=Strict`, `Secure` em produção e com validade máxima de 60 minutos; o corpo de login contém apenas um token CSRF derivado do JWT. Chamadas autenticadas que alteram dados exigem esse token em `X-CSRF-Token`. Configure frontend e API sob o mesmo site HTTPS e mantenha a lista CORS restrita às origens do frontend.
- Não publique `/docs`, `/redoc` ou `/openapi.json`; ficam desligados nesse ambiente.
- Coloque a API e o frontend atrás de um proxy reverso com TLS, limites de requisição e encaminhamento de IP configurado para proxies confiáveis. O Compose de desenvolvimento publica API e frontend apenas em `127.0.0.1`.
- O Compose separa frontend, dados e modelo em redes distintas; frontend não acessa diretamente PostgreSQL, Redis ou Qwen. Não conecte serviços não confiáveis às redes `data` e `ml`.
- PostgreSQL e Redis não publicam portas no host; a chave do Qwen entra por variável de ambiente e não aparece nos argumentos do processo. O vLLM ainda tem rotas não protegidas pela chave, então mantenha sua rede acessível apenas pelo backend e nunca publique a porta do modelo. A chave protege os endpoints compatíveis, não substitui o isolamento de rede.
- Restrinja acesso ao PostgreSQL, Redis, volumes de documentos, backups e arquivo `.env`. O usuário de banco compartilhado não substitui autorização da API.
- O dump de origem habilita RLS sem criar políticas. O backend usa uma conta PostgreSQL proprietária das tabelas, que pode ignorar RLS. Portanto, RLS não é uma segunda barreira neste desenho; mantenha o banco acessível somente pela rede privada e a autorização no backend até migrar o esquema para papéis separados e políticas testadas.
- Senhas são derivadas com scrypt (`N=2^14`, `r=8`, `p=5`); verificações aceitam apenas parâmetros legados dentro de limites de custo conhecidos (`N` entre `2^14` e `2^16`, `r=8`, `p` entre 1 e 5), para impedir que um hash corrompido force consumo excessivo de CPU/memória.
- A outbox cifra corpos enquanto as mensagens aguardam envio. Depois de enviar, cancela ou atingir falha permanente, o backend apaga corpo e assunto. Faça backup seguro da chave Fernet; sua perda impede o envio de mensagens pendentes.
- Mensagens pendentes antigas são cifradas na primeira inicialização com a nova versão. Corpos de mensagens encerradas são apagados.
- `GET /health` verifica apenas se o processo responde. `GET /ready` testa PostgreSQL e Redis e é usado pelo healthcheck do Compose.

## Limites de requisição

Redis aplica limites compartilhados entre instâncias: 10 tentativas de login por minuto, 10 trocas de senha por 15 minutos, 5 pedidos de recuperação por 15 minutos, 10 verificações/redefinições por 15 minutos, 10 reenvios de verificação por 15 minutos, 5 triagens de processo por minuto, 2 sincronizações por 5 minutos, 20 interpretações/movimentações de IA por minuto e 5 uploads por minuto, por endereço remoto. Limites para documentos e movimentações agrupam todos os IDs de processo para impedir que o mesmo cliente contorne a regra variando o ID. Tokens de acesso duram no máximo 60 minutos. Respostas da API usam `Cache-Control: no-store`. O proxy de produção deve aplicar limites adicionais por IP e não deve confiar em cabeçalhos de endereço encaminhado de clientes não confiáveis.

O upload é limitado antes do parser multipart, inclusive quando o cliente transmite o corpo em chunks sem `Content-Length`. O limite considera o arquivo configurado em `SINDCOMB_MAX_UPLOAD_MB` (máximo 100 MB) mais 1 MiB para os campos multipart. A API também valida extensão e formato do conteúdo; em produção, o proxy deve aplicar um limite equivalente.
