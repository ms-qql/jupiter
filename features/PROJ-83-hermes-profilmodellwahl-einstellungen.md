# PROJ-83: Modellwahl pro Hermes-Profil in den Einstellungen

## Status: Planned
**Created:** 2026-08-19

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
- Anzeige des Profilnamens, aktuell wirksamen Modells und eines Dropdowns mit den auswählbaren Modellen.
- Persistieren einer gültigen Auswahl in der jeweiligen Profil-`config.yaml`.
- Deutsche Lade-, Erfolg- und Fehlermeldungen.

Out of scope:
- Anlegen, Löschen, Umbenennen oder sonstige Bearbeitung von Hermes-Profilen.
- Ändern von Provider, Credentials, Skills, Tools, Berechtigungen oder anderen Profilwerten.
- Bearbeiten von Nicht-abc-Profilen.
- Modellwechsel bereits laufender Hermes-Worker oder Jupiter-Sessions.
- Neue Modelle, Provider oder eine zweite Modellregistry.

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
- [ ] Jedes angezeigte Profil besitzt ein Dropdown mit den für die Profilwahl verfügbaren Modellen; das aktuell konfigurierte Modell ist vorausgewählt.
- [ ] Der Nutzer kann die Auswahl für ein oder mehrere Profile ändern und anschließend explizit speichern.
- [ ] Nach erfolgreichem Speichern zeigt Jupiter eine deutsche Erfolgsmeldung und den vom Server zurückgegebenen, gültigen Profilstand.
- [ ] Nach dem Speichern, Neuladen der Einstellungsseite und Backend-Neustart ist das gewählte Modell weiter als aktuelles Modell des betreffenden Profils sichtbar.
- [ ] Die Änderung gilt für anschließend gestartete Hermes-Worker dieses Profils; bereits laufende Worker behalten ihr beim Start verwendetes Modell.
- [ ] Eine ungültige oder nicht angebotene Modellauswahl wird serverseitig abgewiesen; die UI zeigt eine verständliche deutsche Fehlermeldung und den letzten gültigen Stand.

### C — Profilisolation und Konfigurationsschutz
- [ ] Das Speichern einer Modellauswahl verändert ausschließlich die `config.yaml` des ausgewählten Profils.
- [ ] Nicht zum Modell gehörende Profilwerte bleiben unverändert erhalten.
- [ ] Die Einstellungen lesen oder zeigen keine Secret-Werte, Tokens, API-Keys oder Credentials aus Profilkonfigurationen.
- [ ] Eine fehlende, unlesbare oder syntaktisch ungültige `config.yaml` eines Profils wird für dieses Profil klar als Fehlerzustand angezeigt; andere lesbare Profile bleiben weiterhin bedienbar.
- [ ] Schlägt das Speichern eines Profils fehl, bleibt dessen zuvor gültige Konfiguration wirksam; Jupiter darf keinen unvollständigen oder irreführenden Erfolgszustand anzeigen.

### D — Konsistenz mit bestehender Modellverwaltung
- [ ] Die Profilmodell-Dropdowns verwenden nur Modelle, die in Jupiters bestehender Modellverwaltung als auswählbar verfügbar sind; dieses Feature legt keine eigene Modellliste an.
- [ ] Eine Änderung in der globalen Modellverwaltung wird bei erneutem Laden der Profileinstellungen berücksichtigt.
- [ ] Der bestehende Einstellungen-Tab **„Modelle"**, der Neue-Session-Dialog und die Hermes-Kanban-Funktionen bleiben unverändert nutzbar.

## Edge Cases
- **Ein abc-Profil wird zwischen Laden und Speichern gelöscht oder umbenannt** — Speichern schlägt nur für dieses Profil mit einer deutschen Meldung fehl; die übrigen Profile bleiben unverändert.
- **Aktuelles Profilmodell ist nicht mehr in der verfügbaren Modellliste** — der aktuelle Wert bleibt als solcher sichtbar und wird als nicht mehr verfügbar markiert; der Nutzer muss vor einem Speichern ein gültiges Modell wählen.
- **Mehrere Browser-Tabs ändern dasselbe Profil** — der zuletzt erfolgreich gespeicherte, serverseitig gültige Stand wird nach dem Speichern zurückgegeben; die UI darf keinen lokalen Entwurf als gespeichert darstellen.
- **Mehrere Profile werden gespeichert und eines ist ungültig oder nicht schreibbar** — fehlgeschlagene Profile werden eindeutig benannt; bereits erfolgreich gespeicherte Profile bleiben mit ihrem tatsächlich gespeicherten Stand sichtbar.
- **Server kann Profilverzeichnis oder Konfigurationsdatei temporär nicht erreichen** — keine Auswahl wird als gespeichert bestätigt; die UI bietet Wiederholen an.
- **Ein Modellwechsel wird während eines laufenden Workers vorgenommen** — der laufende Worker wird weder neu gestartet noch in seinem Modell geändert; die Wahl gilt erst für künftige Starts.
- **Profilkonfiguration enthält unbekannte zusätzliche Einstellungen** — diese bleiben erhalten und werden durch die Modellwahl weder angezeigt noch entfernt.

---

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
<!-- Sections below are added by subsequent skills -->
