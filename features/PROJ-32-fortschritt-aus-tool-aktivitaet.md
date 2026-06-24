# PROJ-32: Fortschritts-Signal aus Tool-Aktivität (kein False-„hängt" bei langen Tools)

## Status: In Progress
**Created:** 2026-06-24
**Last Updated:** 2026-06-24

## Dependencies
- Requires: PROJ-16 (Amok-Watchdog) — besitzt die geteilte Fortschritts-Uhr (`WatchdogMonitor._last_progress` in `backend/app/engine/watchdog.py`), die hier zusätzlich aus Tool-Aktivität gespeist wird.
- Requires: PROJ-27 (Liveness + Reanimieren) — liest dieselbe Uhr über `seconds_since_progress()` für die Hänger-Erkennung; dies ist die Behebung des dort bekannten False-Positive-Findings.
- Requires: PROJ-4 (Decision Cards) — der vorhandene PreToolUse-Hook (`request_decision`) ist das natürliche „ein Tool startet jetzt"-Signal.
- Verwandt: PROJ-1 (Engine-Treiber) — liefert den Event-Strom (`tool_use`-/`result`-Events), aus dem Fortschritt abgeleitet wird.

## Beschreibung
Die Fortschritts-Uhr, die sowohl der **Amok-Watchdog** (PROJ-16, Stillstands-/`max_idle`-Erkennung am Tool-Gate) als auch die **Liveness-Hänger-Erkennung** (PROJ-27, Hintergrund-Poller) nutzen, wird heute **nur** durch Assistenten-Output (`note_progress`, `manager.py:353`) und `result`-Events (`feed_usage`) zurückgesetzt.

Ein **langer, legitimer Tool-Call innerhalb von Claude** — z. B. `npm run build`, die volle pytest-Suite, ein langer Explore-/CodeGraph-Lauf — erzeugt minutenlang **keinen** Assistenten-Output und **kein** `result`. Die Session gilt nach `progress_timeout_seconds` (Default 180 s) fälschlich als **„hängt"**; der Liveness-Poller (`evaluate_liveness_once` → `_auto_reanimate` → `_reanimate_once`) **stoppt den arbeitenden Prozess und startet `claude --resume`** (Voll-Reload). Das **verwirft laufende Arbeit** und verursacht **hohen Tokenverbrauch** (vollständiges Neu-Laden der Konversation + Fixkosten-Block).

Dieses Feature lässt **Tool-Aktivität als echten Fortschritt zählen** (die Uhr zurücksetzen) und führt — weil ein laufendes Tool für Jupiter wie Stille aussieht — einen **separaten, höheren Timeout während ein Tool in-flight ist** ein. So laufen lange Builds/Tests ungestört, ein wirklich ewig hängender Tool-Call wird aber nach dem höheren Timeout doch noch erkannt. Die **Amok-Schleifen-Erkennung des Watchdogs** (identische Tool-Wiederholungen, Schreibrate) bleibt **unverändert** — nur die *Stillstands-Uhr* wird genauer.

## User Stories
- Als Nutzer möchte ich, dass eine Session, die gerade einen **langen, legitimen Tool-Call** ausführt (Build, Testsuite, Explore), **nicht** als „hängt" angezeigt und **nicht** automatisch reanimiert wird, damit laufende Arbeit nicht verworfen wird.
- Als Nutzer möchte ich, dass durch diese Schonung **kein Token verschwendet** wird (kein unnötiger `claude --resume`-Voll-Reload arbeitender Sessions).
- Als Nutzer möchte ich, dass ein **wirklich** hängender Tool-Call (ewig kein Fortschritt) **trotzdem** noch automatisch oder per Knopf reanimiert werden kann — die Hänger-Erkennung soll nicht blind werden.
- Als Nutzer möchte ich, dass der **Amok-Watchdog** weiterhin echte Endlosschleifen (identische Tool-Wiederholungen) und exzessive Schreibraten stoppt — diese Schutzfunktion darf der Fix nicht aushebeln.
- Als Betreiber möchte ich den **In-Flight-Timeout zentral konfigurieren** können (gleiches YAML-/Live-Reload-Muster wie die bestehenden Schwellen).

## Acceptance Criteria
- [ ] **Tool-Start zählt als Fortschritt:** Wenn ein Tool-Aufruf beginnt (PreToolUse-Hook `request_decision` bzw. `tool_use`-Event im Stream), wird die Fortschritts-Uhr (`_last_progress`) zurückgesetzt — sichtbar daran, dass `seconds_since_progress()` danach ~0 ist.
- [ ] **Langer legitimer Tool-Call → kein False-„hängt":** Eine Session, die einen einzelnen Tool-Call > 180 s (alter `progress_timeout`) ohne zwischenzeitlichen Assistenten-Output ausführt, wird **nicht** als „hängt" eingestuft und **nicht** auto-reanimiert, solange der **In-Flight-Timeout** nicht überschritten ist. (Behebt das PROJ-27-Finding / dortige AC „Legitime lange Aufgabe → kein False-hängt".)
- [ ] **Separater In-Flight-Timeout:** Während ein Tool in-flight ist, gilt `tool_in_flight_timeout_seconds` (Default **600 s**) statt `progress_timeout_seconds` (Default 180 s). Wird auch dieser überschritten (Tool produziert ewig nichts), wird die Session regulär als „hängt" erkannt (Auto-Reanimierung/Knopf greifen wie in PROJ-27).
- [ ] **Idle ohne Tool unverändert:** Eine Session, die *ohne* laufenden Tool-Call still steht (kein Tool gestartet, kein Output), wird weiterhin nach dem normalen `progress_timeout_seconds` (180 s) als „hängt" erkannt — die Hänger-Erkennung wird für echten Stillstand **nicht** schwächer.
- [ ] **Amok-Watchdog unberührt:** Die Schleifen-Erkennung (identische Tool-Wiederholungen) und die Schreibraten-Metrik aus PROJ-16 funktionieren unverändert; ein identisches Tool im Hammer-Takt löst weiterhin die Watchdog-Reißleine aus (Tool-Aktivität als Fortschritt darf das **nicht** maskieren).
- [ ] **Geteilte Uhr, eine Buchhaltung:** Die Verbesserung wirkt konsistent auf **beide** Konsumenten der Uhr (PROJ-16 `max_idle` am Tool-Gate **und** PROJ-27 Hintergrund-Poller) — keine zweite, parallele Fortschritts-Buchhaltung.
- [ ] **Konfigurierbar + live:** `tool_in_flight_timeout_seconds` ist zentral konfigurierbar (Liveness-Config-Muster: YAML, mtime-Live-Reload, Default-Fallback, validiert `> 0`), inkl. `GET/PUT`-Settings-Anbindung wie die übrigen Liveness-Schwellen.
- [ ] **Legitime Wartestellung weiterhin „aktiv":** Decision-Card-/Watchdog-Pause-Warten bleibt wie in PROJ-27 „aktiv" (kein „hängt").
- [ ] Alle Texte/Logs deutsch; keine Regression in der bestehenden Test-Suite.

## Edge Cases
- **Tool startet, liefert dann ewig nichts (echter Tool-Hänger):** Nach `tool_in_flight_timeout_seconds` (600 s) wird die Session doch als „hängt" erkannt → Auto-Reanimierung (Limit/Backoff aus PROJ-27) bzw. manueller Knopf. Kein „blinder Fleck".
- **Schnell aufeinanderfolgende Tool-Calls (normaler Arbeitstakt):** Jeder Tool-Start setzt die Uhr zurück → durchgehend „aktiv"; kein Flackern.
- **Identische Tool-Wiederholung in Endlosschleife:** Watchdog-Schleifen-Metrik (PROJ-16) feuert weiter — die Schleife wird gestoppt, obwohl „Tool-Aktivität" vorliegt (Fortschritts-Uhr ≠ Schleifen-Zähler).
- **Tool endet, dann echter Stillstand:** Nach Tool-Ende (`result`/Assistenten-Output) gilt wieder der normale `progress_timeout` (180 s) — In-Flight-Sonderfall endet mit dem Tool.
- **Bypass-Mode (`bypassPermissions`):** Der PreToolUse-Hook feuert auch im Bypass (vgl. PROJ-16) → Tool-Start wird auch dort als Fortschritt gezählt; keine Sonderbehandlung nötig.
- **Backend-Neustart-Orphans:** Unverändert „tot" (PROJ-14/PROJ-27) — kein In-Flight-Zustand über einen Restart hinweg.
- **Mehrere parallele Tool-Calls in einem Turn:** „In-Flight" gilt, solange mindestens ein Tool offen ist; erst wenn keines mehr offen ist, greift wieder der normale Timeout.

## Technical Requirements (optional)
- **Kein Hot-Path-Regress:** Das Zurücksetzen der Uhr beim Tool-Start ist eine O(1)-Operation im bestehenden Event-/Gate-Pfad; kein zusätzlicher Timer pro Session.
- **Quelle des „in-flight"-Zustands:** aus vorhandenen Signalen ableiten (offene PreToolUse-Gates / `tool_use` ohne zugehöriges `tool_result`), keine neue Parallel-Buchhaltung.
- **Konfiguration:** `tool_in_flight_timeout_seconds` in `backend/config/liveness.yaml` (+ `liveness.example.yaml`, Defaults als Konstante), validiert `> 0`, live mtime-Reload — exakt das Muster aus PROJ-16/PROJ-27.
- **Abwärtskompatibel:** Fehlt der neue Schlüssel, greift der Default (600 s); bestehende Configs bleiben gültig.

## Betroffene Features (Cross-Feature-Impact — explizit)
| Feature | Wirkung dieses Fixes |
|---|---|
| **PROJ-16 (Amok-Watchdog)** | Speist die **geteilte** Fortschritts-Uhr; dessen `max_idle`/Stillstands-Erkennung am Tool-Gate profitiert automatisch (lange Tools ≠ Stillstand). Schleifen-/Schreibraten-Metriken **unverändert**. |
| **PROJ-27 (Liveness + Reanimieren)** | Direkte Behebung des False-Positive-Findings: lange legitime Tools werden nicht mehr fälschlich „hängt"/auto-reanimiert. Re-QA des betroffenen AC empfohlen, bevor PROJ-27 auf Approved/Deployed geht. |
| **PROJ-4 (Decision Cards)** | Liefert das PreToolUse-Signal (Tool-Start) — keine Verhaltensänderung an den Cards selbst. |

## Offene Design-Frage (mit Nutzer geklärt, 2026-06-24)
- **Verhalten während eines laufenden Tools:** Gewählt **Option A** — Tool-Aktivität zählt als Fortschritt **und** separater, höherer Timeout (`tool_in_flight_timeout_seconds`, Default 600 s) während ein Tool in-flight ist. (Alternativen verworfen: „Tool = legitime Wartestellung, nie auto-reanimieren" → echte Tool-Hänger nur manuell fangbar; „nur Tool-Start, Timeout 180 s" → löst lange Einzel-Builds nicht.)

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-24 · **Stack:** FastAPI (conda `Dashboard`, In-Memory-Session-Registry, 1 uvicorn-Worker) + Next.js 16 (nur kleiner Settings-Zusatz) + kein DB · **Branch:** dev

### Leitidee in einem Satz
Der Hänger-Detektor (PROJ-27) bekommt **zwei** neue, aus vorhandenen Signalen abgeleitete Informationen: „der Agent hat gerade ein Tool **gestartet**" (zählt als Fortschritt) und „gerade läuft ein Tool" (→ höhere Geduld). Es entsteht **keine** zweite Buchhaltung — wir füttern dieselbe Fortschritts-Uhr (`WatchdogMonitor._last_progress`) und ergänzen ein einziges Boolean.

### Warum die Lücke entsteht (verankert im Code)
- `handle_event` sieht ausschließlich **`assistant`-** und **`result`-Events** ([manager.py:332–369](backend/app/engine/manager.py#L332)) — es gibt **kein** `tool_use`/`tool_result`-Event im Strom. Während ein Tool (z. B. ein langer Build) läuft, kommt also minutenlang **gar nichts** an, und die Uhr läuft weiter.
- Der einzige verlässliche „ein Tool startet jetzt"-Punkt ist der **PreToolUse-Hook** `request_decision` ([manager.py:473](backend/app/engine/manager.py#L473)), der über den Matcher `"*"` ([hooks.py:37](backend/app/engine/hooks.py#L37)) **bei jedem** Tool feuert.
- Loop-Erkennung (`_repeat`/`_last_fp`) und Schreibrate (`_writes`) liegen in **eigenen** Deques, getrennt von `_last_progress` ([watchdog.py:189–193](backend/app/engine/watchdog.py#L189)) — die Fortschritts-Uhr aus Tool-Start zu speisen **berührt die Amok-Erkennung nicht**.

### A) Ablauf-Logik (Klartext — kein Code)

```
Tool-START  (request_decision → record, NACH evaluate)      manager.py:502
  └─ Fortschritts-Uhr zurücksetzen (Tool-Start = Aktivität)
  └─ Flag „Tool läuft gerade" = AN

Tool-ENDE / Modell produziert wieder (assistant- ODER result-Event)   manager.py:332/356
  └─ Fortschritts-Uhr zurücksetzen (wie heute: note_progress / feed_usage)
  └─ Flag „Tool läuft gerade" = AUS

Hänger-Frage (Hintergrund-Poller, derive_liveness)          manager.py:257–276
  └─ Geduld = Flag AN ? tool_in_flight_timeout (600s) : progress_timeout (180s)
  └─ wenn seconds_since_progress() > Geduld  →  „hängt"
```

- **Reihenfolge wichtig:** Die Watchdog-Reißleine `evaluate()` ([manager.py:489](backend/app/engine/manager.py#L489)) läuft **vor** dem Uhr-Reset (der erst in `record()`, [manager.py:502](backend/app/engine/manager.py#L502), passiert) — so bleibt die gate-zeitige `max_idle`-Prüfung von PROJ-16 unverändert.
- **Parallele Tool-Calls:** Ein einziges Boolean genügt — „Tool läuft" bleibt AN, solange noch kein `assistant`/`result`-Event eingetroffen ist; ob ein oder fünf Tools offen sind, ändert die Geduld nicht.

### B) Datenmodell (alles In-Memory, keine DB, keine neue Tabelle)
Pro Session **ein** zusätzliches Flag am `WatchdogMonitor`:
```
tool_in_flight: bool   # AN ab Tool-Start (record), AUS beim nächsten assistant/result-Event
```
Plus **eine** neue, zentral konfigurierbare Schwelle (kein neuer Zeitstempel — es wird dieselbe `_last_progress`-Uhr gelesen):
```
tool_in_flight_timeout_seconds: 600   # Geduld, solange ein Tool läuft (Default 600s)
```

### C) Konfiguration (genau das vorhandene Liveness-Muster)
`tool_in_flight_timeout_seconds` kommt in dieselbe Stelle wie die übrigen Liveness-Schwellen:
- `DEFAULTS` + `_POSITIVE_FIELDS` (`> 0`) in [liveness.py:37–51](backend/app/engine/liveness.py#L37) → YAML, mtime-Live-Reload, Default-Fallback bei fehlender/kaputter Datei.
- `backend/config/liveness.example.yaml` um die Zeile ergänzen (dokumentiert).
- Abwärtskompatibel: fehlt der Schlüssel → 600 s Default; bestehende `liveness.yaml` bleibt gültig.

### D) API-Form (kein neuer Endpunkt — nur ein Feld mehr)
```
GET /settings/liveness   → liefert tool_in_flight_timeout_seconds zusätzlich
PUT /settings/liveness   → akzeptiert/validiert tool_in_flight_timeout_seconds (>0 → sonst 422)
```
- Die `liveness`-Anzeige selbst reist unverändert im bestehenden `SessionRead`/Poll mit — **kein** Anzeige-Endpunkt nötig.

### E) Komponenten / berührte Bausteine
```
Backend (Schwerpunkt)
├── watchdog.py        NEU: tool_in_flight-Flag + Reset der Uhr bei record()/Klartext-Accessor
├── manager.py         request_decision: Flag AN bei record · handle_event: Flag AUS bei assistant/result
│                       derive_liveness: Geduld = in_flight ? 600 : 180
├── liveness.py        NEU: tool_in_flight_timeout_seconds (DEFAULTS + Validierung)
├── schemas/settings.py + routes/settings.py   GET/PUT /settings/liveness um das Feld erweitert
└── config/liveness.example.yaml               dokumentierte neue Zeile

Frontend (minimal)
└── liveness-control.tsx (+ lib/types.ts)      ein zusätzliches Zahlenfeld im „Liveness"-Settings-Tab
```

### F) Tech-Entscheidungen (WARUM)
- **Tool-Start aus dem PreToolUse-Hook statt aus dem Event-Strom:** Es gibt schlicht kein Tool-Event im Strom; der Hook ist die **einzige** verlässliche, bei *jedem* Tool feuernde Quelle (Matcher `"*"`).
- **Ein Boolean statt Tool-Zähler/Per-Tool-Timer:** „läuft ein Tool?" reicht, um die Geduld umzuschalten — minimal, kein Hot-Path-Regress, keine Synchronisations-Wahrheit.
- **Dieselbe `_last_progress`-Uhr füttern (keine zweite Buchhaltung):** folgt dem PROJ-27-Leitprinzip; Loop-/Schreibraten-Metriken bleiben unberührt (eigene Deques).
- **Höhere Geduld statt „Tool = nie Hänger":** ein wirklich ewig hängender Tool-Call wird nach 600 s doch erkannt — die Auto-Reanimierung bleibt für echte Hänger scharf (gewählte Option A, mit Nutzer geklärt).
- **`evaluate()` vor Uhr-Reset:** PROJ-16-Verhalten am Tool-Gate bleibt exakt erhalten.

### G) Abhängigkeiten (keine neuen Pakete)
Backend nutzt vorhandenes `asyncio`/`pydantic-settings`/`PyYAML`; Frontend nur ein zusätzliches Feld im bestehenden Settings-Formular. **Keine** neuen Packages.

### Mapping Akzeptanzkriterien → Bausteine / Verantwortliche
| Kriterium | Baustein | Spezialist |
|---|---|---|
| Tool-Start zählt als Fortschritt | `record()` setzt `_last_progress` + Flag (manager.py:502) | Backend |
| Langer Tool-Call → kein False-„hängt" | `derive_liveness` Geduld = `tool_in_flight_timeout` | Backend |
| Separater In-Flight-Timeout (600 s) | `tool_in_flight_timeout_seconds` in `liveness.py` | Backend |
| Idle **ohne** Tool unverändert (180 s) | Flag AUS → normaler `progress_timeout` | Backend |
| Amok-Watchdog unberührt | Reset nur `_last_progress`, nicht `_repeat`/`_writes` | Backend |
| Geteilte Uhr, eine Buchhaltung | dasselbe `_last_progress` für PROJ-16 + PROJ-27 | Backend |
| Konfigurierbar + live | `liveness.yaml` + `GET/PUT /settings/liveness` | Backend + Frontend |
| Settings-Feld im UI | `liveness-control.tsx` + `lib/types.ts` | Frontend |

### Handoff-Reihenfolge
Backend-lastig. Empfehlung: **`/abc-backend 32`** (Flag + Reset, `derive_liveness`-Geduld, `tool_in_flight_timeout_seconds`, Settings-Endpunkt, Tests inkl. „langer Tool ≠ hängt" und „echter Tool-Hänger > 600 s wird doch erkannt") → **`/abc-frontend 32`** (ein Zahlenfeld im Liveness-Tab) → **`/abc-qa 32`** (AC + Edge Cases; danach das PROJ-27-False-Positive-AC re-testen).

## Implementierungsnotizen — Backend (2026-06-24, `/abc-backend`, Branch `dev`)

**Status:** Backend implementiert + getestet (10 PROJ-32-Tests, volle Suite **518 grün**, App importiert sauber). Frontend (1 Settings-Feld) offen.

**Geänderte Dateien:**
- `backend/app/engine/watchdog.py` — `WatchdogMonitor`: neues Flag `_tool_in_flight` + Property `tool_in_flight`. `record()` setzt jetzt `_last_progress = now` **und** `_tool_in_flight = True` (Tool-Start = Fortschritt, in-flight). `note_progress()`/`feed_usage()` löschen `_tool_in_flight` (Modell produziert wieder). **Loop-(`_repeat`/`_last_fp`)- und Schreibrate-(`_writes`)-Buchhaltung unberührt** → Amok-Erkennung bleibt scharf.
- `backend/app/engine/manager.py` — `derive_liveness`: läuft ein Tool (`watchdog.tool_in_flight`), gilt `tool_in_flight_timeout_seconds` statt `progress_timeout_seconds`. `record()` wird weiterhin **nach** `evaluate()` aufgerufen (manager.py:489→502) → PROJ-16-Gate-Verhalten unverändert.
- `backend/app/engine/liveness.py` — `DEFAULTS["tool_in_flight_timeout_seconds"] = 600` + in `_POSITIVE_FIELDS` (`> 0`, sonst Fallback/422).
- `backend/app/schemas/settings.py` — `LivenessLimitsPut.tool_in_flight_timeout_seconds` (`Field(..., gt=0)`); reist via Vererbung auch in `LivenessSettingRead`.
- `backend/config/liveness.example.yaml` — dokumentierte neue Zeile.
- `backend/tests/test_proj32_tool_in_flight.py` (neu, 10 Tests) — record/Fortschritt/in-flight, Löschen via note_progress/feed_usage, Amok-Buchhaltung intakt, `derive_liveness` (langer Tool < 600 s → aktiv · > 600 s → hängt · Stillstand ohne Tool > 180 s → hängt), Config-Default/Validierung, GET/PUT-Round-Trip.

**Cross-Feature (PROJ-27):** Die PROJ-27-QA-Tests für **BUG-1** (`test_proj27_qa.py`) waren bewusst als `xfail(strict)` „grün, sobald PROJ-32 da ist" angelegt. Sie wurden auf **Fix-Verifikation** umgestellt (record = Fortschritt; langer Tool bleibt „aktiv"). `test_proj27_liveness.py::test_put_liveness_live` um das neue Feld ergänzt. **Damit ist das PROJ-27-False-Positive-AC behoben + re-getestet** — PROJ-27 kann nach Gegencheck auf Approved.

**Abweichungen:** `tool_in_flight_timeout_seconds` ist im PUT-Schema **required** (konsistent mit den übrigen Limit-Feldern); der Store füllt fehlende Schlüssel in Alt-Configs aber mit dem Default 600 (abwärtskompatibel beim Laden).

**API-Vertrag fürs Frontend:** `GET/PUT /settings/liveness` führt zusätzlich `tool_in_flight_timeout_seconds: int` (> 0). Ein Zahlenfeld im „Liveness"-Settings-Tab ergänzen (`liveness-control.tsx` + `lib/types.ts`). Die `liveness`-Anzeige selbst ändert sich nicht.

**Nächster Schritt:** `/abc-frontend 32` (ein Zahlenfeld im Liveness-Tab), danach `/abc-qa 32`.

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
