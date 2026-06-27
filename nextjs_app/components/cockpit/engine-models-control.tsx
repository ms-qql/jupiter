"use client";

// PROJ-51: Engine-/Modellverwaltung. Die UI editiert nicht direkt im Browser eine
// Datei, sondern sendet die vollständige, validierte Konfiguration ans Backend; das
// Backend schreibt atomar in backend/config/engines.yaml.

import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangleIcon,
  CheckCircle2Icon,
  PlusIcon,
  RefreshCwIcon,
  RotateCcwIcon,
  SaveIcon,
  Trash2Icon,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  ApiError,
  getEngineSettings,
  setEngineSettings,
  validateEngineSettings,
} from "@/lib/api";
import type { EngineSettingsEntry, EngineSettingsOverview } from "@/lib/types";

function cloneEngines(engines: EngineSettingsEntry[]): EngineSettingsEntry[] {
  return engines.map((e) => ({
    ...e,
    models: [...e.models],
    capabilities: [...e.capabilities],
    argv_template: [...e.argv_template],
    resume_argv_template: [...e.resume_argv_template],
  }));
}

function statusBadge(engine: EngineSettingsEntry) {
  if (!engine.enabled) {
    return <Badge variant="outline">deaktiviert</Badge>;
  }
  if (engine.available) {
    return (
      <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
        verfügbar
      </Badge>
    );
  }
  return <Badge variant="destructive">nicht verfügbar</Badge>;
}

function providerKind(engine: EngineSettingsEntry): string {
  if (engine.key === "claude") return "Built-in";
  if (engine.driver === "openai") return "HTTP";
  if (engine.driver === "generic_cli") return "CLI";
  return engine.driver ?? engine.kind;
}

function csv(values: string[]): string {
  return values.join(", ");
}

function parseCsv(value: string): string[] {
  return value
    .split(",")
    .map((v) => v.trim())
    .filter(Boolean);
}

function ensureDefault(engine: EngineSettingsEntry): EngineSettingsEntry {
  if (!engine.default_model || !engine.models.includes(engine.default_model)) {
    return { ...engine, default_model: engine.models[0] ?? null };
  }
  return engine;
}

export function EngineModelsControl() {
  const [snapshot, setSnapshot] = useState<EngineSettingsOverview | null>(null);
  const [engines, setEngines] = useState<EngineSettingsEntry[]>([]);
  const [selectedKey, setSelectedKey] = useState("claude");
  const [modelDraft, setModelDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);

  function applySnapshot(s: EngineSettingsOverview, keepSelection = true) {
    setSnapshot(s);
    setEngines(cloneEngines(s.engines));
    const sessionEngines = s.engines.filter((e) => e.kind === "engine");
    setSelectedKey((cur) =>
      keepSelection
        ? (sessionEngines.find((e) => e.key === cur)?.key ?? sessionEngines[0]?.key ?? "claude")
        : (sessionEngines[0]?.key ?? "claude"),
    );
    setLoadFailed(false);
  }

  async function reload() {
    setLoading(true);
    try {
      applySnapshot(await getEngineSettings());
    } catch {
      setLoadFailed(true);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    const ac = new AbortController();
    getEngineSettings(ac.signal)
      .then((s) => {
        if (!ac.signal.aborted) applySnapshot(s, false);
      })
      .catch(() => {
        if (!ac.signal.aborted) setLoadFailed(true);
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoading(false);
      });
    return () => ac.abort();
  }, []);

  const selected = useMemo(
    () => {
      const sessionEngines = engines.filter((e) => e.kind === "engine");
      return sessionEngines.find((e) => e.key === selectedKey) ?? sessionEngines[0] ?? null;
    },
    [engines, selectedKey],
  );
  const visibleEngines = useMemo(
    () => engines.filter((e) => e.kind === "engine"),
    [engines],
  );
  const dirty = Boolean(snapshot) && JSON.stringify(engines) !== JSON.stringify(snapshot?.engines);

  function patchSelected(patch: Partial<EngineSettingsEntry>) {
    if (!selected) return;
    setEngines((items) =>
      items.map((e) => (e.key === selected.key ? ensureDefault({ ...e, ...patch }) : e)),
    );
  }

  function updateModel(index: number, value: string) {
    if (!selected) return;
    const next = [...selected.models];
    next[index] = value.trim();
    patchSelected({ models: next.filter(Boolean) });
  }

  function removeModel(model: string) {
    if (!selected) return;
    patchSelected({ models: selected.models.filter((m) => m !== model) });
  }

  function addModel() {
    const model = modelDraft.trim();
    if (!selected || !model) return;
    if (selected.models.includes(model)) {
      toast.error("Dieses Modell ist bereits vorhanden");
      return;
    }
    patchSelected({ models: [...selected.models, model], default_model: selected.default_model ?? model });
    setModelDraft("");
  }

  async function handleValidate() {
    if (validating || saving) return;
    setValidating(true);
    try {
      const result = await validateEngineSettings(engines);
      toast.success(
        result.warnings.length > 0
          ? `Konfiguration gültig (${result.warnings.length} Hinweis(e))`
          : "Konfiguration gültig",
      );
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Validierung fehlgeschlagen");
    } finally {
      setValidating(false);
    }
  }

  async function handleSave() {
    if (saving) return;
    setSaving(true);
    try {
      const saved = await setEngineSettings(engines);
      setSnapshot(saved);
      setEngines(cloneEngines(saved.engines));
      toast.success("Modelle gespeichert");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  function resetLocal() {
    if (!snapshot) return;
    const sessionEngines = snapshot.engines.filter((e) => e.kind === "engine");
    setEngines(cloneEngines(snapshot.engines));
    setSelectedKey((cur) =>
      sessionEngines.find((e) => e.key === cur)?.key ?? sessionEngines[0]?.key ?? "claude",
    );
  }

  if (loadFailed) {
    return (
      <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-700 dark:text-amber-400">
        <div className="flex items-center gap-2 font-medium">
          <AlertTriangleIcon className="size-4" />
          Modelleinstellungen nicht erreichbar
        </div>
        <p className="mt-1 text-xs">
          Backend offline oder Endpunkt <code>/settings/engines</code> nicht verfügbar.
        </p>
      </div>
    );
  }

  if (loading || !selected) {
    return <p className="text-xs text-muted-foreground">Lädt Modelle…</p>;
  }

  const apiEditable = selected.driver === "openai" && selected.key !== "claude";
  const isClaude = selected.key === "claude";

  return (
    <div className="grid gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-xs text-muted-foreground">
          Quelle: <span className="font-mono">{snapshot?.source ?? "default"}</span>
          {snapshot?.warning ? (
            <span className="ml-2 text-amber-600 dark:text-amber-400">
              {snapshot.warning}
            </span>
          ) : null}
          <span className="ml-2">
            Micro-Apps, iFrames und Startknöpfe bleiben unverändert.
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => void reload()} disabled={saving}>
            <RefreshCwIcon />
            Neu laden
          </Button>
          <Button size="sm" variant="outline" onClick={resetLocal} disabled={!dirty || saving}>
            <RotateCcwIcon />
            Verwerfen
          </Button>
          <Button size="sm" variant="outline" onClick={handleValidate} disabled={validating || saving}>
            <CheckCircle2Icon />
            Prüfen
          </Button>
          <Button size="sm" onClick={handleSave} disabled={!dirty || saving}>
            <SaveIcon />
            Speichern
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(180px,240px)_1fr]">
        <div className="grid content-start gap-2">
          {visibleEngines.map((engine) => (
            <button
              key={engine.key}
              type="button"
              onClick={() => setSelectedKey(engine.key)}
              className={`rounded-md border p-2 text-left transition hover:bg-muted/60 ${
                engine.key === selected.key ? "border-primary bg-muted" : "border-border"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-sm font-medium">{engine.label}</span>
                {statusBadge(engine)}
              </div>
              <div className="mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
                <span className="font-mono">{engine.key}</span>
                <span>{providerKind(engine)}</span>
              </div>
            </button>
          ))}
        </div>

        <div className="grid gap-4 rounded-md border border-border p-3">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h3 className="text-sm font-semibold">{selected.label}</h3>
              <p className="text-xs text-muted-foreground">
                <span className="font-mono">{selected.key}</span> · {providerKind(selected)}
              </p>
            </div>
            <div className="flex items-center gap-2">
              {statusBadge(selected)}
              {selected.enabled && !selected.available && selected.unavailable_reason ? (
                <span className="max-w-72 text-xs text-amber-600 dark:text-amber-400">
                  {selected.unavailable_reason}
                </span>
              ) : null}
            </div>
          </div>

          <Separator />

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="grid gap-1.5">
              <Label htmlFor="engine-label" className="text-xs">Anzeigename</Label>
              <Input
                id="engine-label"
                value={selected.label}
                onChange={(e) => patchSelected({ label: e.target.value })}
                disabled={isClaude}
              />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="engine-driver" className="text-xs">Treiber</Label>
              <Input id="engine-driver" value={selected.driver ?? selected.kind} disabled />
            </div>
            <label className="flex items-center gap-2 text-sm sm:col-span-2">
              <input
                type="checkbox"
                checked={selected.enabled}
                disabled={isClaude}
                onChange={(e) => patchSelected({ enabled: e.target.checked })}
                className="size-4 accent-emerald-500"
              />
              Im Neue-Session-Dialog auswählbar
            </label>
          </div>

          {apiEditable ? (
            <>
              <Separator />
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label htmlFor="engine-api-base" className="text-xs">API-Base</Label>
                  <Input
                    id="engine-api-base"
                    value={selected.api_base ?? ""}
                    onChange={(e) => patchSelected({ api_base: e.target.value })}
                    placeholder="https://…"
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="engine-api-path" className="text-xs">API-Pfad</Label>
                  <Input
                    id="engine-api-path"
                    value={selected.api_path ?? ""}
                    onChange={(e) => patchSelected({ api_path: e.target.value })}
                    placeholder="/v1/chat/completions"
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="engine-auth-env" className="text-xs">Auth-Env-Variable</Label>
                  <Input
                    id="engine-auth-env"
                    value={selected.auth_env ?? ""}
                    onChange={(e) => patchSelected({ auth_env: e.target.value })}
                    placeholder="OPENAI_API_KEY"
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="engine-context" className="text-xs">Kontextfenster</Label>
                  <Input
                    id="engine-context"
                    type="number"
                    min={1}
                    value={String(selected.context_window ?? 128000)}
                    onChange={(e) => patchSelected({ context_window: Number(e.target.value) })}
                  />
                </div>
              </div>
            </>
          ) : null}

          {selected.driver === "generic_cli" ? (
            <>
              <Separator />
              <div className="grid gap-2 text-xs text-muted-foreground">
                <p>
                  CLI-Spezialfelder bleiben erhalten und werden aktuell nicht im Detail bearbeitet.
                </p>
                <p>
                  Binary: <span className="font-mono">{selected.bin ?? selected.argv_template[0] ?? "n/v"}</span>
                </p>
                <p>
                  Adapter: <span className="font-mono">{selected.adapter ?? "plaintext"}</span>
                  {selected.sandbox ? <> · Sandbox: <span className="font-mono">{selected.sandbox}</span></> : null}
                </p>
              </div>
            </>
          ) : null}

          <Separator />

          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="engine-default-model" className="text-xs">Default-Modell</Label>
              <select
                id="engine-default-model"
                value={selected.default_model ?? ""}
                onChange={(e) => patchSelected({ default_model: e.target.value || null })}
                className="h-8 rounded-lg border border-border bg-background px-2 text-sm"
              >
                {selected.models.length === 0 ? (
                  <option value="">Kein Modell konfiguriert</option>
                ) : null}
                {selected.models.map((m) => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            </div>

            <div className="grid gap-2">
              <Label className="text-xs">Modelle</Label>
              <div className="grid gap-2">
                {selected.models.map((model, index) => (
                  <div key={`${model}-${index}`} className="flex items-center gap-2">
                    <Input
                      value={model}
                      onChange={(e) => updateModel(index, e.target.value)}
                      className="font-mono text-xs"
                    />
                    <Button
                      type="button"
                      size="icon-sm"
                      variant="ghost"
                      onClick={() => removeModel(model)}
                      disabled={selected.models.length <= 1 && selected.enabled}
                      aria-label={`Modell ${model} entfernen`}
                    >
                      <Trash2Icon />
                    </Button>
                  </div>
                ))}
              </div>
              <div className="flex gap-2">
                <Input
                  value={modelDraft}
                  onChange={(e) => setModelDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      e.preventDefault();
                      addModel();
                    }
                  }}
                  placeholder="neues-modell"
                  className="font-mono text-xs"
                />
                <Button type="button" size="sm" variant="outline" onClick={addModel}>
                  <PlusIcon />
                  Hinzufügen
                </Button>
              </div>
            </div>

            <div className="grid gap-1.5">
              <Label htmlFor="engine-capabilities" className="text-xs">Capabilities</Label>
              <Input
                id="engine-capabilities"
                value={csv(selected.capabilities)}
                onChange={(e) => patchSelected({ capabilities: parseCsv(e.target.value) })}
                placeholder="usage, multi_turn"
                className="font-mono text-xs"
              />
              <p className="text-[11px] text-muted-foreground">
                Kommagetrennt. Bestehende Werte wie <span className="font-mono">abc</span> bleiben erhalten, solange sie hier stehen.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
