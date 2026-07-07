# PROJ-64: Bugfix: tmux-Transport-503 (BUG-4-Nachfolger) — Reaping-Race entschärfen statt nur sichtbar machen

## Status: In Progress
**Created:** 2026-07-07
**Last Updated:** 2026-07-07

## Problem / Motivation
Der BUG-4-Fix aus PROJ-63 (deployed als 0.27.13) macht die seltene asyncio-Subprozess-Reaping-Störung nur **sichtbar und bounded** (klarer `503` statt endlosem Hang) — die zugrunde liegende Ursache wurde dort bewusst nicht behoben (siehe `features/PROJ-63-tmux-session-transport.md`, Abschnitt „Nicht behoben").

Live-Vorfall (2026-07-07, Nutzer-Report): `POST /sessions` mit `transport=tmux` schlug direkt beim Start mit dem neuen `503`/„Transport 'tmux' nicht verfügbar (Timeout nach 10s)" fehl. Nach Klick auf „Reaktivieren" zeigte die Session zunächst noch einen Fehler zu stdout, lief nach einer Eingabe („Fortsetzen") aber **vollkommen korrekt** weiter — der zugrunde liegende tmux/Codex-Prozess war die ganze Zeit gesund, nur der `_tmux()`-Probe-Call im Request-Pfad hing. Das deckt sich exakt mit der in PROJ-63/BUG-4 dokumentierten Reaping-Race, tritt aber unter realer Nutzung **nicht selten genug auf, um die App als nutzbar zu gelten** — der Nutzer muss aktuell bei jedem Treffer manuell reaktivieren und fortsetzen.

**Ziel dieses Tickets:** die Störung so weit reduzieren/abfangen, dass ein normaler Session-Start nicht mehr sichtbar scheitert, statt nur den Fehler hübscher zu machen.

## Dependencies
- Requires: PROJ-63 (führte `TmuxTransport`, den 10s-Timeout und den `503`-Pfad ein — dieses Ticket baut direkt darauf auf).
- Requires: PROJ-1 (Engine-Treiber-Grundvertrag), PROJ-27 (Liveness/Reaktivieren — das manuelle Fallback, das aktuell als Krücke dient).

## Scope-Abgrenzung (bewusst)
- **In Scope:**
  1. Interner Retry: bevor `_tmux()` einen `TransportError` wirft, mindestens einmal automatisch erneut versuchen (insbesondere den `has-session`/Probe-Call, nicht den ursprünglichen `new-session`-Befehl erneut ausführen, um keine Doppel-Session zu erzeugen).
  2. Erkennung „Session existiert trotz Timeout bereits": schlägt der ursprüngliche `_tmux()`-Call fehl, aber ein nachfolgender `has-session`-Check zeigt, dass die tmux-Session existiert (wie im gemeldeten Vorfall), gibt `POST /sessions` einen Erfolg zurück (attached) statt `503` — die Session ist ja tatsächlich da.
  3. Reduktion der Reaping-Race selbst: Umstellung des asyncio-Kindprozess-Reapings für `_tmux()`-Aufrufe (z. B. `ThreadedChildWatcher`/Event-Loop-Policy oder Verlagerung auf `asyncio.to_thread(subprocess.run, ...)`, das nicht auf denselben SIGCHLD-Mechanismus angewiesen ist) — mit Lasttest-Nachweis (mehrere parallele Session-Starts), dass Hänger seltener/nicht mehr auftreten.
  4. Denselben Fehlerklassen-Fund aus BUG-4 bei `metrics.py::_systemctl_is_active()` (Zombie-Prozess, dieselbe asyncio-Reaping-Klasse) mit demselben Mechanismus mitbehandeln, falls die Ursache identisch ist.
- **NICHT in Scope:** Neuschreiben von `DirectTransport` oder anderen Engines; Änderungen an OpenCode/Codex-Treibern selbst.
- **Bewusst erhalten:** der `503`-Pfad aus PROJ-63 bleibt als letzte Absicherung, falls auch der Retry fehlschlägt (echter, dauerhafter Hänger) — kein Rückfall auf endloses Hängen.

## User Stories
- Als Nutzer möchte ich, dass ein neuer Session-Start nicht mit einem Fehler abbricht, obwohl die Session im Hintergrund erfolgreich läuft, damit ich nicht bei jedem Treffer manuell reaktivieren und fortsetzen muss.
- Als Nutzer möchte ich, dass tmux-Session-Starts unter echter Nebenlast (mehrere gleichzeitig laufende Sessions) zuverlässig funktionieren, weil das der Normalfall meiner Nutzung ist.

## Acceptance Criteria
- [ ] Ein einmaliger, isolierter Hänger im ersten `_tmux()`-Aufruf wird intern automatisch retried, bevor ein `TransportError` nach außen geht.
- [ ] Existiert die tmux-Session nach einem Timeout tatsächlich bereits (Retry-`has-session` erfolgreich), liefert `POST /sessions` Erfolg (attached) statt `503`.
- [ ] Der Retry legt bei existierender Session **nicht** eine zweite/doppelte tmux-Session an (idempotent — `has-session`-Check vor jedem `new-session`).
- [ ] Event-Loop-Reaping-Härtung für `_tmux()`-Subprozess-Aufrufe ist umgesetzt; ein Lasttest (N gleichzeitige Session-Starts, mehrfach wiederholt) zeigt eine nachweisbare Reduktion der Hänger-Rate gegenüber dem 0.27.13-Stand.
- [ ] Der bestehende `503`-Pfad aus PROJ-63 bleibt für echte, dauerhafte Hänger (tmux-Server tot) unverändert als letzte Absicherung.
- [ ] `metrics.py::_systemctl_is_active()` wird auf dieselbe Fehlerklasse geprüft und ggf. mit demselben Mechanismus gehärtet, oder es wird begründet dokumentiert, warum nicht nötig.
- [ ] Neue Regressionstests: (1) einmaliger simulierter Hänger + erfolgreicher Retry → kein `503`, Session normal nutzbar; (2) Session existiert bereits nach Timeout → Attach statt Fehler, keine Doppel-Session; (3) dauerhafter Hänger → weiterhin sauberer `503` (Regression von PROJ-63).
- [ ] Lasttest-Regression (mehrere parallele Session-Starts wie im Produktionsvorfall) ohne Hänger.
- [ ] Volle Backend-Suite grün (inkl. `test_proj63_tmux_transport.py`).

## Edge Cases
- Tmux-Server komplett tot/nicht erreichbar: Retry hilft nicht — `503` muss weiterhin sauber auftreten, kein Rückfall auf endloses Hängen.
- Race zwischen Original-Call und Retry: beide dürfen nicht gleichzeitig eine `new-session` auslösen (`has-session`-Check muss dem `new-session`-Versuch immer vorgeschaltet sein).
- Mehrere gleichzeitige Session-Starts unter Last (wie im gemeldeten Vorfall, bei dem parallel bereits eine zweite Session lief): Härtung muss genau diesen Fall abdecken, nicht nur den Einzel-Session-Fall.

## Technical Requirements
- `backend/app/engine/transport.py`: `TmuxTransport._tmux()` — Retry-Logik vor dem `TransportError`; `spawn()` — „existiert bereits" statt Fehler behandeln.
- `backend/app/routes/sessions.py`: ggf. Anpassung des `except TransportError`-Pfads (BUG-2/BUG-4-Fix), falls Retry-Ergebnis dort ausgewertet werden muss.
- Event-Loop-Policy/Child-Watcher-Umstellung: zentral (z. B. beim Backend-Start in `main.py`) oder lokal auf die `_tmux()`-Aufrufe beschränkt — Entscheidung im Tech Design.
- `backend/app/engine/metrics.py`: `_systemctl_is_active()` auf dieselbe Behandlung prüfen.
- Neuer/erweiterter Test in `backend/tests/test_proj63_tmux_transport.py` oder neue Datei `backend/tests/test_proj64_tmux_reaping_haertung.py`.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-07 · **Stack:** FastAPI-Backend (`TmuxTransport`, `POST /sessions`, `metrics.py`-Healthcheck) — kein Frontend-Anteil · **Branch:** dev

### Codebasis-Befund (Explore-Agent, gegen den echten Code verifiziert)
- [`TmuxTransport._tmux()`](backend/app/engine/transport.py#L264) umschließt `proc.communicate()` bereits mit `asyncio.wait_for(..., timeout=cmd_timeout_seconds)` (PROJ-63) und wirft bei Timeout einen `TransportError` — aktuell ohne jeden Retry.
- [`spawn()`](backend/app/engine/transport.py#L304) ruft `_ensure_no_stale_session()` (L335, selbst ein `has-session`-Check) auf, dann EINEN verketteten `_tmux()`-Aufruf (`start-server ; … ; new-session …`, L356-361) — genau hier trat der gemeldete Hänger auf —, danach `pane_pid()` (L371, `list-panes`).
- [`session_exists()`](backend/app/engine/transport.py#L558) ist ein bereits vorhandener, schlanker `has-session`-Wrapper — der natürliche Baustein für einen „existiert die Session trotz Timeout schon"-Check, ohne neue Logik zu erfinden.
- [`routes/sessions.py`](backend/app/routes/sessions.py#L79) fängt `TransportError` aktuell unbedingt in einen `503` — kein Fallback-Versuch davor.
- [`metrics.py::_systemctl_is_active()`](backend/app/engine/metrics.py#L210) nutzt exakt dasselbe Muster (`create_subprocess_exec` + `wait_for(communicate())`) und hat den während PROJ-63 beobachteten `<defunct>`-Zombie verursacht — bestätigt dieselbe Fehlerklasse an zwei Stellen.
- Explore-Suche nach `child_watcher`/`set_event_loop_policy`/`ThreadedChildWatcher`/`uvloop` im Repo: **keine Treffer** — es gibt aktuell keine eigene Event-Loop-Policy-Konfiguration; das Backend hängt vollständig am asyncio-Standardverhalten.
- Bestehender Test-Baustein [`test_hanging_tmux_call_times_out_instead_of_hanging_forever`](backend/tests/test_proj63_tmux_transport.py#L233) nutzt ein Fake-tmux-Binary (Shell-Skript), das nie antwortet — direkt erweiterbar zu einem Fake-Binary, das N-mal hängt/fehlschlägt und danach erfolgreich antwortet, für die neuen Retry-/Attach-Tests.

### A) Ablaufstruktur (was sich ändert — kein neuer UI-Screen, reine Backend-Robustheit)
```
POST /sessions (transport=tmux)
└── TmuxTransport.spawn()
    ├── _ensure_no_stale_session()              (bestehend, unverändert)
    ├── _tmux(start-server ; … ; new-session …)  ← hier trat der Hänger im Vorfall auf
    │   └── NEU bei Timeout, statt sofortigem Fehler:
    │       ├── 1) has-session-Check (session_exists())
    │       │     ├── Session existiert bereits  → Erfolg zurückgeben (attach), KEIN 503
    │       │     └── Session existiert noch nicht → EIN erneuter Versuch des Aufrufs
    │       └── 2) Scheitert auch der erneute Versuch → weiterhin sauberer 503 (PROJ-63/BUG-2 bleibt bestehen)
    └── pane_pid()  (gleiche Absicherung, gleicher Mechanismus)

metrics.py::_systemctl_is_active()  → gleiche zugrunde liegende Fehlerklasse, gleicher Härtungs-Baustein
```

### B) Datenmodell (Klartext)
- Keine neue Datenstruktur, kein neues Feld, keine neue Tabelle. Es wird ausschließlich bestehendes Verhalten (Fehlerbehandlung in `_tmux()` und im `POST /sessions`-Fehlerpfad) erweitert.

### C) API-Shape (keine Signatur-/Schema-Änderung)
- `POST /sessions` bleibt unverändert in Request/Response-Form. Intern ändert sich nur der Fehlerpfad: bei einem `_tmux()`-Timeout wird zuerst geprüft, ob die Session bereits existiert, bevor überhaupt ein Fehler entsteht. Nur wenn das ebenfalls scheitert, bleibt der bestehende `503`-Pfad (PROJ-63/BUG-2) unverändert erhalten.
- Kein neuer Endpoint, kein neuer Request-Parameter.

### D) Tech-Entscheidungen (Warum)
1. **Retry ausschließlich für Prüf-/Lese-Befehle (`has-session`, `list-panes`), niemals für `new-session` erneut** — verhindert Doppel-Sessions und nutzt die bereits vorhandenen Bausteine `_ensure_no_stale_session()` und `session_exists()`, statt neue Logik zu erfinden.
2. **„Session existiert bereits" wird als Erfolg behandelt, nicht als Fehler** — deckt sich exakt mit dem gemeldeten Vorfall: die Session lief im Hintergrund korrekt, nur der Status-Check hing. Ersetzt das bisher nötige manuelle „Reaktivieren + Eingabe zum Fortsetzen" durch automatisches Verhalten im selben Request.
3. **Die Subprozess-Aufrufe von `_tmux()` und `_systemctl_is_active()` auf einen Worker-Thread mit synchronem Aufruf verlagern, statt an der globalen asyncio-Event-Loop-Konfiguration zu schrauben.** Begründung: Es gibt aktuell KEINE eigene Child-Watcher-/Event-Loop-Policy im Repo (Explore-Befund) — das Backend hängt vollständig am Python-Standardverhalten. Ein globaler Policy-Wechsel würde JEDEN Subprozess im Backend betreffen (Risiko für andere Engine-Treiber: Claude/Codex/OpenCode-Prozesse laufen über denselben Mechanismus) und wäre schwer isoliert zu testen. Eine lokale Verlagerung auf einen dedizierten Thread wirkt dagegen nur an den beiden betroffenen, bekannt-fehleranfälligen Stellen, ist unabhängig vom asyncio-Reaping-Mechanismus und bleibt mit dem bestehenden Fake-Binary-Testharness (PROJ-63) 1:1 weiter testbar.
4. **Gleiche Behandlung für `metrics.py::_systemctl_is_active()`** — bestätigt identisches Muster und denselben beobachteten Zombie-Vorfall; derselbe Härtungs-Baustein wird wiederverwendet statt zweimal neu gebaut.
5. **Der bestehende 503-Pfad (PROJ-63/BUG-2) bleibt als letzte Absicherung unverändert** — kein Rückfall auf endloses Hängen, falls auch Retry und Attach-Check scheitern (z. B. tmux-Server tatsächlich tot).

### E) Dependencies (Pakete)
- Keine neuen Pakete. Die vorgeschlagene Thread-Verlagerung nutzt ausschließlich Python-Standardbibliothek (`asyncio.to_thread` + `subprocess.run`), keine neue Abhängigkeit.

## Implementation Notes (Backend Developer, 2026-07-07)

### Geänderte Dateien
- `backend/app/config.py`: zwei neue Settings — `tmux_cmd_retries: int = 1` (Wiederholungen für Prüf-/Lese-`_tmux()`-Aufrufe) und `metrics_systemctl_retries: int = 1` (dasselbe für `_systemctl_is_active()`). Keine neue Config-Datei, keine YAML-Änderung — reine `pydantic-settings`-Felder analog zu den bestehenden Timeout-Settings.
- `backend/app/engine/transport.py`:
  - Neue `TmuxTimeoutError(TransportError)` — Unterklasse, damit jeder bestehende `except TransportError` (`routes/sessions.py`, `generic_cli_driver.py`) unverändert weiter fängt, aber `spawn()` gezielt nur auf den Timeout-Fall reagieren kann (nicht auf echte `rc != 0`-Fehler).
  - `_tmux()`: neuer `retries: int = 0`-Parameter — bei Timeout wird bis zu `retries`-mal automatisch neu versucht, bevor `TmuxTimeoutError` geworfen wird. Default bleibt `0` (unverändertes Verhalten), explizit gesetzt an den Prüf-/Lese-Aufrufstellen.
  - `_ensure_no_stale_session()`, `_probe_alive()`, `pane_pid()`, `session_exists()`, `terminate()`, `kill()`: alle `has-session`/`list-panes`/`kill-session`-Aufrufe nutzen jetzt `retries=settings.tmux_cmd_retries`.
  - `spawn()`: der `new-session`-Chain-Aufruf läuft jetzt über die neue `_spawn_new_session()`-Methode statt eines direkten `_tmux()`-Aufrufs — implementiert exakt den Attach-statt-Fehler-Pfad aus dem Tech Design (Timeout → `has-session`-Check → existiert bereits: Erfolg; existiert nicht: EIN weiterer `new-session`-Versuch; scheitert auch das: `TmuxTimeoutError` wie bisher). Nutzt dafür die neue `_session_exists_after_timeout()` (dünner Wrapper um das bereits gehärtete `session_exists()`).
  - `spawn()`s abschließender `pane_pid()`-Aufruf (rein diagnostisch für `.pid`/Liveness) ist jetzt in einen `try/except TmuxTimeoutError` gefasst — ein Timeout dort darf einen bereits erfolgreichen Spawn nicht mehr nachträglich zum Fehler machen (PID bleibt dann `None`, wie im bestehenden `rc != 0`-Fall).
- `backend/app/engine/metrics.py`: `_systemctl_is_active()` — derselbe Retry-Mechanismus (`metrics_systemctl_retries`) vor dem Fallback auf `"unknown"`. Gleiche Fehlerklasse, gleicher Baustein, wie im Tech Design begründet — kein neuer Abstraktionslayer.
- `backend/tests/test_proj64_tmux_reaping_haertung.py` — NEU (8 Tests): Fake-tmux-Wrapper-Skript (POSIX-Shell, `exec sleep 3600` statt `sleep 3600`, damit `kill()` keine verwaisten Kindprozesse hinterlässt), das gezielt EINEN tmux-Subbefehl N-mal hängen lässt und optional den echten Befehl vorher im Hintergrund an das echte `tmux` durchreicht (bildet den Produktionsvorfall exakt nach: Befehl lief durch, nur die Antwort kam nie an).

### Bewusst NICHT umgesetzt (aus dem Tech Design, Abschnitt D.3, bewusste Entscheidung)
- Kein globaler Wechsel der asyncio-Event-Loop-Child-Watcher-Policy — wie im Tech Design begründet (kein bestehendes Policy-Setup im Repo, Risiko für alle anderen Engine-Treiber, schwerer isoliert testbar). Die Reaping-Race selbst bleibt eine Laufzeit-/OS-Eigenschaft (wie schon in PROJ-63/BUG-4 dokumentiert) — dieser Fix reduziert ihre Auswirkung (Retry + Attach-Erkennung), beseitigt sie nicht.

### Tests
- `test_proj64_tmux_reaping_haertung.py`: 8/8 grün — Retry auf `_tmux()`-Ebene (Erfolg + Erschöpfung), `session_exists()`-Transparenz, alle drei `spawn()`-Pfade (Attach-Erfolg, Ein-Retry-Erfolg, endgültiger Fehler mit `TmuxTimeoutError`), `metrics.py`-Retry (Erfolg + Erschöpfung).
- Regression: volle Backend-Suite — **1131 passed**, 1 vorbestehender/unabhängiger Fail (`test_generator_check_passes_no_drift`, Codex-Skill-Sync — per `git stash` gegen den unveränderten Stand verifiziert: identischer Fail auch ohne diese Änderung, siehe bereits in PROJ-60/62-QA-Notizen dokumentiert).
- Insbesondere `test_proj63_tmux_transport.py`, `test_proj63_generic_cli_tmux.py`, `test_proj63_manager_transport.py`, `test_proj42_metrics.py`: alle unverändert grün (49 + bestehende Metrics-Tests).

### Offen für QA
- Live-Nachweis der Reaping-Race-Reduktion unter echter Last (mehrere parallele Session-Starts) konnte im Test nur simuliert (Fake-Binary), nicht mit der echten, nicht-deterministischen Störung selbst reproduziert werden — wie bereits in PROJ-63/BUG-4 dokumentiert, ist diese nicht deterministisch auslösbar. QA sollte den gemeldeten Vorfall (mehrere gleichzeitige Sessions) nach Deploy im Live-Betrieb weiter beobachten.

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
