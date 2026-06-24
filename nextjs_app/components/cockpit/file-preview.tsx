"use client";

// PROJ-28: Inhalts-Ansicht (Spalte 3) des Fileexplorers. Bezieht den Inhalt aus
// dem bestehenden /files/download-Endpoint (kein neues Backend-API):
//   .md            → MarkdownView (aus PROJ-7 wiederverwendet)
//   Text/Code/YAML → monospace <pre> (Roh-Inhalt)
//   Bilder         → <img src=downloadUrl>
//   Binär/zu groß  → Hinweis + Download (kein Preview-Fehler)

import { useEffect, useMemo, useState } from "react";
import { Download, FileWarning } from "lucide-react";

import { Button } from "@/components/ui/button";
import { fileDownloadUrl } from "@/lib/api";
import type { FileEntry, MdIndexEntry } from "@/lib/types";
import { MarkdownView } from "./markdown-view";

const IMAGE_EXT = new Set([
  "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "ico", "avif",
]);
const MARKDOWN_EXT = new Set(["md", "markdown"]);
const TEXT_EXT = new Set([
  "txt", "text", "yaml", "yml", "json", "jsonc", "log", "csv", "tsv", "xml",
  "toml", "ini", "cfg", "conf", "env", "properties", "sh", "bash", "zsh",
  "fish", "py", "js", "mjs", "cjs", "ts", "tsx", "jsx", "css", "scss", "sass",
  "less", "html", "htm", "sql", "rs", "go", "java", "kt", "c", "h", "cpp",
  "hpp", "cc", "rb", "php", "pl", "lua", "r", "dart", "vue", "svelte",
  "gradle", "makefile", "dockerfile", "gitignore", "editorconfig", "npmrc",
]);

// Text/MD werden vollständig in den Browser geladen → harte Grenze gegen Hänger.
const MAX_PREVIEW_BYTES = 2_000_000; // 2 MB
const MAX_TEXT_CHARS = 200_000;

type Kind = "image" | "markdown" | "text" | "binary";

/** Endung (bzw. Sondernamen wie Dockerfile/.gitignore) in Kleinschreibung. */
function extOf(name: string): string {
  const base = name.toLowerCase();
  const dot = base.lastIndexOf(".");
  if (dot <= 0) return base.replace(/^\./, ""); // Dockerfile, .gitignore …
  return base.slice(dot + 1);
}

function kindOf(name: string): Kind {
  const e = extOf(name);
  if (IMAGE_EXT.has(e)) return "image";
  if (MARKDOWN_EXT.has(e)) return "markdown";
  if (TEXT_EXT.has(e)) return "text";
  return "binary";
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

// Hinweis: Der Aufrufer remountet via key={path}, damit der Lade-/Inhaltsstand
// pro Datei frisch startet (kein synchrones setState im Effect nötig).
export function FilePreview({ entry }: { entry: FileEntry | null }) {
  // MarkdownView braucht einen Wikilink-Index — im Explorer gibt es keinen.
  const emptyIndex = useMemo<Map<string, MdIndexEntry>>(() => new Map(), []);

  const kind = entry ? kindOf(entry.name) : null;
  const tooLarge = entry ? entry.size > MAX_PREVIEW_BYTES : false;
  const needsText = kind === "markdown" || kind === "text";

  const [text, setText] = useState<string | null>(null);
  const [loading, setLoading] = useState(() => !!entry && needsText && !tooLarge);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!entry || !needsText || tooLarge) return;
    let active = true;
    const ctrl = new AbortController();
    fetch(fileDownloadUrl(entry.path), { signal: ctrl.signal })
      .then((r) => {
        if (!r.ok) throw new Error(`Fehler ${r.status}`);
        return r.text();
      })
      .then((t) => {
        if (active) setText(t);
      })
      .catch((e) => {
        if (active && (e as Error).name !== "AbortError")
          setError("Vorschau konnte nicht geladen werden.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      ctrl.abort();
    };
  }, [entry, needsText, tooLarge]);

  if (!entry) {
    return (
      <p className="py-20 text-center text-sm text-muted-foreground">
        Wähle links eine Datei für die Vorschau.
      </p>
    );
  }

  const downloadBtn = (
    <a href={fileDownloadUrl(entry.path)} download>
      <Button size="sm" variant="outline">
        <Download className="size-3.5" /> Herunterladen
      </Button>
    </a>
  );

  return (
    <article className="flex min-h-0 flex-col">
      <div className="mb-4 flex items-center justify-between gap-3 border-b border-border pb-3">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-semibold">{entry.name}</h2>
          <p className="truncate text-xs text-muted-foreground">
            {formatBytes(entry.size)}
          </p>
        </div>
        {downloadBtn}
      </div>

      {kind === "image" ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={fileDownloadUrl(entry.path)}
          alt={entry.name}
          className="mx-auto max-h-[75vh] max-w-full rounded-md border border-border object-contain"
        />
      ) : tooLarge || kind === "binary" ? (
        <PreviewHint
          text={
            tooLarge
              ? `Datei zu groß für die Vorschau (${formatBytes(entry.size)}). Bitte herunterladen.`
              : "Für diesen Dateityp gibt es keine Vorschau. Bitte herunterladen."
          }
        />
      ) : loading ? (
        <p className="py-10 text-center text-sm text-muted-foreground">Lädt…</p>
      ) : error ? (
        <PreviewHint text={error} />
      ) : text !== null ? (
        kind === "markdown" ? (
          <MarkdownView body={text} index={emptyIndex} onNavigate={() => {}} />
        ) : (
          <TextPreview text={text} />
        )
      ) : null}
    </article>
  );
}

function TextPreview({ text }: { text: string }) {
  const truncated = text.length > MAX_TEXT_CHARS;
  const shown = truncated ? text.slice(0, MAX_TEXT_CHARS) : text;
  return (
    <div>
      {truncated && (
        <p className="mb-3 rounded-md border border-amber-500/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-600 dark:text-amber-400">
          Große Datei ({Math.round(text.length / 1000)} KB) — Anzeige auf die ersten{" "}
          {MAX_TEXT_CHARS / 1000} KB gekürzt.
        </p>
      )}
      <pre className="overflow-x-auto rounded-md border border-border bg-muted/30 p-4 font-mono text-xs leading-relaxed">
        {shown}
      </pre>
    </div>
  );
}

function PreviewHint({ text }: { text: string }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border px-4 py-12 text-center">
      <FileWarning className="size-8 text-muted-foreground" />
      <p className="text-sm text-muted-foreground">{text}</p>
    </div>
  );
}
