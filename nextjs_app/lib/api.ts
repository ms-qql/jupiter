// Dünner Client für das Jupiter-FastAPI-Backend (PROJ-1/PROJ-2).
// Basis-URL via NEXT_PUBLIC_API_BASE; Default = lokaler uvicorn auf :8000.

import type {
  HandoverPreview,
  MdFileRead,
  MdIndexResult,
  MdSource,
  Session,
  SessionCreate,
  SessionDetail,
  ThresholdSetting,
  VaultWriteResult,
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

/** ws(s)://…/sessions/{id}/stream — Live-Events nur für die Detailansicht. */
export function streamUrl(id: string): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/sessions/${id}/stream`;
}
