// Dünner Client für das Jupiter-FastAPI-Backend (PROJ-1/PROJ-2).
// Basis-URL via NEXT_PUBLIC_API_BASE; Default = lokaler uvicorn auf :8000.

import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "./auth-store";
import type {
  AuthStatus,
  AuthUser,
  LoginResult,
  ClipboardDir,
  DeleteResult,
  DirListing,
  EnginesOverview,
  FileEntry,
  HandoverPreview,
  LaunchSuggestion,
  MdBacklinksResult,
  MdFileRead,
  MdIndexEntry,
  MdIndexResult,
  MdSaveResult,
  MdSource,
  BranchStatus,
  PhaseGateConfig,
  PolicyPreview,
  PolicyRule,
  RecoveryListResult,
  RootEntry,
  EngineSettingsEntry,
  EngineSettingsOverview,
  EngineSettingsValidation,
  Session,
  SessionCreate,
  SessionDetail,
  LivenessLimits,
  LivenessSetting,
  ThresholdSetting,
  TranscriptionResult,
  TranscriptionSetting,
  TrustPolicy,
  UploadResult,
  UsageDrilldownRead,
  UsageRange,
  UsageSummaryRead,
  ScoutRequest,
  ScoutResult,
  VaultRagPreview,
  VaultSearchResult,
  VaultWriteResult,
  WatchdogLimits,
  WatchdogSetting,
  RegistryCatalog,
  RegistryEntry,
  RegistryEntryDetail,
  RegistryImportPreview,
  RegistryType,
  VideoSummaryQueue,
  VideoSummaryAddResult,
  VideoSummarySettings,
  VideoSummaryLibraryItem,
  MetricsSnapshot,
  MetricsStatus,
  TerminalInfo,
  ChallengeRequest,
  ReviewRead,
  FindingRead,
  FindingAction,
  CoordinatorPlan,
  CoordinatorPlanItem,
  CoordinatorFleet,
} from "./types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE?.replace(/\/$/, "") || "http://localhost:8000";

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Roh-Fetch mit Standard-Headern: hängt den Access-Token (PROJ-25) als
 *  Bearer-Header an und schickt Cookies mit (httpOnly-Refresh-Cookie). */
async function rawFetch(
  path: string,
  init?: RequestInit,
  withAuth = true,
): Promise<Response> {
  const headers = new Headers(init?.headers);
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  const token = getAccessToken();
  if (withAuth && token) headers.set("Authorization", `Bearer ${token}`);
  return fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...init,
    headers,
  });
}

/** Nur der Bearer-Header (oder leer) — für Multipart-Fetches, die KEINEN
 *  Content-Type setzen dürfen (Browser setzt die FormData-Boundary). */
function authHeaders(): Record<string, string> {
  const token = getAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// Parallel-401 teilen sich EINEN Refresh-Versuch (kein Token-Sturm).
let refreshInFlight: Promise<boolean> | null = null;

/** Erneuert den Access-Token genau einmal über den Refresh-Cookie. true =
 *  erfolgreich (Token gesetzt), false = Refresh ungültig/abgelaufen. */
export function refreshAccessToken(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const resp = await rawFetch("/auth/refresh", { method: "POST" }, false);
        if (!resp.ok) {
          clearAccessToken();
          return false;
        }
        const body = (await resp.json()) as { access_token: string };
        setAccessToken(body.access_token);
        return true;
      } catch {
        clearAccessToken();
        return false;
      }
    })().finally(() => {
      refreshInFlight = null;
    });
  }
  return refreshInFlight;
}

interface RequestOpts {
  /** Bei 401 erst Refresh+Retry (Default true). */
  retry?: boolean;
  /** Was tun, wenn auch nach Refresh kein Zugriff besteht:
   *  "redirect" → harter Wechsel auf /login (Default), "throw" → nur werfen
   *  (für die Auth-Probes des AuthProviders, die den Redirect selbst steuern). */
  onAuthFail?: "redirect" | "throw";
}

async function request<T>(
  path: string,
  init?: RequestInit,
  opts: RequestOpts = {},
): Promise<T> {
  const { retry = true, onAuthFail = "redirect" } = opts;
  let resp: Response;
  try {
    resp = await rawFetch(path, init);
  } catch {
    throw new ApiError("Backend nicht erreichbar", 0);
  }

  if (resp.status === 401) {
    if (retry && (await refreshAccessToken())) {
      return request<T>(path, init, { ...opts, retry: false });
    }
    if (onAuthFail === "redirect") handleAuthFailure();
    throw new ApiError("Nicht angemeldet", 401);
  }

  if (!resp.ok) {
    let detail = `Fehler ${resp.status}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, resp.status);
  }
  if (resp.status === 204) return undefined as T;
  return (await resp.json()) as T;
}

/** Session endgültig abgelaufen: Token verwerfen und auf die In-App-Login-Seite
 *  leiten. Loop-Schutz: nicht, wenn wir schon auf /login sind. SSR-safe. */
function handleAuthFailure(): void {
  clearAccessToken();
  if (typeof window === "undefined") return;
  if (window.location.pathname.startsWith("/login")) return;
  const next = window.location.pathname + window.location.search;
  window.location.assign(`/login?next=${encodeURIComponent(next)}`);
}

// --- PROJ-25: Auth-Endpunkte (öffentlich + geschützt) ----------------------

/** Fehlertext aus einer fehlgeschlagenen Auth-Antwort ziehen (deutsch). */
async function authErrorDetail(resp: Response, fallback: string): Promise<string> {
  try {
    const body = await resp.json();
    if (body?.detail) return String(body.detail);
  } catch {
    /* ignore */
  }
  return fallback;
}

/** Öffentlich: Username + Passwort → Access-Token (Body) + Refresh-Cookie. */
export async function login(username: string, password: string): Promise<AuthUser> {
  const resp = await rawFetch(
    "/auth/login",
    { method: "POST", body: JSON.stringify({ username, password }) },
    false,
  );
  if (!resp.ok) {
    throw new ApiError(
      await authErrorDetail(resp, "Anmeldung fehlgeschlagen"),
      resp.status,
    );
  }
  const body = (await resp.json()) as LoginResult;
  setAccessToken(body.access_token);
  return body.user;
}

/** Öffentlich, nur bei leerer Nutzerbasis: ersten Account anlegen + einloggen. */
export async function bootstrap(
  username: string,
  password: string,
): Promise<AuthUser> {
  const resp = await rawFetch(
    "/auth/bootstrap",
    { method: "POST", body: JSON.stringify({ username, password }) },
    false,
  );
  if (!resp.ok) {
    throw new ApiError(
      await authErrorDetail(resp, "Konto konnte nicht angelegt werden"),
      resp.status,
    );
  }
  const body = (await resp.json()) as LoginResult;
  setAccessToken(body.access_token);
  return body.user;
}

/** Öffentlich: existiert schon ein Account? Steuert Bootstrap- vs. Login-Modus. */
export async function getAuthStatus(signal?: AbortSignal): Promise<AuthStatus> {
  const resp = await rawFetch("/auth/status", { method: "GET", signal }, false);
  if (!resp.ok) throw new ApiError("Auth-Status nicht abrufbar", resp.status);
  return (await resp.json()) as AuthStatus;
}

/** Geschützt: aktuelle Identität (für AuthProvider-Rehydrierung). */
export function getMe(signal?: AbortSignal): Promise<AuthUser> {
  return request<AuthUser>("/auth/me", { signal }, { onAuthFail: "throw" });
}

/** Refresh-Cookie serverseitig widerrufen, lokalen Access-Token verwerfen. */
export async function logout(): Promise<void> {
  try {
    await rawFetch("/auth/logout", { method: "POST" });
  } catch {
    /* Best-effort: Cookie-Widerruf darf den lokalen Logout nicht blockieren. */
  }
  clearAccessToken();
}

export function listSessions(signal?: AbortSignal): Promise<Session[]> {
  return request<Session[]>("/sessions", { signal });
}

export function getSession(id: string, signal?: AbortSignal): Promise<SessionDetail> {
  return request<SessionDetail>(`/sessions/${id}`, { signal });
}

export function createSession(body: SessionCreate): Promise<Session> {
  return request<Session>("/sessions", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// --- PROJ-18: Engine-Registry ----------------------------------------------

/** Alle konfigurierten Engines/iFrames/Launch-Einträge + Verfügbarkeit (secret-frei).
 *  Speist den Engine-Selector im „Neue Session"-Dialog und das Werkzeuge-Panel. */
export function getEngines(signal?: AbortSignal): Promise<EnginesOverview> {
  return request<EnginesOverview>("/engines", { signal });
}

/** PROJ-51: Bearbeitbare Engine-/Modell-Konfiguration lesen. */
export function getEngineSettings(signal?: AbortSignal): Promise<EngineSettingsOverview> {
  return request<EngineSettingsOverview>("/settings/engines", { signal });
}

/** PROJ-51: Engine-Konfiguration validieren, ohne engines.yaml zu schreiben. */
export function validateEngineSettings(
  engines: EngineSettingsEntry[],
): Promise<EngineSettingsValidation> {
  return request<EngineSettingsValidation>("/settings/engines/validate", {
    method: "POST",
    body: JSON.stringify({ engines }),
  });
}

/** PROJ-51: Engine-Konfiguration validieren und atomar in engines.yaml speichern. */
export function setEngineSettings(
  engines: EngineSettingsEntry[],
): Promise<EngineSettingsOverview> {
  return request<EngineSettingsOverview>("/settings/engines", {
    method: "PUT",
    body: JSON.stringify({ engines }),
  });
}

// --- PROJ-19 (#28/#27): Token-/Kosten-Dashboard ----------------------------

/** Verbrauchs-Aggregat (Tokens/Kosten gesamt + je Modell/Projekt + Cache-Quote). */
export function getUsageSummary(
  range: UsageRange,
  signal?: AbortSignal,
): Promise<UsageSummaryRead> {
  return request<UsageSummaryRead>(`/usage/summary?range=${range}`, { signal });
}

/** Session-Drilldown (nach Tokens absteigend), optional nach Modell/Projekt gefiltert. */
export function getUsageDrilldown(
  range: UsageRange,
  opts?: { model?: string; project?: string },
  signal?: AbortSignal,
): Promise<UsageDrilldownRead> {
  const params = new URLSearchParams({ range });
  if (opts?.model) params.set("model", opts.model);
  if (opts?.project) params.set("project", opts.project);
  return request<UsageDrilldownRead>(`/usage/drilldown?${params.toString()}`, { signal });
}

export function sendInput(id: string, text: string): Promise<{ ok: boolean }> {
  return request(`/sessions/${id}/input`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function stopSession(id: string): Promise<{ ok: boolean }> {
  return request(`/sessions/${id}/stop`, { method: "POST" });
}

// --- PROJ-27: Liveness + Reanimieren ---------------------------------------

/** Hängende/tote Session manuell reaktivieren (claude --resume-Pfad). Liefert den
 *  aktualisierten Session-Zustand. 409 = läuft bereits · 429 = Session-Limit greift
 *  · 503 = Resume/CLI-Fehler (→ ApiError.status). */
export function reanimateSession(id: string): Promise<Session> {
  return request<Session>(`/sessions/${id}/reanimate`, { method: "POST" });
}

// --- PROJ-21: Session-Löschen / Cockpit-Aufräumen --------------------------

/** Eine terminale Session aus dem Live-Index löschen (Vault-Log bleibt erhalten).
 *  204 → void · 404 unbekannt · 409 aktive Session (→ ApiError.status). */
export function deleteSession(id: string): Promise<void> {
  return request<void>(`/sessions/${id}`, { method: "DELETE" });
}

/** Bulk „Erledigte aufräumen": entfernt alle terminalen Sessions, aktive werden
 *  serverseitig still übersprungen. Liefert die Anzahl gelöschter Sessions. */
export function cleanupSessions(): Promise<{ deleted: number }> {
  return request<{ deleted: number }>("/sessions/cleanup", { method: "POST" });
}

/** Decision Card entscheiden: Freigeben / Ablehnen / Mit Kommentar zurück (PROJ-4)
 *  bzw. Wissens-Vorschlag Freigeben / Editieren / Verwerfen (PROJ-15).
 *  `edited` (nur knowledge_proposal): editierter Titel/Body bei „approve". */
export function resolveDecision(
  sessionId: string,
  decisionId: string,
  decision: "approve" | "deny",
  comment?: string,
  edited?: { title?: string | null; body?: string | null },
): Promise<{ ok: boolean }> {
  return request(`/sessions/${sessionId}/decisions/${decisionId}`, {
    method: "POST",
    body: JSON.stringify({
      decision,
      comment: comment ?? null,
      edited_title: edited?.title ?? null,
      edited_body: edited?.body ?? null,
    }),
  });
}

// --- PROJ-23: Cross-Agent-Review / Challenge -------------------------------

/** Eine Challenge auf einem Artefakt der Autor-Session starten → Reviewer-Session.
 *  409 = Rundenlimit erreicht (Eskalation an den Menschen) · 429 = Session-Limit ·
 *  503 = Reviewer-Engine nicht verfügbar (→ ApiError.status). */
export function startChallenge(
  sessionId: string,
  body: ChallengeRequest,
): Promise<ReviewRead> {
  return request<ReviewRead>(`/sessions/${sessionId}/challenge`, {
    method: "POST",
    body: JSON.stringify({
      artifact_pointer: body.artifact_pointer,
      reviewer_engine: body.reviewer_engine ?? null,
      focus: body.focus ?? null,
    }),
  });
}

/** Reviews, in denen diese Session die Autor-Session ist (Befunde werden serverseitig
 *  beim Lesen eingesammelt). */
export function listReviews(
  sessionId: string,
  signal?: AbortSignal,
): Promise<ReviewRead[]> {
  return request<ReviewRead[]>(`/sessions/${sessionId}/reviews`, { signal });
}

/** Pro Befund entscheiden: übernehmen · verwerfen · zurück (+ Kommentar). */
export function resolveFinding(
  reviewId: string,
  findingId: string,
  action: FindingAction,
  comment?: string,
): Promise<FindingRead> {
  return request<FindingRead>(`/reviews/${reviewId}/findings/${findingId}`, {
    method: "POST",
    body: JSON.stringify({ action, comment: comment ?? null }),
  });
}

/** PROJ-15: Vault-Volltextsuche. scope=curated → nur kuratiertes Wissen (projektübergreifend). */
export function searchVault(
  q: string,
  scope: "all" | "curated" = "all",
  limit = 20,
  signal?: AbortSignal,
): Promise<VaultSearchResult> {
  const params = new URLSearchParams({ q, scope, limit: String(limit) });
  return request<VaultSearchResult>(`/vault/search?${params.toString()}`, { signal });
}

// --- PROJ-19 (#23): Pointer/RAG-Vorschau -----------------------------------

/** Gerankte relevante Vault-Ausschnitte statt Volltext + Ersparnis-Messung/Fallback. */
export function getRagPreview(
  q: string,
  topN = 5,
  scope: "all" | "curated" = "all",
  signal?: AbortSignal,
): Promise<VaultRagPreview> {
  const params = new URLSearchParams({ q, top_n: String(topN), scope });
  return request<VaultRagPreview>(`/vault/rag/preview?${params.toString()}`, { signal });
}

// --- PROJ-19 (#26): Späher-Agenten -----------------------------------------

/** Fazit-Aufgabe an einen günstigen Späher delegieren → nur das verdichtete Fazit. */
export function runScout(body: ScoutRequest): Promise<ScoutResult> {
  return request<ScoutResult>("/agents/scout", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// --- PROJ-5: Context-Management & Handover ---------------------------------

/** Handover-Inhalt erzeugen (Vorschau, Hybrid-Gerüst) — schreibt noch NICHT. */
export function generateHandover(id: string): Promise<HandoverPreview> {
  return request<HandoverPreview>(`/sessions/${id}/handover/generate`, {
    method: "POST",
  });
}

/** (ggf. editierten) Handover in den Vault schreiben → liefert den Datei-Pointer. */
export function writeHandover(
  id: string,
  body: string,
  title?: string,
): Promise<VaultWriteResult> {
  return request<VaultWriteResult>(`/sessions/${id}/handover`, {
    method: "POST",
    body: JSON.stringify({ body, title: title ?? null, on_exists: "version" }),
  });
}

/** „Session zurücksetzen": archiviert alt, startet Kind-Session mit Handover-Seed. */
export function resetSession(
  id: string,
  seedContext: string,
  initialPrompt?: string,
): Promise<Session> {
  return request<Session>(`/sessions/${id}/reset`, {
    method: "POST",
    body: JSON.stringify({
      seed_context: seedContext,
      initial_prompt: initialPrompt ?? null,
    }),
  });
}

/** Pro-Session-Override der Kontext-Schwelle (null = globale Schwelle nutzen). */
export function setSessionThreshold(
  id: string,
  thresholdPct: number | null,
): Promise<Session> {
  return request<Session>(`/sessions/${id}/threshold`, {
    method: "PATCH",
    body: JSON.stringify({ threshold_pct: thresholdPct }),
  });
}

/** Globale Kontext-Schwelle lesen. */
export function getThreshold(signal?: AbortSignal): Promise<ThresholdSetting> {
  return request<ThresholdSetting>("/settings/threshold", { signal });
}

/** Globale Kontext-Schwelle setzen (serverseitig geklemmt). */
export function setThreshold(thresholdPct: number): Promise<ThresholdSetting> {
  return request<ThresholdSetting>("/settings/threshold", {
    method: "PATCH",
    body: JSON.stringify({ threshold_pct: thresholdPct }),
  });
}

// --- PROJ-10: Trust-Policy -------------------------------------------------

/** Aktuelle Trust-Policy lesen (Regeln + Phasen-Gate + Herkunft/Warnung). */
export function getPolicy(signal?: AbortSignal): Promise<TrustPolicy> {
  return request<TrustPolicy>("/settings/policy", { signal });
}

/** Trust-Policy ersetzen — wird serverseitig validiert und LIVE übernommen
 *  (kein Neustart, laufende Sessions bleiben ununterbrochen). */
export function setPolicy(
  rules: PolicyRule[],
  phaseGate: PhaseGateConfig,
): Promise<TrustPolicy> {
  return request<TrustPolicy>("/settings/policy", {
    method: "PUT",
    body: JSON.stringify({ rules, phase_gate: phaseGate }),
  });
}

/** Trockenlauf: welche Stufe/Regel würde für einen Kontext greifen (Nachvollziehbarkeit). */
export function previewPolicy(
  match: { tool?: string; role?: string; skill?: string; project?: string },
  signal?: AbortSignal,
): Promise<PolicyPreview> {
  const params = new URLSearchParams();
  for (const [k, v] of Object.entries(match)) if (v) params.set(k, v);
  return request<PolicyPreview>(`/settings/policy/preview?${params.toString()}`, {
    signal,
  });
}

// --- PROJ-16: Amok-Watchdog + Limits ---------------------------------------

/** Aktuelle Watchdog-Limits lesen (vier Schwellen + Herkunft/Warnung). */
export function getWatchdog(signal?: AbortSignal): Promise<WatchdogSetting> {
  return request<WatchdogSetting>("/settings/watchdog", { signal });
}

/** Watchdog-Limits ersetzen — serverseitig validiert (Werte > 0) und LIVE
 *  übernommen (kein Neustart, laufende Sessions bleiben ununterbrochen). */
export function setWatchdog(limits: WatchdogLimits): Promise<WatchdogSetting> {
  return request<WatchdogSetting>("/settings/watchdog", {
    method: "PUT",
    body: JSON.stringify(limits),
  });
}

// --- PROJ-27: Liveness-Schwellen + Auto-Reanimierung -----------------------

/** Aktuelle Liveness-Schwellen lesen (Timeout/Poll/Versuche/Backoff + Herkunft/Warnung). */
export function getLiveness(signal?: AbortSignal): Promise<LivenessSetting> {
  return request<LivenessSetting>("/settings/liveness", { signal });
}

/** Liveness-Schwellen ersetzen — serverseitig validiert und LIVE übernommen. */
export function setLiveness(limits: LivenessLimits): Promise<LivenessSetting> {
  return request<LivenessSetting>("/settings/liveness", {
    method: "PUT",
    body: JSON.stringify(limits),
  });
}

// --- PROJ-7: MD-Reader (read-only) -----------------------------------------

/** Verfügbare Lese-Quellen (Vault + Projekt). */
export function listMdSources(
  project?: string,
  signal?: AbortSignal,
): Promise<MdSource[]> {
  const qs = project ? `?project=${encodeURIComponent(project)}` : "";
  return request<MdSource[]>(`/md/sources${qs}`, { signal });
}

/** Flacher Index aller .md einer Quelle → Baum + Wikilink-Auflösung. */
export function getMdIndex(
  source: string,
  project?: string,
  signal?: AbortSignal,
): Promise<MdIndexResult> {
  const params = new URLSearchParams({ source });
  if (project) params.set("project", project);
  return request<MdIndexResult>(`/md/index?${params.toString()}`, { signal });
}

/** Eine .md lesen (absoluter Pfad, gegen allowed_roots validiert). */
export function readMdFile(path: string, signal?: AbortSignal): Promise<MdFileRead> {
  return request<MdFileRead>(`/md/file?path=${encodeURIComponent(path)}`, { signal });
}

/**
 * PROJ-12: Eine .md atomar zurückschreiben. `content` ist der volle Rohtext
 * (Frontmatter-Block + Body, 1:1). `expected_*` speisen die optimistische
 * Konflikterkennung — weicht der Server-Stand ab und `force` ist nicht gesetzt,
 * antwortet das Backend mit 409 (→ ApiError.status === 409).
 */
export function saveMdFile(
  input: {
    path: string;
    content: string;
    expected_mtime?: number;
    expected_hash?: string;
    force?: boolean;
  },
  signal?: AbortSignal,
): Promise<MdSaveResult> {
  return request<MdSaveResult>(`/md/file`, {
    method: "POST",
    body: JSON.stringify(input),
    signal,
  });
}

/** PROJ-12: Notizen, die per [[…]] auf `path` verlinken (serverseitiger Reverse-Scan). */
export function getMdBacklinks(
  path: string,
  signal?: AbortSignal,
): Promise<MdIndexEntry[]> {
  return request<MdBacklinksResult>(
    `/md/backlinks?path=${encodeURIComponent(path)}`,
    { signal },
  ).then((r) => r.backlinks);
}

/** ws(s)://…/sessions/{id}/stream — Live-Events nur für die Detailansicht.
 *  Robust für absolute (http→ws) UND relative API-Base (z. B. „/api"): bei einer
 *  relativen Base wird die ws(s)-URL aus dem aktuellen Origin gebildet. */
export function streamUrl(id: string): string {
  let base: string;
  if (/^https?:/.test(API_BASE)) {
    base = API_BASE.replace(/^http/, "ws");
  } else if (typeof window !== "undefined") {
    base = window.location.origin.replace(/^http/, "ws") + API_BASE;
  } else {
    base = API_BASE; // SSR-Fallback (Browser nutzt den window-Pfad zur Laufzeit)
  }
  // PROJ-25: Browser-WebSockets können keinen Authorization-Header setzen → der
  // Access-Token reist als Query-Param; das Backend löst die Identität daraus auf
  // und beschränkt den Stream auf die eigene Session.
  const token = getAccessToken();
  const auth = token ? `?access_token=${encodeURIComponent(token)}` : "";
  return `${base}/sessions/${id}/stream${auth}`;
}

// --- PROJ-11: Fileexplorer + Clipboard -------------------------------------

/** Erlaubte Wurzel-Ordner (RootSelector). */
export function listFileRoots(signal?: AbortSignal): Promise<RootEntry[]> {
  return request<RootEntry[]>("/files/roots", { signal });
}

/** Verzeichnis-Inhalt (Default = erste erlaubte Wurzel). */
export function listDir(path?: string, signal?: AbortSignal): Promise<DirListing> {
  const qs = path ? `?path=${encodeURIComponent(path)}` : "";
  return request<DirListing>(`/files/list${qs}`, { signal });
}

/** Direkter Download-Link einer Datei (für <a href> / neues Tab). */
export function fileDownloadUrl(path: string): string {
  return `${API_BASE}/files/download?path=${encodeURIComponent(path)}`;
}

/** Datei(en) hochladen — Default-Ziel = Clipboard-Ordner. Multipart, daher
 *  eigenes fetch (kein JSON-Content-Type wie bei `request`). */
export async function uploadFiles(
  files: File[],
  targetDir?: string,
): Promise<UploadResult> {
  const fd = new FormData();
  for (const f of files) fd.append("files", f);
  if (targetDir) fd.append("target_dir", targetDir);
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}/files/upload`, {
      method: "POST",
      body: fd,
      credentials: "include",
      headers: authHeaders(),
    });
  } catch {
    throw new ApiError("Backend nicht erreichbar", 0);
  }
  if (!resp.ok) {
    if (resp.status === 401) handleAuthFailure();
    let detail = `Fehler ${resp.status}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, resp.status);
  }
  return (await resp.json()) as UploadResult;
}

export function makeDir(parent: string, name: string): Promise<FileEntry> {
  return request<FileEntry>("/files/mkdir", {
    method: "POST",
    body: JSON.stringify({ parent, name }),
  });
}

export function renameFile(path: string, newName: string): Promise<FileEntry> {
  return request<FileEntry>("/files/rename", {
    method: "POST",
    body: JSON.stringify({ path, new_name: newName }),
  });
}

export function moveFile(path: string, destDir: string): Promise<FileEntry> {
  return request<FileEntry>("/files/move", {
    method: "POST",
    body: JSON.stringify({ path, dest_dir: destDir }),
  });
}

export function deleteFiles(paths: string[]): Promise<DeleteResult> {
  return request<DeleteResult>("/files/delete", {
    method: "POST",
    body: JSON.stringify({ paths }),
  });
}

/** PROJ-9: Smart-Launcher-Vorschlag aus features/INDEX.md des Projekts. */
export function getLaunchSuggestion(
  projectPath: string,
  signal?: AbortSignal,
): Promise<LaunchSuggestion> {
  return request<LaunchSuggestion>(
    `/projects/suggestion?project_path=${encodeURIComponent(projectPath)}`,
    { signal },
  );
}

/** Aktuellen Clipboard-Ordner lesen. */
export function getClipboardDir(signal?: AbortSignal): Promise<ClipboardDir> {
  return request<ClipboardDir>("/settings/clipboard-dir", { signal });
}

/** Clipboard-Ordner setzen (innerhalb der erlaubten Roots). */
export function setClipboardDir(path: string): Promise<ClipboardDir> {
  return request<ClipboardDir>("/settings/clipboard-dir", {
    method: "PATCH",
    body: JSON.stringify({ path }),
  });
}

// --- PROJ-13: Git-Branch-Handling ------------------------------------------

/** Branch-Status eines Projekts (read-only, pollbar). project_path = aktueller
 *  Pfad im Explorer; das Backend härtet ihn gegen die erlaubten Roots. */
export function getBranchStatus(
  projectPath: string,
  signal?: AbortSignal,
): Promise<BranchStatus> {
  return request<BranchStatus>(
    `/git/status?project_path=${encodeURIComponent(projectPath)}`,
    { signal },
  );
}

/** Branch wechseln. Wirft ApiError(409) bei dirty Working Tree (kein Zwang). */
export function switchBranch(
  projectPath: string,
  branch: string,
): Promise<BranchStatus> {
  return request<BranchStatus>("/git/switch", {
    method: "POST",
    body: JSON.stringify({ project_path: projectPath, branch }),
  });
}

/** Feature-Branch `specs/PROJ-<id>-<slug>` anlegen (oder auschecken, falls vorhanden). */
export function createFeatureBranch(
  projectPath: string,
  featureId: number,
  slug: string,
  base = "main",
): Promise<BranchStatus> {
  return request<BranchStatus>("/git/feature-branch", {
    method: "POST",
    body: JSON.stringify({
      project_path: projectPath,
      feature_id: featureId,
      slug,
      base,
    }),
  });
}

/** `source` nach `target` mergen (--no-ff). Vorab-Check + Konflikt → ApiError(409). */
export function promoteBranch(
  projectPath: string,
  source: string,
  target: string,
): Promise<BranchStatus> {
  return request<BranchStatus>("/git/promote", {
    method: "POST",
    body: JSON.stringify({ project_path: projectPath, source, target }),
  });
}

/** Expliziter Stash (inkl. untracked) vor einem Wechsel — nie automatisch. */
export function stashChanges(projectPath: string): Promise<BranchStatus> {
  return request<BranchStatus>("/git/stash", {
    method: "POST",
    body: JSON.stringify({ project_path: projectPath }),
  });
}

/** `git init` für ein Nicht-Repo innerhalb der Roots. */
export function gitInit(projectPath: string): Promise<BranchStatus> {
  return request<BranchStatus>("/git/init", {
    method: "POST",
    body: JSON.stringify({ project_path: projectPath }),
  });
}

// --- PROJ-17: Recovery über den Vault --------------------------------------

/** Nach Reboot/Crash wiederherstellbare Stränge (verwaist + ohne Nachfolger).
 *  Read-only Sicht über Live-Index + Vault; der Seed wird serverseitig gebaut. */
export function listRecovery(signal?: AbortSignal): Promise<RecoveryListResult> {
  return request<RecoveryListResult>("/recovery", { signal });
}

/** Strang wiederherstellen: startet eine Kind-Session mit dem (serverseitig aus
 *  Handover/Log verdichteten) Seed als System-Kontext, verknüpft via
 *  parent_session_id (wie PROJ-5). Idempotent: 1 Strang = 1 Nachfolger
 *  (Zweitversuch → 409 → ApiError.status). */
export function restoreRecovery(
  sessionId: string,
  initialPrompt?: string,
): Promise<Session> {
  return request<Session>(`/recovery/${sessionId}/restore`, {
    method: "POST",
    body: JSON.stringify({ initial_prompt: initialPrompt ?? null }),
  });
}

/** Kandidat verwerfen: aus der Recovery-Ansicht entfernen, OHNE den Vault-Eintrag
 *  zu löschen (Audit bleibt). 204 → void. */
export function dismissRecovery(sessionId: string): Promise<void> {
  return request<void>(`/recovery/${sessionId}/dismiss`, { method: "POST" });
}

// --- PROJ-20: Spracheingabe / Push-to-Talk ---------------------------------

/** Audio transkribieren — multipart, daher eigenes fetch (kein JSON-Content-Type
 *  wie bei `request`). Engine-Wahl (self-hosted/Groq) entscheidet das Backend
 *  anhand der Settings. Audio wird serverseitig nicht gespeichert. */
export async function transcribeAudio(
  audio: Blob,
  language?: string,
): Promise<TranscriptionResult> {
  const fd = new FormData();
  fd.append("audio", audio, "aufnahme.webm");
  if (language) fd.append("language", language);
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}/transcription`, {
      method: "POST",
      body: fd,
      credentials: "include",
      headers: authHeaders(),
    });
  } catch {
    throw new ApiError("Backend nicht erreichbar", 0);
  }
  if (!resp.ok) {
    if (resp.status === 401) handleAuthFailure();
    let detail = `Fehler ${resp.status}`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, resp.status);
  }
  return (await resp.json()) as TranscriptionResult;
}

export function getTranscriptionSettings(signal?: AbortSignal): Promise<TranscriptionSetting> {
  return request<TranscriptionSetting>("/settings/transcription", { signal });
}

/** Cloud-Fallback (Groq) bewusst an/aus. 400, wenn use_groq=true ohne Key. */
export function setTranscriptionSettings(useGroq: boolean): Promise<TranscriptionSetting> {
  return request<TranscriptionSetting>("/settings/transcription", {
    method: "PATCH",
    body: JSON.stringify({ use_groq: useGroq }),
  });
}

// --- PROJ-41: Video Summary (native Micro-App) -----------------------------

/** Warteschlange + Worker-Zustand (für das Polling). */
export function getVideoSummaryQueue(
  signal?: AbortSignal,
): Promise<VideoSummaryQueue> {
  return request<VideoSummaryQueue>("/video-summary/queue", { signal });
}

/** Eine/mehrere URLs einreihen (Paste-Block erlaubt; Server zerlegt + dedupliziert). */
export function addVideoSummaryUrls(
  urls: string,
): Promise<VideoSummaryAddResult> {
  return request<VideoSummaryAddResult>("/video-summary/queue", {
    method: "POST",
    body: JSON.stringify({ urls }),
  });
}

/** Einen Eintrag entfernen. */
export function deleteVideoSummaryItem(id: number): Promise<void> {
  return request<void>(`/video-summary/queue/${id}`, { method: "DELETE" });
}

/** Fehlgeschlagenen Eintrag erneut versuchen (→ pending + Drain). */
export function retryVideoSummaryItem(id: number): Promise<VideoSummaryQueue> {
  return request<VideoSummaryQueue>(`/video-summary/queue/${id}/retry`, {
    method: "POST",
  });
}

/** „Jetzt ausführen": Abarbeitung sofort starten (idempotent). */
export function runVideoSummaryNow(): Promise<VideoSummaryQueue> {
  return request<VideoSummaryQueue>("/video-summary/run-now", {
    method: "POST",
  });
}

/** Einstellungen (Cooldown / Batch / Zeitplan) lesen. */
export function getVideoSummarySettings(
  signal?: AbortSignal,
): Promise<VideoSummarySettings> {
  return request<VideoSummarySettings>("/video-summary/settings", { signal });
}

/** Einstellungen ändern (Teil-Update). */
export function patchVideoSummarySettings(
  patch: Partial<VideoSummarySettings>,
): Promise<VideoSummarySettings> {
  return request<VideoSummarySettings>("/video-summary/settings", {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

/** PROJ-44: Bibliothek — alle bereits umgewandelten Notizen im Standard-Ordner
 *  (Vault-Scan, neueste zuerst). Unabhängig von der DB-Queue. */
export function getVideoSummaryLibrary(
  signal?: AbortSignal,
): Promise<VideoSummaryLibraryItem[]> {
  return request<VideoSummaryLibraryItem[]>("/video-summary/library", { signal });
}

/** PROJ-44: Deeplink, der eine Vault-Notiz im MD-Reader (PROJ-7) öffnet. */
export function mdReaderUrl(absolutePath: string): string {
  return `/doku?source=vault&path=${encodeURIComponent(absolutePath)}`;
}

// --- PROJ-42: VPS-Admin Metriken (native Micro-App) ------------------------

/** Vollständiger Host-Metrik-Snapshot inkl. Verlauf (für die geöffnete App,
 *  Polling). Liest den serverseitig gecachten Worker-Stand — kein Messen pro
 *  Request. */
export function getMetricsCurrent(
  signal?: AbortSignal,
): Promise<MetricsSnapshot> {
  return request<MetricsSnapshot>("/metrics/current", { signal });
}

/** Leichtgewichtige Gesamt-Ampel (green/amber/red) für das Sidebar-Status-Icon —
 *  läuft unabhängig davon, ob die App geöffnet ist. */
export function getMetricsStatus(
  signal?: AbortSignal,
): Promise<MetricsStatus> {
  return request<MetricsStatus>("/metrics/status", { signal });
}

// --- PROJ-43: VPS-Admin Terminal (ttyd-iFrame) ------------------------------

/** Erreichbarkeit + einzubettende URL des ttyd-Terminal-Dienstes. Das Backend
 *  liest die URL aus seiner Config (nie vom Client) und macht einen kurzen
 *  TCP-Probe auf den lokalen ttyd-Port, damit „Dienst aus" sauber von
 *  „Einbettung verweigert" getrennt werden kann. */
export function getTerminalInfo(
  signal?: AbortSignal,
): Promise<TerminalInfo> {
  return request<TerminalInfo>("/terminal/info", { signal });
}

// --- PROJ-22: Multi-Agent-Dispatch (Koordinator) ---------------------------

/** Verteilungsplan aus features/INDEX.md des Projekts erzeugen — startet NICHTS
 *  (Human-in-the-Loop). Liefert Ticket→Rolle/Skill/Engine + topologische
 *  Reihenfolge + Warnungen (zirkuläre/fehlende Abhängigkeiten). */
export function getCoordinatorPlan(
  projectPath: string,
  signal?: AbortSignal,
): Promise<CoordinatorPlan> {
  return request<CoordinatorPlan>("/coordinator/plan", {
    method: "POST",
    body: JSON.stringify({ project_path: projectPath }),
    signal,
  });
}

/** Freigegebenen Plan dispatchen: startet die Koordinator-Session + je nicht
 *  blockiertem Ticket eine Spezialisten-Session (policy-gegatet, PROJ-10).
 *  Liefert die frisch gestartete Flotte. 429 = Engine-Slot-Limit (PROJ-14). */
export function dispatchCoordinator(
  projectPath: string,
  items: CoordinatorPlanItem[],
): Promise<CoordinatorFleet> {
  return request<CoordinatorFleet>("/coordinator/dispatch", {
    method: "POST",
    body: JSON.stringify({ project_path: projectPath, items }),
  });
}

/** Live-Sicht einer Flotte (Koordinator + Kinder) — pollbar fürs Cockpit. */
export function getCoordinatorFleet(
  coordinatorId: string,
  signal?: AbortSignal,
): Promise<CoordinatorFleet> {
  return request<CoordinatorFleet>(`/coordinator/${coordinatorId}/fleet`, { signal });
}

/** Dispatch pausieren/fortsetzen (keine neuen Tickets, laufende Kinder bleiben). */
export function setCoordinatorPaused(
  coordinatorId: string,
  paused: boolean,
): Promise<CoordinatorFleet> {
  return request<CoordinatorFleet>(`/coordinator/${coordinatorId}/pause`, {
    method: "POST",
    body: JSON.stringify({ paused }),
  });
}

/** Ein Ticket manuell umverteilen (andere Rolle/Engine/Modell) → Plan-Neuberechnung. */
export function reassignTicket(
  coordinatorId: string,
  ticketId: string,
  patch: { role?: string; engine?: string; model?: string },
): Promise<CoordinatorFleet> {
  return request<CoordinatorFleet>(`/coordinator/${coordinatorId}/reassign`, {
    method: "POST",
    body: JSON.stringify({ ticket_id: ticketId, ...patch }),
  });
}

/** API-Vertrag als Vault-Artefakt ablegen/aktualisieren → Update-Signal an die
 *  Kinder (Pointer bleibt gleich, Inhalt neu). Liefert den Datei-Pointer. */
export function setCoordinatorContract(
  coordinatorId: string,
  body: string,
  title?: string,
): Promise<VaultWriteResult> {
  return request<VaultWriteResult>(`/coordinator/${coordinatorId}/contract`, {
    method: "POST",
    body: JSON.stringify({ body, title: title ?? null }),
  });
}

// --- PROJ-26: Marktplatz/Registry ------------------------------------------

/** Katalog durchsuchen — optionaler Filter nach Typ, Status und Freitext.
 *  Aktiv = Datei am Resolver-Pfad → steht Sessions/Launcher (PROJ-9) zur Verfügung. */
export function getRegistryCatalog(
  filter?: { typ?: RegistryType; status?: string; query?: string },
  signal?: AbortSignal,
): Promise<RegistryCatalog> {
  const params = new URLSearchParams();
  if (filter?.typ) params.set("typ", filter.typ);
  if (filter?.status) params.set("status", filter.status);
  if (filter?.query) params.set("query", filter.query);
  const qs = params.toString();
  return request<RegistryCatalog>(`/registry/catalog${qs ? `?${qs}` : ""}`, { signal });
}

/** Detail eines Eintrags inkl. Definition-Text + Versions-Historie + Capabilities. */
export function getRegistryEntry(
  typ: RegistryType,
  id: string,
  signal?: AbortSignal,
): Promise<RegistryEntryDetail> {
  return request<RegistryEntryDetail>(`/registry/${typ}/${encodeURIComponent(id)}`, {
    signal,
  });
}

/** Einen vorhandenen, aber noch nicht aktivierten Eintrag installieren
 *  (Datei extrahieren). Liefert den aktualisierten Eintrag zurück. */
export function installRegistryEntry(
  typ: RegistryType,
  id: string,
): Promise<RegistryEntry> {
  return request<RegistryEntry>(
    `/registry/${typ}/${encodeURIComponent(id)}/install`,
    { method: "POST" },
  );
}

/** Aktivieren/Deaktivieren. Deaktivierung wirkt erst auf NEUE Sessions —
 *  laufende Sessions behalten die geladene Version (PROJ-26 Edge Case). */
export function toggleRegistryEntry(
  typ: RegistryType,
  id: string,
): Promise<RegistryEntry> {
  return request<RegistryEntry>(
    `/registry/${typ}/${encodeURIComponent(id)}/toggle`,
    { method: "PATCH" },
  );
}

/** Auf eine frühere Version zurückrollen. Referenziert sie ein fehlendes Tool,
 *  wird der Eintrag als „eingeschränkt lauffähig" markiert (Hinweis, kein Crash). */
export function rollbackRegistryEntry(
  typ: RegistryType,
  id: string,
  version: string,
): Promise<RegistryEntry> {
  return request<RegistryEntry>(
    `/registry/${typ}/${encodeURIComponent(id)}/rollback`,
    { method: "POST", body: JSON.stringify({ version }) },
  );
}

/** Eintrag deinstallieren (entfernt Datei + Versionen). */
export function deleteRegistryEntry(typ: RegistryType, id: string): Promise<void> {
  return request<void>(`/registry/${typ}/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
}

/** Eintrag als portierbares `.jupkg`-Paket exportieren und im Browser speichern.
 *  Eigener fetch (Blob), damit der Bearer-Token (PROJ-25) am Download hängt. */
export async function exportRegistryPackage(
  typ: RegistryType,
  id: string,
): Promise<void> {
  let resp: Response;
  try {
    resp = await fetch(
      `${API_BASE}/registry/${typ}/${encodeURIComponent(id)}/export`,
      { credentials: "include", headers: authHeaders() },
    );
  } catch {
    throw new ApiError("Backend nicht erreichbar", 0);
  }
  if (!resp.ok) {
    if (resp.status === 401) handleAuthFailure();
    throw new ApiError(`Export fehlgeschlagen (${resp.status})`, resp.status);
  }
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${id}.jupkg`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

/** `.jupkg` hochladen → Capability-/Policy-VORSCHAU (noch NICHT aktiv).
 *  Validierung (Schema-Version, Struktur) passiert serverseitig; ein defektes/
 *  inkompatibles Paket wird hier abgewiesen. Multipart → eigener fetch. */
export async function importRegistryPreview(
  file: File,
): Promise<RegistryImportPreview> {
  const fd = new FormData();
  fd.append("file", file);
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}/registry/import`, {
      method: "POST",
      body: fd,
      credentials: "include",
      headers: authHeaders(),
    });
  } catch {
    throw new ApiError("Backend nicht erreichbar", 0);
  }
  if (!resp.ok) {
    if (resp.status === 401) handleAuthFailure();
    let detail = `Import abgelehnt (${resp.status})`;
    try {
      const body = await resp.json();
      if (body?.detail) detail = String(body.detail);
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, resp.status);
  }
  return (await resp.json()) as RegistryImportPreview;
}

/** Nach Bestätigung der Vorschau aktivieren (Human-in-the-Loop). `token` stammt
 *  unverändert aus der Vorschau-Antwort. Liefert den neuen Katalog-Eintrag. */
export function importRegistryConfirm(token: string): Promise<RegistryEntry> {
  return request<RegistryEntry>("/registry/import/confirm", {
    method: "POST",
    body: JSON.stringify({ token }),
  });
}
