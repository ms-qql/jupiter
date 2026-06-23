"use client";

// PROJ-7: MD-Reader — read-only Vault-/Projekt-Doku im Browser.
// Links: Quellen-Umschalter (Vault | Projekt) + Datei-Baum. Rechts: gerenderte
// MD mit klickbaren Wikilinks + Frontmatter-Panel. Deep-linkbar via ?source=&path=
// (bzw. ?source=vault&rel=… für vault-relative Pointer aus PROJ-5-Handovers).

import { Suspense, useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { ThemeToggle } from "@/components/cockpit/theme-toggle";
import { FileTree } from "@/components/cockpit/file-tree";
import { FrontmatterPanel } from "@/components/cockpit/frontmatter-panel";
import { MarkdownView } from "@/components/cockpit/markdown-view";
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
    (path: string) => {
      if (path === selectedPath) return;
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

  const switchSource = useCallback(
    (source: string) => {
      setActiveSource(source);
      updateUrl(source, selectedPath);
    },
    [updateUrl, selectedPath],
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
              <article>
                <FrontmatterPanel frontmatter={file.frontmatter} />
                <MarkdownView body={file.body} index={wikiIndex} onNavigate={(f) => selectPath(f.path)} />
              </article>
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
