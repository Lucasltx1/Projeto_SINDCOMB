"use client";
import { Calendar } from "@/components/ui/calendar";
import { ptBR } from "react-day-picker/locale/pt-BR";

export default function PrazosCalendario({prazos}: {prazos?: Date[]}) {
    return (
            <Calendar 
            mode="multiple"
            className="rounded-md border w-fit"
            locale={ptBR}
            timeZone="UTC"
            selected={prazos}
            footer={
                <div className="text-center text-sm text-muted-foreground">
                    {prazos && prazos.length > 0 ? `Prazos: ${prazos.map(p => p.toLocaleDateString("pt-BR")).join(", ")}` : "Nenhum prazo no momento."}
                </div>
            }
            />
    );
}