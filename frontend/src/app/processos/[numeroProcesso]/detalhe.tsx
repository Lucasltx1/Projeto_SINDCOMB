"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Movimentacao } from "../../../../types/processo";
import LinhaDoTempo from "./linhaDoTempo";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type ProcessoDetalhe = {
  id: string;
  dados: {
    numero: string;
    tribunal: string;
    classe?: string | null;
    assunto: string;
    fonte_url?: string | null;
    origem_dados?: "datajud" | "djen" | null;
    consultado_em?: string | null;
  };
  triagem: {
    relevancia: string;
    justificativa: string;
    confianca: number;
  };
  status: string;
  arquivado: boolean;
  movimentacoes: Movimentacao[];
};

function formatarData(valor?: string | null): string | null {
  if (!valor) return null;
  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return null;
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "short", timeStyle: "short" }).format(data);
}

export default function ProcessoDetalhe({processoId}: {processoId: string}) {
  const [processo, setProcesso] = useState<ProcessoDetalhe | null>(null);
  const [carregando, setCarregando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let ativo = true;
    fetch(`${API_URL}/api/v1/processos/${encodeURIComponent(processoId)}`, {
      credentials: "include",
    })
      .then(async (resposta) => {
        const dados = await resposta.json();
        if (!resposta.ok) throw new Error(dados.detail ?? "Não foi possível carregar o processo.");
        if (ativo) {
          setErro("");
          setProcesso(dados);
        }
      })
      .catch((error: unknown) => {
        if (ativo) setErro(error instanceof Error ? error.message : "Falha de conexão com a API.");
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });

    return () => { ativo = false; };
  }, [processoId]);

  return (
    <main className="min-h-screen px-6 py-10 sm:px-10">
      <section className="mx-auto max-w-5xl space-y-6">
        <header className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">
              {processo ? `Processo ${processo.dados.numero}` : "Detalhes do processo"}
            </h1>
            {processo && (
              <p className="mt-1 text-sm text-muted-foreground">
                {processo.dados.tribunal}{processo.dados.classe ? ` · ${processo.dados.classe}` : ""}
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="outline">
              <Link href={`/processos/${encodeURIComponent(processoId)}/gestao`}>Gestão do processo</Link>
            </Button>
            <Button asChild variant="outline"><Link href="/processos">Voltar aos processos</Link></Button>
          </div>
        </header>

        {carregando && <p role="status" className="text-sm text-muted-foreground">Carregando processo…</p>}
        {erro && (
          <p role="alert" className="text-sm text-destructive">
            {erro} <Link className="underline" href="/login">Verifique sua sessão</Link>
          </p>
        )}

        {processo && (
          <>
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center gap-2">
                  <CardTitle className="text-lg">Resumo do processo</CardTitle>
                  <Badge variant={processo.arquivado ? "outline" : "secondary"}>
                    {processo.arquivado ? "Arquivado" : processo.status.replaceAll("_", " ")}
                  </Badge>
                  <Badge variant="outline">Triagem: {processo.triagem.relevancia.replaceAll("_", " ")}</Badge>
                </div>
                <CardDescription>{processo.dados.assunto}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <p>{processo.triagem.justificativa}</p>
                <p className="text-muted-foreground">
                  Confiança da triagem: {Math.round(processo.triagem.confianca * 100)}%
                  {formatarData(processo.dados.consultado_em)
                    ? ` · consulta às fontes em ${formatarData(processo.dados.consultado_em)}`
                    : ""}
                </p>
                {processo.dados.fonte_url && (
                  <a
                    className="inline-block text-primary underline underline-offset-4"
                    href={processo.dados.fonte_url}
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    Abrir consulta/certidão oficial
                  </a>
                )}
              </CardContent>
            </Card>

            <section className="space-y-4" aria-labelledby="titulo-movimentacoes">
              <div>
                <h2 id="titulo-movimentacoes" className="text-xl font-semibold">Movimentações</h2>
                <p className="text-sm text-muted-foreground">
                  {processo.movimentacoes.length} registro(s). Confirme prazos e atos no sistema oficial do tribunal.
                </p>
              </div>
              <LinhaDoTempo movimentacoes={[...processo.movimentacoes].reverse()} />
            </section>
          </>
        )}
      </section>
    </main>
  );
}
