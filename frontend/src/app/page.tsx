"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError, api } from "@/lib/api";
import type { UsuarioPerfil } from "@/lib/api";

export default function HomePage() {
  const [perfil, setPerfil] = useState<UsuarioPerfil | null>(null);
  const [verificando, setVerificando] = useState(true);
  const [erro, setErro] = useState("");
  const [saindo, setSaindo] = useState(false);

  useEffect(() => {
    let ativo = true;
    api.auth.perfil()
      .then((usuario) => { if (ativo) setPerfil(usuario); })
      .catch((error: unknown) => {
        if (!ativo) return;
        if (error instanceof ApiError && error.status === 401) {
          setPerfil(null);
          return;
        }
        setErro(error instanceof Error ? error.message : "Não foi possível verificar a sessão.");
      })
      .finally(() => { if (ativo) setVerificando(false); });
    return () => { ativo = false; };
  }, []);

  async function sair() {
    setErro("");
    setSaindo(true);
    try {
      await api.auth.logout();
      setPerfil(null);
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível encerrar a sessão.");
    } finally {
      setSaindo(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-6 py-12">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle>SINDCOMB · Jurídico</CardTitle>
          <CardDescription>
            {perfil
              ? `Olá, ${perfil.nome}. Escolha uma área do sistema.`
              : "Acompanhamento processual para advogados e usuários autorizados."}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3">
          {erro && <p role="alert" className="text-sm text-destructive">{erro}</p>}
          {verificando ? (
            <p role="status" className="text-sm text-muted-foreground">Verificando sessão…</p>
          ) : perfil ? (
            <>
              <Button asChild><Link href="/processos">Processos</Link></Button>
              <Button asChild variant="outline"><Link href="/prazos">Prazos</Link></Button>
              {perfil.papel === "advogado" && (
                <Button asChild variant="outline"><Link href="/peticoes/modelos">Modelos de petição</Link></Button>
              )}
              {perfil.papel === "administrador" && (
                <Button asChild variant="outline"><Link href="/admin">Administração</Link></Button>
              )}
              <Button asChild variant="outline"><Link href="/sistema">Estado do sistema</Link></Button>
              <Button type="button" variant="ghost" onClick={sair} disabled={saindo}>
                {saindo ? "Saindo…" : "Encerrar sessão"}
              </Button>
            </>
          ) : (
            <>
              <Button asChild><Link href="/login">Entrar</Link></Button>
              <Button asChild variant="outline"><Link href="/recuperar_senha">Recuperar senha</Link></Button>
              <Button asChild variant="ghost"><Link href="/recuperar_senha?primeiro_acesso=1">Primeiro acesso</Link></Button>
            </>
          )}
        </CardContent>
      </Card>
    </main>
  );
}
