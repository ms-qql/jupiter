"""Test-Fixtures.

Sicherheits-Isolation (PROJ-2): KEIN Test darf jemals in den echten Hal-Vault
schreiben. Diese autouse-Fixture biegt ``settings.vault_root`` für jeden Test auf
ein temporäres Verzeichnis um (greift auch für den Auto-Log-Hook im Manager).
"""
from __future__ import annotations

import pytest

from app.config import settings


@pytest.fixture(autouse=True)
def _isolate_vault(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "vault_root", str(tmp_path / "vault"))
