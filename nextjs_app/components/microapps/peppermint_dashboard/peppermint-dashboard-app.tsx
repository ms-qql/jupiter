"use client";

// PROJ-67: Native Micro-App "Peppermint Dashboard".
// Sicht- und Steuerflaeche fuer den lokalen Peppermint-Ticketspiegel. Die
// eigentliche Polling-/Analyse-/Notizsync-Arbeit laeuft serverseitig im Backend.

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertCircleIcon,
  CheckCircle2Icon,
  ExternalLinkIcon,
  FilterIcon,
  RefreshCcwIcon,
  RotateCcwIcon,
  Settings2Icon,
  ShieldCheckIcon,
  TicketIcon,
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
  getPeppermintSettings,
  getPeppermintStatus,
  getPeppermintSummary,
  getPeppermintTickets,
  patchPeppermintSettings,
  pollPeppermintNow,
  retryPeppermintAnalysis,
  retryPeppermintNoteSync,
} from "@/lib/api";
import type {
  PeppermintAnalysisStatus,
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
  const [loadError, setLoadError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [selectedId, setSelectedId] = useState<number | null>(null);

  const [analysisFilter, setAnalysisFilter] = useState("all");
  const [urgencyFilter, setUrgencyFilter] = useState("all");
  const [ticketStatusFilter, setTicketStatusFilter] = useState("");
  const [query, setQuery] = useState("");

  const refresh = useCallback(
    async (signal?: AbortSignal) => {
      try {
        const filters = {
          analysis_status: analysisFilter === "all" ? undefined : analysisFilter,
          urgency: urgencyFilter === "all" ? undefined : urgencyFilter,
          status: ticketStatusFilter.trim() || undefined,
          q: query.trim() || undefined,
        };
        const [ticketList, sum, st, cfg] = await Promise.all([
          getPeppermintTickets(filters, signal),
          getPeppermintSummary(signal),
          getPeppermintStatus(signal),
          getPeppermintSettings(signal),
        ]);
        setTickets(ticketList.items);
        setSummary(sum);
        setStatus(st);
        setSettings(cfg);
        setLoadError(null);
      } catch (err) {
        if (signal?.aborted) return;
        setLoadError(err instanceof ApiError ? err.message : "Peppermint-Daten nicht erreichbar");
      }
    },
    [analysisFilter, urgencyFilter, ticketStatusFilter, query],
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

      <section className="grid gap-3 md:grid-cols-3 lg:grid-cols-6">
        <MetricCard label="Neue Tickets heute" value={summary?.new_today ?? 0} />
        <MetricCard label="Offene Tickets" value={summary?.open_tickets ?? 0} />
        <MetricCard label="Analysiert" value={summary?.analyzed_tickets ?? 0} />
        <MetricCard label="Fehlerhafte Analysen" value={summary?.failed_analyses ?? 0} />
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
          <Input
            value={ticketStatusFilter}
            onChange={(event) => setTicketStatusFilter(event.target.value)}
            placeholder="Ticketstatus"
            className="h-9 w-[160px]"
          />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Suche nach Betreff, Kunde, Kurzbefund"
            className="h-9 min-w-[240px] flex-1"
          />
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1.45fr)_minmax(360px,0.8fr)]">
        <section className="overflow-hidden rounded-lg border border-border bg-card">
          <div className="border-b border-border px-4 py-3">
            <h2 className="text-sm font-semibold">Tickets</h2>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[920px] text-left text-sm">
              <thead className="border-b border-border bg-muted/40 text-xs text-muted-foreground">
                <tr>
                  <th className="px-4 py-2 font-medium">ID</th>
                  <th className="px-4 py-2 font-medium">Betreff</th>
                  <th className="px-4 py-2 font-medium">Kunde</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                  <th className="px-4 py-2 font-medium">Alter</th>
                  <th className="px-4 py-2 font-medium">Analyse</th>
                  <th className="px-4 py-2 font-medium">Dringlichkeit</th>
                  <th className="px-4 py-2 font-medium">Kurzbefund</th>
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
                    <td className="px-4 py-3">{ticket.status || "-"}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {ageLabel(ticket.peppermint_created_at || ticket.created_at)}
                    </td>
                    <td className="px-4 py-3">
                      <StatusBadge status={ticket.analysis_status} />
                    </td>
                    <td className="px-4 py-3">{ticket.urgency || "-"}</td>
                    <td className="max-w-[260px] px-4 py-3 text-muted-foreground">
                      <div className="truncate">{ticket.short_finding || "-"}</div>
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
        />
      </div>
    </div>
  );
}

function TicketDetail({
  ticket,
  busy,
  onRetryAnalysis,
  onRetrySync,
}: {
  ticket: PeppermintTicket | null;
  busy: boolean;
  onRetryAnalysis: (ticket: PeppermintTicket) => void;
  onRetrySync: (ticket: PeppermintTicket) => void;
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
          {ticket.status && <Badge variant="secondary">Ticketstatus: {ticket.status}</Badge>}
        </div>

        {(ticket.error_message || ticket.sync_error_message) && (
          <div className="rounded-lg border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
            {ticket.error_message || ticket.sync_error_message}
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
