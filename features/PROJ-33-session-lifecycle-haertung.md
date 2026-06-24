# PROJ-33: Session-Lifecycle-Härtung (Restart-Resilienz + prozess-verifiziertes Liveness)

## Status: Planned
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
_To be added by /abc-architecture_

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
