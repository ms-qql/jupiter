"""PROJ-56 — Kontext-Persistenz & Resume für Nicht-Claude-Engines (Codex, GLM/OpenRouter).

Deterministisch über echte Treiber (GenericCliDriver/OpenAIDriver), ein echtes SQLite-Repo
(tmp) und direkt konstruierte SessionRuntimes. Geprüft:

- Persistenz-Store: ``resume_id``/``context_status`` überleben upsert→list_all; der neue
  ``session_context``-Store speichert/liest/löscht den Verlauf; Migration auf alter DB.
- GenericCliDriver (Codex): ``start`` mit Resume-ID **primt** ohne frischen Thread zu spawnen;
  ohne ID fällt es bewusst auf den kontextlosen Frischstart zurück.
- OpenAIDriver (GLM): ``load_history`` spielt zurück, ``start`` dupliziert den System-Prompt
  nicht, ``conversation_history`` exponiert den Verlauf.
- Manager ``_resume`` engine-bewusst: Codex nutzt die persistierte ``resume_id`` (mit Kontext),
  fehlt sie → kontextlos; GLM spielt den persistierten Verlauf zurück (gedeckelt), fehlt er →
  kontextlos. ``_persist`` sichert den Verlauf nur bei SETTLED-Status (kein halber Turn).
- Claude bleibt unverändert (nativer --resume-Pfad, kein Regress).
"""
from __future__ import annotations

import asyncio
import json

import pytest

from app.config import settings
from app.db.session_index import SqliteSessionIndexRepository
from app.engine.base import EngineDriver, EventHandler, LaunchSpec
from app.engine.generic_cli_driver import GenericCliDriver
from app.engine.manager import (
    DONE,
    RUNNING,
    WAITING,
    SessionManager,
    SessionRuntime,
    SessionState,
)
from app.engine import manager as mgr_module
from app.engine.openai_driver import OpenAIDriver
from app.engine.registry import EngineProfile

PROJECT = "/home/dev/projects/jupiter"


async def _flush(mgr: SessionManager) -> None:
    for _ in range(6):
        pending = list(mgr._persist_tasks)
        if not pending:
            return
        await asyncio.gather(*pending, return_exceptions=True)


def _codex_profile() -> EngineProfile:
    return EngineProfile(
        key="codex",
        label="OpenAI Codex",
        driver="generic_cli",
        bin="/home/dev/.local/bin/codex",
        argv_template=["exec", "-m", "{model}", "--json", "-"],
        resume_argv_template=["exec", "-m", "{model}", "--json", "resume", "{resume_id}", "-"],
        adapter="codex",
        prompt_via="stdin",
        input_format="text",
        oneshot=True,
    )


# ===========================================================================
# 1) Persistenz-Store (session_index-Spalten + session_context)
# ===========================================================================


@pytest.mark.asyncio
async def test_resume_id_and_context_status_roundtrip(tmp_path):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    await repo.upsert(
        {"session_id": "s1", "status": "waiting", "engine": "codex",
         "resume_id": "thread-abc", "context_status": "mit Kontext"}
    )
    rows = {r["session_id"]: r for r in await repo.list_all()}
    assert rows["s1"]["resume_id"] == "thread-abc"
    assert rows["s1"]["context_status"] == "mit Kontext"


@pytest.mark.asyncio
async def test_session_context_save_load_delete(tmp_path):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    assert await repo.load_context("s1") is None  # noch nichts
    msgs = [{"role": "system", "content": "K"}, {"role": "user", "content": "hi"}]
    await repo.save_context("s1", json.dumps(msgs))
    assert json.loads(await repo.load_context("s1")) == msgs
    # Ersetzen (kein Duplikat, PK = session_id)
    await repo.save_context("s1", json.dumps([{"role": "user", "content": "neu"}]))
    assert len(json.loads(await repo.load_context("s1"))) == 1
    # Löschen der Session entfernt auch den Verlauf
    await repo.delete("s1")
    assert await repo.load_context("s1") is None


@pytest.mark.asyncio
async def test_migration_adds_columns_on_old_db(tmp_path):
    """Alte DB (Basis-Schema OHNE die PROJ-56-Spalten) → ALTER TABLE zieht sie idempotent nach."""
    import sqlite3

    from app.db.session_index import COLUMNS

    # Vor-PROJ-56-Schema nachstellen: alle Basisspalten außer resume_id/context_status.
    base_cols = [c for c in COLUMNS if c not in ("resume_id", "context_status")]
    ddl = ", ".join(f"{c} TEXT" if c != "session_id" else f"{c} TEXT PRIMARY KEY" for c in base_cols)
    path = str(tmp_path / "old.db")
    conn = sqlite3.connect(path)
    conn.execute(f"CREATE TABLE session_index ({ddl})")
    conn.commit()
    conn.close()
    repo = SqliteSessionIndexRepository(path)
    await repo.init()  # darf nicht crashen, legt Spalten + session_context nach
    await repo.upsert({"session_id": "s1", "status": "done", "resume_id": "t1"})
    await repo.save_context("s1", json.dumps([{"role": "user", "content": "x"}]))
    rows = {r["session_id"]: r for r in await repo.list_all()}
    assert rows["s1"]["resume_id"] == "t1"
    assert json.loads(await repo.load_context("s1"))[0]["content"] == "x"


# ===========================================================================
# 2) GenericCliDriver (Codex) — resume-primen ohne Fresh-Thread
# ===========================================================================


@pytest.mark.asyncio
async def test_generic_start_primes_resume_without_spawn():
    driver = GenericCliDriver(_codex_profile())
    events: list = []
    spec = LaunchSpec(
        session_id="s1", project_path="/p", model="gpt-5.5",
        permission_mode="default", initial_prompt="",
        resume=True, resume_id="thread-xyz",
    )
    await driver.start(spec, lambda e: events.append(e) or asyncio.sleep(0))
    # KEIN Subprozess gespawnt (Kontext hängt serverseitig an der ID), ID vorgemerkt.
    assert driver._proc is None
    assert driver.resume_id == "thread-xyz"
    assert driver.is_alive is False
    # Kein init-Event → der nächste send_input nimmt den Thread über das Resume-argv auf.
    assert events == []


@pytest.mark.asyncio
async def test_generic_start_without_resume_id_does_not_prime():
    """resume=True aber KEINE ID → bewusst kein Primen (fällt auf Frischstart-Pfad)."""
    driver = GenericCliDriver(_codex_profile())
    spec = LaunchSpec(
        session_id="s1", project_path="/p", model="gpt-5.5",
        permission_mode="default", initial_prompt="",
        resume=True, resume_id=None,
    )
    # Ohne echtes Binary würde ein Spawn scheitern; wir prüfen nur, dass der Prime-Zweig
    # NICHT greift (er würde sofort und ohne Prozess zurückkehren).
    with pytest.raises(Exception):
        await driver.start(spec, lambda e: asyncio.sleep(0))


# ===========================================================================
# 3) OpenAIDriver (GLM) — Verlauf laden/exponieren, kein Doppel-System
# ===========================================================================


@pytest.mark.asyncio
async def test_openai_load_history_and_no_duplicate_system():
    prof = EngineProfile(
        key="openrouter", label="OpenRouter", driver="openai",
        auth_env="OPENROUTER_API_KEY", api_base="https://x", api_path="/v1/chat/completions",
    )
    driver = OpenAIDriver(prof)
    history = [{"role": "system", "content": "Konstitution"}, {"role": "user", "content": "hi"},
               {"role": "assistant", "content": "hallo"}]
    driver.load_history(history)
    assert driver.conversation_history == history
    spec = LaunchSpec(
        session_id="s1", project_path="/p", model="z-ai/glm-5.2",
        permission_mode="default", initial_prompt="",  # kein Turn → keine echte API-Call
        system_prompt_append="Konstitution",
    )
    await driver.start(spec, lambda e: asyncio.sleep(0))
    # System-Prompt steckt bereits im geladenen Verlauf → NICHT erneut angehängt.
    assert [m["role"] for m in driver.conversation_history] == ["system", "user", "assistant"]


# ===========================================================================
# 4) Manager._resume — engine-bewusst
# ===========================================================================


class _RecordingDriver(EngineDriver):
    """Fake-Treiber, der den Resume-Spec + geladenen Verlauf festhält."""

    def __init__(self, *, self_resume: bool, has_history: bool) -> None:
        self._self_resume = self_resume
        self._has_history = has_history
        self.started_spec: LaunchSpec | None = None
        self.loaded_history: list[dict] | None = None
        self._msgs: list[dict] = []

    @property
    def is_alive(self) -> bool:
        return False

    @property
    def supports_self_resume(self) -> bool:
        return self._self_resume

    @property
    def conversation_history(self):
        return self._msgs if self._has_history else None

    def load_history(self, messages):
        self.loaded_history = list(messages)
        self._msgs = list(messages)

    async def start(self, spec: LaunchSpec, on_event: EventHandler) -> None:
        self.started_spec = spec

    async def send_input(self, text: str) -> None:  # pragma: no cover
        pass

    async def pause(self) -> None:  # pragma: no cover
        pass

    async def stop(self) -> None:  # pragma: no cover
        pass


class _Profile:
    def __init__(self, key: str) -> None:
        self.key = key
        self.is_claude = False
        self.driver = "generic_cli"


def _runtime(mgr: SessionManager, *, engine: str, resume_id=None) -> SessionRuntime:
    state = SessionState(
        session_id="s1", owner="dev", project_path=PROJECT, model="m",
        permission_mode="default", engine=engine, resume_id=resume_id,
    )
    return SessionRuntime(state, _RecordingDriver(self_resume=True, has_history=False),
                          on_persist=mgr._persist)


@pytest.mark.asyncio
async def test_resume_codex_uses_persisted_resume_id(tmp_path, monkeypatch):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    fake = _RecordingDriver(self_resume=True, has_history=False)
    mgr = SessionManager(repo=repo, engine_factory=lambda p: fake)
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("codex"))
    rt = _runtime(mgr, engine="codex", resume_id="thread-123")

    await mgr._resume(rt)
    await _flush(mgr)

    assert rt.state.context_status == "mit Kontext"
    assert fake.started_spec is not None
    assert fake.started_spec.resume is True
    assert fake.started_spec.resume_id == "thread-123"


@pytest.mark.asyncio
async def test_resume_codex_without_id_degrades_contextless(tmp_path, monkeypatch):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    fake = _RecordingDriver(self_resume=True, has_history=False)
    mgr = SessionManager(repo=repo, engine_factory=lambda p: fake)
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("codex"))
    rt = _runtime(mgr, engine="codex", resume_id=None)

    await mgr._resume(rt)
    await _flush(mgr)

    assert rt.state.context_status == "kontextlos (keine Resume-ID der Engine)"
    assert fake.started_spec.resume is False


@pytest.mark.asyncio
async def test_resume_glm_replays_persisted_history(tmp_path, monkeypatch):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    history = [{"role": "system", "content": "K"}, {"role": "user", "content": "vorher"},
               {"role": "assistant", "content": "geantwortet"}]
    await repo.save_context("s1", json.dumps(history))
    fake = _RecordingDriver(self_resume=False, has_history=True)
    mgr = SessionManager(repo=repo, engine_factory=lambda p: fake)
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("openrouter"))
    rt = SessionRuntime(
        SessionState(session_id="s1", owner="dev", project_path=PROJECT, model="z-ai/glm-5.2",
                     permission_mode="default", engine="openrouter"),
        fake, on_persist=mgr._persist,
    )

    await mgr._resume(rt)
    await _flush(mgr)

    assert rt.state.context_status == "mit Kontext"
    assert fake.loaded_history == history


@pytest.mark.asyncio
async def test_resume_glm_without_history_degrades_contextless(tmp_path, monkeypatch):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    fake = _RecordingDriver(self_resume=False, has_history=True)
    mgr = SessionManager(repo=repo, engine_factory=lambda p: fake)
    monkeypatch.setattr(mgr_module.engine_registry, "get", lambda key: _Profile("openrouter"))
    rt = SessionRuntime(
        SessionState(session_id="s1", owner="dev", project_path=PROJECT, model="z-ai/glm-5.2",
                     permission_mode="default", engine="openrouter"),
        fake, on_persist=mgr._persist,
    )

    await mgr._resume(rt)
    await _flush(mgr)

    assert rt.state.context_status == "kontextlos (kein gespeicherter Verlauf)"
    assert fake.loaded_history is None


# ===========================================================================
# 5) _persist — Verlauf NUR bei settled Status sichern
# ===========================================================================


@pytest.mark.asyncio
async def test_persist_saves_history_only_when_settled(tmp_path):
    repo = SqliteSessionIndexRepository(str(tmp_path / "idx.db"))
    await repo.init()
    mgr = SessionManager(repo=repo)
    fake = _RecordingDriver(self_resume=False, has_history=True)
    fake._msgs = [{"role": "user", "content": "halb"}]  # simulierter Verlauf
    rt = SessionRuntime(
        SessionState(session_id="s1", owner="dev", project_path=PROJECT, model="m",
                     permission_mode="default", engine="openrouter", status=RUNNING),
        fake, on_persist=mgr._persist,
    )

    # RUNNING (Turn läuft) → KEIN Verlauf gesichert (kein halber Turn persistiert).
    mgr._persist(rt)
    await _flush(mgr)
    assert await repo.load_context("s1") is None

    # WAITING (Turn abgeschlossen) → Verlauf wird gesichert.
    rt.state.status = WAITING
    fake._msgs = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "ok"}]
    mgr._persist(rt)
    await _flush(mgr)
    saved = json.loads(await repo.load_context("s1"))
    assert saved[-1]["content"] == "ok"


# ===========================================================================
# 6) _cap_history — Deckel gegen Overspend, System-Prompt bleibt
# ===========================================================================


def test_cap_history_keeps_system_and_newest(monkeypatch):
    monkeypatch.setattr(settings, "openai_resume_max_messages", 3)
    mgr = SessionManager()
    msgs = [{"role": "system", "content": "K"}] + [
        {"role": "user", "content": str(i)} for i in range(10)
    ]
    capped, trimmed = mgr._cap_history(msgs)
    assert trimmed is True
    assert len(capped) == 3
    assert capped[0] == {"role": "system", "content": "K"}  # System bewahrt
    assert capped[-1] == {"role": "user", "content": "9"}   # neuester bleibt


def test_cap_history_noop_when_within_limit(monkeypatch):
    monkeypatch.setattr(settings, "openai_resume_max_messages", 40)
    mgr = SessionManager()
    msgs = [{"role": "user", "content": "a"}]
    capped, trimmed = mgr._cap_history(msgs)
    assert trimmed is False
    assert capped == msgs
