import { Trace, TraceIcon, TraceLine, TraceTitle } from "@/components/ui/trace";
import type { Movimentacao } from "../../../../types/processo";

export default async function LinhaDoTempo({movimentacoes}: {movimentacoes: Movimentacao[]}) {
    
    return(
        <Trace>
            {movimentacoes.map((mov, index) => (
                <TraceLine key={index}>
                    <TraceIcon>{mov.tipo === "Audiência" ? "🎤" : mov.tipo === "Despacho" ? "📝" : mov.tipo === "Decisão" ? "✅" : mov.tipo === "Sentença" ? "⚖️" : mov.tipo === "Recurso" ? "📄" : "📁"}</TraceIcon>
                    <TraceTitle>{mov.data} - {mov.descricao}</TraceTitle>
                </TraceLine>
            ))}
        </Trace>
    );
}