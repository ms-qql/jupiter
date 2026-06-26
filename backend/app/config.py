"""Konfiguration (pydantic-settings). Env-Prefix: JUPITER_."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Standard-Ort der Konstitutions-MD-Dateien: backend/constitution/.
_DEFAULT_CONSTITUTION_DIR = str(Path(__file__).resolve().parent.parent / "constitution")

# Standard-Ort der Trust-Policy (PROJ-10): backend/config/policy.yaml. Muss NICHT
# existieren — fehlt sie, gilt der konservative Default (rückwärtskompatibel zu PROJ-4).
_DEFAULT_POLICY_PATH = str(Path(__file__).resolve().parent.parent / "config" / "policy.yaml")

# Standard-Ort der Watchdog-Limits (PROJ-16): backend/config/watchdog.yaml. Muss
# NICHT existieren — fehlt/defekt → eingebaute konservative Defaults (nie „kein Watchdog").
_DEFAULT_WATCHDOG_PATH = str(Path(__file__).resolve().parent.parent / "config" / "watchdog.yaml")

# Standard-Ort der Engine-Registry (PROJ-18): backend/config/engines.yaml. Muss NICHT
# existieren — fehlt/defekt → nur die eingebaute Claude-Engine (rückwärtskompatibel).
# Hier werden weitere CLI-Engines, iFrame-Einbettungen und Launch-Einträge OHNE
# Codeänderung registriert (live editierbar, mtime-geprüft wie Policy/Watchdog).
_DEFAULT_ENGINES_PATH = str(Path(__file__).resolve().parent.parent / "config" / "engines.yaml")

# Standard-Ort der Konsumenten-Registry (PROJ-24): backend/config/consumers.yaml. Muss
# NICHT existieren — fehlt/defekt → kein externer Konsument (nur der optionale interne
# Voll-Scope-Konsument, falls ein Key gesetzt ist). Live mtime-geprüft wie engines.yaml.
_DEFAULT_CONSUMERS_PATH = str(Path(__file__).resolve().parent.parent / "config" / "consumers.yaml")

# Standard-Ort der Liveness-Schwellen (PROJ-27): backend/config/liveness.yaml. Muss
# NICHT existieren — fehlt/defekt → eingebaute konservative Defaults (nie „kein Liveness";
# Auto-Reanimierung mit hartem Limit). Live mtime-geprüft wie Policy/Watchdog.
_DEFAULT_LIVENESS_PATH = str(Path(__file__).resolve().parent.parent / "config" / "liveness.yaml")

# Standard-Wurzel der Marktplatz/Registry (PROJ-26): backend/registry/. Dort liegen die
# installierten Rollen/Skills/Agenten (manifest.yaml + definition.md + versions/) und das
# Import/Export-Staging. Datei-first, kein DB-Zwang — git-versionierbar, von Hand prüfbar.
_DEFAULT_REGISTRY_ROOT = str(Path(__file__).resolve().parent.parent / "registry")

# Im MVP unterstützte Modell-Aliase (werden 1:1 an `claude --model` durchgereicht).
VALID_MODELS: set[str] = {"haiku", "sonnet", "opus"}

# Alle Headless-Permission-Modi, die Claude Code kennt.
VALID_PERMISSION_MODES: set[str] = {"default", "acceptEdits", "plan", "bypassPermissions"}

# Erlaubte Modi: `plan` bleibt gesperrt. `bypassPermissions` ist auf ausdrücklichen
# Nutzerwunsch wählbar (Vollautonomie). ACHTUNG: bypassPermissions umgeht in Claude
# Code die Permission-Prüfung → die PROJ-4-Decision-Cards greifen dann NICHT (kein
# Freigabe-Gate, kein Watchdog #19 vorhanden). Bewusste Nutzerentscheidung pro Session.
MVP_ALLOWED_PERMISSION_MODES: set[str] = {"default", "acceptEdits", "bypassPermissions"}

# Obergrenze für Prompt-/Eingabe-Länge in Zeichen (QA-2) — verhindert blindes
# Fluten des Kontextfensters.
MAX_INPUT_CHARS: int = 100_000

# Kontext-Schwelle (PROJ-5): erlaubter Bereich, auf den jeder Schwellenwert
# (global oder pro Session) geklemmt wird. Schützt vor Fehlkonfiguration
# (0/100/Unsinn → keine Dauerwarnung, kein „nie warnen").
THRESHOLD_MIN_PCT: int = 50
THRESHOLD_MAX_PCT: int = 98


def clamp_threshold(value: int) -> int:
    """Klemmt die Kontext-Schwelle auf ``[THRESHOLD_MIN_PCT, THRESHOLD_MAX_PCT]``."""
    return max(THRESHOLD_MIN_PCT, min(THRESHOLD_MAX_PCT, int(value)))


# PROJ-42 — VPS-Admin Ampel-Schwellen (Auslastung in %): < WARN grün,
# WARN..CRIT gelb, > CRIT rot. Gilt für CPU/RAM/Disk und (Load1/Cores)*100.
METRIC_WARN_PCT: int = 75
METRIC_CRIT_PCT: int = 90


# PROJ-14 — Limit paralleler Sessions: Untergrenze. Eine Fehlkonfiguration
# (0/negativ) würde jede Session-Erstellung blockieren → auf mind. 1 klemmen.
SESSION_LIMIT_MIN: int = 1


def clamp_session_limit(value: int) -> int:
    """Klemmt das Limit gleichzeitiger Sessions auf ``>= SESSION_LIMIT_MIN`` (Edge-Case ``Limit = 0``)."""
    return max(SESSION_LIMIT_MIN, int(value))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JUPITER_", env_file=".env", extra="ignore")

    # Pfad/Name des Claude-Code-CLI-Binaries (Subscription-Auth via `claude login`).
    claude_bin: str = "claude"

    # PROJ-13: Pfad/Name des git-Binaries + hartes Zeitlimit je Git-Aufruf.
    # Git läuft als parametrisierter Subprozess (kein Shell, keine interaktiven
    # Flags) ausschließlich innerhalb der allowed_roots. Status muss schnell sein
    # (pollbar im Cockpit) → knappes Timeout statt unbegrenztem Hängen.
    git_bin: str = "git"
    git_timeout_seconds: float = 15.0

    # Verzeichnisse, in denen Sessions arbeiten dürfen (Projekt-Scope, PROJ-1-Entscheidung).
    allowed_roots: list[str] = ["/home/dev/projects", "/home/dev/tools"]

    # Defaults für neue Sessions.
    default_model: str = "sonnet"
    default_permission_mode: str = "default"

    # Single-User-MVP: kein JWT — der Owner wird serverseitig gestempelt (#21).
    # PROJ-25: bleibt der Owner-Wert des Bootstrap-Accounts (= ``user_id`` des ersten
    # Nutzers), damit vor dem Auth angelegte Artefakte (``owner="dev"``) nahtlos diesem
    # Account gehören (Migration ohne Datenverlust). Solange keine Nutzerbasis existiert,
    # ist es auch der Anonym-Owner (rückwärtskompatibler Single-User-Betrieb).
    default_owner: str = "dev"

    # --- Auth / JWT (PROJ-25) --------------------------------------------
    # JWT HS256. Das Secret MUSS in Prod via JUPITER_JWT_SECRET (≥ 32 Byte zufällig)
    # gesetzt werden — der Default ist NUR für lokale Dev gedacht und wird beim Start
    # mit einer Warnung quittiert. Ein Wechsel des Secrets invalidiert alle Tokens.
    jwt_secret: str = "dev-only-insecure-change-me-jupiter-jwt-secret-0123456789"
    jwt_algorithm: str = "HS256"
    # Kurzer Access-Token (Minuten) begrenzt den Schaden eines Leaks; langer Refresh
    # (Tage) hält den Login bequem. Stack-Konvention: 15 min / 7 d.
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 7
    # httpOnly-Refresh-Cookie. ``secure``/``samesite`` sind dev-tauglich vorbelegt
    # (cross-site :3000→:8000 braucht im Dev http → samesite="lax" + secure=False).
    # In Prod (gleiche Origin hinter TLS) via Env auf secure=True/samesite="strict".
    refresh_cookie_name: str = "jupiter_refresh"
    refresh_cookie_secure: bool = False
    refresh_cookie_samesite: str = "lax"
    refresh_cookie_path: str = "/auth"
    # Mindestlänge für Bootstrap-/Login-Passwörter (Eingabe-Validierung).
    password_min_length: int = 8
    # Rate-Limiting der öffentlichen Auth-Endpunkte (Login/Bootstrap/Refresh) gegen
    # Brute-Force — nötig, seit der Forward-Auth-Perimeter entfernt wurde und /auth/*
    # direkt internet-exponiert ist. In Tests via conftest abgeschaltet.
    auth_rate_limit_enabled: bool = True

    # CORS-Origins für das Browser-Frontend (PROJ-3 Cockpit). Dev-Default = Next.js
    # auf :3000. In Prod via JUPITER_CORS_ORIGINS (JSON-Liste) überschreiben.
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Sekunden Kulanz zwischen SIGTERM und SIGKILL beim Stoppen.
    process_stop_grace_seconds: float = 5.0

    # --- PROJ-14: Härtung (Limit + Persistenz) ---------------------------
    # Obergrenze gleichzeitig AKTIVER Sessions (starting/running/waiting/
    # awaiting_approval). Schützt den Single-Worker-VPS vor Ressourcen-Überlast
    # (jede Session ist ein headless-claude-Subprozess mit eigenem RAM-/CPU-Bedarf).
    # Default bewusst großzügig für einen Dev-VPS; in Prod via
    # JUPITER_MAX_PARALLEL_SESSIONS an CPU/RAM anpassen. Wird auf >= 1 geklemmt.
    max_parallel_sessions: int = 12
    # Persistenz-Seam: Live-Index der Sessions in SQLite spiegeln, damit die
    # Übersicht einen Backend-Neustart übersteht. False → reines In-Memory
    # (NullRepository), wie vor PROJ-14.
    session_index_enabled: bool = True
    # Pfad der SQLite-Datei (Live-Index, NICHT die Wahrheit — die bleibt der Vault).
    # Wird inkl. Elternverzeichnis bei Bedarf automatisch angelegt.
    session_index_db_path: str = str(Path.home() / "jupiter-data" / "session_index.db")
    # PROJ-33: Nach einem GEORDNETEN Backend-Neustart gedrainte Sessions automatisch via
    # `claude --resume` fortsetzen. False → Sessions bleiben verwaist + manueller Knopf.
    auto_resume_on_restart: bool = True

    # PROJ-19 (#27): Prompt-Caching. An → stabile Prompt-Bestandteile (Konstitution/
    # Rolle) bilden das cache-freundliche Präfix + werden über einen Inhalts-Hash
    # identifiziert (Änderung = automatische Invalidierung). Aus → identische
    # Assemblierung, nur ohne Cache-Key (No-op-Fallback, kein Hard-Fail).
    prompt_cache_enabled: bool = True

    # PROJ-19 (#26): billige Späher-Agenten. Kurzlebiger, nicht-steuerbarer Lauf auf
    # dem günstigen Modell, der viel liest/sucht und nur das Fazit zurückgibt. Aus →
    # Endpunkt liefert 503 (kein Hard-Fail im Treiber-Pfad).
    scout_enabled: bool = True
    scout_default_model: str = "haiku"  # günstiges Modell für Fazit-Aufgaben.
    scout_timeout_seconds: int = 180
    scout_max_context_chars: int = 40_000  # eingelesener Kontext gedeckelt (Kosten-Schutz).

    # --- Decision Cards / Freigabe-Hook (PROJ-4) ---------------------------
    # Freigabe-Flow aktivieren: Sessions starten mit dem PreToolUse-Hook.
    enable_decision_cards: bool = True
    # Eigene Backend-URL, die der Hook-Subprozess (lokal) erreicht.
    hook_self_url: str = "http://127.0.0.1:8000"
    # Geteiltes Geheimnis für den internen Hook-Endpoint (nur localhost-Aufrufe).
    hook_token: str = "jupiter-local-hook"
    # Obergrenze, wie lange Claude auf die Entscheidung wartet (Hook-Timeout, Sek.).
    # Bewusst groß (24 h): kein Timeout-Autoproceed; läuft er ab, greift Claudes
    # sicherer Default (deny). Edge-Case „Nutzer ignoriert Card lange".
    hook_timeout_seconds: int = 86_400

    # Verzeichnis der Knappheits-Konstitution (PROJ-6): global.md + roles/<rolle>.md.
    constitution_dir: str = _DEFAULT_CONSTITUTION_DIR

    # Trust-Policy-Datei (PROJ-10): abgestufte Freigabe-Regeln + Phasen-Gate. Wird
    # bei JEDER Auswertung mtime-geprüft (live editierbar ohne Neustart). Fehlt/kaputt
    # → konservativer Default + sichtbare Warnung.
    policy_config_path: str = _DEFAULT_POLICY_PATH

    # Watchdog-Limits-Datei (PROJ-16): vier Schwellen (Tokens/Zeit, Laufzeit-ohne-
    # Fortschritt, identische Tool-Calls, Schreibrate) als Reißleine. Wird live
    # mtime-geprüft (editierbar ohne Neustart). Fehlt/kaputt → konservative Defaults.
    watchdog_config_path: str = _DEFAULT_WATCHDOG_PATH

    # Engine-Registry-Datei (PROJ-18): weitere CLI-Engines / iFrames / Launch-Einträge.
    # Live mtime-geprüft; fehlt/kaputt → nur die eingebaute Claude-Engine (kein Crash).
    engines_config_path: str = _DEFAULT_ENGINES_PATH

    # Liveness-Schwellen-Datei (PROJ-27): Fortschritts-Timeout, Poll-Frequenz, Auto-
    # Reanimierungs-Versuche/Backoff + globaler An/Aus-Schalter. Live mtime-geprüft;
    # fehlt/kaputt → konservative Defaults (nie „kein Liveness").
    liveness_config_path: str = _DEFAULT_LIVENESS_PATH

    # Marktplatz/Registry-Wurzel (PROJ-26): installierte Rollen/Skills/Agenten +
    # Import/Export-Staging. Wird bei Bedarf angelegt; leerer Ordner = leerer Katalog.
    registry_root: str = _DEFAULT_REGISTRY_ROOT

    # Hal-Vault (PROJ-2): Lese-/Such-Wurzel = GANZER Vault; geschrieben wird NUR im
    # Jupiter-Unterbaum (Agentic OS/Jupiter), ohne die PARA-Struktur zu verändern.
    vault_root: str = "/home/dev/tools/Hal"
    vault_jupiter_subdir: str = "Agentic OS/Jupiter"
    # Roh-Session-Logs beim Session-Ende automatisch in den Vault schreiben (Grundlage #8/#9).
    vault_autolog: bool = True

    # --- Vault als geteilter Dienst (PROJ-24) ----------------------------
    # Konsumenten-Registry (id + api_key + read/write-Scope-Globs). Live mtime-geprüft;
    # fehlt/kaputt → kein externer Konsument (Dienst bleibt nutzbar, nur intern/leer).
    # Secrets (api_key) NUR hier in der gitignored Datei, nie im Repo.
    consumers_config_path: str = _DEFAULT_CONSUMERS_PATH
    # Optionaler eingebauter Voll-Scope-Konsument „jupiter" für HTTP-Aufrufer (Lesen ganzer
    # Vault, Schreiben im Jupiter-Bereich). Leer = AUS (kein impliziter HTTP-Vollzugriff).
    # Single-User-Brücke bis PROJ-25 (JWT) — Key aus der Server-Umgebung.
    vault_internal_consumer_key: str = ""
    # Harte Obergrenze für Volltext-Lesen über /vault/v1/read?mode=full (Bytes). Größere
    # Dateien → 413 mit Hinweis auf mode=excerpt (Edge Case „Große Datei").
    vault_max_read_bytes: int = 1_000_000
    # Pfad des Audit-Logs (Append-only JSONL) relativ zum Jupiter-Schreibbereich. Bleibt
    # offen lesbar (keine Black-Box) und trägt Herkunft jedes Schreibzugriffs.
    vault_audit_rel_path: str = "_audit/vault-writes.jsonl"

    # --- Kuratierung / Vault Stufe 3 (PROJ-15) ---------------------------
    # Ereignisgetriebene Wissens-Vorschläge: erkannte Marker (Bug gelöst / ADR /
    # Sackgasse) im Session-Stream erzeugen eine nicht-blockierende Vorschlags-Card.
    # False → kein Marker-Scan (wie vor PROJ-15).
    enable_curation: bool = True

    # --- MD-Reader (PROJ-7) ----------------------------------------------
    # Standard-„Projekt"-Quelle des read-only MD-Readers (Feature-Specs unter
    # features/, Doku unter docs/). Muss innerhalb von allowed_roots liegen.
    # Pro Request via ?project=<pfad> überschreibbar (z. B. project_path der Session).
    reader_default_project: str = "/home/dev/projects/jupiter"

    # --- Kontext-Management & Handover (PROJ-5) ---------------------------
    # Schwelle (%) für Kontext-Warnung + Handover-Vorschlag. Global; pro Session
    # überschreibbar. Beim Lesen/Setzen auf [THRESHOLD_MIN_PCT, THRESHOLD_MAX_PCT]
    # geklemmt.
    context_fill_threshold_pct: int = 50
    # Optionale LLM-Anreicherung der Handover-Prosa (Hybrid-Generator). Default
    # AUS: das mechanische Gerüst ist der garantierte, deterministische Pfad;
    # die Anreicherung ist ein optionaler Aufsatz (Tech-Design PROJ-5).
    handover_llm_enrich: bool = False

    # --- Fileexplorer + Clipboard (PROJ-11) ------------------------------
    # Globaler, kurzer Clipboard-Ordner: Pastes/Drops landen hier, der Pfad ist
    # aus jeder Session/jedem Terminal kurz referenzierbar. MUSS innerhalb von
    # allowed_roots liegen (sonst weder im Explorer browsbar noch sicher). Wird
    # bei Bedarf automatisch angelegt. Pro Lauf via JUPITER_CLIPBOARD_DIR / PATCH
    # /settings/clipboard-dir überschreibbar.
    clipboard_dir: str = "/home/dev/projects/clipboard"
    # Obergrenze pro hochgeladener Datei (Streaming-Abbruch bei Überschreitung).
    upload_max_file_bytes: int = 50 * 1024 * 1024  # 50 MB
    # Erlaubte Datei-Endungen (lowercase, ohne Punkt) für Uploads. LEERE Menge =
    # alle erlauben (Escape-Hatch). Default deckt Bilder + gängige Dokumente ab.
    upload_allowed_extensions: set[str] = {
        # Bilder
        "png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "avif", "heic",
        # Dokumente / Text / Daten
        "pdf", "txt", "md", "markdown", "rtf", "csv", "tsv", "json", "yaml",
        "yml", "log", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt",
        "ods", "odp",
        # Archive
        "zip", "tar", "gz", "tgz",
    }

    # --- Spracheingabe / Push-to-Talk (PROJ-20) --------------------------
    # Standard ist self-hosted faster-whisper (lokal, kein API-Key, keine
    # laufenden Kosten). Modellgröße als Kompromiss aus Deutsch-Qualität und
    # CPU-Latenz/RAM auf dem GPU-losen Dev-VPS; via Env hoch-/runterschaltbar.
    whisper_model: str = "small"
    # Transkriptions-Sprache (Default Deutsch); pro Request überschreibbar.
    whisper_language: str = "de"
    # Optionaler Groq-Cloud-Fallback (pay-per-use). Leerer Key = nicht verfügbar.
    # Secret NUR aus der .env (JUPITER_GROQ_API_KEY), nie im Repo.
    groq_api_key: str = ""
    # Cloud-Fallback bewusst an/aus. Default AUS (DSGVO: Audio bleibt lokal).
    # Greift nur, wenn zusätzlich ein Key gesetzt ist.
    use_groq_transcription: bool = False
    # Längenlimit der Aufnahme (Sek.) — Schutz vor Riesen-Uploads. Das Frontend
    # stoppt zusätzlich clientseitig; hier ist die serverseitige Obergrenze.
    max_audio_seconds: int = 120
    # Harte Obergrenze der Audio-Größe (Bytes) als zweite Verteidigungslinie.
    max_audio_bytes: int = 25 * 1024 * 1024  # 25 MB

    # --- Video Summary (PROJ-41) -----------------------------------------
    # Native Micro-App: reiht Video-URLs ein und lässt sie von einer headless
    # Claude-Session über den `hal-video-summary`-Skill in Notiz+PDF (Hal-Vault)
    # umwandeln. Warteschlange + Einstellungen leben in einer eigenen SQLite-Datei
    # (überlebt Neustart, Akzeptanzkriterium). Wird inkl. Elternverzeichnis bei
    # Bedarf automatisch angelegt.
    video_summary_db_path: str = str(Path.home() / "jupiter-data" / "video_summary.db")
    # Poll-Frequenz des Hintergrund-Workers (Sek.). Niedrigfrequent — die Skill-Läufe
    # dauern Minuten, der Tick muss nur Zustandswechsel einsammeln und nachstarten.
    video_summary_poll_interval_seconds: float = 5.0
    # Drossel gegen YouTube-Blocking: nach `batch_size` Videos in Folge eine
    # Cooldown-Pause; Default-Werte (pro App-Einstellungen überschreibbar/persistiert).
    video_summary_default_cooldown_minutes: int = 30
    video_summary_batch_size: int = 4
    # Modell + Permission-Mode der Verarbeitungs-Sessions. bypassPermissions, weil
    # headless KEIN interaktives Decision-Card-Gate bedient werden kann (sonst hinge
    # jeder yt-dlp-/ffmpeg-Aufruf ewig auf einer Freigabe).
    video_summary_model: str = "sonnet"
    video_summary_permission_mode: str = "bypassPermissions"
    # Arbeitsverzeichnis (cwd/Scope) der Verarbeitungs-Sessions. Default = Hal-Vault,
    # in dem der Skill ohnehin schreibt. MUSS innerhalb allowed_roots liegen + existieren.
    video_summary_project_path: str = "/home/dev/tools/Hal"

    # --- VPS-Admin Metriken (PROJ-42) ------------------------------------
    # Read-only Host-Metriken (CPU/RAM/Disk/Load/Swap/Netz/Uptime/Prozesse) +
    # systemd-Service-Health. Ein Hintergrund-Worker misst periodisch und cached
    # Snapshot + rollierenden Verlauf IM SPEICHER (flüchtige Live-Daten, bewusst
    # KEINE DB — passt zur Live-Index-Haltung; Verlust nach Neustart ist ok).
    metrics_poll_interval_seconds: float = 5.0
    # Länge des rollierenden Verlaufs je Kennzahl (Sparklines). 60 Punkte ≈ 5 min
    # bei 5 s Takt.
    metrics_history_points: int = 60
    # PROJ-22 (M3): Takt, in dem eingereihte Flotten-Tickets nachrücken, sobald ein
    # Engine-Slot frei wird (Hintergrund-Drain).
    coordinator_drain_interval_seconds: float = 5.0
    # Anzahl der Top-Prozesse (nach CPU, dann RAM) im Snapshot.
    metrics_top_processes: int = 5
    # Erwartete systemd-Dienste der Service-Health-Liste (Anzeigereihenfolge).
    # Nicht gefundene Dienste → Status "unknown" (kein Crash, zählt nicht zur Ampel).
    metrics_services: list[str] = [
        "jupiter-backend",
        "jupiter-frontend",
        "jupiter-webhook",
        "caddy",
    ]
    # Hartes Zeitlimit je `systemctl is-active`-Aufruf (Sek.) — Status muss schnell
    # bleiben (pollbar), nie unbegrenzt hängen.
    metrics_systemctl_timeout_seconds: float = 5.0

    # --- VPS-Admin Terminal (PROJ-43) ------------------------------------
    # ttyd-Shell als iFrame im Terminal-Tab der VPS-Admin-Micro-App. Die URL wird
    # AUSSCHLIESSLICH hier (Backend-Config) gesetzt, nie vom Client — sie ist die
    # gleich-origin Caddy-Route auf den lokal gebundenen ttyd-Dienst.
    # Leer = Feature AUS (enabled=false) → das Frontend zeigt sauber „nicht
    # konfiguriert" statt einer kaputten Fläche; aktiviert wird per /abc-deploy
    # (JUPITER_TERMINAL_URL setzen, ttyd+Caddy einrichten).
    terminal_url: str = ""
    # Erreichbarkeits-Probe: kurzer TCP-Connect auf den LOKAL gebundenen ttyd-Port
    # (Default 127.0.0.1:7681). Trennt „Dienst aus" (reachable=false → Hinweis+Retry)
    # von „Einbettung verweigert" (greift dann der iFrame-Fallback im Frontend).
    # Host/Port kommen NUR aus der Config (keine Client-Eingabe, keine Shell).
    terminal_probe_host: str = "127.0.0.1"
    terminal_probe_port: int = 7681
    terminal_probe_timeout_seconds: float = 1.5


settings = Settings()
