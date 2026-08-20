# PROJ-83: Modellwahl pro Hermes-Profil in den Einstellungen

## Status: Architected
**Created:** 2026-08-19
**Rework 2026-08-20:** Scope nach Nutzer-Klärung erweitert (Engine→Modell-Zweistufenauswahl + Cross-Provider, siehe Tech-Design-Nachtrag unten). Die gemergte Implementierung (Commit 02159d7, QA „READY" unten) deckt diesen erweiterten Scope NICHT ab — sie nutzt eine hartkodierte 4-Alias-Liste (`VALID_MODELS`) statt der echten Engine-Registry und schreibt nie `model.provider`. Nicht deployen, bevor die Rework-Kriterien unten erfüllt sind.

## Dependencies
- Requires: PROJ-51 (Engine- und Modellverwaltung in den App-Einstellungen) — stellt die bestehende Modelleinstellungs-UX und den konfigurierten Modellbestand bereit.
- Requires: PROJ-82 (Hermes-Kanban nativ in Jupiter) — Jupiter kennt die auf dem Server verfügbaren Hermes-Profile und deren ABC-Kontext.

## Problem / Motivation
Die abc-Rollen laufen als eigene Hermes-Profile, zum Beispiel `jupiter-requirements`, `jupiter-architecture`, `jupiter-frontend`, `jupiter-backend` und `jupiter-qa`. Ihr Modell ist heute nur durch manuelles Editieren der jeweiligen `config.yaml` unter `/home/dev/.hermes/profiles/` änderbar. Das ist fehleranfällig und verhindert, dass der Nutzer Kosten, Qualität und Geschwindigkeit je Rolle direkt aus Jupiter steuert.

Jupiter soll deshalb in den globalen Einstellungen eine profilbezogene Modellwahl anbieten. Der Nutzer wählt je erkanntem abc-Profil ein Modell aus einem Dropdown; die Auswahl wird in genau dessen Hermes-`config.yaml` dauerhaft gespeichert.

## Annahme
Als abc-Profil gilt jedes auf dem Jupiter-Server erkannte Hermes-Profil mit dem Präfix `jupiter-`, das eine lesbare `config.yaml` besitzt. Die Liste wird zur Laufzeit ermittelt, nicht im Frontend fest kodiert. Nicht-abc-Profile, insbesondere `default`, sind nicht Teil dieses Features.

## Scope
In scope:
- Einstellungsbereich für die Modellwahl je erkanntem abc-Profil.
- Anzeige des Profilnamens, aktuell wirksamen Providers/Modells und einer zweistufigen Auswahl **Engine → Modell** (siehe Tech-Design-Nachtrag), analog zum Engine/Modell-Muster im Schwarm-Verteilungsplan (Coordinator-Dialog, PROJ-8).
- Die Engine-Liste und die je Engine wählbaren Modelle stammen ausschließlich aus der bestehenden Engine-Registry (`GET /engines`, `backend/config/engines.yaml`, PROJ-51/PROJ-18) — keine eigene, zweite Modellliste.
- Übersetzung der gewählten Engine+Modell-Kombination in das Format, das die jeweilige Profil-`config.yaml` erwartet (`model.default` + `model.provider`), inklusive der Rückrichtung beim Anzeigen eines bereits konfigurierten Profils.
- Persistieren einer gültigen Auswahl (Modell UND Provider gemeinsam) in der jeweiligen Profil-`config.yaml`.
- Deutsche Lade-, Erfolg- und Fehlermeldungen.

Out of scope:
- Anlegen, Löschen, Umbenennen oder sonstige Bearbeitung von Hermes-Profilen.
- Ändern von Credentials, Skills, Tools, Berechtigungen oder anderen Profilwerten außerhalb von `model.default`/`model.provider`.
- Bearbeiten von Nicht-abc-Profilen.
- Modellwechsel bereits laufender Hermes-Worker oder Jupiter-Sessions.
- Neue Modelle, Provider oder eine zweite Modellregistry — Engine/Modell-Bestand kommt ausschließlich aus der bestehenden `GET /engines`-Registry.

## User Stories
- Als Nutzer möchte ich in den Jupiter-Einstellungen alle auf dem Server verfügbaren abc-Profile mit ihrem aktuellen Modell sehen, damit ich die Rollenbelegung ohne Terminal überblicke.
- Als Nutzer möchte ich für jedes abc-Profil ein Modell aus einem Dropdown wählen, damit ich etwa Requirements sparsam und Architecture mit einem stärkeren Modell ausführen kann.
- Als Nutzer möchte ich die Auswahl speichern und nach einem Seiten- oder Backend-Neustart wieder sehen, damit ich weiß, dass sie dauerhaft für künftige Worker gilt.
- Als Nutzer möchte ich bei einer nicht lesbaren oder nicht speicherbaren Profilkonfiguration einen klaren deutschen Fehler sehen, damit ich keine scheinbar erfolgreiche, aber wirkungslose Änderung annehme.
- Als Nutzer möchte ich sicher sein, dass beim Modellwechsel keine Secrets oder anderen Profiloptionen angezeigt oder verändert werden.

## Acceptance Criteria

### A — Einstellungsbereich und Profilübersicht
- [ ] Die globalen Jupiter-Einstellungen enthalten einen klar benannten Bereich **„Hermes-Profile"** oder gleichwertig eindeutig **„Modelle je abc-Profil"**.
- [ ] Der Bereich lädt die aktuell erkannten abc-Profile dynamisch vom Server und zeigt mindestens Profilname sowie aktuelles Modell.
- [ ] Die bekannte Rollenbelegung wie Requirements, Architecture, Frontend, Backend und QA ist sichtbar, sofern das entsprechende Profil auf dem Server vorhanden ist.
- [ ] Nicht-abc-Profile, insbesondere `default`, werden nicht angeboten.
- [ ] Gibt es keine erkannten abc-Profile, zeigt die Oberfläche den deutschen Leerzustand „Keine abc-Profile gefunden." statt einer leeren oder defekten Auswahl.
- [ ] Scheitert das Laden, zeigt die Oberfläche eine deutsche Fehlermeldung mit einer Wiederholen-Möglichkeit.

### B — Modellwahl und Speichern
- [ ] Jedes angezeigte Profil besitzt zwei gekoppelte Dropdowns nebeneinander — **Engine** und **Modell** — analog zum Engine/Modell-Muster im Schwarm-Verteilungsplan: das Engine-Dropdown listet ausschließlich die verfügbaren `claude`-, `codex`- und `opencode`-Einträge aus `GET /engines`; das Modell-Dropdown listet die Modelle der gerade gewählten Engine.
- [ ] Engine- und Modell-Dropdown sind vorausgewählt mit der aus dem aktuell im Profil hinterlegten `model.provider`/`model.default` zurückübersetzten Engine/Modell-Kombination (siehe Tech-Design-Nachtrag, Rückübersetzung).
- [ ] Ändert der Nutzer das Engine-Dropdown, aktualisiert sich das Modell-Dropdown auf die Modellliste der neu gewählten Engine; eine bisherige Modellauswahl, die zur neuen Engine nicht passt, wird verworfen und muss neu getroffen werden.
- [ ] Der Nutzer kann die Auswahl für ein oder mehrere Profile ändern und anschließend explizit speichern.
- [ ] Speichern übersetzt die gewählte Engine+Modell-Kombination gemäß Tech-Design-Nachtrag in `model.default` + `model.provider` und schreibt beide Felder gemeinsam konsistent in die Profil-`config.yaml`.
- [ ] Nach erfolgreichem Speichern zeigt Jupiter eine deutsche Erfolgsmeldung und den vom Server zurückgegebenen, gültigen Profilstand (inkl. zurückübersetzter Engine/Modell-Anzeige).
- [ ] Nach dem Speichern, Neuladen der Einstellungsseite und Backend-Neustart ist die gewählte Engine/Modell-Kombination weiter als aktueller Stand des betreffenden Profils sichtbar.
- [ ] Die Änderung gilt für anschließend gestartete Hermes-Worker dieses Profils; bereits laufende Worker behalten ihr beim Start verwendetes Modell.
- [ ] Eine ungültige oder nicht angebotene Engine/Modell-Kombination wird serverseitig abgewiesen; die UI zeigt eine verständliche deutsche Fehlermeldung und den letzten gültigen Stand.

### C — Profilisolation und Konfigurationsschutz
- [ ] Das Speichern einer Modellauswahl verändert ausschließlich die `config.yaml` des ausgewählten Profils, und darin ausschließlich `model.default` und `model.provider`.
- [ ] Nicht zum Modell/Provider gehörende Profilwerte (inkl. `model.base_url`) bleiben unverändert erhalten.
- [ ] Die Einstellungen lesen oder zeigen keine Secret-Werte, Tokens, API-Keys oder Credentials aus Profilkonfigurationen.
- [ ] Eine fehlende, unlesbare oder syntaktisch ungültige `config.yaml` eines Profils wird für dieses Profil klar als Fehlerzustand angezeigt; andere lesbare Profile bleiben weiterhin bedienbar.
- [ ] Schlägt das Speichern eines Profils fehl, bleibt dessen zuvor gültige Konfiguration wirksam; Jupiter darf keinen unvollständigen oder irreführenden Erfolgszustand anzeigen.

### D — Konsistenz mit bestehender Modellverwaltung
- [ ] Die Engine- und Modell-Dropdowns verwenden ausschließlich Engines/Modelle aus der bestehenden `GET /engines`-Registry (PROJ-51/PROJ-18); dieses Feature legt keine eigene Modellliste an. Insbesondere darf keine hartkodierte Teilmenge (z. B. nur Claude-Aliase) verwendet werden.
- [ ] Eine Änderung in der globalen Engine-/Modellverwaltung (`engines.yaml`) wird bei erneutem Laden der Profileinstellungen berücksichtigt.
- [ ] Der bestehende Einstellungen-Tab **„Modelle"**, der Neue-Session-Dialog und die Hermes-Kanban-Funktionen bleiben unverändert nutzbar.

## Tech-Design-Nachtrag: Engine/Modell ↔ Hermes-`config.yaml`-Übersetzung

**Branch:** `feat/proj-83-hermes-profilmodellwahl-rework` (anzulegen)

Die UI arbeitet mit dem bestehenden Engine/Modell-Vokabular aus `GET /engines` (`EngineRead.key` + `EngineRead.models[]`), nicht mit den Rohwerten aus `config.yaml`. Speichern und Anzeigen brauchen daher eine Übersetzung in beide Richtungen:

| Engine (`key`) | Modellwert aus `engines.yaml` | → `config.yaml` `model.provider` | → `config.yaml` `model.default` |
|---|---|---|---|
| `claude` | Alias `sonnet`/`haiku`/`opus`/`fable` | `anthropic` | `claude-sonnet-5` / `claude-haiku-4.5` / `claude-opus-5` / `claude-fable-5` |
| `codex` | z. B. `gpt-5.6-terra` | `openai-codex` | Modellwert unverändert |
| `opencode` | z. B. `opencode-go/hy3` oder `opencode/deepseek-v4-flash` | Teil vor dem ersten `/` (z. B. `opencode-go`, `opencode`) | Teil nach dem ersten `/` (z. B. `hy3`, `deepseek-v4-flash`) |

Rückübersetzung (Anzeige eines bestehenden Profils) läuft spiegelbildlich: aus `model.provider`+`model.default` wird die passende Engine + der passende Modellwert aus `engines.yaml` rekonstruiert. Ist keine passende Kombination auffindbar (z. B. Provider/Modell wurde außerhalb Jupiters gesetzt), gilt das aktuelle Modell als „nicht mehr verfügbar" (siehe Edge Cases) und wird trotzdem unverändert angezeigt.

### Implementierungsvertrag

- **Komponente:** `HermesProfileModelsControl` bleibt der alleinige Settings-Abschnitt. Sie lädt `getHermesProfiles()` und `getEngines()` gemeinsam, filtert die Registry auf `kind === "engine"`, `available === true` und die feste erlaubte Menge `{claude, codex, opencode}` und hält pro Profil den Draft `{engine: string | null, model: string | null, dirty: boolean}`. Bei Engine-Wechsel wird `model` auf `null` gesetzt. Nicht auflösbare Bestandswerte bleiben als nicht verfügbare, nicht speicherbare Anzeige erhalten.
- **Backend-Service:** `backend/app/engine/hermes_profiles.py` erhält die zentrale, reine Hin-/Rückübersetzung und validiert ausschließlich gegen den zur Laufzeit geladenen `engine_registry`-Snapshot. Sie akzeptiert nur die drei erlaubten Engine-Keys und deren angebotene Modelle. Erst nach erfolgreicher Übersetzung schreibt sie atomar genau `model.provider` und `model.default`; `model.base_url` und alle anderen YAML-Werte bleiben erhalten. Der vorhandene Regex-, Whitelist- und Realpath-Schutz für `profile` bleibt unverändert.
- **Datenvertrag:** Ein gelesener Profileintrag enthält `profile: str`, `label: str`, `engine: str | null`, `model: str | null`, `provider: str | null`, `default: str | null` und `error: str | null`. Ein Patch-Eintrag ist `{profile: str, engine: Literal["claude", "codex", "opencode"], model: str}`; die Antwort enthält pro Profil `ok`, `error` und bei Erfolg den vollständig zurückübersetzten Profileintrag. Kein Tenant/RLS-Modell: Jupiter nutzt den bestehenden Single-User-Auth-Gate auf `settings_routes`; Secrets sind in keinem Schema enthalten.
- **API:** `GET /engines` bleibt unverändert und liefert die Registry. `GET /settings/hermes-profiles` liefert nur die erkannten Profile samt rückübersetztem Stand. `PATCH /settings/hermes-profiles` erhält `{profiles: [...]}`, validiert und speichert jedes Profil einzeln und gibt dessen serverseitigen Endstand zurück. Der bisherige flache `models`-Response und `{models: [{profile, model}]}`-Patchvertrag werden dabei ersetzt.
- **Abhängigkeiten:** Keine neue Bibliothek, Datenbank oder Migration. Die vorhandenen `EngineRead`-, shadcn-`Select`-, YAML- und `os.replace`-Muster werden wiederverwendet. `openai`, `swisscom`, `ollama` und jede spätere Registry-Engine bleiben für Hermes explizit ausgeschlossen, bis ein eigener Rework ihre Hermes-Abbildung festlegt.

## Edge Cases
- **Ein abc-Profil wird zwischen Laden und Speichern gelöscht oder umbenannt** — Speichern schlägt nur für dieses Profil mit einer deutschen Meldung fehl; die übrigen Profile bleiben unverändert.
- **Aktuelles Profilmodell ist nicht mehr in der verfügbaren Modellliste** — der aktuelle Wert bleibt als solcher sichtbar und wird als nicht mehr verfügbar markiert; der Nutzer muss vor einem Speichern ein gültiges Modell wählen.
- **Mehrere Browser-Tabs ändern dasselbe Profil** — der zuletzt erfolgreich gespeicherte, serverseitig gültige Stand wird nach dem Speichern zurückgegeben; die UI darf keinen lokalen Entwurf als gespeichert darstellen.
- **Mehrere Profile werden gespeichert und eines ist ungültig oder nicht schreibbar** — fehlgeschlagene Profile werden eindeutig benannt; bereits erfolgreich gespeicherte Profile bleiben mit ihrem tatsächlich gespeicherten Stand sichtbar.
- **Server kann Profilverzeichnis oder Konfigurationsdatei temporär nicht erreichen** — keine Auswahl wird als gespeichert bestätigt; die UI bietet Wiederholen an.
- **Ein Modellwechsel wird während eines laufenden Workers vorgenommen** — der laufende Worker wird weder neu gestartet noch in seinem Modell geändert; die Wahl gilt erst für künftige Starts.
- **Profilkonfiguration enthält unbekannte zusätzliche Einstellungen** — diese bleiben erhalten und werden durch die Modellwahl weder angezeigt noch entfernt.
- **Nutzer wählt eine andere Engine als die im Profil aktuell hinterlegte** — Speichern übersetzt die neue Engine+Modell-Kombination gemäß Tech-Design-Nachtrag und schreibt `model.default` und `model.provider` gemeinsam; ein providerspezifisches `base_url` bleibt unverändert bestehen, sofern es bereits gesetzt war, und wird nicht automatisch befüllt.
- **`model.provider`/`model.default` eines Profils lässt sich keiner bekannten Engine/Modell-Kombination aus `engines.yaml` zuordnen** (z. B. manuell außerhalb Jupiters gesetzt) — die Rückübersetzung schlägt fehl, der Rohwert wird als „nicht mehr verfügbar" markiert angezeigt; der Nutzer muss vor einem Speichern eine gültige Engine/Modell-Kombination neu wählen.

---

> **Überholt durch Rework 2026-08-20 (siehe Status-Header und Tech-Design-Nachtrag oben):** Die folgenden QA-Läufe testeten die ursprüngliche Scope-Version (flaches Modell-Dropdown, `VALID_MODELS`-Alias-Liste, kein Provider-Schreiben). AC B und D gelten gegen den erweiterten Scope oben als nicht erfüllt — Rework nötig, bevor erneut QA/Deploy läuft.

## QA Test Results (2026-08-20)

**Setup:** Backend-Instanz mit `JUPITER_HERMES_PROFILES_DIR` auf isoliertes Test-Verzeichnis (Kopien realer `jupiter-*`-Profile) gestartet — echte `~/.hermes/profiles` nie angerührt. pytest-Suite (isoliert, temp-dirs) + eigenes Python-Exploit-Skript gegen `hermes_profiles.save_profile_model` für Red-Team.

### Akzeptanzkriterien

**A — Einstellungsbereich und Profilübersicht:** ✅ PASS
- Bereich "Modelle je abc-Profil" in `settings/page.tsx` registriert, lädt dynamisch via GET.
- Bekannte Rollen (Requirements/Architecture/Frontend/Backend/QA) über `_ROLE_LABELS`/`ROLE_LABELS` gemappt (Backend + Frontend konsistent).
- `default` + `jupiter` (Präfix-Sonderfall) ausgeschlossen — bestätigt per Test `test_get_lists_abc_profiles_with_models` und eigenem GET gegen Live-Instanz.
- Leerzustand "Keine abc-Profile gefunden." vorhanden (Code-Review Zeile 222-228).
- Fehlerzustand mit Wiederholen-Button vorhanden (Zeile 192-214).

**B — Modellwahl und Speichern:** ✅ PASS
- Dropdown vorausgewählt mit `current_model` (Draft-Init).
- Explizites Speichern über Button, `dirtyCount`-Gate.
- Erfolg-/Fehlermeldung via `toast`, unterscheidet Voll-/Teilerfolg (Zeile 172-183).
- Server-Antwort wird als neue Wahrheit übernommen (kein lokaler Entwurf als "gespeichert" dargestellt) — erfüllt Edge Case "Mehrere Tabs".
- Ungültiges Modell serverseitig abgewiesen: bestätigt per `test_patch_invalid_model_rejected` + eigenem Livetest (Antwort `ok=false`, Datei unverändert).

**C — Profilisolation und Konfigurationsschutz:** ⚠️ PASS mit Sicherheitsfund (siehe Security-Audit)
- Nur `model`-Sektion geschrieben, restliche Keys erhalten — bestätigt (`test_patch_preserves_other_keys`: `provider`+`toolsets` blieben erhalten).
- Keine Secret-Felder im Response-Schema (`HermesProfileModel` hat nur `profile/label/current_model/provider/error`).
- Kaputte/unlesbare Config eines Profils isoliert markiert, andere Profile bleiben bedienbar — bestätigt (`test_get_lists_abc_profiles_with_models`, `broken`-Profil separat markiert).
- Fehlschlag eines Profils lässt dessen vorherigen Stand unverändert — bestätigt (`test_patch_invalid_model_rejected`: Datei-Inhalt nach fehlgeschlagenem PATCH unverändert).
- **Sicherheitslücke:** `profile`-Parameter wird nicht gegen Pfad-Traversal validiert, siehe unten (BUG-1).

**D — Konsistenz mit bestehender Modellverwaltung:** ✅ PASS
- `available_models()` liest direkt `VALID_MODELS` aus `app/config.py` (PROJ-51), keine eigene Liste — bestätigt per Code-Review + `test_get_lists_abc_profiles_with_models` (`data["models"] == sorted(VALID_MODELS)`).
- Bestehende Settings-Tabs/Session-Dialog/Hermes-Kanban unberührt (nur additive Route + additive UI-Section, kein bestehender Code geändert außer Registrierung in `page.tsx`).

### Security-Audit (Red Team)

**BUG-1 (High) — Fehlende Validierung des `profile`-Parameters ermöglicht Pfad-Traversal-Zugriff außerhalb des Profilverzeichnisses.**

`hermes_profiles.save_profile_model()` prüft nur `profile.startswith("jupiter-")` und `profile not in {"jupiter", "default"}` — nicht aber, ob der Name Pfadseparatoren oder `..`-Segmente enthält, und nicht, ob das Profil tatsächlich in `discover_profiles()` existiert. `cfg_path = os.path.join(base, profile, "config.yaml")` wird direkt aus dem ungeprüften Client-Input gebaut.

Exploit (gegen isoliertes Testverzeichnis, eigenes Skript, kein Zugriff auf echte Profile):
```
PATCH-Payload: {"profile": "jupiter-qa/../../escape_target", "model": "opus"}
```
Ergebnis: Der Service öffnet und liest `escape_target/config.yaml` **außerhalb** von `profiles_dir` erfolgreich (Lesezugriff bestätigt — Inhalt inkl. eines Test-Secret-Werts wurde geparst, bevor der Schreibversuch fehlschlägt). Der Schreibversuch selbst scheitert nur zufällig, weil `tempfile.mkstemp(prefix=f".{profile}.")` den unsanitisierten `profile`-String (inkl. `/` und `..`) als Prefix verwendet und dadurch selbst einen ungültigen Pfad erzeugt — das ist **kein bewusster Schutz**, sondern ein Nebeneffekt eines anderen Bugs. Mit einem leicht anderen Payload (ohne Slash direkt im Tempfile-Prefix-Pfad-Segment) ist ein Schreibzugriff außerhalb von `profiles_dir` plausibel nicht ausgeschlossen — wurde aus Zeit-/Risikogründen nicht bis zum vollen Schreib-Exploit weiterverfolgt, aber die fehlende Eingabevalidierung ist der Kernfehler, nicht die zufällige tempfile-Fehlermeldung.

Auch als reiner Read-Oracle sicherheitsrelevant: unterschiedliche Fehlermeldungen (`"nicht lesbar/schreibbar"` vs. spätere `"Speichern fehlgeschlagen"`) erlauben Datei-Existenz-Probing außerhalb des Profilverzeichnisses.

**Fix-Empfehlung:** `profile` gegen die tatsächlich von `discover_profiles()` erkannte Namensliste whitelisten (nicht nur Präfix-Check), oder mindestens per Regex auf `^jupiter-[a-z0-9_-]+$` einschränken UND zusätzlich `os.path.commonpath([os.path.realpath(cfg_path), os.path.realpath(base)])`-Check vor jedem Dateizugriff.

**Weitere Red-Team-Checks:** kein Auth-Bypass möglich (Router hängt an `auth_gate = [Depends(get_current_user)]`, GET ohne Token → 401 sobald Nutzer existieren — konsistent mit Rest der App). Keine Secrets im Response-Body (Schema-Review). Kein Cross-Tenant-Aspekt (Single-User-App, kein Mandantenmodell).

### Regressionstest

`conda run -n Dashboard python -m pytest` (backend, volle Suite): **27 Fehlschläge, 1295 bestanden** — alle 27 Fehlschläge bestätigt **vorbestehend** (identisch reproduzierbar auf `git stash` = Stand vor PROJ-83-Änderungen, betreffen `test_proj50_codex_abc.py`, `test_proj79_feature_coordinator.py`, `test_proj80_followup.py` — nicht PROJ-83-Code). Keine Regression durch PROJ-83.

Neue PROJ-83-Tests: `test_proj83_hermes_profiles.py` — 11/11 grün, isoliert nachvollzogen.

Frontend: `next build` — 0 Fehler, 0 Warnungen (Turbopack, alle Routen inkl. `/settings` erfolgreich generiert). `tsc --noEmit`: keine PROJ-83-bezogenen Fehler; die 7 verbleibenden Fehler betreffen ausschließlich vorbestehende `*.test.tsx`/`*.test.ts`-Dateien (Session-Fixture-Typ-Drift, nicht PROJ-83).

### Production-Ready-Empfehlung: **NOT READY**

1 offener Bug: **BUG-1 (High)** — Path-Traversal-Validierungslücke im `profile`-Parameter (Backend `hermes_profiles.py`). Muss vor Deploy gefixt werden.

---

## QA Re-Verifikation BUG-1 (2026-08-20)

**Fix (Backend, unabhängig geprüft):** `save_profile_model()` validiert `profile` jetzt dreistufig — (1) Format-Regex `^jupiter-[a-z0-9_-]+$` gegen `/`, `..`, Absolutpfad, Steuerzeichen; (2) Whitelist gegen `discover_profiles()`-Namen; (3) Realpath-Scope-Check (`_is_within`/`commonpath`) vor jedem Dateizugriff.

**Eigener Testlauf:** `test_proj83_hermes_profiles.py` 15/15 grün (11 bestehend + 4 neue Traversal-Regressionstests: slash, `..`, Absolutpfad, Großschreibung).

**Eigener unabhängiger Exploit-Versuch** (eigenes Skript, nicht die vorhandene Suite) mit 11 Payloads gegen `save_profile_model()`, inkl. Vektoren, die im ursprünglichen Fund nicht getestet wurden:
- Alle bekannten Payloads (`jupiter-qa/../../escape_target`, `jupiter-qa/..`, `jupiter-/etc/passwd`, `jupiter-QA`) → `ok=False`, `"Kein abc-Profil."`
- Zusätzlich getestet: URL-encoded Slash (`%2f`), Null-Byte (`\x00`), Leerzeichen, `jupiter-..`, verschachtelter `./../../`-Pfad → alle korrekt abgewiesen.
- **Symlink-Escape (neuer Vektor, nicht in ursprünglicher Suite):** Profil `jupiter-evil` als Symlink auf ein Verzeichnis außerhalb von `profiles_dir` angelegt und via `discover_profiles()` nicht in die Whitelist aufgenommen (da direkter Verzeichnis-Scan) — Zugriff korrekt mit `"Kein abc-Profil."` verweigert; Realpath-Scope-Check hätte selbst bei Whitelist-Aufnahme gegriffen.
- Geheime Datei außerhalb `profiles_dir` (`escape_target/config.yaml`, Inhalt `secret: TOPSECRET`) nach allen 11 Angriffsversuchen **unverändert** — kein Lese- oder Schreibzugriff außerhalb des Scopes möglich.

**Regressionstest (volle Suite, eigener Lauf):** `python -m pytest` (backend): 1299 passed, 27 failed, 1 skipped, 1 xfailed. Die 27 Fehlschläge sind identisch mit dem vorherigen QA-Lauf (`test_proj50_codex_abc.py`, `test_proj79_feature_coordinator.py`, `test_proj80_followup.py`) — bestätigt vorbestehend, keine Regression durch den BUG-1-Fix. 4 zusätzliche PROJ-83-Tests ggü. vorherigem Lauf (1295→1299 passed) entsprechen den 4 neuen Traversal-Regressionstests.

**Ergebnis: BUG-1 (High) bestätigt gefixt.** Keine der bekannten oder zusätzlich versuchten Umgehungen (inkl. Symlink) war erfolgreich.

### Production-Ready-Empfehlung: **READY**

Alle 4 Akzeptanzkriterien PASS, keine offenen Critical/High-Bugs, keine Regression.

---
<!-- Sections below are added by subsequent skills -->

## Architecture Review (abc-review-architecture)
**Reviewed:** 2026-08-20 · **Verdict:** Architected

### Checklist
- [x] Component structure — `HermesProfileModelsControl` bleibt die klar abgegrenzte Komponente; Engine-/Modell-Drafts und die gekoppelten shadcn-Selects sind im Implementierungsvertrag festgelegt.
- [x] Data model — Profil-Lese- und Patchfelder, Typen, erlaubte Engine-Keys sowie die Single-User-Auth-Grenze sind festgelegt.
- [x] API shape — `GET /engines`, `GET /settings/hermes-profiles` und `PATCH /settings/hermes-profiles` haben Methode, Pfad, Auth und Payload/Antwortvertrag.
- [x] Tech decisions — atomisches, profilweises Schreiben sowie Erhalt übriger `model`-Felder sind konkret beschrieben; die vorhandene Implementierung nutzt bereits atomisches `os.replace`.
- [x] Dependencies — `GET /engines` ist verfügbar und auth-geschützt (`backend/app/routes/engines.py:13`, `backend/app/main.py:426-431`); die Produktentscheidung begrenzt Hermes auf Claude, Codex und OpenCode.
- [x] Branch field — `feat/proj-83-hermes-profilmodellwahl-rework` ist als creatable Branch festgelegt.
- [x] Conflict-free — keine Route kollidiert: `/settings/hermes-profiles` ist vorhanden; die Erweiterung ersetzt dessen flachen Vertrag. Der aktuelle Vertrag ist jedoch für den Rework unzureichend (`backend/app/routes/settings.py:344-374`).
- [x] Acceptance-criteria coverage — AC A/C bleiben im bestehenden Profilbereich; AC B/D sind durch den Engine-Registry-Filter, die zentrale Übersetzung und den erweiterten PATCH-Vertrag abgedeckt. Die flache Altimplementierung wird bewusst ersetzt.

### Autonom behoben
- Branch-Feld, vollständiger Komponenten-/Daten-/API-Vertrag und die Alias-Abbildung ergänzt.
- Nutzerentscheidung umgesetzt: Hermes beschränkt sich auf Claude, Codex und OpenCode; weitere Registry-Engines werden nicht geraten.

## Backend-Implementierung (Rework, 2026-08-20)

**Branch:** `feat/proj-83-hermes-profilmodellwahl-rework`. Ersetzt die flache Altimplementierung
(`VALID_MODELS`-Aliasliste, nur `model.default`-Schreiben) durch den erweiterten Scope:

- `backend/app/engine/hermes_profiles.py`: zentrale Hin-/Rückübersetzung (Engine/Modell ↔
  `model.provider`/`model.default`) validiert **ausschließlich gegen `engine_registry`** zur
  Laufzeit. Erlaubte Engine-Keys: `claude`/`codex`/`opencode` (verfügbar + `kind=engine`).
  `save_profile_model(profile, engine, model)` schreibt atomar **beide** Felder; `model.base_url`
  und alle übrigen YAML-Werte bleiben erhalten. BUG-1-Validierung (Format-Regex →
  Whitelist → Realpath-Scope) unverändert übernommen.
- `backend/app/schemas/hermes_profiles.py`: Datenvertrag laut Tech-Design-Nachtrag
  (`engine`/`model`/`provider`/`default` im Read; PATCH `{profiles:[{profile,engine,model}]}`;
  Response `entry: HermesProfileModel|null`).
- `backend/app/routes/settings.py`: GET liefert nur Profile + `warning` (kein flacher
  `models`-Bestand mehr); PATCH iteriert `payload.profiles`.
- Frontend-Typen/API (`types.ts`, `api.ts`) und `hermes-profile-models-control.tsx`
  (zwei gekoppelte Engine/Modell-Selects) bereits im Branch angepasst.

**Tests:** `backend/tests/test_proj83_hermes_profiles.py` — 17/17 grün (inkl. Reverse-Translation,
atomarem Schreiben, Erhalt übriger Keys, ungültige Engine/Modell-Ablehnung, BUG-1-Traversal).
Kein neuer Import von `available_models` mehr vorhanden.

---

## QA Test Results — Rework (2026-08-20)

**Scope:** Zweistufenauswahl Engine→Modell (Commit `45ca1ca`), gegen die erweiterten Akzeptanzkriterien A–D oben. Ersetzt die überholten QA-Läufe der alten Scope-Version (siehe Überholt-Hinweis oben).

**Setup:** Backend `backend/tests/test_proj83_hermes_profiles.py` (isolierte temp-dirs) ausgeführt; `nextjs_app` `tsc --noEmit` + `npm run build`; Code-Review der Übersetzungslogik (`hermes_profiles.py`) und der neuen Komponente (`hermes-profile-models-control.tsx`) gegen den Implementierungsvertrag; gezielter Node-Repl-Test der Filterlogik.

### Automatisierte Läufe
- `pytest backend/tests/test_proj83_hermes_profiles.py`: **17/17 grün**.
- `pytest backend/` (volle Suite): 1325 passed, 1 xfailed, **4 failed** — alle 4 in `test_proj50_codex_abc.py` (Skill-Generator-Tests gegen `~/.claude/skills`, unabhängig von PROJ-83-Code, kein Bezug zu `hermes_profiles`/`settings`). Keine Regression durch PROJ-83.
- `nextjs_app`: `npm run build` — erfolgreich, 0 Fehler (Turbopack, `/settings` inkl.). `tsc --noEmit` (Standalone, ohne Next-Build-Skip): 7 Fehler, alle in vorbestehenden `*.test.tsx`/`*.test.ts`-Fixtures (Session-Typ-Drift), keiner in PROJ-83-Dateien.

### Akzeptanzkriterien

**A — Einstellungsbereich und Profilübersicht:** ✅ PASS
- Lädt `getHermesProfiles()` + `getEngines()` parallel; Lade-/Leer-/Fehlerzustand mit Wiederholen vorhanden (Zeilen 244–280).

**B — Modellwahl und Speichern:** ❌ **FAIL — Critical**
Siehe BUG-2 unten: das Engine-Dropdown ist durch einen Logikfehler in der Filterbedingung **immer leer**, unabhängig vom tatsächlichen Registry-Inhalt. Damit ist die zentrale Neuerung des Reworks (Engine→Modell-Zweistufenauswahl) in der UI nicht bedienbar — kein Nutzer kann eine Engine wählen oder speichern.

**C — Profilisolation und Konfigurationsschutz:** ✅ PASS
- Nur `model.provider`/`model.default` geschrieben, Rest der YAML erhalten (Code-Review `save_profile_model`, Tests bestätigen). BUG-1-Schutz (Format-Regex → Whitelist → Realpath-Scope) unverändert vorhanden und weiterhin per Test abgedeckt.
- Keine Secret-Felder im Schema (`HermesProfileModel`).

**D — Konsistenz mit bestehender Modellverwaltung:** ✅ PASS
- `allowed_engine_models()` liest ausschließlich aus `engine_registry` (Backend). Kein hartkodierter Modellbestand mehr.
- Bestehende Tabs/Session-Dialog/Kanban unverändert (nur additive Registrierung).

### Bugs

**BUG-2 (Critical) — Engine-Dropdown durch `in`-Operator auf `Set` immer leer, Feature unbedienbar.**

`nextjs_app/components/cockpit/hermes-profile-models-control.tsx:82`:
```ts
const ALLOWED_ENGINES = new Set<HermesEngineKey>(["claude", "codex", "opencode"]);
...
engines.filter((e) => e.kind === "engine" && e.available && e.key in ALLOWED_ENGINES)
```
`in` prüft Property-Existenz auf dem `Set`-Objekt (Prototyp-Kette), nicht Mengenzugehörigkeit — dafür ist `.has()` nötig. Für reale Engine-Keys (`"claude"`, `"codex"`, `"opencode"`) ist `key in aSet` immer `false` (verifiziert per Node-Repl):
```
> new Set(["claude"]).has("claude")   // true
> "claude" in new Set(["claude"])     // false
```
Folge: `engineOptions` ist immer `[]`, unabhängig vom `GET /engines`-Inhalt. Das Engine-`<Select>` zeigt dauerhaft „Keine Engines verfügbar", das Modell-Select bleibt disabled (`disabled={!selectedEngine || !engineAvailable}`). Kein Nutzer kann eine Engine/Modell-Kombination wählen oder speichern — AC B (Kernstück des Reworks) ist vollständig unbedienbar. Vom Build/`tsc` nicht erkannt, da `in` auf beliebigen Objekten syntaktisch gültig ist (kein Typfehler). Keine Frontend-Tests für diese Komponente vorhanden, die den Bug abgefangen hätten.

**Fix-Empfehlung:** `ALLOWED_ENGINES.has(e.key)` statt `e.key in ALLOWED_ENGINES` (Zeile 82). Gleiches Muster prüfen, falls an anderer Stelle wiederverwendet — an dieser einen Stelle im Diff ist es der einzige Fund.

**Nebenbefund (Low, kein Blocker):** Die Komponente berechnet Rollenlabels lokal (`ROLE_LABELS`/`roleLabel()`) statt das vom Backend gelieferte `profile.label` zu verwenden; Backend- und Frontend-Labelmap sind nicht deckungsgleich (z. B. `jupiter-predeploy`/`jupiter-review-architecture` nur im Frontend, `jupiter-review` nur im Backend). Führt zu keinem Funktionsfehler, nur zu potenziell inkonsistenter Anzeige gegenüber einer künftigen zweiten Oberfläche, die `label` direkt nutzt.

### Regressionstest
Siehe automatisierte Läufe oben — keine Regression durch PROJ-83 (alle 4 Fehlschläge vorbestehend, unabhängig vom Feature).

### Production-Ready-Empfehlung: **NOT READY**

1 offener Bug: **BUG-2 (Critical)** — Engine-Dropdown durch `Set`-`in`-Fehler dauerhaft leer, Feature komplett unbedienbar. Ein-Zeilen-Fix (`.has()` statt `in`), muss vor erneuter QA/Deploy behoben werden.

---

## BUG-2 Fix (2026-08-20)

`hermes-profile-models-control.tsx:82`: `e.key in ALLOWED_ENGINES` → `ALLOWED_ENGINES.has(e.key as HermesEngineKey)`. Node-Repl-Verifikation: Filter liefert jetzt `[{key:"claude",...}]` statt `[]`. `npm run build` erfolgreich, keine neuen `tsc`-Fehler in der Datei.

**Noch offen:** Erneute QA-Verifikation gegen den laufenden Server (Re-Test AC B) steht aus — dieser Fix wurde direkt (nicht über `/abc-frontend`) angewandt.
