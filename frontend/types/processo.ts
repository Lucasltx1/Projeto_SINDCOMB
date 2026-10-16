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
