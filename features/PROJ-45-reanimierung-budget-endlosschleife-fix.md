# PROJ-45: Auto-Reanimierungs-Budget — Endlosschleife & False-„hängt" abstellen

## Status: In Progress
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
**Erstellt:** 2026-06-26 · **Stack:** Backend-only (FastAPI / Engine-Layer, Python) — kein Frontend, keine DB, kein neuer API-Endpoint · **Branch:** dev

### Kurzfassung
Reiner Engine-Bugfix in drei Dateien (`manager.py`, `liveness.py`, `watchdog.py`). Zwei
unabhängige Wurzelursachen, zwei kleine, getrennt testbare Eingriffe — kein neuer Zustand,
keine zweite Buchhaltung, O(1) im Poll-Tick. Frontend, Settings-Tab und die Liveness-Config
(YAML) bleiben unverändert; bestehende Schwellen genügen.

### Was wird geändert (grobes Bild)
```
Engine-Layer (backend/app/engine/)
├── manager.py
│   ├── evaluate_liveness_once()      ← Bug 1: Budget-Reset nicht mehr blind bei „aktiv",
│   │                                    sondern nur bei ECHTEM neuen Fortschritt
│   ├── _auto_reanimate()             ← merkt sich den Fortschritts-Stand zum Reanim-Zeitpunkt
│   └── _resume()                     ← markiert „kein Tool mehr in-flight" beim Resume-Start
├── liveness.py
│   └── LivenessMonitor               ← ein neues Feld: Fortschritts-Wasserstand (turns@Versuch)
└── watchdog.py
    └── note_progress()               ← Bug 2: löscht tool_in_flight NICHT mehr
                                         (nur Turn-Ende/Resume löschen es)
```

### Designentscheidung 1 — „Echten Fortschritt" vom Resume-Replay unterscheiden
**Problem:** `evaluate_liveness_once` setzt das Auto-Budget zurück, sobald die Session
„aktiv" wirkt ([manager.py:1403-1405](backend/app/engine/manager.py#L1403)). Das kurze
Transkript-Abspiel eines `_resume` erzeugt aber bereits Assistenten-Output → Uhr resettet →
„aktiv" → Budget genullt → `max_auto_attempts` greift nie → Endlosschleife.

**Entscheidung (Default-Vorschlag der Spec, geschärft): Turn-Wasserstand statt Zeitmarge.**
- Zum Reanimierungs-Zeitpunkt merkt sich der Monitor den **Turn-Zähler** (`state.num_turns`,
  vorhandenes Signal — wächst nur bei abgeschlossenem `result`-Event,
  [manager.py:420](backend/app/engine/manager.py#L420)).
- Das Budget wird **nur** zurückgesetzt, wenn der Turn-Zähler diesen Wasserstand **übersteigt**
  — d. h. die Session hat nach dem Replay einen **neuen Turn abgeschlossen** (= substanzieller
  neuer Fortschritt), nicht nur den alten Verlauf nachgespielt.
- Im Belegfall `a66fa404` hängt jeder Resume am selben Tool-Call **innerhalb desselben Turns**
  → `num_turns` wächst nie über den Wasserstand → Budget bleibt → nach `max_auto_attempts`
  bleibt „hängt" stehen. Schleife terminiert. ✔
- Erholt sich die Session real (Turn fertig) → Wasserstand überschritten → Budget frisch →
  ein *späterer, anderer* Hänger bekommt wieder volle `max_auto_attempts`. ✔ (kein Dauer-Ausschluss)

**Warum `num_turns` und nicht „Zeitmarge nach Reanimierung":** Eine reine Zeitmarge würde das
deterministisch-erneut-hängende Replay (das ja kurzzeitig Output erzeugt) fälschlich als
Fortschritt werten. Der Turn-Zähler ist der einzige vorhandene, monoton wachsende „echte
Arbeit ist fertig"-Marker — exakt die Grenze zwischen „nachgespielt" und „weitergekommen".

**Verworfene Alternative:** harter Budget-Deckel pro Session-Lebenszeit (einfachste Variante).
Abgelehnt, weil eine kurz hängende, dann lange gesunde Session dauerhaft vom Auto-Schutz
ausgeschlossen bliebe (verletzt User Story 3).

### Designentscheidung 2 — In-Flight-Geduld über kurze Zwischen-Sätze halten
**Problem:** Jeder kurze Assistenten-Satz löscht `tool_in_flight`
([watchdog.py:213](backend/app/engine/watchdog.py#L213) via
[manager.py:415](backend/app/engine/manager.py#L415)). Für den darauf folgenden großen Edit
(+ Modell-Denk-/Generierzeit) gilt dann der **180 s**-Timeout statt der **600 s**-In-Flight-
Geduld aus PROJ-32 → vorzeitiger „hängt"-Fehlalarm, der die Schleife aus (1) erst startet.

**Entscheidung: Flag-Hysterese (nicht Timeout-Anhebung).**
- `note_progress()` setzt weiterhin die Fortschritts-**Uhr** zurück (echter Fortschritt zählt),
  **löscht aber `tool_in_flight` nicht mehr**.
- `tool_in_flight` wird nur noch an einer echten **Turn-Grenze** gelöscht: im `result`-Pfad
  (`feed_usage`, [watchdog.py:208](backend/app/engine/watchdog.py#L208)) und explizit beim
  **Resume-Start** (frischer Prozess, noch kein Tool offen).
- Effekt: Solange ein Turn mit Tools läuft, bleibt die 600 s-Geduld über kurze Zwischen-Sätze
  hinweg erhalten; sobald der Turn fertig ist (`result`), gilt wieder der strenge 180 s-Idle-
  Timeout. Ein real *unbegrenzt* hängendes Tool wird weiterhin nach 600 s als „hängt" erkannt.

**Warum nicht `progress_timeout` global auf 240–300 s anheben:** das würde **jede** echt
leerlaufende Session pauschal träger erkennen. Die Hysterese hält den strengen 180 s-Wert für
den genuinen Leerlauf und verlängert die Geduld nur, *während ein Turn nachweislich läuft*.

### Auswirkung auf andere Features (keine Schwächung)
- **PROJ-16 Amok-Watchdog:** unberührt. Die separaten Deques (Token-/Schreibraten-Fenster,
  Loop-Fingerprint `_repeat`) werden nicht angefasst; nur das `tool_in_flight`-Flag und die
  Budget-Reset-Bedingung ändern sich. Eine echte Wiederholungs-Schleife wird weiter erkannt.
- **PROJ-27 Liveness/Reanimieren:** Indikator, manueller „Reaktivieren"-Knopf und der
  unbedingte Budget-Reset bei manuellem Eingriff ([manager.py:1366](backend/app/engine/manager.py#L1366))
  bleiben. Re-QA des Auto-Limits empfohlen.
- **PROJ-32 Fortschritt aus Tool-Aktivität:** 600 s-In-Flight-Timeout bleibt, greift jetzt
  zuverlässig. PROJ-33 (Restart-Orphans/`tot`) bleibt bewusst außen vor.

### Konfiguration / API / Daten
- **Keine** neuen Liveness-Schwellen nötig — beide Fixes nutzen vorhandene Signale.
  `max_auto_attempts`, `backoff_seconds`, `progress_timeout_seconds`,
  `tool_in_flight_timeout_seconds` bleiben gültig + live-konfigurierbar (YAML/mtime/Settings).
- **Kein** neuer Endpoint, **keine** DB-Migration, **kein** Frontend-Eingriff.

### Test-Strategie (für /abc-backend → /abc-qa)
Unit-Tests mit injizierter Uhr (`clock`) + Stream-Stub (das Muster existiert bereits in den
Liveness/Watchdog-Tests):
1. **Endlosschleifen-Repro (`a66fa404`):** Session hängt nach jedem Resume am selben Turn →
   genau `max_auto_attempts` Auto-Reanimierungen, danach stabil „hängt", kein weiterer Versuch.
2. **Echter Fortschritt resettet Budget:** nach Reanim einen Turn abschließen (`num_turns`+1) →
   späterer, anderer Hänger bekommt wieder vololles Budget.
3. **In-Flight-Hysterese:** Tool-Start → kurzer Assistenten-Satz → >180 s ohne Event →
   NICHT „hängt" (600 s gelten); erst `result` schaltet auf 180 s zurück.
4. **DEAD/Manuell unverändert:** toter Prozess wird nicht auto-reanimiert; manueller Knopf wirkt
   auch nach erschöpftem Budget.
5. **Regression PROJ-16:** Loop-/Schreibraten-Alarm feuert unverändert.

### Abhängigkeiten / Pakete
Keine neuen Pakete. Reiner Logik-Fix im bestehenden Engine-Layer.

### Nächster Schritt
`/abc-backend` (PROJ-45) auf Branch `dev` umsetzen — kein Frontend nötig, danach `/abc-qa`.

---

## Implementierung (Backend Developer) — 2026-06-26
**Branch:** `dev` · **Status:** In Progress (bereit für `/abc-qa`)

Reiner Engine-Bugfix, drei Dateien geändert, ein neues Test-Modul. Keine neuen Pakete,
keine DB/Migration, kein Frontend, keine neuen Liveness-Schwellen.

### Fix 1 — Budget übersteht Resume-„Fortschritt" (Turn-Wasserstand)
- `liveness.py` · `LivenessMonitor`: neues Feld `progress_watermark: int` + Methode
  `note_reanimation_baseline(turns)`. `reset()` verwirft den Wasserstand (`= 0`).
- `manager.py` · `_auto_reanimate()`: merkt sich VOR dem Resume den Turn-Stand
  (`note_reanimation_baseline(runtime.state.num_turns)`).
- `manager.py` · `evaluate_liveness_once()`: Budget-Reset jetzt **nur** wenn
  `live == aktiv` **und** `auto_attempts > 0` **und** `num_turns > progress_watermark`
  (echter neuer Turn nach dem Replay) — statt blind bei „aktiv".
- Effekt: Belegfall a66fa404 (gleicher Turn hängt jeden Resume, `num_turns` wächst nie)
  → nach `max_auto_attempts` bleibt „hängt" stehen, Schleife terminiert. Erholt sich die
  Session real (neuer Turn) → Wasserstand überschritten → frisches Budget für einen
  späteren, anderen Hänger.

### Fix 2 — In-Flight-Geduld über kurze Zwischen-Sätze (Flag-Hysterese)
- `watchdog.py` · `note_progress()`: löscht `tool_in_flight` **nicht mehr** (nur noch die
  Fortschritts-Uhr). Neue Methode `clear_tool_in_flight()` für den Resume-Start.
- `manager.py` · `_resume()`: ruft nach `note_progress()` zusätzlich
  `clear_tool_in_flight()` (frischer Prozess, kein Tool offen).
- `tool_in_flight` fällt damit nur noch an echten Turn-Grenzen: `feed_usage()` (result-
  Event) und Resume-Start. Während eines Tool-laufenden Turns überlebt die 600 s-Geduld
  kurze Zwischensätze; nach `result` gilt wieder der strenge 180 s-Idle-Timeout.

### Tests
- **Neu:** `backend/tests/test_proj45_budget_loop.py` (5 Tests): deterministischer Hänger
  terminiert bei `max_auto_attempts`; Replay-„aktiv" nullt das Budget nicht; echter neuer
  Turn resettet das Budget; In-Flight-Geduld übersteht kurzen Zwischensatz, bricht erst bei
  `result`; Resume löscht In-Flight-Flag.
- **Angepasst** (alte Verträge, die PROJ-45 bewusst ändert): `test_proj32_tool_in_flight.py`
  (`note_progress` hält jetzt das Flag; neuer Test für `clear_tool_in_flight`),
  `test_proj32_qa.py` und `test_proj27_qa.py` (Tool-Ende-Trigger von `note_progress` auf
  `feed_usage` umgestellt).
- **Volle Suite grün:** 853 passed.

### Geänderte Dateien
`backend/app/engine/liveness.py`, `backend/app/engine/manager.py`,
`backend/app/engine/watchdog.py`, `backend/tests/test_proj45_budget_loop.py` (neu),
`backend/tests/test_proj32_tool_in_flight.py`, `backend/tests/test_proj32_qa.py`,
`backend/tests/test_proj27_qa.py`.
