"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangleIcon,
  CheckIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  EyeIcon,
  ImageIcon,
  Loader2Icon,
  RefreshCwIcon,
  SearchIcon,
  Trash2Icon,
  XIcon,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  ApiError,
  applyHalMatches,
  cancelHalQueueItem,
  cleanHalQueue,
  dismissHalMatches,
  getHalRegistry,
  refreshHalRegistry,
  selectHalQueueItems,
  startHalIngest,
} from "@/lib/api";
import type {
  HalRegistryEntry,
  HalRegistryInventoryItem,
  HalRegistryMatchCandidate,
  HalRegistryQueueItem,
  HalRegistryResponse,
} from "@/lib/types";

function useHalRegistry() {
  const [data, setData] = useState<HalRegistryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await getHalRegistry();
      setData(res);
    } catch (err) {
      setData(null);
      setError(
        err instanceof ApiError
          ? err.message
          : "Hal↔Registry-Daten nicht erreichbar.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [reloadKey, load]);

  return {
    data,
    loading,
    error,
    reload: () => setReloadKey((k) => k + 1),
    refresh: async () => {
      setLoading(true);
      try {
        const res = await refreshHalRegistry();
        setData(res);
        setError(null);
      } catch (err) {
        toast.error(
          err instanceof ApiError ? err.message : "Refresh fehlgeschlagen.",
        );
      } finally {
        setLoading(false);
      }
    },
    setData,
  };
}

export function HalRegistryPanel() {
  const { data, loading, error, reload, refresh, setData } = useHalRegistry();
  const [subTab, setSubTab] = useState("library");

  if (error) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertTriangleIcon className="size-4 text-amber-500" />
            Hal↔Registry nicht lesbar
          </CardTitle>
          <CardDescription>{error}</CardDescription>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Der Hal-Workflow benötigt Zugriff auf die Hal-Bibliothek und die
            Registry-Dateien. Queue und vorhandene Kandidaten bleiben
            unabhängig davon nutzbar.
          </p>
          <div className="mt-3 flex gap-2">
            <Button type="button" variant="outline" size="sm" onClick={reload}>
              Erneut versuchen
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <Tabs value={subTab} onValueChange={setSubTab} className="w-full">
          <TabsList>
            <TabsTrigger value="library">Hal-Bibliothek</TabsTrigger>
            <TabsTrigger value="queue">
              Auswahl-Queue
              {(data?.queue ?? []).length > 0 && (
                <Badge variant="secondary" className="ml-1.5 text-xs">
                  {data!.queue.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="matching">
              Matching
              {(data?.candidates ?? []).length > 0 && (
                <Badge variant="secondary" className="ml-1.5 text-xs">
                  {data!.candidates.length}
                </Badge>
              )}
            </TabsTrigger>
            <TabsTrigger value="inventory">Registry-Inventar</TabsTrigger>
          </TabsList>
        </Tabs>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={refresh}
          disabled={loading}
        >
          <RefreshCwIcon
            className={`mr-1.5 size-3.5 ${loading ? "animate-spin" : ""}`}
          />
          Neu laden
        </Button>
      </div>

      {loading ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <Skeleton key={i} className="h-32 rounded-lg" />
          ))}
        </div>
      ) : (
        <>
          <Tabs value={subTab}>
            <TabsContent value="library" className="mt-0">
              <HalLibrarySection
                entries={data?.entries ?? []}
                onSelect={(ids) => handleSelect(ids)}
              />
            </TabsContent>
            <TabsContent value="queue" className="mt-0">
              <QueueSection
                queue={data?.queue ?? []}
                onCancel={(id) => handleCancel(id)}
                onClean={() => handleClean()}
                onIngest={(id) => handleIngest(id)}
              />
            </TabsContent>
            <TabsContent value="matching" className="mt-0">
              <MatchingSection
                candidates={data?.candidates ?? []}
                inventory={data?.inventory ?? []}
                onApply={(matches) => handleApplyMatches(matches)}
                onDismiss={(items) => handleDismissMatches(items)}
              />
            </TabsContent>
            <TabsContent value="inventory" className="mt-0">
              <InventorySection items={data?.inventory ?? []} />
            </TabsContent>
          </Tabs>
        </>
      )}
    </div>
  );

  async function handleSelect(ids: string[]) {
    if (ids.length === 0) return;
    try {
      const res = await selectHalQueueItems(ids, data?.revision);
      setData(res);
      toast.success(`${ids.length} Einträge zur Queue hinzugefügt.`);
    } catch (err) {
      await handleWriteError(err, "Auswahl fehlgeschlagen.");
    }
  }

  async function handleWriteError(err: unknown, fallback: string) {
    if (err instanceof ApiError && err.status === 409) {
      toast.error("Daten wurden zwischenzeitlich geändert — neu geladen.");
      reload();
      return;
    }
    toast.error(err instanceof ApiError ? err.message : fallback);
  }

  async function handleCancel(id: string) {
    try {
      const res = await cancelHalQueueItem(id, data?.revision);
      setData(res);
      toast.success("Eintrag verworfen.");
    } catch (err) {
      await handleWriteError(err, "Fehler beim Verwerfen.");
    }
  }

  async function handleClean() {
    try {
      const res = await cleanHalQueue(data?.revision);
      setData(res);
      toast.success("Queue bereinigt.");
    } catch (err) {
      await handleWriteError(err, "Fehler beim Bereinigen.");
    }
  }

  async function handleApplyMatches(matches: HalRegistryMatchCandidate[]) {
    try {
      const res = await applyHalMatches(matches, data?.revision);
      setData(res);
      toast.success(`${matches.length} Zuordnung(en) bestätigt.`);
    } catch (err) {
      await handleWriteError(err, "Fehler beim Bestätigen der Zuordnungen.");
    }
  }

  async function handleDismissMatches(items: string[]) {
    try {
      const res = await dismissHalMatches(items, data?.revision);
      setData(res);
      toast.success(`${items.length} Vorschlag/Vorschläge entfernt.`);
    } catch (err) {
      await handleWriteError(err, "Fehler beim Entfernen der Vorschläge.");
    }
  }

  async function handleIngest(entryId: string) {
    try {
      const res = await startHalIngest(entryId);
      toast.success(res.message);
      reload();
    } catch (err) {
      toast.error(
        err instanceof ApiError ? err.message : "Ingest-Start fehlgeschlagen.",
      );
    }
  }
}

// ── Hal-Bibliothek ─────────────────────────────────────────────────────────

function HalLibrarySection({
  entries,
  onSelect,
}: {
  entries: HalRegistryEntry[];
  onSelect: (ids: string[]) => void;
}) {
  const [search, setSearch] = useState("");
  const [catFilter, setCatFilter] = useState<string>("__all__");
  const [statusFilter, setStatusFilter] = useState<string>("__all__");
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    return entries.filter((e) => {
      if (search.trim()) {
        const q = search.toLowerCase();
        if (
          !e.name.toLowerCase().includes(q) &&
          !e.rel_path.toLowerCase().includes(q)
        )
          return false;
      }
      if (catFilter !== "__all__" && e.category !== catFilter) return false;
      if (statusFilter === "selected" && e.queue_status !== "selected")
        return false;
      if (statusFilter === "done" && e.queue_status !== "done") return false;
      if (statusFilter === "free" && e.queue_status !== null) return false;
      return true;
    });
  }, [entries, search, catFilter, statusFilter]);

  const toggle = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const selectable = filtered.filter((e) => e.queue_status !== "done");

  return (
    <div className="space-y-3">
      <Card>
        <CardHeader>
          <CardTitle>Hal-Bibliothek durchsuchen</CardTitle>
          <CardDescription>
            Websites und Komponenten aus der Hal-Klon-Bibliothek auswählen und
            zur Queue hinzufügen.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="hal-search">Suche</Label>
            <div className="relative">
              <SearchIcon className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="hal-search"
                className="pl-8"
                placeholder="Name oder Pfad"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label>Kategorie</Label>
              <Select value={catFilter} onValueChange={(v) => v && setCatFilter(v)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">Alle</SelectItem>
                  <SelectItem value="Websites">Websites</SelectItem>
                  <SelectItem value="Components">Komponenten</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>Queue-Status</Label>
              <Select value={statusFilter} onValueChange={(v) => v && setStatusFilter(v)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__all__">Alle</SelectItem>
                  <SelectItem value="free">Nicht in Queue</SelectItem>
                  <SelectItem value="selected">Ausgewählt</SelectItem>
                  <SelectItem value="done">Erledigt</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
        </CardContent>
      </Card>

      {selected.size > 0 && (
        <Card className="border-primary/30">
          <CardContent className="flex items-center justify-between p-3">
            <span className="text-sm font-medium">
              {selected.size} Eintrag/Einträge ausgewählt
            </span>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setSelected(new Set())}
              >
                Auswahl aufheben
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  onSelect([...selected]);
                  setSelected(new Set());
                }}
              >
                Zur Queue hinzufügen
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {filtered.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-center text-sm text-muted-foreground">
            Keine Einträge in der Hal-Bibliothek gefunden.
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {filtered.map((entry) => (
            <HalCard
              key={entry.id}
              entry={entry}
              checked={selected.has(entry.id)}
              disabled={entry.queue_status === "done"}
              onToggle={() => toggle(entry.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function HalCard({
  entry,
  checked,
  disabled,
  onToggle,
}: {
  entry: HalRegistryEntry;
  checked: boolean;
  disabled: boolean;
  onToggle: () => void;
}) {
  return (
    <Card
      size="sm"
      className={`flex flex-col ${checked ? "ring-2 ring-primary/40" : ""}`}
    >
      <CardContent className="space-y-2 p-3">
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={checked}
            disabled={disabled}
            onChange={onToggle}
            className="mt-0.5 size-4 accent-primary"
          />
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <span className="truncate text-sm font-medium">
                {entry.name}
              </span>
              <Badge variant="outline" className="shrink-0 text-xs">
                {entry.category === "Websites" ? "Website" : "Komponente"}
              </Badge>
            </div>
            <p className="truncate font-mono text-xs text-muted-foreground">
              {entry.rel_path}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2 text-xs">
          {entry.has_preview ? (
            <Badge variant="secondary" className="flex items-center gap-1">
              <ImageIcon className="size-3" /> Vorschau
            </Badge>
          ) : (
            <Badge variant="outline" className="flex items-center gap-1 text-muted-foreground">
              <EyeIcon className="size-3" /> Keine Vorschau
            </Badge>
          )}
          {entry.queue_status === "selected" && (
            <Badge className="bg-sky-500/10 text-sky-500">Ausgewählt</Badge>
          )}
          {entry.queue_status === "done" && (
            <Badge className="bg-emerald-500/10 text-emerald-500">Erledigt</Badge>
          )}
          {entry.queue_status === "cancelled" && (
            <Badge className="bg-amber-500/10 text-amber-500">Verworfen</Badge>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ── Auswahl-Queue ──────────────────────────────────────────────────────────

function QueueSection({
  queue,
  onCancel,
  onClean,
  onIngest,
}: {
  queue: HalRegistryQueueItem[];
  onCancel: (id: string) => void;
  onClean: () => void;
  onIngest: (id: string) => void;
}) {
  const [cleanOpen, setCleanOpen] = useState(false);
  const [ingesting, setIngesting] = useState<string | null>(null);

  const selected = queue.filter((q) => q.status === "selected");
  const done = queue.filter((q) => q.status === "done");
  const cancelled = queue.filter((q) => q.status === "cancelled");
  const hasCleanable = done.length > 0 || cancelled.length > 0;

  if (queue.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center text-sm text-muted-foreground">
          Die Auswahl-Queue ist leer. Wähle Einträge aus der Hal-Bibliothek
          aus.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {selected.length > 0 && (
        <div className="space-y-2">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            Ausgewählt ({selected.length})
          </h3>
          <div className="space-y-2">
            {selected.map((item) => (
              <QueueCard
                key={item.id}
                item={item}
                onCancel={() => onCancel(item.id)}
                onIngest={async () => {
                  setIngesting(item.id);
                  await onIngest(item.id);
                  setIngesting(null);
                }}
                ingesting={ingesting === item.id}
              />
            ))}
          </div>
        </div>
      )}

      {done.length > 0 && (
        <div className="space-y-2">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
            Erledigt ({done.length})
          </h3>
          <div className="grid gap-2 md:grid-cols-2">
            {done.map((item) => (
              <QueueCard key={item.id} item={item} />
            ))}
          </div>
        </div>
      )}

      {cancelled.length > 0 && (
        <div className="space-y-2">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
            Verworfen ({cancelled.length})
          </h3>
          <div className="grid gap-2 md:grid-cols-2">
            {cancelled.map((item) => (
              <QueueCard key={item.id} item={item} />
            ))}
          </div>
        </div>
      )}

      {hasCleanable && (
        <div className="flex justify-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => setCleanOpen(true)}
          >
            <Trash2Icon className="mr-1.5 size-3.5" />
            Erledigte/Verworfene entfernen
          </Button>
        </div>
      )}

      <Dialog open={cleanOpen} onOpenChange={setCleanOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Queue bereinigen</DialogTitle>
            <DialogDescription>
              Entfernt {done.length} erledigte und {cancelled.length} verworfene
              Einträge aus der Queue. Ausgewählte Einträge bleiben erhalten.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setCleanOpen(false)}>
              Abbrechen
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => {
                setCleanOpen(false);
                onClean();
              }}
            >
              Entfernen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function QueueCard({
  item,
  onCancel,
  onIngest,
  ingesting,
}: {
  item: HalRegistryQueueItem;
  onCancel?: () => void;
  onIngest?: () => void;
  ingesting?: boolean;
}) {
  return (
    <Card size="sm">
      <CardContent className="flex items-center justify-between gap-3 p-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium">{item.name}</span>
            {item.status === "done" && (
              <Badge className="bg-emerald-500/10 text-emerald-500">Erledigt</Badge>
            )}
            {item.status === "cancelled" && (
              <Badge className="bg-amber-500/10 text-amber-500">Verworfen</Badge>
            )}
          </div>
          <p className="truncate font-mono text-xs text-muted-foreground">
            {item.rel_path}
          </p>
        </div>
        {item.status === "selected" && (
          <div className="flex shrink-0 gap-1">
            {onIngest && (
              <Button
                type="button"
                size="sm"
                disabled={ingesting}
                onClick={onIngest}
              >
                {ingesting ? (
                  <Loader2Icon className="size-3.5 animate-spin" />
                ) : (
                  "Übernehmen"
                )}
              </Button>
            )}
            {onCancel && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onCancel}
              >
                <XIcon className="size-3.5" />
              </Button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ── Matching-Kandidaten ────────────────────────────────────────────────────

function MatchingSection({
  candidates,
  inventory,
  onApply,
  onDismiss,
}: {
  candidates: HalRegistryMatchCandidate[];
  inventory: HalRegistryInventoryItem[];
  onApply: (matches: HalRegistryMatchCandidate[]) => void;
  onDismiss: (items: string[]) => void;
}) {
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [overwriteTarget, setOverwriteTarget] = useState<
    HalRegistryMatchCandidate[] | null
  >(null);

  const existingSourceClone = useMemo(() => {
    const map = new Map<string, string>();
    for (const item of inventory) {
      if (item.source_clone) map.set(item.name, item.source_clone);
    }
    return map;
  }, [inventory]);

  function confirmApply(matches: HalRegistryMatchCandidate[]) {
    const overwrites = matches.filter((m) => {
      const existing = existingSourceClone.get(m.registry_item);
      return existing && existing !== m.suggested_clone;
    });
    if (overwrites.length > 0) {
      setOverwriteTarget(matches);
      return;
    }
    onApply(matches);
  }

  const pending = candidates.filter((c) => !c.confirmed);
  const confirmed = candidates.filter((c) => c.confirmed);
  const unconfirmed = pending;

  const toggle = (key: string) => {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const checkedItems = unconfirmed.filter((c) =>
    checked.has(`${c.registry_item}::${c.suggested_clone}`),
  );

  if (candidates.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center text-sm text-muted-foreground">
          Keine Matching-Kandidaten. Führe „Neu laden“ aus, um Vorschläge zu
          generieren.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {checkedItems.length > 0 && (
        <Card className="border-primary/30">
          <CardContent className="flex items-center justify-between p-3">
            <span className="text-sm font-medium">
              {checkedItems.length} Kandidat/Kandidaten ausgewählt
            </span>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setChecked(new Set())}
              >
                Auswahl aufheben
              </Button>
              <Button
                type="button"
                size="sm"
                onClick={() => {
                  confirmApply(checkedItems);
                  setChecked(new Set());
                }}
              >
                {checkedItems.length} bestätigen
              </Button>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                onClick={() => {
                  onDismiss(checkedItems.map((c) => c.registry_item));
                  setChecked(new Set());
                }}
              >
                Ablehnen
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {unconfirmed.length > 0 && (
        <div className="space-y-2">
          <h3 className="flex items-center gap-2 text-sm font-semibold">
            Offene Vorschläge ({unconfirmed.length})
          </h3>
          <div className="space-y-2">
            {unconfirmed.map((c) => {
              const key = `${c.registry_item}::${c.suggested_clone}`;
              return (
                <CandidateCard
                  key={key}
                  candidate={c}
                  checked={checked.has(key)}
                  onToggle={() => toggle(key)}
                />
              );
            })}
          </div>
        </div>
      )}

      {confirmed.length > 0 && (
        <div className="space-y-2">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
            Bereits bestätigt ({confirmed.length})
          </h3>
          <div className="grid gap-2 md:grid-cols-2">
            {confirmed.map((c) => (
              <CandidateCard key={`${c.registry_item}::${c.suggested_clone}--confirmed`} candidate={c} confirmed />
            ))}
          </div>
        </div>
      )}

      <Dialog
        open={overwriteTarget !== null}
        onOpenChange={(open) => !open && setOverwriteTarget(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Vorhandene Herkunft überschreiben?</DialogTitle>
            <DialogDescription>
              Für die folgenden Registry-Items ist bereits ein anderer{" "}
              <code>source_clone</code>-Pfad hinterlegt. Er wird durch den
              neuen Pfad ersetzt.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2 text-sm">
            {overwriteTarget?.map((m) => {
              const old = existingSourceClone.get(m.registry_item);
              if (!old || old === m.suggested_clone) return null;
              return (
                <div key={m.registry_item} className="rounded border p-2">
                  <div className="font-medium">{m.registry_item}</div>
                  <div className="font-mono text-xs text-muted-foreground line-through">
                    {old}
                  </div>
                  <div className="font-mono text-xs text-emerald-500">
                    {m.suggested_clone}
                  </div>
                </div>
              );
            })}
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => setOverwriteTarget(null)}
            >
              Abbrechen
            </Button>
            <Button
              type="button"
              variant="destructive"
              onClick={() => {
                if (overwriteTarget) onApply(overwriteTarget);
                setOverwriteTarget(null);
              }}
            >
              Überschreiben und bestätigen
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function CandidateCard({
  candidate,
  checked,
  onToggle,
  confirmed,
}: {
  candidate: HalRegistryMatchCandidate;
  checked?: boolean;
  onToggle?: () => void;
  confirmed?: boolean;
}) {
  return (
    <Card
      size="sm"
      className={checked ? "ring-2 ring-primary/40" : ""}
    >
      <CardContent className="flex items-start gap-3 p-3">
        {onToggle && (
          <input
            type="checkbox"
            checked={checked}
            onChange={onToggle}
            className="mt-0.5 size-4 accent-primary"
          />
        )}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-medium">
              {candidate.registry_item}
            </span>
            <Badge variant="outline" className="shrink-0 text-xs">
              Score: {candidate.score}
            </Badge>
            {confirmed && (
              <Badge className="bg-emerald-500/10 text-emerald-500">
                <CheckIcon className="mr-0.5 size-3" />
                Bestätigt
              </Badge>
            )}
          </div>
          <p className="truncate font-mono text-xs text-muted-foreground">
            {candidate.suggested_clone}
          </p>
        </div>
      </CardContent>
    </Card>
  );
}

// ── Registry-Inventar ──────────────────────────────────────────────────────

function InventorySection({
  items,
}: {
  items: HalRegistryInventoryItem[];
}) {
  const [filter, setFilter] = useState<string>("__all__");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    return items.filter((item) => {
      if (search.trim()) {
        const q = search.toLowerCase();
        if (
          !item.name.toLowerCase().includes(q) &&
          !(item.title ?? "").toLowerCase().includes(q)
        )
          return false;
      }
      if (filter === "linked" && item.link_status !== "linked") return false;
      if (filter === "unlinked" && item.link_status !== "unlinked")
        return false;
      if (filter === "missing" && item.link_status !== "missing") return false;
      return true;
    });
  }, [items, filter, search]);

  const linked = filtered.filter((i) => i.link_status === "linked");
  const unlinked = filtered.filter((i) => i.link_status === "unlinked");
  const missing = filtered.filter((i) => i.link_status === "missing");

  if (items.length === 0) {
    return (
      <Card>
        <CardContent className="p-6 text-center text-sm text-muted-foreground">
          Registry-Inventar ist leer.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-3">
      <Card>
        <CardHeader>
          <CardTitle>Registry-Inventar — Herkunftsstatus</CardTitle>
          <CardDescription>
            Zeigt je Registry-Eintrag, ob eine gültige Hal-Herkunft
            (source_clone) existiert.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="inventory-search">Suche</Label>
            <div className="relative">
              <SearchIcon className="absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
              <Input
                id="inventory-search"
                className="pl-8"
                placeholder="Name oder Titel"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>
          <div className="space-y-1.5">
            <Label>Herkunftsstatus</Label>
            <Select value={filter} onValueChange={(v) => v && setFilter(v)}>
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">Alle ({items.length})</SelectItem>
                <SelectItem value="linked">
                  Verknüpft ({items.filter((i) => i.link_status === "linked").length})
                </SelectItem>
                <SelectItem value="unlinked">
                  Nicht verknüpft ({items.filter((i) => i.link_status === "unlinked").length})
                </SelectItem>
                <SelectItem value="missing">
                  Quelle nicht gefunden ({items.filter((i) => i.link_status === "missing").length})
                </SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      {filtered.length === 0 ? (
        <Card>
          <CardContent className="p-6 text-center text-sm text-muted-foreground">
            Keine Treffer für den aktuellen Filter.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {linked.length > 0 && (
            <div className="space-y-2">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-emerald-600">
                <CheckIcon className="size-3.5" /> Verknüpft ({linked.length})
              </h3>
              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {linked.map((item) => (
                  <InventoryCard key={item.name} item={item} />
                ))}
              </div>
            </div>
          )}
          {unlinked.length > 0 && (
            <div className="space-y-2">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
                Nicht verknüpft ({unlinked.length})
              </h3>
              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {unlinked.map((item) => (
                  <InventoryCard key={item.name} item={item} />
                ))}
              </div>
            </div>
          )}
          {missing.length > 0 && (
            <div className="space-y-2">
              <h3 className="flex items-center gap-2 text-sm font-semibold text-amber-600">
                <AlertTriangleIcon className="size-3.5" /> Quelle nicht gefunden ({missing.length})
              </h3>
              <div className="grid gap-2 md:grid-cols-2 xl:grid-cols-3">
                {missing.map((item) => (
                  <InventoryCard key={item.name} item={item} />
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function InventoryCard({ item }: { item: HalRegistryInventoryItem }) {
  const typeLabel = item.type === "registry:template" ? "Template" : "Block";
  return (
    <Card size="sm">
      <CardContent className="space-y-2 p-3">
        <div className="flex items-start justify-between gap-2">
          <span className="truncate text-sm font-medium">
            {item.title ?? item.name}
          </span>
          <Badge variant="outline" className="shrink-0 text-xs">
            {typeLabel}
          </Badge>
        </div>
        <p className="truncate font-mono text-xs text-muted-foreground">
          {item.name}
        </p>
        {item.section && (
          <Badge variant="secondary" className="text-xs">
            {item.section}
          </Badge>
        )}
        {item.source_clone ? (
          <div className="rounded border border-border p-2 text-xs">
            <div className="text-muted-foreground">Herkunft:</div>
            <div className="font-mono">{item.source_clone}</div>
          </div>
        ) : (
          <p className="text-xs text-muted-foreground">Keine Herkunft hinterlegt.</p>
        )}
      </CardContent>
    </Card>
  );
}
