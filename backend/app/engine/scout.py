"""Billige Späher-Agenten (PROJ-19 #26).

Ein Späher ist ein **kurzlebiger, nicht-steuerbarer** Lauf auf dem günstigen Modell
(Default Haiku): er liest viel (RAG-Ausschnitte + explizite Vault-Datei-Pointer) und
gibt der teuren Hauptsession **nur das verdichtete Fazit** zurück — nicht die Rohdaten.

Bewusst leichter als die volle Dispatch-Schicht (PROJ-22): kein Steering, keine
Decision Cards, keine Index-Persistenz. Der eigentliche Lauf ist über ``runner``
injizierbar (Tests geben einen Fake; Default ruft die ``claude``-CLI einmalig auf).

Eskalation (Edge Case der Spec): ist das Fazit leer/zu dünn, meldet das Ergebnis
``usable=False`` + einen Hinweis — die Hauptsession kann denselben Auftrag dann
nachvollziehbar mit einem teureren Modell wiederholen (``model``-Parameter).

Doppelte Ersparnis: der Späher zieht seinen Kontext über Pointer/RAG (#23) statt
Volltext-Dumps — billiges Modell **und** schlanker Kontext.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from ..config import settings

# (prompt, model, cwd) -> stdout-Text des einmaligen Laufs.
ScoutRunner = Callable[[str, str, str], Awaitable[str]]

_MIN_USABLE_CHARS = 20  # kürzeres Fazit gilt als „unbrauchbar" → Eskalations-Hinweis.


@dataclass
class ScoutResult:
    task: str
    model_used: str
    summary: str
    sources: list[str] = field(default_factory=list)
    context_chars: int = 0
    usable: bool = True
    note: str | None = None


async def _default_runner(prompt: str, model: str, cwd: str) -> str:
    """Einmaliger, nicht-streamender ``claude -p``-Lauf → reiner Antworttext.

    Kein Stream-JSON, kein Hook, keine Session-ID: ein Fazit, dann Ende. Der Kontext
    steckt komplett im Prompt → das Modell braucht keine Tools (keine Freigaben).
    """
    proc = await asyncio.create_subprocess_exec(
        settings.claude_bin, "-p", prompt, "--model", model,
        cwd=cwd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=settings.scout_timeout_seconds)
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise TimeoutError("Späher-Lauf hat das Zeitlimit überschritten.") from exc
    if proc.returncode not in (0, None):
        msg = err.decode("utf-8", "replace").strip() or f"Späher endete mit Code {proc.returncode}."
        raise RuntimeError(msg)
    return out.decode("utf-8", "replace").strip()


class ScoutService:
    """Liest Kontext (RAG + Datei-Pointer) ein und delegiert das Fazit ans günstige Modell."""

    def __init__(self, vault, runner: ScoutRunner | None = None) -> None:
        self._vault = vault
        self._runner = runner or _default_runner

    def _gather_context(
        self, query: str | None, paths: list[str] | None, top_n: int
    ) -> tuple[list[str], list[str]]:
        """Sammelt Kontext-Blöcke + Quellen-Pfade (RAG-Snippets zuerst, dann Datei-Pointer)."""
        blocks: list[str] = []
        sources: list[str] = []
        budget = settings.scout_max_context_chars

        if query:
            for snip in self._vault.relevant_snippets(query, top_n=top_n):
                block = f"[{snip['path']}]\n{snip['snippet']}"
                if budget - len(block) < 0:
                    break
                blocks.append(block)
                sources.append(snip["path"])
                budget -= len(block)

        for rel in paths or []:
            try:
                doc = self._vault.read_file(rel)
            except (FileNotFoundError, IsADirectoryError, ValueError):
                continue  # fehlender/ungültiger Pointer wird übersprungen, kein Hard-Fail
            body = doc.get("body") or doc.get("content") or ""
            block = f"## {doc['path']}\n{body[:budget]}"
            if budget <= 0:
                break
            blocks.append(block)
            sources.append(doc["path"])
            budget -= len(block)

        return blocks, sources

    def _build_prompt(self, task: str, blocks: list[str]) -> str:
        parts = [
            "Du bist ein günstiger Späher-Agent. Lies den folgenden Kontext und "
            "beantworte die Aufgabe. Antworte EXTREM knapp — nur das Fazit, keine "
            "Wiederholung des Kontexts, keine Vorrede.",
            f"\nAufgabe:\n{task}",
        ]
        if blocks:
            parts.append("\nKontext:\n" + "\n\n".join(blocks))
        return "\n".join(parts)

    async def scout(
        self,
        *,
        task: str,
        query: str | None = None,
        paths: list[str] | None = None,
        project_path: str | None = None,
        model: str | None = None,
        top_n: int = 5,
    ) -> ScoutResult:
        model_used = (model or settings.scout_default_model).strip()
        cwd = project_path or settings.reader_default_project
        blocks, sources = self._gather_context(query, paths, top_n)
        prompt = self._build_prompt(task, blocks)

        summary = (await self._runner(prompt, model_used, cwd)).strip()
        usable = len(summary) >= _MIN_USABLE_CHARS
        note = (
            None
            if usable
            else "Fazit wirkt dünn/leer — Auftrag ggf. mit größerem Modell wiederholen "
            "(model=sonnet|opus)."
        )
        return ScoutResult(
            task=task,
            model_used=model_used,
            summary=summary,
            sources=sources,
            context_chars=len(prompt),
            usable=usable,
            note=note,
        )
