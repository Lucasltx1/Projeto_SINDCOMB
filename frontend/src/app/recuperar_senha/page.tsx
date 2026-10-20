"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function RecuperarSenhaPage() {
  const [email, setEmail] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  async function enviarSolicitacao(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro("");
    setMensagem("");
    setCarregando(true);

    try {
      const resposta = await fetch(`${API_URL}/api/v1/auth/solicitar-recuperacao-senha`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      const dados = await resposta.json();
      if (!resposta.ok) {
        throw new Error(dados.detail ?? "Não foi possível processar a solicitação.");
      }
      setMensagem(dados.mensagem);
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Falha de conexão com o sistema.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Recuperar senha</CardTitle>
          <CardDescription>
            Informe o e-mail da sua conta. Se ela estiver ativa e confirmada, enviaremos um link de redefinição.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={enviarSolicitacao}>
            <label className="grid gap-2 text-sm font-medium" htmlFor="email">
              E-mail
              <input
                id="email"
                name="email"
                type="email"
                autoComplete="email"
                required
                maxLength={255}
                value={email}
                onChange={(evento) => setEmail(evento.target.value)}
                className="h-10 rounded-md border border-input bg-background px-3 font-normal outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
            {mensagem && <p role="status" className="text-sm text-foreground">{mensagem}</p>}
            {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
            <Button type="submit" disabled={carregando}>
              {carregando ? "Enviando…" : "Enviar instruções"}
            </Button>
          </form>
          <Link className="mt-5 inline-block text-sm underline underline-offset-4" href="/login">
            Voltar para o login
          </Link>
        </CardContent>
      </Card>
    </main>
  );
}
