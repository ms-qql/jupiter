# PROJ-45: Auto-Reanimierungs-Budget — Endlosschleife & False-„hängt" abstellen

## Status: Planned
**Created:** 2026-06-26
**Last Updated:** 2026-06-26

## Dependencies
- Requires: PROJ-27 (Liveness + Reanimieren) — enthält den Hintergrund-Poller (`evaluate_liveness_once`), die Auto-Reanimierung (`_auto_reanimate`/`_reanimate_once`) und das Budget-Objekt (`LivenessMonitor`), deren Logik hier korrigiert wird.
- Requires: PROJ-32 (Fortschritt aus Tool-Aktivität) — liefert `tool_in_flight` + den In-Flight-Timeout; dieses Ticket härtet den verbleibenden False-Positive-Pfad (kurzer Assistenten-Text löscht `tool_in_flight` zu früh).
- Requires: PROJ-16 (Amok-Watchdog) — Eigentümer der geteilten Fortschritts-Uhr (`WatchdogMonitor._last_progress`); darf von diesem Fix nicht geschwächt werden.
- Verwandt: PROJ-33 (Session-Lifecycle-Härtung) — Backend-Restart-Orphans (`tot`) und Deploy-Kill sind die *zweite* Todesart (siehe „Out of Scope").

## Problem / Beweislage (Live-Betrieb 25.–26.06.2026)
Auswertung der Vault-Session-Logs seit 25.06. zeigt Sessions, die **bis zu 25×** das komplette Transkript neu dumpen (= 25 volle `claude --resume`-Reloads) — bei teils **null** Nutzer-Eingaben. Belegfall `a66fa404` (26.06. 05:31): **0 User-Turns, 150 Claude-Blöcke**, exakt **dieselbe 6-Schritt-Sequenz ~25× wiederholt**, jedes Mal abgebrochen am selben großen Multi-File-Edit. Im Zeitfenster gab es **keinen** Backend-Restart → reine Auto-Reanimierungs-Schleife.

### Wurzelursache (im Code verankert)
1. **Budget-Reset hebt das Limit auf (Hauptbug).** `evaluate_liveness_once` ([manager.py:1402-1414](backend/app/engine/manager.py#L1402)) setzt bei `LIVENESS_ACTIVE` das Reanimierungs-Budget zurück: `if live == ACTIVE and auto_attempts: runtime.liveness.reset()` → `auto_attempts = 0` ([liveness.py:187-193](backend/app/engine/liveness.py#L187)). Ein `_resume` spielt das Transkript ab und erzeugt **kurzzeitig Assistenten-Output** → der nächste Poll-Tick sieht `ACTIVE` → **Budget genullt**. Danach erreicht die Session denselben langen Schritt, hängt wieder > `progress_timeout` (180 s) → `may_auto_attempt` ist erneut `True` → **erneut killen**. `max_auto_attempts: 2` greift damit **nie** — aus „2 Versuche, dann Ruhe" wird eine **Endlosschleife** für jede Session, die deterministisch an derselben Stelle stockt.
2. **`tool_in_flight` wird zu früh gelöscht (sekundärer Auslöser des Fehlalarms).** Jeder kurze Assistenten-Satz setzt `_tool_in_flight = False` ([watchdog.py:208/213](backend/app/engine/watchdog.py#L208)). Bei einer Folge „kurzer Satz → großer Edit → kurzer Satz → großer Edit" gilt für den großen Edit meist der **180 s**-Timeout statt der 600 s-In-Flight-Geduld aus PROJ-32 — ein einzelner großer Edit + Modell-Denkzeit reißt die 180 s leicht und löst den Hänger-Fehlalarm aus, der die Schleife aus (1) überhaupt startet.

### Auswirkungen
- **„Session startet von alleine neu"** (Nutzer-Symptom 1): die Auto-Reanimierung feuert wieder und wieder.
- **„Sehr schnell über das 50 %-Limit"** (Nutzer-Symptom 2): jeder `_resume` **bricht den Prompt-Cache** und liest die *gesamte* (mitwachsende) Konversation + den vollen Fixkosten-Block (CLAUDE.md + `rules/*.md` + Tool-/MCP-Schemata) zum **vollen, nicht-gecachten** Eingabepreis neu ein (sichtbar als `cache_creation`-Tokens je Resume). Eine 20×-reanimierte Session zahlt diesen Block 20× — viel Quote/Geld für gefühlt „nichts Neues".
- **Verworfene Arbeit:** der Kill mitten im langen Tool-Call verwirft den Fortschritt.

## User Stories
- Als Nutzer möchte ich, dass eine Session, die deterministisch an derselben Stelle stockt, **höchstens `max_auto_attempts`-mal** automatisch reanimiert wird und danach **stehen bleibt** (Indikator „hängt" + manueller „Reaktivieren"-Knopf) — **keine** Endlosschleife, die Tokens verbrennt.
- Als Nutzer möchte ich, dass der Resume-eigene Transkript-Abspiel-„Fortschritt" das Reanimierungs-Budget **nicht** zurücksetzt, damit das Limit tatsächlich greift.
- Als Nutzer möchte ich, dass eine Session, die nach einer Reanimierung **echt weiterarbeitet** (substantieller *neuer* Fortschritt), später bei einem *anderen* Hänger wieder ein frisches Budget bekommt — damit eine einmal kurz hängende, dann lange gesunde Session nicht dauerhaft vom Auto-Schutz ausgeschlossen ist.
- Als Nutzer möchte ich, dass ein **langer legitimer Tool-Call** (großer Edit, Build, Testsuite) auch nach kurzen Zwischen-Sätzen nicht fälschlich als „hängt" gilt — der Fehlalarm, der die Schleife startet, soll verschwinden.
- Als Betreiber möchte ich die Schwellen weiterhin zentral über die Liveness-Config (YAML + Live-Reload + Settings-Tab) steuern.

## Acceptance Criteria
- [ ] **Budget übersteht Resume-„Fortschritt":** Nach einer Auto-Reanimierung setzt der unmittelbar folgende `LIVENESS_ACTIVE`-Zustand (durch das Transkript-Abspiel) das `auto_attempts`-Budget **nicht** zurück. Nachweis: eine Session, die nach jedem Resume erneut am selben Punkt hängt, wird **maximal `max_auto_attempts`-mal** auto-reanimiert, danach bleibt sie „hängt" ohne weitere Auto-Versuche.
- [ ] **Echter neuer Fortschritt setzt das Budget zurück:** Macht die Session nach einer Reanimierung **substantiellen neuen** Fortschritt (über den Resume-Replay hinaus — Default-Definition siehe „Offene Design-Frage"), wird `auto_attempts` zurückgesetzt; ein *späterer*, *anderer* Hänger darf wieder bis `max_auto_attempts` auto-reanimiert werden.
- [ ] **Deterministischer Hänger terminiert:** Reproduktion des Belegfalls (`a66fa404`: gleicher Schritt killt jedes Mal) erzeugt **≤ `max_auto_attempts`** Reloads statt unbegrenzt. Verifiziert per Unit-Test mit injizierter Uhr/Stream-Stub.
- [ ] **In-Flight-Geduld bleibt über kurze Zwischen-Sätze erhalten:** Ein großer Tool-Call, dem ein kurzer Assistenten-Satz vorausging, wird **nicht** vorzeitig nach 180 s als „hängt" eingestuft (Härtung von PROJ-32 — siehe „Offene Design-Frage" für den Mechanismus).
- [ ] **Amok-Watchdog unberührt:** Schleifen-Erkennung (identische Tool-Wiederholungen) und Schreibraten-Metrik aus PROJ-16 funktionieren unverändert; der Budget-Fix maskiert **keine** echte Endlosschleife.
- [ ] **DEAD bleibt manuell:** Eine wirklich tote/verwaiste Session (`LIVENESS_DEAD`, Prozess weg) wird weiterhin **nicht** auto-reanimiert (nur Indikator + Knopf) — dieser Fix ändert nur den `HANGING`-Pfad.
- [ ] **Manueller Knopf jederzeit:** Der manuelle „Reaktivieren"-Knopf (PROJ-27) funktioniert unverändert, auch nachdem das Auto-Budget erschöpft ist.
- [ ] **Konfig/Live unverändert:** Bestehende Liveness-Schwellen (`max_auto_attempts`, `backoff_seconds`, `progress_timeout_seconds`, `tool_in_flight_timeout_seconds`) bleiben gültig und live-konfigurierbar; ggf. neue Schwellen folgen demselben YAML-/mtime-/Default-Muster + Settings-Anbindung.
- [ ] Alle Texte/Logs deutsch; volle Test-Suite grün, keine Regression in PROJ-16/27/32/33.

## Edge Cases
- **Backoff aktiv:** Während `next_attempt_at` in der Zukunft liegt, läuft kein Auto-Versuch — auch wenn „hängt" anhält (unverändert PROJ-27).
- **Reanimierung schlägt fehl (`success=False`):** zählt weiter aufs Budget (`record_attempt`); nach Erschöpfung bleibt „hängt" + Knopf.
- **Session erholt sich nach 1 Auto-Versuch dauerhaft:** kein zweiter Versuch nötig; Budget wird durch echten neuen Fortschritt zurückgesetzt — späterer, *anderer* Hänger bekommt frisches Budget (kein dauerhafter Ausschluss).
- **Mehrere parallele Tool-Calls:** „in-flight" bleibt AN, solange mindestens ein Tool offen ist (PROJ-32-Verhalten beibehalten/gehärtet).
- **Manueller Resume direkt vor Auto-Tick:** kein Doppel-Resume; manueller Eingriff setzt Budget zurück (legitimer Nutzer-Fortschritt).
- **Legitime Wartestellung (Decision Card / Watchdog-Pause / Eingabe):** bleibt „aktiv", nie „hängt", nie Budget-Verbrauch (unverändert PROJ-27).
- **Backend-Neustart während Hänger:** Session wird `tot` (cgroup-Kill) → kein Auto-Pfad mehr (siehe „Out of Scope").

## Technical Requirements (optional)
- **Kein Hot-Path-Regress:** Budget-Entscheidung bleibt O(1) im Poll-Tick; keine zweite Fortschritts-Buchhaltung (Leitprinzip PROJ-27/32 — dieselbe `_last_progress`-Uhr lesen).
- **„Echter neuer Fortschritt" aus vorhandenen Signalen ableiten** (kein neuer Parallel-Zustand) — z. B. Vergleich des Fortschritts-Zeitstempels/Turn-Zählers gegen den Stand *zum Reanimierungs-Zeitpunkt*, statt blind auf `ACTIVE` zu reagieren.
- **Abwärtskompatibel:** fehlende/alte Liveness-Configs greifen weiter auf Defaults.

## Betroffene Features (Cross-Feature-Impact — explizit)
| Feature | Wirkung dieses Fixes |
|---|---|
| **PROJ-27 (Liveness + Reanimieren)** | Korrigiert die Budget-/Reset-Logik im Poller — Re-QA des Reanimierungs-Limits empfohlen. Indikator & manueller Knopf unverändert. |
| **PROJ-32 (Fortschritt aus Tool-Aktivität)** | Härtet den `tool_in_flight`-Reset gegen kurze Zwischen-Sätze; der dort gewählte 600 s-In-Flight-Timeout bleibt, greift aber zuverlässiger. |
| **PROJ-16 (Amok-Watchdog)** | Geteilte Uhr; Schleifen-/Schreibraten-Schutz muss nachweislich unberührt bleiben. |
| **PROJ-33 (Lifecycle-Härtung)** | Berührt die zweite Todesart (Restart-Orphans) nicht — bewusst getrennt. |

## Offene Design-Fragen (für /abc-architecture — mit Default-Vorschlag)
1. **Wie „echten neuen Fortschritt" von Resume-Replay unterscheiden?** *Default-Vorschlag:* Budget nur zurücksetzen, wenn der Fortschritts-Zeitstempel den Zeitpunkt der letzten Reanimierung um eine Marge (z. B. > 1 Poll-Intervall mit zusätzlichem neuen Output/`result`) übersteigt — d. h. die Session ist nach dem Replay *weitergekommen*. Alternative: Budget pro Session-Lebenszeit hart deckeln (einfachste, aber strengste Variante).
2. **Härtung `tool_in_flight`:** *Default-Vorschlag:* kurze Assistenten-Zwischen-Sätze setzen `tool_in_flight` **nicht** zurück, solange unmittelbar danach wieder ein Tool startet; alternativ den normalen `progress_timeout_seconds`-Default moderat anheben (z. B. 240–300 s). Architektur entscheidet zwischen „Flag-Hysterese" und „Timeout-Anhebung".

## Out of Scope (bewusst, eigenes Ticket)
- **Backend-Restart-/Deploy-Kill (Nutzer-Symptom „erst nach Stop + Fortsetzen"):** Sessions sterben, weil ein `systemctl restart jupiter-backend` (Deploy/Crash) per Default-`KillMode=control-group` die ganze cgroup inkl. der `claude`-Kinder killt → Session ist `tot`, nicht „hängt" → kein Auto-Pfad. Fix (z. B. `KillMode=process`/eigene cgroup/`setsid`, Deploy von laufenden Sessions entkoppeln) ist **Infra/Lifecycle** und gehört in ein eigenes Ticket (Erweiterung PROJ-33), nicht in diese Reanimierungs-Logik.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
_To be added by /abc-architecture_
