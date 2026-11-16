"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { ReactNode } from "react";
import {
  Activity,
  ArrowUpRight,
  CalendarDays,
  FileText,
  FolderKanban,
  Home,
  LogIn,
  LogOut,
  Menu,
  Shield,
  X,
} from "lucide-react";
import { useEffect, useState } from "react";
import { ApiError, api } from "@/lib/api";
import type { UsuarioPerfil } from "@/lib/api";

const ROTAS_PUBLICAS = ["/login", "/recuperar_senha", "/redefinir-senha", "/verificar-email"];

function rotaPublica(pathname: string): boolean {
  return ROTAS_PUBLICAS.some((rota) => pathname === rota || pathname.startsWith(`${rota}/`));
}

export function AppShell({ children }: Readonly<{ children: ReactNode }>) {
  const pathname = usePathname();
  const router = useRouter();
  const paginaPublica = rotaPublica(pathname);
  const [perfil, setPerfil] = useState<UsuarioPerfil | null>(null);
  const [carregandoPerfil, setCarregandoPerfil] = useState(!paginaPublica);
  const [erroSessao, setErroSessao] = useState("");
  const [menuAberto, setMenuAberto] = useState(false);
  const [saindo, setSaindo] = useState(false);

  useEffect(() => {
    if (paginaPublica) {
      setPerfil(null);
      setErroSessao("");
      setCarregandoPerfil(false);
      return;
    }

    let ativo = true;
    setCarregandoPerfil(true);
    api.auth.perfil()
      .then((usuario) => {
        if (ativo) {
          setPerfil(usuario);
          setErroSessao("");
        }
      })
      .catch((error: unknown) => {
        if (!ativo) return;
        if (error instanceof ApiError && error.status === 401) {
          setPerfil(null);
          setErroSessao("");
          return;
        }
        setErroSessao(error instanceof Error ? error.message : "Não foi possível verificar a sessão.");
      })
      .finally(() => {
        if (ativo) setCarregandoPerfil(false);
      });

    return () => {
      ativo = false;
    };
  }, [paginaPublica]);

  useEffect(() => {
    setMenuAberto(false);
  }, [pathname]);

  async function sair() {
    setErroSessao("");
    setSaindo(true);
    try {
      const { csrf_token } = await api.auth.csrf();
      await api.auth.logout(csrf_token);
      setPerfil(null);
      router.push("/login");
    } catch (error) {
      setErroSessao(error instanceof Error ? error.message : "Não foi possível encerrar a sessão.");
    } finally {
      setSaindo(false);
    }
  }

  if (paginaPublica) {
    return <>{children}</>;
  }

  const itens = [
    { href: "/", label: "Início", icon: Home },
    ...(perfil && perfil.primeiro_acesso !== true && perfil.papel !== "administrador"
      ? [
          { href: "/processos", label: "Processos", icon: FolderKanban },
          { href: "/prazos", label: "Prazos", icon: CalendarDays },
        ]
      : []),
    ...(perfil?.papel === "advogado" && perfil.primeiro_acesso !== true
      ? [{ href: "/peticoes/modelos", label: "Modelos de petição", icon: FileText }]
      : []),
    ...(perfil?.papel === "administrador" && perfil.primeiro_acesso !== true
      ? [{ href: "/admin", label: "Administração", icon: Shield }]
      : []),
    ...(perfil && perfil.primeiro_acesso !== true
      ? [{ href: "/sistema", label: "Estado do sistema", icon: Activity }]
      : []),
    ...(!perfil ? [{ href: "/login", label: "Entrar", icon: LogIn }] : []),
  ];

  return (
    <div className="min-h-screen bg-[#f4f6fb] text-slate-900">
      {menuAberto && (
        <button
          type="button"
          aria-label="Fechar menu"
          className="fixed inset-0 z-40 bg-slate-950/45 backdrop-blur-[2px] lg:hidden"
          onClick={() => setMenuAberto(false)}
        />
      )}

      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col bg-[#101d3c] text-white shadow-2xl shadow-slate-950/15 transition-transform duration-300 lg:translate-x-0 ${
          menuAberto ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex items-center justify-between px-5 pb-5 pt-6">
          <Link href="/" aria-label="SINDCOMB — início" className="block min-w-0 flex-1">
            <span className="block rounded-2xl bg-white px-3 py-1.5">
              <Image
                src="/sindcomb-logo-recortado.png"
                alt="SINDCOMB Rio"
                width={323}
                height={140}
                priority
                className="h-[76px] w-full object-contain"
              />
            </span>
            <span className="mt-3 block text-[10px] font-semibold tracking-[0.24em] text-slate-400">
              ACOMPANHAMENTO PROCESSUAL
            </span>
          </Link>
          <button
            type="button"
            aria-label="Fechar menu"
            onClick={() => setMenuAberto(false)}
            className="ml-3 rounded-lg p-2 text-slate-300 transition hover:bg-white/10 hover:text-white lg:hidden"
          >
            <X className="size-5" />
          </button>
        </div>

        <div className="mx-5 h-px bg-white/10" />
        <p className="px-6 pb-3 pt-6 text-[10px] font-semibold uppercase tracking-[0.2em] text-slate-500">
          Navegação
        </p>

        <nav aria-label="Navegação principal" className="flex-1 space-y-1 px-3">
          {itens.map(({ href, label, icon: Icon }) => {
            const ativo = href === "/" ? pathname === "/" : pathname === href || pathname.startsWith(`${href}/`);
            return (
              <Link
                key={href}
                href={href}
                aria-current={ativo ? "page" : undefined}
                className={`group flex items-center gap-3 rounded-xl px-3.5 py-3 text-sm font-medium transition ${
                  ativo
                    ? "bg-[#f59e0b] text-[#17213a] shadow-lg shadow-orange-950/15"
                    : "text-slate-300 hover:bg-white/[0.07] hover:text-white"
                }`}
              >
                <Icon className={`size-[18px] shrink-0 ${ativo ? "text-[#17213a]" : "text-slate-400 group-hover:text-orange-300"}`} />
                <span className="flex-1">{label}</span>
                {ativo && <ArrowUpRight className="size-4 opacity-70" />}
              </Link>
            );
          })}
        </nav>

        <div className="mx-5 mb-5 rounded-2xl border border-white/10 bg-white/[0.045] p-4">
          {perfil ? (
            <>
              <div className="flex items-center gap-3">
                <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-[#f59e0b] text-sm font-bold text-[#17213a]">
                  {perfil.nome.trim().charAt(0).toLocaleUpperCase("pt-BR")}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-white">{perfil.nome}</span>
                  <span className="mt-0.5 block text-xs capitalize text-slate-400">{perfil.papel}</span>
                </span>
              </div>
              <button
                type="button"
                onClick={() => void sair()}
                disabled={saindo}
                className="mt-4 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-xs font-medium text-slate-400 transition hover:bg-white/[0.07] hover:text-white disabled:opacity-50"
              >
                <LogOut className="size-4" />
                {saindo ? "Encerrando sessão…" : "Encerrar sessão"}
              </button>
            </>
          ) : carregandoPerfil ? (
            <p role="status" className="text-xs text-slate-400">Verificando sessão…</p>
          ) : (
            <div>
              <p className="text-sm font-semibold text-white">Área de acesso</p>
              <p className="mt-1 text-xs leading-relaxed text-slate-400">
                Entre para acessar os recursos disponíveis à sua conta.
              </p>
            </div>
          )}
          {erroSessao && <p role="alert" className="mt-3 text-xs text-orange-200">{erroSessao}</p>}
        </div>
      </aside>

      <div className="min-w-0 lg:ml-[280px]">
        <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-slate-200/80 bg-white/90 px-4 backdrop-blur-xl lg:hidden">
          <button
            type="button"
            aria-label="Abrir menu"
            aria-expanded={menuAberto}
            onClick={() => setMenuAberto(true)}
            className="rounded-xl border border-slate-200 p-2 text-slate-700 transition hover:bg-slate-100"
          >
            <Menu className="size-5" />
          </button>
          <Image src="/sindcomb-logo-recortado.png" alt="" width={100} height={44} className="h-9 w-[84px] object-contain" />
          <span className="ml-auto text-xs font-medium text-slate-500">Acompanhamento Processual</span>
        </header>
        {children}
      </div>
    </div>
  );
}
