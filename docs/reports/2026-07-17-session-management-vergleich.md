# Report: Session-Management — Jupiter vs. Wayland vs. Agentic OS

**Datum:** 2026-07-17
**Auftrag:** Prüfen, wie `/home/dev/.wayland-server` und `/home/dev/.tools/agentic-os`
(tatsächlich unter `/home/dev/tools/agentic_os`) Session-Management für Agenten
implementieren, und was Jupiter daraus lernen kann. Reiner Analyse-Report, **keine
Implementierung**.

---

## 1. Ist-Zustand Jupiter

Engine-/Session-Layer: `backend/app/engine/` (~18.000 Zeilen, ~45 Dateien). Kern:
`manager.py:1-2297` (`SessionManager`/`SessionRuntime` — Turn-Handling, Resume,
Liveness, Watchdog, Persistenz — ein "God-Module"), `transport.py:1-704`
(Direct/Tmux-Abstraktion), `claude_driver.py`, `generic_cli_driver.py`,
`watchdog.py`, `liveness.py`, `adapters.py`, `db/session_index.py`.

**Prozess-Modell ist bereits differenziert, nicht naiv "ein Prozess pro Turn":**
- Claude läuft per Default über **tmux-Transport** (`transport.yaml`:
  `engine_overrides: {claude: tmux, codex: tmux, opencode: tmux}`) — EIN
  langlebiger Prozess pro Session, stdin bleibt über eine FIFO offen
  (`transport.py:514-527`), Folge-Turns schreiben rein statt den Prozess neu zu
  starten (`claude_driver.py:145-177`).
- Codex/OpenCode laufen **oneshot** (ein Prozess pro Turn), aber mit nativem
  Server-seitigem Resume (`resume_argv_template`, `generic_cli_driver.py:26-54,
  271-288`) — kein Transkript-Replay, sondern z. B. `codex exec resume <thread_id>`.
- Persistenz: SQLite (`session_index`, `session_context`, `session_transcript` —
  `db/session_index.py:22,87-263`).
- Liveness: Poll-Loop alle 15 s (`main.py:93-108`, `liveness.py:43`), kombiniert
  `pid_alive()` + Zeit seit letztem Progress-Event, 180 s Leerlaufgrenze (600 s
  während ein Tool läuft, PROJ-45-Hysterese), Auto-Reanimation mit Backoff
  (`manager.py:1949-2006`).
- Mehrere konkrete Bugs dieser Klasse wurden bereits einzeln gefixt: OpenCode-
  Stdin-Race (PROJ-58), stiller Tool-Turn-Gap (PROJ-60), Stop-Hang nach Resume
  (PROJ-59), Replay-Duplikate via `seek_to_end` (PROJ-71/72).

**Bekannte offene/fragile Stellen** (aus Code + Hal-Memory):
- `rehydrate()` (`manager.py:1391-1447`) markiert bei Backend-Neustart **jede**
  vorher ACTIVE Session pauschal als ERROR/verwaist, außer `drained_at` wurde
  durch ein *geordnetes* `drain()` gesetzt (`manager.py:1449-1471`). Bei einem
  harten Backend-Absturz (Crash, OOM, Deploy ohne graceful shutdown) gibt es kein
  `drained_at` — obwohl der tmux-Pane-Prozess technisch weiterlebt, wird die
  Session trotzdem als tot behandelt. Der Kommentar im Code selbst
  (`manager.py:1394-1398`) markiert das als vermutlich veraltet seit PROJ-63.
  **Das ist der wahrscheinlichste Kandidat für "Session bricht ab, obwohl der
  Agent eigentlich noch lebt".**
- `transport.yaml`: tmux ist nur per **Opt-in-Liste** (`engine_overrides`) aktiv,
  Default ist `direct` (Prozess an Backend-Lebenszeit gekoppelt). Eine neue
  Engine, die vergessen wird in die Liste einzutragen, fällt still zurück auf das
  fragile Verhalten — kein Fehler, kein Hinweis.
- PROJ-72 laut Hal-Memory (`proj72-resume-replay-unvollstaendig.md`) **nicht
  vollständig** geschlossen — nach einem zweiten Resume trat weiterhin Faktor-2-
  Replay auf. Der jetzige Code-Fix (`seek_to_end`) deckt den Erstfall, nicht
  zwingend wiederholtes Resume. Doppelte Transkript-Einträge wirken auf Nutzer
  wie Kontextverlust, selbst wenn die Session technisch überlebt.
- Kein Fallback-Pfad, falls eine native Resume-ID (Claude-Session-ID, Codex-
  Thread-ID) ungültig/inkompatibel wird (z. B. nach CLI-Versionssprung) — anders
  als bei OpenAI/GLM (die *immer* Transkript-Replay nutzen, `manager.py:1790-1822`)
  gibt es für die "eigentlich native" Engines keinen Rettungsanker, wenn Resume
  selbst fehlschlägt.
- Zustandslogik ist ad hoc über Flags/Timestamps verteilt (`tool_in_flight`,
  `drained_at`, Liveness-Status) statt einer expliziten Zustandsmaschine mit
  geprüften Übergängen — die PROJ-45-Hysterese-ADR ist im Kern ein Symptom davon:
  ein Flag wurde an der falschen Stelle zurückgesetzt, weil es keine formale
  "das ist eine Turn-Grenze"-Prüfung gab.

## 2. Wayland — Muster

Self-hosted Server, treibt Claude Code/Codex/Gemini per **ACP (Agent Client
Protocol)** als langlebige Kindprozesse. Kernstück: explizite **Zustandsmaschine**
mit Übergangsprüfung (`idle → starting → active → prompting → active`,
`active ⇄ suspended ⇄ resuming`) in `AcpSession.ts` (`server.mjs:679177-679510`).

- **Suspend statt kill bei Idle-Disconnect**: Prozess wird bei Inaktivität nur
  suspendiert (Ressourcen freigegeben), nicht zerstört; Resume passiert lazy bei
  der nächsten Nachricht (`server.mjs:679323-679326`).
- **4-Signal-Crash-Erkennung** (Prozess-`exit`, `close`, stdout-Pipe-`close`,
  Connection-Abort — erstes Signal gewinnt, idempotent), kein Polling
  (`server.mjs:676288-676304`).
- **Exponential-Backoff-Retry** getrennt für Kaltstart vs. Resume
  (`server.mjs:678976-679019`).
- **Natives Resume zuerst** (`session/load` mit gespeicherter Session-ID), **DB-
  Transkript-Replay als budgetierter Fallback**, wenn native Resume wegen
  Versions-Mismatch nicht vertrauenswürdig ist: letzte 20 Nachrichten, auf 6000
  Zeichen gekappt, als synthetischer Kontext-Block injiziert
  (`historyReplay.ts`, `server.mjs:673457-673568`) — genau die Absicherung, die
  Jupiter für den "native Resume schlägt fehl"-Fall fehlt.

## 3. Agentic OS — Muster

Next.js-Dashboard, das echte Vendor-CLIs (Claude, Codex, Hermes …) per
`child_process` startet. Kein FSM, dafür zwei robuste, einfache Muster:

- **Detached/`unref()`'te Kindprozesse** (`hermesGoals.ts`) — der Agent-Prozess
  überlebt einen Absturz/Neustart des Dashboards, weil er bewusst vom
  Supervisor-Prozess entkoppelt ist.
- **Orphan-Recovery als Log-Reconciliation**: beim nächsten Read wird das
  Scratch-Verzeichnis nach Prozess-Ordnern durchsucht, die im State-File fehlen,
  und aus `=== START ===`/`=== END ... exit N ===`-Markern im Log rekonstruiert
  (`hermesGoals.ts:81-136`). Das Log ist "source of truth", der JSON-Index nur
  ein Cache, der repariert werden kann — nicht umgekehrt.
- **PID-Liveness-Poll** (`process.kill(pid, 0)`) statt Heartbeat-Protokoll —
  strukturell identisch zu Jupiters eigenem `pid_alive()`-Ansatz, nur zusätzlich
  mit Reconciliation kombiniert.
- **Atomic-Write + In-Process-Mutex** für State-Dateien (`.tmp` + `rename`,
  serialisierte Schreib-Queue) — Crash-mid-write-Sicherheit ohne DB.
- Explizites Speichern der Vendor-Session-ID beim ersten Auftauchen im
  Stream-Output, danach immer explizit per ID resumen statt "resume latest".

## 4. Gegenüberstellung

| Aspekt | Jupiter (Ist) | Wayland | Agentic OS |
|---|---|---|---|
| Prozess-Lebensdauer | tmux: pro Session; Codex/OpenCode: pro Turn (nativ resumt) | pro Conversation (ACP, langlebig) | pro Turn/Goal, aber `detached` |
| Crash-Erkennung | Poll alle 15 s (PID + Progress-Zeit) | 4 Event-Signale, sofort | PID-Poll bei Read + Log-Reconciliation |
| Resume-Mechanismus | nativ (Claude/Codex) *oder* Full-Replay (OpenAI/GLM) — kein Fallback zwischen beiden | nativ zuerst, **budgetierter DB-Replay als Fallback** | nativ (Claude Ultracode), sonst Prompt-Stuffing |
| Reaktion auf Backend-Neustart | pauschal ERROR, außer geordnet gedraint | Suspend/Resume unabhängig vom Server | Prozess überlebt (`detached`), Reconciliation beim nächsten Read |
| Zustandsmodell | Flags/Timestamps verteilt in `manager.py` | explizite FSM mit Übergangsprüfung | keine FSM, dafür Log-als-Quelle-der-Wahrheit |
| Bekannte Lücke | s. Abschnitt 1 | — | — |

## 5. Übertragbare Lehren für Jupiter (priorisiert, ohne Code)

1. **`rehydrate()` an echte Prozess-Liveness koppeln, nicht nur an `drained_at`.**
   Für tmux-gestützte Sessions: vor dem Orphanieren prüfen, ob der tmux-Pane/
   Prozess tatsächlich tot ist (analog Agentic-OS-PID-Check bzw. Waylands
   Suspend-statt-Kill), statt einen harten Backend-Crash implizit mit einem
   toten Agenten gleichzusetzen. Das ist der wahrscheinlichste Hebel gegen
   "Session bricht ab, obwohl der Agent eigentlich noch lief" — bei einem
   Deploy/Crash-Restart des Backends verliert der Nutzer aktuell eine
   Session, die technisch weiterläuft.
2. **`direct`-Transport als Default umkehren oder absichern.** Entweder tmux
   (oder ein äquivalent von der Backend-Lebenszeit entkoppelter Transport) zum
   Default für alle Engines machen, oder zumindest einen Check/Test einbauen,
   der eine neu konfigurierte Engine ohne expliziten `engine_overrides`-Eintrag
   sichtbar macht (Config-Lint), statt dass sie still ins fragile
   Default-Verhalten fällt.
3. **DB-Transkript-Replay als Fallback für native Resume-Fehler**, nicht nur als
   feste Strategie für Resume-lose Engines. Die Bausteine (`session_context`,
   `session_transcript`) existieren bereits (`db/session_index.py`) — fehlt ist
   die Verdrahtung "native Resume schlägt fehl → auf budgetierten Replay
   zurückfallen" nach Waylands `historyReplay.ts`-Vorbild.
4. **Offenen PROJ-72-Rest verifizieren, bevor weitere Session-Stabilitätsarbeit
   passiert.** Laut Hal-Memory trat nach wiederholtem Resume weiterhin
   Faktor-2-Replay auf — das ist für Nutzer nicht von echtem Kontextverlust zu
   unterscheiden. Konkreter Repro-Test: Session zweimal hintereinander
   resumen und Transkript-Einträge auf Duplikate prüfen.
5. **Ad-hoc-Flags durch eine kleine, geprüfte Zustandsmaschine ersetzen**
   (Wayland-Vorbild: `VALID_TRANSITIONS`-Tabelle + Guard). Der `tool_in_flight`-
   Hysterese-Bug (PROJ-45) und die OpenCode-Bugs (PROJ-58/59/60) sind
   strukturell dieselbe Fehlerklasse — ein Flag, das an der falschen Stelle
   gesetzt/gelöscht wird, weil es keine explizite Turn-Grenzen-Prüfung gibt.
   Eine formale FSM in `SessionRuntime` hätte mehrere dieser Bugs strukturell
   verhindert statt sie einzeln zu patchen.

## 6. Nicht empfohlen

- ACP-Protokoll komplett übernehmen (Wayland) — zu großer Umbau für den
  erzielbaren Nutzen; Jupiters tmux-Ansatz löst das Kernproblem
  (Prozess-Persistenz) bereits strukturell ähnlich.
- Flat-File/JSONL statt SQLite (Agentic OS) — Jupiter hat mit SQLite bereits die
  robustere Grundlage; kein Rückschritt nötig.

## 7. Nächster Schritt

Kein Fix in diesem Report. Für Punkt 1 (rehydrate/tmux-Liveness) und Punkt 4
(PROJ-72-Verifikation) eignet sich `/abc-backoffice` direkt als nächster
Schritt — beide sind eng genug eingegrenzt für Root-Cause-Fix +
Reproduktion-dann-grün. Punkt 5 (FSM) ist eher ein `/abc-refactor`-Thema
(verhaltenswahrender Umbau ohne akuten Einzel-Bug).
