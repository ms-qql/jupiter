# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #80)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint fdeb3800-7511-4415-af6f-7b490b10b111 (Freshdesk #80) — "Art Terminen Begriffe hinzufügen" | Kein Fehler, Feature-Wunsch: 3 neue Termin-Arten in fest codierter Dropdown-Liste ergänzen | Niedrig |

---

### Ticket: "Art Terminen Begriffe hinzufügen." (Peppermint fdeb3800-7511-4415-af6f-7b490b10b111, Freshdesk #80, Absender: Firat Erol / Erol Immobilien GmbH, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht, sondern ein einfacher Erweiterungswunsch: Bei der Termin-Art
("Art") sollen die drei zusätzlichen Begriffe **"Beratung Leibrente"**, **"Privattermin"** und
**"Objektaufnahme"** ergänzt werden. Kein Datensatz, kein Zeitraum genannt — betrifft die
allgemeine Auswahlliste, kein Einzelfall.

**Eingrenzung:** Frontend (Projekt `immo-crm`, nicht Jupiter selbst) · Modul: Terminverwaltung.

Code-Grep-Befund (read-only, im Nachbarprojekt `/home/dev/projects/immo-crm`):
- Die Termin-Art wird über eine fest codierte Dart-Liste `_validTypes` in
  `lib/features/appointments/widgets/appointment_form_dialog.dart:55-64` gepflegt:
  `Besichtigung, Beratung, Beratungsgespräch im Büro, Beratungsgespräch vor Ort,
  Bewertungstermin, Beurkundung/Notartermin, Übergabetermin, Mietvertrag Unterzeichnung,
  Open House, Entrümpelungsangebot, Umzugsangebot, Urlaub (Beata,Firat), Geburtstage,
  Werbeflächen Überweisung, Sonstiges`.
- Keiner der drei gewünschten Begriffe ("Beratung Leibrente", "Privattermin",
  "Objektaufnahme") ist aktuell enthalten; ein unbekannter/gespeicherter Wert fällt im
  Formular automatisch auf `"Sonstiges"` zurück (`appointment_form_dialog.dart:101`).
- Backend-seitig ist `type` in der `appointments`-Tabelle ein freies Textfeld ohne
  DB-Constraint/Enum — nur einzelne Auswertungen (Dashboard-Fortschrittskacheln in
  `backend/app/services/property_progress.py:30-42`, `lib/features/properties/progress/
  fortschritt_section.dart:29-30`) kennen eine eigene, kleinere Teilmenge bekannter Typen
  (`Besichtigung`, `Beurkundung/Notartermin`) für Zähl-Widgets. Die drei neuen Begriffe
  würden dort nicht automatisch mitgezählt, das ist aber unabhängig von der eigentlichen
  Ergänzung der Dropdown-Liste und für die Kundenanfrage nicht relevant.
- Ergebnis: Eine kleine, klar lokalisierte Frontend-Änderung (drei Strings in einer
  Konstanten-Liste), kein Bug, keine Datenmigration nötig.

**Dringlichkeit:** Niedrig
Freshdesk hat "low" gesetzt, das passt: reine Komfort-/Vollständigkeitsanfrage für die
Terminerfassung, kein Datenrisiko, keine DSGVO-Relevanz, keine Blockade — der Kunde kann Termine
weiterhin normal anlegen (aktuell unter "Sonstiges" oder einem bestehenden ähnlichen Begriff).

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre Nachricht. Wir nehmen die drei gewünschten Termin-Arten "Beratung
> Leibrente", "Privattermin" und "Objektaufnahme" gerne in die Auswahlliste bei den Terminen
> auf und melden uns, sobald die Ergänzung umgesetzt ist.

**Rückfragen-Guidance:** Keine notwendig für die Einstufung — die drei gewünschten Begriffe sind
eindeutig benannt. Für die Umsetzung selbst wäre allenfalls zu klären, ob "Beratung Leibrente"
zusätzlich in die Dashboard-Fortschrittszählung (`property_progress.py`) aufgenommen werden soll
oder rein als Auswahlbegriff ohne Statistik-Anbindung reicht — das ist eine Scope-Frage für
`/abc-requirements` im `immo-crm`-Projekt, keine fehlende Information für diese Triage.

---

Nächster Schritt bei Bedarf: `/abc-requirements` im `immo-crm`-Projekt für eine kleine
Frontend-Spec ("Termin-Art: drei neue Begriffe ergänzen") — kein Bug-Fix, sondern regulärer
Feature-Weg.
