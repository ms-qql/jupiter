# PROJ-51: Engine- und Modellverwaltung in den App-Einstellungen

## Status: Deployed
**Created:** 2026-06-26
**Last Updated:** 2026-06-27

## Dependencies
- Requires: PROJ-18 (Weitere Engines + iFrame/Launch) — liefert Engine-Registry, `GET /engines`, Provider-Profile und Modellvalidierung über `engines.yaml`.
- Requires: PROJ-48 (Engine — OpenAI Codex CLI) — zeigt, dass Engine-Profile auch Subscription-/CLI-Engines ohne API-Key abbilden können.
- Requires: PROJ-50 (abc-Workflow für die Codex-Engine) — nutzt Engine-Capabilities wie `abc`; die Einstellungsoberfläche darf diese Capability nicht versehentlich entfernen.
- Verwandt: PROJ-9 (Smart Launcher) — der Neue-Session-Dialog liest die sichtbaren Engines und deren Default-Modell.

## Problem / Motivation
Die Multi-Engine-Fähigkeit ist vorhanden, aber die Verwaltung ist heute zu technisch: Provider, Modelle, Default-Modell, API-Base und Verfügbarkeit werden in `backend/config/engines.yaml` gepflegt. Für alltägliche Anpassungen muss der Nutzer YAML editieren, Syntaxfehler riskieren und anschließend prüfen, ob der Launcher die Änderung korrekt sieht.

Ziel dieses Features: Die App-Einstellungen bekommen einen eigenen Bereich **„Modelle"**, in dem Claude, OpenAI, OpenRouter und Swisscom direkt verwaltet werden können. Die UI speichert diese Auswahlen **über das Backend direkt in die bestehende `engines.yaml`**; YAML bleibt also die offene, git-versionierbare Quelle, nur ohne manuelles Editieren im Terminal.

## User Stories
- Als Nutzer möchte ich in den globalen **Einstellungen** sehen, welche KI-Anbieter aktuell konfiguriert und verfügbar sind, ohne `engines.yaml` zu öffnen.
- Als Nutzer möchte ich für **Claude, OpenAI, OpenRouter und Swisscom** die verfügbaren Modelle und das jeweilige Default-Modell bearbeiten können.
- Als Nutzer möchte ich Anbieter aktivieren/deaktivieren können, damit der Smart Launcher nur sinnvolle Optionen anbietet.
- Als Nutzer möchte ich API-Provider wie OpenAI, OpenRouter und Swisscom über **API-Base, API-Pfad, Auth-Env-Variable und Modelle** pflegen können, ohne API-Key-Werte in der UI offenzulegen.
- Als Nutzer möchte ich speichern können und sofort sehen, ob die Änderung gültig ist und im Neue-Session-Dialog greift.

## Acceptance Criteria

### Block A — Einstellungsbereich „Modelle"
- [ ] Der globale Einstellungsdialog enthält einen neuen Tab **„Modelle"**.
- [ ] Der Tab listet mindestens die Provider **Claude**, **OpenAI**, **OpenRouter** und **Swisscom**.
- [ ] Pro Provider werden angezeigt: Anzeigename, Provider-Key, Typ/Treiber, Verfügbarkeit, Default-Modell, Modellliste und relevante Capabilities.
- [ ] Nicht verfügbare Provider zeigen einen deutschen Grund, z. B. fehlende Umgebungsvariable oder fehlendes CLI-Binary.
- [ ] Der Bereich lädt die aktuelle Server-Konfiguration; bei Ladefehler erscheint eine deutsche Fehlermeldung, kein leerer/kaputter Dialog.

### Block B — Modelle und Defaults bearbeiten
- [ ] Pro Provider kann der Nutzer die **Modellliste** bearbeiten: Modelle hinzufügen, entfernen und umbenennen.
- [ ] Pro Provider kann genau ein **Default-Modell** aus der Modellliste gewählt werden.
- [ ] Das Default-Modell muss Bestandteil der Modellliste sein; andernfalls wird Speichern serverseitig abgewiesen.
- [ ] Für Claude bleiben die bekannten Modell-Aliase **Haiku · Sonnet · Opus** erhalten; der Nutzer kann den Default ändern, ohne den eingebauten Claude-Pfad zu beschädigen.
- [ ] Neue Sessions verwenden nach dem Speichern das neue Default-Modell; bereits laufende Sessions bleiben unverändert.

### Block C — Provider-Konfiguration
- [ ] OpenAI, OpenRouter und Swisscom können als OpenAI-kompatible HTTP-Provider verwaltet werden: `api_base`, `api_path`, `auth_env`, `context_window`, `capabilities`.
- [ ] Swisscom ist als eigener Provider sichtbar und standardmäßig als OpenAI-kompatibler Provider modellierbar; falls noch keine echte Runtime-Konfiguration vorhanden ist, erscheint der Provider als „nicht verfügbar" mit Setup-Hinweis.
- [ ] `auth_env` speichert nur den **Namen** der Server-Umgebungsvariable, nie den API-Key-Wert.
- [ ] Die UI zeigt nur, ob die referenzierte Umgebungsvariable serverseitig gesetzt ist; der Wert selbst wird nie angezeigt.
- [ ] Provider können aktiviert/deaktiviert werden. Deaktivierte Provider erscheinen nicht als auswählbare Engine im Neue-Session-Dialog, bleiben aber in den Einstellungen bearbeitbar.

### Block D — Speichern, Validierung und Live-Wirkung
- [ ] Änderungen werden persistiert und überleben Backend-Neustarts.
- [ ] Die App speichert Provider-, Modell- und Default-Auswahlen in der bestehenden `engines.yaml` bzw. in einem klar dokumentierten YAML-Override für eingebaute Profile wie Claude; keine separate DB wird zur Quelle der Wahrheit.
- [ ] Nach erfolgreichem Speichern wirkt die Änderung live auf `GET /engines` und den Neue-Session-Dialog, ohne manuelles YAML-Editieren.
- [ ] Fehlerhafte Eingaben werden serverseitig validiert und mit deutschen Meldungen abgewiesen, z. B. leerer Provider-Key, ungültige URL, leere Modellliste bei aktivem Provider, Default nicht in Modellliste.
- [ ] Ein einzelnes fehlerhaftes Provider-Profil darf Claude nicht unbrauchbar machen; Claude bleibt als Fallback verfügbar.
- [ ] Die UI bietet eine sichere Rückkehr zum letzten gültigen Stand, wenn Speichern fehlschlägt.

### Block E — Nachvollziehbarkeit und YAML-Kompatibilität
- [ ] Die vorhandene Datei-basierte Registry bleibt kompatibel: bestehende `engines.yaml`-Einträge werden korrekt gelesen.
- [ ] Von der UI gespeicherte Konfiguration ist weiterhin als YAML lesbar und git-diffbar.
- [ ] Kommentare müssen nicht erhalten bleiben, aber die gespeicherte Struktur bleibt stabil und menschenlesbar.
- [ ] Es gibt keine Secret-Leaks in API-Antworten, Frontend-State, Logs oder Fehlermeldungen.

## Edge Cases
- **`engines.yaml` fehlt** → Einstellungen zeigen Claude als eingebauten Fallback und bieten an, eine verwaltete Konfiguration anzulegen.
- **`engines.yaml` ist syntaktisch kaputt** → UI zeigt den Parse-Fehler und blockiert Speichern nicht blind über die defekte Datei; Claude bleibt verfügbar.
- **Swisscom-Key fehlt** → Swisscom bleibt sichtbar, aber „nicht verfügbar"; Neue Sessions können Swisscom nicht wählen.
- **Modell wird entfernt, während es Default ist** → Speichern nur möglich, wenn vorher ein neuer Default gewählt wird.
- **Laufende Session nutzt altes Modell** → keine Migration; die Session zeigt weiterhin ihr Startmodell.
- **Provider ohne Usage-Capability** → Token-/Kostenanzeigen degradieren wie bisher zu „n/v"; Einstellungen dürfen keine falsche Usage-Capability erzwingen.
- **Mehrere Nutzer/Tabs speichern parallel** → letzter gültiger Speichervorgang gewinnt oder Konflikt wird angezeigt; keine teilweise kaputte YAML-Datei.
- **API-Key-Wert versehentlich in `auth_env` eingetragen** → Validierung warnt, wenn der Wert wie ein Secret statt wie ein Variablenname aussieht.

## Technical Requirements (optional)
- Erweiterung der Settings-API um read/write Endpunkte für die Engine-Registry, getrennt von `GET /engines` als secret-freiem Read-only-Überblick.
- Speichern sollte atomar erfolgen (temporäre Datei + Rename), damit keine halb geschriebene YAML-Datei entsteht.
- Backend validiert gegen das bestehende `EngineProfile`-Schema und erzwingt reservierte Keys wie `claude`.
- Frontend-Erweiterung in `SettingsDialog`: neuer Tab „Modelle" mit Provider-Liste, Detailformular, Modelllisten-Editor, Default-Modell-Select und Verfügbarkeits-Badges.
- Tests: API liest/schreibt YAML, validiert Fehlerfälle, leakt keine Secrets; Frontend rendert Provider, Modell-Editor, Fehler- und Ladezustände; Regression für `GET /engines` und Neue-Session-Dialog.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-06-26 · **Stack:** Next.js 16 Settings-UI + FastAPI Engine-Registry + YAML-Dateispeicher · **Branch:** dev

### Überblick / Kernaussage
PROJ-51 macht die bestehende Engine-Registry bedienbar, ohne ihr Grundprinzip zu ändern: **`engines.yaml` bleibt die offene, git-diffbare Quelle**, `GET /engines` bleibt der **secret-freie Read-only-Überblick** für Launcher und Sidebar, und ein neuer Settings-Pfad übernimmt das **validierte Bearbeiten und atomare Speichern derselben YAML-Datei**. Es gibt keine neue Datenbank und keine Secret-Speicherung in Jupiter.

Der wichtigste Architektur-Schnitt ist bewusst: **Launcher-Read und Admin-Write sind getrennt.** Der Launcher braucht nur sichere Anzeige-Daten; die Einstellungen brauchen zusätzliche Felder wie `api_base`, `api_path`, `auth_env`, `context_window`, Capabilities und Aktiv-Status.

### A) Komponenten-Struktur
```
SettingsDialog
├── Tab Allgemein
├── Tab Trust-Policy
├── Tab Watchdog
├── Tab Liveness
├── Tab Sprache
├── Tab Registry
└── Tab Modelle
    └── EngineModelsControl
        ├── ProviderList
        │   ├── Claude Max
        │   ├── OpenAI
        │   ├── OpenRouter
        │   └── Swisscom
        ├── ProviderDetailForm
        │   ├── Anzeigename / Key / Treiber
        │   ├── Aktiv-Schalter
        │   ├── Verfügbarkeits-Badge
        │   ├── API-Konfiguration (bei openai-kompatiblen Providern)
        │   ├── Modelllisten-Editor
        │   ├── Default-Modell-Select
        │   └── Capability-Auswahl
        └── Actions
            ├── Speichern
            ├── Änderungen verwerfen
            └── Letzten gültigen Stand neu laden
```

Die UI bleibt arbeitsorientiert und kompakt: links Provider-Liste, rechts Detailformular. Claude ist sichtbar, aber eingeschränkt editierbar; API-Provider sind vollständig über Formularfelder pflegbar.

### B) Datenmodell (Klartext)
**Kein neues DB-Modell.** Gespeichert wird weiterhin eine YAML-Datei am bestehenden Registry-Pfad.

Ein verwalteter Provider hat:
- **Identität:** `key`, Anzeigename, `kind=engine`, Treiber.
- **Aktiv-Status:** ob der Provider im Launcher auswählbar ist.
- **Modelle:** Liste erlaubter Modell-Slugs plus genau ein Default-Modell.
- **Runtime-Daten:** Kontextfenster und Capabilities wie `usage`, `multi_turn`, `abc`.
- **API-Daten für OpenAI-kompatible Provider:** `api_base`, `api_path`, `auth_env`.
- **Nur bei CLI-Providern:** bestehende CLI-Felder bleiben kompatibel, werden in PROJ-51 aber nicht zum primären Editor für neue Anbieter.

Claude bleibt ein eingebautes Profil. Damit der Nutzer den Claude-Default über die UI ändern kann, braucht die Settings-Sicht ein kleines **Override-Konzept**: Die eingebaute Claude-Engine bleibt nicht überschreibbar als YAML-Key `claude`, aber ihr Default-Modell wird als globaler Claude-Default bzw. expliziter Override behandelt. So bleibt der reservierte Key geschützt.

### C) API-Shape (Endpunkte, keine Implementierung)
```
GET  /settings/engines
  → vollständige, bearbeitbare Engine-Konfiguration:
    Provider, editierbare Felder, Verfügbarkeit, Quelle, Warnungen,
    aber keine Secret-Werte.

PUT  /settings/engines
  → ersetzt die verwaltete Engine-Konfiguration validiert und atomar.
    Antwort ist der neu geladene, gültige Stand.

POST /settings/engines/validate
  → Trockenlauf: prüft eine Konfiguration und liefert Fehler/Warnungen,
    ohne zu speichern.
```

`GET /engines` bleibt unverändert und wird nicht mit Admin-Feldern aufgeblasen. Es bleibt die stabile, secret-freie Quelle für Neue-Session-Dialog, Micro-Apps, Orchestration und Sidebar.

### D) Validierungs- und Speicherverhalten
- Speichern ist **ganz oder gar nicht**: Wenn ein Provider ungültig ist, bleibt die alte YAML aktiv.
- Die Datei wird atomar geschrieben, damit kein Backend-Neustart oder Prozessabbruch eine halbe YAML-Datei hinterlässt.
- Vor dem Schreiben wird gegen dasselbe Profilmodell validiert, das auch die Runtime nutzt.
- `default_model` muss in `models` enthalten sein.
- `auth_env` muss wie ein Variablenname aussehen und darf nicht wie ein API-Key wirken.
- `api_base` muss eine gültige `https://`-URL sein; `api_path` muss ein Pfad sein.
- Deaktivierte Provider bleiben in der Settings-Ansicht, werden aber für den Launcher ausgeblendet oder als nicht wählbar markiert.
- Ein kaputter Eintrag darf Claude nicht beschädigen; Claude bleibt die Fallback-Engine.

### E) Swisscom-Entscheidung
Swisscom wird als **OpenAI-kompatibler HTTP-Provider** modelliert. Das nutzt den vorhandenen `openai`-Treiber und hält die Integration parallel zu OpenRouter: anderer `api_base`, anderer `auth_env`, eigene Modellliste, kein neuer Treiber.

Default-Profil:
- Key: `swisscom`
- Label: `Swisscom`
- Driver: `openai`
- Auth-Env: z. B. `SWISSCOM_API_KEY`
- Status ohne gesetzte Env-Variable: sichtbar, aber nicht verfügbar

Falls Swisscom später ein abweichendes Protokoll braucht, wird das ein Folgefeature für einen eigenen Treiber. PROJ-51 muss dafür nur verhindern, dass die UI auf OpenAI/OpenRouter hartverdrahtet ist.

### F) Tech-Entscheidungen (Warum)
- **YAML bleibt Quelle statt DB:** Jupiter nutzt für Engine-, Policy- und Watchdog-Konfiguration bereits dateibasierte, live geladene YAML. Das ist nachvollziehbar, git-versionierbar und passt zum offenen-MD/Datei-Prinzip des Projekts.
- **Separater Settings-Endpunkt statt `GET /engines` erweitern:** Der Launcher braucht keine `auth_env`, `api_base` oder Bearbeitungsdetails. Die Trennung reduziert Secret-Leak-Risiko und hält bestehende Consumers stabil.
- **Keine API-Key-Werte in Jupiter:** Die UI verwaltet nur Umgebungsvariablen-Namen. Secrets bleiben in `.env`, Dokploy/systemd oder der Server-Umgebung. Das passt zur bestehenden PROJ-18-Sicherheitslinie.
- **Claude als Built-in plus Override:** Der reservierte `claude`-Key schützt den stabilen MVP-Pfad. Der Nutzer kann trotzdem den Default ändern, ohne die eingebaute Engine zu kapern.
- **Validieren vor Speichern:** Ein Formularfehler darf nicht dazu führen, dass der Smart Launcher keine Engines mehr laden kann. Der letzte gültige Stand bleibt aktiv.
- **Aktiv-Status explizit:** „nicht verfügbar" (Key fehlt) und „deaktiviert" (bewusste Ausblendung) sind verschiedene Zustände und müssen in der UI unterscheidbar sein.

### G) Abhängigkeiten / Pakete
- **Backend:** keine neuen Pakete. `pyyaml`, Pydantic/FastAPI und atomare Datei-Operationen sind bereits im Projektmuster vorhanden.
- **Frontend:** keine neuen Pakete. Vorhandene shadcn/ui-Komponenten reichen: Tabs, Select, Input, Button, Badge, ScrollArea, ggf. Switch/Checkbox.
- **Datenbank/MinIO:** nicht betroffen.

### H) Auswirkungen auf bestehende Features
| Feature | Auswirkung |
|---|---|
| PROJ-18 | Registry bekommt einen validierten Schreibpfad; `GET /engines` bleibt kompatibel. |
| PROJ-48 | Codex-Profil muss mit seinen CLI-/Resume-/Sandbox-Feldern unverändert erhalten bleiben; PROJ-51 bearbeitet es vorsichtig oder read-only für CLI-Spezialfelder. |
| PROJ-50 | Capability `abc` darf beim Speichern nicht verloren gehen; UI zeigt Capabilities explizit. |
| PROJ-9 | Neue Sessions verwenden sofort die gespeicherten Defaults und die aktivierten Provider. |
| PROJ-39/40 | iFrame/native/launch-Einträge bleiben in derselben YAML; der Modelle-Tab fokussiert `kind=engine` und darf Micro-App-Metadaten nicht löschen. |

### I) Bau-Reihenfolge / Handoff
1. **Backend zuerst:** Settings-Schemas, Registry-Settings-Service, Validierungs-/Speicher-Endpunkte, Swisscom-Default/Beispielprofil, Tests für Secret-Freiheit und YAML-Kompatibilität.
2. **Frontend danach:** Tab „Modelle" in `SettingsDialog`, Provider-Liste, Detailformular, Modelllisten-Editor, Speichern/Verwerfen, Lade-/Fehlerzustände.
3. **QA:** Regression `GET /engines`, Neue-Session-Dialog, bestehende OpenAI/OpenRouter/Codex-Profile, kaputte YAML, fehlende Env-Variablen, Secret-Leak-Checks.

### J) Offene Umsetzungsentscheidung für Backend
Die Architektur empfiehlt einen **verwalteten YAML-Snapshot**, der nicht versucht, alte Kommentare zu erhalten. Kommentare dürfen verloren gehen, weil die Requirements das erlauben. Wichtig ist stattdessen eine stabile, gut lesbare Sortierung:
1. Built-in/Claude-Override
2. API-Provider: OpenAI, OpenRouter, Swisscom
3. CLI-Engines wie Codex/Ollama
4. iFrame/native/launch-Einträge unverändert erhalten

## Implementation Notes (Backend — /abc-backend, 2026-06-26)

**Branch:** `dev`. Backend umgesetzt; Frontend-Tab „Modelle" ist der nächste Handoff.

### Gebaut
- `backend/app/engine/registry.py`
  - Engine-Profile haben jetzt `enabled` und eine bearbeitbare Settings-Sicht (`to_settings`) zusätzlich zur secret-freien Launcher-Sicht (`to_read`).
  - `GET /engines` filtert deaktivierte Provider aus; `manager.create` kann deaktivierte Engines nicht starten.
  - `settings_snapshot`, `validate_settings` und `save_settings` validieren eine bearbeitbare Engine-Konfiguration und speichern sie atomar in `engines.yaml`.
  - Claude bleibt Built-in; sein Default-Modell wird über einen YAML-Block `claude.default_model` persistiert, ohne den reservierten Key `claude` als normalen Engine-Eintrag zu kapern.
  - Swisscom ist als deaktivierter OpenAI-kompatibler Default-Provider sichtbar (`auth_env=SWISSCOM_API_KEY`).
  - Validierung: `default_model ∈ models`, aktive Engines brauchen mindestens ein Modell, `auth_env` ist nur Variablenname (kein API-Key-Wert), OpenAI-kompatible Provider brauchen `https://api_base` und einen `/api_path`.
- `backend/app/schemas/settings.py`
  - Neue Schemas `EngineSettingsEntry`, `EngineSettingsRead`, `EngineSettingsPut`, `EngineSettingsValidationRead`.
- `backend/app/routes/settings.py`
  - Neue Endpunkte:
    - `GET /settings/engines`
    - `POST /settings/engines/validate`
    - `PUT /settings/engines`
- `backend/config/engines.example.yaml`
  - Swisscom-Beispielprofil ergänzt, standardmäßig `enabled: false`.
- `backend/tests/test_proj51_engine_settings.py`
  - Tests für Settings-Snapshot, YAML-Schreiben, Live-Wirkung auf `GET /engines`, Trockenlauf ohne Datei-Schreibzugriff, Validierungsfehler und Secret-Leak-Schutz.

### API-Vertrag für Frontend
```
GET  /settings/engines
  -> {engines, source, warning}

POST /settings/engines/validate
  Body: {engines}
  -> {valid, warnings, engines}

PUT  /settings/engines
  Body: {engines}
  -> {engines, source, warning}
```

Die Settings-Sicht enthält `auth_env`, `api_base`, `api_path`, `context_window`, `enabled`, `models`, `default_model`, `capabilities` und bei CLI-Profilen die bestehenden CLI-Felder. API-Key-Werte werden nie gelesen oder zurückgegeben.

### Tests
- Gezielt grün: `python -m pytest backend/tests/test_proj51_engine_settings.py backend/tests/test_proj18_engines.py` → **33 passed**.
- Volle Backend-Suite grün: `python -m pytest backend/tests` → **907 passed, 1 warning**.
- Hinweis: `conda run -n Dashboard ...` war in dieser Shell nicht verfügbar (`conda: command not found`); `python` zeigte aber auf `/home/dev/miniconda3/envs/Dashboard/bin/python`.

## Implementation Notes (Frontend — /abc-frontend, 2026-06-26)

**Branch:** `dev`. Frontend umgesetzt im bestehenden Next.js/shadcn-Stack (kein Flutter-App-Code vorhanden).

### Gebaut
- `nextjs_app/components/cockpit/engine-models-control.tsx`
  - Neuer Einstellungen-Control für den Tab **„Modelle"**.
  - Providerliste mit Status-Badges: verfügbar, nicht verfügbar, deaktiviert.
  - Detailformular für Anzeigename, Aktiv-Schalter, API-Base, API-Pfad, Auth-Env, Kontextfenster, Modelle, Default-Modell und Capabilities.
  - Modelllisten-Editor mit Hinzufügen/Umbenennen/Entfernen.
  - CLI-Profile wie Codex bleiben erhalten; Spezialfelder werden aktuell read-only angezeigt, damit Resume/Sandbox/Adapter nicht versehentlich verloren gehen.
  - Aktionen: Neu laden, Verwerfen, Prüfen, Speichern.
- `nextjs_app/components/cockpit/settings-dialog.tsx`
  - Neuer Tab **„Modelle"** im globalen Einstellungsdialog.
- `nextjs_app/lib/types.ts`
  - Neue Typen `EngineSettingsEntry`, `EngineSettingsOverview`, `EngineSettingsValidation`.
- `nextjs_app/lib/api.ts`
  - Neue Funktionen `getEngineSettings`, `validateEngineSettings`, `setEngineSettings`.

### UX-Entscheidungen
- Die UI sendet die vollständige Engine-Liste an `PUT /settings/engines`; das Backend validiert und schreibt atomar in `engines.yaml`.
- API-Key-Werte werden nicht abgefragt. Das Feld **Auth-Env-Variable** speichert nur den Namen der Server-Umgebungsvariable.
- Claude ist sichtbar und sein Default-Modell editierbar; Built-in-Felder wie Key/Treiber bleiben gesperrt.
- Deaktivierte Provider bleiben in der Modelle-Ansicht bearbeitbar, erscheinen aber nicht im Neue-Session-Dialog.
- **BUG-51-1 Fix:** Der Modelle-Tab zeigt nur noch Session-Engines (`kind=engine`). Micro-Apps, iFrames und Startknöpfe bleiben im Payload unverändert erhalten, sind aber in diesem Tab nicht mehr sichtbar/bearbeitbar.

### Tests
- `npm run lint` → grün.
- `npm run build` → grün.
- `npm test` → **19 files / 169 tests passed**.
- Nach BUG-51-1-Fix erneut grün: `npm run lint`, `npm run build`, `npm test` → **19 files / 169 tests passed**.
- `npx tsc --noEmit` bleibt durch einen vorbestehenden, unabhängigen Typfehler in `nextjs_app/lib/md-tree.test.ts:118` rot.

## QA Test Results (QA Engineer, 2026-06-26)

**Branch:** `dev` · **Scope:** Backend-Endpunkte `/settings/engines`, YAML-Registry-Speicherung, `GET /engines`-Regression, Next.js-Einstellungen-Tab „Modelle". Flutter ist in diesem Projekt nicht vorhanden; QA erfolgte gegen den bestehenden Next.js-Stack.

### Automatisierte Tests
- Backend gezielt: `python -m pytest backend/tests/test_proj51_engine_settings.py backend/tests/test_proj18_engines.py` → **33 passed**.
- Backend voll: `python -m pytest backend/tests` → **907 passed, 1 warning**.
- Frontend: `npm run lint` → grün.
- Frontend Build: `npm run build` → grün.
- Frontend Tests: `npm test` → **19 files / 169 tests passed**.
- `npx tsc --noEmit` → weiterhin rot durch vorbestehenden, unabhängigen Fehler in `nextjs_app/lib/md-tree.test.ts:118`.

### Akzeptanzkriterien
| Block | Ergebnis | Nachweis |
|---|---|---|
| A — Einstellungsbereich „Modelle" | 🟡 Teilweise | Tab existiert und lädt `/settings/engines`; Provider und Status-Badges werden angezeigt. BUG-51-1: Nicht-Engine-Einträge werden ebenfalls im Modelle-Tab angezeigt. |
| B — Modelle und Defaults bearbeiten | ✅ Pass | Modellliste, Default-Auswahl, Hinzufügen/Umbenennen/Entfernen im UI; Backend validiert `default_model ∈ models`. |
| C — Provider-Konfiguration | ✅ Pass | OpenAI-kompatible Felder `api_base`, `api_path`, `auth_env`, `context_window`, `capabilities`; Swisscom sichtbar/deaktiviert; keine API-Key-Werte. |
| D — Speichern, Validierung, Live-Wirkung | ✅ Pass | `PUT /settings/engines` schreibt atomar YAML; `GET /engines` reflektiert Änderungen und filtert deaktivierte Provider; Fehler bleiben 400 ohne Dateischreibzugriff. |
| E — YAML-Kompatibilität / Secret-Schutz | ✅ Pass | YAML bleibt Quelle; Kommentare werden nicht garantiert; `GET /engines` bleibt secret-frei; Settings-Sicht enthält nur `auth_env`-Namen. |

### Bugs
**BUG-51-1 — Medium — Modelle-Tab zeigt und bearbeitet auch Nicht-Engine-Einträge**
- **Befund:** `EngineModelsControl` rendert alle Einträge aus `/settings/engines`, inklusive `kind=native`, `kind=iframe` und `kind=launch` (z. B. Video Summary, VPS-Admin, Excalidraw), obwohl PROJ-51 fachlich die Modell-/Providerverwaltung für Session-Engines ist.
- **Risiko:** Der Schalter „Im Neue-Session-Dialog auswählbar" ist für Micro-Apps/iFrames/Launch-Einträge falsch benannt. Wenn ein Nutzer dort z. B. eine native Micro-App deaktiviert und speichert, filtert das Backend den Eintrag aus `GET /engines`; dadurch können Sidebar-/Micro-App-Einträge verschwinden. Das verletzt die Architektur-Notiz „Modelle-Tab fokussiert `kind=engine` und darf Micro-App-Metadaten nicht löschen/verändern".
- **Reproduktion:** `GET /settings/engines` enthält alle Registry-Kinds; der Frontend-Code mappt `engines.map(...)` ohne Filter auf die Providerliste und bietet `enabled` für den selektierten Eintrag an.
- **Erwartung:** Der Tab „Modelle" zeigt/bearbeitet nur `kind=engine`. Nicht-Engine-Einträge müssen im Payload unverändert erhalten bleiben, dürfen aber nicht in diesem Tab editierbar sein.
- **Empfohlener Fix:** Frontend: Liste/Detail auf `kind === "engine"` filtern, beim Speichern aber die unveränderten Nicht-Engine-Einträge im Payload mitschicken. Optional Backend: `enabled` für Nicht-Engine-Einträge weiterhin unterstützen, aber PROJ-51-UI nicht dafür verwenden.

### Security / Red-Team
- **Secret-Leaks:** Keine API-Key-Werte in Backend-Tests, API-Responses oder Frontend-Typen. `auth_env` wird als Variablenname validiert; offensichtliche Secret-Werte werden abgewiesen. ✅
- **YAML-Schreibsicherheit:** Speichern erfolgt atomar; Validierungsfehler schreiben keine Datei. ✅
- **Registry-Fallback:** Defekte/fehlende YAML degradiert weiter auf Claude; `GET /engines` bleibt secret-frei. ✅
- **Auth:** Settings-Router hängt am bestehenden Auth-Gate; keine neue öffentliche Route. ✅

## QA Re-Test Results (QA Engineer, 2026-06-27)

**Branch:** `dev` · **Scope:** Re-Test nach BUG-51-1-Fix, Backend-Registry-Speicherung, Settings-API, Next.js-Modelle-Tab, Regression für bestehende Engine-/Micro-App-Registry-Einträge. Flutter ist in diesem Projekt nicht vorhanden; QA erfolgte gegen den bestehenden FastAPI + Next.js-Stack.

### Automatisierte Tests
- Backend gezielt: `python -m pytest backend/tests/test_proj51_engine_settings.py backend/tests/test_proj18_engines.py` → **34 passed**.
- Backend voll: `python -m pytest backend/tests` → **907 passed, 1 warning**.
- Frontend Lint: `npm run lint` → grün.
- Frontend Tests: `npm test` → **19 files / 169 tests passed**.
- Frontend Build: `npm run build` → grün, inklusive Next-TypeScript-Schritt.
- Standalone TypeScript: `npx tsc --noEmit` → weiterhin rot durch bekannten, unabhängigen Fehler in `nextjs_app/lib/md-tree.test.ts:118`.

### Zusätzliche Regression
- Ergänzt: `backend/tests/test_proj51_engine_settings.py::test_put_settings_engines_preserves_non_engine_entries`.
- Nachweis: Ein vollständiger Settings-Save erhält `kind=native`, `kind=iframe` und `kind=launch` inklusive `group`, `icon`, `url`, `sandbox` und `target`. Damit ist der BUG-51-1-Risikopfad dauerhaft abgedeckt.

### Akzeptanzkriterien
| Block | Ergebnis | Nachweis |
|---|---|---|
| A — Einstellungsbereich „Modelle" | ✅ Pass | Tab „Modelle" existiert; UI filtert die sichtbare Providerliste auf `kind=engine`; Ladefehler zeigen deutsche Meldung. |
| B — Modelle und Defaults bearbeiten | ✅ Pass | Modellliste, Default-Auswahl, Hinzufügen/Umbenennen/Entfernen; Backend validiert `default_model ∈ models`. |
| C — Provider-Konfiguration | ✅ Pass | OpenAI-kompatible Felder, Swisscom deaktiviert sichtbar, `auth_env` nur als Variablenname, keine Secret-Werte. |
| D — Speichern, Validierung, Live-Wirkung | ✅ Pass | Atomarer YAML-Save; `GET /engines` reflektiert Änderungen; deaktivierte Provider werden im Launcher gefiltert; Fehler schreiben keine Datei. |
| E — YAML-Kompatibilität / Secret-Schutz | ✅ Pass | YAML bleibt Quelle; gespeicherte Struktur ist lesbar; Nicht-Engine-Einträge bleiben erhalten; Settings- und Launcher-Sichten bleiben secret-frei. |

### Bugs
- Keine offenen PROJ-51-Bugs im Re-Test.
- BUG-51-1 ist verifiziert behoben und durch Regressionstest abgesichert.

### Security / Red-Team
- **Secret-Leaks:** Keine API-Key-Werte in API-Antworten, Frontend-Typen oder Tests; `auth_env`-Secret-Muster werden serverseitig abgewiesen. ✅
- **YAML-Schreibsicherheit:** Validierung vor Speichern, atomarer Rename, keine Teil-Datei bei Fehlern. ✅
- **Fallback:** Fehlende/kaputte Registry degradiert auf Claude; ein fehlerhafter Eintrag macht Claude nicht unbrauchbar. ✅
- **Registry-Isolation:** Der Modelle-Tab bearbeitet nur Session-Engines; Micro-Apps/iFrames/Launch-Einträge werden nicht sichtbar editiert und bleiben beim Save erhalten. ✅

### Produktionsentscheidung
**READY / Approved.** Keine Critical- oder High-Bugs offen. Ein bekannter, unabhängiger TypeScript-Testtypfehler in `md-tree.test.ts` bleibt außerhalb des PROJ-51-Scopes bestehen.
- **DB/RLS/MinIO:** nicht betroffen.

### Production-Ready
**READY / Approved.** BUG-51-1 ist verifiziert behoben; keine Critical- oder High-Bugs offen.

## Deployment
- **Production URL:** https://jupiter.auxevo.tech
- **Deployed:** 2026-06-27 · **Version:** 0.23.0 · **Tag:** v0.23.0-PROJ-51
- **Host project:** Jupiter / Dokploy
- **Shipped:** Einstellungen-Tab „Modelle" mit validierter Engine-/Modellverwaltung, atomarem YAML-Speichern, Swisscom-Profil und Secret-freien Settings-Endpunkten.
- **Smoke-Test nach Deploy:** `/api/health`, Login, Einstellungen → Modelle laden/speichern, Neue-Session-Dialog Default-Modell prüfen, Host-Logs kontrollieren.
