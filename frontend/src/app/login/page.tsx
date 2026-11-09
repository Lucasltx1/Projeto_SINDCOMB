"use client";

import Link from "next/link";
import { useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Usuario = { nome: string; papel: string; primeiro_acesso: boolean };

export default function LoginPage() {
  const [usuario, setUsuario] = useState("");
  const [senha, setSenha] = useState("");
  const [novaSenha, setNovaSenha] = useState("");
  const [confirmacao, setConfirmacao] = useState("");
  const [csrfToken, setCsrfToken] = useState("");
  const [perfil, setPerfil] = useState<Usuario | null>(null);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(false);

  async function entrar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro("");
    setCarregando(true);
    try {
      const resposta = await fetch(`${API_URL}/api/v1/auth/login`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ usuario, senha }),
      });
      const dados = await resposta.json();
      if (!resposta.ok) {
        throw new Error(dados.detail ?? "Não foi possível entrar.");
      }
      setCsrfToken(dados.csrf_token);
      setPerfil(dados.usuario);
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Falha de conexão com o sistema.");
    } finally {
      setCarregando(false);
    }
  }

  async function alterarSenhaInicial(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro("");
    if (novaSenha !== confirmacao) {
      setErro("As senhas não coincidem.");
      return;
    }
    setCarregando(true);
    try {
      const resposta = await fetch(`${API_URL}/api/v1/auth/alterar-senha`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify({ senha_atual: senha, nova_senha: novaSenha }),
      });
      const dados = await resposta.json();
      if (!resposta.ok) {
        throw new Error(dados.detail ?? "Não foi possível alterar a senha.");
      }
      setCsrfToken(dados.csrf_token);
      setPerfil(dados.usuario);
      setSenha("");
      setNovaSenha("");
      setConfirmacao("");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Falha de conexão com o sistema.");
    } finally {
      setCarregando(false);
    }
  }

  async function sair() {
    setErro("");
    setCarregando(true);
    try {
      const resposta = await fetch(`${API_URL}/api/v1/auth/logout`, {
        method: "POST",
        credentials: "include",
        headers: { "X-CSRF-Token": csrfToken },
      });
      if (!resposta.ok) {
        const dados = await resposta.json();
        throw new Error(dados.detail ?? "Não foi possível encerrar a sessão.");
      }
      setPerfil(null);
      setCsrfToken("");
      setSenha("");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Falha ao encerrar a sessão.");
    } finally {
      setCarregando(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Acessar o SINDCOMB</CardTitle>
          <CardDescription>Entre com seu e-mail ou nome de usuário e sua senha.</CardDescription>
        </CardHeader>
        <CardContent>
          {perfil ? (
            perfil.primeiro_acesso ? (
              <form className="grid gap-4" onSubmit={alterarSenhaInicial}>
                <p className="text-sm">Defina uma nova senha para concluir seu primeiro acesso.</p>
                <label className="grid gap-2 text-sm font-medium" htmlFor="nova-senha">
                  Nova senha (mínimo de 12 caracteres)
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
                <label className="grid gap-2 text-sm font-medium" htmlFor="confirmacao-senha">
                  Confirme a nova senha
                  <input
                    id="confirmacao-senha"
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
                {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
                <Button type="submit" disabled={carregando}>
                  {carregando ? "Salvando…" : "Salvar nova senha"}
                </Button>
              </form>
            ) : (
              <div className="grid gap-4">
                <p role="status" className="text-sm">
                  Acesso autenticado para {perfil.nome} ({perfil.papel}).
                </p>
                <p className="text-sm text-muted-foreground">Sua sessão fica ativa nesta aba.</p>
                <Button asChild><Link href="/processos">Abrir processos</Link></Button>
                <Button asChild variant="outline"><Link href="/prazos">Ver prazos</Link></Button>
                {perfil.papel === "advogado" && (
                  <Button asChild variant="outline"><Link href="/peticoes/modelos">Modelos de petição</Link></Button>
                )}
                {perfil.papel === "administrador" && (
                  <Button asChild variant="outline"><Link href="/admin">Administração</Link></Button>
                )}
                <Button type="button" variant="outline" disabled={carregando} onClick={sair}>
                  Encerrar sessão
                </Button>
              </div>
            )
          ) : (
            <form className="grid gap-4" onSubmit={entrar}>
              <label className="grid gap-2 text-sm font-medium" htmlFor="usuario">
                E-mail ou usuário
                <input
                  id="usuario"
                  name="usuario"
                  autoComplete="username"
                  required
                  maxLength={255}
                  value={usuario}
                  onChange={(evento) => setUsuario(evento.target.value)}
                  className="h-10 rounded-md border border-input bg-background px-3 font-normal outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </label>
              <label className="grid gap-2 text-sm font-medium" htmlFor="senha">
                Senha
                <input
                  id="senha"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={senha}
                  onChange={(evento) => setSenha(evento.target.value)}
                  className="h-10 rounded-md border border-input bg-background px-3 font-normal outline-none focus-visible:ring-2 focus-visible:ring-ring"
                />
              </label>
              {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
              <Button type="submit" disabled={carregando}>
                {carregando ? "Entrando…" : "Entrar"}
              </Button>
            </form>
          )}
          <Link className="mt-5 inline-block text-sm underline underline-offset-4" href="/recuperar_senha">
            Esqueci minha senha
          </Link>
        </CardContent>
      </Card>
    </main>
  );
}
