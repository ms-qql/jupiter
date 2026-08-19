"""Hermes-Kanban-API — native Jupiter-Ansicht über die Hermes-CLI (PROJ-82).

Reine Durchreich-Schicht ohne eigene Datenhaltung: jede Anfrage ruft die
Hermes-CLI als parametrisierten Subprozess auf (nie Shell-String-Interpolation),
bekommt strukturierte Daten zurück und gibt sie durch. Die Wahrheit bleibt zu
100 % in der Hermes-Kanban-DB. Alle Aufrufe zentral in ``_run_hermes`` gekapselt
(``--board`` VOR dem Unterkommando, Zeitlimits pro Subcommand-Klasse, hartes
Abbrechen bei Hängen — Vorbild ``engine/scout.py``).

Hermes-Fehler werden als ``HermesError`` geworfen und in ``main.create_app``
auf HTTP 502 gemappt, damit das Frontend die CLI-Meldung 1:1 zeigen kann.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from ..config import settings
from ..schemas.hermes_kanban import (
    BlockRequest,
    CommentRequest,
    CreateTaskRequest,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/hermes-kanban", tags=["hermes-kanban"])

# --- Validierung ------------------------------------------------------------
_BOARD_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_TASK_ID_RE = re.compile(r"^t_[a-f0-9]+$")
_BULK_MAX = 100

# --- Zeitlimits pro Subcommand-Klasse (Tech Design D) -----------------------
_T_READ = 10.0
_T_CREATE = 20.0
_T_DISPATCH = 30.0

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class HermesError(Exception):
    """Die Hermes-CLI lieferte einen Fehler (Exit≠0) oder hing (Timeout)."""


async def _run_hermes(args: list[str], timeout: float) -> str:
    """Führt ``hermes <args>`` als parametrisierten Subprozess aus.

    Wirft ``HermesError`` bei Exit≠0 (detail = stderr/stdout der CLI) oder bei
    Timeout (Prozess wird hart abgebrochen). Gibt stdout zurück.
    """
    proc = await asyncio.create_subprocess_exec(
        settings.hermes_bin, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise HermesError(f"Hermes-CLI hat das Zeitlimit ({timeout:.0f}s) überschritten.") from exc
    if proc.returncode not in (0, None):
        msg = (err or out).decode("utf-8", "replace").strip() or f"Hermes endete mit Code {proc.returncode}."
        raise HermesError(msg)
    return out.decode("utf-8", "replace").strip()


async def _run_hermes_partial(args: list[str], timeout: float) -> str:
    """Wie ``_run_hermes``, wirft aber NICHT bei Exit≠0.

    Für Aufrufe, bei denen ein Teilfehlschlag (z. B. eine von mehreren IDs
    ungültig) normal ist und stdout trotzdem die erfolgreichen Ergebnisse
    enthält (``hermes kanban archive`` ist pro ID atomar, meldet aber über den
    Gesamt-Exit-Code einen Fehler, sobald irgendeine ID scheitert). Wirft nur
    bei Timeout.
    """
    proc = await asyncio.create_subprocess_exec(
        settings.hermes_bin, *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise HermesError(f"Hermes-CLI hat das Zeitlimit ({timeout:.0f}s) überschritten.") from exc
    return out.decode("utf-8", "replace").strip() + "\n" + err.decode("utf-8", "replace").strip()


def _board_args(board: str) -> list[str]:
    if not _BOARD_RE.match(board or ""):
        raise HTTPException(status_code=400, detail="Ungültiger Board-Slug.")
    return ["kanban", "--board", board]


def _normalize_timestamps(obj):
    # `hermes kanban ... --json` emits *_at fields as raw Unix-second integers
    # (matches the sqlite `INTEGER` column), but the frontend types declare
    # ISO strings and does `new Date(iso)`, which treats a bare number as
    # milliseconds — off by 1000x, rendering dates around 1970-01-21 instead
    # of the real date. Convert every `..._at` integer to an ISO-8601 string
    # recursively so task/events/comments/runs all get a real date.
    if isinstance(obj, dict):
        return {
            k: (
                datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
                if k.endswith("_at") and isinstance(v, int)
                else _normalize_timestamps(v)
            )
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [_normalize_timestamps(v) for v in obj]
    return obj


def _require_task_ids(ids: list[str]) -> list[str]:
    ids = [i for i in ids if i]
    if not ids:
        raise HTTPException(status_code=400, detail="Mindestens eine Task-ID erforderlich.")
    for i in ids:
        if not _TASK_ID_RE.match(i):
            raise HTTPException(status_code=400, detail=f"Ungültige Task-ID: {i}")
    return ids


# --- Service-Funktionen (keine FastAPI-Imports nötig) -----------------------


async def get_boards() -> list[dict]:
    raw = await _run_hermes(["kanban", "boards", "list", "--json"], _T_READ)
    return json.loads(raw) if raw else []


async def get_tasks(board: str, assignee: str | None, include_archived: bool) -> list[dict]:
    args = _board_args(board) + ["list", "--json"]
    if assignee and assignee.lower() not in ("alle", "all"):
        args += ["--assignee", assignee]
    if include_archived:
        args += ["--archived"]
    raw = await _run_hermes(args, _T_READ)
    return _normalize_timestamps(json.loads(raw)) if raw else []


async def get_assignees(board: str) -> list[str]:
    # `hermes kanban assignees --json` liefert Objekte ({name, on_disk, counts}),
    # nicht die vom Frontend erwartete `string[]` — ungefiltert durchgereicht
    # rendert React ein rohes Objekt als Kind und crasht hart (React error #31),
    # was mangels Error Boundary ganz Jupiter mitreißt.
    raw = await _run_hermes(_board_args(board) + ["assignees", "--json"], _T_READ)
    entries = json.loads(raw) if raw else []
    return [e["name"] if isinstance(e, dict) else e for e in entries]


async def get_projects() -> list[dict]:
    """``hermes project list`` hat KEIN JSON → Textausgabe parsen (Best-Effort)."""
    try:
        raw = await _run_hermes(["project", "list"], _T_READ)
    except HermesError as exc:
        log.warning("hermes project list fehlgeschlagen: %s", exc)
        return []
    out: list[dict] = []
    for line in raw.splitlines():
        # Kein Pre-Strip: das führende Aktiv-Zeichen ("*" oder " ") trägt Info
        # und würde von .strip() entfernt. Reale Ausgabe hat KEINE Klammern um
        # den Marker (anders als ursprünglich angenommen): "* slug  Name  [N folder(s)]".
        if not line.strip():
            continue
        m = re.match(
            r"^(?P<active>[*\s])\s(?P<slug>\S+)\s{2,}(?P<name>.+?)(?:\s*\[\d+ folder\(s\)\])?\s*$",
            line,
        )
        if m:
            out.append({
                "slug": m.group("slug"),
                "name": m.group("name").strip(),
                "active": m.group("active") == "*",
            })
    return out


async def get_task(board: str, task_id: str) -> dict:
    raw = await _run_hermes(_board_args(board) + ["show", task_id, "--json"], _T_READ)
    return _normalize_timestamps(json.loads(raw))


async def get_task_log(board: str, task_id: str) -> dict:
    raw = await _run_hermes(_board_args(board) + ["log", task_id, "--tail", "65536"], _T_READ)
    return {"log": raw}


async def create_task(board: str, req: CreateTaskRequest) -> dict:
    args = _board_args(board) + ["create"]
    if req.body:
        args += ["--body", req.body]
    if req.assignee:
        args += ["--assignee", req.assignee]
    if req.project:
        args += ["--project", req.project]
    if req.workspace_mode == "dir":
        args += ["--workspace", f"dir:{req.workspace_path}"]
    elif req.workspace_mode == "worktree":
        args += ["--workspace", "worktree", "--branch", req.branch]
    elif req.workspace_mode == "worktree_path":
        args += ["--workspace", f"worktree:{req.workspace_path}", "--branch", req.branch]
    for parent in req.parents:
        if not _TASK_ID_RE.match(parent):
            raise HTTPException(status_code=400, detail=f"Ungültige Parent-ID: {parent}")
        args += ["--parent", parent]
    if req.priority is not None:
        args += ["--priority", str(req.priority)]
    for skill in req.skills:
        args += ["--skill", skill]
    if req.initial_status != "normal":
        args += ["--initial-status", req.initial_status]
    if req.triage:
        args += ["--triage"]
    if req.tenant:
        args += ["--tenant", req.tenant]
    if req.idempotency_key:
        args += ["--idempotency-key", req.idempotency_key]
    if req.max_runtime:
        args += ["--max-runtime", req.max_runtime]
    if req.max_retries is not None:
        args += ["--max-retries", str(req.max_retries)]
    if req.model_override:
        args += ["--model", req.model_override]
    if req.provider_override:
        args += ["--provider", req.provider_override]
    if req.goal_mode:
        args += ["--goal"]
    if req.goal_max_turns is not None:
        args += ["--goal-max-turns", str(req.goal_max_turns)]
    args += ["--created-by", "jupiter", "--json", req.title]
    raw = await _run_hermes(args, _T_CREATE)
    return json.loads(raw) if raw else {}


async def dispatch(board: str) -> dict:
    raw = await _run_hermes(_board_args(board) + ["dispatch", "--json"], _T_DISPATCH)
    return json.loads(raw) if raw else {}


async def block_task(board: str, task_id: str, reason: str | None, kind: str | None) -> dict:
    args = _board_args(board) + ["block", task_id]
    if reason:
        args += [reason]
    if kind:
        args += ["--kind", kind]
    raw = await _run_hermes(args, _T_READ)
    return {"result": raw}


async def unblock_task(board: str, task_id: str, reason: str | None) -> dict:
    args = _board_args(board) + ["unblock", task_id]
    if reason:
        args += ["--reason", reason]
    raw = await _run_hermes(args, _T_READ)
    return {"result": raw}


async def archive_task(board: str, task_id: str) -> dict:
    raw = await _run_hermes(_board_args(board) + ["archive", task_id], _T_READ)
    return {"result": raw}


async def comment_task(board: str, task_id: str, text: str) -> dict:
    args = _board_args(board) + ["comment", task_id, text, "--author", "jupiter"]
    raw = await _run_hermes(args, _T_READ)
    return {"result": raw}


_ARCHIVED_RE = re.compile(r"^Archived\s+(t_[a-f0-9]+)", re.IGNORECASE)
_CANNOT_ARCHIVE_RE = re.compile(r"^cannot archive\s+(t_[a-f0-9]+)\s*:?\s*(.*)$", re.IGNORECASE)


async def archive_bulk(board: str, ids: list[str]) -> dict:
    """EIN CLI-Aufruf für alle IDs; pro-ID-Ergebnis wird aus stdout geparst.

    ``hermes kanban archive`` ist pro ID atomar, meldet aber über den
    Gesamt-Exit-Code einen Fehler, sobald irgendeine ID scheitert — die
    bereits archivierten IDs bleiben trotzdem archiviert (keine Rollback-
    Illusion). Deshalb NICHT über ``_run_hermes`` (das würfe HermesError und
    verwürfe damit die Erfolgsmeldungen), sondern über ``_run_hermes_partial``.
    """
    ids = _require_task_ids(ids)
    if len(ids) > _BULK_MAX:
        raise HTTPException(status_code=400, detail=f"Maximal {_BULK_MAX} Tasks pro Bulk-Archivierung.")
    raw = await _run_hermes_partial(_board_args(board) + ["archive", *ids], _T_READ)
    archived: list[str] = []
    failed: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _ARCHIVED_RE.match(line)
        if m:
            archived.append(m.group(1))
            continue
        m = _CANNOT_ARCHIVE_RE.match(line)
        if m:
            failed[m.group(1)] = m.group(2).strip() or line
    for i in ids:
        if i not in archived and i not in failed:
            failed[i] = "Unbekanntes Ergebnis (CLI-Ausgabe nicht zuordenbar)."
    return {"archived": archived, "failed": failed}


async def feature_lookup(proj_number: str) -> dict:
    """Best-Effort-Titel aus ``features/INDEX.md`` für die Kurzsyntax-Vorbefüllung."""
    index = _REPO_ROOT / "features" / "INDEX.md"
    try:
        text = index.read_text(encoding="utf-8")
    except OSError:
        return {"proj_number": proj_number, "title": None, "found": False}
    m = re.search(
        rf"^\|\s*PROJ-{re.escape(proj_number)}\s*\|\s*(.+?)\s*\|",
        text,
        re.MULTILINE,
    )
    title = m.group(1).strip() if m else None
    return {"proj_number": proj_number, "title": title, "found": bool(title)}


# --- Routen (dünn: validieren → Service → durchreichen) ---------------------


@router.get("/boards")
async def boards() -> list[dict]:
    return await get_boards()


@router.get("/tasks")
async def tasks(
    board: str = Query(...),
    assignee: str | None = None,
    include_archived: bool = False,
) -> dict:
    # Frontend erwartet {board, tasks: [...]} (HermesKanbanTasksResponse) — ein
    # bares Array liefert `r.tasks === undefined`, das Board bleibt dauerhaft leer.
    return {
        "board": board,
        "tasks": await get_tasks(board, assignee, include_archived),
    }


@router.get("/assignees")
async def assignees(board: str = Query(...)) -> list[str]:
    return await get_assignees(board)


@router.get("/projects")
async def projects() -> list[dict]:
    return await get_projects()


@router.get("/tasks/{task_id}/log")
async def task_log(task_id: str, board: str = Query(...)) -> dict:
    if not _TASK_ID_RE.match(task_id):
        raise HTTPException(status_code=400, detail="Ungültige Task-ID.")
    return await get_task_log(board, task_id)


@router.get("/tasks/{task_id}")
async def task_detail(task_id: str, board: str = Query(...)) -> dict:
    if not _TASK_ID_RE.match(task_id):
        raise HTTPException(status_code=400, detail="Ungültige Task-ID.")
    return await get_task(board, task_id)


@router.post("/tasks")
async def create(req: CreateTaskRequest, board: str = Query(...)) -> dict:
    return await create_task(board, req)


@router.post("/dispatch")
async def dispatch_now(board: str = Query(...)) -> dict:
    return await dispatch(board)


@router.post("/tasks/{task_id}/block")
async def block(task_id: str, req: BlockRequest, board: str = Query(...)) -> dict:
    if not _TASK_ID_RE.match(task_id):
        raise HTTPException(status_code=400, detail="Ungültige Task-ID.")
    return await block_task(board, task_id, req.reason, req.kind)


@router.post("/tasks/{task_id}/unblock")
async def unblock(task_id: str, req: BlockRequest, board: str = Query(...)) -> dict:
    if not _TASK_ID_RE.match(task_id):
        raise HTTPException(status_code=400, detail="Ungültige Task-ID.")
    return await unblock_task(board, task_id, req.reason)


@router.post("/tasks/{task_id}/archive")
async def archive(task_id: str, board: str = Query(...)) -> dict:
    if not _TASK_ID_RE.match(task_id):
        raise HTTPException(status_code=400, detail="Ungültige Task-ID.")
    return await archive_task(board, task_id)


@router.post("/tasks/{task_id}/comments")
async def comment(task_id: str, req: CommentRequest, board: str = Query(...)) -> dict:
    if not _TASK_ID_RE.match(task_id):
        raise HTTPException(status_code=400, detail="Ungültige Task-ID.")
    return await comment_task(board, task_id, req.text)


@router.post("/tasks/archive-bulk")
async def archive_bulk_route(payload: dict, board: str = Query(...)) -> dict:
    ids = payload.get("ids", [])
    if not isinstance(ids, list):
        raise HTTPException(status_code=400, detail="ids muss eine Liste sein.")
    return await archive_bulk(board, [str(i) for i in ids])


@router.get("/feature-lookup/{proj_number}")
async def feature_lookup_route(proj_number: str) -> dict:
    if not re.match(r"^\d{1,4}$", proj_number):
        raise HTTPException(status_code=400, detail="Ungültige Projektnummer.")
    return await feature_lookup(proj_number)
