"use client";

// PROJ-20: Quelle der Spracheingabe-Transkription wählen.
// Standard = self-hosted Whisper auf dem VPS (DSGVO, keine laufenden Kosten).
// Cloud-Fallback (Groq) ist eine bewusste Entscheidung und nur wählbar, wenn
// im Backend ein API-Key konfiguriert ist (groq_available).

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ApiError, getTranscriptionSettings, setTranscriptionSettings } from "@/lib/api";
import type { TranscriptionSetting } from "@/lib/types";

export function TranscriptionControl() {
  const [setting, setSetting] = useState<TranscriptionSetting | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    const ac = new AbortController();
    getTranscriptionSettings(ac.signal)
      .then(setSetting)
      .catch(() => {
        /* Backend evtl. offline — Control bleibt leer. */
      });
    return () => ac.abort();
  }, []);

  async function apply(useGroq: boolean) {
    if (saving) return;
    setSaving(true);
    try {
      const updated = await setTranscriptionSettings(useGroq);
      setSetting(updated);
      toast.success(
        updated.use_groq ? "Transkription: Groq (Cloud)" : "Transkription: lokal (self-hosted)",
      );
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  const useGroq = setting?.use_groq ?? false;
  const groqAvailable = setting?.groq_available ?? false;

  return (
    <div className="grid gap-3">
      <div className="grid gap-2">
        <Label>Transkriptions-Quelle</Label>
        <div className="flex gap-2">
          <Button
            size="sm"
            variant={useGroq ? "outline" : "default"}
            onClick={() => apply(false)}
            disabled={saving}
          >
            Lokal (self-hosted)
          </Button>
          <Button
            size="sm"
            variant={useGroq ? "default" : "outline"}
            onClick={() => apply(true)}
            disabled={saving || !groqAvailable}
            title={groqAvailable ? undefined : "Kein Groq-API-Key konfiguriert"}
          >
            Groq (Cloud)
          </Button>
        </div>
      </div>

      {setting && (
        <p className="text-xs text-muted-foreground">
          Standard ist <span className="font-medium">lokal</span> auf dem VPS
          (Modell <span className="font-mono">{setting.model}</span>, Sprache{" "}
          <span className="font-mono">{setting.language}</span>) — keine Audiodaten verlassen das
          System.{" "}
          {groqAvailable
            ? "Groq ist ein schnellerer Cloud-Fallback (Audio wird dann an Groq gesendet)."
            : "Für den Groq-Fallback einen API-Key in der .env setzen (JUPITER_GROQ_API_KEY)."}
        </p>
      )}
      {!setting && (
        <p className="text-xs text-muted-foreground">Einstellung nicht verfügbar (Backend offline?).</p>
      )}
    </div>
  );
}
