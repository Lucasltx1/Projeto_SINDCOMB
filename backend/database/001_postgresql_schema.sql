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
COMMIT;

-- PostgreSQL database dump complete
--

\unrestrict 1URI9H642SjbfmDTgPoRUDfZqonWkRIOaHzWv0GUkevggSw3weUcWUemgQrufwN


