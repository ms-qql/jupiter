"""Konfiguration (pydantic-settings). Env-Prefix: JUPITER_."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Standard-Ort der Konstitutions-MD-Dateien: backend/constitution/.
_DEFAULT_CONSTITUTION_DIR = str(Path(__file__).resolve().parent.parent / "constitution")

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

    # Verzeichnisse, in denen Sessions arbeiten dürfen (Projekt-Scope, PROJ-1-Entscheidung).
    allowed_roots: list[str] = ["/home/dev/projects", "/home/dev/tools"]

    # Defaults für neue Sessions.
    default_model: str = "sonnet"
    default_permission_mode: str = "default"

    # Single-User-MVP: kein JWT — der Owner wird serverseitig gestempelt (#21).
    default_owner: str = "dev"

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

    # Hal-Vault (PROJ-2): Lese-/Such-Wurzel = GANZER Vault; geschrieben wird NUR im
    # Jupiter-Unterbaum (Agentic OS/Jupiter), ohne die PARA-Struktur zu verändern.
    vault_root: str = "/home/dev/tools/Hal"
    vault_jupiter_subdir: str = "Agentic OS/Jupiter"
    # Roh-Session-Logs beim Session-Ende automatisch in den Vault schreiben (Grundlage #8/#9).
    vault_autolog: bool = True

    # --- MD-Reader (PROJ-7) ----------------------------------------------
    # Standard-„Projekt"-Quelle des read-only MD-Readers (Feature-Specs unter
    # features/, Doku unter docs/). Muss innerhalb von allowed_roots liegen.
    # Pro Request via ?project=<pfad> überschreibbar (z. B. project_path der Session).
    reader_default_project: str = "/home/dev/projects/jupiter"

    # --- Kontext-Management & Handover (PROJ-5) ---------------------------
    # Schwelle (%) für Kontext-Warnung + Handover-Vorschlag. Global; pro Session
    # überschreibbar. Beim Lesen/Setzen auf [THRESHOLD_MIN_PCT, THRESHOLD_MAX_PCT]
    # geklemmt.
    context_fill_threshold_pct: int = 85
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


settings = Settings()
