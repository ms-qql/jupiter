"use client";

// PROJ-82: Polling-Intervall der Hermes-Kanban-Ansicht konfigurieren
// (GET/PATCH /settings/hermes-kanban). Wert in Sekunden, 5–60, Default 10.

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ApiError,
  getHermesKanbanSettings,
  setHermesKanbanSettings,
} from "@/lib/api";
import type { HermesKanbanSettings } from "@/lib/types";

export function HermesKanbanControl() {
  const [setting, setSetting] = useState<HermesKanbanSettings | null>(null);
  const [value, setValue] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    getHermesKanbanSettings(ac.signal)
      .then((s) => {
        setSetting(s);
        setValue(String(s.poll_interval_seconds));
      })
      .catch(() => {
        /* Backend evtl. offline — Control bleibt leer. */
      });
    return () => ac.abort();
  }, []);

  async function handleSave() {
    const secs = Number(value);
    if (Number.isNaN(secs) || saving) return;
    setSaving(true);
    try {
      const updated = await setHermesKanbanSettings(secs);
      setSetting(updated);
      setValue(String(updated.poll_interval_seconds));
      toast.success(`Hermes-Kanban-Intervall: ${updated.poll_interval_seconds} s`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="grid gap-2">
      <Label htmlFor="hk_poll_interval">Aktualisierungsintervall (Sekunden)</Label>
      <div className="flex items-center gap-2">
        <Input
          id="hk_poll_interval"
          type="number"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          className="w-24"
          min={5}
          max={60}
        />
        <span className="text-sm text-muted-foreground">s</span>
        <Button size="sm" onClick={handleSave} disabled={saving}>
          {saving ? "Speichert…" : "Speichern"}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Wie oft die Hermes-Kanban-Ansicht automatisch aktualisiert (5–60 s,
        Default 10). Änderungen wirken ohne Neustart.
      </p>
    </div>
  );
}
