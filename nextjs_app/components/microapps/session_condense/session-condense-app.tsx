"use client";

// PROJ-55: Native Micro-App „Session-Kondensierung".
// Wochen-Sweep über alte rohe Session-Logs (`Agentic OS/Jupiter/Sessions/`):
// verdichtet die wichtigsten Erkenntnisse via headless `hal-session-condense`-Session
// nach `Knowledge/` und archiviert+gzip die Roh-Logs. Reine Ansicht + Steuerung —
// ALLE Auswahl-/Archiv-/Zeitplan-Logik liegt im Backend-Worker (Tab schließen
// unterbricht den Sweep nicht). Die Liste POLLT GET /session-condense/queue.

import { useCallback, useEffect, useRef, useState } from "react";
import {
  BrainCircuitIcon,
  PlayIcon,
  ScanLineIcon,
  Trash2Icon,
  RotateCcwIcon,
  Settings2Icon,
  FileTextIcon,
  HistoryIcon,
  ArchiveIcon,
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ApiError,
  deleteSessionCondenseItem,
  getEngines,
  getSessionCondenseQueue,
  getSessionCondenseRuns,
  getSessionCondenseSettings,
  mdReaderUrl,
  patchSessionCondenseSettings,
  retrySessionCondenseItem,
  runSessionCondense,
  scanSessionCondense,
} from "@/lib/api";
import { modelLabel } from "@/lib/status";
import type {
  EngineRead,
  SessionCondenseItem,
  SessionCondenseQueue,
  SessionCondenseRun,
  SessionCondenseSettings,
  SessionCondenseStatus,
  SessionCondenseWorkerState,
} from "@/lib/types";

/** Lesbares Label für einen Modell-Slug. Claude-Aliase über `modelLabel`; Fremd-Slugs
 *  (z. B. „opencode-go/minimax-m3") auf den Teil nach dem „/" gekürzt + entkebabt. */
function condenseModelLabel(model: string): string {
  const base = modelLabel(model);
  if (base !== model) return base;
  const tail = model.includes("/") ? (model.split("/").pop() ?? model) : model;
  return tail.replace(/-/g, " ");
}

// Wochentage für den Zeitplan (DOW HH:MM).
const DOW_CHOICES: { value: string; label: string }[] = [
  { value: "MON", label: "Montag" },
  { value: "TUE", label: "Dienstag" },
  { value: "WED", label: "Mittwoch" },
  { value: "THU", label: "Donnerstag" },
  { value: "FRI", label: "Freitag" },
  { value: "SAT", label: "Samstag" },
  { value: "SUN", label: "Sonntag" },
];

const POLL_INTERVAL_MS = 3000;

/** ISO-Zeit → lokales „TT.MM., HH:MM" (für den nächsten Plan-Lauf / Protokoll). */
function fmtDateTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/** knowledge_paths (JSON-Array-String) → Pfad-Liste (best-effort). */
function parseNotePaths(raw: string | null): string[] {
  if (!raw) return [];
  try {
    const arr = JSON.parse(raw);
    return Array.isArray(arr) ? arr.filter((x): x is string => typeof x === "string") : [];
  } catch {
    return [];
  }
}

const STATUS_LABEL: Record<SessionCondenseStatus, string> = {
  pending: "Wartend",
  running: "Läuft",
  done: "Fertig",
  error: "Fehler",
};

function StatusBadge({ item }: { item: SessionCondenseItem }) {
  if (item.status === "done") {
    if (item.outcome === "trivial")
      return (
        <Badge className="border-slate-500/40 bg-slate-500/10 text-slate-400">
          Trivial (archiviert)
        </Badge>
      );
    return (
      <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-500">
        Kondensiert
      </Badge>
    );
  }
  if (item.status === "error") return <Badge variant="destructive">{STATUS_LABEL.error}</Badge>;
  if (item.status === "running") return <Badge>{STATUS_LABEL.running}</Badge>;
  return <Badge variant="secondary">{STATUS_LABEL.pending}</Badge>;
}

function WorkerBadge({ state }: { state: SessionCondenseWorkerState }) {
  if (state.status === "running") return <Badge>Läuft</Badge>;
  if (state.status === "draining")
    return (
      <Badge className="border-amber-500/40 bg-amber-500/10 text-amber-500">Arbeitet ab</Badge>
    );
  return <Badge variant="outline">Leerlauf</Badge>;
}

export default function SessionCondenseApp() {
  const [queue, setQueue] = useState<SessionCondenseQueue | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const q = await getSessionCondenseQueue(signal);
      setQueue(q);
      setLoadError(null);
    } catch (err) {
      if (signal?.aborted) return;
      setLoadError(err instanceof ApiError ? err.message : "Nicht erreichbar");
    }
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    const tick = () => {
      getSessionCondenseQueue(ctrl.signal)
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

  async function handleScan() {
    if (busy) return;
    setBusy(true);
    try {
      const q = await scanSessionCondense();
      setQueue(q);
      const pending = q.items.filter((i) => i.status === "pending").length;
      toast.success(`Scan fertig — ${pending} Session(s) wartend.`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Scan fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleRun() {
    if (busy) return;
    setBusy(true);
    try {
      const q = await runSessionCondense();
      setQueue(q);
      toast.success("Kondensierung gestartet");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Start fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(id: number) {
    try {
      await deleteSessionCondenseItem(id);
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Entfernen fehlgeschlagen");
    }
  }

  async function handleRetry(id: number) {
    try {
      const q = await retrySessionCondenseItem(id);
      setQueue(q);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Erneut versuchen fehlgeschlagen");
    }
  }

  const items = queue?.items ?? [];
  const state = queue?.state;
  const pendingCount = items.filter((i) => i.status === "pending").length;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5 p-5">
      {/* Kopf */}
      <section className="rounded-xl border border-border bg-card p-4">
        <div className="flex items-center gap-2">
          <BrainCircuitIcon className="size-5 text-primary" />
          <h1 className="text-base font-semibold">Session-Kondensierung</h1>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          Alte Session-Logs (älter als die eingestellte Schwelle) werden zu kompakten
          Knowledge-Notizen verdichtet und die Roh-Logs anschließend archiviert (gzip).
          Läuft serverseitig — Tab schließen unterbricht nichts.
        </p>
      </section>

      {/* Steuerleiste */}
      <section className="flex flex-wrap items-center gap-3">
        <Button onClick={handleRun} disabled={busy} size="sm">
          <PlayIcon className="size-4" />
          Jetzt kondensieren
        </Button>
        <Button onClick={handleScan} disabled={busy} variant="outline" size="sm">
          <ScanLineIcon className="size-4" />
          Nur scannen
        </Button>
        {state && <WorkerBadge state={state} />}
        {state?.next_scheduled_run && (
          <span className="text-xs text-muted-foreground">
            Nächster Plan-Lauf: {fmtDateTime(state.next_scheduled_run)}
          </span>
        )}
        <div className="ml-auto">
          <SettingsDialog onSaved={() => void refresh()} />
        </div>
      </section>

      {/* Warteschlange */}
      <section className="rounded-xl border border-border bg-card">
        <header className="flex items-center gap-2 border-b border-border px-4 py-3">
          <h2 className="text-sm font-medium">Warteschlange</h2>
          {items.length > 0 && (
            <Badge variant="outline" className="ml-auto">
              {pendingCount} wartend · {items.length} gesamt
            </Badge>
          )}
        </header>
        {loadError && !queue ? (
          <p className="px-4 py-6 text-sm text-red-400">
            Warteschlange nicht erreichbar ({loadError}).
          </p>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-4 py-12 text-center">
            <BrainCircuitIcon className="size-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Keine alten Sessions in der Warteschlange. &bdquo;Nur scannen&ldquo; prüft
              auf neue Kandidaten.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((item) => (
              <SessionRow
                key={item.id}
                item={item}
                onRemove={() => handleRemove(item.id)}
                onRetry={() => handleRetry(item.id)}
              />
            ))}
          </ul>
        )}
      </section>

      {/* Lauf-Protokoll */}
      <RunsSection />
    </div>
  );
}

const RUNS_POLL_MS = 8000;

function RunsSection() {
  const [runs, setRuns] = useState<SessionCondenseRun[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    const tick = () => {
      getSessionCondenseRuns(ctrl.signal)
        .then((list) => {
          setRuns(list);
          setError(null);
        })
        .catch((err) => {
          if (ctrl.signal.aborted) return;
          setError(err instanceof ApiError ? err.message : "Nicht erreichbar");
        });
    };
    tick();
    const t = setInterval(tick, RUNS_POLL_MS);
    return () => {
      ctrl.abort();
      clearInterval(t);
    };
  }, []);

  return (
    <section className="rounded-xl border border-border bg-card">
      <header className="flex items-center gap-2 border-b border-border px-4 py-3">
        <HistoryIcon className="size-4 text-muted-foreground" />
        <h2 className="text-sm font-medium">Lauf-Protokoll</h2>
        <span className="text-xs text-muted-foreground">letzte Sweeps</span>
      </header>

      {error && !runs ? (
        <p className="px-4 py-6 text-sm text-red-400">Protokoll nicht erreichbar ({error}).</p>
      ) : runs === null ? (
        <p className="px-4 py-6 text-sm text-muted-foreground">Lädt…</p>
      ) : runs.length === 0 ? (
        <p className="px-4 py-6 text-sm text-muted-foreground">Noch kein Lauf.</p>
      ) : (
        <ul className="divide-y divide-border">
          {runs.map((run) => (
            <li key={run.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-xs">
              <span className="font-medium text-foreground">
                {fmtDateTime(run.started_at) || `Lauf #${run.id}`}
                {run.finished_at ? "" : " · läuft"}
              </span>
              <span className="text-muted-foreground">{run.checked} geprüft</span>
              <span className="text-emerald-500">{run.condensed} kondensiert</span>
              <span className="text-slate-400">{run.trivial} trivial</span>
              <span className="inline-flex items-center gap-1 text-muted-foreground">
                <ArchiveIcon className="size-3" />
                {run.archived} archiviert
              </span>
              {run.pruned > 0 && (
                <span className="text-muted-foreground">{run.pruned} gelöscht</span>
              )}
              {run.errors > 0 && <span className="text-red-400">{run.errors} Fehler</span>}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function SessionRow({
  item,
  onRemove,
  onRetry,
}: {
  item: SessionCondenseItem;
  onRemove: () => void;
  onRetry: () => void;
}) {
  const notes = parseNotePaths(item.knowledge_paths);
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          {item.project && (
            <Badge variant="outline" className="shrink-0 text-[10px]">
              {item.project}
            </Badge>
          )}
          <p className="truncate font-mono text-xs text-foreground" title={item.session_filename}>
            {item.session_filename}
          </p>
        </div>
        {item.status === "done" && item.outcome === "condensed" && (
          <div className="mt-1 flex flex-wrap gap-3 text-xs">
            {notes.length > 0 ? (
              notes.map((p) => (
                <a
                  key={p}
                  href={mdReaderUrl(p)}
                  className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
                  title={p}
                >
                  <FileTextIcon className="size-3.5" /> {p.split("/").pop()}
                </a>
              ))
            ) : (
              <span className="text-muted-foreground">Kondensiert — siehe Knowledge-Ordner.</span>
            )}
          </div>
        )}
        {item.status === "error" && item.error_message && (
          <p className="mt-1 text-xs text-red-400">{item.error_message}</p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <StatusBadge item={item} />
        {item.status === "error" && (
          <Button variant="ghost" size="icon-sm" onClick={onRetry} title="Erneut versuchen">
            <RotateCcwIcon className="size-4" />
          </Button>
        )}
        <Button variant="ghost" size="icon-sm" onClick={onRemove} title="Aus Liste entfernen">
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
  const [planEnabled, setPlanEnabled] = useState(true);
  const [dow, setDow] = useState("MON");
  const [time, setTime] = useState("03:00");
  const [ageDays, setAgeDays] = useState("7");
  const [retentionDays, setRetentionDays] = useState("30");
  const [minChars, setMinChars] = useState("800");
  const [engine, setEngine] = useState("opencode");
  const [model, setModel] = useState("opencode-go/minimax-m3");
  const [engines, setEngines] = useState<EngineRead[]>([]);
  const loaded = useRef(false);

  // Nur steuerbare Session-Engines (kind=engine) — keine iFrames/Launch-Einträge.
  const sessionEngines = engines.filter((e) => e.kind === "engine");
  const selectedEngine = sessionEngines.find((e) => e.key === engine);
  const modelOptions = selectedEngine?.models ?? (model ? [model] : []);

  /** Engine wechseln → Modell auf den (ersten gültigen) Wert der neuen Engine setzen. */
  function handleEngineChange(nextKey: string) {
    setEngine(nextKey);
    const eng = sessionEngines.find((e) => e.key === nextKey);
    if (eng && !eng.models.includes(model)) {
      setModel(eng.default_model ?? eng.models[0] ?? "");
    }
  }

  function applySchedule(schedule: string) {
    const m = /^(MON|TUE|WED|THU|FRI|SAT|SUN)\s+(\d{1,2}:\d{2})$/i.exec(schedule.trim());
    if (m) {
      setPlanEnabled(true);
      setDow(m[1].toUpperCase());
      setTime(m[2].padStart(5, "0"));
    } else {
      setPlanEnabled(false);
    }
  }

  async function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next || loaded.current) return;
    setLoading(true);
    try {
      const [s, eng] = await Promise.all([
        getSessionCondenseSettings(),
        getEngines().catch(() => null),
      ]);
      if (eng) setEngines(eng.engines);
      applySchedule(s.schedule);
      setAgeDays(String(s.age_days));
      setRetentionDays(String(s.retention_days));
      setMinChars(String(s.min_chars));
      setEngine(s.engine);
      setModel(s.model);
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
      const schedule = planEnabled ? `${dow} ${time}` : "";
      const patch: Partial<SessionCondenseSettings> = {
        schedule,
        age_days: Math.max(0, Number(ageDays) || 0),
        retention_days: Math.max(0, Number(retentionDays) || 0),
        min_chars: Math.max(0, Number(minChars) || 0),
        engine,
        model,
      };
      const s = await patchSessionCondenseSettings(patch);
      applySchedule(s.schedule);
      setAgeDays(String(s.age_days));
      setRetentionDays(String(s.retention_days));
      setMinChars(String(s.min_chars));
      setEngine(s.engine);
      setModel(s.model);
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
          <DialogTitle>Session-Kondensierung — Einstellungen</DialogTitle>
          <DialogDescription>
            Wochenplan, Schwellen sowie Engine + Modell. Gilt serverseitig für den Sweep.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Lädt…</p>
        ) : (
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label>Wochenplan</Label>
              <div className="flex items-center gap-2">
                <Select
                  value={planEnabled ? "on" : "off"}
                  onValueChange={(v) => setPlanEnabled(v === "on")}
                >
                  <SelectTrigger aria-label="Zeitplan aktiv" className="w-28">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="on">Wöchentlich</SelectItem>
                    <SelectItem value="off">Nur manuell</SelectItem>
                  </SelectContent>
                </Select>
                {planEnabled && (
                  <>
                    <Select value={dow} onValueChange={(v) => setDow(v ?? "MON")}>
                      <SelectTrigger aria-label="Wochentag" className="flex-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {DOW_CHOICES.map((d) => (
                          <SelectItem key={d.value} value={d.value}>
                            {d.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <Input
                      aria-label="Uhrzeit"
                      type="time"
                      value={time}
                      onChange={(e) => setTime(e.target.value)}
                      className="w-28"
                    />
                  </>
                )}
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-2">
                <Label htmlFor="sc_age">Kondensieren ab (Tage)</Label>
                <Input
                  id="sc_age"
                  type="number"
                  min={0}
                  max={3650}
                  value={ageDays}
                  onChange={(e) => setAgeDays(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="sc_ret">Archiv löschen nach (Tage)</Label>
                <Input
                  id="sc_ret"
                  type="number"
                  min={0}
                  max={3650}
                  value={retentionDays}
                  onChange={(e) => setRetentionDays(e.target.value)}
                />
              </div>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="sc_min">Trivial-Schwelle (Zeichen)</Label>
              <Input
                id="sc_min"
                type="number"
                min={0}
                max={100000}
                value={minChars}
                onChange={(e) => setMinChars(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Kürzere Logs ohne Erkenntnis-Marker werden nur archiviert (kein Skill-Lauf).
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="grid gap-2">
                <Label htmlFor="sc_engine">Engine</Label>
                <Select value={engine} onValueChange={(v) => v && handleEngineChange(v)}>
                  <SelectTrigger id="sc_engine" aria-label="Engine">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {sessionEngines.length === 0 && (
                      <SelectItem value={engine}>{engine}</SelectItem>
                    )}
                    {sessionEngines.map((e) => (
                      <SelectItem key={e.key} value={e.key} disabled={!e.available}>
                        {e.label}
                        {!e.available && " — nicht verfügbar"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="sc_model">Modell</Label>
                <Select value={model} onValueChange={(v) => v && setModel(v)}>
                  <SelectTrigger id="sc_model" aria-label="Kondensier-Modell">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {modelOptions.map((m) => (
                      <SelectItem key={m} value={m}>
                        {condenseModelLabel(m)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            {selectedEngine && !selectedEngine.available && selectedEngine.unavailable_reason && (
              <p className="-mt-2 text-xs text-amber-500">
                {selectedEngine.unavailable_reason}
              </p>
            )}
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
