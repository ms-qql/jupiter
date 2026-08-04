"""Live-Budget-Quellen für PROJ-52 (Iteration 2) — echte providerseitige Werte.

Iteration 1 zeigte nur manuell gepflegte bzw. geschätzte Werte. Hier werden die
tatsächlichen 5h-/Wochen-Verbräuche **nicht-interaktiv** abgefragt — auf drei
provider-spezifischen Wegen, weil sich die CLIs/APIs unterscheiden:

**Claude** — ``claude -p "/usage"`` liefert headless parsebaren Klartext, u. a.::

    You are currently using your subscription to power your Claude Code usage
    Current session: 22% used · resets Jun 28, 10:40am (UTC)
    Current week (all models): 45% used · resets Jul 1, 8pm (UTC)

→ ``Current session`` = 5h-Fenster, ``Current week (all models)`` = Wochenfenster.

**Codex** — ``/status`` ist KEIN ``codex exec``-Befehl (würde als Agent-Prompt laufen).
Die echten Limits stehen aber strukturiert in jeder Rollout-Datei
``~/.codex/sessions/<jjjj>/<mm>/<tt>/rollout-*.jsonl``; jeder Turn schreibt::

    "rate_limits":{"primary":{"used_percent":20.0,"window_minutes":300,"resets_at":...},
                   "secondary":{"used_percent":20.0,"window_minutes":10080,"resets_at":...}}

→ ``primary`` = 5h-Fenster (300 min), ``secondary`` = Woche (10080 min = 7 d).
Wird **read-only** gelesen; Rollouts bleiben durch Jupiters eigene Codex-Sessions frisch.

**OpenCode Go** — die offizielle API dokumentiert keinen Endpunkt für den aktuellen
Abo-Verbrauch. Jupiter berechnet die 5h-/Wochenwerte deshalb im Budget-Service aus
den von der OpenCode-CLI gemeldeten Turn-Kosten gegen die offiziellen Go-Limits.

Jede Probe liefert ``{"5h": LiveWindow, "week": LiveWindow}`` (Teilmenge erlaubt) oder
ein leeres Dict, wenn keine Live-Daten vorliegen. CLI-/Parser-Fehler werden geschluckt
(geloggt) und ergeben „keine Live-Daten" — nie einen Crash. Der ``ProviderBudgetService``
fällt dann sauber auf Schätzung/manuell/``n/v`` zurück.
"""
from __future__ import annotations

import asyncio
import glob
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ..config import settings

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveWindow:
    """Ein live abgefragter Fensterwert (Prozent + optionaler Reset-Zeitpunkt)."""

    used_pct: float
    reset_at: datetime | None
    source: str = "cli_live"


# --------------------------------------------------------------------------- Claude

# "Current session: 22% used · resets Jun 28, 10:40am (UTC)"
_CLAUDE_SESSION_RE = re.compile(
    r"current session:\s*([\d.]+)%\s*used.*?resets\s*(.+?)\s*$",
    re.IGNORECASE,
)
# "Current week (all models): 45% used · resets Jul 1, 8pm (UTC)"
_CLAUDE_WEEK_RE = re.compile(
    r"current week\s*\(all models\):\s*([\d.]+)%\s*used.*?resets\s*(.+?)\s*$",
    re.IGNORECASE,
)


def _parse_claude_reset(text: str, now: datetime) -> datetime | None:
    """„Jun 28, 10:40am (UTC)" / „Jul 1, 8pm (UTC)" → tz-aware UTC.

    Das Jahr fehlt im CLI-Output → aktuelles Jahr annehmen; liegt der Zeitpunkt deutlich
    in der Vergangenheit (Fenster bereits umgeschlagen), aufs nächste Jahr rollen.
    """
    s = text.strip().rstrip(".").replace("(UTC)", "").strip()
    s = re.sub(r"\s+", " ", s)
    for fmt in ("%b %d, %I:%M%p", "%b %d, %I%p"):
        try:
            dt = datetime.strptime(s, fmt).replace(year=now.year, tzinfo=timezone.utc)
        except ValueError:
            continue
        if dt < now - timedelta(days=2):
            dt = dt.replace(year=now.year + 1)
        return dt
    log.debug("Claude-Reset-String nicht parsebar: %r", text)
    return None


def parse_claude_usage(stdout: str, now: datetime) -> dict[str, LiveWindow]:
    """Parst die ``/usage``-Ausgabe in 5h-/Wochenfenster (reine Funktion, testbar)."""
    out: dict[str, LiveWindow] = {}
    for line in stdout.splitlines():
        line = line.strip()
        for key, pattern in (("5h", _CLAUDE_SESSION_RE), ("week", _CLAUDE_WEEK_RE)):
            if key in out:
                continue
            m = pattern.search(line)
            if m:
                try:
                    pct = float(m.group(1))
                except ValueError:
                    continue
                out[key] = LiveWindow(
                    used_pct=pct,
                    reset_at=_parse_claude_reset(m.group(2), now),
                    source="cli_live:claude_usage",
                )
    return out


class ClaudeUsageProbe:
    """Fragt das echte Claude-Kontingent über ``claude -p "/usage"`` ab."""

    def __init__(self, *, cfg=settings) -> None:
        self._cfg = cfg

    async def __call__(self, now: datetime) -> dict[str, LiveWindow]:
        if not getattr(self._cfg, "provider_budget_claude_cli_enabled", True):
            return {}
        argv = [self._cfg.claude_bin, "-p", "/usage"]
        timeout = max(1.0, float(self._cfg.provider_budget_timeout_seconds))
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except (OSError, ValueError) as exc:
            log.warning("Claude-/usage-Probe konnte nicht starten: %s", exc)
            return {}
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            log.warning("Claude-/usage-Probe Timeout nach %.0fs — verworfen.", timeout)
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            return {}
        if proc.returncode != 0:
            log.warning("Claude-/usage-Probe Exit %s — verworfen.", proc.returncode)
            return {}
        return parse_claude_usage(stdout.decode("utf-8", "replace"), now)


# ---------------------------------------------------------------------------- Codex

# Welcher rate_limits-Slot welches UI-Fenster ist (per Fensterlänge in Minuten robust).
_CODEX_WINDOW_BY_MINUTES = {300: "5h", 10080: "week"}
_CODEX_SLOT_FALLBACK = {"primary": "5h", "secondary": "week"}


def _find_rate_limits(obj: object) -> dict | None:
    """Sucht rekursiv das ``rate_limits``-Objekt mit ``primary``/``secondary``."""
    if isinstance(obj, dict):
        rl = obj.get("rate_limits")
        if isinstance(rl, dict) and ("primary" in rl or "secondary" in rl):
            return rl
        for value in obj.values():
            found = _find_rate_limits(value)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_rate_limits(item)
            if found is not None:
                return found
    return None


def parse_codex_rate_limits(rate_limits: dict, now: datetime) -> dict[str, LiveWindow]:
    """``rate_limits``-Objekt → 5h-/Wochenfenster (reine Funktion, testbar)."""
    out: dict[str, LiveWindow] = {}
    for slot, fallback_key in _CODEX_SLOT_FALLBACK.items():
        data = rate_limits.get(slot)
        if not isinstance(data, dict):
            continue
        pct = data.get("used_percent")
        if pct is None:
            continue
        try:
            pct = float(pct)
        except (TypeError, ValueError):
            continue
        minutes = data.get("window_minutes")
        key = _CODEX_WINDOW_BY_MINUTES.get(int(minutes)) if isinstance(minutes, (int, float)) else None
        key = key or fallback_key
        reset_at = None
        epoch = data.get("resets_at")
        if isinstance(epoch, (int, float)):
            try:
                reset_at = datetime.fromtimestamp(epoch, tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                reset_at = None
        out[key] = LiveWindow(used_pct=pct, reset_at=reset_at, source="cli_live:codex_session")
    return out


def latest_rollout_file(sessions_dir: str) -> str | None:
    """Jüngste ``rollout-*.jsonl`` unterhalb des Codex-Session-Ordners (nach mtime)."""
    pattern = os.path.join(sessions_dir, "**", "rollout-*.jsonl")
    files = glob.glob(pattern, recursive=True)
    if not files:
        return None
    try:
        return max(files, key=os.path.getmtime)
    except OSError:
        return None


def read_codex_rate_limits(path: str) -> dict | None:
    """Liest die Datei und liefert das **letzte** ``rate_limits``-Event (oder None)."""
    last: dict | None = None
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if '"rate_limits"' not in line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rl = _find_rate_limits(obj)
                if rl is not None:
                    last = rl
    except OSError as exc:
        log.warning("Codex-Rollout %s nicht lesbar: %s", path, exc)
        return None
    return last


class CodexRolloutProbe:
    """Liest die echten Codex-Limits read-only aus der jüngsten Rollout-Datei."""

    def __init__(self, *, cfg=settings) -> None:
        self._cfg = cfg

    async def __call__(self, now: datetime) -> dict[str, LiveWindow]:
        if not getattr(self._cfg, "provider_budget_codex_rollout_enabled", True):
            return {}
        sessions_dir = self._cfg.codex_sessions_dir
        # Dateizugriff im Threadpool, damit der Event-Loop nicht blockiert.
        return await asyncio.to_thread(self._read, sessions_dir, now)

    @staticmethod
    def _read(sessions_dir: str, now: datetime) -> dict[str, LiveWindow]:
        path = latest_rollout_file(sessions_dir)
        if path is None:
            return {}
        rate_limits = read_codex_rate_limits(path)
        if not rate_limits:
            return {}
        return parse_codex_rate_limits(rate_limits, now)


# ------------------------------------------------------------------------ OpenCode

# "AI_APICallError: Weekly usage limit reached. Resets in 2 days. To continue ..."
_OPENCODE_LIMIT_RE = re.compile(
    r"usage limit reached\.\s*resets in\s*([\d.]+)\s*(day|days|hour|hours|minute|minutes)",
    re.IGNORECASE,
)
_OPENCODE_TS_RE = re.compile(r"^timestamp=(\S+)")


def _opencode_reset_delta(amount: float, unit: str) -> timedelta:
    unit = unit.lower()
    if unit.startswith("day"):
        return timedelta(days=amount)
    if unit.startswith("hour"):
        return timedelta(hours=amount)
    return timedelta(minutes=amount)


def parse_opencode_log_limit(lines: list[str]) -> LiveWindow | None:
    """Letzte „usage limit reached"-Zeile im OpenCode-Log → Live-Fenster.

    ponytail: OpenCode meldet bislang ausschließlich das Wochenlimit (kein 5h-Fenster
    beobachtet) → hart auf ``week`` gemappt. Taucht künftig ein Scope-Wort wie „Daily"/
    „Hourly" im Fehlertext auf, hier um ein 5h-Mapping erweitern.
    """
    for line in reversed(lines):
        m = _OPENCODE_LIMIT_RE.search(line)
        if not m:
            continue
        ts_m = _OPENCODE_TS_RE.match(line)
        if not ts_m:
            continue
        try:
            event_time = datetime.fromisoformat(ts_m.group(1).replace("Z", "+00:00"))
        except ValueError:
            continue
        delta = _opencode_reset_delta(float(m.group(1)), m.group(2))
        return LiveWindow(
            used_pct=100.0,
            reset_at=event_time + delta,
            source="cli_live:opencode_log",
        )
    return None


class OpenCodeLogProbe:
    """Liest read-only die letzte Kontingent-Fehlerzeile aus dem lokalen OpenCode-Log.

    OpenCode Go hat keinen API-Endpunkt für den aktuellen Abo-Stand — die einzige
    verlässliche Live-Quelle ist der Fehlertext, den die CLI beim Erreichen des
    Limits selbst loggt (inkl. Reset-Countdown).
    """

    def __init__(self, *, cfg=settings) -> None:
        self._cfg = cfg

    async def __call__(self, now: datetime) -> dict[str, LiveWindow]:
        if not getattr(self._cfg, "provider_budget_opencode_log_enabled", True):
            return {}
        path = self._cfg.opencode_log_path
        return await asyncio.to_thread(self._read, path, now)

    @staticmethod
    def _read(path: str, now: datetime) -> dict[str, LiveWindow]:
        try:
            with open(path, encoding="utf-8") as fh:
                lines = fh.readlines()
        except OSError as exc:
            log.warning("OpenCode-Log %s nicht lesbar: %s", path, exc)
            return {}
        window = parse_opencode_log_limit(lines[-2000:])
        if window is None:
            return {}
        # Reset schon vorbei → Fehlerzeile ist obsolet, sonst bliebe die Anzeige nach
        # Kontingent-Reset für immer bei 100 %. Zurück auf die Kostenschätzung fallen lassen.
        if window.reset_at is not None and window.reset_at <= now:
            return {}
        return {"week": window}


def build_live_probes(cfg=settings) -> dict:
    """Echte Live-Probes für den ``ProviderBudgetService`` (Production-Wiring)."""
    return {
        "claude": ClaudeUsageProbe(cfg=cfg),
        "codex": CodexRolloutProbe(cfg=cfg),
        "opencode": OpenCodeLogProbe(cfg=cfg),
    }
