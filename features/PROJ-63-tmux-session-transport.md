# PROJ-63: Tmux-Session-Transport fuer stabile Jupiter-Agenten

## Status: Deployed
**Created:** 2026-07-06
**Last Updated:** 2026-07-07

## Problem / Motivation
Jupiter-Sessions brechen im Live-Betrieb weiterhin zu oft ab oder geraten in uneindeutige Zustände. Die bisherigen Härtungen haben einzelne Fehlerklassen repariert: Liveness/Reanimation (PROJ-27), Restart-Drain/Auto-Resume (PROJ-33), Reader-Stall (PROJ-47), WebSocket-Replay (PROJ-49), Kontext-Persistenz fuer Nicht-Claude-Engines (PROJ-56) und mehrere OpenCode-Transport-Fixes (PROJ-58/60/62). Trotzdem bleibt die Grundannahme fragil: Jupiter hält die Agentenprozesse direkt als Backend-Kindprozesse und muss stdin/stdout, Prozessende, Resume und Status selbst korrekt interpretieren.

In normalen Terminalfenstern laufen dieselben Agenten in `tmux` deutlich stabiler. Dieses Feature prüft und spezifiziert daher `tmux` als optionale Transport-/Supervisor-Schicht fuer Jupiter: Agenten laufen in persistenten tmux-Sessions/Panes, Jupiter attachiert logisch daran, sendet Eingaben und liest Output/Status aus, statt den Agentenprozess direkt an den FastAPI-Lifecycle zu binden.

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — heutiger Subprozess-/Stream-Vertrag, der um einen alternativen Transport ergänzt wird.
- Requires: PROJ-14 (Session-Limit + Persistenz) — Session-Metadaten und Live-Index muessen tmux-Session-/Pane-IDs persistieren.
- Requires: PROJ-27 (Liveness + Reanimieren) — Liveness muss tmux-Pane/Prozess-Realität statt nur Backend-Kindprozess prüfen.
- Requires: PROJ-33 (Restart-Resilienz) — tmux soll Backend-Restarts ueberleben und Drain/Auto-Resume vereinfachen, darf aber bestehende Regeln nicht brechen.
- Requires: PROJ-56 (Kontext-Persistenz Nicht-Claude-Engines) — Codex/OpenCode-Resume-State bleibt weiterhin relevant, auch wenn die TTY stabiler ist.
- Verwandt: PROJ-47, PROJ-58, PROJ-60, PROJ-62 — Symptome der direkten stdout/stdin-Kopplung, die der tmux-Transport reduzieren soll.

## Scope-Abgrenzung
- **In Scope:** ein optionaler tmux-basierter Transport fuer CLI-Agenten, ein Spike mit echten Claude/Codex/OpenCode-Sessions, persistierte tmux-Metadaten, Attach/Detach/Stop/Reattach-Verhalten, Cockpit-Sichtbarkeit und klare Fallbacks.
- **Nicht in Scope:** sofortige Entfernung der bestehenden direkten Treiber, ein neues Terminal-UI im Browser, Multi-User-Rechte fuer fremde tmux-Sessions, Ersatz des Vault-/Kontext-Systems.
- **Unberührt:** Engine-Auswahl, Modellverwaltung, Vault, Smart Launcher und bestehende Session-APIs aus Nutzersicht.

## User Stories
- Als Nutzer möchte ich Jupiter-Sessions in einer stabilen tmux-Laufzeit starten können, damit Backend-Restarts, WebSocket-Reconnects oder Reader-Probleme die Agentenarbeit nicht abbrechen.
- Als Nutzer möchte ich nach einem Jupiter-Neustart laufende Agenten wieder im Cockpit sehen und weiter steuern können, ohne manuell im Terminal attachen zu müssen.
- Als Nutzer möchte ich Jupiter von verschiedenen Geräten, Browsern und Tabs aus öffnen können und dieselben aktiven Sessions sehen, ohne dass die Session an ein einzelnes Gerät gebunden ist.
- Als Nutzer möchte ich pro Session erkennen, ob sie direkt oder über tmux läuft, damit ich Verhalten und Fehler besser einordnen kann.
- Als Nutzer möchte ich eine hängende tmux-Session sicher stoppen, reattachen oder in den bestehenden Resume-/Recovery-Pfad überführen können.
- Als Betreiber möchte ich tmux zunächst pro Engine oder global aktivieren/deaktivieren können, damit der neue Transport kontrolliert eingeführt wird.

## Acceptance Criteria
- [ ] Es gibt eine konfigurierbare Transport-Option `direct` vs. `tmux` (global und/oder pro Engine). Default bleibt bis nach erfolgreichem Spike konservativ `direct`.
- [ ] Eine neue Session kann im tmux-Transport gestartet werden; Jupiter legt eine eindeutig benannte tmux-Session oder ein Pane pro Jupiter-Session an und persistiert die tmux-ID im Live-Index.
- [ ] Jupiter kann Eingaben an die tmux-Session senden, ohne auf geschlossene stdin-Pipes des Agentenprozesses zu schreiben.
- [ ] Jupiter kann Output aus der tmux-Session zuverlässig erfassen und dem bestehenden Transkript-/Activity-/WebSocket-Pfad zuführen.
- [ ] Ein FastAPI-Backend-Restart beendet tmux-basierte Agentenprozesse nicht; nach Startup werden tmux-Sessions wiedergefunden und im Cockpit als steuerbar oder kontrolliert eingeschränkt angezeigt.
- [ ] Ein Browserwechsel, Gerätewechsel, Tab-Close oder WebSocket-Reconnect beendet keine tmux-basierte Session; das neu verbundene Gerät sieht dieselbe aktive Session-Liste.
- [ ] Beim Öffnen von Jupiter auf einem anderen Gerät rekonstruiert das Cockpit aktive Sessions aus Live-Index plus tmux-Realität und zeigt den letzten relevanten Output per Backfill an.
- [ ] Parallele Eingaben von mehreren Geräten werden kontrolliert behandelt: Jupiter verhindert widersprüchliche Doppelsteuerung oder weist sie mit klarer deutscher Meldung ab.
- [ ] JWT/Auth bleibt die einzige Web-Zugriffskontrolle; der tmux-Transport öffnet keinen separaten ungeschützten Zugriffspfad.
- [ ] Liveness basiert beim tmux-Transport auf tmux-Pane-/Child-Prozess-Zustand und sichtbarer Output-/Statusänderung, nicht nur auf einer Backend-PID.
- [ ] Stop beendet genau die zur Jupiter-Session gehörende tmux-Session/Panes und hinterlässt keine verwaisten Prozesse.
- [ ] Session-Limit, Reanimation und Kontext-Resume respektieren tmux-Sessions; es entsteht kein zweiter paralleler Agent mit demselben Kontext.
- [ ] Direct-Transport bleibt unverändert und regressionsfrei fuer Claude, Codex, OpenCode und Swisscom.
- [ ] Der Spike vergleicht mindestens Claude, Codex und OpenCode jeweils mit `direct` und `tmux` ueber: Start, Folge-Eingabe, langer Tool-Lauf, Backend-Restart, Stop, Reattach.
- [ ] Bei fehlendem `tmux` oder fehlgeschlagenem Attach zeigt Jupiter eine klare deutsche Meldung und fällt kontrolliert auf `direct` oder „nicht verfügbar" zurück.

## Edge Cases
- **tmux ist nicht installiert:** Engine/Transport wird als nicht verfügbar markiert; kein Start-Crash.
- **tmux-Session existiert, Agentprozess darin ist tot:** Cockpit zeigt „tot" mit Reaktivieren/Recovery statt „aktiv".
- **tmux-Session existiert nicht mehr, DB-Eintrag schon:** Rehydrate markiert die Jupiter-Session als beendet/verwaist.
- **Backend-Restart während laufendem Tool-Call:** tmux hält den Prozess am Leben; Jupiter synchronisiert nach dem Restart Output und Status ohne doppelten Resume.
- **Gerätewechsel / Browserwechsel:** neue Clients erhalten nach Login einen konsistenten Snapshot der aktiven tmux-Sessions plus Backfill, nicht nur neue Events.
- **Mehrere Browser gleichzeitig:** eine Session darf nicht durch konkurrierende Eingaben von zwei Geräten in einen unklaren Zustand geraten; Eingaben werden sequenziert oder abgelehnt.
- **Nutzer attachiert manuell im Terminal:** Jupiter toleriert paralleles Lesen, verhindert aber destruktive Doppelsteuerung so weit wie möglich.
- **Mehrere Engines parallel:** tmux-Namen/Panes kollidieren nicht; Stop einer Session betrifft keine andere.
- **Großer Output/Scrollback:** Capture begrenzt Speicherverbrauch und verliert nicht den letzten relevanten Stand.
- **Codex/OpenCode oneshot-Verhalten:** tmux darf nicht fälschlich annehmen, dass ein beendeter oneshot-Prozess steuerbar bleibt; Resume-Regeln aus PROJ-48/56/57 bleiben maßgeblich.

## Technical Requirements (optional)
- Spike zuerst: echte CLI-Läufe unter tmux gegen lokale Projektpfade, ohne Web-UI-Umbau.
- Tmux-Metadaten im bestehenden Session-Snapshot speichern: `transport`, `tmux_session`, optional `tmux_pane`, letzter Capture-Cursor/Offset.
- Reconnect-/Multi-Device-Verhalten nutzt den bestehenden Snapshot-/Event-Replay-Pfad und muss für tmux-Backfill explizit getestet werden.
- Keine Shell-String-Injection: tmux-Aufrufe mit argumentierter Prozessausführung; Session-Namen aus serverseitigen IDs ableiten.
- Capture/Replay muss bounded sein (z. B. Zeilen-/Byte-Limit) und darf den Event-Loop nicht blockieren.
- Logs und UI-Texte deutsch; keine Secrets im tmux-Session-Namen oder persistierten Metadaten.

## Open Design Questions
1. **Transport-Grenze:** Soll tmux im bestehenden `generic_cli`-/Claude-Treiber sitzen oder als eigener `EngineTransport` unterhalb aller CLI-Treiber eingeführt werden? Default-Vorschlag: als Transport-Abstraktion unterhalb der CLI-Treiber, damit Claude/Codex/OpenCode profitieren.
2. **Output-Quelle:** Soll Jupiter `tmux capture-pane` pollen, pipe-pane nutzen oder beide kombinieren? Default-Vorschlag: Spike vergleicht `pipe-pane` fuer Live-Events plus `capture-pane` fuer Reattach/Backfill.
3. **Interaktive Agenten:** Braucht tmux einen echten TTY-Modus fuer Engines, die non-interaktiv bisher instabil sind? Default-Vorschlag: zuerst die bestehenden non-interaktiven Befehle in tmux kapseln; echtes interaktives TTY nur, wenn der Spike zeigt, dass es notwendig ist.
4. **Rollout:** Soll tmux zuerst nur fuer OpenCode/Codex aktiviert werden oder auch Claude? Default-Vorschlag: Feature-Flag pro Engine; OpenCode/Codex zuerst, Claude erst nach Spike.


---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-06 · **Stack:** Next.js 16 Cockpit + FastAPI Engine-Layer + SQLite-Live-Index + tmux auf dem Host · **Branch:** main

### Kernaussage
PROJ-63 führt `tmux` nicht als neues UI-Terminal ein, sondern als **optionalen Transport unterhalb der bestehenden Engine-Treiber**. Jupiter bleibt die Web-Kommandozentrale: Auth, Cockpit, Session-Liste, Transkript, Decision Cards, Liveness und Recovery laufen weiter über FastAPI/Next.js. Der Unterschied ist, dass CLI-Agenten nicht mehr zwingend als direktes Kind des Backend-Prozesses laufen, sondern in einer langlebigen tmux-Session auf dem Host.

Der wichtigste Produktnutzen: Sessions sind serverseitig stabil und geräteunabhängig. Ein Browserwechsel, ein anderes Gerät, ein WebSocket-Reconnect oder ein Backend-Restart darf die Agentenarbeit nicht mehr abbrechen. Neue Clients bekommen beim Öffnen von Jupiter einen Snapshot plus Backfill und sehen dieselben aktiven Sessions.

### A) Komponentenstruktur
```text
Next.js Cockpit
├── Session-Liste / Kanban
│   ├── Transport-Badge: direct | tmux
│   ├── Liveness aus Session-Snapshot
│   └── Multi-Device-Snapshot aus GET /sessions
├── Session-Detail
│   ├── bestehender WebSocket-Stream
│   ├── Connect-Snapshot mit Transkript + tmux-Backfill
│   ├── Eingabeformular mit Konflikt-/Busy-Hinweis
│   └── Stop / Reanimieren / Recovery unverändert sichtbar
└── Neue-Session-Dialog / Settings
    └── Transport-Auswahl bzw. Engine-Default: direct | tmux

FastAPI Backend
├── SessionManager
│   ├── bestehende SessionState-/Liveness-/Persistenz-Logik
│   ├── neue Transport-Metadaten pro Session
│   └── Eingabe-Arbitration für mehrere Geräte
├── EngineDriver-Schicht
│   ├── ClaudeCodeDriver
│   ├── GenericCliDriver (Codex/OpenCode)
│   └── Transport-Abstraktion darunter: direct oder tmux
├── TmuxTransport
│   ├── tmux-Session/Panename anlegen
│   ├── Eingaben senden
│   ├── Output live abgreifen
│   ├── Backfill aus Scrollback liefern
│   └── Stop/Reattach/Liveness prüfen
└── SQLite-Live-Index
    └── persistiert Session + Transport + tmux-IDs + Capture-Position
```

### B) Datenmodell
Der bestehende `session_index` bleibt die zentrale Rehydrate-Quelle. Er wird um Transport-Metadaten erweitert:

```text
Jede Session bekommt zusätzlich:
- transport: direct oder tmux
- tmux_session: serverseitig abgeleiteter Name, keine Nutzereingabe
- tmux_pane: Pane-ID, falls genutzt
- tmux_capture_cursor: letzter verarbeiteter Output-Punkt oder Offset
- transport_status: verbunden, wiedergefunden, tmux fehlt, pane tot, backfill unvollständig
- active_input_client: optionaler kurzer Lease, wenn ein Gerät gerade sendet
```

Transkript bleibt fachlich im bestehenden SessionRuntime-/Vault-Pfad. `tmux` ist nicht die Wahrheit für Wissen, sondern die robuste Laufzeit- und Backfill-Quelle. Nach Reconnect oder Gerätewechsel rekonstruiert Jupiter den sichtbaren Stand aus Live-Index, In-Memory-Snapshot und tmux-Backfill.

Es gibt keine MinIO-Nutzung und keine neue externe Datenbank. Der Store bleibt host-nativ SQLite, passend zur vorhandenen Jupiter-Architektur.

### C) API-Shape
Bestehende Endpunkte bleiben stabil:

```text
GET  /sessions                 → Session-Liste inkl. transport/transport_status
GET  /sessions/{id}            → Detail inkl. Transkript und tmux-Backfill, falls nötig
POST /sessions                 → startet mit Engine-Default oder gewünschtem Transport
POST /sessions/{id}/input      → sendet Eingabe; bei paralleler Steuerung klarer 409-Hinweis
POST /sessions/{id}/stop       → beendet direct-Prozess oder tmux-Session gezielt
POST /sessions/{id}/reanimate  → nutzt bestehenden Recovery-/Resume-Pfad, tmux-bewusst
WS   /sessions/{id}/stream     → Connect-Snapshot enthält Transkript + tmux-Backfill
```

Neue Settings-/Diagnoseform:

```text
GET  /settings/transports      → verfügbare Transporte, tmux-Verfügbarkeit, Defaults
PUT  /settings/transports      → globaler Default und optionale Engine-Overrides
GET  /sessions/{id}/transport  → Diagnose: tmux-Name, Status, letzter Backfill, Fehlerhinweis
```

Der Diagnose-Endpunkt ist read-only und für Betrieb/QA gedacht. Die normale Nutzung bleibt über die bestehende Session-API.

### D) Multi-Device-Verhalten
Multi-Device ist ein Kernkriterium, kein Zusatz:

1. **Jedes Gerät nutzt dieselbe Web-App und dieselbe JWT-Auth.** `tmux` öffnet keinen eigenen Web-Zugriff und ersetzt nicht die Auth-Schicht.
2. **GET /sessions ist die geräteübergreifende Wahrheit für die Übersicht.** Beim Öffnen auf einem anderen Gerät lädt der Client die aktive Session-Liste wie heute per Polling.
3. **Der WebSocket-Connect-Snapshot bleibt die Detail-Wahrheit.** Bei jedem Connect sendet das Backend den aktuellen Session-State plus Transkript. Für tmux-Sessions wird vorher ein bounded Backfill aus tmux ergänzt, damit neue Geräte nicht nur neue Events sehen.
4. **Parallele Eingaben werden kontrolliert.** Jupiter nimmt Eingaben serverseitig sequentiell an. Wenn eine Eingabe gerade verarbeitet wird oder ein anderer Client einen kurzen Eingabe-Lease hält, bekommt der zweite Client eine deutsche 409-Meldung statt unklarer Doppelsteuerung.
5. **Mehrere Geräte dürfen lesen.** Mehrere Browser/Tabs können dieselbe Session beobachten; nur widersprüchliches Schreiben wird begrenzt.

### E) Tech-Entscheidungen
- **Transport-Abstraktion statt OpenCode-Spezialfix:** Die letzten Fixes (PROJ-58/60/62) zeigen, dass einzelne Adapter-Fixes die Grundklasse nicht beseitigen. Ein Transport unterhalb der CLI-Treiber kann Claude, Codex und OpenCode nutzen, ohne jeden Adapter anders zu behandeln.
- **`direct` bleibt Fallback:** Der heutige Pfad ist produktiv und getestet. `tmux` wird per Feature-Flag/Engine-Default eingeführt, damit ein Problem nicht alle Engines blockiert.
- **`pipe-pane` plus `capture-pane` als Spike-Kandidat:** Live-Ausgabe braucht ein kontinuierliches Signal; Reconnect/Device-Wechsel braucht Backfill. Deshalb soll der Spike beide Quellen prüfen: `pipe-pane` für Live-Events, `capture-pane` für Snapshot/Backfill.
- **tmux-Session pro Jupiter-Session:** Klare Stop-/Cleanup-Grenze, keine Kollisionen, einfache Rehydrate-Prüfung. Namen werden aus serverseitigen Session-IDs abgeleitet, nicht aus Nutzereingaben.
- **tmux ist Laufzeit, nicht Persistenz-Wahrheit:** Der Vault bleibt die langlebige Wissensquelle, SQLite der Live-Index. tmux liefert nur robuste Prozess- und Scrollback-Realität.
- **Backfill ist bounded:** Scrollback kann groß werden. Jupiter übernimmt nur einen begrenzten, zuletzt relevanten Bereich und merkt den Fortschritt, damit Speicher und WebSocket-Frames kontrollierbar bleiben.
- **Kein neues Terminal im Browser:** PROJ-63 stabilisiert Agenten-Sessions. Eine rohe Terminal-Ansicht wäre ein anderes Produkt-/Sicherheitsfeature.
- **Manuelles `tmux attach` wird toleriert, aber nicht als Hauptpfad gebaut:** Der Nutzer kann im Notfall terminalseitig schauen; Jupiter bleibt aber der kontrollierte Steuerpfad.

### F) Rollout-Plan
1. **Spike ohne UI-Umbau:** echte Claude-, Codex- und OpenCode-Läufe in tmux starten, Output erfassen, Eingaben senden, Backend-Restart simulieren, Stop/Reattach prüfen.
2. **Backend-Transport-Schicht:** `direct` und `tmux` als austauschbare Transportoptionen für CLI-Treiber modellieren; SQLite-Metadaten erweitern.
3. **Snapshot/Backfill:** WebSocket-Connect-Snapshot und REST-Detail so erweitern, dass neue Geräte tmux-Backfill erhalten.
4. **Settings/Anzeige:** Transport-Default konfigurierbar machen; Session-Badge und Diagnosehinweise im Cockpit anzeigen.
5. **Engine-weise Aktivierung:** zuerst Codex/OpenCode, danach Claude. `direct` bleibt jederzeit wählbar.

### G) Abhängigkeiten
- Backend: keine neuen Python-Pakete erwartet; `tmux` als Host-Binary ist erforderlich und auf diesem System vorhanden (`/usr/bin/tmux`).
- Frontend: keine neuen npm-Pakete erwartet; bestehende Session-Komponenten werden erweitert.
- Infrastruktur: systemd darf tmux-Prozesse nicht zusammen mit `jupiter-backend` töten; tmux muss als User `dev` laufen und in denselben erlaubten Projektpfaden arbeiten.

### H) QA-/Spike-Matrix
| Szenario | direct | tmux | Erwartung |
|---|---:|---:|---|
| Claude starten + Folgeeingabe | ja | ja | beide steuerbar, tmux ohne Backend-Kindprozess-Abhängigkeit |
| Codex/OpenCode oneshot + Resume | ja | ja | Resume-State bleibt korrekt, kein Doppelprozess |
| Langer Tool-Lauf | ja | ja | tmux zeigt weiterhin Output/Backfill, kein falscher Abbruch |
| Backend-Restart | begrenzt | ja | tmux-Agent läuft weiter und wird wiedergefunden |
| Browser-/Gerätewechsel | ja | ja | neuer Client bekommt Snapshot; tmux zusätzlich Backfill |
| Zwei Geräte senden gleichzeitig | ja | ja | eine Eingabe gewinnt/sequenziert, die andere bekommt klare Meldung |
| Stop | ja | ja | nur die eigene Session wird beendet, keine fremden tmux-Panes |
| tmux fehlt | n/a | ja | Transport nicht verfügbar, klare Meldung/Fallback |

### I) Offene Architekturentscheidungen für den Spike
1. Ob `pipe-pane` stabil genug für strukturierte Live-Events ist oder ob ein Polling-Capture einfacher und robuster ist.
2. Wie genau der Capture-Cursor modelliert wird, damit Backfill keine Duplikate erzeugt.
3. Ob Claude im tmux-Modus weiter im headless-stream-json-Modus läuft oder ob ein echter interaktiver TTY-Modus für Stabilität nötig ist.
4. Wie streng die Eingabe-Arbitration zwischen mehreren Geräten sein soll: kurzer Server-Lease pro Send, oder harte Sperre solange ein Turn aktiv ist.

---

## Spike-Ergebnisse (Backend Developer, 2026-07-06)

Per Rollout-Plan Schritt 1 ("Spike ohne UI-Umbau") wurden echte `claude`-, `codex`- und `opencode`-Läufe unter `tmux 3.4` gegen ein isoliertes Scratch-Verzeichnis (`/tmp/proj63-spike`, kein Repo-Zugriff) durchgeführt — mit den exakten Argv-Templates aus `claude_driver.py`/`engines.yaml`. Alle Tests wurden nach Abschluss aufgeräumt (`tmux kill-server`, Scratch-Verzeichnis gelöscht). Kein Produktivcode wurde verändert.

### Kernbefund: naives `tmux new-session "<cli-befehl>"` bricht Claude sofort
Claudes `-p --input-format stream-json` prüft beim Start, ob `stdin` ein TTY ist, und bricht **sofort** ab (`Error: Input must be provided either through stdin or as a prompt argument when using --print`), wenn der Befehl direkt als tmux-Pane-Kommando läuft — eine tmux-Pane liefert immer ein PTY als stdin, nie eine reine Pipe. Codex zeigt dasselbe Muster indirekt (verlangt echten Prompt-Inhalt über stdin, kein PTY-Sonderfall beobachtet, da hier stdin ohnehin per Datei-Redirect befüllt wird, siehe unten). Damit ist Design-Frage 3 ("braucht tmux einen echten interaktiven TTY-Modus?") beantwortet: **Nein — im Gegenteil, das bestehende JSON-Stream-Protokoll aller drei Engines bleibt unverändert nutzbar, aber nur wenn stdin explizit NICHT die Pane-PTY ist.**

**Lösung, verifiziert für alle drei Engines:**
- **Long-lived Engines (Claude; generisch auch nicht-oneshot `generic_cli`-Profile):** Der Pane-Befehl öffnet zuerst selbst eine benannte Pipe read-write (`exec 3<>control.in; claude … <&3 > out.log 2> err.log`). Dieser Selbst-Open hält permanent einen Writer-Handle auf der FIFO — dadurch sieht der lesende Prozess **nie EOF**, auch wenn der Backend-Prozess, der zwischendurch in dieselbe FIFO schreibt, sein eigenes Schreib-Handle wieder schließt. Verifiziert: zwei komplett getrennte, nacheinander laufende externe Schreib-Kommandos (`echo … > control.in`) simulierten zwei unabhängige Backend-Prozess-Lebenszyklen (inkl. eines kompletten Bash-Tool-Neustarts dazwischen) — die Claude-Session blieb über beide Turns hinweg am Leben (`pane_dead=0`) und lieferte in beiden Fällen korrekte `result`-Events. **Ohne** den Selbst-Open-Trick (reines `< control.in`) beendete sich Claude sofort sauber (Exit 0), sobald der einzige externe Schreiber seine Pipe schloss — das hätte in Produktion jeden Backend-Neustart in ein stilles, vermeintlich "sauberes" Sessionende verwandelt (fatal für das zentrale Akzeptanzkriterium "Backend-Restart beendet tmux-Agenten nicht").
- **Oneshot-Engines (Codex, OpenCode, Hermes):** Kein FIFO-Trick nötig. Der Prompt wird vor dem `tmux new-session`-Aufruf in eine Temp-Datei geschrieben und per echtem Datei-Redirect (`< prompt.txt`) als stdin übergeben — das ist bereits eine reine Datei, kein PTY, daher kein TTY-Fehler. Jeder Turn ist ohnehin ein neuer Prozess (Resume via `resume_argv_template`/`thread_id`/`sessionID`), es gibt zwischen Turns keine offene Pipe zu erhalten. Verifiziert mit Codex (`sleep 4`-Tool-Call + Antwort, sauberer `turn.completed`) und OpenCode (`step_finish` mit korrektem `cost`).

### Output-Capture: `pipe-pane` + `capture-pane` funktionieren unverändert (Design-Frage 1 beantwortet)
Wenn `stdout` NICHT umgeleitet wird (reines JSON-Zeilen-Protokoll ohne ANSI/Cursor-Tricks, anders als der interaktive REPL), landet der Event-Stream unverändert im Pane-Scrollback. Verifiziert:
- `tmux pipe-pane -o "cat >> live.log"` lieferte die Live-Events 1:1 (identisch zum heutigen `stream.readline()`-Loop) — geeignet als Live-Quelle für den bestehenden `handle_event`/WebSocket-Pfad.
- `tmux capture-pane -p -S -N` lieferte denselben Inhalt als Snapshot — geeignet für Reconnect-/Geräte-Backfill, `-S` liefert direkt die geforderte Bounded-Capture (Zeilen-Limit über den Scrollback-Start).
Empfehlung: **beide kombinieren**, wie im Tech Design (E) bereits vorgeschlagen — `pipe-pane` für den laufenden Transkript-Zufluss, `capture-pane -S -N` für den einmaligen Backfill bei Connect/Gerätewechsel. Damit ist keine Polling-Capture-Lösung nötig.

### Stop-Sauberkeit
`tmux kill-session` beendete den CLI-Kindprozess in allen Tests zuverlässig und ohne Waisenprozess (verifiziert per `ps --ppid <pane_pid>` vor und `ps -p <child_pid>` nach dem Kill). Der tmux-Server fährt bei der letzten Session automatisch herunter.

### Neue, im ursprünglichen Tech Design nicht erfasste Erkenntnis: der eigentliche Resilienz-Gewinn kommt vom **Prozessbaum**, nicht vom Terminal
Weil in beiden Mustern (FIFO-Selbst-Open bzw. Datei-Redirect) `stdin`/`stdout` gar nicht mehr über die PTY-Interaktion laufen, ist die "Terminal-Emulation" von tmux für den Datenfluss selbst **nicht** der tragende Teil — tmux dient hier primär als **Prozess-Supervisor außerhalb des `jupiter-backend`-Cgroups** (der tmux-Server läuft nicht als Kind von `uvicorn`/systemd-Unit `jupiter-backend.service`, daher überlebt er `systemctl restart jupiter-backend` unabhängig von dessen `KillMode`). Das ist der eigentliche Mechanismus hinter Akzeptanzkriterium "Backend-Restart beendet tmux-Agenten nicht" — nicht die PTY an sich. Folgerung für die Transport-Abstraktion (Tech Design E/G): `TmuxTransport.send_input()` sollte **kurzlebig** öffnen-schreiben-schließen (wie ein normaler Dateihandle), niemals einen dauerhaften FD aus dem Backend-Prozess offen halten — die Offenhaltung muss aus dem Pane-Wrapper-Skript selbst kommen, sonst wiederholt sich exakt der oben beobachtete Bug (stiller, vermeintlich sauberer Sessionabbruch bei jedem Backend-Neustart).

### Empfehlungen für die offenen Design-Fragen (Abschnitt I)
1. **`pipe-pane` ist stabil genug** — kombiniert mit `capture-pane -S -N` für Backfill. Kein Polling nötig.
2. **Capture-Cursor:** einfachste robuste Variante ist die Byte-/Zeilenlänge der bereits konsumierten `pipe-pane`-Log-Datei als Cursor (Datei wächst nur an); `capture-pane -S -<N>` für Backfill braucht keinen Cursor, da es ohnehin dedupliziert gegen das bereits im Transkript vorhandene Ende abgeglichen werden muss (z. B. über die letzte bekannte `uuid`/`request_id` aus dem JSON, nicht über Byte-Offsets).
3. **Kein echter interaktiver TTY-Modus nötig** — im Gegenteil, er würde das bestehende, robuste JSON-Event-Parsing zerstören. Die Lösung ist FIFO-Selbst-Open (long-lived) bzw. Datei-Redirect (oneshot), nicht ein TTY-taugliches UI.
4. Eingabe-Arbitration wurde im Spike nicht getestet (reines Backend-Verhalten, kein tmux-Aspekt) — bleibt offen für die Implementierungsphase.

### Scope-Implikation für Schritt 2 (Backend-Transport-Schicht)
Die o. g. Prozessbaum-Erkenntnis ist eine **Korrektur** am Tech Design, kein Show-Stopper: `TmuxTransport` muss beim Anlegen einer Session ein kleines Wrapper-Kommando erzeugen (FIFO anlegen, `exec N<>fifo` voranstellen bei long-lived Profilen; Prompt vorab in eine Temp-Datei schreiben bei oneshot-Profilen), statt die vorhandenen `build_argv()`-Ergebnisse unverändert 1:1 als Pane-Kommando zu übergeben. Das ist ein klar abgegrenzter, testbarer Baustein unterhalb der bestehenden Driver-Klassen und ändert nichts an `StreamEvent`/`parse_line`/Adaptern.

**Empfehlung:** Vor Beginn von Schritt 2 (Transport-Abstraktion in `manager.py`/neue `TmuxTransport`-Klasse, SQLite-Schema-Erweiterung, Liveness-Anpassung) Rücksprache mit dem Nutzer — dieser Schritt fasst eine 2000+-Zeilen-Produktivdatei an, die den direkten Transport für Claude/Codex/OpenCode/Swisscom im Live-Betrieb trägt. Der Spike selbst hat keinen Produktivcode berührt.

---

## Implementierungsstand Schritt 2 (Backend Developer, 2026-07-06)

Nach Nutzer-Freigabe wurde Schritt 2 begonnen — bewusst additiv und ohne die produktiven Treiber (`claude_driver.py`, `generic_cli_driver.py`) oder den Kontroll-Fluss in `manager.py` (Create/`_resume`/`rehydrate`) anzufassen. Direct-Transport ist dadurch byte-identisch unverändert; volle Regression (1108 Tests, siehe unten) bestätigt das.

**Gebaut + getestet:**
- `backend/app/engine/transport.py` — `Transport`-ABC + `DirectTransport` (Referenz-Nachbildung des heutigen `asyncio.subprocess`-Verhaltens) + `TmuxTransport` (spike-validierte FIFO-Selbst-Open- bzw. Datei-Redirect-Logik, Naming/Sanitizing, `capture_backfill()` als Byte-Offset-Cursor, `kill()`/`session_exists()`/`pane_pid()`). Noch von KEINEM Treiber genutzt — eigenständig testbar.
- `backend/tests/test_proj63_tmux_transport.py` (9 Tests, echte tmux-Sessions gegen Fake-CLI-Skripte, Muster wie `test_proj48_codex.py`): Long-lived-Multi-Turn übersteht unabhängige Schreiber-Öffnen/Schließen-Zyklen (Kernbefund des Spikes) ohne fälschliches EOF; Oneshot-Respawn über mehrere Turns mit kumulativem Log; sauberer Stop ohne Waisenprozess; Exit-Code-Erfassung; bounded Backfill; klarer `TransportError` bei fehlendem tmux-Binary.
- `backend/app/db/session_index.py` — Schema additiv erweitert um `transport`, `tmux_session`, `tmux_pane`, `tmux_capture_cursor`, `transport_status` (Spalten + idempotente `_MIGRATIONS`-Einträge, bestehende DBs migrieren automatisch beim nächsten Start). Roundtrip-Test in `test_proj14_haertung.py` ergänzt.
- `backend/app/engine/transport_settings.py` + `GET/PUT /settings/transports` (Route in `routes/settings.py`, Schemas in `schemas/settings.py`) — globaler Default + Engine-Overrides, YAML-backed/live mtime-geprüft wie Liveness/Watchdog. `resolve(engine_key)` fällt IMMER auf `"direct"` zurück, wenn das tmux-Binary fehlt — eine konfigurierte `tmux`-Wahl kann nie zum Startfehler führen. 10 Tests in `test_proj63_transport_settings.py`.
- `backend/app/config.py` — neue Settings `tmux_bin`, `tmux_data_dir`, `transport_config_path`.

**Bewusst NICHT angefasst (nächster, risikoreicherer Teilschritt):**
- `LaunchSpec.transport`-Feld + tatsächliche Nutzung von `TmuxTransport`/`DirectTransport` in `ClaudeCodeDriver`/`GenericCliDriver` — bisher wählt jede Session weiterhin zwangsläufig den heutigen direkten Pfad.
- `SessionState`-Felder (`transport`, `tmux_session`, …) in `manager.py` + `to_read()`/`_row()` — die neuen SQLite-Spalten existieren, werden aber von keiner echten Session befüllt.
- `derive_liveness()`-Anpassung für tmux-Sessions — zurückgestellt, weil ohne Treiber-Verdrahtung kein realer Codepfad die tmux-Verzweigung je erreichen würde (spekulative, untestbare Logik in einer sicherheitskritischen Funktion wäre selbst ein Risiko).
- `GET /sessions/{id}/transport`-Diagnose-Endpunkt (Tech Design C) — hängt an den `SessionState`-Feldern oben.

**Regression:** `conda run -n Dashboard --no-capture-output python -m pytest -q` → 1108 passed, 1 deselected (vorbestehende, unabhängige Skill-Drift zwischen `~/.claude` und `~/.codex`, siehe `test_proj50_codex_abc.py::test_generator_check_passes_no_drift` — nicht durch PROJ-63 verursacht).

**Nächster Schritt:** Treiber-Verdrahtung (`LaunchSpec.transport`, Driver-Anpassung, `SessionState`-Felder, Liveness) — berührt den Live-Betrieb direkt, daher vor Beginn erneut mit dem Nutzer abstimmen, mit welcher Engine zuerst (Spec-Empfehlung: Codex/OpenCode vor Claude) und ob zunächst nur hinter einem Feature-Flag ohne Frontend-Sichtbarkeit.

---

## Treiber-Verdrahtung: Codex/OpenCode zuerst, mit Frontend-Sichtbarkeit (Backend Developer, 2026-07-06)

Nutzer-Entscheidung: Codex/OpenCode zuerst verdrahten (Claude bleibt unberührt), Transport-Badge im Cockpit sichtbar.

**Backend:**
- `LaunchSpec.transport` (Default `"direct"`) — `base.py`.
- `SessionState.transport` (Default `"direct"`) in `manager.py`, in `to_read()` (Cockpit-Badge), `_row()`/`_state_from_row()` (Persistenz/Rehydrate) verdrahtet.
- `SessionManager.create()`: für `profile.driver == DRIVER_GENERIC_CLI` (Codex/OpenCode/Hermes) wird `transport_settings.transport_store.resolve(profile.key)` aufgelöst und am State gehalten; **Claude wird nie aufgelöst, bleibt immer `"direct"`** (auch wenn der globale Default `tmux` wäre — Test `test_claude_never_resolves_tmux_even_if_global_default_is_tmux`).
- `SessionManager._resume()`: nutzt `state.transport` (NICHT erneut `resolve()`) — eine laufende/rehydrierte Session wechselt nicht durch eine spätere Settings-Änderung den Transport (Test `test_resume_keeps_original_transport_even_if_settings_changed_meanwhile`).
- `GenericCliDriver` (`generic_cli_driver.py`): neuer `_transport_mode`/`_transport_obj`-Zweig in `_spawn`/`_spawn_tmux`/`is_alive`/`pid`/`stop`/`_read_stdout`. Bei `transport="tmux"` wird pro Turn `TmuxTransport.spawn()` (Oneshot: Prompt vorab in eine Datei, `stdin_file`-Redirect) aufgerufen; eine gleichnamige Vorgänger-Session wird dabei zuerst beendet (stabile tmux-Session-Identität über alle Turns einer Jupiter-Session hinweg). `is_alive`/`pid` nutzen `pid_alive(transport.pid)` — **dieselbe** OS-Signal-0-Prüfung wie im direct-Pfad, da `TmuxTransport.pid` die echte OS-PID des Pane-Prozesses cacht; `derive_liveness()` in `manager.py` musste dafür NICHT angepasst werden (Annahme aus dem vorigen Zwischenstand war zu pessimistisch). Direct-Modus bleibt Zeile für Zeile unverändert (jeder neue Zweig ist ein `if self._transport_mode == "tmux"`-Ast, der für `"direct"` nie betreten wird).
- Gefundener + gefixter Bug beim Bau: `stop()` prüfte zuerst `if self._proc is None` — im tmux-Modus ist `self._proc` IMMER `None`, das hätte `stop()` auf ein reines "closed"-Event ohne tatsächliches Beenden der tmux-Session reduziert (Prozess-Leck). Test `test_stop_actually_kills_tmux_session` deckt das ab.
- `TmuxTransport` (transport.py) um `prepare_prompt_file()` (Prompt-Datei je Turn) und einen gecachten `pid` (`pane_pid()` einmalig bei `spawn()`, synchron abrufbar) erweitert; `kill()`/`terminate()` invalidieren den Liveness-Cache sofort (kein Warten auf Cache-Ablauf, bis der Reader-Loop das Prozessende bemerkt).

**Tests (alle neu, 1117/1117 Backend-Tests grün inkl. dieser):**
- `test_proj63_generic_cli_tmux.py` (5): Einzelturn über tmux, Multi-Turn-Resume behält Kontext + dieselbe tmux-Session, Fehler-Exit meldet stderr ohne die interne Exit-Marker-Zeile, `stop()` beendet die tmux-Session wirklich, Default ohne `transport`-Angabe bleibt `"direct"`.
- `test_proj63_manager_transport.py` (4): generic_cli löst `tmux` nur bei konfiguriertem Override auf, Default `direct`, Claude bleibt immer `direct`, Resume behält den ursprünglichen Transport.

**Frontend (Next.js, Sichtbarkeit wie gewünscht):**
- `lib/types.ts`: `Session.transport: "direct" | "tmux"` (neuer Pflicht-Feldtyp `SessionTransport`) — alle bestehenden Test-Fixtures (`gantt-chart.test.tsx`, `active-session-panel.test.tsx`, `session-tile.test.tsx`, `status.test.ts`, `active-session.test.ts`, `usage.test.ts`) um `transport: "direct"` ergänzt.
- `components/cockpit/session-tile.tsx`: neuer `tmux`-Badge neben dem bestehenden Engine-Badge — **nur sichtbar, wenn `transport === "tmux"`** (Default `direct` bleibt stumm, analog zum Claude-Engine-Badge). Tooltip erklärt den Nutzen ("übersteht Backend-Neustarts").
- 2 neue Vitest-Fälle in `session-tile.test.tsx` (direct → kein Badge, tmux → Badge sichtbar). `npx tsc --noEmit` und `npx eslint` sauber; 2 vorbestehende, unabhängige Test-Fehlschläge (`file-preview.test.tsx`, `sidebar-prefs-provider.test.ts`) bestätigt NICHT durch diese Änderung verursacht (per `git stash` gegengeprüft).

**Bewusst noch nicht angefasst:**
- `ClaudeCodeDriver` — bleibt unverändert, wertet `spec.transport` gar nicht aus (Rollout-Reihenfolge laut Spec: Codex/OpenCode zuerst).
- `GET /sessions/{id}/transport`-Diagnose-Endpunkt und `tmux_session`/`tmux_pane`/`transport_status`-Befüllung am `SessionState` — die Cockpit-Sichtbarkeit ist über das einfache `transport`-Badge bereits erfüllt; der Diagnose-Endpunkt ist ein Ausbau für Betrieb/QA, kein Blocker für den Rollout.
- Aufräumen der tmux-Arbeitsverzeichnisse (`~/jupiter-data/tmux/<session>/`) nach einem endgültigen `stop()`/`delete()` — Dateien bleiben aktuell liegen (kleine Disk-Hygiene-Lücke, kein Korrektheits-Problem).
- Ein Betreiber muss den Transport aktiv über `PUT /settings/transports` (`engine_overrides: {"codex": "tmux"}` bzw. `"opencode": "tmux"`) einschalten — ohne diesen Schritt bleibt ALLES beim heutigen `direct`-Verhalten (Default bleibt konservativ, wie in der Spec gefordert).

---

## QA Test Results

**Tested:** 2026-07-06
**Backend:** isolierte Scratch-Instanz `uvicorn app.main:app --port 8091` (eigene SQLite-DB, eigenes `tmux_data_dir`, eigene `engines.yaml`/`transport.yaml` — der produktive `jupiter-backend` auf Port 8000 wurde NICHT angefasst/neu gestartet)
**Frontend:** `npx vitest`, `npx tsc --noEmit`, `npx eslint` (kein laufendes Next.js nötig für diesen Umfang — reine Komponenten-/Typtests)
**Tester:** QA Engineer (AI)
**Getestete Engines:** Codex (`codex-cli` echt, Subscription-Auth), OpenCode (`opencode` echt, OpenRouter `minimax-m3`), Claude (`sonnet`/`haiku`, Regressionscheck) — alles reale CLI-Läufe, keine Fakes.

### Wichtiger Scope-Hinweis
Diese Spec beschreibt ein sehr breites Zielbild (Multi-Device-Snapshot, WS-Backfill, Reattach, Diagnose-Endpunkt, Eingabe-Arbitration, `derive_liveness()`-Tmux-Bewusstsein). Der aktuelle Implementierungsstand deckt davon **nur** die Spike-validierte Transport-Schicht + die Verdrahtung für Codex/OpenCode + das Cockpit-Badge ab (siehe "Implementierungsstand"/"Treiber-Verdrahtung" oben). Alles, was darüber hinausgeht, ist als "Nicht getestet — noch nicht implementiert" markiert, nicht als "durchgefallen".

### Acceptance Criteria Status (aus dem Original-Spec)

- [x] Transport-Option `direct`/`tmux` konfigurierbar, Default konservativ `direct` — **PASS** (`GET/PUT /settings/transports`, verifiziert: frischer Store liefert `default_transport=direct`, `engine_overrides={}`).
- [ ] Neue Session im tmux-Transport startbar, eindeutige tmux-Session/Pane pro Jupiter-Session, tmux-ID im Live-Index persistiert — **FAIL, siehe BUG-1**. Die Session/FIFO/Logs werden zwar angelegt, aber `POST /sessions` schlägt für Codex UND OpenCode **reproduzierbar (3/3)** fehl, bevor der Turn nutzbar ist.
- [ ] Eingaben ohne Schreiben auf geschlossene stdin-Pipes senden — **Nicht erreichbar getestet** (Session kommt wegen BUG-1 nie in einen Zustand, in dem ein Folge-Turn gesendet werden könnte). Der zugrunde liegende FIFO-Selbst-Open-Mechanismus selbst ist aber über die Unit-/Integrationstests (`test_proj63_tmux_transport.py`, `test_proj63_generic_cli_tmux.py`, alle mit synthetisch verzögerten Fake-Skripten) isoliert nachgewiesen und dort grün — das Timing-Problem tritt nur mit der **echten**, sehr schnellen CLI-Antwortzeit auf (s. u.).
- [ ] Output zuverlässig erfassen und dem Transkript-/WS-Pfad zuführen — **Nicht erreichbar getestet** (gleicher Grund).
- [ ] Backend-Restart beendet tmux-Prozesse nicht, Wiederfund im Cockpit — **Nicht getestet** (kein Restart-Rehydrate-Pfad für tmux implementiert, siehe "Bewusst noch nicht angefasst" oben — das ist erwarteter, dokumentierter Stand, kein neuer Bug).
- [ ] Geräte-/Browserwechsel, Multi-Device-Snapshot, Eingabe-Arbitration, Diagnose-Endpunkt — **Nicht getestet — nicht implementiert** (außerhalb des aktuellen Verdrahtungs-Umfangs).
- [x] Direct-Transport bleibt unverändert/regressionsfrei für Claude, Codex, OpenCode — **PASS**. Claude-Session (direct) auf der Scratch-Instanz erfolgreich erstellt, lief in `waiting`, sauber gestoppt. Codex-Session **ohne** tmux-Override (`engine_overrides={}`) lief normal in `running` an. Voller Backend-Testlauf (`pytest`, 1117 Tests) grün.
- [x] Bei fehlendem tmux klare deutsche Meldung + Fallback auf direct — **PASS für die Settings-Auflösung** (`TransportStore.resolve()` fällt bei fehlendem Binary nachweislich auf `direct` zurück, unit-getestet). **Für den Live-Pfad nicht separat nachgestellt** (tmux ist auf diesem Host vorhanden) — sollte aber wegen BUG-2 (s. u.) ohnehin nicht zu einer sauberen Meldung führen, sondern zu einem rohen 500er.
- [ ] Spike-Matrix (Start/Folge-Eingabe/langer Tool-Lauf/Restart/Stop/Reattach) je Engine — nur "Start" real geprüft (und dort fehlgeschlagen, BUG-1); der Rest baut darauf auf und wurde nicht erreicht.

### Bugs Found

#### BUG-1: `TmuxTransport.spawn()` schlägt bei jedem realen, schnellen Oneshot-Turn fehl (Codex UND OpenCode, 3/3 reproduziert)
- **Severity:** Critical
- **Root Cause:** `spawn()` ruft zuerst `tmux new-session -d ...` auf und **danach** in einem zweiten, separaten `tmux`-Aufruf `set-option -t <session> remain-on-exit on`. Ist der gestartete Oneshot-Befehl (echter `codex exec …`/`opencode run …`) schnell fertig — was er in der Praxis fast immer ist, besonders bei gecachtem Kontext/kurzen Antworten — beendet sich die Pane/das Fenster/die Session, BEVOR der zweite `set-option`-Aufruf läuft. Da es die einzige Session war, fährt der tmux-Server selbst herunter; der zweite Aufruf trifft auf "no server running" und wirft `TransportError`.
- **Beweis (echter Codex-Lauf, reproduziert 2/2, identisch für OpenCode 1/1):**
  ```
  app.engine.transport.TransportError: tmux set-option -t jupiter-9bcf776f-... remain-on-exit on
  fehlgeschlagen (Code 1): no server running on /tmp/tmux-1000/default
  ```
  `out.log`/`err.log` der betroffenen Session zeigen: der Codex-Turn LIEF vollständig durch und lieferte ein korrektes `turn.completed` — das Problem ist rein die Nachbereitung in `TmuxTransport`, nicht die Engine selbst.
- **Steps to Reproduce:**
  1. `PUT /settings/transports` mit `engine_overrides: {"codex": "tmux"}`.
  2. `POST /sessions` mit `engine=codex`, kurzem Prompt ("Antworte nur mit OK").
  3. Erwartet: Session startet, `status` wird `waiting`/`running`, `result`-Event sichtbar.
  4. Tatsächlich: `POST /sessions` liefert **immer** (in diesem Test 3/3) eine 500-Antwort; die Session landet in `status=error` mit exakt obiger Meldung.
- **Impact:** Der komplette in dieser Session verdrahtete Rollout (Codex/OpenCode auf tmux) ist in der jetzigen Form **funktionsunfähig** — nicht nur ein Rand- oder Timing-Sonderfall, sondern der Normalfall bei realen, performanten CLI-Antworten. Die Unit-/Integrationstests haben das nicht gefangen, weil ihre Fake-Skripte (mit Python-Overhead + Adapter-Parsing) offenbar knapp langsamer sind als die Race-Schwelle bzw. weil die Tests keinen echten Prozess-Turnaround im Sub-100ms-Bereich erzeugen.
- **Priority:** Fix before deployment (Blocker für den vom Nutzer gewünschten Rollout).

#### BUG-2: Fehlgeschlagener Session-Start liefert rohen 500 statt strukturierter Fehlermeldung
- **Severity:** Medium
- **Steps to Reproduce:** Wie BUG-1. `routes/sessions.py: create_session()` fängt `SessionLimitError`, `EngineUnavailableError`, `ValueError`, `FileNotFoundError` ab, aber **keine** `TransportError` — die Exception aus `manager.create()` (die sie korrekt weiterreicht, nachdem sie den State auf `ERROR` gesetzt hat) landet unbehandelt beim FastAPI-Default-Handler → `500 Internal Server Error` ohne nutzbare `detail`-Message für den Client. Der Session-Zustand selbst ist korrekt (`status=error`, `error`-Feld gefüllt) und über `GET /sessions` sichtbar — das Problem ist nur die unmittelbare HTTP-Antwort auf den `POST`.
- **Priority:** Fix before deployment (schlechte Diagnostizierbarkeit für Frontend/Betreiber, besonders relevant, weil BUG-1 diesen Pfad aktuell immer auslöst).

#### BUG-3: `transport`-Feld fehlt in der API-Antwort (Pydantic-Schema filtert es heraus) — Frontend-Sichtbarkeit ist tot
- **Severity:** High
- **Root Cause:** `SessionState.to_read()` liefert zwar `"transport": self.transport` (verifiziert im Python-Objekt), aber `routes/sessions.py` deklariert `response_model=SessionRead`/`response_model=list[SessionRead]` bzw. `SessionDetail`. Die Pydantic-Modelle in `schemas/sessions.py` (`SessionRead`, `SessionDetail`) haben **kein** `transport`-Feld — FastAPI/Pydantic v2 filtert unbekannte Dict-Schlüssel beim Response-Serialisieren heraus.
- **Beweis:** `GET /sessions` auf der Scratch-Instanz — für alle 5 angelegten Test-Sessions (Claude direct, Codex tmux ×2, OpenCode tmux, Codex direct) fehlt der Schlüssel `"transport"` komplett in der JSON-Antwort (`'transport' in d` → `False` für jede einzelne).
- **Impact:** Das in dieser Session gebaute Next.js-Badge (`session-tile.tsx`) kann **niemals** ein `tmux`-Badge anzeigen, weil `session.transport` vom Backend nie ankommt — es ist immer `undefined`. Das widerspricht direkt der expliziten Nutzeranforderung "Mit Frontend Sichtbarkeit" aus dem vorigen Turn. Kein reines "noch nicht verdrahtet", sondern ein konkreter, stiller Bruch der Frontend-Backend-Vertragskette, den weder die Backend- noch die Frontend-Tests gefangen haben (Backend-Tests prüfen `state.to_read()`/`SessionState` direkt, nie die tatsächliche HTTP-Response; Frontend-Tests nutzen handgebaute Fixtures, nie echte Backend-Payloads).
- **Priority:** Fix before deployment (Blocker für "Mit Frontend Sichtbarkeit").

### Weitere Beobachtungen (kein Bug-Ticket, aber relevant)

- **Ressourcen-Leck bei fehlgeschlagenem Start:** `manager.create()` setzt bei einer Exception aus `driver.start()` den State auf `ERROR` und reicht sie weiter, ruft aber nie `driver.stop()`/eine Aufräumroutine auf. Da BUG-1 JEDEN echten tmux-Codex/OpenCode-Start treffen dürfte, bedeutet das: **jeder** fehlgeschlagene Versuch hinterlässt ein Arbeitsverzeichnis (`FIFO`, `prompt-N.txt`, `out.log`, `err.log`) unter `tmux_data_dir`, das nie aufgeräumt wird. In diesem QA-Lauf: 3 fehlgeschlagene Starts → 3 liegen gebliebene Verzeichnisse. Auf Dauer ein Speicher-/Aufräum-Problem, nicht nur beim erfolgreichen Stop (wie im vorigen Zwischenstand vermerkt), sondern gerade auch im (aktuell sehr häufigen) Fehlerfall.
- **Dateiberechtigungen (Low, kein neues Problem):** Prompt-/Log-Dateien unter `~/jupiter-data/tmux/<session>/` sind `644` (world-readable), Verzeichnisse `755` — identisch zur bestehenden Praxis bei `session_index.db` (ebenfalls `644`). Kein neu eingeführtes Sicherheitsniveau, aber auf einem Mehrbenutzer-Host theoretisch einsehbar für andere lokale User; nur der Vollständigkeit halber notiert.
- **Shell-Injection:** Kein Fund. `argv`/`cwd` werden in `TmuxTransport._pane_command_*` konsequent per `shlex.quote()` in den Pane-Befehl eingebettet; Session-Namen kommen ausschließlich aus serverseitigen UUIDs (`sanitize_tmux_session_name`), nie aus Nutzereingaben. `SessionCreate` (Pydantic) hat kein client-steuerbares `transport`-Feld — die Wahl ist ausschließlich serverseitig über `engine`+Settings auflösbar.
- **Auth-Gate:** `GET/PUT /settings/transports` korrekt hinter `Depends(get_current_user)` (über `dependencies=auth_gate` beim Router-Include in `main.py`) — vor dem ersten Bootstrap anonym erlaubt (dokumentiertes, gewolltes Verhalten), danach `401` ohne gültiges Token. Verifiziert.
- **Regression:** Voller Backend-Testlauf (`pytest`, 1117 Tests) weiterhin grün; Claude (direct) und Codex (direct, ohne Override) funktionieren auf der Scratch-Instanz einwandfrei — die Regression auf den bestehenden Direct-Pfad ist NICHT betroffen.

### Summary
- **Acceptance Criteria:** 3/9 klar PASS, 1/9 FAIL (BUG-1, zieht mehrere Folge-Kriterien mit sich), 5/9 nicht erreichbar/nicht implementiert (außerhalb des aktuellen Umfangs, kein neuer Fund).
- **Bugs Found:** 3 (1 Critical, 1 High, 1 Medium) + 1 dokumentiertes Ressourcen-Leck (kein Ticket, Verstärkung eines bereits bekannten Punkts).
- **Security:** Keine neuen Lücken gefunden (Injection/Auth/Client-Steuerbarkeit geprüft); Dateiberechtigungen konsistent mit bestehender Praxis.
- **Production Ready:** **NO**
- **Recommendation:** Vor jedem Rollout (auch nur intern) müssen BUG-1 (Blocker — Feature ist aktuell nicht nutzbar), BUG-3 (Blocker für die explizit gewünschte Frontend-Sichtbarkeit) und BUG-2 (bessere Fehlerdiagnose) behoben werden. Empfehlung für BUG-1: `remain-on-exit` VOR `new-session` serverweit setzen (`tmux set-option -g remain-on-exit on` einmalig, bevor die Session angelegt wird) statt danach — damit gilt die Option von Anfang an für die neu erstellte Session, ohne Zeitfenster.

---

## Bugfixes (Backend Developer, 2026-07-06)

Reihenfolge auf Nutzerwunsch: BUG-1 → BUG-3 → BUG-2. Alle drei behoben, regressionsgetestet (inkl. Stash-Gegencheck: jeder neue Test schlägt nachweislich fehl, wenn der jeweilige Fix rückgängig gemacht wird) und live gegen echte Codex-/OpenCode-Läufe re-verifiziert (neue isolierte Scratch-Instanz, Port 8092 — der produktive `jupiter-backend` wurde wieder nicht angefasst).

**BUG-1-Fix (`transport.py: TmuxTransport.spawn()`):** `new-session` + separater `set-option -t <session>`-Aufruf ersetzt durch EINEN chained tmux-Aufruf (`start-server ; set-option -g exit-empty off ; set-option -g remain-on-exit on ; new-session …`). Die Optionen gelten dadurch bereits BEVOR die Session angelegt wird — kein Zeitfenster mehr, in dem ein sofort fertiger Oneshot-Turn die Session/den Server verschwinden lässt. Nebeneffekt (gewollt): der tmux-Server bleibt jetzt dauerhaft als leichter Leerlauf-Prozess bestehen (`exit-empty off`), statt sich bei null Sessions selbst zu beenden — passt zum "persistenter Supervisor"-Architekturziel der Spec.
- Neuer Regressionstest `test_survives_an_instantly_completing_command` (`true`-Befehl — schneller als jeder reale CLI-Turnaround).
- **Beim Fixen selbst ein ZWEITES, dadurch aufgedecktes Timing-Problem gefunden und mitbehoben:** `first_spawn = not self._dir.exists()` war trügerisch, weil `GenericCliDriver._spawn_tmux()` über `prepare_prompt_file()` das Arbeitsverzeichnis bereits VOR `spawn()` anlegt — `out.log`/`err.log` wurden dadurch nie proaktiv erzeugt und existierten bisher nur zufällig, sobald die Pane-Shell ihr eigenes `>>`-Redirect geöffnet hatte. Der langsamere alte Zwei-Schritt-tmux-Aufruf gab dafür genug Zeit; der schnellere BUG-1-Fix deckte das Rennen auf (`FileNotFoundError` beim Öffnen von `out.log`, 4/5 in einer Testschleife). Fix: Dateien werden jetzt unabhängig von jeder "erster Spawn?"-Heuristik angelegt, falls sie fehlen (`if not self.out_path.exists(): write_bytes(b"")`) — idempotent, kein Trunkieren bei Turn-2+-Respawns.
- Live-Verifikation: echte Codex- UND OpenCode-Sessions unter `transport=tmux` starten jetzt fehlerfrei (`status=running`→`waiting`, kein `error`), inkl. Multi-Turn-Resume (Codex: Turn 1 „VERIFY-CODEX-TMUX-OK" → Turn 2 „VERIFY-CODEX-TURN2", Kontext erhalten, dieselbe tmux-Session), sauberer Stop/Delete, keine Waisen-tmux-Sessions danach.

**BUG-3-Fix (`schemas/sessions.py: SessionRead`):** Feld `transport: str = "direct"` ergänzt — vorher filterte Pydantic den von `SessionState.to_read()` gelieferten Schlüssel beim `response_model`-Serialisieren einfach heraus.
- 3 neue HTTP-Contract-Tests in `test_proj63_manager_transport.py` (`POST /sessions`, `GET /sessions`, `GET /sessions/{id}` — jeweils `resp.json()["transport"]` geprüft). Gegencheck: alle 3 schlagen mit `KeyError: 'transport'` fehl, wenn der Schema-Fix zurückgenommen wird.
- Live-Verifikation: `POST /sessions`-Antwort für die echten Codex-/OpenCode-Sessions enthält jetzt `"transport":"tmux"` — das Next.js-Badge aus der vorigen Runde bekommt den Wert damit tatsächlich zugestellt.

**BUG-2-Fix (`routes/sessions.py: create_session`):** `except TransportError as exc: raise HTTPException(503, str(exc))` ergänzt (zwischen den bestehenden `EngineUnavailableError`- und `FileNotFoundError`-Zweigen) — ein fehlgeschlagener Transport-Start liefert jetzt eine strukturierte 503 statt eines rohen 500.
- Neuer Test `test_post_sessions_transport_error_returns_503_not_raw_500` (monkeypatcht `TmuxTransport.spawn` auf einen erzwungenen `TransportError`). Gegencheck: schlägt ohne den Fix mit einer unbehandelten `TransportError` fehl (in Produktion: rohes 500).

**Nicht angefasst (bewusst außerhalb der drei benannten Bugs):** das dokumentierte Ressourcen-Leck bei fehlgeschlagenem Start (Arbeitsverzeichnis bleibt liegen) — war kein eigenes Bug-Ticket, sondern eine Beobachtung; durch den BUG-1-Fix jetzt ohnehin seltener (fehlgeschlagene Starts sind nicht mehr der Regelfall).

**Regression:** Voller Backend-Testlauf `pytest` → **1122 passed**, 1 deselected (weiterhin die vorbestehende, unabhängige Skill-Drift). 13 neue/geänderte Tests in dieser Runde, alle grün.

**Status:** Die drei benannten Bugs sind behoben und live re-verifiziert; Status bleibt formal **In Review**, bis eine erneute `/abc-qa`-Runde das offiziell bestätigt (auf Wunsch des Nutzers).

---

## QA Re-Test (Bestätigung nach Bugfixes, 2026-07-06)

**Backend:** neue, isolierte Scratch-Instanz `uvicorn app.main:app --port 8093` (eigene DB/Config, der produktive `jupiter-backend` auf Port 8000 wurde wieder NICHT angefasst/neu gestartet).
**Frontend:** `npx vitest run`.
**Tester:** QA Engineer (AI), unabhängig vom vorherigen Bugfix-Durchlauf neu aufgesetzt (frische Scratch-Instanz, frisches Bootstrap, keine Wiederverwendung der Backend-Entwickler-Verifikation).

### Automatisierte Tests
- Backend `pytest`: **1122 passed**, 1 deselected (vorbestehende, unabhängige Skill-Drift `test_proj50_codex_abc.py::test_generator_check_passes_no_drift`).
- Frontend `vitest`: **174 passed**, 2 vorbestehende, unabhängige Fehlschläge (`file-preview.test.tsx`, `sidebar-prefs-provider.test.ts`) — bereits im ersten QA-Durchlauf per `git stash` als nicht durch PROJ-63 verursacht bestätigt.

### Re-Verifikation der drei Bugs
- **BUG-1 (Critical):** Echte Codex- UND OpenCode-Sessions unter `transport=tmux` starten jetzt fehlerfrei (`status` durchläuft `running`→`waiting`/`done`, kein `error`). Zusätzlich getestet: **zwei gleichzeitige Codex-Sessions** (unterschiedliche tmux-Namen, kein Cross-Talk, beide liefern ihr jeweils korrektes Ergebnis) und ein **langer Tool-Lauf** (`sleep 5` über die Bash-Tool, Turn schließt danach korrekt mit `LONGRUN-OK` ab) — der Fix bricht schnelle UND langsame Turns nicht. **PASS.**
- **BUG-3 (High):** `POST /sessions`-Antworten für Codex/OpenCode enthalten `"transport":"tmux"`; für Claude/direct `"transport":"direct"` — in allen drei Response-Pfaden (`POST`, `GET`-Liste, `GET`-Detail) verifiziert. **PASS.**
- **BUG-2 (Medium):** Nicht erneut künstlich provoziert (bereits per Stash-Gegencheck auf Routen-Ebene bewiesen) — stattdessen indirekt bestätigt: kein einziger der zahlreichen Live-Aufrufe in dieser Runde produzierte einen rohen 500. **PASS (indirekt, Route-Level-Test bleibt die primäre Absicherung).**

### Zusätzliche Prüfungen (über die ursprünglichen 3 Bugs hinaus)
- **Neue Engine-Kombination gleichzeitig:** 2 parallele Codex-Sessions — kein Namens-/Ressourcenkonflikt, beide sauber stopp-/löschbar, keine Waisenprozesse danach (`ps -ef | grep "codex exec"` leer, `tmux list-sessions` leer).
- **Client-seitige Transport-Injektion:** `POST /sessions` mit `"transport":"direct"` im Payload (Feld existiert nicht in `SessionCreate`) → wird von FastAPI/Pydantic ignoriert, Server löst weiterhin serverseitig über Engine+Settings auf (`transport` blieb `tmux`, wie konfiguriert). Kein Bypass möglich.
- **Settings-Validierung:** `PUT /settings/transports` mit ungültigem Wert (`"ssh"`) → `400`, wie erwartet.
- **Auth-Gate:** `GET /sessions`, `GET /settings/transports` ohne Token nach Bootstrap → `401`. Bestätigt.
- **Regression:** Claude (direct) läuft unverändert (`thinking`+`text`-Transkript, `status=waiting`, `transport=direct`).
- **Cleanup:** Alle 8 in dieser Runde erzeugten Sessions über `stop`+`delete` sauber beendet; danach keine tmux-Sessions, keine verwaisten CLI-Prozesse.

### Summary
- **Bugs aus dem vorherigen Durchlauf:** 3/3 verifiziert behoben (BUG-1 Critical, BUG-3 High, BUG-2 Medium).
- **Neue Bugs in dieser Runde:** keine gefunden.
- **Security:** Client-seitige Transport-Injektion abgewehrt (Server-Resolution einzige Quelle der Wahrheit), Auth-Gate korrekt, Settings-Validierung korrekt.
- **Production Ready:** **YES** — für den vom Nutzer gewählten Umfang (Codex/OpenCode über `tmux`, opt-in via Settings, Claude unberührt auf `direct`). Weiterhin außerhalb des Umfangs (nicht implementiert, kein Blocker für diesen Rollout): Backend-Restart-Rehydrate für tmux-Sessions, Multi-Device-Snapshot/Backfill, Diagnose-Endpunkt, Eingabe-Arbitration — siehe "Bewusst noch nicht angefasst" weiter oben.
- **Recommendation:** Freigegeben für `/abc-deploy`. Nach dem Deploy muss ein Betreiber `PUT /settings/transports` mit `engine_overrides: {"codex":"tmux","opencode":"tmux"}` aufrufen, damit der neue Transport tatsächlich aktiv wird — der Default bleibt bewusst `direct`.

---

## Deployment

**Production URL:** https://jupiter.auxevo.tech
**Deployed:** 2026-07-07 · **Version:** 0.27.12
**Host:** host-nativ auf dem Dev-VPS (systemd `jupiter-backend`/`jupiter-frontend`, Auto-Deploy via GitHub-Webhook auf `main` — kein Dokploy/Container, siehe [[jupiter-deployment]])

**Was ausgeliefert wurde:**
- `Transport`-Abstraktion (`direct`/`tmux`) unterhalb der CLI-Engine-Treiber (`transport.py`, `transport_settings.py`).
- `GenericCliDriver` (Codex/OpenCode/Hermes) kann Sessions über `tmux` statt direkt als Backend-Kindprozess laufen lassen — Default bleibt `direct`.
- Neue Settings-API `GET/PUT /settings/transports` (globaler Default + Engine-Overrides).
- Cockpit-Badge (`tmux`) in der Session-Kachel, sichtbar sobald eine Session tatsächlich über tmux läuft.
- `ClaudeCodeDriver` bewusst unverändert (Rollout-Reihenfolge: Codex/OpenCode zuerst).

**Betreiber-Schritt nach dem Deploy (manuell, nicht Teil des Deploys):**
```bash
curl -X PUT https://jupiter.auxevo.tech/api/settings/transports \
  -H "Authorization: Bearer <token>" -H 'Content-Type: application/json' \
  -d '{"engine_overrides": {"codex": "tmux", "opencode": "tmux"}}'
```
Ohne diesen Schritt bleibt ALLES beim heutigen `direct`-Verhalten (Default konservativ, wie in der Spec gefordert).

**Ausstehende Browser-Smoke-Tests (manuell durch den Nutzer, nicht headless verifizierbar):**
- [ ] Cockpit-Session-Liste zeigt den `tmux`-Badge, sobald eine Codex-/OpenCode-Session mit aktiviertem Override läuft.
- [ ] Neue-Session-Dialog/Settings-UI (falls vorhanden) zeigt weiterhin korrekt an, welcher Transport aktiv ist.

**Bekannte, bewusst nicht in diesem Deploy enthaltene Folgearbeiten:** Backend-Restart-Rehydrate für tmux-Sessions, Multi-Device-Snapshot/Backfill, `GET /sessions/{id}/transport`-Diagnose-Endpunkt, Eingabe-Arbitration, Aufräumen liegen gebliebener tmux-Arbeitsverzeichnisse nach Stop/Fehlschlag.
