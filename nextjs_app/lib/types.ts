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

/** PROJ-27: verifizierter Liveness-Zustand — nicht „läuft die Uhr", sondern „lebt der
 *  Prozess wirklich + Fortschritt". „aktiv" (lebt + Fortschritt/legitime Wartestellung),
 *  „hängt" (lebt, aber kein Fortschritt), „tot" (beendet/verwaist). */
export type Liveness = "aktiv" | "hängt" | "tot";

/** PROJ-27: Rückmeldung des letzten (Auto-/manuellen) Reanimations-Versuchs. */
export type LivenessResult = "läuft_wieder" | "fehlgeschlagen" | null;

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
    /** PROJ-23: bei review_finding die Kontext-Felder des Cross-Agent-Reviews
     *  (Engine-Attribution + Verknüpfung Review↔Befund + Schweregrad). */
    review_id?: string;
    author_session_id?: string;
    author_engine?: string;
    author_model?: string;
    reviewer_engine?: string;
    reviewer_model?: string;
    same_engine?: boolean;
    severity?: Severity;
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
  /** PROJ-10/15/16/33: Card-Typ — „normal" (operative Freigabe), „phase_transition"
   *  (bypass-festes Phasen-Gate), „deny" (hart verboten, nur Info), „watchdog_pause"
   *  (PROJ-16: Reißleine hat pausiert), „knowledge_proposal" (PROJ-15:
   *  nicht-blockierender Wissens-Vorschlag) oder „self_restart" (PROJ-33: ein Tool
   *  würde den eigenen Host/Backend neustarten → bypass-feste Freigabe nötig). */
  card_type?:
    | "normal"
    | "phase_transition"
    | "deny"
    | "watchdog_pause"
    | "knowledge_proposal"
    | "self_restart"
    /** PROJ-22: Der Koordinator konnte einen Vertrags-Konflikt zwischen zwei
     *  Spezialisten-Sessions nicht automatisch vermitteln → Eskalation an den Menschen. */
    | "contract_conflict"
    /** PROJ-23: ein Cross-Agent-Review-Befund (nicht-blockierend) — erscheint auf der
     *  Reviewer-Session; Aktionen übernehmen/verwerfen/zurück laufen über die Review-API. */
    | "review_finding";
  /** PROJ-15: editierbarer Inhalt eines Wissens-Vorschlags (nur knowledge_proposal). */
  proposal_title?: string | null;
  proposal_body?: string | null;
}

// --- PROJ-23: Cross-Agent-Review / Challenge -------------------------------

/** 3-stufige Schweregrad-Skala eines Befunds (Design-Entscheid 2026-06-25). */
export type Severity = "hoch" | "mittel" | "niedrig";

/** Aktion pro Befund: übernehmen (Gegenvorschlag an die Autor-Session) ·
 *  verwerfen (Artefakt unberührt) · zurück (Befund + Kommentar an die Autor-Session). */
export type FindingAction = "übernehmen" | "verwerfen" | "zurück";

/** Ein einzelner Review-Befund. Spiegelt FindingRead (backend/app/schemas/challenge.py). */
export interface FindingRead {
  finding_id: string;
  severity: Severity;
  location: string;
  title: string;
  suggestion: string;
  state: string; // open | resolved
  resolution: FindingAction | null;
}

/** Ein Cross-Agent-Review (1 Challenge = 1 Reviewer-Session). Spiegelt ReviewRead. */
export interface ReviewRead {
  review_id: string;
  author_session_id: string;
  author_engine: string;
  author_model: string;
  reviewer_engine: string;
  reviewer_model: string;
  same_engine: boolean;
  artifact_pointer: string;
  artifact_version: string | null;
  round: number;
  focus: string | null;
  collected: boolean;
  incomplete: boolean;
  stale: boolean;
  created_at: string;
  findings: FindingRead[];
}

/** Body von POST /sessions/{id}/challenge. */
export interface ChallengeRequest {
  artifact_pointer: string;
  reviewer_engine?: string | null;
  focus?: string | null;
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
  /** PROJ-18: welche Engine die Session fährt (Default „claude"). Steuert die
   *  Degradation engine-spezifischer Anzeigen (z. B. Kosten → „n/v"). */
  engine: string;
  role: string | null;
  constitution_source: string | null;
  status: SessionStatus;
  created_at: string; // ISO
  last_activity: string; // ISO
  tokens_used: number;
  /** PROJ-19 (#27): kumulative Cache-Tokens — sichtbare Cache-Treffer (read = wiederverwendet). */
  cache_read_tokens: number;
  cache_creation_tokens: number;
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
  /** PROJ-22: Bei einer dispatchten Spezialisten-Session → die Koordinator-Session,
   *  die sie gestartet hat (1:N-Flotte, neben dem 1:1-Staffelstab). null = keine Flotte. */
  parent_coordinator_id: string | null;
  /** PROJ-22: Das Ticket („PROJ-X"), das diese Spezialisten-Session bearbeitet. */
  ticket_id: string | null;
  /** PROJ-22: Nur an der Koordinator-Session gesetzt — IDs seiner Kind-Sessions. */
  child_session_ids: string[];
  /** PROJ-22: Vault-Pointer auf das API-Vertrag-Artefakt (kein Volltext-Duplikat). */
  contract_pointer: string | null;
  /** PROJ-22 (M3): am Koordinator eingereihte, noch nicht gestartete Tickets (IDs) —
   *  rücken automatisch nach, sobald ein Engine-Slot frei wird. Optional (additiv). */
  queued_ticket_ids?: string[];
  /** PROJ-8: sprechendes Projekt-Label (Fallback Basename) — Gantt-Zeilen-Titel. */
  project_name: string | null;
  /** PROJ-8: AKTUELLE ABC-Phase (hervorgehoben). null = keine Phase. */
  abc_phase: AbcPhase | null;
  /** PROJ-8: WEITESTE bisher erreichte Phase (Bar-Füllung). */
  abc_phase_reached: AbcPhase | null;
  /** PROJ-8: Feature-Referenz, z. B. „8" (aus Skill-Arg/berührtem Spec). */
  abc_feature: string | null;
  pending_decisions: PendingDecision[];
  /** PROJ-27: verifizierter Heartbeat (aktiv/hängt/tot) — eigenes Signal neben der Ampel. */
  liveness: Liveness;
  /** PROJ-27: bisher unternommene automatische Reanimierungs-Versuche dieser Episode. */
  liveness_auto_attempts: number;
  /** PROJ-27: Ergebnis des letzten Reanimations-Versuchs (für die UI-Rückmeldung). */
  liveness_last_result: LivenessResult;
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

// --- PROJ-19 (#28/#27): Token-/Kosten-Dashboard (Backend-Antworten) ---------

export type UsageRange = "today" | "7d" | "30d" | "all";
export type UsageCostStatus = "complete" | "partial" | "none";

/** Eine Verbrauchs-Gruppe (je Modell bzw. Projekt) aus GET /usage/summary. */
export interface UsageGroupRead {
  key: string;
  label: string;
  tokens: number;
  cost_usd: number;
  cost_status: UsageCostStatus;
  session_count: number;
}

/** Antwort von GET /usage/summary. */
export interface UsageSummaryRead {
  range: UsageRange;
  session_count: number;
  total_tokens: number;
  total_cost_usd: number;
  cost_status: UsageCostStatus;
  cache_read_tokens: number;
  cache_creation_tokens: number;
  cache_hit_ratio: number;
  by_model: UsageGroupRead[];
  by_project: UsageGroupRead[];
}

/** Eine Session-Zeile aus GET /usage/drilldown. */
export interface UsageDrilldownRow {
  session_id: string;
  project_path: string;
  project_name: string | null;
  model: string;
  engine: string;
  role: string | null;
  abc_phase: string | null;
  tokens_used: number;
  total_cost_usd: number;
  cost_status: UsageCostStatus;
  created_at: string | null;
}

/** Antwort von GET /usage/drilldown. */
export interface UsageDrilldownRead {
  range: UsageRange;
  rows: UsageDrilldownRow[];
}

// --- PROJ-19 (#23): Pointer/RAG-Vorschau -----------------------------------

/** Ein gerankter Vault-Ausschnitt aus GET /vault/rag/preview. */
export interface VaultRagSnippet {
  path: string;
  line: number;
  snippet: string;
  score: number;
  terms_matched: number;
  full_chars: number;
}

/** Antwort von GET /vault/rag/preview — Ausschnitte + Ersparnis-Messung + Fallback. */
export interface VaultRagPreview {
  query: string;
  snippets: VaultRagSnippet[];
  fallback: boolean;
  reason: string | null;
  context_chars: number;
  fulltext_chars: number;
  reduction_pct: number;
}

// --- PROJ-19 (#26): Späher-Agenten -----------------------------------------

/** Eingabe für POST /agents/scout. */
export interface ScoutRequest {
  task: string;
  query?: string | null;
  paths?: string[];
  project_path?: string | null;
  model?: string | null;
  top_n?: number;
}

/** Antwort von POST /agents/scout — verdichtetes Fazit + Eskalations-Signal. */
export interface ScoutResult {
  task: string;
  model_used: string;
  summary: string;
  sources: string[];
  context_chars: number;
  usable: boolean;
  note: string | null;
}

/** Globale Kontext-Schwelle + erlaubter Bereich (PROJ-5). */
export interface ThresholdSetting {
  threshold_pct: number;
  min_pct: number;
  max_pct: number;
}

// --- PROJ-20: Spracheingabe / Push-to-Talk ---------------------------------

/** Antwort von POST /transcription — Transkript + welche Engine es erzeugt hat. */
export interface TranscriptionResult {
  transcript: string;
  provider: string; // "faster-whisper" | "groq"
}

/** GET/PATCH /settings/transcription — Quelle der Transkription (PROJ-20).
 *  Standard ist self-hosted (use_groq=false). Groq nur wählbar, wenn ein Key
 *  konfiguriert ist (groq_available=true). */
export interface TranscriptionSetting {
  use_groq: boolean;
  groq_available: boolean;
  model: string;
  language: string;
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

// --- PROJ-27: Verifizierter Liveness-Indikator + Auto-Reanimierung ----------

/** Konfigurierbare Liveness-Schwellen (editierbarer Teil von GET/PUT /settings/liveness).
 *  Spiegelt backend/app/schemas/settings.py LivenessLimitsPut. */
export interface LivenessLimits {
  /** Globaler Schalter der Automatik. Aus → nur Indikator + manueller Knopf. */
  enabled_auto_reanimation: boolean;
  /** Kein Fortschritt seit > X s → Zustand „hängt" (analog Watchdog-Stillstand). */
  progress_timeout_seconds: number;
  /** PROJ-32: höhere Geduld, solange ein Tool läuft (langer Build/Test ist kein Hänger). */
  tool_in_flight_timeout_seconds: number;
  /** Frequenz des Hintergrund-Auswerters (s). */
  poll_interval_seconds: number;
  /** Max. automatische Reanimations-Versuche; danach nur noch der manuelle Knopf. */
  max_auto_attempts: number;
  /** Wartezeit zwischen automatischen Versuchen (s); 0 = kein Backoff. */
  backoff_seconds: number;
}

/** Gesamte Liveness-Config (GET /settings/liveness) — Schwellen + Herkunft/Warnung. */
export interface LivenessSetting extends LivenessLimits {
  source: string;
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
  /** Modell — bei Claude „haiku|sonnet|opus", bei anderen Engines ein freier
   *  Profil-Modellname (z. B. „gpt-4o-mini"). */
  model: string;
  permission_mode?: PermissionMode;
  role?: string | null;
  /** PROJ-8: sprechendes Projekt-Label; ohne Angabe nutzt das Backend den Basename. */
  project_name?: string | null;
  /** PROJ-18: Ziel-Engine (Default „claude", wenn weggelassen). */
  engine?: string;
}

// --- PROJ-18: Weitere Engines + iFrame/Launch ------------------------------

/** Integrations-Tiefe eines Registry-Eintrags: steuerbare Session, eingebettete
 *  Web-App (iFrame), reiner externer Startknopf oder — PROJ-40 — eine nativ in
 *  Jupiter programmierte Micro-App (Render über die Frontend-Komponenten-Registry
 *  `lib/microapps-registry.ts`, verknüpft per `key`; kein iFrame). */
export type EngineKind = "engine" | "iframe" | "launch" | "native";

/** Ein Eintrag aus GET /engines (spiegelt backend/app/schemas/engines.py EngineRead).
 *  Engine-agnostisch + secret-frei: kein API-Key, kein argv. */
export interface EngineRead {
  key: string;
  label: string;
  kind: EngineKind;
  /** nur bei kind=engine: „claude" | „generic_cli" | „openai". */
  driver: string | null;
  /** false → ausgrauen; `unavailable_reason` trägt den deutschen Setup-Hinweis. */
  available: boolean;
  unavailable_reason: string | null;
  models: string[];
  default_model: string | null;
  capabilities: string[];
  /** iFrame-Quelle (kind=iframe). */
  url: string | null;
  sandbox: string | null;
  /** Launch-Ziel (kind=launch). */
  target: string | null;
  /** PROJ-39: Gruppe — z. B. „orchestration" (Sidebar-Sektion) | „micro". null = ungruppiert. */
  group: string | null;
  /** PROJ-39: lucide-Icon-Name für die Sidebar (sonst Default-Icon). */
  icon: string | null;
}

/** Antwort von GET /engines — alle Engines/iFrames/Launch-Einträge + Herkunft/Warnung. */
export interface EnginesOverview {
  engines: EngineRead[];
  source: string;
  warning: string | null;
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

// --- PROJ-13: Git-Branch-Handling ------------------------------------------

/** Live aus dem Repo gelesener Branch-Status (GET /git/status). Spiegelt
 *  backend/app/schemas/git.py BranchStatus. Git ist die Quelle der Wahrheit —
 *  kein DB-State. ahead/behind sind rein lokal (kein fetch); null = kein Upstream. */
export interface BranchStatus {
  path: string;
  is_repo: boolean;
  branch: string | null; // bei detached HEAD: Kurz-Hash
  detached: boolean;
  dirty: boolean;
  ahead: number | null;
  behind: number | null;
  branches: string[];
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

// --- PROJ-41: Video Summary (native Micro-App) -----------------------------

/** Status eines Warteschlangen-Eintrags (= UI-Badges). */
export type VideoSummaryStatus = "pending" | "running" | "done" | "error";

/** Laufzeit-Zustand des Backend-Workers. */
export type VideoSummaryWorkerStatus = "idle" | "running" | "paused";

/** Ein Eintrag der Video-Summary-Warteschlange (eine Zeile pro Video). */
export interface VideoSummaryItem {
  id: number;
  url: string;
  owner: string | null;
  status: VideoSummaryStatus;
  result_note_path: string | null;
  result_pdf_path: string | null;
  error_message: string | null;
  session_id: string | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
}

/** Worker-Zustand für die UI (Leerlauf · Läuft · Pausiert bis …). */
export interface VideoSummaryWorkerState {
  status: VideoSummaryWorkerStatus;
  draining: boolean;
  paused_until: string | null;
  next_scheduled_run: string | null;
}

/** Antwort von GET /video-summary/queue (+ run-now/retry). */
export interface VideoSummaryQueue {
  items: VideoSummaryItem[];
  state: VideoSummaryWorkerState;
}

/** Ergebnis von POST /video-summary/queue. */
export interface VideoSummaryAddResult {
  added: VideoSummaryItem[];
  rejected: string[];
  duplicates: string[];
  queue: VideoSummaryItem[];
}

/** Worker-Einstellungen (persistiert). */
export interface VideoSummarySettings {
  cooldown_minutes: number;
  batch_size: number;
  schedule: string;
  /** PROJ-44: Umwandlungs-Modell (haiku | sonnet | opus). */
  model: string;
}

/** PROJ-44: eine bereits umgewandelte Notiz im Standard-Ordner (Vault-Scan). */
export interface VideoSummaryLibraryItem {
  title: string;
  md_path: string;
  pdf_path: string | null;
  mtime: string | null;
}

// --- PROJ-42: VPS-Admin Metriken (native Micro-App) ------------------------

/** Ampel-Status eines Gauges / des Gesamtzustands (spiegelt backend
 *  `schemas/metrics.py` Status). Teilmenge des Sidebar-`Ampel`-Typs. */
export type MetricStatus = "green" | "amber" | "red";

/** systemd-Dienst-Zustand (spiegelt backend `ServiceStatus`). */
export type MetricServiceStatus = "active" | "inactive" | "failed" | "unknown";

export interface GaugeCpu {
  percent: number;
  cores: number;
  /** Belegte Cores ≈ percent/100 · cores (für „0,2 / 8"). */
  used_cores: number;
  status: MetricStatus;
  /** Rollierender Verlauf für die Sparkline. */
  history: number[];
}

export interface GaugeMem {
  percent: number;
  used_gb: number;
  total_gb: number;
  status: MetricStatus;
  history: number[];
}

export interface GaugeSwap {
  percent: number;
  used_gb: number;
  total_gb: number;
}

export interface GaugeDisk {
  percent: number;
  used_gb: number;
  total_gb: number;
  mount: string;
  status: MetricStatus;
  history: number[];
}

export interface GaugeLoad {
  load1: number;
  load5: number;
  load15: number;
  /** (Load1/Cores)·100 — Bewertungsgröße für die Ampel. */
  per_core: number;
  status: MetricStatus;
  history: number[];
}

export interface MetricNetIO {
  rx_bytes_per_sec: number;
  tx_bytes_per_sec: number;
}

export interface MetricTopProcess {
  pid: number;
  name: string;
  cpu_percent: number;
  mem_percent: number;
}

export interface MetricServiceHealth {
  name: string;
  status: MetricServiceStatus;
}

/** Antwort von GET /metrics/current — vollständiger Snapshot inkl. Verlauf. */
export interface MetricsSnapshot {
  timestamp: string;
  overall_status: MetricStatus;
  cpu: GaugeCpu;
  memory: GaugeMem;
  swap: GaugeSwap;
  disk: GaugeDisk;
  load: GaugeLoad;
  net: MetricNetIO;
  uptime_seconds: number;
  top_processes: MetricTopProcess[];
  services: MetricServiceHealth[];
}

/** Antwort von GET /metrics/status — leichtgewichtige Gesamt-Ampel (Sidebar). */
export interface MetricsStatus {
  status: MetricStatus;
}

// --- PROJ-22: Multi-Agent-Dispatch (Koordinator) ---------------------------

/** Ein Posten des Verteilungsplans: ein Ticket aus features/INDEX.md + die vom
 *  Koordinator (Smart-Launcher-Logik, PROJ-9) abgeleitete Zuweisung. Spiegelt das
 *  geplante backend/app/schemas/coordinator.py DispatchPlanItem. */
export interface CoordinatorPlanItem {
  ticket_id: string; // „PROJ-22"
  title: string;
  status: string; // INDEX-Status (Planned, Architected, …)
  /** Abgeleitete Rolle/Skill/Engine/Modell für die Spezialisten-Session. */
  role: string | null;
  skill: string | null;
  engine: string;
  model: ModelName | null;
  /** Position in der topologisch sortierten Dispatch-Reihenfolge (1-basiert). */
  order: number;
  /** Tickets, von denen dieses laut `Abhängigkeiten`-Spalte abhängt. */
  dependencies: string[];
  /** true → wird (noch) nicht dispatcht, weil ein `Requires`-Ticket nicht im
   *  erforderlichen Zustand ist; `blocked_reason` trägt den Klartext. */
  blocked: boolean;
  blocked_reason: string | null;
}

/** Antwort von POST /coordinator/plan — der Verteilungsplan VOR dem Dispatch
 *  (Human-in-the-Loop). `warnings` deckt zirkuläre/fehlende Abhängigkeiten ab;
 *  dispatchbar ist nur der auflösbare Teilgraph (`items` ohne `blocked`). */
export interface CoordinatorPlan {
  project_path: string;
  items: CoordinatorPlanItem[];
  warnings: string[];
}

/** Live-Sicht einer Koordinator-Flotte (GET /coordinator/{id}/fleet):
 *  die Koordinator-Session + ihre Kind-Sessions als zusammengehörige Gruppe. */
export interface CoordinatorFleet {
  coordinator: Session;
  children: Session[];
  /** true → Dispatch pausiert (keine neuen Tickets werden gestartet). */
  paused: boolean;
  /** Vault-Pointer auf den API-Vertrag (von allen Kindern geteilt). */
  contract_pointer: string | null;
  /** M3: bei vollem Engine-Slot eingereihte Tickets (IDs) — rücken automatisch nach. */
  queued: string[];
}

// --- PROJ-25: Auth (JWT) + owner-Scope -------------------------------------

/** Angemeldete Identität. `user_id` ist zugleich der `owner`-Wert, gegen den
 *  serverseitig bescoped wird (Sessions/Handovers/Wissensnotizen/Vault). */
export interface AuthUser {
  user_id: string;
  username: string;
}

/** Antwort von POST /auth/login bzw. /auth/bootstrap. Der Refresh-Token wird
 *  NICHT im Body geführt, sondern vom Backend als httpOnly-Cookie gesetzt. */
export interface LoginResult {
  access_token: string;
  user: AuthUser;
}

/** Öffentlicher Status von GET /auth/status — steuert, ob die Login-Seite den
 *  Bootstrap-Modus (erster Account) statt des normalen Logins zeigt. */
export interface AuthStatus {
  has_users: boolean;
}

// --- PROJ-43: VPS-Admin Terminal (ttyd-iFrame) -----------------------------

/** Antwort von GET /terminal/info — Erreichbarkeit + einzubettende ttyd-URL.
 *  `enabled=false` ⇒ kein Terminal-Dienst konfiguriert (Hinweis statt iFrame).
 *  `reachable` kommt aus einem kurzen TCP-Probe im Backend (Dienst aus vs. an).
 *  `url` wird ausschließlich vom Backend gesetzt, nie vom Client. */
export interface TerminalInfo {
  enabled: boolean;
  url: string | null;
  reachable: boolean;
}

// --- PROJ-26: Marktplatz/Registry für Rollen/Skills/Agenten ----------------

/** Was die Registry verwaltet — bestimmt den Resolver-Pfad, an den eine aktive
 *  Definition gelegt wird (Rolle/Skill/Agent). */
export type RegistryType = "role" | "skill" | "agent";

/** Lebenszyklus eines Katalog-Eintrags. `installed` = vorhanden, aber noch nicht
 *  aktiviert (frisch importiert); `active`/`inactive` = vom Nutzer geschaltet.
 *  Nur `active` steht Sessions/Launcher (PROJ-9) zur Verfügung. */
export type RegistryStatus = "installed" | "active" | "inactive";

/** Ein Katalog-Eintrag (GET /registry/catalog). `default_policy` ist die beim
 *  Import konservativ vergebene Trust-Stufe (PROJ-10, nie auto-allow ungeprüft);
 *  `capabilities` listet die von der Definition angeforderten Tools. */
export interface RegistryEntry {
  id: string;
  typ: RegistryType;
  name: string;
  beschreibung: string;
  status: RegistryStatus;
  version: string;
  /** PROJ-25-kompatibles Eigentümer-Feld; bis Auth da ist lokaler Single-User-Default. */
  owner: string | null;
  /** Angeforderte Tools (Capability-Vorschau / Risiko-Einschätzung). */
  capabilities: string[];
  /** Konservativ vergebene Trust-Default-Stufe (card/deny — nie auto-allow). */
  default_policy: PolicyLevel;
  /** false → Quelle nicht verifiziert (Import aus fremder Quelle, ohne PROJ-25). */
  verified: boolean;
  /** true → referenziert ein nicht mehr vorhandenes Tool → „eingeschränkt lauffähig". */
  limited: boolean;
}

/** Eine frühere Version eines Eintrags (Rollback-Quelle). */
export interface RegistryVersion {
  version: string;
  created_at: string;
  note: string | null;
  /** true → diese Version referenziert ein fehlendes Tool (Rollback nur eingeschränkt). */
  limited: boolean;
}

/** Detail eines Eintrags (GET /registry/{typ}/{id}) inkl. Definition + Historie. */
export interface RegistryEntryDetail extends RegistryEntry {
  /** Der eigentliche Rollen-/Skill-/Agenten-Prompt (definition.md). */
  definition: string;
  /** Versions-Historie, neueste zuerst. */
  versions: RegistryVersion[];
}

/** Antwort von GET /registry/catalog. */
export interface RegistryCatalog {
  entries: RegistryEntry[];
}

/** Capability-/Policy-Vorschau von POST /registry/import — das Paket ist hier
 *  NOCH NICHT aktiv. `token` wird unverändert an /registry/import/confirm
 *  zurückgegeben (Human-in-the-Loop). `collision` = ID existiert schon →
 *  Import erzeugt eine neue Version statt zu überschreiben. */
export interface RegistryImportPreview {
  token: string;
  id: string;
  typ: RegistryType;
  name: string;
  beschreibung: string;
  version: string;
  owner: string | null;
  /** Schema-Version des Pakets — bei Inkompatibilität wird der Import abgewiesen. */
  schema_version: string;
  capabilities: string[];
  default_policy: PolicyLevel;
  verified: boolean;
  collision: boolean;
  /** Warnungen (unbekannte/gefährliche Tools, „Quelle nicht verifiziert" …). */
  warnings: string[];
}
