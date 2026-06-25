"use client";

// Surface B (PROJ-11): Ein-Klick „Anhängen" direkt im Session-Fenster.
// Öffnet den Datei-Dialog; Drag-and-Drop + Paste laufen über die Session-Textarea
// (siehe sessions/[id]/page.tsx). Der hochgeladene Pfad wird ins Eingabefeld
// eingefügt — ohne Wechsel in den Fileexplorer.

import { useRef } from "react";
import { Loader2, Paperclip } from "lucide-react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function SessionClipboardButton({
  onPick,
  disabled,
  uploading,
  className,
}: {
  onPick: (files: File[]) => void;
  disabled?: boolean;
  uploading?: boolean;
  className?: string;
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
        size="icon"
        variant="outline"
        disabled={disabled || uploading}
        onClick={() => inputRef.current?.click()}
        aria-label={uploading ? "Datei wird angehängt…" : "Datei anhängen"}
        title={
          uploading
            ? "Datei wird angehängt…"
            : "Datei anhängen — oder ins Eingabefeld ziehen / einfügen (Strg/Cmd+V)"
        }
        className={cn("shrink-0", className)}
      >
        {uploading ? (
          <Loader2 className="size-4 animate-spin" />
        ) : (
          <Paperclip className="size-4" />
        )}
      </Button>
    </>
  );
}
