"use client";

import { use, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Ampel } from "@/components/cockpit/ampel";
import { ThemeToggle } from "@/components/cockpit/theme-toggle";
import { useNow } from "@/components/cockpit/sessions-provider";
import { useSessionStream } from "@/hooks/use-session-stream";
import { ApiError, getSession, sendInput, stopSession } from "@/lib/api";
import { formatDuration, modelLabel, projectName, statusMeta } from "@/lib/status";
import type { SessionDetail } from "@/lib/types";

export default function SessionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = use(params);
  const now = useNow();
  const { state: liveState, liveText, connected } = useSessionStream(id);

  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const logRef = useRef<HTMLDivElement>(null);

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

  return (
    <div className="mx-auto flex h-dvh max-w-4xl flex-col p-4 md:p-6">
      <div className="mb-3">
        <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
          ← Cockpit
        </Link>
      </div>

      <header className="flex flex-wrap items-center gap-3 border-b border-border pb-3">
        {meta && <Ampel color={meta.ampel} />}
        <h1 className="text-lg font-semibold">
          {head ? projectName(head.project_path) : "Session"}
        </h1>
        {head && (
          <>
            <Badge variant="secondary">{modelLabel(head.model)}</Badge>
            <span className="text-sm text-muted-foreground">{meta?.label}</span>
            {head.role && (
              <span className="text-sm text-muted-foreground">· {head.role}</span>
            )}
            <span className="ml-auto text-xs text-muted-foreground">
              {connected ? "● live" : "○ getrennt"}
            </span>
          </>
        )}
        <ThemeToggle />
      </header>

      {head && (
        <div className="flex flex-wrap gap-x-4 gap-y-1 py-2 text-xs text-muted-foreground">
          <span className="font-mono">{head.project_path}</span>
          <span className="tabular-nums">
            Laufzeit {formatDuration(head.created_at, now)}
          </span>
          <span className="tabular-nums">
            Kontext {Math.round(head.context_fill_pct)}%
          </span>
          <span className="tabular-nums">${head.total_cost_usd.toFixed(4)}</span>
          <span className="tabular-nums">{head.num_turns} Turns</span>
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

      {/* Eingabe IMMER zeigen — an beendeten Sessions setzt eine Nachricht sie fort. */}
      {ended && (
        <p className="mb-2 text-xs text-muted-foreground">
          {head?.status === "error"
            ? "Session mit Fehler beendet"
            : "Session beendet"}{" "}
          — eine Nachricht setzt sie fort.
        </p>
      )}
      <form onSubmit={handleSend} className="flex items-end gap-2">
        <Textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            ended ? "Nachricht senden, um fortzusetzen…" : "Nachricht an die Session…"
          }
          rows={2}
          className="flex-1"
          onKeyDown={(e) => {
            if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) handleSend(e);
          }}
        />
        <div className="flex flex-col gap-2">
          <Button type="submit" disabled={!input.trim() || busy}>
            {ended ? "Fortsetzen" : "Senden"}
          </Button>
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
