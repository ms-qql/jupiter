"use client";

// PROJ-7: rendert MD-Body (react-markdown + remark-gfm) mit klickbaren Wikilinks.
// Wikilinks werden vom remark-Plugin als Links mit Schema wikilink:/wikiembed:
// markiert; hier aufgelöst gegen den Index → Navigation oder „fehlend"-Stil.

import ReactMarkdown, { defaultUrlTransform } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ImageIcon } from "lucide-react";
import { remarkWikilink } from "@/lib/remark-wikilink";
import { resolveWikilink, type TreeFile } from "@/lib/md-tree";
import type { MdIndexEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

// QA-7.4: sehr große Dateien gekürzt rendern, damit der DOM-Baum nicht explodiert.
// Großzügig gewählt — normale Doku/Specs bleiben unberührt.
const MAX_RENDER_CHARS = 400_000;

export function MarkdownView({
  body,
  index,
  onNavigate,
}: {
  body: string;
  index: Map<string, MdIndexEntry>;
  onNavigate: (file: Pick<TreeFile, "path">) => void;
}) {
  const truncated = body.length > MAX_RENDER_CHARS;
  const rendered = truncated ? body.slice(0, MAX_RENDER_CHARS) : body;
  return (
    <div className="md-body">
      {truncated && (
        <p className="mb-4 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-600 dark:text-amber-400">
          Große Datei ({Math.round(body.length / 1000)} KB) — Anzeige auf die ersten{" "}
          {MAX_RENDER_CHARS / 1000} KB gekürzt.
        </p>
      )}
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkWikilink]}
        // QA-7.2: react-markdowns Default-urlTransform würde die custom Schemata
        // wikilink:/wikiembed: zu "" strippen → durchlassen, sonst Default (XSS-Schutz bleibt).
        urlTransform={(url) =>
          url.startsWith("wikilink:") || url.startsWith("wikiembed:")
            ? url
            : defaultUrlTransform(url)
        }
        components={{
          // QA-7.3: `node` (mdast) NICHT auf das DOM-Element spreaden.
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
          a({ href, children, node, ...props }) {
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
        {rendered}
      </ReactMarkdown>
    </div>
  );
}
