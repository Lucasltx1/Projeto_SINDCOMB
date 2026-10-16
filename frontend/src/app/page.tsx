
import CardProcesso from "@/components/cardProcesso";
import { Label } from "@/components/ui/label"
import { loremIpsum } from "lorem-ipsum";
import type { Processo } from "../../types/processo";

const processos: Processo[] = [
  { numeroProcesso: "NNNNNNN-DD.AAAA.8.19.OOOO",
    partes: {
        poloAtivo: [{nomeRazaoSocial: "Fulano de Tal", cpfCnpj: "123.456.789-00"}, {nomeRazaoSocial: "Cicrano de Tal", cpfCnpj: "123.456.789-00"}],
        poloPassivo: [{nomeRazaoSocial: "Posto X", cpfCnpj: "12.345.678/0001-00", associado: true}]
    },
     detalhes: loremIpsum({ count: 1, units: "paragraphs" }),
     necessitaAcao: true 
  },
  { numeroProcesso: "NNNNNNN-DD.AAAA.8.19.OOOO",
    partes: {
        poloAtivo: [{nomeRazaoSocial: "Beltrano de Tal", cpfCnpj: "123.456.789-00"}],
        poloPassivo: [{nomeRazaoSocial: "Posto Y", cpfCnpj: "12.345.678/0001-00", associado: true}]
    },
     detalhes: loremIpsum({ count: 1, units: "paragraphs" }),
     necessitaAcao: false 
  },
]
export default function HomePage() {
  return (
    <main className="min-h-screen px-6 py-12 sm:px-10">
      <section className="mx-auto max-w-5xl">
        <Label htmlFor="sindcomb" >
          SINDCOMB · Jurídico
        </Label>
        <div id="processos" className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {processos.map((processo, index) => (
          <CardProcesso
            key={index}
            processo={processo}
          />
        ))}

        </div>
      </section>
    </main>
  );
}
