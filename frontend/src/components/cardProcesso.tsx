import { Button } from "./ui/button";
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "./ui/badge";
import type {Processo, Parte} from "../../types/processo";
import type { ReactElement } from "react";
import { HoverCard, HoverCardContent, HoverCardTrigger } from "./ui/hover-card";

export default function CardProcesso({processo}: {processo: Processo}) {
    const poloAtivo = formatarPartes(processo.partes.poloAtivo);
    const poloPassivo = formatarPartes(processo.partes.poloPassivo);
    return(
        <Card>
        <CardHeader>
            <CardTitle>Processo {processo.numeroProcesso}</CardTitle>
            <CardDescription>{poloAtivo} x {poloPassivo}</CardDescription>
            <CardAction>
                {processo.necessitaAcao && <Badge variant="destructive">Necessita ação</Badge>}
            </CardAction>
        </CardHeader>
        <CardContent>
            <p>{processo.detalhes}</p>
        </CardContent>
        <CardFooter>
            <Button variant="default">Expandir</Button>
        </CardFooter>
        </Card>
    );
}

function formatarNome(parte: Parte): ReactElement {
    if (parte.associado) {
        return <HoverCard openDelay={100} closeDelay={200}>
                    <HoverCardTrigger>
                        <span className="font-semibold">{parte.nomeRazaoSocial}</span>
                    </HoverCardTrigger>
                    <HoverCardContent side="top" align="start">
                        <p>Associado</p>
                    </HoverCardContent>
                </HoverCard>;
    } else {
        return <span>{parte.nomeRazaoSocial}</span>;
    }
}

function formatarPartes(partes: Parte[]): ReactElement {
    return <>{
        partes.map((p, i) => {
        if (i == partes.length - 1) {
            return <span key={i}>{formatarNome(p)}</span>;
        } else if (i == partes.length - 2) {
            return <span key={i}>{formatarNome(p)} e </span>;
        }
        return <span key={i}>{formatarNome(p)}, </span>;
    })}</>;
}