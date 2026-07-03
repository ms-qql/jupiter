"use client";

// PROJ-14: Native Micro-App "UI-Check".
// URL + Modus + KI-Modell -> lokaler headless Runner -> Run-Artefakte.
// Das Frontend pollt nur die Jupiter-internen Endpunkte; die Pipeline bleibt im Backend.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChart3Icon,
  BlocksIcon,
  ExternalLinkIcon,
  ImageIcon,
  LayoutDashboardIcon,
  PaletteIcon,
  PlayIcon,
  RefreshCwIcon,
  RotateCcwIcon,
  ShieldAlertIcon,
  SquareIcon,
  WandSparklesIcon,
} from "lucide-react";
import { toast } from "sonner";
import { ThemeToggle } from "@/components/cockpit/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  cancelUiCheckRun,
  getUiCheckRun,
  getUiCheckRuns,
  runUiCheckRedesign,
  startUiCheckRun,
  uiCheckArtifactUrl,
} from "@/lib/api";
import type {
  UiCheckAiProvider,
  UiCheckDepth,
  UiCheckDimensionScore,
  UiCheckFinding,
  UiCheckMode,
  UiCheckRunDetail,
  UiCheckRunStatus,
  UiCheckRunSummary,
} from "@/lib/types";

const POLL_INTERVAL_MS = 3000;

const PROVIDERS: {
  value: UiCheckAiProvider;
  label: string;
  detail: string;
  models: string[];
}[] = [
  {
    value: "claude",
    label: "Claude",
    detail: "Stark für UI-Urteile und begründete Designkritik.",
    models: ["Claude Sonnet", "Claude Opus", "Claude Haiku"],
  },
  {
    value: "codex",
    label: "Codex",
    detail: "Robust für strukturierte Analyse und Pipeline-Schritte.",
    models: ["Codex", "Codex Mini", "Codex Pro"],
  },
  {
    value: "openrouter",
    label: "OpenRouter",
    detail: "Alternative Modellfamilien für schnelle Varianten.",
    models: ["OpenRouter Auto", "OpenRouter Reasoning", "OpenRouter Fast"],
  },
];

const STATUS_LABEL: Record<UiCheckRunStatus, string> = {
  queued: "Wartend",
  running: "Läuft",
  done: "Fertig",
  error: "Fehler",
  cancelled: "Abgebrochen",
};

const PHASES = [
  "Capture",
  "Lighthouse",
  "Branding",
  "Scoring",
  "Redesign",
  "Mockup",
];

function fmtDate(iso: string | null): string {
  if (!iso) return "unbekannt";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unbekannt";
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtScore(score: number | null): string {
  return typeof score === "number" ? `${Math.round(score)}` : "n/v";
}

function providerLabel(value: string | null): string {
  return PROVIDERS.find((p) => p.value === value)?.label ?? value ?? "n/v";
}

function statusTone(status: UiCheckRunStatus): string {
  if (status === "done") return "border-emerald-500/40 bg-emerald-500/10 text-emerald-500";
  if (status === "error") return "border-red-500/40 bg-red-500/10 text-red-500";
  if (status === "cancelled") return "border-amber-500/40 bg-amber-500/10 text-amber-500";
  if (status === "running") return "border-sky-500/40 bg-sky-500/10 text-sky-500";
  return "";
}

function StatusBadge({ status }: { status: UiCheckRunStatus }) {
  const tone = statusTone(status);
  return tone ? (
    <Badge className={tone}>{STATUS_LABEL[status]}</Badge>
  ) : (
    <Badge variant="secondary">{STATUS_LABEL[status]}</Badge>
  );
}

function SeverityBadge({ severity }: { severity: UiCheckFinding["severity"] }) {
  if (severity === "high") return <Badge variant="destructive">Hoch</Badge>;
  if (severity === "medium")
    return <Badge className="border-amber-500/40 bg-amber-500/10 text-amber-500">Mittel</Badge>;
  return <Badge variant="outline">Niedrig</Badge>;
}

function ArtifactButton({
  runId,
  kind,
  label,
}: {
  runId: string;
  kind: string;
  label: string;
}) {
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={() => window.open(uiCheckArtifactUrl(runId, kind), "_blank", "noopener,noreferrer")}
    >
      <ExternalLinkIcon className="size-3.5" />
      {label}
    </Button>
  );
}

export default function UiCheckApp() {
  const [runs, setRuns] = useState<UiCheckRunSummary[]>([]);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [detail, setDetail] = useState<UiCheckRunDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const [url, setUrl] = useState("https://kunden-website.de");
  const [mode, setMode] = useState<UiCheckMode>("auto");
  const [depth, setDepth] = useState<UiCheckDepth>("redesign");
  const [provider, setProvider] = useState<UiCheckAiProvider>("claude");
  const [model, setModel] = useState(PROVIDERS[0].models[0]);
  const [industry, setIndustry] = useState("");
  const [desktop, setDesktop] = useState(true);
  const [prompt, setPrompt] = useState("");

  const selectedProvider = PROVIDERS.find((p) => p.value === provider) ?? PROVIDERS[0];
  const activeSummary = runs.find((r) => r.run_id === activeRunId) ?? null;
  const current = detail ?? activeSummary;
  const activeIsRunning = current?.status === "queued" || current?.status === "running";

  const stats = useMemo(() => {
    const finished = runs.filter((r) => typeof r.score_total === "number");
    const avg =
      finished.length > 0
        ? Math.round(finished.reduce((sum, r) => sum + (r.score_total ?? 0), 0) / finished.length)
        : null;
    const best = finished.reduce<number | null>(
      (max, r) => (max === null ? r.score_total : Math.max(max, r.score_total ?? max)),
      null,
    );
    const deltas = runs.filter((r) => typeof r.redesign_score === "number").length;
    return { avg, best, deltas };
  }, [runs]);

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const res = await getUiCheckRuns(signal);
        setRuns(res.runs);
        const nextId = activeRunId ?? res.active_run_id ?? res.runs[0]?.run_id ?? null;
        setActiveRunId(nextId);
        if (nextId) {
          const d = await getUiCheckRun(nextId, signal);
          setDetail(d);
        } else {
          setDetail(null);
        }
        setLoadError(null);
      } catch (err) {
        if (signal?.aborted) return;
        setLoadError(err instanceof ApiError ? err.message : "UI-Check ist nicht erreichbar");
      }
    },
    [activeRunId],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    const tick = () => {
      refresh(ctrl.signal).catch(() => {
        /* refresh setzt den sichtbaren Fehler selbst. */
      });
    };
    tick();
    const interval = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      ctrl.abort();
      clearInterval(interval);
    };
  }, [refresh]);

  async function selectRun(runId: string) {
    setActiveRunId(runId);
    try {
      setDetail(await getUiCheckRun(runId));
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof ApiError ? err.message : "Lauf konnte nicht geladen werden");
    }
  }

  async function handleStart() {
    if (!url.trim() || busy) return;
    setBusy(true);
    try {
      const res = await startUiCheckRun({
        url: url.trim(),
        mode,
        depth,
        ai_provider: provider,
        ai_model: model,
        prompt: prompt.trim() || undefined,
        industry: industry.trim() || null,
        desktop,
      });
      setActiveRunId(res.run_id);
      toast.success("UI-Check-Lauf gestartet");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Start fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleCancel() {
    if (!activeRunId || busy) return;
    setBusy(true);
    try {
      setDetail(await cancelUiCheckRun(activeRunId));
      toast.success("Lauf abgebrochen");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Abbruch fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleRedesign() {
    if (!activeRunId || busy) return;
    setBusy(true);
    try {
      setDetail(await runUiCheckRedesign(activeRunId));
      toast.success("Redesign gestartet");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Redesign-Start fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  function handleProvider(next: UiCheckAiProvider) {
    setProvider(next);
    const first = PROVIDERS.find((p) => p.value === next)?.models[0];
    if (first) setModel(first);
  }

  return (
    <div className="min-h-full bg-background text-foreground">
      <header className="sticky top-0 z-10 border-b border-border bg-background/95 px-4 py-3 backdrop-blur">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex size-9 items-center justify-center rounded-lg border border-border bg-muted">
              <WandSparklesIcon className="size-4" />
            </div>
            <div>
              <h1 className="text-base font-semibold tracking-tight">UI-Check</h1>
              <p className="text-xs text-muted-foreground">
                Jupiter-MicroApp für Audit, Branding und Redesign-Artefakte
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {current && <StatusBadge status={current.status} />}
            <Button type="button" variant="outline" size="sm" onClick={() => refresh()} disabled={busy}>
              <RefreshCwIcon className="size-3.5" />
              Aktualisieren
            </Button>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="space-y-4 p-4">
        {loadError && (
          <div className="rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-sm text-amber-600 dark:text-amber-400">
            {loadError}
          </div>
        )}

        <Tabs defaultValue="dashboard" className="gap-4">
          <TabsList className="w-full justify-start overflow-x-auto" variant="line">
            <TabsTrigger value="dashboard">
              <LayoutDashboardIcon className="size-3.5" /> Dashboard
            </TabsTrigger>
            <TabsTrigger value="audit">
              <BarChart3Icon className="size-3.5" /> Audit-Report
            </TabsTrigger>
            <TabsTrigger value="branding">
              <PaletteIcon className="size-3.5" /> Branding
            </TabsTrigger>
            <TabsTrigger value="compare">
              <ImageIcon className="size-3.5" /> Vorher/Nachher
            </TabsTrigger>
            <TabsTrigger value="portfolio">
              <BlocksIcon className="size-3.5" /> Portfolio
            </TabsTrigger>
          </TabsList>

          <TabsContent value="dashboard">
            <DashboardTab
              url={url}
              setUrl={setUrl}
              mode={mode}
              setMode={setMode}
              depth={depth}
              setDepth={setDepth}
              provider={provider}
              handleProvider={handleProvider}
              selectedProvider={selectedProvider}
              model={model}
              setModel={setModel}
              industry={industry}
              setIndustry={setIndustry}
              desktop={desktop}
              setDesktop={setDesktop}
              prompt={prompt}
              setPrompt={setPrompt}
              busy={busy}
              activeIsRunning={activeIsRunning}
              onStart={handleStart}
              onCancel={handleCancel}
              stats={stats}
              runs={runs}
              activeRunId={activeRunId}
              onSelectRun={selectRun}
              detail={detail}
            />
          </TabsContent>

          <TabsContent value="audit">
            <AuditTab detail={detail} />
          </TabsContent>

          <TabsContent value="branding">
            <BrandingTab detail={detail} />
          </TabsContent>

          <TabsContent value="compare">
            <CompareTab detail={detail} busy={busy} onRedesign={handleRedesign} />
          </TabsContent>

          <TabsContent value="portfolio">
            <PortfolioTab detail={detail} runs={runs} />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

function DashboardTab({
  url,
  setUrl,
  mode,
  setMode,
  depth,
  setDepth,
  provider,
  handleProvider,
  selectedProvider,
  model,
  setModel,
  industry,
  setIndustry,
  desktop,
  setDesktop,
  prompt,
  setPrompt,
  busy,
  activeIsRunning,
  onStart,
  onCancel,
  stats,
  runs,
  activeRunId,
  onSelectRun,
  detail,
}: {
  url: string;
  setUrl: (value: string) => void;
  mode: UiCheckMode;
  setMode: (value: UiCheckMode) => void;
  depth: UiCheckDepth;
  setDepth: (value: UiCheckDepth) => void;
  provider: UiCheckAiProvider;
  handleProvider: (value: UiCheckAiProvider) => void;
  selectedProvider: (typeof PROVIDERS)[number];
  model: string;
  setModel: (value: string) => void;
  industry: string;
  setIndustry: (value: string) => void;
  desktop: boolean;
  setDesktop: (value: boolean) => void;
  prompt: string;
  setPrompt: (value: string) => void;
  busy: boolean;
  activeIsRunning: boolean;
  onStart: () => void;
  onCancel: () => void;
  stats: { avg: number | null; best: number | null; deltas: number };
  runs: UiCheckRunSummary[];
  activeRunId: string | null;
  onSelectRun: (runId: string) => void;
  detail: UiCheckRunDetail | null;
}) {
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Neuen Lauf starten</CardTitle>
            <CardDescription>Audit-only oder kompletter Redesign-Lauf mit Modellwahl.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 lg:grid-cols-[minmax(260px,1fr)_180px_190px]">
              <div className="space-y-1.5">
                <Label htmlFor="ui-url">URL</Label>
                <Input id="ui-url" value={url} onChange={(e) => setUrl(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label>Seitentyp</Label>
                <Select value={mode} onValueChange={(v) => v && setMode(v as UiCheckMode)}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="auto">Auto</SelectItem>
                    <SelectItem value="landing">Landing Page</SelectItem>
                    <SelectItem value="app">App/Tool</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label>Tiefe</Label>
                <Select value={depth} onValueChange={(v) => v && setDepth(v as UiCheckDepth)}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="redesign">Audit + Redesign</SelectItem>
                    <SelectItem value="audit">Nur Audit</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid gap-3 lg:grid-cols-3">
              {PROVIDERS.map((p) => (
                <button
                  key={p.value}
                  type="button"
                  onClick={() => handleProvider(p.value)}
                  className={`rounded-lg border p-3 text-left transition-colors ${
                    provider === p.value
                      ? "border-primary bg-primary/10"
                      : "border-border bg-background hover:bg-muted"
                  }`}
                >
                  <div className="text-sm font-semibold">{p.label}</div>
                  <div className="mt-1 text-xs leading-relaxed text-muted-foreground">{p.detail}</div>
                </button>
              ))}
            </div>

            <div className="grid gap-3 md:grid-cols-[220px_minmax(220px,1fr)_180px]">
              <div className="space-y-1.5">
                <Label>Anbieter</Label>
                <Input value={selectedProvider.label} readOnly />
              </div>
              <div className="space-y-1.5">
                <Label>Modell</Label>
                <Select value={model} onValueChange={(v) => v && setModel(v)}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {selectedProvider.models.map((m) => (
                      <SelectItem key={m} value={m}>
                        {m}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="ui-industry">Branche</Label>
                <Input
                  id="ui-industry"
                  placeholder="optional"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="ui-prompt">Spezielle Anweisungen</Label>
              <Textarea
                id="ui-prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="z. B. Fokus auf Terminbuchung, Marke beibehalten, Zielgruppe Hausbesitzer 45+."
              />
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-sm text-muted-foreground">
                <input
                  type="checkbox"
                  checked={desktop}
                  onChange={(e) => setDesktop(e.target.checked)}
                  className="size-4"
                />
                Desktop-Screenshot priorisieren
              </label>
              <div className="flex gap-2">
                {activeIsRunning && (
                  <Button type="button" variant="destructive" onClick={onCancel} disabled={busy}>
                    <SquareIcon className="size-3.5" />
                    Abbrechen
                  </Button>
                )}
                <Button type="button" onClick={onStart} disabled={busy || !url.trim()}>
                  <PlayIcon className="size-3.5" />
                  Lauf starten
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <ProgressPanel detail={detail} />
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Läufe" value={String(runs.length)} />
          <StatCard label="Ø Score" value={fmtScore(stats.avg)} />
          <StatCard label="Deltas" value={String(stats.deltas)} />
        </div>
        <RunHistory runs={runs} activeRunId={activeRunId} onSelectRun={onSelectRun} />
      </div>
    </div>
  );
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <Card size="sm">
      <CardContent>
        <div className="text-xs text-muted-foreground">{label}</div>
        <div className="mt-1 text-2xl font-semibold">{value}</div>
      </CardContent>
    </Card>
  );
}

function ProgressPanel({ detail }: { detail: UiCheckRunDetail | null }) {
  const progress = Math.max(0, Math.min(100, detail?.progress ?? 0));
  return (
    <Card>
      <CardHeader>
        <CardTitle>Fortschritt</CardTitle>
        <CardDescription>{detail?.status_message ?? detail?.phase ?? "Kein aktiver Lauf ausgewählt."}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="h-2 rounded-full bg-muted">
          <div className="h-full rounded-full bg-primary" style={{ width: `${progress}%` }} />
        </div>
        <div className="grid gap-2 md:grid-cols-6">
          {PHASES.map((phase, index) => {
            const isReached = progress >= (index / (PHASES.length - 1)) * 100 || detail?.phase === phase.toLowerCase();
            return (
              <div
                key={phase}
                className={`rounded-lg border px-2 py-2 text-xs ${
                  isReached ? "border-primary/40 bg-primary/10" : "border-border bg-background"
                }`}
              >
                {phase}
              </div>
            );
          })}
        </div>
      </CardContent>
    </Card>
  );
}

function RunHistory({
  runs,
  activeRunId,
  onSelectRun,
}: {
  runs: UiCheckRunSummary[];
  activeRunId: string | null;
  onSelectRun: (runId: string) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Lauf-Historie</CardTitle>
        <CardDescription>Aus runs.jsonl und Run-Artefakten.</CardDescription>
      </CardHeader>
      <CardContent>
        {runs.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            Noch keine UI-Check-Läufe vorhanden.
          </div>
        ) : (
          <div className="space-y-2">
            {runs.map((run) => (
              <button
                key={run.run_id}
                type="button"
                onClick={() => onSelectRun(run.run_id)}
                className={`w-full rounded-lg border p-3 text-left transition-colors ${
                  run.run_id === activeRunId ? "border-primary bg-primary/10" : "border-border hover:bg-muted"
                }`}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate text-sm font-medium">
                      {run.display_url ?? run.url_hash}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      {fmtDate(run.created_at)} · {providerLabel(run.ai_provider)} · {run.ai_model ?? "n/v"}
                    </div>
                  </div>
                  <StatusBadge status={run.status} />
                </div>
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                  <span>Score {fmtScore(run.score_total)}</span>
                  <span>Nachher {fmtScore(run.redesign_score)}</span>
                  <span>Rubrik {run.rubric_version ?? "n/v"}</span>
                </div>
              </button>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function AuditTab({ detail }: { detail: UiCheckRunDetail | null }) {
  return (
    <div className="grid gap-4 xl:grid-cols-[320px_minmax(0,1fr)]">
      <Card>
        <CardHeader>
          <CardTitle>Gesamtscore</CardTitle>
          <CardDescription>Rubrik {detail?.rubric_version ?? "n/v"}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mx-auto flex size-44 items-center justify-center rounded-full border-[12px] border-primary/30 bg-muted">
            <div className="text-center">
              <div className="text-4xl font-semibold">{fmtScore(detail?.score_total ?? null)}</div>
              <div className="text-xs text-muted-foreground">von 100</div>
            </div>
          </div>
          {detail?.run_id && (
            <div className="mt-4 flex flex-wrap gap-2">
              <ArtifactButton runId={detail.run_id} kind="report" label="Report" />
              <ArtifactButton runId={detail.run_id} kind="scores" label="Scores" />
            </div>
          )}
        </CardContent>
      </Card>

      <div className="space-y-4">
        <DimensionGrid dimensions={detail?.dimensions ?? []} />
        <FindingsList findings={detail?.findings ?? []} />
      </div>
    </div>
  );
}

function DimensionGrid({ dimensions }: { dimensions: UiCheckDimensionScore[] }) {
  const rows =
    dimensions.length > 0
      ? dimensions
      : [
          { key: "visual", label: "Visuell", source: "scores.json", score: null },
          { key: "ai", label: "KI-Generik", source: "scores.json", score: null },
          { key: "performance", label: "Performance", source: "lighthouse", score: null },
          { key: "accessibility", label: "Accessibility", source: "lighthouse", score: null },
          { key: "conversion", label: "Conversion", source: "report", score: null },
        ];
  return (
    <Card>
      <CardHeader>
        <CardTitle>Dimensionen</CardTitle>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
        {rows.map((d) => (
          <div key={d.key} className="rounded-lg border border-border p-3">
            <div className="text-sm font-medium">{d.label}</div>
            <div className="mt-2 text-2xl font-semibold">{fmtScore(d.score)}</div>
            <div className="mt-1 text-xs text-muted-foreground">{d.source}</div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

function FindingsList({ findings }: { findings: UiCheckFinding[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Befunde</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {findings.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            Keine Befunde im ausgewählten Lauf gefunden.
          </div>
        ) : (
          findings.map((f, i) => (
            <div key={`${f.title}-${i}`} className="rounded-lg border border-border p-3">
              <div className="flex flex-wrap items-center gap-2">
                <SeverityBadge severity={f.severity} />
                <div className="font-medium">{f.title}</div>
              </div>
              <p className="mt-2 text-sm text-muted-foreground">{f.description}</p>
              <div className="mt-2 text-xs text-muted-foreground">{f.location}</div>
            </div>
          ))
        )}
      </CardContent>
    </Card>
  );
}

function BrandingTab({ detail }: { detail: UiCheckRunDetail | null }) {
  const branding = detail?.branding ?? null;
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,0.8fr)_minmax(0,1.2fr)]">
      <Card>
        <CardHeader>
          <CardTitle>Scraped-Branding</CardTitle>
          <CardDescription>{branding?.domain ?? "Kein Branding-Artefakt ausgewählt."}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div>
            <div className="text-xs text-muted-foreground">Marke</div>
            <div className="text-lg font-semibold">{branding?.name ?? "n/v"}</div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Schriften</div>
            <div className="mt-1 flex flex-wrap gap-2">
              {(branding?.fonts?.length ? branding.fonts : ["n/v"]).map((font) => (
                <Badge key={font} variant="outline">{font}</Badge>
              ))}
            </div>
          </div>
          <div>
            <div className="text-xs text-muted-foreground">Tonalität</div>
            <p className="mt-1 text-sm">{branding?.voice ?? "Keine Tonalitätsnotiz vorhanden."}</p>
          </div>
          {detail?.run_id && <ArtifactButton runId={detail.run_id} kind="tokens" label="Tokens öffnen" />}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Farb-Tokens</CardTitle>
          <CardDescription>{branding?.token_count ? `${branding.token_count} Tokens erkannt` : "Defensive Anzeige bei fehlenden Tokens"}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {(branding?.colors?.length ? branding.colors : ["#0f172a", "#14b8a6", "#f8fafc", "#f59e0b"]).map((color) => (
              <div key={color} className="rounded-lg border border-border p-3">
                <div className="h-12 rounded-md border border-border" style={{ backgroundColor: color }} />
                <div className="mt-2 font-mono text-xs text-muted-foreground">{color}</div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function CompareTab({
  detail,
  busy,
  onRedesign,
}: {
  detail: UiCheckRunDetail | null;
  busy: boolean;
  onRedesign: () => void;
}) {
  const hasMockup = Boolean(detail?.artifacts?.mockup);
  const hasScreens = Boolean(detail?.artifacts?.screenshots?.length);
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
      <Card>
        <CardHeader>
          <CardTitle>Vorher/Nachher</CardTitle>
          <CardDescription>Original, Safe und Bold werden aktiv, sobald die Artefakte im Run liegen.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid min-h-72 place-items-center rounded-lg border border-dashed border-border bg-muted/40 p-6 text-center">
            <div>
              <ImageIcon className="mx-auto size-10 text-muted-foreground" />
              <div className="mt-3 text-sm font-medium">
                {hasMockup || hasScreens ? "Artefakte sind verfügbar" : "Noch keine Vergleichsartefakte"}
              </div>
              <p className="mt-1 max-w-md text-sm text-muted-foreground">
                Fehlende Redesign-, Screenshot- oder Mockup-Dateien werden bewusst nicht leer gerendert.
              </p>
              {detail?.run_id && (
                <div className="mt-4 flex justify-center gap-2">
                  {hasMockup && <ArtifactButton runId={detail.run_id} kind="mockup" label="Mockup" />}
                  {hasScreens && <ArtifactButton runId={detail.run_id} kind="screenshots" label="Screenshots" />}
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Redesign-Aktion</CardTitle>
          <CardDescription>Safe/Bold und Mockup für vorhandenen Audit-Lauf nachziehen.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="rounded-lg border border-border p-3 text-sm">
            <div className="flex items-center justify-between gap-2">
              <span>Originalscore</span>
              <strong>{fmtScore(detail?.score_total ?? null)}</strong>
            </div>
            <div className="mt-2 flex items-center justify-between gap-2">
              <span>Nachher-Score</span>
              <strong>{fmtScore(detail?.redesign_score ?? null)}</strong>
            </div>
          </div>
          <Button type="button" className="w-full" onClick={onRedesign} disabled={busy || !detail?.run_id}>
            <RotateCcwIcon className="size-3.5" />
            Redesign starten
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

function PortfolioTab({
  detail,
  runs,
}: {
  detail: UiCheckRunDetail | null;
  runs: UiCheckRunSummary[];
}) {
  const reusable = runs.filter((r) => typeof r.redesign_score === "number").length;
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <PortfolioCard
        icon={<BlocksIcon className="size-4" />}
        title="Komponenten-Kandidaten"
        value={String(reusable)}
        text="Kandidaten werden aus Redesign-Läufen sichtbar, sobald PROJ-11-Daten vorliegen."
      />
      <PortfolioCard
        icon={<PaletteIcon className="size-4" />}
        title="Branding-Profile"
        value={detail?.branding ? "1" : "0"}
        text="Das Profil bleibt lokal am Run-Ordner und wird später durch PROJ-12 erweitert."
      />
      <PortfolioCard
        icon={<ShieldAlertIcon className="size-4" />}
        title="Versionen"
        value={detail?.rubric_version ?? "n/v"}
        text="Rubrik-Versionen bleiben sichtbar; alte Scores werden nicht still vergleichbar gemacht."
      />
      {detail?.run_id && (
        <Card className="lg:col-span-3">
          <CardHeader>
            <CardTitle>Artefakte</CardTitle>
            <CardDescription>Direkte Links zu bekannten lokalen Run-Dateien.</CardDescription>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-2">
            <ArtifactButton runId={detail.run_id} kind="report" label="Report" />
            <ArtifactButton runId={detail.run_id} kind="scores" label="Scores" />
            <ArtifactButton runId={detail.run_id} kind="tokens" label="Tokens" />
            <ArtifactButton runId={detail.run_id} kind="mockup" label="Mockup" />
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function PortfolioCard({
  icon,
  title,
  value,
  text,
}: {
  icon: React.ReactNode;
  title: string;
  value: string;
  text: string;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {icon}
          {title}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-semibold">{value}</div>
        <p className="mt-2 text-sm text-muted-foreground">{text}</p>
      </CardContent>
    </Card>
  );
}
