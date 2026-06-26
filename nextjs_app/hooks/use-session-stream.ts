"use client";

// Live-Stream einer EINZELNEN Session via WebSocket (/sessions/{id}/stream).
// Nur für die Detailansicht (Board nutzt Polling). Mit einfachem Reconnect.

import { useEffect, useRef, useState } from "react";
import { streamUrl } from "@/lib/api";
import type { Session, TranscriptEntry } from "@/lib/types";

/** Server-Notice (PROJ-5): einmaliger Auto-Vorschlag beim Schwellen-Überschreiten. */
export interface ThresholdNotice {
  event: "threshold_reached";
  context_fill_pct: number;
  threshold_pct: number;
}

/** Live-Aktivitäts-Ticker (PROJ-46): jüngste Tool-Start-Aktion, transient. */
export interface LiveActivity {
  /** Tool-Name (z. B. "Edit", "Bash"); `null` = Ticker geleert (Session terminal). */
  tool: string | null;
  /** Knapper, serverseitig gekürzter Ziel-Hinweis (Datei/Kommando-Kopf). */
  target: string;
  /** ISO-Zeitstempel des Tool-Starts (oder `null` beim Leeren). */
  ts: string | null;
}

interface StreamResult {
  /** Letzter State-Snapshot vom Server (live, ohne Polling). */
  state: Session | null;
  /**
   * PROJ-49 B: Transkript-Baseline aus dem Connect-Snapshot. Nach JEDEM (Re-)Connect
   * liefert der Server den Vollzustand inkl. Transkript → verlustfreier Resync ohne
   * Re-Polling. `null`, bis der erste Snapshot eintraf (dann zählt `detail` der Seite).
   */
  transcript: TranscriptEntry[] | null;
  /** Seit dem letzten Snapshot gestreamter Assistenten-Text (wird beim Resync geleert). */
  liveText: string;
  /** PROJ-46: jüngste Tool-Aktion (transient); `null`, solange noch keine kam. */
  lastActivity: LiveActivity | null;
  connected: boolean;
}

interface StreamOptions {
  /** Wird bei einem `kind=notice`-Event gefeuert (z. B. Schwelle erreicht). */
  onNotice?: (notice: ThresholdNotice) => void;
}

export function useSessionStream(id: string, opts?: StreamOptions): StreamResult {
  const [state, setState] = useState<Session | null>(null);
  const [transcript, setTranscript] = useState<TranscriptEntry[] | null>(null);
  const [liveText, setLiveText] = useState("");
  const [lastActivity, setLastActivity] = useState<LiveActivity | null>(null);
  const [connected, setConnected] = useState(false);
  const closedByUs = useRef(false);
  // Callback in einem Ref halten → die WS-Verbindung hängt nicht an seiner Identität.
  const onNotice = useRef(opts?.onNotice);
  useEffect(() => {
    onNotice.current = opts?.onNotice;
  });

  useEffect(() => {
    closedByUs.current = false;
    let ws: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;
    // PROJ-49 A: Reconnect-Versuche zählen → Backoff statt Tight-Loop; bei `onopen`
    // zurückgesetzt, damit nach einer stabilen Phase wieder schnell reconnectet wird.
    let attempt = 0;

    const connect = () => {
      ws = new WebSocket(streamUrl(id));

      ws.onopen = () => {
        attempt = 0;
        setConnected(true);
      };

      ws.onmessage = (ev) => {
        let msg: {
          kind?: string;
          role?: string;
          text?: string;
          event?: string;
          tool?: string | null;
          target?: string;
          ts?: string | null;
          transcript?: TranscriptEntry[];
        } & Partial<Session>;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        if (msg.kind === "state") {
          setState(msg as Session);
          // PROJ-49 B: Nur der Connect-Snapshot trägt `transcript` (Live-`state`-
          // Broadcasts nicht) → als Baseline übernehmen und den seit-Snapshot-Strom
          // leeren. Idempotent: verpasste Chunks stecken bereits im Transkript,
          // also kein Verlust und keine Doppelung beim Reconnect.
          if (Array.isArray(msg.transcript)) {
            setTranscript(msg.transcript);
            setLiveText("");
          }
        } else if (msg.kind === "ping") {
          // PROJ-49 A1: Keepalive vom Server — bewusst ignorieren (kein UI-Effekt).
        } else if (msg.kind === "message" && msg.role === "assistant" && msg.text) {
          setLiveText((prev) => prev + msg.text);
        } else if (msg.kind === "activity") {
          // PROJ-46: leerer Stand (tool === null) = Session terminal → Ticker löschen.
          setLastActivity(
            msg.tool
              ? { tool: msg.tool, target: msg.target ?? "", ts: msg.ts ?? null }
              : null,
          );
        } else if (msg.kind === "notice" && msg.event === "threshold_reached") {
          onNotice.current?.(msg as unknown as ThresholdNotice);
        }
      };

      ws.onclose = (ev) => {
        setConnected(false);
        if (closedByUs.current) return;
        // PROJ-49 A3: Schließgrund protokollieren, um den Flapping-Auslöser
        // einzugrenzen (Client- vs. Server- vs. Proxy-seitiger Close anhand des Codes).
        if (process.env.NODE_ENV !== "production") {
          console.debug(
            `[ws ${id}] closed code=${ev.code} reason=${ev.reason || "—"} → reconnect #${attempt + 1}`,
          );
        }
        // Exponentieller Backoff mit Jitter (1s → max 15s) statt fixem Tight-Loop:
        // bremst einen Flapping-Sturm und übersteht kurze Netz-/Proxy-Aussetzer.
        const delay = Math.min(1000 * 2 ** attempt, 15000) + Math.random() * 500;
        attempt += 1;
        retry = setTimeout(connect, delay);
      };

      ws.onerror = () => ws?.close();
    };

    connect();

    return () => {
      closedByUs.current = true;
      if (retry) clearTimeout(retry);
      ws?.close();
    };
  }, [id]);

  return { state, transcript, liveText, lastActivity, connected };
}
