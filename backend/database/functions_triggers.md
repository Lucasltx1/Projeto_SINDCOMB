```SQL
-- SINDCOMB / ADP2 | 04 - TESTE DAS 3 FUNCTIONS E 3 PROCEDURES
-- Todos os INSERT/UPDATE de teste serao revertidos pelo ROLLBACK.
-- Executar no SQL Editor como dono APOS 02 e 03 (e massa de teste).
-- Para testes confiaveis, execute o arquivo inteiro numa unica consulta.
BEGIN;
DO $teste$
DECLARE
  v_processo_ativo BIGINT;
  v_processo_encerrado BIGINT;
  v_prazo_pendente BIGINT;
  v_prazo_cancelado BIGINT;
  v_id_usuario BIGINT;
  v_total BIGINT;
  v_nivel TEXT;
  v_erro TEXT;
BEGIN
  SELECT id_processo INTO STRICT v_processo_ativo
  FROM public.processo WHERE numero_processo='SINDCOMB-TESTE-2026-0001';
  SELECT id_processo INTO STRICT v_processo_encerrado
  FROM public.processo WHERE numero_processo='SINDCOMB-TESTE-2026-0016';
  SELECT pr.id_prazo INTO STRICT v_prazo_pendente
  FROM public.prazo AS pr
  JOIN public.processo AS p ON p.id_processo=pr.id_processo
  WHERE p.numero_processo='SINDCOMB-TESTE-2026-0002'
    AND pr.descricao='[MASSA SINDCOMB] Prazo ficticio 02';
  SELECT pr.id_prazo INTO STRICT v_prazo_cancelado
  FROM public.prazo AS pr
  JOIN public.processo AS p ON p.id_processo=pr.id_processo
  WHERE p.numero_processo='SINDCOMB-TESTE-2026-0004'
    AND pr.descricao='[MASSA SINDCOMB] Prazo ficticio 04';
  SELECT id_usuario INTO STRICT v_id_usuario
  FROM public.usuario WHERE email='sindcomb.teste.usuario.01@example.invalid';

  IF NOT EXISTS (SELECT 1 FROM public.processo WHERE id_processo=v_processo_ativo
                 AND status='ativo' AND arquivado IS FALSE) THEN
     RAISE EXCEPTION 'Fixture ativo ausente/alterado: processo 0001';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.processo WHERE id_processo=v_processo_encerrado
                 AND status='encerrado' AND arquivado IS FALSE) THEN
     RAISE EXCEPTION 'Fixture encerrado ausente/alterado: processo 0016';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.prazo WHERE id_prazo=v_prazo_pendente
                 AND status='pendente') THEN
     RAISE EXCEPTION 'Fixture prazo pendente 02 foi alterado';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM public.prazo WHERE id_prazo=v_prazo_cancelado
                 AND status='cancelado') THEN
     RAISE EXCEPTION 'Fixture prazo cancelado 04 foi alterado';
  END IF;

  -- F1
  SELECT public.contar_processos_ativos() INTO v_total;
  IF v_total <> (SELECT COUNT(*) FROM public.processo
                WHERE status='ativo' AND arquivado IS FALSE) THEN
      RAISE EXCEPTION 'FALHA FUNCTION contar_processos_ativos';
  END IF;
  RAISE NOTICE 'PASS F1 - contar_processos_ativos: %', v_total;

  -- F2
  SELECT public.contar_prazos_pendentes((SELECT id_processo FROM public.prazo
    WHERE id_prazo=v_prazo_pendente)) INTO v_total;
  IF v_total <> (SELECT COUNT(*) FROM public.prazo
                WHERE id_processo=(SELECT id_processo FROM public.prazo WHERE id_prazo=v_prazo_pendente)
                  AND status='pendente') THEN
      RAISE EXCEPTION 'FALHA FUNCTION contar_prazos_pendentes';
  END IF;
  RAISE NOTICE 'PASS F2 - contar_prazos_pendentes: %', v_total;

  -- F3
  SELECT public.consultar_nivel_acesso(v_id_usuario,v_processo_ativo)
  INTO v_nivel;
  IF v_nivel IS DISTINCT FROM 'leitura' THEN
      RAISE EXCEPTION 'FALHA FUNCTION consultar_nivel_acesso: %', v_nivel;
  END IF;
  RAISE NOTICE 'PASS F3 - consultar_nivel_acesso: %', v_nivel;

  -- P1 positivo
  CALL public.arquivar_processo(v_processo_encerrado);
  IF NOT EXISTS (SELECT 1 FROM public.processo WHERE id_processo=v_processo_encerrado
                 AND arquivado IS TRUE) THEN
    RAISE EXCEPTION 'FALHA PROCEDURE arquivar_processo';
  END IF;
  RAISE NOTICE 'PASS P1 - arquivar_processo';

  -- P1 negativo: ativo nao pode ser arquivado
  BEGIN
    CALL public.arquivar_processo(v_processo_ativo);
    RAISE EXCEPTION 'FALHA: arquivamento indevido de processo ativo permitido';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS v_erro = MESSAGE_TEXT;
    IF v_erro NOT LIKE '%Somente processos encerrados%' THEN RAISE; END IF;
    RAISE NOTICE 'PASS P1 negativo - ativo nao arquivado';
  END;

  -- P2 positivo
  CALL public.concluir_prazo(v_prazo_pendente);
  IF NOT EXISTS (SELECT 1 FROM public.prazo WHERE id_prazo=v_prazo_pendente
                 AND status='concluido') THEN
    RAISE EXCEPTION 'FALHA PROCEDURE concluir_prazo';
  END IF;
  RAISE NOTICE 'PASS P2 - concluir_prazo';

  -- P2 negativo: cancelado nao deve ser concluido
  BEGIN
    CALL public.concluir_prazo(v_prazo_cancelado);
    RAISE EXCEPTION 'FALHA: prazo cancelado concluido indevidamente';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS v_erro = MESSAGE_TEXT;
    IF v_erro NOT LIKE '%Somente prazos pendentes%' THEN RAISE; END IF;
    RAISE NOTICE 'PASS P2 negativo - cancelado protegido';
  END;

  -- P3 positivo
  CALL public.registrar_movimentacao(
    v_processo_ativo, '[TESTE ROLLBACK] movimentacao autorizada',
    'teste', v_id_usuario, 'manual'
  );
  IF NOT EXISTS (SELECT 1 FROM public.linha_tempo
                 WHERE id_processo=v_processo_ativo
                   AND descricao='[TESTE ROLLBACK] movimentacao autorizada') THEN
    RAISE EXCEPTION 'FALHA PROCEDURE registrar_movimentacao';
  END IF;
  RAISE NOTICE 'PASS P3 - registrar_movimentacao';

  -- P3 negativo: processo arquivado
  BEGIN
    CALL public.registrar_movimentacao(v_processo_encerrado,
      '[TESTE ROLLBACK] nao deve inserir','teste',NULL,'manual');
    RAISE EXCEPTION 'FALHA: movimentacao em processo arquivado foi permitida';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS v_erro = MESSAGE_TEXT;
    IF v_erro NOT LIKE '%Processo arquivado%' THEN RAISE; END IF;
    RAISE NOTICE 'PASS P3 negativo - processo arquivado protegido';
  END;
END;
$teste$;
ROLLBACK;
SELECT 'PASS: 3 FUNCTIONS + 3 PROCEDURES, incluindo casos negativos. Dados preservados com ROLLBACK.' AS resultado;
```


| resultado                                                                                    |
| -------------------------------------------------------------------------------------------- |
| PASS: 3 FUNCTIONS + 3 PROCEDURES, incluindo casos negativos. Dados preservados com ROLLBACK. |





```SQL
-- SINDCOMB / ADP2 | 05 - TESTES POSITIVOS E NEGATIVOS DOS 3 TRIGGERS
-- Executar apos 02_rotinas_triggers_adp2.sql. Nenhuma mudanca persistira.
BEGIN;
DO $teste$
DECLARE
  v_processo BIGINT;
  v_prazo BIGINT;
  v_usuario BIGINT;
  v_erro TEXT;
BEGIN
  SELECT id_processo INTO STRICT v_processo
  FROM public.processo WHERE numero_processo='SINDCOMB-TESTE-2026-0001';
  SELECT id_usuario INTO STRICT v_usuario
  FROM public.usuario WHERE email='sindcomb.teste.usuario.01@example.invalid';
  SELECT id_prazo INTO STRICT v_prazo
  FROM public.prazo WHERE id_processo=v_processo
    AND descricao='[MASSA SINDCOMB] Prazo ficticio 01';

  -- T1 negativo: nao pode arquivar ativo
  BEGIN
    UPDATE public.processo SET arquivado=TRUE WHERE id_processo=v_processo;
    RAISE EXCEPTION 'FALHA T1: processo ativo arquivado';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS v_erro = MESSAGE_TEXT;
    IF v_erro NOT LIKE '%Somente processos encerrados%' THEN RAISE; END IF;
    RAISE NOTICE 'PASS T1 negativo - arquivamento invalido bloqueado';
  END;

  -- T1 positivo: encerrar e arquivar na mesma transacao
  UPDATE public.processo SET status='encerrado', arquivado=TRUE,
    data_encerramento=CURRENT_DATE WHERE id_processo=v_processo;
  IF NOT EXISTS (SELECT 1 FROM public.processo WHERE id_processo=v_processo
    AND status='encerrado' AND arquivado=TRUE) THEN
    RAISE EXCEPTION 'FALHA T1 positivo';
  END IF;
  RAISE NOTICE 'PASS T1 positivo';

  -- T2 negativo: status nao aceito
  BEGIN
    UPDATE public.prazo SET status='invalido' WHERE id_prazo=v_prazo;
    RAISE EXCEPTION 'FALHA T2: prazo invalido aceito';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS v_erro = MESSAGE_TEXT;
    IF v_erro NOT LIKE '%Status de prazo invalido%' THEN RAISE; END IF;
    RAISE NOTICE 'PASS T2 negativo - status invalido bloqueado';
  END;

  -- T2 positivo: prazo pendente pode ser concluido
  UPDATE public.prazo SET status='concluido' WHERE id_prazo=v_prazo;
  IF NOT EXISTS (SELECT 1 FROM public.prazo WHERE id_prazo=v_prazo
                 AND status='concluido') THEN
    RAISE EXCEPTION 'FALHA T2 positivo';
  END IF;
  RAISE NOTICE 'PASS T2 positivo';

  -- T2 negativo complementar: nao reabre prazo concluido
  BEGIN
    UPDATE public.prazo SET status='pendente' WHERE id_prazo=v_prazo;
    RAISE EXCEPTION 'FALHA T2: prazo concluido reaberto';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS v_erro = MESSAGE_TEXT;
    IF v_erro NOT LIKE '%Prazo finalizado ou cancelado%' THEN RAISE; END IF;
    RAISE NOTICE 'PASS T2 negativo - reabertura de prazo bloqueada';
  END;

  -- T3 negativo: descricao em branco
  BEGIN
    INSERT INTO public.linha_tempo(id_processo,id_usuario,descricao,tipo_evento,origem)
    VALUES(v_processo,v_usuario,'   ','teste','manual');
    RAISE EXCEPTION 'FALHA T3: descricao vazia aceita';
  EXCEPTION WHEN OTHERS THEN
    GET STACKED DIAGNOSTICS v_erro = MESSAGE_TEXT;
    IF v_erro NOT LIKE '%Descricao da movimentacao nao pode ser vazia%' THEN RAISE; END IF;
    RAISE NOTICE 'PASS T3 negativo - descricao vazia bloqueada';
  END;

  -- T3 positivo: movimentacao valida
  INSERT INTO public.linha_tempo(id_processo,id_usuario,descricao,tipo_evento,origem)
  VALUES(v_processo,v_usuario,'[TESTE ROLLBACK] evento valido','teste','manual');
  IF NOT EXISTS (SELECT 1 FROM public.linha_tempo
                 WHERE id_processo=v_processo
                   AND descricao='[TESTE ROLLBACK] evento valido') THEN
    RAISE EXCEPTION 'FALHA T3 positivo';
  END IF;
  RAISE NOTICE 'PASS T3 positivo';
END;
$teste$;
ROLLBACK;
SELECT 'PASS: 3 TRIGGERS testados nos cenarios validos e invalidos. Dados preservados com ROLLBACK.' AS resultado;
```

| resultado                                                                                   |
| ------------------------------------------------------------------------------------------- |
| PASS: 3 TRIGGERS testados nos cenarios validos e invalidos. Dados preservados com ROLLBACK. |






```SQL
-- SINDCOMB | 08 - EVIDENCIAS DO CATALOGO (ADP1/2/3)
-- Use para capturas de tela apos instalar os scripts.

-- Tabelas: 16 esperadas.
SELECT table_name FROM information_schema.tables
WHERE table_schema='public' AND table_type='BASE TABLE'
  AND table_name IN ('usuario','administrador','juridico','associado','processo',
   'processo_associado','linha_tempo','documento','prazo','peticao','notificacao',
   'usuario_notificacao','associado_notificacao','permissao_processo',
   'auditoria','sincronizacao')
ORDER BY table_name;

-- Funcoes/procedures: 3 + 3, desconsiderando helpers e trigger functions.
SELECT p.proname AS rotina, CASE p.prokind
    WHEN 'p' THEN 'PROCEDURE' WHEN 'f' THEN 'FUNCTION' ELSE 'OUTRA' END AS tipo,
    pg_catalog.pg_get_function_identity_arguments(p.oid) AS parametros
FROM pg_catalog.pg_proc p
JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
WHERE n.nspname='public' AND p.proname IN
  ('contar_processos_ativos','contar_prazos_pendentes','consultar_nivel_acesso',
   'arquivar_processo','concluir_prazo','registrar_movimentacao')
ORDER BY tipo, rotina;

-- Triggers ativos: 3 esperados.
SELECT c.relname AS tabela, t.tgname AS trigger, NOT t.tgisinternal AS nao_interno
FROM pg_catalog.pg_trigger AS t
JOIN pg_catalog.pg_class AS c ON c.oid=t.tgrelid
JOIN pg_catalog.pg_namespace AS n ON n.oid=c.relnamespace
WHERE n.nspname='public' AND t.tgname IN
  ('tr_validar_arquivamento','tr_validar_status_prazo','tr_validar_movimentacao')
  AND NOT t.tgisinternal
ORDER BY tabela;

-- Relacionamentos por chave estrangeira (FK).
SELECT con.conname AS restricao_fk, con.conrelid::regclass AS origem,
  con.confrelid::regclass AS destino
FROM pg_catalog.pg_constraint AS con
WHERE con.contype='f' AND con.connamespace='public'::regnamespace
ORDER BY origem, restricao_fk;

-- Qualidade dos dados de exemplo.
SELECT status, COUNT(*) AS quantidade FROM public.processo GROUP BY status ORDER BY status;
SELECT status, COUNT(*) AS quantidade FROM public.prazo GROUP BY status ORDER BY status;
SELECT nivel_acesso, COUNT(*) AS quantidade FROM public.permissao_processo
GROUP BY nivel_acesso ORDER BY nivel_acesso;
```


| nivel_acesso | quantidade |
| ------------ | ---------- |
| edicao       | 8          |
| leitura      | 8          |
| total        | 4          |
