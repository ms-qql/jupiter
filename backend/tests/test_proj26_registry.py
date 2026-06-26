"""PROJ-26 — Marktplatz/Registry für Rollen/Skills/Agenten.

Deckt die Akzeptanzkriterien + Edge Cases ab:
- Durchsuchbarer Katalog mit Status (installed/active/inactive).
- Import zweistufig: Vorschau (NICHT aktiv) → Bestätigen (aktiviert, Human-in-the-Loop).
- Capability-/Policy-Vorschau: konservative Default-Policy (card/deny — nie auto-allow);
  unbekannte/gefährliche Tools → deny + „eingeschränkt lauffähig".
- Defektes/inkompatibles Paket wird beim Import abgewiesen (kein Teil-Import).
- Aktiv = Datei am Resolver-Pfad (Rolle landet in constitution_dir/roles → list_roles sieht sie).
- Versionierung + Rollback; ID-Kollision → neue Version statt stillem Überschreiben.
- Export → re-importierbares .jupkg.
- owner kommt serverseitig (Token/Default), nicht aus dem Client.
"""
from __future__ import annotations

import io
import zipfile

import pytest
import yaml
from fastapi.testclient import TestClient

from app.config import settings
from app.engine.constitution import list_roles
from app.engine.marketplace import SCHEMA_VERSION, registry_store
from app.main import create_app

from .fakes import FakeDriver


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    # Registry-Wurzel + Konstitutions-Roots auf tmp biegen (nie echte Dateien anfassen).
    monkeypatch.setattr(registry_store, "_root", str(tmp_path / "registry"))
    monkeypatch.setattr(settings, "constitution_dir", str(tmp_path / "constitution"))
    app = create_app(driver_factory=lambda: FakeDriver())
    with TestClient(app) as c:
        yield c


def _jupkg(
    *,
    entry_id="test-role",
    typ="role",
    name="Test-Rolle",
    capabilities=None,
    schema_version=SCHEMA_VERSION,
    version="1.0.0",
    definition="# Test-Rolle\nSei knapp.",
    omit_definition=False,
) -> bytes:
    manifest = {
        "schema_version": schema_version,
        "id": entry_id,
        "typ": typ,
        "name": name,
        "beschreibung": "Eine Test-Definition.",
        "version": version,
        "capabilities": capabilities if capabilities is not None else ["Read", "Grep"],
    }
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("manifest.yaml", yaml.safe_dump(manifest, allow_unicode=True))
        if not omit_definition:
            zf.writestr("definition.md", definition)
    return buf.getvalue()


def _preview(client, data) -> dict:
    r = client.post(
        "/registry/import", files={"file": ("pkg.jupkg", data, "application/octet-stream")}
    )
    return r


def _import_active(client, **kw) -> dict:
    """Vollständiger Import: Vorschau → Bestätigen. Liefert den aktiven Eintrag."""
    prev = _preview(client, _jupkg(**kw))
    assert prev.status_code == 200, prev.text
    token = prev.json()["token"]
    r = client.post("/registry/import/confirm", json={"token": token})
    assert r.status_code == 200, r.text
    return r.json()


# ===========================================================================
# Katalog
# ===========================================================================

def test_catalog_empty_on_first_start(client: TestClient):
    r = client.get("/registry/catalog")
    assert r.status_code == 200
    assert r.json() == {"entries": []}


def test_catalog_lists_imported_entry_with_status(client: TestClient):
    _import_active(client)
    r = client.get("/registry/catalog")
    entries = r.json()["entries"]
    assert len(entries) == 1
    e = entries[0]
    assert e["id"] == "test-role"
    assert e["typ"] == "role"
    assert e["status"] == "active"


def test_catalog_filters_by_type_status_query(client: TestClient):
    _import_active(client, entry_id="rolle-a", typ="role", name="Alpha")
    _import_active(client, entry_id="skill-b", typ="skill", name="Beta")
    assert len(client.get("/registry/catalog?typ=role").json()["entries"]) == 1
    assert len(client.get("/registry/catalog?typ=skill").json()["entries"]) == 1
    assert len(client.get("/registry/catalog?query=alph").json()["entries"]) == 1
    assert client.get("/registry/catalog?status=inactive").json()["entries"] == []


# ===========================================================================
# Import: zweistufig, Validierung, Capability-Vorschau
# ===========================================================================

def test_import_preview_does_not_activate(client: TestClient):
    r = _preview(client, _jupkg())
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["verified"] is False  # Quelle nicht verifiziert
    assert body["default_policy"] in ("card", "deny")  # nie auto-allow
    assert any("nicht verifiziert" in w.lower() for w in body["warnings"])
    # Noch nicht im Katalog — Vorschau aktiviert nichts.
    assert client.get("/registry/catalog").json()["entries"] == []


def test_import_confirm_activates_and_places_role_at_resolver(client: TestClient):
    entry = _import_active(client, entry_id="mein-architekt", typ="role")
    assert entry["status"] == "active"
    # AC: aktive Rolle steht dem Konstitutions-Resolver (Sessions/Launcher) zur Verfügung.
    assert "mein-architekt" in list_roles(settings.constitution_dir)


def test_readonly_caps_get_card_policy(client: TestClient):
    body = _preview(client, _jupkg(capabilities=["Read", "Grep"])).json()
    assert body["default_policy"] == "card"  # konservativ, nie auto-allow


def test_unknown_dangerous_tool_gets_deny_and_limited(client: TestClient):
    body = _preview(client, _jupkg(capabilities=["Read", "TotalWorldDomination"])).json()
    assert body["default_policy"] == "deny"
    assert any("gefährlich" in w.lower() or "unbekannt" in w.lower() for w in body["warnings"])
    entry = _import_active(client, capabilities=["Read", "TotalWorldDomination"])
    assert entry["limited"] is True  # „eingeschränkt lauffähig"


def test_corrupt_package_rejected(client: TestClient):
    r = _preview(client, b"das-ist-kein-zip")
    assert r.status_code == 400
    assert "Paket" in r.json()["detail"]


def test_incompatible_schema_version_rejected(client: TestClient):
    r = _preview(client, _jupkg(schema_version="9.0"))
    assert r.status_code == 400
    assert "Schema-Version" in r.json()["detail"]
    # kein Teil-Import — Katalog bleibt leer
    assert client.get("/registry/catalog").json()["entries"] == []


def test_missing_definition_rejected(client: TestClient):
    r = _preview(client, _jupkg(omit_definition=True))
    assert r.status_code == 400
    assert "definition.md" in r.json()["detail"]


def test_empty_upload_rejected(client: TestClient):
    r = _preview(client, b"")
    assert r.status_code == 400


# ===========================================================================
# Toggle / Lifecycle / Resolver-Schutz
# ===========================================================================

def test_toggle_active_inactive_round_trip(client: TestClient):
    _import_active(client, entry_id="r1", typ="role")
    assert "r1" in list_roles(settings.constitution_dir)
    off = client.patch("/registry/role/r1/toggle").json()
    assert off["status"] == "inactive"
    assert "r1" not in list_roles(settings.constitution_dir)  # Resolver-Datei entfernt
    on = client.patch("/registry/role/r1/toggle").json()
    assert on["status"] == "active"
    assert "r1" in list_roles(settings.constitution_dir)


def test_install_activates_existing(client: TestClient):
    _import_active(client, entry_id="r2", typ="role")
    client.patch("/registry/role/r2/toggle")  # → inactive
    r = client.post("/registry/role/r2/install")
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_foreign_resolver_file_not_overwritten(client: TestClient, tmp_path):
    # Eine von Hand gepflegte Konstitutions-Rolle existiert bereits am Resolver-Pfad.
    import os

    roles_dir = os.path.join(settings.constitution_dir, "roles")
    os.makedirs(roles_dir, exist_ok=True)
    handcrafted = os.path.join(roles_dir, "architect.md")
    with open(handcrafted, "w", encoding="utf-8") as fh:
        fh.write("HANDGEPFLEGT — nicht überschreiben")
    # Import einer gleichnamigen Rolle → Aktivierung muss die fremde Datei schützen (409).
    prev = _preview(client, _jupkg(entry_id="architect", typ="role"))
    token = prev.json()["token"]
    r = client.post("/registry/import/confirm", json={"token": token})
    assert r.status_code == 409
    with open(handcrafted, encoding="utf-8") as fh:
        assert fh.read() == "HANDGEPFLEGT — nicht überschreiben"


# ===========================================================================
# Versionierung / Rollback / Kollision
# ===========================================================================

def test_id_collision_creates_new_version_not_overwrite(client: TestClient):
    _import_active(client, entry_id="dup", typ="role", version="1.0.0", definition="V1")
    prev = _preview(client, _jupkg(entry_id="dup", typ="role", version="2.0.0", definition="V2"))
    assert prev.json()["collision"] is True
    token = prev.json()["token"]
    r = client.post("/registry/import/confirm", json={"token": token})
    assert r.status_code == 200
    detail = client.get("/registry/role/dup").json()
    assert detail["definition"] == "V2"
    versions = [v["version"] for v in detail["versions"]]
    assert "1.0.0" in versions  # alte Version bewahrt (kein stilles Überschreiben)


def test_rollback_restores_previous_version(client: TestClient):
    _import_active(client, entry_id="dup2", typ="role", version="1.0.0", definition="ERSTE")
    prev = _preview(client, _jupkg(entry_id="dup2", typ="role", version="2.0.0", definition="ZWEITE"))
    client.post("/registry/import/confirm", json={"token": prev.json()["token"]})
    assert client.get("/registry/role/dup2").json()["definition"] == "ZWEITE"
    r = client.post("/registry/role/dup2/rollback", json={"version": "1.0.0"})
    assert r.status_code == 200
    assert client.get("/registry/role/dup2").json()["definition"] == "ERSTE"


def test_rollback_unknown_version_404(client: TestClient):
    _import_active(client, entry_id="r3", typ="role")
    r = client.post("/registry/role/r3/rollback", json={"version": "9.9.9"})
    assert r.status_code == 404


# ===========================================================================
# Export / Delete / Detail / owner
# ===========================================================================

def test_export_roundtrip(client: TestClient):
    _import_active(client, entry_id="exp", typ="role", definition="EXPORT-MICH")
    r = client.get("/registry/role/exp/export")
    assert r.status_code == 200
    assert r.headers["content-disposition"].endswith('"exp.jupkg"')
    # Re-Import des Exports in einen anderen Eintrag möglich (portierbar).
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert "manifest.yaml" in zf.namelist()
        assert zf.read("definition.md").decode() == "EXPORT-MICH"


def test_delete_removes_entry_and_resolver_file(client: TestClient):
    _import_active(client, entry_id="del", typ="role")
    assert "del" in list_roles(settings.constitution_dir)
    r = client.delete("/registry/role/del")
    assert r.status_code == 204
    assert client.get("/registry/role/del").status_code == 404
    assert "del" not in list_roles(settings.constitution_dir)


def test_detail_unknown_404(client: TestClient):
    assert client.get("/registry/role/gibtsnicht").status_code == 404


def test_owner_comes_from_server_not_client(client: TestClient):
    # Anonymer Vor-Bootstrap-Nutzer → owner == default_owner, nie aus dem Client.
    entry = _import_active(client, entry_id="own", typ="role")
    assert entry["owner"] == settings.default_owner


def test_unknown_type_rejected(client: TestClient):
    assert client.get("/registry/banane/x").status_code == 404


# ===========================================================================
# Red-Team — dokumentierte offene Befunde (xfail bis Backend-Fix)
# ===========================================================================

@pytest.mark.xfail(reason="BUG-26-1: kein Dekomprimierungs-Limit (.jupkg-Zip-Bombe)", strict=False)
def test_decompression_bomb_rejected(client: TestClient):
    """Ein kleines, stark komprimiertes Paket darf den Server nicht über die
    entpackte Größe fluten. Edge Case ‚Manipuliertes Paket': Validierung muss greifen.
    Aktuell prüft nur die KOMPRIMIERTE Upload-Größe (2 MB) — die entpackte
    definition.md ist ungedeckelt. Erwartet: Ablehnung (413/400)."""
    bomb = _jupkg(definition="A" * (4 * 1024 * 1024))  # ~4 MB entpackt, wenige KB auf der Leitung
    assert len(bomb) < 2 * 1024 * 1024  # umgeht den Upload-Cap
    r = _preview(client, bomb)
    assert r.status_code in (400, 413), "Zip-Bombe wurde nicht abgewiesen"


@pytest.mark.xfail(reason="BUG-26-2: 409-Abbruch hinterlässt Teil-Installation + Staging-Leak", strict=False)
def test_foreign_collision_409_leaves_no_partial_entry(client: TestClient):
    """Wird die Aktivierung wegen einer fremden Resolver-Datei mit 409 abgebrochen,
    darf KEIN halber Katalog-Eintrag zurückbleiben (und das Staging soll aufräumen).
    Aktuell bleibt der Eintrag als ‚installed' im Katalog stehen."""
    import os

    roles_dir = os.path.join(settings.constitution_dir, "roles")
    os.makedirs(roles_dir, exist_ok=True)
    with open(os.path.join(roles_dir, "architect.md"), "w", encoding="utf-8") as fh:
        fh.write("HANDGEPFLEGT")
    prev = _preview(client, _jupkg(entry_id="architect", typ="role"))
    r = client.post("/registry/import/confirm", json={"token": prev.json()["token"]})
    assert r.status_code == 409
    assert client.get("/registry/catalog").json()["entries"] == [], "Teil-Installation blieb zurück"


@pytest.mark.xfail(reason="BUG-26-3: nicht bestätigte Vorschauen lecken Staging-Pakete (kein TTL/Cleanup)", strict=False)
def test_unconfirmed_previews_do_not_leak_staging(client: TestClient, tmp_path):
    """Jede Vorschau ohne Confirm legt dauerhaft ein .jupkg im Staging ab.
    Erwartet: gedeckelte/aufgeräumte Staging-Ablage statt unbegrenztem Wachstum."""
    import os

    for i in range(8):
        _preview(client, _jupkg(entry_id=f"ghost-{i}"))
    staging = os.path.join(str(tmp_path / "registry"), "packages", "_staging")
    leaked = os.listdir(staging) if os.path.isdir(staging) else []
    assert len(leaked) <= 1, f"{len(leaked)} verwaiste Staging-Pakete"
