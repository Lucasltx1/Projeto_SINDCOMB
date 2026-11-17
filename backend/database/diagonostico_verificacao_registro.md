-- SINDCOMB / ADP1 | 00 - DIAGNOSTICO PRE-EXECUCAO
-- Nao modifica dados. Rodar no Supabase SQL Editor com permissao de dono.
-- Garante que todas as 16 tabelas estejam presentes e tenham >=20 linhas.
DO $diag$
DECLARE
    v_tabela TEXT;
    v_quantidade BIGINT;
    v_tabelas TEXT[] := ARRAY[
       'usuario','administrador','juridico','associado','processo',
       'processo_associado','linha_tempo','documento','prazo','peticao',
       'notificacao','usuario_notificacao','associado_notificacao',
       'permissao_processo','auditoria','sincronizacao'
    ];
BEGIN
    FOREACH v_tabela IN ARRAY v_tabelas LOOP
        IF to_regclass(format('public.%I', v_tabela)) IS NULL THEN
            RAISE EXCEPTION 'FALHA ADP1: tabela public.% ausente.', v_tabela;
        END IF;
        EXECUTE format('SELECT COUNT(*) FROM public.%I', v_tabela) INTO v_quantidade;
        IF v_quantidade < 20 THEN
            RAISE EXCEPTION 'FALHA ADP1: public.% possui apenas % registros (minimo 20).', v_tabela, v_quantidade;
        END IF;
    END LOOP;
    RAISE NOTICE 'PASS: 16 tabelas presentes, todas com pelo menos 20 registros.';
END;
$diag$;

SELECT 'usuario' AS tabela, COUNT(*) AS registros FROM public.usuario
UNION ALL SELECT 'administrador',COUNT(*) FROM public.administrador
UNION ALL SELECT 'juridico',COUNT(*) FROM public.juridico
UNION ALL SELECT 'associado',COUNT(*) FROM public.associado
UNION ALL SELECT 'processo',COUNT(*) FROM public.processo
UNION ALL SELECT 'processo_associado',COUNT(*) FROM public.processo_associado
UNION ALL SELECT 'linha_tempo',COUNT(*) FROM public.linha_tempo
UNION ALL SELECT 'documento',COUNT(*) FROM public.documento
UNION ALL SELECT 'prazo',COUNT(*) FROM public.prazo
UNION ALL SELECT 'peticao',COUNT(*) FROM public.peticao
UNION ALL SELECT 'notificacao',COUNT(*) FROM public.notificacao
UNION ALL SELECT 'usuario_notificacao',COUNT(*) FROM public.usuario_notificacao
UNION ALL SELECT 'associado_notificacao',COUNT(*) FROM public.associado_notificacao
UNION ALL SELECT 'permissao_processo',COUNT(*) FROM public.permissao_processo
UNION ALL SELECT 'auditoria',COUNT(*) FROM public.auditoria
UNION ALL SELECT 'sincronizacao',COUNT(*) FROM public.sincronizacao
ORDER BY tabela;

-- Verificacoes de consistencia: idealmente 0 linhas nas duas consultas.
SELECT id_usuario, id_processo, COUNT(*) AS repeticoes
FROM public.permissao_processo
GROUP BY id_usuario, id_processo HAVING COUNT(*) > 1;
SELECT id_processo, numero_processo, status, arquivado
FROM public.processo WHERE arquivado IS TRUE AND status <> 'encerrado';




| tabela                | registros |
| --------------------- | --------- |
| administrador         | 20        |
| associado             | 20        |
| associado_notificacao | 20        |
| auditoria             | 20        |
| documento             | 20        |
| juridico              | 20        |
| linha_tempo           | 20        |
| notificacao           | 20        |
| permissao_processo    | 20        |
| peticao               | 20        |
| prazo                 | 20        |
| processo              | 20        |
| processo_associado    | 40        |
| sincronizacao         | 20        |
| usuario               | 40        |
| usuario_notificacao   | 20        |
