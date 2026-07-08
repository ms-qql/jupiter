"use client";

// PROJ-69: Native Micro-App „Clipboard".
// Geräteübergreifender Datei-Puffer: Upload/Paste/Drag&Drop → HAL-Inbox +
// aktive Liste. Keine Verarbeitung im Hintergrund; die UI aktualisiert direkt
// nach jeder Aktion und pollt zusätzlich leicht für andere Geräte.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ClipboardIcon,
  CopyIcon,
  DownloadIcon,
  EyeIcon,
  FileIcon,
  FileTextIcon,
  ImageIcon,
  PencilIcon,
  RefreshCwIcon,
  Share2Icon,
  Trash2Icon,
  UploadIcon,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  deleteClipboardItem,
  downloadClipboardItem,
  fetchClipboardBlob,
  getClipboardItems,
  getClipboardSettings,
  patchClipboardItem,
  uploadClipboardItem,
} from "@/lib/api";
import type {
  ClipboardItem as ClipboardItemRead,
  ClipboardList,
  ClipboardSettings,
  ClipboardSourceDevice,
  ClipboardSourceMethod,
} from "@/lib/types";

const POLL_INTERVAL_MS = 5000;

function fmtDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function deviceLabel(device: ClipboardSourceDevice | null): string {
  const labels: Record<ClipboardSourceDevice, string> = {
    pc: "PC",
    mac: "Mac",
    ipad: "iPad",
    iphone: "iPhone",
    unknown: "Unbekannt",
  };
  return labels[device ?? "unknown"];
}

function methodLabel(method: ClipboardSourceMethod): string {
  return {
    drag_drop: "Drag&Drop",
    paste: "Paste",
    upload: "Upload",
    ios_share: "iOS Share",
  }[method];
}

function detectDevice(): ClipboardSourceDevice {
  if (typeof navigator === "undefined") return "unknown";
  const ua = navigator.userAgent.toLowerCase();
  const platform = navigator.platform?.toLowerCase() ?? "";
  const touchMac = platform.includes("mac") && navigator.maxTouchPoints > 1;
  if (ua.includes("iphone")) return "iphone";
  if (ua.includes("ipad") || touchMac) return "ipad";
  if (platform.includes("mac")) return "mac";
  if (platform.includes("win") || platform.includes("linux")) return "pc";
  return "unknown";
}

function isImage(item: ClipboardItemRead): boolean {
  return (item.mime_type ?? "").startsWith("image/");
}

function isPdf(item: ClipboardItemRead): boolean {
  return item.mime_type === "application/pdf" || item.extension === "pdf";
}

function itemIcon(item: ClipboardItemRead) {
  if (isImage(item)) return <ImageIcon className="size-4 text-sky-500" />;
  if (isPdf(item)) return <FileTextIcon className="size-4 text-red-500" />;
  return <FileIcon className="size-4 text-muted-foreground" />;
}

type PreviewState = {
  item: ClipboardItemRead;
  url: string;
  kind: "image" | "pdf" | "file";
};

type EditState = {
  item: ClipboardItemRead;
  displayName: string;
  notes: string;
};

export default function ClipboardApp() {
  const [list, setList] = useState<ClipboardList | null>(null);
  const [settings, setSettings] = useState<ClipboardSettings | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [preview, setPreview] = useState<PreviewState | null>(null);
  const [edit, setEdit] = useState<EditState | null>(null);

  const fileRef = useRef<HTMLInputElement>(null);
  const device = useMemo(() => detectDevice(), []);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const [items, cfg] = await Promise.all([
        getClipboardItems(signal),
        getClipboardSettings(signal),
      ]);
      setList(items);
      setSettings(cfg);
      setLoadError(null);
    } catch (err) {
      if (signal?.aborted) return;
      setLoadError(err instanceof ApiError ? err.message : "Nicht erreichbar");
    }
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    const tick = () => void refresh(ctrl.signal);
    tick();
    const t = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      ctrl.abort();
      clearInterval(t);
    };
  }, [refresh]);

  useEffect(() => {
    return () => {
      if (preview?.url) URL.revokeObjectURL(preview.url);
    };
  }, [preview]);

  async function handleFiles(files: FileList | File[] | null, method: ClipboardSourceMethod) {
    const arr = Array.from(files ?? []);
    if (!arr.length || uploading) return;
    setUploading(true);
    try {
      for (const file of arr) {
        await uploadClipboardItem(file, method, device);
      }
      toast.success(`${arr.length} Datei(en) in Clipboard übernommen`);
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Upload fehlgeschlagen");
      await refresh();
    } finally {
      setUploading(false);
      if (fileRef.current) fileRef.current.value = "";
    }
  }

  async function handlePaste(e: React.ClipboardEvent<HTMLDivElement>) {
    const files = Array.from(e.clipboardData.files ?? []);
    if (!files.length) return;
    e.preventDefault();
    await handleFiles(files, "paste");
  }

  async function openPreview(item: ClipboardItemRead) {
    try {
      const blob = await fetchClipboardBlob(item.id, "preview");
      const url = URL.createObjectURL(blob);
      setPreview({
        item,
        url,
        kind: isImage(item) ? "image" : isPdf(item) ? "pdf" : "file",
      });
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Vorschau fehlgeschlagen");
    }
  }

  async function copyImage(item: ClipboardItemRead) {
    if (!isImage(item)) return;
    if (!("clipboard" in navigator) || !("ClipboardItem" in window)) {
      toast.error("Dieser Browser kann Bilder nicht in die Zwischenablage kopieren");
      return;
    }
    try {
      const blob = await fetchClipboardBlob(item.id, "download");
      await navigator.clipboard.write([
        new ClipboardItem({ [blob.type || item.mime_type || "image/png"]: blob }),
      ]);
      toast.success("Bild in Zwischenablage kopiert");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Kopieren fehlgeschlagen");
    }
  }

  async function shareItem(item: ClipboardItemRead) {
    if (!navigator.share) {
      await downloadClipboardItem(item);
      return;
    }
    try {
      const blob = await fetchClipboardBlob(item.id, "download");
      const file = new File([blob], item.display_name, {
        type: blob.type || item.mime_type || "application/octet-stream",
      });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: item.display_name });
      } else {
        await downloadClipboardItem(item);
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Teilen fehlgeschlagen");
    }
  }

  async function removeItem(item: ClipboardItemRead) {
    try {
      await deleteClipboardItem(item.id);
      toast.success("Aus aktiver Liste entfernt; HAL-Datei bleibt erhalten");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Entfernen fehlgeschlagen");
    }
  }

  async function saveEdit() {
    if (!edit) return;
    try {
      await patchClipboardItem(edit.item.id, {
        display_name: edit.displayName,
        notes: edit.notes,
      });
      setEdit(null);
      toast.success("Metadaten gespeichert");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    }
  }

  const items = list?.items ?? [];
  const accept = settings?.allowed_extensions.length
    ? settings.allowed_extensions.map((e) => `.${e}`).join(",")
    : undefined;

  return (
    <div
      className="mx-auto flex max-w-5xl flex-col gap-5 p-5"
      onPaste={(e) => void handlePaste(e)}
    >
      <section
        className={`rounded-xl border border-dashed p-5 transition-colors ${
          dragOver ? "border-primary bg-primary/5" : "border-border bg-card"
        }`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragOver(false);
          void handleFiles(e.dataTransfer.files, "drag_drop");
        }}
      >
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <ClipboardIcon className="size-5 text-primary" />
              <h2 className="text-base font-semibold">Clipboard</h2>
              <Badge variant="outline">{deviceLabel(device)}</Badge>
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              Dateien hier ablegen, einfügen oder auswählen. Alles wird automatisch im
              HAL Inbox gespeichert.
            </p>
            {settings && (
              <p className="mt-1 text-xs text-muted-foreground">
                Limit {fmtBytes(settings.max_file_bytes)} · Ziel: {settings.inbox_dir}
              </p>
            )}
          </div>
          <div className="flex flex-wrap gap-2">
            <input
              ref={fileRef}
              type="file"
              multiple
              accept={accept}
              className="hidden"
              onChange={(e) => void handleFiles(e.target.files, "upload")}
            />
            <Button
              type="button"
              size="sm"
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
            >
              <UploadIcon className="size-4" />
              {uploading ? "Lädt hoch…" : "Datei auswählen"}
            </Button>
            <Button type="button" size="sm" variant="outline" onClick={() => void refresh()}>
              <RefreshCwIcon className="size-4" />
              Aktualisieren
            </Button>
          </div>
        </div>
      </section>

      {loadError && (
        <p className="rounded-lg border border-red-500/40 bg-red-500/5 px-4 py-3 text-sm text-red-500">
          Clipboard nicht erreichbar: {loadError}
        </p>
      )}

      <section className="rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h3 className="text-sm font-semibold">Aktive Einträge</h3>
            <p className="text-xs text-muted-foreground">
              Entfernen räumt nur diese Liste auf; HAL-Rohdateien bleiben erhalten.
            </p>
          </div>
          <Badge variant="secondary">{items.length}</Badge>
        </div>

        {items.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 px-4 py-12 text-center">
            <ClipboardIcon className="size-8 text-muted-foreground" />
            <p className="text-sm font-medium">Noch keine Clipboard-Einträge</p>
            <p className="max-w-md text-xs text-muted-foreground">
              Ziehe eine Datei hierher, füge einen Screenshot ein oder nutze die
              Dateiauswahl. Auf iPhone/iPad funktioniert der Upload über die
              Browser-Dateiauswahl.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {items.map((item) => (
              <div
                key={item.id}
                className="flex flex-col gap-3 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0 flex items-start gap-3">
                  <div className="mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-md border border-border">
                    {itemIcon(item)}
                  </div>
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium">{item.display_name}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                      <span>{item.mime_type || item.extension || "Datei"}</span>
                      <span>{fmtBytes(item.size_bytes)}</span>
                      <span>{methodLabel(item.source_method)}</span>
                      <span>{deviceLabel(item.source_device)}</span>
                      <span>{fmtDate(item.created_at)}</span>
                    </div>
                    {item.notes && (
                      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                        {item.notes}
                      </p>
                    )}
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 sm:justify-end">
                  <Button size="icon" variant="outline" onClick={() => void openPreview(item)}>
                    <EyeIcon className="size-4" />
                    <span className="sr-only">Vorschau</span>
                  </Button>
                  <Button
                    size="icon"
                    variant="outline"
                    onClick={() => void downloadClipboardItem(item)}
                  >
                    <DownloadIcon className="size-4" />
                    <span className="sr-only">Herunterladen</span>
                  </Button>
                  <Button
                    size="icon"
                    variant="outline"
                    disabled={!isImage(item)}
                    onClick={() => void copyImage(item)}
                  >
                    <CopyIcon className="size-4" />
                    <span className="sr-only">In Zwischenablage kopieren</span>
                  </Button>
                  <Button size="icon" variant="outline" onClick={() => void shareItem(item)}>
                    <Share2Icon className="size-4" />
                    <span className="sr-only">Teilen oder öffnen</span>
                  </Button>
                  <Button
                    size="icon"
                    variant="outline"
                    onClick={() =>
                      setEdit({
                        item,
                        displayName: item.display_name,
                        notes: item.notes ?? "",
                      })
                    }
                  >
                    <PencilIcon className="size-4" />
                    <span className="sr-only">Bearbeiten</span>
                  </Button>
                  <Button size="icon" variant="outline" onClick={() => void removeItem(item)}>
                    <Trash2Icon className="size-4" />
                    <span className="sr-only">Entfernen</span>
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <Dialog open={preview !== null} onOpenChange={(open) => !open && setPreview(null)}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>{preview?.item.display_name ?? "Vorschau"}</DialogTitle>
            <DialogDescription>
              {preview ? `${fmtBytes(preview.item.size_bytes)} · ${preview.item.mime_type ?? "Datei"}` : ""}
            </DialogDescription>
          </DialogHeader>
          {preview?.kind === "image" && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={preview.url}
              alt={preview.item.display_name}
              className="max-h-[70vh] w-full rounded-md object-contain"
            />
          )}
          {preview?.kind === "pdf" && (
            <iframe
              src={preview.url}
              title={preview.item.display_name}
              className="h-[70vh] w-full rounded-md border border-border"
            />
          )}
          {preview?.kind === "file" && (
            <div className="rounded-md border border-border p-6 text-sm text-muted-foreground">
              Für diesen Dateityp gibt es keine Browser-Vorschau. Nutze Download oder Teilen.
            </div>
          )}
          <DialogFooter>
            {preview && (
              <Button onClick={() => void downloadClipboardItem(preview.item)}>
                <DownloadIcon className="size-4" />
                Herunterladen
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={edit !== null} onOpenChange={(open) => !open && setEdit(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Eintrag bearbeiten</DialogTitle>
            <DialogDescription>Anzeigename und Kontextnotiz für den HAL-Sidecar.</DialogDescription>
          </DialogHeader>
          <div className="grid gap-4">
            <div className="grid gap-2">
              <Label htmlFor="clip_name">Anzeigename</Label>
              <Input
                id="clip_name"
                value={edit?.displayName ?? ""}
                onChange={(e) =>
                  setEdit((cur) => (cur ? { ...cur, displayName: e.target.value } : cur))
                }
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="clip_notes">Notiz</Label>
              <Textarea
                id="clip_notes"
                value={edit?.notes ?? ""}
                rows={4}
                onChange={(e) =>
                  setEdit((cur) => (cur ? { ...cur, notes: e.target.value } : cur))
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEdit(null)}>
              Abbrechen
            </Button>
            <Button disabled={!edit?.displayName.trim()} onClick={() => void saveEdit()}>
              Speichern
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
