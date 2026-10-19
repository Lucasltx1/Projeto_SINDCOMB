"use client";
import { Calendar } from "@/components/ui/calendar";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { ptBR } from "react-day-picker/locale/pt-BR";

export default function PrazosCalendario({prazos}: {prazos?: Date[]}) {
    return (
            <Card className="w-fit">
            <CardHeader>
                Calendário de Prazos
            </CardHeader>
            <CardContent>
            <Calendar 
            mode="multiple"
            className="w-full"
            locale={ptBR}
            timeZone="UTC"
            selected={prazos}
            onSelect={() => {}}
            />
            </CardContent>
            <CardFooter>
                {prazos && prazos.length > 0 ? `Prazos: ${prazos.map(p => p.toLocaleDateString("pt-BR")).join(", ")}` : "Nenhum prazo no momento."}
            </CardFooter>
            </Card>
    );
}