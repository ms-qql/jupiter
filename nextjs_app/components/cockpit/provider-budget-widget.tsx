"use client";

import { useEffect, useState } from "react";
import { RefreshCwIcon } from "lucide-react";
import { ApiError, getProviderBudgets, refreshProviderBudgets } from "@/lib/api";
import type {
  ProviderBudgetRead,
  ProviderBudgetSnapshotRead,
  ProviderBudgetWindowRead,
} from "@/lib/types";
import { cn } from "@/lib/utils";

const MINUTE_MS = 60_000;

type LoadState = "idle" | "loading" | "refreshing" | "error";

export function ProviderBudgetWidget() {
  const [snapshot, setSnapshot] = useState<ProviderBudgetSnapshotRead | null>(null);
  const [state, setState] = useState<LoadState>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [nowMs, setNowMs] = useState(() => Date.now());

  useEffect(() => {
    const ac = new AbortController();
    getProviderBudgets(ac.signal)
      .then((data) => {
        if (ac.signal.aborted) return;
        setSnapshot(data);
        setMessage(null);
        setState("idle");
      })
      .catch((err) => {
        if (ac.signal.aborted) return;
        setMessage(errorText(err, "Budget gerade nicht abrufbar"));
        setState("error");
      });
    return () => ac.abort();
  }, []);

  useEffect(() => {
    if (!snapshot?.ttl_seconds) return;
    const intervalMs = Math.max(1, snapshot.ttl_seconds) * 1000;
    const id = window.setInterval(() => {
      getProviderBudgets()
        .then((data) => {
          setSnapshot(data);
          setMessage(null);
          setState("idle");
        })
        .catch((err) => {
          setMessage(errorText(err, "Aktualisierung fehlgeschlagen"));
          setState((cur) => (cur === "loading" ? "error" : cur));
        });
    }, intervalMs);
    return () => window.clearInterval(id);
  }, [snapshot?.ttl_seconds]);

  useEffect(() => {
    const id = window.setInterval(() => setNowMs(Date.now()), MINUTE_MS);
    return () => window.clearInterval(id);
  }, []);

  async function handleRefresh() {
    if (state === "refreshing") return;
    setState("refreshing");
    try {
      const data = await refreshProviderBudgets();
      setSnapshot(data);
      setMessage(null);
      setState("idle");
    } catch (err) {
      setMessage(errorText(err, "Aktualisierung fehlgeschlagen"));
      setState(snapshot ? "idle" : "error");
    }
  }

  const providerRows = snapshot?.providers ?? [];
  const lastUpdate = snapshot ? relativeTime(snapshot.updated_at) : null;

  return (
    <section className="border-t border-border px-3 py-2" aria-label="Token-Budget">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <div className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
            Budget
          </div>
          {lastUpdate && (
            <div className="truncate text-[0.68rem] tabular-nums text-muted-foreground">
              Stand {lastUpdate}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={state === "refreshing"}
          title="Budget aktualisieren"
          aria-label="Budget aktualisieren"
          className="rounded-md border border-border p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:cursor-not-allowed disabled:opacity-60"
        >
          <RefreshCwIcon
            className={cn("size-3.5", state === "refreshing" && "animate-spin")}
          />
        </button>
      </div>

      {state === "loading" && providerRows.length === 0 ? (
        <BudgetSkeleton />
      ) : providerRows.length > 0 ? (
        <div className="flex flex-col gap-1.5">
          {providerRows.map((provider) => (
            <ProviderRow key={provider.provider} provider={provider} nowMs={nowMs} />
          ))}
        </div>
      ) : (
        <p className="rounded-md border border-dashed border-border px-2 py-2 text-xs text-muted-foreground">
          Budget gerade nicht abrufbar.
        </p>
      )}

      {message && (
        <p className="mt-1.5 truncate text-[0.68rem] text-muted-foreground" title={message}>
          {message}
        </p>
      )}
    </section>
  );
}

function ProviderRow({ provider, nowMs }: { provider: ProviderBudgetRead; nowMs: number }) {
  const disabled = provider.availability !== "available";
  return (
    <div
      className={cn(
        "rounded-md border border-border/70 bg-background/40 px-2 py-1.5",
        disabled && "opacity-70",
      )}
      title={provider.unavailable_reason ?? undefined}
    >
      <div className="mb-1 flex items-center justify-between gap-2">
        <span className="truncate text-xs font-medium">{provider.label}</span>
        <span
          className={cn(
            "shrink-0 rounded-sm px-1.5 py-0.5 text-[0.62rem] font-medium",
            provider.availability === "available"
              ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
              : "bg-muted text-muted-foreground",
          )}
        >
          {availabilityLabel(provider.availability)}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-1.5">
        {provider.windows.map((window) => (
          <BudgetWindowPill
            key={window.window}
            window={window}
            disabled={disabled}
            nowMs={nowMs}
          />
        ))}
      </div>
    </div>
  );
}

function BudgetWindowPill({
  window,
  disabled,
  nowMs,
}: {
  window: ProviderBudgetWindowRead;
  disabled: boolean;
  nowMs: number;
}) {
  const pct = window.used_pct;
  const known = typeof pct === "number";
  const clamped = Math.max(0, Math.min(100, pct ?? 0));
  const quality = qualityLabel(resolveWindowQuality(window, nowMs));
  const resetText = window.reset_at ? formatReset(window.reset_at, nowMs) : null;
  const title = [
    `${window.label}: ${known ? `${pct}% verbraucht` : "n/v"}`,
    resetText ? `Reset ${resetText}` : null,
    `Qualität: ${quality}`,
    window.error,
  ]
    .filter(Boolean)
    .join(" · ");
  return (
    <div
      className={cn(
        "min-w-0 rounded border border-border/70 px-1.5 py-1",
        disabled ? "bg-muted/20" : "bg-card/40",
      )}
      title={title}
    >
      <div className="flex items-center justify-between gap-1">
        <span className="text-[0.65rem] font-medium text-muted-foreground">
          {window.label}
        </span>
        <span className={cn("text-[0.68rem] font-semibold tabular-nums", pctColor(pct))}>
          {known ? `${pct > 100 ? ">" : ""}${Math.min(pct, 100).toFixed(pct % 1 ? 1 : 0)}%` : "n/v"}
        </span>
      </div>
      <div className="mt-1 h-1 overflow-hidden rounded-sm bg-muted">
        <div
          className={cn("h-full rounded-sm", barColor(pct))}
          style={{ width: `${known ? clamped : 0}%` }}
        />
      </div>
      <div className="mt-0.5 flex items-center justify-between gap-1 text-[0.62rem] text-muted-foreground">
        <span className="truncate">{quality}</span>
        <span className="shrink-0 tabular-nums">
          {resetText ?? "kein Reset"}
        </span>
      </div>
    </div>
  );
}

function BudgetSkeleton() {
  return (
    <div className="flex flex-col gap-1.5">
      {[0, 1].map((i) => (
        <div key={i} className="rounded-md border border-border/70 px-2 py-2">
          <div className="mb-2 h-3 w-20 rounded-sm bg-muted" />
          <div className="grid grid-cols-2 gap-1.5">
            <div className="h-11 rounded border border-border/60 bg-muted/40" />
            <div className="h-11 rounded border border-border/60 bg-muted/40" />
          </div>
        </div>
      ))}
    </div>
  );
}

function availabilityLabel(value: ProviderBudgetRead["availability"]): string {
  if (value === "available") return "aktiv";
  if (value === "disabled") return "aus";
  return "n/v";
}

function qualityLabel(value: ProviderBudgetWindowRead["quality"]): string {
  if (value === "live") return "live";
  if (value === "estimated") return "geschätzt";
  if (value === "stale") return "veraltet";
  return "n/v";
}

export function resolveWindowQuality(
  window: Pick<ProviderBudgetWindowRead, "quality" | "reset_at">,
  nowMs: number,
): ProviderBudgetWindowRead["quality"] {
  if (window.quality === "unavailable" || !window.reset_at) return window.quality;
  const resetAtMs = Date.parse(window.reset_at);
  if (Number.isNaN(resetAtMs)) return window.quality;
  return resetAtMs <= nowMs ? "stale" : window.quality;
}

function pctColor(pct: number | null): string {
  if (pct == null) return "text-muted-foreground";
  if (pct >= 90) return "text-red-600 dark:text-red-300";
  if (pct >= 70) return "text-amber-600 dark:text-amber-300";
  return "text-emerald-700 dark:text-emerald-300";
}

function barColor(pct: number | null): string {
  if (pct == null) return "bg-muted";
  if (pct >= 90) return "bg-red-500";
  if (pct >= 70) return "bg-amber-500";
  return "bg-emerald-500";
}

export function formatReset(value: string, nowMs = Date.now()): string {
  const target = Date.parse(value);
  if (Number.isNaN(target)) return "Reset n/v";
  const diff = target - nowMs;
  if (diff <= 0) return "fällig";
  const minutes = Math.round(diff / MINUTE_MS);
  if (minutes < 60) return `in ${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `in ${hours}h`;
  return `in ${Math.round(hours / 24)}d`;
}

function relativeTime(value: string): string {
  const t = Date.parse(value);
  if (Number.isNaN(t)) return "unbekannt";
  const minutes = Math.max(0, Math.round((Date.now() - t) / MINUTE_MS));
  if (minutes < 1) return "gerade eben";
  if (minutes < 60) return `vor ${minutes}m`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `vor ${hours}h`;
  return `vor ${Math.round(hours / 24)}d`;
}

function errorText(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.message || fallback;
  return fallback;
}
