# Autenticação e acompanhamento processual

## Regras de acesso

- Administradores iniciais são provisionados pela variável `SINDCOMB_BOOTSTRAP_ADMIN_PASSWORD`. O login fixo é `adm_sindcomb`; a conta não possui e-mail, telefone ou outro contato. Defina uma senha aleatória de pelo menos 16 caracteres antes da primeira inicialização. Não há rota para cadastrar outro administrador, alterar o nome de usuário ou trocar sua senha. Um marcador no PostgreSQL bloqueia novo provisionamento depois do bootstrap.
- O administrador só gerencia cadastros de advogados e associados. Ele não pode listar, consultar, cadastrar, sincronizar, analisar ou receber notificações sobre processos. Os endpoints de processos retornam `403` para essa conta.
- O e-mail do advogado é seu usuário de acesso. A conta começa sem e-mail verificado. Após confirmar o link enviado por e-mail, o advogado usa “Esqueci minha senha” para definir uma senha pessoal; não há senha temporária compartilhada.
- Somente advogados cadastrados na tabela `juridico` podem cadastrar processos ou iniciar sincronizações. Listas, detalhes, documentos, petições, prazos e históricos verificam a permissão individual no processo. Para movimentar, alterar status ou arquivar, advogados precisam de permissão de edição naquele processo. Visualizadores autorizados podem consultar, mas não alterar.
- O encerramento processual e o arquivamento são operações distintas. Apenas advogado com permissão de edição arquiva/desarquiva; arquivados saem da lista ativa e da sincronização automática, mas continuam consultáveis e com histórico preservado.
- Associados não têm conta de usuário. O cadastro de associados é consultado para vincular partes a processos e descobrir endereços de e-mail.
- A exclusão de um advogado ou associado é permanente e exclusiva para administradores. O sistema anonimiza referências textuais em processos, prazos, petições, versões, modelos, auditorias, sincronizações e mensagens da fila; mensagens pendentes endereçadas à pessoa são canceladas. Arquivos anexados não são reescritos automaticamente e precisam ser revisados segundo a política de retenção do projeto.
- Atualizações e notificações não são mantidas numa caixa de entrada do sistema. A outbox cifra corpos pendentes com Fernet e apaga assunto/corpo após envio, cancelamento ou falha permanente. Preserve `SINDCOMB_EMAIL_ENCRYPTION_KEY` enquanto houver mensagens pendentes; trocá-la torna esses corpos irrecuperáveis.

## Configuração

Copie `.env.example` para `.env` e substitua todos os valores `CHANGE-ME`. Gere segredos diferentes para cada variável; não versione `.env` nem reutilize `adm123` ou qualquer senha divulgada anteriormente.

1. `SINDCOMB_AUTH_SECRET` (32+ caracteres), `SINDCOMB_EMAIL_ENCRYPTION_KEY` (chave Fernet), `SINDCOMB_ML_API_KEY` e `POSTGRES_PASSWORD` com valores aleatórios exclusivos.
2. `SINDCOMB_BOOTSTRAP_ADMIN_PASSWORD` provisiona `adm_sindcomb` apenas na primeira inicialização e precisa ter de 16 a 128 caracteres. A conta não armazena e-mail ou contato; a senha não pode ser alterada pela aplicação. Em produção, se o banco ainda tiver a senha conhecida de desenvolvimento, a API não inicia.
3. `SINDCOMB_ENVIRONMENT=production` habilita validações fortes e desativa `/docs`, `/redoc` e `/openapi.json`. Configure `SINDCOMB_CORS_ORIGINS` com origens HTTPS explícitas e URLs públicas HTTPS.
5. `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_FROM` e `SMTP_STARTTLS` para confirmação de e-mail e avisos. E-mails pendentes são repetidos com intervalo exponencial até `SINDCOMB_EMAIL_MAX_ATTEMPTS` (padrão 8).
6. `SINDCOMB_PUBLIC_API_URL` e `SINDCOMB_PUBLIC_APP_URL` para os links de confirmação e recuperação.
7. `DATAJUD_API_KEY` para consulta pública do CNJ. Quando o DataJud não localiza o processo, o backend consulta também a API pública do DJEN/CNJ, sem credencial comercial.
8. `SINDCOMB_SYNC_INTERVAL_MINUTES` e `SINDCOMB_SYNC_FAILURE_RETRY_MINUTES` controlam os ciclos automáticos.

As rotas de login, verificação, recuperação de senha e interpretação por IA usam limites distribuídos pelo Redis. Se o Redis estiver indisponível, essas rotas respondem `503` em vez de ignorar o controle. Configure também limites no proxy reverso e encaminhe endereços de cliente somente de proxies confiáveis.

O banco é PostgreSQL e a aplicação usa `DATABASE_URL` com `psycopg`. O bootstrap cria as tabelas canônicas e adiciona os campos da aplicação ao esquema PostgreSQL exportado. O agente Qwen continua responsável por classificar o contexto e interpretar movimentações; sua porta não é publicada no host. A movimentação e os e-mails correspondentes entram na mesma transação; se o SMTP estiver indisponível, a alteração continua salva e os envios permanecem na fila para novas tentativas.

O SQL exportado não contém registros. Em volume PostgreSQL já existente, os scripts de `/docker-entrypoint-initdb.d` não rodam novamente; consulte `backend/database/README.md` para aplicar o esquema manualmente.

O dump habilita RLS, mas não define políticas PostgreSQL. O backend usa uma conta proprietária das tabelas, que pode ignorar RLS; mantenha as verificações de autorização da API e não exponha o usuário de banco a clientes. Consulte `docs/seguranca-backend.md` antes de implantar.

## Fluxo de login

1. `POST /api/v1/auth/login` recebe `usuario` e `senha`. O administrador usa `adm_sindcomb`; advogados continuam usando o e-mail cadastrado. Para compatibilidade, a API também aceita o campo legado `email` para advogados.
2. Advogados precisam confirmar o e-mail antes de entrar. O administrador usa o login fixo e não depende de e-mail.
3. Advogados recém-cadastrados confirmam o e-mail e usam “Esqueci minha senha” para definir uma senha pessoal. Contas legadas com `alterar_senha_no_primeiro_acesso=true` devem usar `POST /api/v1/auth/alterar-senha`, enviando `senha_atual` e `nova_senha` (mínimo 12 caracteres). Para administradores, essa rota responde `403` e a senha não é alterada.
4. A API grava o JWT em cookie `HttpOnly`, `SameSite=Strict` e `Secure` em produção. A interface recebe apenas um token CSRF e o envia em `X-CSRF-Token` para operações que alteram dados. Use frontend e API sob o mesmo site HTTPS.

## Endpoints

- `POST /api/v1/auth/login`, `GET /api/v1/auth/me`, `GET /api/v1/auth/csrf`, `POST /api/v1/auth/logout`, `GET /api/v1/auth/verificar-email?token=...`, `POST /api/v1/auth/verificar-email`, `POST /api/v1/auth/alterar-senha`, `POST /api/v1/auth/solicitar-recuperacao-senha` e `POST /api/v1/auth/redefinir-senha`.
- `GET/POST /api/v1/admin/advogados`; `PATCH /api/v1/admin/advogados/{usuario_id}` para alterar nome/OAB ou ativar/desativar; `POST /api/v1/admin/advogados/{usuario_id}/reenviar-verificacao`; `DELETE /api/v1/admin/advogados/{usuario_id}` para apagar o cadastro e anonimizar referências associadas.
- `GET/POST /api/v1/admin/associados`; `PATCH /api/v1/admin/associados/{associado_id}`; `DELETE /api/v1/admin/associados/{associado_id}`. Associados são somente contatos/partes, não usuários.
- `POST /api/v1/processos/triagem` — advogado informa o número CNJ; o backend consulta DataJud e, se não houver resultado exato, busca publicações no DJEN/CNJ antes de fazer a triagem contextual. A resposta é genérica para não revelar se aquele processo já é acompanhado no sistema; consulte a lista de processos para verificar seu acesso.
- `POST /api/v1/processos/sincronizar` — advogado sincroniza os processos em que tem permissão de edição pelas fontes configuradas; movimentação nova passa pelo agente e entra na fila de e-mails.
- `GET /api/v1/processos/{id}/sincronizacoes` — consulta o histórico recente de tentativas e resultados daquele processo.
- `GET /api/v1/processos?arquivado=false` e `GET /api/v1/processos?arquivado=true` — lista ativa e arquivo, respectivamente; o padrão é `false`.
- `GET /api/v1/processos/{id}` — consulta um processo.
- `POST /api/v1/processos/{id}/arquivar` e `POST /api/v1/processos/{id}/desarquivar` — arquiva processo encerrado ou reativa seu acompanhamento. As ações exigem advogado com permissão de edição e deixam registro na auditoria do processo.
- `PATCH /api/v1/processos/{id}/status` — somente advogado; registra histórico e envia aviso por e-mail.
- `POST /api/v1/processos/{id}/movimentacoes` — somente advogado; agente resume/classifica e o sistema avisa os contatos vinculados.
- `POST /api/v1/processos/interpretar-movimentacao` — usuário autenticado; análise avulsa sem gravar ou enviar notificação.

No cadastro do processo, envie apenas `{"numero":"<número CNJ real>"}` para `POST /api/v1/processos/triagem`. O sistema aceita os 20 dígitos ou o formato CNJ `NNNNNNN-DD.AAAA.J.TR.OOOO`; números sem pontuação são formatados ao salvar e os já formatados são preservados. O endpoint do tribunal é inferido dos campos `J/TR`. A busca DataJud usa os 20 dígitos sem pontuação, como exige o campo `numeroProcesso` da API. Se o DataJud responder sem um resultado exato para o CNJ, o backend consulta a API pública de comunicações do DJEN/CNJ pelo número do processo. Uma falha HTTP ou de rede é registrada como falha e não é tratada como processo inexistente. A resposta da triagem continua genérica por segurança; quando incluído, o processo aparece na lista do advogado.

O DJEN é uma fonte oficial complementar de publicações e comunicações processuais; ele não é uma cópia integral dos autos e não fornece, por si só, todas as peças e documentos do processo. O sistema registra a fonte em `dados.origem_dados` e nas movimentações, a hora da consulta em `dados.consultado_em`, e apresenta um link para a certidão do DJEN ou para a consulta oficial. O DJEN não garante acesso a processos sigilosos, peças ou documentos que não tenham sido publicados. Confira informações completas no sistema do tribunal. A origem, as datas e o link aparecem nos cartões de processo.

Referências oficiais: [API Pública do DataJud (CNJ)](https://www.cnj.jus.br/sistemas/datajud/api-publica/), [documentação da API do DJEN](https://hcomunicaapi.cnj.jus.br/swagger/index.html) e [Modelo Nacional de Interoperabilidade (CNJ)](https://www.cnj.jus.br/category/acoes-e-programas/modelo-nacional-de-interoperabilidade-versao/).

Com os metadados retornados, o backend compara os nomes em `associados_mencionados` e `partes` com o cadastro de associados, ignorando caixa e acentos. Também vincula o advogado criador e advogados citados que correspondam ao nome/OAB cadastrado. Os e-mails de quem foi vinculado ao processo são usados como destinatários.

A API inicia um ciclo automático após `SINDCOMB_SYNC_INITIAL_DELAY_SECONDS` (padrão 30 segundos) e repete a cada `SINDCOMB_SYNC_INTERVAL_MINUTES`. As consultas ao DataJud e, quando necessário, ao DJEN repetem falhas temporárias de rede, HTTP 408, 429 e 5xx, com backoff exponencial, até `SINDCOMB_SYNC_MAX_ATTEMPTS`. Se um ciclo tiver falhas, o worker tenta novamente após `SINDCOMB_SYNC_FAILURE_RETRY_MINUTES`. O Redis coordena o lock entre instâncias; o histórico de cada processo fica em `sincronizacao` e pode ser consultado pela API.

Processos arquivados não entram na sincronização automática. Para alterar status, movimentações, documentos, petições ou prazos de um processo arquivado, um advogado com permissão de edição deve desarquivá-lo primeiro. O arquivamento não exclui dados, documentos, prazos ou histórico.

O mesmo worker verifica a fila persistente de e-mails a cada `SINDCOMB_WORKER_POLL_SECONDS`. Cada destinatário é uma unidade separada, então falha de um endereço não repete envios que já deram certo para outros. A resposta `email_verificacao_enviado` significa que a mensagem foi enfileirada, não que o servidor SMTP já confirmou a entrega.

## Documentos, petições e prazos

Os recursos do processo usam a permissão gravada em `permissao_processo`. Administradores não podem acessar esses endpoints. Advogados com nível `edicao` ou `total` podem cadastrar e alterar documentos, petições e prazos; uma permissão `leitura` só permite consulta e download.

### Documentos

- `GET/POST /api/v1/processos/{processo_id}/documentos` lista ou envia arquivo.
- `GET /api/v1/documentos/{documento_id}/download` baixa o arquivo após verificar a permissão no processo.
- `DELETE /api/v1/documentos/{documento_id}` remove o arquivo e registra auditoria.
- Tipos aceitos: PDF, DOC, DOCX, TXT, PNG e JPEG. O limite padrão é 20 MB (`SINDCOMB_MAX_UPLOAD_MB`, máximo configurável de 100 MB).
- Os arquivos ficam no volume Docker `backend_uploads`, em `/app/storage`; o banco mantém somente metadados, hash SHA-256 e caminho relativo.

### Petições

- `GET/POST /api/v1/processos/{processo_id}/peticoes` lista ou cria uma petição.
- `GET/PATCH /api/v1/peticoes/{peticao_id}` consulta ou edita o rascunho.
- `GET /api/v1/peticoes/{peticao_id}/versoes` consulta os snapshots imutáveis de conteúdo.
- `POST /api/v1/peticoes/{peticao_id}/status` aplica as transições de revisão, aprovação, rejeição e protocolo.
- `GET /api/v1/peticoes/{peticao_id}/exportar?formato=docx` ou `formato=pdf` gera arquivo para download.
- Modelos são gerenciados em `GET/POST /api/v1/peticoes/modelos`, `PATCH/DELETE /api/v1/peticoes/modelos/{modelo_id}`. Variáveis aceitas incluem `{{processo_numero}}`, `{{processo_tribunal}}`, `{{processo_classe}}`, `{{processo_assunto}}`, `{{associado_nome}}`, `{{advogado_nome}}`, `{{advogado_oab}}`, `{{vara}}` e `{{comarca}}`. Variáveis sem informação correspondente permanecem como marcadores para revisão humana.
- Cada edição de conteúdo diferente cria uma nova versão. A aprovação exige que a petição esteja em revisão; petições aprovadas só podem avançar para protocoladas.
- Quando um advogado é excluído, autoria de petições, versões e prazos fica sem vínculo de usuário, preservando o histórico jurídico sem manter a identidade no cadastro.

As tabelas existentes `peticao` e `documento` são mapeadas pelos modelos ORM. `versao_peticao` e `modelo_peticao` são tabelas auxiliares criadas pelo bootstrap do SQLAlchemy nos bancos existentes.

### Prazos

- `GET /api/v1/prazos` lista prazos dos processos aos quais o usuário tem acesso; aceita `status` e `somente_atrasados`.
- `GET/POST /api/v1/processos/{processo_id}/prazos` lista ou cria prazo vinculado ao processo.
- `GET /api/v1/processos/{processo_id}/prazos/responsaveis` lista advogados ativos com permissão de edição no processo, para selecionar o responsável.
- `PATCH/DELETE /api/v1/prazos/{prazo_id}` atualiza ou exclui o prazo, registrando auditoria.
- O responsável precisa ser advogado ativo com permissão de edição naquele processo. Se o cadastro do advogado for excluído, o prazo permanece sem vínculo de responsável até ser reatribuído. A resposta informa `atrasado` e `dias_restantes`.
- A lista e o sinalizador de atraso estão disponíveis; o envio automático de lembretes por data ainda depende de uma regra de negócio para antecedência e destinatário.

## Cadastro de advogado para teste

No Swagger (`/docs`), autentique-se como administrador e use `POST /api/v1/admin/advogados`. Exemplo de dados fictícios:

```json
{
  "nome": "Advogado de Teste",
  "email": "advogado.teste@example.com",
  "oab": "SP/000000-T"
}
```

`example.com` é um endereço reservado para exemplos e não recebe e-mails de uma pessoa real. Portanto, este exemplo serve apenas para preencher o formulário: para testar confirmação, login e definição de senha de ponta a ponta, substitua-o por uma caixa de e-mail acessível. A API mantém `email_verificado=false` até a confirmação e não oferece bypass para contas de teste. Após confirmar, use “Esqueci minha senha” para criar a senha pessoal.

A busca periódica por nome de parte não está implementada. Confirme movimentações e prazos na fonte oficial.
