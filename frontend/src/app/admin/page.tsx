
"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";

const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Usuario = {
  id: string;
  nome: string;
  papel: string;
  primeiro_acesso: boolean;
};

type Advogado = {
  id: string;
  nome: string;
  email: string;
  oab: string;
  ativo: boolean;
  email_verificado: boolean;
  primeiro_acesso: boolean;
};

type Associado = {
  id: number;
  nome: string;
  cpf: string | null;
  email: string | null;
  telefone: string | null;
};

type FormAdvogado = {
  nome: string;
  email: string;
  oab: string;
  ativo: boolean;
};

type FormAssociado = {
  nome: string;
  cpf: string;
  email: string;
  telefone: string;
};

const advogadoVazio: FormAdvogado = {
  nome: "",
  email: "",
  oab: "",
  ativo: true,
};

const associadoVazio: FormAssociado = {
  nome: "",
  cpf: "",
  email: "",
  telefone: "",
};

async function requisicao<T>(
  caminho: string,
  opcoes: RequestInit = {}
): Promise<T> {
  const resposta = await fetch(`${API_URL}${caminho}`, {
    ...opcoes,
    credentials: "include",
    cache: "no-store",
  });

  if (resposta.status === 204) {
    if (!resposta.ok) {
      throw new Error("Operação não concluída.");
    }
    return undefined as T;
  }

  const dados = await resposta.json().catch(() => null);

  if (!resposta.ok) {
    let mensagem = "Não foi possível concluir a operação.";

    if (typeof dados?.detail === "string") {
      mensagem = dados.detail;
    } else if (resposta.status === 401) {
      mensagem = "Sessão expirada. Entre novamente.";
    } else if (resposta.status === 403) {
      mensagem = "Você não tem permissão para esta operação.";
    } else if (resposta.status === 409) {
      mensagem = "O registro não pôde ser alterado.";
    }

    throw new Error(mensagem);
  }

  return dados as T;
}

function mensagemErro(erro: unknown): string {
  return erro instanceof Error
    ? erro.message
    : "Ocorreu um erro inesperado.";
}

function cpfValido(valor: string): boolean {
  const cpf = valor.replace(/\D/g, "");
  if (!/^\d{11}$/.test(cpf) || /^(\d)\1{10}$/.test(cpf)) return false;
  for (let tamanho = 9; tamanho < 11; tamanho++) {
    let soma = 0;
    for (let i = 0; i < tamanho; i++) {
      soma += Number(cpf[i]) * (tamanho + 1 - i);
    }
    const digito = (soma * 10) % 11;
    if ((digito === 10 ? 0 : digito) !== Number(cpf[tamanho])) return false;
  }
  return true;
}

export default function AdminPage() {
  const [perfil, setPerfil] = useState<Usuario | null>(null);
  const [csrfToken, setCsrfToken] = useState("");

  const [advogados, setAdvogados] = useState<Advogado[]>([]);
  const [associados, setAssociados] = useState<Associado[]>([]);

  const [formAdvogado, setFormAdvogado] =
    useState<FormAdvogado>(advogadoVazio);

  const [formAssociado, setFormAssociado] =
    useState<FormAssociado>(associadoVazio);

  const [editandoAdvogado, setEditandoAdvogado] =
    useState<string | null>(null);

  const [editandoAssociado, setEditandoAssociado] =
    useState<number | null>(null);

  const [carregando, setCarregando] = useState(true);
  const [enviando, setEnviando] = useState(false);

  const [erro, setErro] = useState("");
  const [sucesso, setSucesso] = useState("");

  async function carregarListas() {
    const [listaAdvogados, listaAssociados] = await Promise.all([
      requisicao<Advogado[]>("/api/v1/admin/advogados"),
      requisicao<Associado[]>("/api/v1/admin/associados"),
    ]);

    setAdvogados(listaAdvogados);
    setAssociados(listaAssociados);
  }

  useEffect(() => {
    let ativo = true;

    async function iniciar() {
      try {
        const usuario = await requisicao<Usuario>(
          "/api/v1/auth/me"
        );

        if (!ativo) return;

        setPerfil(usuario);

        if (usuario.papel !== "administrador") {
          return;
        }

        const token = await requisicao<{ csrf_token: string }>(
          "/api/v1/auth/csrf"
        );

        const [listaAdvogados, listaAssociados] = await Promise.all([
          requisicao<Advogado[]>("/api/v1/admin/advogados"),
          requisicao<Associado[]>("/api/v1/admin/associados"),
        ]);

        if (!ativo) return;

        setCsrfToken(token.csrf_token);
        setAdvogados(listaAdvogados);
        setAssociados(listaAssociados);
      } catch (falha) {
        if (ativo) {
          setErro(mensagemErro(falha));
        }
      } finally {
        if (ativo) {
          setCarregando(false);
        }
      }
    }

    iniciar();

    return () => {
      ativo = false;
    };
  }, []);

  function limparMensagens() {
    setErro("");
    setSucesso("");
  }

  function iniciarEdicaoAdvogado(advogado: Advogado) {
    limparMensagens();

    setEditandoAdvogado(advogado.id);
    setFormAdvogado({
      nome: advogado.nome,
      email: advogado.email,
      oab: advogado.oab,
      ativo: advogado.ativo,
    });
  }

  function cancelarEdicaoAdvogado() {
    setEditandoAdvogado(null);
    setFormAdvogado(advogadoVazio);
  }

  function iniciarEdicaoAssociado(associado: Associado) {
    limparMensagens();

    setEditandoAssociado(associado.id);
    setFormAssociado({
      nome: associado.nome,
      cpf: associado.cpf ?? "",
      email: associado.email ?? "",
      telefone: associado.telefone ?? "",
    });
  }

  function cancelarEdicaoAssociado() {
    setEditandoAssociado(null);
    setFormAssociado(associadoVazio);
  }

  async function salvarAdvogado(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    limparMensagens();
    setEnviando(true);

    try {
      if (!csrfToken) {
        throw new Error("Token CSRF indisponível.");
      }

      if (formAdvogado.nome.trim().length < 3 || formAdvogado.oab.trim().length < 3) {
        throw new Error("Informe um nome e uma OAB válidos.");
      }
      if (!editandoAdvogado && !formAdvogado.email.trim()) {
        throw new Error("Informe o e-mail do advogado.");
      }

      const editando = editandoAdvogado !== null;

      const caminho = editando
        ? `/api/v1/admin/advogados/${editandoAdvogado}`
        : "/api/v1/admin/advogados";

      // A API não permite alterar o e-mail pelo PATCH.
      const dados = editando
        ? {
            nome: formAdvogado.nome.trim(),
            oab: formAdvogado.oab.trim(),
            ativo: formAdvogado.ativo,
          }
        : {
            nome: formAdvogado.nome.trim(),
            email: formAdvogado.email.trim(),
            oab: formAdvogado.oab.trim(),
          };

      await requisicao(caminho, {
        method: editando ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify(dados),
      });

      await carregarListas();

      cancelarEdicaoAdvogado();

      setSucesso(
        editando
          ? "Advogado atualizado com sucesso."
          : "Advogado cadastrado com sucesso."
      );
    } catch (falha) {
      setErro(mensagemErro(falha));
    } finally {
      setEnviando(false);
    }
  }

  async function excluirAdvogado(advogado: Advogado) {
    const confirmado = window.confirm(
      `Deseja realmente excluir o advogado ${advogado.nome}?`
    );

    if (!confirmado) return;

    limparMensagens();
    setEnviando(true);

    try {
      if (!csrfToken) {
        throw new Error("Token CSRF indisponível.");
      }

      await requisicao(
        `/api/v1/admin/advogados/${advogado.id}`,
        {
          method: "DELETE",
          headers: {
            "X-CSRF-Token": csrfToken,
          },
        }
      );

      await carregarListas();
      cancelarEdicaoAdvogado();
      setSucesso("Advogado excluído com sucesso.");
    } catch (falha) {
      setErro(mensagemErro(falha));
    } finally {
      setEnviando(false);
    }
  }

  async function salvarAssociado(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    limparMensagens();
    setEnviando(true);

    try {
      if (!csrfToken) {
        throw new Error("Token CSRF indisponível.");
      }

      if (formAssociado.nome.trim().length < 2) {
        throw new Error("O nome do associado deve conter ao menos 2 caracteres.");
      }
      if (formAssociado.cpf.trim() && !cpfValido(formAssociado.cpf)) {
        throw new Error("CPF inválido. Confira os dígitos informados.");
      }

      const editando = editandoAssociado !== null;

      const caminho = editando
        ? `/api/v1/admin/associados/${editandoAssociado}`
        : "/api/v1/admin/associados";

      const dados = {
        nome: formAssociado.nome.trim(),
        cpf: formAssociado.cpf.trim() || null,
        email: formAssociado.email.trim() || null,
        telefone: formAssociado.telefone.trim() || null,
      };

      await requisicao(caminho, {
        method: editando ? "PATCH" : "POST",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify(dados),
      });

      await carregarListas();
      cancelarEdicaoAssociado();

      setSucesso(
        editando
          ? "Associado atualizado com sucesso."
          : "Associado cadastrado com sucesso."
      );
    } catch (falha) {
      setErro(mensagemErro(falha));
    } finally {
      setEnviando(false);
    }
  }

  async function excluirAssociado(associado: Associado) {
    const confirmado = window.confirm(
      `Deseja realmente excluir o associado ${associado.nome}?`
    );

    if (!confirmado) return;

    limparMensagens();
    setEnviando(true);

    try {
      if (!csrfToken) {
        throw new Error("Token CSRF indisponível.");
      }

      await requisicao(
        `/api/v1/admin/associados/${associado.id}`,
        {
          method: "DELETE",
          headers: {
            "X-CSRF-Token": csrfToken,
          },
        }
      );

      await carregarListas();
      cancelarEdicaoAssociado();
      setSucesso("Associado excluído com sucesso.");
    } catch (falha) {
      setErro(mensagemErro(falha));
    } finally {
      setEnviando(false);
    }
  }

  // Mantém inputs HTML acessíveis: o projeto ainda não possui ui/input.tsx.
  const estiloCampo =
    "flex h-9 w-full rounded-md border border-input bg-background px-3 py-1 text-sm text-foreground shadow-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50";

  if (carregando) {
    return (
      <main className="p-8">
        <p>Verificando acesso administrativo...</p>
      </main>
    );
  }

  if (!perfil) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <h1 className="text-2xl font-bold">
          Acesso administrativo
        </h1>

        <p className="mt-4">
          {erro || "É necessário fazer login para continuar."}
        </p>

        <Link href="/login" className="mt-4 inline-block underline">
          Ir para o login
        </Link>
      </main>
    );
  }

  if (perfil.papel !== "administrador") {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <h1 className="text-2xl font-bold">Acesso negado</h1>

        <p className="mt-4">
          Esta página é exclusiva para administradores.
        </p>

        <Link href="/" className="mt-4 inline-block underline">
          Voltar ao início
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl space-y-8 p-6">
      <header className="space-y-2">
        <h1 className="text-3xl font-bold">
          Painel Administrativo - SINDCOMB
        </h1>

        <p>
          Administrador: <strong>{perfil.nome}</strong>
        </p>

        <p className="text-sm text-muted-foreground">
          Gerenciamento de advogados e associados.
        </p>
      </header>

      {erro && (
        <div
          role="alert"
          className="rounded-md border border-destructive/50 bg-destructive/5 p-3 text-destructive"
        >
          {erro}
        </div>
      )}

      {sucesso && (
        <div
          role="status"
          className="rounded-md border border-emerald-600/30 bg-emerald-600/5 p-3 text-emerald-700 dark:text-emerald-400"
        >
          {sucesso}
        </div>
      )}

      <Card className="gap-5">
        <CardHeader><CardTitle className="text-2xl">Gerenciamento de advogados</CardTitle></CardHeader>
        <CardContent className="space-y-5">

        <form onSubmit={salvarAdvogado} className="grid gap-3">
          <h3 className="font-semibold">
            {editandoAdvogado
              ? "Editar advogado"
              : "Cadastrar advogado"}
          </h3>

          <div className="grid gap-2">
            <Label htmlFor="adv-nome">Nome</Label>
            <input id="adv-nome"
              className={estiloCampo}
              required
              minLength={3}
              maxLength={150}
              value={formAdvogado.nome}
              onChange={(evento) =>
                setFormAdvogado({
                  ...formAdvogado,
                  nome: evento.target.value,
                })
              }
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="adv-email">E-mail</Label>
            <input id="adv-email"
              className={estiloCampo}
              type="email"
              required
              disabled={editandoAdvogado !== null}
              maxLength={255}
              value={formAdvogado.email}
              onChange={(evento) =>
                setFormAdvogado({
                  ...formAdvogado,
                  email: evento.target.value,
                })
              }
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="adv-oab">OAB</Label>
            <input id="adv-oab"
              className={estiloCampo}
              required
              minLength={3}
              maxLength={30}
              value={formAdvogado.oab}
              onChange={(evento) =>
                setFormAdvogado({
                  ...formAdvogado,
                  oab: evento.target.value,
                })
              }
            />
          </div>

          {editandoAdvogado && (
            <Label htmlFor="adv-ativo" className="flex items-center gap-2">
              <input
                type="checkbox"
                id="adv-ativo"
                checked={formAdvogado.ativo}
                onChange={(evento) =>
                  setFormAdvogado({
                    ...formAdvogado,
                    ativo: evento.target.checked,
                  })
                }
              />
              Conta ativa
            </Label>
          )}

          <div className="flex flex-wrap gap-2">
            <Button
              className="w-fit"
              type="submit"
              disabled={enviando || !csrfToken}
            >
              {editandoAdvogado ? "Salvar alterações" : "Cadastrar"}
            </Button>

            {editandoAdvogado && (
              <Button
                type="button"
                variant="outline"
                onClick={cancelarEdicaoAdvogado}
              >
                Cancelar
              </Button>
            )}
          </div>
        </form>

        <h3 className="text-lg font-semibold">
          Advogados cadastrados
        </h3>

        {advogados.length === 0 ? (
          <p>Nenhum advogado encontrado.</p>
        ) : (
          <div className="space-y-3">
            {advogados.map((advogado) => (
              <div
                key={advogado.id}
                className="space-y-2 rounded-md border bg-muted/20 p-4"
              >
                <p className="font-semibold">{advogado.nome}</p>

                <p className="text-sm">
                  E-mail: {advogado.email}
                </p>

                <p className="text-sm">
                  OAB: {advogado.oab}
                </p>

                <p className="text-sm">
                  Situação: <Badge variant={advogado.ativo ? "default" : "secondary"}>{advogado.ativo ? "Ativo" : "Inativo"}</Badge>
                </p>

                <p className="text-sm">
                  E-mail verificado: <Badge variant={advogado.email_verificado ? "outline" : "secondary"}>{advogado.email_verificado ? "Sim" : "Não"}</Badge>
                </p>

                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={enviando}
                    onClick={() => iniciarEdicaoAdvogado(advogado)}
                  >
                    Editar
                  </Button>

                  <Button
                    type="button"
                    variant="destructive"
                    disabled={enviando || !csrfToken}
                    onClick={() => excluirAdvogado(advogado)}
                  >
                    Excluir
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
        </CardContent>
      </Card>

      <Card className="gap-5">
        <CardHeader><CardTitle className="text-2xl">Gerenciamento de associados</CardTitle></CardHeader>
        <CardContent className="space-y-5">

        <form onSubmit={salvarAssociado} className="grid gap-3">
          <h3 className="font-semibold">
            {editandoAssociado !== null
              ? "Editar associado"
              : "Cadastrar associado"}
          </h3>

          <div className="grid gap-2">
            <Label htmlFor="assoc-nome">Nome</Label>
            <input id="assoc-nome"
              className={estiloCampo}
              required
              minLength={2}
              maxLength={150}
              value={formAssociado.nome}
              onChange={(evento) =>
                setFormAssociado({
                  ...formAssociado,
                  nome: evento.target.value,
                })
              }
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="assoc-cpf">CPF (opcional)</Label>
            <input id="assoc-cpf"
              className={estiloCampo}
              maxLength={14}
              value={formAssociado.cpf}
              onChange={(evento) =>
                setFormAssociado({
                  ...formAssociado,
                  cpf: evento.target.value,
                })
              }
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="assoc-email">E-mail (opcional)</Label>
            <input id="assoc-email"
              className={estiloCampo}
              type="email"
              maxLength={255}
              value={formAssociado.email}
              onChange={(evento) =>
                setFormAssociado({
                  ...formAssociado,
                  email: evento.target.value,
                })
              }
            />
          </div>

          <div className="grid gap-2">
            <Label htmlFor="assoc-telefone">Telefone (opcional)</Label>
            <input id="assoc-telefone"
              className={estiloCampo}
              type="tel"
              maxLength={25}
              value={formAssociado.telefone}
              onChange={(evento) =>
                setFormAssociado({
                  ...formAssociado,
                  telefone: evento.target.value,
                })
              }
            />
          </div>

          <div className="flex flex-wrap gap-2">
            <Button
              className="w-fit"
              type="submit"
              disabled={enviando || !csrfToken}
            >
              {editandoAssociado !== null
                ? "Salvar alterações"
                : "Cadastrar"}
            </Button>

            {editandoAssociado !== null && (
              <Button
                type="button"
                variant="outline"
                onClick={cancelarEdicaoAssociado}
              >
                Cancelar
              </Button>
            )}
          </div>
        </form>

        <h3 className="text-lg font-semibold">
          Associados cadastrados
        </h3>

        {associados.length === 0 ? (
          <p>Nenhum associado encontrado.</p>
        ) : (
          <div className="space-y-3">
            {associados.map((associado) => (
              <div
                key={associado.id}
                className="space-y-2 rounded-md border bg-muted/20 p-4"
              >
                <p className="font-semibold">{associado.nome}</p>

                <p className="text-sm">
                  CPF: {associado.cpf || "Não informado"}
                </p>

                <p className="text-sm">
                  E-mail: {associado.email || "Não informado"}
                </p>

                <p className="text-sm">
                  Telefone: {associado.telefone || "Não informado"}
                </p>

                <div className="flex flex-wrap gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    disabled={enviando}
                    onClick={() => iniciarEdicaoAssociado(associado)}
                  >
                    Editar
                  </Button>

                  <Button
                    type="button"
                    variant="destructive"
                    disabled={enviando || !csrfToken}
                    onClick={() => excluirAssociado(associado)}
                  >
                    Excluir
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
        </CardContent>
      </Card>

      <footer className="flex flex-wrap gap-4">
        <Link href="/" className="underline">
          Página inicial
        </Link>

        <Link href="/processos" className="underline">
          Processos
        </Link>
      </footer>
    </main>
  );
}
