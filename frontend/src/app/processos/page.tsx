"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Processo = {
  id: string;
  dados: {
    numero: string;
    tribunal: string;
    classe?: string | null;
    assunto: string;
    fonte_url?: string | null;
    origem_dados?: "datajud" | "djen" | null;
    consultado_em?: string | null;
    data_ultima_verificacao_fonte?: string | null;
  };
  triagem: { relevancia: string; justificativa: string; confianca: number };
  status: string;
  arquivado: boolean;
};

type Perfil = { nome: string; papel: "administrador" | "advogado" | "visualizador" };

function formatarData(valor?: string | null): string | null {
  if (!valor) return null;
  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return null;
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(data);
}

function rotuloFonte(fonte?: "datajud" | "djen" | null): string | null {
  if (fonte === "datajud") return "DataJud";
  if (fonte === "djen") return "DJEN / CNJ";
  return null;
}

export default function ProcessosPage() {
  const [csrfToken, setCsrfToken] = useState("");
  const [sessaoAtiva, setSessaoAtiva] = useState(false);
  const [perfil, setPerfil] = useState<Perfil | null>(null);
  const [processos, setProcessos] = useState<Processo[]>([]);
  const [mostrarArquivados, setMostrarArquivados] = useState(false);
  const [carregando, setCarregando] = useState(true);
  const [sincronizando, setSincronizando] = useState(false);
  const [acaoEmAndamento, setAcaoEmAndamento] = useState<string | null>(null);
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");
  const [numeroTriagem, setNumeroTriagem] = useState("");

  useEffect(() => {
    let ativa = true;
    const opcoes: RequestInit = { credentials: "include" };
    Promise.all([
      fetch(`${API_URL}/api/v1/auth/me`, opcoes),
      fetch(`${API_URL}/api/v1/processos?arquivado=${mostrarArquivados}`, opcoes),
      fetch(`${API_URL}/api/v1/auth/csrf`, opcoes),
    ])
      .then(async ([respostaPerfil, respostaProcessos, respostaCsrf]) => {
        const dadosPerfil = await respostaPerfil.json();
        const dadosProcessos = await respostaProcessos.json();
        const dadosCsrf = await respostaCsrf.json();
        if (!respostaPerfil.ok) throw new Error(dadosPerfil.detail ?? "Sessão inválida. Entre novamente.");
        if (ativa) {
          setSessaoAtiva(true);
          setPerfil(dadosPerfil);
        }
        if (!respostaProcessos.ok) throw new Error(dadosProcessos.detail ?? "Não foi possível carregar os processos.");
        if (!respostaCsrf.ok) throw new Error(dadosCsrf.detail ?? "Sessão inválida. Entre novamente.");
        if (ativa) {
          setProcessos(dadosProcessos);
          setCsrfToken(dadosCsrf.csrf_token);
        }
      })
      .catch((error: unknown) => {
        if (ativa) setErro(error instanceof Error ? error.message : "Falha de conexão com a API.");
      })
      .finally(() => {
        if (ativa) setCarregando(false);
      });

    return () => { ativa = false; };
  }, [mostrarArquivados]);

  async function alterarArquivamento(processo: Processo) {
    if (!csrfToken) return;
    setErro("");
    setMensagem("");
    setAcaoEmAndamento(processo.id);
    const acao = processo.arquivado ? "desarquivar" : "arquivar";
    try {
      const resposta = await fetch(`${API_URL}/api/v1/processos/${processo.id}/${acao}`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfToken },
      });
      const dados = await resposta.json();
      if (!resposta.ok) throw new Error(dados.detail ?? "Não foi possível atualizar o arquivamento.");
      setMensagem(processo.arquivado ? "Processo desarquivado." : "Processo arquivado.");
      setProcessos((atuais) => atuais.filter((item) => item.id !== processo.id));
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Falha de conexão com a API.");
    } finally {
      setAcaoEmAndamento(null);
    }
  }

  async function sincronizarAgora() {
    if (!csrfToken || perfil?.papel !== "advogado") return;
    setErro("");
    setMensagem("");
    setSincronizando(true);
    try {
      const resposta = await fetch(`${API_URL}/api/v1/processos/sincronizar`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfToken },
      });
      const resultado = await resposta.json();
      if (!resposta.ok) throw new Error(resultado.detail ?? "Não foi possível sincronizar os processos.");

      const respostaProcessos = await fetch(
        `${API_URL}/api/v1/processos?arquivado=${mostrarArquivados}`,
        { credentials: "include" },
      );
      const dadosProcessos = await respostaProcessos.json();
      if (!respostaProcessos.ok) {
        throw new Error(dadosProcessos.detail ?? "Sincronização concluída, mas não foi possível atualizar a lista.");
      }
      setProcessos(dadosProcessos);
      const avisos = resultado.falhas?.length
        ? ` Avisos: ${resultado.falhas.join(" ")}`
        : "";
      setMensagem(
        `Sincronização concluída: ${resultado.processos_consultados} processo(s) consultado(s), `
        + `${resultado.processos_com_movimentacao_nova} com novas movimentações.${avisos}`,
      );
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Falha de conexão com a API.");
    } finally {
      setSincronizando(false);
    }
  }

  async function solicitarTriagem(evento: React.FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro("");
    setMensagem("");
    try {
      const resposta = await api.processos.triagem({ numero: numeroTriagem });
      setMensagem(resposta.mensagem);
      setNumeroTriagem("");
      setProcessos(await api.processos.listar({ arquivado: mostrarArquivados }));
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível solicitar a triagem.");
    }
  }

  function selecionarArquivamento(mostrar: boolean) {
    setErro("");
    setCarregando(true);
    setMostrarArquivados(mostrar);
  }

  return (
    <main className="min-h-screen px-6 py-10 sm:px-10">
      <section className="mx-auto max-w-5xl">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold tracking-tight">Processos</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {perfil ? `Sessão de ${perfil.nome}` : "Acompanhamento processual SINDCOMB"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {perfil?.papel === "advogado" && (
              <Button
                type="button"
                variant="secondary"
                disabled={sincronizando || carregando}
                onClick={sincronizarAgora}
              >
                {sincronizando ? "Sincronizando…" : "Sincronizar agora"}
              </Button>
            )}
            <Button asChild variant="outline"><Link href="/prazos">Prazos</Link></Button>
            {perfil?.papel === "advogado" && (
              <Button asChild variant="outline"><Link href="/peticoes/modelos">Modelos</Link></Button>
            )}
            {perfil?.papel === "administrador" && (
              <Button asChild variant="outline"><Link href="/admin">Administração</Link></Button>
            )}
            <Button asChild variant="outline"><Link href="/">Início</Link></Button>
          </div>
        </header>

        <div className="mt-8 flex gap-2" aria-label="Filtro de arquivamento">
          <Button
            type="button"
            variant={!mostrarArquivados ? "default" : "outline"}
            disabled={sincronizando}
            onClick={() => selecionarArquivamento(false)}
          >
            Ativos
          </Button>
          <Button
            type="button"
            variant={mostrarArquivados ? "default" : "outline"}
            disabled={sincronizando}
            onClick={() => selecionarArquivamento(true)}
          >
            Arquivados
          </Button>
        </div>

        {perfil?.papel === "advogado" && !mostrarArquivados && (
          <form
            className="mt-5 flex flex-wrap items-end gap-3 rounded-lg border p-4"
            onSubmit={solicitarTriagem}
          >
            <label className="grid flex-1 gap-2 text-sm font-medium" htmlFor="numero-triagem">
              Solicitar acompanhamento de processo pelo número CNJ
              <input
                id="numero-triagem"
                className="h-10 rounded-md border bg-background px-3 font-normal"
                required
                maxLength={30}
                value={numeroTriagem}
                onChange={(evento) => setNumeroTriagem(evento.target.value)}
                placeholder="0000000-00.0000.0.00.0000"
              />
            </label>
            <Button type="submit" disabled={!csrfToken}>Solicitar triagem</Button>
          </form>
        )}

        {mensagem && <p role="status" className="mt-4 text-sm">{mensagem}</p>}
        {erro && (
          <p role="alert" className="mt-4 text-sm text-destructive">
              {erro}{!sessaoAtiva && <> <Link className="underline" href="/login">Ir para o login</Link></>}
          </p>
        )}
        {carregando && <p className="mt-6 text-sm text-muted-foreground">Carregando processos…</p>}

        {!carregando && !erro && processos.length === 0 && (
          <p className="mt-8 text-sm text-muted-foreground">
            {mostrarArquivados ? "Não há processos arquivados." : "Não há processos ativos."}
          </p>
        )}

        <div className="mt-6 grid gap-4 md:grid-cols-2">
          {processos.map((processo) => (
            <Card key={processo.id}>
              <CardHeader>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <CardTitle className="text-lg">{processo.dados.numero}</CardTitle>
                  <Badge variant={processo.arquivado ? "outline" : "secondary"}>
                    {processo.arquivado ? "Arquivado" : processo.status.replaceAll("_", " ")}
                  </Badge>
                </div>
                <CardDescription>
                  {processo.dados.tribunal}{processo.dados.classe ? ` · ${processo.dados.classe}` : ""}
                </CardDescription>
              </CardHeader>
              <CardContent className="grid gap-2 text-sm">
                <p><span className="font-medium">Assunto:</span> {processo.dados.assunto}</p>
                <p><span className="font-medium">Triagem:</span> {processo.triagem.relevancia.replaceAll("_", " ")}</p>
                {rotuloFonte(processo.dados.origem_dados) && (
                  <p className="text-muted-foreground">
                    Fonte: {rotuloFonte(processo.dados.origem_dados)}
                    {formatarData(processo.dados.consultado_em)
                      ? ` · consultado em ${formatarData(processo.dados.consultado_em)}`
                      : ""}
                    {formatarData(processo.dados.data_ultima_verificacao_fonte)
                      ? ` · fonte verificada em ${formatarData(processo.dados.data_ultima_verificacao_fonte)}`
                      : ""}
                  </p>
                )}
                {processo.dados.fonte_url && (
                  <a
                    className="w-fit text-primary underline underline-offset-4"
                    href={processo.dados.fonte_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    {processo.dados.origem_dados === "djen"
                      ? "Abrir certidão/publicação oficial do DJEN"
                      : "Abrir fonte processual"}
                  </a>
                )}
              </CardContent>
              <CardFooter className="flex flex-wrap gap-2">
                <Button asChild variant="outline">
                  <Link href={`/processos/${encodeURIComponent(processo.id)}`}>Ver processo</Link>
                </Button>
                {perfil?.papel === "advogado" && (
                  processo.arquivado ? (
                    <Button
                      type="button"
                      disabled={acaoEmAndamento === processo.id}
                      onClick={() => alterarArquivamento(processo)}
                    >
                      {acaoEmAndamento === processo.id ? "Reativando…" : "Desarquivar"}
                    </Button>
                  ) : processo.status === "encerrado" ? (
                    <Button
                      type="button"
                      variant="secondary"
                      disabled={acaoEmAndamento === processo.id}
                      onClick={() => alterarArquivamento(processo)}
                    >
                      {acaoEmAndamento === processo.id ? "Arquivando…" : "Arquivar"}
                    </Button>
                  ) : null
                )}
              </CardFooter>
            </Card>
          ))}
        </div>
      </section>
    </main>
  );
}
