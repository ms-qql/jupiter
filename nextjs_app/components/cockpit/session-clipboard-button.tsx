"use client";

// Surface B (PROJ-11): Ein-Klick „Anhängen" direkt im Session-Fenster.
// Öffnet den Datei-Dialog; Drag-and-Drop + Paste laufen über die Session-Textarea
// (siehe sessions/[id]/page.tsx). Der hochgeladene Pfad wird ins Eingabefeld
// eingefügt — ohne Wechsel in den Fileexplorer.

import { useRef } from "react";
import { Paperclip } from "lucide-react";

import { Button } from "@/components/ui/button";

export function SessionClipboardButton({
  onPick,
  disabled,
  uploading,
}: {
  onPick: (files: File[]) => void;
  disabled?: boolean;
  uploading?: boolean;
}) {
  const inputRef = useRef<HTMLInputElement>(null);

  return (
    <>
      <input
        ref={inputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length) onPick(files);
          e.target.value = "";
        }}
      />
      <Button
        type="button"
        variant="outline"
        disabled={disabled || uploading}
        onClick={() => inputRef.current?.click()}
        title="Datei anhängen — oder ins Eingabefeld ziehen / einfügen (Strg/Cmd+V)"
      >
        <Paperclip className="size-4" />
        {uploading ? "Lädt…" : "Anhängen"}
      </Button>
    </>
  );
}
