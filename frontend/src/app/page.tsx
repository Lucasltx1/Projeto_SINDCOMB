"use client";

import Image from "next/image";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ArrowRight,
  CalendarDays,
  FileText,
  FolderKanban,
  ShieldCheck,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { ApiError, api } from "@/lib/api";
import type { UsuarioPerfil } from "@/lib/api";

const recursos = [
  {
    titulo: "Processos organizados",
    descricao: "Consulte movimentações, documentos e histórico processual em uma visão integrada.",
    icon: FolderKanban,
  },
  {
    titulo: "Prazos em foco",
    descricao: "Acompanhe vencimentos e mantenha as atividades jurídicas em dia.",
    icon: CalendarDays,
  },
  {
    titulo: "Gestão com segurança",
    descricao: "Acesso organizado por perfil, com trilha de auditoria e informações centralizadas.",
    icon: ShieldCheck,
  },
];

export default function HomePage() {
  const [perfil, setPerfil] = useState<UsuarioPerfil | null>(null);
  const [verificando, setVerificando] = useState(true);
  const [erro, setErro] = useState("");

  useEffect(() => {
    let ativo = true;
    api.auth.perfil()
      .then((usuario) => {
        if (ativo) setPerfil(usuario);
      })
      .catch((error: unknown) => {
        if (!ativo) return;
        if (!(error instanceof ApiError && error.status === 401)) {
          setErro(error instanceof Error ? error.message : "Não foi possível verificar a sessão.");
        }
      })
      .finally(() => {
        if (ativo) setVerificando(false);
      });

    return () => {
      ativo = false;
    };
  }, []);

  const destinoPrincipal = perfil?.papel === "administrador" ? "/admin" : "/processos";

  return (
    <main className="min-h-[calc(100vh-4rem)] px-4 py-6 sm:px-7 sm:py-9 lg:px-10">
      <div className="mx-auto max-w-6xl space-y-8">
        <section className="relative isolate overflow-hidden rounded-[2rem] bg-[#101d3c] px-6 py-8 text-white shadow-2xl shadow-slate-900/10 sm:px-10 sm:py-12 lg:px-14 lg:py-14">
          <div
            aria-hidden="true"
            className="absolute -right-24 -top-32 -z-10 size-[27rem] rounded-full bg-[#f59e0b]/20 blur-[90px]"
          />
          <div
            aria-hidden="true"
            className="absolute -bottom-48 left-1/4 -z-10 size-[24rem] rounded-full bg-blue-400/10 blur-[80px]"
          />
          <div className="grid items-center gap-12 lg:grid-cols-[1.1fr_0.9fr]">
            <div>
              <div className="mb-8 inline-flex rounded-2xl bg-white px-4 py-1.5 shadow-lg shadow-slate-950/10">
                <Image
                  src="/sindcomb-logo-recortado.png"
                  alt="SINDCOMB Rio"
                  width={323}
                  height={140}
                  priority
                  className="h-[82px] w-[210px] object-contain sm:w-[245px]"
                />
              </div>
              <p className="mb-3 text-xs font-semibold uppercase tracking-[0.22em] text-orange-300">
                Gestão jurídica integrada
              </p>
              <h1 className="max-w-2xl text-3xl font-semibold leading-tight tracking-tight sm:text-4xl lg:text-5xl">
                {perfil ? `Olá, ${perfil.nome}.` : "Acompanhe cada processo com mais clareza."}
              </h1>
              <p className="mt-5 max-w-xl text-base leading-7 text-slate-300 sm:text-lg">
                {perfil
                  ? "Seu espaço de trabalho para consultar processos, prazos e ferramentas disponíveis ao seu perfil."
                  : "Processos, prazos, documentos e movimentações em um só lugar, para apoiar o trabalho jurídico do SINDCOMB."}
              </p>
              {erro && <p role="alert" className="mt-4 text-sm text-orange-200">{erro}</p>}
              <div className="mt-8 flex flex-wrap items-center gap-3">
                {verificando ? (
                  <p role="status" className="text-sm text-slate-300">Verificando sessão…</p>
                ) : perfil ? (
                  <Button
                    asChild
                    className="h-12 rounded-xl bg-[#f59e0b] px-5 font-semibold text-[#17213a] hover:bg-orange-300"
                  >
                    <Link href={destinoPrincipal}>
                      {perfil.papel === "administrador" ? "Abrir administração" : "Abrir processos"}
                      <ArrowRight className="ml-2 size-4" />
                    </Link>
                  </Button>
                ) : (
                  <>
                    <Button
                      asChild
                      className="h-12 rounded-xl bg-[#f59e0b] px-5 font-semibold text-[#17213a] hover:bg-orange-300"
                    >
                      <Link href="/login">
                        Entrar no sistema
                        <ArrowRight className="ml-2 size-4" />
                      </Link>
                    </Button>
                    <Button
                      asChild
                      variant="outline"
                      className="h-12 rounded-xl border-white/25 bg-white/5 px-5 text-white hover:bg-white/10 hover:text-white"
                    >
                      <Link href="/recuperar_senha">Recuperar acesso</Link>
                    </Button>
                  </>
                )}
              </div>
            </div>

            <div className="relative mx-auto w-full max-w-[390px]">
              <div
                aria-hidden="true"
                className="absolute -inset-4 rotate-3 rounded-[2rem] border border-white/10 bg-white/[0.035]"
              />
              <div className="relative rounded-[1.7rem] border border-white/15 bg-white/[0.08] p-5 shadow-xl backdrop-blur-md sm:p-6">
                <div className="flex items-center justify-between border-b border-white/10 pb-5">
                  <div>
                    <p className="text-xs font-medium uppercase tracking-[0.16em] text-slate-400">
                      Ambiente de trabalho
                    </p>
                    <p className="mt-1 text-lg font-semibold">Acompanhamento jurídico</p>
                  </div>
                  <span className="flex size-11 items-center justify-center rounded-2xl bg-orange-400/15 text-orange-300">
                    <ShieldCheck className="size-5" />
                  </span>
                </div>
                <div className="mt-5 space-y-3">
                  {[
                    { icon: FolderKanban, label: "Processos", sublabel: "Consulta e acompanhamento" },
                    { icon: CalendarDays, label: "Prazos", sublabel: "Agenda e vencimentos" },
                    { icon: FileText, label: "Documentos", sublabel: "Arquivos e petições" },
                  ].map(({ icon: Icon, label, sublabel }) => (
                    <div
                      key={label}
                      className="flex items-center gap-3 rounded-2xl border border-white/[0.08] bg-slate-950/20 px-4 py-3.5"
                    >
                      <span className="flex size-10 items-center justify-center rounded-xl bg-white/10 text-orange-200">
                        <Icon className="size-[18px]" />
                      </span>
                      <span>
                        <span className="block text-sm font-semibold">{label}</span>
                        <span className="mt-0.5 block text-xs text-slate-400">{sublabel}</span>
                      </span>
                    </div>
                  ))}
                </div>
                <p className="mt-5 text-xs leading-relaxed text-slate-400">
                  Acesso às funcionalidades conforme as permissões da sua conta.
                </p>
              </div>
            </div>
          </div>
        </section>

        <section aria-labelledby="recursos-titulo">
          <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-orange-600">
                Um espaço mais organizado
              </p>
              <h2 id="recursos-titulo" className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
                Tudo o que sua equipe precisa para acompanhar
              </h2>
            </div>
            <span className="text-sm text-slate-500">SINDCOMB · Jurídico</span>
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            {recursos.map(({ titulo, descricao, icon: Icon }) => (
              <article
                key={titulo}
                className="rounded-2xl border border-slate-200/80 bg-white p-5 shadow-sm shadow-slate-900/[0.025] transition duration-200 hover:-translate-y-0.5 hover:border-orange-200 hover:shadow-lg hover:shadow-slate-900/[0.06] sm:p-6"
              >
                <span className="flex size-11 items-center justify-center rounded-xl bg-orange-50 text-orange-600">
                  <Icon className="size-5" />
                </span>
                <h3 className="mt-4 text-base font-semibold text-slate-900">{titulo}</h3>
                <p className="mt-2 text-sm leading-6 text-slate-600">{descricao}</p>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
