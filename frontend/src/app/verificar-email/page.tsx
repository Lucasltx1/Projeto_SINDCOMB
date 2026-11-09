"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { api } from "@/lib/api";

function VerificarEmailResultado() {
  const searchParams = useSearchParams();
  const token = searchParams.get("token");
  const [mensagem, setMensagem] = useState("");
  const [erro, setErro] = useState("");

  useEffect(() => {
    if (!token) return;

    window.history.replaceState(null, "", window.location.pathname);
    void api.auth.verificarEmail(token)
      .then((resultado) => setMensagem(resultado.mensagem))
      .catch((error: unknown) => {
        setErro(error instanceof Error ? error.message : "Não foi possível verificar o e-mail.");
      });
  }, [token]);

  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/30 px-4 py-10">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle>Verificação de e-mail</CardTitle>
          <CardDescription>Confirmação do endereço usado no SINDCOMB.</CardDescription>
        </CardHeader>
        <CardContent className="grid gap-4">
          {!token ? (
            <p role="alert" className="text-destructive">O link não contém um token de verificação.</p>
          ) : !mensagem && !erro ? (
            <p role="status">Verificando…</p>
          ) : null}
          {mensagem && <p role="status">{mensagem}</p>}
          {erro && <p role="alert" className="text-destructive">{erro}</p>}
          <Button asChild><Link href="/login">Ir para o login</Link></Button>
        </CardContent>
      </Card>
    </main>
  );
}

export default function VerificarEmailPage() {
  return (
    <Suspense fallback={<p role="status" className="p-6 text-center">Verificando…</p>}>
      <VerificarEmailResultado />
    </Suspense>
  );
}
