export default interface Processo {
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

interface Parte {
    nomeRazaoSocial: string;
    cpfCnpj?: string;
    associado?: boolean;
}