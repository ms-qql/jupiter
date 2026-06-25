"""CoordinatorService — Multi-Agent-Dispatch + Vertrag-zuerst (PROJ-22).

Materialisiert die bisher manuelle Dispatch-Rolle: liest offene Tickets aus
``features/INDEX.md``, baut einen topologisch sortierten Verteilungsplan (Ticket →
Rolle/Skill/Engine/Modell), startet je nicht-blockiertem Ticket eine Spezialisten-
Session über das bestehende Treiber-Modell (PROJ-1/PROJ-14) und hält die Eltern-Kind-
Flotte (1:N) im selben In-memory-Index. Der API-Vertrag liegt als Vault-Artefakt
(PROJ-2); die Kinder bekommen einen **Pointer** darauf (kein Volltext-Duplikat).

Kein neues Persistenz-Schema (Tech-Design Abschnitt 0): Wahrheit/Recovery laufen
über den Vault (PROJ-17), die Flotte ist ein Feld am bestehenden ``SessionState``.

Die *automatische Vermittlung* eines Vertrags-Konflikts ist Laufzeit-Verhalten der
Koordinator-Session (Prompt/Konstitution); diese Schicht stellt das deterministische
Gerüst (Plan/Dispatch/Fleet/Pause/Reassign/Contract) + den ``contract_conflict``-Card-
Typ bereit. Die Konflikt-Eskalation als Decision Card nutzt den vorhandenen Card-Flow.
"""
from __future__ import annotations

import os

from . import abc_phases
from .launcher import parse_index_features
from .manager import SessionLimitError, SessionManager, SessionRuntime, validate_project_path
from .vault import VaultService

# Phase → Spezialisten-Rolle (spiegelt rules/agents/*). Bestimmt die Konstitution
# der Kind-Session (resolve_constitution); fehlt eine Rollendatei, gilt die globale.
PHASE_TO_ROLE: dict[str, str] = {
    "brainstorm": "coordinator",
    "requirements": "architect",
    "architecture": "architect",
    "frontend": "frontend",
    "backend": "backend",
    "qa": "qa",
    "deploy": "backend",
    "document": "architect",
}

# Status, die NICHT mehr verteilbar sind: „deployed" ist fertig; „approved" hat als
# einzigen offenen Schritt den menschlich freizugebenden Deploy (kein Auto-Dispatch).
_NON_DISPATCHABLE = {"deployed", "approved"}


def _number(ticket_id: str) -> str:
    """„PROJ-22" → „22" (für den Skill-Aufruf)."""
    return ticket_id.split("-", 1)[1] if "-" in ticket_id else ticket_id


def _initial_prompt(skill: str | None, ticket_id: str, title: str) -> str:
    """Start-Auftrag einer Spezialisten-Session — bevorzugt der abc-Skill-Aufruf."""
    if skill:
        return f"/{skill} {_number(ticket_id)}"
    return f"Bearbeite Ticket {ticket_id}: {title}".strip()


def build_plan(project_path: str) -> dict:
    """Verteilungsplan aus ``features/INDEX.md`` (read-only, kein Dispatch).

    Reihenfolge topologisch über die ``Abhängigkeiten``-Spalte: ein Ticket gilt als
    sofort verteilbar, wenn alle seine offenen Abhängigkeiten erledigt sind; hängt es
    an noch offener Arbeit, ist es ``blocked`` (wartet). Zirkuläre/fehlende
    Abhängigkeiten werden als Warnung gemeldet, statt zu blockieren oder zu raten —
    der auflösbare Teilgraph wird trotzdem geplant. ``ValueError`` bei Pfad außerhalb
    der Roots.
    """
    real = validate_project_path(project_path)
    index_path = os.path.join(real, "features", "INDEX.md")
    if not os.path.isfile(index_path):
        return {"project_path": real, "items": [], "warnings": ["Keine features/INDEX.md gefunden."]}
    try:
        with open(index_path, encoding="utf-8") as fh:
            features = parse_index_features(fh.read())
    except OSError as exc:
        return {"project_path": real, "items": [], "warnings": [f"INDEX.md nicht lesbar: {exc}"]}

    recognized = [f for f in features if abc_phases.status_maturity(f["status"]) is not None]
    all_ids = {f["id"] for f in features}
    open_feats = [
        f for f in recognized if abc_phases.normalize_status(f["status"]) not in _NON_DISPATCHABLE
    ]
    open_ids = {f["id"] for f in open_feats}

    warnings: list[str] = []
    # Offene Abhängigkeiten je Ticket (nur solche, die selbst noch offen sind, blockieren).
    open_deps: dict[str, list[str]] = {}
    for f in open_feats:
        deps = f.get("dependencies", []) or []
        missing = [d for d in deps if d not in all_ids]
        for d in missing:
            warnings.append(f"{f['id']} hängt von unbekanntem {d} ab (in INDEX.md nicht gefunden).")
        open_deps[f["id"]] = [d for d in deps if d in open_ids and d != f["id"]]

    ordered_ids, cyclic_ids = _topo_order(open_feats, open_deps)
    if cyclic_ids:
        warnings.append(
            "Zirkuläre Abhängigkeit erkannt (" + ", ".join(sorted(cyclic_ids)) + ") — "
            "nur der auflösbare Teil wird verteilt."
        )

    by_id = {f["id"]: f for f in open_feats}
    items: list[dict] = []
    for order, fid in enumerate(ordered_ids, start=1):
        f = by_id[fid]
        phase = abc_phases.next_phase_for_status(f["status"])
        deps = open_deps[fid]
        in_cycle = fid in cyclic_ids
        blocked = bool(deps) or in_cycle
        if in_cycle:
            reason = "Teil einer zirkulären Abhängigkeit."
        elif deps:
            reason = "Wartet auf Abschluss von " + ", ".join(deps) + "."
        else:
            reason = None
        items.append({
            "ticket_id": fid,
            "title": f["title"],
            "status": f["status"],
            "role": PHASE_TO_ROLE.get(phase) if phase else None,
            "skill": abc_phases.skill_for_phase(phase),
            "engine": "claude",
            "model": abc_phases.model_for_phase(phase),
            "order": order,
            "dependencies": f.get("dependencies", []) or [],
            "blocked": blocked,
            "blocked_reason": reason,
        })
    return {"project_path": real, "items": items, "warnings": warnings}


def _topo_order(open_feats: list[dict], open_deps: dict[str, list[str]]) -> tuple[list[str], set[str]]:
    """Kahn-Topo-Sort über die offenen Tickets. Determinismus über die Dokument-
    Reihenfolge (``order``). Rückgabe: (sortierte IDs inkl. Zyklus-Rest am Ende,
    Menge der Knoten in einem Zyklus)."""
    order_of = {f["id"]: f["order"] for f in open_feats}
    indeg = {fid: len(open_deps.get(fid, [])) for fid in order_of}
    # Kanten dep → ticket (ein erledigter dep macht ticket „bereiter").
    dependents: dict[str, list[str]] = {fid: [] for fid in order_of}
    for fid, deps in open_deps.items():
        for d in deps:
            if d in dependents:
                dependents[d].append(fid)

    ready = sorted((fid for fid, d in indeg.items() if d == 0), key=lambda x: order_of[x])
    result: list[str] = []
    while ready:
        fid = ready.pop(0)
        result.append(fid)
        for dep in dependents[fid]:
            indeg[dep] -= 1
            if indeg[dep] == 0:
                # Einfügen unter Wahrung der Dokument-Reihenfolge.
                ready.append(dep)
                ready.sort(key=lambda x: order_of[x])
    cyclic = {fid for fid in order_of if fid not in result}
    # Zyklus-Knoten deterministisch hinten anhängen, damit der Plan vollständig bleibt.
    result.extend(sorted(cyclic, key=lambda x: order_of[x]))
    return result, cyclic


class CoordinatorNotFoundError(Exception):
    """Koordinator-Session existiert nicht (oder ist keine Koordinator-Session)."""


class TicketNotFoundError(Exception):
    """Kein Kind dieser Flotte bearbeitet das angefragte Ticket."""


class CoordinatorService:
    """Dispatch-Schicht über dem SessionManager — startet/aggregiert eine Flotte."""

    ROLE = "coordinator"

    def __init__(self, manager: SessionManager, vault: VaultService) -> None:
        self._manager = manager
        self._vault = vault

    # --- Plan --------------------------------------------------------------

    def plan(self, project_path: str) -> dict:
        return build_plan(project_path)

    # --- Dispatch ----------------------------------------------------------

    async def dispatch(self, project_path: str, items: list[dict]) -> dict:
        """Koordinator-Session + je nicht-blockiertem Ticket eine Spezialisten-Session.

        Bricht beim ersten erschöpften Engine-Slot (PROJ-14) ab und liefert die bis
        dahin gestartete Flotte — die übrigen Tickets bleiben unverteilt (statt sie zu
        verlieren; der Nutzer kann nach dem Beenden einer Session erneut dispatchen).
        ``ValueError`` bei ungültigem Pfad; ``SessionLimitError`` nur, wenn schon der
        Koordinator selbst keinen Slot mehr bekommt.
        """
        real = validate_project_path(project_path)
        label = os.path.basename(real) or real
        coordinator = await self._manager.create(
            project_path=real,
            initial_prompt=(
                "Du bist der Koordinator dieser Flotte (PROJ-22). Überwache die "
                "Spezialisten-Sessions, vermittle Vertrags-Konflikte anhand des "
                "API-Vertrags und eskaliere nur Unlösbares als Decision Card."
            ),
            model="opus",
            role=self.ROLE,
            project_name=f"{label} · Koordinator",
            engine="claude",
        )
        cid = coordinator.state.session_id

        dispatchable = [it for it in items if not it.get("blocked")]
        for it in dispatchable:
            try:
                child = await self._manager.create(
                    project_path=real,
                    initial_prompt=_initial_prompt(it.get("skill"), it["ticket_id"], it.get("title", "")),
                    model=it.get("model") or "sonnet",
                    role=it.get("role"),
                    project_name=f"{label} · {it['ticket_id']}",
                    engine=it.get("engine") or "claude",
                    parent_coordinator_id=cid,
                    ticket_id=it["ticket_id"],
                    contract_pointer=coordinator.state.contract_pointer,
                )
            except SessionLimitError:
                # Kein freier Slot mehr → restliche Tickets nicht fallen lassen, nur
                # nicht jetzt starten (der Nutzer kann nach dem Freiwerden erneut dispatchen).
                break
            coordinator.state.child_session_ids.append(child.state.session_id)
        return self._fleet_dict(coordinator)

    # --- Live-Sicht --------------------------------------------------------

    def fleet(self, coordinator_id: str) -> dict:
        return self._fleet_dict(self._require_coordinator(coordinator_id))

    # --- Steuerung ---------------------------------------------------------

    def set_paused(self, coordinator_id: str, paused: bool) -> dict:
        coordinator = self._require_coordinator(coordinator_id)
        coordinator.state.coordinator_paused = paused
        return self._fleet_dict(coordinator)

    async def reassign(
        self,
        coordinator_id: str,
        ticket_id: str,
        *,
        role: str | None = None,
        engine: str | None = None,
        model: str | None = None,
    ) -> dict:
        """Ticket auf andere Rolle/Engine umverteilen: alte Kind-Session beenden +
        frische starten (gleiches Ticket, neue Zuweisung). Die alte wird aus der Flotte
        gelöst (Audit-Log im Vault bleibt)."""
        coordinator = self._require_coordinator(coordinator_id)
        old = self._child_for_ticket(coordinator_id, ticket_id)
        if old is None:
            raise TicketNotFoundError(f"Kein Kind dieser Flotte bearbeitet {ticket_id}.")

        real = coordinator.state.project_path
        label = os.path.basename(real) or real
        new = await self._manager.create(
            project_path=real,
            initial_prompt=f"Übernimm Ticket {ticket_id} und führe die Arbeit fort.",
            # Bewusst NICHT old.state.model wiederverwenden: der Treiber überschreibt es
            # beim Start mit der vollen Modell-ID (z. B. „claude-haiku-4-5-…"), die die
            # Claude-Whitelist beim Neu-Erstellen ablehnt. None → Engine-Default.
            model=model,
            role=role if role is not None else old.state.role,
            project_name=f"{label} · {ticket_id}",
            engine=engine or old.state.engine,
            parent_coordinator_id=coordinator_id,
            ticket_id=ticket_id,
            contract_pointer=coordinator.state.contract_pointer,
        )
        # Alte Kind-Session beenden + aus der Flotte lösen (kein Doppel-Tile).
        try:
            await self._manager.stop(old.state.session_id)
        except Exception:  # noqa: BLE001 — bereits terminal o. Ä. ist unkritisch
            pass
        old.state.parent_coordinator_id = None
        ids = coordinator.state.child_session_ids
        if old.state.session_id in ids:
            ids.remove(old.state.session_id)
        ids.append(new.state.session_id)
        return self._fleet_dict(coordinator)

    # --- Vertrag -----------------------------------------------------------

    def set_contract(self, coordinator_id: str, body: str, title: str | None = None) -> dict:
        """API-Vertrag als lebende Vault-Notiz ablegen; Pointer am Koordinator + allen
        Kindern aktualisieren (gleicher Pointer, neuer Inhalt = Update-Signal)."""
        coordinator = self._require_coordinator(coordinator_id)
        result = self._vault.write(
            type="curated",
            body=body,
            title=title or f"API-Vertrag {os.path.basename(coordinator.state.project_path)}",
            session_id=coordinator_id,
            on_exists="version",
            dated=False,
        )
        pointer = result.path
        coordinator.state.contract_pointer = pointer
        for child in self._children(coordinator_id):
            child.state.contract_pointer = pointer
        return {"path": result.path, "type": result.type, "created": result.created}

    # --- intern ------------------------------------------------------------

    def _require_coordinator(self, coordinator_id: str) -> SessionRuntime:
        runtime = self._manager.get(coordinator_id)
        if runtime is None or runtime.state.role != self.ROLE:
            raise CoordinatorNotFoundError(f"Keine Koordinator-Session: {coordinator_id}.")
        return runtime

    def _children(self, coordinator_id: str) -> list[SessionRuntime]:
        return [r for r in self._manager.list() if r.state.parent_coordinator_id == coordinator_id]

    def _child_for_ticket(self, coordinator_id: str, ticket_id: str) -> SessionRuntime | None:
        for r in self._children(coordinator_id):
            if r.state.ticket_id == ticket_id:
                return r
        return None

    def _fleet_dict(self, coordinator: SessionRuntime) -> dict:
        cid = coordinator.state.session_id
        children = sorted(self._children(cid), key=lambda r: r.state.ticket_id or "")
        return {
            "coordinator": coordinator.to_read(),
            "children": [c.to_read() for c in children],
            "paused": coordinator.state.coordinator_paused,
            "contract_pointer": coordinator.state.contract_pointer,
        }
