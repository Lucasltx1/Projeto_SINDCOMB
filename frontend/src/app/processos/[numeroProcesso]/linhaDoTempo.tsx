import { Trace, TraceCollapsible, TraceCollapsibleContent, TraceCollapsibleTrigger, TraceIcon, TraceLine, TraceTitle } from "@/components/ui/trace";
import type { Movimentacao } from "../../../../types/processo";
import { MicVocal, Send, Gavel, Whistle, Folder, Astroid } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

export default async function LinhaDoTempo({movimentacoes}: {movimentacoes: Movimentacao[]}) {
    
    return(
        <Trace>
            {movimentacoes.map((mov, index) => (
                <TraceCollapsible key={index}>
                    <TraceCollapsibleTrigger>
                        <TraceLine>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <TraceIcon>{mov.tipo === "Audiência" ? <MicVocal /> : mov.tipo === "Despacho" ? <Send /> : mov.tipo === "Decisão" ? <Gavel /> : mov.tipo === "Sentença" ? <Gavel /> : mov.tipo === "Recurso" ? <Whistle /> : <Folder />}</TraceIcon>
                                </TooltipTrigger>
                                <TooltipContent>
                                    <p>{mov.tipo}</p>
                                </TooltipContent>
                            </Tooltip>
                            <TraceTitle>{mov.data} - {mov.descricao}</TraceTitle>
                        </TraceLine>
                    </TraceCollapsibleTrigger>
                    <TraceCollapsibleContent>
                        <Label><Astroid />Resumo gerado pelo Qwen do SINDCOMB:</Label>
                        <p>{mov.resumo ? mov.resumo : "Sem resumo disponível."}</p>
                    </TraceCollapsibleContent>
                </TraceCollapsible>
            ))}
        </Trace>
    );
}