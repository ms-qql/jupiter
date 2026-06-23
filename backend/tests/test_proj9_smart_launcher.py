"""PROJ-9 — Smart Launcher (Backend).

Deckt das Status→Phase/Skill/Modell-Mapping (geteilt mit PROJ-8 via ``abc_phases``),
den header-basierten INDEX.md-Parser, die Auswahl des nächsten Features (geringster
Reifegrad → Prio → Reihenfolge) sowie die Sonder-/Fehlerfälle (keine INDEX, alle
deployed, Pfad-Ausbruch) und den REST-Vertrag ab — reiner File-Parse, keine Session.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.engine import abc_phases
from app.engine.launcher import LauncherService, parse_index_features
from app.main import create_app

INDEX_SAMPLE = """# Feature Index

| ID | Feature | Prio | Status | Abhängigkeiten | Spec |
|----|---------|------|--------|----------------|------|
| PROJ-1 | Auth | P0 | Deployed | — | [Spec](PROJ-1-auth.md) |
| PROJ-2 | Cockpit | P0 | Architected | — | [Spec](PROJ-2-cockpit.md) |
| PROJ-3 | Launcher | P1 | Planned | PROJ-2 | [Spec](PROJ-3-launcher.md) |

## Roadmap (keine Tabelle)
- PROJ-99 irgendwas
"""


# --- Mapping (Quelle der Wahrheit, geteilt mit PROJ-8) ----------------------

@pytest.mark.parametrize(
    "status,phase",
    [
        ("Planned", "architecture"),
        ("Architected", "frontend"),
        ("In Progress", "backend"),
        ("In Review", "qa"),
        ("Approved", "deploy"),
        ("Deployed", None),
        ("  architected ", "frontend"),   # case-/whitespace-tolerant
        ("Unfug", None),                    # unbekannt → None
    ],
)
def test_next_phase_for_status(status, phase):
    assert abc_phases.next_phase_for_status(status) == phase


def test_phase_to_skill_and_model():
    assert abc_phases.skill_for_phase("architecture") == "abc-architecture"
    assert abc_phases.skill_for_phase(None) is None
    assert abc_phases.model_for_phase("architecture") == "opus"
    assert abc_phases.model_for_phase("frontend") == "sonnet"
    assert abc_phases.model_for_phase("deploy") == "haiku"


def test_status_maturity_orders_unreif_first():
    assert abc_phases.status_maturity("Planned") < abc_phases.status_maturity("In Review")
    assert abc_phases.status_maturity("blah") is None


# --- INDEX.md-Parser --------------------------------------------------------

def test_parse_index_features_header_based():
    feats = parse_index_features(INDEX_SAMPLE)
    ids = [f["id"] for f in feats]
    assert ids == ["PROJ-1", "PROJ-2", "PROJ-3"]  # Roadmap-Liste wird ignoriert
    p3 = feats[2]
    assert p3["number"] == "3"
    assert p3["title"] == "Launcher"
    assert p3["status"] == "Planned"
    assert p3["prio"] == "P1"


def test_parse_index_strips_markdown_link_in_title():
    text = (
        "| ID | Feature | Prio | Status | Spec |\n"
        "|----|----|----|----|----|\n"
        "| PROJ-5 | [Vermietung](PROJ-5-v.md) | P1 | Planned | x |\n"
    )
    feats = parse_index_features(text)
    assert feats[0]["title"] == "Vermietung"


def test_parse_index_tolerates_reordered_columns():
    text = (
        "| Status | Prio | ID | Feature |\n"
        "|----|----|----|----|\n"
        "| Approved | P2 | PROJ-7 | Foo |\n"
    )
    feats = parse_index_features(text)
    assert feats[0]["status"] == "Approved"
    assert feats[0]["prio"] == "P2"
    assert feats[0]["title"] == "Foo"


# --- Vorschlags-Logik -------------------------------------------------------

@pytest.fixture()
def project(tmp_path, monkeypatch):
    """Legt ein Projekt mit features/INDEX.md unter tmp an und erlaubt den tmp-Root."""
    proj = tmp_path / "proj"
    (proj / "features").mkdir(parents=True)
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path)])

    def _write(index_text: str):
        (proj / "features" / "INDEX.md").write_text(index_text, encoding="utf-8")
        return str(proj)

    return proj, _write


def test_suggest_continue_first_picks_most_advanced_open(project):
    """Fortsetzen-First (BUG-1): reifster OFFENER Stand zuerst, nicht der unreifste."""
    proj, write = project
    path = write(INDEX_SAMPLE)
    sug = LauncherService().suggest(path)

    assert sug["abc_erkannt"] is True
    # PROJ-2 (Architected) ist weiter als PROJ-3 (Planned) → Empfehlung (weitermachen).
    assert sug["empfehlung"]["id"] == "PROJ-2"
    assert sug["empfehlung"]["phase"] == "frontend"
    assert sug["empfehlung"]["skill"] == "abc-frontend"
    assert sug["empfehlung"]["modell"] == "sonnet"
    assert sug["empfehlung"]["initial_prompt"] == "/abc-frontend 2"
    # Default-Felder spiegeln die Empfehlung (für „Vorschlag übernehmen").
    assert sug["naechste_phase"] == "frontend"
    assert sug["skill"] == "abc-frontend"
    assert sug["initial_prompt"] == "/abc-frontend 2"
    # Restliche offene Features als Alternativen (deployed PROJ-1 fällt raus),
    # jede mit EIGENEN abgeleiteten Feldern.
    assert [a["id"] for a in sug["alternativen"]] == ["PROJ-3"]
    assert sug["alternativen"][0]["skill"] == "abc-architecture"  # Planned → architecture
    assert sug["alternativen"][0]["initial_prompt"] == "/abc-architecture 3"


def test_suggest_continue_first_ranking_order(project):
    """In Review > In Progress > Architected > Planned; Approved ans Ende (Deploy human-gated)."""
    proj, write = project
    write(
        "| ID | Feature | Prio | Status | Spec |\n"
        "|----|----|----|----|----|\n"
        "| PROJ-1 | A | P1 | Approved | x |\n"
        "| PROJ-2 | B | P1 | Planned | x |\n"
        "| PROJ-3 | C | P1 | In Review | x |\n"
        "| PROJ-4 | D | P1 | In Progress | x |\n"
    )
    sug = LauncherService().suggest(str(proj))
    order = [sug["empfehlung"]["id"], *[a["id"] for a in sug["alternativen"]]]
    # In Review zuerst, dann In Progress, Architected (keins), Planned, Approved zuletzt.
    assert order == ["PROJ-3", "PROJ-4", "PROJ-2", "PROJ-1"]
    assert sug["empfehlung"]["skill"] == "abc-qa"  # In Review → qa


def test_suggest_all_deployed_recommends_requirements(project):
    proj, write = project
    write(
        "| ID | Feature | Prio | Status | Spec |\n"
        "|----|----|----|----|----|\n"
        "| PROJ-1 | Auth | P0 | Deployed | x |\n"
    )
    sug = LauncherService().suggest(str(proj))
    assert sug["abc_erkannt"] is True
    assert sug["empfehlung"] is None
    assert sug["skill"] == "abc-requirements"
    assert sug["naechste_phase"] == "requirements"
    assert "deployed" in sug["hinweis"].lower()


def test_suggest_no_index_falls_back_to_freetext(project):
    proj, _write = project  # features/ existiert, aber keine INDEX.md
    sug = LauncherService().suggest(str(proj))
    assert sug["abc_erkannt"] is False
    assert sug["empfehlung"] is None
    assert "kein abc-workflow" in sug["hinweis"].lower()


def test_suggest_unparsable_statuses_degrade(project):
    proj, write = project
    write(
        "| ID | Feature | Prio | Status | Spec |\n"
        "|----|----|----|----|----|\n"
        "| PROJ-1 | Auth | P0 | Bananen | x |\n"
    )
    sug = LauncherService().suggest(str(proj))
    assert sug["abc_erkannt"] is False


def test_suggest_rejects_path_outside_roots(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path / "allowed")])
    (tmp_path / "allowed").mkdir()
    with pytest.raises(ValueError):
        LauncherService().suggest("/etc")


# --- Red-Team: Pfad-Härtung des einzigen Eingabeparameters ------------------

@pytest.mark.parametrize(
    "evil",
    [
        "/etc",                                  # absolut außerhalb
        "/home/dev/projects/../../etc",          # relativer Traversal
        "/home/dev/projects/__nope_does_not_exist__",  # nicht-existent innerhalb Root
    ],
)
def test_suggest_path_hardening_rejects(evil, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", ["/home/dev/projects"])
    with pytest.raises(ValueError):
        LauncherService().suggest(evil)


def test_suggest_rejects_null_byte(monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", ["/home/dev/projects"])
    with pytest.raises(ValueError):  # eingebettetes Null-Byte → ValueError → 400
        LauncherService().suggest("/home/dev/projects/jupiter\x00/etc/passwd")


def test_suggest_includes_approved_as_open(project):
    """Approved-Features sind noch nicht deployed → tauchen als offen auf (nächste Phase deploy)."""
    proj, write = project
    write(
        "| ID | Feature | Prio | Status | Spec |\n"
        "|----|----|----|----|----|\n"
        "| PROJ-1 | Auth | P0 | Approved | x |\n"
    )
    sug = LauncherService().suggest(str(proj))
    assert sug["empfehlung"]["id"] == "PROJ-1"
    assert sug["empfehlung"]["phase"] == "deploy"
    assert sug["empfehlung"]["skill"] == "abc-deploy"


# --- REST-Vertrag -----------------------------------------------------------

def test_rest_suggestion_endpoint(project):
    proj, write = project
    write(INDEX_SAMPLE)
    client = TestClient(create_app())
    resp = client.get("/projects/suggestion", params={"project_path": str(proj)})
    assert resp.status_code == 200
    body = resp.json()
    assert body["abc_erkannt"] is True
    assert body["empfehlung"]["id"] == "PROJ-2"  # Architected > Planned (Fortsetzen-First)
    assert body["initial_prompt"] == "/abc-frontend 2"


def test_rest_suggestion_path_outside_roots_returns_400(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "allowed_roots", [str(tmp_path / "allowed")])
    (tmp_path / "allowed").mkdir()
    client = TestClient(create_app())
    resp = client.get("/projects/suggestion", params={"project_path": "/etc"})
    assert resp.status_code == 400
