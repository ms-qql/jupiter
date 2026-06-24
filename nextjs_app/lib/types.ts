// Spiegelt backend/app/schemas/sessions.py (SessionRead / SessionCreate).

export type ModelName = "haiku" | "sonnet" | "opus";
export type PermissionMode = "default" | "acceptEdits" | "bypassPermissions";

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
  context: {
    project_path?: string;
    role?: string | null;
    phase?: string | null;
    /** PROJ-15: bei knowledge_proposal die erkannte Marker-Art (bug_geloest|adr|sackgasse). */
    curation_marker?: string | null;
  };
  created_at: string;
  state: string; // open | resolved | obsolete
  resolution: string | null;
  /** Roh-Input des Tools; bei Frage-Tools (AskUserQuestion) rendert die Card daraus
   *  eine Auswahlliste statt eines JSON-Blobs. */
  tool_input?: AskUserQuestionInput | Record<string, unknown>;
  /** PROJ-10: Klartext der Policy-Regel, die diese Card ausgelöst hat
   *  (z. B. „card · Bash @ Rolle architect"). null = konservativer Default. */
  triggering_rule?: string | null;
  /** PROJ-10/15/16: Card-Typ — „normal" (operative Freigabe), „phase_transition"
   *  (bypass-festes Phasen-Gate), „deny" (hart verboten, nur Info), „watchdog_pause"
   *  (PROJ-16: Reißleine hat pausiert) oder „knowledge_proposal" (PROJ-15:
   *  nicht-blockierender Wissens-Vorschlag, blockiert die Session NICHT). */
  card_type?: "normal" | "phase_transition" | "deny" | "watchdog_pause" | "knowledge_proposal";
  /** PROJ-15: editierbarer Inhalt eines Wissens-Vorschlags (nur knowledge_proposal). */
  proposal_title?: string | null;
  proposal_body?: string | null;
}

/** Struktur des AskUserQuestion-Tool-Inputs (für die Frage-Karte, PROJ-4). */
export interface AskUserQuestionInput {
  questions: {
    question: string;
    header?: string;
    multiSelect?: boolean;
    options: { label: string; description?: string }[];
  }[];
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
  /** PROJ-5: Vorgänger → Reset-Nachfolger (1 Strang = 1 Nachfolger). */
  child_session_id: string | null;
  /** PROJ-8: sprechendes Projekt-Label (Fallback Basename) — Gantt-Zeilen-Titel. */
  project_name: string | null;
  /** PROJ-8: AKTUELLE ABC-Phase (hervorgehoben). null = keine Phase. */
  abc_phase: AbcPhase | null;
  /** PROJ-8: WEITESTE bisher erreichte Phase (Bar-Füllung). */
  abc_phase_reached: AbcPhase | null;
  /** PROJ-8: Feature-Referenz, z. B. „8" (aus Skill-Arg/berührtem Spec). */
  abc_feature: string | null;
  pending_decisions: PendingDecision[];
}

/** PROJ-8: kanonische ABC-Workflow-Phasen (spiegelt backend/app/engine/abc_phases.py). */
export type AbcPhase =
  | "brainstorm"
  | "requirements"
  | "architecture"
  | "frontend"
  | "backend"
  | "qa"
  | "deploy"
  | "document";

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

/** Ein Suchtreffer im Vault (PROJ-2/PROJ-15) — Pfad dient zugleich als Backlink. */
export interface VaultSearchHit {
  path: string; // vault-relativ → über die Doku-/MD-Reader-Route öffenbar
  line: number;
  excerpt: string;
}

/** Antwort von GET /vault/search (PROJ-15: scope=all|curated). */
export interface VaultSearchResult {
  query: string;
  hits: VaultSearchHit[];
}

/** Globale Kontext-Schwelle + erlaubter Bereich (PROJ-5). */
export interface ThresholdSetting {
  threshold_pct: number;
  min_pct: number;
  max_pct: number;
}

// --- PROJ-10: Trust-Policy (abgestuftes, konfigurierbares Vertrauen) --------

/** Vertrauensstufe einer Regel. */
export type PolicyLevel = "auto-allow" | "card" | "deny";

/** Wonach eine Regel matcht — leere Felder = „beliebig" (allgemeiner). */
export interface PolicyRuleMatch {
  tool?: string | null; // Tool-Klasse, z. B. „Bash" (leer = alle Tools)
  role?: string | null;
  skill?: string | null;
  project?: string | null;
}

/** Eine Policy-Regel: Match → Stufe (+ optionaler Klartext-Grund, v. a. bei deny). */
export interface PolicyRule {
  match: PolicyRuleMatch;
  level: PolicyLevel;
  reason?: string | null;
}

/** Phasen-Übergangs-Gate (bypass-fest). transitions = Ziel-Phasen, deren Eintritt
 *  eine Freigabe verlangt; leere Liste = JEDER Phasenwechsel gated. */
export interface PhaseGateConfig {
  enabled: boolean;
  transitions: AbcPhase[];
}

/** Gesamte Trust-Policy (GET/PUT /settings/policy). */
export interface TrustPolicy {
  rules: PolicyRule[];
  phase_gate: PhaseGateConfig;
  /** Herkunft: z. B. „config/policy.yaml" oder „default" (keine Datei gepflegt). */
  source: string;
  /** Warnung bei kaputter/ungültiger Config (sonst null) — UI zeigt Fallback-Hinweis. */
  warning: string | null;
}

/** Antwort von GET /settings/policy/preview — welche Stufe/Regel würde greifen. */
export interface PolicyPreview {
  level: PolicyLevel;
  rule: string; // Klartext der greifenden Regel (oder „Default")
}

// --- PROJ-16: Amok-Watchdog + Limits ---------------------------------------

/** Die vier konfigurierbaren Watchdog-Limits (editierbarer Teil von GET/PUT
 *  /settings/watchdog). Jeder Wert > 0; der Server klemmt unsinnige Werte. */
export interface WatchdogLimits {
  /** An = Reißleine aktiv. Fehlt die Config, greifen konservative Defaults
   *  (nie „kein Watchdog"); dieser Schalter ist die bewusste Nutzer-Wahl. */
  enabled: boolean;
  /** Abgerechnete Tokens je gleitendem Zeitfenster. */
  token_limit: number;
  token_window_seconds: number;
  /** Max. Laufzeit ohne Fortschritt (Sekunden seit letztem Output/Result). */
  max_idle_seconds: number;
  /** N identische Tool-Calls in Folge → Schleife (unterschiedliche = Iteration). */
  max_repeated_calls: number;
  /** Writes je gleitendem Zeitfenster (auf verschiedene Pfade entschärft). */
  write_limit: number;
  write_window_seconds: number;
}

/** Gesamte Watchdog-Config (GET /settings/watchdog) — Limits + Herkunft/Warnung. */
export interface WatchdogSetting extends WatchdogLimits {
  /** Herkunft: z. B. „config/watchdog.yaml" oder „default" (keine Datei gepflegt). */
  source: string;
  /** Warnung bei kaputter/ungültiger Config (sonst null) — UI zeigt Fallback-Hinweis. */
  warning: string | null;
}

// --- PROJ-7: MD-Reader (read-only) -----------------------------------------

/** Lese-Quelle des MD-Readers — spiegelt backend/app/schemas/md.py MdSource. */
export interface MdSource {
  id: string; // "vault" | "project"
  label: string;
  root: string; // absoluter Wurzelpfad
}

/** Ein .md-Eintrag aus dem Index (MdIndexEntry). */
export interface MdIndexEntry {
  path: string; // absoluter Pfad (für GET /md/file)
  rel: string; // relativ zur Quell-Wurzel (für den Baum)
  name: string; // Basisname inkl. .md (für Wikilink-Auflösung)
}

/** Antwort von GET /md/index (MdIndexResult). */
export interface MdIndexResult {
  source: string;
  root: string;
  files: MdIndexEntry[];
}

/** Antwort von GET /md/file (MdFileRead) — Frontmatter getrennt vom Body. */
export interface MdFileRead {
  path: string;
  frontmatter: Record<string, unknown>;
  body: string;
  content: string;
  // PROJ-12: Basis für die optimistische Konflikterkennung beim Speichern.
  // Optional, weil ältere Backend-Stände (nur PROJ-7) sie nicht liefern.
  mtime?: number;
  hash?: string;
}

/** Antwort von POST /md/file (MdSaveResult) — neue mtime + Hash nach dem Schreiben. */
export interface MdSaveResult {
  path: string;
  mtime: number;
  hash: string;
}

/** Antwort von GET /md/backlinks (MdBacklinksResult) — wer verlinkt auf diese Notiz. */
export interface MdBacklinksResult {
  path: string;
  backlinks: MdIndexEntry[];
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
  /** PROJ-8: sprechendes Projekt-Label; ohne Angabe nutzt das Backend den Basename. */
  project_name?: string | null;
}

// --- PROJ-9: Smart Launcher -------------------------------------------------

/** Ein offenes Feature aus features/INDEX.md + die abgeleitete nächste Arbeit.
 *  Spiegelt backend/app/schemas/projects.py FeatureSuggestion. */
export interface FeatureSuggestion {
  id: string;
  number: string;
  title: string;
  status: string;
  prio: string | null;
  phase: AbcPhase | null;
  skill: string | null;
  modell: ModelName | null;
  initial_prompt: string;
}

/** Mitdenkender Session-Start-Vorschlag aus GET /projects/suggestion.
 *  Spiegelt backend/app/schemas/projects.py LaunchSuggestion. */
export interface LaunchSuggestion {
  project_path: string;
  abc_erkannt: boolean;
  hinweis: string | null;
  empfehlung: FeatureSuggestion | null;
  alternativen: FeatureSuggestion[];
  /** Default, den „Vorschlag übernehmen" anwendet (spiegelt die Empfehlung;
   *  im Sonderfall „alle deployed" der /abc-requirements-Vorschlag). */
  naechste_phase: AbcPhase | null;
  skill: string | null;
  modell: ModelName | null;
  initial_prompt: string | null;
}

// --- PROJ-11: Fileexplorer + Clipboard -------------------------------------

/** Eine Datei oder ein Ordner — spiegelt backend/app/schemas/files.py FileEntry. */
export interface FileEntry {
  name: string;
  kind: "file" | "dir";
  size: number;
  mtime: string; // ISO
  path: string; // absoluter Pfad (für „Pfad kopieren" / In-Session-Referenz)
}

/** Erlaubter Wurzel-Ordner (RootSelector). */
export interface RootEntry {
  label: string;
  path: string;
}

/** Antwort von GET /files/list. */
export interface DirListing {
  path: string;
  entries: FileEntry[];
}

/** Antwort von POST /files/upload. */
export interface UploadResult {
  files: FileEntry[];
}

/** Antwort von POST /files/delete. */
export interface DeleteResult {
  deleted: string[];
  failed: string[];
}

/** Clipboard-Ordner (GET/PATCH /settings/clipboard-dir). */
export interface ClipboardDir {
  path: string;
}

// --- PROJ-17: Recovery über den Vault --------------------------------------

/** Quelle, aus der der „Hier ging's weiter"-Vorschlag eines Kandidaten stammt
 *  (stärkste zuerst): kuratierter Handover > Auto-Session-Log > nur Index-Metadaten. */
export type RecoverySource = "handover" | "log" | "incomplete";

/** Ein nach Reboot/Crash wiederherstellbarer Strang — spiegelt das geplante
 *  backend/app/schemas/recovery.py RecoveryCandidate. Read-only Sicht über
 *  Live-Index (PROJ-14) + Vault (PROJ-2/PROJ-5); kein neues Persistenz-Schema. */
export interface RecoveryCandidate {
  /** Verwaiste Vorgänger-Session, an die wiederangeknüpft wird (parent). */
  session_id: string;
  project_path: string;
  project_name: string | null;
  /** Weiteste bekannte ABC-Phase des Strangs (null = unbekannt). */
  abc_phase: AbcPhase | null;
  /** Zeitpunkt des jüngsten Handovers/letzter Aktivität (ISO) — null bei reiner Index-Quelle. */
  last_handover_at: string | null;
  /** Woraus der Vorschlag gebaut wurde (steuert das Quellen-Badge). */
  source: RecoverySource;
  /** „Hier ging's weiter": verdichtete offene Punkte aus dem Handover/Log. */
  suggestion: string;
  /** Wiederherstellen blockiert (z. B. Projektpfad existiert nicht mehr). */
  restore_blocked: boolean;
  /** Klartext-Grund der Blockade (nur wenn restore_blocked). */
  blocked_reason: string | null;
  /** Hinweis bei beschädigtem/halbem Handover (sonst null) — UI zeigt Warnung. */
  warning: string | null;
}

/** Antwort von GET /recovery — die Liste wiederherstellbarer Stränge. */
export interface RecoveryListResult {
  candidates: RecoveryCandidate[];
}
