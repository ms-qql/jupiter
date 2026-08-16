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

import asyncio
import os
import uuid
from datetime import datetime, timezone

from . import abc_phases
from .launcher import parse_index_features
from .manager import SessionLimitError, SessionManager, SessionRuntime, validate_project_path
from .policy import DENY, policy_store
from .vault import VaultService

# Synthetischer „Tool"-Name, unter dem die Trust-Policy (PROJ-10) den Dispatch-Akt
# bewertet — so kann eine deny-Regel „Ticket verteilen" hart untersagen (AC8/M1).
DISPATCH_ACTION = "CoordinatorDispatch"

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


class DispatchDeniedError(Exception):
    """Eine Trust-Policy-Regel (PROJ-10) untersagt den Dispatch (AC8/M1)."""


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
        # M1/AC8: „Ticket verteilen" durch die Trust-Policy (PROJ-10) führen. Eine
        # explizite deny-Regel untersagt den Dispatch hart; „card"/„auto-allow"
        # degradieren bewusst zur bereits vorgeschalteten Human-in-the-Loop-Freigabe
        # (der Nutzer hat den Plan freigegeben) — kein zweites Gate ohne laufende Session.
        decision = policy_store.evaluate(DISPATCH_ACTION, role=self.ROLE, project=real)
        if decision.level == DENY:
            raise DispatchDeniedError(
                decision.reason or "Dispatch ist durch die Trust-Policy untersagt."
            )

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

        dispatchable = [it for it in items if not it.get("blocked")]
        for i, it in enumerate(dispatchable):
            try:
                await self._start_child(coordinator, real, label, it)
            except SessionLimitError:
                # M3: kein freier Slot mehr → Resttickets EINREIHEN (nicht fallen lassen);
                # der Hintergrund-Drain (drain_all) rückt sie nach, sobald ein Slot frei wird.
                coordinator.state.queued_tickets.extend(dispatchable[i:])
                break
        return self._fleet_dict(coordinator)

    async def _start_child(
        self, coordinator: SessionRuntime, real: str, label: str, it: dict
    ) -> SessionRuntime:
        """Eine Spezialisten-Session für ein Ticket starten + in die Flotte hängen."""
        child = await self._manager.create(
            project_path=real,
            initial_prompt=_initial_prompt(it.get("skill"), it["ticket_id"], it.get("title", "")),
            model=it.get("model") or "sonnet",
            role=it.get("role"),
            project_name=f"{label} · {it['ticket_id']}",
            engine=it.get("engine") or "claude",
            parent_coordinator_id=coordinator.state.session_id,
            ticket_id=it["ticket_id"],
            contract_pointer=coordinator.state.contract_pointer,
        )
        coordinator.state.child_session_ids.append(child.state.session_id)
        return child

    # --- Warteschlange nachrücken (M3) -------------------------------------

    async def drain_all(self) -> None:
        """Hintergrund-Tick: für jede Flotte eingereihte Tickets starten, solange ein
        Engine-Slot frei ist. Pausierte Koordinatoren werden übersprungen. Defensiv:
        ein Fehler je Ticket bricht nur diesen Drain ab, nie den Loop."""
        for runtime in self._manager.list():
            if runtime.state.role != self.ROLE:
                continue
            if runtime.state.queued_tickets and not runtime.state.coordinator_paused:
                await self._drain(runtime)

    async def _drain(self, coordinator: SessionRuntime) -> None:
        real = coordinator.state.project_path
        label = os.path.basename(real) or real
        while coordinator.state.queued_tickets:
            if self._manager.active_count() >= self._manager.max_parallel_sessions:
                break  # kein Slot frei → später erneut versuchen
            it = coordinator.state.queued_tickets[0]
            try:
                await self._start_child(coordinator, real, label, it)
            except SessionLimitError:
                break
            except Exception:  # noqa: BLE001 — Engine/Pfad-Fehler verwirft nur dieses Ticket
                coordinator.state.queued_tickets.pop(0)
                continue
            coordinator.state.queued_tickets.pop(0)

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
        # Das Stoppen hat ggf. einen Slot frei gemacht → eingereihte Tickets nachrücken.
        await self._drain(coordinator)
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
            "queued": [t.get("ticket_id") for t in coordinator.state.queued_tickets],
        }


# --- PROJ-79: Featurezentrierter Koordinator ---------------------------------
#
# Ein Feature-Lauf ist selbst eine Koordinator-Session (role="coordinator",
# is_feature_run=True). Die internen Arbeitspakete laufen als Kind-Sessions (wie
# PROJ-22) und werden am Koordinator-State persistiert — kein neuer Persistenz-Store.
# Alle Zustandswechsel eines Laufs laufen durch ein pro Feature gehaltenes Transition-
# Gate, damit parallel endende Kind-Sessions nicht gleichzeitig denselben Lauf
# fortsetzen oder mehr als eine Blockierungs-Card erzeugen.

# Rollenbezogener Abschlussbeleg-Typ je Phase.
_PHASE_PROOF: dict[str, str] = {
    "architecture": "architecture",
    "backend": "backend",
    "frontend": "frontend",
    "qa": "qa",
    "deploy": "other",
    "document": "other",
}
# Vage Schreibbereich-Vermutung je Rolle (der Plan-Dialog zeigt sie zur Korrektur).
_ROLE_WRITE_SCOPE: dict[str, list[str]] = {
    "architect": ["features/"],
    "backend": ["backend/"],
    "frontend": ["nextjs_app/", "flutter_app/"],
    "qa": ["backend/tests/", "nextjs_app/"],
    "document": ["docs/", "features/"],
}
# Paket-Ausführungsrang (architektur → backend/frontend parallel → qa → deploy → doc).
_PACKAGE_RANK: dict[str, int] = {
    "architecture": 1,
    "backend": 2,
    "frontend": 2,
    "qa": 3,
    "deploy": 4,
    "document": 5,
}
# Paketstatus.
PK_WAIT, PK_READY, PK_RUN, PK_DONE, PK_FAIL, PK_SKIP, PK_MANUAL = (
    "wartet", "bereit", "läuft", "erfolgreich", "fehlgeschlagen", "übersprungen", "manuell",
)
# Gesamtlaufstatus.
RUN_PLANNING, RUN_RUNNING, RUN_PAUSED, RUN_BLOCKED, RUN_DONE, RUN_ABORTED = (
    "planung", "läuft", "pausiert", "blockiert", "fertig", "abgebrochen",
)

# Pro Feature serialisiertes Transition-Gate (Einzel-Worker heute; persistierte
# Revision schützt gegen Doppelverarbeitung nach Restart).
_FEATURE_LOCKS: dict[str, asyncio.Lock] = {}


def _feature_lock(coordinator_id: str) -> asyncio.Lock:
    lock = _FEATURE_LOCKS.get(coordinator_id)
    if lock is None:
        lock = asyncio.Lock()
        _FEATURE_LOCKS[coordinator_id] = lock
    return lock


def _norm_feature_id(feature_id: str) -> str:
    """„PROJ-101" → „101"; nackte Zahl bleibt."""
    fid = feature_id.strip().upper()
    if fid.startswith("PROJ-"):
        fid = fid[len("PROJ-"):]
    return fid


def build_feature_plan(project_path: str, feature_id: str) -> dict:
    """Interner Verteilungsplan für EIN Feature ``PROJ-X`` (read-only, kein Dispatch).

    Leitet aus dem INDEX-Status die noch nötigen abc-Phasen ab und baut daraus die
    internen Arbeitspakete samt Abhängigkeiten, Schreibbereichen und rollenbezogenen
    Abschlussbelegen. Nicht benötigte Disziplinen entfernt der Nutzer im Plan-Dialog;
    der Scheduler startet ohnehin nur freigegebene Pakete.
    """
    real = validate_project_path(project_path)
    num = _norm_feature_id(feature_id)
    index_path = os.path.join(real, "features", "INDEX.md")
    warnings: list[str] = []
    feature = None
    if os.path.isfile(index_path):
        try:
            with open(index_path, encoding="utf-8") as fh:
                features = parse_index_features(fh.read())
        except OSError as exc:
            warnings.append(f"INDEX.md nicht lesbar: {exc}")
            features = []
        for f in features:
            if _norm_feature_id(f["id"]) == num:
                feature = f
                break
    if feature is None:
        raise ValueError(f"Feature PROJ-{num} nicht in features/INDEX.md gefunden.")

    start_phase = abc_phases.next_phase_for_status(feature["status"])
    if start_phase is None:
        warnings.append(
            f"PROJ-{num} hat Status „{feature['status']}” — keine offene Arbeit mehr."
        )
        phases: list[str] = []
    else:
        idx = abc_phases.ABC_PHASES.index(start_phase)
        phases = list(abc_phases.ABC_PHASES[idx:])

    # Ausführungs-Reihenfolge (architektur → backend/frontend parallel → qa → …),
    # unabhängig von der ABC_PHASES-Reihenfolge (frontend vor backend).
    exec_order = [p for p in ("architecture", "backend", "frontend", "qa", "deploy", "document")
                  if p in phases]
    by_phase: dict[str, dict] = {}
    for i, phase in enumerate(exec_order, start=1):
        role = PHASE_TO_ROLE.get(phase)
        pkg = {
            "package_id": f"PROJ-{num}.{i}",
            "title": f"{phase} — PROJ-{num}",
            "role": role,
            "skill": abc_phases.skill_for_phase(phase),
            "engine": "claude",
            "model": abc_phases.model_for_phase(phase),
            "order": _PACKAGE_RANK.get(phase, i),
            "dependencies": [],
            "blocked": False,
            "blocked_reason": None,
            "write_scope": list(_ROLE_WRITE_SCOPE.get(role or "", [])),
            "required_proof": _PHASE_PROOF.get(phase, "other"),
            "status": PK_WAIT,
            "session_id": None,
            "resume_attempts": 0,
            "last_safe_state": None,
            "proof": None,
        }
        by_phase[phase] = pkg

    # Abhängigkeiten: architektur zuerst; backend+frontend parallel danach; qa wartet
    # auf beide; deploy/document warten auf qa.
    arch = by_phase.get("architecture")
    backend = by_phase.get("backend")
    frontend = by_phase.get("frontend")
    qa = by_phase.get("qa")
    for pkg in by_phase.values():
        phase = pkg["title"].split(" — ")[0]
        if phase in ("backend", "frontend") and arch:
            pkg["dependencies"].append(arch["package_id"])
        if phase == "qa":
            if backend:
                pkg["dependencies"].append(backend["package_id"])
            if frontend:
                pkg["dependencies"].append(frontend["package_id"])
        if phase in ("deploy", "document") and qa:
            pkg["dependencies"].append(qa["package_id"])

    # Stabile Reihenfolge für den Plan-Dialog: Rang, dann Paket-Nummer.
    items = sorted(by_phase.values(), key=lambda p: (p["order"], p["package_id"]))
    for p in items:
        p["order"] = items.index(p) + 1
    return {
        "project_path": real,
        "feature_id": num,
        "feature_title": feature["title"],
        "items": items,
        "warnings": warnings,
    }


class FeatureNotFoundError(Exception):
    """Keine Feature-Lauf-Koordinator-Session für das angegebene PROJ-X."""


class FeatureCoordinatorService:
    """Featurezentrierter Koordinator über dem SessionManager (PROJ-79)."""

    ROLE = "coordinator"

    def __init__(self, manager: SessionManager, vault: VaultService) -> None:
        self._manager = manager
        self._vault = vault

    # --- Plan --------------------------------------------------------------

    def feature_plan(self, project_path: str, feature_id: str) -> dict:
        return build_feature_plan(project_path, feature_id)

    # --- Dispatch ----------------------------------------------------------

    async def feature_dispatch(self, project_path: str, feature_id: str, items: list[dict]) -> dict:
        """Freigegebenen Feature-Plan dispatchen → eine Feature-Lauf-Koordinator-Session
        + die bereiten internen Arbeitspakete als Kind-Sessions."""
        real = validate_project_path(project_path)
        num = _norm_feature_id(feature_id)
        decision = policy_store.evaluate(DISPATCH_ACTION, role=self.ROLE, project=real)
        if decision.level == DENY:
            raise DispatchDeniedError(
                decision.reason or "Dispatch ist durch die Trust-Policy untersagt."
            )

        label = os.path.basename(real) or real
        coordinator = await self._manager.create(
            project_path=real,
            initial_prompt=(
                f"Du bist der Feature-Koordinator für PROJ-{num} (PROJ-79). Überwache die "
                "internen Arbeitspakete, weise fehlende Abschlussbelege zurück und eskaliere "
                "nur ein unauflösbares Scheitern als Decision Card."
            ),
            model="opus",
            role=self.ROLE,
            project_name=f"{label} · PROJ-{num}",
            engine="claude",
        )
        coordinator.state.is_feature_run = True
        coordinator.state.feature_id = num
        # Pakete aus dem freigegebenen Plan übernehmen; nur nicht-blockierte starten.
        packages = []
        for it in items:
            pkg = dict(it)
            # Alle Pakete starten als „wartet"; der Scheduler befördert bereite (Vorgänger
            # erledigt) selbstständig zu „bereit" und startet sie — keine Voreiligkeit.
            pkg.setdefault("status", PK_WAIT)
            pkg.setdefault("session_id", None)
            pkg.setdefault("resume_attempts", 0)
            pkg.setdefault("last_safe_state", None)
            pkg.setdefault("proof", None)
            packages.append(pkg)
        coordinator.state.feature_packages = packages
        coordinator.state.feature_plan = {
            "feature_title": self._plan_title(items),
            "items": [p["package_id"] for p in packages],
        }
        coordinator.state.feature_revision += 1

        await self._schedule(coordinator)
        return self._run_dict(coordinator)

    @staticmethod
    def _plan_title(items: list[dict]) -> str:
        return items[0]["title"].split(" — ")[0] if items else ""

    # --- Live-Sicht --------------------------------------------------------

    def feature_run(self, feature_id: str) -> dict:
        return self._run_dict(self._require_feature(feature_id))

    def _require_feature(self, feature_id: str) -> SessionRuntime:
        num = _norm_feature_id(feature_id)
        for runtime in self._manager.list():
            if runtime.state.is_feature_run and runtime.state.feature_id == num:
                return runtime
        raise FeatureNotFoundError(f"Keine Feature-Ausführung für PROJ-{num}.")

    # --- Steuerung ---------------------------------------------------------

    def feature_set_paused(self, feature_id: str, paused: bool) -> dict:
        coordinator = self._require_feature(feature_id)
        coordinator.state.coordinator_paused = paused
        return self._run_dict(coordinator)

    async def package_complete(self, feature_id: str, proof: dict) -> dict:
        """Strukturierten Abschlussbeleg eines Pakets annehmen + prüfen. Erst nach
        bestandener Prüfung gilt das Paket als erfolgreich und Folgepakete dürfen starten."""
        coordinator = self._require_feature(feature_id)
        async with _feature_lock(coordinator.state.session_id):
            pkg = self._package(coordinator, proof.get("package_id"))
            if pkg is None:
                raise TicketNotFoundError(f"Kein Arbeitspaket {proof.get('package_id')}.")
            validated = self._validate_proof(pkg, proof)
            if validated is None:
                raise ValueError("Abschlussbeleg unvollständig oder widersprüchlich.")
            pkg["proof"] = validated
            if validated.get("result_state") == "success":
                pkg["status"] = PK_DONE
            else:
                pkg["status"] = PK_FAIL
            coordinator.state.feature_revision += 1
            if pkg["status"] == PK_FAIL:
                await self._block(coordinator, pkg, "Abschlussbeleg meldet Fehlschlag.")
            else:
                await self._schedule(coordinator)
        return self._run_dict(coordinator)

    async def feature_decision(self, feature_id: str, action: str, package_id: str | None) -> dict:
        """„retry" / „manual" / „abort" auf die eine Blockierungs-Card."""
        coordinator = self._require_feature(feature_id)
        async with _feature_lock(coordinator.state.session_id):
            blocker = coordinator.state.feature_blocker
            if action in ("retry", "manual") and blocker is None:
                raise ValueError("Keine offene Blockierungsentscheidung für diesen Lauf.")
            target_id = package_id or (blocker.get("package_id") if blocker else None)
            if action == "retry":
                pkg = self._package(coordinator, target_id)
                if pkg is None:
                    raise TicketNotFoundError(f"Kein Arbeitspaket {target_id}.")
                pkg["status"] = PK_WAIT
                pkg["proof"] = None
                pkg["resume_attempts"] = pkg.get("resume_attempts", 0) + 1
                coordinator.state.feature_blocker = None
                self._resolve_blocker_card(coordinator)
                coordinator.state.coordinator_paused = False  # Blockierung war ein Pausieren
                coordinator.state.feature_revision += 1
                await self._schedule(coordinator)
            elif action == "manual":
                pkg = self._package(coordinator, target_id)
                if pkg is None:
                    raise TicketNotFoundError(f"Kein Arbeitspaket {target_id}.")
                pkg["status"] = PK_MANUAL
                pkg["session_id"] = None
                coordinator.state.feature_blocker = None
                self._resolve_blocker_card(coordinator)
                coordinator.state.feature_revision += 1
                # Manual-Session wird vom Nutzer im Cockpit geöffnet; der Lauf bleibt pausiert,
                # bis der Beleg über /complete eingespielt wird.
                coordinator.state.coordinator_paused = True
            elif action == "abort":
                await self._abort(coordinator)
            else:
                raise ValueError(f"Unbekannte Aktion: {action}")
        return self._run_dict(coordinator)

    # --- Scheduler (Hintergrund-Tick) --------------------------------------

    async def schedule_feature_runs(self) -> None:
        """Für jede laufende Feature-Ausführung: bereite Pakete starten, terminale
        Kind-Sessions auf Abschlussbeleg prüfen, Gesamtlauf abschließen."""
        for runtime in self._manager.list():
            if not runtime.state.is_feature_run:
                continue
            if runtime.state.coordinator_paused or runtime.state.feature_blocker:
                continue
            async with _feature_lock(runtime.state.session_id):
                await self._schedule(runtime)
                await self._reap_children(runtime)

    async def _schedule(self, coordinator: SessionRuntime) -> None:
        """Bereite Pakete starten (freie Slots), Gesamtlauf abschließen."""
        num = coordinator.state.feature_id
        real = coordinator.state.project_path
        label = os.path.basename(real) or real
        for pkg in coordinator.state.feature_packages:
            if pkg["status"] in (PK_WAIT, PK_READY) and self._deps_done(coordinator, pkg):
                pkg["status"] = PK_READY
                if self._manager.active_count() >= self._manager.max_parallel_sessions:
                    continue  # Slot frei → nächster Tick
                await self._start_package(coordinator, real, label, pkg, num)
        if all(p["status"] == PK_DONE for p in coordinator.state.feature_packages) \
                and coordinator.state.feature_packages:
            coordinator.state.feature_blocker = None
            self._resolve_blocker_card(coordinator)

    def _deps_done(self, coordinator: SessionRuntime, pkg: dict) -> bool:
        by_id = {p["package_id"]: p for p in coordinator.state.feature_packages}
        for dep in pkg.get("dependencies", []):
            dep_pkg = by_id.get(dep)
            if dep_pkg is None or dep_pkg["status"] != PK_DONE:
                return False
        return True

    async def _start_package(
        self, coordinator: SessionRuntime, real: str, label: str, pkg: dict, num: str
    ) -> None:
        skill = pkg.get("skill")
        prompt = f"/{skill} {num}" if skill else f"Bearbeite Arbeitspaket {pkg['package_id']}."
        child = await self._manager.create(
            project_path=real,
            initial_prompt=prompt,
            model=pkg.get("model") or "sonnet",
            role=pkg.get("role"),
            project_name=f"{label} · {pkg['package_id']}",
            engine=pkg.get("engine") or "claude",
            parent_coordinator_id=coordinator.state.session_id,
            ticket_id=f"PROJ-{num}",
            contract_pointer=coordinator.state.contract_pointer,
        )
        pkg["session_id"] = child.state.session_id
        pkg["status"] = PK_RUN
        coordinator.state.child_session_ids.append(child.state.session_id)
        coordinator.state.feature_revision += 1

    async def _reap_children(self, coordinator: SessionRuntime) -> None:
        """Terminale Kind-Sessions eines Pakets prüfen: mit gültigem Beleg → erfolgreich,
        sonst → fehlgeschlagen + Blockierung (kein „Prozess beendet = fertig")."""
        from .manager import DONE, ERROR  # lazily, um Import-Runde zu vermeiden

        by_session: dict[str, dict] = {
            p["session_id"]: p for p in coordinator.state.feature_packages if p.get("session_id")
        }
        for pkg in list(by_session.values()):
            if pkg["status"] != PK_RUN:
                continue
            child = self._manager.get(pkg["session_id"])
            if child is None:
                pkg["status"] = PK_FAIL
                pkg["last_safe_state"] = "Session nicht auffindbar."
                await self._block(coordinator, pkg, "Kind-Session nicht auffindbar.")
                continue
            if child.state.status in (DONE, ERROR):
                # Kein Abschlussbeleg → nicht als erfolgreich zählen (AC).
                if pkg.get("proof") and pkg["proof"].get("result_state") == "success":
                    pkg["status"] = PK_DONE
                else:
                    pkg["status"] = PK_FAIL
                    pkg["last_safe_state"] = f"Session endete ({child.state.status}) ohne Beleg."
                    await self._block(coordinator, pkg, pkg["last_safe_state"])

    # --- Blockierung / Abschlussbeleg --------------------------------------

    @staticmethod
    def _validate_proof(pkg: dict, proof: dict) -> dict | None:
        """Rollenbezogenen Abschlussbeleg grob prüfen. None = unvollständig/widersprüchlich."""
        if proof.get("package_id") != pkg["package_id"]:
            return None
        if proof.get("result_state") not in ("success", "failed"):
            return None
        if proof.get("result_state") == "success":
            # Pflicht: Artefakte + mindestens eine Prüfung mit Ergebnis.
            if not proof.get("artifacts"):
                return None
            checks = proof.get("checks") or []
            if not any(c.get("result") for c in checks):
                return None
        return proof

    async def _block(self, coordinator: SessionRuntime, pkg: dict, cause: str) -> None:
        """Gesamtlauf atomar pausieren + genau eine persistierte Blockierungs-Card."""
        coordinator.state.coordinator_paused = True
        coordinator.state.feature_blocker = {
            "package_id": pkg["package_id"],
            "cause": cause,
            "last_safe_state": pkg.get("last_safe_state"),
            "decision_id": str(uuid.uuid4()),
        }
        coordinator.state.feature_revision += 1
        self._add_blocker_card(coordinator, pkg, cause)

    def _add_blocker_card(self, coordinator: SessionRuntime, pkg: dict, cause: str) -> None:
        from .decisions import OPEN, PendingDecision

        decision_id = coordinator.state.feature_blocker["decision_id"]
        card = PendingDecision(
            decision_id=decision_id,
            session_id=coordinator.state.session_id,
            tool_name="FeatureCoordinator",
            action=f"Arbeitspaket {pkg['package_id']} nicht fortsetzbar — Entscheidung nötig",
            excerpt=cause,
            rationale=(
                f"PROJ-{coordinator.state.feature_id}: {pkg['package_id']} konnte nach "
                f"ausgeschöpfter Wiederaufnahme nicht mit Abschlussbeleg abgeschlossen werden."
            ),
            context={
                "feature_id": coordinator.state.feature_id,
                "package_id": pkg["package_id"],
                "role": pkg.get("role"),
                "last_safe_state": pkg.get("last_safe_state"),
            },
            state=OPEN,
            card_type="feature_blocker",
            tool_input={"actions": ["retry", "manual", "abort"]},
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        coordinator.pending[decision_id] = card

    def _resolve_blocker_card(self, coordinator: SessionRuntime) -> None:
        blocker = coordinator.state.feature_blocker
        if blocker is None:
            return
        card = coordinator.pending.get(blocker.get("decision_id"))
        if card is not None:
            card.state = "obsolete"

    async def _abort(self, coordinator: SessionRuntime) -> None:
        for sid in list(coordinator.state.child_session_ids):
            child = self._manager.get(sid)
            if child is not None and child.state.status not in ("done", "error", "aborted"):
                try:
                    await self._manager.stop(sid)
                except Exception:  # noqa: BLE001
                    pass
        coordinator.state.feature_blocker = None
        self._resolve_blocker_card(coordinator)
        coordinator.state.feature_aborted = True
        coordinator.state.feature_revision += 1

    # --- intern ------------------------------------------------------------

    def _package(self, coordinator: SessionRuntime, package_id: str | None) -> dict | None:
        if not package_id:
            return None
        for p in coordinator.state.feature_packages:
            if p["package_id"] == package_id:
                return p
        return None

    def _run_dict(self, coordinator: SessionRuntime) -> dict:
        packages = [
            {
                "package_id": p["package_id"],
                "title": p["title"],
                "role": p.get("role"),
                "skill": p.get("skill"),
                "engine": p.get("engine") or "claude",
                "model": p.get("model"),
                "status": p["status"],
                "dependencies": list(p.get("dependencies", [])),
                "write_scope": list(p.get("write_scope", [])),
                "required_proof": p.get("required_proof", "other"),
                "session_id": p.get("session_id"),
                "resume_attempts": p.get("resume_attempts", 0),
                "last_safe_state": p.get("last_safe_state"),
                "proof": p.get("proof"),
            }
            for p in coordinator.state.feature_packages
        ]
        if coordinator.state.feature_blocker:
            status = RUN_BLOCKED
        elif coordinator.state.feature_aborted:
            status = RUN_ABORTED
        elif coordinator.state.coordinator_paused:
            status = RUN_PAUSED
        elif packages and all(p["status"] == PK_DONE for p in packages):
            status = RUN_DONE
        elif packages:
            status = RUN_RUNNING
        else:
            status = RUN_PLANNING
        return {
            "feature_id": coordinator.state.feature_id or "",
            "status": status,
            "coordinator": coordinator.to_read(),
            "packages": packages,
            "paused": coordinator.state.coordinator_paused,
            "revision": coordinator.state.feature_revision,
            "blocker": coordinator.state.feature_blocker,
        }
