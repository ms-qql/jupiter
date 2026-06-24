# PROJ-33: Session-Lifecycle-Härtung (Restart-Resilienz + prozess-verifiziertes Liveness)

## Status: Deployed
**Created:** 2026-06-24
**Last Updated:** 2026-06-24

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — Subprozess-Lebenszyklus + `is_alive`.
- Requires: PROJ-14 (Härtung) — Live-Index-Persistenz, Orphan-Rehydrierung, `_pid_alive`.
- Requires: PROJ-27 (Liveness + Reanimieren) — `derive_liveness`, Auto-Reanimierung, `claude --resume`-Pfad.
- Verwandt: PROJ-17 (Recovery über den Vault) — Wiederaufnahme verlorener Stränge.
- Verwandt: PROJ-4 / PROJ-10 (Decision Cards / Trust-Policy) — Gate gegen Selbst-Restart des eigenen Hosts.
- Verwandt: Deployment (`deploy.sh` / systemd `jupiter-backend`).

## Beschreibung
Im Live-Betrieb sind zwei Session-Management-Defekte aufgetreten:

**Defekt 1 — Geister-„aktiv" (bereits behoben, Teil 1):** `ClaudeCodeDriver`/`GenericCliDriver.is_alive` prüften nur asyncios `returncode`. Stirbt der Prozess, ohne dass der Event-Loop ihn reapt, bleibt `returncode = None` → die Session meldete fälschlich `status=running` / `liveness=aktiv` **ohne laufenden Prozess**. Folge: falscher Indikator **und** die Auto-Reanimierung greift nicht (sie feuert nur auf „hängt", nie auf „aktiv") → die Session saß unsichtbar fest.

**Defekt 2 — Fleet-Kill bei Backend-Restart (Hauptscope):** Jeder `claude`-Prozess läuft als **Kind im systemd-cgroup von `jupiter-backend`** (`KillMode` = Default `control-group`, kein `start_new_session`). Jeder Backend-Neustart — Deploy-Webhook, Crash **oder ein vom Agenten selbst ausgelöster** `systemctl restart` / `deploy.sh` — schickt SIGTERM an die ganze Gruppe und **verwaist alle laufenden Sessions fleet-weit**; der laufende Turn geht verloren (DONE feuert nie → kein Vault-Log → nicht sauber wiederherstellbar). Beobachtet: eine Session, deren eigener Agent „Backend neu starten:" ausführte, hat sich selbst (und alle parallelen Sessions) gekillt.

Dieses Feature härtet den Session-Lebenszyklus: prozess-verifizierte Lebendigkeit (Teil 1) **und** **Graceful Drain + Auto-Resume** über einen Backend-Neustart hinweg (Teil 2) — so überlebt die *Arbeit* einen Restart, auch wenn der *Prozess* es nicht tut, und ein Agent reißt nicht ungebremst seinen eigenen Host ab.

## User Stories
- Als Nutzer möchte ich, dass eine Session, deren Prozess (egal warum) gestorben ist, **sofort korrekt als „tot" angezeigt** wird und nicht als „aktiv" hängen bleibt — damit ich (oder die Automatik) sie reaktivieren kann.
- Als Nutzer möchte ich, dass meine **laufenden Sessions einen Backend-Neustart überstehen**: nach Deploy/Neustart laufen sie automatisch weiter, statt verwaist und mit verlorenem Turn dazustehen.
- Als Nutzer möchte ich, dass bei einem Neustart **kein laufender Turn verloren** geht (Stand wird vor dem Prozess-Ende gesichert).
- Als Nutzer möchte ich **kein Reanimations-/Resume-Gewitter** bei einem Backend-Crash-Loop — nach wenigen Versuchen bleibt nur der manuelle Knopf.
- Als Nutzer möchte ich, dass ein Agent, der den **eigenen Host neustartet** (`systemctl restart jupiter-backend`, `deploy.sh`), das nicht unbemerkt/ungebremst tut, sondern eine Freigabe braucht — damit er nicht die ganze Flotte (inkl. sich selbst) abschießt.

## Acceptance Criteria
- [x] **Prozess-verifiziertes `is_alive` (Teil 1 — umgesetzt):** Eine Session ohne laufenden OS-Prozess meldet `is_alive=False` → `derive_liveness` liefert „tot" (nicht „aktiv"); der korrekte Indikator erscheint und die (manuelle/automatische) Reanimierung kann greifen.
- [ ] **Graceful Drain beim Backend-Shutdown:** Beim geordneten Stop/Restart des Backends werden laufende Sessions **vor** dem Prozess-Ende sauber pausiert und ihr Stand (Metadaten + laufender Turn/Transkript) persistiert — kein stiller Verlust.
- [ ] **Auto-Resume beim Backend-Startup:** Zuvor laufende, sauber gedrainte Sessions werden nach dem Neustart **automatisch** fortgesetzt (vorhandener `claude --resume`-Pfad), ohne manuelles Zutun; der Nutzer findet die Flotte weiterlaufend vor (nicht „Verwaist").
- [ ] **Kein Resume-Sturm:** Auto-Resume respektiert ein Limit + Backoff und unterscheidet **geplanten Drain** von **wiederholtem Crash** (Crash-Loop → nach N Versuchen nur noch manueller Knopf, kein Endlos-Resume). Respektiert das Session-Limit (PROJ-14).
- [ ] **In-flight-Turn nicht verloren:** Der zum Restart-Zeitpunkt laufende Turn wird recoverbar gemacht (Vault-Log/Recovery-Pfad), sodass PROJ-17-Recovery ihn aufnehmen kann — die DONE-Log-Lücke ist geschlossen.
- [ ] **Selbst-Restart-Gate:** Ein Tool-Aufruf, der den eigenen Host neustartet (`systemctl restart jupiter-backend`, Aufruf von `deploy.sh`, o. ä.), wird erkannt und über die Trust-Policy/Decision Card **gegated** (Freigabe nötig) statt ungebremst durchzulaufen — auch im Bypass.
- [ ] **Harter Crash (SIGKILL/OOM, kein Drain möglich):** degradiert sauber auf das bestehende Orphan-/Recovery-Verhalten (PROJ-14/17) — keine Falschanzeige „aktiv", Wiederaufnahme über den Knopf/Recovery.
- [ ] Alle Texte/Logs deutsch; keine Regression in der bestehenden Suite.

## Edge Cases
- **Backend-Crash-Loop:** wiederholte Neustarts lösen **kein** Auto-Resume-Gewitter aus (Versuchs-Limit + Backoff, geplanter Drain ≠ Crash).
- **Session in `awaiting_approval` (offene Decision Card) beim Restart:** nach Resume ist der Card-Zustand sauber (offene Cards werden obsolet/neu aufgebaut, kein hängender Future).
- **Mehrere parallele Sessions:** alle werden gedrained und einzeln innerhalb des Session-Limits (PROJ-14) wieder fortgesetzt.
- **Geplanter Deploy vs. harter Kill:** SIGTERM/Drain-Fenster → sauberes Drain; SIGKILL/OOM → kein Drain → Fallback Orphan/Recovery.
- **Selbst-Restart trotz Bypass:** Das Gate greift auch im `bypassPermissions` (harte Reißleine wie Phasen-/Watchdog-Gate), damit ein Agent den Host nicht ungefragt neustartet.
- **Prozess als Zombie (defunct, nicht gereapt):** `is_alive` sollte ihn nicht dauerhaft als lebend führen (Teil-1-Fix deckt den vollständig verschwundenen Prozess ab; Zombie-Behandlung in der Architektur prüfen).

## Technical Requirements (optional)
- **Kein Hot-Path-Regress:** `is_alive` bleibt O(1) (ein zusätzlicher `os.kill(pid,0)`); Drain/Resume hängen am `lifespan` (Start/Stop), nicht am Event-Loop.
- **Eine Quelle der Lebendigkeits-Logik:** `is_alive`-PID-Prüfung und `SessionManager._pid_alive` teilen sich die Semantik (`base.pid_alive`).
- **Wiederverwendung:** Drain/Resume nutzen den vorhandenen `_resume()`/Rehydrierungs-Pfad (PROJ-14/27) und den Vault (PROJ-2/17) — kein zweiter Mechanismus.
- **Graceful-Stop-Fenster:** ggf. `systemd` `TimeoutStopSec` so wählen, dass das Drain abgeschlossen werden kann.

## Betroffene Features (Cross-Feature-Impact — explizit)
| Feature | Wirkung |
|---|---|
| **PROJ-1** | `is_alive` beider Subprozess-Treiber gehärtet; Lebenszyklus erweitert. |
| **PROJ-14** | Orphan-Rehydrierung wird zu Auto-Resume erweitert; `_pid_alive`-Semantik geteilt. |
| **PROJ-27** | `derive_liveness` profitiert vom korrekten `is_alive`; Auto-Resume muss sich mit der „Orphans nicht ungefragt auto-reanimieren"-Regel vertragen (Drain ≠ Crash). |
| **PROJ-17** | In-flight-Turn-Persistenz speist die Vault-Recovery. |
| **PROJ-4/10** | Selbst-Restart-Erkennung als Decision-Card/Trust-Policy-Gate. |
| **Deployment** | Zusammenspiel mit `deploy.sh`/systemd (Drain-Fenster, KillMode-Erwägungen). |

## Offene Design-Frage (mit Nutzer geklärt, 2026-06-24)
- **Restart-Verhalten laufender Sessions:** Gewählt **„Graceful Drain + Auto-Resume"** — vor dem Restart drainen/persistieren, nach dem Neustart automatisch via `claude --resume` fortsetzen (Sessions überleben nicht in-process, aber kein Turn-Verlust, Recovery automatisch). Verworfen: „Prozesse überleben Restart" (Re-Attach an tote stdout/stdin-Pipes kaum machbar) und reine „Minimal-Härtung".

## Implementierungs-Status
- **Teil 1 (prozess-verifiziertes `is_alive`) ist bereits umgesetzt** (kleinster sicherer Schritt, vor dieser Spec): `backend/app/engine/base.py::pid_alive()` + gehärtetes `is_alive` in `claude_driver.py` und `generic_cli_driver.py`; `backend/tests/test_proj33_is_alive.py` (7 Tests), volle Suite grün. Commit folgt.
- **Teil 2 (Graceful Drain + Auto-Resume + Selbst-Restart-Gate)** ist der offene Hauptscope → `/abc-architecture 33`.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-24 · **Stack:** FastAPI (conda `Dashboard`, In-Memory-Registry + SQLite-Live-Index, 1 uvicorn-Worker) + kleiner Next.js-Zusatz (Card + Indikator) + kein Neon/MinIO · **Branch:** main (mit Nutzer entschieden 2026-06-24 — PROJ-33 wird auf `main` weitergebaut; Teil-1-Commit `48cf886` + Spec liegen bereits dort).

### Leitidee
Drei Bausteine, alle auf vorhandenen Pfaden — **keine** zweite Buchhaltung:
1. **Drain** beim geordneten Shutdown: laufende Sessions als „bewusst beendet" markieren (Flag `drained_at`), bevor systemd die Prozesse killt.
2. **Auto-Resume** beim Startup: genau diese gedrainten Sessions automatisch via `claude --resume` fortsetzen (nicht die crash-verwaisten — die bleiben „tot" + Knopf, PROJ-27-Regel).
3. **Selbst-Restart-Gate**: ein Tool-Aufruf, der den eigenen Host neustartet, wird zur Freigabe-Card (bypass-fest), bevor er läuft.

### A) Ablauf-Logik (Klartext)
```
Backend-Shutdown (lifespan finally, vor repo.close, main.py:86)
  └─ manager.drain(): je aktiver Session  → pause()  + drained_at=jetzt + persist()
                      (schnell: nur markieren/spiegeln, NICHT auf Turn-Ende warten)

systemd killt danach die cgroup → claude-Kindprozesse enden (Drain-Marke ist schon persistiert)

Backend-Startup (rehydrate, manager.py:910)
  ├─ Zeile hatte drained_at?  → JA  → Auto-Resume (claude --resume), Flag löschen
  │                              NEIN → wie bisher „Verwaist/ERROR" + Reaktivieren-Knopf
  └─ Auto-Resume mit Limit/Backoff (kein Sturm bei Crash-Loop) + Session-Limit (PROJ-14)

Tool-Gate (request_decision, vor Policy-Evaluate, manager.py:~495)
  └─ Bash-Kommando trifft Selbst-Restart-Muster? → „self_restart"-Card (pausiert, bypass-fest)
```

### B) Datenmodell (alles Live-Index/In-Memory, kein Neon)
- **Neue Spalte `drained_at TEXT`** im SQLite-Live-Index (`session_index`) — über den vorhandenen idempotenten `_MIGRATIONS`-Mechanismus (`ALTER TABLE … ADD COLUMN`), genau wie zuletzt `recovery_dismissed`. Gesetzt beim Drain, gelöscht nach erfolgreichem Auto-Resume. **Das ist das „Drain ≠ Crash"-Signal.**
- In-Memory: ein kleines `resume_on_restart`/Drain-Kennzeichen am `SessionState` (reist über `_row()` in den Index).
- **Kein neues Turn-Transkript-Checkpoint nötig:** die maßgebliche Konversation persistiert **Claude selbst** (`claude --resume` lädt sie). Jupiters In-Memory-Transkript-Ansicht baut sich nach dem Resume aus dem Live-Stream neu auf. „Kein Turn-Verlust" wird also über Claudes eigene Session-Persistenz + Resume erreicht, nicht über ein eigenes Checkpoint.

### C) API-/Komponenten-Form
```
Backend
├── main.py            lifespan: drain() im finally (vor repo.close); rehydrate ruft Auto-Resume
├── manager.py         drain(); rehydrate() um drained_at-Zweig + _auto_resume_from_row()
│                       request_decision: harte self_restart-Reißleine vor Policy-Evaluate
│                       (Muster-Check auf tool_input["command"]) → _open_card(card_type="self_restart")
├── db/session_index.py  _MIGRATIONS += ("drained_at","TEXT"); COLUMNS erweitert
└── config              Selbst-Restart-Muster (z. B. in policy.yaml o. eigener Liste),
                        Auto-Resume-Limit/Backoff (analog Liveness-Schwellen)

Frontend (minimal)
├── decision-card.tsx  Render-Zweig card_type="self_restart" (Freigeben/Ablehnen, wie watchdog_pause)
└── (optional) Indikator „nach Neustart fortgesetzt" am Session-Tile
```
- **Keine neuen Endpunkte:** Drain/Resume sind interner Lifecycle; das Self-Restart-Gate nutzt die bestehenden Decision-Card-Endpunkte (Freigeben/Ablehnen).

### D) Tech-Entscheidungen (WARUM)
- **`drained_at`-Flag statt Heuristik:** nur ein *geordneter* Shutdown setzt es → ein harter Crash/OOM (SIGKILL, kein lifespan-finally) hat es nicht → wird korrekt als Crash behandelt (kein Auto-Resume-Sturm; PROJ-27-Regel bleibt). Sauberste Unterscheidung Drain vs. Crash.
- **Auto-Resume nur für gedrainte Sessions:** verträgt sich mit PROJ-27 („Orphans nach Restart nicht ungefragt auto-reanimieren") — die Crash-Orphans bleiben manuell, nur die *bewusst* gedrainten kommen automatisch zurück.
- **Drain ist schnell (nur markieren+persistieren), nicht „Turn fertiglaufen lassen":** passt in das systemd-Stop-Fenster; die eigentliche Wiederaufnahme macht `claude --resume`.
- **Self-Restart als harte Reißleine (bypass-fest), nicht als Policy-Regel:** `policy.evaluate` sieht den Kommando-Inhalt nicht (nur `tool_name`/role/skill/project) — daher ein inhaltsbasiertes Gate an derselben Stelle wie Watchdog-/Phasen-Gate, das auch im Bypass feuert (sonst könnte ein Agent den Host ungebremst neustarten).
- **Wiederverwendung:** Drain nutzt `pause()`+`_persist()`, Resume den `_resume()`-/Rehydrierungs-Pfad, das Gate die `_open_card`-Mechanik — alles vorhanden.

### E) Komplementär (Deployment, kein Code)
- **`KillMode=mixed`** für `jupiter-backend.service` erwägen: SIGTERM zuerst nur an den Hauptprozess (Drain-Fenster), erst nach `TimeoutStopSec` SIGKILL an den Rest. Gibt dem Drain Luft, bevor die Kinder sterben. (Reines Unit-File-Tuning, human-gated.)

### F) Dependencies
Keine neuen Pakete (vorhandenes `asyncio`/`PyYAML`/SQLite). Frontend: nur ein Card-Render-Zweig.

### Mapping Akzeptanzkriterien → Bausteine / Verantwortliche
| Kriterium | Baustein | Spezialist |
|---|---|---|
| Prozess-verifiziertes `is_alive` (Teil 1) | `base.pid_alive` + gehärtetes `is_alive` ✅ erledigt | Backend |
| Graceful Drain beim Shutdown | `manager.drain()` im `lifespan`-finally + `drained_at` | Backend |
| Auto-Resume beim Startup | `rehydrate()`-Zweig + `_auto_resume_from_row()` | Backend |
| Kein Resume-Sturm | Limit/Backoff + `drained_at`-Unterscheidung | Backend |
| In-flight-Turn nicht verloren | `claude --resume` (Claude-eigene Persistenz) | Backend |
| Selbst-Restart-Gate | inhaltsbasierte Reißleine in `request_decision` + `self_restart`-Card | Backend + Frontend |
| Harter Crash degradiert sauber | kein `drained_at` → bestehender Orphan/Recovery-Pfad | Backend |
| Deutsche Texte; keine Regression | UI-Strings + Tests | Backend + Frontend |

### Handoff-Reihenfolge
Backend-lastig. **`/abc-backend 33`** (Drain/Auto-Resume, `drained_at`-Migration, Self-Restart-Gate, Tests) → **`/abc-frontend 33`** (self_restart-Card-Render) → **`/abc-qa 33`**. Alles auf **`main`** (Nutzer-Entscheidung).

### Branch-Hinweis (geklärt)
PROJ-33 wird bewusst auf **`main`** weitergebaut (Nutzer-Entscheidung 2026-06-24) — Teil-1 + Spec liegen bereits dort. Caveat: `main` ist bis zum Feature-Ende potenziell nicht clean-deploybar. Fremde uncommittete PROJ-17-Änderungen (`recovery.py`/`vault.py`) bleiben unangetastet (gehören einer anderen Session).

## Implementierungsnotizen — Backend (2026-06-24, `/abc-backend`, Branch `main`)

**Status:** Teil 1 (is_alive) + Teil 2 (Drain/Auto-Resume/Self-Restart-Gate) backend-seitig implementiert + getestet. **Volle Suite 544 grün**, App importiert sauber. Offen: Frontend (self_restart-Card-Render) + QA.

**Geänderte/neue Dateien (Teil 2):**
- `backend/app/db/session_index.py` — neue Spalte **`drained_at`** (COLUMNS + CREATE TABLE + idempotente `_MIGRATIONS`-Zeile, wie zuletzt `recovery_dismissed`).
- `backend/app/engine/manager.py`:
  - `SessionState.drained_at` (+ in `_row`/`_state_from_row`).
  - Modul-Helfer **`_is_self_restart()`** + `SELF_RESTART_TOOLS` — erkennt `systemctl restart jupiter-backend`, `deploy.sh`, `reboot`/`shutdown` (konservativ; Frontend-only-Restart wird **nicht** gegated).
  - `request_decision`: **harte, bypass-feste Self-Restart-Reißleine** (vor Policy/Bypass) → blockierende `self_restart`-Card.
  - **`drain()`** — beim Shutdown aktive Sessions `pause()` + `drained_at` setzen + **synchron** persistieren.
  - **`auto_resume_drained()`** — beim Startup nur Sessions mit `drained_at` **einmal** via `_resume()` fortsetzen (kein Crash-Sturm), Session-Limit (PROJ-14) gewahrt; Erfolg→Flag löschen, Fehlschlag→Flag löschen+ERROR.
  - `rehydrate()`: unterscheidet **gedraint** (→ „wird automatisch fortgesetzt", Flag bleibt) von **Crash-Orphan** („Verwaist").
- `backend/app/main.py` — `lifespan`: `auto_resume_drained()` nach `rehydrate` (Startup); `drain()` im `finally` vor `repo.close()` (Shutdown).
- `backend/app/config.py` — `auto_resume_on_restart: bool = True` (global abschaltbar).
- Tests: `test_proj33_drain_resume.py` (8) + `test_proj33_is_alive.py` (7) → 15 PROJ-33-Tests.

**„Kein Turn-Verlust":** über Claudes eigene Konversations-Persistenz (`claude --resume`) — kein eigenes Transkript-Checkpoint.

**API-Vertrag fürs Frontend:** neuer **`card_type:"self_restart"`** (blockierende Freigabe-Card mit Future → Freigeben/Ablehnen über die bestehenden Decision-Endpunkte). `decision-card.tsx` braucht einen Render-Zweig (amber-Warnung „Host-/Backend-Neustart beendet laufende Sessions"). Sonst keine neuen Felder/Endpunkte.

**Deployment-Hinweis (human-gated, kein Code):** `KillMode=mixed` in `jupiter-backend.service` gibt dem Drain ein Zeitfenster, bevor systemd die Kindprozesse killt.

**Nächster Schritt:** `/abc-frontend 33` (self_restart-Card), dann `/abc-qa 33`.

## Implementierungsnotizen — Frontend (2026-06-24, `/abc-frontend`, Next.js, Branch `main`)

**Status:** Frontend implementiert + geprüft (Vitest **75 grün**, ESLint sauber, tsc fehlerfrei außer vorbestehendem `md-tree.test.ts`). Bereit für `/abc-qa`.

**Geänderte Dateien (minimal):**
- `nextjs_app/lib/types.ts` — `card_type`-Union um `"self_restart"` ergänzt.
- `nextjs_app/components/cockpit/decision-card.tsx` — neuer Render-Zweig für `self_restart` in `ApproveDenyCard`: **rote** Warnumrandung + `ShieldAlert`-Badge „Host-Neustart", Button „Neustart freigeben"/„Ablehnen"/„Mit Kommentar zurück" (blockierende Freigabe über die bestehenden Decision-Endpunkte — kein neuer API-Call). Approve-Toast „Neustart freigegeben".

**Verhalten:** Will ein Agent den eigenen Host/Backend neustarten (`systemctl restart jupiter-backend`, `deploy.sh`, `reboot`), erscheint eine rote Freigabe-Card statt eines stillen Restarts; der Nutzer gibt frei oder lehnt ab (→ Claude bekommt die Ablehnung inline). Fällt in den Standard-Approve/Deny-Pfad (NICHT die Watchdog-Abbrechen-Aktion), da hier nur der Restart abgelehnt, nicht die Session gestoppt wird.

**Nächster Schritt:** `/abc-qa 33`.

## QA Test Results (2026-06-24, `/abc-qa`, Branch `main`)

**Ergebnis: 8/8 Acceptance Criteria ✅ · alle Edge Cases ✅ · Security sauber · KEINE Critical/High/Medium → produktionsreif.**
Suiten: **Backend 550 passed** (21 PROJ-33: 7 is_alive + 8 Drain/Resume + 6 QA), **Frontend 75 passed**, ESLint sauber, tsc fehlerfrei (außer vorbestehendem `md-tree.test.ts`).

### Acceptance Criteria
| # | Kriterium | Status | Nachweis |
|---|---|---|---|
| 1 | Prozess-verifiziertes `is_alive` (kein Geister-„aktiv") | ✅ | `test_proj33_is_alive` (7, inkl. rc=None+toter PID→False) |
| 2 | Graceful Drain beim Shutdown | ✅ | `test_drain_marks_active_sessions`, `test_drain_skips_terminal_sessions` |
| 3 | Auto-Resume beim Startup | ✅ | `test_auto_resume_resumes_only_drained`, `test_resumed_session_accepts_input` |
| 4 | Kein Resume-Sturm | ✅ | `test_auto_resume_failure_clears_flag_no_storm` (1 Versuch), Crash wird nicht resumt |
| 5 | In-flight-Turn nicht verloren (claude --resume) | ✅ | `test_resumed_session_accepts_input` (Session wieder nutzbar) |
| 6 | Selbst-Restart-Gate (bypass-fest) | ✅ | `test_self_restart_gate_fires_even_in_bypass`, `_approve_allows`, `harmless_not_gated`, `_is_self_restart`-Unit |
| 7 | Harter Crash degradiert sauber | ✅ | `test_rehydrate_crash_orphan_is_not_resume_candidate` (Verwaist, kein Resume) |
| 8 | Legitime Wartestellung weiter „aktiv"; deutsche Texte; keine Regression | ✅ | PROJ-27-Suite grün; 550+75 grün |

### Edge Cases
- **Drain≠Crash:** nur `drained_at` → Auto-Resume; Crash (kein Flag) → Verwaist. ✅
- **Resume scheitert:** `drained_at` gelöscht (genau ein Versuch) → kein Sturm bei wiederholtem Neustart. ✅
- **Session-Limit beim Resume:** Limit=1 + 2 gedrainte → genau 1 fortgesetzt, die andere behält ihr Flag (kein Bypass). ✅ (`test_auto_resume_respects_session_limit`)
- **Terminale Session:** wird nicht gedraint (kein `drained_at`). ✅
- **Bypass-Mode:** Self-Restart-Gate feuert auch im `bypassPermissions`. ✅
- **Harmloses Kommando:** läuft im Bypass durch, keine Card. ✅

### Security / Red-Team
- **Bypass-feste Selbst-Restart-Reißleine** (zentraler Schutz): ein Agent kann den eigenen Host/Backend **nicht still** neustarten (auch nicht im Bypass) → keine Selbst-/Flotten-Tötung ohne Freigabe. ✅
- **Kein Session-Limit-Bypass** über Auto-Resume. ✅
- **Kein selbstverschuldeter Resume-Sturm** (drained_at-Einmal-Versuch + Crash≠Drain). ✅
- **Geister-`is_alive` geschlossen** (eine tote Session maskiert sich nicht mehr als „aktiv"). ✅

### Findings
**Keine Critical/High/Medium.** Info/Low:
1. **Self-Restart-Erkennung ist Muster-basiert** (Substring auf dem Bash-Kommando) — Defense-in-Depth, **kein** Sandbox: ein bewusst verschleiertes Kommando (z. B. in ein Skript schreiben und ausführen) kann es umgehen. Für den realen Fehlerfall (Agent ruft `systemctl restart`/`deploy.sh` direkt) ausreichend; Verschärfung später möglich.
2. **`KillMode=mixed`** ist eine Deployment-Empfehlung (human-gated), im Code nicht erzwungen — ohne sie ist das Drain-Fenster knapper.
3. **SIGKILL/OOM** überspringt den Drain (kein lifespan-Shutdown) → korrekt als Crash-Orphan behandelt (Fallback Recovery), kein Auto-Resume.

**Produktionsreife: JA** (0 Critical/High).

## Deployment (2026-06-24, `/abc-deploy`)
- **Production URL:** https://jupiter.auxevo.tech · **Version:** 0.7.0 · **Host:** Dev-VPS (host-nativ, systemd + GitHub-Webhook → `deploy.sh`).
- **Geshippt mit v0.7.0:** PROJ-33 (prozess-verifiziertes `is_alive` + Graceful Drain/Auto-Resume + Self-Restart-Gate) zusammen mit den PROJ-18-Folgefixes (`dfbdc45`, `03c5e37`) und der PROJ-17-Recovery-Verbesserung (`8dfe06d`).
- **Promotion:** `main` → `origin/main` (Push triggert Webhook-Rebuild + `systemctl restart`). `dev ⊂ main` (kein separater Stand).
- **Caveat (dokumentiert):** Der Deploy-Restart selbst orphaned diesmal noch laufende Sessions (das laufende Backend hatte vor diesem Deploy kein Drain) — beim Deploy waren **0 aktive Sessions**, also kein Verlust. Ab dem **nächsten** Restart greift Drain + Auto-Resume. `KillMode=mixed` (systemd) ist als ergänzende Härtung empfohlen (human-gated, separat).
