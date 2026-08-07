"use client";

// PROJ-14: Native Micro-App "UI-Check".
// URL + Modus + KI-Modell -> lokaler headless Runner -> Run-Artefakte.
// Das Frontend pollt nur die Jupiter-internen Endpunkte; die Pipeline bleibt im Backend.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  BarChart3Icon,
  BlocksIcon,
  EyeIcon,
  EyeOffIcon,
  GlobeIcon,
  LayoutDashboardIcon,
  LayoutTemplateIcon,
  PaletteIcon,
  PlayIcon,
  PuzzleIcon,
  RefreshCwIcon,
  SquareIcon,
  Trash2Icon,
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
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
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
  deleteUiCheckRun,
  getUiCheckRun,
  getUiCheckRuns,
  runUiCheckRedesign,
  startUiCheckAssemble,
  startUiCheckImages,
  startUiCheckMockupExport,
  startUiCheckRecycle,
  startUiCheckRun,
} from "@/lib/api";
import type {
  UiCheckAiProvider,
  UiCheckAssembleOutcome,
  UiCheckAssembleRequest,
  UiCheckDepth,
  UiCheckDimensionScore,
  UiCheckFinding,
  UiCheckMode,
  UiCheckRunDetail,
  UiCheckRunSummary,
} from "@/lib/types";
import {
  ArtifactButton,
  fmtDate,
  fmtScore,
  SeverityBadge,
  STATUS_LABEL,
  StatusBadge,
} from "./shared";
import {
  computePrerequisites,
  hasImagesFilled,
  hasMockupExisting,
  hasRedesignArtifacts,
  PIPELINE_MODES,
  type PipelineModeId,
} from "./pipeline-modes";
import {
  CommandPlanPreview,
  PipelineModeSelector,
  PrerequisiteChecklist,
} from "./pipeline-panel";
import { MockupTab } from "./mockup-tab";
import { PortfolioTab } from "./portfolio-tab";
import { AssemblerTab } from "./assembler-tab";

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

const PHASES = [
  { label: "Capture", phase: "capture" },
  { label: "Lighthouse", phase: "lighthouse" },
  { label: "Branding", phase: "branding" },
  { label: "Scoring", phase: "scoring" },
  { label: "WeDesign", phase: "redesign" },
  { label: "Bildergenerierung", phase: "images" },
  { label: "Mockup", phase: "mockup" },
];

function providerLabel(value: string | null): string {
  return PROVIDERS.find((p) => p.value === value)?.label ?? value ?? "n/v";
}

export default function UiCheckApp() {
  const [runs, setRuns] = useState<UiCheckRunSummary[]>([]);
  const [activeTab, setActiveTab] = useState("dashboard");
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
  const [screenshot, setScreenshot] = useState<File | null>(null);
  const [prompt, setPrompt] = useState("");
  const [pipelineMode, setPipelineMode] = useState<PipelineModeId>("complete");
  const [mockupConflict, setMockupConflict] = useState(false);

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
        full_pipeline: pipelineMode === "complete",
      }, screenshot);
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

  async function handleImages() {
    if (!activeRunId || busy) return;
    setBusy(true);
    try {
      setDetail(await startUiCheckImages(activeRunId));
      toast.success("Bildbefüllung gestartet");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Bildbefüllung fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleMockupExport(force = false) {
    if (!activeRunId || busy) return;
    setBusy(true);
    try {
      setDetail(await startUiCheckMockupExport(activeRunId, force));
      setMockupConflict(false);
      toast.success(force ? "Mockup-Export erzwungen" : "Mockup-Export gestartet");
      await refresh();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409 && err.message.includes("mockup.html")) {
        setMockupConflict(true);
        setActiveTab("mockup");
        toast.error("mockup.html existiert bereits — Details im Mockup-Tab.");
      } else {
        toast.error(err instanceof ApiError ? err.message : "Mockup-Export fehlgeschlagen");
      }
    } finally {
      setBusy(false);
    }
  }

  async function handleRecycle() {
    if (!activeRunId || busy) return;
    setBusy(true);
    try {
      setDetail(await startUiCheckRecycle(activeRunId));
      toast.success("Registry-Recycling gestartet");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Registry-Recycling fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleAssemble(payload: UiCheckAssembleRequest): Promise<UiCheckAssembleOutcome> {
    const outcome = await startUiCheckAssemble(payload);
    if (outcome.ok) {
      setActiveRunId(outcome.response.run_id);
      try {
        setDetail(await getUiCheckRun(outcome.response.run_id));
      } catch {
        /* Detailabruf schlägt in seltenen Fällen fehl; Historie zeigt den Lauf trotzdem. */
      }
      setActiveTab("mockup");
      toast.success("Portfolio-Assembler gestartet");
      await refresh();
    }
    return outcome;
  }

  async function handleDeleteRun(runId: string) {
    if (busy) return;
    setBusy(true);
    try {
      await deleteUiCheckRun(runId);
      toast.success("Lauf gelöscht");
      if (activeRunId === runId) {
        setActiveRunId(null);
        setDetail(null);
      }
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Löschen fehlgeschlagen");
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

        <Tabs value={activeTab} onValueChange={setActiveTab} className="gap-4">
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
            <TabsTrigger value="mockup">
              <LayoutTemplateIcon className="size-3.5" /> Mockup
            </TabsTrigger>
            <TabsTrigger value="portfolio">
              <BlocksIcon className="size-3.5" /> Portfolio
            </TabsTrigger>
            <TabsTrigger value="assembler">
              <PuzzleIcon className="size-3.5" /> Assembler
            </TabsTrigger>
          </TabsList>

          {/* Website-Indikator: außerhalb des Dashboards zeigt sonst nichts an,
              zu welchem Lauf die Tab-Inhalte gehören. */}
          {activeTab !== "dashboard" && (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
              <GlobeIcon className="size-4 shrink-0 text-muted-foreground" />
              {current ? (
                <>
                  <span
                    className="max-w-[24rem] truncate font-medium"
                    title={current.display_url ?? undefined}
                  >
                    {current.display_url ?? "Unbekannte URL"}
                  </span>
                  {current.run_type === "assemble" && (
                    <Badge variant="outline">Assembler-Lauf</Badge>
                  )}
                  <StatusBadge status={current.status} />
                  {typeof current.score_total === "number" && (
                    <span className="text-muted-foreground">
                      Score {fmtScore(current.score_total)}
                    </span>
                  )}
                  {detail?.status_message && (
                    <span className="max-w-[28rem] truncate text-xs text-muted-foreground">
                      · {detail.status_message}
                    </span>
                  )}
                </>
              ) : (
                <span className="text-muted-foreground">
                  Kein Lauf ausgewählt — im Dashboard einen Lauf aus der Historie wählen.
                </span>
              )}
            </div>
          )}

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
              screenshot={screenshot}
              setScreenshot={setScreenshot}
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
              onDeleteRun={handleDeleteRun}
              detail={detail}
              pipelineMode={pipelineMode}
              setPipelineMode={setPipelineMode}
              onRedesign={handleRedesign}
              onImages={handleImages}
              onMockupExport={() => handleMockupExport(false)}
              onRecycle={handleRecycle}
              onJumpToAssembler={() => setActiveTab("assembler")}
            />
          </TabsContent>

          <TabsContent value="audit">
            <AuditTab detail={detail} />
          </TabsContent>

          <TabsContent value="branding">
            <BrandingTab detail={detail} />
          </TabsContent>

          <TabsContent value="mockup">
            <MockupTab
              detail={detail}
              busy={busy}
              onRedesign={handleRedesign}
              onImages={handleImages}
              onExport={() => handleMockupExport(false)}
              onForceExport={() => handleMockupExport(true)}
              conflictOpen={mockupConflict}
              onDismissConflict={() => setMockupConflict(false)}
            />
          </TabsContent>

          <TabsContent value="portfolio">
            <PortfolioTab />
          </TabsContent>

          <TabsContent value="assembler">
            <AssemblerTab onAssemble={handleAssemble} />
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
  screenshot,
  setScreenshot,
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
  onDeleteRun,
  detail,
  pipelineMode,
  setPipelineMode,
  onRedesign,
  onImages,
  onMockupExport,
  onRecycle,
  onJumpToAssembler,
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
  screenshot: File | null;
  setScreenshot: (file: File | null) => void;
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
  onDeleteRun: (runId: string) => void;
  detail: UiCheckRunDetail | null;
  pipelineMode: PipelineModeId;
  setPipelineMode: (value: PipelineModeId) => void;
  onRedesign: () => void;
  onImages: () => void;
  onMockupExport: () => void;
  onRecycle: () => void;
  onJumpToAssembler: () => void;
}) {
  const activeMode = PIPELINE_MODES.find((m) => m.id === pipelineMode) ?? PIPELINE_MODES[0];
  const prerequisites = computePrerequisites(pipelineMode, detail, url);
  const prerequisitesOk = prerequisites.every((p) => p.satisfied);

  useEffect(() => {
    if (pipelineMode === "audit_only" && depth !== "audit") setDepth("audit");
    if (pipelineMode === "complete" && depth !== "redesign") setDepth("redesign");
  }, [pipelineMode, depth, setDepth]);

  const stepAction: Record<string, { label: string; run: () => void }> = {
    redesign: { label: "Redesign starten", run: onRedesign },
    images: { label: "Bilder füllen", run: onImages },
    mockup_export: { label: "Mockup exportieren", run: onMockupExport },
    recycle: { label: "Recycling starten", run: onRecycle },
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
      <div className="space-y-4">
        {activeMode.jumpsToTab === "assembler" ? (
          <Card>
            <CardHeader>
              <CardTitle>Portfolio-Assembler</CardTitle>
              <CardDescription>
                Der Assembler ist ein eigener Arbeitsbereich mit Branding-, Sektions- und
                Registry-Auswahl.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Button type="button" onClick={onJumpToAssembler}>
                <PuzzleIcon className="size-3.5" />
                Zum Assembler-Tab wechseln
              </Button>
            </CardContent>
          </Card>
        ) : activeMode.requiresRun ? (
          <Card>
            <CardHeader>
              <CardTitle>Ziel-Lauf</CardTitle>
              <CardDescription>
                Wirkt auf den aktuell in der Historie ausgewählten Lauf.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="rounded-lg border border-border p-3 text-sm">
                {detail?.run_id ? (
                  <>
                    <div className="truncate font-medium">
                      {detail.display_url ?? detail.url_hash}
                    </div>
                    <div className="mt-1 text-xs text-muted-foreground">
                      Score {fmtScore(detail.score_total)} · Nachher {fmtScore(detail.redesign_score)}
                    </div>
                  </>
                ) : (
                  <span className="text-muted-foreground">
                    Kein Lauf ausgewählt — rechts einen Lauf aus der Historie wählen.
                  </span>
                )}
              </div>
              <Button
                type="button"
                className="w-full"
                onClick={stepAction[pipelineMode]?.run}
                disabled={busy || !prerequisitesOk}
              >
                <PlayIcon className="size-3.5" />
                {stepAction[pipelineMode]?.label ?? "Starten"}
              </Button>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>Neuen Lauf starten</CardTitle>
              <CardDescription>
                {pipelineMode === "audit_only"
                  ? "Nur Stufe-1-Audit ohne Redesign."
                  : "Kompletter Lauf: Audit, Redesign, Bilder, Mockup-Export."}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 lg:grid-cols-[minmax(260px,1fr)_180px]">
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
              </div>

              <div className="grid gap-3 md:grid-cols-[180px_minmax(220px,1fr)_180px]">
                <div className="space-y-1.5">
                  <Label>Anbieter</Label>
                  <Select
                    value={provider}
                    onValueChange={(v) => v && handleProvider(v as UiCheckAiProvider)}
                  >
                    <SelectTrigger className="w-full">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {PROVIDERS.map((p) => (
                        <SelectItem key={p.value} value={p.value}>
                          {p.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
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

              <div className="space-y-1.5">
                <Label htmlFor="ui-screenshot">Screenshot (optional, PNG)</Label>
                <Input
                  id="ui-screenshot"
                  type="file"
                  accept="image/png"
                  onChange={(event) => setScreenshot(event.target.files?.[0] ?? null)}
                />
                {screenshot && (
                  <p className="text-xs text-muted-foreground">
                    {screenshot.name} wird statt des automatischen Snapshots verwendet.
                  </p>
                )}
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
                  <Button type="button" onClick={onStart} disabled={busy || !prerequisitesOk}>
                    <PlayIcon className="size-3.5" />
                    Lauf starten
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <ProgressPanel detail={detail} />

        <Card>
          <CardHeader>
            <CardTitle>Pipeline-Modus</CardTitle>
            <CardDescription>
              Übersetzt die Skill-Pipeline aus docs/pipeline.md in auswählbare Modi —
              kein Slash-Command-Wissen nötig.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <PipelineModeSelector
              modes={PIPELINE_MODES}
              value={pipelineMode}
              onChange={setPipelineMode}
            />
          </CardContent>
        </Card>

        <div className="grid gap-4 md:grid-cols-2">
          <CommandPlanPreview mode={activeMode} />
          <PrerequisiteChecklist items={prerequisites} />
        </div>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-3 gap-3">
          <StatCard label="Läufe" value={String(runs.length)} />
          <StatCard label="Ø Score" value={fmtScore(stats.avg)} />
          <StatCard label="Deltas" value={String(stats.deltas)} />
        </div>
        <RunHistory
          runs={runs}
          activeRunId={activeRunId}
          onSelectRun={onSelectRun}
          onDeleteRun={onDeleteRun}
        />
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
  const completedPhases = useMemo(() => {
    const completed = new Set<string>();
    const progressIndex = Math.floor((progress / 100) * (PHASES.length - 1));

    PHASES.forEach((phase, index) => {
      if (progress > 0 && index <= progressIndex) completed.add(phase.phase);
      if (detail?.phase === phase.phase) completed.add(phase.phase);
    });

    if (typeof detail?.score_total === "number") {
      ["capture", "lighthouse", "branding", "scoring"].forEach((phase) => completed.add(phase));
    }
    if (hasRedesignArtifacts(detail)) completed.add("redesign");
    if (hasImagesFilled(detail)) completed.add("images");
    if (hasMockupExisting(detail)) completed.add("mockup");

    return completed;
  }, [detail, progress]);

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
        <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-4 xl:grid-cols-7">
          {PHASES.map((phase) => {
            const isReached = completedPhases.has(phase.phase);
            return (
              <div
                key={phase.phase}
                className={`rounded-lg border px-2 py-2 text-xs ${
                  isReached ? "border-primary/40 bg-primary/10" : "border-border bg-background"
                }`}
              >
                {phase.label}
              </div>
            );
          })}
        </div>
        {detail?.chain_error && (
          <div className="rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-400">
            Pipeline-Kette abgebrochen bei Schritt „{detail.chain_error.step}&quot; (Exit-Code{" "}
            {detail.chain_error.returncode}).
          </div>
        )}
      </CardContent>
    </Card>
  );
}

const HIDDEN_RUNS_KEY = "ui-check:hidden-runs";

function loadHiddenRuns(): Set<string> {
  if (typeof window === "undefined") return new Set();
  try {
    const raw = window.localStorage.getItem(HIDDEN_RUNS_KEY);
    if (!raw) return new Set();
    const arr = JSON.parse(raw) as string[];
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function storeHiddenRuns(set: Set<string>): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(HIDDEN_RUNS_KEY, JSON.stringify([...set]));
  } catch {
    /* ignore quota / privacy errors */
  }
}

function RunHistory({
  runs,
  activeRunId,
  onSelectRun,
  onDeleteRun,
}: {
  runs: UiCheckRunSummary[];
  activeRunId: string | null;
  onSelectRun: (runId: string) => void;
  onDeleteRun: (runId: string) => void;
}) {
  const [hidden, setHidden] = useState<Set<string>>(() => loadHiddenRuns());
  const [showHidden, setShowHidden] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState<UiCheckRunSummary | null>(null);

  useEffect(() => {
    storeHiddenRuns(hidden);
  }, [hidden]);

  function toggleHidden(runId: string) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(runId)) next.delete(runId);
      else next.add(runId);
      return next;
    });
  }

  const visibleRuns = useMemo(
    () => (showHidden ? runs : runs.filter((r) => !hidden.has(r.run_id))),
    [runs, hidden, showHidden],
  );
  const hiddenCount = runs.filter((r) => hidden.has(r.run_id)).length;

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-2">
          <div>
            <CardTitle>Lauf-Historie</CardTitle>
            <CardDescription>Aus runs.jsonl und Run-Artefakten.</CardDescription>
          </div>
          {hiddenCount > 0 && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={() => setShowHidden((v) => !v)}
              title={showHidden ? "Ausgeblendete Läufe verbergen" : "Ausgeblendete Läufe anzeigen"}
            >
              {showHidden ? (
                <EyeOffIcon className="size-3.5" />
              ) : (
                <EyeIcon className="size-3.5" />
              )}
              {showHidden ? "Verbergen" : `Ausgeblendete (${hiddenCount})`}
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        {runs.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            Noch keine UI-Check-Läufe vorhanden.
          </div>
        ) : visibleRuns.length === 0 ? (
          <div className="rounded-lg border border-dashed border-border p-4 text-sm text-muted-foreground">
            Alle Läufe sind ausgeblendet.{' '}
            <button
              type="button"
              className="text-foreground underline underline-offset-2"
              onClick={() => setShowHidden(true)}
            >
              Eingeblendete anzeigen
            </button>
          </div>
        ) : (
          <div className="max-h-[28rem] space-y-2 overflow-y-auto pr-1">
            {visibleRuns.map((run) => {
              const isHidden = hidden.has(run.run_id);
              const isRunning = run.status === "queued" || run.status === "running";
              return (
                <div
                  key={run.run_id}
                  className={`w-full rounded-lg border p-3 transition-colors ${
                    run.run_id === activeRunId
                      ? "border-primary bg-primary/10"
                      : "border-border hover:bg-muted"
                  } ${isHidden ? "opacity-60" : ""}`}
                >
                  <button
                    type="button"
                    onClick={() => onSelectRun(run.run_id)}
                    className="block w-full text-left"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2">
                          <div className="truncate text-sm font-medium">
                            {run.display_url ?? run.url_hash}
                          </div>
                          {run.run_type === "assemble" && (
                            <Badge variant="outline" className="shrink-0">
                              Assembler
                            </Badge>
                          )}
                        </div>
                        <div className="mt-1 text-xs text-muted-foreground">
                          {fmtDate(run.created_at)} · {providerLabel(run.ai_provider)} · {run.ai_model ?? "n/v"}
                        </div>
                      </div>
                      <StatusBadge status={run.status} />
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted-foreground">
                      {run.run_type === "assemble" ? (
                        <span>Mockup-Score {fmtScore(run.redesign_score)}</span>
                      ) : (
                        <>
                          <span>Score {fmtScore(run.score_total)}</span>
                          <span>Nachher {fmtScore(run.redesign_score)}</span>
                        </>
                      )}
                      <span>Rubrik {run.rubric_version ?? "n/v"}</span>
                    </div>
                  </button>
                  <div className="mt-2 flex justify-end gap-1 border-t border-border/60 pt-2">
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      title={isHidden ? "Lauf wieder einblenden" : "Lauf ausblenden"}
                      onClick={() => toggleHidden(run.run_id)}
                    >
                      {isHidden ? (
                        <EyeOffIcon className="size-3.5" />
                      ) : (
                        <EyeIcon className="size-3.5" />
                      )}
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="icon-sm"
                      className="text-destructive hover:bg-destructive/10 hover:text-destructive"
                      title="Lauf endgültig löschen"
                      disabled={isRunning}
                      onClick={() => setConfirmDelete(run)}
                    >
                      <Trash2Icon className="size-3.5" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>

      <Dialog open={confirmDelete !== null} onOpenChange={(open) => !open && setConfirmDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Lauf löschen</DialogTitle>
            <DialogDescription>
              Der Lauf wird unwiderruflich gelöscht — inklusive aller Artefakte (Audit,
              Branding, Redesign, Mockup) auf dem Server. Diese Aktion kann nicht rückgängig
              gemacht werden.
            </DialogDescription>
          </DialogHeader>
          {confirmDelete && (
            <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm">
              <div className="truncate font-medium">
                {confirmDelete.display_url ?? confirmDelete.url_hash}
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                {fmtDate(confirmDelete.created_at)} · Status: {STATUS_LABEL[confirmDelete.status]}
              </div>
            </div>
          )}
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setConfirmDelete(null)}>
              Abbrechen
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={async () => {
                const target = confirmDelete;
                setConfirmDelete(null);
                if (target) {
                  setHidden((prev) => {
                    const next = new Set(prev);
                    next.delete(target.run_id);
                    return next;
                  });
                  await onDeleteRun(target.run_id);
                }
              }}
            >
              <Trash2Icon className="size-3.5" />
              Endgültig löschen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
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
