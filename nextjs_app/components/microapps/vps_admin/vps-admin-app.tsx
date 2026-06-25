"use client";

// PROJ-42: Native Micro-App „VPS-Admin" — Dashboard.
// Read-only Host-Zustand auf einen Blick: Status-Banner (Gut/Achtung/Kritisch),
// vier Kern-Gauges (CPU/RAM/Disk/Load) mit Sparkline, Info-Kacheln (Uptime/Netz/
// Swap), Top-Prozesse und systemd-Service-Health.
//
// Reine Ansicht: ALLE Bewertung/Schwellen liegen im Backend (eine Quelle der
// Wahrheit, damit Sidebar-Ampel und Banner nie driften). Die App POLLT
// GET /metrics/current; im Hintergrund-Tab wird das Polling gedrosselt und beim
// Zurückkehren sofort ein frischer Wert geholt.

import { useCallback, useEffect, useState } from "react";
import {
  ActivityIcon,
  ClockIcon,
  HardDriveIcon,
  NetworkIcon,
  ServerIcon,
} from "lucide-react";
import { getMetricsCurrent, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";
import type {
  MetricServiceStatus,
  MetricStatus,
  MetricsSnapshot,
} from "@/lib/types";

const POLL_INTERVAL_MS = 5000;

// --- Formatierung (deutsch) --------------------------------------------------

const nf1 = (n: number) =>
  n.toLocaleString("de-DE", { minimumFractionDigits: 1, maximumFractionDigits: 1 });
const nf2 = (n: number) =>
  n.toLocaleString("de-DE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Bytes/s → „1,2 MB/s" (deutsche Dezimalkomma-Schreibweise). */
function fmtRate(bps: number): string {
  if (bps < 1024) return `${Math.round(bps)} B/s`;
  const kb = bps / 1024;
  if (kb < 1024) return `${nf1(kb)} KB/s`;
  const mb = kb / 1024;
  if (mb < 1024) return `${nf1(mb)} MB/s`;
  return `${nf1(mb / 1024)} GB/s`;
}

/** Sekunden seit Boot → „3 T 4 h 12 min". */
function fmtUptime(secs: number): string {
  const s = Math.max(0, Math.floor(secs));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d} T ${h} h ${m} min`;
  if (h > 0) return `${h} h ${m} min`;
  return `${m} min`;
}

// --- Farb-/Status-Tabellen ---------------------------------------------------

const STATUS_TEXT: Record<MetricStatus, string> = {
  green: "text-emerald-500",
  amber: "text-amber-400",
  red: "text-red-500",
};

const BANNER: Record<MetricStatus, { label: string; cls: string; dot: string }> = {
  green: {
    label: "Gut",
    cls: "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
    dot: "bg-emerald-500",
  },
  amber: {
    label: "Achtung",
    cls: "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400",
    dot: "bg-amber-400",
  },
  red: {
    label: "Kritisch",
    cls: "border-red-500/40 bg-red-500/10 text-red-600 dark:text-red-400",
    dot: "bg-red-500",
  },
};

const SERVICE_META: Record<
  MetricServiceStatus,
  { label: string; cls: string }
> = {
  active: { label: "aktiv", cls: "border-emerald-500/40 bg-emerald-500/10 text-emerald-500" },
  inactive: { label: "inaktiv", cls: "border-amber-500/40 bg-amber-500/10 text-amber-500" },
  failed: { label: "fehlerhaft", cls: "border-red-500/40 bg-red-500/10 text-red-500" },
  unknown: { label: "unbekannt", cls: "border-border bg-muted text-muted-foreground" },
};

/** „Niedrig/Erhöht/Hoch" als deutsche Einordnung der Load (Status-abgeleitet). */
const LOAD_WORD: Record<MetricStatus, string> = {
  green: "Niedrig",
  amber: "Erhöht",
  red: "Hoch",
};

export default function VpsAdminApp() {
  const [snap, setSnap] = useState<MetricsSnapshot | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [initialLoading, setInitialLoading] = useState(true);

  // Stiller Refresh (kein Spinner-Flackern je Tick). Abbruch via Signal.
  const fetchNow = useCallback((signal?: AbortSignal) => {
    getMetricsCurrent(signal)
      .then((s) => {
        setSnap(s);
        setLoadError(null);
      })
      .catch((err) => {
        if (signal?.aborted) return;
        setLoadError(err instanceof ApiError ? err.message : "Nicht erreichbar");
      })
      .finally(() => {
        if (!signal?.aborted) setInitialLoading(false);
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    const tick = () => {
      // Hintergrund-Tab: Polling drosseln (Edge Case der Spec).
      if (typeof document !== "undefined" && document.hidden) return;
      fetchNow(ctrl.signal);
    };
    tick();
    const t = setInterval(tick, POLL_INTERVAL_MS);
    // Beim Zurückkehren in den Tab sofort frische Werte holen.
    const onVisible = () => {
      if (!document.hidden) fetchNow(ctrl.signal);
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      ctrl.abort();
      clearInterval(t);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [fetchNow]);

  // --- Loading / Error (vor dem ersten Snapshot) -----------------------------
  if (initialLoading && !snap) {
    return (
      <div className="flex items-center justify-center p-12 text-sm text-muted-foreground">
        Lade Metriken…
      </div>
    );
  }
  if (!snap) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <p className="rounded-lg border border-red-500/40 bg-red-500/5 px-4 py-6 text-sm text-red-400">
          Metriken nicht erreichbar{loadError ? ` (${loadError})` : ""}. Erneuter Versuch
          läuft automatisch.
        </p>
      </div>
    );
  }

  const banner = BANNER[snap.overall_status];

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-5 p-5">
      {/* Status-Banner */}
      <section
        className={cn(
          "flex items-center gap-3 rounded-xl border px-4 py-3",
          banner.cls,
        )}
      >
        <span className={cn("size-3 shrink-0 rounded-full", banner.dot)} />
        <div className="flex flex-col">
          <span className="text-sm font-semibold leading-tight">
            VPS-Status: {banner.label}
          </span>
          <span className="text-xs opacity-80">
            Abgeleitet aus dem schlechtesten Einzelwert (CPU · RAM · Disk · Load · Dienste).
          </span>
        </div>
        {loadError && (
          <span
            className="ml-auto text-xs opacity-70"
            title="Letzter Abruf fehlgeschlagen — zeige letzten bekannten Stand."
          >
            veraltet
          </span>
        )}
      </section>

      {/* Gauges */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <Gauge
          label="CPU"
          ringPercent={snap.cpu.percent}
          status={snap.cpu.status}
          valueText={nf1(snap.cpu.percent)}
          unit="%"
          footer={`${nf2(snap.cpu.used_cores)} / ${snap.cpu.cores} Cores`}
          history={snap.cpu.history}
        />
        <Gauge
          label="RAM"
          ringPercent={snap.memory.percent}
          status={snap.memory.status}
          valueText={nf1(snap.memory.percent)}
          unit="%"
          footer={`${nf1(snap.memory.used_gb)} / ${nf1(snap.memory.total_gb)} GB`}
          history={snap.memory.history}
        />
        <Gauge
          label={`Disk ${snap.disk.mount}`}
          ringPercent={snap.disk.percent}
          status={snap.disk.status}
          valueText={nf1(snap.disk.percent)}
          unit="%"
          footer={`${nf1(snap.disk.used_gb)} / ${nf1(snap.disk.total_gb)} GB`}
          history={snap.disk.history}
        />
        <Gauge
          label="Load"
          ringPercent={snap.load.per_core}
          status={snap.load.status}
          valueText={nf1(snap.load.per_core)}
          unit="%"
          footer={`Ø ${nf2(snap.load.load1)} · ${LOAD_WORD[snap.load.status]}`}
          history={snap.load.history}
        />
      </section>

      {/* Info-Kacheln */}
      <section className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <InfoCard icon={<ClockIcon className="size-4" />} title="Uptime">
          <span className="text-lg font-semibold">{fmtUptime(snap.uptime_seconds)}</span>
        </InfoCard>
        <InfoCard icon={<NetworkIcon className="size-4" />} title="Netz-I/O">
          <div className="flex flex-col text-sm">
            <span>
              <span className="text-muted-foreground">↓ rx</span>{" "}
              {fmtRate(snap.net.rx_bytes_per_sec)}
            </span>
            <span>
              <span className="text-muted-foreground">↑ tx</span>{" "}
              {fmtRate(snap.net.tx_bytes_per_sec)}
            </span>
          </div>
        </InfoCard>
        <InfoCard icon={<HardDriveIcon className="size-4" />} title="Swap">
          {snap.swap.total_gb > 0 ? (
            <div className="flex flex-col">
              <span className="text-lg font-semibold">{nf1(snap.swap.percent)} %</span>
              <span className="text-xs text-muted-foreground">
                {nf1(snap.swap.used_gb)} / {nf1(snap.swap.total_gb)} GB
              </span>
            </div>
          ) : (
            <span className="text-sm text-muted-foreground">Kein Swap</span>
          )}
        </InfoCard>
      </section>

      {/* Top-Prozesse + Service-Health */}
      <section className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        <div className="rounded-xl border border-border bg-card">
          <header className="flex items-center gap-2 border-b border-border px-4 py-2.5">
            <ActivityIcon className="size-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold">Top-Prozesse</h2>
          </header>
          {snap.top_processes.length === 0 ? (
            <p className="px-4 py-6 text-sm text-muted-foreground">
              Keine Prozessdaten verfügbar.
            </p>
          ) : (
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-xs text-muted-foreground">
                  <th className="px-4 py-1.5 font-medium">Prozess</th>
                  <th className="px-2 py-1.5 font-medium">PID</th>
                  <th className="px-2 py-1.5 text-right font-medium">CPU</th>
                  <th className="px-4 py-1.5 text-right font-medium">RAM</th>
                </tr>
              </thead>
              <tbody>
                {snap.top_processes.map((p) => (
                  <tr key={p.pid} className="border-t border-border/60">
                    <td className="max-w-[10rem] truncate px-4 py-1.5" title={p.name}>
                      {p.name}
                    </td>
                    <td className="px-2 py-1.5 font-mono text-xs text-muted-foreground">
                      {p.pid}
                    </td>
                    <td className="px-2 py-1.5 text-right tabular-nums">
                      {nf1(p.cpu_percent)} %
                    </td>
                    <td className="px-4 py-1.5 text-right tabular-nums">
                      {nf1(p.mem_percent)} %
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="rounded-xl border border-border bg-card">
          <header className="flex items-center gap-2 border-b border-border px-4 py-2.5">
            <ServerIcon className="size-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold">Dienste</h2>
          </header>
          {snap.services.length === 0 ? (
            <p className="px-4 py-6 text-sm text-muted-foreground">
              Keine Dienste konfiguriert.
            </p>
          ) : (
            <ul className="divide-y divide-border/60">
              {snap.services.map((s) => {
                const meta = SERVICE_META[s.status];
                return (
                  <li
                    key={s.name}
                    className="flex items-center justify-between px-4 py-2.5"
                  >
                    <span className="font-mono text-xs text-foreground">{s.name}</span>
                    <span
                      className={cn(
                        "rounded-md border px-2 py-0.5 text-xs font-medium",
                        meta.cls,
                      )}
                    >
                      {meta.label}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </section>
    </div>
  );
}

// --- Gauge (leichtgewichtiges SVG, kein Plotly) ------------------------------

function Gauge({
  label,
  ringPercent,
  status,
  valueText,
  unit,
  footer,
  history,
}: {
  label: string;
  ringPercent: number;
  status: MetricStatus;
  valueText: string;
  unit: string;
  footer: string;
  history: number[];
}) {
  const pct = Math.max(0, Math.min(100, ringPercent));
  const r = 38;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - pct / 100);
  return (
    <div className="flex flex-col items-center gap-2 rounded-xl border border-border bg-card p-3">
      <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </span>
      <div className="relative">
        <svg width="96" height="96" viewBox="0 0 96 96" className="-rotate-90">
          <circle
            cx="48"
            cy="48"
            r={r}
            fill="none"
            strokeWidth="8"
            className="stroke-muted"
          />
          <circle
            cx="48"
            cy="48"
            r={r}
            fill="none"
            strokeWidth="8"
            strokeLinecap="round"
            strokeDasharray={c}
            strokeDashoffset={offset}
            className={cn("transition-[stroke-dashoffset] duration-500", STATUS_TEXT[status])}
            stroke="currentColor"
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="text-lg font-semibold leading-none tabular-nums">
            {valueText}
          </span>
          <span className="text-[10px] text-muted-foreground">{unit}</span>
        </div>
      </div>
      <Sparkline history={history} status={status} />
      <span className="text-center text-xs text-muted-foreground">{footer}</span>
    </div>
  );
}

/** Mini-SVG-Verlauf. Feste 0..max(100,peak)-Skala → kein „springender" Graph bei
 *  frisch gebootetem VPS / kurzer Historie (Edge Case der Spec). */
function Sparkline({
  history,
  status,
}: {
  history: number[];
  status: MetricStatus;
}) {
  const w = 88;
  const h = 22;
  if (history.length < 2) {
    return <div className="h-[22px] w-[88px]" aria-hidden />;
  }
  const scaleMax = Math.max(100, ...history);
  const n = history.length;
  const pts = history
    .map((v, i) => {
      const x = (i / (n - 1)) * w;
      const y = h - (Math.max(0, v) / scaleMax) * h;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} aria-hidden>
      <polyline
        points={pts}
        fill="none"
        strokeWidth="1.5"
        strokeLinejoin="round"
        strokeLinecap="round"
        className={STATUS_TEXT[status]}
        stroke="currentColor"
      />
    </svg>
  );
}

function InfoCard({
  icon,
  title,
  children,
}: {
  icon: React.ReactNode;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <div className="mb-1.5 flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {icon}
        {title}
      </div>
      {children}
    </div>
  );
}
