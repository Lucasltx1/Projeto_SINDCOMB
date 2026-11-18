--
-- PostgreSQL database dump
--

\restrict 1URI9H642SjbfmDTgPoRUDfZqonWkRIOaHzWv0GUkevggSw3weUcWUemgQrufwN

BEGIN;

-- Dumped from database version 17.11
-- Dumped by pg_dump version 17.11

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA IF NOT EXISTS public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: administrador; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.administrador (
    id_usuario bigint NOT NULL
);


--
-- Name: associado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.associado (
    id_associado bigint NOT NULL,
    nome character varying(150) NOT NULL,
    cpf character varying(14),
    email character varying(255),
    telefone character varying(25)
);


--
-- Name: associado_id_associado_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.associado ALTER COLUMN id_associado ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.associado_id_associado_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: associado_notificacao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.associado_notificacao (
    id_associado bigint NOT NULL,
    id_notificacao bigint NOT NULL,
    data_envio_email timestamp with time zone,
    status_envio character varying(20) DEFAULT 'pendente'::character varying NOT NULL,
    CONSTRAINT associado_notificacao_status_envio_check CHECK (((status_envio)::text = ANY ((ARRAY['pendente'::character varying, 'enviado'::character varying, 'falhou'::character varying])::text[])))
);


--
-- Name: auditoria; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auditoria (
    id_auditoria bigint NOT NULL,
    id_usuario bigint,
    id_processo bigint,
    tipo_operacao character varying(50) NOT NULL,
    descricao text,
    data_hora timestamp with time zone DEFAULT now() NOT NULL,
    resultado character varying(30) NOT NULL
);


--
-- Name: auditoria_id_auditoria_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auditoria ALTER COLUMN id_auditoria ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.auditoria_id_auditoria_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: documento; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.documento (
    id_documento bigint NOT NULL,
    id_processo bigint NOT NULL,
    id_usuario bigint,
    nome character varying(255) NOT NULL,
    tipo character varying(100),
    data_upload timestamp with time zone DEFAULT now() NOT NULL,
    local_armazenamento text NOT NULL,
    tamanho bigint,
    hash_arquivo character varying(128),
    id_peticao bigint,
    CONSTRAINT documento_tamanho_check CHECK (((tamanho IS NULL) OR (tamanho >= 0)))
);


--
-- Name: documento_id_documento_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.documento ALTER COLUMN id_documento ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.documento_id_documento_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: juridico; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.juridico (
    id_usuario bigint NOT NULL,
    oab character varying(30) NOT NULL
);


--
-- Name: linha_tempo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.linha_tempo (
    id_evento bigint NOT NULL,
    id_processo bigint NOT NULL,
    id_usuario bigint,
    data_hora timestamp with time zone DEFAULT now() NOT NULL,
    descricao text NOT NULL,
    tipo_evento character varying(50) NOT NULL,
    origem character varying(30) NOT NULL,
    CONSTRAINT linha_tempo_origem_check CHECK (((origem)::text = ANY ((ARRAY['manual'::character varying, 'automatico'::character varying])::text[])))
);


--
-- Name: linha_tempo_id_evento_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.linha_tempo ALTER COLUMN id_evento ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.linha_tempo_id_evento_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: notificacao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notificacao (
    id_notificacao bigint NOT NULL,
    titulo character varying(200) NOT NULL,
    mensagem text NOT NULL,
    data_criacao timestamp with time zone DEFAULT now() NOT NULL,
    status_leitura character varying(20) DEFAULT 'nao_aplicavel'::character varying NOT NULL,
    data_envio_email timestamp with time zone,
    id_prazo bigint,
    CONSTRAINT notificacao_status_leitura_check CHECK (((status_leitura)::text = ANY ((ARRAY['nao_aplicavel'::character varying, 'nao_lida'::character varying, 'lida'::character varying])::text[])))
);


--
-- Name: notificacao_id_notificacao_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.notificacao ALTER COLUMN id_notificacao ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.notificacao_id_notificacao_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: permissao_processo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.permissao_processo (
    id_permissao bigint NOT NULL,
    id_usuario bigint NOT NULL,
    id_processo bigint NOT NULL,
    nivel_acesso character varying(30) NOT NULL,
    data_concessao timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT permissao_processo_nivel_acesso_check CHECK (((nivel_acesso)::text = ANY ((ARRAY['leitura'::character varying, 'edicao'::character varying, 'total'::character varying])::text[])))
);


--
-- Name: permissao_processo_id_permissao_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.permissao_processo ALTER COLUMN id_permissao ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.permissao_processo_id_permissao_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: peticao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.peticao (
    id_peticao bigint NOT NULL,
    id_processo bigint NOT NULL,
    id_usuario bigint,
    tipo character varying(100) NOT NULL,
    descricao text,
    data_peticao timestamp with time zone DEFAULT now() NOT NULL,
    status character varying(30) DEFAULT 'rascunho'::character varying NOT NULL
);


--
-- Name: peticao_id_peticao_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.peticao ALTER COLUMN id_peticao ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.peticao_id_peticao_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: prazo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.prazo (
    id_prazo bigint NOT NULL,
    id_processo bigint NOT NULL,
    id_usuario bigint,
    descricao text NOT NULL,
    data_inicio date,
    data_vencimento date NOT NULL,
    status character varying(30) DEFAULT 'pendente'::character varying NOT NULL,
    CONSTRAINT prazo_check CHECK (((data_inicio IS NULL) OR (data_inicio <= data_vencimento)))
);


--
-- Name: prazo_id_prazo_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.prazo ALTER COLUMN id_prazo ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.prazo_id_prazo_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: processo; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.processo (
    id_processo bigint NOT NULL,
    numero_processo character varying(50) NOT NULL,
    tipo character varying(100),
    assunto text,
    status character varying(30) DEFAULT 'ativo'::character varying NOT NULL,
    data_abertura date DEFAULT CURRENT_DATE NOT NULL,
    data_encerramento date,
    arquivado boolean DEFAULT false NOT NULL,
    CONSTRAINT processo_check CHECK (((data_encerramento IS NULL) OR (data_encerramento >= data_abertura)))
);


--
-- Name: processo_associado; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.processo_associado (
    id_processo bigint NOT NULL,
    id_associado bigint NOT NULL
);


--
-- Name: processo_id_processo_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.processo ALTER COLUMN id_processo ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.processo_id_processo_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: sincronizacao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.sincronizacao (
    id_sincronizacao bigint NOT NULL,
    id_processo bigint,
    data_hora timestamp with time zone DEFAULT now() NOT NULL,
    status character varying(30) NOT NULL,
    descricao text,
    quantidade_atualizacoes integer DEFAULT 0 NOT NULL,
    CONSTRAINT sincronizacao_quantidade_atualizacoes_check CHECK ((quantidade_atualizacoes >= 0))
);


--
-- Name: sincronizacao_id_sincronizacao_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.sincronizacao ALTER COLUMN id_sincronizacao ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.sincronizacao_id_sincronizacao_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: usuario; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario (
    id_usuario bigint NOT NULL,
    nome character varying(150) NOT NULL,
    email character varying(255) NOT NULL,
    senha text NOT NULL,
    primeiro_acesso boolean DEFAULT true NOT NULL,
    ativo boolean DEFAULT true NOT NULL
);


--
-- Name: usuario_id_usuario_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.usuario ALTER COLUMN id_usuario ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.usuario_id_usuario_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: usuario_notificacao; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.usuario_notificacao (
    id_usuario bigint NOT NULL,
    id_notificacao bigint NOT NULL,
    data_leitura timestamp with time zone,
    status_leitura character varying(20) DEFAULT 'nao_lida'::character varying NOT NULL,
    CONSTRAINT usuario_notificacao_status_leitura_check CHECK (((status_leitura)::text = ANY ((ARRAY['nao_lida'::character varying, 'lida'::character varying])::text[])))
);


--
-- Name: administrador administrador_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrador
    ADD CONSTRAINT administrador_pkey PRIMARY KEY (id_usuario);


--
-- Name: associado associado_cpf_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.associado
    ADD CONSTRAINT associado_cpf_key UNIQUE (cpf);


--
-- Name: associado_notificacao associado_notificacao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.associado_notificacao
    ADD CONSTRAINT associado_notificacao_pkey PRIMARY KEY (id_associado, id_notificacao);


--
-- Name: associado associado_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.associado
    ADD CONSTRAINT associado_pkey PRIMARY KEY (id_associado);


--
-- Name: auditoria auditoria_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria
    ADD CONSTRAINT auditoria_pkey PRIMARY KEY (id_auditoria);


--
-- Name: documento documento_hash_arquivo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento
    ADD CONSTRAINT documento_hash_arquivo_key UNIQUE (hash_arquivo);


--
-- Name: documento documento_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento
    ADD CONSTRAINT documento_pkey PRIMARY KEY (id_documento);


--
-- Name: juridico juridico_oab_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.juridico
    ADD CONSTRAINT juridico_oab_key UNIQUE (oab);


--
-- Name: juridico juridico_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.juridico
    ADD CONSTRAINT juridico_pkey PRIMARY KEY (id_usuario);


--
-- Name: linha_tempo linha_tempo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.linha_tempo
    ADD CONSTRAINT linha_tempo_pkey PRIMARY KEY (id_evento);


--
-- Name: notificacao notificacao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notificacao
    ADD CONSTRAINT notificacao_pkey PRIMARY KEY (id_notificacao);


--
-- Name: permissao_processo permissao_processo_id_usuario_id_processo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissao_processo
    ADD CONSTRAINT permissao_processo_id_usuario_id_processo_key UNIQUE (id_usuario, id_processo);


--
-- Name: permissao_processo permissao_processo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissao_processo
    ADD CONSTRAINT permissao_processo_pkey PRIMARY KEY (id_permissao);


--
-- Name: peticao peticao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peticao
    ADD CONSTRAINT peticao_pkey PRIMARY KEY (id_peticao);


--
-- Name: prazo prazo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prazo
    ADD CONSTRAINT prazo_pkey PRIMARY KEY (id_prazo);


--
-- Name: processo_associado processo_associado_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processo_associado
    ADD CONSTRAINT processo_associado_pkey PRIMARY KEY (id_processo, id_associado);


--
-- Name: processo processo_numero_processo_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processo
    ADD CONSTRAINT processo_numero_processo_key UNIQUE (numero_processo);


--
-- Name: processo processo_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processo
    ADD CONSTRAINT processo_pkey PRIMARY KEY (id_processo);


--
-- Name: sincronizacao sincronizacao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sincronizacao
    ADD CONSTRAINT sincronizacao_pkey PRIMARY KEY (id_sincronizacao);


--
-- Name: usuario usuario_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_email_key UNIQUE (email);


--
-- Name: usuario_notificacao usuario_notificacao_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_notificacao
    ADD CONSTRAINT usuario_notificacao_pkey PRIMARY KEY (id_usuario, id_notificacao);


--
-- Name: usuario usuario_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario
    ADD CONSTRAINT usuario_pkey PRIMARY KEY (id_usuario);


--
-- Name: documento_peticao_unica; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX documento_peticao_unica ON public.documento USING btree (id_peticao) WHERE (id_peticao IS NOT NULL);


--
-- Name: idx_auditoria_data; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_auditoria_data ON public.auditoria USING btree (data_hora DESC);


--
-- Name: idx_documento_processo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_documento_processo ON public.documento USING btree (id_processo);


--
-- Name: idx_linha_tempo_processo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_linha_tempo_processo ON public.linha_tempo USING btree (id_processo, data_hora DESC);


--
-- Name: idx_peticao_processo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_peticao_processo ON public.peticao USING btree (id_processo);


--
-- Name: idx_prazo_processo; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prazo_processo ON public.prazo USING btree (id_processo);


--
-- Name: idx_prazo_vencimento; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prazo_vencimento ON public.prazo USING btree (data_vencimento);


--
-- Name: idx_sincronizacao_data; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_sincronizacao_data ON public.sincronizacao USING btree (data_hora DESC);


--
-- Name: administrador administrador_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.administrador
    ADD CONSTRAINT administrador_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE CASCADE;


--
-- Name: associado_notificacao associado_notificacao_id_associado_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.associado_notificacao
    ADD CONSTRAINT associado_notificacao_id_associado_fkey FOREIGN KEY (id_associado) REFERENCES public.associado(id_associado) ON DELETE CASCADE;


--
-- Name: associado_notificacao associado_notificacao_id_notificacao_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.associado_notificacao
    ADD CONSTRAINT associado_notificacao_id_notificacao_fkey FOREIGN KEY (id_notificacao) REFERENCES public.notificacao(id_notificacao) ON DELETE CASCADE;


--
-- Name: auditoria auditoria_id_processo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria
    ADD CONSTRAINT auditoria_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES public.processo(id_processo) ON DELETE SET NULL;


--
-- Name: auditoria auditoria_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auditoria
    ADD CONSTRAINT auditoria_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE SET NULL;


--
-- Name: documento documento_id_peticao_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento
    ADD CONSTRAINT documento_id_peticao_fkey FOREIGN KEY (id_peticao) REFERENCES public.peticao(id_peticao) ON DELETE RESTRICT;


--
-- Name: documento documento_id_processo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento
    ADD CONSTRAINT documento_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES public.processo(id_processo) ON DELETE RESTRICT;


--
-- Name: documento documento_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.documento
    ADD CONSTRAINT documento_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE SET NULL;


--
-- Name: juridico juridico_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.juridico
    ADD CONSTRAINT juridico_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE CASCADE;


--
-- Name: linha_tempo linha_tempo_id_processo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.linha_tempo
    ADD CONSTRAINT linha_tempo_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES public.processo(id_processo) ON DELETE RESTRICT;


--
-- Name: linha_tempo linha_tempo_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.linha_tempo
    ADD CONSTRAINT linha_tempo_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE SET NULL;


--
-- Name: notificacao notificacao_id_prazo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notificacao
    ADD CONSTRAINT notificacao_id_prazo_fkey FOREIGN KEY (id_prazo) REFERENCES public.prazo(id_prazo) ON DELETE SET NULL;


--
-- Name: permissao_processo permissao_processo_id_processo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissao_processo
    ADD CONSTRAINT permissao_processo_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES public.processo(id_processo) ON DELETE CASCADE;


--
-- Name: permissao_processo permissao_processo_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permissao_processo
    ADD CONSTRAINT permissao_processo_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE RESTRICT;


--
-- Name: peticao peticao_id_processo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peticao
    ADD CONSTRAINT peticao_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES public.processo(id_processo) ON DELETE RESTRICT;


--
-- Name: peticao peticao_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.peticao
    ADD CONSTRAINT peticao_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE SET NULL;


--
-- Name: prazo prazo_id_processo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prazo
    ADD CONSTRAINT prazo_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES public.processo(id_processo) ON DELETE RESTRICT;


--
-- Name: prazo prazo_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.prazo
    ADD CONSTRAINT prazo_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE SET NULL;


--
-- Name: processo_associado processo_associado_id_associado_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processo_associado
    ADD CONSTRAINT processo_associado_id_associado_fkey FOREIGN KEY (id_associado) REFERENCES public.associado(id_associado) ON DELETE RESTRICT;


--
-- Name: processo_associado processo_associado_id_processo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processo_associado
    ADD CONSTRAINT processo_associado_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES public.processo(id_processo) ON DELETE CASCADE;


--
-- Name: sincronizacao sincronizacao_id_processo_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.sincronizacao
    ADD CONSTRAINT sincronizacao_id_processo_fkey FOREIGN KEY (id_processo) REFERENCES public.processo(id_processo) ON DELETE SET NULL;


--
-- Name: usuario_notificacao usuario_notificacao_id_notificacao_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_notificacao
    ADD CONSTRAINT usuario_notificacao_id_notificacao_fkey FOREIGN KEY (id_notificacao) REFERENCES public.notificacao(id_notificacao) ON DELETE CASCADE;


--
-- Name: usuario_notificacao usuario_notificacao_id_usuario_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.usuario_notificacao
    ADD CONSTRAINT usuario_notificacao_id_usuario_fkey FOREIGN KEY (id_usuario) REFERENCES public.usuario(id_usuario) ON DELETE CASCADE;


--
-- Name: administrador; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.administrador ENABLE ROW LEVEL SECURITY;

--
-- Name: associado; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.associado ENABLE ROW LEVEL SECURITY;

--
-- Name: associado_notificacao; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.associado_notificacao ENABLE ROW LEVEL SECURITY;

--
-- Name: auditoria; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.auditoria ENABLE ROW LEVEL SECURITY;

--
-- Name: documento; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.documento ENABLE ROW LEVEL SECURITY;

--
-- Name: juridico; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.juridico ENABLE ROW LEVEL SECURITY;

--
-- Name: linha_tempo; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.linha_tempo ENABLE ROW LEVEL SECURITY;

--
-- Name: notificacao; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.notificacao ENABLE ROW LEVEL SECURITY;

--
-- Name: permissao_processo; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.permissao_processo ENABLE ROW LEVEL SECURITY;

--
-- Name: peticao; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.peticao ENABLE ROW LEVEL SECURITY;

--
-- Name: prazo; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.prazo ENABLE ROW LEVEL SECURITY;

--
-- Name: processo; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.processo ENABLE ROW LEVEL SECURITY;

--
-- Name: processo_associado; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.processo_associado ENABLE ROW LEVEL SECURITY;

--
-- Name: sincronizacao; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.sincronizacao ENABLE ROW LEVEL SECURITY;

--
-- Name: usuario; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.usuario ENABLE ROW LEVEL SECURITY;

--
-- Name: usuario_notificacao; Type: ROW SECURITY; Schema: public; Owner: -
--

ALTER TABLE public.usuario_notificacao ENABLE ROW LEVEL SECURITY;

--
CREATE OR REPLACE FUNCTION public.contar_processos_ativos()
RETURNS BIGINT
LANGUAGE sql
STABLE
AS $codigo$
    SELECT COUNT(*)
    FROM public.processo
    WHERE status IN ('novo', 'em_acompanhamento', 'aguardando_prazo', 'ativo')
      AND arquivado IS FALSE;
$codigo$;

CREATE OR REPLACE FUNCTION public.contar_prazos_pendentes(
    p_id_processo BIGINT
)
RETURNS BIGINT
LANGUAGE sql
STABLE
AS $codigo$
    SELECT COUNT(*)
    FROM public.prazo
    WHERE id_processo = p_id_processo
      AND status = 'pendente';
$codigo$;

CREATE OR REPLACE FUNCTION public.consultar_nivel_acesso(
    p_id_usuario BIGINT,
    p_id_processo BIGINT
)
RETURNS VARCHAR(30)
LANGUAGE sql
STABLE
AS $codigo$
    SELECT nivel_acesso
    FROM public.permissao_processo
    WHERE id_usuario = p_id_usuario
      AND id_processo = p_id_processo;
$codigo$;

CREATE OR REPLACE PROCEDURE public.arquivar_processo(
    p_id_processo BIGINT
)
LANGUAGE plpgsql
AS $codigo$
DECLARE
    v_status VARCHAR(30);
    v_arquivado BOOLEAN;
BEGIN
    SELECT status, arquivado
      INTO v_status, v_arquivado
      FROM public.processo
     WHERE id_processo = p_id_processo
     FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Processo % nao encontrado', p_id_processo;
    END IF;

    IF v_arquivado THEN
        RETURN;
    END IF;

    IF v_status <> 'encerrado' THEN
        RAISE EXCEPTION 'Somente processos encerrados podem ser arquivados';
    END IF;

    UPDATE public.processo
       SET arquivado = TRUE
     WHERE id_processo = p_id_processo;
END;
$codigo$;

CREATE OR REPLACE PROCEDURE public.concluir_prazo(
    p_id_prazo BIGINT
)
LANGUAGE plpgsql
AS $codigo$
BEGIN
    UPDATE public.prazo
       SET status = 'concluido'
     WHERE id_prazo = p_id_prazo;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Prazo % nao encontrado', p_id_prazo;
    END IF;
END;
$codigo$;

CREATE OR REPLACE PROCEDURE public.registrar_movimentacao(
    p_id_processo BIGINT,
    p_descricao TEXT,
    p_tipo_evento VARCHAR(50),
    p_id_usuario BIGINT DEFAULT NULL,
    p_origem VARCHAR(30) DEFAULT 'manual'
)
LANGUAGE plpgsql
AS $codigo$
DECLARE
    v_arquivado BOOLEAN;
BEGIN
    SELECT arquivado
      INTO v_arquivado
      FROM public.processo
     WHERE id_processo = p_id_processo;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Processo % nao encontrado', p_id_processo;
    END IF;

    IF v_arquivado THEN
        RAISE EXCEPTION 'Desarquive o processo antes de registrar movimentacoes';
    END IF;

    INSERT INTO public.linha_tempo (
        id_processo, id_usuario, descricao, tipo_evento, origem
    ) VALUES (
        p_id_processo, p_id_usuario, p_descricao, p_tipo_evento, p_origem
    );
END;
$codigo$;

CREATE OR REPLACE FUNCTION public.fn_validar_arquivamento()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $codigo$
BEGIN
    IF NEW.arquivado IS TRUE AND NEW.status <> 'encerrado' THEN
        RAISE EXCEPTION 'Somente processos encerrados podem ser arquivados';
    END IF;
    RETURN NEW;
END;
$codigo$;

CREATE OR REPLACE FUNCTION public.fn_validar_status_prazo()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $codigo$
BEGIN
    IF NEW.status NOT IN ('pendente', 'concluido', 'cancelado') THEN
        RAISE EXCEPTION 'Status de prazo invalido: %', NEW.status;
    END IF;
    RETURN NEW;
END;
$codigo$;

CREATE OR REPLACE FUNCTION public.fn_validar_movimentacao()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $codigo$
BEGIN
    IF NEW.descricao IS NULL OR BTRIM(NEW.descricao) = '' THEN
        RAISE EXCEPTION 'Descricao da movimentacao nao pode ser vazia';
    END IF;

    IF NEW.tipo_evento IS NULL OR BTRIM(NEW.tipo_evento) = '' THEN
        RAISE EXCEPTION 'Tipo da movimentacao nao pode ser vazio';
    END IF;

    RETURN NEW;
END;
$codigo$;


CREATE OR REPLACE TRIGGER tr_validar_arquivamento
BEFORE INSERT OR UPDATE OF status, arquivado ON public.processo
FOR EACH ROW
EXECUTE FUNCTION public.fn_validar_arquivamento();

CREATE OR REPLACE TRIGGER tr_validar_status_prazo
BEFORE INSERT OR UPDATE OF status ON public.prazo
FOR EACH ROW
EXECUTE FUNCTION public.fn_validar_status_prazo();

CREATE OR REPLACE TRIGGER tr_validar_movimentacao
BEFORE INSERT OR UPDATE OF descricao, tipo_evento ON public.linha_tempo
FOR EACH ROW
EXECUTE FUNCTION public.fn_validar_movimentacao();

REVOKE EXECUTE ON PROCEDURE public.arquivar_processo(BIGINT) FROM PUBLIC;
REVOKE EXECUTE ON PROCEDURE public.concluir_prazo(BIGINT) FROM PUBLIC;
REVOKE EXECUTE ON PROCEDURE public.registrar_movimentacao(BIGINT, TEXT, VARCHAR, BIGINT, VARCHAR) FROM PUBLIC;


DO $seed$
BEGIN
  IF current_database() <> 'sindcomb_apd' THEN
    RETURN;
  END IF;

  INSERT INTO public.usuario (nome, email, senha, primeiro_acesso, ativo)
  SELECT 'Usuario ' || n, 'usuario' || n || '@exemplo.invalid',
         'HASH_DE_TESTE_SEM_LOGIN', FALSE, TRUE
  FROM generate_series(1,20) AS n;

  INSERT INTO public.administrador (id_usuario)
  SELECT id_usuario FROM public.usuario
  WHERE email LIKE 'usuario%@exemplo.invalid';

  INSERT INTO public.juridico (id_usuario, oab)
  SELECT id_usuario, 'RJ-' || lpad(row_number() OVER (ORDER BY id_usuario)::text, 6, '0')
  FROM public.usuario WHERE email LIKE 'usuario%@exemplo.invalid';

  INSERT INTO public.associado (nome, cpf, email, telefone)
  SELECT 'Associado ' || n, lpad(n::text, 11, '0'),
         'associado' || n || '@exemplo.invalid', '2190000' || lpad(n::text, 4, '0')
  FROM generate_series(1,20) AS n;

  INSERT INTO public.processo (numero_processo, tipo, assunto, status, arquivado)
  SELECT 'TESTE-SINDCOMB-' || lpad(n::text, 6, '0'), 'Civel',
         'Processo ficticio ' || n,
         CASE WHEN n % 4 = 0 THEN 'encerrado' ELSE 'em_acompanhamento' END, FALSE
  FROM generate_series(1,20) AS n;

  INSERT INTO public.processo_associado (id_processo, id_associado)
  SELECT p.id_processo, a.id_associado
  FROM (SELECT id_processo, row_number() OVER (ORDER BY id_processo) AS n
        FROM public.processo WHERE numero_processo LIKE 'TESTE-SINDCOMB-%') p
  JOIN (SELECT id_associado, row_number() OVER (ORDER BY id_associado) AS n
        FROM public.associado WHERE email LIKE 'associado%@exemplo.invalid') a USING (n);

  INSERT INTO public.permissao_processo (id_usuario, id_processo, nivel_acesso)
  SELECT u.id_usuario, p.id_processo, 'edicao'
  FROM (SELECT id_usuario, row_number() OVER (ORDER BY id_usuario) AS n
        FROM public.usuario WHERE email LIKE 'usuario%@exemplo.invalid') u
  JOIN (SELECT id_processo, row_number() OVER (ORDER BY id_processo) AS n
        FROM public.processo WHERE numero_processo LIKE 'TESTE-SINDCOMB-%') p USING (n);

  INSERT INTO public.peticao (id_processo, id_usuario, tipo, descricao)
  SELECT p.id_processo, u.id_usuario, 'Inicial', 'Peticao de teste ' || p.n
  FROM (SELECT id_processo, row_number() OVER (ORDER BY id_processo) AS n
        FROM public.processo WHERE numero_processo LIKE 'TESTE-SINDCOMB-%') p
  JOIN (SELECT id_usuario, row_number() OVER (ORDER BY id_usuario) AS n
        FROM public.usuario WHERE email LIKE 'usuario%@exemplo.invalid') u USING (n);

  INSERT INTO public.prazo (id_processo, id_usuario, descricao, data_inicio, data_vencimento)
  SELECT p.id_processo, u.id_usuario, 'Prazo de teste ' || p.n,
         CURRENT_DATE, CURRENT_DATE + (p.n::integer + 1)
  FROM (SELECT id_processo, row_number() OVER (ORDER BY id_processo) AS n
        FROM public.processo WHERE numero_processo LIKE 'TESTE-SINDCOMB-%') p
  JOIN (SELECT id_usuario, row_number() OVER (ORDER BY id_usuario) AS n
        FROM public.usuario WHERE email LIKE 'usuario%@exemplo.invalid') u USING (n);

  INSERT INTO public.documento
     (id_processo, id_usuario, nome, tipo, local_armazenamento, tamanho, hash_arquivo, id_peticao)
  SELECT p.id_processo, u.id_usuario, 'documento_' || p.n || '.pdf', 'pdf',
         'testes/documento_' || p.n || '.pdf', 1024 * p.n, 'hash-ficticio-' || p.n, pt.id_peticao
  FROM (SELECT id_processo, row_number() OVER (ORDER BY id_processo) AS n
        FROM public.processo WHERE numero_processo LIKE 'TESTE-SINDCOMB-%') p
  JOIN (SELECT id_usuario, row_number() OVER (ORDER BY id_usuario) AS n
        FROM public.usuario WHERE email LIKE 'usuario%@exemplo.invalid') u USING (n)
  JOIN (SELECT id_peticao, row_number() OVER (ORDER BY id_peticao) AS n
        FROM public.peticao) pt USING (n);

  INSERT INTO public.linha_tempo (id_processo, id_usuario, descricao, tipo_evento, origem)
  SELECT p.id_processo, u.id_usuario, 'Movimentacao de teste ' || p.n,
         'andamento', 'manual'
  FROM (SELECT id_processo, row_number() OVER (ORDER BY id_processo) AS n
        FROM public.processo WHERE numero_processo LIKE 'TESTE-SINDCOMB-%') p
  JOIN (SELECT id_usuario, row_number() OVER (ORDER BY id_usuario) AS n
        FROM public.usuario WHERE email LIKE 'usuario%@exemplo.invalid') u USING (n);

  INSERT INTO public.sincronizacao (id_processo, status, descricao, quantidade_atualizacoes)
  SELECT id_processo, 'sucesso', 'Sincronizacao ficticia', 1
  FROM public.processo WHERE numero_processo LIKE 'TESTE-SINDCOMB-%';

  INSERT INTO public.auditoria (id_usuario, id_processo, tipo_operacao, descricao, resultado)
  SELECT u.id_usuario, p.id_processo, 'CONSULTA', 'Auditoria de teste', 'SUCESSO'
  FROM (SELECT id_processo, row_number() OVER (ORDER BY id_processo) AS n
        FROM public.processo WHERE numero_processo LIKE 'TESTE-SINDCOMB-%') p
  JOIN (SELECT id_usuario, row_number() OVER (ORDER BY id_usuario) AS n
        FROM public.usuario WHERE email LIKE 'usuario%@exemplo.invalid') u USING (n);

  INSERT INTO public.notificacao (titulo, mensagem, id_prazo)
  SELECT 'Notificacao ' || x.n, 'Aviso ficticio ' || x.n, x.id_prazo
  FROM (SELECT id_prazo, row_number() OVER (ORDER BY id_prazo) AS n FROM public.prazo) x;

  INSERT INTO public.usuario_notificacao (id_usuario, id_notificacao)
  SELECT u.id_usuario, no.id_notificacao
  FROM (SELECT id_usuario, row_number() OVER (ORDER BY id_usuario) AS n
        FROM public.usuario WHERE email LIKE 'usuario%@exemplo.invalid') u
  JOIN (SELECT id_notificacao, row_number() OVER (ORDER BY id_notificacao) AS n
        FROM public.notificacao) no USING (n);

  INSERT INTO public.associado_notificacao (id_associado, id_notificacao)
  SELECT a.id_associado, no.id_notificacao
  FROM (SELECT id_associado, row_number() OVER (ORDER BY id_associado) AS n
        FROM public.associado WHERE email LIKE 'associado%@exemplo.invalid') a
  JOIN (SELECT id_notificacao, row_number() OVER (ORDER BY id_notificacao) AS n
        FROM public.notificacao) no USING (n);
END;
$seed$;


DO $roles$
BEGIN
  IF current_database() <> 'sindcomb_apd' THEN
    RETURN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sindcomb_leitura_demo') THEN
    CREATE ROLE sindcomb_leitura_demo NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sindcomb_edicao_demo') THEN
    CREATE ROLE sindcomb_edicao_demo NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sindcomb_usuario_leitura_demo') THEN
    CREATE ROLE sindcomb_usuario_leitura_demo LOGIN PASSWORD NULL;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sindcomb_usuario_edicao_demo') THEN
    CREATE ROLE sindcomb_usuario_edicao_demo LOGIN PASSWORD NULL;
  END IF;
END;
$roles$;

DO $security$
BEGIN
  IF current_database() <> 'sindcomb_apd' THEN
    RETURN;
  END IF;
  GRANT sindcomb_leitura_demo TO sindcomb_usuario_leitura_demo;
  GRANT sindcomb_edicao_demo TO sindcomb_usuario_edicao_demo;
  GRANT CONNECT ON DATABASE sindcomb_apd TO sindcomb_usuario_leitura_demo, sindcomb_usuario_edicao_demo;
  GRANT USAGE ON SCHEMA public TO sindcomb_leitura_demo, sindcomb_edicao_demo;
  GRANT SELECT ON public.processo, public.prazo TO sindcomb_leitura_demo, sindcomb_edicao_demo;
  GRANT INSERT, UPDATE ON public.prazo TO sindcomb_edicao_demo;
  GRANT USAGE ON SEQUENCE public.prazo_id_prazo_seq TO sindcomb_edicao_demo;
  REVOKE DELETE ON public.processo, public.prazo FROM sindcomb_leitura_demo, sindcomb_edicao_demo;
  EXECUTE 'CREATE POLICY sindcomb_demo_consulta_processo ON public.processo FOR SELECT TO sindcomb_leitura_demo, sindcomb_edicao_demo USING (true)';
  EXECUTE 'CREATE POLICY sindcomb_demo_consulta_prazo ON public.prazo FOR SELECT TO sindcomb_leitura_demo, sindcomb_edicao_demo USING (true)';
  EXECUTE 'CREATE POLICY sindcomb_demo_inserir_prazo ON public.prazo FOR INSERT TO sindcomb_edicao_demo WITH CHECK (true)';
  EXECUTE 'CREATE POLICY sindcomb_demo_atualizar_prazo ON public.prazo FOR UPDATE TO sindcomb_edicao_demo USING (true) WITH CHECK (true)';
END;
$security$;

COMMIT;

-- PostgreSQL database dump complete
--

\unrestrict 1URI9H642SjbfmDTgPoRUDfZqonWkRIOaHzWv0GUkevggSw3weUcWUemgQrufwN

-- Consultas e testes opcionais executados apenas no banco de demonstracao.
SELECT CASE WHEN current_database() = 'sindcomb_apd' THEN 'true' ELSE 'false' END AS sindcomb_executar_testes \gset
\if :sindcomb_executar_testes

-- Consultas e verificacoes para executar somente em sindcomb_apd.

-- Consulta simples 1
SELECT id_usuario, nome, email FROM public.usuario ORDER BY id_usuario LIMIT 20;
-- Consulta simples 2
SELECT numero_processo, status FROM public.processo WHERE arquivado = FALSE ORDER BY numero_processo;
-- Consulta simples 3
SELECT id_prazo, descricao, data_vencimento FROM public.prazo WHERE status = 'pendente' ORDER BY data_vencimento;
-- Consulta simples 4
SELECT nome, tipo, tamanho FROM public.documento WHERE tamanho >= 1024 ORDER BY nome;
-- Consulta simples 5
SELECT id_evento, descricao, origem FROM public.linha_tempo WHERE origem = 'manual' ORDER BY id_evento;

-- JOIN 1
SELECT p.numero_processo, COUNT(pr.id_prazo) AS total_prazos
FROM public.processo p JOIN public.prazo pr ON pr.id_processo = p.id_processo
WHERE pr.status = 'pendente'
GROUP BY p.id_processo, p.numero_processo HAVING COUNT(pr.id_prazo) >= 1;
-- JOIN 2
SELECT p.numero_processo, COUNT(pa.id_associado) AS total_associados
FROM public.processo p JOIN public.processo_associado pa ON pa.id_processo = p.id_processo
GROUP BY p.id_processo, p.numero_processo HAVING COUNT(pa.id_associado) > 0;
-- JOIN 3
SELECT u.nome, COUNT(pp.id_processo) AS processos_com_edicao
FROM public.usuario u JOIN public.permissao_processo pp ON pp.id_usuario = u.id_usuario
WHERE pp.nivel_acesso = 'edicao'
GROUP BY u.id_usuario, u.nome HAVING COUNT(pp.id_processo) >= 1;

-- Subconsulta 1: IN
SELECT numero_processo FROM public.processo
WHERE id_processo IN (SELECT id_processo FROM public.prazo WHERE status = 'pendente');
-- Subconsulta 2: EXISTS
SELECT p.numero_processo FROM public.processo p
WHERE EXISTS (SELECT 1 FROM public.linha_tempo t
              WHERE t.id_processo = p.id_processo AND t.origem = 'manual');
-- Subconsulta 3: ALL
SELECT id_prazo, data_vencimento FROM public.prazo
WHERE data_vencimento > ALL (
    SELECT data_vencimento FROM public.prazo
    WHERE id_processo = (SELECT MIN(id_processo) FROM public.processo)
);

-- Registro de quantidades por tabela
SELECT table_name FROM information_schema.tables
WHERE table_schema='public' AND table_type='BASE TABLE'
ORDER BY table_name;
DO $verifica$
DECLARE r RECORD; n BIGINT;
BEGIN
    IF current_database() <> 'sindcomb_apd' THEN
        RAISE EXCEPTION 'Execute apenas no banco sindcomb_apd';
    END IF;
    FOR r IN SELECT tablename FROM pg_tables WHERE schemaname='public' LOOP
        EXECUTE format('SELECT count(*) FROM public.%I',r.tablename) INTO n;
        RAISE NOTICE '%: % registros',r.tablename,n;
        IF n < 20 THEN RAISE EXCEPTION 'Tabela % tem menos de 20 registros',r.tablename; END IF;
    END LOOP;
END;
$verifica$;

-- Objects criados
SELECT routine_name, routine_type FROM information_schema.routines
WHERE routine_schema='public' ORDER BY routine_name;
SELECT tgname, tgrelid::regclass FROM pg_trigger
WHERE NOT tgisinternal AND tgrelid IN ('public.processo'::regclass,
'public.prazo'::regclass,'public.linha_tempo'::regclass) ORDER BY tgname;

-- Testes de permissoes sem usar credenciais
SELECT
  has_table_privilege('sindcomb_usuario_leitura_demo','public.processo','SELECT') AS leitor_consulta,
  NOT has_table_privilege('sindcomb_usuario_leitura_demo','public.prazo','UPDATE') AS leitor_nao_edita,
  has_table_privilege('sindcomb_usuario_edicao_demo','public.prazo','UPDATE') AS editor_edita,
  NOT has_table_privilege('sindcomb_usuario_edicao_demo','public.processo','DELETE') AS editor_nao_exclui;

-- Testes de rotinas e triggers: todas as modificacoes sao revertidas
BEGIN;
SELECT public.contar_processos_ativos();
SELECT public.contar_prazos_pendentes((SELECT MIN(id_processo) FROM public.processo));
SELECT public.consultar_nivel_acesso((SELECT MIN(id_usuario) FROM public.usuario),
                                   (SELECT MIN(id_processo) FROM public.processo));
CALL public.arquivar_processo(
   (SELECT MIN(id_processo) FROM public.processo WHERE status='encerrado'));
CALL public.concluir_prazo((SELECT MIN(id_prazo) FROM public.prazo));
CALL public.registrar_movimentacao((SELECT MIN(id_processo) FROM public.processo WHERE arquivado = FALSE),
  'Movimentacao de verificacao', 'andamento');
DO $validacao$
DECLARE idp BIGINT; idt BIGINT;
BEGIN
  SELECT MIN(id_processo) INTO idp FROM public.processo WHERE status <> 'encerrado';
  BEGIN
    UPDATE public.processo SET arquivado=TRUE WHERE id_processo=idp;
    RAISE EXCEPTION 'ERRO: arquivamento irregular foi permitido';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM <> 'Somente processos encerrados podem ser arquivados' THEN RAISE; END IF;
  END;
  SELECT MIN(id_prazo) INTO idt FROM public.prazo;
  BEGIN
    UPDATE public.prazo SET status='inexistente' WHERE id_prazo=idt;
    RAISE EXCEPTION 'ERRO: status invalido foi permitido';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM NOT LIKE 'Status de prazo invalido:%' THEN RAISE; END IF;
  END;
  BEGIN
    INSERT INTO public.linha_tempo(id_processo, descricao, tipo_evento, origem)
    VALUES(idp,'  ','andamento','manual');
    RAISE EXCEPTION 'ERRO: movimentacao vazia foi permitida';
  EXCEPTION WHEN raise_exception THEN
    IF SQLERRM <> 'Descricao da movimentacao nao pode ser vazia' THEN RAISE; END IF;
  END;
END;
$validacao$;
SELECT COUNT(*) AS processos_arquivados_teste FROM public.processo WHERE arquivado;
SELECT COUNT(*) AS prazos_concluidos_teste FROM public.prazo WHERE status='concluido';
ROLLBACK;

DO $permissoes$
BEGIN
  IF NOT has_table_privilege('sindcomb_usuario_leitura_demo','public.processo','SELECT')
    OR has_table_privilege('sindcomb_usuario_leitura_demo','public.prazo','UPDATE')
    OR NOT has_table_privilege('sindcomb_usuario_edicao_demo','public.prazo','UPDATE')
    OR has_table_privilege('sindcomb_usuario_edicao_demo','public.processo','DELETE') THEN
      RAISE EXCEPTION 'Privilegios diferentes dos esperados';
  END IF;
END;
$permissoes$;
\endif
