// Spiegelt backend/app/schemas/sessions.py (SessionRead / SessionCreate).

export type ModelName = "haiku" | "sonnet" | "opus";
export type PermissionMode = "default" | "acceptEdits";

/** Roher Session-Status aus dem Backend (engine/manager.py). */
export type SessionStatus =
  | "starting"
  | "running"
  | "waiting"
  | "done"
  | "error";

export interface Session {
  session_id: string;
  owner: string;
  project_path: string;
  model: string;
  permission_mode: string;
  role: string | null;
  constitution_source: string | null;
  status: SessionStatus;
  created_at: string; // ISO
  last_activity: string; // ISO
  tokens_used: number;
  context_fill_pct: number;
  total_cost_usd: number;
  num_turns: number;
  error: string | null;
  rate_limit: Record<string, unknown> | null;
}

export interface TranscriptEntry {
  role: string;
  kind: string;
  text: string;
  ts: string;
}

export interface SessionDetail extends Session {
  transcript: TranscriptEntry[];
}

export interface SessionCreate {
  project_path: string;
  initial_prompt: string;
  model: ModelName;
  permission_mode?: PermissionMode;
  role?: string | null;
}
