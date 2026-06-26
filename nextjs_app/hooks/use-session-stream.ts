"use client";

// Live-Stream einer EINZELNEN Session via WebSocket (/sessions/{id}/stream).
// Nur für die Detailansicht (Board nutzt Polling). Mit einfachem Reconnect.

import { useEffect, useRef, useState } from "react";
import { streamUrl } from "@/lib/api";
import type { Session } from "@/lib/types";

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
  /** Seit Verbindungsaufbau gestreamter Assistenten-Text. */
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

    const connect = () => {
      ws = new WebSocket(streamUrl(id));

      ws.onopen = () => setConnected(true);

      ws.onmessage = (ev) => {
        let msg: {
          kind?: string;
          role?: string;
          text?: string;
          event?: string;
          tool?: string | null;
          target?: string;
          ts?: string | null;
        } & Partial<Session>;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        if (msg.kind === "state") {
          setState(msg as Session);
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

      ws.onclose = () => {
        setConnected(false);
        if (!closedByUs.current) {
          retry = setTimeout(connect, 2000);
        }
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

  return { state, liveText, lastActivity, connected };
}
