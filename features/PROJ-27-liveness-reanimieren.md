# PROJ-27: Verifizierter Liveness-Indikator + Reanimieren hängender Sessions

## Status: In Review
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

---

## Implementierungsnotizen — Backend (2026-06-24, `/abc-backend`, Branch `dev`)

**Status:** Backend implementiert + getestet (22 PROJ-27-Tests, volle Suite 497 grün). Frontend offen.

**Neue/geänderte Dateien:**
- `backend/app/engine/liveness.py` (neu) — `LivenessStore` (YAML, mtime-live, Default-Fallback nach Watchdog-Muster), `LivenessMonitor` (Auto-Versuche/Backoff/letztes-Ergebnis), Konstanten `aktiv`/`hängt`/`tot`.
- `backend/config/liveness.example.yaml` (neu) — dokumentierte Vorlage (nicht geladen; nach `liveness.yaml` kopieren).
- `backend/app/config.py` — `liveness_config_path`.
- `backend/app/engine/watchdog.py` — `WatchdogMonitor.seconds_since_progress()` (legt die vorhandene Fortschritts-Uhr offen; keine zweite Buchhaltung).
- `backend/app/engine/manager.py` — `SessionAliveError`; pro-Runtime `liveness`-Monitor; `SessionRuntime.derive_liveness()` (PID + Status + Fortschritts-Uhr); `to_read()` um `liveness`/`liveness_auto_attempts`/`liveness_last_result`; `_resume()` setzt die Fortschritts-Uhr zurück; Manager-Methoden `reanimate()`, `_reanimate_once()` (stoppt lebenden Hänger-Prozess vor Resume → kein Geister-Prozess), `evaluate_liveness_once()` (Poll-Tick), `_auto_reanimate()`.
- `backend/app/main.py` — Hintergrund-`_liveness_loop` im `lifespan` (Frequenz live aus Config; nie fatal; sauberer Cancel beim Shutdown).
- `backend/app/schemas/sessions.py` — Liveness-Felder in `SessionRead`.
- `backend/app/schemas/settings.py` + `backend/app/routes/settings.py` — `GET/PUT /settings/liveness`.
- `backend/app/routes/sessions.py` — `POST /sessions/{id}/reanimate` (404/409/429/503).
- `backend/tests/test_proj27_liveness.py` (neu) — Monitor, Store, `derive_liveness`, Auto-Reanimierung (an/aus/Orphan-Schutz), API.

**API-Vertrag fürs Frontend:**
- Jede Session führt im bestehenden `SessionRead`/WS-Snapshot neu: `liveness` (`"aktiv"|"hängt"|"tot"`), `liveness_auto_attempts` (int), `liveness_last_result` (`"läuft_wieder"|"fehlgeschlagen"|null`). Kein Extra-Endpoint für die Anzeige.
- `POST /sessions/{id}/reanimate` → `200` mit aktualisiertem `SessionRead`; `404` unbekannt; `409` Session läuft bereits; `429` Session-Limit (PROJ-14) greift; `503` Resume/CLI-Fehler. Knopf nur bei `liveness ∈ {hängt, tot}` zeigen.
- `GET/PUT /settings/liveness` → `{enabled_auto_reanimation, progress_timeout_seconds, poll_interval_seconds, max_auto_attempts, backoff_seconds, source, warning}` (Watchdog-Tab-Muster).

**Abweichungen/Entscheidungen:** Liveness ist ein **abgeleitetes** Feld (frisch je Snapshot), keine gespeicherte Zustandsmaschine. Auto-Reanimierung feuert strukturell nur auf „hängt" (= aktive Session mit belegtem Slot), daher kein Limit-Bypass; die manuelle Reanimierung einer terminalen Session prüft das Limit explizit. Restart-Orphans (DeadDriver/ERROR) sind „tot" → keine Auto-Reanimierung.

**Nächster Schritt:** `/abc-frontend` (HeartbeatDot + Reaktivieren-Knopf + Reanimations-Rückmeldung), dann `/abc-qa`.

---

## Implementierungsnotizen — Frontend (2026-06-24, `/abc-frontend`, Next.js, Branch `dev`)

**Status:** Frontend implementiert + getestet (64 Frontend-Tests grün, Lint sauber, TypeScript fehlerfrei). Bereit für `/abc-qa`.

**Neue/geänderte Dateien:**
- `nextjs_app/components/cockpit/heartbeat-dot.tsx` (neu) — additiver Heartbeat-Indikator NEBEN der Status-Ampel (Herz-Icon, klar abgesetzt vom runden Ampel-Punkt): `aktiv` = pulsierender Herzschlag (grün), `hängt` = Riss (amber), `tot` = durchgestrichen (grau), mit erklärendem Tooltip (inkl. Auto-Versuchs-Zähler).
- `nextjs_app/components/cockpit/reanimate-button.tsx` (neu) — manueller „Reaktivieren"-Knopf (Varianten `icon` für die Kachel, `full` fürs Detail); ruft `POST /sessions/{id}/reanimate`, deutsche Toasts (409 = läuft bereits, 429 = Limit), Provider-Refetch.
- `nextjs_app/components/cockpit/liveness-control.tsx` (neu) — Settings-Tab „Liveness": Schwellen (Timeout/Poll/Versuche/Backoff) + globaler Auto-Schalter (`GET/PUT /settings/liveness`, live), Muster wie Watchdog-Control.
- `nextjs_app/lib/types.ts` — `Liveness`/`LivenessResult`-Typen, 3 neue `Session`-Felder, `LivenessLimits`/`LivenessSetting`.
- `nextjs_app/lib/status.ts` — `livenessMeta()` + `canReanimate()` (Knopf nur bei `hängt`/`tot`).
- `nextjs_app/lib/api.ts` — `reanimateSession()`, `getLiveness()`, `setLiveness()`.
- `nextjs_app/components/cockpit/session-tile.tsx` — HeartbeatDot neben der Ampel + Reaktivieren-Knopf (bei `hängt`/`tot`).
- `nextjs_app/app/(cockpit)/sessions/[id]/page.tsx` — HeartbeatDot im Header + Liveness-Banner mit Reaktivieren-Knopf und Rückmeldung („✓ läuft wieder" / „Reanimation fehlgeschlagen").
- `nextjs_app/components/cockpit/settings-dialog.tsx` — neuer „Liveness"-Tab.
- Tests: `lib/status.test.ts` (+ Liveness-Helfer), beide Session-Factories (`status.test.ts`, `gantt-chart.test.tsx`) um die Liveness-Defaultfelder ergänzt.

**Kerngedanke der UI:** Der Heartbeat liegt NEBEN der Ampel — eine grün-pulsierende „arbeitet"-Ampel kann lügen, wenn die Session in Wahrheit hängt; der amber-Herzriss deckt genau das auf. `liveness` reist über das bestehende Polling/WS mit (kein Extra-Fetch); der Live-Stream aktualisiert Indikator + Banner sofort nach Auto-/manueller Reanimierung.

**Review lokal:** `cd nextjs_app && npm run dev` (Backend per `conda run -n Dashboard --no-capture-output uvicorn app.main:app --reload --app-dir backend`).

**Nächster Schritt:** `/abc-qa` (Akzeptanzkriterien + Edge Cases gegen Front- und Backend).

---

## QA Test Results (2026-06-24, `/abc-qa`, Branch `dev`)

**Tester:** QA Engineer / Red-Team · **Methodik:** Code-Audit + automatisierte Tests (FakeDriver, injizierte Uhren) + Suiten-Regression.
**Produktreife-Entscheidung: NOT READY — Status bleibt „In Review".** Grund: 1 offenes **High**-Finding (BUG-1, False-Positive „hängt"). Fix ist als **PROJ-32** spezifiziert; nach Behebung Re-QA dieses ACs.

**Test-Suiten:** Backend `506 passed, 1 xfailed` (der xfail = BUG-1, `strict` → wird Alarm, sobald PROJ-32 ihn behebt). Frontend `64 passed`, Lint sauber, TypeScript fehlerfrei.
Neue QA-Tests: `backend/tests/test_proj27_qa.py` (9), zusätzlich zu `test_proj27_liveness.py` (22).

### Akzeptanzkriterien
| # | Kriterium | Ergebnis | Beleg |
|---|-----------|----------|-------|
| 1 | Liveness-Symbol (aktiv/hängt/tot) in Kachel + Detail | ✅ Pass | `HeartbeatDot` in `session-tile.tsx` + Detail-Header/-Banner; `liveness` in `SessionRead` |
| 2 | „aktiv" = echter Heartbeat (PID **und** Fortschritt im Fenster) | ⚠️ **Teilweise** | PID + Status korrekt; Fortschritts-Signal **unvollständig** → siehe **BUG-1** |
| 3 | Hänger **hintergrund-getrieben** erkannt (eigener Poll, nicht erst am Tool-Gate) | ✅ Pass | `_liveness_loop` (`main.py`) → `evaluate_liveness_once`; `test_auto_reanimation_revives_hanging` |
| 4 | Auto-Reanimierungs-Versuch bei Hänger, Ergebnis sichtbar | ✅ Pass | `_auto_reanimate`; `liveness_last_result` → „✓ läuft wieder"/„fehlgeschlagen" |
| 5 | Manueller „Reaktivieren"-Knopf, selber Resume-Pfad | ✅ Pass | `POST /reanimate` → `reanimate()` → `_resume`; `ReanimateButton` |
| 6 | Auto-Reanimierung mit Limit (max. Versuche + Backoff) | ✅ Pass | `LivenessMonitor.may_auto_attempt`; `test_monitor_attempts_backoff_and_budget` |
| 7 | Session-Limit (PROJ-14) nicht umgangen | ✅ Pass | `reanimate` prüft Limit bei terminalen Sessions; `…_429` + `…_keeps_one_slot` |
| 8 | Schwellen zentral konfigurierbar; Auto global abschaltbar | ✅ Pass | `GET/PUT /settings/liveness`; `test_auto_off_keeps_indicator_and_manual_button` |
| 9 | Deutsche Texte; Lade-/Erfolg-/Fehlerzustände explizit | ✅ Pass | Tooltips/Toasts/Banner deutsch; Control-Lade-/Offline-Zustände |

### Edge Cases
| Edge Case (Spec) | Ergebnis | Beleg |
|---|---|---|
| **Legitime lange Aufgabe → kein False-„hängt"** | ❌ **Fail (BUG-1)** | `test_bug1_long_toolcall_should_stay_active` (xfail) |
| Auto-Reanimierung schlägt wiederholt fehl → Stopp nach `max_versuche` | ✅ Pass | Budget-Test; danach nur manueller Knopf |
| Prozess lebt, Stream tot → „hängt" + Reanimation | ✅ Pass | `derive` (RUNNING + idle) = „hängt"; Auto-Reanimierung feuert |
| Warten auf Decision Card / Watchdog-Pause → **nicht** „hängt" | ✅ Pass | `test_derive_awaiting_approval_is_active_despite_idle` |
| Reanimierung am Session-Limit → klare Meldung statt Bypass | ✅ Pass | 429; `_keeps_one_slot` (hängend = aktiv belegt keinen 2. Slot) |
| Backend-Neustart-Orphans → „tot", keine Auto-Reanimierung | ✅ Pass | `test_restart_orphan_not_auto_reanimated` |

### Red-Team / API
- `POST /reanimate`: `404` unbekannt, `409` läuft bereits, `429` Limit, `503` Resume-Fehler (deutsche Meldung) — alle bestätigt (`test_reanimate_failed_resume_returns_503`, `…_unknown_is_404_not_500`).
- `PUT /settings/liveness`: negativ **und** Nicht-Ganzzahl → `422` (`test_put_liveness_negative_is_422`, `…_non_integer_is_422`).
- `enabled_auto_reanimation:false`: Automatik global aus, Indikator + manueller Knopf bleiben funktionsfähig (bestätigt).
- Kein Tenant-Scope im MVP (single-user, `owner` serverseitig) — nicht anwendbar.

### Regression
Volle Backend-Suite grün (506); Frontend-Suite grün (64); Lint/TS sauber. Keine Regression in PROJ-14/16/17/18 (Manager/Watchdog/Schemas/Routen mit-getestet).

### 🔴 BUG-1 (High) — False-Positive „hängt" bei legitimer langer Aufgabe
**Severity:** High (verwirft aktive Arbeit + hoher Tokenverbrauch durch unnötigen `--resume`-Voll-Reload).
**Beschreibung:** Die Fortschritts-Uhr (`WatchdogMonitor._last_progress`) wird **nur** von Assistenten-Output (`manager.py:353`) und `result`-Events (`feed_usage`, `:413`) zurückgesetzt. Ein langer Tool-Call **innerhalb** von Claude (`npm run build`, volle pytest-Suite, langer Explore/CodeGraph-Lauf) erzeugt minutenlang keinen Assistenten-Output und kein `result`; `watchdog.record` (Tool-Aufzeichnung, `:502`) setzt die Uhr **nicht** zurück. Nach `progress_timeout_seconds` (Default 180 s) wird die Session fälschlich „hängt" → `evaluate_liveness_once` → `_auto_reanimate` → `_reanimate_once` **stoppt den arbeitenden Prozess** und macht `claude --resume` (Voll-Reload) → **verworfene Arbeit + Tokenkosten**.
**Repro:** Session starten, einen Tool-Call > 180 s ohne Assistenten-Text auslösen (z. B. langes Bash-Kommando). **Erwartung (Spec, Beschreibung Z. 23 / Edge Case Z. 37):** bleibt „aktiv", keine Auto-Reanimierung. **Ist:** wird „hängt" + auto-reanimiert.
**Wurzelursache (belegt):** `test_bug1_root_cause_toolcall_is_not_progress` — `record()` lässt `seconds_since_progress` ungebremst über den Timeout wachsen.
**Fix:** als eigenes Feature **PROJ-32** spezifiziert (Fortschritt auch aus Tool-Aktivität ableiten + In-Flight-Timeout ~600 s); betrifft auch PROJ-16. Bis Behebung + Re-QA bleibt PROJ-27 „In Review".
**Belegt durch:** `test_bug1_long_toolcall_should_stay_active` (xfail strict — flippt automatisch auf Alarm, sobald der Fix greift).

### Fazit
Funktional vollständig und stabil bis auf die **eine** Fortschritts-Definition (BUG-1), die das KRITISCHE „kein False-hängt"-AC verletzt und ungewollte Auto-Reanimierungen produzieren kann. **Empfehlung: PROJ-32 umsetzen, dann Re-QA dieses ACs**; danach `/abc-deploy`. Bis dahin Status **In Review**.

**Nächster Schritt:** PROJ-32 (Fortschritts-Definition härten) bauen → Re-QA von BUG-1 → bei Grün Status auf **Approved**.
