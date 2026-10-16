import { Button } from "./ui/button";
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "./ui/badge";
import type Processo from "../../types/processo";

export default function CardProcesso({processo}: {processo: Processo}) {
    const poloAtivo = processo.partes.poloAtivo.map(p => p.nomeRazaoSocial).join(", ");
    const poloPassivo = processo.partes.poloPassivo.map(p => p.nomeRazaoSocial).join(", ");
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