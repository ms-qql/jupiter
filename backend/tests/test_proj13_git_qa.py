"""PROJ-13 — QA / Red-Team für das Git-Branch-Handling.

Ergänzt die funktionale Suite (``test_proj13_git.py``) um Angreifer-Sicht:
Option-/Command-Injection über Branch-Namen, Symlink-Scope-Escape, Detached HEAD,
sowie die numerische Korrektheit von ahead/behind gegen einen echten Upstream.
"""
from __future__ import annotations

import os
import subprocess

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import create_app

from .fakes import FakeDriver


def _git(cwd, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    ).stdout.strip()


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


# --- Red-Team: Option-/Command-Injection über Branch-Namen ----------------

@pytest.mark.parametrize("evil", [
    "--help",
    "-f",
    "--output=/tmp/jupiter_pwned",
    "; touch /tmp/jupiter_pwned",
    "$(touch /tmp/jupiter_pwned)",
    "main; rm -rf /",
])
def test_switch_rejects_injection_branch_names(client, repo, evil):
    res = client.post("/git/switch", json={"project_path": str(repo), "branch": evil})
    # Existenz-Check fängt jeden Nicht-Branch ab → 400, niemals Ausführung als Flag/Shell.
    assert res.status_code == 400
    assert not os.path.exists("/tmp/jupiter_pwned")


@pytest.mark.parametrize("field", ["source", "target"])
def test_promote_rejects_injection_refs(client, repo, field):
    payload = {"project_path": str(repo), "source": "dev", "target": "main"}
    payload[field] = "--upload-pack=touch /tmp/jupiter_pwned"
    res = client.post("/git/promote", json=payload)
    assert res.status_code == 400
    assert not os.path.exists("/tmp/jupiter_pwned")


def test_feature_branch_rejects_injection_base(client, repo):
    res = client.post("/git/feature-branch", json={
        "project_path": str(repo), "feature_id": 13, "slug": "x", "base": "--foo",
    })
    assert res.status_code == 400


def test_feature_branch_slug_is_sanitised(client, repo):
    # Pfad-/Shell-Metazeichen im Slug werden zu kebab-case normalisiert.
    res = client.post("/git/feature-branch", json={
        "project_path": str(repo), "feature_id": 7,
        "slug": "../../etc/passwd; rm -rf", "base": "main",
    })
    assert res.status_code == 200
    name = res.json()["branch"]
    assert name.startswith("specs/PROJ-7-")
    assert ".." not in name and "/" not in name.removeprefix("specs/")
    assert ";" not in name and " " not in name


# --- Red-Team: Scope-Escape -----------------------------------------------

def test_symlink_escape_blocked(client, root):
    # Symlink innerhalb der Root, der nach außen (/etc) zeigt → realpath fällt raus.
    link = root / "escape"
    try:
        os.symlink("/etc", link)
    except OSError:
        pytest.skip("Symlinks nicht verfügbar")
    res = client.get("/git/status", params={"project_path": str(link)})
    assert res.status_code == 400


def test_path_outside_roots_on_write_endpoints(client):
    for path in ("/etc", "/", "/root"):
        res = client.post("/git/switch", json={"project_path": path, "branch": "main"})
        assert res.status_code == 400


# --- Edge Cases: Detached HEAD, Stash-clean -------------------------------

def test_detached_head_detected(client, repo):
    sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", sha)
    res = client.get("/git/status", params={"project_path": str(repo)})
    body = res.json()
    assert body["detached"] is True
    assert body["is_repo"] is True
    # zurück auf einen Branch führen bleibt möglich
    back = client.post("/git/switch", json={"project_path": str(repo), "branch": "main"})
    assert back.status_code == 200 and back.json()["detached"] is False


def test_stash_clean_tree_400(client, repo):
    res = client.post("/git/stash", json={"project_path": str(repo)})
    assert res.status_code == 400


# --- ahead/behind: numerische Korrektheit gegen echten Upstream -----------

def test_ahead_behind_against_upstream(client, root):
    bare = root / "remote.git"
    bare.mkdir()
    _git(bare, "init", "--bare", "-b", "main")

    work = root / "work"
    work.mkdir()
    _git(work, "init", "-b", "main")
    _git(work, "config", "user.email", "t@j.local")
    _git(work, "config", "user.name", "T")
    _write(work, "a.txt", "1\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-m", "c1")
    _git(work, "remote", "add", "origin", str(bare))
    _git(work, "push", "-u", "origin", "main")

    # Ein lokaler Commit ohne Push → ahead=1, behind=0 (rein lokal, kein fetch).
    _write(work, "b.txt", "2\n")
    _git(work, "add", "-A")
    _git(work, "commit", "-m", "c2")

    res = client.get("/git/status", params={"project_path": str(work)})
    body = res.json()
    assert body["ahead"] == 1
    assert body["behind"] == 0
