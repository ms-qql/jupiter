# PROJ-27: Verifizierter Liveness-Indikator + Reanimieren hängender Sessions

## Status: Architected
**Created:** 2026-06-24
**Last Updated:** 2026-06-24

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — liefert den Live-Event-Stream + Subprozess (PID), an dem Lebendigkeit verifiziert wird.
- Requires: PROJ-3 (Cockpit) — der Indikator lebt an der Session-Kachel/-Zeile und im Session-Detail.
- Requires: PROJ-14 (Härtung) — nutzt den vorhandenen **PID-Lebendigkeits-Check** (`os.kill(pid,0)`/`_pid_alive`) und den **`claude --resume`-Reanimations-Pfad** (rehydrierte/verwaiste Sessions → Resume).
- Verwandt: PROJ-16 (Watchdog) — dessen `max_idle_seconds`/Fortschritts-Uhr ist ein Stillstands-Signal; hier wird es zu einem **hintergrund-getriebenen** Hänger-Erkenner ausgebaut (PROJ-16 wertet nur am nächsten Tool-Gate aus).

## Beschreibung
Sessions laufen teils sehr lange ohne sichtbare Rückmeldung. Heute lässt sich nicht unterscheiden, ob eine Session **noch aktiv arbeitet** oder sich **aufgehängt** hat — eine mitlaufende Uhr beweist nichts. Dieses Feature führt ein **verifiziertes Lebenssymbol** pro Session ein, das auf einem **tatsächlich geprüften Heartbeat** beruht (Prozess lebt + Stream produziert/erwartet legitim Fortschritt), nicht auf Zeitablauf allein.

Erkennt das System einen **Hänger** (Prozess lebt nominell, aber kein Fortschritt jenseits der Schwelle / Stream tot), wird die Session als „hängt" markiert und **automatisch ein Reanimations-Versuch** über den vorhandenen `claude --resume`-Pfad gestartet (Variante B). Schlägt der Auto-Versuch fehl oder ist die Session bereits beendet/im Archiv, steht zusätzlich ein **manueller „Reaktivieren"-Knopf** bereit — entsprechend dem heute schon funktionierenden Ablauf „Session beenden → Archiv → wiederbeleben → läuft korrekt weiter".

## User Stories
- Als Nutzer möchte ich pro Session ein **verifiziertes Lebenssymbol** sehen, das wirklich geprüft ist (nicht nur eine laufende Uhr), um auf einen Blick zu erkennen, ob die Session aktiv ist oder hängt.
- Als Nutzer möchte ich, dass eine **als hängend erkannte Session automatisch reanimiert** wird, ohne dass ich es manuell anstoßen muss.
- Als Nutzer möchte ich eine hängende/beendete Session **per Knopfdruck reaktivieren** können (wie heute: beenden → wiederbeleben → läuft weiter), falls die Automatik nicht greift.
- Als Nutzer möchte ich beim Reanimieren eine klare Rückmeldung (läuft wieder / Reanimation fehlgeschlagen) statt eines stillen Zustands.
- Als Nutzer möchte ich, dass eine lange, **legitim arbeitende** Session **nicht** fälschlich als „hängt" angezeigt oder unnötig neu gestartet wird.

## Acceptance Criteria
- [ ] Jede Session zeigt im Cockpit (Kachel/Zeile) **und** im Detail ein **Liveness-Symbol** mit mindestens drei verifizierten Zuständen: **aktiv** (lebt + Fortschritt), **hängt** (lebt, aber kein Fortschritt über Schwelle / Stream tot), **tot/beendet**.
- [ ] Der „aktiv"-Zustand basiert auf einem **echten Heartbeat**: (a) Subprozess lebt (PID-Check, PROJ-14) **und** (b) der Event-Stream hat innerhalb des Fensters legitimen Fortschritt gezeigt (neues `result`/Assistenten-Output/erwartete Eingabe) — **nicht** nur „Zeit läuft".
- [ ] Ein **Hänger** wird **hintergrund-getrieben** erkannt (eigener Timer/Poll), nicht erst beim nächsten Tool-Aufruf — eine komplett stillstehende Session wird ohne weitere Aktion als „hängt" erkannt.
- [ ] Bei erkanntem Hänger wird **automatisch ein Reanimations-Versuch** (`claude --resume` / vorhandener Resume-Pfad) gestartet; das Ergebnis ist sichtbar (erfolgreich → „aktiv"; fehlgeschlagen → „hängt/tot" + Knopf).
- [ ] Ein **„Reaktivieren"-Knopf** ist an der hängenden/beendeten Session verfügbar und löst denselben Resume-Pfad manuell aus.
- [ ] Auto-Reanimierung respektiert ein **Limit** (max. Versuche + Backoff), damit eine wirklich tote Session keine Endlos-Reanimations-Schleife auslöst; danach bleibt nur der manuelle Knopf.
- [ ] Die Reanimierung respektiert das **Session-Limit** aus PROJ-14 (kein Limit-Bypass über automatisches Resume).
- [ ] Schwellen (Fortschritts-Timeout, Auto-Versuche, Backoff) sind **zentral konfigurierbar** mit konservativen Defaults; Auto-Reanimierung global abschaltbar (nur Indikator + Knopf).
- [ ] Alle Texte deutsch; Lade-/Erfolg-/Fehlerzustände explizit.

## Edge Cases
- **Legitime lange Aufgabe** (großer Build/Tool läuft) → kein False-„hängt", keine unnötige Reanimierung; Fortschritts-Signal zählt, nicht reine Zeit.
- **Auto-Reanimierung schlägt wiederholt fehl** → nach `max_versuche` stoppen, Zustand „tot", nur manueller Knopf; keine Schleife/Card-Flut.
- **Prozess lebt, aber Stream ist tot** (Pipe hängt) → als „hängt" werten, Reanimation versuchen.
- **Session hängt während einer wartenden Decision Card** (legitime Wartestellung) → **nicht** als Hänger werten (Warten auf Nutzer ≠ Stillstand).
- **Reanimierung am Session-Limit** → Limit-Prüfung greift (PROJ-14-Medium-Finding), klare Meldung statt stillem Bypass.
- **Backend-Neustart** → verwaiste Sessions (PROJ-14) zeigen „tot" + Reaktivieren-Knopf; Auto-Reanimierung greift dort nicht ungefragt (sonst Versuchs-Sturm nach Restart).
- **Watchdog-Pause (PROJ-16)** ist kein Hänger → pausierte Sessions sind „wartend", nicht „hängt".

## Technical Requirements (optional)
- Hänger-Erkennung als **Hintergrund-Task** (asyncio) mit geringer Frequenz; kein Hot-Path-Regress im Event-Loop.
- Heartbeat aus vorhandenen Signalen ableiten (PID + letzte-Fortschritts-Zeit aus PROJ-16-Monitor), keine doppelte Buchhaltung.
- Reanimierung über den bestehenden `--resume`/Rehydrierungs-Pfad (PROJ-14) — kein zweiter Reaktivierungs-Mechanismus.
- Liveness-Zustand fließt über das vorhandene Session-`to_read()`/Polling ins Frontend (kein Extra-Endpoint zwingend).

## Open Design Questions (in /abc-architecture zu klären)
1. **Fortschritts-Definition** — was genau zählt als „lebt": neues `result`, Assistenten-Token, jeder Stream-Event? _Default:_ neues `result`/Assistenten-Output **oder** erwartete Nutzer-Eingabe (= legitime Wartestellung).
2. **Auto-Reanimierungs-Schwellen** — Default-Timeout bis „hängt", max. Auto-Versuche, Backoff. _Default-Vorschlag:_ 180 s ohne Fortschritt (analog PROJ-16 `max_idle_seconds`), 1–2 Auto-Versuche mit kurzem Backoff, dann manuell.
3. **Indikator-Form** — Punkt/Badge/Puls; Verhältnis zum bestehenden Ampel-/Status-Modell (PROJ-3). _Default:_ kleiner verifizierter Heartbeat-Punkt zusätzlich zum vorhandenen Status, kein Ersatz.

---

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-24 · **Stack:** Next.js 16 (React) Frontend + FastAPI (conda `Dashboard`, In-Memory-Session-Registry, 1 uvicorn-Worker) + kein DB nötig · **Branch:** dev

### Designentscheidungen (mit Nutzer geklärt, 2026-06-24)
1. **Indikator-Form:** Additiver **Heartbeat-Punkt** ZUSÄTZLICH zur bestehenden Ampel (PROJ-3) — die Ampel (`status`) bleibt unverändert das „Workflow-Signal", der Heartbeat ist das eigene, *verifizierte* „lebt der Prozess wirklich"-Signal. Kein Ersatz.
2. **Auto-Reanimierung:** Standardmäßig **AN** — Schwelle 180 s ohne Fortschritt (analog Watchdog `max_idle_seconds`), **max. 2 Auto-Versuche** mit kurzem Backoff, danach nur noch der manuelle Knopf. Respektiert das Session-Limit (PROJ-14). Orphans nach Backend-Neustart werden **nicht** ungefragt auto-reanimiert. Global abschaltbar (dann nur Indikator + Knopf).
3. **Reaktivieren-Knopf:** An **Kachel/Zeile UND Detail**, sichtbar nur wenn die Session „hängt" oder „tot" ist.

### Leitprinzip: keine zweite Buchhaltung
PROJ-27 erfindet **kein** neues Fortschritts-/Resume-System. Es baut ausschließlich auf vorhandenen Signalen auf:
- **Lebt der Prozess?** → `_pid_alive()` / `driver.is_alive` (PROJ-14, `manager.py`).
- **Gibt es Fortschritt?** → die schon existierende Fortschritts-Uhr des Watchdog-Monitors (`WatchdogMonitor._last_progress`, gefüttert von `note_progress()` bei Assistenten-Output und `feed_usage()` bei `result`-Events, `watchdog.py`).
- **Wie reanimieren?** → der vorhandene `_resume()`-Pfad (`claude --resume`, PROJ-14/PROJ-17).

Der **einzige neue Kernbaustein** ist ein **hintergrund-getriebener Auswerter**: Der Watchdog wertet die Stillstands-Uhr nur *am nächsten Tool-Gate* aus (eine komplett eingefrorene Session erreicht nie ein Gate → bliebe unerkannt). PROJ-27 schließt genau diese Lücke mit einem periodischen Hintergrund-Poll.

### A) Komponenten-Struktur (Frontend, Next.js)

```
SessionTile / SessionRow  (components/cockpit/session-tile.tsx)
├── Ampel-Badge            (bestehend, lib/status.ts → status)   ← unverändert
├── HeartbeatDot           (NEU — aktiv: grün, pulsiert · hängt: amber · tot: grau)
│   └── Tooltip (optional späterer Ausbau: „kein Fortschritt seit Xs / Versuch 1/2")
└── ReaktivierenButton     (NEU — nur sichtbar bei liveness ∈ {hängt, tot})

SessionDetail  (app/(cockpit)/sessions/[id]/…)
├── HeartbeatDot           (NEU — gleiche Komponente, größer)
├── Reanimations-Status    (NEU — „läuft wieder" / „Reanimation fehlgeschlagen (2/2)")
└── ReaktivierenButton     (NEU — prominent)
```
- `liveness` kommt über die **bestehende Polling-/Stream-Schicht** (`SessionRead` → `use-session-stream.ts` / GET `/sessions/{id}`) — kein Extra-Endpoint für die Anzeige nötig.
- Mapping `liveness → Punktfarbe/Label` als neue Hilfsfunktion neben `lib/status.ts`.

### B) Datenmodell (Klartext — alles In-Memory, keine DB-Tabelle)

Pro Session kommt **ein abgeleitetes Liveness-Feld** hinzu, berechnet aus vorhandenem Zustand:
```
liveness:  "aktiv" | "hängt" | "tot"
  aktiv  = Prozess lebt (PID)  UND  Fortschritt innerhalb des Fensters (≤ progress_timeout)
           ODER legitime Wartestellung (wartet auf Nutzer / Decision Card / Watchdog-Pause)
  hängt  = Prozess lebt, aber kein Fortschritt > Schwelle  ODER  Stream tot
  tot    = Prozess nicht (mehr) am Leben / beendet / verwaist nach Restart
```
Zusätzlich pro Session (nur im Speicher, im LivenessMonitor):
```
auto_versuche:        Zähler der bereits unternommenen Auto-Reanimierungen
naechster_versuch_ab: monotonic-Zeitpunkt (Backoff-Gate)
letztes_ergebnis:     "läuft_wieder" | "fehlgeschlagen" | null  (für die UI-Rückmeldung)
```
**Wichtig — legitime Wartestellung ≠ Hänger:** Ist die Session in einem wartenden Zustand (`status` ∈ {`waiting`, `awaiting_approval`} bzw. offene Decision Card / Watchdog-Pause), gilt sie als **„aktiv/wartend"**, niemals als „hängt". Die Fortschritts-Uhr wird in diesen Zuständen ignoriert (kein False-Positive).

### C) Hintergrund-Auswerter (der einzige neue „Motor")

- Ein **einziger asyncio-Hintergrund-Task**, gestartet/gestoppt im bestehenden `lifespan()` (`main.py`) — analog zur vorhandenen `rehydrate()`-Logik. Kein per-Session-Timer (Skaliert; ein Worker, In-Memory-Registry).
- **Niedrige Frequenz** (Default-Poll alle ~15 s, konfigurierbar) → kein Hot-Path-Regress im Event-Loop.
- Pro Tick über `manager.list()` iterieren und je Session entscheiden:
  1. `liveness` neu ableiten (PID + Fortschritts-Uhr + Warte-Status) und im Session-Zustand setzen (fließt beim nächsten Poll/Stream ins Frontend).
  2. Wenn `liveness == "hängt"`, Auto-Reanimierung **AN**, Versuche < `max_auto_attempts`, Backoff-Gate offen, **und** Session-Limit (PROJ-14) erlaubt es → `_resume()` aufrufen, `auto_versuche++`, Backoff setzen, Ergebnis in `letztes_ergebnis` festhalten.
  3. Nach `max_auto_attempts` ohne Erfolg → Zustand „tot/hängt" einfrieren, nur noch manueller Knopf (keine Schleife, keine Card-Flut).
- **Restart-Schutz:** Nach Backend-Neustart als orphaned/`error` markierte Sessions (PROJ-14) werden **nicht** automatisch reanimiert (sonst Versuchs-Sturm). Sie zeigen „tot" + Knopf; Auto-Reanimierung greift nur bei *laufend gewordenen* Hängern.

### D) API-Form (Endpunkte — nur Form, kein Code)

```
POST /sessions/{id}/reanimate   → manueller Reaktivieren-Knopf.
                                   Ruft denselben _resume()-Pfad wie die Automatik.
                                   Prüft Session-Limit (PROJ-14) → bei Überschreitung
                                   klare 4xx-Meldung statt stillem Bypass.
                                   Antwort: neuer Session-Zustand (liveness/status).

GET  /settings/liveness         → aktuelle Schwellen lesen (analog GET /settings/watchdog).
PUT  /settings/liveness         → Schwellen + Auto-An/Aus setzen (validiert, live).
```
- Für die **Anzeige** kein neuer Endpunkt: `liveness` reist im bestehenden `SessionRead` mit.
- Prüfen, ob bereits ein generischer Resume-/Recovery-Endpunkt existiert (`recovery.py`); falls ja, **wiederverwenden** statt zweitem Mechanismus — der neue `reanimate`-Endpunkt ist dann nur ein dünner, klar benannter Alias auf denselben Pfad.

### E) Konfiguration (zentral, konservative Defaults, live)

Neue Schwellen folgen **exakt dem Watchdog-Muster** (`WatchdogStore`: YAML-Datei, mtime-live-reload, Default-Fallback bei fehlender/kaputter Datei, `GET/PUT /settings/...`). Neue Datei `backend/config/liveness.yaml`:
```
enabled_auto_reanimation:  true     # global An/Aus der Automatik (Indikator+Knopf bleiben)
progress_timeout_seconds:  180      # kein Fortschritt > X → „hängt“ (analog max_idle_seconds)
poll_interval_seconds:     15       # Frequenz des Hintergrund-Auswerters
max_auto_attempts:         2        # danach nur manueller Knopf
backoff_seconds:           30       # Wartezeit zwischen Auto-Versuchen
```
- Defaults als eingebaute Konstanten (greifen auch ohne Datei → nie „kein Liveness").
- `progress_timeout_seconds` ist bewusst getrennt vom Watchdog (anderer Zweck: Hänger-Erkennung vs. Amok-Reißleine), liest aber denselben Fortschritts-Zeitstempel.

### F) Tech-Entscheidungen (WARUM)
- **Abgeleitetes Feld statt eigener Zustandsmaschine:** `liveness` wird bei jedem Poll frisch aus PID + Fortschritts-Uhr + Warte-Status berechnet — keine zu synchronisierende Parallel-Wahrheit, kein Drift gegenüber dem echten Prozess.
- **Ein zentraler Hintergrund-Task statt N Timer:** Bei In-Memory-Registry + 1 Worker ist ein einzelner Poll-Loop am sparsamsten und am einfachsten sauber zu stoppen (`lifespan`-Shutdown).
- **Wiederverwendung der Watchdog-Uhr:** Verhindert doppelte Buchhaltung und Inkonsistenzen — der Hänger-Detektor „sieht" denselben Fortschritt wie der Watchdog, nur kontinuierlich statt am Gate.
- **Reanimierung über `_resume()`:** Genau der Pfad, der im manuellen „beenden → Archiv → wiederbeleben"-Flow schon funktioniert — ein Mechanismus, eine Limit-Prüfung, kein Bypass.
- **Auto-Reanimierung mit hartem Versuchs-Limit + Backoff + Restart-Schutz:** schützt vor Reanimations-Stürmen (tote Session, Backend-Neustart) — der teuerste Fehlerfall des Features.

### G) Abhängigkeiten (keine neuen Pakete)
- Backend: nutzt vorhandenes `asyncio`, `pydantic-settings`, `PyYAML` — **keine neuen Pakete**.
- Frontend: bestehende Cockpit-Komponenten + Polling/Stream-Hook — **keine neuen Pakete**; nur neue React-Komponente `HeartbeatDot` + Reaktivieren-Button + `liveness`-Mapping.

### Mapping Akzeptanzkriterien → Bausteine / Verantwortliche
| Kriterium | Baustein | Spezialist |
|---|---|---|
| Liveness-Symbol (3 Zustände) in Kachel + Detail | `HeartbeatDot` + `liveness`-Mapping; `liveness` in `SessionRead` | Frontend + Backend |
| „aktiv" = echter Heartbeat (PID + Fortschritt) | Ableitung aus `_pid_alive` + `WatchdogMonitor._last_progress` | Backend |
| Hintergrund-getriebene Hänger-Erkennung | neuer asyncio-Poll im `lifespan` + `LivenessMonitor` | Backend |
| Auto-Reanimierung bei Hänger, Ergebnis sichtbar | Poll ruft `_resume()`; `letztes_ergebnis` → UI | Backend + Frontend |
| Manueller Reaktivieren-Knopf | `POST /sessions/{id}/reanimate` + Button | Backend + Frontend |
| Versuchs-Limit + Backoff | `max_auto_attempts`/`backoff_seconds` im `LivenessMonitor` | Backend |
| Session-Limit nicht umgehen (PROJ-14) | Limit-Check im `_resume()`/reanimate-Pfad | Backend |
| Schwellen zentral konfigurierbar, Auto abschaltbar | `liveness.yaml` + `GET/PUT /settings/liveness` (Watchdog-Muster) | Backend |
| Warten ≠ Hänger (Decision Card / Watchdog-Pause) | Warte-Status in der `liveness`-Ableitung ausnehmen | Backend |
| Deutsche Texte, Lade-/Erfolg-/Fehlerzustände | UI-Strings + Status-Mapping | Frontend |

### Handoff-Reihenfolge
Backend-lastiges Feature. Empfehlung: **`/abc-backend`** zuerst (Liveness-Ableitung, Poll-Task, `LivenessMonitor`, `reanimate`-Endpunkt, `liveness.yaml`, `liveness`-Feld in `SessionRead`) → dann **`/abc-frontend`** (`HeartbeatDot`, Reaktivieren-Knopf, Reanimations-Rückmeldung) → **`/abc-qa`** (Edge Cases: legitimer Langläufer, Reanimations-Sturm, Stream-tot, Decision-Card-Warten, Restart-Orphans, Limit am Reanimieren).
