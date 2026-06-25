"use client";

// PROJ-7: MD-Reader — read-only Vault-/Projekt-Doku im Browser.
// Links: Quellen-Umschalter (Vault | Projekt) + Datei-Baum. Rechts: gerenderte
// MD mit klickbaren Wikilinks + Frontmatter-Panel. Deep-linkbar via ?source=&path=
// (bzw. ?source=vault&rel=… für vault-relative Pointer aus PROJ-5-Handovers).

import { Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Pencil } from "lucide-react";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/cockpit/theme-toggle";
import { FileTree } from "@/components/cockpit/file-tree";
import { KnowledgeSearch } from "@/components/cockpit/knowledge-search";
import { FrontmatterPanel } from "@/components/cockpit/frontmatter-panel";
import { MarkdownView } from "@/components/cockpit/markdown-view";
import { MdEditorPanel } from "@/components/cockpit/md-editor";
import { BacklinksPanel } from "@/components/cockpit/backlinks-panel";
import { ApiError, getMdIndex, listMdSources, readMdFile } from "@/lib/api";
import {
  buildTree,
  buildWikilinkIndex,
  type TreeNode,
} from "@/lib/md-tree";
import type { MdFileRead, MdIndexEntry, MdIndexResult, MdSource } from "@/lib/types";

const EXPAND_PREFIXES: Record<string, string[]> = {
  vault: ["Agentic OS/Jupiter", "Agentic OS/Jupiter/Handovers"],
  project: ["features"],
};

// PROJ-31: zur Überschrift mit der Anker-ID scrollen (Slug aus markdown-view).
function scrollToAnchor(hash: string): void {
  const id = decodeURIComponent(hash.replace(/^#/, ""));
  if (!id) return;
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function DocReader() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();

  const [sources, setSources] = useState<MdSource[]>([]);
  const [indices, setIndices] = useState<Record<string, MdIndexResult>>({});
  const [activeSource, setActiveSource] = useState<string>(
    () => searchParams.get("source") || "project",
  );
  const [selectedPath, setSelectedPath] = useState<string | null>(
    () => searchParams.get("path"),
  );
  const [file, setFile] = useState<MdFileRead | null>(null);
  // Initial-Loading, falls die URL bereits ein Ziel (?path= oder ?rel=) trägt.
  const [fileLoading, setFileLoading] = useState(
    () => !!(searchParams.get("path") || searchParams.get("rel")),
  );
  const [fileError, setFileError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // PROJ-12: Lesen ⇄ Bearbeiten; dirtyRef speist die Verlassen-Warnung beim Navigieren.
  const [editing, setEditing] = useState(false);
  const dirtyRef = useRef(false);
  // PROJ-31: Anker, zu dem nach dem Laden einer (anderen) Datei gescrollt wird.
  const pendingAnchorRef = useRef<string | null>(null);

  // 1) Quellen + Index beider Quellen laden (Cross-Source-Wikilinks). Löst auch
  //    einen vault-relativen Pointer (?rel=) auf einen absoluten Pfad auf.
  useEffect(() => {
    let active = true;
    listMdSources()
      .then(async (srcs) => {
        if (!active) return;
        setSources(srcs);
        const loaded: Record<string, MdIndexResult> = {};
        await Promise.all(
          srcs.map(async (s) => {
            try {
              loaded[s.id] = await getMdIndex(s.id);
            } catch {
              /* einzelne Quelle ignorieren */
            }
          }),
        );
        if (!active) return;
        setIndices(loaded);
        // Falls die initial gewählte Quelle nicht existiert → erste verfügbare.
        if (!srcs.some((s) => s.id === activeSource) && srcs.length > 0) {
          setActiveSource(srcs[0].id);
        }
        // ?rel= (vault-relativer Handover-Pointer aus PROJ-5) → absoluter Pfad.
        const rel = searchParams.get("rel");
        if (rel && !selectedPath) {
          const src = srcs.find((s) => s.id === (searchParams.get("source") || "vault"));
          if (src) setSelectedPath(`${src.root.replace(/\/$/, "")}/${rel}`);
          else setFileLoading(false);
        }
      })
      .catch((e) =>
        active && setLoadError(e instanceof ApiError ? e.message : "Nicht erreichbar"),
      );
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // 2) Ausgewählte Datei laden (setState nur in async-Callbacks → kein Cascading).
  useEffect(() => {
    if (!selectedPath) return;
    let active = true;
    readMdFile(selectedPath)
      .then((f) => {
        if (!active) return;
        setFile(f);
        setFileError(null);
      })
      .catch((e) => {
        if (!active) return;
        setFile(null);
        setFileError(e instanceof ApiError ? e.message : "Datei nicht lesbar");
      })
      .finally(() => active && setFileLoading(false));
    return () => {
      active = false;
    };
  }, [selectedPath]);

  // Index der aktiven Quelle → Baum.
  const tree: TreeNode[] = useMemo(() => {
    const entries = indices[activeSource]?.files ?? [];
    return buildTree(entries);
  }, [indices, activeSource]);

  // Wikilink-Index: alle Quellen gemerged, aktive Quelle gewinnt (wird zuletzt gesetzt).
  const wikiIndex = useMemo(() => {
    const all: MdIndexEntry[] = [];
    for (const id of Object.keys(indices)) {
      if (id !== activeSource) all.push(...indices[id].files);
    }
    all.push(...(indices[activeSource]?.files ?? []));
    return buildWikilinkIndex(all);
  }, [indices, activeSource]);

  // PROJ-12: flache Notiz-Liste aller Quellen fürs [[-Autocomplete (de-dupliziert).
  const allNotes = useMemo(() => {
    const seen = new Set<string>();
    const out: MdIndexEntry[] = [];
    for (const id of Object.keys(indices)) {
      for (const f of indices[id].files) {
        if (seen.has(f.path)) continue;
        seen.add(f.path);
        out.push(f);
      }
    }
    return out;
  }, [indices]);

  // Zu welcher Quelle gehört ein absoluter Pfad? (längster Root-Match)
  const sourceOf = useCallback(
    (absPath: string): string | null => {
      let best: { id: string; len: number } | null = null;
      for (const s of sources) {
        if (absPath === s.root || absPath.startsWith(s.root.replace(/\/$/, "") + "/")) {
          if (!best || s.root.length > best.len) best = { id: s.id, len: s.root.length };
        }
      }
      return best?.id ?? null;
    },
    [sources],
  );

  const updateUrl = useCallback(
    (source: string, path: string | null) => {
      const params = new URLSearchParams({ source });
      if (path) params.set("path", path);
      router.replace(`${pathname}?${params.toString()}`, { scroll: false });
    },
    [router, pathname],
  );

  const selectPath = useCallback(
    (path: string, hash?: string) => {
      if (path === selectedPath) {
        // Schon offen → bei Anker (z. B. eigener Datei-Link mit #) nur scrollen.
        if (hash) scrollToAnchor(hash);
        return;
      }
      // PROJ-12: ungespeicherte Änderungen → vor dem Wechsel nachfragen.
      if (
        dirtyRef.current &&
        !window.confirm("Ungespeicherte Änderungen verwerfen und Datei wechseln?")
      ) {
        return;
      }
      dirtyRef.current = false;
      setEditing(false);
      // PROJ-31: Anker merken → nach dem Laden der Zieldatei dorthin scrollen.
      pendingAnchorRef.current = hash ?? null;
      // Springt der Pfad in eine andere Quelle (Cross-Source-Wikilink), Tab mitschalten.
      const owner = sourceOf(path);
      const nextSource = owner ?? activeSource;
      if (owner && owner !== activeSource) setActiveSource(owner);
      setFileLoading(true);
      setFileError(null);
      setSelectedPath(path);
      updateUrl(nextSource, path);
    },
    [sourceOf, activeSource, updateUrl, selectedPath],
  );

  // PROJ-31: nach dem Rendern einer frisch geladenen Datei zum gemerkten Anker springen.
  useEffect(() => {
    if (fileLoading || !file) return;
    const hash = pendingAnchorRef.current;
    if (!hash) return;
    pendingAnchorRef.current = null;
    requestAnimationFrame(() => scrollToAnchor(hash));
  }, [file, fileLoading]);

  // PROJ-12: nach dem Speichern den geladenen Stand (inkl. mtime/Hash) auffrischen,
  // damit die Lese-Ansicht konsistent bleibt.
  const reloadFile = useCallback(() => {
    if (!selectedPath) return;
    readMdFile(selectedPath)
      .then((f) => setFile(f))
      .catch(() => {
        /* Lese-Fehler hier ignorieren — Editor hat den Stand bereits */
      });
  }, [selectedPath]);

  const switchSource = useCallback(
    (source: string) => {
      setActiveSource(source);
      updateUrl(source, selectedPath);
    },
    [updateUrl, selectedPath],
  );

  // PROJ-15: kuratierten Treffer (vault-relativer Pfad) im Reader öffnen.
  const openVaultRel = useCallback(
    (rel: string) => {
      const vault = sources.find((s) => s.id === "vault");
      if (!vault) return;
      selectPath(`${vault.root.replace(/\/$/, "")}/${rel}`);
    },
    [sources, selectPath],
  );

  if (loadError) {
    return (
      <div className="p-6">
        <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
          ← Cockpit
        </Link>
        <p className="mt-6 text-red-400">{loadError}</p>
      </div>
    );
  }

  return (
    <div className="flex h-dvh flex-col">
      <header className="flex items-center gap-3 border-b border-border px-4 py-3">
        <Link href="/" className="text-sm text-muted-foreground hover:text-foreground">
          ← Cockpit
        </Link>
        <h1 className="text-sm font-semibold tracking-tight">📄 Doku</h1>
        {sources.length > 1 && (
          <Tabs value={activeSource} onValueChange={(v) => switchSource(String(v))}>
            <TabsList>
              {sources.map((s) => (
                <TabsTrigger key={s.id} value={s.id}>
                  {s.id === "vault" ? "Vault" : s.label}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>
        )}
        <div className="ml-auto">
          <ThemeToggle />
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* Datei-Baum */}
        <aside className="hidden w-72 shrink-0 flex-col border-r border-border bg-card/40 md:flex">
          <KnowledgeSearch onSelect={openVaultRel} />
          <ScrollArea className="flex-1">
            <div className="p-2">
              <FileTree
                nodes={tree}
                activePath={selectedPath}
                defaultExpandedPrefixes={EXPAND_PREFIXES[activeSource] ?? []}
                onSelect={selectPath}
              />
            </div>
          </ScrollArea>
        </aside>

        {/* Viewer */}
        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto max-w-3xl px-4 py-6 md:px-8">
            {!selectedPath ? (
              <p className="py-20 text-center text-sm text-muted-foreground">
                Wähle links eine Datei zum Lesen.
              </p>
            ) : fileLoading ? (
              <div className="flex flex-col gap-3">
                <Skeleton className="h-6 w-1/2" />
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-4 w-2/3" />
              </div>
            ) : fileError ? (
              <p className="rounded-lg border border-red-500/40 bg-red-500/5 px-4 py-6 text-center text-sm text-red-400">
                {fileError}
              </p>
            ) : file ? (
              editing ? (
                <div className="flex min-h-0 flex-col">
                  <MdEditorPanel
                    key={file.path}
                    file={file}
                    notes={allNotes}
                    wikiIndex={wikiIndex}
                    onNavigate={selectPath}
                    onSaved={reloadFile}
                    onDirtyChange={(d) => (dirtyRef.current = d)}
                  />
                  <BacklinksPanel path={file.path} onNavigate={selectPath} />
                </div>
              ) : (
                <article>
                  <div className="mb-3 flex justify-end">
                    <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                      <Pencil className="size-3.5" /> Bearbeiten
                    </Button>
                  </div>
                  <FrontmatterPanel frontmatter={file.frontmatter} />
                  <MarkdownView
                    body={file.body}
                    index={wikiIndex}
                    currentPath={file.path}
                    onNavigate={(f) => selectPath(f.path, f.hash)}
                  />
                  <BacklinksPanel path={file.path} onNavigate={selectPath} />
                </article>
              )
            ) : null}
          </div>
        </main>
      </div>
    </div>
  );
}

export default function DocReaderPage() {
  return (
    <Suspense fallback={<div className="p-6 text-sm text-muted-foreground">Lädt…</div>}>
      <DocReader />
    </Suspense>
  );
}
