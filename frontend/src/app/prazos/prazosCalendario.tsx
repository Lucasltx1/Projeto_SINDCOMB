"use client";
import { Calendar, CalendarDayButton } from "@/components/ui/calendar";
import { Card, CardContent, CardFooter, CardHeader } from "@/components/ui/card";
import { ptBR } from "react-day-picker/locale/pt-BR";
import { Prazo } from "../../../types/processo";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import Link from "next/link";

export default function PrazosCalendario({prazos}: {prazos?: Prazo[]}) {
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
            selected={prazos?.map(p => p.prazo)}
            onSelect={() => {}}
            components={{
                DayButton: ({children, modifiers, day, ...props}) => {
                    if (modifiers.selected) {
                        const prazo =  prazos?.find(p => p.prazo.toDateString() == day.date.toDateString())
                        return (
                            <Tooltip>
                                <TooltipContent>
                                    <p>{prazo?.tipo} | {prazo?.numeroProcesso}</p>
                                </TooltipContent>
                                <TooltipTrigger asChild>
                                    <CalendarDayButton day={day} modifiers={modifiers} {...props}>
                                        {children}
                                        <Link href={`/processos/${prazo?.numeroProcesso}`} className="absolute inset-0 z-10" />
                                    </CalendarDayButton>
                                </TooltipTrigger>
                            </Tooltip>
                        )
                    }
                    return (
                        <CalendarDayButton day={day} modifiers={modifiers} {...props}>
                            {children}
                        </CalendarDayButton>
                    )
            }
            }}
            />
            </CardContent>
            <CardFooter>
                {prazos && prazos.length > 0 ? `Prazos: ${prazos.map(p => p.prazo.toLocaleDateString("pt-BR")).join(", ")}` : "Nenhum prazo no momento."}
            </CardFooter>
            </Card>
    );
}