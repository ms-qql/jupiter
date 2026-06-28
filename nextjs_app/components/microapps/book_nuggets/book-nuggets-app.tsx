"use client";

// PROJ-53: Native Micro-App „Buch-Nuggets".
// Buch (Upload/Drag&Drop ODER Datei-URL) → headless `hal-book-nuggets`-Session →
// strukturiertes Nugget (md + Abbildungen + PDF, inkl. Contra-Kapitel) im Hal-Vault.
// Reine Ansicht + Steuerung: die gesamte Verarbeitung läuft im Backend-Worker.
// Die Liste POLLT GET /book-nuggets/queue (Tab schließen unterbricht nichts).

import { useCallback, useEffect, useRef, useState } from "react";
import {
  BookOpenIcon,
  PlayIcon,
  Trash2Icon,
  RotateCcwIcon,
  Settings2Icon,
  FileTextIcon,
  FileIcon,
  PlusIcon,
  UploadIcon,
  LinkIcon,
  LibraryIcon,
  CalculatorIcon,
} from "lucide-react";
import { toast } from "sonner";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  ApiError,
  addBookNuggets,
  deleteBookNuggetsItem,
  estimateBookNuggets,
  fileDownloadUrl,
  getBookNuggetsLibrary,
  getBookNuggetsQueue,
  getBookNuggetsSettings,
  mdReaderUrl,
  patchBookNuggetsSettings,
  retryBookNuggetsItem,
  runBookNuggetsNow,
  uploadFiles,
} from "@/lib/api";
import type {
  BookNuggetsAddRequest,
  BookNuggetsDuplicate,
  BookNuggetsEstimate,
  BookNuggetsItem,
  BookNuggetsLibraryItem,
  BookNuggetsModel,
  BookNuggetsModelMode,
  BookNuggetsQueue,
  BookNuggetsSettings,
  BookNuggetsStatus,
} from "@/lib/types";

// Modell-Whitelist (Backend: haiku/sonnet/opus).
const MODEL_CHOICES: { value: BookNuggetsModel; label: string }[] = [
  { value: "haiku", label: "Haiku (schnell & günstig)" },
  { value: "sonnet", label: "Sonnet (ausgewogen)" },
  { value: "opus", label: "Opus (höchste Qualität)" },
];

// Im MVP unterstützte Formate (mobi bewusst nicht).
const ACCEPT = ".pdf,.epub,.txt,.docx";
const POLL_INTERVAL_MS = 3000;
const LIBRARY_POLL_MS = 10000;

const STATUS_LABEL: Record<BookNuggetsStatus, string> = {
  pending: "Wartend",
  running: "Läuft",
  done: "Fertig",
  error: "Fehler",
};

const PHASE_LABEL: Record<string, string> = {
  parsing: "Parsen",
  analysis: "Analyse",
  contra: "Contra-Recherche",
  pdf: "PDF-Bau",
};

function fmtDate(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function fmtCost(c: number | null): string {
  if (c === null || c === undefined) return "unbekannt";
  return `~${c.toFixed(2)} $`;
}

function StatusBadge({ status, phase }: { status: BookNuggetsStatus; phase?: string | null }) {
  if (status === "done")
    return (
      <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-500">
        {STATUS_LABEL.done}
      </Badge>
    );
  if (status === "error") return <Badge variant="destructive">{STATUS_LABEL.error}</Badge>;
  if (status === "running")
    return (
      <Badge>
        {STATUS_LABEL.running}
        {phase && PHASE_LABEL[phase] ? ` · ${PHASE_LABEL[phase]}` : ""}
      </Badge>
    );
  return <Badge variant="secondary">{STATUS_LABEL.pending}</Badge>;
}

export default function BookNuggetsApp() {
  const [queue, setQueue] = useState<BookNuggetsQueue | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  // Eingabe-Zustand.
  const [sourceMode, setSourceMode] = useState<"upload" | "url">("upload");
  const [urlInput, setUrlInput] = useState("");
  const [uploadPath, setUploadPath] = useState<string | null>(null);
  const [uploadName, setUploadName] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [dragOver, setDragOver] = useState(false);

  // Modell-Steuerung (D7).
  const [modelMode, setModelMode] = useState<BookNuggetsModelMode>("staged");
  const [modelExtract, setModelExtract] = useState<BookNuggetsModel>("sonnet");
  const [modelConsolidate, setModelConsolidate] = useState<BookNuggetsModel>("opus");
  const [pageLimit, setPageLimit] = useState("");

  // Kostenschätzung + Hinzufügen + Duplikat-Konflikt.
  const [estimate, setEstimate] = useState<BookNuggetsEstimate | null>(null);
  const [estimating, setEstimating] = useState(false);
  const [adding, setAdding] = useState(false);
  const [busy, setBusy] = useState(false);
  const [conflict, setConflict] = useState<BookNuggetsDuplicate | null>(null);

  const fileRef = useRef<HTMLInputElement>(null);

  const refresh = useCallback(async (signal?: AbortSignal) => {
    try {
      const q = await getBookNuggetsQueue(signal);
      setQueue(q);
      setLoadError(null);
    } catch (err) {
      if (signal?.aborted) return;
      setLoadError(err instanceof ApiError ? err.message : "Nicht erreichbar");
    }
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    const tick = () => {
      getBookNuggetsQueue(ctrl.signal)
        .then((q) => {
          setQueue(q);
          setLoadError(null);
        })
        .catch((err) => {
          if (ctrl.signal.aborted) return;
          setLoadError(err instanceof ApiError ? err.message : "Nicht erreichbar");
        });
    };
    tick();
    const t = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      ctrl.abort();
      clearInterval(t);
    };
  }, []);

  // Vorbelegung aus den gespeicherten Defaults.
  useEffect(() => {
    getBookNuggetsSettings()
      .then((s) => {
        setModelMode(s.default_model_mode);
        setModelExtract(s.default_model_extract);
        setModelConsolidate(s.default_model_consolidate);
        if (s.default_page_limit) setPageLimit(String(s.default_page_limit));
      })
      .catch(() => {
        /* Defaults bleiben — kein Blocker. */
      });
  }, []);

  function currentSource(): { source_type: "url" | "upload"; source_ref: string } | null {
    if (sourceMode === "url") {
      const ref = urlInput.trim();
      return ref ? { source_type: "url", source_ref: ref } : null;
    }
    return uploadPath ? { source_type: "upload", source_ref: uploadPath } : null;
  }

  function buildRequest(onDuplicate?: "overwrite" | "new_version"): BookNuggetsAddRequest | null {
    const src = currentSource();
    if (!src) return null;
    const limit = pageLimit.trim() ? Math.max(1, Number(pageLimit) || 0) : null;
    return {
      ...src,
      model_mode: modelMode,
      model_extract: modelMode === "single" ? modelConsolidate : modelExtract,
      model_consolidate: modelConsolidate,
      page_limit: limit,
      ...(onDuplicate ? { on_duplicate: onDuplicate } : {}),
    };
  }

  function resetInput() {
    setUrlInput("");
    setUploadPath(null);
    setUploadName(null);
    setEstimate(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  async function handleFile(file: File | undefined) {
    if (!file || uploading) return;
    setUploading(true);
    setEstimate(null);
    try {
      const res = await uploadFiles([file]);
      const f = res.files[0];
      if (!f) throw new ApiError("Upload lieferte keine Datei", 0);
      setUploadPath(f.path);
      setUploadName(f.name);
      toast.success(`Hochgeladen: ${f.name}`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Upload fehlgeschlagen");
    } finally {
      setUploading(false);
    }
  }

  async function handleEstimate() {
    const req = buildRequest();
    if (!req || estimating) return;
    setEstimating(true);
    try {
      setEstimate(await estimateBookNuggets(req));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Schätzung fehlgeschlagen");
    } finally {
      setEstimating(false);
    }
  }

  async function submit(req: BookNuggetsAddRequest) {
    const outcome = await addBookNuggets(req);
    if (!outcome.ok) {
      setConflict(outcome.conflict);
      return;
    }
    toast.success("Buch eingereiht — Verarbeitung gestartet");
    resetInput();
    await refresh();
  }

  async function handleAdd() {
    const req = buildRequest();
    if (!req || adding) return;
    setAdding(true);
    try {
      await submit(req);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Hinzufügen fehlgeschlagen");
    } finally {
      setAdding(false);
    }
  }

  async function handleDuplicateChoice(choice: "overwrite" | "new_version") {
    const req = buildRequest(choice);
    setConflict(null);
    if (!req) return;
    setAdding(true);
    try {
      await submit(req);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Hinzufügen fehlgeschlagen");
    } finally {
      setAdding(false);
    }
  }

  async function handleRunNow() {
    if (busy) return;
    setBusy(true);
    try {
      const q = await runBookNuggetsNow();
      setQueue(q);
      toast.success("Verarbeitung gestartet");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Start fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(id: number) {
    try {
      await deleteBookNuggetsItem(id);
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Entfernen fehlgeschlagen");
    }
  }

  async function handleRetry(id: number) {
    try {
      setQueue(await retryBookNuggetsItem(id));
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Erneut versuchen fehlgeschlagen");
    }
  }

  const items = queue?.items ?? [];
  const sourceReady = currentSource() !== null;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-5 p-5">
      {/* Eingabe */}
      <section className="rounded-xl border border-border bg-card p-4">
        {/* Quellen-Umschalter */}
        <div className="mb-3 inline-flex rounded-lg border border-border p-0.5">
          <Button
            variant={sourceMode === "upload" ? "default" : "ghost"}
            size="sm"
            onClick={() => setSourceMode("upload")}
          >
            <UploadIcon className="size-4" /> Upload
          </Button>
          <Button
            variant={sourceMode === "url" ? "default" : "ghost"}
            size="sm"
            onClick={() => setSourceMode("url")}
          >
            <LinkIcon className="size-4" /> URL
          </Button>
        </div>

        {sourceMode === "upload" ? (
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={(e) => {
              e.preventDefault();
              setDragOver(false);
              void handleFile(e.dataTransfer.files?.[0]);
            }}
            className={`flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-8 text-center transition-colors ${
              dragOver ? "border-primary bg-primary/5" : "border-border"
            }`}
          >
            <BookOpenIcon className="size-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              {uploadName ? (
                <span className="font-medium text-foreground">{uploadName}</span>
              ) : (
                "Buch hierher ziehen oder auswählen (pdf, epub, txt, docx)"
              )}
            </p>
            <input
              ref={fileRef}
              type="file"
              accept={ACCEPT}
              className="hidden"
              onChange={(e) => void handleFile(e.target.files?.[0])}
            />
            <Button
              variant="outline"
              size="sm"
              disabled={uploading}
              onClick={() => fileRef.current?.click()}
            >
              {uploading ? "Lädt hoch…" : "Datei auswählen"}
            </Button>
          </div>
        ) : (
          <div className="grid gap-2">
            <Label htmlFor="bn_url">Direkte Datei-URL (pdf/epub/txt/docx)</Label>
            <Input
              id="bn_url"
              value={urlInput}
              onChange={(e) => {
                setUrlInput(e.target.value);
                setEstimate(null);
              }}
              placeholder="https://example.com/buch.pdf"
              className="font-mono text-xs"
            />
            <p className="text-xs text-muted-foreground">
              Direkter Link zur Buchdatei — keine Produktseite (Goodreads/Amazon liefern
              keinen Volltext).
            </p>
          </div>
        )}

        {/* Modell-Steuerung */}
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <div className="grid gap-2">
            <Label htmlFor="bn_mode">Modell-Modus</Label>
            <Select
              value={modelMode}
              onValueChange={(v) => {
                setModelMode((v as BookNuggetsModelMode) ?? "staged");
                setEstimate(null);
              }}
            >
              <SelectTrigger id="bn_mode" aria-label="Modell-Modus">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="staged">Stufen-Logik (günstig + stark)</SelectItem>
                <SelectItem value="single">Ein Modell für alles</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="bn_limit">Seitenlimit (optional)</Label>
            <Input
              id="bn_limit"
              type="number"
              min={1}
              value={pageLimit}
              onChange={(e) => {
                setPageLimit(e.target.value);
                setEstimate(null);
              }}
              placeholder="z. B. 400"
            />
          </div>
          {modelMode === "staged" && (
            <div className="grid gap-2">
              <Label htmlFor="bn_extract">Extrakt-Modell (Chunks)</Label>
              <Select
                value={modelExtract}
                onValueChange={(v) => {
                  setModelExtract((v as BookNuggetsModel) ?? "sonnet");
                  setEstimate(null);
                }}
              >
                <SelectTrigger id="bn_extract" aria-label="Extrakt-Modell">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MODEL_CHOICES.map((m) => (
                    <SelectItem key={m.value} value={m.value}>
                      {m.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}
          <div className="grid gap-2">
            <Label htmlFor="bn_consolidate">
              {modelMode === "single" ? "Modell" : "Konsolidierung + Contra"}
            </Label>
            <Select
              value={modelConsolidate}
              onValueChange={(v) => {
                setModelConsolidate((v as BookNuggetsModel) ?? "opus");
                setEstimate(null);
              }}
            >
              <SelectTrigger id="bn_consolidate" aria-label="Konsolidierungs-Modell">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {MODEL_CHOICES.map((m) => (
                  <SelectItem key={m.value} value={m.value}>
                    {m.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        {/* Kostenschätzung + Hinzufügen */}
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={handleEstimate}
            disabled={!sourceReady || estimating}
          >
            <CalculatorIcon className="size-4" />
            {estimating ? "Schätze…" : "Kosten schätzen"}
          </Button>
          {estimate && (
            <span className="text-xs text-muted-foreground">
              {estimate.pages ? `~${estimate.pages} Seiten · ` : ""}
              {estimate.est_tokens ? `~${estimate.est_tokens.toLocaleString("de-DE")} Tokens · ` : ""}
              Kosten {fmtCost(estimate.est_cost)}
              {estimate.est_cost === null ? " (URL: erst nach Download bekannt)" : ""}
            </span>
          )}
          <div className="ml-auto">
            <Button onClick={handleAdd} disabled={!sourceReady || adding} size="sm">
              <PlusIcon className="size-4" />
              {adding ? "Reihe ein…" : "Zur Warteschlange hinzufügen"}
            </Button>
          </div>
        </div>
      </section>

      {/* Steuerleiste */}
      <section className="flex flex-wrap items-center gap-3">
        <Button onClick={handleRunNow} disabled={busy} size="sm">
          <PlayIcon className="size-4" />
          Jetzt ausführen
        </Button>
        {queue?.state && (
          <Badge variant={queue.state.status === "running" ? "default" : "outline"}>
            {queue.state.status === "running" ? "Läuft" : "Leerlauf"}
          </Badge>
        )}
        <div className="ml-auto">
          <SettingsDialog />
        </div>
      </section>

      {/* Warteschlange */}
      <section className="rounded-xl border border-border bg-card">
        {loadError && !queue ? (
          <p className="px-4 py-6 text-sm text-red-400">
            Warteschlange nicht erreichbar ({loadError}).
          </p>
        ) : items.length === 0 ? (
          <div className="flex flex-col items-center gap-2 px-4 py-12 text-center">
            <BookOpenIcon className="size-6 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Noch keine Bücher in der Warteschlange.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((item) => (
              <BookRow
                key={item.id}
                item={item}
                onRemove={() => handleRemove(item.id)}
                onRetry={() => handleRetry(item.id)}
              />
            ))}
          </ul>
        )}
      </section>

      {/* Bibliothek */}
      <LibrarySection />

      {/* Duplikat-Dialog (D9) */}
      <Dialog open={conflict !== null} onOpenChange={(o) => !o && setConflict(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>Buch bereits vorhanden</DialogTitle>
            <DialogDescription>
              {conflict?.detail ??
                "Dieses Buch wurde bereits verarbeitet. Überschreiben oder neue Version anlegen?"}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter showCloseButton>
            <Button
              variant="outline"
              onClick={() => handleDuplicateChoice("new_version")}
              disabled={conflict?.existing_status !== "done"}
            >
              Neue Version
            </Button>
            <Button
              onClick={() => handleDuplicateChoice("overwrite")}
              disabled={conflict?.existing_status !== "done"}
            >
              Überschreiben
            </Button>
          </DialogFooter>
          {conflict?.existing_status !== "done" && (
            <p className="text-xs text-muted-foreground">
              Das Buch ist gerade in Bearbeitung — bitte warten, bis es fertig ist.
            </p>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

function LibrarySection() {
  const [items, setItems] = useState<BookNuggetsLibraryItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    const tick = () => {
      getBookNuggetsLibrary(ctrl.signal)
        .then((list) => {
          setItems(list);
          setError(null);
        })
        .catch((err) => {
          if (ctrl.signal.aborted) return;
          setError(err instanceof ApiError ? err.message : "Nicht erreichbar");
        });
    };
    tick();
    const t = setInterval(tick, LIBRARY_POLL_MS);
    return () => {
      ctrl.abort();
      clearInterval(t);
    };
  }, []);

  return (
    <section className="rounded-xl border border-border bg-card">
      <header className="flex items-center gap-2 border-b border-border px-4 py-3">
        <LibraryIcon className="size-4 text-muted-foreground" />
        <h2 className="text-sm font-medium">Bibliothek</h2>
        <span className="text-xs text-muted-foreground">Erzeugte Nuggets im Standard-Ordner</span>
        {items && (
          <Badge variant="outline" className="ml-auto">
            {items.length}
          </Badge>
        )}
      </header>

      {error && !items ? (
        <p className="px-4 py-6 text-sm text-red-400">Bibliothek nicht erreichbar ({error}).</p>
      ) : items === null ? (
        <p className="px-4 py-6 text-sm text-muted-foreground">Lädt…</p>
      ) : items.length === 0 ? (
        <div className="flex flex-col items-center gap-2 px-4 py-12 text-center">
          <FileTextIcon className="size-6 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">Noch keine Nuggets.</p>
        </div>
      ) : (
        <ul className="divide-y divide-border">
          {items.map((item) => (
            <li key={item.md_path} className="flex items-center gap-3 px-4 py-3">
              <div className="min-w-0 flex-1">
                <a
                  href={mdReaderUrl(item.md_path)}
                  className="block truncate text-sm font-medium text-foreground underline-offset-2 hover:text-primary hover:underline"
                  title={item.title}
                >
                  {item.title}
                </a>
                {item.mtime && (
                  <p className="mt-0.5 text-xs text-muted-foreground">{fmtDate(item.mtime)}</p>
                )}
              </div>
              <div className="flex shrink-0 items-center gap-3 text-xs">
                <a
                  href={mdReaderUrl(item.md_path)}
                  className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
                >
                  <FileTextIcon className="size-3.5" /> Notiz
                </a>
                {item.pdf_path && (
                  <a
                    href={fileDownloadUrl(item.pdf_path)}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
                  >
                    <FileIcon className="size-3.5" /> PDF
                  </a>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function BookRow({
  item,
  onRemove,
  onRetry,
}: {
  item: BookNuggetsItem;
  onRemove: () => void;
  onRetry: () => void;
}) {
  const heading =
    item.title || (item.author ? `${item.author} — ?` : null) || item.source_ref;
  return (
    <li className="flex items-start gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground" title={item.source_ref}>
          {heading}
        </p>
        <p className="mt-0.5 truncate font-mono text-[11px] text-muted-foreground">
          {item.source_type === "url" ? item.source_ref : item.source_ref.split("/").pop()}
          {" · "}
          {item.model_mode === "single"
            ? item.model_consolidate
            : `${item.model_extract}→${item.model_consolidate}`}
          {item.cost_estimate !== null ? ` · ~${item.cost_estimate.toFixed(2)} $` : ""}
        </p>
        {item.status === "done" && (
          <div className="mt-1 flex flex-wrap gap-3 text-xs">
            {item.result_note_path && (
              <a
                href={mdReaderUrl(item.result_note_path)}
                className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
              >
                <FileTextIcon className="size-3.5" /> Notiz öffnen
              </a>
            )}
            {item.result_pdf_path && (
              <a
                href={fileDownloadUrl(item.result_pdf_path)}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 text-primary underline-offset-2 hover:underline"
              >
                <FileIcon className="size-3.5" /> PDF
              </a>
            )}
            {!item.result_note_path && !item.result_pdf_path && (
              <span className="text-muted-foreground">Fertig — Pfad nicht ermittelt (siehe Vault).</span>
            )}
          </div>
        )}
        {item.status === "error" && item.error_message && (
          <p className="mt-1 text-xs text-red-400">{item.error_message}</p>
        )}
      </div>

      <div className="flex shrink-0 items-center gap-2">
        <StatusBadge status={item.status} phase={item.phase} />
        {item.status === "error" && (
          <Button variant="ghost" size="icon-sm" onClick={onRetry} title="Erneut versuchen">
            <RotateCcwIcon className="size-4" />
          </Button>
        )}
        <Button variant="ghost" size="icon-sm" onClick={onRemove} title="Entfernen">
          <Trash2Icon className="size-4" />
        </Button>
      </div>
    </li>
  );
}

function SettingsDialog() {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [mode, setMode] = useState<BookNuggetsModelMode>("staged");
  const [extract, setExtract] = useState<BookNuggetsModel>("sonnet");
  const [consolidate, setConsolidate] = useState<BookNuggetsModel>("opus");
  const [limit, setLimit] = useState("");
  const loaded = useRef(false);

  async function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next || loaded.current) return;
    setLoading(true);
    try {
      const s = await getBookNuggetsSettings();
      setMode(s.default_model_mode);
      setExtract(s.default_model_extract);
      setConsolidate(s.default_model_consolidate);
      setLimit(s.default_page_limit ? String(s.default_page_limit) : "");
      loaded.current = true;
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Einstellungen nicht ladbar");
      setOpen(false);
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (saving) return;
    setSaving(true);
    try {
      const patch: Partial<BookNuggetsSettings> = {
        default_model_mode: mode,
        default_model_extract: extract,
        default_model_consolidate: consolidate,
        default_page_limit: limit.trim() ? Math.max(1, Number(limit) || 0) : null,
      };
      const s = await patchBookNuggetsSettings(patch);
      setMode(s.default_model_mode);
      setExtract(s.default_model_extract);
      setConsolidate(s.default_model_consolidate);
      setLimit(s.default_page_limit ? String(s.default_page_limit) : "");
      toast.success("Einstellungen gespeichert");
      setOpen(false);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger
        render={
          <Button variant="outline" size="sm">
            <Settings2Icon className="size-4" />
            Einstellungen
          </Button>
        }
      />
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Buch-Nuggets — Standardwerte</DialogTitle>
          <DialogDescription>
            Vorbelegung für neue Bücher (pro Buch weiterhin überschreibbar).
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <p className="py-6 text-center text-sm text-muted-foreground">Lädt…</p>
        ) : (
          <div className="grid gap-4 py-2">
            <div className="grid gap-2">
              <Label htmlFor="bn_set_mode">Modell-Modus</Label>
              <Select value={mode} onValueChange={(v) => setMode((v as BookNuggetsModelMode) ?? "staged")}>
                <SelectTrigger id="bn_set_mode" aria-label="Modell-Modus">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="staged">Stufen-Logik</SelectItem>
                  <SelectItem value="single">Ein Modell für alles</SelectItem>
                </SelectContent>
              </Select>
            </div>
            {mode === "staged" && (
              <div className="grid gap-2">
                <Label htmlFor="bn_set_extract">Extrakt-Modell</Label>
                <Select value={extract} onValueChange={(v) => setExtract((v as BookNuggetsModel) ?? "sonnet")}>
                  <SelectTrigger id="bn_set_extract" aria-label="Extrakt-Modell">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {MODEL_CHOICES.map((m) => (
                      <SelectItem key={m.value} value={m.value}>
                        {m.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            )}
            <div className="grid gap-2">
              <Label htmlFor="bn_set_consolidate">
                {mode === "single" ? "Modell" : "Konsolidierung + Contra"}
              </Label>
              <Select
                value={consolidate}
                onValueChange={(v) => setConsolidate((v as BookNuggetsModel) ?? "opus")}
              >
                <SelectTrigger id="bn_set_consolidate" aria-label="Konsolidierungs-Modell">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {MODEL_CHOICES.map((m) => (
                    <SelectItem key={m.value} value={m.value}>
                      {m.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="grid gap-2">
              <Label htmlFor="bn_set_limit">Seitenlimit (leer = kein Limit)</Label>
              <Input
                id="bn_set_limit"
                type="number"
                min={1}
                value={limit}
                onChange={(e) => setLimit(e.target.value)}
                placeholder="z. B. 400"
              />
            </div>
          </div>
        )}

        <DialogFooter showCloseButton>
          <Button onClick={handleSave} disabled={loading || saving}>
            {saving ? "Speichert…" : "Speichern"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
