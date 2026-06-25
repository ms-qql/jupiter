"""PROJ-13 — Git-Branch-Handling (Backend).

Isoliert: ``allowed_roots`` wird je Test auf ein tmp-Verzeichnis umgebogen, in dem
echte Git-Repos angelegt werden. Kein JWT/DB (Jupiter-Override) — Sicherheit =
``realpath``-Scope + parametrisierter Subprozess (kein Shell, kein Force-Default).
"""
from __future__ import annotations

import subprocess

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app

from .fakes import FakeDriver


def _git(cwd, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def _write(repo, name: str, text: str) -> None:
    (repo / name).write_text(text, encoding="utf-8")


@pytest.fixture
def root(tmp_path, monkeypatch):
    r = tmp_path / "roots"
    r.mkdir()
    monkeypatch.setattr(settings, "allowed_roots", [str(r)])
    return r


@pytest.fixture
def repo(root):
    """Repo mit Default-Branch ``main``, einem Commit und einem ``dev``-Branch."""
    p = root / "proj"
    p.mkdir()
    _git(p, "init", "-b", "main")
    _git(p, "config", "user.email", "test@jupiter.local")
    _git(p, "config", "user.name", "Test")
    _write(p, "README.md", "init\n")
    _git(p, "add", "-A")
    _git(p, "commit", "-m", "init")
    _git(p, "branch", "dev")
    return p


@pytest.fixture
def client(root) -> TestClient:
    return TestClient(create_app(driver_factory=lambda: FakeDriver()))


# --- Status ---------------------------------------------------------------

def test_status_non_repo(client, root):
    plain = root / "plain"
    plain.mkdir()
    res = client.get("/git/status", params={"project_path": str(plain)})
    assert res.status_code == 200
    body = res.json()
    assert body["is_repo"] is False
    assert body["branch"] is None and body["branches"] == []


def test_status_repo(client, repo):
    res = client.get("/git/status", params={"project_path": str(repo)})
    assert res.status_code == 200
    body = res.json()
    assert body["is_repo"] is True
    assert body["branch"] == "main"
    assert body["dirty"] is False
    assert set(body["branches"]) == {"main", "dev"}
    assert body["ahead"] is None  # kein Upstream → kein Netz nötig


def test_status_dirty_detected(client, repo):
    _write(repo, "README.md", "changed\n")
    res = client.get("/git/status", params={"project_path": str(repo)})
    assert res.json()["dirty"] is True


# --- Switch ---------------------------------------------------------------

def test_switch_clean(client, repo):
    res = client.post("/git/switch", json={"project_path": str(repo), "branch": "dev"})
    assert res.status_code == 200
    assert res.json()["branch"] == "dev"


def test_switch_dirty_blocks_409(client, repo):
    _write(repo, "README.md", "dirty\n")
    res = client.post("/git/switch", json={"project_path": str(repo), "branch": "dev"})
    assert res.status_code == 409
    assert "ncommittete" in res.json()["detail"]


def test_switch_unknown_branch_400(client, repo):
    res = client.post("/git/switch", json={"project_path": str(repo), "branch": "nope"})
    assert res.status_code == 400


# --- Feature-Branch -------------------------------------------------------

def test_feature_branch_created_with_schema(client, repo):
    res = client.post("/git/feature-branch", json={
        "project_path": str(repo), "feature_id": 13,
        "slug": "Git Branch Handling", "base": "main",
    })
    assert res.status_code == 200
    assert res.json()["branch"] == "specs/PROJ-13-git-branch-handling"


def test_feature_branch_existing_checks_out(client, repo):
    _git(repo, "branch", "specs/PROJ-13-foo")
    res = client.post("/git/feature-branch", json={
        "project_path": str(repo), "feature_id": 13, "slug": "foo", "base": "main",
    })
    assert res.status_code == 200
    assert res.json()["branch"] == "specs/PROJ-13-foo"


# --- Promote --------------------------------------------------------------

def test_promote_dev_into_main(client, repo):
    # Commit auf dev, dann dev → main promoten.
    _git(repo, "checkout", "dev")
    _write(repo, "feature.txt", "x\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "feat")
    _git(repo, "checkout", "main")
    res = client.post("/git/promote", json={
        "project_path": str(repo), "source": "dev", "target": "main",
    })
    assert res.status_code == 200
    assert res.json()["branch"] == "main"
    assert (repo / "feature.txt").exists()  # Merge angekommen


def test_promote_diverged_target_blocked(client, repo):
    # main bekommt einen eigenen Commit → nicht mehr Vorfahr von dev → Vorab-Check schlägt an.
    _write(repo, "main_only.txt", "m\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "main-only")
    res = client.post("/git/promote", json={
        "project_path": str(repo), "source": "dev", "target": "main",
    })
    assert res.status_code == 400
    assert "zusammenführen" in res.json()["detail"]


# --- Init / Scope ---------------------------------------------------------

def test_init_makes_repo(client, root):
    fresh = root / "fresh"
    fresh.mkdir()
    res = client.post("/git/init", json={"project_path": str(fresh)})
    assert res.status_code == 200
    assert res.json()["is_repo"] is True


def test_init_on_existing_repo_400(client, repo):
    res = client.post("/git/init", json={"project_path": str(repo)})
    assert res.status_code == 400


def test_path_outside_roots_blocked(client, repo):
    res = client.get("/git/status", params={"project_path": "/etc"})
    assert res.status_code == 400


def test_stash_then_switch(client, repo):
    _write(repo, "README.md", "dirty\n")
    res = client.post("/git/stash", json={"project_path": str(repo)})
    assert res.status_code == 200
    assert res.json()["dirty"] is False
    # nach dem Stash ist der Wechsel erlaubt
    res2 = client.post("/git/switch", json={"project_path": str(repo), "branch": "dev"})
    assert res2.status_code == 200
