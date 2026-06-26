# PROJ-47: Stream-Reader-Stall — verwaister Subprozess & eingefrorene Session-Anzeige

## Status: Planned
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
_To be added by /abc-architecture_
