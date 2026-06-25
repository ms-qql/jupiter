"""LauncherService — Smart-Launcher-Vorschlag aus features/INDEX.md (PROJ-9).

Liest die Feature-Tabelle der ``features/INDEX.md`` eines Projekts (read-only),
bestimmt das nächste sinnvolle Feature + die nächste abc-Phase und leitet daraus
Skill, Modell und einen Start-Prompt ab. Kein DB-State; reiner File-Parse (<300 ms).

Die Phasen-/Skill-/Modell-Logik stammt aus ``abc_phases`` — dieselbe Quelle der
Wahrheit wie der Gantt (PROJ-8), damit Vorschlag und Fortschritt konsistent sind.
Pfad-Scope identisch zu ``validate_project_path`` (kein neuer Datei-Angriffsweg).
"""
from __future__ import annotations

import os
import re

from . import abc_phases
from .manager import validate_project_path

_PROJ_RE = re.compile(r"PROJ-(\d+)", re.IGNORECASE)
_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_PRIO_RE = re.compile(r"\bP(\d+)\b", re.IGNORECASE)


def _strip_links(text: str) -> str:
    """Markdown-Link ``[Label](url)`` → ``Label`` (Titel-Spalte mancher Projekte ist verlinkt)."""
    return _LINK_RE.sub(r"\1", text).strip()


def _split_row(line: str) -> list[str]:
    """Zerlegt eine Markdown-Tabellenzeile in getrimmte Zellen (ohne Rand-Pipes)."""
    s = line.strip()
    if s.startswith("|"):
        s = s[1:]
    if s.endswith("|"):
        s = s[:-1]
    return [c.strip() for c in s.split("|")]


def _is_separator(line: str) -> bool:
    """Trennzeile einer Markdown-Tabelle (``|---|:--:|`` …)."""
    s = line.strip()
    return bool(s) and "-" in s and set(s) <= set("|-: ")


def _find_col(header: list[str], keywords: tuple[str, ...]) -> int | None:
    """Index der ersten Header-Zelle, deren Name eines der Keywords enthält."""
    for idx, cell in enumerate(header):
        low = cell.strip().lower()
        if any(k in low for k in keywords):
            return idx
    return None


def parse_index_features(text: str) -> list[dict]:
    """Alle Feature-Zeilen aus den Markdown-Tabellen einer INDEX.md.

    Header-basiert (robust gegen unterschiedliche Spaltenreihenfolge): erkennt die
    Spalten ``Status``/``Feature``/``Prio`` per Überschrift. Eine Zeile zählt nur,
    wenn irgendwo eine ``PROJ-<n>``-Referenz steht (Roadmap-Listen ohne Tabelle
    werden ignoriert).
    """
    lines = text.splitlines()
    out: list[dict] = []
    n = len(lines)
    i = 0
    while i < n:
        line = lines[i]
        if "|" in line and i + 1 < n and _is_separator(lines[i + 1]):
            header = _split_row(line)
            status_idx = _find_col(header, ("status",))
            feat_idx = _find_col(header, ("feature", "name"))
            prio_idx = _find_col(header, ("prio", "priorität", "priority"))
            # PROJ-22: Abhängigkeits-Spalte (Topo-Sort des Koordinators). Nur die
            # ID-Zelle wird gelesen; die Feature-Spalte enthält selbst eine PROJ-ID
            # (Spec-Link) und darf nicht als Abhängigkeit fehlinterpretiert werden.
            dep_idx = _find_col(header, ("abhäng", "depend", "requires", "voraussetz"))
            j = i + 2
            while j < n and lines[j].strip().startswith("|"):
                cells = _split_row(lines[j])
                m = _PROJ_RE.search(lines[j])
                if m:
                    def _cell(idx: int | None) -> str:
                        return cells[idx] if idx is not None and idx < len(cells) else ""

                    pm = _PRIO_RE.search(_cell(prio_idx))
                    deps = [f"PROJ-{d}" for d in _PROJ_RE.findall(_cell(dep_idx))] if dep_idx is not None else []
                    out.append({
                        "id": f"PROJ-{m.group(1)}",
                        "number": m.group(1),
                        "title": _strip_links(_cell(feat_idx)),
                        "status": _cell(status_idx),
                        "prio": f"P{pm.group(1)}" if pm else "",
                        "dependencies": deps,
                        "order": len(out),
                    })
                j += 1
            i = j
        else:
            i += 1
    return out


def _prio_num(prio: str | None) -> int:
    """Prio-Zahl (P0 → 0); fehlend/unparsebar → 99 (niedrigste Priorität)."""
    m = _PRIO_RE.search(prio or "")
    return int(m.group(1)) if m else 99


def _feature_suggestion(f: dict) -> dict:
    """Feature-Zeile + daraus abgeleitete nächste Phase/Skill/Modell/Prompt."""
    phase = abc_phases.next_phase_for_status(f["status"])
    skill = abc_phases.skill_for_phase(phase)
    prompt = f"/{skill} {f['number']}" if skill else f"Arbeite an {f['id']}: {f['title']}".strip()
    return {
        "id": f["id"],
        "number": f["number"],
        "title": f["title"],
        "status": f["status"],
        "prio": f["prio"] or None,
        "phase": phase,
        "skill": skill,
        "modell": abc_phases.model_for_phase(phase),
        "initial_prompt": prompt,
    }


def _empty(project_path: str, hinweis: str | None) -> dict:
    """Basis-Vorschlag ohne abc-Erkennung (Freitext-Fallback)."""
    return {
        "project_path": project_path,
        "abc_erkannt": False,
        "hinweis": hinweis,
        "empfehlung": None,
        "alternativen": [],
        "naechste_phase": None,
        "skill": None,
        "modell": None,
        "initial_prompt": None,
    }


class LauncherService:
    """Leitet den Session-Start-Vorschlag aus der INDEX.md eines Projekts ab (PROJ-9)."""

    def suggest(self, project_path: str) -> dict:
        """Vorschlag für ``project_path``. ``ValueError`` bei Pfad außerhalb der Roots."""
        real = validate_project_path(project_path)  # ValueError → 400
        index_path = os.path.join(real, "features", "INDEX.md")
        if not os.path.isfile(index_path):
            return _empty(real, "Kein abc-Workflow erkannt (keine features/INDEX.md) — Freitext-Modus.")
        try:
            with open(index_path, encoding="utf-8") as fh:
                text = fh.read()
        except OSError:
            return _empty(real, "features/INDEX.md nicht lesbar — Freitext-Modus.")

        features = parse_index_features(text)
        recognized = [f for f in features if abc_phases.status_maturity(f["status"]) is not None]
        if not recognized:
            return _empty(real, "Kein abc-Workflow erkannt (INDEX.md ohne lesbare Status) — Freitext-Modus.")

        open_feats = [
            f for f in recognized if abc_phases.normalize_status(f["status"]) != "deployed"
        ]
        if not open_feats:
            # Alle erkannten Features sind deployed → neues Feature vorschlagen.
            sug = _empty(real, "Alle Features sind deployed — neues Feature mit /abc-requirements anlegen?")
            sug.update({
                "abc_erkannt": True,
                "naechste_phase": "requirements",
                "skill": "abc-requirements",
                "modell": abc_phases.model_for_phase("requirements"),
                "initial_prompt": "/abc-requirements ",
            })
            return sug

        # „Fortsetzen-First" (BUG-1): angefangene Dev-Arbeit zuerst — reifster offener
        # Stand oben (In Review → … → Planned, Approved ans Ende). Bei Gleichstand
        # höhere Prio (kleinere Zahl), dann Dokument-Reihenfolge (erste Tabellenzeile).
        open_feats.sort(key=lambda f: (
            abc_phases.selection_rank(f["status"]),
            _prio_num(f["prio"]),
            f["order"],
        ))
        options = [_feature_suggestion(f) for f in open_feats]
        primary = options[0]

        sug = _empty(real, None)
        sug.update({
            "abc_erkannt": True,
            "empfehlung": primary,
            "alternativen": options[1:],
            "naechste_phase": primary["phase"],
            "skill": primary["skill"],
            "modell": primary["modell"],
            "initial_prompt": primary["initial_prompt"],
        })
        return sug
