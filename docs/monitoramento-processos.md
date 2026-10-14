# Autenticação e acompanhamento processual

## Regras de acesso

- Administradores iniciais são provisionados pela variável `SINDCOMB_BOOTSTRAP_ADMIN_PASSWORD`. O login fixo é `adm_sindcomb`; a conta não possui e-mail, telefone ou outro contato. A senha inicial definida para o projeto é `adm123`. Não há rota para cadastrar outro administrador, alterar o nome de usuário ou trocar a senha administrativa. Na primeira inicialização, a senha configurada cria a conta; um marcador no PostgreSQL bloqueia novo provisionamento mesmo que a variável do ambiente seja alterada depois. A senha não é trocada no primeiro acesso.
- O administrador só gerencia cadastros de advogados e associados. Ele não pode listar, consultar, cadastrar, sincronizar, analisar ou receber notificações sobre processos. Os endpoints de processos retornam `403` para essa conta.
- O e-mail do advogado é seu usuário de acesso. A senha inicial vem de `SINDCOMB_SENHA_INICIAL`, fica armazenada com hash scrypt e deve ser compartilhada com o advogado por canal seguro.
- A conta do advogado começa sem e-mail verificado e com `primeiro_acesso=true`. Ele precisa confirmar o link recebido por e-mail, entrar com a senha inicial e trocá-la antes de usar as demais funções.
- Somente advogados cadastrados na tabela `juridico` podem cadastrar processos, incluir movimentações, sincronizar pelo DataJud ou alterar status. Visualizadores podem consultar processos, mas não alterá-los.
- Associados não têm conta de usuário. O cadastro de associados é consultado para vincular partes a processos e descobrir endereços de e-mail.
- A exclusão de um advogado ou associado é permanente e exclusiva para administradores. O sistema apaga o cadastro e seus vínculos com processos, anonimiza as referências encontradas no conteúdo dos processos, movimentações, auditorias e sincronizações, e invalida a triagem afetada para revisão. O processo e seu histórico jurídico permanecem; referências ao usuário removido na autoria ficam anonimizadas.
- Atualizações e notificações não são mantidas numa caixa permanente do sistema. Quando um advogado altera status ou uma movimentação é registrada manualmente ou pelo DataJud após análise do agente, o sistema envia e-mail aos associados e advogados vinculados ao processo que tenham e-mail disponível.

## Configuração

Copie `.env.example` para `.env` e configure localmente:

1. `SINDCOMB_AUTH_SECRET` com segredo aleatório de pelo menos 32 caracteres.
2. `SINDCOMB_BOOTSTRAP_ADMIN_PASSWORD` provisiona o administrador `adm_sindcomb` na primeira inicialização. A conta administrativa não armazena e-mail ou contato. O `.env.example` contém a senha inicial `adm123`, compartilhada com os colaboradores conforme solicitado. Depois que a conta for criada, mudar a variável não altera o login nem a senha e não cadastra outro administrador.
3. `SINDCOMB_SENHA_INICIAL` para a senha temporária usada ao criar advogados. Não use o valor de exemplo em produção e não envie essa senha por e-mail.
4. `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` e `SMTP_STARTTLS` para confirmação de e-mail e avisos de processo.
5. `SINDCOMB_PUBLIC_API_URL` para o endereço externo da API usado nos links de confirmação.
6. `DATAJUD_API_KEY` para a consulta pública do CNJ.

O banco é PostgreSQL e a aplicação usa `DATABASE_URL` com `psycopg`. O bootstrap cria as tabelas canônicas e adiciona os campos da aplicação ao esquema PostgreSQL exportado. O agente Qwen continua responsável por classificar o contexto e interpretar movimentações; o envio de e-mail ocorre após a gravação bem-sucedida do evento. Se o SMTP estiver indisponível, a alteração no processo continua salva e a falha fica registrada nos logs da API.

O SQL exportado não contém registros. Em volume PostgreSQL já existente, os scripts de `/docker-entrypoint-initdb.d` não rodam novamente; consulte `backend/database/README.md` para aplicar o esquema manualmente.

## Fluxo de login

1. `POST /api/v1/auth/login` recebe `usuario` e `senha`. O administrador usa `adm_sindcomb`; advogados continuam usando o e-mail cadastrado. Para compatibilidade, a API também aceita o campo legado `email` para advogados.
2. Advogados precisam confirmar o e-mail antes de entrar. O administrador usa o login fixo e não depende de e-mail.
3. Advogados recém-cadastrados recebem `alterar_senha_no_primeiro_acesso=true`; devem usar `POST /api/v1/auth/alterar-senha`, enviando `senha_atual` e `nova_senha` (mínimo 12 caracteres). Para administradores, essa rota responde `403` e a senha não é alterada.
4. A resposta da troca de senha do advogado contém um token renovado para seguir usando a API.

## Endpoints

- `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `GET /api/v1/auth/verificar-email?token=...`, `POST /api/v1/auth/verificar-email`, `POST /api/v1/auth/alterar-senha`.
- `GET/POST /api/v1/admin/advogados`; `PATCH /api/v1/admin/advogados/{usuario_id}` para alterar nome/OAB ou ativar/desativar; `POST /api/v1/admin/advogados/{usuario_id}/reenviar-verificacao`; `DELETE /api/v1/admin/advogados/{usuario_id}` para apagar o cadastro e anonimizar referências associadas.
- `GET/POST /api/v1/admin/associados`; `PATCH /api/v1/admin/associados/{associado_id}`; `DELETE /api/v1/admin/associados/{associado_id}`. Associados são somente contatos/partes, não usuários.
- `POST /api/v1/processos/triagem` — advogado informa o número CNJ; o backend localiza o tribunal e consulta os metadados no DataJud, então o agente Qwen faz a triagem contextual.
- `POST /api/v1/processos/sincronizar` — advogado consulta pelo número CNJ; movimentação nova passa pelo agente e aciona os e-mails.
- `GET /api/v1/processos` e `GET /api/v1/processos/{id}` — usuário verificado que já trocou a senha inicial.
- `PATCH /api/v1/processos/{id}/status` — somente advogado; registra histórico e envia aviso por e-mail.
- `POST /api/v1/processos/{id}/movimentacoes` — somente advogado; agente resume/classifica e o sistema avisa os contatos vinculados.
- `POST /api/v1/processos/interpretar-movimentacao` — usuário autenticado; análise avulsa sem gravar ou enviar notificação.

No cadastro do processo, envie apenas `{"numero":"<número CNJ real>"}` para `POST /api/v1/processos/triagem`. O sistema aceita os 20 dígitos ou o formato CNJ `NNNNNNN-DD.AAAA.J.TR.OOOO`; números sem pontuação são formatados ao salvar e os já formatados são preservados. O endpoint do tribunal é inferido dos campos `J/TR`. A busca DataJud usa os 20 dígitos sem pontuação, como exige o campo `numeroProcesso` da API. Se o número não for localizado, o processo não é cadastrado.

Com os metadados retornados, o backend compara os nomes em `associados_mencionados` e `partes` com o cadastro de associados, ignorando caixa e acentos. Também vincula o advogado criador e advogados citados que correspondam ao nome/OAB cadastrado. Os e-mails de quem foi vinculado ao processo são usados como destinatários.

## Cadastro de advogado para teste

No Swagger (`/docs`), autentique-se como administrador e use `POST /api/v1/admin/advogados`. Exemplo de dados fictícios:

```json
{
  "nome": "Advogado de Teste",
  "email": "advogado.teste@example.com",
  "oab": "SP/000000-T"
}
```

`example.com` é um endereço reservado para exemplos e não recebe e-mails de uma pessoa real. Portanto, este exemplo serve apenas para preencher o formulário: para testar confirmação, login e troca de senha de ponta a ponta, substitua-o por uma caixa de e-mail acessível. A API mantém `email_verificado=false` até a confirmação e não oferece bypass para contas de teste. A senha inicial é a variável `SINDCOMB_SENHA_INICIAL`; não a registre em documentação nem a envie para este e-mail fictício.

A sincronização DataJud continua manual. A busca periódica por nome de parte não está implementada. Confirme movimentações e prazos na fonte oficial.
