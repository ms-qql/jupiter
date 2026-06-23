"use client";

// PROJ-7: rendert MD-Body (react-markdown + remark-gfm) mit klickbaren Wikilinks.
// Wikilinks werden vom remark-Plugin als Links mit Schema wikilink:/wikiembed:
// markiert; hier aufgelöst gegen den Index → Navigation oder „fehlend"-Stil.

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { ImageIcon } from "lucide-react";
import { remarkWikilink } from "@/lib/remark-wikilink";
import { resolveWikilink, type TreeFile } from "@/lib/md-tree";
import type { MdIndexEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

export function MarkdownView({
  body,
  index,
  onNavigate,
}: {
  body: string;
  index: Map<string, MdIndexEntry>;
  onNavigate: (file: Pick<TreeFile, "path">) => void;
}) {
  return (
    <div className="md-body">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkWikilink]}
        components={{
          a({ href, children, ...props }) {
            const url = href ?? "";

            // Bild-Embed ![[…]] → Platzhalter (Anzeige = nice-to-have, MVP).
            if (url.startsWith("wikiembed:")) {
              const name = decodeURIComponent(url.slice("wikiembed:".length));
              return (
                <span className="inline-flex items-center gap-1 rounded border border-dashed border-border px-1.5 py-0.5 align-middle text-xs text-muted-foreground">
                  <ImageIcon className="size-3" />
                  {name}
                </span>
              );
            }

            // Wikilink [[…]] → gegen Index auflösen.
            if (url.startsWith("wikilink:")) {
              const target = url.slice("wikilink:".length);
              const hit = resolveWikilink(target, index);
              if (hit) {
                return (
                  <button
                    type="button"
                    onClick={() => onNavigate(hit)}
                    className="text-primary underline-offset-2 hover:underline"
                  >
                    {children}
                  </button>
                );
              }
              // Fehlendes Ziel → markiert, kein Crash, keine Navigation.
              return (
                <span
                  className="cursor-not-allowed text-muted-foreground/70 line-through decoration-dotted"
                  title="Ziel nicht gefunden"
                >
                  {children}
                </span>
              );
            }

            // Normale Links extern öffnen.
            return (
              <a
                href={url}
                target="_blank"
                rel="noreferrer noopener"
                className="text-primary underline-offset-2 hover:underline"
                {...props}
              >
                {children}
              </a>
            );
          },
          // Bilder relativer Pfade können wir read-only nicht ausliefern → Platzhalter.
          img({ alt }) {
            return (
              <span className={cn("inline-flex items-center gap-1 rounded border border-dashed border-border px-1.5 py-0.5 text-xs text-muted-foreground")}>
                <ImageIcon className="size-3" />
                {alt || "Bild"}
              </span>
            );
          },
        }}
      >
        {body}
      </ReactMarkdown>
    </div>
  );
}
