"use client";

// „Neue Session"-Dialog (PROJ-3) + Smart Launcher (PROJ-9): nach Projektwahl liest
// das Backend die features/INDEX.md und schlägt nächstes Feature + abc-Phase + Skill
// + Modell vor. Der Vorschlag ist mit einem Klick übernehmbar; jedes Feld bleibt
// manuell überschreibbar. Projekte ohne INDEX.md fallen auf den Freitext-Modus zurück.

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError, createSession, getEngines, getLaunchSuggestion } from "@/lib/api";
import { ABC_PHASES, modelLabel, projectName } from "@/lib/status";
import type {
  AbcPhase,
  EngineRead,
  FeatureSuggestion,
  LaunchSuggestion,
  PermissionMode,
} from "@/lib/types";
import { useSessions } from "./sessions-provider";

function phaseLabel(phase: AbcPhase | null): string {
  return ABC_PHASES.find((p) => p.key === phase)?.label ?? "—";
}

// PROJ-18: Fallback-Engine, falls GET /engines (noch) nichts liefert — die
// eingebaute Claude-Engine ist immer wählbar (rückwärtskompatibel zu PROJ-1).
const CLAUDE_FALLBACK: EngineRead = {
  key: "claude",
  label: "Claude Max",
  kind: "engine",
  driver: "claude",
  available: true,
  unavailable_reason: null,
  models: ["haiku", "sonnet", "opus"],
  default_model: "sonnet",
  capabilities: ["usage", "resume", "multi_turn", "tools"],
  url: null,
  sandbox: null,
  target: null,
};

export function NewSessionDialog({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { refresh } = useSessions();
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const [project, setProject] = useState("");
  const [projectPath, setProjectPath] = useState("/home/dev/projects/");
  const [prompt, setPrompt] = useState("");
  const [role, setRole] = useState("");
  const [model, setModel] = useState<string>("sonnet");
  const [mode, setMode] = useState<PermissionMode>("default");
  // PROJ-18: Engine-Auswahl (Default „claude"); Liste + Verfügbarkeit aus GET /engines.
  const [engine, setEngine] = useState<string>("claude");
  const [engines, setEngines] = useState<EngineRead[]>([]);

  // PROJ-9: Vorschlag aus der INDEX.md.
  const [suggestion, setSuggestion] = useState<LaunchSuggestion | null>(null);
  const [sugLoading, setSugLoading] = useState(false);
  const [sugError, setSugError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // PROJ-8: Projekt-Label. Leer → Backend nutzt den Pfad-Basename; Placeholder
  // zeigt diesen Vorschlag live an, damit die Gantt-Zeile sprechend bleibt.
  const suggestedName = projectName(projectPath.trim()) || "jupiter";

  // PROJ-18: nur steuerbare Engines (kind=engine) sind im Selector wählbar;
  // iFrame/Launch leben im Werkzeuge-Panel. Ohne Backend-Antwort bleibt Claude.
  const engineOptions: EngineRead[] = engines.filter((e) => e.kind === "engine");
  const effectiveEngines = engineOptions.length > 0 ? engineOptions : [CLAUDE_FALLBACK];
  const selectedEngine =
    effectiveEngines.find((e) => e.key === engine) ?? effectiveEngines[0];
  const modelOptions =
    selectedEngine.models.length > 0 ? selectedEngine.models : ["haiku", "sonnet", "opus"];

  const valid =
    projectPath.trim().length > 0 && prompt.trim().length > 0 && selectedEngine.available;

  // Engine-Wechsel: Modell auf das Default-Modell des neuen Profils setzen.
  // Plain function (kein useCallback): `effectiveEngines` wird je Render neu
  // abgeleitet — der React Compiler übernimmt die Memoisierung.
  function onEngineChange(key: string) {
    setEngine(key);
    const e = effectiveEngines.find((x) => x.key === key);
    const next = e?.default_model ?? e?.models[0];
    if (next) setModel(next);
  }

  // Vorschlag nach Projektwahl laden (debounced), solange der Dialog offen ist.
  useEffect(() => {
    if (!open) return;
    const path = projectPath.trim();
    const ctrl = new AbortController();
    const timer = setTimeout(async () => {
      if (path.length === 0) {
        setSuggestion(null);
        setSugError(null);
        return;
      }
      setSugLoading(true);
      setSugError(null);
      try {
        const s = await getLaunchSuggestion(path, ctrl.signal);
        setSuggestion(s);
        setSelectedId(s.empfehlung?.id ?? null);
      } catch (err) {
        if (ctrl.signal.aborted) return;
        setSuggestion(null);
        setSugError(
          err instanceof ApiError ? err.message : "Vorschlag konnte nicht geladen werden",
        );
      } finally {
        if (!ctrl.signal.aborted) setSugLoading(false);
      }
    }, 300);
    return () => {
      clearTimeout(timer);
      ctrl.abort();
    };
  }, [open, projectPath]);

  // PROJ-18: konfigurierte Engines laden, sobald der Dialog öffnet. Nicht-blockierend
  // — schlägt es fehl, bleibt der Claude-Fallback wählbar.
  useEffect(() => {
    if (!open) return;
    const ctrl = new AbortController();
    getEngines(ctrl.signal)
      .then((o) => setEngines(o.engines))
      .catch(() => {
        /* Backend nicht erreichbar → nur Claude (Fallback) */
      });
    return () => ctrl.abort();
  }, [open]);

  // Optionen = Empfehlung + Alternativen (für die Auswahlliste).
  const options: FeatureSuggestion[] = suggestion?.empfehlung
    ? [suggestion.empfehlung, ...suggestion.alternativen]
    : [];
  const selected = options.find((o) => o.id === selectedId) ?? suggestion?.empfehlung ?? null;

  const applyFeature = useCallback((opt: FeatureSuggestion) => {
    setSelectedId(opt.id);
    setPrompt(opt.initial_prompt);
    if (opt.modell) setModel(opt.modell);
  }, []);

  // Sonderfall „alle deployed": kein Feature, aber ein /abc-requirements-Default.
  const applyDefault = useCallback(() => {
    if (suggestion?.initial_prompt) setPrompt(suggestion.initial_prompt);
    if (suggestion?.modell) setModel(suggestion.modell);
  }, [suggestion]);

  function resetForm() {
    setPrompt("");
    setProject("");
    setRole("");
    setSuggestion(null);
    setSelectedId(null);
    setSugError(null);
    setEngine("claude");
    setModel("sonnet");
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!valid || submitting) return;
    setSubmitting(true);
    try {
      const session = await createSession({
        project_path: projectPath.trim(),
        initial_prompt: prompt.trim(),
        model,
        permission_mode: mode,
        role: role.trim() || undefined,
        project_name: project.trim() || undefined,
        engine,
      });
      toast.success("Session gestartet");
      setOpen(false);
      resetForm();
      refresh();
      router.push(`/sessions/${session.session_id}`);
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "Session konnte nicht gestartet werden";
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {/* Base UI: eigenes Element via render (kein asChild wie bei Radix). */}
      <DialogTrigger render={children as React.ReactElement} />
      <DialogContent className="sm:max-w-lg">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>Neue Session</DialogTitle>
            <DialogDescription>
              Startet eine Session im gewählten Projekt — Standard ist Claude Max.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-4 py-4">
            <div className="grid gap-2">
              <Label htmlFor="project_name">Projekt</Label>
              <Input
                id="project_name"
                value={project}
                onChange={(e) => setProject(e.target.value)}
                placeholder={suggestedName}
                autoComplete="off"
                spellCheck={false}
              />
            </div>

            <div className="grid gap-2">
              <Label htmlFor="project_path">Projekt-Pfad</Label>
              <Input
                id="project_path"
                value={projectPath}
                onChange={(e) => setProjectPath(e.target.value)}
                placeholder="/home/dev/projects/jupiter"
                autoComplete="off"
                spellCheck={false}
              />
            </div>

            {/* PROJ-9: Smart-Launcher-Vorschlag */}
            <SuggestionCard
              loading={sugLoading}
              error={sugError}
              suggestion={suggestion}
              options={options}
              selectedId={selectedId}
              onApplyFeature={applyFeature}
              onApplyDefault={applyDefault}
            />

            <div className="grid gap-2">
              <Label htmlFor="initial_prompt">Initial-Prompt</Label>
              <Textarea
                id="initial_prompt"
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="Was soll die Session tun?"
                rows={4}
              />
              {selected?.skill && prompt.trim() === selected.initial_prompt && (
                <p className="text-xs text-muted-foreground">
                  Skill <span className="font-mono">{selected.skill}</span> wird über den Prompt
                  übergeben — frei editierbar.
                </p>
              )}
            </div>

            <div className="grid gap-2">
              <Label htmlFor="role">Rolle (optional)</Label>
              <Input
                id="role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="z. B. backend-dev"
                autoComplete="off"
                spellCheck={false}
              />
            </div>

            {/* PROJ-18: Engine-Auswahl (Default „Claude Max"). Nicht verfügbare Engines
                sind ausgegraut + tragen ihren deutschen Setup-Hinweis. */}
            <div className="grid gap-2">
              <Label htmlFor="engine">Engine</Label>
              <Select value={engine} onValueChange={(v) => v && onEngineChange(v)}>
                <SelectTrigger id="engine">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {effectiveEngines.map((e) => (
                    <SelectItem key={e.key} value={e.key} disabled={!e.available}>
                      {e.label}
                      {!e.available && " — nicht verfügbar"}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {!selectedEngine.available && selectedEngine.unavailable_reason && (
                <p className="text-xs text-amber-500">{selectedEngine.unavailable_reason}</p>
              )}
              {selectedEngine.available && selectedEngine.key !== "claude" && (
                <p className="text-xs text-muted-foreground">
                  {`Fremd-Engine: Decision Cards / Phasen-Gate greifen ggf. nicht; ohne Usage-Daten zeigen Token/Kosten „n/v“.`}
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="model">Modell</Label>
                <Select value={model} onValueChange={(v) => v && setModel(v)}>
                  <SelectTrigger id="model">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {modelOptions.map((m) => (
                      <SelectItem key={m} value={m}>
                        {modelLabel(m)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="mode">Berechtigung</Label>
                <Select value={mode} onValueChange={(v) => setMode(v as PermissionMode)}>
                  <SelectTrigger id="mode">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="default">Standard</SelectItem>
                    <SelectItem value="acceptEdits">Edits automatisch</SelectItem>
                    <SelectItem value="bypassPermissions">Ohne Rückfragen (Bypass)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {mode === "bypassPermissions" && (
              <p className="text-xs text-amber-500">
                ⚠️ Vollautonom: Diese Session führt alles ohne Freigabe aus — die
                Decision Cards greifen nicht.
              </p>
            )}
          </div>

          <DialogFooter>
            <Button type="submit" disabled={!valid || submitting}>
              {submitting ? "Startet…" : "Session starten"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// --- Vorschlags-Karte (PROJ-9) ---------------------------------------------

function SuggestionCard({
  loading,
  error,
  suggestion,
  options,
  selectedId,
  onApplyFeature,
  onApplyDefault,
}: {
  loading: boolean;
  error: string | null;
  suggestion: LaunchSuggestion | null;
  options: FeatureSuggestion[];
  selectedId: string | null;
  onApplyFeature: (opt: FeatureSuggestion) => void;
  onApplyDefault: () => void;
}) {
  if (loading) {
    return (
      <div className="rounded-md border border-border bg-muted/30 p-3">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="mt-2 h-3 w-56" />
        <Skeleton className="mt-3 h-8 w-32" />
      </div>
    );
  }

  // Fehler ist nicht-blockierend: der Freitext-Modus bleibt nutzbar.
  if (error) {
    return (
      <p className="rounded-md border border-border bg-muted/30 p-2 text-xs text-muted-foreground">
        Vorschlag nicht verfügbar ({error}) — du kannst frei einen Prompt eingeben.
      </p>
    );
  }

  if (!suggestion) return null;

  // Kein abc-Workflow erkannt → Hinweis, Freitext-Fallback.
  if (!suggestion.abc_erkannt) {
    return (
      <p className="rounded-md border border-border bg-muted/30 p-2 text-xs text-muted-foreground">
        {suggestion.hinweis ?? "Kein abc-Workflow erkannt — Freitext-Modus."}
      </p>
    );
  }

  // Alle Features deployed → /abc-requirements vorschlagen (kein konkretes Feature).
  if (!suggestion.empfehlung) {
    return (
      <div className="rounded-md border border-border bg-muted/30 p-3">
        <p className="text-sm">{suggestion.hinweis}</p>
        <Button type="button" size="sm" variant="secondary" className="mt-2" onClick={onApplyDefault}>
          /abc-requirements übernehmen
        </Button>
      </div>
    );
  }

  const selected = options.find((o) => o.id === selectedId) ?? suggestion.empfehlung;

  return (
    <div className="rounded-md border border-primary/40 bg-primary/5 p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Vorschlag aus dem Workflow
        </span>
        <Badge variant="outline">{modelLabel(selected.modell ?? "")}</Badge>
      </div>

      <p className="mt-1 text-sm font-medium">
        {selected.id} — {selected.title}
      </p>
      <p className="text-xs text-muted-foreground">
        Status {selected.status || "—"} → nächste Phase{" "}
        <span className="font-medium text-foreground">{phaseLabel(selected.phase)}</span>
        {selected.skill && (
          <>
            {" · "}
            <span className="font-mono">{selected.skill}</span>
          </>
        )}
      </p>

      <Button type="button" size="sm" className="mt-2" onClick={() => onApplyFeature(selected)}>
        Vorschlag starten
      </Button>

      {options.length > 1 && (
        <div className="mt-3">
          <span className="text-xs text-muted-foreground">Weitere offene Features:</span>
          <div className="mt-1 flex flex-wrap gap-1">
            {options.map((opt) => (
              <button
                key={opt.id}
                type="button"
                onClick={() => onApplyFeature(opt)}
                className={`rounded border px-2 py-0.5 text-xs transition-colors ${
                  opt.id === selected.id
                    ? "border-primary bg-primary/10 text-foreground"
                    : "border-border text-muted-foreground hover:bg-muted"
                }`}
              >
                {opt.id}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
