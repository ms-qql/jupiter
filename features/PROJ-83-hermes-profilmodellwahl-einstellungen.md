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
<!-- Sections below are added by subsequent skills -->
