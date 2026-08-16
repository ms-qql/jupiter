"use client";

// Surface A (PROJ-11): vollständiger Fileexplorer über die erlaubten Roots.
// Navigieren, Upload (Drag-and-Drop / Paste / Button) in den aktuellen Ordner,
// neuer Ordner, Download, „Pfad kopieren", Umbenennen, Löschen. Bewusst von
// Sessions entkoppelt (eigene Datenquelle, kein SessionsProvider).
//
// PROJ-28: Drei-Spalten-Layout analog Doku-Reader (PROJ-7) — Cockpit-Sidebar
// (über CockpitShell) · schmales Datei-Panel · große Inhalts-Ansicht. Auswahl
// einer Datei rendert ihre Vorschau rechts (FilePreview).
//
// PROJ-78: das Listing-Panel ist in FileWorkspace ausgelagert, damit der
// Workspace es als zweiten Pane einbetten kann. Diese Komponente behält
// Header, Toolbar, Vorschau/Editor und den Ungespeichert-Dialog.

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  ArrowUp,
  FolderPlus,
  RefreshCw,
  Upload,
} from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ThemeToggle } from "@/components/cockpit/theme-toggle";
import { FilePreview } from "@/components/cockpit/file-preview";
import { TextFileEditor } from "@/components/cockpit/text-file-editor";
import { ActiveSessionPanel } from "@/components/cockpit/active-session-panel";
import { BranchBadge } from "@/components/cockpit/branch-panel";
import { FileWorkspace } from "@/components/cockpit/file-workspace";
import { ApiError, getClipboardDir, listFileRoots, listDir, makeDir } from "@/lib/api";
import { copyText } from "@/lib/clipboard";
import { cn } from "@/lib/utils";
import type { FileEntry } from "@/lib/types";
import { useFileUpload } from "./use-file-upload";

function parentOf(path: string): string {
  const trimmed = path.replace(/\/+$/, "");
  const i = trimmed.lastIndexOf("/");
  return i > 0 ? trimmed.slice(0, i) : "/";
}

export function FileExplorer() {
  // Pfad liegt hier, damit Header (Hoch, Refresh, Pfad, BranchBadge) und
  // FileWorkspace synchron bleiben. FileWorkspace ist controlled und
  // emittiert Pfad-Wechsel via `onPathChange`.
  const [path, setPath] = useState<string | null>(null);
  const [roots, setRoots] = useState<{ path: string; label: string }[]>([]);
  // Refresh-Schlüssel: monoton steigend, löst einen Reload in FileWorkspace
  // aus (z. B. nach Upload / Neuer Ordner). Erweitert wird er auch, wenn
  // FileExplorer den Pfad bereits kennt und die Liste neu braucht.
  const [refreshKey, setRefreshKey] = useState(0);

  // Preview/Editor-Staat (Inline-Preview rechts, Texte bearbeiten).
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [editingPath, setEditingPath] = useState<string | null>(null);
  const dirtyRef = useRef(false);
  const saveRef = useRef<(() => Promise<void>) | null>(null);
  const [savingUnsaved, setSavingUnsaved] = useState(false);
  const [unsavedAction, setUnsavedAction] = useState<(() => void) | null>(null);
  // PROJ-28: auf schmalen Breiten Panel ⇄ Ansicht umschalten (nie beide quetschen).
  const [mobilePane, setMobilePane] = useState<"list" | "view">("list");

  const { upload, uploading } = useFileUpload(path ?? undefined);

  // Roots + Clipboard-Ordner initial laden, damit die Toolbar den Pfad
  // bereits kennt, bevor FileWorkspace eingebunden ist.
  const [initialError, setInitialError] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    Promise.all([listFileRoots(), getClipboardDir()])
      .then(([r]) => {
        if (!active) return;
        setRoots(r);
        setPath((prev) => prev ?? r[0]?.path ?? null);
      })
      .catch((e) =>
        active && setInitialError(e instanceof ApiError ? e.message : "Nicht erreichbar"),
      );
    return () => {
      active = false;
    };
  }, []);

  // PROJ-76: Browser-Reload/Tab-Schließen mit ungespeicherten Änderungen.
  useEffect(() => {
    function onBeforeUnload(e: BeforeUnloadEvent) {
      if (dirtyRef.current) {
        e.preventDefault();
        e.returnValue = "";
      }
    }
    window.addEventListener("beforeunload", onBeforeUnload);
    return () => window.removeEventListener("beforeunload", onBeforeUnload);
  }, []);

  const refresh = () => setRefreshKey((k) => k + 1);

  const handleUpload = async (files: File[]) => {
    const entries = await upload(files);
    if (entries.length) {
      toast.success(`${entries.length} Datei(en) hochgeladen`);
      refresh();
    }
  };

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path]);

  async function handleNewFolder() {
    if (!path) return;
    const name = window.prompt("Name des neuen Ordners:")?.trim();
    if (!name) return;
    try {
      await makeDir(path, name);
      refresh();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Ordner anlegen fehlgeschlagen");
    }
  }

  async function copyPath(p: string) {
    const ok = await copyText(p);
    toast[ok ? "success" : "error"](ok ? "Pfad kopiert" : "Kopieren nicht möglich");
  }

  // FileWorkspace ruft diese Funktionen auf, wenn der Nutzer eine Datei
  // anklickt. Wir müssen dabei aber den Ungespeichert-Guard (PROJ-76) und
  // die mobilePane-Umschaltung übernehmen.
  function openListingDir(p: string) {
    function go() {
      setSelectedPath(null);
      setEditingPath(null);
      setPath(p);
    }
    if (editingPath && dirtyRef.current) {
      setUnsavedAction(() => go);
    } else {
      go();
    }
  }

  function selectFile(entry: FileEntry) {
    function go() {
      setSelectedPath(entry.path);
      setEditingPath(null);
      setMobilePane("view");
    }
    if (editingPath && editingPath !== entry.path && dirtyRef.current) {
      setUnsavedAction(() => go);
    } else {
      go();
    }
  }

  function editFile(entry: FileEntry) {
    function go() {
      setSelectedPath(entry.path);
      setEditingPath(entry.path);
      setMobilePane("view");
    }
    if (editingPath && editingPath !== entry.path && dirtyRef.current) {
      setUnsavedAction(() => go);
    } else {
      go();
    }
  }

  const canGoUp = path !== null && !roots.some((r) => r.path === path);

  // Auswahl-Datei aus aktiv geladenem Listing ableiten — wir laden das
  // Listing bei Bedarf einmal hier, damit ein gelöschter/umbenannter Pfad
  // nicht zu einem toten Verweis im Preview-Panel führt. Die Liste wird
  // zusätzlich an path und refreshKey gehängt, damit „Hoch/Refresh/Neu/
  // Upload" exakt dieselbe Datenquelle wie FileWorkspace sehen.
  const [previewListing, setPreviewListing] = useState<{ entries: FileEntry[] } | null>(null);
  useEffect(() => {
    if (!path) return;
    let active = true;
    listDir(path)
      .then((d) => active && setPreviewListing(d))
      .catch(() => {
        // Fehler werden vom FileWorkspace angezeigt; hier nur stumm
        // verwerfen, damit das Preview-Panel leer bleibt.
      });
    return () => {
      active = false;
    };
  }, [path, refreshKey]);
  const selectedEntry =
    (selectedPath &&
      previewListing?.entries.find((e) => e.path === selectedPath && e.kind === "file")) ||
    null;

  return (
    <div className="flex h-dvh flex-col">
      {/* Header: Back · H1 · Toolbar-Buttons · Pfad · BranchBadge · Theme */}
      <header className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-3">
        <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
          ← Cockpit
        </Link>
        <h1 className="text-sm font-semibold tracking-tight">📁 Dateien</h1>

        <div className="flex items-center gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={!canGoUp}
            onClick={() => path && openListingDir(parentOf(path))}
          >
            <ArrowUp className="size-4" /> Hoch
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={refresh}
          >
            <RefreshCw className="size-4" />
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={handleNewFolder}
            disabled={!path}
          >
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
        <div className="ml-auto flex items-center gap-2">
          {/* PROJ-13: Branch-Status + Verwaltung für den aktuellen Projektpfad. */}
          <BranchBadge path={path} />
          <ThemeToggle />
        </div>
      </header>

      {initialError && (
        <p className="border-b border-border bg-red-500/10 px-4 py-2 text-sm text-red-400">
          {initialError}
        </p>
      )}

      <div className="flex min-h-0 flex-1">
        {/* Spalte 2: Datei-/Verzeichnis-Panel (PROJ-78: ausgelagert in FileWorkspace). */}
        <div
          className={cn(
            "w-full md:flex",
            mobilePane === "list" ? "flex" : "hidden md:flex",
          )}
        >
          <FileWorkspace
            key={path ?? "__none__"}
            storageKey="dateien:list-width"
            defaultListWidth={320}
            path={path}
            onPathChange={openListingDir}
            onOpenFile={selectFile}
            onEditFile={editFile}
            refreshKey={refreshKey}
          />
        </div>

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
            {/* PROJ-76: Editor-Modus hat Vorrang vor Vorschau. */}
            {selectedEntry && editingPath === selectedEntry.path ? (
              <TextFileEditor
                key={selectedEntry.path}
                entry={selectedEntry}
                saveRef={saveRef}
                onClose={() => setEditingPath(null)}
                onDirtyChange={(d) => {
                  dirtyRef.current = d;
                }}
                onSaved={() => refresh()}
              />
            ) : selectedEntry ? (
              <FilePreview key={selectedEntry.path} entry={selectedEntry} />
            ) : (
              <ActiveSessionPanel />
            )}
          </div>
        </main>
      </div>
      {/* PROJ-76: Ungespeichert-Dialog bei Datei-/Ordnerwechsel */}
      <Dialog open={!!unsavedAction} onOpenChange={(o) => !o && setUnsavedAction(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Ungespeicherte Änderungen</DialogTitle>
            <DialogDescription>
              Der aktuelle Entwurf wurde noch nicht gespeichert.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setUnsavedAction(null)}>
              Abbrechen
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                dirtyRef.current = false;
                const fn = unsavedAction;
                setUnsavedAction(null);
                fn?.();
              }}
            >
              Verwerfen
            </Button>
            <Button
              disabled={savingUnsaved}
              onClick={async () => {
                setSavingUnsaved(true);
                try {
                  await saveRef.current?.();
                } catch {
                  return;
                } finally {
                  setSavingUnsaved(false);
                }
                dirtyRef.current = false;
                const fn = unsavedAction;
                setUnsavedAction(null);
                fn?.();
              }}
            >
              {savingUnsaved ? "Speichert…" : "Speichern"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
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
      <Button
        type="button"
        size="sm"
        variant="outline"
        disabled={uploading}
        onClick={() => ref.current?.click()}
      >
        <Upload className="size-4" /> {uploading ? "Lädt…" : "Hochladen"}
      </Button>
    </>
  );
}
