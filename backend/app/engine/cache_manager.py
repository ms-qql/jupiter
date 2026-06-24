"""Prompt-Caching (PROJ-19 #27).

Stabile, wiederkehrende Prompt-Bestandteile (Konstitution + Rolle) bilden das
**cache-freundliche Präfix**: sie kommen zuerst, der session-spezifische, variable
Zusatz (Seed-Kontext bei Reset/Recovery) zuletzt. So bleibt das gecachte Präfix
über Sessions/Turns hinweg identisch — der Treiber (Claude Code) bzw. die API
können es wiederverwenden statt neu zu senden.

Der ``cache_key`` ist ein Inhalts-Hash des stabilen Präfixes: ändert sich die
Rolle/der Skill/die Konstitution, ändert sich der Hash → **automatische
Invalidierung** (kein Servieren veralteter Prompts, Edge Case der Spec).

Bewusst zustandslos und engine-agnostisch: der eigentliche Cache lebt in der
Engine. Ist das Feature aus, liefert :meth:`plan` denselben Prompt, nur ohne
``cache_key`` (No-op-Fallback, kein Hard-Fail — AC „einzeln abschaltbar").
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class CachePlan:
    """Ergebnis der Prompt-Planung."""

    enabled: bool
    cache_key: str | None  # Inhalts-Hash des stabilen Präfixes (None = aus/leer).
    prompt: str            # assemblierter Append-System-Prompt (stabil zuerst).
    stable_chars: int      # Größe des cachefähigen Präfixes (für Sichtbarkeit/Mess.).


class CacheManager:
    """Plant den cache-freundlichen Append-System-Prompt + dessen Cache-Identität."""

    def __init__(self, enabled: bool = True) -> None:
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def plan(self, stable_prefix: str, variable_suffix: str | None = None) -> CachePlan:
        """Assembliert ``stable_prefix`` (cachefähig) + optionalen ``variable_suffix``.

        Reihenfolge ist identisch zu ``constitution.combine_with_extra`` (stabil zuerst),
        damit das Verhalten unverändert bleibt — nur der Cache-Key kommt hinzu.
        """
        stable = (stable_prefix or "").strip()
        variable = (variable_suffix or "").strip()
        if stable and variable:
            prompt = f"{stable}\n\n{variable}"
        else:
            prompt = stable or variable

        if not self._enabled or not stable:
            return CachePlan(enabled=False, cache_key=None, prompt=prompt, stable_chars=0)

        key = hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]
        return CachePlan(enabled=True, cache_key=key, prompt=prompt, stable_chars=len(stable))
