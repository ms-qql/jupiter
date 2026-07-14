# PROJ-72: Bugfix: Claude-Engine dupliziert Nachrichten (und Fragekarten) nach jedem Resume/Restart

## Status: Deployed
**Created:** 2026-07-14
**Last Updated:** 2026-07-14
**Deployed:** 2026-07-14 · Version 0.27.30 · https://jupiter.auxevo.tech

## Problem / Motivation
Nutzer meldete: In **Claude**-Terminal-Sessions ("Cloud") werden, je länger die Session läuft, **Assistenten-Nachrichten doppelt und dreifach** ins Transkript geschrieben (Belegscreenshot: `crypto_mts_ui`, Laufzeit 13 h 38 m, dieselben ASSISTANT-Blöcke 2×/3× untereinander). Zusätzlich: **Fragekarten kommen immer wieder**, nachdem eine Session unterbrochen und wieder gestartet wurde. Bei **Codex** und **OpenCode** tritt beides nicht auf.

Dies ist der **Nachfolger/Vervollständigung von PROJ-70**. PROJ-70 hat nur die Fragekarten (`_open_user_question`) gegen ein *In-Memory*-Replay entprellt — der zugrunde liegende Mechanismus (das out.log-Offset-0-Replay) blieb aber bestehen und trifft (a) den **normalen Assistenten-Text** (nie entprellt) und (b) die Fragekarten nach einem **Backend-Neustart** (frische Runtime → leeres `pending` → Guard greift nicht).

**Root Cause (empirisch + Reproduktionstest verifiziert):**

Claude läuft als **langlebige tmux-Session** (PROJ-63); stdout wird per `>> out.log` (Append) in dieselbe, an der `session_id` hängende Datei geschrieben. Bei jedem `_resume` (Reanimierung, Auto-Resume, Backend-Neustart/Deploy) baut der Treiber eine **frische** `TmuxTransport`, deren `spawn()` das Lese-Handle **ab Offset 0** öffnet (`transport.py`, `open(out_path,"rb")`) → `_read_stdout` liest die **komplette Historie erneut** und schickt jedes vergangene `assistant`-Event nochmal durch `handle_event`:
- `handle_event` (assistant-Zweig) hängt den Text **ungeprüft** an `self.transcript` an und broadcastet ihn erneut → bei Same-Process-Resume (dieselbe Runtime) **akkumulieren** die Kopien (K Resumes ⇒ K+1 Kopien; „je länger die Session, desto mehr").
- Nach einem Backend-Neustart re-öffnet der Replay zudem alte, bereits beantwortete Fragekarten (frisches, leeres `pending`).
- Nebenbefund: der Replay ruft auch `_apply_usage` erneut → Usage/Kosten würden nach Restart doppelt gezählt.

**Empirischer Beleg:** Eine reale `out.log` (32 Prozess-Spawns) enthält **jede Assistant-Message-ID genau 1×** (max repeat = 1) — `claude --resume` dumpt den Verlauf also **nicht** erneut; die Dubletten entstehen ausschließlich aus dem clientseitigen Offset-0-Re-Read derselben Datei.

Codex/OpenCode sind **oneshot** (Transkript aus DB rehydriert, kein wiederverwendetes out.log-Re-Read) → nicht betroffen.

## Dependencies
- Requires: PROJ-63 (langlebiger tmux-Transport mit wiederverwendeter out.log), PROJ-66 (Transkript-Persistenz in der DB), PROJ-27/PROJ-45 (Resume/Reanimierung), PROJ-70 (Fragekarten-Guard bleibt als zweite Verteidigungslinie).

## Scope-Abgrenzung (bewusst)
- **In Scope:** Das out.log-**Replay eliminieren** (statt jeden re-emittierten Seiteneffekt einzeln zu entprellen). Der Resume-Respawn seekt ans out.log-Ende; der Transkript-Wiederaufbau kommt jetzt aus der DB — auch für Claude.
- **Kehrt eine PROJ-70-Scope-Entscheidung um:** PROJ-70 hatte Seek-to-End verworfen („würde das Transkript leeren"). Das galt nur, **solange** der Transkript-Rebuild vom Replay abhing. Durch das gleichzeitige Laden des Claude-Transkripts aus der DB (PROJ-66 persistiert es ohnehin bereits für jede Engine) ist Seek-to-End jetzt korrekt und sicher.
- **Unberührt:** Codex/OpenCode/OpenAI-Pfade, `--resume`-Kontexterhalt (serverseitig), Kosten-/Turn-Zählung im Normalbetrieb.

## Lösung (kleinster korrekter Eingriff)
1. `transport.py` — `TmuxTransport.spawn(..., seek_to_end: bool=False)`: bei `True` wird das Lese-Handle nach dem Öffnen ans Datei-Ende gesetzt (`seek(0, os.SEEK_END)`) → nur neu angehängte Ausgabe wird gelesen. (Signatur auch an `Transport`-ABC + `DirectTransport` gespiegelt; dort ohne Wirkung.)
2. `claude_driver.py` — `_spawn_tmux` übergibt `seek_to_end=spec.resume`: der Erststart liest ab 0 (Live-Stream), jeder Resume-Respawn liest nur Neues.
3. `manager.py` — `rehydrate()` lädt das UI-Transkript jetzt aus der DB für **jede** Engine inkl. Claude (die frühere `not profile.is_claude`-Ausnahme entfällt), damit der Rebuild ohne Replay funktioniert.

## Acceptance Criteria
- [x] Ein Resume-Respawn (`seek_to_end=True`) liest den bereits vorhandenen out.log-Inhalt **nicht** erneut — nur neu Angehängtes (`test_long_lived_seek_to_end_skips_preexisting_log`); Gegenprobe belegt, dass ohne Seek das Replay auftritt (`test_long_lived_without_seek_replays_preexisting_log`).
- [x] Der Erststart (kein Resume) liest weiterhin die volle Live-Ausgabe (`seek_to_end=spec.resume`, beim Create `False`).
- [x] Nach einem Backend-Neustart liefert auch eine Claude-Session ihr Transkript zurück (aus der DB rehydriert) statt leer (`test_rehydrate_laedt_transkript_auch_fuer_claude`, `test_route_get_session_transcript_restored_for_claude`).
- [x] Mehrere Neustarts einer Claude-Session vervielfachen das Transkript **nicht** (`test_rehydrate_mehrfacher_neustart_keine_dopplung_claude`).
- [x] Der PROJ-70-Fragekarten-Guard bleibt grün (zweite Verteidigungslinie, `test_replayed_question_marker_does_not_duplicate_card`).
- [x] Keine Regression in den Resume-/Transport-/Persistenz-Suiten (proj27/33/48/56/62/63/64/66/70) — 246 relevante Tests grün; volle Suite 1178 passed (2 vorbestehende, thematisch fremde `test_proj50_codex_abc`-YAML-Failures ausgenommen).

## Implementation Notes
- Bewusst **Replay-Elimination** statt weiterer Entprellung: ein einziger Mechanismus (kein Re-Read) beseitigt Text-Dubletten, wiederkehrende Fragekarten **und** die potenzielle Usage-Doppelzählung — statt jeden Seiteneffekt in `handle_event` einzeln idempotent zu machen.
- **Akzeptiertes Rest-Risiko:** Bricht der Prozess **ungeordnet mitten im Turn** ab, bevor der letzte Ausgabe-Rest per `_persist` (feuert an Statuswechseln) in die DB kam, fehlt genau dieser Rest nach dem Neustart in der UI. Der Konversations-**Kontext** bleibt über `claude --resume` (serverseitig) erhalten; im Ruhezustand (WAITING) ist das Transkript stets aktuell. Klar besser als das bisherige 2×/3×-Replay.

## Nächster Schritt
- Deploy ist human-gated → `/abc-deploy` (Version-Bump). Empfehlung: nach Deploy eine langlaufende Claude-Session mehrfach reanimieren/neu starten und prüfen, dass Nachrichten/Fragekarten nicht mehr dupliziert werden.
