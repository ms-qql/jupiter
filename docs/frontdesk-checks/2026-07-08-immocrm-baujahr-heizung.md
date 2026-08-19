# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #46)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 55d4ab3c (Freshdesk #46) — "Baustein bei Energiedaten fehlt noch das Baujahr der Heizung" | Kein Fehler, berechtigter Feature-Wunsch: Baujahr/Alter der Heizung fehlt als Feld in den Energiedaten | Niedrig |

---

### Ticket: Peppermint-Ticket "Baustein bei Energiedaten fehlt noch das Baujahr der Heizung" (Peppermint 55d4ab3c-bbf9-4f9d-bf23-0b90f56376b2, Freshdesk #46, Absenderin: Beata Rutkowska / Erol Immobilien GmbH, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht, sondern ein klarer Verbesserungswunsch: "könntest du bitte
bei den Energiedaten noch ein Textbaustein einfügen, wo man das Jahr der Heizung einfügen kann.
Dort steht nur Datum und Gültig von/bis des Ausweisen." Kein Datum, kein konkreter Datensatz
nötig — Anfrage betrifft die allgemeine Formularstruktur, nicht einen Einzelfall.

**Eingrenzung:** Frontend (+ kleines Backend/DB-Feld) · Modul: Objektdetail → Energiedaten
(`immo-crm`, `lib/features/properties/property_detail_screen.dart`).

Code-Grep-Befund:
- Die Energiedaten-Card (Zeile ~3296–3450) zeigt/erfasst aktuell: Heizungsart (`heatingType`),
  Energiekennwert (`thermalCharacteristic`), Energieausweis vorhanden (`energyCertificateAvailable`),
  Ausstellungsdatum (`energyCertificateIssueDate`, Zeile 3331/3379), Gültig bis
  (`energyCertificateValidUntil`, Zeile 3333/3387) und Warmwasseraufbereitung
  (`hotWaterPreparation`). Das deckt sich mit der Kundenbeschreibung ("Datum und Gültig von/bis
  des Ausweises").
- Es existiert bereits ein separates Feld "Baujahr" (`construction_year`, Zeile 2058) — das
  bezieht sich aber auf das **Gebäude**, nicht auf die Heizungsanlage. Ein Feld für das
  Heizungs-Baujahr/-Alter ist im Energiedaten-Formular nicht vorhanden, Backend-seitig gibt es
  keinen entsprechenden Parameter im Umfeld von `heatingType`/`heating_type`
  (`backend/app/services/is24_mapper.py`, `openimmo_parser.py`, `routes/expose.py`,
  `routes/import_export.py`).
- Strukturelle Lücke, kein Datenfehler: das Feld fehlt schlicht im Formular, DB-Schema und
  vermutlich in den Export-Mappings (IS24/OpenImmo) — vollständige Umsetzung bräuchte neue Spalte
  + Formularfeld + Anzeige + ggf. Export-Mapping.

**Dringlichkeit:** Niedrig
Freshdesk hat "low" gesetzt, passt zum Charakter: kein Datenrisiko, kein DSGVO-Bezug, keine
Blockade — Kunde kann weiterarbeiten, das Feld ist lediglich ein Komfort-/Vollständigkeits-Wunsch
für den Energieausweis-Bereich (energetisch relevant für Exposés, aber nicht akut).

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für den Hinweis. Aktuell erfassen wir bei den Energiedaten das Ausstellungsdatum
> und die Gültigkeit des Energieausweises, aber tatsächlich noch kein separates Feld für das
> Baujahr bzw. Alter der Heizungsanlage. Wir nehmen das als kleine Ergänzung des Formulars auf
> und melden uns, sobald es umgesetzt ist.

**Rückfragen-Guidance:** Keine notwendig für die Einstufung — das Ticket ist klar genug für die
Umsetzung als reguläre Feature-Spec. Für die Umsetzung selbst wäre höchstens zu klären, ob das
neue Feld nur Anzeige/Erfassungs-Feld im Frontend sein soll oder auch in Exporte (IS24, OpenImmo,
Exposé-PDF) einfließen muss — das ist aber eine Scope-Frage für `/abc-requirements`, keine
fehlende Information für diese Triage.

---

Nächster Schritt bei Bedarf: `/abc-requirements` im `immo-crm`-Projekt für eine kleine
Frontend+Backend-Spec ("Baujahr der Heizung als Feld in Energiedaten") — kein Bug-Fix, sondern
regulärer Feature-Weg.
