import EditorComponent from "./editor";


export default function EditorPeticaoPage() {

    return (
        <div className="flex flex-col items-center justify-center py-2">
        <h1 className="text-4xl font-bold mb-4">Editor de Petição</h1>
        <div className="w-full h-full max-w-4xl p-4 border rounded-lg shadow-md">
            <EditorComponent />
        </div>
        </div>
    );
    }