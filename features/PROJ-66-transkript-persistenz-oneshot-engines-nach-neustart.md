# PROJ-66: Bugfix: Session-Transkript von Oneshot-Engines geht bei Backend-Neustart dauerhaft verloren

## Status: Planned
**Created:** 2026-07-07
**Last Updated:** 2026-07-07

## Problem / Motivation
Live-Vorfall (2026-07-07, Nutzer-Report): Eine Codex-Session ("Peppermint") brach wiederholt ab; nach jedem Abbruch war das bisherige Transkript komplett verschwunden. Journal zeigt fünf Backend/Frontend-Neustarts in 14 Minuten (11:26–11:40 Uhr), ausgelöst durch den `jupiter-deploy`-Webhook, direkt vor der beobachteten Session-Aktivität.

**Root Cause (durch Code-Analyse verifiziert, Explore-Agent-Untersuchung 2026-07-07):**
1. Das UI-Transkript einer Session existiert ausschließlich im Arbeitsspeicher: `SessionRuntime.__init__` (`backend/app/engine/manager.py:410`) initialisiert `self.transcript: list[TranscriptEntry] = []`. `GET /sessions/{id}` und der WS-Snapshot (`routes/sessions.py:117`, `routes/sessions.py:388`) liefern direkt aus diesem RAM-Objekt.
2. Für Oneshot-Engines mit `supports_self_resume` (Codex, OpenCode) wird nur die `resume_id` persistiert — nie der volle Nachrichtenverlauf.
3. Persistiert wird sonst nur (a) einmalig als Obsidian-MD beim ersten sauberen `DONE` (`_write_session_log`, `manager.py:2110`, gated durch `_done_fired`) und (b) für nicht-selbstfortsetzende Engines (OpenAI/OpenRouter direkt) ein gedeckelter Rohverlauf via `_safe_save_context`.
4. `rehydrate()` (`manager.py:1283-1323`), aufgerufen bei **jedem Backend-Neustart** für jede in der DB gefundene Session, baut eine **komplett neue** `SessionRuntime` mit leerem `transcript` — anders als `_resume()`/`_reanimate_once()`, die dasselbe Runtime-Objekt weiterverwenden und das Transkript dadurch erhalten.
5. Ein Backend-Neustart während einer laufenden Session löscht damit das sichtbare Transkript unwiderruflich, unabhängig davon, ob der zugrunde liegende Turn selbst sauber lief.

Dies ist eine andere, schwerwiegendere Baustelle als `features/PROJ-65-tmux-oneshot-status-race-nach-spawn.md` (dort bleibt der Kontext erhalten, nur die Status-Anzeige ist kurzzeitig falsch).

**Ziel dieses Tickets:** Das Transkript einer Session übersteht einen Backend-Neustart (Deploy, Crash-Recovery) vollständig — unabhängig von Engine-Typ und Transport.

## Dependencies
- Requires: PROJ-56, PROJ-58, PROJ-60 (Kontext-Persistenz/Resumability-Modell für Oneshot-Engines, das hier um vollständige Transkript-Rückspielung ergänzt wird).
- Requires: PROJ-63, PROJ-64 (tmux-Transport, dessen Sessions besonders häufig neu erstellt/reanimiert werden und daher am stärksten betroffen sind).
- Related (nicht blockierend): PROJ-65 (verwandte, aber andere Race — Status-Anzeige statt Datenverlust).

## Scope-Abgrenzung (bewusst)
- **In Scope:**
  1. Persistente Speicherung des vollständigen Transkripts für **alle Oneshot-Engines mit RAM-only-Transkript** (Codex, OpenCode/OpenRouter via `generic_cli`), nicht nur Codex.
  2. **Append-only pro Turn:** Jeder abgeschlossene Turn (User-Input + Assistant-Antwort inkl. Tool-Events, die aktuell im `TranscriptEntry` landen) wird direkt nach Verarbeitung in einer neuen DB-Tabelle (Arbeitstitel `session_transcript_entries`, FK auf `session_id`, fortlaufender Index) geschrieben — kein gedeckelter/verlustbehafteter Rohverlauf wie bei `_safe_save_context`.
  3. `rehydrate()` liest beim Neustart die persistierten Einträge je Session aus dieser Tabelle und befüllt `SessionRuntime.transcript` damit, statt es leer zu initialisieren.
  4. Das bestehende einmalige Obsidian-MD-Log (`_write_session_log` bei erstem `DONE`) bleibt unverändert zusätzlich bestehen — es ist ein separates Artefakt für den Vault, kein Ersatz für die Live-Rehydrierung.
- **NICHT in Scope:**
  - Long-lived Treiber (Claude, PROJ-1): dort läuft der Prozess bei Neustart i. d. R. nicht durchgehend weiter, das Transkript-Persistenzverhalten für Claude-Sessions ist bereits durch PROJ-14/PROJ-17 abgedeckt und wird hier nicht angefasst.
  - Die PROJ-65-Statusrace selbst (separates Ticket).
  - Eine UI-Änderung an der Transkript-Darstellung — nur die Datenquelle/Persistenz ändert sich, das Rendering bleibt gleich.
  - Rückwirkende Rekonstruktion von Transkripten, die VOR Deployment dieses Fixes bereits verloren gingen.

## User Stories
- Als Nutzer möchte ich, dass mein Session-Transkript einen Deploy/Backend-Neustart übersteht, damit ein Routine-Deploy nicht meine bisherige Konversation zerstört.
- Als Nutzer möchte ich nach einem Neustart eine reanimierte Session genauso vorfinden wie vorher — inklusive aller bisherigen Turns —, damit ich nicht manuell rekonstruieren muss, was besprochen wurde.
- Als Entwickler (Deploy-Verantwortlicher) möchte ich, dass der `jupiter-deploy`-Webhook-Neustart keine Datenverluste in aktiven Sessions verursacht, damit Deploys jederzeit sicher ausgelöst werden können.

## Acceptance Criteria
- [ ] Eine Codex-Session mit ≥2 abgeschlossenen Turns übersteht einen Backend-Neustart (`systemctl restart jupiter-backend`) mit vollständig erhaltenem Transkript (alle bisherigen Turns sichtbar nach Reconnect).
- [ ] Dasselbe gilt für eine OpenCode-Session mit ≥2 abgeschlossenen Turns.
- [ ] Jeder Turn wird spätestens unmittelbar nach seinem Abschluss (nicht erst bei Session-Ende) persistiert — ein Neustart mitten in einer Session verliert höchstens den zum Neustart-Zeitpunkt laufenden, unvollständigen Turn, keine bereits abgeschlossenen.
- [ ] Das bestehende Obsidian-MD-Log (`_write_session_log`) wird weiterhin unverändert beim ersten `DONE` geschrieben (Regressionstest).
- [ ] Long-lived Claude-Sessions (PROJ-1) zeigen unverändertes Verhalten (Regressionstest gegen PROJ-14/PROJ-17/PROJ-33).
- [ ] Mehrfache Neustarts hintereinander (wie im Peppermint-Vorfall: 5 Neustarts in 14 Minuten) führen zu keinem kumulativen Transkript-Verlust und keinen doppelten Einträgen.
- [ ] Neue Regressionstests: (1) Transkript übersteht Neustart bei Codex, (2) Transkript übersteht Neustart bei OpenCode, (3) unvollständiger Turn zum Neustart-Zeitpunkt verliert nur diesen Turn, (4) Obsidian-MD-Log unverändert, (5) Claude-Session-Verhalten unverändert.
- [ ] Volle Backend-Suite grün (inkl. `test_proj56_*`, `test_proj58_*`, `test_proj60_*`, `test_proj63_*`).

## Edge Cases
- Neustart passiert exakt während ein Turn geschrieben wird (Race zwischen Turn-Abschluss und DB-Write) — darf keinen korrupten/halben Eintrag erzeugen (Transaktion pro Eintrag).
- Session wird nach Neustart weitergeführt (neuer Turn) — neue Einträge müssen sich nahtlos an die rehydrierten anhängen (fortlaufender Index, keine Lücken/Kollisionen).
- Sehr lange Sessions mit vielen Turns — Rehydrierung darf die Session-Erstellungs-/Reconnect-Antwort nicht spürbar verlangsamen (Pagination/Limit prüfen, falls nötig).
- Session wird während eines laufenden Turns gelöscht (PROJ-21) — persistierte Einträge müssen mitgelöscht werden (kein verwaister Datenmüll).
- Zwei Neustarts kurz hintereinander, bevor der erste `rehydrate()`-Lauf fertig war — keine doppelte Rehydrierung/doppelte Einträge.

## Technical Requirements
- Neue DB-Tabelle (Arbeitstitel `session_transcript_entries`): `id`, `session_id` (FK), `entry_index` (fortlaufend pro Session), `payload` (JSON, entspricht `TranscriptEntry`), `created_at`.
- `backend/app/engine/manager.py`: Stelle, an der ein `TranscriptEntry` aktuell nur an `self.transcript` angehängt wird — dort zusätzlich synchron/transaktional in die neue Tabelle schreiben.
- `backend/app/engine/manager.py::rehydrate()` (Zeile ~1283-1323): `SessionRuntime.transcript` aus der neuen Tabelle befüllen statt leer zu initialisieren.
- Löschpfad (PROJ-21, Session-Löschen): persistierte Einträge der Tabelle mit löschen (`ON DELETE CASCADE` oder expliziter Cleanup).
- Neue Tests unter `backend/tests/test_proj66_transkript_persistenz_rehydrate.py`.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_

## Implementation Notes
_To be added by /abc-backend_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
