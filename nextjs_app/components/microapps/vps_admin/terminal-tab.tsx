"use client";

// PROJ-43: Terminal-Tab der VPS-Admin-Micro-App. Bettet die von `ttyd` servierte
// Shell per iFrame ein und nutzt dafür das vorhandene Einbettungs-Muster
// (EmbedTab: Sandbox + „Erneut laden" + „In neuem Tab öffnen"-Fallback).
//
// Davor liegt ein Erreichbarkeits-Gate (GET /terminal/info): es trennt sauber
// „Terminal nicht konfiguriert" (enabled=false, vor /abc-deploy) und „Dienst
// gestoppt" (reachable=false, TCP-Probe) von „Einbettung verweigert" (greift
// dann der EmbedTab-onError-Fallback) — kein Crash, keine leere Fläche.

import { useCallback, useEffect, useState } from "react";
import { RotateCwIcon, TerminalIcon } from "lucide-react";
import { getTerminalInfo, ApiError } from "@/lib/api";
import type { EngineRead, TerminalInfo } from "@/lib/types";
import { EmbedTab } from "@/components/cockpit/embed-tab";

// Scripts → xterm.js; same-origin → WebSocket + lokale ttyd-Einstellungen;
// Clipboard → Copy/Paste im Terminal. same-origin ist unbedenklich, da wir ttyd
// selbst betreiben (gleiche Origin via Caddy-Reverse-Proxy).
const TERMINAL_SANDBOX =
  "allow-scripts allow-same-origin allow-clipboard-read allow-clipboard-write";

export function TerminalTab() {
  const [info, setInfo] = useState<TerminalInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // Erhöhen → erneuter /terminal/info-Abruf + frischer iFrame-Mount (Retry).
  const [reloadKey, setReloadKey] = useState(0);

  // `loading` startet true; danach genügt das Setzen in finally(). Kein
  // synchrones setState im Effect (sonst Kaskaden-Render). Beim Retry bleibt der
  // letzte Zustand stehen, bis das neue /terminal/info eintrifft (kein Flackern).
  const probe = useCallback((signal?: AbortSignal) => {
    getTerminalInfo(signal)
      .then((i) => {
        setInfo(i);
        setErrorMsg(null);
      })
      .catch((err) => {
        if (signal?.aborted) return;
        setInfo(null);
        setErrorMsg(err instanceof ApiError ? err.message : "Nicht erreichbar");
      })
      .finally(() => {
        if (!signal?.aborted) setLoading(false);
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    probe(ctrl.signal);
    return () => ctrl.abort();
  }, [probe, reloadKey]);

  const retry = () => setReloadKey((k) => k + 1);

  // --- Lade-Zustand (nur initial, kein Flackern beim Retry) ------------------
  if (loading && !info) {
    return (
      <div className="flex h-full items-center justify-center p-12 text-sm text-muted-foreground">
        Terminal wird geprüft …
      </div>
    );
  }

  // --- /terminal/info nicht abrufbar (Backend aus / Route fehlt) -------------
  if (errorMsg) {
    return (
      <TerminalNotice
        title="Terminal nicht erreichbar"
        body={`Der Terminal-Dienst lässt sich nicht prüfen (${errorMsg}). Läuft das Backend bzw. der ttyd-Dienst auf dem VPS?`}
        onRetry={retry}
      />
    );
  }

  // --- Kein Terminal konfiguriert (enabled=false, vor /abc-deploy) -----------
  if (info && !info.enabled) {
    return (
      <TerminalNotice
        title="Terminal nicht konfiguriert"
        body="Es ist noch keine Terminal-Adresse hinterlegt. Der ttyd-Dienst wird beim Deploy eingerichtet und über JUPITER_TERMINAL_URL aktiviert."
      />
    );
  }

  // --- Dienst gestoppt/abgestürzt (reachable=false) -------------------------
  if (info && (!info.reachable || !info.url)) {
    return (
      <TerminalNotice
        title="Terminal nicht erreichbar"
        body="Der ttyd-Dienst ist gerade gestoppt oder startet neu. Sobald er wieder läuft, „Erneut versuchen“."
        onRetry={retry}
      />
    );
  }

  // --- Bereit → iFrame auf die ttyd-Shell (EmbedTab-Reuse) -------------------
  // Minimales engine-förmiges Objekt: erbt Sandbox, „Erneut laden", „In neuem
  // Tab öffnen"-Fallback und die X-Frame-Hinweiszeile ohne Duplizierung.
  const engine: EngineRead = {
    key: "vps_terminal",
    label: "Terminal",
    kind: "iframe",
    driver: null,
    available: true,
    unavailable_reason: null,
    models: [],
    default_model: null,
    capabilities: [],
    url: info!.url,
    sandbox: TERMINAL_SANDBOX,
    target: null,
    group: null,
    icon: "terminal",
  };

  // key={reloadKey} → „Erneut versuchen" remountet auch den iFrame (frische
  // WebSocket). Solange reachable bleibt, läuft kein Re-Probe → der iFrame bleibt
  // beim Dashboard↔Terminal-Wechsel stabil (Persistenz via tmux serverseitig).
  return (
    <div key={reloadKey} className="h-full">
      <EmbedTab engine={engine} fullHeight />
    </div>
  );
}

/** Zentriertes Hinweis-Panel für die Nicht-bereit-Zustände (deutsch). */
function TerminalNotice({
  title,
  body,
  onRetry,
}: {
  title: string;
  body: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex h-full items-center justify-center p-6">
      <div className="mx-auto max-w-md rounded-xl border border-border bg-card p-6 text-center">
        <TerminalIcon className="mx-auto mb-3 size-8 text-muted-foreground" />
        <h2 className="text-base font-semibold">{title}</h2>
        <p className="mt-2 text-sm text-muted-foreground">{body}</p>
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 inline-flex items-center gap-1.5 rounded-md border border-border bg-card px-3 py-2 text-sm font-medium transition-colors hover:border-foreground/30"
          >
            <RotateCwIcon className="size-3.5" />
            Erneut versuchen
          </button>
        )}
      </div>
    </div>
  );
}
