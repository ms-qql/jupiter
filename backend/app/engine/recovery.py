"""RecoveryService — Crash-Recovery über den Vault (PROJ-17).

Nach einem VPS-Reboot/Backend-Crash rekonstruiert Jupiter unterbrochene Stränge
bis zum letzten Handover und bietet pro Strang einen „Hier ging's weiter"-Vorschlag.

Design (Tech-Design PROJ-17): **read-only Sicht** über Vorhandenes — der
SessionManager (PROJ-14: Live-Index, beim Startup rehydriert → verwaiste Stränge)
und der VaultService (PROJ-2/PROJ-5: Handovers/Sessions). Es entsteht **kein neues
Persistenz-Schema**; das einzige Schreibziel ist das ``recovery_dismissed``-Flag im
Live-Index (Verwerfen blendet nur aus, der Vault-Eintrag bleibt → Audit).

Quellen-Stufen je Strang (stärkste zuerst):
1. **handover** — kuratierter Handover aus ``Handovers/`` (starker Vorschlag),
2. **log** — Auto-Session-Log aus ``Sessions/`` (mittlerer Vorschlag),
3. **incomplete** — nur Index-Metadaten (schwacher Vorschlag, „unvollständig").

Funktioniert auch bei komplett verlorenem In-Memory-Zustand: fehlt der Live-Index,
werden Kandidaten direkt aus den Vault-Dateien (``session_id`` aus dem Frontmatter)
rekonstruiert (reiner Vault-Wiederaufbau).
"""
from __future__ import annotations

import os
import re

from .handover import build_handover_md
from .manager import ERROR, SessionManager

# Marker, mit dem ``rehydrate()`` verwaiste (vor dem Restart aktive) Stränge
# kennzeichnet — siehe SessionManager.rehydrate.
_ORPHAN_MARKER = "Verwaist"
_SUGGESTION_CHARS = 400
_SEED_LOG_CHARS = 4000


def _is_orphan_strand(state) -> bool:
    """Ist dieser In-Memory-Strang ein verwaister Recovery-Kandidat?

    Nur nach einem Reboot/Crash verwaiste Stränge (Status ``error`` mit dem
    „Verwaist"-Marker aus ``rehydrate()``) dürfen wiederhergestellt werden — eine
    aktive (``running``/``waiting``) oder sauber beendete Session ist KEIN Kandidat
    (sonst ließe sich ein lebender Strang über die Recovery-API doppeln, BUG-1).
    Der ``child_session_id``-Zustand wird hier bewusst NICHT geprüft: die
    Idempotenz (1 Strang = 1 Nachfolger) verantwortet ``manager.recover()`` → 409.
    """
    return state.status == ERROR and (state.error or "").startswith(_ORPHAN_MARKER)


def _pname(path: str | None) -> str | None:
    if not path:
        return None
    return os.path.basename(path.rstrip("/")) or path


def _clip(text: str, limit: int) -> str:
    text = (text or "").strip()
    return text if len(text) <= limit else text[:limit].rstrip() + " … (gekürzt)"


def _extract_section(body: str, heading: str) -> str:
    """Inhalt eines ``## <heading>``-Abschnitts bis zur nächsten ``##``-Überschrift."""
    if not body:
        return ""
    m = re.search(
        rf"^##\s+{re.escape(heading)}\s*\n(.*?)(?=^##\s|\Z)", body, re.S | re.M
    )
    return m.group(1).strip() if m else ""


def _last_block(body: str) -> str:
    """Letzter ``## …``-Block eines Session-Logs (jüngste Äußerung)."""
    if not body:
        return ""
    parts = re.split(r"^##\s.*$", body, flags=re.M)
    tail = parts[-1].strip() if parts else ""
    return tail


class RecoveryService:
    """Aggregiert verwaiste Stränge (Manager) + Vault-Inhalte zu Recovery-Kandidaten."""

    # Frontmatter: voller Pfad eines Handover-Pointers (für reinen Vault-Wiederaufbau).
    _PROJECT_RE = re.compile(r"Projektpfad:\s*`([^`]+)`")

    def __init__(self, manager: SessionManager, vault) -> None:
        self._manager = manager
        self._vault = vault
        # In-Process-Ausblendung für reine Vault-Kandidaten (ohne Live-Index-Zeile,
        # in der das Flag persistiert würde). In-Memory-Verwaiste tragen das Flag
        # dagegen am ``SessionState`` (überdauert den Neustart).
        self._dismissed: set[str] = set()

    # --- öffentliche API ---------------------------------------------------

    def candidates(self) -> list[dict]:
        """Alle aktuell wiederherstellbaren Stränge (jüngster Stand zuerst)."""
        out: dict[str, dict] = {}
        for cand in self._vault_candidates():  # zuerst — In-Memory überschreibt.
            out[cand["session_id"]] = cand
        for cand in self._inmemory_candidates():
            out[cand["session_id"]] = cand

        # Idempotenz: Stränge mit bereits existierendem Nachfolger nicht doppelt zeigen.
        recovered = {
            r.state.parent_session_id
            for r in self._manager.list()
            if r.state.parent_session_id
        }
        result = [
            c
            for sid, c in out.items()
            if sid not in self._dismissed and sid not in recovered
        ]
        result.sort(key=lambda c: c.get("last_handover_at") or "", reverse=True)
        return result

    async def restore(self, session_id: str, *, initial_prompt: str | None = None):
        """Strang wiederherstellen → Kind-Session mit verdichtetem Seed.

        ``KeyError`` wenn kein Kandidat · ``ValueError`` wenn blockiert (z. B.
        Projektpfad weg) · ``RuntimeError`` wenn bereits wiederhergestellt (→ 409).
        """
        cand = self._candidate_for(session_id)
        if cand is None:
            raise KeyError(session_id)
        if cand["restore_blocked"]:
            raise ValueError(cand["blocked_reason"] or "Wiederherstellung blockiert.")
        return await self._manager.recover(
            session_id,
            seed_context=cand["_seed"],
            initial_prompt=initial_prompt,
            project_path=cand["project_path"],
            model=cand.get("_model"),
            permission_mode=cand.get("_permission_mode"),
            role=cand.get("_role"),
            owner=cand.get("_owner"),
            project_name=cand.get("project_name"),
        )

    def dismiss(self, session_id: str) -> None:
        """Kandidat verwerfen (idempotent). Vault-Eintrag bleibt unberührt (Audit).

        In-Memory-Verwaiste: Flag am State + im Live-Index (überdauert Neustart).
        Reine Vault-Kandidaten: nur In-Process (kein Live-Index-Eintrag vorhanden).
        """
        self._dismissed.add(session_id)
        self._manager.mark_recovery_dismissed(session_id)

    # --- Kandidaten-Quellen ------------------------------------------------

    def _inmemory_candidates(self) -> list[dict]:
        out = []
        for rt in self._manager.list():
            s = rt.state
            if not _is_orphan_strand(s):
                continue
            if s.child_session_id is not None or s.recovery_dismissed:
                continue
            out.append(self._candidate_from_state(s))
        return out

    def _vault_candidates(self) -> list[dict]:
        out: list[dict] = []
        seen: set[str] = set()
        for subdir in ("Handovers", "Sessions"):
            try:
                files = self._vault.list_files(subdir)
            except Exception:  # noqa: BLE001 — Vault-Bereich (noch) nicht vorhanden.
                continue
            for f in files:
                try:
                    data = self._vault.read_file(f["path"])
                except Exception:  # noqa: BLE001 — beschädigte Datei überspringen.
                    continue
                sid = str(data.get("frontmatter", {}).get("session_id") or "")
                if not sid or sid in seen:
                    continue
                if self._manager.get(sid) is not None:  # In-Memory hat Vorrang.
                    continue
                seen.add(sid)
                cand = self._candidate_for(sid)
                if cand is not None:
                    out.append(cand)
        return out

    # --- Kandidaten-Bau ----------------------------------------------------

    def _candidate_for(self, session_id: str) -> dict | None:
        """Einzelnen Kandidaten bauen (In-Memory-Verwaister bevorzugt, sonst Vault)."""
        rt = self._manager.get(session_id)
        if rt is not None:
            # BUG-1-Fix: eine im Speicher liegende, aber NICHT verwaiste Session
            # (aktiv/terminal) ist kein Recovery-Kandidat → kein Kandidat (→ 404).
            if not _is_orphan_strand(rt.state):
                return None
            return self._candidate_from_state(rt.state)
        source, body, created, warning, frontmatter = self._load_source(session_id)
        if source == "incomplete":
            return None  # nur Vault, aber weder Handover noch Log → nichts zu zeigen.
        # Projektpfad rekonstruieren, stärkste Quelle zuerst:
        #  1. Handover-Body (``Projektpfad: `…```),
        #  2. Frontmatter ``project_path`` (Session-Log trägt es seit PROJ-17),
        #  3. Projektname → existierendes Verzeichnis unter ``allowed_roots`` (Backfill
        #     für Altbestand ohne ``project_path`` im Frontmatter).
        m = self._PROJECT_RE.search(body or "")
        project_name = frontmatter.get("project_name") or frontmatter.get("title")
        if m:
            project_path = m.group(1)
        else:
            project_path = frontmatter.get("project_path") or self._resolve_by_name(project_name)
        project_name = project_name or _pname(project_path)
        return self._build(
            session_id,
            project_path=project_path,
            project_name=project_name,
            abc_phase=None,
            source=source,
            body=body,
            created=created,
            warning=warning,
            state=None,
        )

    @staticmethod
    def _resolve_by_name(project_name: str | None) -> str | None:
        """Altbestand ohne Frontmatter-Pfad: Projektname → existierendes Verzeichnis.

        Sucht ``<root>/<name>`` über die konfigurierten ``allowed_roots`` und gibt nur
        einen TATSÄCHLICH existierenden Ordner zurück (nie geraten) — existiert keiner,
        bleibt die Recovery wie bisher blockiert.
        """
        if not project_name:
            return None
        from ..config import settings

        for root in getattr(settings, "allowed_roots", []):
            cand = os.path.join(root, project_name)
            if os.path.isdir(cand):
                return cand
        return None

    def _candidate_from_state(self, s) -> dict:
        source, body, created, warning, _frontmatter = self._load_source(s.session_id)
        return self._build(
            s.session_id,
            project_path=s.project_path,
            project_name=s.project_name or _pname(s.project_path),
            abc_phase=s.abc_phase_reached or s.abc_phase,
            source=source,
            body=body,
            created=created or s.last_activity.isoformat(),
            warning=warning,
            state=s,
        )

    def _build(
        self, session_id, *, project_path, project_name, abc_phase, source, body, created, warning, state
    ) -> dict:
        suggestion, seed = self._suggestion_and_seed(source, body, state)
        blocked, reason = False, None
        if not project_path:
            blocked, reason = True, "Projektpfad nicht rekonstruierbar — Wiederherstellung nicht möglich."
        elif not os.path.isdir(project_path):
            blocked, reason = True, f"Projektpfad existiert nicht mehr: {project_path}"
        return {
            "session_id": session_id,
            "project_path": project_path or "",
            "project_name": project_name,
            "abc_phase": abc_phase,
            "last_handover_at": created,
            "source": source,
            "suggestion": suggestion.strip() or "Kein verdichteter Stand verfügbar.",
            "restore_blocked": blocked,
            "blocked_reason": reason,
            "warning": warning,
            # interne Felder (vom Response-Schema gefiltert) — für restore().
            "_seed": seed,
            "_model": getattr(state, "model", None),
            "_permission_mode": getattr(state, "permission_mode", None),
            "_role": getattr(state, "role", None),
            "_owner": getattr(state, "owner", None),
        }

    def _suggestion_and_seed(self, source: str, body: str | None, state) -> tuple[str, str]:
        if source == "handover":
            offen = _extract_section(body, "Offen")
            wo = _extract_section(body, "Wo stehen wir?")
            suggestion = offen or wo or _clip(body or "", _SUGGESTION_CHARS)
            return suggestion, (body or "")
        if source == "log":
            last = _last_block(body)
            suggestion = (
                "Letzter Stand aus dem Session-Log (kein kuratierter Handover):\n"
                + _clip(last, _SUGGESTION_CHARS)
                if last
                else "Letzter Stand aus dem Session-Log."
            )
            seed = self._skeleton(state) if state is not None else _clip(body or "", _SEED_LOG_CHARS)
            return suggestion, seed
        # incomplete
        seed = self._skeleton(state) if state is not None else "Wiederaufnahme nach Absturz — kein Handover/Log vorhanden."
        phase = getattr(state, "abc_phase_reached", None) or getattr(state, "abc_phase", None) if state else None
        suggestion = "Kein Handover/Log gefunden — nur Metadaten (unvollständig)."
        if phase:
            suggestion += f"\nLetzte bekannte Phase: {phase}."
        return suggestion, seed

    @staticmethod
    def _skeleton(state) -> str:
        """Mechanisches Handover-Gerüst aus dem Zustand (kein Transkript nötig)."""
        return build_handover_md(state, [], [])

    # --- Vault-Lookup ------------------------------------------------------

    def _load_source(
        self, session_id: str
    ) -> tuple[str, str | None, str | None, str | None, dict]:
        """Beste verfügbare Quelle: (source, body, created_iso, warning, frontmatter)."""
        h = self._find_latest(session_id, "Handovers")
        if h is not None:
            return "handover", h["body"], h["created"], self._handover_warning(h["body"]), h["frontmatter"]
        log = self._find_latest(session_id, "Sessions")
        if log is not None:
            return "log", log["body"], log["created"], None, log["frontmatter"]
        return "incomplete", None, None, None, {}

    def _find_latest(self, session_id: str, subdir: str) -> dict | None:
        """Jüngste Datei in ``subdir`` mit passendem ``session_id`` im Frontmatter.

        Mehrere Handovers je Strang → der mit dem jüngsten ``created`` gewinnt.
        """
        try:
            files = self._vault.list_files(subdir)
        except Exception:  # noqa: BLE001
            return None
        best: dict | None = None
        for f in files:
            try:
                data = self._vault.read_file(f["path"])
            except Exception:  # noqa: BLE001
                continue
            if str(data.get("frontmatter", {}).get("session_id") or "") != session_id:
                continue
            fm = data.get("frontmatter", {})
            created = str(fm.get("created") or f.get("modified") or "")
            if best is None or created > best["created"]:
                best = {"body": data.get("body") or "", "created": created, "frontmatter": fm}
        return best

    @staticmethod
    def _handover_warning(body: str) -> str | None:
        """Beschädigter/halber Handover: Standard-Abschnitte fehlen → Warnung."""
        if not body or not (_extract_section(body, "Wo stehen wir?") or _extract_section(body, "Offen")):
            return "Handover wirkt unvollständig oder beschädigt — Standard-Abschnitte fehlen."
        return None
