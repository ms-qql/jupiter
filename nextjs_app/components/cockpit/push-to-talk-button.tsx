"use client";

// PROJ-20: Wiederverwendbarer Push-to-Talk-Button. Klick startet/stoppt die
// Aufnahme; das Transkript wird per Callback geliefert (Aufrufer fügt es ins
// Zielfeld ein — KEIN Auto-Submit, der Text bleibt editierbar). Drei sichtbare
// Zustände: idle (Mic), recording (Stopp, pulsierend), transcribing (Spinner).

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

  const label = transcribing
    ? "Transkribiert…"
    : recording
      ? "Aufnahme stoppen"
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
        <Loader2 className="size-4 animate-spin" />
      ) : recording ? (
        <Square className="size-4 fill-current" />
      ) : (
        <Mic className="size-4" />
      )}
    </Button>
  );
}
