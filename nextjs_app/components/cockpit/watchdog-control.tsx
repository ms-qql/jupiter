"use client";

// Watchdog-Limits konfigurieren (PROJ-16). Vier Schwellen als Reißleine gegen
// durchdrehende Sessions: Tokens/Zeit, Laufzeit-ohne-Fortschritt, identische
// Tool-Wiederholungen, Schreibrate. GET/PUT /settings/watchdog, live übernommen.
// Fehlt/kaputt die Server-Config → konservative Defaults (nie „kein Watchdog").

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, getWatchdog, setWatchdog } from "@/lib/api";
import type { WatchdogLimits, WatchdogSetting } from "@/lib/types";

// Editierbare Felder + menschenlesbare Beschriftung/Einheit/Hilfetext.
const FIELDS: {
  key: keyof Omit<WatchdogLimits, "enabled">;
  label: string;
  unit: string;
  hint: string;
}[] = [
  {
    key: "token_limit",
    label: "Tokens je Zeitfenster",
    unit: "Tokens",
    hint: "Abgerechnete Tokens, ab denen pausiert wird (Token-Verbrennen).",
  },
  {
    key: "token_window_seconds",
    label: "Token-Zeitfenster",
    unit: "s",
    hint: "Gleitendes Fenster für das Token-Limit.",
  },
  {
    key: "max_idle_seconds",
    label: "Max. Laufzeit ohne Fortschritt",
    unit: "s",
    hint: "Sekunden ohne neuen Output/Result → Stillstand/Hänger.",
  },
  {
    key: "max_repeated_calls",
    label: "Identische Tool-Calls in Folge",
    unit: "×",
    hint: "Gleicher Aufruf N-mal → Schleife (unterschiedliche = Iteration).",
  },
  {
    key: "write_limit",
    label: "Writes je Zeitfenster",
    unit: "Writes",
    hint: "Schreibrate; viele Writes auf verschiedene Pfade bleiben erlaubt.",
  },
  {
    key: "write_window_seconds",
    label: "Write-Zeitfenster",
    unit: "s",
    hint: "Gleitendes Fenster für die Schreibrate.",
  },
];

export function WatchdogControl() {
  const [setting, setSetting] = useState<WatchdogSetting | null>(null);
  const [form, setForm] = useState<WatchdogLimits | null>(null);
  const [saving, setSaving] = useState(false);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    getWatchdog(ac.signal)
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
    // Sanity vor dem Senden: positive Zahlen (Server klemmt zusätzlich).
    const invalid = FIELDS.some((f) => !Number.isFinite(form[f.key]) || form[f.key] <= 0);
    if (invalid) {
      toast.error("Alle Limits müssen positive Zahlen sein.");
      return;
    }
    setSaving(true);
    try {
      const updated = await setWatchdog(form);
      setSetting(updated);
      setForm(extractLimits(updated));
      toast.success("Watchdog-Limits gespeichert (live)");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  if (offline) {
    return (
      <p className="rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-700 dark:text-amber-400">
        Watchdog-Einstellungen nicht erreichbar — Backend offline oder Endpunkt
        (<code>/settings/watchdog</code>) noch nicht gebaut.
      </p>
    );
  }
  if (!form) {
    return <p className="text-xs text-muted-foreground">Lädt…</p>;
  }

  return (
    <div className="grid gap-4">
      {/* Defekt-/Quelle-Banner (analog Trust-Policy) */}
      {setting?.warning ? (
        <p className="rounded-md border border-red-500/40 bg-red-500/10 p-2 text-xs text-red-600 dark:text-red-400">
          {setting.warning} — es greifen konservative Defaults.
        </p>
      ) : (
        setting && (
          <p className="text-xs text-muted-foreground">
            Quelle: <span className="font-mono">{setting.source}</span>. Reißleine gegen
            durchdrehende Sessions — bei Riss wird <strong>pausiert</strong> (nicht getötet)
            und eine Decision Card erzeugt.
          </p>
        )
      )}

      {/* Globaler An/Aus-Schalter */}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.enabled}
          onChange={(e) => setForm({ ...form, enabled: e.target.checked })}
          className="size-4 accent-amber-500"
        />
        Watchdog aktiv
      </label>

      {/* Vier Limits (sechs Felder: zwei haben ein Zeitfenster) */}
      <div className="grid gap-3 sm:grid-cols-2">
        {FIELDS.map((f) => (
          <div key={f.key} className="grid gap-1.5">
            <Label htmlFor={`wd_${f.key}`} className="text-xs">
              {f.label}
            </Label>
            <div className="flex items-center gap-2">
              <Input
                id={`wd_${f.key}`}
                type="number"
                min={1}
                value={String(form[f.key])}
                disabled={!form.enabled}
                onChange={(e) => setForm({ ...form, [f.key]: Number(e.target.value) })}
                className="w-28"
              />
              <span className="text-xs text-muted-foreground">{f.unit}</span>
            </div>
            <p className="text-[11px] leading-snug text-muted-foreground">{f.hint}</p>
          </div>
        ))}
      </div>

      <div>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? "Speichert…" : "Speichern (live)"}
        </Button>
      </div>
    </div>
  );
}

function extractLimits(s: WatchdogSetting): WatchdogLimits {
  return {
    enabled: s.enabled,
    token_limit: s.token_limit,
    token_window_seconds: s.token_window_seconds,
    max_idle_seconds: s.max_idle_seconds,
    max_repeated_calls: s.max_repeated_calls,
    write_limit: s.write_limit,
    write_window_seconds: s.write_window_seconds,
  };
}
