"""Trust-Policy — die EINE zentrale Stelle, die den Freigabe-Trigger definiert (PROJ-4).

Im MVP ist der Trigger **fix & konservativ** (AC PROJ-4): reine Lesezugriffe laufen
automatisch durch, jede Schreib-/Shell-/sonstige Operation erzeugt eine Decision Card.
Diese Funktion ist bewusst die einzige Quelle der Wahrheit — die konfigurierbare
Trust-Policy (#5, P1) ersetzt sie später 1:1, ohne dass der Rest des Codes sich ändert.

Außerdem destilliert dieses Modul aus dem rohen ``tool_input`` einen **knappen Ausschnitt**
(Befehl bzw. Diff) statt des Volltexts — das zahlt auf die Knappheits-Konstitution (PROJ-6)
und die Token-Disziplin ein.
"""
from __future__ import annotations

import json

# Bekannte, eindeutig lesende Tools von Claude Code → laufen ohne Card durch.
# Alles, was NICHT hier steht (Bash, Edit, Write, NotebookEdit, Task, unbekannt …),
# ist im MVP genehmigungspflichtig (konservativ: im Zweifel fragen).
AUTO_ALLOW_TOOLS: frozenset[str] = frozenset(
    {
        "Read",
        "Glob",
        "Grep",
        "NotebookRead",
        "TodoWrite",
        "WebFetch",
        "WebSearch",
        "BashOutput",
        "ListMcpResources",
        "ReadMcpResource",
    }
)

# Obergrenze für den Card-Ausschnitt (Zeichen) — nie das ganze Log in die Card.
MAX_EXCERPT_CHARS: int = 4_000
# Obergrenze für die „Warum"-Begründung (Denk-Blöcke können lang sein).
MAX_RATIONALE_CHARS: int = 800


def clip_rationale(text: str) -> str:
    """Kürzt die „Warum"-Begründung auf eine card-taugliche Länge (Token-Disziplin)."""
    return _clip(text or "", MAX_RATIONALE_CHARS)


def requires_card(tool_name: str, tool_input: dict | None = None) -> bool:
    """Zentraler Trigger: braucht diese Tool-Nutzung eine Decision Card?

    MVP-Regel: alles außer den bekannten Lese-Tools (``AUTO_ALLOW_TOOLS``) → Card.
    """
    return tool_name not in AUTO_ALLOW_TOOLS


def summarize_action(tool_name: str, tool_input: dict | None = None) -> str:
    """Kurze, menschenlesbare ‚Was'-Zeile für die Card-Überschrift."""
    inp = tool_input or {}
    if tool_name == "Bash":
        cmd = str(inp.get("command", "")).strip().splitlines()
        head = cmd[0] if cmd else ""
        return f"Shell-Befehl: {_clip(head, 80)}" if head else "Shell-Befehl"
    if tool_name in ("Edit", "MultiEdit"):
        return f"Datei bearbeiten: {inp.get('file_path', '?')}"
    if tool_name == "Write":
        return f"Datei schreiben: {inp.get('file_path', '?')}"
    if tool_name == "NotebookEdit":
        return f"Notebook bearbeiten: {inp.get('notebook_path', '?')}"
    return f"Tool: {tool_name}"


def extract_excerpt(tool_name: str, tool_input: dict | None = None) -> str:
    """Destilliert den **relevanten Ausschnitt** (Befehl/Diff), nicht den Volltext.

    - Bash       → die Befehlszeile(n) (+ Beschreibung, falls vorhanden)
    - Edit       → ein Mini-Diff (alt → neu)
    - MultiEdit  → mehrere Mini-Diffs
    - Write      → Pfad + Vorschau des Inhalts
    - sonst      → kompakt serialisierter Input
    """
    inp = tool_input or {}
    if tool_name == "Bash":
        cmd = str(inp.get("command", ""))
        desc = str(inp.get("description", "")).strip()
        body = f"$ {cmd}"
        if desc:
            body = f"# {desc}\n{body}"
        return _clip(body, MAX_EXCERPT_CHARS)
    if tool_name == "Edit":
        return _clip(_diff_block(inp), MAX_EXCERPT_CHARS)
    if tool_name == "MultiEdit":
        edits = inp.get("edits") or []
        blocks = [_diff_block(e) for e in edits if isinstance(e, dict)]
        head = f"{inp.get('file_path', '?')} ({len(blocks)} Änderung(en)):\n"
        return _clip(head + "\n\n".join(blocks), MAX_EXCERPT_CHARS)
    if tool_name == "Write":
        content = str(inp.get("content", ""))
        return _clip(f"{inp.get('file_path', '?')}:\n{content}", MAX_EXCERPT_CHARS)
    if tool_name == "NotebookEdit":
        return _clip(str(inp.get("new_source", inp)), MAX_EXCERPT_CHARS)
    # Fallback: kompaktes JSON des Inputs.
    try:
        return _clip(json.dumps(inp, ensure_ascii=False, indent=2), MAX_EXCERPT_CHARS)
    except (TypeError, ValueError):
        return _clip(str(inp), MAX_EXCERPT_CHARS)


def _diff_block(edit: dict) -> str:
    old = str(edit.get("old_string", ""))
    new = str(edit.get("new_string", ""))
    old_lines = "\n".join(f"- {ln}" for ln in old.splitlines()) or "- (leer)"
    new_lines = "\n".join(f"+ {ln}" for ln in new.splitlines()) or "+ (leer)"
    return f"{old_lines}\n{new_lines}"


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… [gekürzt, {len(text) - limit} weitere Zeichen]"
