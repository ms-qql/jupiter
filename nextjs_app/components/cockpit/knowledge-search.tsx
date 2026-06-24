"use client";

// PROJ-15 — Suche über kuratiertes Wissen (Knowledge/), projektübergreifend.
// Treffer = Pfad (Backlink) + Ausschnitt; Klick öffnet die Notiz im MD-Reader.

import { useState } from "react";
import { Lightbulb, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ApiError, searchVault } from "@/lib/api";
import type { VaultSearchHit } from "@/lib/types";

type Props = {
  /** Öffnet einen Treffer (vault-relativer Pfad) im Reader. */
  onSelect: (vaultRelPath: string) => void;
};

export function KnowledgeSearch({ onSelect }: Props) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<VaultSearchHit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    const query = q.trim();
    if (!query || busy) return;
    setBusy(true);
    setError(null);
    try {
      const res = await searchVault(query, "curated", 30);
      setHits(res.hits);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Suche fehlgeschlagen");
      setHits(null);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="border-b border-border p-2">
      <div className="mb-1 flex items-center gap-1.5 px-1 text-[11px] font-medium text-muted-foreground">
        <Lightbulb className="size-3 text-emerald-600 dark:text-emerald-400" />
        Kuratiertes Wissen
      </div>
      <div className="flex gap-1.5">
        <Input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
          placeholder="Projektübergreifend suchen…"
          className="h-8 text-sm"
        />
        <Button size="sm" variant="outline" className="h-8 shrink-0" disabled={busy} onClick={run}>
          <Search className="size-3.5" />
        </Button>
      </div>

      {error && <p className="mt-2 px-1 text-xs text-red-400">{error}</p>}

      {hits && (
        <div className="mt-2 space-y-1">
          {hits.length === 0 ? (
            <p className="px-1 text-xs text-muted-foreground">Keine Treffer im kuratierten Wissen.</p>
          ) : (
            hits.map((h, i) => (
              <button
                key={`${h.path}-${h.line}-${i}`}
                onClick={() => onSelect(h.path)}
                className="block w-full rounded-md border border-transparent px-2 py-1.5 text-left hover:border-border hover:bg-muted/50"
                title={h.path}
              >
                <div className="truncate text-xs font-medium">
                  {h.path.split("/").pop()?.replace(/\.md$/, "")}
                </div>
                <div className="line-clamp-2 text-[11px] text-muted-foreground">{h.excerpt}</div>
              </button>
            ))
          )}
        </div>
      )}
    </div>
  );
}
