"""Trust-Policy — die EINE zentrale Stelle, die den Freigabe-Trigger definiert (PROJ-4/PROJ-10).

PROJ-4 lieferte einen **fixen, konservativen** Trigger (Lesen → durch, Rest → Card).
PROJ-10 macht daraus eine **abgestufte, konfigurierbare** Richtlinie: pro Regel
``auto-allow`` / ``card`` / ``deny``, gematcht nach Tool-Klasse + Kontext
(Rolle/Skill/Projekt). Die Auswertung bleibt die einzige Quelle der Wahrheit — der
Rest des Codes ruft nur ``policy_store.evaluate(...)`` bzw. (rückwärtskompatibel)
``requires_card(...)``.

Außerdem destilliert dieses Modul aus dem rohen ``tool_input`` einen **knappen Ausschnitt**
(Befehl bzw. Diff) statt des Volltexts — das zahlt auf die Knappheits-Konstitution (PROJ-6)
und die Token-Disziplin ein.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass

import yaml

from ..config import settings

log = logging.getLogger(__name__)

# Bekannte, eindeutig lesende Tools von Claude Code → laufen ohne Card durch.
# Alles, was NICHT hier steht (Bash, Edit, Write, NotebookEdit, Task, unbekannt …),
# ist im konservativen Default genehmigungspflichtig (im Zweifel fragen).
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

# Die drei Vertrauensstufen (PROJ-10).
AUTO_ALLOW, CARD, DENY = "auto-allow", "card", "deny"
_LEVELS: frozenset[str] = frozenset({AUTO_ALLOW, CARD, DENY})

# Obergrenze für den Card-Ausschnitt (Zeichen) — nie das ganze Log in die Card.
MAX_EXCERPT_CHARS: int = 4_000
# Obergrenze für die „Warum"-Begründung (Denk-Blöcke können lang sein).
MAX_RATIONALE_CHARS: int = 800


def clip_rationale(text: str) -> str:
    """Kürzt die „Warum"-Begründung auf eine card-taugliche Länge (Token-Disziplin)."""
    return _clip(text or "", MAX_RATIONALE_CHARS)


def requires_card(tool_name: str, tool_input: dict | None = None) -> bool:
    """Konservativer Default-Trigger: alles außer Lese-Tools → Card.

    Bleibt als Hilfsfunktion erhalten (Default-Stufe + Rückwärtskompatibilität);
    die abgestufte Entscheidung trifft ``PolicyStore.evaluate``.
    """
    return tool_name not in AUTO_ALLOW_TOOLS


def default_level(tool_name: str) -> str:
    """Konservative Default-Stufe ohne passende Regel: Lesen → auto, sonst Card.

    Deckt den Edge-Case ‚unbekannte Tool-Klasse' ab — nie versehentlich auto-allow.
    """
    return AUTO_ALLOW if tool_name in AUTO_ALLOW_TOOLS else CARD


# --- PROJ-10: abgestufter, konfigurierbarer Evaluator ----------------------


@dataclass(frozen=True)
class PolicyDecision:
    """Ergebnis einer Auswertung: Stufe + menschenlesbare Begründung (auslösende Regel)."""

    level: str          # auto-allow | card | deny
    rule: str           # Klartext, der in die Card wandert (Nachvollziehbarkeit, AC)
    reason: str = ""    # optionaler Grund (v. a. bei deny → Ablehnungs-Notiz)


@dataclass
class _Rule:
    tool: str | None
    role: str | None
    skill: str | None
    project: str | None
    level: str
    reason: str | None = None

    @property
    def specificity(self) -> int:
        """Wie viele Match-Felder gesetzt sind — spezifischer schlägt allgemeiner."""
        return sum(1 for v in (self.tool, self.role, self.skill, self.project) if v)

    def matches(self, tool: str, role: str | None, skill: str | None, project: str | None) -> bool:
        """Match nur, wenn jedes GESETZTE Feld dem Kontext entspricht (leer = beliebig)."""
        if self.tool and self.tool != tool:
            return False
        if self.role and self.role != role:
            return False
        if self.skill and self.skill != skill:
            return False
        if self.project and self.project not in (project or ""):
            # Projekt-Match per Teilstring: erlaubt sowohl Label als auch Pfadsegment.
            return False
        return True

    def describe(self, default_part: str) -> str:
        parts = []
        if self.tool:
            parts.append(self.tool)
        for label, value in (("rolle", self.role), ("skill", self.skill), ("projekt", self.project)):
            if value:
                parts.append(f"{label}={value}")
        scope = " @ ".join([parts[0], ", ".join(parts[1:])]) if len(parts) > 1 else (parts[0] if parts else default_part)
        return f"{self.level} · {scope}"


# Phasen-Gate-Default: AN, jeder Phasenwechsel (leere transitions-Liste).
_DEFAULT_PHASE_GATE: dict = {"enabled": True, "transitions": []}


class PolicyStore:
    """Liest die Trust-Policy aus einer YAML-Datei — **live**, mtime-gecacht.

    - Fehlt die Datei → konservativer Default (Lesen auto, Rest Card), Quelle ``default``.
    - Defekte/ungültige Datei → Default + sichtbare Warnung, **kein Crash** (Edge-Case).
    - Auswertung pro Tool-Call ist in-process & O(Regelzahl) → < 5 ms.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._mtime: float | None = None
        self._rules: list[_Rule] = []
        self._phase_gate: dict = dict(_DEFAULT_PHASE_GATE)
        self._source: str = "default"
        self._warning: str | None = None
        self._loaded_once = False

    # --- Laden / Live-Reload ------------------------------------------

    def _reload_if_changed(self) -> None:
        try:
            mtime = os.path.getmtime(self._path)
        except OSError:
            # Keine Datei → konservativer Default (rückwärtskompatibel zu PROJ-4).
            if self._source != "default" or not self._loaded_once:
                self._rules = []
                self._phase_gate = dict(_DEFAULT_PHASE_GATE)
                self._source = "default"
                self._warning = None
                self._mtime = None
                self._loaded_once = True
            return
        if self._loaded_once and mtime == self._mtime:
            return
        self._parse_file(mtime)

    def _parse_file(self, mtime: float) -> None:
        self._loaded_once = True
        self._mtime = mtime
        try:
            with open(self._path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh) or {}
            if not isinstance(data, dict):
                raise ValueError("Policy-Datei muss ein Objekt sein.")
            self._rules = [self._parse_rule(r) for r in (data.get("rules") or [])]
            self._phase_gate = self._parse_phase_gate(data.get("phase_gate"))
            self._source = self._path
            self._warning = None
        except (OSError, ValueError, yaml.YAMLError) as exc:
            # Edge-Case ‚Policy-Datei kaputt/ungültig' → Fallback + Warnung, kein Crash.
            log.warning("Trust-Policy %s ungültig: %s — Fallback auf Default.", self._path, exc)
            self._rules = []
            self._phase_gate = dict(_DEFAULT_PHASE_GATE)
            self._source = "default"
            self._warning = f"Policy-Datei ungültig ({exc})"

    @staticmethod
    def _parse_rule(raw: dict) -> _Rule:
        if not isinstance(raw, dict):
            raise ValueError(f"Regel muss ein Objekt sein, war {type(raw).__name__}.")
        level = str(raw.get("level", "")).strip()
        if level not in _LEVELS:
            raise ValueError(f"Ungültige Stufe '{level}' (erlaubt: {sorted(_LEVELS)}).")

        def _opt(key: str) -> str | None:
            v = raw.get(key)
            v = str(v).strip() if v not in (None, "") else None
            return v

        return _Rule(
            tool=_opt("tool"), role=_opt("role"), skill=_opt("skill"),
            project=_opt("project"), level=level, reason=_opt("reason"),
        )

    @staticmethod
    def _parse_phase_gate(raw: object) -> dict:
        if raw is None:
            return dict(_DEFAULT_PHASE_GATE)
        if not isinstance(raw, dict):
            raise ValueError("phase_gate muss ein Objekt sein.")
        transitions = raw.get("transitions") or []
        if not isinstance(transitions, list):
            raise ValueError("phase_gate.transitions muss eine Liste sein.")
        return {
            "enabled": bool(raw.get("enabled", True)),
            "transitions": [str(t).strip() for t in transitions if str(t).strip()],
        }

    # --- Öffentliche API ----------------------------------------------

    def evaluate(
        self,
        tool_name: str,
        *,
        role: str | None = None,
        skill: str | None = None,
        project: str | None = None,
    ) -> PolicyDecision:
        """Welche Stufe greift für diesen Tool-Aufruf im gegebenen Kontext?

        Spezifischere Regel schlägt allgemeinere; bei gleicher Spezifität gewinnt die
        restriktivere Stufe (``deny`` > ``card`` > ``auto-allow``) — Konflikt wird geloggt.
        Ohne passende Regel: konservativer Default (Lesen auto, sonst Card).
        """
        self._reload_if_changed()
        matched = [r for r in self._rules if r.matches(tool_name, role, skill, project)]
        if not matched:
            lvl = default_level(tool_name)
            return PolicyDecision(level=lvl, rule=f"Default ({'Lesen' if lvl == AUTO_ALLOW else 'Schreiben/Shell'})")

        best = _pick_winner(matched)
        return PolicyDecision(level=best.level, rule=best.describe("alle"), reason=best.reason or "")

    def phase_gate(self) -> dict:
        """Aktuelle Phasen-Gate-Config ({enabled, transitions})."""
        self._reload_if_changed()
        return dict(self._phase_gate)

    def snapshot(self) -> dict:
        """Voller Lese-Snapshot für die Settings-API (GET /settings/policy)."""
        self._reload_if_changed()
        return {
            "rules": [
                {
                    "match": {"tool": r.tool, "role": r.role, "skill": r.skill, "project": r.project},
                    "level": r.level,
                    "reason": r.reason,
                }
                for r in self._rules
            ],
            "phase_gate": dict(self._phase_gate),
            "source": self._source,
            "warning": self._warning,
        }

    def save(self, rules: list[dict], phase_gate: dict) -> dict:
        """Policy validieren + nach YAML schreiben → wird beim nächsten ``evaluate`` live aktiv.

        Wirft ``ValueError`` bei ungültiger Stufe/Struktur (Route → HTTP 400).
        """
        parsed_rules = [self._parse_rule(_rule_from_api(r)) for r in rules]
        parsed_gate = self._parse_phase_gate(phase_gate)
        payload = {
            "rules": [
                {k: v for k, v in (
                    ("tool", r.tool), ("role", r.role), ("skill", r.skill),
                    ("project", r.project), ("level", r.level), ("reason", r.reason),
                ) if v is not None}
                for r in parsed_rules
            ],
            "phase_gate": parsed_gate,
        }
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        with open(self._path, "w", encoding="utf-8") as fh:
            yaml.safe_dump(payload, fh, allow_unicode=True, sort_keys=False)
        self._loaded_once = False  # nächster Zugriff lädt frisch (Live-Reload).
        return self.snapshot()


def _pick_winner(rules: list[_Rule]) -> _Rule:
    """Höchste Spezifität gewinnt; bei Gleichstand die restriktivere Stufe (deny>card>auto)."""
    order = {DENY: 2, CARD: 1, AUTO_ALLOW: 0}
    best = max(rules, key=lambda r: (r.specificity, order[r.level]))
    # Konflikt (gleiche Spezifität, andere Stufe) sichtbar machen.
    rivals = [r for r in rules if r.specificity == best.specificity and r.level != best.level]
    if rivals:
        log.info("Policy-Konflikt bei Spezifität %d → restriktivste Stufe '%s' gewinnt.",
                 best.specificity, best.level)
    return best


def _rule_from_api(r: dict) -> dict:
    """Mappt das Frontend-Format ({match:{...}, level, reason}) auf das flache YAML-Schema."""
    match = r.get("match") or {}
    return {
        "tool": match.get("tool"),
        "role": match.get("role"),
        "skill": match.get("skill"),
        "project": match.get("project"),
        "level": r.get("level"),
        "reason": r.get("reason"),
    }


# Modul-Singleton — eine Policy pro Backend-Prozess (live aus der Datei).
policy_store = PolicyStore(settings.policy_config_path)


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
