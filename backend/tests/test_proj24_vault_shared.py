"""Tests für PROJ-24 (Vault als geteilter Dienst): Scope-Registry, VaultService-v1-
Bausteine (Version/Read-Excerpt/Resolve/Write-at/Audit) + /vault/v1-API-Integration."""
from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.consumers import Consumer, ConsumerRegistry, _glob_to_regex
from app.engine.vault import VaultService, VersionConflictError
from app.main import create_app

from .fakes import FakeDriver

JUP = "Agentic OS/Jupiter"


# --- Unit: Scope-Globs ------------------------------------------------------

@pytest.mark.parametrize(
    "glob,path,ok",
    [
        ("Agentic OS/Jupiter/**", "Agentic OS/Jupiter/Shared/a.md", True),
        ("Agentic OS/Jupiter/**", "Agentic OS/Jupiter/x/y/z.md", True),
        ("Agentic OS/Jupiter/**", "02 Projects/Fremd.md", False),
        ("Knowledge/*", "Knowledge/note.md", True),
        ("Knowledge/*", "Knowledge/sub/deep.md", False),  # * matcht keinen Slash
        ("**", "irgendwas/tief/drin.md", True),
    ],
)
def test_glob_matching(glob, path, ok):
    assert bool(_glob_to_regex(glob).match(path)) is ok


def test_consumer_scope_read_write_separation():
    c = Consumer(id="x", api_key="k", read=[f"{JUP}/**"], write=[f"{JUP}/Shared/**"])
    assert c.can_read(f"{JUP}/Knowledge/a.md")
    assert not c.can_write(f"{JUP}/Knowledge/a.md")  # nur lesen
    assert c.can_write(f"{JUP}/Shared/a.md")
    assert not c.can_read("02 Projects/Fremd.md")  # außerhalb Scope


def test_no_default_full_access():
    c = Consumer(id="x", api_key="k", read=[], write=[])
    assert not c.can_read("a.md") and not c.can_write("a.md")


# --- Unit: Registry (YAML + interner Konsument) -----------------------------

def _write_consumers_yaml(tmp_path, body: str) -> str:
    p = os.path.join(tmp_path, "consumers.yaml")
    open(p, "w", encoding="utf-8").write(body)
    return p


def test_registry_loads_and_authenticates(tmp_path):
    path = _write_consumers_yaml(
        tmp_path,
        f"""
consumers:
  - id: app1
    api_key: "geheim123"
    read: ["{JUP}/**"]
    write: ["{JUP}/Shared/**"]
""",
    )
    reg = ConsumerRegistry(path)
    assert reg.authenticate("app1", "geheim123") is not None
    assert reg.authenticate("app1", "falsch") is None     # falscher Key
    assert reg.authenticate("unbekannt", "x") is None      # unbekannte id
    assert reg.authenticate(None, None) is None


def test_registry_missing_file_is_empty(tmp_path):
    reg = ConsumerRegistry(os.path.join(tmp_path, "fehlt.yaml"))
    assert reg.snapshot()["consumers"] == []  # kein Crash, kein Default-Zugriff


def test_registry_broken_entry_skipped_rest_loads(tmp_path):
    path = _write_consumers_yaml(
        tmp_path,
        """
consumers:
  - id: kaputt
  - id: gut
    api_key: "k"
    read: ["**"]
""",
    )
    reg = ConsumerRegistry(path)
    assert reg.authenticate("gut", "k") is not None
    assert reg.authenticate("kaputt", "") is None


def test_builtin_internal_consumer_opt_in(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "vault_internal_consumer_key", "intern-key")
    reg = ConsumerRegistry(os.path.join(tmp_path, "fehlt.yaml"))
    jup = reg.authenticate("jupiter", "intern-key")
    assert jup is not None
    assert jup.can_read("02 Projects/Anything.md")          # ganzer Vault lesbar
    assert jup.can_write(f"{JUP}/Sessions/x.md")            # schreibt im Jupiter-Bereich
    assert not jup.can_write("02 Projects/Fremd.md")        # nicht außerhalb


# --- Unit: VaultService v1-Bausteine ---------------------------------------

@pytest.fixture()
def vault(tmp_path) -> VaultService:
    return VaultService(vault_root=str(tmp_path / "vault"))


def test_write_at_create_and_version(vault):
    res = vault.write_at(f"{JUP}/Shared/note.md", "Hallo", mode="create")
    assert res["action"] == "create" and res["version_before"] is None
    assert vault.file_version(f"{JUP}/Shared/note.md") == res["version"]


def test_write_at_create_conflict(vault):
    vault.write_at(f"{JUP}/Shared/n.md", "x", mode="create")
    with pytest.raises(FileExistsError):
        vault.write_at(f"{JUP}/Shared/n.md", "y", mode="create")


def test_write_at_overwrite_optimistic_lock(vault):
    a = vault.write_at(f"{JUP}/Shared/n.md", "v1", mode="create")
    # Falsche/fehlende base_version → Konflikt (kein stilles Überschreiben).
    with pytest.raises(VersionConflictError):
        vault.write_at(f"{JUP}/Shared/n.md", "v2", mode="overwrite")
    with pytest.raises(VersionConflictError):
        vault.write_at(f"{JUP}/Shared/n.md", "v2", mode="overwrite", base_version="falsch")
    # Korrekte base_version → erlaubt.
    b = vault.write_at(f"{JUP}/Shared/n.md", "v2", mode="overwrite", base_version=a["version"])
    assert b["version"] != a["version"]
    assert "v2" in vault.read_at(f"{JUP}/Shared/n.md")["content"]


def test_write_at_append(vault):
    vault.write_at(f"{JUP}/Shared/log.md", "Zeile1", mode="create")
    vault.write_at(f"{JUP}/Shared/log.md", "Zeile2", mode="append")
    content = vault.read_at(f"{JUP}/Shared/log.md")["content"]
    assert "Zeile1" in content and "Zeile2" in content


def test_write_at_rejects_non_md(vault):
    with pytest.raises(ValueError):
        vault.write_at(f"{JUP}/Shared/data.json", "{}", mode="create")


def test_write_at_traversal_rejected(vault):
    with pytest.raises(ValueError):
        vault.write_at("../../../tmp/evil.md", "x", mode="create")


def test_read_at_excerpt(vault):
    vault.write_at(f"{JUP}/Shared/big.md", "0123456789", mode="create")
    r = vault.read_at(f"{JUP}/Shared/big.md", mode="excerpt", offset=2, limit=4)
    assert r["content"] == "2345"
    assert r["offset"] == 2 and r["truncated"] is True


def test_read_at_full_too_large(vault):
    vault.write_at(f"{JUP}/Shared/big.md", "x" * 100, mode="create")
    with pytest.raises(ValueError):
        vault.read_at(f"{JUP}/Shared/big.md", mode="full", max_bytes=10)


def test_resolve_pointer(vault):
    vault.write_at(f"{JUP}/Shared/doc.md", "a\nb\nZIEL\nd\ne", mode="create")
    r = vault.resolve_pointer(f"{JUP}/Shared/doc.md", line=3, radius=1)
    assert "ZIEL" in r["excerpt"]
    assert r["start_line"] == 2 and r["end_line"] == 4


def test_audit_write_appends_jsonl(vault):
    vault.audit_write(
        consumer_id="app1", path=f"{JUP}/Shared/n.md", action="create",
        byte_count=5, version_before=None, version_after="abc",
    )
    audit = os.path.join(vault.vault_root, settings.vault_jupiter_subdir, settings.vault_audit_rel_path)
    line = json.loads(open(audit, encoding="utf-8").read().strip())
    assert line["consumer"] == "app1" and line["action"] == "create"


# --- API-Integration: /vault/v1 --------------------------------------------

@pytest.fixture()
def client(tmp_path) -> TestClient:
    vault = VaultService(vault_root=str(tmp_path / "vault"))
    path = _write_consumers_yaml(
        str(tmp_path),
        f"""
consumers:
  - id: writer
    api_key: "wkey"
    read: ["{JUP}/**"]
    write: ["{JUP}/Shared/**"]
  - id: reader
    api_key: "rkey"
    read: ["{JUP}/Knowledge/**"]
    write: []
""",
    )
    app = create_app(driver_factory=lambda: FakeDriver(), vault_service=vault)
    app.state.consumers = ConsumerRegistry(path)  # Test-Registry statt Modul-Singleton
    return TestClient(app)


def _h(cid, key):
    return {"X-Vault-Consumer": cid, "X-Vault-Key": key}


def test_api_requires_auth(client: TestClient):
    assert client.get("/vault/v1/read", params={"path": f"{JUP}/Shared/x.md"}).status_code == 401
    assert client.get("/vault/v1/read", params={"path": f"{JUP}/Shared/x.md"},
                      headers=_h("writer", "falsch")).status_code == 401


def test_api_write_read_roundtrip(client: TestClient):
    w = client.post("/vault/v1/write",
                    json={"path": f"{JUP}/Shared/hallo.md", "content": "Welt", "mode": "create"},
                    headers=_h("writer", "wkey"))
    assert w.status_code == 200
    version = w.json()["version"]

    r = client.get("/vault/v1/read", params={"path": f"{JUP}/Shared/hallo.md"}, headers=_h("writer", "wkey"))
    assert r.status_code == 200 and r.json()["content"].startswith("Welt")
    assert r.json()["version"] == version


def test_api_write_out_of_scope_403(client: TestClient):
    # reader darf gar nicht schreiben; writer nur in Shared/, nicht in Knowledge/.
    assert client.post("/vault/v1/write",
                       json={"path": f"{JUP}/Knowledge/x.md", "content": "x", "mode": "create"},
                       headers=_h("writer", "wkey")).status_code == 403
    assert client.post("/vault/v1/write",
                       json={"path": f"{JUP}/Shared/x.md", "content": "x", "mode": "create"},
                       headers=_h("reader", "rkey")).status_code == 403


def test_api_read_out_of_scope_403(client: TestClient):
    # reader darf nur Knowledge/ lesen, nicht Shared/.
    assert client.get("/vault/v1/read", params={"path": f"{JUP}/Shared/x.md"},
                      headers=_h("reader", "rkey")).status_code == 403


def test_api_write_create_then_create_409(client: TestClient):
    body = {"path": f"{JUP}/Shared/k.md", "content": "v1", "mode": "create"}
    assert client.post("/vault/v1/write", json=body, headers=_h("writer", "wkey")).status_code == 200
    assert client.post("/vault/v1/write", json=body, headers=_h("writer", "wkey")).status_code == 409


def test_api_overwrite_requires_version_409(client: TestClient):
    client.post("/vault/v1/write",
                json={"path": f"{JUP}/Shared/k.md", "content": "v1", "mode": "create"},
                headers=_h("writer", "wkey"))
    bad = client.post("/vault/v1/write",
                      json={"path": f"{JUP}/Shared/k.md", "content": "v2", "mode": "overwrite"},
                      headers=_h("writer", "wkey"))
    assert bad.status_code == 409
    assert "current_version" in bad.json()["detail"]


def test_api_read_missing_404(client: TestClient):
    assert client.get("/vault/v1/read", params={"path": f"{JUP}/Shared/nope.md"},
                      headers=_h("writer", "wkey")).status_code == 404


def test_api_read_traversal_400(client: TestClient):
    assert client.get("/vault/v1/read", params={"path": "../../etc/passwd"},
                      headers=_h("writer", "wkey")).status_code in (400, 403)


def test_api_search_filters_by_scope(client: TestClient):
    # writer legt je eine Datei in Shared/ und Knowledge/ an (writer darf beides lesen).
    client.post("/vault/v1/write",
                json={"path": f"{JUP}/Shared/s.md", "content": "Drachenei im Shared", "mode": "create"},
                headers=_h("writer", "wkey"))
    # Knowledge-Datei direkt über den Vault anlegen (writer darf dort nicht schreiben).
    vault = client.app.state.vault
    vault.write_at(f"{JUP}/Knowledge/k.md", "Drachenei im Knowledge", mode="create")

    # reader sucht „Drachenei" → sieht NUR den Knowledge-Treffer (Shared außerhalb Scope).
    s = client.get("/vault/v1/search", params={"q": "Drachenei"}, headers=_h("reader", "rkey"))
    assert s.status_code == 200
    paths = [h["path"] for h in s.json()["hits"]]
    assert paths == [f"{JUP}/Knowledge/k.md"]


def test_api_write_records_audit(client: TestClient):
    client.post("/vault/v1/write",
                json={"path": f"{JUP}/Shared/a.md", "content": "x", "mode": "create"},
                headers=_h("writer", "wkey"))
    vault = client.app.state.vault
    audit_rel = os.path.join(settings.vault_jupiter_subdir, settings.vault_audit_rel_path)
    audit = os.path.join(vault.vault_root, audit_rel)
    assert os.path.exists(audit)
    entry = json.loads(open(audit, encoding="utf-8").read().strip().splitlines()[-1])
    assert entry["consumer"] == "writer" and entry["path"] == f"{JUP}/Shared/a.md"
