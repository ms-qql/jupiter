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
    # PROJ-14: Persistenz im Test standardmäßig AUS (kein Schreiben in den echten
    # Home-SQLite-Pfad, keine Fremd-Rehydrierung). Tests, die den Live-Index prüfen,
    # injizieren ein eigenes Repository explizit.
    monkeypatch.setattr(settings, "session_index_enabled", False)
    monkeypatch.setattr(settings, "session_index_db_path", str(tmp_path / "session_index.db"))
