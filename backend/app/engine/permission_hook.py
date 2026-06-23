"""PreToolUse-Hook-Skript — Brücke Claude-Code-Session ↔ Jupiter-Backend (PROJ-4).

Claude Code ruft dieses Skript vor jeder genehmigungspflichtigen Tool-Nutzung auf
(`--settings` mit `hooks.PreToolUse`). Es liest den Hook-Payload von **stdin**
(enthält u. a. ``session_id``, ``tool_name``, ``tool_input``, ``tool_use_id``),
reicht ihn an das Backend (`POST /internal/permission`) weiter und **blockiert**, bis
der Nutzer im Cockpit entschieden hat. Die Antwort des Backends ist bereits der exakte
PreToolUse-Hook-Output (`hookSpecificOutput`) und wird unverändert auf **stdout**
ausgegeben.

Bewusst **nur Standardbibliothek** (json, sys, os, urllib) — das Skript läuft als
eigenständiger Subprozess in beliebigem cwd, ohne das ``app``-Paket oder Dritt-Pakete.

Fail-safe: Bei jedem Fehler (Backend nicht erreichbar, Timeout, kaputte Antwort) wird
**abgelehnt** — Jupiter genehmigt im Zweifel nie automatisch.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request


def _deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def main() -> int:
    url = os.environ.get("JUPITER_HOOK_URL", "http://127.0.0.1:8000").rstrip("/")
    token = os.environ.get("JUPITER_HOOK_TOKEN", "")
    # CLI-Overrides (--url / --token) haben Vorrang vor der Umgebung.
    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg == "--url" and i + 1 < len(argv):
            url = argv[i + 1].rstrip("/")
        elif arg == "--token" and i + 1 < len(argv):
            token = argv[i + 1]

    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except (json.JSONDecodeError, ValueError):
        print(json.dumps(_deny("Hook-Eingabe unlesbar — vorsichtshalber blockiert.")))
        return 0

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{url}/internal/permission",
        data=body,
        headers={"Content-Type": "application/json", "X-Jupiter-Hook-Token": token},
        method="POST",
    )
    try:
        # Kein client-seitiges Timeout: der Nutzer darf sich beliebig Zeit lassen
        # (AC: kein Timeout-Autoproceed). Claude Codes Hook-Timeout begrenzt die
        # Wartezeit nach oben; läuft er ab, greift dort der sichere Default (deny).
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        print(json.dumps(_deny(f"Jupiter nicht erreichbar — blockiert ({exc}).")))
        return 0
    except (json.JSONDecodeError, ValueError):
        print(json.dumps(_deny("Ungültige Antwort von Jupiter — blockiert.")))
        return 0

    # Das Backend liefert bereits den fertigen hookSpecificOutput-Vertrag.
    print(json.dumps(data))
    return 0


if __name__ == "__main__":
    sys.exit(main())
