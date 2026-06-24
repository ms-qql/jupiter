"use client";

// Surface A (PROJ-11): vollständiger Fileexplorer über die erlaubten Roots.
// Navigieren, Upload (Drag-and-Drop / Paste / Button) in den aktuellen Ordner,
// neuer Ordner, Download, „Pfad kopieren", Umbenennen, Löschen. Bewusst von
// Sessions entkoppelt (eigene Datenquelle, kein SessionsProvider).
//
// PROJ-28: Drei-Spalten-Layout analog Doku-Reader (PROJ-7) — Cockpit-Sidebar
// (über CockpitShell) · schmales Datei-Panel · große Inhalts-Ansicht. Auswahl
// einer Datei rendert ihre Vorschau rechts (FilePreview).

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUp,
  ClipboardPaste,
  Copy,
  Download,
  File as FileIcon,
  Folder,
  FolderPlus,
  Pencil,
  RefreshCw,
  Trash2,
  Upload,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ThemeToggle } from "@/components/cockpit/theme-toggle";
import { FilePreview } from "@/components/cockpit/file-preview";
import {
  ApiError,
  deleteFiles,
  fileDownloadUrl,
  getClipboardDir,
  listDir,
  listFileRoots,
  makeDir,
  renameFile,
} from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { cn } from "@/lib/utils";
import type { DirListing, FileEntry, RootEntry } from "@/lib/types";
import { useFileUpload } from "./use-file-upload";

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

function parentOf(path: string): string {
  const trimmed = path.replace(/\/+$/, "");
  const i = trimmed.lastIndexOf("/");
  return i > 0 ? trimmed.slice(0, i) : "/";
}

export function FileExplorer() {
  const [roots, setRoots] = useState<RootEntry[]>([]);
  const [path, setPath] = useState<string | null>(null);
  const [listing, setListing] = useState<DirListing | null>(null);
  const [clipboardPath, setClipboardPath] = useState<string | null>(null);
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // PROJ-28: auf schmalen Breiten Panel ⇄ Ansicht umschalten (nie beide quetschen).
  const [mobilePane, setMobilePane] = useState<"list" | "view">("list");
  const dropActive = useRef(false);
  const [dragOver, setDragOver] = useState(false);

  const { upload, uploading } = useFileUpload(path ?? undefined);

  // Einmalig: Roots + Clipboard-Ordner laden, ersten Root öffnen.
  useEffect(() => {
    let active = true;
    Promise.all([listFileRoots(), getClipboardDir()])
      .then(([r, clip]) => {
        if (!active) return;
        setRoots(r);
        setClipboardPath(clip.path);
        setPath((prev) => prev ?? r[0]?.path ?? null);
      })
      .catch((e) =>
        active && setError(e instanceof ApiError ? e.message : "Nicht erreichbar"),
      );
    return () => {
      active = false;
    };
  }, []);

  // Nach Mutationen (Upload/mkdir/rename/delete) neu laden — ohne Spinner-Flackern.
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

  // Laden bei Pfadwechsel — setState nur in den Promise-Callbacks (kein sync setState im Effect).
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
  }, [path]);

  const handleUpload = useCallback(
    async (files: File[]) => {
      const entries = await upload(files);
      if (entries.length) {
        toast.success(`${entries.length} Datei(en) hochgeladen`);
        void refresh();
      }
    },
    [upload, refresh],
  );

  // Paste (Screenshot/Datei) → Upload in den aktuellen Ordner.
  useEffect(() => {
    function onPaste(e: ClipboardEvent) {
      const files = Array.from(e.clipboardData?.files ?? []);
      if (files.length) {
        e.preventDefault();
        void handleUpload(files);
      }
    }
    window.addEventListener("paste", onPaste);
    return () => window.removeEventListener("paste", onPaste);
  }, [handleUpload]);

  async function handleNewFolder() {
    if (!path) return;
    const name = window.prompt("Name des neuen Ordners:")?.trim();
    if (!name) return;
    try {
      await makeDir(path, name);
      void refresh();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Ordner anlegen fehlgeschlagen");
    }
  }

  async function handleRename(entry: FileEntry) {
    const next = window.prompt("Neuer Name:", entry.name)?.trim();
    if (!next || next === entry.name) return;
    try {
      await renameFile(entry.path, next);
      if (selectedPath === entry.path) setSelectedPath(null); // toter Verweis vermeiden
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
      if (selectedPath === entry.path) setSelectedPath(null); // Ansicht auf Empty-State
      void refresh();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Löschen fehlgeschlagen");
    }
  }

  async function copyPath(p: string) {
    const ok = await copyText(p);
    toast[ok ? "success" : "error"](ok ? "Pfad kopiert" : "Kopieren nicht möglich");
  }

  function openDir(p: string) {
    setSelectedPath(null);
    setPath(p);
  }

  function selectFile(entry: FileEntry) {
    setSelectedPath(entry.path);
    setMobilePane("view");
  }

  const canGoUp = path !== null && !roots.some((r) => r.path === path);
  // Ausgewählte Datei aus der aktuellen Liste ableiten → gelöscht/umbenannt/weg-
  // navigiert ⇒ automatisch Empty-State, kein toter Verweis.
  const selectedEntry =
    (selectedPath &&
      listing?.entries.find((e) => e.path === selectedPath && e.kind === "file")) ||
    null;

  return (
    <div className="flex h-dvh flex-col">
      {/* Header: Breadcrumb · Toolbar · Pfad · Theme */}
      <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
        <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
          ← Cockpit
        </Link>
        <h1 className="text-sm font-semibold tracking-tight">📁 Dateien</h1>

        <div className="flex items-center gap-2">
          <Button type="button" size="sm" variant="outline" disabled={!canGoUp}
            onClick={() => path && openDir(parentOf(path))}>
            <ArrowUp className="size-4" /> Hoch
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={() => void refresh()}>
            <RefreshCw className="size-4" />
          </Button>
          <Button type="button" size="sm" variant="outline" onClick={handleNewFolder} disabled={!path}>
            <FolderPlus className="size-4" /> Neuer Ordner
          </Button>
          <UploadButton onPick={handleUpload} uploading={uploading} />
        </div>

        {path && (
          <button
            onClick={() => void copyPath(path)}
            className="hidden max-w-[40%] truncate font-mono text-xs text-muted-foreground hover:text-foreground md:block"
            title="Pfad kopieren"
          >
            {path}
          </button>
        )}
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* Spalte 2: Datei-/Verzeichnis-Panel */}
        <aside
          className={cn(
            "w-full shrink-0 flex-col border-r border-border bg-card/40 md:flex md:w-80",
            mobilePane === "list" ? "flex" : "hidden md:flex",
          )}
          onDrop={(e) => {
            const files = Array.from(e.dataTransfer.files);
            if (files.length) {
              e.preventDefault();
              void handleUpload(files);
            }
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
                variant={path?.startsWith(r.path) ? "default" : "outline"}
                onClick={() => openDir(r.path)}
              >
                {r.label}
              </Button>
            ))}
            {clipboardPath && (
              <Button
                type="button"
                size="sm"
                variant={path === clipboardPath ? "default" : "secondary"}
                onClick={() => openDir(clipboardPath)}
                title={clipboardPath}
              >
                <ClipboardPaste className="size-4" /> Clipboard
              </Button>
            )}
          </div>

          {/* Listing */}
          <ScrollArea
            className={cn("flex-1", dragOver && "bg-primary/5 ring-1 ring-inset ring-primary")}
          >
            {loading ? (
              <p className="p-6 text-center text-sm text-muted-foreground">Lädt…</p>
            ) : error ? (
              <p className="p-6 text-center text-sm text-red-400">{error}</p>
            ) : !listing || listing.entries.length === 0 ? (
              <p className="p-6 text-center text-sm text-muted-foreground">
                Leerer Ordner. Dateien hierher ziehen oder einfügen (Strg/Cmd+V).
              </p>
            ) : (
              <ul className="divide-y divide-border">
                {listing.entries.map((entry) => (
                  <li
                    key={entry.path}
                    className={cn(
                      "group flex items-center gap-2 px-3 py-2 text-sm",
                      entry.path === selectedPath && "bg-accent",
                    )}
                  >
                    {entry.kind === "dir" ? (
                      <button
                        className="flex flex-1 items-center gap-2 truncate text-left hover:text-primary"
                        onClick={() => openDir(entry.path)}
                      >
                        <Folder className="size-4 shrink-0 text-muted-foreground" />
                        <span className="truncate">{entry.name}</span>
                      </button>
                    ) : (
                      <button
                        className="flex flex-1 items-center gap-2 truncate text-left hover:text-primary"
                        onClick={() => selectFile(entry)}
                      >
                        <FileIcon className="size-4 shrink-0 text-muted-foreground" />
                        <span className="truncate">{entry.name}</span>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {formatBytes(entry.size)}
                        </span>
                      </button>
                    )}
                    <div className="flex items-center gap-1 text-muted-foreground opacity-0 group-hover:opacity-100">
                      <IconBtn title="Pfad kopieren" onClick={() => void copyPath(entry.path)}>
                        <Copy className="size-4" />
                      </IconBtn>
                      {entry.kind === "file" && (
                        <a
                          href={fileDownloadUrl(entry.path)}
                          download
                          className="rounded p-1 hover:bg-accent hover:text-foreground"
                          title="Herunterladen"
                        >
                          <Download className="size-4" />
                        </a>
                      )}
                      <IconBtn title="Umbenennen" onClick={() => void handleRename(entry)}>
                        <Pencil className="size-4" />
                      </IconBtn>
                      <IconBtn title="Löschen" onClick={() => void handleDelete(entry)}>
                        <Trash2 className="size-4" />
                      </IconBtn>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </ScrollArea>
        </aside>

        {/* Spalte 3: Inhalts-Ansicht */}
        <main
          className={cn(
            "min-w-0 flex-1 overflow-y-auto",
            mobilePane === "view" ? "block" : "hidden md:block",
          )}
        >
          <div className="mx-auto max-w-3xl px-4 py-6 md:px-8">
            {/* Mobile: zurück zur Liste */}
            <Button
              size="sm"
              variant="ghost"
              className="mb-3 md:hidden"
              onClick={() => setMobilePane("list")}
            >
              <ArrowLeft className="size-4" /> Liste
            </Button>
            <FilePreview key={selectedEntry?.path ?? "none"} entry={selectedEntry} />
          </div>
        </main>
      </div>
    </div>
  );
}

function IconBtn({
  title,
  onClick,
  children,
}: {
  title: string;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      title={title}
      onClick={onClick}
      className="rounded p-1 hover:bg-accent hover:text-foreground"
    >
      {children}
    </button>
  );
}

function UploadButton({
  onPick,
  uploading,
}: {
  onPick: (files: File[]) => void;
  uploading: boolean;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <>
      <input
        ref={ref}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          if (files.length) onPick(files);
          e.target.value = "";
        }}
      />
      <Button type="button" size="sm" variant="outline" disabled={uploading}
        onClick={() => ref.current?.click()}>
        <Upload className="size-4" /> {uploading ? "Lädt…" : "Hochladen"}
      </Button>
    </>
  );
}
