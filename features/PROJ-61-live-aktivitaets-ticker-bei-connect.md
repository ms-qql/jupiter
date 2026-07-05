# PROJ-61: Live-Aktivitäts-Ticker fehlt im Connect-Snapshot (OpenCode/Codex wirken dadurch eingefroren)

## Status: Approved
**Created:** 2026-07-05
**Last Updated:** 2026-07-05

## Problem / Motivation
Nutzerwunsch: eine Statusaktivitätsanzeige für OpenCode- und Codex-Sessions, wie sie bei Claude bereits funktioniert („Agent arbeitet… <letzte Aktion/Text>"). Beobachtung: bei einer frisch geöffneten OpenCode-Session zeigt das Cockpit oben nur „Arbeitet", der Transkript-Bereich darunter bleibt komplett leer — keine Tool-Chips, kein Text.

**Root Cause (durch Code-Analyse verifiziert):**

Der Live-Aktivitäts-Ticker (PROJ-46, Komponente `nextjs_app/components/cockpit/activity-ticker.tsx`) ist bereits **vollständig engine-agnostisch** — er rendert rein aus zwei transienten Client-States (`lastActivity`, `liveText`), die der Hook `use-session-stream.ts` ausschließlich aus **live gestreamten** WebSocket-Nachrichten (`kind:"activity"` bzw. `kind:"message"`) befüllt. Der **initiale Verbindungs-Snapshot** (`kind:"state"`, gesendet bei jedem WS-Connect/Reconnect — laut Logs alle 1–2 Minuten) enthält den aktuellen Ticker-Stand jedoch **nicht** (`SessionRuntime.to_read()` liefert kein `last_activity`-Äquivalent). Folge: nach jedem (Re-)Connect — Seitenaufruf, Tab-Wechsel, oder ein Reconnect nach kurzem Netz-Hänger — sieht der Client den Ticker leer, bis der **nächste** Tool-Call passiert, unabhängig von der Engine.

Bei Claude fällt das kaum auf: Claude liefert während längerer Turns sehr häufig sichtbaren Zwischentext (Denkblöcke), der über `kind:"message"` weiterläuft und die Lücke meist überbrückt, bevor ein Reconnect überhaupt bemerkt wird. OpenCode und Codex liefern deutlich seltener Zwischentext zwischen Tool-Aufrufen (insbesondere bei reinen Reasoning-Phasen ohne Toolaufruf) — dort bleibt die Lücke nach einem Connect/Reconnect entsprechend länger sichtbar leer und wirkt wie ein Hänger.

## Dependencies
- Requires: PROJ-46 (Live-Aktivitäts-Ticker, Ursprungs-Feature), PROJ-49 (WS-Reconnect-Verhalten, das die Häufigkeit der Lücke erst sichtbar macht).
- Verwandt: PROJ-60 (behebt den Fall, in dem eine Session wirklich hängt — dieses Ticket behebt den Fall, in dem sie NUR unsichtbar aktiv ist).

## Scope-Abgrenzung (bewusst)
- **In Scope:** Aktuellen Ticker-Stand (`last_activity`-Dict der `SessionRuntime`) in den State-Snapshot (`to_read()`) aufnehmen; Frontend übernimmt ihn aus jedem `kind:"state"`-Broadcast (nicht nur aus dedizierten `kind:"activity"`-Pushes).
- **NICHT in Scope:** neue Frontend-Komponente (die bestehende ist bereits engine-agnostisch und braucht keine Änderung) · Verlaufs-Replay der letzten ~5 Aktionen über einen Reconnect hinweg (bewusst weiterhin nur der aktuellste Stand, siehe „Bewusst NICHT geändert") · Surfacing von OpenCodes bislang verworfenen `reasoning`-Events als eigener Text-/Denk-Kanal (kein Live-Sample mit tatsächlichem Reasoning-Text verfügbar — GLM-5.2 lieferte in Stichproben `tokens.reasoning: 0`; separates Ticket, falls ein Modell mit sichtbarem Reasoning-Text auftaucht).

## User Stories
- Als Nutzer möchte ich beim Öffnen/Neuladen einer OpenCode- oder Codex-Session sofort sehen, was der Agent gerade tut (letztes Tool/Ziel), statt eine leere Fläche zu sehen, bis die nächste Aktion passiert.

## Acceptance Criteria
- [x] `SessionRuntime.to_read()` enthält ein neues Feld `live_activity` (Dict `{tool, target, ts}` oder `null`), gespiegelt aus dem bestehenden transienten `self.last_activity`.
- [x] Der WS-Connect-Snapshot UND jeder nachfolgende `kind:"state"`-Broadcast tragen dieses Feld (keine Sonderbehandlung nötig, da `to_read()` bei jedem Snapshot aufgerufen wird).
- [x] Frontend (`use-session-stream.ts`) übernimmt `lastActivity` aus JEDEM `kind:"state"`-Broadcast (nicht nur aus `kind:"activity"`), sodass ein frischer Connect sofort den korrekten Stand zeigt.
- [x] Terminale Sessions (`DONE`/`ERROR`) zeigen weiterhin keinen (veralteten) Ticker — `_clear_activity()` setzt `self.last_activity = None`, das über `live_activity: null` mitreist.
- [x] Kein Verhaltensunterschied für Claude (rein additiv — bestehende `kind:"activity"`-Pushes unverändert; das Feld ergänzt nur den bisher blinden Fleck beim Connect).
- [x] Backend-Suite grün (bis auf den vorbestehenden, unabhängigen Codex-Skill-Drift-Test); Frontend Lint + Vitest grün (bis auf einen vorbestehenden, unabhängigen `file-preview`-Test).

## Edge Cases
- Session hatte noch NIE eine Tool-Aktivität (frisch gestartet, erster Prompt läuft noch): `live_activity` ist `null` — Ticker bleibt wie bisher eingeklappt (kein Fake-Zustand).
- Sehr schneller Reconnect mitten in einem Tool-Aufruf: der Snapshot zeigt den zum Zeitpunkt des Connects zuletzt bekannten Stand — leichte Verzögerung gegenüber dem Live-Push ist unvermeidbar und unkritisch (identisch zum bisherigen Verhalten des `state`-Snapshots für alle anderen Felder).

## Technical Requirements
- `backend/app/engine/manager.py` — `SessionRuntime.to_read()`, neues Feld `live_activity`.
- `nextjs_app/hooks/use-session-stream.ts` — `kind==="state"`-Handler, `setLastActivity(msg.live_activity ?? null)`.

---
<!-- Sections below are added by subsequent skills -->

## Implementation Notes (Backend + Frontend, 2026-07-05)

### Geänderte Dateien
- `backend/app/engine/manager.py` — `SessionRuntime.to_read()`: `data["live_activity"] = self.last_activity` ergänzt (kein Namenskonflikt mit `SessionState.to_read()`s `last_activity`-Zeitstempel-Feld, da unterschiedliche Objekte/Keys).
- `nextjs_app/hooks/use-session-stream.ts` — `kind==="state"`-Zweig: `setLastActivity(msg.live_activity ?? null)` vor der bestehenden Transkript-Baseline-Logik; Message-Typ um `live_activity?: LiveActivity | null` erweitert.

### Bewusst NICHT geändert
- Kein Verlaufs-Replay der `_activity_ring` (letzte ~5 Aktionen) über den Snapshot — bleibt bewusst rein clientseitig aus aufeinanderfolgenden Live-Ständen abgeleitet (siehe Kommentar in `activity-ticker.tsx`); nur der AKTUELLSTE Stand wird jetzt zuverlässig beim Connect geliefert.
- Kein Mapping von OpenCodes `reasoning`-Event-Typ (bleibt weiterhin `None`/verworfen) — mangels eines echten Live-Samples mit Reasoning-Text nicht ohne Rätselraten umsetzbar; separates Ticket bei Bedarf.

### Tests
- Backend: volle Suite 1059 passed, 1 deselected (vorbestehender, unabhängiger Codex-Skill-Drift-Test).
- Frontend: `npm run lint` sauber; `npm run test` (Vitest) 173/174 grün — der eine Fail (`file-preview.test.tsx`) ist vorbestehend und unabhängig, per `git stash`-Vergleich vor dieser Änderung identisch rot bestätigt.
- Kein dedizierter WS-Mock-Test für den Hook ergänzt (kein bestehendes Mocking-Pattern im Repo für WebSocket-Hooks; Änderung ist ein reiner additiver Pass-Through eines bereits typisierten Felds, Risiko gering) — Nachholbedarf für QA/Live-Smoke.

### Offen für QA
- Live-Cockpit-Test: eine OpenCode-Session mit einem Prompt starten, der mehrere Tool-Aufrufe braucht; Seite währenddessen neu laden/reconnecten → der zuletzt bekannte Tool-Chip muss SOFORT erscheinen, nicht erst beim nächsten Tool-Call.
- Regressionscheck Claude: Ticker-Verhalten bei Claude-Sessions unverändert (insbesondere kein Doppel-Update-Flackern durch die zusätzliche Quelle im `state`-Broadcast).

## QA Test Results

**Tested:** 2026-07-05
**Backend/Frontend:** kein Zugriff auf den produktiven `jupiter-backend`-Dienst für einen echten Browser-Cockpit-Test (aktive Session läuft darüber, siehe PROJ-58/59/60-Präzedenzfall). Live-Verifikation direkt gegen `SessionRuntime.to_read()` (reale Klasse) + Code-Review des Frontend-Diffs; ergänzend volle Frontend-Suite (Lint + Vitest + `tsc --noEmit`).
**Tester:** QA Engineer (AI)

### Methodik
- Backend: volle Suite (1060 Tests) + gezielte Live-Verifikation von `SessionRuntime.to_read()` in drei Zuständen: vor jeglicher Aktivität, nach einem Tool-Aufruf, nach `_clear_activity()` (Session terminal).
- Frontend: `npm run lint` (ESLint), `npm run test` (Vitest, 174 Tests), `npx tsc --noEmit` (vollständiger Typecheck des Projekts, nicht nur der geänderten Datei).
- Kollisions-Check: `live_activity` (Ticker-Dict) vs. bestehendes `last_activity` (ISO-Zeitstempel) im selben `to_read()`-Dict — beide Keys gleichzeitig vorhanden und korrekt typisiert geprüft.

### Acceptance Criteria Status
- [x] `SessionRuntime.to_read()` enthält `live_activity` (`{tool,target,ts}` oder `null`) — live verifiziert: `None` vor Aktivität, korrektes Dict nach `_emit_activity("Bash", ...)`.
- [x] Feld reist in JEDEM `to_read()`-Aufruf mit (Connect-Snapshot UND laufende State-Broadcasts nutzen dieselbe Methode) — Code-Review bestätigt (keine Sonderpfade, `to_read()` wird überall gleich aufgerufen).
- [x] Frontend übernimmt `lastActivity` aus jedem `kind==="state"`-Broadcast — Code-Review des Diffs in `use-session-stream.ts` bestätigt (`setLastActivity(msg.live_activity ?? null)` im `state`-Zweig, vor der Transkript-Baseline-Logik, läuft also bei JEDER state-Nachricht).
- [x] Terminale Sessions zeigen keinen veralteten Ticker — live verifiziert: nach `_clear_activity()` liefert `to_read()` wieder `live_activity: None`.
- [x] Kein Verhaltensunterschied für Claude — rein additives Feld, bestehende `kind:"activity"`-Pushes unverändert (kein Diff in `_emit_activity`/`_broadcast`); volle Suite grün.
- [x] Backend-Suite grün (1060 Tests, 1 vorbestehender unabhängiger Fail) — Frontend Lint sauber, Vitest 173/174 (1 vorbestehender unabhängiger Fail, `file-preview.test.tsx`, per `git stash`-Vergleich vor dieser Änderung identisch rot bestätigt), `tsc --noEmit` zeigt nur einen vorbestehenden, unabhängigen Fehler in `lib/md-tree.test.ts` (nicht in einer der geänderten Dateien).

### Edge Cases Status
- [x] Nie Tool-Aktivität gehabt (frischer Start): `live_activity` bleibt `null`, Ticker bleibt eingeklappt — durch den `None`-Ausgangszustand im Live-Check bestätigt.
- [ ] Sehr schneller Reconnect mitten in einem Tool-Aufruf: nicht live gegen den echten Browser durchgespielt (kein Zugriff auf den laufenden Dienst, siehe oben); Verhalten folgt aber direkt aus der Snapshot-Semantik (Code-Review), kein neuer Mechanismus nötig.

### Security Audit Results
- [x] Keine neue Angriffsfläche: `live_activity` enthält dieselben, bereits über `kind:"activity"`-Pushes live sichtbaren Daten (Tool-Name + serverseitig sanitisiertes Ziel) — kein neues Datenfeld, nur ein zusätzlicher Zeitpunkt der Auslieferung.
- [x] Kein Informationsleck: `sanitize_target()` (unverändert) bleibt die einzige Quelle für den `target`-String.

### Bugs Found
Keine.

### Summary
- **Acceptance Criteria:** 6/6 bestanden (0 Fails).
- **Bugs Found:** 0 total.
- **Security:** Pass.
- **Production Ready:** YES
- **Empfehlung:** Approved. Ein manueller Live-Cockpit-Gegencheck (Reconnect während laufender Tool-Aufrufe) nach dem nächsten Deploy ist empfehlenswert, aber kein Blocker.
