// Spiegelt backend/app/schemas/sessions.py (SessionRead / SessionCreate).

export type ModelName = "haiku" | "sonnet" | "opus";
export type PermissionMode = "default" | "acceptEdits";

/** Roher Session-Status aus dem Backend (engine/manager.py). */
export type SessionStatus =
  | "starting"
  | "running"
  | "waiting"
  | "awaiting_approval" // PROJ-4: wartet auf eine Freigabe-Entscheidung
  | "done"
  | "error";

/** Offene Decision Card (PROJ-4) — spiegelt PendingDecisionRead. */
export interface PendingDecision {
  decision_id: string;
  session_id: string;
  tool_name: string;
  action: string; // „Was"
  excerpt: string; // relevanter Ausschnitt (Befehl/Diff)
  rationale: string; // „Warum"
  context: { project_path?: string; role?: string | null; phase?: string | null };
  created_at: string;
  state: string; // open | resolved | obsolete
  resolution: string | null;
}

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
  /** PROJ-5: false → Treiber lieferte noch keine Token-Daten (Gauge „unbekannt"). */
  context_known: boolean;
  /** PROJ-5: wirksame Kontext-Schwelle (% — Override oder global, geklemmt). */
  context_fill_threshold_pct: number;
  /** PROJ-5: true, sobald der bekannte Füllstand die Schwelle erreicht. */
  threshold_warning: boolean;
  total_cost_usd: number;
  num_turns: number;
  error: string | null;
  rate_limit: Record<string, unknown> | null;
  /** PROJ-5: Reset-Kind-Session → Vorgänger (Staffelstab). */
  parent_session_id: string | null;
  pending_decisions: PendingDecision[];
}

/** Vorschau von POST /sessions/{id}/handover/generate (PROJ-5). */
export interface HandoverPreview {
  title: string;
  body: string;
}

/** Ergebnis eines Vault-Writes (PROJ-2). */
export interface VaultWriteResult {
  path: string;
  type: string;
  created: string;
}

/** Globale Kontext-Schwelle + erlaubter Bereich (PROJ-5). */
export interface ThresholdSetting {
  threshold_pct: number;
  min_pct: number;
  max_pct: number;
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
