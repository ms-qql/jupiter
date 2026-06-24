# PROJ-16: Amok-Watchdog + Limits

## Status: In Progress
**Created:** 2026-06-23
**Last Updated:** 2026-06-24
**Baustein:** #19 (kritischstes Failure-Szenario)

## Dependencies
- Requires: PROJ-1 (Engine-Treiber) — überwacht den Live-Event-Stream der Session.
- Requires: PROJ-4 (Decision Cards) — eine pausierte Session erzeugt eine Card.
- Requires: PROJ-10 (Trust-Policy) — Watchdog nutzt dieselbe Policy/Limits als Reißleine.

## Beschreibung
Autonomie braucht eine **Reißleine**: Token-/Zeit-/Aktions-**Limits** plus ein **Watchdog**, der Endlosschleifen und wildes Schreiben erkennt und die Session **pausiert (nicht killt)** → Decision Card. So bleibt der Fortschritt erhalten und der Nutzer entscheidet (weiterlaufen / abbrechen / korrigieren).

## User Stories
- Als Nutzer möchte ich, dass eine durchdrehende Session automatisch pausiert wird, bevor sie Schaden anrichtet oder Tokens verbrennt.
- Als Nutzer möchte ich beim Pausieren eine Decision Card mit dem Grund (welches Limit/Muster) und Handlungsoptionen sehen.
- Als Nutzer möchte ich Limits (Tokens/min, Laufzeit, wiederholte identische Aktionen, Schreibrate) konfigurieren.
- Als Nutzer möchte ich eine pausierte Session gezielt **fortsetzen, abbrechen oder mit Korrektur** weiterführen.

## Acceptance Criteria
- [ ] Konfigurierbare Limits: **Tokens/Zeitfenster**, **max. Laufzeit ohne Fortschritt**, **wiederholte identische Tool-Calls**, **Schreibrate** (Writes/Zeitfenster).
- [ ] Bei Überschreiten wird die Session **pausiert** (Prozess nicht getötet) und in einen klar erkennbaren Zustand „pausiert/Watchdog" versetzt.
- [ ] Es wird eine **Decision Card** erzeugt: Grund (welche Metrik), relevanter Ausschnitt, Aktionen **Fortsetzen / Abbrechen / Mit Kommentar korrigieren**.
- [ ] Die Erkennung läuft live auf dem Event-Stream und unterscheidet **Schleife** (identische Wiederholung) von legitimer Iteration.
- [ ] Watchdog **sticht auto-allow** (PROJ-10): selbst autonom erlaubte Aktionen werden bei Alarm pausiert.
- [ ] Fortsetzen setzt die Zähler des ausgelösten Limits zurück (kein sofortiges Re-Trigger).
- [ ] Schwellen sind zentral konfigurierbar; sinnvolle Defaults aus PRD-Offenpunkt #4.
- [ ] Alle Texte deutsch.

## Edge Cases
- **False Positive** (legitime lange Aufgabe) → Fortsetzen muss reibungslos sein; Schwellen anpassbar; „diesmal erlauben".
- **Mehrfach-Alarm** in Folge → keine Card-Flut; nach Fortsetzen Cooldown.
- **Session stirbt während Pause** → Card wird obsolet (wie PROJ-4-Abandon).
- **Schreibrate-Spike legitim** (z. B. Codegen) → unterscheidbar von „wildem Schreiben" über Pfad-/Wiederholungsmuster.
- **Limit-Konfig fehlt** → konservative Defaults greifen, nie „kein Watchdog".

## Technical Requirements (optional)
- Erkennung im Event-Verarbeitungs-Pfad des SessionManagers (geringe Latenz, kein Hot-Path-Regress).
- „Pausieren" = Stream/Prozess anhalten ohne Kill; sauber fortsetzbar.
- Metriken pro Session zählbar in Sliding Windows; Defaults konfigurierbar via Settings.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-24 · **Stack:** FastAPI (Engine/Watchdog) + Next.js (Watchdog-Card + Settings) + dateibasierte Config (YAML, kein DB) · **Branch:** dev

### Leitidee
Der Watchdog ist **kein neuer Freigabe-Typ**, sondern ein **Sicherheits-Schaltkreis** über zwei vorhandenen Stellen:
1. **Messen** im Event-Pfad (`handle_event`/`_apply_usage`) — Schiebefenster (Sliding Windows) für Tokens, Laufzeit-ohne-Fortschritt, Schreibrate und identische Tool-Wiederholungen. Reines In-Memory-Zählen, kein Hot-Path-Regress.
2. **Anhalten** am vorhandenen Per-Tool-Gate (`request_decision`) — ist ein Limit gerissen, wird der **nächste Tool-Aufruf** in eine **Watchdog-Card** umgelenkt und blockiert über die bestehende PROJ-4-Future-Mechanik. Genau hier wird **„auto-allow gestochen"**: das Gate feuert vor jedem Tool, auch im Bypass — so hält der Watchdog die durchdrehende Agenten-Schleife wirklich an, ohne den Prozess zu töten.

Warum am Tool-Gate statt am Driver-`pause()`: Das heutige `pause()` (claude_driver) blockiert nur **neue Eingaben** — der laufende Turn (und damit eine Schleife *innerhalb* eines Turns) läuft weiter. Das Tool-Gate dagegen liegt **im** Agenten-Loop und kann ihn am nächsten Schritt sauber festhalten und wieder freigeben.

### A) Komponenten (was gebaut wird)

```
Watchdog-Monitor (Backend, NEU: engine/watchdog.py)
├── WatchdogMonitor (1 pro SessionRuntime, in-memory)
│   ├── Sliding Windows: Tokens/Zeit · Writes/Zeit (Zeitstempel-Deques)
│   ├── Fortschritts-Uhr: Zeit seit letztem result/Assistenten-Output
│   ├── Wiederholungs-Erkennung: Fingerprint (Tool+Input) der letzten N Calls
│   └── alarm() → (Metrik, Klartext-Grund) | None   +  Cooldown nach Resume
└── WatchdogConfig: Schwellen (Defaults + Live aus watchdog.yaml, optional per Session)

SessionRuntime (engine/manager.py — erweitert, KEIN neuer Pfad)
├── handle_event()/_apply_usage  → Monitor.feed_event(...) füttern (Tokens/Zeit/Progress)
└── request_decision()           → VOR Phasen-Gate/Evaluator: Monitor.alarm()?
                                    JA → Watchdog-Card (card_type="watchdog_pause"),
                                         pausiert — auch im Bypass (sticht auto-allow)
                                    Aktion ausführen → Monitor.feed_tool(tool,input)
                                                       (Writes-Rate + Wiederholung)

Settings „Watchdog" (Next.js)
├── Schwellen-Editor (4 Limits) + globale Defaults / Per-Session-Override
└── „Live übernommen"-Hinweis (kein Neustart), Defekt-/Quelle-Banner

Watchdog-Card (Next.js, components/cockpit)
└── eigenes Rendering (card_type="watchdog_pause"): Grund/Metrik + Ausschnitt,
    Aktionen: Fortsetzen · Abbrechen · Mit Kommentar korrigieren
```

### B) Datenmodell (Klartext, kein DB)

**Watchdog-Limits** — vier konfigurierbare Schwellen, jeweils mit Schiebefenster:
- **Tokens/Zeitfenster** — abgerechnete Tokens pro gleitendem Zeitfenster (z. B. „>X Tokens in 60 s").
- **Max. Laufzeit ohne Fortschritt** — Sekunden seit dem letzten echten Fortschritt (neues `result`/Assistenten-Text), nicht seit Sessionstart.
- **Wiederholte identische Tool-Calls** — N gleiche Aufrufe (Tool + Input-Fingerprint) in Folge → **Schleife**; unterschiedliche Inputs = legitime **Iteration** (so wird unterschieden).
- **Schreibrate** — Writes pro Zeitfenster; Spike legitim (Codegen) wird über **Pfad-/Wiederholungsmuster** entschärft: viele Writes auf *verschiedene* Pfade = ok, identische/gleicher-Pfad-Wiederholung = verdächtig.

Quelle: globale Defaults in `config.py` (`JUPITER_WATCHDOG_*`), live editierbar über `config/watchdog.yaml` (mtime-Reload wie PROJ-10-Policy; fehlt/defekt → eingebaute konservative Defaults, sichtbare Warnung, **nie** „kein Watchdog"). Optionaler Per-Session-Override wie bei der Schwelle (PROJ-5).

**Decision Card** (erweitert `PendingDecision`, in-memory):
- neuer `card_type`-Wert **`watchdog_pause`** (zusätzlich zu `normal`/`phase_transition`/`deny`).
- `triggering_rule` trägt die **ausgelöste Metrik** im Klartext (z. B. „Schreibrate: 41 Writes/60 s > Limit 30").
- `excerpt`/`rationale`/`action` wie gehabt: der blockierte Tool-Call + jüngste Assistenten-Äußerung als „Warum".

**WatchdogMonitor-Zustand** (pro Session, flüchtig): Zeitstempel-Deques (Tokens/Writes), letzte-Fortschritts-Zeit, Ring der letzten Tool-Fingerprints, Cooldown-Deadline. Bewusst **nicht** persistiert (Live-Schutz; nach Restart sind betroffene Sessions ohnehin „verwaist", PROJ-14).

### C) Wo es greift (Verhalten)

Reihenfolge in `request_decision` (vor den PROJ-10-Gates eingehängt):
1. **Watchdog-Alarm?** (Monitor meldet gerissenes Limit, kein Cooldown) → **Watchdog-Card** (`watchdog_pause`), Session pausiert auf der vorhandenen Future — **auch im Bypass** (Reißleine sticht jede operative auto-allow). Auflösung:
   - **Fortsetzen** (`approve`) → Future entsperrt; der ausgelöste Zähler/Fenster wird **zurückgesetzt** + kurzer **Cooldown** (kein sofortiges Re-Trigger, keine Card-Flut).
   - **Mit Kommentar korrigieren** (`deny` + Kommentar) → natives Deny-mit-Begründung (PROJ-4): Kommentar reist inline zu Claude zurück, Session läuft korrigiert weiter; ebenfalls Cooldown.
   - **Abbrechen** → bestehender Stop-Pfad (`POST /sessions/{id}/stop`), kein neuer Mechanismus.
2. Kein Alarm → unverändert weiter zu Phasen-Gate → Evaluator (PROJ-10).

Messen passiert orthogonal: `handle_event` füttert Tokens/Zeit/Fortschritt; nach erfolgtem Tool-Call werden Schreibrate + Wiederholungs-Fingerprint aktualisiert. **Schleife-im-Turn**: da `request_decision` pro Tool-Aufruf feuert, greift die Wiederholungs-Erkennung auch innerhalb eines einzigen Turns (genau der gefährliche Endlos-Fall).

### D) HTTP-Endpunkte (Settings-UI, kein DB)

```
GET  /settings/watchdog   → aktuelle Limits + Quelle/Warnung (Defaults vs. watchdog.yaml)
PUT  /settings/watchdog   → Limits ersetzen (validiert: positive Zahlen/Fenster → 422; schreibt YAML; live)
```
Per-Session-Override optional über das bestehende Session-Settings-Feld (analog `threshold`). Kein neuer Hook-Endpunkt — die Durchsetzung lebt komplett im vorhandenen `request_decision`. Single-User-MVP: kein JWT (konsistent mit PROJ-1/2/5/10/14); Pfade/Secrets nie aus Client-Payload.

### E) Tech-Entscheidungen (Warum)
- **Zwei vorhandene Stellen statt neuem Subsystem** — Messen im Event-Pfad, Anhalten am Tool-Gate. Wiederverwendung der PROJ-4-Pause-Card-Resume-Maschinerie und des PROJ-10-„auto-allow-Stechens" (Gate feuert auch im Bypass). Eine Quelle der Wahrheit, minimaler neuer Code.
- **Anhalten am Tool-Gate statt Driver-`pause()`** — `pause()` lässt den laufenden Turn (und damit eine Schleife) weiterlaufen; das Tool-Gate hält den Agenten-Loop wirklich an und gibt ihn sauber wieder frei. „Pausieren statt killen" bleibt erfüllt: der Prozess lebt, blockiert nur auf der Future.
- **Sliding Windows mit Zeitstempel-Deques** — billige O(1)-Amortisierung im Event-Pfad, kein Hot-Path-Regress (AC + PROJ-14-Prinzip).
- **Schleife ≠ Iteration über Input-Fingerprint** — identische Wiederholung schlägt an, fortschreitende Arbeit (andere Inputs/Pfade) nicht; Schreibrate-Spike via Pfad-Diversität entschärft (Edge-Cases „False Positive", „legitimer Codegen").
- **YAML + Live-Reload + konservative Defaults** — deckt sich mit PROJ-10/PROJ-6 (Datei-Config, mtime-Reload). Defekt/fehlend → Defaults greifen, **nie** „kein Watchdog" (AC).
- **Cooldown + Counter-Reset nach Resume** — verhindert sofortiges Re-Trigger und Card-Flut (Edge-Cases „Mehrfach-Alarm").

### F) Default-Schwellen (PRD-Offenpunkt #4 — Vorschlag, tunebar)
| Limit | Default-Vorschlag | Begründung |
|---|---|---|
| Tokens / Zeitfenster | 200.000 abgerechnete Tokens / 60 s | weit über normalem Turn-Verbrauch; fängt nur echtes Verbrennen |
| Max. Laufzeit ohne Fortschritt | 180 s ohne neues `result`/Assistenten-Output | erkennt Hänger/Stillstand, ohne lange legitime Tools zu killen |
| Wiederholte identische Tool-Calls | 5 identische Aufrufe in Folge | klare Schleife; legitime Retries (2–3) bleiben unberührt |
| Schreibrate | 30 Writes / 60 s (auf verschiedene Pfade entschärft) | Codegen-Bursts ok, „wildes Schreiben" gleicher Pfade schlägt an |

### G) Abhängigkeiten
- Backend: `PyYAML` (bereits durch PROJ-10 vorhanden). Sonst keine neuen Pakete (stdlib `collections.deque`, `time`).
- Frontend: bestehende shadcn/ui-Komponenten (Card, Badge, Dialog, Input, Switch) — nichts Neues.

### H) Abdeckung der Acceptance Criteria
| AC | Umsetzung |
|---|---|
| Konfigurierbare Limits (Tokens/Zeit, Laufzeit-o.-Fortschritt, identische Calls, Schreibrate) | 4 Schwellen in `WatchdogConfig` (config.py + watchdog.yaml + Per-Session) |
| Bei Überschreiten **pausiert** (Prozess nicht getötet), Zustand „pausiert/Watchdog" | Hold auf Future am Tool-Gate; Status `awaiting_approval` + `card_type=watchdog_pause` |
| **Decision Card** mit Grund/Ausschnitt + Fortsetzen/Abbrechen/Korrigieren | Watchdog-Card; `triggering_rule`=Metrik; Aktionen über resolve/stop |
| Live auf Event-Stream, Schleife vs. Iteration | Messen in `handle_event`; Fingerprint-Wiederholung am Tool-Gate |
| Watchdog **sticht auto-allow** (PROJ-10) | Alarm-Prüfung steht **vor** Bypass-/Evaluator-auto-allow |
| Fortsetzen setzt Zähler des ausgelösten Limits zurück | Counter-Reset + Cooldown im Approve-Zweig |
| Zentral konfigurierbar, sinnvolle Defaults (#4) | watchdog.yaml + eingebaute Defaults (Tabelle F) |
| Alles deutsch | UI- + Card-Texte |

### I) Offene Designwahl (für Backend/QA)
- **Config-Ort:** Vorschlag eigene `config/watchdog.yaml` (statt Einbettung in `policy.yaml`), weil es **Limits**, keine Tool-Regeln sind — getrennte Verantwortung, gleiches Live-Reload-Muster. Bei Wunsch nach „einer Policy-Datei" stattdessen ein `watchdog:`-Block in `policy.yaml`.
- **Default-Werte (Tabelle F):** bewusst grob; in QA gegen reale Sessions kalibrieren.

## Frontend-Implementierung (2026-06-24)
Stack: **Next.js** (Jupiter-Override, nicht Flutter). Branch `dev`. UI gegen den geplanten
API-Kontrakt gebaut; Backend (Monitor + Enforcement + `/settings/watchdog`) folgt via `/abc-backend`.

**Neu/geändert:**
- `lib/types.ts` — `card_type` um **`watchdog_pause`** erweitert; neue `WatchdogLimits` (4 Limits: `token_limit`+`token_window_seconds`, `max_idle_seconds`, `max_repeated_calls`, `write_limit`+`write_window_seconds`, plus `enabled`) und `WatchdogSetting` (+ `source`/`warning`).
- `lib/api.ts` — `getWatchdog` (GET `/settings/watchdog`), `setWatchdog` (PUT, live).
- `components/cockpit/watchdog-control.tsx` (neu) — Limit-Editor (An/Aus + 6 Felder mit Hilfetexten), Quelle-/Defekt-Banner (analog Trust-Policy), Client-Sanity (positive Zahlen, Server klemmt zusätzlich), Offline-/404-Fallback („Endpunkt noch nicht gebaut").
- `components/cockpit/settings-dialog.tsx` — dritter Tab **„Watchdog"** (neben Allgemein + Trust-Policy).
- `components/cockpit/decision-card.tsx` — eigenes Rendering für `watchdog_pause`: amber-Reißleine-Styling + `ShieldAlert`-Badge „Watchdog", Aktionen **Fortsetzen** (`approve`, Toast „Limit zurückgesetzt"), **Mit Kommentar korrigieren** (`deny`+Kommentar → „Korrigiert fortsetzen"), **Abbrechen** (`stopSession`). Die ausgelöste Metrik kommt über das bestehende `triggering_rule`-Feld.

**Verifikation:** `tsc --noEmit` ohne neue Fehler (vorbestehender `md-tree.test.ts`-Fehler unberührt), `eslint` der PROJ-16-Dateien ohne Befund. Backend-Endpunkt fehlt noch → Control fängt Offline/404 ab (amber-Banner).

**Offene Punkte für Backend:** Kontrakt `WatchdogSetting`/`WatchdogLimits` (Feldnamen oben) umsetzen; Watchdog-Card mit `card_type="watchdog_pause"` + Metrik-Text in `triggering_rule`; Per-Session-Override (optional, analog Threshold) noch nicht im UI.

## Backend-Implementierung (2026-06-24)
Stack: FastAPI + **dateibasierter** Watchdog (YAML, kein DB). Branch `dev`. In-Memory/Datei-Ansatz wie PROJ-10.

**Neu/geändert:**
- `engine/watchdog.py` (neu) — **`WatchdogStore`** (YAML, mtime-Live-Reload, fehlende Keys mergen mit Defaults, defekt → Defaults + Warnung, `save()` validiert `> 0`) + **`WatchdogMonitor`** (pro Session): Sliding Windows als Zeitstempel-Deques für Tokens & Schreibrate, Fortschritts-Uhr (Stillstand), Fingerprint-Serie (Schleife ≠ Iteration). `evaluate()` = reine Lese-Prüfung am Tool-Gate, `record()` nimmt erlaubte Calls auf, `reset(metric)` leert das ausgelöste Fenster + setzt **Cooldown** (30 s). Injizierbarer `clock` für Tests. Modul-Singleton `watchdog_store`. Defaults: 200k Tokens/60 s · 180 s Stillstand · 5 identische Calls · 30 Writes/60 s.
- `engine/manager.py` — `SessionRuntime` hält einen `WatchdogMonitor`. `request_decision` prüft **ZUERST** (vor Phasen-Gate **und** vor Bypass-Auto-Allow) `watchdog.evaluate(...)`; bei Alarm → `_open_card(card_type="watchdog_pause", triggering_rule=<Metrik-Klartext>)` (pausiert, Prozess lebt), nach Auflösung `reset(metric)`. Kein Alarm → `record(...)`. `_apply_usage` füttert `feed_usage(billed_tokens)`; Assistenten-Output ruft `note_progress()`. → **Watchdog sticht auto-allow** (auch im Bypass).
- `schemas/settings.py` — `WatchdogLimitsPut` (alle Zähler `Field(gt=0)` → 422) + `WatchdogSettingRead` (+ `source`/`warning`).
- `routes/settings.py` — `GET /settings/watchdog`, `PUT /settings/watchdog` (validiert, schreibt YAML, live).
- `schemas/sessions.py` — `card_type`-Kommentar um `watchdog_pause` ergänzt (Feld ist freier `str`, Wert reist ohne Schema-Bruch ins Frontend).
- `config.py` — `watchdog_config_path` (Default `backend/config/watchdog.yaml`, muss nicht existieren).
- `config/watchdog.example.yaml` (dokumentierte Vorlage, nicht geladen); Laufzeit-`watchdog.yaml` in `.gitignore`.

**Abweichung vom Tech-Design:** keine `JUPITER_WATCHDOG_*`-Einzel-Envs — die YAML-Datei (+ eingebaute Defaults) ist die alleinige Konfig-Fläche, 1:1 wie PROJ-10s `policy.yaml`. Reduziert Oberfläche, eine Quelle der Wahrheit.

**Bekannte Grenze (für QA):** Stillstands-Erkennung (`max_idle_seconds`) wird **am nächsten Tool-Gate** ausgewertet, nicht von einem Hintergrund-Timer — eine komplett hängende Session ohne weiteren Tool-Call wird erst beim nächsten Aufruf pausiert. Für die realen Amok-Fälle (Schleife/Token-Burn/Schreib-Spike) feuert das Gate ohnehin. Background-Timer wäre ein optionaler Ausbau.

**Tests** (`tests/test_proj16_watchdog.py`, 16): Monitor (Schleife vs. Iteration, Token-Fenster+Ablauf, Stillstand, Schreibrate nur für Write-Tools, Reset+Cooldown, disabled), Store (Defaults/Save+Live-Reload/Defekt-Fallback/Key-Merge/`save` lehnt ≤0 ab), REST (GET-Defaults, PUT-live, 422 bei ≤0), Integration (Schleife öffnet `watchdog_pause`-Card → Fortsetzen → running; **sticht Bypass-auto-allow**). **Gesamt-Suite: 423 passed.**

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
