"use client";

import { useEffect, useState } from "react";
import { CheckCircle2Icon, CircleAlertIcon, CircleXIcon } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError, getSavingsMetrics, getTokenSavings, setTokenSavings } from "@/lib/api";
import type {
  SavingsModuleHealth,
  TokenSavingsConfig,
  TokenSavingsSetting,
  SavingsMetrics,
} from "@/lib/types";

const MODULE_LABELS: Record<string, string> = {
  caveman: "Caveman",
  ponytail: "Ponytail",
  codegraph: "CodeGraph",
};

export function TokenSavingsControl() {
  const [setting, setSetting] = useState<TokenSavingsSetting | null>(null);
  const [form, setForm] = useState<TokenSavingsConfig | null>(null);
  const [engine, setEngine] = useState("claude");
  const [saving, setSaving] = useState(false);
  const [offline, setOffline] = useState(false);
  const [metrics, setMetrics] = useState<SavingsMetrics | null>(null);

  useEffect(() => {
    const ac = new AbortController();
    getTokenSavings(engine, "/home/dev/projects/jupiter", ac.signal)
      .then((value) => {
        setSetting(value);
        // Engine-Tabs wechseln nur die Health-Sicht; noch nicht gespeicherte
        // Schalteränderungen dürfen dabei nicht verloren gehen.
        setForm((current) => current ?? extractConfig(value));
        setOffline(false);
      })
      .catch(() => setOffline(true));
    return () => ac.abort();
  }, [engine]);

  useEffect(() => {
    const ac = new AbortController();
    getSavingsMetrics(ac.signal).then(setMetrics).catch(() => setMetrics(null));
    return () => ac.abort();
  }, []);

  async function handleSave() {
    if (!form || saving) return;
    setSaving(true);
    try {
      const updated = await setTokenSavings(form, engine);
      setSetting(updated);
      setForm(extractConfig(updated));
      toast.success("Token-Savings-Einstellungen gespeichert");
    } catch (error) {
      toast.error(error instanceof ApiError ? error.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  if (offline) {
    return (
      <p className="rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-700 dark:text-amber-400">
        Token Savings nicht erreichbar — Backend offline oder Endpunkt noch nicht verfügbar.
      </p>
    );
  }
  if (!form || !setting) {
    return <p className="text-xs text-muted-foreground">Lädt…</p>;
  }

  return (
    <div className="grid gap-4">
      {setting.warning && (
        <p className="rounded-md border border-red-500/40 bg-red-500/10 p-2 text-xs text-red-600 dark:text-red-400">
          {setting.warning} — bis zur Korrektur bleibt der sichere Default „Aus“ aktiv.
        </p>
      )}

      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="grid gap-1">
          <label className="flex items-center gap-2 text-sm font-medium">
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(event) => setForm({ ...form, enabled: event.target.checked })}
              className="size-4 accent-emerald-500"
            />
            Token Savings als globalen Standard aktivieren
          </label>
          <p className="text-[11px] leading-snug text-muted-foreground">
            Gilt für neue Sessions. Laufende Sessions behalten ihren Start-Snapshot.
            Im Neue-Session-Dialog kann der Standard überschrieben werden.
          </p>
        </div>
        <Badge variant="outline">{form.profile_id}</Badge>
      </div>

      <div className="flex flex-wrap gap-1" aria-label="Engine für Health-Prüfung">
        {[
          ["claude", "Claude"],
          ["codex", "Codex"],
          ["opencode", "OpenCode"],
        ].map(([key, label]) => (
          <Button
            key={key}
            type="button"
            size="sm"
            variant={engine === key ? "default" : "outline"}
            onClick={() => setEngine(key)}
          >
            {label}
          </Button>
        ))}
      </div>

      <div className="grid gap-2">
        {setting.modules.map((module) => (
          <ModuleRow
            key={module.name}
            module={module}
            enabled={form.module_enabled[module.name] !== false}
            onToggle={(enabled) =>
              setForm({
                ...form,
                module_enabled: { ...form.module_enabled, [module.name]: enabled },
              })
            }
          />
        ))}
      </div>

      <p className="text-[11px] leading-snug text-muted-foreground">
        Der Schalter installiert keine Tools. Fehlende oder ungesunde Module werden beim
        Session-Start ausgelassen und als eingeschränkt gemeldet. Es gibt keine garantierte
        Einsparquote.
      </p>

      {metrics && (
        <div className="rounded-md border border-border p-3 text-xs">
          <p className="font-medium">Pilot-Messung (30 Tage)</p>
          <p className="mt-1 text-muted-foreground">
            Einsparung: {metrics.estimated_tokens_avoided ?? "nicht messbar"} · Zusatzlatenz: {metrics.additional_latency_ms ?? "nicht messbar"} · Fallbacks: {metrics.fallback_count}
          </p>
          <p className="mt-1 text-muted-foreground">
            Savings-Samples: {metrics.sample_size} · Kontroll-Samples: {metrics.control_sample_size}
            {metrics.small_sample ? " · kleine Stichprobe" : ""} · Pilot: {metrics.pilot_status === "not_ready" ? "noch nicht freigabefähig" : metrics.pilot_status}
          </p>
        </div>
      )}

      <div>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? "Speichert…" : "Speichern"}
        </Button>
      </div>
    </div>
  );
}

function ModuleRow({
  module,
  enabled,
  onToggle,
}: {
  module: SavingsModuleHealth;
  enabled: boolean;
  onToggle: (enabled: boolean) => void;
}) {
  const Icon = module.healthy
    ? CheckCircle2Icon
    : module.installed
      ? CircleAlertIcon
      : CircleXIcon;
  const status = module.healthy
    ? "bereit"
    : module.installed
      ? "Konfiguration nötig"
      : "nicht installiert";

  return (
    <div className="grid gap-2 rounded-md border border-border p-3 sm:grid-cols-[1fr_auto] sm:items-start">
      <div className="flex min-w-0 gap-2">
        <Icon
          className={`mt-0.5 size-4 shrink-0 ${
            module.healthy
              ? "text-emerald-500"
              : module.installed
                ? "text-amber-500"
                : "text-muted-foreground"
          }`}
        />
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-sm font-medium">
              {MODULE_LABELS[module.name] ?? module.name}
            </span>
            <Badge variant="outline">{module.stability}</Badge>
            <Badge variant={module.healthy ? "default" : "secondary"}>{status}</Badge>
          </div>
          <p className="mt-1 break-words text-[11px] leading-snug text-muted-foreground">
            Integration: {integrationLabel(module.integration)}
            {module.version ? ` · Version ${module.version}` : ""}
            {module.detail ? ` · ${module.detail}` : ""}
          </p>
          {module.name === "codegraph" && (
            <p className="mt-1 text-[11px] text-muted-foreground">
              Binary {yesNo(module.binary_found)} · MCP {yesNo(module.mcp_configured)} · Index{" "}
              {yesNo(module.project_index_present)} · Frische {module.index_freshness ?? "unbekannt"}
            </p>
          )}
        </div>
      </div>
      <label className="flex items-center gap-2 text-xs">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => onToggle(event.target.checked)}
          className="size-4 accent-emerald-500"
        />
        Im Profil erlaubt
      </label>
    </div>
  );
}

function extractConfig(value: TokenSavingsSetting): TokenSavingsConfig {
  return {
    enabled: value.enabled,
    profile_id: value.profile_id,
    module_enabled: { ...value.module_enabled },
  };
}

function integrationLabel(value: string): string {
  return {
    native: "nativ",
    mcp: "MCP",
    instruction: "Instruktions-Fallback",
    unavailable: "nicht verfügbar",
  }[value] ?? value;
}

function yesNo(value: boolean | null): string {
  if (value === null) return "unbekannt";
  return value ? "vorhanden" : "fehlt";
}
