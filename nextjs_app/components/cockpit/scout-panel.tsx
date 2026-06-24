"use client";

// PROJ-19 (#26) — Späher-Agent: delegiert eine Fazit-Aufgabe (viel lesen, wenig
// zurück) an ein günstiges Modell und zeigt nur das verdichtete Fazit. Bei dünnem
// Fazit (usable=false) erscheint der Eskalations-Hinweis + ein „Mit Opus wiederholen".

import { useState } from "react";
import { Bot, Send } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ApiError, runScout } from "@/lib/api";
import type { ScoutResult } from "@/lib/types";

export function ScoutPanel() {
  const [task, setTask] = useState("");
  const [query, setQuery] = useState("");
  const [res, setRes] = useState<ScoutResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run(model?: string) {
    const t = task.trim();
    if (!t || busy) return;
    setBusy(true);
    setError(null);
    try {
      setRes(
        await runScout({
          task: t,
          query: query.trim() || null,
          ...(model ? { model } : {}),
        }),
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Späher-Lauf fehlgeschlagen");
      setRes(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h2 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        <Bot className="size-4" /> Späher-Agent (günstiges Modell → nur Fazit)
      </h2>
      <div className="flex flex-col gap-1.5">
        <Textarea
          value={task}
          onChange={(e) => setTask(e.target.value)}
          placeholder="Aufgabe: was soll der Späher herausfinden/zusammenfassen?"
          className="min-h-[64px] text-sm"
        />
        <div className="flex gap-1.5">
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && run()}
            placeholder="Optional: Vault-Query für den Kontext (RAG)…"
            className="h-9 text-sm"
          />
          <Button size="sm" variant="outline" className="h-9 shrink-0" disabled={busy} onClick={() => run()}>
            <Send className="size-3.5" /> {busy ? "Läuft…" : "Späher starten"}
          </Button>
        </div>
      </div>

      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}

      {res && (
        <div className="mt-3 rounded-md border border-border bg-card/30 p-3">
          <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
            <Badge variant="outline">Modell: {res.model_used}</Badge>
            {res.sources.length > 0 && (
              <span className="text-muted-foreground" title={res.sources.join("\n")}>
                {res.sources.length} Quelle(n)
              </span>
            )}
          </div>
          <p className="whitespace-pre-wrap text-sm">{res.summary || "(leeres Fazit)"}</p>

          {!res.usable && (
            <div className="mt-3 flex flex-wrap items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-500">
              <span>{res.note ?? "Fazit wirkt dünn — Eskalation empfohlen."}</span>
              <Button
                size="sm"
                variant="outline"
                className="h-7 shrink-0"
                disabled={busy}
                onClick={() => run("opus")}
              >
                Mit Opus wiederholen
              </Button>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
