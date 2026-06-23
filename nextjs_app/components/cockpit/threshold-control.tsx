"use client";

// Kontext-Schwelle konfigurieren (PROJ-5). Zwei Varianten:
//  - ThresholdControl: globaler Default (GET/PATCH /settings/threshold).
//  - SessionThresholdControl: pro-Session-Override (PATCH /sessions/{id}/threshold,
//    null = globalen Wert nutzen). Der Server klemmt jeden Wert auf [min, max].

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ApiError,
  getThreshold,
  setSessionThreshold,
  setThreshold,
} from "@/lib/api";
import type { Session, ThresholdSetting } from "@/lib/types";

export function ThresholdControl() {
  const [setting, setSetting] = useState<ThresholdSetting | null>(null);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    getThreshold(ac.signal)
      .then((s) => {
        setSetting(s);
        setValue(String(s.threshold_pct));
      })
      .catch(() => {
        /* Backend evtl. offline — Control bleibt leer. */
      });
    return () => ac.abort();
  }, []);

  async function handleSave() {
    const pct = Number(value);
    if (Number.isNaN(pct) || saving) return;
    setSaving(true);
    try {
      const updated = await setThreshold(pct);
      setSetting(updated);
      setValue(String(updated.threshold_pct));
      toast.success(`Globale Schwelle: ${updated.threshold_pct}%`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-2">
      <Label htmlFor="global_threshold">Kontext-Schwelle (global)</Label>
      <div className="flex items-center gap-2">
        <Input
          id="global_threshold"
          type="number"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="w-24"
          min={setting?.min_pct}
          max={setting?.max_pct}
        />
        <span className="text-sm text-muted-foreground">%</span>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? "Speichert…" : "Speichern"}
        </Button>
      </div>
      {setting && (
        <p className="text-xs text-muted-foreground">
          Erlaubt {setting.min_pct}–{setting.max_pct} % (Werte außerhalb werden geklemmt).
          Ab dieser Füllung schlägt Jupiter ein Handover vor.
        </p>
      )}
    </div>
  );
}

export function SessionThresholdControl({
  sessionId,
  effective,
  onChange,
}: {
  sessionId: string;
  effective: number;
  onChange?: (s: Session) => void;
}) {
  const [value, setValue] = useState(String(effective));
  const [busy, setBusy] = useState(false);

  // Effektiven Wert übernehmen, wenn er sich serverseitig ändert (z. B. globaler Wechsel) —
  // Reset-on-prop-change ohne Effekt (React-empfohlenes Muster).
  const [prevEffective, setPrevEffective] = useState(effective);
  if (effective !== prevEffective) {
    setPrevEffective(effective);
    setValue(String(effective));
  }

  async function apply(pct: number | null) {
    if (busy) return;
    setBusy(true);
    try {
      const updated = await setSessionThreshold(sessionId, pct);
      setValue(String(updated.context_fill_threshold_pct));
      onChange?.(updated);
      toast.success(
        pct === null
          ? "Schwelle: globaler Wert"
          : `Session-Schwelle: ${updated.context_fill_threshold_pct}%`,
      );
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex items-center gap-1.5">
      <Input
        type="number"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        className="h-7 w-16 text-xs"
        aria-label="Kontext-Schwelle dieser Session (%)"
      />
      <Button
        size="sm"
        variant="outline"
        className="h-7"
        onClick={() => apply(Number(value))}
        disabled={busy || Number.isNaN(Number(value))}
      >
        Setzen
      </Button>
      <Button
        size="sm"
        variant="ghost"
        className="h-7 text-muted-foreground"
        onClick={() => apply(null)}
        disabled={busy}
        title="Auf globale Schwelle zurücksetzen"
      >
        Global
      </Button>
    </div>
  );
}
