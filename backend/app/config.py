"""Konfiguration (pydantic-settings). Env-Prefix: JUPITER_."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict

# Im MVP unterstützte Modell-Aliase (werden 1:1 an `claude --model` durchgereicht).
VALID_MODELS: set[str] = {"haiku", "sonnet", "opus"}

# Headless-Permission-Modi von Claude Code.
VALID_PERMISSION_MODES: set[str] = {"default", "acceptEdits", "plan", "bypassPermissions"}


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

    # Sekunden Kulanz zwischen SIGTERM und SIGKILL beim Stoppen.
    process_stop_grace_seconds: float = 5.0


settings = Settings()
