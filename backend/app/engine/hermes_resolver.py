"""Hermes-Modell-Resolver (PROJ-85) — reine, lesende Übersetzung der Engine-Registry.

Liefert die fürs „Neu Hermes"-Startdialog verfügbaren Modelle und übersetzt eine
gewählte Registry-Modellkombination (engine + model) in die Hermes-CLI-Argumente
(``-m <model> --provider <provider>``) — ausschließlich für DIESE neue Session.

Bewusst KEIN Schreibzugriff: PROJ-85 verändert keine ``jupiter-*``-Profile
(``PATCH /settings/hermes-profiles`` bleibt außen vor). Die Hin-/Rückübersetzung
von PROJ-83 wird als Vorlage wiederverwendet, aber hier niemals in YAML geschrieben.
"""
from __future__ import annotations

from dataclasses import dataclass

from .registry import engine_registry
from .hermes_profiles import CLAUDE_PROVIDER, CLAUDE_ALIAS_TO_MODEL, CODEX_PROVIDER

# Engine-Key → Hermes-``--provider``-Wert. Alles, was hier nicht steht, wird über
# den Engine-Key selbst abgebildet (Default: provider == engine).
_PROVIDER_BY_ENGINE: dict[str, str] = {
    "claude": CLAUDE_PROVIDER,
    "codex": CODEX_PROVIDER,
}


@dataclass(frozen=True)
class HermesModelOption:
    """Ein im Startdialog wählbares, Hermes-kompatibles Modell."""

    engine: str
    model: str
    label: str


@dataclass(frozen=True)
class HermesInvocation:
    """Aufgelöste Hermes-CLI-Argumente für genau eine Session."""

    provider: str
    model: str


def hermes_model_options() -> list[HermesModelOption]:
    """Verfügbare, Hermes-kompatible Registry-Modelle (engine, model, Anzeigename).

    Nur steuerbare Session-Engines (``kind == engine``), die aktiv UND verfügbar
    sind, landen hier — exakt die Menge, die das Frontend anbietet. PROJ-83s
    Profil-Schreibpfad ist ausdrücklich nicht beteiligt (Lesen only).
    """
    out: list[HermesModelOption] = []
    for prof in engine_registry.all():
        if prof.kind != "engine" or not prof.enabled:
            continue
        available, _ = prof.availability()
        if not available:
            continue
        if not prof.models:
            continue
        for model in prof.models:
            label = f"{prof.label}: {model}"
            out.append(HermesModelOption(engine=prof.key, model=model, label=label))
    return out


def resolve_hermes_invocation(engine: str, model: str) -> HermesInvocation:
    """Engine+Modell (Registry-Vokabular) → Hermes ``-m``/``--provider``.

    Wirft ``ValueError``, wenn die Kombination nicht auswählbar ist (→ 400 im
    Startvertrag). Claude wird über PROJ-83s Alias-Map auf das Hermes-Modell
    übersetzt; andere Engines nutzen ihren Key als Provider (Default).
    """
    prof = engine_registry.get(engine)
    if prof is None or prof.kind != "engine" or not prof.enabled:
        raise ValueError(f"Unbekannte oder nicht verfügbare Engine '{engine}'.")
    available, _ = prof.availability()
    if not available:
        raise ValueError(f"Engine '{engine}' ist aktuell nicht verfügbar.")
    if model not in prof.models:
        raise ValueError(f"Modell '{model}' ist für Engine '{engine}' nicht auswählbar.")

    provider = _PROVIDER_BY_ENGINE.get(engine, engine)
    if engine == "claude":
        mapped = CLAUDE_ALIAS_TO_MODEL.get(model)
        if not mapped:
            raise ValueError(f"Modell '{model}' ist für Hermes nicht übersetzbar.")
        hermes_model = mapped
    else:
        hermes_model = model
    return HermesInvocation(provider=provider, model=hermes_model)
