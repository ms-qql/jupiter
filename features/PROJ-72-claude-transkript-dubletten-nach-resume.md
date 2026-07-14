# PROJ-72: Bugfix: Claude-Engine dupliziert Nachrichten (und Fragekarten) nach jedem Resume/Restart

## Status: Deployed
**Created:** 2026-07-14
**Last Updated:** 2026-07-14
**Deployed:** 2026-07-14 · Version 0.27.30 · https://jupiter.auxevo.tech
**Reopened:** 2026-07-14 · Produktions-Gegenbeleg nach Deploy (Session `90a13f65`)
**Redeployed:** 2026-07-14 · Version 0.27.31 · https://jupiter.auxevo.tech

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

### Produktionsbefund nach dem ersten PROJ-72-Deploy

Der Fix aus Version 0.27.30 ist **nicht in allen Claude-Resume-Pfaden wirksam**:

- Session `90a13f65` erhielt um 10:02 UTC — rund drei Stunden nach dem Deploy um 07:18 UTC — weiterhin einen vollständigen Faktor-2-Replay mit 44 direkt aufeinanderfolgenden Doppel-Einträgen.
- Weitere persistierte Sessions zeigen dieselbe Signatur, z. B. `d162bff5` mit 202 Wiederholungen.
- Innerhalb einer betroffenen Session erscheint jeder Assistant-Eintrag mit einem konstanten Faktor: Faktor 2 nach einem Replay, Faktor 3 nach zwei Replays. Das belegt einen Voll-Transkript-Replay statt einzelner UI-Dubletten.
- Die Dubletten sind im gespeicherten Servertranskript (`session_index.db`) vorhanden. Ein frisch verbundener Browser macht sie durch den Full-Snapshot lediglich sichtbar; der read-only WebSocket-Connect erzeugt sie nicht.

Damit ist das Akzeptanzkriterium „Mehrere Neustarts/Resumes vervielfachen das Transkript nicht“ in Produktion widerlegt. Die bisherige Implementierung deckt mindestens einen Resume-/Respawn-Pfad nicht ab oder reicht die Seek-Absicht dort nicht bis zum tatsächlich lesenden Transport durch.

## Dependencies
- Requires: PROJ-63 (langlebiger tmux-Transport mit wiederverwendeter out.log), PROJ-66 (Transkript-Persistenz in der DB), PROJ-27/PROJ-45 (Resume/Reanimierung), PROJ-70 (Fragekarten-Guard bleibt als zweite Verteidigungslinie).

## Scope-Abgrenzung (bewusst)
- **In Scope:** Das out.log-**Replay eliminieren** (statt jeden re-emittierten Seiteneffekt einzeln zu entprellen). Der Resume-Respawn seekt ans out.log-Ende; der Transkript-Wiederaufbau kommt jetzt aus der DB — auch für Claude.
- **Kehrt eine PROJ-70-Scope-Entscheidung um:** PROJ-70 hatte Seek-to-End verworfen („würde das Transkript leeren"). Das galt nur, **solange** der Transkript-Rebuild vom Replay abhing. Durch das gleichzeitige Laden des Claude-Transkripts aus der DB (PROJ-66 persistiert es ohnehin bereits für jede Engine) ist Seek-to-End jetzt korrekt und sicher.
- **Unberührt:** Codex/OpenCode/OpenAI-Pfade, `--resume`-Kontexterhalt (serverseitig), Kosten-/Turn-Zählung im Normalbetrieb.
- **Separater Defekt, nicht Teil dieses Reopenings:** `send_input` besitzt keinen atomaren Turn-/Resume-Lock pro Konversation. Zwei Clients, die gleichzeitig senden, können durch den Check-then-act-Ablauf zwei Resumes auslösen. Der beobachtete Vorfall wurde nicht so ausgelöst; hierfür ist nach PROJ-72 ein eigenes Requirement anzulegen.

## Lösung (kleinster korrekter Eingriff)
1. `transport.py` — `TmuxTransport.spawn(..., seek_to_end: bool=False)`: bei `True` wird das Lese-Handle nach dem Öffnen ans Datei-Ende gesetzt (`seek(0, os.SEEK_END)`) → nur neu angehängte Ausgabe wird gelesen. (Signatur auch an `Transport`-ABC + `DirectTransport` gespiegelt; dort ohne Wirkung.)
2. `claude_driver.py` — `_spawn_tmux` übergibt `seek_to_end=spec.resume`: der Erststart liest ab 0 (Live-Stream), jeder Resume-Respawn liest nur Neues.
3. `manager.py` — `rehydrate()` lädt das UI-Transkript jetzt aus der DB für **jede** Engine inkl. Claude (die frühere `not profile.is_claude`-Ausnahme entfällt), damit der Rebuild ohne Replay funktioniert.
4. **Reopening-Fix:** `claude_driver.py` koppelt das Seek nicht länger an `spec.resume`, sondern setzt für jeden Claude-tmux-Start `seek_to_end=True`. Die korrekte Invariante liegt an der Append-Log selbst: ist sie beim echten Erststart leer, bleibt der Start unverändert; enthält sie bereits Historie, darf kein Treiber sie erneut durch `handle_event` schicken — unabhängig davon, welches Start-/Recovery-Metadatum der Aufrufer gesetzt hat.

## Acceptance Criteria
- [x] Ein Resume-Respawn (`seek_to_end=True`) liest den bereits vorhandenen out.log-Inhalt **nicht** erneut — nur neu Angehängtes (`test_long_lived_seek_to_end_skips_preexisting_log`); Gegenprobe belegt, dass ohne Seek das Replay auftritt (`test_long_lived_without_seek_replays_preexisting_log`).
- [x] Der Erststart liest weiterhin seine vollständige neue Live-Ausgabe: seine session-skopierte `out.log` ist vor dem ersten Spawn leer, daher entspricht das Seek-to-End dem Offset 0; anschließend neu angehängte Events werden normal gelesen (`test_single_turn_over_tmux`).
- [x] Nach einem Backend-Neustart liefert auch eine Claude-Session ihr Transkript zurück (aus der DB rehydriert) statt leer (`test_rehydrate_laedt_transkript_auch_fuer_claude`, `test_route_get_session_transcript_restored_for_claude`).
- [x] **Jeder** Claude-tmux-Treiberstart setzt den Reader auf das Ende der bereits vorhandenen `out.log`, bevor neue Events verarbeitet werden; die Garantie hängt nicht mehr von einem einzelnen Resume-Pfad oder `LaunchSpec.resume` ab.
- [x] Mehrere Neustarts/Resumes einer Claude-Session vervielfachen das persistierte Transkript **nicht**. `test_multiple_claude_resume_attachments_only_emit_each_new_turn` bindet zweimal einen echten Claude-tmux-Treiber an dieselbe Append-Log und sieht pro Bindung ausschließlich den neuen Turn.
- [x] Ein zweiter, nur lesender Client erhält denselben kanonischen Server-Snapshot wie der erste Client und verursacht dabei weder Resume noch zusätzliche Transkript-/Fragekarten-Einträge (`test_read_only_clients_do_not_mutate_session_or_trigger_resume`).
- [x] Regressionstest auf der fehlerhaften Grenze: `test_existing_claude_log_is_never_replayed_when_driver_attaches` bindet einen Claude-Treiber mit absichtlich fehlendem Resume-Merker an eine vorbereitete `out.log`; vor dem Fix wurde `ALT-HISTORIE` erneut emittiert, danach ausschließlich neue Ausgabe.
- [x] Bestandsdubletten werden durch den Fix nicht erneut vervielfacht: der Zwei-Resume-Test startet mit zwei identischen historischen Assistant-Zeilen und emittiert keine davon erneut. Eine automatische Bereinigung bereits korrumpierter Transkripte ist bewusst nicht Teil dieses Fixes, weil legitime Wiederholungen nicht sicher von Replay-Dubletten unterschieden werden können.
- [x] Der PROJ-70-Fragekarten-Guard bleibt grün (zweite Verteidigungslinie, `test_replayed_question_marker_does_not_duplicate_card`).
- [x] Keine Regression in den Resume-/Transport-/Persistenz-Suiten (proj27/33/48/56/62/63/64/66/70) — 246 relevante Tests grün; volle Suite 1178 passed (2 vorbestehende, thematisch fremde `test_proj50_codex_abc`-YAML-Failures ausgenommen).

## Implementation Notes
- Bewusst **Replay-Elimination** statt weiterer Entprellung: ein einziger Mechanismus (kein Re-Read) beseitigt Text-Dubletten, wiederkehrende Fragekarten **und** die potenzielle Usage-Doppelzählung — statt jeden Seiteneffekt in `handle_event` einzeln idempotent zu machen.
- **Akzeptiertes Rest-Risiko:** Bricht der Prozess **ungeordnet mitten im Turn** ab, bevor der letzte Ausgabe-Rest per `_persist` (feuert an Statuswechseln) in die DB kam, fehlt genau dieser Rest nach dem Neustart in der UI. Der Konversations-**Kontext** bleibt über `claude --resume` (serverseitig) erhalten; im Ruhezustand (WAITING) ist das Transkript stets aktuell. Klar besser als das bisherige 2×/3×-Replay.
- **Root Cause des Reopenings:** Der erste Fix formulierte die richtige Transporthandlung, koppelte sie aber an das indirekte Aufrufer-Metadatum `spec.resume`. Dadurch blieb die Append-Log-Invariante lückenhaft: ein Bindepfad ohne gesetzten Merker las weiterhin ab Offset 0. Der neue Fix macht die Sicherheit pfadunabhängig in `ClaudeCodeDriver._spawn_tmux`.
- **Verifikation Reopening:** roter Repro vor Fix (`['ALT-HISTORIE', 'echo:neu']` statt `['echo:neu']`); danach 75/75 Tests grün in `test_proj63_claude_tmux.py`, `test_proj63_tmux_transport.py`, `test_proj66_transkript_persistenz_rehydrate.py` und `test_proj4_decision_cards.py`. Eine vorbestehende asyncio-Subprocess-Destruktor-Warnung blieb unverändert.

## Nächster Schritt
- `/abc-deploy`; im Produktiv-Smoke eine langlaufende Claude-Session über mehrere Resume-Auslöser prüfen. Ein zweiter Browser dient dabei ausschließlich als Snapshot-Kontrolle.

## QA Test Results — Reopening-Fix (2026-07-14)

**Entscheidung:** READY / Approved — keine Critical-, High-, Medium- oder Low-Befunde in PROJ-72.

### Akzeptanzkriterien

| Bereich | Ergebnis | Nachweis |
|---|---|---|
| Claude-Erststart liest neue Live-Ausgabe vollständig | PASS | `test_single_turn_over_tmux` |
| Bereits vorhandene Append-Log wird unabhängig von `resume` nicht erneut gelesen | PASS | roter Repro vor Fix, danach `test_existing_claude_log_is_never_replayed_when_driver_attaches` |
| Zwei aufeinanderfolgende echte Claude-tmux-Resume-Anbindungen emittieren nur ihren jeweiligen neuen Turn | PASS | `test_multiple_claude_resume_attachments_only_emit_each_new_turn` |
| Bereits vorhandene Dubletten werden bei weiteren Resumes nicht vervielfacht | PASS | Zwei identische `ALT-HISTORIE`-Zeilen im Zwei-Resume-Test, beide bleiben unemittiert |
| Claude-Transkript wird nach Backend-Restart aus der DB rehydriert | PASS | `test_proj66_transkript_persistenz_rehydrate.py` |
| Fragekarten-Guard bleibt intakt | PASS | `test_proj4_decision_cards.py` |
| Zwei read-only WebSocket-Clients verändern weder Treiber, Status noch Transkript | PASS | `test_read_only_clients_do_not_mutate_session_or_trigger_resume` |

### Regression und Security

- Gezielter Resume-/Transport-/Persistenz-/Decision-Card-/WebSocket-Lauf: **106 passed**.
- Zusätzlicher QA-Lauf der neuen Claude-Resume- und Zwei-Client-Tests: **10 passed**.
- Vollständige Backend-Suite: **1180 passed, 2 failed, 2 warnings**. Beide Fehler sind vorbestehend und thematisch fremd in `test_proj50_codex_abc.py`: Skillgenerator-Drift bei `abc-backoffice`/`abc-customer-journey` sowie daraus folgende ungültige YAML-Kurzbeschreibung. Diese exakten PROJ-50-Ausnahmen waren bereits vor dem Reopening dokumentiert.
- WebSocket-Auth/Owner-Isolation und unbekannte/fremde Session-ID bleiben unverändert; die vorhandenen PROJ-25-Auth-Tests liefen in der Gesamtsuite grün. Der Fix fügt keinen Endpoint, keine Nutzereingabe und keine neue Datenfreigabe hinzu.
- Visuelle, responsive und Flutter-Tests: nicht einschlägig; Änderung liegt ausschließlich im Backend-Treiber/Transport, die UI-Verträge werden über Snapshot-Integrationstests abgedeckt.

### Rest-Risiko

- Der Fix verhindert neue Replays, bereinigt aber bereits persistierte Dubletten nicht automatisch. Eine heuristische Bereinigung könnte legitime identische Antworten löschen und wäre ein separates Requirement.
- Produktiv-Smoke nach Deploy bleibt erforderlich, weil der ursprüngliche Gegenbeleg erst im Live-Resume-Betrieb sichtbar wurde.
