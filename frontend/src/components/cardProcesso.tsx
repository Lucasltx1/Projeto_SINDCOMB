import { Button } from "./ui/button";
import { Card, CardAction, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "./ui/badge";

export default function CardProcesso({numeroProcesso, partes, detalhes, necessitaAcao}: {numeroProcesso: string, partes: string[], detalhes: string, necessitaAcao?: boolean}) {
    return(
        <Card>
        <CardHeader>
            <CardTitle>Processo {numeroProcesso}</CardTitle>
            <CardDescription>{partes.join(" x ")}</CardDescription>
            <CardAction>
                {necessitaAcao && <Badge variant="destructive">Necessita ação</Badge>}
            </CardAction>
        </CardHeader>
        <CardContent>
            <p>{detalhes}</p>
        </CardContent>
        <CardFooter>
            <Button variant="default">Expandir</Button>
        </CardFooter>
        </Card>
    );
}