# PROJ-76: Textdateien im Fileexplorer bearbeiten

## Status: Architected
**Created:** 2026-08-07
**Last Updated:** 2026-08-07

## Dependencies
- Requires: PROJ-11 (Fileexplorer + Drag-and-Drop) — Dateiliste, Dateioperationen und sicherer Zugriff auf erlaubte Roots.
- Requires: PROJ-12 (MD-Editor) — vorhandenes Muster für Bearbeiten, Live-Vorschau, Speichern und Konfliktbehandlung.
- Requires: PROJ-28 (Fileexplorer Drei-Spalten-Layout) — der Editor erscheint in der bestehenden rechten Inhalts-Ansicht.
- Requires: PROJ-37 (Aktives Fenster bleibt rechts) — die bestehende Umschaltlogik zwischen Dateiansicht und aktivem Fenster bleibt erhalten.

## Beschreibung
Gängige Textdateien können direkt im Fileexplorer bearbeitet werden. Das bisher für **Umbenennen** verwendete Stift-Symbol öffnet bei bearbeitbaren Dateien den Editor in der rechten Inhalts-Ansicht. Die Umbenennen-Aktion erhält ein eigenes, eindeutig unterscheidbares Symbol.

Änderungen bleiben bis zum ausdrücklichen Speichern ein lokaler Entwurf. Sie sind im Editor sofort sichtbar; Markdown kann zusätzlich als laufend aktualisierte Vorschau angezeigt werden. Ungespeicherte Änderungen lassen sich per Strg/Cmd+Z oder vollständig bis zum zuletzt gespeicherten Stand zurücksetzen. Eine Versionierung bereits gespeicherter Fassungen ist nicht Teil dieses Features.

## User Stories
- Als Nutzer möchte ich eine gängige Textdatei über das Stift-Symbol direkt im Fileexplorer bearbeiten, damit ich nicht ins Terminal wechseln muss.
- Als Nutzer möchte ich die Datei im bestehenden rechten Bereich bearbeiten, damit Auswahl und Arbeitskontext erhalten bleiben.
- Als Nutzer möchte ich meine Eingaben sofort im Editor und Markdown wahlweise als Live-Vorschau sehen, damit ich das Ergebnis vor dem Speichern prüfen kann.
- Als Nutzer möchte ich einzelne ungespeicherte Eingaben rückgängig machen oder den gesamten Entwurf verwerfen, damit Fehler nicht in der Datei landen.
- Als Nutzer möchte ich Änderungen ausdrücklich speichern und eine klare Rückmeldung erhalten, damit ich den persistierten Stand erkenne.
- Als Nutzer möchte ich vor dem Verlust ungespeicherter Änderungen und vor dem Überschreiben fremder Änderungen geschützt werden.

## Acceptance Criteria
- [ ] Der Stift wird in der Dateiliste ausschließlich bei bearbeitbaren Textdateien als Aktion **„Bearbeiten“** angezeigt und öffnet den Editor für diese Datei.
- [ ] Die bisherige Aktion **„Umbenennen“** bleibt für Dateien und Ordner verfügbar, verwendet jedoch ein anderes, eindeutig als Umbenennen erkennbares Symbol und den Tooltip „Umbenennen“.
- [ ] Der Editor ersetzt für die ausgewählte Datei die Vorschau in der bestehenden rechten Inhalts-Ansicht; es öffnet sich weder ein Dialog noch eine neue Browserseite.
- [ ] Bearbeitbar sind `.md`, `.markdown`, `.txt`, `.text`, `.yaml`, `.yml`, `.json`, `.jsonc`, `.log`, `.csv`, `.tsv`, `.xml`, `.toml`, `.ini`, `.cfg`, `.conf`, `.env`, `.properties` sowie die bereits in der Dateivorschau unterstützten gängigen Skript- und Quelltextdateien.
- [ ] Nicht unterstützte, binäre, nicht als UTF-8 lesbare oder mehr als 2 MB große Dateien bleiben reine Vorschau-/Download-Dateien und zeigen keine Bearbeiten-Aktion.
- [ ] Beim Öffnen enthält der Editor exakt den aktuell gespeicherten Dateiinhalt; auch Leerdateien lassen sich bearbeiten.
- [ ] Jede Eingabe ist sofort im Editor sichtbar. Bei Markdown kann zwischen **„Bearbeiten“** und **„Vorschau“** gewechselt werden; die Vorschau verwendet stets den aktuellen ungespeicherten Entwurf.
- [ ] Ungespeicherte Änderungen werden sichtbar als **„Ungespeichert“** gekennzeichnet; ohne Änderung ist die Speichern-Aktion deaktiviert.
- [ ] Strg/Cmd+Z macht die üblichen Eingabeschritte innerhalb des aktuellen ungespeicherten Entwurfs rückgängig.
- [ ] Die Aktion **„Änderungen verwerfen“** setzt nach Bestätigung den gesamten Entwurf auf den zuletzt vom Server geladenen beziehungsweise erfolgreich gespeicherten Stand zurück.
- [ ] Die Aktion **„Speichern“** und Strg/Cmd+S schreiben den vollständigen Entwurf in dieselbe Datei. Nach Erfolg verschwindet die Kennzeichnung „Ungespeichert“ und die sichtbare Ansicht zeigt den gespeicherten Inhalt.
- [ ] Beim Wechsel zu einer anderen Datei, beim Ordnerwechsel, beim Schließen des Editors oder beim Verlassen der Seite mit ungespeicherten Änderungen kann der Nutzer **„Speichern“**, **„Verwerfen“** oder **„Abbrechen“** wählen.
- [ ] Wurde die Datei seit dem Laden außerhalb dieses Editors verändert, wird sie nicht still überschrieben. Der Nutzer erhält einen deutschen Konflikthinweis und kann den aktuellen Serverstand neu laden oder bewusst überschreiben.
- [ ] Schlägt das Laden oder Speichern fehl, bleibt der ungespeicherte Entwurf erhalten und eine verständliche deutsche Fehlermeldung wird angezeigt.
- [ ] Nach erfolgreichem Speichern werden Dateigröße und Änderungszeit in der Dateiliste beziehungsweise Ansicht aktualisiert, ohne die aktuelle Datei abzuwählen.
- [ ] Das bestehende Drei-Spalten-Layout, die mobile Umschaltung zwischen Liste und Ansicht sowie die Rückkehr zum aktiven Session-Fenster ohne ausgewählte Datei bleiben funktionsfähig.

## Edge Cases
- **Leere Datei:** Der Editor zeigt ein leeres Eingabefeld; eingegebener Inhalt kann normal gespeichert werden.
- **Ungültiges YAML/JSON oder syntaktisch fehlerhafter Code:** Der Inhalt darf als Rohtext gespeichert werden; dieses Feature führt keine Formatvalidierung oder automatische Korrektur ein.
- **Nicht-UTF-8-Inhalt:** Bearbeiten ist gesperrt; die Datei bleibt herunterladbar und der Hinweis „Diese Datei kann nicht als UTF-8-Text bearbeitet werden.“ wird angezeigt.
- **Datei größer als 2 MB:** Kein Editor wird geladen; Vorschau-/Download-Verhalten und Größenhinweis bleiben erhalten.
- **Datei wird extern geändert:** Speichern führt zum Konflikthinweis statt zum stillen Überschreiben.
- **Datei wird extern gelöscht oder umbenannt:** Speichern schlägt kontrolliert fehl, der Entwurf bleibt kopierbar und es gibt keinen neuen Dateinamen ohne Nutzeraktion.
- **Keine Schreibberechtigung:** Der Editor darf gelesen werden, Speichern meldet „Keine Berechtigung zum Speichern dieser Datei.“ und behält den Entwurf.
- **Netzwerk-/Backendfehler:** Der Entwurf bleibt im Browser erhalten; erneutes Speichern ist möglich.
- **Datei- oder Ordnerwechsel mit ungespeichertem Entwurf:** Der Wechsel erfolgt erst nach Speichern oder bewusstem Verwerfen; „Abbrechen“ lässt Editor und Entwurf unverändert.
- **Mehrfaches Speichern ohne weitere Änderung:** Es erfolgt kein unnötiger Schreibvorgang; die Speichern-Aktion bleibt deaktiviert.
- **Mobilansicht:** Editor, Vorschau, Speichern und Verwerfen sind ohne horizontales Überlaufen bedienbar; der Zurück-Wechsel zur Liste löst bei ungespeicherten Änderungen dieselbe Schutzabfrage aus.

## Non-Goals
- Keine Versionshistorie und kein Wiederherstellen bereits gespeicherter Fassungen.
- Kein kollaboratives gleichzeitiges Bearbeiten.
- Kein Syntax-Highlighting, Linting, Formatieren oder Schema-Validieren.
- Kein Bearbeiten binärer Dateien oder beliebiger unbekannter Dateiendungen.
- Kein Anlegen neuer Dateien; das bleibt eine separate Fileexplorer-Funktion.

## Technical Requirements (optional)
- Dateiinhalt wird nur innerhalb der bestehenden erlaubten Roots gelesen und geschrieben; Pfad-Traversal und Symlink-Ausbruch bleiben serverseitig gesperrt.
- Speichern darf bei Fehlern keine teilweise geschriebene Datei hinterlassen.
- Konflikterkennung basiert auf dem beim Laden beziehungsweise letzten Speichern bekannten Dateistand.
- Alle sichtbaren Beschriftungen, Bestätigungen und Fehlermeldungen sind deutsch.
- Keine neue Editor-Bibliothek ist für den MVP erforderlich; Browser-Textbearbeitung und vorhandene Markdown-Vorschau genügen.

---
<!-- Sections below are added by subsequent skills -->

## Tech Design (Solution Architect)
**Erstellt:** 2026-08-07 · **Stack:** Next.js 16 + React + Tailwind/shadcn UI · FastAPI + Host-Dateisystem · **Branch:** dev

### Kurzfassung

PROJ-76 erweitert den bestehenden Fileexplorer um **einen** allgemeinen Texteditor. Es entsteht weder ein zweiter Dateibrowser noch ein eigener Editor pro Dateityp. Der vorhandene Vorschau-Bereich rechts wechselt für bearbeitbare Dateien zwischen Vorschau und Editor; Markdown nutzt dort die bereits vorhandene `MarkdownView`.

Die Dateien bleiben direkt im Host-Dateisystem. Es gibt keine neue Datenbanktabelle und keinen MinIO-Speicher. Das Backend ergänzt den bestehenden `/files`-Dienst um einen sicheren Text-Lese-/Schreibpfad mit derselben Root-Prüfung, atomarem Speichern und Konflikterkennung, die Jupiter bereits beim MD-Editor verwendet.

### A) Komponentenstruktur

```text
FileExplorer (/dateien)
├── Dateiliste
│   └── Dateiaktionen
│       ├── Stift „Bearbeiten“ (nur wenn serverseitig als editierbar markiert)
│       ├── Text-Cursor „Umbenennen“ (Dateien und Ordner)
│       ├── Download
│       ├── Pfad kopieren
│       └── Löschen
└── Rechte Inhalts-Ansicht
    ├── FilePreview (bestehend, normaler Auswahl-Klick)
    ├── TextFileEditor (neu, Stift-Klick)
    │   ├── Dateikopf mit Name, Größe und „Ungespeichert“-Status
    │   ├── Toolbar: Bearbeiten · Vorschau (nur Markdown) · Verwerfen · Speichern
    │   ├── Textarea für Rohtext
    │   ├── MarkdownView für den aktuellen Entwurf
    │   └── Konflikt-Dialog: Neu laden · Überschreiben
    ├── UnsavedChangesDialog
    │   └── Speichern · Verwerfen · Abbrechen
    └── ActiveSessionPanel (bestehend, wenn keine Datei gewählt ist)
```

Der `FileExplorer` bleibt Eigentümer von Auswahl, Ordnernavigation und mobilem Pane. Er kennt zusätzlich den Modus **Vorschau/Bearbeiten** und ob der aktive Editor ungespeicherte Änderungen hat. Dadurch laufen Dateiwechsel, Ordnerwechsel, Zurück zur Liste und Editor-Schließen durch dieselbe Schutzabfrage.

### B) Datenmodell und Zustand

**Keine persistente App-Datenhaltung:** Die Datei im Host-Dateisystem bleibt die einzige Wahrheit. Kein Postgres, kein MinIO und keine Versionshistorie.

Ein Dateieintrag erhält zusätzlich die Information, ob er direkt bearbeitet werden darf. Das Backend entscheidet dies aus:

- erlaubter Text-Endung,
- Dateigröße bis einschließlich 2 MB,
- gültigem UTF-8-Inhalt.

Damit besitzt das Backend die verbindliche Allowlist; das Frontend muss sie nicht ein zweites Mal pflegen. Die bestehende Preview-Typisierung bleibt ausschließlich für die Darstellung zuständig.

Beim Öffnen liefert der Text-Lesepfad:

- absoluten, validierten Pfad,
- vollständigen Textinhalt,
- Größe und Änderungszeit,
- Inhalts-Hash als Konfliktbasis.

Der Browser hält nur zwei Textstände: **zuletzt geladener/gespeicherter Stand** und **aktueller Entwurf**. Sind sie verschieden, ist der Editor „Ungespeichert“. Nach erfolgreichem Speichern wird der Entwurf zur neuen Basis. Strg/Cmd+Z bleibt die native Rückgängig-Funktion des Textfelds; „Änderungen verwerfen“ setzt vollständig auf die Basis zurück.

### C) API-Form

- `GET /files/list?path=…` → wie bisher; Dateieinträge enthalten zusätzlich `editable`.
- `GET /files/text?path=…` → lädt eine editierbare UTF-8-Textdatei samt Größe, Änderungszeit und Hash.
- `PUT /files/text` → ersetzt den vollständigen Dateiinhalt atomar; erwartet Pfad, Inhalt und den beim Laden bekannten Hash.
- `PUT /files/text` mit bewusster Überschreibfreigabe → speichert trotz erkanntem externen Konflikt.
- Bestehende Endpunkte für Download, Umbenennen, Löschen und Verzeichnislisten bleiben unverändert.

Antwortregeln:

- `400` für nicht unterstützten Typ, ungültiges UTF-8 oder Datei über 2 MB,
- `403` für Pfade außerhalb der erlaubten Roots oder fehlende Schreibberechtigung,
- `404` für zwischenzeitlich gelöschte/umbenannte Dateien,
- `409` wenn der aktuelle Datei-Hash nicht mehr dem geladenen Stand entspricht.

### D) Interaktionsablauf

1. Ein normaler Klick auf eine Datei zeigt weiterhin die bestehende Vorschau.
2. Ein Klick auf den Stift wählt dieselbe Datei und öffnet rechts den Editor.
3. Eingaben ändern nur den lokalen Entwurf. Markdown-Vorschau liest direkt diesen Entwurf; andere Texttypen bleiben in der Rohtextansicht.
4. „Speichern“ oder Strg/Cmd+S sendet den vollständigen Entwurf mit dem bekannten Hash.
5. Nach Erfolg bleiben Datei und Editor ausgewählt; Metadaten und Dateiliste werden aktualisiert.
6. Bei `409` bleiben lokale Änderungen erhalten. „Neu laden“ verwirft sie bewusst, „Überschreiben“ sendet denselben Entwurf mit expliziter Freigabe erneut.
7. Bei internen Wechseln mit ungespeichertem Entwurf erscheint der Drei-Wege-Dialog. Browser-Reload und Tab-Schließen verwenden aus Plattformgründen die native Browserwarnung mit **Verlassen/Abbrechen**; Browser erlauben dort keine eigene „Speichern“-Schaltfläche.

### E) Technische Entscheidungen

1. **Ein allgemeiner Texteditor statt Erweiterung des vollen MD-Editors.** Der vorhandene MD-Editor enthält Doku-spezifische Funktionen wie Frontmatter, Wikilinks und Backlinks. Der Fileexplorer braucht nur Rohtext, Speichern, Konfliktschutz und optional Markdown-Vorschau. So werden keine Doku-Funktionen in YAML-, JSON- oder Code-Dateien gezogen.
2. **Bestehende Bausteine wiederverwenden.** `MarkdownView`, shadcn-Textarea/Dialog/Button, authentifizierter Dateiabruf, Root-Validierung und atomares Schreiben sind vorhanden. Es kommt keine Editor-Bibliothek hinzu.
3. **Backend entscheidet Editierbarkeit.** Extension, Größe und UTF-8 werden an der Vertrauensgrenze geprüft. Manipulierte Requests können dadurch weder Binärdateien noch große oder nicht erlaubte Dateien überschreiben.
4. **Vollständiges Ersetzen statt Patchen.** Textdateien sind auf 2 MB begrenzt; ein kompletter Entwurf ist einfacher, nachvollziehbarer und passt zur bestehenden MD-Editor-Semantik. Teil-Patches oder kollaborative Operationen wären unnötige Komplexität.
5. **Hash-basierte optimistische Konflikterkennung.** Externe Änderungen werden sicher erkannt, ohne Locks oder dauerhaften Serverzustand. Bewusstes Überschreiben bleibt möglich.
6. **Atomisches Schreiben.** Der bestehende Temp-Datei-plus-Ersetzen-Mechanismus verhindert halbe Dateien bei Prozess- oder I/O-Fehlern.
7. **Umbenennen bleibt eigenständig.** Ein vorhandenes Lucide-Text-Cursor-Symbol ersetzt den Stift. Tooltip und zugänglicher Name bleiben „Umbenennen“.

### F) Sicherheit und Grenzfälle

- Jeder Lese- und Schreibzugriff wird nach Auflösung von Symlinks erneut gegen `allowed_roots` geprüft.
- Der Server akzeptiert nur die festgelegten Texttypen, gültiges UTF-8 und höchstens 2 MB Inhalt; die Prüfung gilt beim Lesen **und** beim Speichern.
- Schreibfehler lassen die bestehende Datei unverändert und den Browserentwurf erhalten.
- Syntaxfehler in YAML, JSON oder Code werden bewusst nicht validiert: Es ist ein Texteditor, kein Konfigurationsassistent.
- Wird die Datei gelöscht oder umbenannt, bleibt der Entwurf sichtbar und kopierbar; Jupiter legt nicht still eine neue Datei an.
- Die Mobile-Ansicht verwendet dieselbe Schutzlogik wie Desktop und behält die vorhandene Liste/Ansicht-Umschaltung.

### G) Abhängigkeiten und betroffene Bereiche

**Neue Pakete:** keine.

**Frontend:** Fileexplorer-Auswahl/Aktionen, Dateivorschau-Klassifikation, neuer schlanker Texteditor, API-Typen und API-Aufrufe.

**Backend:** vorhandener `/files`-Router, FileService und Datei-Schemas; keine Datenbankmigration und kein neuer Dienst.

**Umsetzungsreihenfolge:** Da der Editor den neuen sicheren Text-Endpunkt benötigt, wird nach der Frontend-Oberfläche `/abc-backend` ausgeführt; anschließend prüft `/abc-qa` beide Teile gemeinsam.

## QA Test Results
_To be added by /qa_

## Deployment
_To be added by /deploy_
