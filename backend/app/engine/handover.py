"""Handover-Generator (PROJ-5) — verdichteter Staffelstab statt Volltext.

Baut ein strukturiertes Übergabe-MD aus dem In-Memory-Zustand einer Session:
**Wo stehen wir? / Erledigt / Offen / Fallstricke / Pointer**. Pointer (Datei-/
Vault-Zeiger) statt Volltext hält das Dokument klein — direkte Vorarbeit für RAG (#23).

Hybrid (Tech-Design PROJ-5): das mechanische Gerüst hier ist der garantierte,
deterministische Pfad. Eine optionale LLM-Anreicherung (``enrichment``) kann die
Prosa-Felder (Wo/Erledigt/Offen/Fallstricke) verfeinern; fällt sie aus oder ist sie
abgeschaltet, bleibt das Gerüst ein vollständig gültiger Handover.
"""
from __future__ import annotations

import os

from ..config import settings

# Maschinen-Status → deutsches Label für „Wo stehen wir?".
_STATUS_LABEL = {
    "starting": "startet",
    "running": "arbeitet",
    "waiting": "wartet auf Eingabe",
    "awaiting_approval": "wartet auf Freigabe",
    "done": "abgeschlossen",
    "error": "Fehler",
}

# Pointer/Prosa-Ausschnitte begrenzen — der Handover bleibt ein Staffelstab.
_EXCERPT_CHARS = 600
_MAX_USER_TURNS = 8


def _clip(text: str, limit: int = _EXCERPT_CHARS) -> str:
    text = (text or "").strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " … (gekürzt)"


def build_title(state) -> str:
    """Lesbarer Titel → Dateiname-Slug im Vault."""
    project = os.path.basename(state.project_path.rstrip("/")) or "session"
    return f"handover-{project}-{state.session_id[:8]}"


def build_handover_md(
    state,
    transcript,
    pending,
    *,
    enrichment: dict | None = None,
    session_log_pointer: str | None = None,
) -> str:
    """Erzeugt den Handover-Body (ohne Frontmatter — das ergänzt der Vault-Write).

    ``enrichment`` darf die Prosa-Felder ``wo``/``erledigt``/``offen``/``fallstricke``
    überschreiben; fehlende Felder fallen aufs mechanische Gerüst zurück. ``pending``
    ist die Liste offener Decision Cards (PROJ-4).
    """
    enr = enrichment or {}

    last_assistant = ""
    for entry in reversed(transcript):
        if entry.role == "assistant" and entry.kind == "text" and entry.text.strip():
            last_assistant = entry.text.strip()
            break
    user_turns = [e.text.strip() for e in transcript if e.role == "user" and e.text.strip()]

    wo = enr.get("wo") or _wo_mechanical(state, last_assistant)
    erledigt = enr.get("erledigt") or _erledigt_mechanical(state, user_turns, last_assistant)
    offen = enr.get("offen") or _offen_mechanical(pending)
    fallstricke = enr.get("fallstricke") or _fallstricke_mechanical(state)
    pointer = _pointer_mechanical(state, session_log_pointer)  # immer Fakten → nie LLM

    project = os.path.basename(state.project_path.rstrip("/")) or "Session"
    parts = [
        f"# Handover — {project}",
        f"## Wo stehen wir?\n\n{wo}",
        f"## Erledigt\n\n{erledigt}",
        f"## Offen\n\n{offen}",
        f"## Fallstricke\n\n{fallstricke}",
        f"## Pointer\n\n{pointer}",
    ]
    return "\n\n".join(parts) + "\n"


def _wo_mechanical(state, last_assistant: str) -> str:
    status = _STATUS_LABEL.get(state.status, state.status)
    fill = f"{state.context_fill_pct:.1f}%" if state.context_known else "unbekannt"
    lines = [
        f"- Status: **{status}** · Modell `{state.model}` · {state.num_turns} Turns",
        f"- Kontext-Füllstand: {fill} · {state.tokens_used} Tokens",
    ]
    if last_assistant:
        lines.append(f"- Zuletzt: {_clip(last_assistant)}")
    return "\n".join(lines)


def _erledigt_mechanical(state, user_turns: list[str], last_assistant: str) -> str:
    if not user_turns:
        return "- (keine Nutzer-Eingaben protokolliert)"
    shown = user_turns[-_MAX_USER_TURNS:]
    head = ""
    if len(user_turns) > _MAX_USER_TURNS:
        head = f"_(letzte {_MAX_USER_TURNS} von {len(user_turns)} Aufträgen)_\n"
    bullets = "\n".join(f"- {_clip(t, 160)}" for t in shown)
    return f"{head}{bullets}"


def _offen_mechanical(pending) -> str:
    cards = list(pending)
    if not cards:
        return "- Keine offenen Freigaben."
    return "\n".join(f"- Freigabe ausstehend: {_clip(c.action, 160)}" for c in cards)


def _fallstricke_mechanical(state) -> str:
    notes = []
    if state.error:
        notes.append(f"- Letzter Fehler: {_clip(state.error, 200)}")
    if state.rate_limit:
        status = state.rate_limit.get("status") or "aktiv"
        notes.append(f"- Rate-Limit: {status}")
    if not state.context_known:
        notes.append("- Kontext-Daten vom Treiber fehlen noch (Füllstand unbekannt).")
    return "\n".join(notes) if notes else "- Keine bekannten Fallstricke."


def _pointer_mechanical(state, session_log_pointer: str | None) -> str:
    short_id = state.session_id[:8]
    sessions_dir = f"{settings.vault_jupiter_subdir}/Sessions"
    log = session_log_pointer or f"{sessions_dir}/ (Session {short_id}, nach Session-Ende)"
    return "\n".join(
        [
            f"- Projektpfad: `{state.project_path}`",
            f"- Vault-Session-Log: {log}",
            f"- Rolle/Konstitution: {state.role or '—'} ({state.constitution_source or 'global'})",
            f"- Volltext-Transkript bei Bedarf über die Session-Detailseite ({short_id}).",
        ]
    )
