"use client";

import {EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
export default function EditorComponent() {
    const editor = useEditor({
        extensions: [StarterKit],
        content: "<p>Escreva sua petição aqui...</p>",
        immediatelyRender: true,
        editorProps: {
            attributes: {
                class: "w-full h-full",
            },
        },
    });
    if (!editor) {
        return <div>Carregando editor...</div>;
    }
    return <EditorContent editor={editor} />;
}