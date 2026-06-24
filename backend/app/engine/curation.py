"""Kuratierung — ereignisgetriebene Erkennung von Wissens-Markern (PROJ-15).

Reine Funktionen (testbar wie ``policy.py``): scannt den Assistenten-/Denk-Strom
einer Session auf **Kuratierungs-Marker** (Bug gelöst, ADR/Entscheidung, Sackgasse)
und destilliert daraus einen knappen Wissens-Vorschlag (Pointer/Ausschnitt statt
Volltext — Token-Disziplin, PROJ-6). Schreiben/Card-Lifecycle liegen im ``manager``,
das Persistieren im ``VaultService`` (``write_curated_note``).

MVP bewusst einfach: konservative Schlüsselwort-/Phrasen-Heuristik. Ein semantischer
Klassifikator ist explizit RAG-Ausbau (PROJ-19) und hier Non-Goal.
"""
from __future__ import annotations

from dataclasses import dataclass

# Maximale Länge des Kontext-Auszugs im Vorschlag (kein Volltext).
_SNIPPET_CHARS = 1_200


@dataclass(frozen=True)
class Marker:
    kind: str       # "bug_geloest" | "adr" | "sackgasse"
    label: str      # deutsche Anzeige (Card-Titel)
    keyword: str    # die konkret getroffene Phrase (Nachvollziehbarkeit)


# Reihenfolge = Priorität bei Mehrfachtreffern in einem Text.
_MARKER_DEFS: list[tuple[str, str, list[str]]] = [
    (
        "bug_geloest",
        "Bug gelöst",
        [
            "bug behoben", "bug gelöst", "bug gefixt", "fehler behoben", "fehler gelöst",
            "problem behoben", "problem gelöst", "ursache gefunden", "root cause",
            "bug fixed", "fixed the bug", "tests sind grün", "tests grün", "jetzt grün",
        ],
    ),
    (
        "adr",
        "Architektur-Entscheidung",
        [
            "architektur-entscheidung", "architekturentscheidung", "design-entscheidung",
            "entscheidung getroffen", "wir entscheiden uns", "wir haben uns entschieden",
            "entschieden:", "adr:", " adr ", "wir setzen auf", "trade-off",
        ],
    ),
    (
        "sackgasse",
        "Sackgasse / verworfener Ansatz",
        [
            "sackgasse", "dead end", "dead-end", "ansatz verworfen", "verworfen",
            "führt nicht zum ziel", "funktioniert nicht wie gedacht", "fehlgeschlagener ansatz",
            "war ein irrweg", "irrweg", "kommt nicht in frage",
        ],
    ),
]


def detect_marker(text: str | None) -> Marker | None:
    """Erster passender Kuratierungs-Marker im Text (case-insensitiv) oder ``None``."""
    low = (text or "").lower()
    if not low:
        return None
    for kind, label, keywords in _MARKER_DEFS:
        for kw in keywords:
            if kw in low:
                return Marker(kind=kind, label=label, keyword=kw.strip())
    return None


def proposal_title(marker: Marker, project_name: str | None) -> str:
    """Themen-Titel = Dedup-Basis (gleicher Titel ⇒ gleiche Knowledge-Notiz, Append)."""
    project = (project_name or "Allgemein").strip() or "Allgemein"
    return f"{marker.label} — {project}"


def build_proposal(
    marker: Marker, source_text: str, *, project_name: str | None, session_id: str
) -> tuple[str, str]:
    """Erzeugt ``(title, body)`` des Wissens-Vorschlags — knapp, mit Quell-Pointer.

    Der Body ist ein editierbares Gerüst (der Nutzer kuratiert vor der Freigabe).
    Statt des Volltexts nur ein gekappter Auszug + Backlink-Hinweis aufs Roh-Log.
    """
    title = proposal_title(marker, project_name)
    snippet = _clip((source_text or "").strip(), _SNIPPET_CHARS)
    body = (
        f"> Kuratiert aus Session `{session_id[:8]}` "
        f"({(project_name or 'Allgemein').strip() or 'Allgemein'}). "
        f"Auslöser: **{marker.label}** (Marker „{marker.keyword}“).\n\n"
        f"## Kontext (Auszug)\n\n{snippet}\n\n"
        f"## Erkenntnis\n\n_Bitte ergänzen/kuratieren._\n\n"
        f"---\n"
        f"_Quelle: rohes Session-Log unter `Agentic OS/Jupiter/Sessions/` "
        f"(nach Session-Ende verfügbar)._\n"
    )
    return title, body


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n… [gekürzt, {len(text) - limit} weitere Zeichen]"
