"use client";

// Marktplatz/Registry (PROJ-26). Durchsuchbarer Katalog aller Rollen/Skills/
// Agenten: installieren · aktivieren/deaktivieren · versionieren/zurückrollen ·
// als portierbares .jupkg exportieren/importieren. Import ist zweistufig
// (Capability-/Policy-Vorschau → Bestätigen, Human-in-the-Loop) — importierte
// Definitionen laufen nie ungeprüft mit Vollrechten (PROJ-10 Default-Policy
// konservativ). „Aktiv" = Datei am Resolver-Pfad → steht Sessions/Launcher
// (PROJ-9) automatisch zur Verfügung.

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangleIcon,
  DownloadIcon,
  PackageIcon,
  RotateCcwIcon,
  SearchIcon,
  ShieldAlertIcon,
  Trash2Icon,
  UploadIcon,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  ApiError,
  deleteRegistryEntry,
  exportRegistryPackage,
  getRegistryCatalog,
  getRegistryEntry,
  importRegistryConfirm,
  importRegistryPreview,
  installRegistryEntry,
  rollbackRegistryEntry,
  toggleRegistryEntry,
} from "@/lib/api";
import type {
  PolicyLevel,
  RegistryEntry,
  RegistryEntryDetail,
  RegistryImportPreview,
  RegistryStatus,
  RegistryType,
} from "@/lib/types";

const TYPE_LABEL: Record<RegistryType, string> = {
  role: "Rolle",
  skill: "Skill",
  agent: "Agent",
};

const STATUS_LABEL: Record<RegistryStatus, string> = {
  installed: "installiert",
  active: "aktiv",
  inactive: "inaktiv",
};

const STATUS_BADGE: Record<RegistryStatus, string> = {
  active: "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  inactive: "border-border bg-muted/40 text-muted-foreground",
  installed: "border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-400",
};

const POLICY_LABEL: Record<PolicyLevel, string> = {
  "auto-allow": "Auto-Freigabe",
  card: "Decision Card",
  deny: "Verboten",
};

const POLICY_BADGE: Record<PolicyLevel, string> = {
  "auto-allow": "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  card: "border-orange-500/40 bg-orange-500/10 text-orange-600 dark:text-orange-400",
  deny: "border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400",
};

function errMsg(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

export function RegistryControl() {
  const [entries, setEntries] = useState<RegistryEntry[] | null>(null);
  const [loadFailed, setLoadFailed] = useState(false);
  const [query, setQuery] = useState("");
  const [typFilter, setTypFilter] = useState<RegistryType | "all">("all");
  const [statusFilter, setStatusFilter] = useState<RegistryStatus | "all">("all");
  const [detailKey, setDetailKey] = useState<{ typ: RegistryType; id: string } | null>(
    null,
  );

  const load = useCallback((signal?: AbortSignal) => {
    getRegistryCatalog(undefined, signal)
      .then((cat) => {
        if (!signal?.aborted) {
          setEntries(cat.entries);
          setLoadFailed(false);
        }
      })
      .catch((err) => {
        if (!signal?.aborted) setLoadFailed(err instanceof ApiError);
      });
  }, []);

  useEffect(() => {
    const ac = new AbortController();
    load(ac.signal);
    return () => ac.abort();
  }, [load]);

  // Client-seitiges Filtern — der Katalog ist klein; spart Roundtrips beim Tippen.
  const filtered = useMemo(() => {
    if (!entries) return [];
    const q = query.trim().toLowerCase();
    return entries.filter((e) => {
      if (typFilter !== "all" && e.typ !== typFilter) return false;
      if (statusFilter !== "all" && e.status !== statusFilter) return false;
      if (q && !(`${e.name} ${e.beschreibung} ${e.id}`.toLowerCase().includes(q)))
        return false;
      return true;
    });
  }, [entries, query, typFilter, statusFilter]);

  function patchEntry(updated: RegistryEntry) {
    setEntries((es) =>
      es ? es.map((e) => (e.id === updated.id && e.typ === updated.typ ? updated : e)) : es,
    );
  }
  function dropEntry(typ: RegistryType, id: string) {
    setEntries((es) => (es ? es.filter((e) => !(e.id === id && e.typ === typ)) : es));
  }

  if (loadFailed) {
    return (
      <p className="text-sm text-muted-foreground">
        Katalog nicht ladbar — Backend offline?
      </p>
    );
  }
  if (!entries) {
    return <p className="text-sm text-muted-foreground">Lädt Katalog…</p>;
  }

  return (
    <div className="grid gap-4">
      {/* Such-/Filterleiste */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="relative min-w-44 flex-1">
          <SearchIcon className="absolute left-2 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Katalog durchsuchen…"
            className="h-8 pl-7 text-sm"
            aria-label="Katalog durchsuchen"
          />
        </div>
        <Select value={typFilter} onValueChange={(v) => setTypFilter((v as RegistryType | "all") || "all")}>
          <SelectTrigger size="sm" className="w-32" aria-label="Typ-Filter">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Typen</SelectItem>
            <SelectItem value="role">Rollen</SelectItem>
            <SelectItem value="skill">Skills</SelectItem>
            <SelectItem value="agent">Agenten</SelectItem>
          </SelectContent>
        </Select>
        <Select
          value={statusFilter}
          onValueChange={(v) => setStatusFilter((v as RegistryStatus | "all") || "all")}
        >
          <SelectTrigger size="sm" className="w-32" aria-label="Status-Filter">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Alle Status</SelectItem>
            <SelectItem value="active">aktiv</SelectItem>
            <SelectItem value="inactive">inaktiv</SelectItem>
            <SelectItem value="installed">installiert</SelectItem>
          </SelectContent>
        </Select>
        <ImportDialog onImported={() => load()} />
      </div>

      {/* Katalog / Empty-States */}
      {entries.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-6 text-center">
          <PackageIcon className="mx-auto mb-2 size-6 text-muted-foreground" />
          <p className="text-sm font-medium">Katalog leer</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Importiere ein <span className="font-mono">.jupkg</span>-Paket, um eine
            Rolle/einen Skill/einen Agenten hinzuzufügen.
          </p>
        </div>
      ) : filtered.length === 0 ? (
        <p className="py-4 text-center text-xs text-muted-foreground">
          Keine Treffer für die aktuellen Filter.
        </p>
      ) : (
        <div className="grid gap-2">
          {filtered.map((e) => (
            <CatalogRow
              key={`${e.typ}:${e.id}`}
              entry={e}
              onPatch={patchEntry}
              onOpenDetail={() => setDetailKey({ typ: e.typ, id: e.id })}
            />
          ))}
        </div>
      )}

      {detailKey && (
        <EntryDetailDialog
          typ={detailKey.typ}
          id={detailKey.id}
          onClose={() => setDetailKey(null)}
          onPatch={patchEntry}
          onDeleted={() => {
            dropEntry(detailKey.typ, detailKey.id);
            setDetailKey(null);
          }}
        />
      )}
    </div>
  );
}

// Eine Katalog-Zeile: Name · Typ · Status · Version · Aktion (installieren/
// aktivieren) · Detail öffnen.
function CatalogRow({
  entry,
  onPatch,
  onOpenDetail,
}: {
  entry: RegistryEntry;
  onPatch: (e: RegistryEntry) => void;
  onOpenDetail: () => void;
}) {
  const [busy, setBusy] = useState(false);

  async function act(fn: () => Promise<RegistryEntry>, okMsg: string) {
    if (busy) return;
    setBusy(true);
    try {
      onPatch(await fn());
      toast.success(okMsg);
    } catch (err) {
      toast.error(errMsg(err, "Aktion fehlgeschlagen"));
    } finally {
      setBusy(false);
    }
  }

  const isInstalled = entry.status === "installed";
  const isActive = entry.status === "active";

  return (
    <div className="flex items-center gap-2 rounded-lg border border-border bg-muted/20 p-2.5">
      <button
        type="button"
        onClick={onOpenDetail}
        className="min-w-0 flex-1 text-left"
        aria-label={`Details zu ${entry.name}`}
      >
        <div className="flex items-center gap-2">
          <span className="truncate text-sm font-medium">{entry.name}</span>
          <Badge variant="secondary" className="shrink-0">
            {TYPE_LABEL[entry.typ]}
          </Badge>
          {entry.limited && (
            <Badge
              variant="secondary"
              className="shrink-0 border-orange-500/40 bg-orange-500/10 text-orange-600 dark:text-orange-400"
            >
              eingeschränkt
            </Badge>
          )}
        </div>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {entry.beschreibung || entry.id}
        </p>
      </button>

      <span className="font-mono text-xs text-muted-foreground">v{entry.version}</span>
      <Badge variant="secondary" className={STATUS_BADGE[entry.status]}>
        {STATUS_LABEL[entry.status]}
      </Badge>

      {isInstalled ? (
        <Button
          size="sm"
          variant="outline"
          disabled={busy}
          onClick={() =>
            act(() => installRegistryEntry(entry.typ, entry.id), "Installiert")
          }
        >
          Installieren
        </Button>
      ) : (
        <Button
          size="sm"
          variant={isActive ? "secondary" : "outline"}
          disabled={busy}
          onClick={() =>
            act(
              () => toggleRegistryEntry(entry.typ, entry.id),
              isActive ? "Deaktiviert" : "Aktiviert",
            )
          }
        >
          {isActive ? "Deaktivieren" : "Aktivieren"}
        </Button>
      )}
    </div>
  );
}

// Zweistufiger Import: Datei wählen → Capability-/Policy-Vorschau → Bestätigen.
function ImportDialog({ onImported }: { onImported: () => void }) {
  const [open, setOpen] = useState(false);
  const [preview, setPreview] = useState<RegistryImportPreview | null>(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  function reset() {
    setPreview(null);
    setBusy(false);
    if (fileRef.current) fileRef.current.value = "";
  }

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setBusy(true);
    try {
      setPreview(await importRegistryPreview(file));
    } catch (err) {
      toast.error(errMsg(err, "Paket abgelehnt"));
      reset();
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    if (!preview || busy) return;
    setBusy(true);
    try {
      await importRegistryConfirm(preview.token);
      toast.success(`„${preview.name}" importiert`);
      onImported();
      setOpen(false);
      reset();
    } catch (err) {
      toast.error(errMsg(err, "Import fehlgeschlagen"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        setOpen(o);
        if (!o) reset();
      }}
    >
      <Button size="sm" variant="default" onClick={() => setOpen(true)}>
        <UploadIcon className="size-3.5" /> Import
      </Button>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>Paket importieren</DialogTitle>
          <DialogDescription>
            Ein <span className="font-mono">.jupkg</span> wird zuerst geprüft. Aktiviert
            wird es erst nach deiner Bestätigung — du siehst vorher, was es darf.
          </DialogDescription>
        </DialogHeader>

        {!preview ? (
          <div className="grid gap-3 py-2">
            <input
              ref={fileRef}
              type="file"
              accept=".jupkg,application/zip"
              onChange={onFile}
              disabled={busy}
              className="block w-full text-sm text-muted-foreground file:mr-3 file:rounded-md file:border file:border-border file:bg-muted file:px-3 file:py-1.5 file:text-sm file:font-medium hover:file:bg-muted/70"
              aria-label="Paketdatei wählen"
            />
            {busy && <p className="text-xs text-muted-foreground">Prüft Paket…</p>}
          </div>
        ) : (
          <CapabilityPreview preview={preview} />
        )}

        <DialogFooter>
          <DialogClose
            render={
              <Button variant="ghost" size="sm" disabled={busy}>
                Abbrechen
              </Button>
            }
          />
          {preview && (
            <Button size="sm" onClick={confirm} disabled={busy}>
              {busy ? "Importiert…" : "Importieren & aktivieren"}
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// Was darf das Paket? Angeforderte Tools + konservative Trust-Default-Stufe +
// Herkunfts-/Kollisions-Hinweise. Vor der Aktivierung sichtbar (Transparenz).
function CapabilityPreview({ preview }: { preview: RegistryImportPreview }) {
  return (
    <div className="grid gap-3 py-1">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">{preview.name}</span>
        <Badge variant="secondary">{TYPE_LABEL[preview.typ]}</Badge>
        <span className="font-mono text-xs text-muted-foreground">v{preview.version}</span>
      </div>
      {preview.beschreibung && (
        <p className="text-xs text-muted-foreground">{preview.beschreibung}</p>
      )}

      {!preview.verified && (
        <div className="flex items-start gap-2 rounded-md border border-orange-500/40 bg-orange-500/5 p-2 text-xs text-orange-600 dark:text-orange-400">
          <ShieldAlertIcon className="mt-0.5 size-3.5 shrink-0" />
          <span>
            Quelle nicht verifiziert. Ohne Auth (PROJ-25) lässt sich der Ursprung des
            Pakets nicht bestätigen — Inhalt vor der Aktivierung prüfen.
          </span>
        </div>
      )}

      {preview.collision && (
        <div className="flex items-start gap-2 rounded-md border border-sky-500/40 bg-sky-500/5 p-2 text-xs text-sky-600 dark:text-sky-400">
          <AlertTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
          <span>
            Eine Rolle/ein Skill mit dieser ID existiert bereits — der Import wird als{" "}
            <span className="font-medium">neue Version</span> abgelegt, nichts wird
            überschrieben.
          </span>
        </div>
      )}

      {preview.warnings.map((w, i) => (
        <div
          key={i}
          className="flex items-start gap-2 rounded-md border border-red-500/40 bg-red-500/5 p-2 text-xs text-red-600 dark:text-red-400"
        >
          <AlertTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
          <span>{w}</span>
        </div>
      ))}

      <Separator />

      <div className="grid gap-1.5">
        <Label className="text-xs">Angeforderte Tools ({preview.capabilities.length})</Label>
        {preview.capabilities.length === 0 ? (
          <p className="text-xs text-muted-foreground">Keine — reine Prompt-Definition.</p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {preview.capabilities.map((c) => (
              <Badge key={c} variant="secondary" className="font-mono">
                {c}
              </Badge>
            ))}
          </div>
        )}
      </div>

      <div className="flex items-center gap-2 text-xs">
        <span className="text-muted-foreground">Default-Trust-Policy:</span>
        <Badge variant="secondary" className={POLICY_BADGE[preview.default_policy]}>
          {POLICY_LABEL[preview.default_policy]}
        </Badge>
        <span className="text-muted-foreground">— konservativ, anpassbar in Trust-Policy.</span>
      </div>

      <p className="text-[11px] text-muted-foreground">
        Schema-Version <span className="font-mono">{preview.schema_version}</span>
        {preview.owner ? ` · Owner: ${preview.owner}` : ""}
      </p>
    </div>
  );
}

// Detail eines Eintrags: Definition-Text · Versions-Historie + Rollback ·
// Export · Deinstallieren.
function EntryDetailDialog({
  typ,
  id,
  onClose,
  onPatch,
  onDeleted,
}: {
  typ: RegistryType;
  id: string;
  onClose: () => void;
  onPatch: (e: RegistryEntry) => void;
  onDeleted: () => void;
}) {
  const [detail, setDetail] = useState<RegistryEntryDetail | null>(null);
  const [failed, setFailed] = useState(false);
  const [busy, setBusy] = useState(false);

  const reload = useCallback(
    (signal?: AbortSignal) => {
      return getRegistryEntry(typ, id, signal)
        .then((d) => {
          if (!signal?.aborted) {
            setDetail(d);
            setFailed(false);
          }
        })
        .catch((err) => {
          if (!signal?.aborted) setFailed(err instanceof ApiError);
        });
    },
    [typ, id],
  );

  useEffect(() => {
    const ac = new AbortController();
    reload(ac.signal);
    return () => ac.abort();
  }, [reload]);

  async function rollback(version: string) {
    if (busy) return;
    setBusy(true);
    try {
      const updated = await rollbackRegistryEntry(typ, id, version);
      onPatch(updated);
      await reload();
      toast.success(`Auf v${version} zurückgerollt`);
    } catch (err) {
      toast.error(errMsg(err, "Rollback fehlgeschlagen"));
    } finally {
      setBusy(false);
    }
  }

  async function exportPkg() {
    if (busy) return;
    setBusy(true);
    try {
      await exportRegistryPackage(typ, id);
    } catch (err) {
      toast.error(errMsg(err, "Export fehlgeschlagen"));
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (busy) return;
    if (!window.confirm(`„${detail?.name ?? id}" wirklich deinstallieren?`)) return;
    setBusy(true);
    try {
      await deleteRegistryEntry(typ, id);
      toast.success("Deinstalliert");
      onDeleted();
    } catch (err) {
      toast.error(errMsg(err, "Deinstallieren fehlgeschlagen"));
      setBusy(false);
    }
  }

  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {detail?.name ?? id}
            {detail && <Badge variant="secondary">{TYPE_LABEL[detail.typ]}</Badge>}
          </DialogTitle>
          <DialogDescription>
            {detail?.beschreibung || "Definition, Versionen und Aktionen."}
          </DialogDescription>
        </DialogHeader>

        {failed ? (
          <p className="py-4 text-sm text-muted-foreground">
            Detail nicht ladbar — Backend offline?
          </p>
        ) : !detail ? (
          <p className="py-4 text-sm text-muted-foreground">Lädt Detail…</p>
        ) : (
          <div className="grid gap-4">
            {detail.limited && (
              <div className="flex items-start gap-2 rounded-md border border-orange-500/40 bg-orange-500/5 p-2 text-xs text-orange-600 dark:text-orange-400">
                <AlertTriangleIcon className="mt-0.5 size-3.5 shrink-0" />
                <span>
                  Eingeschränkt lauffähig — die aktuelle Version referenziert ein nicht
                  (mehr) vorhandenes Tool.
                </span>
              </div>
            )}

            {/* Capabilities + Policy */}
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs">
              <span className="text-muted-foreground">Tools:</span>
              {detail.capabilities.length === 0 ? (
                <span className="text-muted-foreground">keine</span>
              ) : (
                detail.capabilities.map((c) => (
                  <Badge key={c} variant="secondary" className="font-mono">
                    {c}
                  </Badge>
                ))
              )}
              <span className="ml-2 text-muted-foreground">Policy:</span>
              <Badge variant="secondary" className={POLICY_BADGE[detail.default_policy]}>
                {POLICY_LABEL[detail.default_policy]}
              </Badge>
            </div>

            {/* Definition */}
            <div className="grid gap-1.5">
              <Label className="text-xs">Definition</Label>
              <ScrollArea className="max-h-48 rounded-md border border-border bg-muted/20 p-2.5">
                <pre className="whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">
                  {detail.definition}
                </pre>
              </ScrollArea>
            </div>

            <Separator />

            {/* Versions-Historie */}
            <div className="grid gap-1.5">
              <Label className="text-xs">Versionen ({detail.versions.length})</Label>
              {detail.versions.length === 0 ? (
                <p className="text-xs text-muted-foreground">Nur die aktuelle Version.</p>
              ) : (
                <div className="grid gap-1.5">
                  {detail.versions.map((v) => {
                    const current = v.version === detail.version;
                    return (
                      <div
                        key={v.version}
                        className="flex items-center gap-2 rounded-md border border-border bg-muted/20 px-2.5 py-1.5"
                      >
                        <span className="font-mono text-xs">v{v.version}</span>
                        {current && (
                          <Badge
                            variant="secondary"
                            className="border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                          >
                            aktuell
                          </Badge>
                        )}
                        {v.limited && (
                          <Badge
                            variant="secondary"
                            className="border-orange-500/40 bg-orange-500/10 text-orange-600 dark:text-orange-400"
                          >
                            eingeschränkt
                          </Badge>
                        )}
                        <span className="truncate text-xs text-muted-foreground">
                          {v.note || v.created_at}
                        </span>
                        {!current && (
                          <Button
                            size="sm"
                            variant="ghost"
                            className="ml-auto h-7"
                            disabled={busy}
                            onClick={() => rollback(v.version)}
                          >
                            <RotateCcwIcon className="size-3.5" /> Zurückrollen
                          </Button>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        <DialogFooter className="sm:justify-between">
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground hover:text-red-500"
            disabled={busy || !detail}
            onClick={remove}
          >
            <Trash2Icon className="size-3.5" /> Deinstallieren
          </Button>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" disabled={busy || !detail} onClick={exportPkg}>
              <DownloadIcon className="size-3.5" /> Export (.jupkg)
            </Button>
            <DialogClose
              render={
                <Button variant="secondary" size="sm">
                  Schließen
                </Button>
              }
            />
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
