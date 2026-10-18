export default async function ProcessoPage({params}: {params: Promise<{numeroProcesso: string}>}) {
    const {numeroProcesso} = await params;
    return(
        <main className="min-h-screen px-6 py-12 sm:px-10">
            <section className="mx-auto max-w-5xl">
                <h1 className="text-2xl font-bold">Processo {numeroProcesso}</h1>
                <h2>Movimentações</h2>
            </section>
        </main>
    );
}