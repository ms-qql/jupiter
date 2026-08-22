"use client";

// PROJ-78: Wiederverwendbare EINZELNE Session-Ansicht (Header, Live-Status,
// Transkript, Composer, Decision Cards). Aus der früheren routegebundenen
// Detailseite extrahiert, damit der Arbeitsbereich sie 1–2× mounten kann.
// Entwurf kommt aus dem Workspace (pro Session, localStorage-fest); Senden
// leert ihn nur bei Erfolg.

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { XIcon } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Ampel } from "@/components/cockpit/ampel";
import { DecisionCard } from "@/components/cockpit/decision-card";
import { ThemeToggle } from "@/components/cockpit/theme-toggle";
import { ContextGauge } from "@/components/cockpit/context-gauge";
import { HermesContextUsage } from "@/components/cockpit/hermes-context-usage";
import { ThresholdBadge } from "@/components/cockpit/threshold-badge";
import { HandoverDialog } from "@/components/cockpit/handover-dialog";
import { HeartbeatDot } from "@/components/cockpit/heartbeat-dot";
import { ActivityTicker } from "@/components/cockpit/activity-ticker";
import { ReanimateButton } from "@/components/cockpit/reanimate-button";
import { ResetSessionButton } from "@/components/cockpit/reset-session-button";
import { SessionThresholdControl } from "@/components/cockpit/threshold-control";
import { SessionClipboardButton } from "@/components/cockpit/session-clipboard-button";
import { PushToTalkButton } from "@/components/cockpit/push-to-talk-button";
import { useFileUpload } from "@/components/cockpit/use-file-upload";
import { useNow } from "@/components/cockpit/sessions-provider";
import { useWorkspace, type PaneIndex } from "@/components/cockpit/workspace-provider";
import { useSessionStream } from "@/hooks/use-session-stream";
import { ApiError, getSession, sendInput, stopSession } from "@/lib/api";
import {
  canReanimate,
  contextLabel,
  displayName,
  formatDuration,
  modelLabel,
  statusMeta,
} from "@/lib/status";
import { cn } from "@/lib/utils";
import type { SessionDetail } from "@/lib/types";

export function SessionView({ id, paneIndex }: { id: string; paneIndex: PaneIndex }) {
  const now = useNow();
  const { draft, setDraft, clearDraft, focus, close } = useWorkspace();
  const {
    state: liveState,
    transcript: liveTranscript,
    liveText,
    lastActivity,
    connected,
  } = useSessionStream(id, {
    onNotice: (n) => {
      if (n.event === "threshold_reached") {
        toast.warning(
          `Kontext-Schwelle (${n.threshold_pct}%) erreicht — Handover empfohlen.`,
        );
      }
    },
  });

  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const input = draft(id);
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);
  // Surface B (PROJ-11): Datei anhängen → Upload in den Clipboard-Ordner →
  // absoluten Pfad ins Eingabefeld einfügen (referenzieren).
  const { upload, uploading } = useFileUpload();

  async function attachFiles(files: File[]) {
    const entries = await upload(files);
    if (entries.length === 0) return;
    const paths = entries.map((e) => e.path).join(" ");
    setDraft(id, input.trim() ? `${input.trimEnd()} ${paths} ` : `${paths} `);
    toast.success(
      entries.length === 1
        ? "Datei angehängt — Pfad eingefügt"
        : `${entries.length} Dateien angehängt — Pfade eingefügt`,
    );
  }

  useEffect(() => {
    let active = true;
    getSession(id)
      .then((d) => active && setDetail(d))
      .catch(
        (e) =>
          active &&
          setLoadError(e instanceof ApiError ? e.message : "Nicht erreichbar"),
      );
    return () => {
      active = false;
    };
  }, [id]);

  // Header bevorzugt den Live-State, fällt sonst auf den initialen Detail-Load.
  const head = liveState ?? detail;
  // PROJ-49 B: Transkript bevorzugt aus dem WS-Snapshot (resync-fest nach jedem
  // Reconnect), Fallback auf den initialen REST-Load bis der erste Snapshot da ist.
  const transcript = liveTranscript ?? detail?.transcript ?? [];

  // PROJ-49: „getrennt"-Hinweis erst zeigen, wenn die WS schon einmal stand —
  // unterdrückt den kurzen Flash beim allerersten Verbindungsaufbau.
  const [everConnected, setEverConnected] = useState(false);
  if (connected && !everConnected) setEverConnected(true);

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [liveText, transcript.length]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || busy) return;
    setBusy(true);
    try {
      await sendInput(id, input.trim());
      // Nur bei Erfolg leeren — ein Fehler lässt den Entwurf erhalten (PROJ-78).
      clearDraft(id);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Senden fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleStop() {
    try {
      await stopSession(id);
      toast.success("Session gestoppt");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Stoppen fehlgeschlagen");
    }
  }

  if (loadError && !detail) {
    return (
      <div className="p-6">
        <p className="text-red-400">{loadError}</p>
      </div>
    );
  }

  const meta = head ? statusMeta(head.status) : null;
  const ended = head?.status === "done" || head?.status === "error";
  // PROJ-4: Bei offener Decision Card ist die Eingabe gesperrt — erst entscheiden.
  const hasPending = (head?.pending_decisions?.length ?? 0) > 0;

  return (
    <div className="flex h-full flex-col p-4 md:p-6">
      <div className="mb-3 flex items-center justify-between">
        {/* PROJ-78: Klick aktiviert diese Ansicht (Workspace) — Aktiv machen. */}
        <button
          type="button"
          onClick={() => focus(paneIndex)}
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ⇥ Aktiv machen
        </button>
        <button
          type="button"
          onClick={() => close(id)}
          aria-label="Session-Ansicht schließen"
          title="Ansicht schließen (Session läuft weiter)"
          className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <XIcon className="size-4" />
        </button>
      </div>

      <header className="flex flex-wrap items-center gap-3 border-b border-border pb-3">
        {meta && <Ampel color={meta.ampel} />}
        {head && (
          <HeartbeatDot
            liveness={head.liveness}
            autoAttempts={head.liveness_auto_attempts}
            size="md"
          />
        )}
        <h1
          className="text-lg font-semibold"
          title={head ? displayName(head) : undefined}
        >
          {head ? displayName(head) : "Session"}
        </h1>
        {head && (
          <>
            <Badge variant="secondary">{modelLabel(head.model)}</Badge>
            {head.engine === "hermes" && (
              <Badge variant="outline" className="text-[10px] uppercase">
                Hermes
              </Badge>
            )}
            <span className="text-sm text-muted-foreground">{meta?.label}</span>
            {head.role && (
              <span className="text-sm text-muted-foreground">· {head.role}</span>
            )}
            {head.threshold_warning && (
              <ThresholdBadge thresholdPct={head.context_fill_threshold_pct} />
            )}
            <span className="ml-auto text-xs text-muted-foreground">
              {connected ? "● live" : "○ getrennt"}
            </span>
          </>
        )}
        <ThemeToggle />
      </header>

      {head && (
        <div className="flex flex-wrap items-center gap-2 border-b border-border py-2">
          <HandoverDialog sessionId={id} />
          {/* Bereits zurückgesetzte Stränge haben genau einen Nachfolger → kein zweiter Reset. */}
          {!head.child_session_id && (
            <ResetSessionButton sessionId={id} numTurns={head.num_turns} />
          )}
          {head.parent_session_id && (
            <Link
              href={`/sessions/${head.parent_session_id}`}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              ← Vorgänger-Session
            </Link>
          )}
          {head.child_session_id && (
            <Link
              href={`/sessions/${head.child_session_id}`}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              Nachfolger-Session →
            </Link>
          )}
        </div>
      )}

      {head && (
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 py-2 text-xs text-muted-foreground">
          <span className="font-mono">{head.project_path}</span>
          <span className="tabular-nums">
            Laufzeit {formatDuration(head.created_at, now)}
          </span>
          <span className="tabular-nums">
            Kontext {contextLabel(head.context_fill_pct, head.context_known)}
          </span>
          <span className="tabular-nums">${head.total_cost_usd.toFixed(4)}</span>
          <span className="tabular-nums">{head.num_turns} Turns</span>
          <span className="ml-auto flex items-center gap-1.5">
            <span>Schwelle</span>
            <SessionThresholdControl
              sessionId={id}
              effective={head.context_fill_threshold_pct}
              onChange={(s) => setDetail((d) => (d ? { ...d, ...s } : d))}
            />
          </span>
        </div>
      )}

      {head && head.engine === "hermes" && (
        <div className="border-b border-border py-2">
          <HermesContextUsage
            available={head.context_usage_available}
            used={head.context_used_tokens}
            window={head.context_window_tokens}
          />
        </div>
      )}

      {head && (
        <ContextGauge
          pct={head.context_fill_pct}
          known={head.context_known}
          threshold={head.context_fill_threshold_pct}
          className="pb-1"
        />
      )}

      {/* PROJ-46: Live-Aktivitäts-Ticker — zeigt die jüngste Tool-Aktion + Text-Schnipsel. */}
      <ActivityTicker lastActivity={lastActivity} liveText={liveText} className="my-1" />

      {/* PROJ-27: Liveness-Banner — hängende/tote Sessions reanimieren.
          PROJ-86: für Hermes ausgeblendet (kein tmux, keine Reanimation). */}
      {head && head.engine !== "hermes" && canReanimate(head.liveness) && (
        <div
          className={cn(
            "my-2 flex flex-wrap items-center gap-x-3 gap-y-1.5 rounded-md border px-3 py-2 text-sm",
            head.liveness === "hängt"
              ? "border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400"
              : "border-zinc-500/40 bg-zinc-500/10 text-muted-foreground",
          )}
        >
          <HeartbeatDot
            liveness={head.liveness}
            autoAttempts={head.liveness_auto_attempts}
            size="md"
          />
          <span>
            {head.liveness === "hängt"
              ? "Diese Session hängt — der Prozess lebt, macht aber keinen Fortschritt."
              : "Session beendet/nicht steuerbar."}
            {head.liveness_auto_attempts > 0 &&
              ` Automatische Reanimierung ${head.liveness_auto_attempts}× versucht.`}
          </span>
          {head.liveness_last_result === "läuft_wieder" && (
            <span className="font-medium text-emerald-600 dark:text-emerald-400">
              ✓ läuft wieder
            </span>
          )}
          {head.liveness_last_result === "fehlgeschlagen" && (
            <span className="font-medium text-red-600 dark:text-red-400">
              Reanimation fehlgeschlagen
            </span>
          )}
          <ReanimateButton sessionId={id} variant="full" className="ml-auto" />
        </div>
      )}

      {/* PROJ-62: neben echten Fehlern auch den stillen PROJ-60-Fallback zeigen. */}
      {(head?.status === "error" || head?.liveness === "tot") && head?.error && (
        <p className="my-2 rounded bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {head.error}
        </p>
      )}

      {/* PROJ-86: Hermes wartet vor dem ersten Turn und zwischen Turns auf Eingabe. */}
      {head && head.engine === "hermes" && head.status === "waiting" && (
        <p className="my-2 rounded border border-border bg-card/40 px-3 py-2 text-sm text-muted-foreground">
          Wartet auf Eingabe
        </p>
      )}

      {/* PROJ-49: Verbindungs-Status sichtbar. */}
      {everConnected && !connected && (
        <div
          role="status"
          className="my-1 flex items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-1.5 text-sm text-amber-700 dark:text-amber-400"
        >
          <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-amber-500" />
          Verbindung getrennt — verbinde neu … (Stand wird beim Reconnect nachgeladen)
        </div>
      )}

      <div
        ref={logRef}
        className="my-3 flex-1 overflow-y-auto rounded-lg border border-border bg-card/30 p-4 font-mono text-sm leading-relaxed"
      >
        {transcript.length ? (
          transcript.map((t, i) => (
            <div key={i} className="mb-3">
              <span className="text-xs uppercase tracking-wide text-muted-foreground">
                {t.role}
              </span>
              <p className="whitespace-pre-wrap">{t.text}</p>
            </div>
          ))
        ) : (
          <p className="text-muted-foreground">Noch keine Transkript-Historie.</p>
        )}
        {liveText && (
          <div className="mb-3">
            <span className="text-xs uppercase tracking-wide text-emerald-500">
              assistant · live
            </span>
            <p className="whitespace-pre-wrap">{liveText}</p>
          </div>
        )}
      </div>

      {/* Offene Decision Cards (PROJ-4): blockieren mitten im Turn auf deine Freigabe. */}
      {head?.pending_decisions && head.pending_decisions.length > 0 && (
        <div className="mb-3 flex flex-col gap-2">
          <p className="text-xs font-medium text-orange-500">
            Freigabe nötig — die Session wartet auf dich:
          </p>
          {head.pending_decisions.map((d) => (
            <DecisionCard key={d.decision_id} decision={d} showJump={false} />
          ))}
        </div>
      )}

      {/* Eingabe IMMER zeigen — an beendeten Sessions setzt eine Nachricht sie fort.
          PROJ-86: Hermes-Fehler impliziert KEINEN Resume (kein neuer Chat). */}
      {ended && (
        <p className="mb-2 text-xs text-muted-foreground">
          {head?.status === "error"
            ? head?.engine === "hermes"
              ? "Session mit Fehler beendet."
              : "Session mit Fehler beendet — eine Nachricht setzt sie fort."
            : "Session beendet — eine Nachricht setzt sie fort."}
        </p>
      )}
      {hasPending && (
        <p className="mb-2 text-xs font-medium text-orange-500">
          Eingabe gesperrt — bitte erst die offene Freigabe oben entscheiden.
        </p>
      )}
      <form onSubmit={handleSend} className="flex items-stretch gap-2">
        <Textarea
          value={input}
          onChange={(e) => setDraft(id, e.target.value)}
          placeholder={
            hasPending
              ? "Erst Decision Card entscheiden…"
              : ended
                ? head?.engine === "hermes"
                  ? "Nachricht an Hermes senden…"
                  : "Nachricht senden, um fortzusetzen…"
                : "Nachricht an die Session…"
          }
          rows={2}
          className="flex-1"
          disabled={hasPending}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSend(e);
          }}
          onPaste={(e) => {
            const files = Array.from(e.clipboardData.files);
            if (files.length) {
              e.preventDefault();
              attachFiles(files);
            }
          }}
          onDrop={(e) => {
            const files = Array.from(e.dataTransfer.files);
            if (files.length) {
              e.preventDefault();
              attachFiles(files);
            }
          }}
          onDragOver={(e) => {
            if (e.dataTransfer.types.includes("Files")) e.preventDefault();
          }}
        />
        <div className="flex flex-col gap-2">
          <Button type="submit" disabled={!input.trim() || busy || hasPending}>
            {ended && head?.engine !== "hermes" ? "Fortsetzen" : "Senden"}
          </Button>
          <div className="flex gap-2">
            <PushToTalkButton
              className="flex-1"
              disabled={hasPending}
              onTranscript={(t) =>
                setDraft(
                  id,
                  input.trimEnd() ? `${input.trimEnd()} ${t}` : t,
                )
              }
            />
            <SessionClipboardButton
              className="flex-1"
              onPick={attachFiles}
              disabled={hasPending}
              uploading={uploading}
            />
          </div>
          {!ended && (
            <Button type="button" variant="outline" onClick={handleStop}>
              Stop
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
