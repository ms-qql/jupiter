"use client";

// PROJ-76: Allgemeiner Texteditor für den Fileexplorer (rechte Spalte).
// Lädt den Inhalt via GET /files/text, speichert atomar via PUT /files/text
// mit Hash-basierter Konflikterkennung. Markdown kann zwischen Bearbeiten und
// Vorschau umgeschaltet werden; andere Texttypen bleiben im Rohtext-Modus.

import { useCallback, useEffect, useRef, useState } from "react";
import { Eye, Loader2, Pencil, Save, X } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MarkdownView } from "@/components/cockpit/markdown-view";
import { ApiError, readFileText, writeFileText } from "@/lib/api";
import type { FileEntry, MdIndexEntry, TextFileRead } from "@/lib/types";

const MAX_TEXT_CHARS = 200_000;
const MARKDOWN_EXT = new Set(["md", "markdown"]);

type Mode = "edit" | "preview";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function TextFileEditor({
  entry,
  onClose,
  onSaved,
  onDirtyChange,
  saveRef,
}: {
  entry: FileEntry;
  onClose: () => void;
  onSaved?: () => void;
  onDirtyChange?: (dirty: boolean) => void;
  /** Parent füllt dies mit der Save-Funktion → kann über den Guard-Dialog speichern. */
  saveRef?: React.MutableRefObject<(() => Promise<void>) | null>;
}) {
  const isMarkdown = MARKDOWN_EXT.has(entry.name.toLowerCase().split(".").pop() ?? "");

  const [mode, setMode] = useState<Mode>("edit");
  const [file, setFile] = useState<TextFileRead | null>(null);
  const [draft, setDraft] = useState("");
  const [baseContent, setBaseContent] = useState("");
  const [baseHash, setBaseHash] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const dirty = file !== null && draft !== baseContent;

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  // Load file content on mount
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);
    readFileText(entry.path)
      .then((f) => {
        if (!active) return;
        setFile(f);
        setDraft(f.content);
        setBaseContent(f.content);
        setBaseHash(f.hash);
        setLoading(false);
      })
      .catch((e) => {
        if (!active) return;
        const msg = e instanceof ApiError ? e.message : "Datei konnte nicht geladen werden.";
        setError(msg);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [entry.path]);

  const handleSave = useCallback(async () => {
    if (!file || saving) return;
    setSaving(true);
    try {
      const result = await writeFileText({
        path: file.path,
        content: draft,
        hash: conflict ? baseHash : baseHash,
        force: conflict,
      });
      setFile(result);
      setBaseContent(result.content);
      setBaseHash(result.hash);
      setConflict(false);
      toast.success("Gespeichert");
      onSaved?.();
    } catch (e) {
      if (e instanceof ApiError && e.status === 409) {
        setConflict(true);
        return;
      }
      toast.error(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen");
      throw e;
    } finally {
      setSaving(false);
    }
  }, [file, draft, conflict, baseHash, saving, onSaved]);

  // saveRef für den Parent (Ungespeichert-Dialog).
  useEffect(() => {
    if (saveRef) saveRef.current = handleSave;
    return () => { if (saveRef) saveRef.current = null; };
  }, [handleSave, saveRef]);

  // Strg/Cmd+S → speichern.
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "s") {
        e.preventDefault();
        void handleSave();
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [handleSave]);

  const handleForceSave = useCallback(async () => {
    if (!file || saving) return;
    setSaving(true);
    try {
      const result = await writeFileText({
        path: file.path,
        content: draft,
        hash: baseHash,
        force: true,
      });
      setFile(result);
      setBaseContent(result.content);
      setBaseHash(result.hash);
      setConflict(false);
      toast.success("Überschrieben");
      onSaved?.();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }, [file, draft, baseHash, saving, onSaved]);

  const handleReload = useCallback(async () => {
    if (!file) return;
    setConflict(false);
    try {
      const f = await readFileText(file.path);
      setFile(f);
      setDraft(f.content);
      setBaseContent(f.content);
      setBaseHash(f.hash);
      toast.info("Datei neu geladen");
    } catch {
      toast.error("Neu laden fehlgeschlagen");
    }
  }, [file]);

  const handleDiscard = useCallback(() => {
    setDraft(baseContent);
    toast.info("Änderungen verworfen");
  }, [baseContent]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="size-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="mx-auto max-w-lg py-20 text-center">
        <p className="mb-4 text-sm text-red-400">{error}</p>
        <Button variant="outline" onClick={onClose}>Schließen</Button>
      </div>
    );
  }

  if (!file) return null;

  return (
    <article className="flex min-h-0 flex-col">
      {/* Header: Name, Größe, Dirty-Badge */}
      <div className="mb-3 flex items-center justify-between gap-3 border-b border-border pb-3">
        <div className="flex min-w-0 items-center gap-3">
          <h2 className="truncate text-sm font-semibold">{entry.name}</h2>
          <span className="shrink-0 text-xs text-muted-foreground">
            {formatBytes(file.size)}
          </span>
          {dirty && (
            <span className="shrink-0 rounded-md bg-amber-500/15 px-2 py-0.5 text-xs text-amber-600 dark:text-amber-400">
              Ungespeichert
            </span>
          )}
        </div>
        <Button
          size="sm"
          variant="ghost"
          className="shrink-0"
          onClick={onClose}
          title="Schließen"
        >
          <X className="size-4" />
        </Button>
      </div>

      {/* Toolbar */}
      <div className="mb-3 flex items-center gap-2">
        {isMarkdown && (
          <div className="flex items-center gap-1 rounded-md border border-border bg-card p-0.5">
            <Button
              size="sm"
              variant={mode === "edit" ? "default" : "ghost"}
              className="h-7 px-2"
              onClick={() => setMode("edit")}
            >
              <Pencil className="size-3.5" /> Bearbeiten
            </Button>
            <Button
              size="sm"
              variant={mode === "preview" ? "default" : "ghost"}
              className="h-7 px-2"
              onClick={() => setMode("preview")}
            >
              <Eye className="size-3.5" /> Vorschau
            </Button>
          </div>
        )}
        <div className="ml-auto flex items-center gap-1">
          <Button
            size="sm"
            variant="outline"
            disabled={!dirty}
            onClick={handleDiscard}
          >
            Verwerfen
          </Button>
          <Button
            size="sm"
            disabled={!dirty || saving}
            onClick={handleSave}
          >
            {saving ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
            Speichern
          </Button>
        </div>
      </div>

      {/* Content */}
      <ScrollArea className="flex-1">
        {mode === "preview" && isMarkdown ? (
          <div className="min-h-0 rounded-md border border-border bg-card p-4">
            <MarkdownView
              body={draft}
              index={new Map<string, MdIndexEntry>()}
              currentPath={entry.path}
              onNavigate={() => {}}
            />
          </div>
        ) : (
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            className="min-h-[300px] w-full resize-none rounded-md border border-border bg-card p-4 font-mono text-sm leading-relaxed"
            placeholder="Dateiinhalt bearbeiten…"
          />
        )}
      </ScrollArea>

      {/* Conflict dialog */}
      <Dialog open={conflict} onOpenChange={(o) => !o && setConflict(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Externe Änderung erkannt</DialogTitle>
            <DialogDescription>
              Die Datei wurde seit dem letzten Laden von einer anderen Quelle geändert.
              Deine ungespeicherten Änderungen bleiben erhalten.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setConflict(false)}>
              Abbrechen
            </Button>
            <Button variant="outline" onClick={handleReload}>
              Neu laden
            </Button>
            <Button onClick={handleForceSave}>
              Überschreiben
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </article>
  );
}
