"use client";

// PROJ-19 (#23) — Pointer/RAG-Vorschau: zeigt, welche relevanten Vault-Ausschnitte
// statt Volltext geladen würden, inkl. messbarer Kontext-Ersparnis. Liefert keine
// Treffer → Fallback-Hinweis (Caller würde auf Volltext zurückfallen).

import { useState } from "react";
import { FileSearch, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ApiError, getRagPreview } from "@/lib/api";
import type { VaultRagPreview } from "@/lib/types";

export function RagPreviewPanel() {
  const [q, setQ] = useState("");
  const [res, setRes] = useState<VaultRagPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    const query = q.trim();
    if (!query || busy) return;
    setBusy(true);
    setError(null);
    try {
      setRes(await getRagPreview(query, 5));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Vorschau fehlgeschlagen");
      setRes(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section>
      <h2 className="mb-2 flex items-center gap-1.5 text-sm font-medium text-muted-foreground">
        <FileSearch className="size-4" /> RAG-Vorschau (Vault-Ausschnitte statt Volltext)
      </h2>
      <div className="flex gap-1.5">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
          placeholder="Wonach im Vault suchen?…"
          className="h-9 text-sm"
        />
        <Button size="sm" variant="outline" className="h-9 shrink-0" disabled={busy} onClick={run}>
          <Search className="size-3.5" /> Vorschau
        </Button>
      </div>

      {error && <p className="mt-2 text-xs text-red-400">{error}</p>}

      {res && (
        <div className="mt-3 space-y-2">
          {res.fallback ? (
            <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-500">
              {res.reason ?? "Kein relevanter Ausschnitt — Caller würde Volltext laden."}
            </p>
          ) : (
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <Badge variant="secondary">
                {res.reduction_pct}% weniger Kontext
              </Badge>
              <span className="tabular-nums">
                {res.context_chars.toLocaleString("de-DE")} statt{" "}
                {res.fulltext_chars.toLocaleString("de-DE")} Zeichen
              </span>
            </div>
          )}

          {res.snippets.map((s) => (
            <div
              key={`${s.path}-${s.line}`}
              className="rounded-md border border-border bg-card/30 p-2.5"
            >
              <div className="mb-1 flex items-center justify-between gap-2">
                <span className="truncate font-mono text-xs" title={s.path}>
                  {s.path}:{s.line}
                </span>
                <Badge variant="outline" className="shrink-0" title="getroffene Begriffe">
                  {s.terms_matched} Treffer
                </Badge>
              </div>
              <p className="line-clamp-3 text-[11px] text-muted-foreground">{s.snippet}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
