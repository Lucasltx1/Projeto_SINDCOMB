"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function RedefinirSenhaPage() {
  const [token, setToken] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  useEffect(() => {
    const valor = new URLSearchParams(window.location.hash.slice(1)).get("token");
    if (valor) {
      setToken(valor);
      // Remove o token do endereço do navegador assim que o formulário o capturar.
      window.history.replaceState(null, "", `${window.location.pathname}${window.location.search}`);
    }
  }, []);

  async function redefinir(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro("");
    setMensagem("");
    if (novaSenha !== confirmacao) {
      setErro("As senhas não coincidem.");
      return;
    }
    if (!token) {
      setErro("O link não contém um token válido. Solicite outra mensagem de recuperação.");
      return;
    }

    setCarregando(true);
    try {
      const resposta = await fetch(`${API_URL}/api/v1/auth/redefinir-senha`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, nova_senha: novaSenha }),
      });
      const dados = await resposta.json();
      if (!resposta.ok) {
        throw new Error(dados.detail ?? "Não foi possível redefinir a senha.");
      }
      setMensagem(dados.mensagem);
      setToken("");
      setNovaSenha("");
      setConfirmacao("");
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
          <CardTitle>Definir nova senha</CardTitle>
          <CardDescription>A senha deve ter pelo menos 12 caracteres.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="grid gap-4" onSubmit={redefinir}>
            <label className="grid gap-2 text-sm font-medium" htmlFor="nova-senha">
              Nova senha
              <input
                id="nova-senha"
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                required
                value={novaSenha}
                onChange={(evento) => setNovaSenha(evento.target.value)}
                className="h-10 rounded-md border border-input bg-background px-3 font-normal outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
            <label className="grid gap-2 text-sm font-medium" htmlFor="confirmacao">
              Confirme a nova senha
              <input
                id="confirmacao"
                type="password"
                autoComplete="new-password"
                minLength={12}
                maxLength={128}
                required
                value={confirmacao}
                onChange={(evento) => setConfirmacao(evento.target.value)}
                className="h-10 rounded-md border border-input bg-background px-3 font-normal outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </label>
            {mensagem && <p role="status" className="text-sm text-foreground">{mensagem}</p>}
            {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
            <Button type="submit" disabled={carregando || Boolean(mensagem)}>
              {carregando ? "Salvando…" : "Redefinir senha"}
            </Button>
          </form>
          <Link className="mt-5 inline-block text-sm underline underline-offset-4" href="/login">
            Ir para o login
          </Link>
        </CardContent>
      </Card>
    </main>
  );
}
