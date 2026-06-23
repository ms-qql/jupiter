// Dünner Client für das Jupiter-FastAPI-Backend (PROJ-1/PROJ-2).
// Basis-URL via NEXT_PUBLIC_API_BASE; Default = lokaler uvicorn auf :8000.

import type { Session, SessionCreate, SessionDetail } from "./types";

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

/** ws(s)://…/sessions/{id}/stream — Live-Events nur für die Detailansicht. */
export function streamUrl(id: string): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}/sessions/${id}/stream`;
}
