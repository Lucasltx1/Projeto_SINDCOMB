export type PapelUsuario = "administrador" | "advogado" | "visualizador";
export type StatusPrazo = "pendente" | "concluido" | "cancelado";
export type StatusProcesso =
  | "novo"
  | "em_acompanhamento"
  | "aguardando_prazo"
  | "suspenso"
  | "encerrado";

export type UsuarioPerfil = {
  id_usuario?: number;
  nome: string;
  papel: PapelUsuario;
  email?: string | null;
  ativo?: boolean;
  primeiro_acesso?: boolean;
};

export type ModeloPeticao = {
  id_modelo: number;
  nome: string;
  tipo: string;
  conteudo: string;
  ativo: boolean;
  criado_em?: string;
};

export type Prazo = {
  id_prazo: number;
  id_processo: number;
  descricao: string;
  data_vencimento: string;
  status: StatusPrazo;
  atrasado: boolean;
  dias_restantes: number;
  id_usuario?: number | null;
  responsavel?: string | null;
};

export type ResponsavelPrazo = {
  id_usuario: number;
  nome: string;
  oab: string;
};

export type Processo = {
  id: string;
  status: string;
  arquivado: boolean;
  dados: {
    numero: string;
    tribunal: string;
    classe?: string | null;
    assunto: string;
    fonte_url?: string | null;
    origem_dados?: "datajud" | "djen" | null;
    consultado_em?: string | null;
    data_ultima_verificacao_fonte?: string | null;
  };
  triagem: {
    relevancia: string;
    justificativa: string;
    confianca: number;
  };
};

export type Comentario = {
  id_comentario: number;
  conteudo: string;
  autor?: string | null;
  criado_em: string;
};

export type Documento = {
  id_documento: number;
  nome: string;
  data_upload: string;
  id_peticao?: number | null;
};

export type Peticao = {
  id_peticao: number;
  tipo: string;
  status: "rascunho" | "em_revisao" | "aprovada" | "rejeitada" | "protocolada" | string;
  versao_atual: number;
  descricao?: string | null;
  conteudo: string;
};

export type VersaoPeticao = {
  id_versao: number;
  numero_versao: number;
  data_versao: string;
  conteudo: string;
};

export type AuditoriaEvento = {
  id: number;
  operacao: string;
  descricao: string;
  resultado: string;
  ocorrido_em: string;
};

export type Sincronizacao = {
  id_sincronizacao: number;
  status: string;
  quantidade_atualizacoes: number;
  descricao: string;
  data_hora: string;
};

export class ApiError extends Error {
  readonly status: number;
  readonly body?: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers ?? {});
  const method = (init.method ?? "GET").toUpperCase();
  if (!(init.body instanceof FormData) && !headers.has("Content-Type") && method !== "GET" && method !== "DELETE") {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers,
  });

  const contentType = response.headers.get("content-type") ?? "";
  const payload = contentType.includes("application/json") ? await response.json().catch(() => undefined) : undefined;

  if (!response.ok) {
    const detail = payload && typeof payload === "object" && "detail" in payload ? String((payload as { detail?: unknown }).detail ?? "Erro da API") : "Erro da API";
    throw new ApiError(response.status, detail, payload);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (payload === undefined) {
    return response.text() as unknown as T;
  }

  return payload as T;
}

async function requestFile(path: string, init: RequestInit = {}): Promise<Blob> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
  });
  if (!response.ok) {
    const text = await response.text().catch(() => "Erro ao baixar arquivo");
    throw new ApiError(response.status, text || "Erro ao baixar arquivo");
  }
  return response.blob();
}

const api = {
  auth: {
    perfil: () => request<UsuarioPerfil>("/api/v1/auth/me"),
    csrf: () => request<{ csrf_token: string }>("/api/v1/auth/csrf"),
    logout: (csrfToken: string) =>
      request<void>("/api/v1/auth/logout", {
        method: "POST",
        headers: { "X-CSRF-Token": csrfToken },
      }),
    solicitarRecuperacao: (email: string) =>
      request<{ mensagem?: string }>("/api/v1/auth/solicitar-recuperacao", {
        method: "POST",
        body: JSON.stringify({ email }),
      }),
    verificarEmail: (token: string) =>
      request<{ mensagem?: string }>(`/api/v1/auth/verificar-email?token=${encodeURIComponent(token)}`),
  },
  sistema: {
    health: () => request<{ status: string; sistema: string; banco: string }>("/health"),
    readiness: () => request<{ status: string; banco: string; cache: string }>("/ready"),
  },
  processos: {
    listar: (params?: { arquivado?: boolean }) => {
      const query = params ? new URLSearchParams({ arquivado: String(!!params.arquivado) }) : new URLSearchParams();
      return request<Processo[]>(`/api/v1/processos?${query.toString()}`);
    },
    triagem: ({ numero }: { numero: string }) =>
      request<{ mensagem: string }>("/api/v1/processos/triagem", {
        method: "POST",
        body: JSON.stringify({ numero }),
      }),
    obter: (id: string) => request<Processo>(`/api/v1/processos/${encodeURIComponent(id)}`),
    auditoria: (id: string, params?: { limite?: number }) =>
      request<{ itens: AuditoriaEvento[] }>(`/api/v1/processos/${encodeURIComponent(id)}/auditoria?${new URLSearchParams({ limite: String(params?.limite ?? 50) }).toString()}`),
    sincronizacoes: (id: string, limite = 50) =>
      request<Sincronizacao[]>(`/api/v1/processos/${encodeURIComponent(id)}/sincronizacoes?limite=${limite}`),
    registrarMovimentacao: (id: string, payload: { texto: string }) =>
      request<{ mensagem?: string }>(`/api/v1/processos/${encodeURIComponent(id)}/movimentacoes`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    alterarStatus: (id: string, payload: { status: StatusProcesso }) =>
      request<{ mensagem?: string }>(`/api/v1/processos/${encodeURIComponent(id)}/status`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
  },
  documentos: {
    listar: (processoId: string) => request<Documento[]>(`/api/v1/processos/${encodeURIComponent(processoId)}/documentos`),
    enviar: (processoId: string, arquivo: File, id_peticao?: number) => {
      const form = new FormData();
      form.append("arquivo", arquivo);
      if (id_peticao !== undefined) form.append("id_peticao", String(id_peticao));
      return request<{ mensagem?: string }>(`/api/v1/processos/${encodeURIComponent(processoId)}/documentos`, {
        method: "POST",
        body: form,
      });
    },
    baixar: (id: number) => requestFile(`/api/v1/documentos/${id}/download`),
    excluir: (id: number) => request<void>(`/api/v1/documentos/${id}`, { method: "DELETE" }),
  },
  comentarios: {
    listar: (processoId: string) => request<Comentario[]>(`/api/v1/processos/${encodeURIComponent(processoId)}/comentarios`),
    criar: (processoId: string, conteudo: string) =>
      request<Comentario>(`/api/v1/processos/${encodeURIComponent(processoId)}/comentarios`, {
        method: "POST",
        body: JSON.stringify({ conteudo }),
      }),
  },
  prazos: {
    listar: (filters?: { status?: StatusPrazo | ""; somente_atrasados?: boolean }) => {
      const params = new URLSearchParams();
      if (filters?.status) params.set("status", filters.status);
      if (filters?.somente_atrasados) params.set("somente_atrasados", "true");
      return request<Prazo[]>(`/api/v1/prazos${params.size ? `?${params.toString()}` : ""}`);
    },
    doProcesso: (processoId: string) => request<Prazo[]>(`/api/v1/processos/${encodeURIComponent(processoId)}/prazos`),
    responsaveis: (processoId: string) => request<ResponsavelPrazo[]>(`/api/v1/processos/${encodeURIComponent(processoId)}/prazos/responsaveis`),
    criar: (processoId: string, payload: { descricao: string; data_vencimento: string; id_usuario_responsavel?: number | null }) =>
      request<Prazo>(`/api/v1/processos/${encodeURIComponent(processoId)}/prazos`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    atualizar: (id: number, payload: Partial<Prazo> & { status?: StatusPrazo }) =>
      request<Prazo>(`/api/v1/prazos/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    excluir: (id: number) => request<void>(`/api/v1/prazos/${id}`, { method: "DELETE" }),
  },
  peticoes: {
    listar: (processoId: string) => request<Peticao[]>(`/api/v1/processos/${encodeURIComponent(processoId)}/peticoes`),
    listarModelos: () => request<ModeloPeticao[]>("/api/v1/peticoes/modelos"),
    criarModelo: (payload: { nome: string; tipo: string; conteudo: string }) =>
      request<ModeloPeticao>("/api/v1/peticoes/modelos", {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    atualizarModelo: (id: number, payload: Partial<ModeloPeticao> & { ativo?: boolean }) =>
      request<ModeloPeticao>(`/api/v1/peticoes/modelos/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    excluirModelo: (id: number) => request<void>(`/api/v1/peticoes/modelos/${id}`, { method: "DELETE" }),
    criar: (processoId: string, payload: { id_modelo?: number; tipo?: string; conteudo?: string }) =>
      request<Peticao>(`/api/v1/processos/${encodeURIComponent(processoId)}/peticoes`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    atualizar: (id: number, payload: Partial<Peticao>) =>
      request<Peticao>(`/api/v1/peticoes/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    alterarStatus: (id: number, payload: { status: string }) =>
      request<Peticao>(`/api/v1/peticoes/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    versoes: (id: number) => request<VersaoPeticao[]>(`/api/v1/peticoes/${id}/versoes`),
    exportar: (id: number, formato: "pdf" | "docx") => requestFile(`/api/v1/peticoes/${id}/exportar?formato=${formato}`),
  },
};

export { api };
export default api;
