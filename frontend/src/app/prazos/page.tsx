"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { Prazo as PrazoApi, StatusPrazo } from "@/lib/api";
import PrazosCalendario from "./prazosCalendario";

const statusLabels: Record<StatusPrazo, string> = {
  pendente: "Pendente",
  concluido: "Concluído",
  cancelado: "Cancelado",
};

function formatarData(valor: string): string {
  return new Date(`${valor}T12:00:00`).toLocaleDateString("pt-BR");
}

export default function PrazosPage() {
  const [prazos, setPrazos] = useState<PrazoApi[]>([]);
  const [status, setStatus] = useState<StatusPrazo | "">("pendente");
  const [atrasados, setAtrasados] = useState(false);
  const [erro, setErro] = useState("");
  const [carregando, setCarregando] = useState(true);

  const obterPrazos = useCallback(
    () => api.prazos.listar({
      status: status || undefined,
      somente_atrasados: atrasados || undefined,
    }),
    [status, atrasados],
  );

  useEffect(() => {
    let ativo = true;
    obterPrazos()
      .then((dados) => {
        if (ativo) {
          setPrazos(dados);
          setErro("");
        }
      })
      .catch((error: unknown) => {
        if (ativo) setErro(error instanceof Error ? error.message : "Não foi possível carregar os prazos.");
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });
    return () => { ativo = false; };
  }, [obterPrazos]);

  async function carregar() {
    try {
      setPrazos(await obterPrazos());
      setErro("");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível carregar os prazos.");
    } finally {
      setCarregando(false);
    }
  }

  async function atualizar(prazo: PrazoApi, novoStatus: StatusPrazo) {
    setErro("");
    try {
      await api.prazos.atualizar(prazo.id_prazo, { status: novoStatus });
      await carregar();
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível atualizar o prazo.");
    }
  }

  function atualizarFiltroStatus(valor: StatusPrazo | "") {
    setErro("");
    setCarregando(true);
    setStatus(valor);
  }

  function atualizarFiltroAtrasados(valor: boolean) {
    setErro("");
    setCarregando(true);
    setAtrasados(valor);
  }

  function atualizarLista() {
    setErro("");
    setCarregando(true);
    void carregar();
  }

  const prazosCalendario = prazos.map((prazo) => ({
    prazo: new Date(`${prazo.data_vencimento}T12:00:00`),
    numeroProcesso: String(prazo.id_processo),
    tipo: prazo.descricao,
  }));

  return (
    <main className="min-h-screen px-6 py-10 sm:px-10">
      <section className="mx-auto max-w-5xl space-y-6">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-3xl font-semibold">Prazos</h1>
            <p className="text-sm text-muted-foreground">Prazos carregados da API e vinculados aos processos.</p>
          </div>
          <Button asChild variant="outline"><Link href="/processos">Processos</Link></Button>
        </header>

        <div className="grid gap-6 lg:grid-cols-[auto_1fr]">
          <PrazosCalendario prazos={prazosCalendario} />

          <section className="space-y-4">
            <div className="flex flex-wrap items-end gap-3">
              <label className="grid gap-1 text-sm">
                Status
                <select
                  className="h-10 rounded-md border bg-background px-3"
                  value={status}
                  onChange={(evento) => atualizarFiltroStatus(evento.target.value as StatusPrazo | "")}
                >
                  <option value="">Todos</option>
                  {Object.entries(statusLabels).map(([valor, rotulo]) => (
                    <option key={valor} value={valor}>{rotulo}</option>
                  ))}
                </select>
              </label>
              <label className="flex items-center gap-2 self-end pb-2 text-sm">
                <input
                  type="checkbox"
                  checked={atrasados}
                  onChange={(evento) => atualizarFiltroAtrasados(evento.target.checked)}
                />
                Somente atrasados
              </label>
              <Button className="self-end" variant="outline" onClick={atualizarLista}>
                Atualizar
              </Button>
            </div>

            {erro && (
              <p role="alert" className="text-sm text-destructive">
                {erro} <Link className="underline" href="/login">Verifique a sessão</Link>
              </p>
            )}
            {carregando ? (
              <p role="status">Carregando prazos…</p>
            ) : prazos.length === 0 ? (
              <p className="text-sm text-muted-foreground">Nenhum prazo encontrado.</p>
            ) : (
              <ul className="grid gap-3">
                {prazos.map((prazo) => (
                  <li key={prazo.id_prazo} className="rounded-lg border p-4">
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-1">
                        <p className="font-medium">{prazo.descricao}</p>
                        <p className="text-sm text-muted-foreground">
                          Vencimento: {formatarData(prazo.data_vencimento)} ·{" "}
                          {prazo.atrasado
                            ? "Atrasado"
                            : prazo.dias_restantes === 0
                              ? "Vence hoje"
                              : `${prazo.dias_restantes} dia(s)`}
                        </p>
                        <Link className="text-sm text-primary underline" href={`/processos/${encodeURIComponent(String(prazo.id_processo))}`}>
                          Abrir processo #{prazo.id_processo}
                        </Link>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-sm">{statusLabels[prazo.status]}</span>
                        {prazo.status === "pendente" && (
                          <>
                            <Button size="sm" onClick={() => void atualizar(prazo, "concluido")}>
                              Concluir
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => void atualizar(prazo, "cancelado")}>
                              Cancelar
                            </Button>
                          </>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </section>
    </main>
  );
}
