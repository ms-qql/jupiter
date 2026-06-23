"use client";

// PROJ-12: Leichter MD-Editor mit Obsidian-DNA auf der PROJ-7-Basis.
// - Rohtext-Edit (Frontmatter + Body bleiben 1:1 erhalten) ⇄ Vorschau.
// - [[-Autocomplete aus dem MD-Index (clientseitig gefiltert).
// - Optimistische Konflikterkennung (mtime + Hash) → 409-Dialog statt blindem
//   Überschreiben.
// - Dirty-State: Speichern-Button + Warnung beim Verlassen.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Eye, Loader2, Pencil, Save } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FrontmatterPanel } from "@/components/cockpit/frontmatter-panel";
import { MarkdownView } from "@/components/cockpit/markdown-view";
import { ApiError, readMdFile, saveMdFile } from "@/lib/api";
import {
  searchNotes,
  splitFrontmatter,
  type TreeFile,
} from "@/lib/md-tree";
import type { MdFileRead, MdIndexEntry, MdSaveResult } from "@/lib/types";

type Mode = "edit" | "preview";

/** Erkennt einen offenen ``[[…``-Trigger direkt vor dem Cursor. */
function wikilinkTrigger(
  value: string,
  caret: number,
): { start: number; query: string } | null {
  const before = value.slice(0, caret);
  const open = before.lastIndexOf("[[");
  if (open === -1) return null;
  const between = before.slice(open + 2);
  // Trigger gilt nur, solange [[ nicht geschlossen/abgebrochen wurde.
  if (between.includes("]]") || between.includes("\n") || between.includes("[")) {
    return null;
  }
  return { start: open, query: between };
}

export function MdEditorPanel({
  file,
  notes,
  wikiIndex,
  onNavigate,
  onSaved,
  onDirtyChange,
}: {
  file: MdFileRead;
  notes: MdIndexEntry[];
  wikiIndex: Map<string, MdIndexEntry>;
  onNavigate: (path: string) => void;
  onSaved?: (res: MdSaveResult) => void;
  onDirtyChange?: (dirty: boolean) => void;
}) {
  const [mode, setMode] = useState<Mode>("edit");
  const [draft, setDraft] = useState(file.content);
  // Baseline = serverseitiger Stand; aktualisiert nach Speichern/Neu-Laden.
  const [baseContent, setBaseContent] = useState(file.content);
  const [baseMtime, setBaseMtime] = useState(file.mtime);
  const [baseHash, setBaseHash] = useState(file.hash);
  const [saving, setSaving] = useState(false);
  const [conflict, setConflict] = useState(false);

  // Autocomplete-Zustand.
  const taRef = useRef<HTMLTextAreaElement>(null);
  const [trigger, setTrigger] = useState<{ start: number; query: string } | null>(null);
  const [activeIdx, setActiveIdx] = useState(0);

  const dirty = draft !== baseContent;
  const suggestions = useMemo(
    () => (trigger ? searchNotes(notes, trigger.query) : []),
    [trigger, notes],
  );

  useEffect(() => onDirtyChange?.(dirty), [dirty, onDirtyChange]);

  // Warnung beim Schließen/Reload des Tabs mit ungespeicherten Änderungen.
  useEffect(() => {
    if (!dirty) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const previewBody = useMemo(() => splitFrontmatter(draft).body, [draft]);

  const updateTrigger = useCallback((value: string, caret: number) => {
    const t = wikilinkTrigger(value, caret);
    setTrigger(t);
    setActiveIdx(0);
  }, []);

  const onChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setDraft(e.target.value);
    updateTrigger(e.target.value, e.target.selectionStart);
  };

  /** Fügt den gewählten Wikilink an der Trigger-Stelle ein. */
  const insertWikilink = useCallback(
    (entry: MdIndexEntry) => {
      if (!trigger) return;
      const ta = taRef.current;
      const caret = ta?.selectionStart ?? draft.length;
      const linkName = entry.name.replace(/\.md$/i, "");
      const insert = `[[${linkName}]]`;
      const next = draft.slice(0, trigger.start) + insert + draft.slice(caret);
      setDraft(next);
      setTrigger(null);
      // Cursor hinter das eingefügte ]] setzen.
      const pos = trigger.start + insert.length;
      requestAnimationFrame(() => {
        ta?.focus();
        ta?.setSelectionRange(pos, pos);
      });
    },
    [trigger, draft],
  );

  const reload = useCallback(async () => {
    try {
      const fresh = await readMdFile(file.path);
      setDraft(fresh.content);
      setBaseContent(fresh.content);
      setBaseMtime(fresh.mtime);
      setBaseHash(fresh.hash);
      setConflict(false);
      toast.success("Neu geladen");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Neu laden fehlgeschlagen");
    }
  }, [file.path]);

  const save = useCallback(
    async (force = false) => {
      setSaving(true);
      try {
        const res = await saveMdFile({
          path: file.path,
          content: draft,
          expected_mtime: baseMtime,
          expected_hash: baseHash,
          force,
        });
        setBaseContent(draft);
        setBaseMtime(res.mtime);
        setBaseHash(res.hash);
        setConflict(false);
        toast.success("Gespeichert");
        onSaved?.(res);
      } catch (e) {
        if (e instanceof ApiError && e.status === 409) {
          setConflict(true);
        } else {
          toast.error(e instanceof ApiError ? e.message : "Speichern fehlgeschlagen");
        }
      } finally {
        setSaving(false);
      }
    },
    [file.path, draft, baseMtime, baseHash, onSaved],
  );

  const onKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Autocomplete-Navigation hat Vorrang.
    if (trigger && suggestions.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIdx((i) => (i + 1) % suggestions.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIdx((i) => (i - 1 + suggestions.length) % suggestions.length);
        return;
      }
      if (e.key === "Enter" || e.key === "Tab") {
        e.preventDefault();
        insertWikilink(suggestions[activeIdx]);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setTrigger(null);
        return;
      }
    }
    // Strg/Cmd+S → speichern.
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "s") {
      e.preventDefault();
      if (dirty && !saving) save();
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      {/* Toolbar */}
      <div className="mb-3 flex items-center gap-2">
        <div className="inline-flex overflow-hidden rounded-md border border-border">
          <button
            type="button"
            onClick={() => setMode("edit")}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs ${
              mode === "edit"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Pencil className="size-3" /> Bearbeiten
          </button>
          <button
            type="button"
            onClick={() => setMode("preview")}
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 text-xs ${
              mode === "preview"
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Eye className="size-3" /> Vorschau
          </button>
        </div>

        {dirty && (
          <span className="text-xs text-amber-600 dark:text-amber-400">
            ● Ungespeicherte Änderungen
          </span>
        )}

        <Button
          size="sm"
          className="ml-auto"
          disabled={!dirty || saving}
          onClick={() => save()}
        >
          {saving ? (
            <Loader2 className="size-3.5 animate-spin" />
          ) : (
            <Save className="size-3.5" />
          )}
          Speichern
        </Button>
      </div>

      {/* Inhalt */}
      {mode === "edit" ? (
        <div className="relative min-h-0 flex-1">
          <Textarea
            ref={taRef}
            value={draft}
            onChange={onChange}
            onKeyDown={onKeyDown}
            onClick={(e) =>
              updateTrigger(e.currentTarget.value, e.currentTarget.selectionStart)
            }
            spellCheck={false}
            className="h-[60vh] w-full resize-none overflow-auto font-mono text-xs leading-relaxed [field-sizing:fixed]"
            aria-label="Markdown-Editor"
          />
          {trigger && suggestions.length > 0 && (
            <ul
              role="listbox"
              className="absolute left-2 right-2 bottom-2 z-10 max-h-56 overflow-auto rounded-md border border-border bg-popover p-1 shadow-lg"
            >
              <li className="px-2 py-1 text-[10px] uppercase tracking-wide text-muted-foreground">
                Notiz verlinken
              </li>
              {suggestions.map((s, i) => (
                <li key={s.path}>
                  <button
                    type="button"
                    role="option"
                    aria-selected={i === activeIdx}
                    // onMouseDown statt onClick: feuert vor blur der Textarea.
                    onMouseDown={(e) => {
                      e.preventDefault();
                      insertWikilink(s);
                    }}
                    onMouseEnter={() => setActiveIdx(i)}
                    className={`flex w-full flex-col items-start gap-0 rounded px-2 py-1 text-left text-xs ${
                      i === activeIdx ? "bg-accent" : "hover:bg-accent/60"
                    }`}
                  >
                    <span className="font-medium">{s.name.replace(/\.md$/i, "")}</span>
                    <span className="text-[10px] text-muted-foreground">{s.rel}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : (
        <div className="min-h-0 flex-1 overflow-y-auto">
          <FrontmatterPanel frontmatter={file.frontmatter} />
          <MarkdownView
            body={previewBody}
            index={wikiIndex}
            onNavigate={(f: Pick<TreeFile, "path">) => onNavigate(f.path)}
          />
        </div>
      )}

      {/* Konflikt-Dialog (409): Datei wurde extern geändert. */}
      <Dialog open={conflict} onOpenChange={setConflict}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Datei wurde extern geändert</DialogTitle>
            <DialogDescription>
              Die Datei wurde seit dem Laden außerhalb von Jupiter verändert (z. B. in
              Obsidian oder einem zweiten Tab). Überschreiben verwirft die externe
              Änderung; Neu laden verwirft deine lokalen Änderungen.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={reload}>
              Neu laden (lokal verwerfen)
            </Button>
            <Button
              variant="destructive"
              disabled={saving}
              onClick={() => save(true)}
            >
              Überschreiben
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
