"use client";

// Trust-Policy konfigurieren (PROJ-10). Abgestuftes, kontextabhängiges Vertrauen:
// pro Regel auto-allow / card / deny, gematcht nach Tool-Klasse + Kontext
// (Rolle/Skill/Projekt). Plus das bypass-feste Phasen-Übergangs-Gate.
// Speichern wirkt LIVE (GET/PUT /settings/policy) — kein Neustart.

import { useEffect, useState } from "react";
import { AlertTriangleIcon, PlusIcon, Trash2Icon } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ApiError, getPolicy, previewPolicy, setPolicy } from "@/lib/api";
import type {
  AbcPhase,
  PolicyLevel,
  PolicyPreview,
  PolicyRule,
  TrustPolicy,
} from "@/lib/types";

// Tool-Klassen für das Match-Dropdown („" = alle Tools).
const TOOL_CHOICES: { value: string; label: string }[] = [
  { value: "*", label: "Alle Tools" },
  { value: "Bash", label: "Bash" },
  { value: "Edit", label: "Edit" },
  { value: "MultiEdit", label: "MultiEdit" },
  { value: "Write", label: "Write" },
  { value: "NotebookEdit", label: "NotebookEdit" },
  { value: "Task", label: "Task" },
  { value: "WebFetch", label: "WebFetch" },
  { value: "WebSearch", label: "WebSearch" },
  { value: "Read", label: "Read" },
  { value: "Glob", label: "Glob" },
  { value: "Grep", label: "Grep" },
];

const LEVELS: { value: PolicyLevel; label: string; hint: string }[] = [
  { value: "auto-allow", label: "Auto-Freigabe", hint: "läuft ohne Card durch" },
  { value: "card", label: "Decision Card", hint: "Freigabe nötig" },
  { value: "deny", label: "Verboten", hint: "wird nie ausgeführt" },
];

const ABC_PHASES: AbcPhase[] = [
  "brainstorm",
  "requirements",
  "architecture",
  "frontend",
  "backend",
  "qa",
  "deploy",
  "document",
];

const LEVEL_BADGE: Record<PolicyLevel, string> = {
  "auto-allow": "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  card: "border-orange-500/40 bg-orange-500/10 text-orange-600 dark:text-orange-400",
  deny: "border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400",
};

export function PolicyControl() {
  const [policy, setPolicyState] = useState<TrustPolicy | null>(null);
  const [rules, setRules] = useState<PolicyRule[]>([]);
  const [gateEnabled, setGateEnabled] = useState(true);
  const [gateTransitions, setGateTransitions] = useState<AbcPhase[]>([]);
  const [loadFailed, setLoadFailed] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    getPolicy(ac.signal)
      .then(hydrate)
      .catch((err) => {
        if (!ac.signal.aborted) setLoadFailed(err instanceof ApiError);
      });
    return () => ac.abort();
  }, []);

  function hydrate(p: TrustPolicy) {
    setPolicyState(p);
    setRules(p.rules);
    setGateEnabled(p.phase_gate.enabled);
    setGateTransitions(p.phase_gate.transitions);
    setLoadFailed(false);
  }

  function patchRule(i: number, patch: Partial<PolicyRule>) {
    setRules((rs) => rs.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  function patchMatch(i: number, key: keyof PolicyRule["match"], value: string) {
    setRules((rs) =>
      rs.map((r, idx) =>
        idx === i ? { ...r, match: { ...r.match, [key]: value || null } } : r,
      ),
    );
  }
  function addRule() {
    setRules((rs) => [...rs, { match: { tool: null }, level: "card", reason: null }]);
  }
  function removeRule(i: number) {
    setRules((rs) => rs.filter((_, idx) => idx !== i));
  }
  function toggleTransition(phase: AbcPhase) {
    setGateTransitions((t) =>
      t.includes(phase) ? t.filter((p) => p !== phase) : [...t, phase],
    );
  }

  async function handleSave() {
    if (saving) return;
    setSaving(true);
    try {
      const updated = await setPolicy(rules, {
        enabled: gateEnabled,
        transitions: gateTransitions,
      });
      hydrate(updated);
      toast.success("Trust-Policy live übernommen");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  if (loadFailed) {
    return (
      <p className="text-sm text-muted-foreground">
        Trust-Policy nicht ladbar — Backend offline?
      </p>
    );
  }
  if (!policy) {
    return <p className="text-sm text-muted-foreground">Lädt Policy…</p>;
  }

  return (
    <div className="grid gap-4">
      {/* Herkunft / Defekt-Warnung */}
      {policy.warning ? (
        <div className="flex items-start gap-2 rounded-md border border-orange-500/40 bg-orange-500/5 p-2 text-xs text-orange-600 dark:text-orange-400">
          <AlertTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
          <span>{policy.warning} — es gilt der konservative Default.</span>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          Quelle: <span className="font-mono">{policy.source}</span>. Spezifischere Regel
          schlägt allgemeinere; <span className="font-medium">Verboten</span> gewinnt jeden
          Konflikt. Ohne passende Regel: Lesen → auto, Schreiben/Shell → Card.
        </p>
      )}

      {/* Regel-Liste */}
      <div className="grid gap-2">
        <div className="flex items-center justify-between">
          <Label>Regeln ({rules.length})</Label>
          <Button size="sm" variant="outline" onClick={addRule}>
            <PlusIcon className="size-3.5" /> Regel
          </Button>
        </div>

        {rules.length === 0 && (
          <p className="text-xs text-muted-foreground">
            Keine Regeln — es gilt der konservative Default (rückwärtskompatibel zu PROJ-4).
          </p>
        )}

        {rules.map((rule, i) => (
          <div key={i} className="rounded-lg border border-border bg-muted/20 p-2.5">
            <div className="flex items-center gap-2">
              <Select
                value={rule.match.tool || "*"}
                onValueChange={(v) => patchMatch(i, "tool", !v || v === "*" ? "" : v)}
              >
                <SelectTrigger size="sm" className="w-36" aria-label="Tool-Klasse">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {TOOL_CHOICES.map((t) => (
                    <SelectItem key={t.value} value={t.value}>
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select
                value={rule.level}
                onValueChange={(v) => patchRule(i, { level: v as PolicyLevel })}
              >
                <SelectTrigger size="sm" className="w-40" aria-label="Vertrauensstufe">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LEVELS.map((l) => (
                    <SelectItem key={l.value} value={l.value}>
                      {l.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Badge variant="secondary" className={LEVEL_BADGE[rule.level]}>
                {LEVELS.find((l) => l.value === rule.level)?.hint}
              </Badge>

              <Button
                size="icon"
                variant="ghost"
                className="ml-auto size-7 text-muted-foreground hover:text-red-500"
                onClick={() => removeRule(i)}
                aria-label="Regel entfernen"
              >
                <Trash2Icon className="size-3.5" />
              </Button>
            </div>

            {/* Kontext-Match (optional) */}
            <div className="mt-2 grid grid-cols-3 gap-1.5">
              <Input
                value={rule.match.role ?? ""}
                onChange={(e) => patchMatch(i, "role", e.target.value)}
                placeholder="Rolle (alle)"
                className="h-7 text-xs"
                aria-label="Rolle"
              />
              <Input
                value={rule.match.skill ?? ""}
                onChange={(e) => patchMatch(i, "skill", e.target.value)}
                placeholder="Skill (alle)"
                className="h-7 text-xs"
                aria-label="Skill"
              />
              <Input
                value={rule.match.project ?? ""}
                onChange={(e) => patchMatch(i, "project", e.target.value)}
                placeholder="Projekt (alle)"
                className="h-7 text-xs"
                aria-label="Projekt"
              />
            </div>

            {/* Grund — vor allem bei deny sichtbar nützlich */}
            <Input
              value={rule.reason ?? ""}
              onChange={(e) => patchRule(i, { reason: e.target.value || null })}
              placeholder={
                rule.level === "deny" ? "Grund (erscheint in der Ablehnungs-Notiz)" : "Notiz (optional)"
              }
              className="mt-1.5 h-7 text-xs"
              aria-label="Grund"
            />
          </div>
        ))}
      </div>

      <Separator />

      {/* Phasen-Übergangs-Gate (bypass-fest) */}
      <div className="grid gap-2">
        <label className="flex items-center gap-2 text-sm font-medium">
          <input
            type="checkbox"
            checked={gateEnabled}
            onChange={(e) => setGateEnabled(e.target.checked)}
            className="size-4 accent-orange-500"
          />
          Phasen-Übergangs-Gate
        </label>
        <p className="text-xs text-muted-foreground">
          Erzeugt beim ABC-Phasenwechsel eine Freigabe-Card — <span className="font-medium">auch im
          Bypass-Modus</span>. So bleibst du an den Schaltstellen in der Schleife, während die
          Kleinarbeit innerhalb einer Phase ungebremst läuft.
        </p>
        {gateEnabled && (
          <>
            <p className="text-xs text-muted-foreground">
              Freigabe beim Eintritt in diese Phasen — <span className="font-medium">keine
              Auswahl = jeder Phasenwechsel</span>:
            </p>
            <div className="flex flex-wrap gap-1.5">
              {ABC_PHASES.map((phase) => {
                const active = gateTransitions.includes(phase);
                return (
                  <button
                    key={phase}
                    type="button"
                    onClick={() => toggleTransition(phase)}
                    className={
                      "rounded-md border px-2 py-0.5 text-xs transition-colors " +
                      (active
                        ? "border-orange-500/50 bg-orange-500/10 text-orange-600 dark:text-orange-400"
                        : "border-border text-muted-foreground hover:bg-muted")
                    }
                  >
                    {phase}
                  </button>
                );
              })}
            </div>
          </>
        )}
      </div>

      <Separator />

      <PolicyPreviewTester />

      <div className="flex items-center justify-end gap-2">
        <Button variant="ghost" size="sm" onClick={() => hydrate(policy)} disabled={saving}>
          Zurücksetzen
        </Button>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? "Speichert…" : "Speichern (live)"}
        </Button>
      </div>
    </div>
  );
}

// Trockenlauf-Tester: zeigt, welche Stufe + Regel für einen Kontext greifen würde.
function PolicyPreviewTester() {
  const [tool, setTool] = useState("Bash");
  const [role, setRole] = useState("");
  const [result, setResult] = useState<PolicyPreview | null>(null);
  const [busy, setBusy] = useState(false);

  async function run() {
    if (busy) return;
    setBusy(true);
    try {
      setResult(await previewPolicy({ tool, role: role || undefined }));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Vorschau fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-2">
      <Label className="text-xs">Regel-Test</Label>
      <div className="flex flex-wrap items-center gap-1.5">
        <Select value={tool} onValueChange={(v) => setTool(v ?? "")}>
          <SelectTrigger size="sm" className="w-32" aria-label="Tool für Test">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {TOOL_CHOICES.filter((t) => t.value !== "*").map((t) => (
              <SelectItem key={t.value} value={t.value}>
                {t.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input
          value={role}
          onChange={(e) => setRole(e.target.value)}
          placeholder="Rolle (optional)"
          className="h-7 w-32 text-xs"
          aria-label="Rolle für Test"
        />
        <Button size="sm" variant="outline" onClick={run} disabled={busy}>
          Testen
        </Button>
        {result && (
          <span className="flex items-center gap-1.5 text-xs">
            <Badge variant="secondary" className={LEVEL_BADGE[result.level]}>
              {LEVELS.find((l) => l.value === result.level)?.label ?? result.level}
            </Badge>
            <span className="text-muted-foreground">· {result.rule}</span>
          </span>
        )}
      </div>
    </div>
  );
}
