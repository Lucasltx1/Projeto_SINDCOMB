import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function HomePage() {
  return (
    <main className="flex min-h-screen items-center justify-center px-6 py-12">
      <Card className="w-full max-w-xl">
        <CardHeader>
          <CardTitle>SINDCOMB · Jurídico</CardTitle>
          <CardDescription>
            Acompanhamento processual para advogados e usuários autorizados.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-3">
          <Button asChild><Link href="/login">Entrar</Link></Button>
          <Button asChild variant="outline"><Link href="/recuperar_senha">Recuperar senha</Link></Button>
        </CardContent>
      </Card>
    </main>
  );
}
