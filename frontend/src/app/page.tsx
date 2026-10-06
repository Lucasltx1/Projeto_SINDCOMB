export default function HomePage() {
  return (
    <main className="min-h-screen px-6 py-12 sm:px-10">
      <section className="mx-auto max-w-5xl">
        <p className="text-sm font-semibold uppercase tracking-[0.18em] text-blue-700">
          SINDCOMB · Jurídico
        </p>
        <h1 className="mt-3 text-3xl font-bold tracking-tight sm:text-4xl">
          Acompanhamento processual
        </h1>
        <p className="mt-3 max-w-2xl text-base leading-7 text-slate-600">
          A estrutura inicial do front-end está funcionando. As áreas de processos,
          associados, prazos e notificações serão implementadas nesta aplicação.
        </p>
        <div className="mt-8 rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold">Ambiente de desenvolvimento</h2>
          <p className="mt-2 text-sm text-slate-600">
            Esta página confirma que o Next.js iniciou dentro do Docker.
          </p>
        </div>
      </section>
    </main>
  );
}
