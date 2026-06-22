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

# Im MVP erlaubte Modi (QA-1): `bypassPermissions`/`plan` sind gesperrt, bis
# PROJ-4 (Decision Cards) + #19 (Watchdog) ein Safety-Net liefern.
MVP_ALLOWED_PERMISSION_MODES: set[str] = {"default", "acceptEdits"}

# Obergrenze für Prompt-/Eingabe-Länge in Zeichen (QA-2) — verhindert blindes
# Fluten des Kontextfensters.
MAX_INPUT_CHARS: int = 100_000


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

    # Verzeichnis der Knappheits-Konstitution (PROJ-6): global.md + roles/<rolle>.md.
    constitution_dir: str = _DEFAULT_CONSTITUTION_DIR

    # Hal-Vault (PROJ-2): Lese-/Such-Wurzel = GANZER Vault; geschrieben wird NUR im
    # Jupiter-Unterbaum (Agentic OS/Jupiter), ohne die PARA-Struktur zu verändern.
    vault_root: str = "/home/dev/tools/Hal"
    vault_jupiter_subdir: str = "Agentic OS/Jupiter"
    # Roh-Session-Logs beim Session-Ende automatisch in den Vault schreiben (Grundlage #8/#9).
    vault_autolog: bool = True


settings = Settings()
