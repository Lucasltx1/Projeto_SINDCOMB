import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { TooltipProvider } from "@/components/ui/tooltip";
import { LimparTokenLegado } from "@/components/security/limpar-token-legado";

export const metadata: Metadata = {
  title: "SINDCOMB | Acompanhamento Processual",
  description: "Sistema interno de acompanhamento processual do SINDCOMB.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="pt-BR">
      <TooltipProvider>
      <body>
        <LimparTokenLegado />
        {children}
      </body>
      </TooltipProvider>
    </html>
  );
}
