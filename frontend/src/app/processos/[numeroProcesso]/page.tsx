import { loremIpsum } from "lorem-ipsum";
import LinhaDoTempo from "./linhaDoTempo";

export default async function ProcessoPage({params}: {params: Promise<{numeroProcesso: string}>}) {
    const {numeroProcesso} = await params;
    
    return(
        <main className="min-h-screen px-6 py-12 sm:px-10">
            <section className="mx-auto max-w-5xl">
                <h1 className="text-2xl font-bold">Processo {numeroProcesso}</h1>
                <h2>Movimentações</h2>
                <LinhaDoTempo movimentacoes={[
                    {data: "2026-01-01", descricao: "Audiência de conciliação", tipo: "Audiência", resumo: loremIpsum()},
                    {data: "2026-02-01", descricao: "Despacho do juiz", tipo: "Despacho", resumo: loremIpsum()},
                    {data: "2026-03-01", descricao: "Decisão do juiz", tipo: "Decisão", resumo: loremIpsum()},
                    {data: "2026-04-01", descricao: "Sentença do juiz", tipo: "Sentença", resumo: loremIpsum()},
                    {data: "2026-05-01", descricao: "Recurso interposto", tipo: "Recurso", resumo: loremIpsum()},
                    {data: "2026-06-01", descricao: "Outros atos processuais", tipo: "Outros", resumo: loremIpsum()},
                ]} />
            </section>
        </main>
    );
}