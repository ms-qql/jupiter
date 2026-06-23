"use client";

// Surface A (PROJ-11): vollständiger Fileexplorer über die erlaubten Roots.
// Navigieren, Upload (Drag-and-Drop / Paste / Button) in den aktuellen Ordner,
// neuer Ordner, Download, „Pfad kopieren", Umbenennen, Löschen. Bewusst von
// Sessions entkoppelt (eigene Datenquelle, kein SessionsProvider).

import { useCallback, useEffect, useRef, useState } from "react";
import {
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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
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

  async function copyPath(p: string) {
    const ok = await copyText(p);
    toast[ok ? "success" : "error"](ok ? "Pfad kopiert" : "Kopieren nicht möglich");
  }

  const canGoUp = path !== null && !roots.some((r) => r.path === path);

  return (
    <div className="flex flex-col gap-3">
      {/* Root-Auswahl */}
      <div className="flex flex-wrap items-center gap-2">
        {roots.map((r) => (
          <Button
            key={r.path}
            type="button"
            size="sm"
            variant={path?.startsWith(r.path) ? "default" : "outline"}
            onClick={() => setPath(r.path)}
          >
            {r.label}
          </Button>
        ))}
        {clipboardPath && (
          <Button
            type="button"
            size="sm"
            variant={path === clipboardPath ? "default" : "secondary"}
            onClick={() => setPath(clipboardPath)}
            title={clipboardPath}
          >
            <ClipboardPaste className="size-4" /> Clipboard
          </Button>
        )}
      </div>

      {/* Toolbar */}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" size="sm" variant="outline" disabled={!canGoUp}
          onClick={() => path && setPath(parentOf(path))}>
          <ArrowUp className="size-4" /> Hoch
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={() => void refresh()}>
          <RefreshCw className="size-4" />
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={handleNewFolder} disabled={!path}>
          <FolderPlus className="size-4" /> Neuer Ordner
        </Button>
        <UploadButton onPick={handleUpload} uploading={uploading} />
        {path && (
          <button
            onClick={() => void copyPath(path)}
            className="ml-auto truncate font-mono text-xs text-muted-foreground hover:text-foreground"
            title="Pfad kopieren"
          >
            {path}
          </button>
        )}
      </div>

      {/* Listing + Drop-Zone */}
      <div
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
        className={`min-h-40 rounded-md border ${
          dragOver ? "border-primary bg-primary/5" : "border-border"
        }`}
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
              <li key={entry.path} className="flex items-center gap-3 px-3 py-2 text-sm">
                {entry.kind === "dir" ? (
                  <button
                    className="flex flex-1 items-center gap-2 text-left hover:text-primary"
                    onClick={() => setPath(entry.path)}
                  >
                    <Folder className="size-4 shrink-0 text-muted-foreground" />
                    {entry.name}
                  </button>
                ) : (
                  <span className="flex flex-1 items-center gap-2">
                    <FileIcon className="size-4 shrink-0 text-muted-foreground" />
                    {entry.name}
                    <span className="text-xs text-muted-foreground">
                      {formatBytes(entry.size)}
                    </span>
                  </span>
                )}
                <div className="flex items-center gap-1 text-muted-foreground">
                  <IconBtn title="Pfad kopieren" onClick={() => void copyPath(entry.path)}>
                    <Copy className="size-4" />
                  </IconBtn>
                  {entry.kind === "file" && (
                    <a
                      href={fileDownloadUrl(entry.path)}
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
