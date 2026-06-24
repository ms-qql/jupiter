"use client";

// PROJ-27: Liveness + Auto-Reanimierung konfigurieren. Schwellen für den verifizierten
// Heartbeat (wann gilt eine Session als „hängt") und die automatische Reanimierung
// (Versuche + Backoff), plus ein globaler An/Aus-Schalter der Automatik. GET/PUT
// /settings/liveness, live übernommen. Fehlt/kaputt die Server-Config → konservative
// Defaults (nie „kein Liveness"). Der Indikator + manuelle Knopf bleiben auch bei
// abgeschalteter Automatik aktiv.

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, getLiveness, setLiveness } from "@/lib/api";
import type { LivenessLimits, LivenessSetting } from "@/lib/types";

// Editierbare Zahlenfelder. `min` 0 erlaubt für den Backoff (kein Backoff); `autoOnly`
// = nur relevant, wenn die Automatik an ist (sonst deaktiviert).
const FIELDS: {
  key: keyof Omit<LivenessLimits, "enabled_auto_reanimation">;
  label: string;
  unit: string;
  min: number;
  autoOnly: boolean;
  hint: string;
}[] = [
  {
    key: "progress_timeout_seconds",
    label: "Fortschritts-Timeout",
    unit: "s",
    min: 1,
    autoOnly: false,
    hint: "Kein Fortschritt seit > X s → Zustand „hängt“ (analog Watchdog-Stillstand).",
  },
  {
    key: "poll_interval_seconds",
    label: "Poll-Intervall",
    unit: "s",
    min: 1,
    autoOnly: false,
    hint: "Frequenz des Hintergrund-Auswerters (erkennt Hänger ohne Tool-Gate).",
  },
  {
    key: "max_auto_attempts",
    label: "Max. Auto-Versuche",
    unit: "×",
    min: 1,
    autoOnly: true,
    hint: "Automatische Reanimierungs-Versuche pro Hänger; danach nur der manuelle Knopf.",
  },
  {
    key: "backoff_seconds",
    label: "Backoff zwischen Versuchen",
    unit: "s",
    min: 0,
    autoOnly: true,
    hint: "Wartezeit zwischen automatischen Versuchen (0 = kein Backoff).",
  },
];

export function LivenessControl() {
  const [setting, setSetting] = useState<LivenessSetting | null>(null);
  const [form, setForm] = useState<LivenessLimits | null>(null);
  const [saving, setSaving] = useState(false);
  const [offline, setOffline] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    getLiveness(ac.signal)
      .then((s) => {
        setSetting(s);
        setForm(extractLimits(s));
        setOffline(false);
      })
      .catch(() => setOffline(true));
    return () => ac.abort();
  }, []);

  async function handleSave() {
    if (!form || saving) return;
    const invalid = FIELDS.some(
      (f) => !Number.isFinite(form[f.key]) || form[f.key] < f.min,
    );
    if (invalid) {
      toast.error("Timeout, Poll und Versuche müssen > 0 sein; Backoff ≥ 0.");
      return;
    }
    setSaving(true);
    try {
      const updated = await setLiveness(form);
      setSetting(updated);
      setForm(extractLimits(updated));
      toast.success("Liveness-Einstellungen gespeichert (live)");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  if (offline) {
    return (
      <p className="rounded-md border border-amber-500/40 bg-amber-500/10 p-2 text-xs text-amber-700 dark:text-amber-400">
        Liveness-Einstellungen nicht erreichbar — Backend offline oder Endpunkt
        (<code>/settings/liveness</code>) noch nicht gebaut.
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
          {setting.warning} — es greifen konservative Defaults.
        </p>
      ) : (
        setting && (
          <p className="text-xs text-muted-foreground">
            Quelle: <span className="font-mono">{setting.source}</span>. Der verifizierte
            Heartbeat erkennt Hänger hintergrund-getrieben; eine hängende Session wird
            (sofern aktiviert) über <strong>claude --resume</strong> reanimiert.
          </p>
        )
      )}

      {/* Globaler An/Aus-Schalter der Automatik */}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={form.enabled_auto_reanimation}
          onChange={(e) =>
            setForm({ ...form, enabled_auto_reanimation: e.target.checked })
          }
          className="size-4 accent-emerald-500"
        />
        Automatische Reanimierung aktiv
      </label>
      <p className="-mt-2 text-[11px] leading-snug text-muted-foreground">
        Aus = nur Indikator + manueller „Reaktivieren“-Knopf (keine Automatik).
      </p>

      <div className="grid gap-3 sm:grid-cols-2">
        {FIELDS.map((f) => {
          const disabled = f.autoOnly && !form.enabled_auto_reanimation;
          return (
            <div key={f.key} className="grid gap-1.5">
              <Label htmlFor={`lv_${f.key}`} className="text-xs">
                {f.label}
              </Label>
              <div className="flex items-center gap-2">
                <Input
                  id={`lv_${f.key}`}
                  type="number"
                  min={f.min}
                  value={String(form[f.key])}
                  disabled={disabled}
                  onChange={(e) =>
                    setForm({ ...form, [f.key]: Number(e.target.value) })
                  }
                  className="w-28"
                />
                <span className="text-xs text-muted-foreground">{f.unit}</span>
              </div>
              <p className="text-[11px] leading-snug text-muted-foreground">{f.hint}</p>
            </div>
          );
        })}
      </div>

      <div>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? "Speichert…" : "Speichern (live)"}
        </Button>
      </div>
    </div>
  );
}

function extractLimits(s: LivenessSetting): LivenessLimits {
  return {
    enabled_auto_reanimation: s.enabled_auto_reanimation,
    progress_timeout_seconds: s.progress_timeout_seconds,
    poll_interval_seconds: s.poll_interval_seconds,
    max_auto_attempts: s.max_auto_attempts,
    backoff_seconds: s.backoff_seconds,
  };
}
