"""PROJ-82 — Hermes-Kanban-Backend (native Ansicht über die Hermes-CLI).

Testet Schema-Validierung, das 1:1-Argument-Building der CLI-Aufrufe (via
Monkeypatch von ``_run_hermes``) und die Routen inkl. Settings-Endpunkt. Die
echte Hermes-CLI wird nie aufgerufen.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.hermes_kanban_store import HermesKanbanStore
from app.main import create_app
from app.routes import hermes_kanban as hk
from app.schemas.hermes_kanban import CreateTaskRequest


# --- Schema-Validierung -----------------------------------------------------


def test_model_and_provider_must_come_together():
    with pytest.raises(ValueError):
        CreateTaskRequest(title="t", model_override="m")  # provider fehlt
    with pytest.raises(ValueError):
        CreateTaskRequest(title="t", provider_override="p")  # model fehlt


def test_branch_or_path_no_longer_accepted():
    # workspace_mode/project/branch sind entfernt -> extra="forbid" liefert 422.
    base = {"title": "t", "workspace_path": "/home/dev/projects/foo"}
    for bad in (
        {"workspace_mode": "worktree"},
        {"workspace_mode": "worktree_path", "workspace_path": "/x"},
        {"project": "jupiter-abc"},
        {"branch": "wt/x"},
    ):
        with pytest.raises(ValueError):
            CreateTaskRequest(**{**base, **bad})


def test_workspace_path_required_and_canonical():
    # Fehlender Pfad -> 422.
    with pytest.raises(ValueError):
        CreateTaskRequest(title="t")
    # Leerer Pfad -> 422.
    with pytest.raises(ValueError):
        CreateTaskRequest(title="t", workspace_path="   ")


def test_workspace_path_rejects_outside_root(tmp_path, monkeypatch):
    import app.schemas.hermes_kanban as hk_schema

    root = tmp_path / "projects"
    root.mkdir()
    monkeypatch.setattr(hk_schema, "_WORKSPACE_ROOT", root)

    # Pfad außerhalb der Wurzel wird abgewiesen.
    with pytest.raises(ValueError):
        CreateTaskRequest(title="t", workspace_path="/etc")
    # Nicht existierender Pfad unter der Wurzel wird abgewiesen.
    with pytest.raises(ValueError):
        CreateTaskRequest(title="t", workspace_path=str(root / "nope"))
    # Die Wurzel selbst wird abgewiesen.
    with pytest.raises(ValueError):
        CreateTaskRequest(title="t", workspace_path=str(root))


def test_workspace_path_rejects_symlink_escape(tmp_path, monkeypatch):
    import app.schemas.hermes_kanban as hk_schema

    root = tmp_path / "projects"
    root.mkdir()
    # Ein echtes Projekt-Verzeichnis unter der Wurzel.
    proj = root / "ok-proj"
    proj.mkdir()
    # Ein Angriffsziel außerhalb der Wurzel.
    outside = tmp_path / "secret"
    outside.mkdir()
    # Symlink innerhalb der Wurzel zeigt nach außen.
    link = root / "evil"
    link.symlink_to(outside)
    monkeypatch.setattr(hk_schema, "_WORKSPACE_ROOT", root)

    # Der Symlink selbst ist ein Verzeichnis, aber aufgelöst liegt er außerhalb
    # der Wurzel -> muss abgewiesen werden.
    with pytest.raises(ValueError):
        CreateTaskRequest(title="t", workspace_path=str(link))


def test_workspace_path_canonicalizes(tmp_path, monkeypatch):
    import app.schemas.hermes_kanban as hk_schema

    root = tmp_path / "projects"
    root.mkdir()
    proj = root / "my-proj"
    proj.mkdir()
    monkeypatch.setattr(hk_schema, "_WORKSPACE_ROOT", root)

    # Ein Pfad mit ``..``-Segmenten, der kanonisch unter der Wurzel landet,
    # wird auf den aufgelösten Pfad normalisiert.
    sub = proj / "sub"
    sub.mkdir()
    messy = str(sub / "..")
    req = CreateTaskRequest(title="t", workspace_path=messy)
    assert req.workspace_path == str(proj)


def test_triage_excludes_initial_status():
    with pytest.raises(ValueError):
        CreateTaskRequest(title="t", workspace_path="/home/dev/projects/foo", triage=True, initial_status="blocked")


# --- CLI-Argument-Building (echte CLI wird gemockt) -------------------------


async def test_create_forces_dir_workspace(monkeypatch, tmp_path):
    # Workspace-Wurzel auf ein temporäres Verzeichnis lenken, damit der
    # kanonische Pfad ohne echtes /home/dev/projects existiert.
    import app.schemas.hermes_kanban as hk_schema

    root = tmp_path / "projects"
    root.mkdir()
    proj = root / "my-proj"
    proj.mkdir()
    monkeypatch.setattr(hk_schema, "_WORKSPACE_ROOT", root)

    captured = {}

    async def fake_run(args, timeout):
        captured["args"] = args
        captured["timeout"] = timeout
        return '{"id": "t_abc123"}'

    monkeypatch.setattr(hk, "_run_hermes", fake_run)
    req = CreateTaskRequest(
        title="PROJ-84: backend starten",
        body="Body text",
        assignee="jupiter-coordinator",
        workspace_path=str(proj),
        parents=["t_abc123"],
        priority=5,
        skills=["abc-backend"],
        initial_status="normal",
        tenant="acme",
        idempotency_key="ik1",
        max_runtime="90s",
        max_retries=2,
        model_override="opus",
        provider_override="anthropic",
        goal_mode=True,
        goal_max_turns=20,
    )
    res = await hk.create_task("jupiter-abc", req)
    assert res == {"id": "t_abc123"}
    args = captured["args"]
    assert args[:4] == ["kanban", "--board", "jupiter-abc", "create"]
    assert "--created-by" in args and args[args.index("--created-by") + 1] == "jupiter"
    assert "--json" in args
    # Workspace ist IMMER dir:<kanonischer_pfad>, kein worktree/branch mehr.
    assert "--workspace" in args
    ws_idx = args.index("--workspace")
    assert args[ws_idx + 1] == f"dir:{proj}"
    assert "--branch" not in args  # worktree-Branch existiert im neuen Contract nicht.
    assert "--project" not in args
    assert "--parent" in args and "t_abc123" in args
    assert "--model" in args and "--provider" in args
    assert "--goal" in args and "--goal-max-turns" in args
    assert captured["timeout"] == hk._T_CREATE
    assert args[-1] == "PROJ-84: backend starten"  # Titel ist letztes pos. Argument


async def test_create_omits_empty_optional_fields(monkeypatch, tmp_path):
    import app.schemas.hermes_kanban as hk_schema

    root = tmp_path / "projects"
    root.mkdir()
    proj = root / "my-proj"
    proj.mkdir()
    monkeypatch.setattr(hk_schema, "_WORKSPACE_ROOT", root)

    captured = {}

    async def fake_run(args, timeout):
        captured["args"] = args
        return "{}"

    monkeypatch.setattr(hk, "_run_hermes", fake_run)
    await hk.create_task(
        "jupiter-abc", CreateTaskRequest(title="nur Titel", workspace_path=str(proj))
    )
    args = captured["args"]
    assert "--assignee" not in args
    assert "--body" not in args
    assert "--triage" not in args
    assert "--initial-status" not in args
    assert "--workspace" in args and args[args.index("--workspace") + 1].startswith("dir:")



async def test_bulk_archive_rejects_bad_ids(monkeypatch):
    async def fake_run(args, timeout):
        return "ok"

    monkeypatch.setattr(hk, "_run_hermes", fake_run)
    with pytest.raises(Exception):  # Service wirft HTTPException 400.
        await hk.archive_bulk("jupiter-abc", ["not-a-task-id"])


# --- Routen (TestClient, anonym vor Bootstrap) ------------------------------


def _client(monkeypatch, fake_return):
    captured = {}

    async def fake_run(args, timeout):
        captured["last_args"] = args
        return fake_return

    async def fake_run_partial(args, timeout):
        captured["last_args"] = args
        return fake_return

    monkeypatch.setattr(hk, "_run_hermes", fake_run)
    monkeypatch.setattr(hk, "_run_hermes_partial", fake_run_partial)
    app = create_app()
    app.state._captured = captured
    return TestClient(app), captured


def test_get_boards_route(monkeypatch):
    client, cap = _client(monkeypatch, '[{"slug": "jupiter-abc", "name": "ABC", "is_current": true}]')
    r = client.get("/hermes-kanban/boards")
    assert r.status_code == 200
    assert r.json()[0]["slug"] == "jupiter-abc"
    assert cap["last_args"][:3] == ["kanban", "boards", "list"]


def test_get_tasks_with_filters(monkeypatch):
    client, cap = _client(monkeypatch, "[]")
    r = client.get("/hermes-kanban/tasks", params={"board": "jupiter-abc", "assignee": "all", "include_archived": "true"})
    assert r.status_code == 200
    assert "--archived" in cap["last_args"]
    assert "--assignee" not in cap["last_args"]  # "all" darf nicht durchgereicht werden.


def test_invalid_board_slug_rejected(monkeypatch):
    client, _ = _client(monkeypatch, "[]")
    r = client.get("/hermes-kanban/tasks", params={"board": "Bad Slug!"})
    assert r.status_code == 400


def test_get_tasks_route_wraps_response(monkeypatch):
    # Frontend erwartet {board, tasks: [...]} (HermesKanbanTasksResponse) — ein
    # bares Array liefert `r.tasks === undefined`, das Board bleibt leer.
    client, _ = _client(monkeypatch, '[{"id": "t_1", "title": "x", "status": "todo"}]')
    r = client.get("/hermes-kanban/tasks", params={"board": "jupiter-abc"})
    assert r.status_code == 200
    body = r.json()
    assert body["board"] == "jupiter-abc"
    assert body["tasks"][0]["id"] == "t_1"


def test_get_assignees_route_flattens_to_names(monkeypatch):
    # `hermes kanban assignees --json` liefert Objekte ({name, on_disk, counts}),
    # nicht die vom Frontend erwartete string[] — sonst rendert React ein rohes
    # Objekt als Kind und crasht ganz Jupiter (React error #31, kein Boundary).
    client, _ = _client(
        monkeypatch,
        '[{"name": "jupiter-coordinator", "on_disk": true, "counts": {"done": 6}}]',
    )
    r = client.get("/hermes-kanban/assignees", params={"board": "jupiter-abc"})
    assert r.status_code == 200
    assert r.json() == ["jupiter-coordinator"]


def test_get_task_route_normalizes_unix_timestamps(monkeypatch):
    # `hermes kanban show --json` liefert *_at als rohe Unix-Sekunden-Integer
    # (sqlite INTEGER-Spalte). `new Date(iso)` im Frontend interpretiert eine
    # nackte Zahl als Millisekunden -> Anzeige landet um 1970-01-21 statt am
    # echten Datum. Route muss in ISO-8601-Strings konvertieren.
    client, _ = _client(
        monkeypatch,
        '{"task": {"id": "t_1", "created_at": 1787173296, "started_at": null}, '
        '"events": [{"kind": "created", "created_at": 1787173296}]}',
    )
    r = client.get("/hermes-kanban/tasks/t_1", params={"board": "jupiter-abc"})
    assert r.status_code == 200
    body = r.json()
    assert body["task"]["created_at"] == "2026-08-19T21:01:36+00:00"
    assert body["task"]["started_at"] is None
    assert body["events"][0]["created_at"] == "2026-08-19T21:01:36+00:00"


def test_invalid_task_id_rejected(monkeypatch):
    client, _ = _client(monkeypatch, "{}")
    r = client.get("/hermes-kanban/tasks/xyz/log", params={"board": "jupiter-abc"})
    assert r.status_code == 400


def test_hermes_cli_error_maps_to_502(monkeypatch):
    async def boom(args, timeout):
        raise hk.HermesError("Kaputt")

    monkeypatch.setattr(hk, "_run_hermes", boom)
    client = TestClient(create_app())
    r = client.get("/hermes-kanban/boards")
    assert r.status_code == 502
    assert "Kaputt" in r.json()["detail"]


async def test_feature_lookup_reads_index(monkeypatch, tmp_path):
    monkeypatch.setattr(hk, "_REPO_ROOT", tmp_path)
    (tmp_path / "features").mkdir()
    (tmp_path / "features" / "INDEX.md").write_text(
        "| ID | Feature | ... |\n| PROJ-82 | Hermes-Kanban nativ in Jupiter (kein iFrame) | P1 | ... |\n"
    )
    res = await hk.feature_lookup("82")
    assert res["found"] is True
    assert "Hermes-Kanban" in res["title"]


def test_settings_get_and_patch(monkeypatch, tmp_path):
    store = HermesKanbanStore(str(tmp_path / "hk.yaml"))
    monkeypatch.setattr("app.routes.settings.hermes_kanban_store", store)
    client = TestClient(create_app())
    r = client.get("/settings/hermes-kanban")
    assert r.status_code == 200
    assert 5 <= r.json()["poll_interval_seconds"] <= 60
    r = client.patch("/settings/hermes-kanban", json={"poll_interval_seconds": 15})
    assert r.status_code == 200
    assert r.json()["poll_interval_seconds"] == 15
    r = client.patch("/settings/hermes-kanban", json={"poll_interval_seconds": 999})
    assert r.status_code in (400, 422)  # Pydantic 422 oder Store-ValueError 400


def test_bulk_archive_payload(monkeypatch):
    client, cap = _client(monkeypatch, '{"result": "ok"}')
    r = client.post(
        "/hermes-kanban/tasks/archive-bulk",
        params={"board": "jupiter-abc"},
        json={"ids": ["t_aaa", "t_bbb"]},
    )
    assert r.status_code == 200
    assert cap["last_args"][-2:] == ["t_aaa", "t_bbb"]  # ein Aufruf, beide IDs, kein Loop
