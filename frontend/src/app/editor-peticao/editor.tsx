"use client";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EditorContent, useEditor } from "@tiptap/react";
import StarterKit from "@tiptap/starter-kit";
import { useEffect } from "react";

export default function EditorComponent() {
    const editor = useEditor({
        extensions: [StarterKit],
        content: "",
        immediatelyRender: false,
        editorProps: {
            attributes: {
                class: "w-full h-full",
            },
        },
    });

    useEffect(() => {
      if (!editor) {
        return;
      }

      const savedContent = window.localStorage.getItem("editorContent");
      if (!savedContent) {
        return;
      }

      try {
        editor.commands.setContent(JSON.parse(savedContent));
      } catch (error) {
        console.error("Não foi possível carregar o conteúdo salvo do editor.", error);
      }
    }, [editor]);

    if (!editor) {
          return (
    <div className="flex w-full max-w-xs flex-col gap-2">
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
    }
    return (
      <div>
      <Button onClick={() => {
        const content = editor.getJSON();
        window.localStorage.setItem("editorContent", JSON.stringify(content));
      }}>Salvar</Button>
    <EditorContent editor={editor} />
    </div>
  );
}