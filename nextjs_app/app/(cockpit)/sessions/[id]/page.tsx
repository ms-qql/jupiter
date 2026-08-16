"use client";

// PROJ-78: Host für den Zwei-Pane-Workspace. Liest die kanonische ID aus
// der URL und führt sie über open() in den Workspace. Rendert die zwei
// Pane-Slots plus Datei-Vollansicht (Schicht über den Pane) und die
// dazugehörige Toolbar (Back · Dateien-Toggle · Zurück zu Dateien).
//
// Design: auf Desktop zwei Pane-Slots nebeneinander mit verschiebbarer
// Trennlinie; unterhalb MD nur der aktive Pane sichtbar, mit Tab-Umschalter
// für zwei Sessions. Datei-Vollansicht verdeckt beide Pane, lässt sie
// aber gemountet (kein State-Verlust). Beim Schließen der Vollansicht
// kehrt der vorherige Pane-Zustand unverändert wieder.

import { Fragment, use, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { ArrowLeft, FileIcon, FolderIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FilePreview } from "@/components/cockpit/file-preview";
import { FileWorkspace } from "@/components/cockpit/file-workspace";
import { SplitDivider } from "@/components/cockpit/split-divider";
import { SessionView } from "@/components/cockpit/session-view";
import { ApiError, getClipboardDir, listFileRoots, makeDir } from "@/lib/api";
import { displayName } from "@/lib/status";
import { cn } from "@/lib/utils";
import type { FileEntry } from "@/lib/types";
import { useSessions } from "@/components/cockpit/sessions-provider";
import { useWorkspace, type Pane, type PaneIndex } from "@/components/cockpit/workspace-provider";
import { useFileUpload } from "@/components/cockpit/use-file-upload";
import { toast } from "sonner";

function parentOf(path: string): string {
  const trimmed = path.replace(/\/+$/, "");
  const i = trimmed.lastIndexOf("/");
  return i > 0 ? trimmed.slice(0, i) : "/";
}

export default function SessionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const {
    panes,
    activeIndex,
    fileFullscreen,
    splitRatio,
    setSplitRatio,
    open,
    focus,
    toggleFiles,
    openFileFullscreen,
    closeFileFullscreen,
  } = useWorkspace();
  const { sessions } = useSessions();

  useEffect(() => {
    open(id);
  }, [id, open]);

  const twoPanes = panes[0] !== null && panes[1] !== null;
  const singlePane = !twoPanes && (panes[0] !== null || panes[1] !== null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Im Workspace gehaltener Pfad für die Datei-Arbeitsfläche. FileWorkspace
  // ist controlled, Workspace behält den Pfad für die Toolbar.
  const [filePath, setFilePath] = useState<string | null>(null);
  const [fileRoots, setFileRoots] = useState<{ path: string; label: string }[]>([]);
  const [fileRefreshKey, setFileRefreshKey] = useState(0);
  const { upload: fileUpload, uploading: fileUploading } = useFileUpload(filePath ?? undefined);

  useEffect(() => {
    let active = true;
    Promise.all([listFileRoots(), getClipboardDir()])
      .then(([r]) => {
        if (!active) return;
        setFileRoots(r);
        setFilePath((prev) => prev ?? r[0]?.path ?? null);
      })
      .catch(
        (e) =>
          active &&
          toast.error(e instanceof ApiError ? e.message : "Nicht erreichbar"),
      );
    return () => {
      active = false;
    };
  }, []);

  // Live-Sync CSS-Variable während des Ziehens (kein React-Rerender pro
  // Pixel) — SplitDivider ruft diese Funktion auf mouseMove auf.
  const liveSetSplit = (r: number) => {
    const el = containerRef.current;
    if (el) el.style.setProperty("--split", String(r));
  };

  const filesOpen = panes.some((p) => p?.kind === "files");

  function handleFileUpload(files: File[]) {
    void fileUpload(files).then((entries) => {
      if (entries.length) {
        toast.success(`${entries.length} Datei(en) hochgeladen`);
        setFileRefreshKey((k) => k + 1);
      }
    });
  }

  async function handleNewFolder() {
    if (!filePath) return;
    const name = window.prompt("Name des neuen Ordners:")?.trim();
    if (!name) return;
    try {
      await makeDir(filePath, name);
      setFileRefreshKey((k) => k + 1);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Ordner anlegen fehlgeschlagen");
    }
  }

  const canGoUp =
    filePath !== null && !fileRoots.some((r) => r.path === filePath);

  // File-Fullscreen-Schicht: zeigt die gewählte Datei über beide Pane.
  // Der Explorer-State (Pfad, Listing, Auswahl) bleibt gemountet darunter
  // und taucht beim „Zurück zu Dateien" 1:1 wieder auf.
  const [fullscreenEntry, setFullscreenEntry] = useState<FileEntry | null>(null);

  function handleOpenFile(entry: FileEntry) {
    setFullscreenEntry(entry);
    openFileFullscreen();
  }

  const mobileTablist = twoPanes;

  return (
    <div className="relative flex h-dvh flex-col">
      {/* Workspace-Toolbar: Back · Dateien-Toggle · Zurück zu Dateien. */}
      <div className="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2">
        <Link
          href="/"
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Cockpit
        </Link>
        <div className="ml-auto flex items-center gap-2">
          {fileFullscreen ? (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={closeFileFullscreen}
            >
              <ArrowLeft className="size-4" /> Zurück zu Dateien
            </Button>
          ) : (
            <Button
              type="button"
              size="sm"
              variant={filesOpen ? "secondary" : "outline"}
              onClick={toggleFiles}
              aria-pressed={filesOpen}
            >
              <FolderIcon className="size-4" /> {filesOpen ? "Dateien schließen" : "Dateien"}
            </Button>
          )}
        </div>
      </div>

      {/* Mobile-Tab-Leiste (unterhalb MD): wechselt zwischen den beiden
          offenen Panes — Session ODER Dateien (BUG-11-Fix: vorher nur
          Sessions, der Datei-Pane war auf Mobile nie erreichbar). */}
      {mobileTablist && !fileFullscreen && (
        <div
          role="tablist"
          aria-label="Offene Arbeitsflächen"
          className="flex shrink-0 items-center gap-1 border-b border-border px-2 py-1.5 md:hidden"
        >
          {panes.map((pane, idx) => {
            if (pane === null) return null;
            const paneIndex = idx as PaneIndex;
            const isActive = paneIndex === activeIndex;
            const label =
              pane.kind === "session"
                ? (() => {
                    const s = sessions.find((x) => x.session_id === pane.id);
                    return s ? displayName(s) : pane.id;
                  })()
                : "Dateien";
            return (
              <button
                key={`${paneIndex}-${pane.kind}`}
                role="tab"
                aria-selected={isActive}
                onClick={() => focus(paneIndex)}
                className={cn(
                  "min-w-0 flex-1 truncate rounded-md px-3 py-1.5 text-sm transition-colors",
                  isActive
                    ? "bg-accent font-medium text-accent-foreground"
                    : "text-muted-foreground hover:bg-accent/50",
                )}
              >
                {label}
              </button>
            );
          })}
        </div>
      )}

      {/* Zwei-Pane-Workspace — auf Desktop nebeneinander, darunter gestapelt.
          Jeder Pane wird EINMAL gemountet; CSS versteckt den inaktiven. */}
      <div
        ref={containerRef}
        className={cn("flex min-h-0 flex-1 flex-col md:flex-row")}
        style={
          twoPanes
            ? ({ ["--split" as string]: `${splitRatio}` } as React.CSSProperties)
            : undefined
        }
      >
        {panes.map((pane, idx) => (
          <Fragment key={`${idx}-${pane?.kind ?? "empty"}-${pane?.kind === "session" ? pane.id : ""}`}>
            {idx === 1 && twoPanes && (
              <SplitDivider
                containerRef={containerRef}
                ratio={splitRatio}
                onChange={liveSetSplit}
                onCommit={setSplitRatio}
              />
            )}
            <PaneSlot
              pane={pane}
              index={idx as PaneIndex}
              activeIndex={activeIndex}
              twoPanes={twoPanes}
              singlePane={singlePane}
              fileFullscreen={fileFullscreen}
              filePath={filePath}
              fileRefreshKey={fileRefreshKey}
              fileCanGoUp={canGoUp}
              fileUploading={fileUploading}
              onFilePathChange={setFilePath}
              onFileOpen={handleOpenFile}
              onFileUpload={handleFileUpload}
              onFileNewFolder={handleNewFolder}
              onFileRefresh={() => setFileRefreshKey((k) => k + 1)}
            />
          </Fragment>
        ))}
      </div>

      {fileFullscreen && fullscreenEntry && (
        <div className="absolute inset-0 z-40 flex flex-col bg-background">
          <div className="flex shrink-0 items-center gap-2 border-b border-border px-3 py-2">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={closeFileFullscreen}
            >
              <ArrowLeft className="size-4" /> Zurück zu Dateien
            </Button>
            <span className="ml-2 flex min-w-0 items-center gap-1.5 truncate text-sm">
              <FileIcon className="size-4 shrink-0 text-muted-foreground" />
              <span className="truncate">{fullscreenEntry.name}</span>
            </span>
            <span className="ml-auto font-mono text-xs text-muted-foreground">
              {fullscreenEntry.path}
            </span>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto">
            <div className="mx-auto max-w-3xl px-4 py-6 md:px-8">
              <FilePreview key={fullscreenEntry.path} entry={fullscreenEntry} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PaneSlot({
  pane,
  index,
  activeIndex,
  twoPanes,
  singlePane,
  fileFullscreen,
  filePath,
  fileRefreshKey,
  fileCanGoUp,
  fileUploading,
  onFilePathChange,
  onFileOpen,
  onFileUpload,
  onFileNewFolder,
  onFileRefresh,
}: {
  pane: Pane;
  index: PaneIndex;
  activeIndex: PaneIndex;
  twoPanes: boolean;
  singlePane: boolean;
  fileFullscreen: boolean;
  filePath: string | null;
  fileRefreshKey: number;
  fileCanGoUp: boolean;
  fileUploading: boolean;
  onFilePathChange: (p: string) => void;
  onFileOpen: (entry: FileEntry) => void;
  onFileUpload: (files: File[]) => void;
  onFileNewFolder: () => void;
  onFileRefresh: () => void;
}) {
  if (pane === null) return null;
  const isActive = index === activeIndex;
  const hiddenByFullscreen = fileFullscreen;

  // Breite der zwei Pane-Slots: linke Seite = --split, rechte = 1 - --split.
  // Inline-Style, weil Tailwind arbitrary values keine calc() mit CSS-Vars
  // vollständig ausdrücken können.
  const paneWidth: React.CSSProperties | undefined = twoPanes
    ? {
        flexBasis: index === 0
          ? `calc(var(--split, 0.5) * 100%)`
          : `calc((1 - var(--split, 0.5)) * 100%)`,
      }
    : undefined;

  if (pane.kind === "session") {
    return (
      <div
        className={cn(
          "flex min-w-0 min-h-0 flex-col",
          singlePane && "mx-auto w-full max-w-4xl",
          twoPanes && !isActive && "hidden md:flex",
          // Sichtbare Markierung, welcher Pane aktiv ist (= Ersetzungsziel
          // für "Aktiv machen" / Sidebar-Öffnen; "Dateien" ersetzt den
          // JEWEILS ANDEREN Pane) — ohne diese war für Nutzer nicht
          // vorhersehbar, welche Ansicht beim Öffnen von Dateien verschwindet.
          twoPanes && (isActive ? "border-t-2 border-t-primary" : "border-t-2 border-t-transparent"),
          hiddenByFullscreen && "hidden",
        )}
        style={paneWidth}
      >
        <SessionView id={pane.id} paneIndex={index} />
      </div>
    );
  }

  return (
    <div
      className={cn(
        "flex min-w-0 min-h-0 flex-col",
        singlePane && "mx-auto w-full max-w-4xl",
        twoPanes && !isActive && "hidden md:flex",
        twoPanes && (isActive ? "border-t-2 border-t-primary" : "border-t-2 border-t-transparent"),
        hiddenByFullscreen && "hidden",
      )}
      style={paneWidth}
    >
      <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
        <Button
          type="button"
          size="sm"
          variant="outline"
          disabled={!fileCanGoUp}
          onClick={() => filePath && onFilePathChange(parentOf(filePath))}
        >
          Hoch
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onFileRefresh}
          disabled={!filePath}
          title="Listing neu laden"
        >
          ↻
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onFileNewFolder}
          disabled={!filePath}
        >
          Neuer Ordner
        </Button>
        <UploadButton onPick={onFileUpload} uploading={fileUploading} />
        {filePath && (
          <span
            className="hidden min-w-0 max-w-[40%] truncate font-mono text-xs text-muted-foreground md:block"
            title={filePath}
          >
            {filePath}
          </span>
        )}
      </div>
      <div className="flex min-h-0 flex-1">
        <FileWorkspace
          key={filePath ?? "__none__"}
          path={filePath}
          onPathChange={onFilePathChange}
          onOpenFile={onFileOpen}
          storageKey="workspace:files:list-width"
          defaultListWidth={320}
          refreshKey={fileRefreshKey}
        />
      </div>
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
        Hochladen {uploading ? "…" : ""}
      </Button>
    </>
  );
}
