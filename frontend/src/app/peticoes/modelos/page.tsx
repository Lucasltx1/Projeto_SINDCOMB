"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import type { ModeloPeticao } from "@/lib/api";

export default function ModelosPage() {
  const [modelos, setModelos] = useState<ModeloPeticao[]>([]);
  const [advogado, setAdvogado] = useState(false);
  const [nome, setNome] = useState("");
  const [tipo, setTipo] = useState("");
  const [conteudo, setConteudo] = useState("");
  const [erro, setErro] = useState("");
  const [mensagem, setMensagem] = useState("");
  const [carregando, setCarregando] = useState(true);

  const carregar = useCallback(async () => {
    const perfil = await api.auth.perfil();
    const podeGerenciar = perfil.papel === "advogado";
    return {
      advogado: podeGerenciar,
      modelos: podeGerenciar ? await api.peticoes.listarModelos() : [],
      erro: podeGerenciar ? "" : "A área de modelos está disponível para advogados.",
    };
  }, []);

  useEffect(() => {
    let ativo = true;
    carregar()
      .then((resultado) => {
        if (!ativo) return;
        setAdvogado(resultado.advogado);
        setModelos(resultado.modelos);
        setErro(resultado.erro);
      })
      .catch((error: unknown) => {
        if (ativo) setErro(error instanceof Error ? error.message : "Falha ao carregar modelos.");
      })
      .finally(() => {
        if (ativo) setCarregando(false);
      });
    return () => { ativo = false; };
  }, [carregar]);

  async function recarregar() {
    const resultado = await carregar();
    setAdvogado(resultado.advogado);
    setModelos(resultado.modelos);
    setErro(resultado.erro);
  }

  async function criar(evento: FormEvent<HTMLFormElement>) {
    evento.preventDefault();
    setErro("");
    setMensagem("");
    try {
      await api.peticoes.criarModelo({ nome, tipo, conteudo });
      setMensagem("Modelo criado.");
      setNome("");
      setTipo("");
      setConteudo("");
      await recarregar();
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Não foi possível criar o modelo.");
    }
  }

  async function atualizar(modelo: ModeloPeticao) {
    const novoNome = window.prompt("Nome do modelo", modelo.nome);
    if (novoNome === null) return;
    const novoTipo = window.prompt("Tipo", modelo.tipo);
    if (novoTipo === null) return;
    const novoConteudo = window.prompt(
      "Conteúdo (use {{processo_numero}}, {{advogado_nome}} e outras variáveis disponíveis)",
      modelo.conteudo,
    );
    if (novoConteudo === null) return;

    setErro("");
    setMensagem("");
    try {
      await api.peticoes.atualizarModelo(modelo.id_modelo, {
        nome: novoNome,
        tipo: novoTipo,
        conteudo: novoConteudo,
      });
      await recarregar();
      setMensagem("Modelo atualizado.");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Falha ao atualizar modelo.");
    }
  }

  async function alterarStatus(modelo: ModeloPeticao) {
    setErro("");
    setMensagem("");
    try {
      if (modelo.ativo) {
        await api.peticoes.excluirModelo(modelo.id_modelo);
      } else {
        await api.peticoes.atualizarModelo(modelo.id_modelo, { ativo: true });
      }
      await recarregar();
      setMensagem(modelo.ativo ? "Modelo desativado." : "Modelo ativado.");
    } catch (error) {
      setErro(error instanceof Error ? error.message : "Falha ao atualizar status do modelo.");
    }
  }

  return (
    <main className="min-h-screen px-6 py-10 sm:px-10">
      <section className="mx-auto max-w-5xl space-y-6">
        <header className="flex justify-between gap-4">
          <div>
            <h1 className="text-3xl font-semibold">Modelos de petição</h1>
            <p className="text-sm text-muted-foreground">
              Variáveis: processo_numero, processo_tribunal, processo_classe, processo_assunto,
              associado_nome, advogado_nome, advogado_oab, vara e comarca.
            </p>
          </div>
          <Button asChild variant="outline"><Link href="/processos">Voltar</Link></Button>
        </header>

        {erro && <p role="alert" className="text-destructive">{erro}</p>}
        {mensagem && <p role="status">{mensagem}</p>}
        {carregando && <p role="status">Carregando…</p>}

        {advogado && (
          <form onSubmit={criar} className="grid gap-3 rounded-lg border p-4">
            <h2 className="text-xl font-semibold">Novo modelo</h2>
            <input
              required
              minLength={2}
              className="h-10 rounded-md border bg-background px-3"
              placeholder="Nome"
              value={nome}
              onChange={(evento) => setNome(evento.target.value)}
            />
            <input
              required
              minLength={2}
              className="h-10 rounded-md border bg-background px-3"
              placeholder="Tipo"
              value={tipo}
              onChange={(evento) => setTipo(evento.target.value)}
            />
            <textarea
              required
              maxLength={200000}
              rows={8}
              className="rounded-md border bg-background p-3"
              placeholder="Conteúdo"
              value={conteudo}
              onChange={(evento) => setConteudo(evento.target.value)}
            />
            <Button className="w-fit">Salvar modelo</Button>
          </form>
        )}

        <div className="grid gap-3">
          {modelos.map((modelo) => (
            <article key={modelo.id_modelo} className="flex flex-wrap justify-between gap-3 rounded-lg border p-4">
              <div>
                <p className="font-semibold">
                  {modelo.nome} · {modelo.tipo} {modelo.ativo ? "" : "(inativo)"}
                </p>
                <details className="mt-2">
                  <summary className="cursor-pointer text-sm">Prévia</summary>
                  <pre className="mt-2 whitespace-pre-wrap text-sm">{modelo.conteudo}</pre>
                </details>
              </div>
              {advogado && (
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" onClick={() => void atualizar(modelo)}>Editar</Button>
                  <Button
                    size="sm"
                    variant={modelo.ativo ? "destructive" : "secondary"}
                    onClick={() => void alterarStatus(modelo)}
                  >
                    {modelo.ativo ? "Desativar" : "Ativar"}
                  </Button>
                </div>
              )}
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
