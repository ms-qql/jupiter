// Dünner Client für das Jupiter-FastAPI-Backend (PROJ-1/PROJ-2).
// Basis-URL via NEXT_PUBLIC_API_BASE; Default = lokaler uvicorn auf :8000.

import type {
  ClipboardDir,
  DeleteResult,
  DirListing,
  FileEntry,
  HandoverPreview,
  LaunchSuggestion,
  MdBacklinksResult,
  MdFileRead,
  MdIndexEntry,
  MdIndexResult,
  MdSaveResult,
  MdSource,
  PhaseGateConfig,
  PolicyPreview,
  PolicyRule,
  RootEntry,
  Session,
  SessionCreate,
  SessionDetail,
  ThresholdSetting,
  TrustPolicy,
  UploadResult,
  VaultWriteResult,
  WatchdogLimits,
  WatchdogSetting,
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

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let resp: Response;
  try {
    resp = await fetch(`${API_BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError("Backend nicht erreichbar", 0);
  }
  if (!resp.ok) {
    redirectToLoginOn401(resp.status);
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

/** Bei 401 (Session fehlt/abgelaufen) den Browser auf die Forward-Auth-Login-Seite
 *  leiten. Loop-Schutz: nicht, wenn wir schon auf /__auth/* sind. SSR-safe. */
function redirectToLoginOn401(status: number): void {
  if (status !== 401 || typeof window === "undefined") return;
  if (window.location.pathname.startsWith("/__auth")) return;
  const next = window.location.pathname + window.location.search;
  window.location.assign(`/__auth/login?next=${encodeURIComponent(next)}`);
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

export function sendInput(id: string, text: string): Promise<{ ok: boolean }> {
  return request(`/sessions/${id}/input`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function stopSession(id: string): Promise<{ ok: boolean }> {
  return request(`/sessions/${id}/stop`, { method: "POST" });
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

/** Decision Card entscheiden (PROJ-4): Freigeben / Ablehnen / Mit Kommentar zurück. */
export function resolveDecision(
  sessionId: string,
  decisionId: string,
  decision: "approve" | "deny",
  comment?: string,
): Promise<{ ok: boolean }> {
  return request(`/sessions/${sessionId}/decisions/${decisionId}`, {
    method: "POST",
    body: JSON.stringify({ decision, comment: comment ?? null }),
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
  return `${base}/sessions/${id}/stream`;
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
    resp = await fetch(`${API_BASE}/files/upload`, { method: "POST", body: fd });
  } catch {
    throw new ApiError("Backend nicht erreichbar", 0);
  }
  if (!resp.ok) {
    redirectToLoginOn401(resp.status);
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
