
import CardProcesso from "@/components/cardProcesso";
import { Label } from "@/components/ui/label"
import { loremIpsum } from "lorem-ipsum";

const processos = [
  { numeroProcesso: "NNNNNNN-DD.AAAA.8.19.OOOO",
    partes: ["Fulano de Tal", "Posto X"],
     detalhes: loremIpsum({ count: 1, units: "paragraphs" }),
     necessitaAcao: true 
  },
  { numeroProcesso: "NNNNNNN-DD.AAAA.8.19.OOOO",
    partes: ["Cicrano de Tal", "Posto Y"],
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
            numeroProcesso={processo.numeroProcesso}
            partes={processo.partes}
            detalhes={processo.detalhes}
            necessitaAcao={processo.necessitaAcao}
          />
        ))}
        </div>
      </section>
    </main>
  );
}
