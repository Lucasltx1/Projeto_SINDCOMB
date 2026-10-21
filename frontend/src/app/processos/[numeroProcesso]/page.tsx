import ProcessoDetalhe from "./detalhe";

export default async function ProcessoPage({params}: {params: Promise<{numeroProcesso: string}>}) {
    const {numeroProcesso} = await params;
    return <ProcessoDetalhe processoId={numeroProcesso} />;
}