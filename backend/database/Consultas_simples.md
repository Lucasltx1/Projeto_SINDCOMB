-- SINDCOMB / ADP1 | 01 - 5 consultas simples, 3 JOINs e 3 subconsultas.
-- Consultas de leitura. Execute no SQL Editor e registre resultados.

-- S1 - Usuarios ativos
SELECT id_usuario, nome, email, primeiro_acesso
FROM public.usuario WHERE ativo IS TRUE ORDER BY id_usuario LIMIT 40;

-- S2 - Processos nao arquivados
SELECT id_processo, numero_processo, tipo, status
FROM public.processo WHERE arquivado IS FALSE ORDER BY numero_processo;

-- S3 - Prazos pendentes com vencimento futuro
SELECT id_prazo, id_processo, descricao, data_vencimento
FROM public.prazo WHERE status = 'pendente' AND data_vencimento >= CURRENT_DATE
ORDER BY data_vencimento;

-- S4 - Documentos maiores ou iguais a 1 KiB
SELECT id_documento, nome, tipo, tamanho
FROM public.documento WHERE tamanho >= 1024 ORDER BY tamanho DESC;

-- S5 - Notificacoes nao lidas
SELECT id_notificacao, titulo, data_criacao, status_leitura
FROM public.notificacao WHERE status_leitura = 'nao_lida'
ORDER BY data_criacao DESC;

-- J1 - JOIN + agregacao + agrupamento + filtro: prazos pendentes por processo
SELECT p.numero_processo, COUNT(pr.id_prazo) AS total_prazos_pendentes
FROM public.processo AS p
JOIN public.prazo AS pr ON pr.id_processo = p.id_processo
WHERE pr.status = 'pendente'
GROUP BY p.id_processo, p.numero_processo
HAVING COUNT(pr.id_prazo) >= 1
ORDER BY total_prazos_pendentes DESC, p.numero_processo;

-- J2 - JOIN de tres tabelas: associados vinculados por processo
SELECT p.numero_processo, COUNT(DISTINCT a.id_associado) AS associados_vinculados
FROM public.processo AS p
JOIN public.processo_associado AS pa ON pa.id_processo = p.id_processo
JOIN public.associado AS a ON a.id_associado = pa.id_associado
GROUP BY p.id_processo, p.numero_processo
HAVING COUNT(DISTINCT a.id_associado) > 0
ORDER BY associados_vinculados DESC, p.numero_processo;

-- J3 - JOIN de duas tabelas: processos com permissao de edicao por usuario
SELECT u.nome, COUNT(DISTINCT pp.id_processo) AS processos_editaveis
FROM public.usuario AS u
JOIN public.permissao_processo AS pp ON pp.id_usuario = u.id_usuario
WHERE pp.nivel_acesso IN ('edicao','total')
GROUP BY u.id_usuario, u.nome
HAVING COUNT(DISTINCT pp.id_processo) >= 1
ORDER BY processos_editaveis DESC, u.nome;

-- SUB1 - operador IN: processos com prazo pendente
SELECT p.numero_processo, p.status
FROM public.processo AS p
WHERE p.id_processo IN (
    SELECT pr.id_processo FROM public.prazo AS pr WHERE pr.status = 'pendente'
)
ORDER BY p.numero_processo;

-- SUB2 - operador EXISTS: processos com movimentacao manual
SELECT p.numero_processo, p.assunto
FROM public.processo AS p
WHERE EXISTS (
    SELECT 1 FROM public.linha_tempo AS lt
    WHERE lt.id_processo = p.id_processo AND lt.origem = 'manual'
)
ORDER BY p.numero_processo;

-- SUB3 - operador ALL: prazos posteriores a TODOS os vencimentos do
-- processo de menor ID. A subconsulta contem pelo menos um prazo na massa.
SELECT pr.id_prazo, pr.data_vencimento
FROM public.prazo AS pr
WHERE pr.data_vencimento > ALL (
    SELECT base.data_vencimento
    FROM public.prazo AS base
    WHERE base.id_processo = (SELECT MIN(id_processo) FROM public.processo)
)
ORDER BY pr.data_vencimento;



id_prazo | data_vencimento |
| -------- | --------------- |
| 2        | 2026-11-26      |
| 3        | 2026-11-27      |
| 4        | 2026-11-28      |
| 5        | 2026-11-29      |
| 6        | 2026-11-30      |
| 7        | 2026-12-01      |
| 8        | 2026-12-02      |
| 9        | 2026-12-03      |
| 10       | 2026-12-04      |
| 11       | 2026-12-05      |
| 12       | 2026-12-06      |
| 13       | 2026-12-07      |
| 14       | 2026-12-08      |
| 15       | 2026-12-09      |
| 16       | 2026-12-10      |
| 17       | 2026-12-11      |
| 18       | 2026-12-12      |
| 19       | 2026-12-13      |
| 20       | 2026-12-14      |
