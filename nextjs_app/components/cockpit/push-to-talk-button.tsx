"use client";

// PROJ-20: Wiederverwendbarer Push-to-Talk-Button. Klick startet/stoppt die
// Aufnahme; das Transkript wird per Callback geliefert (Aufrufer fügt es ins
// Zielfeld ein — KEIN Auto-Submit, der Text bleibt editierbar). Drei sichtbare
// Zustände: idle (Mic), recording (Stopp, pulsierend), transcribing (Spinner).

import { useEffect, useState } from "react";
import { Loader2, Mic, Square } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { usePushToTalk } from "./use-push-to-talk";

export function PushToTalkButton({
  onTranscript,
  disabled = false,
  maxSeconds,
  className,
  title = "Diktieren (Push-to-Talk)",
}: {
  onTranscript: (text: string) => void;
  disabled?: boolean;
  maxSeconds?: number;
  className?: string;
  title?: string;
}) {
  const { status, error, toggle } = usePushToTalk({ onTranscript, maxSeconds });
  const recording = status === "recording";
  const transcribing = status === "transcribing";

  // Laufende Sekunden sichtbar machen: Aufnahme und Transkription dauern spürbar,
  // ein reiner Spinner sieht sonst aus wie ein hängender Button.
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    if (status === "idle") return;
    const startedAt = Date.now();
    const id = setInterval(
      () => setSeconds(Math.round((Date.now() - startedAt) / 1000)),
      1000,
    );
    return () => {
      clearInterval(id);
      setSeconds(0);
    };
  }, [status]);

  const label = transcribing
    ? `Transkribiert… ${seconds}s`
    : recording
      ? `Aufnahme stoppen (${seconds}s)`
      : title;

  return (
    <Button
      type="button"
      size="icon"
      variant={recording ? "destructive" : "outline"}
      onClick={toggle}
      disabled={disabled || transcribing}
      aria-label={label}
      aria-pressed={recording}
      title={error ?? label}
      className={cn("shrink-0", recording && "animate-pulse", className)}
    >
      {transcribing ? (
        <span className="flex items-center gap-1">
          <Loader2 className="size-4 animate-spin" />
          <span className="text-[10px] tabular-nums">{seconds}s</span>
        </span>
      ) : recording ? (
        <Square className="size-4 fill-current" />
      ) : (
        <Mic className="size-4" />
      )}
    </Button>
  );
}
