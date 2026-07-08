"use client";

// PROJ-67: Native Micro-App "Peppermint Dashboard".
// Sicht- und Steuerflaeche fuer den lokalen Peppermint-Ticketspiegel. Die
// eigentliche Polling-/Analyse-/Notizsync-Arbeit laeuft serverseitig im Backend.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircleIcon,
  CheckCircle2Icon,
  EyeIcon,
  EyeOffIcon,
  ExternalLinkIcon,
  FilterIcon,
  PencilIcon,
  PlayIcon,
  RefreshCcwIcon,
  RotateCcwIcon,
  Settings2Icon,
  ShieldCheckIcon,
  TicketIcon,
  Trash2Icon,
  Undo2Icon,
} from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
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
import { Separator } from "@/components/ui/separator";
import { Textarea } from "@/components/ui/textarea";
import {
  ApiError,
  getPeppermintProjectOptions,
  getPeppermintSettings,
  getPeppermintStatus,
  getPeppermintSummary,
  getPeppermintTickets,
  hidePeppermintTicket,
  ignorePeppermintTicket,
  patchPeppermintSettings,
  patchPeppermintTicket,
  pollPeppermintNow,
  retryPeppermintAnalysis,
  retryPeppermintNoteSync,
  restorePeppermintTicket,
  startPeppermintResolutionSession,
  unhidePeppermintTicket,
} from "@/lib/api";
import type {
  PeppermintAnalysisStatus,
  PeppermintManualPriority,
  PeppermintManualStatus,
  PeppermintManualType,
  PeppermintProjectOption,
  PeppermintSettings,
  PeppermintStatus,
  PeppermintSummary,
  PeppermintTicket,
} from "@/lib/types";

const POLL_INTERVAL_MS = 4000;

const ANALYSIS_LABEL: Record<PeppermintAnalysisStatus, string> = {
  neu: "Neu",
  wartet: "Wartet",
  laeuft: "Analyse läuft",
  analysiert: "Analysiert",
  fehler: "Fehler",
};

const ANALYSIS_FILTERS = [
  { value: "all", label: "Alle Analysezustände" },
  { value: "neu", label: "Neu" },
  { value: "wartet", label: "Wartet" },
  { value: "laeuft", label: "Analyse läuft" },
  { value: "analysiert", label: "Analysiert" },
  { value: "fehler", label: "Fehler" },
];

const URGENCY_FILTERS = [
  { value: "all", label: "Alle Dringlichkeiten" },
  { value: "Niedrig", label: "Niedrig" },
  { value: "Mittel", label: "Mittel" },
  { value: "Hoch", label: "Hoch" },
  { value: "Dringend", label: "Dringend" },
];

const PRIORITY_LABEL: Record<PeppermintManualPriority, string> = {
  low: "Niedrig",
  medium: "Mittel",
  high: "Hoch",
  urgent: "Dringend",
};

const TYPE_LABEL: Record<PeppermintManualType, string> = {
  question: "Frage",
  incident: "Incident",
  problem: "Problem",
  feature_request: "Feature Request",
  other: "Sonstiges",
};

const MANUAL_STATUS_LABEL: Record<PeppermintManualStatus, string> = {
  open: "Offen",
  assigned: "Zugewiesen",
  on_hold: "On Hold",
  resolved: "Gelöst",
  closed: "Geschlossen",
};

const PRIORITY_OPTIONS = [
  { value: "all", label: "Alle Prioritäten" },
  ...Object.entries(PRIORITY_LABEL).map(([value, label]) => ({ value, label })),
];

const TYPE_OPTIONS = [
  { value: "all", label: "Alle Typen" },
  ...Object.entries(TYPE_LABEL).map(([value, label]) => ({ value, label })),
];

const MANUAL_STATUS_OPTIONS = [
  { value: "all", label: "Alle Status" },
  ...Object.entries(MANUAL_STATUS_LABEL).map(([value, label]) => ({ value, label })),
];

function manualPriorityLabel(value: PeppermintManualPriority | null): string {
  return value ? PRIORITY_LABEL[value] : "-";
}

function manualTypeLabel(value: PeppermintManualType | null): string {
  return value ? TYPE_LABEL[value] : "-";
}

function manualStatusLabel(value: PeppermintManualStatus | null): string {
  return value ? MANUAL_STATUS_LABEL[value] : "-";
}

function fmtDateTime(iso: string | null): string {
  if (!iso) return "nie";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "unbekannt";
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function ageLabel(iso: string | null): string {
  if (!iso) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "-";
  const diff = Date.now() - d.getTime();
  const minutes = Math.max(0, Math.floor(diff / 60000));
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 48) return `${hours} h`;
  return `${Math.floor(hours / 24)} d`;
}

function StatusBadge({ status }: { status: PeppermintAnalysisStatus }) {
  if (status === "analysiert")
    return (
      <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-500">
        {ANALYSIS_LABEL[status]}
      </Badge>
    );
  if (status === "fehler") return <Badge variant="destructive">{ANALYSIS_LABEL[status]}</Badge>;
  if (status === "laeuft") return <Badge>{ANALYSIS_LABEL[status]}</Badge>;
  if (status === "wartet")
    return (
      <Badge className="border-amber-500/40 bg-amber-500/10 text-amber-500">
        {ANALYSIS_LABEL[status]}
      </Badge>
    );
  return <Badge variant="secondary">{ANALYSIS_LABEL[status]}</Badge>;
}

function NoteBadge({ ticket }: { ticket: PeppermintTicket }) {
  if (ticket.note_sync_status === "synchronisiert")
    return (
      <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-500">
        Notiz synchronisiert
      </Badge>
    );
  if (ticket.note_sync_status === "fehler") return <Badge variant="destructive">Sync-Fehler</Badge>;
  if (ticket.note_sync_status === "ausstehend") return <Badge variant="outline">Notiz ausstehend</Badge>;
  return <Badge variant="secondary">Keine Notiz nötig</Badge>;
}

function MetricCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: number | string;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-border bg-card px-4 py-3">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className="mt-1 text-2xl font-semibold tabular-nums">{value}</div>
      {hint && <div className="mt-1 truncate text-xs text-muted-foreground">{hint}</div>}
    </div>
  );
}

function distributionText(values: Record<string, number> | undefined): string {
  const entries = Object.entries(values ?? {})
    .filter(([, count]) => count > 0)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 3);
  if (!entries.length) return "keine Daten";
  return entries.map(([key, count]) => `${key}: ${count}`).join(" · ");
}

export default function PeppermintDashboardApp() {
  const [tickets, setTickets] = useState<PeppermintTicket[]>([]);
  const [summary, setSummary] = useState<PeppermintSummary | null>(null);
  const [status, setStatus] = useState<PeppermintStatus | null>(null);
  const [settings, setSettings] = useState<PeppermintSettings | null>(null);
  const [projectOptions, setProjectOptions] = useState<PeppermintProjectOption[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [editTicket, setEditTicket] = useState<PeppermintTicket | null>(null);
  const [ignoreTicket, setIgnoreTicket] = useState<PeppermintTicket | null>(null);
  const [newSessionTicket, setNewSessionTicket] = useState<PeppermintTicket | null>(null);

  const [analysisFilter, setAnalysisFilter] = useState("all");
  const [urgencyFilter, setUrgencyFilter] = useState("all");
  const [priorityFilter, setPriorityFilter] = useState("all");
  const [typeFilter, setTypeFilter] = useState("all");
  const [manualStatusFilter, setManualStatusFilter] = useState("all");
  const [projectFilter, setProjectFilter] = useState("all");
  const [ticketStatusFilter, setTicketStatusFilter] = useState("");
  const [includeHidden, setIncludeHidden] = useState(false);
  const [includeIgnored, setIncludeIgnored] = useState(false);
  const [query, setQuery] = useState("");

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const filters = {
          analysis_status: analysisFilter === "all" ? undefined : analysisFilter,
          urgency: urgencyFilter === "all" ? undefined : urgencyFilter,
          manual_priority: priorityFilter === "all" ? undefined : priorityFilter,
          manual_type: typeFilter === "all" ? undefined : typeFilter,
          manual_status: manualStatusFilter === "all" ? undefined : manualStatusFilter,
          project_path: projectFilter === "all" ? undefined : projectFilter,
          status: ticketStatusFilter.trim() || undefined,
          include_hidden: includeHidden || undefined,
          include_ignored: includeIgnored || undefined,
          q: query.trim() || undefined,
        };
        const [ticketList, sum, st, cfg, projects] = await Promise.all([
          getPeppermintTickets(filters, signal),
          getPeppermintSummary(signal),
          getPeppermintStatus(signal),
          getPeppermintSettings(signal),
          getPeppermintProjectOptions(signal),
        ]);
        setTickets(ticketList.items);
        setSummary(sum);
        setStatus(st);
        setSettings(cfg);
        setProjectOptions(projects.items);
        setLoadError(null);
      } catch (err) {
        if (signal?.aborted) return;
        setLoadError(err instanceof ApiError ? err.message : "Peppermint-Daten nicht erreichbar");
      }
    },
    [
      analysisFilter,
      urgencyFilter,
      priorityFilter,
      typeFilter,
      manualStatusFilter,
      projectFilter,
      ticketStatusFilter,
      includeHidden,
      includeIgnored,
      query,
    ],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    const tick = () => {
      void refresh(ctrl.signal);
    };
    tick();
    const t = setInterval(tick, POLL_INTERVAL_MS);
    return () => {
      ctrl.abort();
      clearInterval(t);
    };
  }, [refresh]);

  const selected = useMemo(
    () => tickets.find((ticket) => ticket.id === selectedId) ?? tickets[0] ?? null,
    [selectedId, tickets],
  );

  const hasToken = settings?.login_configured || settings?.token_configured;
  const activeLabel = settings?.active ? "Aktiv" : "Deaktiviert";

  function mergeTicket(updated: PeppermintTicket) {
    setTickets((items) => {
      const exists = items.some((item) => item.id === updated.id);
      return exists ? items.map((item) => (item.id === updated.id ? updated : item)) : [updated, ...items];
    });
    setSelectedId(updated.id);
  }

  async function handlePollNow() {
    if (busy) return;
    setBusy(true);
    try {
      const res = await pollPeppermintNow();
      setTickets(res.items);
      await refresh();
      toast.success(`Peppermint-Sync fertig: ${res.items.length} Ticket(s) im Spiegel.`);
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Sync fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleRetryAnalysis(ticket: PeppermintTicket) {
    setBusy(true);
    try {
      const updated = await retryPeppermintAnalysis(ticket.id);
      setTickets((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      toast.success("Analyse erneut eingereiht.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Analyse-Retry fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleRetrySync(ticket: PeppermintTicket) {
    setBusy(true);
    try {
      const updated = await retryPeppermintNoteSync(ticket.id);
      setTickets((items) => items.map((item) => (item.id === updated.id ? updated : item)));
      toast.success("Notiz-Sync erneut eingereiht.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Notiz-Sync fehlgeschlagen");
    } finally {
      setBusy(false);
    }
  }

  async function handleSaveTicket(
    ticket: PeppermintTicket,
    patch: Parameters<typeof patchPeppermintTicket>[1],
  ) {
    setBusy(true);
    try {
      const updated = await patchPeppermintTicket(ticket.id, patch);
      mergeTicket(updated);
      setEditTicket(null);
      toast.success("Ticket-Klassifikation gespeichert.");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Ticket konnte nicht gespeichert werden");
    } finally {
      setBusy(false);
    }
  }

  async function handleHidden(ticket: PeppermintTicket, hidden: boolean) {
    setBusy(true);
    try {
      const updated = hidden
        ? await hidePeppermintTicket(ticket.id)
        : await unhidePeppermintTicket(ticket.id);
      mergeTicket(updated);
      toast.success(hidden ? "Ticket ausgeblendet." : "Ticket eingeblendet.");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Sichtbarkeit konnte nicht geändert werden");
    } finally {
      setBusy(false);
    }
  }

  async function handleIgnore(ticket: PeppermintTicket, reason: string) {
    setBusy(true);
    try {
      const updated = await ignorePeppermintTicket(ticket.id, reason);
      mergeTicket(updated);
      setIgnoreTicket(null);
      toast.success("Ticket lokal entfernt und gegen Reimport gesperrt.");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Ticket konnte nicht entfernt werden");
    } finally {
      setBusy(false);
    }
  }

  async function handleRestore(ticket: PeppermintTicket) {
    setBusy(true);
    try {
      const updated = await restorePeppermintTicket(ticket.id);
      mergeTicket(updated);
      toast.success("Ticket wiederhergestellt.");
      await refresh();
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Ticket konnte nicht wiederhergestellt werden");
    } finally {
      setBusy(false);
    }
  }

  async function handleStartResolution(ticket: PeppermintTicket, force = false) {
    setBusy(true);
    try {
      const updated = await startPeppermintResolutionSession(ticket.id, force);
      mergeTicket(updated);
      toast.success(force ? "Neue weitere Lösungs-Session gestartet." : "Lösungs-Session gestartet.");
      if (updated.resolution_session_id) {
        window.location.href = `/sessions/${updated.resolution_session_id}`;
      }
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Lösungs-Session konnte nicht gestartet werden");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-4 p-5">
      <section className="rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <TicketIcon className="size-5 text-primary" />
              <h1 className="text-base font-semibold">Peppermint Dashboard</h1>
              <Badge variant={settings?.active ? "default" : "secondary"}>{activeLabel}</Badge>
            </div>
            <p className="mt-2 max-w-3xl text-sm text-muted-foreground">
              Lokaler Spiegel für Peppermint-Tickets mit automatischer Frontdesk-Triage,
              Retry-Aktionen und internem Notiz-Sync.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <SettingsDialog settings={settings} onSaved={(cfg) => setSettings(cfg)} />
            <Button variant="outline" size="sm" onClick={() => refresh()} disabled={busy}>
              <RefreshCcwIcon className="size-4" />
              Aktualisieren
            </Button>
            <Button size="sm" onClick={handlePollNow} disabled={busy || !hasToken}>
              <RotateCcwIcon className="size-4" />
              Jetzt synchronisieren
            </Button>
          </div>
        </div>

        <div className="mt-4 grid gap-3 text-sm md:grid-cols-3">
          <div className="flex items-center gap-2 text-muted-foreground">
            <ShieldCheckIcon className="size-4" />
            Token: {hasToken ? "serverseitig konfiguriert" : "nicht konfiguriert"}
          </div>
          <div className="text-muted-foreground">
            Letzter erfolgreicher Poll: {fmtDateTime(status?.last_successful_poll_at ?? null)}
          </div>
          <div className="text-muted-foreground">
            Worker: {status?.worker_status === "running" ? "arbeitet" : "Leerlauf"}
          </div>
        </div>

        {(loadError || status?.last_error) && (
          <div className="mt-4 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertCircleIcon className="mt-0.5 size-4" />
            <span>{loadError || status?.last_error}</span>
          </div>
        )}
      </section>

      <section className="grid gap-3 md:grid-cols-4 lg:grid-cols-8">
        <MetricCard label="Neue Tickets heute" value={summary?.new_today ?? 0} />
        <MetricCard label="Offene Tickets" value={summary?.open_tickets ?? 0} />
        <MetricCard label="Analysiert" value={summary?.analyzed_tickets ?? 0} />
        <MetricCard label="Fehlerhafte Analysen" value={summary?.failed_analyses ?? 0} />
        <MetricCard label="Ausgeblendet" value={summary?.hidden_tickets ?? 0} />
        <MetricCard label="Entfernt" value={summary?.ignored_tickets ?? 0} />
        <MetricCard
          label="Dringlichkeit"
          value={Object.keys(summary?.urgency_distribution ?? {}).length}
          hint={distributionText(summary?.urgency_distribution)}
        />
        <MetricCard
          label="Kurzbefund"
          value={Object.keys(summary?.finding_distribution ?? {}).length}
          hint={distributionText(summary?.finding_distribution)}
        />
      </section>

      <section className="rounded-lg border border-border bg-card p-3">
        <div className="flex flex-wrap items-center gap-2">
          <FilterIcon className="size-4 text-muted-foreground" />
          <Select
            value={analysisFilter}
            onValueChange={(value) => value && setAnalysisFilter(value)}
          >
            <SelectTrigger className="w-[210px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {ANALYSIS_FILTERS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={urgencyFilter}
            onValueChange={(value) => value && setUrgencyFilter(value)}
          >
            <SelectTrigger className="w-[190px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {URGENCY_FILTERS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={priorityFilter}
            onValueChange={(value) => value && setPriorityFilter(value)}
          >
            <SelectTrigger className="w-[170px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PRIORITY_OPTIONS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={typeFilter} onValueChange={(value) => value && setTypeFilter(value)}>
            <SelectTrigger className="w-[180px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {TYPE_OPTIONS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select
            value={manualStatusFilter}
            onValueChange={(value) => value && setManualStatusFilter(value)}
          >
            <SelectTrigger className="w-[170px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {MANUAL_STATUS_OPTIONS.map((item) => (
                <SelectItem key={item.value} value={item.value}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={projectFilter} onValueChange={(value) => value && setProjectFilter(value)}>
            <SelectTrigger className="w-[210px]">
              <SelectValue placeholder="Projekt" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">Alle Projekte</SelectItem>
              {projectOptions.map((project) => (
                <SelectItem key={project.project_path} value={project.project_path}>
                  {project.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Input
            value={ticketStatusFilter}
            onChange={(event) => setTicketStatusFilter(event.target.value)}
            placeholder="Peppermint-Status"
            className="h-9 w-[180px]"
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Suche nach Betreff, Kunde, Kurzbefund, Typ, Status, Priorität"
            className="h-9 min-w-[240px] flex-1"
          />
          <label className="flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm">
            <input
              type="checkbox"
              checked={includeHidden}
              onChange={(event) => setIncludeHidden(event.target.checked)}
              className="size-4"
            />
            Ausgeblendete
          </label>
          <label className="flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm">
            <input
              type="checkbox"
              checked={includeIgnored}
              onChange={(event) => setIncludeIgnored(event.target.checked)}
              className="size-4"
            />
            Entfernte
          </label>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(360px,0.8fr)]">
        <section className="flex h-[460px] flex-col overflow-hidden rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Tickets</h2>
          </div>
          <div className="min-h-0 flex-1 overflow-auto">
            <table className="w-full min-w-[1400px] text-left text-sm">
              <thead className="sticky top-0 z-10 border-b border-border bg-muted text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 font-medium">ID</th>
                  <th className="px-4 py-2 font-medium">Betreff</th>
                  <th className="px-4 py-2 font-medium">Kunde</th>
                  <th className="px-4 py-2 font-medium">Projekt</th>
                  <th className="px-4 py-2 font-medium">Typ</th>
                  <th className="px-4 py-2 font-medium">Priorität</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Alter</th>
                  <th className="px-4 py-2 font-medium">Analyse</th>
                  <th className="px-4 py-2 font-medium">Dringlichkeit</th>
                  <th className="px-4 py-2 font-medium">Kurzbefund</th>
                  <th className="px-4 py-2 font-medium">Aktionen</th>
                </tr>
              </thead>
              <tbody>
                {tickets.map((ticket) => (
                  <tr
                    key={ticket.id}
                    className={`cursor-pointer border-b border-border/60 hover:bg-muted/40 ${
                      selected?.id === ticket.id ? "bg-muted/60" : ""
                    }`}
                    onClick={() => setSelectedId(ticket.id)}
                  >
                    <td className="px-4 py-3 font-mono text-xs">{ticket.peppermint_ticket_id}</td>
                    <td className="max-w-[260px] px-4 py-3">
                      <div className="truncate font-medium">{ticket.title}</div>
                      {ticket.ticket_url && (
                        <a
                          className="mt-1 inline-flex items-center gap-1 text-xs text-primary hover:underline"
                          href={ticket.ticket_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(event) => event.stopPropagation()}
                        >
                          In Peppermint öffnen
                          <ExternalLinkIcon className="size-3" />
                        </a>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {ticket.requester_name || ticket.requester_email || "-"}
                    </td>
                    <td className="max-w-[160px] px-4 py-3">
                      <div className="truncate">{ticket.project_label || ticket.project_path || "-"}</div>
                    </td>
                    <td className="px-4 py-3">{manualTypeLabel(ticket.manual_type)}</td>
                    <td className="px-4 py-3">{manualPriorityLabel(ticket.manual_priority)}</td>
                    <td className="px-4 py-3">{manualStatusLabel(ticket.manual_status)}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {ageLabel(ticket.peppermint_created_at || ticket.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={ticket.analysis_status} />
                    </td>
                    <td className="px-4 py-3">{ticket.urgency || "-"}</td>
                    <td className="max-w-[240px] px-4 py-3 text-muted-foreground">
                      <div className="truncate">{ticket.short_finding || "-"}</div>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          title={ticket.hidden_at ? "Ticket einblenden" : "Ticket ausblenden"}
                          aria-label={ticket.hidden_at ? "Ticket einblenden" : "Ticket ausblenden"}
                          disabled={busy || Boolean(ticket.ignored_at)}
                          onClick={(event) => {
                            event.stopPropagation();
                            void handleHidden(ticket, !ticket.hidden_at);
                          }}
                        >
                          {ticket.hidden_at ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          title="Ticket bearbeiten"
                          aria-label="Ticket bearbeiten"
                          disabled={busy || Boolean(ticket.ignored_at)}
                          onClick={(event) => {
                            event.stopPropagation();
                            setEditTicket(ticket);
                          }}
                        >
                          <PencilIcon className="size-4" />
                        </Button>
                        {ticket.ignored_at ? (
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Ticket wiederherstellen"
                            aria-label="Ticket wiederherstellen"
                            disabled={busy}
                            onClick={(event) => {
                              event.stopPropagation();
                              void handleRestore(ticket);
                            }}
                          >
                            <Undo2Icon className="size-4" />
                          </Button>
                        ) : (
                          <Button
                            variant="ghost"
                            size="icon"
                            title="Ticket entfernen"
                            aria-label="Ticket entfernen"
                            disabled={busy}
                            onClick={(event) => {
                              event.stopPropagation();
                              setIgnoreTicket(ticket);
                            }}
                          >
                            <Trash2Icon className="size-4 text-destructive" />
                          </Button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {!tickets.length && (
            <div className="p-8 text-center text-sm text-muted-foreground">
              Keine Tickets im lokalen Spiegel. Starte einen manuellen Sync oder warte auf den
              nächsten Polling-Lauf.
            </div>
          )}
        </section>

        <TicketDetail
          ticket={selected}
          busy={busy}
          onRetryAnalysis={handleRetryAnalysis}
          onRetrySync={handleRetrySync}
          onEdit={setEditTicket}
          onHidden={handleHidden}
          onIgnore={setIgnoreTicket}
          onRestore={handleRestore}
          onStartResolution={handleStartResolution}
          onStartNewResolution={setNewSessionTicket}
        />
      </div>
      <TicketEditDialog
        key={editTicket?.id ?? "edit-none"}
        ticket={editTicket}
        projectOptions={projectOptions}
        busy={busy}
        onOpenChange={(open) => {
          if (!open) setEditTicket(null);
        }}
        onSave={handleSaveTicket}
      />
      <IgnoreTicketDialog
        key={ignoreTicket?.id ?? "ignore-none"}
        ticket={ignoreTicket}
        busy={busy}
        onOpenChange={(open) => {
          if (!open) setIgnoreTicket(null);
        }}
        onConfirm={handleIgnore}
      />
      <NewResolutionSessionDialog
        key={newSessionTicket?.id ?? "new-session-none"}
        ticket={newSessionTicket}
        busy={busy}
        onOpenChange={(open) => {
          if (!open) setNewSessionTicket(null);
        }}
        onConfirm={(ticket) => {
          setNewSessionTicket(null);
          void handleStartResolution(ticket, true);
        }}
      />
    </div>
  );
}

function TicketDetail({
  ticket,
  busy,
  onRetryAnalysis,
  onRetrySync,
  onEdit,
  onHidden,
  onIgnore,
  onRestore,
  onStartResolution,
  onStartNewResolution,
}: {
  ticket: PeppermintTicket | null;
  busy: boolean;
  onRetryAnalysis: (ticket: PeppermintTicket) => void;
  onRetrySync: (ticket: PeppermintTicket) => void;
  onEdit: (ticket: PeppermintTicket) => void;
  onHidden: (ticket: PeppermintTicket, hidden: boolean) => void;
  onIgnore: (ticket: PeppermintTicket) => void;
  onRestore: (ticket: PeppermintTicket) => void;
  onStartResolution: (ticket: PeppermintTicket) => void;
  onStartNewResolution: (ticket: PeppermintTicket) => void;
}) {
  if (!ticket) {
    return (
      <section className="rounded-lg border border-border bg-card p-5 text-sm text-muted-foreground">
        Wähle ein Ticket aus, um Frontdesk-Report und Sync-Zustand zu sehen.
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-border bg-card">
      <div className="border-b border-border px-4 py-3">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-semibold">{ticket.title}</h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Peppermint-ID {ticket.peppermint_ticket_id} · aktualisiert{" "}
              {fmtDateTime(ticket.peppermint_updated_at || ticket.updated_at)}
            </p>
          </div>
          <StatusBadge status={ticket.analysis_status} />
        </div>
      </div>

      <div className="space-y-4 p-4">
        <div className="flex flex-wrap gap-2">
          <NoteBadge ticket={ticket} />
          {ticket.urgency && <Badge variant="outline">Dringlichkeit: {ticket.urgency}</Badge>}
          <Badge variant="secondary">Priorität: {manualPriorityLabel(ticket.manual_priority)}</Badge>
          <Badge variant="secondary">Typ: {manualTypeLabel(ticket.manual_type)}</Badge>
          <Badge variant="secondary">Status: {manualStatusLabel(ticket.manual_status)}</Badge>
          {ticket.project_label && <Badge variant="outline">Projekt: {ticket.project_label}</Badge>}
          {ticket.status && <Badge variant="outline">Peppermint: {ticket.status}</Badge>}
          {ticket.hidden_at && <Badge variant="outline">Ausgeblendet</Badge>}
          {ticket.ignored_at && <Badge variant="destructive">Entfernt</Badge>}
          {ticket.resolution_session_id && (
            <Badge variant="outline">Session: {ticket.resolution_session_id.slice(0, 8)}</Badge>
          )}
        </div>

        {(ticket.error_message || ticket.sync_error_message || ticket.resolution_session_error) && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {ticket.error_message || ticket.sync_error_message || ticket.resolution_session_error}
          </div>
        )}

        {ticket.peppermint_missing_at && (
          <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-sm text-amber-700">
            Ticket in Peppermint nicht mehr abrufbar (seit {fmtDateTime(ticket.peppermint_missing_at)}). Der
            lokale Datensatz bleibt erhalten; ein lokales Entfernen ist weiterhin möglich.
          </div>
        )}

        <div className="grid gap-3 text-sm">
          <InfoBlock title="Kurzbefund" value={ticket.short_finding} />
          <InfoBlock title="Eingrenzung" value={ticket.scope_hint} />
          <InfoBlock title="Antwortentwurf an den Kunden" value={ticket.customer_reply_draft} />
          <InfoBlock title="Rückfragen-Guidance" value={ticket.missing_info_guidance} />
        </div>

        {ticket.report_text && (
          <>
            <Separator />
            <div>
              <h3 className="mb-2 text-sm font-medium">Vollständiger Frontdesk-Report</h3>
              <Textarea readOnly value={ticket.report_text} className="min-h-[180px] text-xs" />
            </div>
          </>
        )}

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" size="sm" onClick={() => onEdit(ticket)} disabled={busy || Boolean(ticket.ignored_at)}>
            <PencilIcon className="size-4" />
            Bearbeiten
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onHidden(ticket, !ticket.hidden_at)}
            disabled={busy || Boolean(ticket.ignored_at)}
          >
            {ticket.hidden_at ? <EyeOffIcon className="size-4" /> : <EyeIcon className="size-4" />}
            {ticket.hidden_at ? "Einblenden" : "Ausblenden"}
          </Button>
          {ticket.ignored_at ? (
            <Button variant="outline" size="sm" onClick={() => onRestore(ticket)} disabled={busy}>
              <Undo2Icon className="size-4" />
              Wiederherstellen
            </Button>
          ) : (
            <Button variant="outline" size="sm" onClick={() => onIgnore(ticket)} disabled={busy}>
              <Trash2Icon className="size-4" />
              Entfernen
            </Button>
          )}
          <Button
            size="sm"
            onClick={() => onStartResolution(ticket)}
            disabled={busy || ticket.analysis_status !== "analysiert" || Boolean(ticket.ignored_at)}
            title={
              ticket.analysis_status !== "analysiert"
                ? "Erst nach erfolgreicher Analyse verfügbar"
                : "Lösungs-Session starten"
            }
          >
            <PlayIcon className="size-4" />
            {ticket.resolution_session_id ? "Session öffnen" : "Lösungs-Session starten"}
          </Button>
          {ticket.resolution_session_id && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onStartNewResolution(ticket)}
              disabled={busy || ticket.analysis_status !== "analysiert" || Boolean(ticket.ignored_at)}
              title="Startet eine zusätzliche, neue Lösungs-Session für dieses Ticket"
            >
              <PlayIcon className="size-4" />
              Neue weitere Session starten
            </Button>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => onRetryAnalysis(ticket)}
            disabled={busy}
          >
            <RotateCcwIcon className="size-4" />
            Erneut analysieren
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => onRetrySync(ticket)}
            disabled={busy || ticket.analysis_status !== "analysiert"}
          >
            <CheckCircle2Icon className="size-4" />
            Notiz erneut synchronisieren
          </Button>
          {ticket.ticket_url && (
            <a
              href={ticket.ticket_url}
              target="_blank"
              rel="noreferrer"
              className="inline-flex h-7 items-center justify-center gap-1 rounded-lg px-2.5 text-[0.8rem] font-medium hover:bg-muted"
            >
              <ExternalLinkIcon className="size-4" />
              In Peppermint öffnen
            </a>
          )}
        </div>
      </div>
    </section>
  );
}

function InfoBlock({ title, value }: { title: string; value: string | null }) {
  return (
    <div>
      <div className="mb-1 text-xs font-medium text-muted-foreground">{title}</div>
      <div className="rounded-lg border border-border bg-muted/30 p-3">
        {value || <span className="text-muted-foreground">Noch nicht vorhanden</span>}
      </div>
    </div>
  );
}

function TicketEditDialog({
  ticket,
  projectOptions,
  busy,
  onOpenChange,
  onSave,
}: {
  ticket: PeppermintTicket | null;
  projectOptions: PeppermintProjectOption[];
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onSave: (
    ticket: PeppermintTicket,
    patch: Parameters<typeof patchPeppermintTicket>[1],
  ) => void;
}) {
  const [projectPath, setProjectPath] = useState(ticket?.project_path || "none");
  const [priority, setPriority] = useState<PeppermintManualPriority>(ticket?.manual_priority || "low");
  const [type, setType] = useState<PeppermintManualType>(ticket?.manual_type || "other");
  const [manualStatus, setManualStatus] = useState<PeppermintManualStatus>(ticket?.manual_status || "open");

  if (!ticket) return null;

  const selectedProject = projectOptions.find((project) => project.project_path === projectPath);

  return (
    <Dialog open={Boolean(ticket)} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ticket bearbeiten</DialogTitle>
          <DialogDescription>
            Projekt, Priorität, Typ und Status werden lokal in Jupiter gespeichert.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label>Projekt</Label>
            <Select value={projectPath} onValueChange={(value) => value && setProjectPath(value)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="none">Kein Projekt zugewiesen</SelectItem>
                {projectOptions.map((project) => (
                  <SelectItem key={project.project_path} value={project.project_path}>
                    {project.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label>Priorität</Label>
            <Select
              value={priority}
              onValueChange={(value) => value && setPriority(value as PeppermintManualPriority)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(PRIORITY_LABEL).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label>Typ</Label>
            <Select value={type} onValueChange={(value) => value && setType(value as PeppermintManualType)}>
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(TYPE_LABEL).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="grid gap-2">
            <Label>Status</Label>
            <Select
              value={manualStatus}
              onValueChange={(value) => value && setManualStatus(value as PeppermintManualStatus)}
            >
              <SelectTrigger>
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {Object.entries(MANUAL_STATUS_LABEL).map(([value, label]) => (
                  <SelectItem key={value} value={value}>
                    {label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Abbrechen
          </Button>
          <Button
            onClick={() =>
              onSave(ticket, {
                project_path: projectPath === "none" ? "" : projectPath,
                project_label: selectedProject?.label ?? null,
                manual_priority: priority,
                manual_type: type,
                manual_status: manualStatus,
              })
            }
            disabled={busy}
          >
            Speichern
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function IgnoreTicketDialog({
  ticket,
  busy,
  onOpenChange,
  onConfirm,
}: {
  ticket: PeppermintTicket | null;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (ticket: PeppermintTicket, reason: string) => void;
}) {
  const [reason, setReason] = useState("Kein relevantes Ticket");

  if (!ticket) return null;

  return (
    <Dialog open={Boolean(ticket)} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Ticket lokal entfernen?</DialogTitle>
          <DialogDescription>
            Das Ticket wird in Jupiter ausgeblendet und gegen Reimport gesperrt. In Peppermint
            wird es im MVP nicht gelöscht.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 text-sm">
          <div className="rounded-lg border border-border bg-muted/30 p-3">
            <div className="font-medium">{ticket.title}</div>
            <div className="mt-1 font-mono text-xs text-muted-foreground">
              Peppermint-ID {ticket.peppermint_ticket_id}
            </div>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="ignore-reason">Grund</Label>
            <Input
              id="ignore-reason"
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Abbrechen
          </Button>
          <Button variant="destructive" onClick={() => onConfirm(ticket, reason)} disabled={busy}>
            Entfernen
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function NewResolutionSessionDialog({
  ticket,
  busy,
  onOpenChange,
  onConfirm,
}: {
  ticket: PeppermintTicket | null;
  busy: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: (ticket: PeppermintTicket) => void;
}) {
  if (!ticket) return null;

  return (
    <Dialog open={Boolean(ticket)} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Neue weitere Lösungs-Session starten?</DialogTitle>
          <DialogDescription>
            Für dieses Ticket ist bereits eine Session verknüpft. Eine neue Session ersetzt die
            Verknüpfung am Ticket; die bisherige Session bleibt bestehen und ist weiterhin über
            die Sidebar erreichbar.
          </DialogDescription>
        </DialogHeader>
        <div className="rounded-lg border border-border bg-muted/30 p-3 text-sm">
          <div className="font-medium">{ticket.title}</div>
          <div className="mt-1 font-mono text-xs text-muted-foreground">
            Peppermint-ID {ticket.peppermint_ticket_id}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={busy}>
            Abbrechen
          </Button>
          <Button onClick={() => onConfirm(ticket)} disabled={busy}>
            Neue Session starten
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SettingsDialog({
  settings,
  onSaved,
}: {
  settings: PeppermintSettings | null;
  onSaved: (settings: PeppermintSettings) => void;
}) {
  const [open, setOpen] = useState(false);
  const [baseUrl, setBaseUrl] = useState("");
  const [active, setActive] = useState(false);
  const [interval, setIntervalValue] = useState("60");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [apiToken, setApiToken] = useState("");
  const [saving, setSaving] = useState(false);

  function syncFormFromSettings() {
    if (!settings) return;
    setBaseUrl(settings.base_url);
    setActive(settings.active);
    setIntervalValue(String(settings.polling_interval_seconds));
    setWebhookSecret("");
    setApiToken("");
  }

  async function handleSave() {
    if (saving) return;
    setSaving(true);
    try {
      const patch: Parameters<typeof patchPeppermintSettings>[0] = {
        base_url: baseUrl.trim(),
        active,
        polling_interval_seconds: Math.max(15, Number(interval) || 60),
      };
      if (webhookSecret.trim()) patch.webhook_secret = webhookSecret.trim();
      if (apiToken.trim()) patch.api_token = apiToken.trim();
      const saved = await patchPeppermintSettings(patch);
      onSaved(saved);
      setOpen(false);
      toast.success("Peppermint-Einstellungen gespeichert.");
    } catch (err) {
      toast.error(err instanceof ApiError ? err.message : "Speichern fehlgeschlagen");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (nextOpen) syncFormFromSettings();
        setOpen(nextOpen);
      }}
    >
      <DialogTrigger render={<Button variant="outline" size="sm" />}>
        <Settings2Icon className="size-4" />
        Einstellungen
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Peppermint-Verbindung</DialogTitle>
          <DialogDescription>
            Zugangsdaten bleiben serverseitig. Das UI zeigt nur, ob Login, Token und Webhook-Secret
            konfiguriert sind.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="peppermint-base-url">Basis-URL</Label>
            <Input
              id="peppermint-base-url"
              value={baseUrl}
              onChange={(event) => setBaseUrl(event.target.value)}
              placeholder="http://100.125.96.77:3009/"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="peppermint-interval">Polling-Intervall in Sekunden</Label>
            <Input
              id="peppermint-interval"
              value={interval}
              onChange={(event) => setIntervalValue(event.target.value)}
              inputMode="numeric"
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="peppermint-api-token">Peppermint-API-Token neu setzen</Label>
            <Input
              id="peppermint-api-token"
              value={apiToken}
              onChange={(event) => setApiToken(event.target.value)}
              type="password"
              placeholder={settings?.token_configured ? "API-Token ist gesetzt" : "Noch kein API-Token gesetzt"}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="peppermint-webhook-secret">Webhook-Secret neu setzen</Label>
            <Input
              id="peppermint-webhook-secret"
              value={webhookSecret}
              onChange={(event) => setWebhookSecret(event.target.value)}
              type="password"
              placeholder={settings?.webhook_secret_set ? "Secret ist gesetzt" : "Noch kein Secret gesetzt"}
            />
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={active}
              onChange={(event) => setActive(event.target.checked)}
              className="size-4"
            />
            Automatisches Polling aktivieren
          </label>
          <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            Login: {settings?.login_configured ? "konfiguriert" : "nicht konfiguriert"} · Token:{" "}
            {settings?.token_configured ? "konfiguriert" : "nicht konfiguriert"} · Webhook-Secret:{" "}
            {settings?.webhook_secret_set ? "gesetzt" : "nicht gesetzt"}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)}>
            Abbrechen
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            Speichern
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
