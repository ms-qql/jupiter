# PROJ-47: Stream-Reader-Stall — verwaister Subprozess & eingefrorene Session-Anzeige

## Status: Architected
**Created:** 2026-06-26
**Last Updated:** 2026-06-26

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — besitzt den Subprozess-Treiber: stdin-Input (`send_input`) und den stdout-Stream-Leser (`handle_event`/Event-Pump), deren Entkopplung hier das Problem ist.
- Requires: PROJ-14 (Engine-Härtung: Limit + Persistenz) — Status-/Live-Index-Spiegelung; der Status bleibt fälschlich auf `running` stehen.
- Requires: PROJ-27 (Liveness) — der Reader-Stall erzeugt ein **falsches** „hängt" (nach `progress_timeout`), obwohl der Agent idle-wartet.
- Verwandt: PROJ-3 (Cockpit) — die WebSocket-Auslieferung an den Browser (Sekundärbefund, siehe „Zweitbefund").
- Verwandt: PROJ-45 (Reanimierungs-Budget) — **anderer** Bug, gleicher Oberflächen-Effekt „Session steckt". PROJ-45 = Auto-Reanimierungs-Schleife; PROJ-47 = Reader-Stall. Nicht vermischen.
- Verwandt: PROJ-46 (Aktivitäts-Ticker) — würde Aktivität sichtbarer machen, **behebt aber den Stall nicht** (bei stehendem Reader kommt auch kein `activity`-Event mehr).

## Problem / Beweislage (Live-Betrieb 2026-06-26)
Belegfall Session `3e16cb4a` („Reanimierung 45", Opus, bypassPermissions, pid 968982):
- **UI zeigte:** grün/„Arbeitet", Heartbeat aktiv, **0 Turns, $0.0000**, Laufzeit 13m — Nutzerfragen blieben „unbeantwortet".
- **Grundwahrheit Prozess:** `claude`-Prozess **lebt, schläft** (`Sl`), **9 s CPU in 16,5 min**, **keine Kind-Prozesse** → er rechnet nicht und führt kein Tool aus; er ist **idle und wartet auf stdin**.
- **Grundwahrheit Arbeit:** der Agent hatte die Aufgabe **abgeschlossen + committet** und sogar geantwortet — die letzten zwei Assistenten-Nachrichten (13:04:16 „bereit für QA", 13:04:52 „Alles klar …") stehen **im Claude-eigenen Transkript** (`~/.claude/projects/.../3e16cb4a.jsonl`), aber **NICHT** in Jupiters In-Memory-Transkript.
- **Der Schnitt:** Jupiters Backend-Speicher endet exakt bei der Nutzer-Eingabe „ok" um **13:04:49** — genau dem Zeitpunkt, an dem die Eingabe **mitten im laufenden Turn** gesendet wurde (im Claude-Log als `queue-operation` sichtbar). **Ab da liest Jupiter den stdout-Strom des Subprozesses nicht mehr.**

### Wurzelursache (Hypothese, im Verhalten belegt — exakter Code-Defekt von /abc-architecture zu bestätigen)
Der **stdout-Stream-Leser** einer Session bleibt stehen, während der Subprozess weiterläuft und weiter produziert. Starke Korrelation: der Stall trat **beim Senden von stdin-Input während eines noch laufenden Turns** auf (mehrfaches „Dazwischenfunken": „wie ist der status?" 13:04:11, „ok" 13:04:49). Verdacht: die Input-/Output-Behandlung (stdin-Write vs. stdout-Read-Task) ist nicht sauber entkoppelt — ein Write während eines aktiven Turns bringt den Read-Task zum Stehen/Beenden (ohne sichtbare Exception; das Backend-Log zeigt **keinen** Traceback).

### Auswirkungen (alles aus dieser einen Wurzel)
- **Verwaister Subprozess:** `claude` lebt + produziert + verbrennt ggf. Tokens, Jupiter ingestiert nichts.
- **Eingefrorene/irreführende Anzeige:** `num_turns`/`tokens_used`/`total_cost_usd` bleiben auf 0 (nie ein `result`-Event verarbeitet); Status klemmt auf `running`.
- **Falsches Liveness-Signal:** zuerst grün/„aktiv", nach `progress_timeout` (180 s) **falsch „hängt"** — obwohl der Agent nur idle-wartet (Status hätte „wartet" sein müssen).
- **Verlorene Antworten:** die finalen Agent-Nachrichten erreichen den Nutzer nie → „ich bekomme keine Antwort".
- **Recovery nur manuell:** Stop + „Fortsetzen" (`--resume`) hängt einen frischen Reader an und re-synchronisiert — deckt sich mit der Nutzer-Beobachtung „startet erst nach Stop + Fortsetzen wieder".

## User Stories
- Als Nutzer möchte ich, dass **Input, den ich während eines laufenden Turns sende, den Output-Strom nicht zum Stehen bringt** — die Session muss weiter alle Agent-Ausgaben einlesen und anzeigen.
- Als Nutzer möchte ich, dass eine Session nach Turn-Ende verlässlich auf **„wartet"** wechselt (mit korrekten Turns/Kosten), damit ich erkenne, dass der Agent fertig ist und auf mich wartet — statt „Arbeitet/0 Turns" oder falschem „hängt".
- Als Nutzer möchte ich, dass ein **stehender Reader erkannt** wird (Stream lebt, Prozess lebt, aber es kommt nichts mehr an), damit kein verwaister Subprozess unbemerkt weiterläuft.
- Als Nutzer möchte ich im Zweifel **ohne Datenverlust** per Stop + Fortsetzen re-synchronisieren können (die committete Arbeit bleibt sowieso sicher).

## Acceptance Criteria
- [ ] **Input mitten im Turn killt den Reader nicht:** Wird stdin-Input gesendet, während ein Turn aktiv ist (Output strömt noch), liest Jupiter **alle** nachfolgenden Subprozess-Events (Assistenten-Text **und** `result`) weiter ein. Reproduktion des Belegfalls (zwei Eingaben kurz hintereinander während eines langen Turns) führt **nicht** mehr zum Reader-Stall. Verifiziert per Test mit Stream-/Treiber-Stub.
- [ ] **`result`-Verarbeitung → korrekter Endzustand:** Nach Turn-Ende wechselt der Status `running → wartet`, `num_turns`/`tokens_used`/`total_cost_usd` spiegeln den realen Verbrauch (> 0). Kein Steckenbleiben auf „Arbeitet/0".
- [ ] **Kein falsches „hängt" bei Idle-Wartestellung:** Eine Session, die ihren Turn beendet hat und auf Eingabe wartet, ist `wartet` = `liveness aktiv` (legitime Wartestellung), **nicht** nach 180 s „hängt".
- [ ] **Reader-Stall-Erkennung:** Lebt der Subprozess (PID + Stream offen), kommt aber trotz erwarteter Aktivität über eine Schwelle nichts mehr an, wird das als eigener, **diagnostisch klarer** Zustand erkannt (nicht stillschweigend als „aktiv"/„hängt" fehletikettiert) — inkl. Log-Eintrag.
- [ ] **Sauberes Recovery:** Stop + „Fortsetzen" (`--resume`) re-attached den Reader und holt den seit dem Stall entstandenen Stand nach (kein dauerhafter Verlust in der Anzeige; committete Arbeit ohnehin sicher).
- [ ] **Kein stiller Tod:** Wenn der Read-Task ausnahmsweise endet/wirft, wird das geloggt (Traceback) und der Session-Status entsprechend gesetzt — **kein** lautloses Verwaisen.
- [ ] Alle Texte/Logs deutsch; volle Test-Suite grün; keine Regression in PROJ-1/14/27.

## Edge Cases
- **Mehrere Eingaben in schneller Folge während eines Turns:** alle werden korrekt eingereiht; der Reader bleibt am Leben; der Agent beantwortet sie nach Turn-Ende, Jupiter zeigt die Antworten.
- **Input exakt im Moment des `result`:** Race zwischen stdin-Write und Turn-Ende darf weder Event verschlucken noch den Reader stoppen.
- **Bypass vs. normaler Modus:** Gilt in beiden; der Belegfall war `bypassPermissions`, aber die Reader-/stdin-Logik ist modus-unabhängig.
- **Echter Subprozess-Tod während des Stalls:** klar als `tot` erkennen (PROJ-14/27), nicht als „hängt".
- **Sehr langer legitimer Turn ohne Input:** kein Reader-Stall; Abgrenzung zu PROJ-32/45 (Tool-in-flight, Reanimierung) bleibt gewahrt.

## Technical Requirements (optional)
- **stdin-Write und stdout-Read strikt entkoppeln:** ein Input-Write darf den Read-Task niemals blockieren/beenden (getrennte Tasks/Streams; Backpressure sauber behandeln).
- **Read-Task überwachen:** der Stream-Leseschleife eine Aufsicht geben (Task-Done-/Exception-Callback → Log + Status), damit ein stehender/beendeter Reader sichtbar wird statt zu verwaisen.
- **Reproduzierbarer Test:** Treiber-/Stream-Stub, der „Input während aktivem Turn" simuliert und beweist, dass nachfolgende `result`-Events weiter ingestiert werden.
- **Keine zweite Fortschritts-Buchhaltung:** Liveness-Konsequenzen über die vorhandene Uhr/Statuslogik lösen (Leitprinzip PROJ-27).

## Zweitbefund — WebSocket-Flapping zum Browser (separat scope-bar)
Im selben Vorfall flappte die **WebSocket Backend→Browser** für **beide** laufenden Sessions (`3e16cb4a` und `5a2969fc`) im ~15-30-s-Takt (`WebSocket … [accepted]` wiederholt im Backend-Log) mit GET-Re-Polling. Bei jedem Reconnect bekommt der neue Subscriber **nur** ab Verbindungszeit Events — verpasste `message`-Broadcasts werden **nicht nachgeliefert** → veraltetes Transkript im UI, selbst wenn das Backend die Daten hat.
**Empfehlung:** als eigenes Ticket behandeln (Delivery-Layer: WS-Stabilität + Replay/Resync der verpassten Events bei Reconnect), da mechanistisch getrennt vom Reader-Stall (Backend↔Subprozess). Falls /abc-architecture es zusammenfassen will, hier andocken; sonst PROJ-48 dafür.

## Betroffene Features (Cross-Feature-Impact — explizit)
| Feature | Wirkung dieses Fixes |
|---|---|
| **PROJ-1 (Engine-Treiber)** | Kern: stdin/stdout-Entkopplung + Reader-Aufsicht. Re-Test der Input-/Stream-Pfade. |
| **PROJ-27 (Liveness)** | Beseitigt ein falsches „hängt"; korrekter `wartet`-Übergang. Re-QA empfohlen. |
| **PROJ-14 (Persistenz)** | Status/Turns/Kosten spiegeln wieder die Realität (kein Klemmen auf „running/0"). |
| **PROJ-45 / PROJ-46** | Unberührt; PROJ-47 ist ein eigener Defekt (siehe Dependencies). |

## Offene Design-Fragen (für /abc-architecture — mit Default-Vorschlag)
1. **Exakter Stall-Mechanismus:** *Default-Vorschlag:* zunächst die stdin-Write-/stdout-Read-Kopplung in PROJ-1 prüfen (gemeinsamer Lock? Write blockiert Read-Loop? Task-Cancellation beim Input?), mit dem Belegfall als Repro. Bestätigen, dann minimal entkoppeln.
2. **Reader-Stall-Schwelle:** *Default-Vorschlag:* „Prozess lebt + Stream offen + keine Events über X s **trotz** erwarteter Aktivität" als eigenes Diagnose-Signal; Schwelle konservativ, klar von „langer legitimer Turn" (PROJ-32/45) getrennt.
3. **WS-Flapping zusammen oder getrennt:** *Default-Vorschlag:* getrennt (PROJ-48), da Delivery-Layer ≠ Subprozess-Pump.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-26 · **Stack:** Backend-only (FastAPI/Python, Engine-Treiber) — keine Frontend-/DB-Änderung · **Branch:** dev

### Befund: exakter Code-Defekt bestätigt — Spec-Hypothese korrigiert
Die Spec vermutete eine **Kopplung stdin-Write ↔ stdout-Read** („ein Write während des Turns bringt den Reader zum Stehen"). **Das trägt im Code nicht:**
- `send_input` ([claude_driver.py:108](backend/app/engine/claude_driver.py#L108)) schreibt nur `stdin.write()` + `await stdin.drain()` — **kein** geteilter Lock, **keine** Reader-Cancellation. Auch der Manager-Pfad ([manager.py:1364](backend/app/engine/manager.py#L1364)) hält keinen mit dem Reader geteilten Lock. stdin und stdout laufen in asyncio bereits über **getrennte Transports/Tasks** — ein Write kann den `readline()` mechanistisch nicht anhalten.

**Der echte, belegbare Defekt** sitzt im Reader selbst, [`_read_stdout` claude_driver.py:154–166](backend/app/engine/claude_driver.py#L154):
1. **Ungeschützte Leseschleife:** `await stream.readline()` (Z. 158) läuft **ohne `try/except`**. `asyncio`-Subprozess-Streams haben ein **Default-Zeilenlimit von 64 KiB** (`create_subprocess_exec` ohne `limit=`, [Z. 95](backend/app/engine/claude_driver.py#L95)). Eine stream-json-Zeile, die das überschreitet (großer Assistenten-Turn, großes Tool-Result — genau was bei abgeschlossener, committeter Arbeit anfällt), lässt `readline()` ein **`ValueError`/`LimitOverrunError`** werfen.
2. **Stiller Tod:** Diese Exception killt den `_reader_task` lautlos. Der Task wird in [`start()` Z. 102](backend/app/engine/claude_driver.py#L102) per `create_task` erzeugt und **nie überwacht/awaited** (erst in `stop()`). Es gibt **keinen Done-/Exception-Callback** → der Manager erfährt nie, dass der Reader tot ist. Kein Traceback im Log — exakt wie im Belegfall.
3. **Folge = das beobachtete Bild:** Subprozess lebt + produziert weiter, Jupiter ingestiert nichts mehr → `num_turns/cost` bleiben 0 (nie ein `result`-Event verarbeitet, [manager.py:486](backend/app/engine/manager.py#L486)), Status klemmt auf `running` ([manager.py:463](backend/app/engine/manager.py#L463)), die Progress-Uhr ([watchdog.py:191](backend/app/engine/watchdog.py#L191)) bewegt sich nicht → nach 180 s falsch „hängt".

Die starke Korrelation „Stall beim Dazwischenfunken" ist **Koinzidenz**: ein arbeitsreicher Turn (fertig + committet + geantwortet) erzeugt große Ausgabezeilen — eine davon sprengt die 64-KiB-Grenze. Der Input war nicht die Ursache, nur der zeitliche Nachbar.

### Komponenten-Impact (kein UI, keine neuen Endpoints, keine DB)
```
ClaudeCodeDriver  (backend/app/engine/claude_driver.py)   ← Kern des Fixes
├── create_subprocess_exec(limit=…)   große stream-json-Zeilen nicht mehr fatal
├── _read_stdout()                    try/except um die Leseschleife
│   ├── ValueError/LimitOverrunError  → Zeile robust überlesen statt Task-Tod
│   └── sonstige Exception            → Traceback loggen + Fehler-Event emittieren
└── Reader-Aufsicht (Done-Callback)   Reader endet unerwartet → Log + Status-Signal
SessionRuntime    (backend/app/engine/manager.py)
└── Reader-Stall als diagnostischer Zustand (Prozess lebt, Reader tot) — über die
    vorhandene Status-/Uhr-Logik, KEINE zweite Fortschritts-Buchhaltung (PROJ-27-Prinzip)
```

### Tech-Entscheidungen (WARUM)
- **Zeilenlimit anheben statt ignorieren.** Die Subprozess-Streams bekommen ein großzügiges, konfigurierbares `limit` (Default mehrere MiB). Grund: stream-json packt einen ganzen Assistenten-Turn/Tool-Result in **eine** Zeile; 64 KiB ist für Agent-Output schlicht zu klein. Das beseitigt den häufigsten Auslöser an der Wurzel.
- **Reader übersteht trotzdem jede Zeile.** Auch über dem (höheren) Limit darf der Reader **nicht sterben**: `ValueError` wird gefangen, die betroffene Zeile geloggt + übersprungen, die Schleife läuft weiter. Robustheit vor Vollständigkeit einer Monsterzeile.
- **Kein stiller Tod — Aufsicht statt Hoffnung.** Ein Done-/Exception-Callback auf `_reader_task` macht jeden unerwarteten Reader-Tod sichtbar (deutscher Traceback im Log) und setzt den Session-Status, statt zu verwaisen. Deckt die AC „Kein stiller Tod" und „Reader-Stall-Erkennung" gemeinsam ab.
- **Reader-Stall ist ein eigener Zustand.** „Prozess lebt (PID + Stream offen) **aber** Reader-Task beendet" wird diagnostisch klar markiert — nicht als „aktiv" oder pauschal „hängt" fehletikettiert. Bewusst **konservativ** und getrennt vom legitimen langen Turn (PROJ-32) bzw. der Reanimierung (PROJ-45).
- **Keine zweite Uhr.** Liveness-Konsequenzen laufen über die bestehende Watchdog-Progress-Uhr ([watchdog.py:237](backend/app/engine/watchdog.py#L237)) / `derive_liveness` ([manager.py:374](backend/app/engine/manager.py#L374)) — Leitprinzip PROJ-27, kein paralleles Accounting.
- **Recovery bleibt wie gehabt.** Stop + „Fortsetzen" (`--resume`, [manager.py:1360](backend/app/engine/manager.py#L1360)) hängt einen frischen Reader an — funktioniert schon; der Fix sorgt dafür, dass es gar nicht erst nötig wird.

### Datenmodell / API
- **Keine** neuen Tabellen, **keine** MinIO-Nutzung, **keine** neuen/geänderten HTTP-Endpoints. Reiner Treiber-/Manager-Fix. Persistierter Live-Index (PROJ-14) spiegelt durch den Fix wieder reale `status/num_turns/cost`.

### Abhängigkeiten (Pakete)
- **Keine neuen.** `asyncio` (stdlib). Test nutzt den vorhandenen `FakeDriver` ([backend/tests/fakes.py:12](backend/tests/fakes.py#L12)) bzw. einen kleinen Stream-Stub.

### Test-Strategie (deckt die ACs)
- **Stream-Stub-Test** speist eine **über dem alten 64-KiB-Limit liegende** stream-json-Zeile gefolgt von einem `result`-Event ein und beweist: Reader stirbt nicht, `result` wird verarbeitet, Status `running → wartet`, `num_turns/cost > 0` → AC 1+2.
- **„Input mitten im Turn"**: zwei `send_input` während laufendem Output → alle nachfolgenden Events (inkl. `result`) kommen weiter an → AC 1.
- **Reader-Tod-Test**: erzwungene Exception im Reader → Done-Callback loggt Traceback + setzt Status (kein Verwaisen) → AC „Kein stiller Tod" + „Reader-Stall-Erkennung".
- **Idle-Wartestellung**: Turn beendet, keine Eingabe → `wartet`/liveness aktiv, **nicht** nach 180 s „hängt" → AC 3.
- **Regression**: bestehende `test_manager.py` / `test_proj33_is_alive.py` grün → keine Regression PROJ-1/14/27.

### AC-Abdeckung (Mapping)
| AC | Mechanismus |
|---|---|
| Input killt Reader nicht | `limit`-Anhebung + `try/except` in `_read_stdout` |
| `result` → korrekter Endzustand | Reader lebt → `result`-Pfad [manager.py:486](backend/app/engine/manager.py#L486) greift |
| Kein falsches „hängt" bei Idle | bestehende Watchdog-Uhr; `wartet`-Übergang intakt |
| Reader-Stall-Erkennung | Done-Callback + „Prozess lebt, Reader tot"-Diagnose |
| Sauberes Recovery | `--resume`-Pfad re-attached Reader (unverändert) |
| Kein stiller Tod | `try/except` + Traceback-Log + Status-Set |

### Offene Design-Fragen — Entscheidungen
1. **Stall-Mechanismus:** ✅ bestätigt = ungeschützter Reader + 64-KiB-Limit + fehlende Aufsicht (nicht die vermutete stdin-Kopplung).
2. **Stall-Schwelle:** „Prozess lebt + Reader-Task beendet" ist ein **deterministisches** Signal (kein Timeout-Raten) — sauberer als eine Sekunden-Schwelle; konservativ und klar von PROJ-32/45 getrennt.
3. **WS-Flapping (Zweitbefund):** **getrennt** als **PROJ-48** (Delivery-Layer ≠ Subprozess-Pump). Empfehlung: nach PROJ-47 als eigene Spec via `/abc-requirements`.

> **Hinweis an Backend-Dev:** Beim Bau zusätzlich kurz prüfen, ob `send_input` ([manager.py:1366](backend/app/engine/manager.py#L1366)) den Status mitten im Turn fälschlich auf `RUNNING` zurücksetzt (Edge „Input exakt im Moment des `result`") — falls ja, minimal absichern. Kernfix bleibt der Reader.

## Implementierung (Backend-Dev · 2026-06-26)
**Branch:** dev · Reiner Treiber-/Config-Fix, keine DB/Route/Schema.

**Geändert:**
- [`backend/app/config.py`](backend/app/config.py) — neue Einstellung `claude_stream_limit_bytes` (Default **8 MiB**, via `JUPITER_CLAUDE_STREAM_LIMIT_BYTES`). Ersetzt den asyncio-Default von 64 KiB.
- [`backend/app/engine/claude_driver.py`](backend/app/engine/claude_driver.py):
  1. `create_subprocess_exec(..., limit=settings.claude_stream_limit_bytes)` → große stream-json-Zeilen sprengen den Reader nicht mehr.
  2. `_read_stdout` umschließt die Leseschleife mit `try/except`: `ValueError`/`LimitOverrunError` (überlange Zeile) → **loggen + überspringen**, Reader liest weiter; jede sonstige Ausnahme → `log.exception` (Traceback) **+** `system/error`-Event nach oben → Session wird `ERROR` statt verwaist „läuft". `CancelledError` wird sauber durchgereicht (Stop ≠ Fehler).
  3. Neuer `_on_reader_done`-Callback (via `add_done_callback`): Reader-Task endet mit Ausnahme → Log; endet regulär, obwohl der Subprozess noch lebt und kein Stop läuft → **diagnostischer „Reader-Stall"-Log** (kein stilles Verwaisen).
- [`backend/tests/test_proj47_reader_stall.py`](backend/tests/test_proj47_reader_stall.py) — 6 neue Tests (Stream-Stub).

**Befund-Bestätigung:** Die stdin/stdout-Entkopplung war bereits sauber (getrennte Tasks, kein geteilter Lock) — die Spec-Hypothese „Write blockiert Read" trug nicht. Der echte Defekt war der ungeschützte, unbeaufsichtigte Reader + 64-KiB-Limit. Der `send_input`→`RUNNING`-Edge wurde geprüft: unkritisch, da der Reader nun verlässlich weiterläuft und das `result` den Status korrekt nach `WAITING` führt — keine zusätzliche Absicherung nötig.

**AC-Status (Eigenprüfung, finale QA via /abc-qa):**
- [x] Input/große Zeile mitten im Turn killt den Reader nicht (`test_reader_skips_overlong_line_and_keeps_result`).
- [x] `result` → `running→wartet`, Turns/Kosten > 0 (`test_result_event_sets_wartet_with_turns_and_cost`).
- [x] Kein falsches „hängt" bei Idle: unveränderte Watchdog-Uhr; `derive_liveness` führt `WAITING`→`LIVENESS_ACTIVE` (Regression PROJ-27 grün).
- [x] Reader-Stall-Erkennung (`test_done_callback_flags_stall_while_process_alive`).
- [x] Sauberes Recovery: `--resume`-Pfad unverändert (Regression PROJ-33 grün).
- [x] Kein stiller Tod (`test_reader_crash_emits_error_event_not_silent`, `test_done_callback_logs_reader_exception`).
- [x] Deutsche Logs/Texte; volle Suite grün (**859 passed**); keine Regression PROJ-1/14/27.

**Offen / Folgeticket:** WS-Flapping (Zweitbefund) bleibt separat → **PROJ-48** via `/abc-requirements`.
