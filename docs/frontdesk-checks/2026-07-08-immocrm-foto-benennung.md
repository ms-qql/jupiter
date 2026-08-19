# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #49)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint a45c17e3 (Freshdesk #49) — "Foto mit Namen benennen" | Kein Fehler, Feature-Wunsch: Bild-Klassifizierung existiert bereits, aber die gewünschten Raum-Kategorien fehlen im Enum | Niedrig |

---

### Ticket: Peppermint-Ticket "Foto mit Namen benennen" (Peppermint a45c17e3-2c23-4b7c-ad6a-c551578d9c3d, Freshdesk #49, Absenderin: Beata Rutkowska / Erol Immobilien GmbH, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht. Die Kundin möchte Bilddateien entweder selbst benennen können
oder sie sollen automatisch mit festen Bezeichnungen versehen werden (Abstellraum, Treppenhaus,
Waschküche, Aufzug, Fahrradraum, Schwimmbad/Sauna, Gartenhaus, Wintergarten, Ankleidezimmer, Gäste
WC, Außenstellplatz/Carport); der aktuell angezeigte "Titel" soll dann entfallen. Kein Datum, kein
konkreter Datensatz nötig — betrifft die allgemeine Bild-Verwaltung, nicht einen Einzelfall.

**Eingrenzung:** Frontend (Flutter) · Modul: Objekt-Bilder / Exposé-Erzeugung (`immo-crm`).

Code-Grep-Befund:
- Es existiert bereits eine Bild-Klassifizierung: `enum ImageClassification` in
  `lib/features/properties/models/property_enums.dart:460-476` mit den Werten `exterior`,
  `livingRoom`, `bedroom`, `kitchen`, `bathroom`, `balcony`, `garden`, `hallway`, `cellar`,
  `attic`, `garage`, `other`. Diese Klassifizierung wird im Exposé-PDF verwendet
  (`lib/features/properties/expose/expose_pdf_builder.dart:371,380`): pro Bild wird
  `classification.label` plus optional ein frei eingegebener `title` angezeigt
  (`'${images[idx].classification.label}${images[idx].title != null ? ' – ${images[idx].title}' : ''}'`).
- Die von der Kundin gewünschten Raum-Bezeichnungen (Abstellraum, Treppenhaus, Waschküche, Aufzug,
  Fahrradraum, Schwimmbad/Sauna, Gartenhaus, Wintergarten, Ankleidezimmer, Gäste WC,
  Außenstellplatz/Carport) sind **nicht** in der aktuellen Enum-Liste enthalten — die Funktion
  existiert im Prinzip schon (Kategorie statt Freitext-Dateiname), deckt aber nicht alle von ihr
  gewünschten Raumtypen ab.
- "Titel was oben steht" bezieht sich vermutlich auf das optionale `title`-Feld pro Bild, das im
  Exposé zusätzlich zur Klassifizierung angezeigt wird — die Kundin möchte, dass bei vorhandener
  Klassifizierung nur noch die feste Bezeichnung erscheint, kein separater Titel.
- Strukturelle Lücke, kein Datenfehler: Erweiterung des Enums (Backend `classification`-Feld
  vermutlich als String/Enum in `property_images`-Tabelle, kein neues Datenmodell nötig) plus
  ggf. Anpassung der Exposé-Anzeigelogik, wenn Titel bei vorhandener Klassifizierung ausgeblendet
  werden soll — keine tiefgreifende Änderung, aber mehr als eine reine Textkorrektur.

**Dringlichkeit:** Niedrig
Freshdesk hat "low" gesetzt, passt zum Charakter: kein Datenrisiko, kein DSGVO-Bezug, keine
Blockade — Kundin kann weiterarbeiten (Bilder sind bereits hochladbar und exportierbar), es geht
um Komfort/Vollständigkeit bei der Bild-Beschriftung.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für den Hinweis. Es gibt bereits eine Kategorisierung für Bilder (z. B.
> Außenansicht, Wohnzimmer, Küche, Bad, Balkon, Garten, Flur, Keller, Dachboden, Garage), die
> automatisch im Exposé angezeigt wird. Die von Ihnen gewünschten Bezeichnungen wie Abstellraum,
> Treppenhaus, Waschküche, Aufzug, Fahrradraum, Schwimmbad/Sauna, Gartenhaus, Wintergarten,
> Ankleidezimmer, Gäste-WC und Außenstellplatz/Carport sind darin aktuell noch nicht enthalten.
> Wir nehmen das als Ergänzung der Kategorie-Liste auf und schauen uns dabei auch die Anzeige des
> zusätzlichen Bildtitels im Exposé an. Wir melden uns, sobald es umgesetzt ist.

**Rückfragen-Guidance:** Keine notwendig für die Einstufung. Für die Umsetzung selbst wäre zu
klären, ob die neuen Kategorien die bestehende `ImageClassification`-Enum erweitern sollen (dann
feste Auswahlliste, konsistent mit dem bisherigen Verhalten) oder ob stattdessen ein Freitextfeld
pro Bild gewünscht ist ("Bilddateien selbst benennen") — das Ticket nennt beide Varianten
("entweder selbst benennen oder ... mit Bezeichnungen versehen"), das ist aber eine Scope-Frage
für `/abc-requirements`, keine fehlende Information für diese Triage.

---

Nächster Schritt bei Bedarf: `/abc-requirements` im `immo-crm`-Projekt für eine kleine
Frontend(+Backend)-Spec ("Erweiterte Bild-Kategorien + Titel-Anzeige im Exposé") — kein Bug-Fix,
sondern regulärer Feature-Weg.
