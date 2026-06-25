"use client";

// PROJ-41: Native Micro-App „Video Summary".
// URL-Warteschlange → headless `hal-video-summary`-Session → Notiz+PDF im Hal-Vault.
// Reine Ansicht + Steuerung: ALLE Drossel-/Zeitplan-Logik liegt im Backend-Worker.
// Die Liste POLLT GET /video-summary/queue, weil die Verarbeitung serverseitig läuft
// (Tab schließen unterbricht sie nicht).

import { useCallback, useEffect, useRef, useState } from "react";
import {
  FilmIcon,
  PlayIcon,
  Trash2Icon,
  RotateCcwIcon,
  Settings2Icon,
  FileTextIcon,
  FileIcon,
  PlusIcon,
} from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  addVideoSummaryUrls,
  deleteVideoSummaryItem,
  fileDownloadUrl,
  getVideoSummaryQueue,
  getVideoSummarySettings,
  patchVideoSummarySettings,
  retryVideoSummaryItem,
  runVideoSummaryNow,
} from "@/lib/api";
import type {
  VideoSummaryItem,
  VideoSummaryQueue,
  VideoSummarySettings,
  VideoSummaryStatus,
  VideoSummaryWorkerState,
} from "@/lib/types";

const POLL_INTERVAL_MS = 3000;

/** ISO-Zeit → lokales „HH:MM" (für „pausiert bis" / „nächster Lauf"). */
function fmtTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleTimeString("de-DE", { hour: "2-digit", minute: "2-digit" });
}

const STATUS_LABEL: Record<VideoSummaryStatus, string> = {
  pending: "Wartend",
  running: "Läuft",
  done: "Fertig",
  error: "Fehler",
};

function StatusBadge({ status }: { status: VideoSummaryStatus }) {
  if (status === "done")
    return (
      <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-500">
        {STATUS_LABEL.done}
      </Badge>
    );
  if (status === "error") return <Badge variant="destructive">{STATUS_LABEL.error}</Badge>;
  if (status === "running") return <Badge>{STATUS_LABEL.running}</Badge>;
  return <Badge variant="secondary">{STATUS_LABEL.pending}</Badge>;
}

function WorkerBadge({ state }: { state: VideoSummaryWorkerState }) {
  if (state.status === "running") return <Badge>Läuft</Badge>;
  if (state.status === "paused")
    return (
      <Badge className="border-amber-500/40 bg-amber-500/10 text-amber-500">
        Pausiert{state.paused_until ? ` bis ${fmtTime(state.paused_until)}` : ""}
      </Badge>
    );
  return <Badge variant="outline">Leerlauf</Badge>;
}

export default function VideoSummaryApp() {
  const [queue, setQueue] = useState<VideoSummaryQueue | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);

  // Polling-Refresh (still — kein Spinner-Flackern bei jedem Tick).
  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const q = await getVideoSummaryQueue(signal);
      setQueue(q);
      setLoadError(null);
    } catch (err) {
      if (signal?.aborted) return;
      setLoadError(err instanceof ApiError ? err.message : "Nicht erreichbar");
    }
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    // setState läuft im .then-Callback (asynchron), nicht synchron im Effect-Body.
    const tick = () => {
      getVideoSummaryQueue(ctrl.signal)
        .then((q) => {
          setQueue(q);
          setLoadError(null);
        })
        .catch((err) => {
          if (ctrl.signal.aborted) return;
          setLoadError(err instanceof ApiError ? err.message : "Nicht erreichbar");
        });
    };
    tick();
    const t = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      ctrl.abort();
      clearInterval(t);
    };
  }, []);

  async function handleAdd() {
    if (!input.trim() || adding) return;
    setAdding(true);
    try {
      const res = await addVideoSummaryUrls(input);
      const parts: string[] = [];
      if (res.added.length) parts.push(`${res.added.length} hinzugefügt`);
      if (res.duplicates.length) parts.push(`${res.duplicates.length} Duplikat(e)`);
      if (res.rejected.length) parts.push(`${res.rejected.length} ungültig`);
      toast.success(parts.join(" · ") || "Nichts hinzugefügt");
      setInput("");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Hinzufügen fehlgeschlagen");
    } finally {
      setAdding(false);
    }
  }

  async function handleRunNow() {
    if (busy) return;
    setBusy(true);
    try {
      const q = await runVideoSummaryNow();
      setQueue(q);
      toast.success("Verarbeitung gestartet");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Start fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(id: number) {
    try {
      await deleteVideoSummaryItem(id);
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Entfernen fehlgeschlagen");
    }
  }

  async function handleRetry(id: number) {
    try {
      const q = await retryVideoSummaryItem(id);
      setQueue(q);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Erneut versuchen fehlgeschlagen");
    }
  }

  const items = queue?.items ?? [];
  const state = queue?.state;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5 p-5">
      {/* Eingabe */}
      <section className="rounded-xl border border-border bg-card p-4">
        <Label htmlFor="vs_urls" className="text-sm font-medium">
          Video-URLs (per Copy-and-Paste, ein Link pro Zeile)
        </Label>
        <Textarea
          id="vs_urls"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          rows={4}
          spellCheck={false}
          placeholder={"https://youtu.be/…\nhttps://vimeo.com/…"}
          className="mt-2 font-mono text-xs"
        />
        <p className="mt-1.5 text-xs text-muted-foreground">
          Ein eingefügter Block wird automatisch in einzelne Einträge zerlegt (Zeilenumbruch,
          Komma, Semikolon, Leerzeichen), getrimmt und dedupliziert.
        </p>
        <div className="mt-3">
          <Button onClick={handleAdd} disabled={!input.trim() || adding} size="sm">
            <PlusIcon className="size-4" />
            {adding ? "Füge hinzu…" : "Zur Warteschlange hinzufügen"}
          </Button>
        </div>
      </section>

      {/* Steuerleiste */}
      <section className="flex flex-wrap items-center gap-3">
        <Button onClick={handleRunNow} disabled={busy} size="sm">
          <PlayIcon className="size-4" />
          Jetzt ausführen
        </Button>
        {state && <WorkerBadge state={state} />}
        {state?.next_scheduled_run && (
          <span className="text-xs text-muted-foreground">
            Nächster Plan-Lauf: {fmtTime(state.next_scheduled_run)}
          </span>
        )}
        <div className="ml-auto">
          <SettingsDialog onSaved={() => void refresh()} />
        </div>
      </section>

      {/* Warteschlange */}
      <section className="rounded-xl border border-border bg-card">
        {loadError && !queue ? (
          <p className="px-4 py-6 text-sm text-red-400">
            Warteschlange nicht erreichbar ({loadError}).
          </p>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-4 py-12 text-center">
            <FilmIcon className="size-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Noch keine Videos in der Warteschlange.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((item) => (
              <VideoRow
                key={item.id}
                item={item}
                onRemove={() => handleRemove(item.id)}
                onRetry={() => handleRetry(item.id)}
              />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function VideoRow({
  item,
  onRemove,
  onRetry,
}: {
  item: VideoSummaryItem;
  onRemove: () => void;
  onRetry: () => void;
}) {
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate font-mono text-xs text-foreground" title={item.url}>
          {item.url}
        </p>
        {item.status === "done" && (
          <div className="mt-1 flex flex-wrap gap-3 text-xs">
            {item.result_note_path && (
              <a
                href={fileDownloadUrl(item.result_note_path)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
              >
                <FileTextIcon className="size-3.5" /> Notiz öffnen
              </a>
            )}
            {item.result_pdf_path && (
              <a
                href={fileDownloadUrl(item.result_pdf_path)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
              >
                <FileIcon className="size-3.5" /> PDF
              </a>
            )}
            {!item.result_note_path && !item.result_pdf_path && (
              <span className="text-muted-foreground">
                Fertig — Pfad nicht ermittelt (siehe Vault).
              </span>
            )}
          </div>
        )}
        {item.status === "error" && item.error_message && (
          <p className="mt-1 text-xs text-red-400">{item.error_message}</p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <StatusBadge status={item.status} />
        {item.status === "error" && (
          <Button variant="ghost" size="icon-sm" onClick={onRetry} title="Erneut versuchen">
            <RotateCcwIcon className="size-4" />
          </Button>
        )}
        <Button variant="ghost" size="icon-sm" onClick={onRemove} title="Entfernen">
          <Trash2Icon className="size-4" />
        </Button>
      </div>
    </li>
  );
}

function SettingsDialog({ onSaved }: { onSaved: () => void }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [cooldown, setCooldown] = useState("30");
  const [batch, setBatch] = useState("4");
  const [schedule, setSchedule] = useState("");
  const loaded = useRef(false);

  async function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next || loaded.current) return;
    setLoading(true);
    try {
      const s = await getVideoSummarySettings();
      setCooldown(String(s.cooldown_minutes));
      setBatch(String(s.batch_size));
      setSchedule(s.schedule);
      loaded.current = true;
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Einstellungen nicht ladbar");
      setOpen(false);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (saving) return;
    setSaving(true);
    try {
      const patch: Partial<VideoSummarySettings> = {
        cooldown_minutes: Number(cooldown) || 0,
        batch_size: Math.max(1, Number(batch) || 1),
        schedule: schedule.trim(),
      };
      const s = await patchVideoSummarySettings(patch);
      setCooldown(String(s.cooldown_minutes));
      setBatch(String(s.batch_size));
      setSchedule(s.schedule);
      toast.success("Einstellungen gespeichert");
      onSaved();
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm">
            <Settings2Icon className="size-4" />
            Einstellungen
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Video Summary — Einstellungen</DialogTitle>
          <DialogDescription>
            Drossel gegen YouTube-Blocking + optionaler Zeitplan. Gilt serverseitig.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Lädt…</p>
        ) : (
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="vs_cooldown">Cooldown-Pause (Minuten)</Label>
              <Input
                id="vs_cooldown"
                type="number"
                min={0}
                max={1440}
                value={cooldown}
                onChange={(e) => setCooldown(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Pause nach je {batch || "?"} verarbeiteten Videos.
              </p>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="vs_batch">Videos vor der Pause</Label>
              <Input
                id="vs_batch"
                type="number"
                min={1}
                max={20}
                value={batch}
                onChange={(e) => setBatch(e.target.value)}
              />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="vs_schedule">Zeitplan (täglich, HH:MM — leer = nur manuell)</Label>
              <Input
                id="vs_schedule"
                placeholder="z. B. 02:00"
                value={schedule}
                onChange={(e) => setSchedule(e.target.value)}
              />
            </div>
          </div>
        )}

        <DialogFooter showCloseButton>
          <Button onClick={handleSave} disabled={loading || saving}>
            {saving ? "Speichert…" : "Speichern"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
