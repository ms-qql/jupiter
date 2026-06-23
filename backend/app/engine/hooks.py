"""Baut die session-skopierte ``--settings``-JSON für den Freigabe-Hook (PROJ-4).

Claude Code wird mit dieser zusätzlichen Settings-JSON gestartet; sie registriert
einen PreToolUse-Hook über **alle** Tools (``matcher: "*"``). Welche Tool-Nutzung
tatsächlich eine Card braucht, entscheidet ausschließlich ``policy.requires_card``
serverseitig — der Matcher ist bewusst breit, damit der Trigger an genau EINER
Stelle im Code lebt (Vorbereitung auf #5).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Pfad zum eigenständigen Hook-Skript (stdlib-only).
_HOOK_SCRIPT = str(Path(__file__).resolve().parent / "permission_hook.py")


def build_hook_settings(
    self_url: str,
    token: str,
    timeout_seconds: int,
    hook_script: str = _HOOK_SCRIPT,
    python_bin: str | None = None,
) -> str:
    """Liefert die ``--settings``-JSON als String (Claude akzeptiert Datei ODER String).

    Der Hook-Befehl nutzt denselben Python-Interpreter wie das Backend
    (``sys.executable``), damit das Skript zuverlässig läuft.
    """
    python_bin = python_bin or sys.executable
    command = f'{python_bin} {hook_script} --url {self_url} --token {token}'
    settings = {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "*",
                    "hooks": [
                        {
                            "type": "command",
                            "command": command,
                            "timeout": timeout_seconds,
                        }
                    ],
                }
            ]
        }
    }
    return json.dumps(settings)
