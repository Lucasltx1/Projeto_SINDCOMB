import PrazosCalendario from "./prazosCalendario";

export default function PrazosPage() {
    return (
        <div className="container mx-auto p-4">
            <h1 className="text-2xl font-bold">Prazos</h1>
            <PrazosCalendario prazos={[new Date("2026-10-21"), new Date("2026-10-23"), new Date("2026-10-27")]} />
        </div>
    );
}