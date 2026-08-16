"use client";

// PROJ-78: Einbettbare Datei-Arbeitsfläche NUR als Listing-Panel (Roots,
// Ordner-/Dateiliste, Mehrfachauswahl, Source-of-Truth für Pfad/Roots).
// Enthält bewusst KEINEN Toolbar + KEINE Inline-Vorschau: Hoch, Refresh,
// Neuer Ordner, Upload und Pfad zeigt jede Konsument-Komponente selbst, und
// die Vorschau einer geöffneten Datei übernimmt die Eltern-Komponente
// (Standalone: FileExplorer zeigt sie im rechten Spaltenpaar; Workspace:
// Workspace rendert die Dateivollansicht als separate Schicht).
//
// Der Pfad wird vom Konsumenten kontrolliert (controlled component): jede
// Konsument-Komponente hält ihren eigenen `path`-State (mit eigener Toolbar,
// eigenem Hoch/Refresh/Neu/Upload), das FileWorkspace lädt die Liste, sobald
// der Pfad wechselt, und meldet Pfad-Wechsel via `onPathChange`.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  BrainCircuit,
  ClipboardPaste,
  Copy,
  Download,
  File as FileIcon,
  Folder,
  Pencil,
  TextCursor,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ResizableAside } from "@/components/cockpit/resizable-aside";
import { ApiError, deleteFiles, downloadFile, downloadZip, getClipboardDir, listDir, listFileRoots, renameFile } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { cn } from "@/lib/utils";
import type { DirListing, FileEntry, RootEntry } from "@/lib/types";

const HAL_PATH = "/home/dev/tools/Hal";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileWorkspace({
  path,
  onPathChange,
  onOpenFile,
  onEditFile,
  storageKey = "dateien:list-width",
  defaultListWidth = 320,
  refreshKey = 0,
}: {
  /** Aktueller Pfad — wird vom Konsumenten kontrolliert. */
  path: string | null;
  /** Pfad-Wechsel melden (Ordner-Klick, Root-Klick). */
  onPathChange: (p: string) => void;
  /** Wird bei jeder Datei-Auswahl aufgerufen; die Eltern-Komponente
   *  entscheidet, wie sie die Datei anzeigt (Standalone: Inline-Preview;
   *  Workspace: Dateivollansicht als separate Schicht). */
  onOpenFile?: (entry: FileEntry) => void;
  /** Wird aufgerufen, wenn der Nutzer auf den Bearbeiten-Stift klickt.
   *  Fehlt der Callback, wird der Stift nicht angezeigt. */
  onEditFile?: (entry: FileEntry) => void;
  /** localStorage-Key für die Spaltenbreite. Pro Mount-Punkt eigener Key. */
  storageKey?: string;
  /** Default-Breite der Spalte. */
  defaultListWidth?: number;
  /** Erhöhen erzwingt einen Reload der Liste (z. B. nach Upload). */
  refreshKey?: number;
}) {
  const [roots, setRoots] = useState<RootEntry[]>([]);
  const [clipboardPath, setClipboardPath] = useState<string | null>(null);
  const [listing, setListing] = useState<DirListing | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  // PROJ-Fix: Download-Buttons ohne Rückmeldung führten bei langsamem ZIP-Aufbau
  // (großer Ordner) zu Mehrfachklicks → mehrere Downloads gleichzeitig.
  const [downloading, setDownloading] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const dropActive = useRef(false);
  const [dragOver, setDragOver] = useState(false);

  // Roots + Clipboard-Ordner einmalig laden.
  useEffect(() => {
    let active = true;
    Promise.all([listFileRoots(), getClipboardDir()])
      .then(([r, clip]) => {
        if (!active) return;
        setRoots(r);
        setClipboardPath(clip.path);
      })
      .catch((e) =>
        active && setError(e instanceof ApiError ? e.message : "Nicht erreichbar"),
      );
    return () => {
      active = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (!path) return;
    try {
      setListing(await listDir(path));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Ordner nicht lesbar");
      setListing(null);
    }
  }, [path]);

  // Liste bei Pfadwechsel ODER explizitem refreshKey-Stub neu laden — setState
  // nur in den Promise-Callbacks, kein sync setState im Effect.
  // Consumers re-keyen die Komponente bei path-Wechsel (key={path}), damit
  // Selection + Listing+Roots-Cache frisch starten und kein sync setState
  // im Effect nötig ist.
  useEffect(() => {
    if (!path) return;
    let active = true;
    listDir(path)
      .then((d) => {
        if (!active) return;
        setListing(d);
        setError(null);
        setLoading(false);
      })
      .catch((e) => {
        if (!active) return;
        setError(e instanceof ApiError ? e.message : "Ordner nicht lesbar");
        setListing(null);
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [path, refreshKey]);

  async function handleDeleteSelected() {
    const paths = Array.from(selected);
    if (!paths.length) return;
    if (!window.confirm(`${paths.length} Element(e) wirklich löschen?`)) return;
    try {
      const res = await deleteFiles(paths);
      if (res.failed.length) toast.error("Löschen fehlgeschlagen");
      setSelected(new Set());
      void refresh();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Löschen fehlgeschlagen");
    }
  }

  async function handleDownloadSelected() {
    const paths = Array.from(selected);
    if (!paths.length || downloading.has("__selection__")) return;
    setDownloading((prev) => new Set(prev).add("__selection__"));
    try {
      await downloadZip(paths);
      setSelected(new Set());
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Download fehlgeschlagen");
    } finally {
      setDownloading((prev) => {
        const next = new Set(prev);
        next.delete("__selection__");
        return next;
      });
    }
  }

  async function handleDownloadEntry(p: string, name: string) {
    if (downloading.has(p)) return;
    setDownloading((prev) => new Set(prev).add(p));
    try {
      await downloadFile(p, name);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Download fehlgeschlagen");
    } finally {
      setDownloading((prev) => {
        const next = new Set(prev);
        next.delete(p);
        return next;
      });
    }
  }

  async function copyPath(p: string) {
    const ok = await copyText(p);
    toast[ok ? "success" : "error"](ok ? "Pfad kopiert" : "Kopieren nicht möglich");
  }

  async function handleRename(entry: FileEntry) {
    const next = window.prompt("Neuer Name:", entry.name)?.trim();
    if (!next || next === entry.name) return;
    try {
      await renameFile(entry.path, next);
      void refresh();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Umbenennen fehlgeschlagen");
    }
  }

  async function handleDelete(entry: FileEntry) {
    const what = entry.kind === "dir" ? "Ordner (inkl. Inhalt)" : "Datei";
    if (!window.confirm(`${what} „${entry.name}" wirklich löschen?`)) return;
    try {
      const res = await deleteFiles([entry.path]);
      if (res.failed.length) toast.error("Löschen fehlgeschlagen");
      void refresh();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Löschen fehlgeschlagen");
    }
  }

  function selectFile(entry: FileEntry) {
    onOpenFile?.(entry);
  }

  function editFile(entry: FileEntry) {
    onEditFile?.(entry);
  }

  return (
    <ResizableAside
      storageKey={storageKey}
      defaultWidth={defaultListWidth}
      className="flex min-h-0 w-full flex-col border-r border-border bg-card/40"
      onDrop={() => {
        setDragOver(false);
        dropActive.current = false;
      }}
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes("Files")) {
          e.preventDefault();
          if (!dropActive.current) {
            dropActive.current = true;
            setDragOver(true);
          }
        }
      }}
      onDragLeave={() => {
        dropActive.current = false;
        setDragOver(false);
      }}
    >
      {/* Root-Auswahl */}
      <div className="flex flex-wrap items-center gap-2 border-b border-border p-2">
        {roots.map((r) => (
          <Button
            key={r.path}
            type="button"
            size="sm"
            variant={path !== null && path.startsWith(r.path) ? "default" : "outline"}
            onClick={() => onPathChange(r.path)}
          >
            {r.label}
          </Button>
        ))}
        {clipboardPath && (
          <Button
            type="button"
            size="sm"
            variant={path === clipboardPath ? "default" : "secondary"}
            onClick={() => onPathChange(clipboardPath)}
            title={clipboardPath}
          >
            <ClipboardPaste className="size-4" /> Clipboard
          </Button>
        )}
        <Button
          type="button"
          size="sm"
          variant={path === HAL_PATH ? "default" : "secondary"}
          onClick={() => onPathChange(HAL_PATH)}
          title={HAL_PATH}
        >
          <BrainCircuit className="size-4" /> HAL
        </Button>
      </div>

      {/* Mehrfachauswahl: alle markieren + gesammelt löschen. */}
      {listing && listing.entries.length > 0 && (
        <div className="flex items-center gap-2 border-b border-border px-3 py-1.5 text-xs">
          <label className="flex items-center gap-1.5 text-muted-foreground">
            <input
              type="checkbox"
              checked={selected.size === listing.entries.length}
              onChange={(e) =>
                setSelected(
                  e.target.checked
                    ? new Set(listing.entries.map((en) => en.path))
                    : new Set(),
                )
              }
            />
            Alle
          </label>
          {selected.size > 0 && (
            <div className="ml-auto flex items-center gap-1.5">
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-6 px-2"
                disabled={downloading.has("__selection__")}
                onClick={() => void handleDownloadSelected()}
              >
                <Download className="size-3.5" />{" "}
                {downloading.has("__selection__")
                  ? "Lädt…"
                  : `${selected.size} herunterladen`}
              </Button>
              <Button
                type="button"
                size="sm"
                variant="destructive"
                className="h-6 px-2"
                onClick={() => void handleDeleteSelected()}
              >
                <Trash2 className="size-3.5" /> {selected.size} löschen
              </Button>
            </div>
          )}
        </div>
      )}

      <ScrollArea
        className={cn(
          "flex-1",
          dragOver && "bg-primary/5 ring-1 ring-inset ring-primary",
        )}
      >
        {loading ? (
          <p className="p-6 text-center text-sm text-muted-foreground">Lädt…</p>
        ) : error ? (
          <p className="p-6 text-center text-sm text-red-400">{error}</p>
        ) : !listing || listing.entries.length === 0 ? (
          <p className="p-6 text-center text-sm text-muted-foreground">
            Leerer Ordner.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {listing.entries.map((entry) => (
              <li
                key={entry.path}
                className="group flex items-center gap-2 px-3 py-2 text-sm"
              >
                <input
                  type="checkbox"
                  checked={selected.has(entry.path)}
                  onChange={(e) =>
                    setSelected((prev) => {
                      const next = new Set(prev);
                      if (e.target.checked) next.add(entry.path);
                      else next.delete(entry.path);
                      return next;
                    })
                  }
                />
                {entry.kind === "dir" ? (
                  <button
                    className="flex flex-1 items-center gap-2 truncate text-left hover:text-primary"
                    onClick={() => onPathChange(entry.path)}
                  >
                    <Folder className="size-4 shrink-0 text-muted-foreground" />
                    <span className="truncate" title={entry.name}>
                      {entry.name}
                    </span>
                  </button>
                ) : (
                  <button
                    className="flex flex-1 items-center gap-2 truncate text-left hover:text-primary"
                    onClick={() => selectFile(entry)}
                  >
                    <FileIcon className="size-4 shrink-0 text-muted-foreground" />
                    <span className="truncate" title={entry.name}>
                      {entry.name}
                    </span>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {formatBytes(entry.size)}
                    </span>
                  </button>
                )}
                <div className="flex items-center gap-1 text-muted-foreground opacity-0 group-hover:opacity-100">
                  <IconBtn
                    title="Pfad kopieren"
                    onClick={() => void copyPath(entry.path)}
                  >
                    <Copy className="size-4" />
                  </IconBtn>
                  {entry.kind === "file" && (
                    <IconBtn
                      title="Herunterladen"
                      disabled={downloading.has(entry.path)}
                      onClick={() => void handleDownloadEntry(entry.path, entry.name)}
                    >
                      <Download className="size-4" />
                    </IconBtn>
                  )}
                  {entry.editable && entry.kind === "file" && onEditFile && (
                    <IconBtn title="Bearbeiten" onClick={() => editFile(entry)}>
                      <Pencil className="size-4" />
                    </IconBtn>
                  )}
                  <IconBtn
                    title="Umbenennen"
                    onClick={() => void handleRename(entry)}
                  >
                    <TextCursor className="size-4" />
                  </IconBtn>
                  <IconBtn
                    title="Löschen"
                    onClick={() => void handleDelete(entry)}
                  >
                    <Trash2 className="size-4" />
                  </IconBtn>
                </div>
              </li>
            ))}
            {/*
              Stellen, die vorher „Datei bearbeiten" hatten, sind hier
              bewusst NICHT enthalten: im Embedded-Modus (Workspace) gibt
              es keinen Inline-Editor. Bearbeiten via Vollansicht.
            */}
          </ul>
        )}
      </ScrollArea>
    </ResizableAside>
  );
}

function IconBtn({
  title,
  onClick,
  disabled,
  children,
}: {
  title: string;
  onClick: () => void;
  disabled?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      disabled={disabled}
      className="rounded p-1 hover:bg-accent hover:text-foreground disabled:pointer-events-none disabled:opacity-50"
    >
      {children}
    </button>
  );
}
