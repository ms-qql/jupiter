"use client";

// PROJ-20: Push-to-Talk-Aufnahme via MediaRecorder. Kapselt Mikrofon-Zugriff,
// Aufnahme, Auto-Stop (Längenlimit) und die Transkription über das Backend
// (self-hosted Whisper bzw. optional Groq — die Engine wählt der Server).
// Bewusst KEINE Browser Web Speech API (würde Audio an Google senden).

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { ApiError, transcribeAudio } from "@/lib/api";

export type PttStatus = "idle" | "recording" | "transcribing";

const DEFAULT_MAX_SECONDS = 120;

export function usePushToTalk({
  onTranscript,
  maxSeconds = DEFAULT_MAX_SECONDS,
}: {
  onTranscript: (text: string) => void;
  maxSeconds?: number;
}) {
  const [status, setStatus] = useState<PttStatus>("idle");
  const [error, setError] = useState<string | null>(null);

  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const streamRef = useRef<MediaStream | null>(null);
  const autoStopRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const cleanup = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (autoStopRef.current) {
      clearTimeout(autoStopRef.current);
      autoStopRef.current = null;
    }
  }, []);

  // Klare Meldung + sichtbarer Zustand: Tippen bleibt immer möglich.
  const fail = useCallback((msg: string) => {
    setError(msg);
    toast.error(msg);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    if (typeof navigator === "undefined" || !navigator.mediaDevices?.getUserMedia) {
      fail("Mikrofon wird vom Browser nicht unterstützt — bitte tippen.");
      return;
    }
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (err) {
      const name = err instanceof DOMException ? err.name : "";
      fail(
        name === "NotAllowedError" || name === "SecurityError"
          ? "Mikrofon-Zugriff verweigert — Tippen bleibt möglich."
          : name === "NotFoundError"
            ? "Kein Mikrofon gefunden — Tippen bleibt möglich."
            : "Mikrofon konnte nicht geöffnet werden.",
      );
      return;
    }

    streamRef.current = stream;
    chunksRef.current = [];
    const rec = new MediaRecorder(stream);
    recorderRef.current = rec;

    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };
    rec.onstop = async () => {
      cleanup();
      const blob = new Blob(chunksRef.current, { type: rec.mimeType || "audio/webm" });
      chunksRef.current = [];
      if (blob.size === 0) {
        setStatus("idle");
        return;
      }
      setStatus("transcribing");
      try {
        const result = await transcribeAudio(blob);
        const text = result.transcript.trim();
        if (text) onTranscript(text);
        else fail("Keine Sprache erkannt — bitte erneut versuchen.");
      } catch (err) {
        fail(err instanceof ApiError ? err.message : "Transkription fehlgeschlagen.");
      } finally {
        setStatus("idle");
      }
    };

    rec.start();
    setStatus("recording");
    // Längenlimit: lange Aufnahmen werden automatisch beendet (Edge Case).
    autoStopRef.current = setTimeout(() => {
      if (recorderRef.current?.state === "recording") {
        toast.info(`Aufnahme nach ${maxSeconds}s automatisch beendet.`);
        recorderRef.current.stop();
      }
    }, maxSeconds * 1000);
  }, [cleanup, fail, maxSeconds, onTranscript]);

  const stop = useCallback(() => {
    if (recorderRef.current?.state === "recording") recorderRef.current.stop();
  }, []);

  const toggle = useCallback(() => {
    if (status === "recording") stop();
    else if (status === "idle") void start();
  }, [status, start, stop]);

  // Beim Unmount laufende Aufnahme sauber stoppen (Mikrofon freigeben).
  useEffect(() => cleanup, [cleanup]);

  return { status, error, toggle, start, stop };
}
