# PROJ-30: Kanban-Phasenerkennung im Bypass-Mode (QA/Deploy)

## Status: In Progress
**Created:** 2026-06-24
**Last Updated:** 2026-06-24

## Dependencies
- Requires: PROJ-8 (ABC-Workflow-Gantt) — repariert dessen **Phasen-Detektor** (`abc_phase`/`abc_phase_reached`).
- Requires: PROJ-1 (Engine-Treiber) — der **`bypassPermissions`-Modus** ist die Ursache (auto-allow umgeht den Detektor-Seam).
- Verwandt: PROJ-16 (Watchdog) — dessen QA notierte bereits „Phasen-Detektion bei Watchdog-Kurzschluss übersprungen" (gleiche Schwachstelle am Tool-Gate).

## Beschreibung
Seit dem Einbau des **Bypass-Modes** (`bypassPermissions`, PROJ-1/PROJ-14) werden die **aktuellen ABC-Workflow-Phasen im Kanban/Gantt nicht mehr zuverlässig erkannt** — insbesondere die **späteren Phasen QA und Deploy** werden nicht angezeigt.

**Vermutete Ursache (in /abc-architecture zu verifizieren):** PROJ-8s Phasen-Detektor (`_detect_abc`) ist als Seiteneffekt in `request_decision` (dem Per-Tool-Freigabe-Gate) eingehängt. Im `bypassPermissions`-Modus werden Tool-Aufrufe automatisch erlaubt; läuft der Detektor-Seam dabei nicht (oder wird übersprungen), bleibt `abc_phase` stehen und spätere Skill-Aufrufe (`abc-qa`, `abc-qa-e2e`, `abc-deploy`) setzen die Phase nicht mehr. Die Phasen-Erkennung muss **unabhängig vom Freigabe-Modus** funktionieren.

## User Stories
- Als Nutzer möchte ich, dass das Kanban/Gantt die aktuelle ABC-Phase **auch im Bypass-Mode** korrekt erkennt, damit ich den Reifegrad jeder Session weiterhin sehe.
- Als Nutzer möchte ich, dass insbesondere **QA und Deploy** als Phasen erkannt und hervorgehoben werden, wenn die zugehörigen Skills laufen — egal welcher Freigabe-Modus aktiv ist.
- Als Nutzer möchte ich, dass eine bereits erreichte Phase (`abc_phase_reached`) im Bypass nicht „zurückfällt" oder einfriert.

## Acceptance Criteria
- [ ] Die Phasen-Erkennung (`abc_phase`, `abc_phase_reached`, `abc_feature`) funktioniert **unabhängig vom Freigabe-Modus** — identisch in `default`, `acceptEdits` **und** `bypassPermissions`.
- [ ] Bei laufendem `abc-qa`/`abc-qa-e2e` zeigt die Session im Bypass-Mode die Phase **QA**; bei `abc-deploy` die Phase **Deploy** (Hervorhebung + gefüllte Bar bis dahin).
- [ ] Der Phasen-Detektor wird **nicht** durch auto-allow umgangen: Skill-Aufrufe werden auch dann als Phasen-Signal erfasst, wenn keine Decision Card entsteht.
- [ ] Interaktion mit PROJ-16: Pausiert der Watchdog einen Call, geht das Phasen-Signal des **darauffolgenden** Calls nicht dauerhaft verloren (max. ein Call Nachlauf, dokumentiert).
- [ ] `abc_phase_reached` bleibt **monoton** (springt nicht zurück), auch über Bypass-Wechsel hinweg.
- [ ] Bestehende PROJ-8-Tests bleiben grün; **neuer Regressionstest** deckt Phasen-Erkennung explizit im `bypassPermissions`-Modus ab (alle 8 Phasen, Schwerpunkt QA/Deploy).

## Edge Cases
- **Moduswechsel mitten in der Session** (default → bypass) → keine erkannte Phase geht verloren; `abc_phase_reached` bleibt erhalten.
- **Reine Bypass-Session von Anfang an** → alle Phasen vom ersten Skill-Aufruf an korrekt erkannt.
- **Skill ohne Phase** (`abc-refactor` etc.) im Bypass → ändert die Phase nicht (verhaltenswahrend zu PROJ-8).
- **Watchdog-Pause direkt vor `abc-qa`/`abc-deploy`** → Phase wird spätestens beim nächsten Tool-Call der Session korrekt gesetzt.
- **QA/Deploy-Skill ohne Argument** → Phase trotzdem erkannt (Feature ggf. ohne Suffix, wie in PROJ-8).

## Technical Requirements (optional)
- Der Phasen-Detektor muss an einer Stelle hängen, die **vor/unabhängig von** der Bypass-Auto-Allow-Verzweigung läuft (analog dazu, wie PROJ-16 `watchdog.evaluate` bewusst **vor** dem Bypass-Auto-Allow steht).
- Kein Hot-Path-Regress; reiner Seiteneffekt wie bisher (erzeugt keine Decision Card).
- Verhaltenswahrend für alle Nicht-Bypass-Pfade.

## Open Design Questions (in /abc-architecture zu klären)
1. **Genaue Ursache** — feuert `request_decision`/der Detektor-Hook im Bypass gar nicht, oder läuft er, aber das Skill-Signal wird verworfen? Erst verifizieren, dann fixen.
2. **Detektor-Position** — Phasen-Erkennung aus dem Freigabe-Gate herauslösen und an den **Event-Stream** (Skill-Invocation-Event) hängen, sodass sie modus-unabhängig immer feuert? _Default-Vorschlag:_ ja, falls der Hook im Bypass nicht zuverlässig läuft.

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-24 · **Stack:** Next.js (Cockpit/Gantt) + FastAPI (SessionManager) + Postgres · **Branch:** dev

### Verifizierte Ursache (CodeGraph) — korrigiert die Spec-Hypothese
Die in der Beschreibung vermutete Ursache ist **widerlegt**. Der Detektor wird im Bypass *nicht* übersprungen.

Reihenfolge in `request_decision()` ([manager.py:520](backend/app/engine/manager.py#L520)):
1. Watchdog (Z. 536) — vor allem, bypass-fest ✓
2. Selbst-Restart-Gate (Z. 555) — bypass-fest ✓
3. `detect_phase_signal()` **seiteneffektfrei** berechnet (Z. 568) — reine Funktion in [abc_phases.py:178](backend/app/engine/abc_phases.py#L178)
4. **Phasen-Gate** `_should_gate_phase` (Z. 575): feuert bei `old≠new` → **blockierende** `phase_transition`-Card; Phase wird erst bei `allow` via `_apply_phase` (Z. 583) übernommen
5. **Nur im Nicht-Gate-Zweig**: `_detect_abc()` (Z. 587) mutiert + broadcastet die Phase — läuft vor der Bypass-Verzweigung (Z. 612)

**Der echte Defekt** ist die Default-Policy [policy.py:128](backend/app/engine/policy.py#L128): `_DEFAULT_PHASE_GATE = {"enabled": True, "transitions": []}`. Mit `_should_gate_phase` (Z. 633: `not transitions or new_phase in transitions`) **gatet leere Liste = JEDER Phasenübergang**. Damit hängt der Phasen-*Fortschritt* an einer Card-Freigabe. Eine `bypassPermissions`-Session läuft unbeaufsichtigt → niemand bestätigt die `phase_transition`-Card → die Phase bleibt am ersten gegateten Übergang stehen. Frühe Phasen (vor dem ersten Übergang) erscheinen, **QA/Deploy nie**. → exakt das gemeldete Symptom.

Anzeige (`abc_phase`) ist also von der Realität entkoppelt, weil das **Gate beide Bedeutungen vermischt**: „aktuelle Phase anzeigen" (Beobachtung) und „Phasenwechsel zur Freigabe pausieren" (Kontrolle).

### Lösungsansatz — Empfehlung: Option A (Beobachtung von Kontrolle trennen)
Die **Phasen-Erkennung** wird zu einem reinen, modus-unabhängigen Seiteneffekt, der **immer vor** dem Gate-Zweig läuft (analog zum Watchdog) — sie aktualisiert `abc_phase` / `abc_phase_reached` / `abc_feature` und broadcastet den Gantt-State. Das **Phasen-Gate bleibt unverändert bypass-fest**: es öffnet weiterhin seine `phase_transition`-Card und pausiert die *Tool-Ausführung* (PROJ-10-Schutzschiene bleibt erhalten) — aber es ist **nicht mehr der einzige Pfad**, über den die Phase im Gantt vorrückt.

- `abc_phase_reached` (Balkenfüllung „bis hierher erreicht") rückt **sofort & monoton** vor — modus-unabhängig.
- `abc_phase` (aktuelle Hervorhebung) rückt bei Erkennung sofort vor.
- QA-Bug B (PROJ-8: „ein abgelehnter Übergang darf die Phase nicht vorrücken") bleibt nur im **interaktiven** Modus relevant: lehnt der Nutzer die `phase_transition`-Card aktiv ab, wird `abc_phase` per Broadcast auf `old_phase` zurückgesetzt (`reached` bleibt monoton). Im Bypass gibt es keine Ablehnung → kein Rückfall.

**Option B (Alternative):** Im Bypass-Modus das Phasen-Gate gar nicht öffnen (erkennen + durchlaufen). Einfacher, aber schwächt PROJ-10s bewusst „bypass-feste" Checkpoint-Schiene → Regressionsrisiko für PROJ-10. **Nicht empfohlen.**

### Betroffene Komponenten (keine neuen Endpunkte, kein DB-Schema)
- **Backend:** `request_decision()` / `_detect_abc()` / `_apply_phase()` in [manager.py](backend/app/engine/manager.py) — Erkennung vor das Gate ziehen, Gate-Approve/Reject-Pfad auf reine Kontrolle reduzieren.
- **State/Stream:** unverändertes `{"kind":"state", …}`-Broadcast über `_broadcast` → WebSocket [sessions.py:296](backend/app/routes/sessions.py#L296). Frontend-Gantt liest dieselben Felder — **keine Frontend-Änderung nötig**.
- **Tests:** neuer Regressionstest in [test_proj8_gantt.py](backend/tests/test_proj8_gantt.py): alle 8 Phasen (`brainstorm…document`) im `bypassPermissions`-Modus durchspielen, Schwerpunkt QA/Deploy; bestehende PROJ-8-Tests bleiben grün.

### Tech-Entscheidungen (Begründung)
- **Warum Trennung statt „Detektor an Event-Stream hängen" (Spec-Q2):** Es gibt keinen zweiten Event-Stream — alle Tool-Calls laufen ohnehin durch `request_decision`. Der Detektor *läuft* dort bereits; das Problem ist die Kopplung an die Card-Freigabe, nicht die Position. Die kleinste verhaltenswahrende Korrektur ist daher Entkopplung, nicht Umzug.
- **Warum Gate bypass-fest lassen:** PROJ-10 wollte den Checkpoint bewusst auch im Bypass. Option A erfüllt beide ACs gleichzeitig (Anzeige korrekt **und** Checkpoint bleibt).
- **PROJ-16-Interaktion:** Watchdog pausiert *vor* dem Erkennungs-Seam. Bei Watchdog-Pause geht max. ein Call Nachlauf verloren (der pausierte Call selbst); der **darauffolgende** Call erkennt die Phase wieder — dokumentiert, AC-konform.

### Offene Punkte für die Freigabe
- Bestätige **Option A** (empfohlen) vs. Option B. → **Option A vom User freigegeben.**
- Rückfall-Verhalten von `abc_phase` bei *interaktiv* abgelehntem Übergang: zurück auf `old_phase`, `reached` bleibt monoton — OK? → **freigegeben.**

## Implementation Notes (Backend) — 2026-06-24
**Branch:** dev · umgesetzt: Option A (Erkennung von Kontrolle entkoppelt).

**Verifizierte Ursache (korrigiert die Spec-Hypothese):** Der PreToolUse-Hook *feuert* im Bypass (sonst wären `manager.py:612` + die PROJ-10-Bypass-Tests toter Code) — `request_decision` läuft also auch im Bypass. Der Defekt war die Kopplung: Phasen-*Fortschritt* hing an `_apply_phase`, das nur im Card-`allow`-Pfad lief. Default-Gate (`policy.py:128`, leere `transitions`) gatet **jeden** Übergang → im unbeaufsichtigten Bypass blieben späte QA/Deploy-Cards unaufgelöst → `abc_phase` fror ein.

**Änderungen:**
- `manager.py request_decision`: `_apply_phase()` läuft jetzt **immer vor** dem Phasen-Gate (modus-unabhängige Erkennung). Das Gate bleibt bypass-fest, pausiert nur die Tool-Ausführung und ruft bei *aktiver Ablehnung* neu `_revert_phase(old_phase)` (setzt nur `abc_phase` zurück; `abc_phase_reached` bleibt monoton).
- `_detect_abc()` entfernt (redundant) — `_apply_phase()` ist der einzige Recognizer.
- Neu `_revert_phase()` für QA-Bug-B-Rückfall.
- **Bewusste Verhaltensänderung ggü. PROJ-10:** Die Phase rückt im Gantt jetzt **bei Erkennung sofort** vor (Beobachtung), nicht erst bei Card-Freigabe; eine abgelehnte Card revertiert `abc_phase`. Zwei PROJ-10-Assertions (`test_proj10_qa.py`) entsprechend nachgezogen.
- Regressionstest `test_proj8_gantt.py`: `test_bypass_recognizes_all_phases_without_cards` (alle 8 Phasen, Gate aus, keine Card) + `test_bypass_qa_deploy_recognized_even_while_gate_blocks` (Gate an, qa/deploy sofort sichtbar trotz blockierender Card).

**Tests:** 592 passed (gesamte Backend-Suite), inkl. PROJ-8/10/16/32.

**Acceptance Criteria:**
- [x] Phasen-Erkennung modus-unabhängig (default/acceptEdits/bypassPermissions).
- [x] QA bei `abc-qa`/`abc-qa-e2e`, Deploy bei `abc-deploy` — auch im Bypass (Hervorhebung + gefüllte Bar).
- [x] Detektor nicht durch auto-allow umgangen (Erkennung auch ohne Card).
- [x] PROJ-16-Interaktion: max. ein Call Nachlauf (Watchdog-Pause gibt den *nächsten* Call frei; unverändert).
- [x] `abc_phase_reached` monoton, auch über Bypass-Wechsel.
- [x] PROJ-8-Tests grün; neuer Regressionstest deckt Bypass explizit ab (alle 8 Phasen, Schwerpunkt QA/Deploy).
