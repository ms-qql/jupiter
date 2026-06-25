"use client";

// PROJ-23 — Review-Übersicht auf der Autor-Session: alle Challenges, in denen diese
// Session der Autor ist, mit ihren strukturierten Befunden. Pro Befund: übernehmen /
// verwerfen / mit Kommentar zurück. Nennt Autor- UND Reviewer-Engine/-Modell
// (Nachvollziehbarkeit der Diversität) und warnt bei Versions-Drift.

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { ApiError, listReviews } from "@/lib/api";
import type { ReviewRead } from "@/lib/types";
import { FindingActions, SeverityBadge } from "./review-finding";

export function ReviewsPanel({
  sessionId,
  refreshKey = 0,
}: {
  sessionId: string;
  /** Erhöhen, um nach einer neuen Challenge neu zu laden. */
  refreshKey?: number;
}) {
  const [reviews, setReviews] = useState<ReviewRead[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(
    (signal?: AbortSignal) => {
      listReviews(sessionId, signal)
        .then((r) => setReviews(r))
        .catch((e) => {
          if ((e as Error).name !== "AbortError")
            setError(e instanceof ApiError ? e.message : "Reviews nicht erreichbar");
        });
    },
    [sessionId],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load, refreshKey]);

  if (error) {
    return <p className="text-xs text-red-500">{error}</p>;
  }
  if (!reviews || reviews.length === 0) {
    return (
      <p className="text-xs text-muted-foreground">
        Noch keine Reviews — starte eine Challenge auf einem Artefakt dieser Session.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {reviews.map((rv) => (
        <ReviewItem key={rv.review_id} review={rv} onChanged={() => load()} />
      ))}
    </div>
  );
}

function ReviewItem({
  review,
  onChanged,
}: {
  review: ReviewRead;
  onChanged: () => void;
}) {
  return (
    <div className="rounded-lg border border-border bg-card/40 p-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <Badge variant="secondary" className="font-mono">
          {review.artifact_pointer.split("/").pop()}
        </Badge>
        <span className="text-muted-foreground">
          Autor {review.author_engine}/{review.author_model} → Reviewer{" "}
          {review.reviewer_engine}/{review.reviewer_model}
        </span>
        <span className="text-muted-foreground">· Runde {review.round}</span>
        {review.same_engine && (
          <span className="text-amber-600 dark:text-amber-400">
            · ⚠️ gleiche Engine
          </span>
        )}
        {review.stale && (
          <Badge
            variant="secondary"
            className="border-amber-500/40 bg-amber-500/10 text-amber-700 dark:text-amber-400"
          >
            Artefakt geändert (Versions-Drift)
          </Badge>
        )}
        <Link
          href={`/sessions/${review.review_id}`}
          className="ml-auto text-muted-foreground hover:text-foreground"
        >
          Reviewer-Session →
        </Link>
      </div>

      {review.incomplete ? (
        <p className="mt-2 text-xs italic text-amber-600 dark:text-amber-400">
          Review unvollständig (Reviewer-Session beendet ohne verwertbares Ergebnis) —
          erneut challengen möglich.
        </p>
      ) : !review.collected ? (
        <p className="mt-2 text-xs italic text-muted-foreground">
          Reviewer prüft noch…
        </p>
      ) : review.findings.length === 0 ? (
        <p className="mt-2 text-xs text-emerald-600 dark:text-emerald-400">
          Keine Befunde — der Reviewer hat keine Schwachstellen gemeldet.
        </p>
      ) : (
        <ul className="mt-2 flex flex-col gap-2">
          {review.findings.map((f) => (
            <li key={f.finding_id} className="rounded-md border border-border bg-background/50 p-2">
              <div className="flex items-start gap-2">
                <SeverityBadge severity={f.severity} />
                <span className="min-w-0 flex-1 break-words text-sm font-medium">
                  {f.title}
                </span>
              </div>
              <p className="mt-1 text-[11px] text-muted-foreground">
                <span className="font-medium text-foreground/70">Fundstelle: </span>
                {f.location}
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                <span className="font-medium text-foreground/70">Gegenvorschlag: </span>
                {f.suggestion}
              </p>
              <FindingActions
                reviewId={review.review_id}
                findingId={f.finding_id}
                resolution={f.state === "resolved" ? f.resolution : null}
                onResolved={onChanged}
              />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
