"use client";

// Frage-Karte (PROJ-4) — rendert Claudes AskUserQuestion als lesbare Frage mit
// anklickbaren Optionen + Freitext, statt eines JSON-Blobs. Die Antwort reist über
// den „Deny-mit-Begründung"-Kanal zurück (einziger Weg, Claude im headless-Modus eine
// Antwort zu geben): die Begründung IST die Antwort.

import { useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { ApiError, resolveDecision } from "@/lib/api";
import { projectName } from "@/lib/status";
import type { AskUserQuestionInput, PendingDecision } from "@/lib/types";

export function QuestionCard({
  decision,
  questions,
  showJump = true,
  className,
}: {
  decision: PendingDecision;
  questions: AskUserQuestionInput["questions"];
  showJump?: boolean;
  className?: string;
}) {
  const [busy, setBusy] = useState(false);
  // Auswahl je Frage (Index → Set gewählter Labels) + Freitext je Frage.
  const [picked, setPicked] = useState<Record<number, string[]>>({});
  const [freeText, setFreeText] = useState<Record<number, string>>({});
  const obsolete = decision.state === "obsolete";

  function toggle(qi: number, label: string, multi: boolean) {
    setPicked((prev) => {
      const cur = prev[qi] ?? [];
      if (multi) {
        return { ...prev, [qi]: cur.includes(label) ? cur.filter((l) => l !== label) : [...cur, label] };
      }
      return { ...prev, [qi]: cur.includes(label) ? [] : [label] };
    });
  }

  function answerFor(qi: number): string {
    const sel = picked[qi] ?? [];
    const free = (freeText[qi] ?? "").trim();
    return [...sel, ...(free ? [free] : [])].join(", ");
  }

  const hasAnswer = questions.some((_, qi) => answerFor(qi).length > 0);

  async function resolve(decisionVerdict: "deny", reason: string, okMsg: string) {
    if (busy) return;
    setBusy(true);
    try {
      await resolveDecision(decision.session_id, decision.decision_id, decisionVerdict, reason);
      toast.success(okMsg);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Senden fehlgeschlagen");
      setBusy(false);
    }
  }

  async function submit() {
    // Antwort klar formuliert zurück an Claude (Deny-Begründung = Antwort).
    const lines = questions
      .map((q, qi) => {
        const a = answerFor(qi);
        return a ? `${q.header || q.question}: ${a}` : null;
      })
      .filter(Boolean);
    if (!lines.length) return;
    await resolve("deny", `Antwort des Nutzers — ${lines.join(" · ")}`, "Antwort gesendet");
  }

  const proj = decision.context?.project_path ? projectName(decision.context.project_path) : null;

  return (
    <div
      className={cn(
        "rounded-lg border border-orange-500/50 bg-orange-500/5 p-3 ring-1 ring-orange-500/20",
        obsolete && "border-border bg-muted/30 opacity-60 ring-0",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <Badge
          variant="secondary"
          className="shrink-0 border-orange-500/40 bg-orange-500/10 text-orange-600 dark:text-orange-400"
        >
          Frage
        </Badge>
        <span className="text-sm font-medium">Claude fragt dich</span>
        {proj && <span className="text-[11px] text-muted-foreground">· {proj}</span>}
      </div>

      {obsolete ? (
        <p className="mt-3 text-xs italic text-muted-foreground">Obsolet — die Session wurde beendet.</p>
      ) : (
        <>
          <div className="mt-3 flex flex-col gap-4">
            {questions.map((q, qi) => {
              const sel = picked[qi] ?? [];
              return (
                <div key={qi} className="flex flex-col gap-2">
                  <p className="text-sm font-medium">{q.question}</p>
                  <div className="flex flex-col gap-1.5">
                    {q.options.map((opt) => {
                      const active = sel.includes(opt.label);
                      return (
                        <button
                          key={opt.label}
                          type="button"
                          disabled={busy}
                          onClick={() => toggle(qi, opt.label, !!q.multiSelect)}
                          className={cn(
                            "rounded-md border px-3 py-2 text-left text-sm transition-colors",
                            active
                              ? "border-orange-500 bg-orange-500/15 text-foreground"
                              : "border-border bg-card hover:border-foreground/30",
                          )}
                        >
                          <span className="font-medium">{opt.label}</span>
                          {opt.description && (
                            <span className="block text-xs text-muted-foreground">{opt.description}</span>
                          )}
                        </button>
                      );
                    })}
                  </div>
                  <Input
                    value={freeText[qi] ?? ""}
                    onChange={(e) => setFreeText((p) => ({ ...p, [qi]: e.target.value }))}
                    placeholder="… oder eigene Antwort"
                    disabled={busy}
                    className="text-sm"
                  />
                </div>
              );
            })}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button size="sm" disabled={busy || !hasAnswer} onClick={submit}>
              Antwort senden
            </Button>
            <Button
              size="sm"
              variant="ghost"
              disabled={busy}
              onClick={() => resolve("deny", "Nutzer hat die Frage übersprungen.", "Frage übersprungen")}
            >
              Überspringen
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
        </>
      )}
    </div>
  );
}
