"use client";

// Provider-Budget-Schnappschüsse pflegen (PROJ-52). Die 5h-/Wochen-Kontingente von
// Claude/Codex sind nicht stabil maschinenlesbar (Claudes `/usage` zählt alle Geräte +
// claude.ai). Darum trägt der Nutzer hier die echten Zahlen aus der Provider-Anzeige
// ein: pro Fenster Prozent + Reset-Zeitpunkt. Die Sidebar zeigt genau diese Werte und
// markiert abgelaufene Reset-Zeiten automatisch als „veraltet".
// GET/PUT /settings/provider-budgets, live übernommen (Sidebar-Cache wird verworfen).
// Prozent leer = unbekannt → die Sidebar zeigt für dieses Fenster n/v.

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ApiError,
  getProviderBudgetLimits,
  setProviderBudgetLimits,
} from "@/lib/api";
import type { ProviderBudgetLimits, ProviderBudgetSetting } from "@/lib/types";

type PctKey =
  | "claude_5h_pct"
  | "claude_week_pct"
  | "codex_5h_pct"
  | "codex_week_pct"
  | "opencode_5h_pct"
  | "opencode_week_pct";
type ResetKey =
  | "claude_5h_reset_at"
  | "claude_week_reset_at"
  | "codex_5h_reset_at"
  | "codex_week_reset_at"
  | "opencode_5h_reset_at"
  | "opencode_week_reset_at";

const PROVIDERS: {
  name: string;
  windows: { label: string; pctKey: PctKey; resetKey: ResetKey }[];
}[] = [
  {
    name: "Claude",
    windows: [
      { label: "5h-Fenster", pctKey: "claude_5h_pct", resetKey: "claude_5h_reset_at" },
      { label: "Wochen-Fenster", pctKey: "claude_week_pct", resetKey: "claude_week_reset_at" },
    ],
  },
  {
    name: "Codex",
    windows: [
      { label: "5h-Fenster", pctKey: "codex_5h_pct", resetKey: "codex_5h_reset_at" },
      { label: "Wochen-Fenster", pctKey: "codex_week_pct", resetKey: "codex_week_reset_at" },
    ],
  },
  {
    name: "OpenCode",
    windows: [
      { label: "5h", pctKey: "opencode_5h_pct", resetKey: "opencode_5h_reset_at" },
      { label: "Wochen-Fenster", pctKey: "opencode_week_pct", resetKey: "opencode_week_reset_at" },
    ],
  },
];

export function ProviderBudgetControl() {
  const [setting, setSetting] = useState<ProviderBudgetSetting | null>(null);
  const [form, setForm] = useState<ProviderBudgetLimits | null>(null);
  const [saving, setSaving] = useState(false);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    getProviderBudgetLimits(ac.signal)
      .then((s) => {
        setSetting(s);
        setForm(extractLimits(s));
        setOffline(false);
      })
      .catch(() => setOffline(true)); // Backend evtl. offline / Endpunkt fehlt noch.
    return () => ac.abort();
  }, []);

  async function handleSave() {
    if (!form || saving) return;
    setSaving(true);
    try {
      const updated = await setProviderBudgetLimits(form);
      setSetting(updated);
      setForm(extractLimits(updated));
      toast.success("Budget-Werte gespeichert (live)");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  if (offline) {
    return (
      <p className="rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-700 dark:text-amber-400">
        Budget-Einstellungen nicht erreichbar — Backend offline oder Endpunkt
        (<code>/settings/provider-budgets</code>) noch nicht gebaut.
      </p>
    );
  }
  if (!form) {
    return <p className="text-xs text-muted-foreground">Lädt…</p>;
  }

  return (
    <div className="grid gap-4">
      {setting?.warning ? (
        <p className="rounded-md border border-red-500/40 bg-red-500/10 p-2 text-xs text-red-600 dark:text-red-400">
          {setting.warning} — bis zur Korrektur zeigt die Sidebar n/v.
        </p>
      ) : (
        <p className="text-xs text-muted-foreground">
          Echte Verbrauchszahlen aus der Provider-Anzeige eintragen (z. B. Claude{" "}
          <span className="font-mono">/usage</span>). Prozent leer lassen ={" "}
          <span className="font-mono">n/v</span>. Reset-Zeit leer = automatisch ab jetzt.
          Abgelaufene Reset-Zeiten markiert die Sidebar als{" "}
          <em>veraltet</em>. Auto-Refresh alle {setting?.refresh_minutes ?? 30} min.
        </p>
      )}

      {PROVIDERS.map((p) => (
        <div key={p.name} className="grid gap-2 rounded-md border border-border p-3">
          <p className="text-sm font-medium">{p.name}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {p.windows.map((w) => (
              <div key={w.pctKey} className="grid gap-1.5">
                <Label className="text-xs">{w.label}</Label>
                <div className="flex items-center gap-2">
                  <Input
                    type="number"
                    min={0}
                    step={1}
                    placeholder="—"
                    aria-label={`${p.name} ${w.label} Prozent`}
                    value={form[w.pctKey] === null ? "" : String(form[w.pctKey])}
                    onChange={(e) =>
                      setForm({
                        ...form,
                        [w.pctKey]: e.target.value === "" ? null : Number(e.target.value),
                      })
                    }
                    className="w-20"
                  />
                  <span className="text-xs text-muted-foreground">%</span>
                </div>
                <Input
                  type="datetime-local"
                  aria-label={`${p.name} ${w.label} Reset`}
                  value={isoToLocalInput(form[w.resetKey])}
                  onChange={(e) =>
                    setForm({ ...form, [w.resetKey]: localInputToIso(e.target.value) })
                  }
                  className="w-full"
                />
                <p className="text-[11px] leading-snug text-muted-foreground">
                  Reset-Zeitpunkt (lokale Zeit)
                </p>
              </div>
            ))}
          </div>
        </div>
      ))}

      <div>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? "Speichert…" : "Speichern (live)"}
        </Button>
      </div>
    </div>
  );
}

function extractLimits(s: ProviderBudgetSetting): ProviderBudgetLimits {
  return {
    claude_5h_pct: s.claude_5h_pct,
    claude_5h_reset_at: s.claude_5h_reset_at,
    claude_week_pct: s.claude_week_pct,
    claude_week_reset_at: s.claude_week_reset_at,
    codex_5h_pct: s.codex_5h_pct,
    codex_5h_reset_at: s.codex_5h_reset_at,
    codex_week_pct: s.codex_week_pct,
    codex_week_reset_at: s.codex_week_reset_at,
    opencode_5h_pct: s.opencode_5h_pct,
    opencode_5h_reset_at: s.opencode_5h_reset_at,
    opencode_week_pct: s.opencode_week_pct,
    opencode_week_reset_at: s.opencode_week_reset_at,
  };
}

// datetime-local <-> ISO (UTC). Das Input arbeitet in lokaler Zeit; gespeichert wird UTC.
function isoToLocalInput(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(
    d.getHours(),
  )}:${pad(d.getMinutes())}`;
}

function localInputToIso(value: string): string | null {
  if (!value) return null;
  const d = new Date(value); // als lokale Zeit interpretiert
  if (Number.isNaN(d.getTime())) return null;
  return d.toISOString();
}
