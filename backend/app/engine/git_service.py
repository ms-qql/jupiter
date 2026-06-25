"""GitService — in-App Git-Branch-Handling für den abc-Workflow (PROJ-13).

Kapselt Git als **parametrisierten** Subprozess (``asyncio.create_subprocess_exec``
— exakt das ``scout``/``claude_driver``-Muster: feste Argumentliste, ``cwd`` =
Projektpfad, hartes Timeout, ``stderr``-Auswertung). Kein Shell, keine interaktiven
Flags (``-i``), kein Force als Default → keine Injection, kein stiller Datenverlust.

Git **ist** die Quelle der Wahrheit: der Status wird live gelesen, nichts wird in
einer DB gespiegelt. Alle Operationen laufen ausschließlich innerhalb der
``allowed_roots`` — derselbe ``validate_project_path``-Seam wie Fileexplorer/Reader.
Kein JWT/DB (Jupiter-Override).

Sicherheits-Leitplanken (Spec-Akzeptanzkriterien):
- Wechsel/Anlegen bei **dirty** Working Tree → blockiert (``DirtyWorkingTree``),
  nie erzwungen; Stash ist ein **expliziter**, separater Schritt.
- Promote (``--no-ff``) nur nach Vorab-Check (clean + Ziel ⊆ Quelle); ein
  Merge-**Konflikt** wird abgebrochen (``git merge --abort``) und gemeldet
  (``MergeConflict``) — die App führt keinen erzwungenen Merge aus.
- Netz ist optional: ahead/behind wird rein lokal gegen den Tracking-Branch
  berechnet (kein ``fetch``); fehlt ein Upstream, bleibt es ``None``.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re

from ..config import settings
from .manager import validate_project_path

logger = logging.getLogger(__name__)

# Schema für Feature-Branches des abc-Workflows: specs/PROJ-<id>-<kebab-slug>.
_SLUG_RE = re.compile(r"[^a-z0-9]+")


class GitError(Exception):
    """Allgemeiner Git-Fehler (→ 400). Trägt eine deutsche, nutzerlesbare Meldung."""


class NotARepo(GitError):
    """Der Projektpfad ist (noch) kein Git-Repository (→ 409, Angebot ``git init``)."""


class DirtyWorkingTree(GitError):
    """Uncommittete Änderungen blockieren die Operation (→ 409, Optionen statt Zwang)."""


class MergeConflict(GitError):
    """Merge/Wechsel scheiterte an einem Konflikt; wurde abgebrochen (→ 409)."""


class GitTimeout(GitError):
    """Git-Aufruf hat das Zeitlimit überschritten (→ 504)."""


def _slugify(raw: str) -> str:
    """Kebab-Slug für Branch-Namen (a–z, 0–9, Bindestriche) — wie der abc-Skill."""
    s = _SLUG_RE.sub("-", (raw or "").strip().lower()).strip("-")
    if not s:
        raise GitError("Ungültiger Slug für den Feature-Branch.")
    return s


class GitService:
    """Liest Branch-Status und führt geführte, sichere Git-Operationen aus."""

    # --- Subprozess-Kern ---------------------------------------------------

    async def _run(self, real: str, *args: str) -> tuple[int, str, str]:
        """Ein ``git``-Aufruf in ``real`` (validierter Repo-Pfad) → (rc, stdout, stderr)."""
        proc = await asyncio.create_subprocess_exec(
            settings.git_bin, *args,
            cwd=real,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(
                proc.communicate(), timeout=settings.git_timeout_seconds
            )
        except asyncio.TimeoutError as exc:
            proc.kill()
            raise GitTimeout("Git-Aufruf hat das Zeitlimit überschritten.") from exc
        return (
            proc.returncode if proc.returncode is not None else -1,
            out.decode("utf-8", "replace").strip(),
            err.decode("utf-8", "replace").strip(),
        )

    async def _git(self, real: str, *args: str) -> str:
        """Wie ``_run``, aber rc≠0 → ``GitError`` mit der stderr-Meldung."""
        rc, out, err = await self._run(real, *args)
        if rc != 0:
            raise GitError(err or f"git {args[0]} endete mit Code {rc}.")
        return out

    # --- Pfad/Repo-Härtung -------------------------------------------------

    def _repo(self, project_path: str) -> str:
        """Validierter Projekt-Realpfad (innerhalb der Roots, existierendes Verzeichnis)."""
        try:
            return validate_project_path(project_path)
        except ValueError as exc:
            raise GitError(str(exc)) from exc

    async def _is_repo(self, real: str) -> bool:
        rc, out, _ = await self._run(real, "rev-parse", "--is-inside-work-tree")
        return rc == 0 and out == "true"

    async def _require_repo(self, project_path: str) -> str:
        real = self._repo(project_path)
        if not await self._is_repo(real):
            raise NotARepo("Dieses Verzeichnis ist kein Git-Repository.")
        return real

    # --- Status-Bausteine --------------------------------------------------

    async def _current_branch(self, real: str) -> tuple[str | None, bool]:
        """(Branch-Name, detached?). Bei detached HEAD: Kurz-Hash + Flag."""
        rc, out, _ = await self._run(real, "symbolic-ref", "--short", "-q", "HEAD")
        if rc == 0 and out:
            return out, False
        _, sha, _ = await self._run(real, "rev-parse", "--short", "HEAD")
        return (sha or None), True

    async def _is_dirty(self, real: str) -> bool:
        rc, out, _ = await self._run(real, "status", "--porcelain")
        return bool(out) if rc == 0 else False

    async def _ahead_behind(self, real: str) -> tuple[int | None, int | None]:
        """Lokal gegen den Upstream (kein Netz). Ohne Tracking-Branch → (None, None)."""
        rc, out, _ = await self._run(
            real, "rev-list", "--left-right", "--count", "HEAD...@{upstream}"
        )
        if rc != 0 or not out:
            return None, None
        try:
            ahead, behind = (int(x) for x in out.split())
        except ValueError:
            return None, None
        return ahead, behind

    async def _branches(self, real: str) -> list[str]:
        rc, out, _ = await self._run(
            real, "for-each-ref", "--format=%(refname:short)", "refs/heads"
        )
        return out.splitlines() if rc == 0 and out else []

    async def _branch_exists(self, real: str, name: str) -> bool:
        rc, _, _ = await self._run(
            real, "show-ref", "--verify", "--quiet", f"refs/heads/{name}"
        )
        return rc == 0

    async def status(self, project_path: str) -> dict:
        """Voller Branch-Status eines Projekts (read-only, schnell, pollbar)."""
        real = self._repo(project_path)
        if not await self._is_repo(real):
            return {
                "path": real,
                "is_repo": False,
                "branch": None,
                "detached": False,
                "dirty": False,
                "ahead": None,
                "behind": None,
                "branches": [],
            }
        branch, detached = await self._current_branch(real)
        ahead, behind = await self._ahead_behind(real)
        return {
            "path": real,
            "is_repo": True,
            "branch": branch,
            "detached": detached,
            "dirty": await self._is_dirty(real),
            "ahead": ahead,
            "behind": behind,
            "branches": await self._branches(real),
        }

    # --- Operationen -------------------------------------------------------

    async def switch(self, project_path: str, branch: str) -> dict:
        """Branch wechseln. Blockiert bei dirty Working Tree (kein stiller Verlust)."""
        real = await self._require_repo(project_path)
        if await self._is_dirty(real):
            raise DirtyWorkingTree(
                "Uncommittete Änderungen vorhanden. Erst committen oder stashen "
                "(oder den Stash-Schritt nutzen), dann wechseln."
            )
        if not await self._branch_exists(real, branch):
            raise GitError(f"Branch '{branch}' existiert nicht.")
        await self._git(real, "checkout", branch)
        logger.info("PROJ-13 switch: %s → %s", real, branch)
        return await self.status(project_path)

    async def create_feature_branch(
        self, project_path: str, feature_id: int, slug: str, base: str = "main"
    ) -> dict:
        """``specs/PROJ-<id>-<slug>`` anlegen (von ``base``) oder auschecken, falls vorhanden."""
        real = await self._require_repo(project_path)
        name = f"specs/PROJ-{feature_id}-{_slugify(slug)}"
        if await self._is_dirty(real):
            raise DirtyWorkingTree(
                "Uncommittete Änderungen vorhanden — erst sichern, dann den "
                "Feature-Branch anlegen/wechseln."
            )
        if await self._branch_exists(real, name):
            # Feedback-Runde 2: existierenden Branch auschecken statt neu anlegen.
            await self._git(real, "checkout", name)
            logger.info("PROJ-13 feature-branch (checkout): %s → %s", real, name)
        else:
            if not await self._branch_exists(real, base):
                raise GitError(f"Basis-Branch '{base}' existiert nicht.")
            await self._git(real, "checkout", "-b", name, base)
            logger.info("PROJ-13 feature-branch (neu): %s → %s von %s", real, name, base)
        return await self.status(project_path)

    async def promote(self, project_path: str, source: str, target: str) -> dict:
        """``source`` nach ``target`` mergen (``--no-ff``). Vorab-Check + Konflikt-Abbruch."""
        real = await self._require_repo(project_path)
        if await self._is_dirty(real):
            raise DirtyWorkingTree(
                "Uncommittete Änderungen vorhanden — Promote nur bei sauberem "
                "Working Tree."
            )
        for ref in (source, target):
            if not await self._branch_exists(real, ref):
                raise GitError(f"Branch '{ref}' existiert nicht.")
        # Vorab-Check: Ziel ⊆ Quelle (target ist Vorfahr von source) → divergenzfrei.
        rc, _, _ = await self._run(
            real, "merge-base", "--is-ancestor", target, source
        )
        if rc != 0:
            raise GitError(
                f"'{target}' enthält Commits, die '{source}' nicht hat — erst "
                f"zusammenführen, dann promoten."
            )
        await self._git(real, "checkout", target)
        rc, _, err = await self._run(real, "merge", "--no-ff", "--no-edit", source)
        if rc != 0:
            await self._run(real, "merge", "--abort")
            raise MergeConflict(
                f"Merge-Konflikt beim Promoten von '{source}' nach '{target}' — "
                f"abgebrochen. Auflösung bleibt manuell (Terminal). {err}".strip()
            )
        logger.info("PROJ-13 promote: %s — %s → %s", real, source, target)
        return await self.status(project_path)

    async def stash(self, project_path: str) -> dict:
        """Expliziter Stash (inkl. untracked) vor einem Wechsel — nie automatisch."""
        real = await self._require_repo(project_path)
        if not await self._is_dirty(real):
            raise GitError("Keine Änderungen zum Stashen.")
        await self._git(real, "stash", "push", "-u", "-m", "jupiter")
        logger.info("PROJ-13 stash: %s", real)
        return await self.status(project_path)

    async def init(self, project_path: str) -> dict:
        """``git init`` für ein Nicht-Repo innerhalb der Roots (bestätigter Schritt)."""
        real = self._repo(project_path)
        if await self._is_repo(real):
            raise GitError("Verzeichnis ist bereits ein Git-Repository.")
        await self._git(real, "init")
        logger.info("PROJ-13 init: %s", real)
        return await self.status(project_path)
