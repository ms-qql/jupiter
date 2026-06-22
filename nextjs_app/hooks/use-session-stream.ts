"use client";

// Live-Stream einer EINZELNEN Session via WebSocket (/sessions/{id}/stream).
// Nur für die Detailansicht (Board nutzt Polling). Mit einfachem Reconnect.

import { useEffect, useRef, useState } from "react";
import { streamUrl } from "@/lib/api";
import type { Session } from "@/lib/types";

interface StreamResult {
  /** Letzter State-Snapshot vom Server (live, ohne Polling). */
  state: Session | null;
  /** Seit Verbindungsaufbau gestreamter Assistenten-Text. */
  liveText: string;
  connected: boolean;
}

export function useSessionStream(id: string): StreamResult {
  const [state, setState] = useState<Session | null>(null);
  const [liveText, setLiveText] = useState("");
  const [connected, setConnected] = useState(false);
  const closedByUs = useRef(false);

  useEffect(() => {
    closedByUs.current = false;
    let ws: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | null = null;

    const connect = () => {
      ws = new WebSocket(streamUrl(id));

      ws.onopen = () => setConnected(true);

      ws.onmessage = (ev) => {
        let msg: { kind?: string; role?: string; text?: string } & Partial<Session>;
        try {
          msg = JSON.parse(ev.data);
        } catch {
          return;
        }
        if (msg.kind === "state") {
          setState(msg as Session);
        } else if (msg.kind === "message" && msg.role === "assistant" && msg.text) {
          setLiveText((prev) => prev + msg.text);
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

  return { state, liveText, connected };
}
