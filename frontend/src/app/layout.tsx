import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { TooltipProvider } from "@/components/ui/tooltip";

export const metadata: Metadata = {
  title: "SINDCOMB | Acompanhamento Processual",
  description: "Sistema interno de acompanhamento processual do SINDCOMB.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="pt-BR">
      <TooltipProvider>
      <body>{children}</body>
      </TooltipProvider>
    </html>
  );
}
