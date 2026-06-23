"""Kanonische ABC-Workflow-Phasen + Skill→Phase-Detektor (PROJ-8).

Die EINE Quelle der Wahrheit für die Phasen-Reihenfolge im Backend. Das Frontend
spiegelt dieselbe Reihenfolge in ``lib/status.ts`` (``ABC_PHASES``). Der Phasen-
Detektor wird im Freigabe-Hook (``SessionRuntime.request_decision``) als reiner
Seiteneffekt eingehängt: aus einem ``Skill``-Tool-Aufruf mit ``abc-``-Präfix wird
die aktuelle Phase + Feature-Referenz einer Session abgeleitet.
"""
from __future__ import annotations

import re

# Kanonische Reihenfolge der ABC-Phasen (links → rechts im Gantt).
ABC_PHASES: tuple[str, ...] = (
    "brainstorm",
    "requirements",
    "architecture",
    "frontend",
    "backend",
    "qa",
    "deploy",
    "document",
)

# Index je Phase für „weiteste erreichte Phase"-Vergleiche (max entlang der Reihenfolge).
_PHASE_INDEX: dict[str, int] = {p: i for i, p in enumerate(ABC_PHASES)}

# abc-Skill-Name → Phase. NUR Workflow-Skills, die eine Phase markieren.
# Nicht gelistete abc-Skills (abc-refactor, abc-challenge, abc-clarification,
# abc-fullstack, abc-dokploy-data, /codegraph …) ändern die Phase NICHT.
SKILL_TO_PHASE: dict[str, str] = {
    "abc-brainstorm": "brainstorm",
    "abc-requirements": "requirements",
    "abc-architecture": "architecture",
    "abc-frontend": "frontend",
    "abc-backend": "backend",
    "abc-qa": "qa",
    "abc-qa-e2e": "qa",
    "abc-deploy": "deploy",
    "abc-document": "document",
}

# Feature-Referenz aus einem abc-Skill-Argument bzw. einem features/PROJ-X-*.md-Pfad.
_PROJ_RE = re.compile(r"PROJ-(\d+)", re.IGNORECASE)
_NUM_RE = re.compile(r"\d{1,4}")

# --- Smart Launcher (PROJ-9) -----------------------------------------------
# Kanonischer Workflow-Skill je Phase (Umkehrung von SKILL_TO_PHASE). qa → abc-qa
# (nicht abc-qa-e2e); pro Phase genau ein vorgeschlagener Skill.
PHASE_TO_SKILL: dict[str, str] = {p: f"abc-{p}" for p in ABC_PHASES}

# Empfohlenes Modell je Phase (überschreibbar). Denk-/Design-Phasen → Opus
# (Qualität), Bau/QA → Sonnet (Balance), mechanische Phasen → Haiku (günstig).
PHASE_TO_MODEL: dict[str, str] = {
    "brainstorm": "opus",
    "requirements": "opus",
    "architecture": "opus",
    "frontend": "sonnet",
    "backend": "sonnet",
    "qa": "sonnet",
    "deploy": "haiku",
    "document": "haiku",
}

# INDEX.md-Status spiegelt die ZULETZT abgeschlossene Stufe → nächste sinnvolle
# abc-Phase. „Deployed" → None (fertig). Status-Werte case-/whitespace-normalisiert.
STATUS_TO_NEXT_PHASE: dict[str, str | None] = {
    "planned": "architecture",
    "architected": "frontend",
    "in progress": "backend",
    "in review": "qa",
    "approved": "deploy",
    "deployed": None,
}

# Reifegrad-Reihenfolge der INDEX-Status (klein = unreif). Für die Auswahl des
# „nächsten" Features bei mehreren offenen: kleinster Reifegrad zuerst.
STATUS_ORDER: tuple[str, ...] = (
    "planned", "architected", "in progress", "in review", "approved", "deployed",
)
_STATUS_INDEX: dict[str, int] = {s: i for i, s in enumerate(STATUS_ORDER)}


def normalize_status(status: str | None) -> str:
    """Normalisiert einen INDEX-Status (lowercase, Whitespace kollabiert)."""
    if not status:
        return ""
    return " ".join(status.strip().lower().split())


def status_maturity(status: str | None) -> int | None:
    """Reifegrad-Index eines Status entlang ``STATUS_ORDER``, oder ``None`` (unbekannt)."""
    return _STATUS_INDEX.get(normalize_status(status))


# „Fortsetzen-First"-Rang (PROJ-9 / BUG-1): angefangene Dev-Arbeit zuerst, reifster
# OFFENER Stand oben (In Review → In Progress → Architected → Planned). ``Approved``
# wird ans Ende gestellt — dessen einzige offene Stufe ist der human-gated Deploy, den
# der Launcher nicht als Top-Vorschlag drängen soll (bleibt aber als Alternative
# wählbar). ``Deployed`` kommt hier nie vor (vorab herausgefiltert). Kleiner Rang =
# höhere Empfehlung; unbekannt → ans Ende.
_SELECTION_RANK: dict[str, int] = {
    "in review": 0,
    "in progress": 1,
    "architected": 2,
    "planned": 3,
    "approved": 4,
}


def selection_rank(status: str | None) -> int:
    """Sortier-Rang für die „Fortsetzen-First"-Auswahl (kleiner = höher empfohlen)."""
    return _SELECTION_RANK.get(normalize_status(status), 99)


def next_phase_for_status(status: str | None) -> str | None:
    """Nächste abc-Phase für einen INDEX-Status (None bei deployed/unbekannt)."""
    return STATUS_TO_NEXT_PHASE.get(normalize_status(status))


def skill_for_phase(phase: str | None) -> str | None:
    """Vorgeschlagener abc-Skill für eine Phase (None bei None/unbekannt)."""
    return PHASE_TO_SKILL.get(phase) if phase else None


def model_for_phase(phase: str | None) -> str | None:
    """Empfohlenes Modell für eine Phase (None bei None/unbekannt)."""
    return PHASE_TO_MODEL.get(phase) if phase else None


def phase_for_skill(skill: str | None) -> str | None:
    """Phase für einen abc-Skill-Namen, oder ``None`` für Nicht-Phasen-Skills."""
    if not skill:
        return None
    return SKILL_TO_PHASE.get(skill.strip())


def max_phase(a: str | None, b: str | None) -> str | None:
    """Die ‚weiteste' der beiden Phasen entlang der kanonischen Reihenfolge.

    Deckt nicht-lineare Sprünge ab (Edge-Case ‚Deploy vor Document', Frontend↔Backend-
    Wechsel): die Bar-Füllung (``abc_phase_reached``) wächst monoton und springt nie
    zurück. Unbekannte/``None``-Phasen werden ignoriert.
    """
    ia = _PHASE_INDEX.get(a) if a else None
    ib = _PHASE_INDEX.get(b) if b else None
    if ia is None:
        return b if ib is not None else None
    if ib is None:
        return a
    return a if ia >= ib else b


def feature_from_args(args: object | None) -> str | None:
    """Feature-Nummer aus dem abc-Skill-Argument (``/abc-backend 8`` → ``"8"``).

    Erkennt ``PROJ-8`` ebenso wie eine nackte Zahl; normalisiert auf die reine Nummer
    als String. Kein erkennbares Feature → ``None``.
    """
    if args is None:
        return None
    s = str(args)
    m = _PROJ_RE.search(s)
    if m:
        return m.group(1)
    m = _NUM_RE.search(s)
    return m.group(0) if m else None


def feature_from_path(path: object | None) -> str | None:
    """Feature-Nummer aus einem berührten ``features/PROJ-X-*.md``-Pfad (Fallback)."""
    if not path:
        return None
    m = _PROJ_RE.search(str(path))
    return m.group(1) if m else None


def detect_phase_signal(
    tool_name: str,
    tool_input: dict | None,
    *,
    phase: str | None,
    reached: str | None,
    feature: str | None,
) -> tuple[str | None, str | None, str | None]:
    """Leitet aus einem Tool-Aufruf das aktualisierte ABC-Tripel ab (seiteneffektfrei).

    - ``Skill``-Aufruf mit abc-Workflow-Skill → setzt die AKTUELLE Phase, hebt
      ``reached`` monoton an und liest die Feature-Referenz aus ``args``.
    - Write/Edit/MultiEdit auf ``features/PROJ-X-*.md`` → Fallback-Feature (zuletzt
      berührtes Spec-File).
    - Alles andere → Tripel unverändert.

    Gibt das (ggf. unveränderte) Tripel ``(phase, reached, feature)`` zurück.
    """
    inp = tool_input or {}
    if tool_name == "Skill":
        new_phase = phase_for_skill(str(inp.get("skill", "")))
        if new_phase is not None:
            phase = new_phase
            reached = max_phase(reached, new_phase)
            feat = feature_from_args(inp.get("args"))
            if feat is not None:
                feature = feat
        return phase, reached, feature
    if tool_name in ("Write", "Edit", "MultiEdit"):
        feat = feature_from_path(inp.get("file_path"))
        if feat is not None:
            feature = feat
    return phase, reached, feature
