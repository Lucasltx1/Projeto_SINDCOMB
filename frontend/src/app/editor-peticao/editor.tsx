"use client";

import { Skeleton } from "@/components/ui/skeleton";
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
          return (
    <div className="flex w-full max-w-xs flex-col gap-2">
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-full" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
    }
    return <EditorContent editor={editor} />;
}