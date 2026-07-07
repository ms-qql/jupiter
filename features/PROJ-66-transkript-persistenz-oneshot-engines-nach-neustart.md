# PROJ-66: Bugfix: Session-Transkript von Oneshot-Engines geht bei Backend-Neustart dauerhaft verloren

## Status: Architected
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
_(verfeinert in „Tech Design" unten — Blob-pro-Session statt Append-Zeilen-Tabelle, siehe Begründung dort)_
- Neue DB-Tabelle `session_transcript`: `session_id` (Schlüssel, kein FK-Constraint, analog `session_context`), `entries` (JSON, vollständiger `TranscriptEntry`-Verlauf), `updated_at`.
- `backend/app/engine/manager.py`: an den vier bestehenden Append-Stellen (`:582-584`, `:589-591`, `:624-626`, `:1615`) zusätzlich best-effort/fire-and-forget den aktuellen `self.transcript`-Stand in `session_transcript` upserten (gleiches Muster wie `save_context`).
- `backend/app/engine/manager.py::rehydrate()` (Zeile ~1283-1323): `SessionRuntime.transcript` aus `session_transcript` befüllen (für Oneshot-/Self-Resume-Engines, dieselbe Fallunterscheidung wie in `_resume()`), statt leer zu initialisieren.
- Löschpfad (PROJ-21, `_delete_sync` in `session_index.py:243-251`): zusätzliche `DELETE FROM session_transcript WHERE session_id = ?`-Zeile.
- Neue Tests unter `backend/tests/test_proj66_transkript_persistenz_rehydrate.py`.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-07 · **Stack:** FastAPI (`backend/app/engine/manager.py`) + SQLite Live-Index (`backend/app/db/session_index.py`) · **Branch:** dev

### Grundlage (CodeGraph-Exploration, verifiziert)
- `TranscriptEntry` (`manager.py:260-265`) hat die Felder `role`, `kind`, `text`, `ts`. Es gibt genau **vier** Stellen, an denen ein Eintrag ans In-Memory-`self.transcript` gehängt wird: Assistant-„Thinking" (`:582-584`), Assistant-Text (`:589-591`), synthetischer Tool-Eintrag (`:624-626`, aus PROJ-62), User-Text (`:1615`). Das sind die einzigen Hook-Punkte, die eine Persistenz-Anbindung brauchen.
- `rehydrate()` (`manager.py:1283-1323`) baut bei jedem Neustart pro DB-Zeile eine **neue** `SessionRuntime` mit leerem `transcript` — im Gegensatz zu `_resume()`/`_reanimate_once()`, die ein bestehendes Runtime-Objekt weiterverwenden und dessen `transcript` dadurch implizit erhalten. Es gibt aktuell **keinen** Codepfad, der `transcript` je aus einer Quelle außer dem laufenden Prozess befüllt.
- Es existiert bereits eine strukturell ähnliche, aber **andersartige** Tabelle: `session_context` (`session_index.py:117-121`, PROJ-56). Sie speichert einen einzigen JSON-Blob (`messages`) im **Provider-Rohformat** (z. B. OpenAI-Message-Dicts) — nicht im `TranscriptEntry`-UI-Format — und **nur für Engines ohne Self-Resume** (OpenAI/OpenRouter direkt). Codex/OpenCode (`supports_self_resume`) haben kein `conversation_history`-Attribut auf ihrem Treiber, daher überspringt `_persist()` (`manager.py:1241-1262`) den Save für sie stillschweigend (kein expliziter Check, sondern `getattr(..., None)` liefert `None`).
- `GET /sessions/{id}` und der WS-Snapshot (`routes/sessions.py:111-118`, `:383-389`) lesen `runtime.transcript` direkt aus dem Speicher — keine Änderung an diesen Endpunkten nötig, sobald `transcript` beim Rehydrieren korrekt befüllt ist.
- Löschen (PROJ-21) entfernt `session_index`- und `session_context`-Zeilen in `_delete_sync` (`session_index.py:243-251`) — jede neue Tabelle muss dort eine identische `DELETE`-Zeile bekommen.
- `_write_session_log` (Obsidian-MD beim ersten DONE) liest ebenfalls nur `runtime.transcript`, schreibt aber unabhängig in den Vault — bleibt unangetastet.

### A) Betroffene Komponenten (kein UI-Baum nötig)
Reine Backend-Persistenz — an der Sidebar/Session-Ansicht ändert sich nichts, sie liest weiterhin dieselbe `transcript`-Struktur wie heute, nur dass diese nach einem Neustart nicht mehr leer ist:
```
manager.py (4 bestehende Append-Stellen)
└── neuer Persistenz-Hook (best-effort, fire-and-forget)
        └── neue Tabelle: session_transcript
rehydrate()
└── liest session_transcript → befüllt SessionRuntime.transcript vor Auslieferung an Routen
```

### B) Datenmodell (einfache Sprache)
Eine **neue** Tabelle `session_transcript` (bewusst getrennt von `session_context`, weil andere Datenform und anderer Zweck — UI-Transkript statt Provider-Rohverlauf):
- `session_id` — Schlüssel, ein Eintrag pro Session (kein Fremdschlüssel-Constraint, analog zu `session_context`/`session_index`)
- `entries` — der komplette aktuelle Transkript-Inhalt als JSON (Liste von `TranscriptEntry`-artigen Objekten)
- `updated_at` — Zeitstempel der letzten Aktualisierung

**Bewusste Vereinfachung gegenüber dem ursprünglichen Spec-Entwurf** (dort als "Arbeitstitel" mit `entry_index`-Append-Zeilen skizziert): Statt einer echten Zeile-pro-Eintrag-Tabelle mit fortlaufendem Index wird — wie bei `session_context` — **ein Blob pro Session** geschrieben, der bei jedem der vier Hook-Punkte mit dem aktuellen, vollständigen In-Memory-Transkript überschrieben wird (Upsert, gleiches Muster wie `save_context`). Das vermeidet die in den Edge Cases der Spec beschriebene Komplexität (Lücken/Kollisionen im `entry_index` bei parallelem Neustart + neuem Turn) komplett, weil es keinen Index gibt, der aus der Reihe kommen könnte — es gibt immer nur „den aktuellen Stand". Da die Schreibungen best-effort und pro Eintrag (nicht pro Zeichen) passieren, verliert ein Crash mitten im Turn höchstens den seit dem letzten Hook-Punkt ungeschriebenen Rest — das erfüllt die Acceptance Criteria sogar granularer als gefordert (nicht nur „ganze Turns bleiben erhalten", sondern auch bereits sichtbare Teil-Antworten).

Gilt für **alle Oneshot-Engines** (Codex, OpenCode), nicht nur Codex. Die Schreib-Hooks selbst müssen dabei nicht nach Engine unterscheiden (einheitlich, einfacher Code) — sie sind ohnehin billig und best-effort. Die **Lesbarkeit beim Rehydrieren** wird an derselben Fallunterscheidung gespiegelt, die `_resume()` heute schon trifft (`is_claude` vs. `driver.supports_self_resume` vs. sonstige) — Long-lived Claude-Sessions bleiben dadurch unverändert (Scope-Abgrenzung der Spec), ohne dass der Schreibpfad selbst verzweigen muss.

### C) API-Form
Keine neuen oder geänderten Endpunkte. `GET /sessions/{id}` und die WS-Snapshot-Antwort liefern unverändert `runtime.transcript` — der Unterschied ist rein, dass dieses Feld nach einem Neustart bereits gefüllt ankommt statt leer zu sein.

### D) Tech-Entscheidungen (Begründung)
- **Warum eine neue Tabelle statt `session_context` zu erweitern:** `session_context` ist an das Provider-Rohformat für Nicht-Self-Resume-Engines gebunden (eigene Cap-Logik `_cap_history`, eigene Lade-Semantik in `_resume()`). Das UI-Transkript hat eine andere Form (`TranscriptEntry`) und einen anderen Zweck (Anzeige, nicht Modell-Kontext). Eine eigene Tabelle hält beide Belange sauber getrennt und lässt `session_context` unangetastet.
- **Warum ein Blob pro Session statt echter Append-Zeilen:** Einfacher, kein Index-Bookkeeping über einen Neustart hinweg, passt zum bereits etablierten Muster (`session_context`) und zur „Single-Writer, WAL, günstige Schreibungen"-Prämisse des Live-Index. Transkripte sind pro Session natürlich begrenzt (Turns eines Chats), das Wiederschreiben des ganzen Blobs bei jedem Append bleibt günstig.
- **Warum kein Cap/keine Kürzung** (anders als `session_context`): Das UI-Transkript ist das, was der Nutzer tatsächlich sehen will — im Gegensatz zum Provider-Kontext (der nur die Modell-Fortsetzung füttert) gibt es hier keinen fachlichen Grund, ältere Teile wegzuwerfen. Sollte das in der Praxis zu groß werden, ist das ein separates, später zu beobachtendes Problem (nicht Teil dieses Tickets).
- **Warum Best-effort/fire-and-forget statt synchron blockierend:** Konsistent mit jedem anderen Schreibpfad in diesem Persistenz-Seam (`session_index.upsert`, `save_context`) — ein DB-Fehler darf den Live-Betrieb nie blockieren, nur zu einer Warnung degradieren.
- **Warum Rehydrierung nur für Oneshot-/Self-Resume-Engines:** Bewahrt exakt das heutige Verhalten für Claude (Scope-Abgrenzung der Spec), ohne eine neue Sonderfall-Verzweigung im Schreibpfad einzuführen — die Unterscheidung existiert an der Lesestelle (`rehydrate()`) bereits implizit durch die vorhandene `_resume()`-Fallunterscheidung.

### E) Abhängigkeiten (Pakete)
Keine neuen Pakete — nutzt dieselbe `sqlite3`/sync-über-`asyncio.to_thread`-Infrastruktur, die `session_index.py` bereits für `session_context` verwendet.

## Implementation Notes
_To be added by /abc-backend_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
