export interface Processo {
    numeroProcesso: string;
    dataAbertura?: string;
    dataUltimaMovimentacao?: string;
    partes:{
        poloAtivo: Parte[];
        poloPassivo: Parte[];
    };
    detalhes: string;
    necessitaAcao?: boolean;
}

export interface Parte {
    nomeRazaoSocial: string;
    cpfCnpj?: string;
    associado?: boolean;
}

export interface Movimentacao {
    texto: string;
    resumo: string;
    categoria: "andamento" | "intimacao" | "despacho" | "sentenca" | "peticao" | "prazo" | "outro";
    requer_atencao: boolean;
    fonte_url?: string | null;
    fonte_dados?: "datajud" | "djen" | "manual" | null;
    data_fonte?: string | null;
    registrada_em: string;
}

export interface Prazo {
    prazo: Date;
    numeroProcesso: string;
    tipo: "Audiência" | "Despacho" | "Decisão" | "Sentença" | "Recurso" | "Outros";
}