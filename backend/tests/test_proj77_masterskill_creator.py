"""PROJ-77: isolierte QA-Tests für den masterskill-creator-Helfer."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest
import yaml


SCRIPT = Path("/home/dev/tools/Hal/09_Skills/masterskill-creator/scripts/masterskill.py")
GENERATOR = Path(__file__).resolve().parents[2] / "scripts" / "gen_codex_skills.py"


@pytest.fixture
def helper():
    spec = importlib.util.spec_from_file_location("proj77_masterskill", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def configure(helper, tmp_path: Path, agents: list[dict]) -> Path:
    helper.HAL_ROOT = tmp_path / "Hal"
    helper.SKILLS_ROOT = helper.HAL_ROOT / "09_Skills"
    helper.AGENTS_FILE = helper.SKILLS_ROOT / "agents.yaml"
    helper.ARCHIVE_ROOT = helper.HAL_ROOT / "06 Archive" / "09_Skills"
    helper.SKILLS_ROOT.mkdir(parents=True)
    helper.AGENTS_FILE.write_text(yaml.safe_dump({"agents": agents}), encoding="utf-8")
    return helper.SKILLS_ROOT


def write_master(root: Path, name: str, description: str = "Kurzer Test-Skill") -> Path:
    skill = root / name / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# Nur im Master\n",
        encoding="utf-8",
    )
    return skill


def test_stubs_for_active_agents_and_shared_opencode_is_skipped(helper, tmp_path, capsys):
    agents = [
        {"id": "claude", "skills_dir": str(tmp_path / "claude"), "frontmatter": ["name", "description"], "enabled": True},
        {"id": "codex", "skills_dir": str(tmp_path / "codex"), "frontmatter": ["name", "description", "metadata.short-description"], "enabled": True},
        {"id": "opencode", "skills_dir": str(tmp_path / "opencode"), "shares_with": "claude", "enabled": True},
    ]
    root = configure(helper, tmp_path, agents)
    master = write_master(root, "demo")

    assert helper.cmd_stubs(argparse.Namespace(name="demo", agents=None)) == 0

    for agent in ("claude", "codex"):
        stub = tmp_path / agent / "demo" / "SKILL.md"
        text = stub.read_text(encoding="utf-8")
        assert str(master) in text
        assert "# Nur im Master" not in text
        assert len(text.splitlines()) <= 15
    assert not (tmp_path / "opencode" / "demo").exists()
    assert "opencode (geteilt über claude)" in capsys.readouterr().out


def test_registry_only_adds_kimi_without_changing_master(helper, tmp_path):
    agents = [
        {"id": "claude", "skills_dir": str(tmp_path / "claude"), "frontmatter": ["name", "description"], "enabled": True},
        {"id": "kimi", "skills_dir": str(tmp_path / "kimi"), "frontmatter": ["name", "description"], "enabled": True},
    ]
    root = configure(helper, tmp_path, agents)
    master = write_master(root, "demo")
    before = master.read_bytes()

    helper.cmd_stubs(argparse.Namespace(name="demo", agents=None))

    assert (tmp_path / "kimi" / "demo" / "SKILL.md").is_file()
    assert master.read_bytes() == before


def test_symlink_skill_requires_explicit_confirmation(helper, tmp_path, monkeypatch):
    configure(helper, tmp_path, [])
    target = tmp_path / ".agents" / "skills" / "linked"
    target.mkdir(parents=True)
    claude = tmp_path / ".claude" / "skills"
    claude.mkdir(parents=True)
    (claude / "linked").symlink_to(target, target_is_directory=True)
    monkeypatch.setattr(helper.Path, "home", classmethod(lambda cls: tmp_path))

    with pytest.raises(SystemExit, match="Symlink"):
        helper.cmd_migrate(argparse.Namespace(
            name="linked", source="claude", apply=False, force=False, force_symlink=False,
        ))


def test_broken_relative_link_aborts_before_archiving(helper, tmp_path, monkeypatch):
    configure(helper, tmp_path, [])
    source = tmp_path / ".claude" / "skills" / "broken"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: broken\ndescription: Test\n---\n[fehlt](template.md)\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(helper.Path, "home", classmethod(lambda cls: tmp_path))

    with pytest.raises(SystemExit, match="kaputter relativer Link"):
        helper.cmd_migrate(argparse.Namespace(
            name="broken", source="claude", apply=True, force=False, force_symlink=False,
        ))

    assert source.is_dir()
    assert not (helper.SKILLS_ROOT / "broken").exists()


def test_migration_dry_run_waits_without_writing(helper, tmp_path, monkeypatch, capsys):
    configure(helper, tmp_path, [])
    source = tmp_path / ".claude" / "skills" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: demo\ndescription: Test\n---\nMastertext\n", encoding="utf-8",
    )
    monkeypatch.setattr(helper.Path, "home", classmethod(lambda cls: tmp_path))

    assert helper.cmd_migrate(argparse.Namespace(
        name="demo", source="claude", apply=False, force=False, force_symlink=False,
    )) == 0

    assert source.is_dir()
    assert not (helper.SKILLS_ROOT / "demo").exists()
    output = capsys.readouterr().out
    assert "Quelle für den Master" in output and "Nichts geschrieben" in output


def test_migration_archives_assets_and_is_idempotent(helper, tmp_path, monkeypatch):
    agents = [
        {"id": "claude", "skills_dir": str(tmp_path / ".claude" / "skills"), "frontmatter": ["name", "description"], "enabled": True},
        {"id": "codex", "skills_dir": str(tmp_path / ".codex" / "skills"), "frontmatter": ["name", "description"], "enabled": True},
    ]
    configure(helper, tmp_path, agents)
    claude = tmp_path / ".claude" / "skills" / "demo"
    codex = tmp_path / ".codex" / "skills" / "demo"
    for source, body in ((claude, "Claude"), (codex, "Codex")):
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            f"---\nname: demo\ndescription: Test\n---\n[{body}](template.md)\n",
            encoding="utf-8",
        )
        (source / "template.md").write_text(body, encoding="utf-8")
    untouched = tmp_path / ".claude" / "skills" / "anderer-skill" / "SKILL.md"
    untouched.parent.mkdir()
    untouched.write_text("unverändert", encoding="utf-8")
    monkeypatch.setattr(helper.Path, "home", classmethod(lambda cls: tmp_path))

    helper.cmd_migrate(argparse.Namespace(
        name="demo", source="claude", apply=True, force=False, force_symlink=False,
    ))
    master = helper.SKILLS_ROOT / "demo"
    before = {p.relative_to(helper.HAL_ROOT): p.read_bytes() for p in helper.HAL_ROOT.rglob("*") if p.is_file()}
    helper.cmd_stubs(argparse.Namespace(name="demo", agents=None))
    after = {p.relative_to(helper.HAL_ROOT): p.read_bytes() for p in helper.HAL_ROOT.rglob("*") if p.is_file()}

    assert (master / "template.md").read_text(encoding="utf-8") == "Claude"
    assert (helper.ARCHIVE_ROOT / "demo").is_dir()
    assert helper.is_pointer_stub(claude / "SKILL.md")
    assert helper.is_pointer_stub(codex / "SKILL.md")
    assert untouched.read_text(encoding="utf-8") == "unverändert"
    assert before == after


def test_codex_system_skills_are_never_migrated(helper, tmp_path, monkeypatch):
    configure(helper, tmp_path, [])
    system = tmp_path / ".codex" / "skills" / ".system"
    system.mkdir(parents=True)
    (system / ".codex-system-skills.marker").write_text("do not touch", encoding="utf-8")
    (system / "SKILL.md").write_text(
        "---\nname: system\ndescription: Intern\n---\n", encoding="utf-8",
    )
    monkeypatch.setattr(helper.Path, "home", classmethod(lambda cls: tmp_path))

    with pytest.raises(SystemExit, match="System"):
        helper.cmd_migrate(argparse.Namespace(
            name=".system", source="codex", apply=False, force=False, force_symlink=False,
        ))


def test_check_detects_wrong_master_path_in_stub(helper, tmp_path):
    agents = [
        {"id": "claude", "skills_dir": str(tmp_path / "claude"), "frontmatter": ["name", "description"], "enabled": True},
    ]
    root = configure(helper, tmp_path, agents)
    write_master(root, "demo")
    helper.cmd_stubs(argparse.Namespace(name="demo", agents=None))
    stub = tmp_path / "claude" / "demo" / "SKILL.md"
    stub.write_text(
        stub.read_text(encoding="utf-8").replace(str(root / "demo"), "/nicht/vorhanden"),
        encoding="utf-8",
    )

    assert helper.cmd_check(argparse.Namespace(name="demo")) == 1


def test_missing_agent_directory_is_reported_and_skipped(helper, tmp_path, capsys):
    """bootstrap: false (etablierter Agent) — fehlendes Verzeichnis heißt offline, nicht anlegen."""
    missing = tmp_path / "nicht-vorhanden"
    agents = [
        {"id": "offline", "skills_dir": str(missing), "frontmatter": ["name", "description"],
         "bootstrap": False, "enabled": True},
    ]
    root = configure(helper, tmp_path, agents)
    write_master(root, "demo")

    helper.cmd_stubs(argparse.Namespace(name="demo", agents=None))

    assert not missing.exists()
    assert "übersprungen" in capsys.readouterr().out


def test_new_agent_without_bootstrap_flag_still_creates_directory(helper, tmp_path):
    """bootstrap fehlt/true (Default, z. B. Kimi-Neuzugang) — Verzeichnis wird angelegt."""
    fresh = tmp_path / "kimi"
    agents = [
        {"id": "kimi", "skills_dir": str(fresh), "frontmatter": ["name", "description"], "enabled": True},
    ]
    root = configure(helper, tmp_path, agents)
    write_master(root, "demo")

    helper.cmd_stubs(argparse.Namespace(name="demo", agents=None))

    assert (fresh / "demo" / "SKILL.md").is_file()


def test_skill_name_cannot_escape_managed_directories(helper, tmp_path):
    agents = [
        {"id": "claude", "skills_dir": str(tmp_path / "claude"), "frontmatter": ["name", "description"], "enabled": True},
    ]
    root = configure(helper, tmp_path, agents)
    write_master(root.parent, "escape")

    with pytest.raises(SystemExit, match="Name"):
        helper.cmd_stubs(argparse.Namespace(name="../escape", agents=None))


def test_stub_frontmatter_quotes_description(helper, tmp_path):
    agent = {"frontmatter": ["name", "description", "metadata.short-description"]}
    rendered = helper.render_stub(
        "demo",
        {"description": "Test-Skill: Beschreibung mit Doppelpunkt"},
        agent,
        tmp_path / "demo",
    )

    frontmatter = rendered.split("\n---", 1)[0][3:]
    assert yaml.safe_load(frontmatter)["description"] == "Test-Skill: Beschreibung mit Doppelpunkt"


def test_proj50_generator_skips_migrated_pointer_stubs(tmp_path):
    source, destination = tmp_path / "source", tmp_path / "destination"
    for name, marker in (("abc-migriert", "Pointer-Stub, erzeugt von masterskill-creator"), ("abc-alt", "alter Inhalt")):
        skill = source / name / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text(
            f"---\nname: {name}\ndescription: Test\n---\n{marker}\n", encoding="utf-8",
        )

    result = subprocess.run(
        [sys.executable, str(GENERATOR), "--src", str(source), "--dest", str(destination)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "übersprungen (masterskill-creator-Stub, PROJ-77): abc-migriert" in result.stdout
    assert not (destination / "abc-migriert").exists()
    assert (destination / "abc-alt" / "SKILL.md").is_file()


def test_cli_errors_are_in_german():
    result = subprocess.run([sys.executable, str(SCRIPT), "stubs"], capture_output=True, text=True)

    assert result.returncode != 0
    assert "FEHLER" in result.stderr
    assert "required" not in result.stderr
    assert "usage:" not in result.stderr


def test_codex_only_skill_can_be_migrated(helper, tmp_path, monkeypatch):
    agents = [
        {"id": "claude", "skills_dir": str(tmp_path / ".claude" / "skills"), "frontmatter": ["name", "description"], "enabled": True},
        {"id": "codex", "skills_dir": str(tmp_path / ".codex" / "skills"), "frontmatter": ["name", "description"], "enabled": True},
    ]
    configure(helper, tmp_path, agents)
    source = tmp_path / ".codex" / "skills" / "nur-codex"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text(
        "---\nname: nur-codex\ndescription: Test\n---\nInhalt\n", encoding="utf-8",
    )
    monkeypatch.setattr(helper.Path, "home", classmethod(lambda cls: tmp_path))

    helper.cmd_migrate(argparse.Namespace(
        name="nur-codex", source="claude", apply=True, force=False, force_symlink=False,
    ))

    assert (helper.SKILLS_ROOT / "nur-codex" / "SKILL.md").is_file()
    assert helper.is_pointer_stub(tmp_path / ".claude" / "skills" / "nur-codex" / "SKILL.md")
    assert helper.is_pointer_stub(tmp_path / ".codex" / "skills" / "nur-codex" / "SKILL.md")


def test_stub_failure_keeps_originals_in_place(helper, tmp_path, monkeypatch):
    agents = [
        {"id": "claude", "skills_dir": str(tmp_path / ".claude" / "skills"), "frontmatter": ["name", "description"], "enabled": True},
        {"id": "codex", "skills_dir": str(tmp_path / ".codex" / "skills"), "frontmatter": ["name", "description"], "enabled": True},
    ]
    configure(helper, tmp_path, agents)
    originals = []
    for agent in (".claude", ".codex"):
        source = tmp_path / agent / "skills" / "demo"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: demo\ndescription: Test\n---\nOriginal\n", encoding="utf-8",
        )
        originals.append(source)
    monkeypatch.setattr(helper.Path, "home", classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(helper, "cmd_stubs", lambda args: (_ for _ in ()).throw(RuntimeError("Stub-Fehler")))

    with pytest.raises(RuntimeError, match="Stub-Fehler"):
        helper.cmd_migrate(argparse.Namespace(
            name="demo", source="claude", apply=True, force=False, force_symlink=False,
        ))

    assert all((source / "SKILL.md").is_file() for source in originals)


def test_stub_system_exit_keeps_original_in_place(helper, tmp_path, monkeypatch):
    agents = [
        {"id": "claude", "skills_dir": str(tmp_path / ".claude" / "skills"),
         "frontmatter": ["name", "description"], "enabled": True},
    ]
    configure(helper, tmp_path, agents)
    source = tmp_path / ".claude" / "skills" / "demo"
    source.mkdir(parents=True)
    (source / "SKILL.md").write_text("---\nname: demo\n---\nOriginal\n", encoding="utf-8")
    monkeypatch.setattr(helper.Path, "home", classmethod(lambda cls: tmp_path))

    with pytest.raises(SystemExit, match="description"):
        helper.cmd_migrate(argparse.Namespace(
            name="demo", source="claude", apply=True, force=False, force_symlink=False,
        ))

    assert (source / "SKILL.md").is_file()


def test_partial_stub_write_rolls_back_cleanly(helper, tmp_path, monkeypatch):
    agents = [
        {"id": "claude", "skills_dir": str(tmp_path / ".claude" / "skills"),
         "frontmatter": ["name", "description"], "enabled": True},
        {"id": "codex", "skills_dir": str(tmp_path / ".codex" / "skills"),
         "frontmatter": ["name", "description"], "enabled": True},
    ]
    configure(helper, tmp_path, agents)
    originals = []
    for agent in (".claude", ".codex"):
        source = tmp_path / agent / "skills" / "demo"
        source.mkdir(parents=True)
        (source / "SKILL.md").write_text(
            "---\nname: demo\ndescription: Test\n---\nOriginal\n", encoding="utf-8",
        )
        originals.append(source)
    monkeypatch.setattr(helper.Path, "home", classmethod(lambda cls: tmp_path))
    original_render = helper.render_stub
    calls = 0

    def fail_second_stub(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("zweiter Stub fehlgeschlagen")
        return original_render(*args, **kwargs)

    monkeypatch.setattr(helper, "render_stub", fail_second_stub)

    with pytest.raises(OSError, match="zweiter Stub"):
        helper.cmd_migrate(argparse.Namespace(
            name="demo", source="claude", apply=True, force=False, force_symlink=False,
        ))

    assert all((source / "SKILL.md").read_text(encoding="utf-8").endswith("Original\n") for source in originals)


def test_check_skips_offline_non_bootstrap_agent(helper, tmp_path):
    missing = tmp_path / "offline"
    agents = [
        {"id": "offline", "skills_dir": str(missing), "frontmatter": ["name", "description"],
         "bootstrap": False, "enabled": True},
    ]
    root = configure(helper, tmp_path, agents)
    write_master(root, "demo")

    assert helper.cmd_check(argparse.Namespace(name="demo")) == 0


def test_check_detects_missing_master_asset(helper, tmp_path):
    agents = [
        {"id": "claude", "skills_dir": str(tmp_path / "claude"),
         "frontmatter": ["name", "description"], "enabled": True},
    ]
    root = configure(helper, tmp_path, agents)
    master = write_master(root, "demo")
    master.write_text(master.read_text(encoding="utf-8") + "[Vorlage](template.md)\n", encoding="utf-8")
    asset = master.parent / "template.md"
    asset.write_text("Vorlage", encoding="utf-8")
    helper.cmd_stubs(argparse.Namespace(name="demo", agents=None))
    asset.unlink()

    assert helper.cmd_check(argparse.Namespace(name="demo")) == 1
