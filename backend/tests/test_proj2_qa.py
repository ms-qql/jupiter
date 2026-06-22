"""QA-Regressionssuite für PROJ-2 (Vault-Anbindung).

Bildet die 6 Akzeptanzkriterien + Edge-Cases + Red-Team-Befunde dauerhaft ab.
Ergänzt `test_vault.py` (Unit/API) um die Sicherheits-/AC-Nachweise.
"""
from __future__ import annotations

import os
import tempfile

import pytest
from fastapi.testclient import TestClient

from app.engine.vault import VaultService
from app.main import create_app

from .fakes import FakeDriver

PROJECT = "/home/dev/projects/jupiter"


@pytest.fixture()
def vault(tmp_path) -> VaultService:
    return VaultService(vault_root=str(tmp_path / "vault"))


@pytest.fixture()
def client(tmp_path) -> TestClient:
    app = create_app(
        driver_factory=lambda: FakeDriver(),
        vault_service=VaultService(vault_root=str(tmp_path / "vault")),
    )
    return TestClient(app)


# --- Akzeptanzkriterien -----------------------------------------------------

def test_ac1_read_write_list(vault):
    """AC1: MD lesen, schreiben, auflisten."""
    res = vault.write(type="handover", body="Inhalt", title="Doc")
    assert vault.read_file(res.path)["body"].strip() == "Inhalt"
    assert res.path in [f["path"] for f in vault.list_files()]


def test_ac2_dedicated_subfolder_para_untouched(vault):
    """AC2: Artefakte unter Agentic OS/Jupiter/ — bestehende PARA-Struktur unangetastet."""
    res = vault.write(type="handover", body="x", title="Doc")
    assert res.path.startswith("Agentic OS/Jupiter/")
    # Außerhalb des Jupiter-Baums entsteht nichts.
    top = set(os.listdir(vault.vault_root))
    assert top == {"Agentic OS"}


def test_ac3_valid_frontmatter_required_fields(vault):
    """AC3: valides Obsidian-MD mit YAML-Frontmatter (owner, session_id, created, type)."""
    yaml = pytest.importorskip("yaml")
    res = vault.write(type="handover", body="x", title="Doc", session_id="abcd1234")
    raw = open(os.path.join(vault.vault_root, res.path), encoding="utf-8").read()
    fm = yaml.safe_load(raw.split("---\n", 2)[1])
    for key in ("owner", "session_id", "created", "type"):
        assert key in fm and fm[key]


def test_ac4_raw_and_curated_separated(vault):
    """AC4: rohe Logs (Sessions/) und kuratierte Docs (Handovers/) liegen getrennt."""
    log = vault.write(type="session_log", body="roh", title="x")
    doc = vault.write(type="handover", body="kuratiert", title="x")
    assert "/Sessions/" in log.path and "/Handovers/" in doc.path


def test_ac5_search_returns_path_and_excerpt(vault):
    """AC5: Textsuche liefert Treffer mit Dateipfad + Ausschnitt."""
    vault.write(type="handover", body="Findbares Stichwort hier.", title="x")
    hits = vault.search("stichwort")
    assert hits and hits[0]["path"].endswith(".md") and "Stichwort" in hits[0]["excerpt"]


def test_ac6_atomic_write_no_partial(vault):
    """AC6: atomare Writes — keine .tmp-Reste, vollständiger Inhalt."""
    res = vault.write(type="handover", body="vollständig", title="x")
    d = os.path.dirname(os.path.join(vault.vault_root, res.path))
    assert not any(f.endswith(".tmp") for f in os.listdir(d))
    assert "vollständig" in vault.read_file(res.path)["content"]


# --- Edge-Cases -------------------------------------------------------------

def test_edge_existing_file_no_silent_overwrite(vault):
    """Bestehende Datei → append (Default) hängt an, überschreibt NICHT still."""
    a = vault.write(type="handover", body="erste", title="Tag", session_id="s", created=_fixed())
    vault.write(type="handover", body="zweite", title="Tag", session_id="s", created=_fixed())
    content = vault.read_file(a.path)["content"]
    assert "erste" in content and "zweite" in content


def test_edge_vault_unreachable_clear_error_no_corruption(tmp_path):
    """Vault-Pfad nicht beschreibbar → klarer Fehler, keine halbe Datei."""
    root = tmp_path / "ro"
    (root / "Agentic OS" / "Jupiter" / "Handovers").mkdir(parents=True)
    v = VaultService(vault_root=str(root))
    os.chmod(root / "Agentic OS" / "Jupiter" / "Handovers", 0o500)  # read+execute, kein write
    try:
        with pytest.raises((PermissionError, OSError)):
            v.write(type="handover", body="x", title="Doc")
    finally:
        os.chmod(root / "Agentic OS" / "Jupiter" / "Handovers", 0o700)


def test_edge_umlaut_slug(vault):
    res = vault.write(type="handover", body="x", title="Lösung für Café")
    assert "loesung-fuer-cafe" in res.path


def test_edge_concurrent_sessions_separate_files(vault):
    """Zwei Sessions → getrennte Dateien (session_id im Namen), kein Datenverlust."""
    a = vault.write(type="session_log", body="A", title="proj", session_id="aaaaaaaa", created=_fixed())
    b = vault.write(type="session_log", body="B", title="proj", session_id="bbbbbbbb", created=_fixed())
    assert a.path != b.path


# --- Security / Red-Team ----------------------------------------------------

@pytest.mark.parametrize("rel", ["../../etc/passwd", "..", "a/../../b", "/etc/passwd"])
def test_sec_read_traversal_blocked(vault, rel):
    with pytest.raises((ValueError, FileNotFoundError, IsADirectoryError)):
        vault.read_file(rel)


def test_sec_symlink_escape_blocked(vault):
    """Symlink im Vault, der nach außen zeigt → realpath-Guard verweigert das Lesen."""
    secret = os.path.join(tempfile.mkdtemp(), "secret.txt")
    open(secret, "w").write("TOPSECRET")
    os.makedirs(vault.vault_root, exist_ok=True)
    os.symlink(secret, os.path.join(vault.vault_root, "leak.md"))
    with pytest.raises(ValueError):
        vault.read_file("leak.md")


def test_sec_client_session_id_cannot_escape_jupiter(vault):
    """Client-gelieferte session_id mit ../ bricht NICHT aus dem Jupiter-Baum aus."""
    for sid in ["../../../../../../tmp/pwn", "../../../../etc/x"]:
        res = vault.write(type="session_log", body="x", title="doc", session_id=sid)
        full = os.path.realpath(os.path.join(vault.vault_root, res.path))
        assert full.startswith(vault.write_root + os.sep)


def test_sec_frontmatter_injection_safe(vault):
    """Title mit YAML-Breakout-Versuch landet als escapter Wert, keine neue Top-Level-Key."""
    yaml = pytest.importorskip("yaml")
    res = vault.write(type="handover", body="B", title='evil"\n---\ninjected: true\nx: "', session_id="t")
    raw = open(os.path.join(vault.vault_root, res.path), encoding="utf-8").read()
    fm = yaml.safe_load(raw.split("---\n", 2)[1])
    assert "injected" not in fm
    assert sorted(fm) == ["created", "owner", "session_id", "title", "type"]


def test_sec_search_write_asymmetry(vault):
    """Lesen/Suchen sehen den ganzen Vault; Schreiben bleibt im Jupiter-Baum."""
    other = os.path.join(vault.vault_root, "03 Areas", "Privat.md")
    os.makedirs(os.path.dirname(other), exist_ok=True)
    open(other, "w", encoding="utf-8").write("Geheimnis")
    assert vault.search("geheimnis")  # vault-weit lesbar
    with pytest.raises(ValueError):       # aber nicht beschreibbar
        vault._resolve_write("../../03 Areas/Privat.md")


# --- API-Robustheit ---------------------------------------------------------

def test_api_list_dir_traversal_400(client: TestClient):
    assert client.get("/vault/files", params={"dir": "../../"}).status_code == 400


def test_api_search_empty_query_422(client: TestClient):
    assert client.get("/vault/search", params={"q": ""}).status_code == 422


def _fixed():
    from datetime import datetime, timezone

    return datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)
