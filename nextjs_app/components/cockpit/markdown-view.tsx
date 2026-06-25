"use client";

// PROJ-7: rendert MD-Body (react-markdown + remark-gfm) mit klickbaren Wikilinks.
// Wikilinks werden vom remark-Plugin als Links mit Schema wikilink:/wikiembed:
// markiert; hier aufgelöst gegen den Index → Navigation oder „fehlend"-Stil.
//
// PROJ-31: zusätzlich werden Standard-Markdown-Links repariert:
//   - relative MD→MD-Links ([Spec](PROJ-7-….md)) → relativ zur aktuell offenen
//     Datei aufgelöst und im Reader geöffnet (kein toter <a href>),
//   - In-Page-Anker (#abschnitt) → Sprung zur passenden Überschrift,
//   - Cross-File-Anker (X.md#abschnitt) → Datei öffnen + zum Anker springen.
// Externe Links (http(s)/mailto/…) bleiben unverändert. Pfad-Sicherheit bleibt
// serverseitig (realpath + Root-Scope beim Lesen); hier wird nur gegen den
// bekannten Index navigiert.

import { createElement } from "react";
import ReactMarkdown, { defaultUrlTransform, type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { ImageIcon } from "lucide-react";
import { remarkWikilink } from "@/lib/remark-wikilink";
import { resolveWikilink, type TreeFile } from "@/lib/md-tree";
import type { MdIndexEntry } from "@/lib/types";
import { cn } from "@/lib/utils";

// QA-7.4: sehr große Dateien gekürzt rendern, damit der DOM-Baum nicht explodiert.
// Großzügig gewählt — normale Doku/Specs bleiben unberührt.
const MAX_RENDER_CHARS = 400_000;

const HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5", "h6"] as const;

interface HastNode {
  value?: string;
  children?: HastNode[];
}

/** Reiner Textinhalt eines hast-Knotens (für Überschriften-Slugs). */
function nodeText(node?: HastNode): string {
  if (!node) return "";
  if (typeof node.value === "string") return node.value;
  return (node.children ?? []).map(nodeText).join("");
}

/** GitHub-naher Slug: lowercase, Satzzeichen weg, Leerzeichen → „-". */
function slugify(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s-]/gu, "")
    .replace(/\s+/g, "-");
}

/** Trennt ``pfad.md#anker`` → [pfad, "#anker"]; ohne Anker → [url, undefined]. */
function splitHash(url: string): [string, string | undefined] {
  const i = url.indexOf("#");
  return i === -1 ? [url, undefined] : [url.slice(0, i), url.slice(i)];
}

/**
 * Löst einen relativen Pfad (``./``, `../`, `%20`) gegen den absoluten Pfad der
 * aktuell offenen Datei auf → absoluter Zielpfad. Rein lexikalisch; die echte
 * Existenz-/Scope-Prüfung passiert über den Index bzw. serverseitig beim Lesen.
 */
function resolveRelative(currentAbs: string, rel: string): string {
  const decoded = decodeURIComponent(rel);
  const baseDir = currentAbs.slice(0, currentAbs.lastIndexOf("/"));
  const stack = baseDir.split("/");
  for (const seg of decoded.split("/")) {
    if (seg === "" || seg === ".") continue;
    if (seg === "..") stack.pop();
    else stack.push(seg);
  }
  return stack.join("/");
}

/** Scrollt im selben Dokument zur Überschrift mit der Anker-ID. */
function scrollToAnchor(hash: string): void {
  const id = decodeURIComponent(hash.replace(/^#/, ""));
  if (!id) return;
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

/** Überschriften mit Slug-ID rendern → In-Page-Anker funktionieren. */
function headingComponent(Tag: (typeof HEADING_TAGS)[number]): Components[typeof Tag] {
  return function Heading({ node, children, ...props }) {
    const id = slugify(nodeText(node as HastNode | undefined));
    return createElement(Tag, { id, ...props }, children);
  };
}

const headingComponents = Object.fromEntries(
  HEADING_TAGS.map((t) => [t, headingComponent(t)]),
) as Pick<Components, (typeof HEADING_TAGS)[number]>;

export function MarkdownView({
  body,
  index,
  currentPath,
  onNavigate,
}: {
  body: string;
  index: Map<string, MdIndexEntry>;
  /** Absoluter Pfad der aktuell offenen Datei — Basis für relative Links. */
  currentPath: string;
  onNavigate: (file: Pick<TreeFile, "path"> & { hash?: string }) => void;
}) {
  const truncated = body.length > MAX_RENDER_CHARS;
  const rendered = truncated ? body.slice(0, MAX_RENDER_CHARS) : body;
  // Bekannte absolute Pfade (alle Quellen) → relative Links vorab als Treffer
  // oder „fehlend" markieren, konsistent zum Wikilink-Verhalten.
  const knownPaths = new Set(Array.from(index.values(), (e) => e.path));
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
          ...headingComponents,
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
                const [, anchor] = splitHash(target);
                return (
                  <button
                    type="button"
                    onClick={() => onNavigate({ path: hit.path, hash: anchor })}
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

            // PROJ-31: In-Page-Anker (#…) → im selben Dokument scrollen.
            if (url.startsWith("#")) {
              return (
                <a
                  href={url}
                  onClick={(e) => {
                    e.preventDefault();
                    scrollToAnchor(url);
                  }}
                  className="text-primary underline-offset-2 hover:underline"
                >
                  {children}
                </a>
              );
            }

            // Externe Links / fremde Schemata → unverändert extern öffnen.
            if (/^(https?:|mailto:|tel:|\/\/)/i.test(url)) {
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
            }

            // PROJ-31: interne relative Links → gegen die aktuelle Datei auflösen.
            const [relPath, anchor] = splitHash(url);
            const resolved = relPath ? resolveRelative(currentPath, relPath) : currentPath;

            // Nicht-MD-Ziel (Bild/.py/…) → Reader kann es nicht anzeigen.
            if (!resolved.toLowerCase().endsWith(".md")) {
              return (
                <span
                  className="cursor-not-allowed text-muted-foreground/70 underline decoration-dotted"
                  title="Nur Markdown-Dateien können im Reader geöffnet werden"
                >
                  {children}
                </span>
              );
            }

            // Ziel existiert im Index (in-scope) → im Reader navigieren.
            if (knownPaths.has(resolved)) {
              return (
                <button
                  type="button"
                  onClick={() => onNavigate({ path: resolved, hash: anchor })}
                  className="text-primary underline-offset-2 hover:underline"
                >
                  {children}
                </button>
              );
            }

            // Nicht im Index (umbenannt/gelöscht/außerhalb der Roots) → fehlend markieren.
            return (
              <span
                className="cursor-not-allowed text-muted-foreground/70 line-through decoration-dotted"
                title="Ziel nicht gefunden"
              >
                {children}
              </span>
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
