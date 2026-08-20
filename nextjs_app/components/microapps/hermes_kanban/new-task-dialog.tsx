"use client";

// PROJ-82/84: Neuer Hermes-Kanban-Task — vereinfachtes Formular.
// Grundbereich: Titel, große Beschreibung + Push-to-Talk, Assignee,
// Workspace-Pfad (fest `dir:`, startet unter /home/dev/projects/), Priorität,
// Skills, Initial-Status. Parent-Tasks liegen unter „Erweitert" neben den
// seltenen Optionen. PROJ-84 entfernt Projekt-/Workspace-Modus-/Branch-Felder;
// der Request übermittelt kein `project`, kein `workspace_mode` und kein
// `branch` mehr (serverseitig per Schema auf `dir:` erzwungen).

import { useMemo, useState } from "react";
import { ChevronDownIcon, ChevronRightIcon } from "lucide-react";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  createHermesKanbanTask,
  lookupHermesKanbanFeature,
} from "@/lib/api";
import { PushToTalkButton } from "@/components/cockpit/push-to-talk-button";
import type { HermesKanbanCreateRequest, HermesKanbanTask } from "@/lib/types";

// --- Kurzsyntax: kanonische ABC-Phasen + deutsche Aliase (Vorbild
//     backend/app/engine/abc_phases.py). EIN Ort für die Vorbefüll-Zuordnung. --

export interface QuickAddPrefill {
  phase: string;
  projNumber: number;
  title: string;
  body: string;
}

const PHASES: Record<string, { label: string; skill: string }> = {
  brainstorm: { label: "Brainstorm", skill: "abc-brainstorm" },
  requirements: { label: "Requirements", skill: "abc-requirements" },
  architecture: { label: "Architektur", skill: "abc-architecture" },
  "review-architecture": { label: "Architektur-Review", skill: "abc-review-architecture" },
  frontend: { label: "Frontend", skill: "abc-frontend" },
  backend: { label: "Backend", skill: "abc-backend" },
  qa: { label: "QA", skill: "abc-qa" },
  deploy: { label: "Deploy", skill: "abc-deploy" },
  document: { label: "Doku", skill: "abc-document" },
};

const PHASE_ALIASES: Record<string, string> = {
  anforderungen: "requirements",
  architektur: "architecture",
};

/** `<phase> <projektnummer>`-Muster erkennen (case-insensitiv) → Prefill-Payload. */
export function parseQuickAdd(input: string): Omit<QuickAddPrefill, "title" | "body"> | null {
  const m = /^\s*([a-zäöü-]+)\s+(\d{1,4})\s*$/i.exec(input);
  if (!m) return null;
  const phase = PHASE_ALIASES[m[1].toLowerCase()] ?? m[1].toLowerCase();
  if (!PHASES[phase]) return null;
  return { phase, projNumber: Number(m[2]) };
}

export function quickAddTitle(prefill: { phase: string; projNumber: number }): string {
  const label = PHASES[prefill.phase]?.label ?? prefill.phase;
  return `PROJ-${prefill.projNumber}: ${label} starten`;
}

export function quickAddBody(prefill: { phase: string; projNumber: number }): string {
  const skill = PHASES[prefill.phase]?.skill ?? `abc-${prefill.phase}`;
  return `/abc-${skill.replace("abc-", "")} für PROJ-${prefill.projNumber} ausführen`;
}

interface NewTaskDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  board: string;
  assignees: string[];
  parents: HermesKanbanTask[];
  prefill?: QuickAddPrefill | null;
  onCreated: () => void;
}

// PROJ-84 C: fester Workspace-Pfad-Basis; der Nutzer ergänzt nur den Ordner.
const WORKSPACE_BASE = "/home/dev/projects/";

const INITIAL_STATUSES = [
  { value: "normal", label: "Normal" },
  { value: "blocked", label: "Blockiert" },
  { value: "running", label: "Running" },
];

export function NewTaskDialog({
  open,
  onOpenChange,
  board,
  assignees,
  parents,
  prefill,
  onCreated,
}: NewTaskDialogProps) {
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [assignee, setAssignee] = useState("");
  const [workspacePath, setWorkspacePath] = useState(WORKSPACE_BASE);
  const [priority, setPriority] = useState("");
  const [skills, setSkills] = useState("");
  const [initialStatus, setInitialStatus] = useState("normal");
  const [triage, setTriage] = useState(false);
  const [maxRuntime, setMaxRuntime] = useState("");
  const [maxRetries, setMaxRetries] = useState("");
  const [modelOverride, setModelOverride] = useState("");
  const [providerOverride, setProviderOverride] = useState("");
  const [goalMode, setGoalMode] = useState(false);
  const [goalMaxTurns, setGoalMaxTurns] = useState("20");
  const [selectedParents, setSelectedParents] = useState<string[]>([]);
  const [parentSearch, setParentSearch] = useState("");
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [createdId, setCreatedId] = useState<string | null>(null);

  // Vorbefüllung beim Öffnen (Kurzsyntax oder leer) übernehmen. Reset auf neuen
  // Dialog — bewusst kein Effekt, sondern reset-on-open (React-empfohlen).
  const [lastOpen, setLastOpen] = useState(false);
  if (open !== lastOpen) {
    setLastOpen(open);
    if (open) resetForOpen(prefill);
  }

  function resetForOpen(p: QuickAddPrefill | null | undefined) {
    setTitle(p?.title ?? "");
    setBody(p?.body ?? "");
    // PROJ-84 C: jupiter-coordinator nur vorauswählen, wenn verfügbar.
    setAssignee(assignees.includes("jupiter-coordinator") ? "jupiter-coordinator" : "");
    setWorkspacePath(WORKSPACE_BASE);
    setPriority("");
    setSkills("");
    setInitialStatus("normal");
    setTriage(false);
    setMaxRuntime("");
    setMaxRetries("");
    setModelOverride("");
    setProviderOverride("");
    setGoalMode(false);
    setGoalMaxTurns("20");
    setSelectedParents([]);
    setParentSearch("");
    setAdvancedOpen(false);
    setError(null);
    setCreatedId(null);
  }

  // Best-Effort: existiert das Feature, echten Titel aus INDEX.md übernehmen.
  function loadFeatureTitle(projNumber: number) {
    void lookupHermesKanbanFeature(projNumber)
      .then((r) => {
        if (r.title && r.title !== title) setTitle(r.title);
      })
      .catch(() => {
        /* Best-Effort — generischer Titel bleibt. */
      });
  }

  const modelXorProvider = Boolean(modelOverride) !== Boolean(providerOverride);
  const triageConflict = triage && initialStatus !== "normal";

  // PROJ-84 C: clientseitige Vorpüfung des Workspace-Pfads (schnelles Feedback).
  // Serverseitige kanonische Prüfung erfolgt in backend/app/schemas/hermes_kanban.py.
  const trimmedPath = workspacePath.trim();
  const pathError =
    trimmedPath === "" || trimmedPath === WORKSPACE_BASE
      ? "Bitte einen Projektordner unter /home/dev/projects/ ergänzen."
      : !trimmedPath.startsWith(WORKSPACE_BASE)
        ? "Der Workspace-Pfad muss unter /home/dev/projects/ liegen."
        : null;

  const filteredParents = useMemo(() => {
    const q = parentSearch.trim().toLowerCase();
    if (!q) return parents;
    return parents.filter((p) => p.title.toLowerCase().includes(q));
  }, [parents, parentSearch]);

  function toggleParent(id: string) {
    setSelectedParents((cur) =>
      cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id],
    );
  }

  // PROJ-20: erkannter Text wird mit Leerzeichen angehängt, vorhandener
  // Beschreibungstext bleibt erhalten.
  function appendTranscript(text: string) {
    setBody((cur) => (cur ? `${cur} ${text}` : text));
  }

  async function handleSubmit() {
    if (saving || !title.trim()) return;
    if (triageConflict) {
      setError("Triage und ein von 'normal' abweichender Initial-Status schließen sich aus.");
      return;
    }
    if (modelXorProvider) {
      setError("Modell-Override und Provider-Override gehören zusammen oder keines von beiden.");
      return;
    }
    if (pathError) {
      setError(pathError);
      return;
    }

    const payload: HermesKanbanCreateRequest = {
      title: title.trim(),
      body: body.trim() || null,
      assignee: assignee || null,
      workspace_path: trimmedPath,
      parents: selectedParents,
      priority: priority === "" ? null : Number(priority),
      skills: skills
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean),
      initial_status: initialStatus,
      triage,
      max_runtime: maxRuntime.trim() || null,
      max_retries: maxRetries === "" ? null : Number(maxRetries),
      model_override: modelOverride.trim() || null,
      provider_override: providerOverride.trim() || null,
      goal_mode: goalMode,
      goal_max_turns: goalMode ? Number(goalMaxTurns) || 20 : null,
    };

    setSaving(true);
    setError(null);
    try {
      const res = await createHermesKanbanTask(payload, board);
      const id = res.id ?? res.task_id ?? "";
      setCreatedId(id);
      toast.success("Task angelegt");
      onCreated();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Anlegen fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  function close() {
    onOpenChange(false);
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && close()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto max-w-2xl">
        <DialogHeader>
          <DialogTitle>Neuer Kanban-Task</DialogTitle>
          <DialogDescription>
            {prefill
              ? `Vorbefüllt aus Schnell-Anlage (${prefill.phase} ${prefill.projNumber}). Bitte prüfen und bestätigen.`
              : "Titel, Beschreibung, Assignee und Workspace — der Rest ist optional."}
          </DialogDescription>
        </DialogHeader>

        {createdId ? (
          <div className="grid gap-3">
            <p className="rounded-lg border border-green-500/40 bg-green-500/5 px-4 py-3 text-sm text-green-600 dark:text-green-400">
              Task erstellt{createdId ? ` mit ID ${createdId}` : ""}.
            </p>
            <DialogFooter>
              <Button onClick={close}>Schließen</Button>
              <Button variant="outline" onClick={() => resetForOpen(null)}>
                Weitere anlegen
              </Button>
            </DialogFooter>
          </div>
        ) : (
          <div className="grid gap-4">
            {prefill && (
              <button
                type="button"
                className="w-fit text-left text-xs text-muted-foreground hover:text-foreground"
                onClick={() => loadFeatureTitle(prefill.projNumber)}
              >
                Titel aus Feature-Index übernehmen (Best-Effort)
              </button>
            )}

            <div className="grid gap-2">
              <Label htmlFor="hk_title">Titel *</Label>
              <Input
                id="hk_title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={500}
              />
            </div>

            {/* PROJ-84 C: deutlich größere Beschreibung + Push-to-Talk aus PROJ-20. */}
            <div className="grid gap-2">
              <Label htmlFor="hk_body">Beschreibung</Label>
              <div className="flex items-start gap-2">
                <Textarea
                  id="hk_body"
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  rows={10}
                  className="min-h-40 flex-1"
                  placeholder="Aufgabe ausführlich beschreiben — auch per Mikrofon diktieren."
                />
                <PushToTalkButton
                  onTranscript={appendTranscript}
                  title="Beschreibung diktieren"
                />
              </div>
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="hk_assignee">Assignee</Label>
                <select
                  id="hk_assignee"
                  className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm"
                  value={assignee}
                  onChange={(e) => setAssignee(e.target.value)}
                >
                  <option value="">Kein Assignee</option>
                  {assignees.map((a) => (
                    <option key={a} value={a}>
                      {a}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="hk_initial_status">Initial-Status</Label>
                <select
                  id="hk_initial_status"
                  className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm"
                  value={initialStatus}
                  onChange={(e) => setInitialStatus(e.target.value)}
                >
                  {INITIAL_STATUSES.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            {/* PROJ-84 C: fester dir-Workspace, nur der Projektordner wird ergänzt. */}
            <div className="grid gap-2">
              <Label htmlFor="hk_ws_path">Workspace-Pfad *</Label>
              <Input
                id="hk_ws_path"
                value={workspacePath}
                onChange={(e) => setWorkspacePath(e.target.value)}
                placeholder="/home/dev/projects/mein-projekt"
                aria-invalid={pathError ? true : undefined}
              />
              {pathError ? (
                <p className="text-xs text-red-500">{pathError}</p>
              ) : (
                <p className="text-xs text-muted-foreground">
                  Vollständiger Pfad: {trimmedPath}
                </p>
              )}
            </div>

            <div className="grid gap-3 sm:grid-cols-2">
              <div className="grid gap-2">
                <Label htmlFor="hk_priority">Priorität</Label>
                <Input
                  id="hk_priority"
                  type="number"
                  value={priority}
                  onChange={(e) => setPriority(e.target.value)}
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="hk_skills">Skills (kommagetrennt)</Label>
                <Input
                  id="hk_skills"
                  value={skills}
                  onChange={(e) => setSkills(e.target.value)}
                  placeholder="requirements, review"
                />
              </div>
            </div>

            <button
              type="button"
              className="flex w-fit items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
              onClick={() => setAdvancedOpen((v) => !v)}
            >
              {advancedOpen ? (
                <ChevronDownIcon className="size-4" />
              ) : (
                <ChevronRightIcon className="size-4" />
              )}
              Erweitert
            </button>

            {advancedOpen && (
              <div className="grid gap-4 rounded-lg border border-border p-3">
                {/* PROJ-84 C: Parent-Tasks liegen vollständig unter „Erweitert". */}
                <div className="grid gap-2">
                  <Label>Parent-Tasks</Label>
                  <Input
                    value={parentSearch}
                    onChange={(e) => setParentSearch(e.target.value)}
                    placeholder="Nach Titel suchen…"
                    className="mb-1"
                  />
                  {filteredParents.length === 0 ? (
                    <p className="text-xs text-muted-foreground">
                      Keine (weiteren) offenen Tasks für diese Vorfilterung.
                    </p>
                  ) : (
                    <div className="max-h-32 space-y-1 overflow-y-auto rounded-lg border border-border p-2">
                      {filteredParents.map((p) => (
                        <label
                          key={p.id}
                          className="flex cursor-pointer items-center gap-2 text-sm"
                        >
                          <input
                            type="checkbox"
                            checked={selectedParents.includes(p.id)}
                            onChange={() => toggleParent(p.id)}
                          />
                          <span className="truncate">
                            {p.title} {p.status !== "todo" ? `(${p.status})` : ""}
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>

                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={triage}
                    onChange={(e) => setTriage(e.target.checked)}
                  />
                  Triage ({`--triage`})
                </label>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="grid gap-2">
                    <Label htmlFor="hk_max_runtime">Max-Runtime</Label>
                    <Input
                      id="hk_max_runtime"
                      value={maxRuntime}
                      onChange={(e) => setMaxRuntime(e.target.value)}
                      placeholder="z. B. 90s, 30m, 2h, 1d"
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="hk_max_retries">Max-Retries</Label>
                    <Input
                      id="hk_max_retries"
                      type="number"
                      value={maxRetries}
                      onChange={(e) => setMaxRetries(e.target.value)}
                    />
                  </div>
                </div>

                <div className="grid gap-3 sm:grid-cols-2">
                  <div className="grid gap-2">
                    <Label htmlFor="hk_model">Model-Override</Label>
                    <Input
                      id="hk_model"
                      value={modelOverride}
                      onChange={(e) => setModelOverride(e.target.value)}
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="hk_provider">Provider-Override</Label>
                    <Input
                      id="hk_provider"
                      value={providerOverride}
                      onChange={(e) => setProviderOverride(e.target.value)}
                    />
                  </div>
                </div>
                {modelXorProvider && (
                  <p className="text-xs text-red-500">Beide zusammen oder keins.</p>
                )}

                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={goalMode}
                    onChange={(e) => setGoalMode(e.target.checked)}
                  />
                  Goal-Mode
                </label>
                {goalMode && (
                  <div className="grid gap-2">
                    <Label htmlFor="hk_goal_turns">Goal-Max-Turns</Label>
                    <Input
                      id="hk_goal_turns"
                      type="number"
                      value={goalMaxTurns}
                      onChange={(e) => setGoalMaxTurns(e.target.value)}
                    />
                  </div>
                )}
              </div>
            )}

            {error && (
              <p className="rounded-lg border border-red-500/40 bg-red-500/5 px-3 py-2 text-sm text-red-500">
                {error}
              </p>
            )}

            <DialogFooter>
              <Button variant="outline" onClick={close}>
                Abbrechen
              </Button>
              <Button
                disabled={saving || !title.trim() || triageConflict || modelXorProvider || !!pathError}
                onClick={() => void handleSubmit()}
              >
                {saving ? "Erstellt…" : "Erstellen"}
              </Button>
            </DialogFooter>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
