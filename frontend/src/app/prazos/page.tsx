import PrazosCalendario from "./prazosCalendario";

export default function PrazosPage() {
    return (
        <div className="container mx-auto p-4">
            <h1 className="text-2xl font-bold">Prazos</h1>
            <PrazosCalendario prazos={[
                { prazo: new Date("2026-10-21"), numeroProcesso: "001", tipo: "Audiência" },
                { prazo: new Date("2026-10-23"), numeroProcesso: "002", tipo: "Despacho" },
                { prazo: new Date("2026-10-27"), numeroProcesso: "003", tipo: "Decisão" }
            ]} />
        </div>
    );
}