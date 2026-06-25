"use client";

import { use, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Ampel } from "@/components/cockpit/ampel";
import { DecisionCard } from "@/components/cockpit/decision-card";
import { ThemeToggle } from "@/components/cockpit/theme-toggle";
import { ContextGauge } from "@/components/cockpit/context-gauge";
import { ThresholdBadge } from "@/components/cockpit/threshold-badge";
import { HandoverDialog } from "@/components/cockpit/handover-dialog";
import { ChallengeDialog } from "@/components/cockpit/challenge-dialog";
import { ReviewsPanel } from "@/components/cockpit/reviews-panel";
import { HeartbeatDot } from "@/components/cockpit/heartbeat-dot";
import { ReanimateButton } from "@/components/cockpit/reanimate-button";
import { ResetSessionButton } from "@/components/cockpit/reset-session-button";
import { SessionThresholdControl } from "@/components/cockpit/threshold-control";
import { SessionClipboardButton } from "@/components/cockpit/session-clipboard-button";
import { PushToTalkButton } from "@/components/cockpit/push-to-talk-button";
import { useFileUpload } from "@/components/cockpit/use-file-upload";
import { useNow } from "@/components/cockpit/sessions-provider";
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

export default function SessionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const now = useNow();
  const { state: liveState, liveText, connected } = useSessionStream(id, {
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
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  // PROJ-23: erhöht sich nach jedem Challenge-Start → ReviewsPanel lädt neu.
  const [reviewsKey, setReviewsKey] = useState(0);
  const logRef = useRef<HTMLDivElement>(null);
  // Surface B (PROJ-11): Datei anhängen → Upload in den Clipboard-Ordner →
  // absoluten Pfad ins Eingabefeld einfügen (referenzieren).
  const { upload, uploading } = useFileUpload();

  async function attachFiles(files: File[]) {
    const entries = await upload(files);
    if (entries.length === 0) return;
    const paths = entries.map((e) => e.path).join(" ");
    setInput((prev) => (prev.trim() ? `${prev.trimEnd()} ${paths} ` : `${paths} `));
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

  useEffect(() => {
    logRef.current?.scrollTo({ top: logRef.current.scrollHeight });
  }, [liveText, detail]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || busy) return;
    setBusy(true);
    try {
      await sendInput(id, input.trim());
      setInput("");
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
        <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
          ← Zurück zum Cockpit
        </Link>
        <p className="mt-6 text-red-400">{loadError}</p>
      </div>
    );
  }

  const meta = head ? statusMeta(head.status) : null;
  const ended = head?.status === "done" || head?.status === "error";
  // PROJ-4: Bei offener Decision Card ist die Eingabe gesperrt — erst entscheiden.
  // (Sonst verkeilt eine Eingabe mitten in der Freigabe die Session, Bug PROJ4-QA-1.)
  const hasPending = (head?.pending_decisions?.length ?? 0) > 0;

  return (
    <div className="mx-auto flex h-dvh max-w-4xl flex-col p-4 md:p-6">
      <div className="mb-3">
        <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
          ← Cockpit
        </Link>
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
        <h1 className="text-lg font-semibold" title={head ? displayName(head) : undefined}>
          {head ? displayName(head) : "Session"}
        </h1>
        {head && (
          <>
            <Badge variant="secondary">{modelLabel(head.model)}</Badge>
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
          {/* PROJ-23: Cross-Agent-Review auf einem Artefakt dieser Session starten. */}
          <ChallengeDialog
            sessionId={id}
            defaultPointer={head.contract_pointer}
            onStarted={() => setReviewsKey((k) => k + 1)}
          />
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

      {head && (
        <ContextGauge
          pct={head.context_fill_pct}
          known={head.context_known}
          threshold={head.context_fill_threshold_pct}
          className="pb-1"
        />
      )}

      {/* PROJ-27: Liveness-Banner — hängende/tote Sessions reanimieren, mit Rückmeldung. */}
      {head && canReanimate(head.liveness) && (
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

      {head?.status === "error" && head.error && (
        <p className="my-2 rounded bg-red-500/10 px-3 py-2 text-sm text-red-400">
          {head.error}
        </p>
      )}

      <div
        ref={logRef}
        className="my-3 flex-1 overflow-y-auto rounded-lg border border-border bg-card/30 p-4 font-mono text-sm leading-relaxed"
      >
        {detail?.transcript?.length ? (
          detail.transcript.map((t, i) => (
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

      {/* PROJ-23: Cross-Agent-Reviews dieser (Autor-)Session + ihre Befunde. */}
      {head && (
        <details className="mb-3 rounded-lg border border-border bg-card/30 p-3">
          <summary className="cursor-pointer text-xs font-medium text-indigo-500">
            Cross-Agent-Reviews
          </summary>
          <div className="mt-2">
            <ReviewsPanel sessionId={id} refreshKey={reviewsKey} />
          </div>
        </details>
      )}

      {/* Eingabe IMMER zeigen — an beendeten Sessions setzt eine Nachricht sie fort. */}
      {ended && (
        <p className="mb-2 text-xs text-muted-foreground">
          {head?.status === "error"
            ? "Session mit Fehler beendet"
            : "Session beendet"}{" "}
          — eine Nachricht setzt sie fort.
        </p>
      )}
      {hasPending && (
        <p className="mb-2 text-xs font-medium text-orange-500">
          Eingabe gesperrt — bitte erst die offene Freigabe oben entscheiden.
        </p>
      )}
      {/* items-stretch: Textarea übernimmt die Höhe der Button-Spalte (Symmetrie,
          PROJ-29). Die Buttons selbst bleiben h-8 und oben ausgerichtet; wächst die
          Textarea beim Tippen (field-sizing-content), wächst die Zeile mit. */}
      <form onSubmit={handleSend} className="flex items-stretch gap-2">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            hasPending
              ? "Erst Decision Card entscheiden…"
              : ended
                ? "Nachricht senden, um fortzusetzen…"
                : "Nachricht an die Session…"
          }
          rows={2}
          className="flex-1"
          disabled={hasPending}
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSend(e);
          }}
          onPaste={(e) => {
            // Datei aus der Zwischenablage (Screenshot) → anhängen statt einfügen.
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
        {/* PROJ-36: Drei Reihen statt vier — Reihe 1 Senden (voll), Reihe 2
            Mikrofon + Büroklammer (zwei Icon-Buttons nebeneinander), Reihe 3 Stop
            (voll). Höhe bleibt aus den Buttons abgeleitet → PROJ-29-Symmetrie hält. */}
        <div className="flex flex-col gap-2">
          <Button type="submit" disabled={!input.trim() || busy || hasPending}>
            {ended ? "Fortsetzen" : "Senden"}
          </Button>
          <div className="flex gap-2">
            {/* PROJ-20: Nachricht an die Session diktieren statt tippen. */}
            <PushToTalkButton
              className="flex-1"
              disabled={hasPending}
              onTranscript={(t) =>
                setInput((prev) => {
                  const base = prev.trimEnd();
                  return base ? `${base} ${t}` : t;
                })
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
