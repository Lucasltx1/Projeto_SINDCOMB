import { Trace, TraceCollapsible, TraceCollapsibleContent, TraceCollapsibleTrigger, TraceIcon, TraceLine, TraceTitle } from "@/components/ui/trace";
import type { Movimentacao } from "../../../../types/processo";
import { Activity, Bell, FileText, Gavel, Hourglass, Send } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";

function rotuloFonte(fonte?: Movimentacao["fonte_dados"]): string {
    if (fonte === "datajud") return "DataJud / CNJ";
    if (fonte === "djen") return "DJEN / CNJ";
    if (fonte === "manual") return "Registro manual";
    return "Fonte não informada";
}

function iconeCategoria(categoria: Movimentacao["categoria"]) {
    if (categoria === "intimacao") return <Bell />;
    if (categoria === "despacho" || categoria === "peticao") return <FileText />;
    if (categoria === "sentenca") return <Gavel />;
    if (categoria === "prazo") return <Hourglass />;
    if (categoria === "andamento") return <Send />;
    return <Activity />;
}

function formatarData(valor?: string | null): string {
    if (!valor) return "Data não informada pela fonte";
    const data = new Date(valor);
    if (Number.isNaN(data.getTime())) return "Data não informada pela fonte";
    return new Intl.DateTimeFormat("pt-BR", {
        dateStyle: "medium",
        timeStyle: "short",
    }).format(data);
}

function rotuloData(mov: Movimentacao): string {
    if (mov.data_fonte) return `Data da fonte: ${formatarData(mov.data_fonte)}`;
    if (mov.fonte_dados === "manual") {
        return `Registrada no sistema em ${formatarData(mov.registrada_em)}`;
    }
    return `Data da fonte indisponível · importada em ${formatarData(mov.registrada_em)}`;
}

export default function LinhaDoTempo({movimentacoes}: {movimentacoes: Movimentacao[]}) {
    if (!movimentacoes.length) {
        return <p className="text-sm text-muted-foreground">Ainda não há movimentações importadas para este processo.</p>;
    }

    return (
        <Trace>
            {movimentacoes.map((mov, index) => (
                <TraceCollapsible key={`${mov.data_fonte ?? mov.registrada_em}-${index}`}>
                    <TraceCollapsibleTrigger>
                        <TraceLine>
                            <Tooltip>
                                <TooltipTrigger asChild>
                                    <TraceIcon>{iconeCategoria(mov.categoria)}</TraceIcon>
                                </TooltipTrigger>
                                <TooltipContent><p>{mov.categoria.replaceAll("_", " ")}</p></TooltipContent>
                            </Tooltip>
                            <TraceTitle>
                                <span>{rotuloData(mov)}</span>
                                <span className="ml-2 text-xs text-muted-foreground">{rotuloFonte(mov.fonte_dados)}</span>
                                {mov.requer_atencao && <span className="ml-2 text-xs font-medium text-destructive">Revisar</span>}
                                <p className="mt-1 text-sm font-normal">{mov.resumo}</p>
                            </TraceTitle>
                        </TraceLine>
                    </TraceCollapsibleTrigger>
                    <TraceCollapsibleContent className="space-y-3 pl-10">
                        <div>
                            <Label>Texto da movimentação/publicação</Label>
                            <p className="whitespace-pre-wrap text-sm">{mov.texto}</p>
                        </div>
                        {mov.fonte_url && (
                            <a
                                className="text-sm text-primary underline underline-offset-4"
                                href={mov.fonte_url}
                                target="_blank"
                                rel="noopener noreferrer"
                            >
                                Abrir fonte oficial
                            </a>
                        )}
                    </TraceCollapsibleContent>
                </TraceCollapsible>
            ))}
        </Trace>
    );
}