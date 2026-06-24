"""PROJ-33 — Prozess-verifiziertes ``is_alive`` (kein Geister-„aktiv").

Der Subprozess-Treiber meldete bisher ``is_alive=True``, solange asyncios
``returncode`` ``None`` war — auch wenn der OS-Prozess längst tot war (nicht
gereapt). Folge: eine prozesslose Session zeigte „running/aktiv" und entging der
Auto-Reanimierung. Der Fix prüft zusätzlich die OS-PID (``pid_alive``).
"""
from __future__ import annotations

import os

from app.engine.base import pid_alive
from app.engine.claude_driver import ClaudeCodeDriver


def _gone_pid() -> int:
    """Liefert einen PID, der garantiert nicht (mehr) existiert."""
    p = 4_000_000
    while p > 1:
        try:
            os.kill(p, 0)
        except ProcessLookupError:
            return p
        except OSError:
            return p
        p -= 1
    raise RuntimeError("kein freier PID gefunden")


class _FakeProc:
    def __init__(self, returncode, pid) -> None:
        self.returncode = returncode
        self.pid = pid


# --- pid_alive Helfer -------------------------------------------------------


def test_pid_alive_for_self():
    assert pid_alive(os.getpid()) is True


def test_pid_alive_none_and_zero():
    assert pid_alive(None) is False
    assert pid_alive(0) is False


def test_pid_alive_for_gone_pid():
    assert pid_alive(_gone_pid()) is False


# --- ClaudeCodeDriver.is_alive (gehärtet) -----------------------------------


def test_is_alive_false_without_process():
    drv = ClaudeCodeDriver()
    assert drv.is_alive is False  # _proc is None


def test_is_alive_false_when_returncode_set():
    drv = ClaudeCodeDriver()
    drv._proc = _FakeProc(returncode=0, pid=os.getpid())  # beendet (rc gesetzt)
    assert drv.is_alive is False


def test_is_alive_true_for_living_pid():
    drv = ClaudeCodeDriver()
    drv._proc = _FakeProc(returncode=None, pid=os.getpid())  # rc None + lebender PID
    assert drv.is_alive is True


def test_is_alive_false_for_dead_pid_despite_none_returncode():
    """Der Kern-Fix: rc None, aber OS-Prozess weg → NICHT mehr „aktiv" (kein Geister-Zustand)."""
    drv = ClaudeCodeDriver()
    drv._proc = _FakeProc(returncode=None, pid=_gone_pid())
    assert drv.is_alive is False
