# PROJ-71: Effort-Level (Reasoning-Effort) im Neue-Session-Dialog

## Status: Planned
**Created:** 2026-07-14
**Last Updated:** 2026-07-14

## Dependencies
- Requires: PROJ-1 (Engine-Treiber: Claude headless) — `build_argv` in `claude_driver.py` baut den CLI-Aufruf.
- Requires: PROJ-18 (Weitere Engines) — `engines.yaml`/`argv_template` als Mechanismus für zusätzliche CLI-Flags.
- Requires: PROJ-48 (Codex-Engine), PROJ-57 (OpenCode-Harness) — Ziel-Engines für dieses Feature.
- Requires: PROJ-56 (Kontext-Persistenz für Nicht-Claude-Engines) — Codex/OpenCode starten pro Turn einen neuen Exec-Aufruf; der Effort-Wert muss aus der Session-Persistenz erneut in jeden Folge-Turn injiziert werden.
- Requires: PROJ-51 (Engine-/Modellverwaltung) — liefert das Muster für Modellwahl im Neue-Session-Dialog, an dem sich die Effort-Auswahl orientiert.
- Verwandt: PROJ-9 (Smart Launcher) — der Neue-Session-Dialog ist die UI-Oberfläche für dieses Feature.

## Kontext / Motivation
Die drei Jupiter-Engines unterstützen serverseitig ein Reasoning-„Effort"-Level, aber Jupiter setzt es nirgends:
- **Claude Code CLI:** `--effort <low|medium|high|xhigh|max>` — normaler Start-Flag, funktioniert auch im headless-Modus (`-p`), den Jupiter verwendet.
- **Codex CLI:** `-c model_reasoning_effort=<minimal|low|medium|high|xhigh>` — genereller Config-Override.
- **OpenCode CLI:** `--variant <level>` — Modell-/Provider-abhängige Reasoning-Variante.

Alle drei sind reine **Start-Parameter** des jeweiligen CLI-Prozesses — keiner unterstützt eine Effort-Änderung über das laufende Nachrichtenprotokoll (stream-json bei Claude hat kein Effort-Feld pro Message; Codex/OpenCode kennen den Wert nur als Prozess-Flag). Der interaktive Claude-Code-Slash-Command `/effort` funktioniert in Jupiter nicht, weil Jupiter die CLI ausschließlich headless (`-p`/stream-json bzw. tmux-supervisiert ohne echtes TTY) startet — dort existiert kein REPL, an das sich der Picker andocken könnte.

Ziel dieses Features: Der Nutzer wählt das Effort-Level **einmalig beim Erstellen einer Session** im Neue-Session-Dialog, analog zur bestehenden Modellwahl. Es gibt **keinen globalen Default in den App-Einstellungen** (Scope-Entscheidung, siehe unten) und **keine Effort-Änderung während einer laufenden Session**.

## Scope-Entscheidungen (mit Nutzer abgestimmt)
- **Nur Neue-Session-Dialog.** Kein Default-Effort-Tab in den Einstellungen (PROJ-51 bleibt unverändert). Wählt der Nutzer nichts, läuft die Session ohne Effort-Flag mit dem Engine-eigenen Default.
- **Gemeinsame UI-Liste `low / medium / high`.** Eine einheitliche Auswahl für alle drei Engines im Dialog; das Backend mappt intern auf die jeweils passenden nativen Werte pro Engine (siehe Mapping-Tabelle unten). `xhigh`/`max` (Claude, Codex) und weitergehende OpenCode-Varianten sind in v1 bewusst nicht exponiert, um die UI einfach zu halten.
- **Für die ganze Session konstant.** Der gewählte Effort wird in der Session persistiert (analog zu `model`) und bei **jedem** Folge-Turn erneut als Flag an den Engine-Prozess übergeben — auch bei Codex/OpenCode, die pro Turn einen neuen Exec-Aufruf starten. So bleibt das Verhalten über die gesamte Session konsistent, statt nur beim ersten Turn zu gelten.

## Effort-Mapping (UI-Wert → nativer Engine-Wert)
| UI-Wert | Claude (`--effort`) | Codex (`-c model_reasoning_effort=`) | OpenCode (`--variant`) |
|---|---|---|---|
| low | `low` | `low` | `low` |
| medium | `medium` | `medium` | `medium` |
| high | `high` | `high` | `high` |
| *(nicht gewählt)* | Flag entfällt, CLI-Default gilt | Flag entfällt, CLI-Default gilt | Flag entfällt, CLI-Default gilt |

Für OpenCode gilt: `--variant` ist laut CLI provider-/modellabhängig. Unterstützt das gewählte Modell einen Wert nicht, meldet die OpenCode-CLI das zur Laufzeit als Fehler (siehe Edge Cases) — Jupiter validiert das nicht vorab modellspezifisch.

## User Stories
- Als Solo-Entwickler möchte ich beim Erstellen einer neuen Session ein **Effort-Level** wählen können, um bei komplexen Aufgaben höhere Reasoning-Tiefe zu bekommen oder bei einfachen Aufgaben schneller/günstiger zu fahren.
- Als Solo-Entwickler möchte ich, dass die Effort-Wahl **für alle drei Engines** (Claude, Codex, OpenCode) im selben Dialog funktioniert, ohne pro Engine unterschiedliche Bedienung lernen zu müssen.
- Als Solo-Entwickler möchte ich, dass der Effort **über die ganze Session hinweg konstant bleibt**, auch wenn Codex/OpenCode pro Antwort intern einen neuen Prozess starten.
- Als Solo-Entwickler möchte ich, dass ich **nichts wählen muss** — ohne Auswahl verhält sich die Session wie bisher (Engine-Default).
- Als Solo-Entwickler möchte ich im Session-Header/Debug-Kontext erkennen können, **welcher Effort** für eine laufende Session aktiv ist.

## Acceptance Criteria

### Block A — Neue-Session-Dialog
- [ ] Der Neue-Session-Dialog zeigt für Claude, Codex und OpenCode ein optionales Effort-Dropdown mit den Werten `low / medium / high` (deutsches Label, z. B. „Effort (optional)").
- [ ] Standardauswahl ist „kein Effort gesetzt" (Engine-Default); der Nutzer muss aktiv einen Wert wählen.
- [ ] Für Engines ohne Effort-Unterstützung (z. B. zukünftige einfache HTTP-Provider ohne Reasoning-Effort) ist das Dropdown ausgeblendet oder deaktiviert.
- [ ] Die Auswahl ist Teil des Session-Erstellungs-Requests und wird nicht separat nachgereicht.

### Block B — Persistenz & Weitergabe an die Engine
- [ ] Der gewählte Effort-Wert wird in der Session gespeichert (DB, analog zu `model`) und übersteht einen Backend-Neustart.
- [ ] Claude: `build_argv()` in `claude_driver.py` hängt bei gesetztem Effort `--effort <wert>` an den initialen CLI-Aufruf an.
- [ ] Codex: Der `argv_template`-Aufbau für die Codex-Engine hängt bei gesetztem Effort `-c model_reasoning_effort=<wert>` an — bei **jedem** Turn (auch Folge-Turns über `--resume`/Kontext-Persistenz aus PROJ-56), nicht nur beim ersten.
- [ ] OpenCode: Der `argv_template`-Aufbau hängt bei gesetztem Effort `--variant <wert>` an — ebenfalls bei jedem Turn.
- [ ] Ist kein Effort gewählt, wird kein zusätzliches Flag angehängt; bestehendes Verhalten bleibt unverändert (Regression).

### Block C — Sichtbarkeit & Debugging
- [ ] Der aktive Effort-Wert einer Session ist im Session-Objekt/Debug-Log sichtbar (z. B. in den Session-Metadaten, die bereits `model` zeigen).
- [ ] Läuft eine Session ohne gesetzten Effort, wird das eindeutig als „Standard" dargestellt, nicht als leerer/fehlerhafter Zustand.

### Block D — Fehlerbehandlung
- [ ] Lehnt die CLI einen Effort-Wert zur Laufzeit ab (z. B. OpenCode-Modell unterstützt die gewählte Variante nicht), scheitert die Session mit einer klaren deutschen Fehlermeldung statt stillem Hängenbleiben (Regressions-Bezug: PROJ-58/60/62 Lautlos-Hänger-Fixes dürfen nicht umgangen werden).
- [ ] Ungültige Effort-Werte (nicht in `low/medium/high`) werden beim Session-Erstellen serverseitig mit 400 + deutscher Meldung abgewiesen.

## Edge Cases
- **OpenCode-Modell unterstützt gewählte Variante nicht:** CLI-Fehler wird als Session-Fehler durchgereicht, keine stille Endlos-„Arbeitet"-Anzeige (siehe PROJ-60/PROJ-62).
- **Resume einer bestehenden Session ohne gespeicherten Effort (Altbestand vor diesem Feature):** Verhalten bleibt wie bisher — kein Flag, kein Fehler.
- **Codex/OpenCode Folge-Turn nach Backend-Neustart:** Effort muss aus der DB-Persistenz erneut korrekt in den nächsten Exec-Aufruf injiziert werden (Zusammenspiel mit PROJ-66 Transkript-Persistenz).
- **Nutzer wechselt Modell im Dialog, nachdem er Effort gewählt hat:** Effort-Auswahl bleibt bestehen, sofern das neue Modell/Engine Effort weiterhin unterstützt; wechselt der Nutzer auf eine Engine ohne Effort-Unterstützung, wird die Auswahl beim Senden ignoriert und im UI zurückgesetzt.
- **Micro-Apps (Video Summary, Buch-Nuggets, Session-Kondensierung):** Diese starten Sessions programmatisch ohne Neue-Session-Dialog — sie bleiben in v1 ohne Effort-Auswahl (kein Flag, Engine-Default), analog zur Fable-Beschränkung in PROJ-54.
- **Chat-Modus (PROJ-34, keine ABC-Phasen):** Effort-Auswahl gilt dort genauso wie im normalen Session-Start.

## Technical Requirements (optional)
- Backend: neues optionales Feld `effort` (Enum `low|medium|high`) im Session-Erstellungs-Payload/Schema und in `LaunchSpec` (`backend/app/engine/base.py`).
- Backend: Persistenz-Spalte/Feld an der Session analog zu `model` (Migration nötig, falls Sessions relational gespeichert werden).
- Backend: `claude_driver.py::build_argv` erweitern um bedingtes `--effort`.
- Backend: `engines.yaml`-Treiber/Argv-Aufbau für Codex und OpenCode um bedingte Effort-Injection erweitern, inkl. der Stellen, die Folge-Turns bauen (PROJ-56-Kontext-Persistenz-Pfad).
- Frontend: Neue-Session-Dialog (Smart-Launcher-Komponente) um Effort-Select erweitern, analog zum bestehenden Modell-Select-Pattern.
- Tests: Backend — `build_argv`/Argv-Aufbau pro Engine mit/ohne Effort, Validierung ungültiger Werte, Persistenz über Neustart/Resume; Frontend — Dialog rendert Dropdown, sendet Wert korrekt, Regression für Sessions ohne Effort.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-07-14 · **Stack:** FastAPI Engine-Layer (LaunchSpec/SessionState) + SQLite Session-Index + Next.js Neue-Session-Dialog · **Branch:** dev

### Überblick / Kernaussage
PROJ-71 fügt Effort als **drittes Session-Attribut neben `model` und `permission_mode`** ein und folgt exakt deren bestehendem Lebensweg: Payload beim Erstellen → `SessionState` → `session_index`-Persistenz → bei jedem Turn (auch Folge-Turns) neu in die CLI-Argumente gerendert. Es gibt **keine neue Infrastruktur** — nur eine dritte Spalte, ein drittes Dropdown, ein drittes bedingtes Flag pro Treiber.

Wichtigste Design-Entscheidung: Weil der generische CLI-Treiber (`generic_cli_driver.py`, für Codex/OpenCode) Platzhalter **immer** in den Argv-Template einsetzt (kein Konzept für „Flag weglassen, wenn Wert leer"), bekommt Effort **kein** `{effort}`-Platzhalter innerhalb des bestehenden `argv_template`. Stattdessen bekommt jedes Engine-Profil in `engines.yaml` ein **eigenes, optionales Zusatz-Template** (`effort_flag_template`), das der Treiber nur anhängt, wenn ein Effort-Wert gesetzt ist. Das hält den bestehenden, funktionierenden `argv_template`-Mechanismus unverändert und fügt Bedingtheit als reinen Zusatz-Schritt hinzu, statt die String-Replace-Logik umzubauen.

### A) Komponenten-Struktur
```
NewSessionDialog
├── ModelSelect          (bestehend)
├── PermissionModeSelect (bestehend)
└── EffortSelect         (NEU)
    ├── Option: „Standard (kein Effort-Flag)" — Default, kein Wert gesendet
    ├── Option: „Niedrig"
    ├── Option: „Mittel"
    └── Option: „Hoch"
    → nur sichtbar/aktiv, wenn die gewählte Engine die Capability „effort" hat
      (Claude, Codex, OpenCode: ja; künftige einfache HTTP-Provider: nein)

Engine-Layer (Backend)
├── SessionCreate-Schema        + optionales Feld `effort: low|medium|high|None`
├── LaunchSpec                  + Feld `effort: str | None`
├── SessionState                + Feld `effort: str | None` (Quelle für jeden Folge-Turn)
├── ClaudeCodeDriver.build_argv + bedingtes natives `--effort <wert>`
└── GenericCliDriver
    ├── build_generic_argv(...)         unverändert (kennt weiter nur {model}/{session_id}/…)
    └── + bedingtes Anhängen von engine.effort_flag_template, gerendert mit {effort}
        (angewendet bei Erststart UND bei jedem Self-Resume-Folge-Turn)
```

### B) Datenmodell (Klartext)
Kein neues Datenmodell — eine neue, optionale Spalte an der bestehenden Session:
- **`effort`**: einer von `niedrig / mittel / hoch`, oder leer (= Engine-Standard, kein Flag gesetzt).
- Wird **einmalig beim Session-Start** festgelegt und danach nicht mehr geändert (kein Edit-Endpunkt, analog zu `model`).
- Gilt für die **gesamte Session**, auch über mehrere Antworten hinweg — bei Codex/OpenCode wird der Wert bei jeder neuen Antwort erneut mitgeschickt, weil diese Engines intern pro Antwort einen frischen Prozess starten (kein Dauerprozess wie Claude).
- Gespeichert im bestehenden Session-Index (dieselbe Tabelle, die auch `model` hält), übersteht also Backend-Neustarts wie jedes andere Session-Attribut.

### C) API-Shape (Endpunkte, keine Implementierung)
```
POST /sessions
  Body ergänzt um optionales Feld: effort ("niedrig" | "mittel" | "hoch" | nicht gesetzt)
  → wird wie `model` sofort Teil des Session-Zustands, unveränderlich danach.

GET /sessions/{id}
  → zeigt den aktiven Effort-Wert der Session (oder „Standard") in den Metadaten,
    an derselben Stelle, an der `model` heute schon sichtbar ist.

GET /engines
  → jedes Engine-Profil zeigt zusätzlich, ob es Effort unterstützt (Capability),
    damit der Neue-Session-Dialog das Dropdown korrekt ein-/ausblendet.
```
Kein neuer Endpunkt zum nachträglichen Ändern des Effort-Werts — das ist bewusst außerhalb des Scopes (siehe Spec: „keine Laufzeit-Änderung").

### D) Tech-Entscheidungen (Warum)
- **Effort folgt exakt dem `model`-Muster statt einer neuen Mechanik:** Kürzeste, konsistenteste Lösung; Nutzer und Code kennen dieses Muster bereits aus PROJ-51/54.
- **Kein `{effort}`-Platzhalter im bestehenden `argv_template`:** Der generische Renderer ersetzt Platzhalter immer, kann Tokens aber nicht bedingt weglassen. Ein leerer Wert würde ein kaputtes CLI-Argument erzeugen (z. B. `--variant ""`). Ein separates, optionales Zusatz-Template pro Engine vermeidet diesen Fehlerfall komplett, ohne den bestehenden, gut getesteten Renderer anzufassen.
- **Persistenz über den Session-Index, nicht über eine neue Tabelle:** Das bestehende Nachzügler-Spalten-Muster (idempotentes `ALTER TABLE … ADD COLUMN`) ist bereits etabliert und für genau diesen Fall (neues Attribut an einer bestehenden Session) vorgesehen.
- **Effort wird bei jedem Folge-Turn neu injiziert statt einmalig beim Start:** Bei Claude reicht ein einziger Start-Flag, weil die CLI dort dauerhaft läuft. Bei Codex/OpenCode startet aber jeder Turn einen neuen Prozess — ohne erneutes Anhängen würde der Effort nach dem ersten Turn stillschweigend verloren gehen. Das war eine der drei abgestimmten Scope-Entscheidungen der Spec.
- **Gemeinsame UI-Werte `niedrig/mittel/hoch` statt engine-spezifischer Rohwerte:** Vermeidet, dass der Nutzer CLI-interne Begriffe wie `model_reasoning_effort` oder `xhigh/minimal` kennen muss; das Backend übersetzt in die jeweils passenden nativen Werte pro Engine.
- **Effort-Capability pro Engine-Profil statt hartcodierter Liste im Frontend:** Folgt demselben Capability-Muster wie `usage`/`multi_turn`/`abc` in `engines.yaml` (PROJ-51) — neue Engines ohne Effort-Unterstützung brauchen später keine Frontend-Änderung, nur ein fehlendes Capability-Flag.

### E) Abhängigkeiten / Pakete
- **Backend:** keine neuen Pakete. Nutzt bestehendes Pydantic-Schema-Muster, bestehendes SQLite-Migrationsmuster, bestehenden YAML-Registry-Loader.
- **Frontend:** keine neuen Pakete. Bestehendes shadcn/ui `Select` (identisch zum Modell-Dropdown).

### F) Auswirkungen auf bestehende Features
| Feature | Auswirkung |
|---|---|
| PROJ-1/PROJ-63 | `ClaudeCodeDriver.build_argv` bekommt ein zusätzliches bedingtes Flag-Paar; bestehender Aufbau (Modell, Resume, Permission-Mode) bleibt unverändert. |
| PROJ-48/PROJ-57 | `GenericCliDriver` bekommt einen zusätzlichen, optionalen Anhänge-Schritt für Effort — an genau den zwei Stellen, an denen heute schon `LaunchSpec` für Erststart und Self-Resume gebaut wird. |
| PROJ-56 | Effort muss denselben Persistenz-/Rehydrations-Pfad wie `model` über Backend-Neustarts hinweg nehmen — kein separater Mechanismus. |
| PROJ-51 | Kein neuer Tab, aber die Engine-Profile in `engines.yaml` bekommen ein neues optionales Feld (`effort_flag_template`, Capability `effort`); der bestehende Modelle-Tab muss dieses Feld nicht anzeigen/bearbeiten (v1-Scope). |
| PROJ-54 | Gleiches Muster wie Fable: reine Dialog-Option ohne globalen Default — Effort ist konsistent mit dieser bereits etablierten Linie. |
| PROJ-72 (laufender Tmux-Rückbau, in Arbeit) | Betrifft denselben Treiber-Code; Backend-Umsetzung von PROJ-71 sollte erst starten, nachdem PROJ-72 gemerged ist, um nicht auf denselben Zeilen zu kollidieren. |

### G) Bau-Reihenfolge / Handoff
1. **Backend zuerst:** `SessionCreate`/`LaunchSpec`/`SessionState`-Erweiterung, Session-Index-Migration (`effort TEXT`), `ClaudeCodeDriver.build_argv`-Erweiterung, `GenericCliDriver`-Anhänge-Schritt für Erststart + Self-Resume, `engines.yaml`-Beispielprofile (Claude/Codex/OpenCode) um `effort_flag_template` + Capability `effort` ergänzen, Validierung ungültiger Effort-Werte.
2. **Frontend danach:** `EffortSelect` im Neue-Session-Dialog, Payload-Erweiterung, Capability-gesteuertes Ein-/Ausblenden, Anzeige des aktiven Effort-Werts in den Session-Metadaten.
3. **QA:** Regression `POST /sessions` ohne Effort (unverändertes Verhalten), Effort über mehrere Codex/OpenCode-Turns hinweg, Backend-Neustart mit aktivem Effort, ungültiger Effort-Wert → 400, Capability-Ausblendung bei effort-losen Engines.

## QA Test Results
_To be added by /abc-qa_

## Deployment
_To be added by /abc-deploy_
