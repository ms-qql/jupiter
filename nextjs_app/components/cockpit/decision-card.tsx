"use client";

// Decision Card (PROJ-4) — die 5-Sekunden-Entscheidung: Was, Ausschnitt, Warum,
// Kontext + Freigeben / Ablehnen / Mit Kommentar zurück / In Session springen.

import { useState } from "react";
import Link from "next/link";
import { Lightbulb, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { ApiError, resolveDecision, stopSession } from "@/lib/api";
import { projectName } from "@/lib/status";
import type { AskUserQuestionInput, PendingDecision } from "@/lib/types";
import { QuestionCard } from "./question-card";
import { PushToTalkButton } from "./push-to-talk-button";

type CardProps = {
  decision: PendingDecision;
  /** „In Session springen" zeigen (auf der Detailseite überflüssig). */
  showJump?: boolean;
  className?: string;
};

export function DecisionCard(props: CardProps) {
  // PROJ-15: Wissens-Vorschlag → eigene, nicht-blockierende Karte (Freigeben/Editieren/Verwerfen).
  if (props.decision.card_type === "knowledge_proposal") {
    return <KnowledgeProposalCard {...props} />;
  }
  // Frage-Tool (AskUserQuestion) → lesbare Auswahl-Karte statt Approve/Deny-JSON.
  const questions = (props.decision.tool_input as AskUserQuestionInput | undefined)?.questions;
  if (props.decision.tool_name === "AskUserQuestion" && Array.isArray(questions) && questions.length) {
    return <QuestionCard {...props} questions={questions} />;
  }
  return <ApproveDenyCard {...props} />;
}

// PROJ-15 — Wissens-Vorschlag: aus einem erkannten Marker (Bug gelöst / ADR / Sackgasse)
// destilliert. Blockiert die Session NICHT (eigene smaragd-grüne Farbe, klar abgesetzt von
// der orangenen Freigabe-Card). Aktionen: Freigeben · Editieren · Verwerfen.
function KnowledgeProposalCard({ decision, showJump = true, className }: CardProps) {
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [title, setTitle] = useState(decision.proposal_title ?? decision.action);
  const [body, setBody] = useState(decision.proposal_body ?? "");

  const obsolete = decision.state === "obsolete";
  const proj = decision.context?.project_path ? projectName(decision.context.project_path) : null;

  async function approve() {
    if (busy) return;
    setBusy(true);
    try {
      // Bei „Editieren" die geänderte Fassung mitsenden, sonst den Vorschlag unverändert.
      const edited = editing ? { title: title.trim(), body } : undefined;
      await resolveDecision(decision.session_id, decision.decision_id, "approve", undefined, edited);
      toast.success("Ins kuratierte Wissen übernommen");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Übernehmen fehlgeschlagen");
      setBusy(false);
    }
  }

  async function discard() {
    if (busy) return;
    setBusy(true);
    try {
      await resolveDecision(decision.session_id, decision.decision_id, "deny");
      toast.success("Vorschlag verworfen");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Verwerfen fehlgeschlagen");
      setBusy(false);
    }
  }

  return (
    <div
      className={cn(
        "rounded-lg border p-3 ring-1",
        "border-emerald-500/50 bg-emerald-500/5 ring-emerald-500/20",
        obsolete && "border-border bg-muted/30 opacity-60 ring-0",
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <Badge
          variant="secondary"
          className="shrink-0 gap-1 border-emerald-500/40 bg-emerald-500/10 text-emerald-700 dark:text-emerald-400"
        >
          <Lightbulb className="size-3" />
          Wissens-Vorschlag
        </Badge>
        <span className="min-w-0 flex-1 break-words text-sm font-medium">
          {editing ? "Vorschlag bearbeiten" : (decision.proposal_title ?? decision.action)}
        </span>
      </div>

      <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
        {proj && <span className="font-mono">{proj}</span>}
        {decision.triggering_rule && <span>· {decision.triggering_rule}</span>}
      </div>

      {editing ? (
        <div className="mt-2 space-y-2">
          <Input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Titel der kuratierten Notiz"
            className="text-sm"
          />
          <Textarea
            value={body}
            onChange={(e) => setBody(e.target.value)}
            rows={8}
            placeholder="Kuratierter Inhalt (MD)…"
            className="font-mono text-[11px] leading-relaxed"
          />
        </div>
      ) : (
        <pre className="mt-2 max-h-56 overflow-auto rounded-md border border-border bg-background/60 p-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-words">
          {decision.proposal_body}
        </pre>
      )}

      {obsolete ? (
        <p className="mt-3 text-xs italic text-muted-foreground">
          Obsolet — die Session wurde beendet.
        </p>
      ) : (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <Button size="sm" disabled={busy} onClick={approve}>
            {editing ? "Editiert freigeben" : "Freigeben"}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            disabled={busy}
            onClick={() => setEditing((v) => !v)}
          >
            {editing ? "Abbrechen" : "Editieren"}
          </Button>
          <Button
            size="sm"
            variant="outline"
            disabled={busy}
            onClick={discard}
            className="border-red-500/40 text-red-600 hover:bg-red-500/10 dark:text-red-400"
          >
            Verwerfen
          </Button>
          {showJump && (
            <Link
              href={`/sessions/${decision.session_id}`}
              className="ml-auto text-xs text-muted-foreground hover:text-foreground"
            >
              In Session springen →
            </Link>
          )}
        </div>
      )}
    </div>
  );
}

function ApproveDenyCard({ decision, showJump = true, className }: CardProps) {
  const [busy, setBusy] = useState(false);
  const [commentOpen, setCommentOpen] = useState(false);
  const [comment, setComment] = useState("");

  const obsolete = decision.state === "obsolete";
  const cardType = decision.card_type ?? "normal";
  const isPhaseGate = cardType === "phase_transition";
  const isDeny = cardType === "deny"; // Aktion bereits blockiert — nur Kenntnisnahme
  const isWatchdog = cardType === "watchdog_pause"; // PROJ-16: Reißleine hat pausiert
  const isSelfRestart = cardType === "self_restart"; // PROJ-33: Host-/Backend-Neustart abgefangen

  async function decide(verdict: "approve" | "deny", withComment?: string) {
    if (busy) return;
    setBusy(true);
    try {
      await resolveDecision(decision.session_id, decision.decision_id, verdict, withComment);
      toast.success(
        verdict === "approve"
          ? isWatchdog
            ? "Fortgesetzt — Limit zurückgesetzt"
            : isSelfRestart
              ? "Neustart freigegeben"
              : "Freigegeben"
          : withComment
            ? "Mit Kommentar zurückgegeben"
            : "Abgelehnt",
      );
      // Board-Polling / WS blendet die Card danach automatisch aus.
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Entscheidung fehlgeschlagen");
      setBusy(false);
    }
  }

  // Watchdog-Aktion „Abbrechen" → Session stoppen (Prozess beenden, nicht nur pausieren).
  async function abort() {
    if (busy) return;
    setBusy(true);
    try {
      await stopSession(decision.session_id);
      toast.success("Session abgebrochen");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Abbrechen fehlgeschlagen");
      setBusy(false);
    }
  }

  const proj = decision.context?.project_path ? projectName(decision.context.project_path) : null;
  const phase = decision.context?.phase;
  const role = decision.context?.role;

  return (
    <div
      className={cn(
        "rounded-lg border p-3 ring-1",
        "border-orange-500/50 bg-orange-500/5 ring-orange-500/20",
        isPhaseGate && "border-violet-500/50 bg-violet-500/5 ring-violet-500/20",
        isDeny && "border-red-500/50 bg-red-500/5 ring-red-500/20",
        isWatchdog && "border-amber-500/60 bg-amber-500/10 ring-amber-500/30",
        isSelfRestart && "border-red-500/60 bg-red-500/10 ring-red-500/30",
        obsolete && "border-border bg-muted/30 opacity-60 ring-0",
        className,
      )}
    >
      {/* Was + Kontext */}
      <div className="flex items-start gap-2">
        <Badge
          variant="secondary"
          className={cn(
            "shrink-0 gap-1 border-orange-500/40 bg-orange-500/10 text-orange-600 dark:text-orange-400",
            isPhaseGate &&
              "border-violet-500/40 bg-violet-500/10 text-violet-600 dark:text-violet-400",
            isDeny && "border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400",
            isWatchdog &&
              "border-amber-500/50 bg-amber-500/15 text-amber-700 dark:text-amber-400",
            isSelfRestart &&
              "border-red-500/50 bg-red-500/15 text-red-700 dark:text-red-400",
          )}
        >
          {(isWatchdog || isSelfRestart) && <ShieldAlert className="size-3" />}
          {isPhaseGate
            ? "Phasenwechsel"
            : isDeny
              ? "Verboten"
              : isWatchdog
                ? "Watchdog"
                : isSelfRestart
                  ? "Host-Neustart"
                  : decision.tool_name}
        </Badge>
        <span className="min-w-0 flex-1 break-words text-sm font-medium">{decision.action}</span>
      </div>

      <div className="mt-1 flex flex-wrap gap-x-2 gap-y-0.5 text-[11px] text-muted-foreground">
        {proj && <span className="font-mono">{proj}</span>}
        {role && <span>· {role}</span>}
        {phase && <span>· {phase}</span>}
      </div>

      {/* Auslösende Policy-Regel (PROJ-10, Nachvollziehbarkeit) */}
      {decision.triggering_rule && (
        <p className="mt-1 text-[11px] text-muted-foreground">
          <span className="font-medium text-foreground/70">Regel: </span>
          {decision.triggering_rule}
        </p>
      )}

      {/* Relevanter Ausschnitt (Befehl/Diff) — NICHT das ganze Log. */}
      <pre className="mt-2 max-h-44 overflow-auto rounded-md border border-border bg-background/60 p-2 font-mono text-[11px] leading-relaxed whitespace-pre-wrap break-words">
        {decision.excerpt}
      </pre>

      {/* Warum */}
      {decision.rationale && (
        <p className="mt-2 line-clamp-4 text-xs text-muted-foreground">
          <span className="font-medium text-foreground/70">Warum: </span>
          {decision.rationale}
        </p>
      )}

      {obsolete ? (
        <p className="mt-3 text-xs italic text-muted-foreground">
          Obsolet — die Session wurde beendet.
        </p>
      ) : isDeny ? (
        // Deny: die Aktion wurde nie ausgeführt — nur Kenntnisnahme.
        <div className="mt-3 flex items-center gap-2">
          <Button size="sm" variant="outline" disabled={busy} onClick={() => decide("deny")}>
            Zur Kenntnis
          </Button>
          {showJump && (
            <Link
              href={`/sessions/${decision.session_id}`}
              className="ml-auto text-xs text-muted-foreground hover:text-foreground"
            >
              In Session springen →
            </Link>
          )}
        </div>
      ) : isWatchdog ? (
        // Watchdog (PROJ-16): Session ist pausiert (Prozess lebt). Reißleine-Aktionen.
        <>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={busy} onClick={() => decide("approve")}>
              Fortsetzen
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => setCommentOpen((v) => !v)}
            >
              Mit Kommentar korrigieren
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={abort}
              className="border-red-500/40 text-red-600 hover:bg-red-500/10 dark:text-red-400"
            >
              Abbrechen
            </Button>
            {showJump && (
              <Link
                href={`/sessions/${decision.session_id}`}
                className="ml-auto text-xs text-muted-foreground hover:text-foreground"
              >
                In Session springen →
              </Link>
            )}
          </div>
          {commentOpen && (
            <div className="mt-2">
              <Textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                placeholder="Korrektur — Claude sieht sie und setzt korrigiert fort…"
                className="text-sm"
                autoFocus
              />
              <div className="mt-1.5 flex justify-end">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy || !comment.trim()}
                  onClick={() => decide("deny", comment.trim())}
                >
                  Korrigiert fortsetzen
                </Button>
              </div>
            </div>
          )}
        </>
      ) : (
        <>
          {/* Aktionen */}
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={busy} onClick={() => decide("approve")}>
              {isPhaseGate ? "Phase freigeben" : isSelfRestart ? "Neustart freigeben" : "Freigeben"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => decide("deny")}
            >
              Ablehnen
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => setCommentOpen((v) => !v)}
            >
              Mit Kommentar zurück
            </Button>
            {showJump && (
              <Link
                href={`/sessions/${decision.session_id}`}
                className="ml-auto text-xs text-muted-foreground hover:text-foreground"
              >
                In Session springen →
              </Link>
            )}
          </div>

          {/* Kommentar-Eingabe (eingeklappt) */}
          {commentOpen && (
            <div className="mt-2">
              <Textarea
                value={comment}
                onChange={(e) => setComment(e.target.value)}
                rows={2}
                placeholder="Begründung — Claude sieht sie und passt die Aktion an…"
                className="text-sm"
                autoFocus
              />
              <div className="mt-1.5 flex items-center justify-between gap-2">
                {/* PROJ-20: Begründung diktieren statt tippen. */}
                <PushToTalkButton
                  className="size-8"
                  disabled={busy}
                  onTranscript={(t) =>
                    setComment((c) => (c.trimEnd() ? `${c.trimEnd()} ${t}` : t))
                  }
                />
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy || !comment.trim()}
                  onClick={() => decide("deny", comment.trim())}
                >
                  Mit Kommentar ablehnen
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
