"""Tests für PROJ-6 (Knappheits-Konstitution): Resolver + API-Integration."""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.engine.constitution import (
    combine_with_extra,
    is_valid_role,
    list_roles,
    resolve_constitution,
)
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


# --- Resolver-Unit-Tests (isoliert, tmp-Verzeichnis) ------------------------

def _write(path: str, text: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)


def test_global_only(tmp_path):
    _write(str(tmp_path / "global.md"), "GLOBAL-REGELN")
    r = resolve_constitution(None, str(tmp_path))
    assert r.text == "GLOBAL-REGELN"
    assert r.source == "global"
    assert r.role is None


def test_role_append(tmp_path):
    _write(str(tmp_path / "global.md"), "GLOBAL")
    _write(str(tmp_path / "roles" / "backend.md"), "BACKEND-ZUSATZ")
    r = resolve_constitution("backend", str(tmp_path))
    assert r.text == "GLOBAL\n\nBACKEND-ZUSATZ"
    assert r.source == "global+rolle:backend"


def test_role_replace(tmp_path):
    _write(str(tmp_path / "global.md"), "GLOBAL")
    _write(str(tmp_path / "roles" / "wild.md"), "<!-- mode: replace -->\nNUR-WILD")
    r = resolve_constitution("wild", str(tmp_path))
    assert r.text == "NUR-WILD"
    assert r.source == "rolle:wild (replace)"


def test_role_without_file_falls_back_to_global(tmp_path):
    _write(str(tmp_path / "global.md"), "GLOBAL")
    r = resolve_constitution("ghost", str(tmp_path))
    assert r.text == "GLOBAL"
    assert r.source == "global"


def test_missing_global_is_empty_not_fatal(tmp_path):
    r = resolve_constitution(None, str(tmp_path))
    assert r.text == ""
    assert r.source == "leer"


def test_invalid_role_raises(tmp_path):
    with pytest.raises(ValueError):
        resolve_constitution("../etc/passwd", str(tmp_path))


def test_role_name_validation():
    assert is_valid_role("backend") and is_valid_role("abc-123_X")
    assert not is_valid_role("../x") and not is_valid_role("bad name") and not is_valid_role("")


def test_combine_with_extra():
    assert combine_with_extra("KON", "EXTRA") == "KON\n\nEXTRA"
    assert combine_with_extra("KON", None) == "KON"
    assert combine_with_extra("", "EXTRA") == "EXTRA"


def test_list_roles(tmp_path):
    _write(str(tmp_path / "roles" / "a.md"), "x")
    _write(str(tmp_path / "roles" / "b.md"), "y")
    assert list_roles(str(tmp_path)) == ["a", "b"]


# --- Mitgelieferter Default-Store -------------------------------------------

def test_shipped_global_constitution_present():
    from app.config import settings

    r = resolve_constitution(None, settings.constitution_dir)
    assert r.source == "global" and len(r.text) > 0
    assert "architect" in list_roles(settings.constitution_dir)


# --- API-Integration --------------------------------------------------------

@pytest.fixture()
def client() -> TestClient:
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


def test_session_injects_global_constitution(client: TestClient):
    sid = client.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "x"}).json()["session_id"]
    detail = client.get(f"/sessions/{sid}").json()
    assert detail["role"] is None
    assert detail["constitution_source"] == "global"
    eff = client.get(f"/sessions/{sid}/constitution").json()
    assert eff["source"] == "global" and len(eff["text"]) > 0


def test_session_with_role_override(client: TestClient):
    sid = client.post(
        "/sessions", json={"project_path": PROJECT, "initial_prompt": "x", "role": "architect"}
    ).json()["session_id"]
    eff = client.get(f"/sessions/{sid}/constitution").json()
    assert eff["source"] == "global+rolle:architect"
    assert "Architektur" in eff["text"]


def test_extra_system_prompt_appended_after_constitution(client: TestClient):
    sid = client.post(
        "/sessions",
        json={"project_path": PROJECT, "initial_prompt": "x", "extra_system_prompt": "ZUSATZXYZ"},
    ).json()["session_id"]
    eff = client.get(f"/sessions/{sid}/constitution").json()
    assert eff["text"].endswith("ZUSATZXYZ")
    assert len(eff["text"]) > len("ZUSATZXYZ")  # Konstitution bleibt davor erhalten


def test_invalid_role_at_create_422(client: TestClient):
    r = client.post("/sessions", json={"project_path": PROJECT, "initial_prompt": "x", "role": "bad name"})
    assert r.status_code == 422


def test_constitution_overview(client: TestClient):
    data = client.get("/constitution").json()
    assert len(data["global_text"]) > 0
    assert "architect" in data["roles"]


def test_constitution_role_preview(client: TestClient):
    data = client.get("/constitution/architect").json()
    assert data["source"] == "global+rolle:architect"


def test_constitution_invalid_role_400(client: TestClient):
    assert client.get("/constitution/...").status_code == 400
