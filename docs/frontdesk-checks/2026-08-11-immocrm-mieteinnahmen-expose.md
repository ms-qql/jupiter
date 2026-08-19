# Frontdesk-Triage — 2026-08-11

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #139)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 2f786257-bc12-4cf7-8403-4cfbb423642e (Freshdesk #139) — "ImmoCRM - Mieteinnahmen Expose" | Kein Fehler, Feature-Wunsch: Mieteinnahmen fehlen im Exposé bei vermieteten Objekten | Niedrig |

---

### Ticket: "ImmoCRM - Mieteinnahmen Expose" (Peppermint 2f786257-bc12-4cf7-8403-4cfbb423642e, Freshdesk #139, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht, sondern ein Verbesserungswunsch: "Mieteinnahmen muss der
Kunde im Exposé einsehen können bei vermieteten Objekten." Kein Datensatz, keine Uhrzeit, kein
Absendername im Ticket genannt.

**Kurzbefund (Klassifikation):** Übergreifendes Problem (Feature-Lücke, keine Bug) — die fehlende
Anzeige beträfe strukturell jedes vermietete Objekt, nicht nur einen Einzelfall.

**Eingrenzung:** Frontend · Modul: Exposé-Generator
(`immo-crm/lib/features/properties/expose/expose_pdf_builder.dart`).

Code-Grep-Befund (read-only):
- Mieteinnahmen-Felder existieren im Objektformular: `rentalIncomeActual` ("Mieteinnahmen IST")
  und `rentalIncomeTarget` ("Mieteinnahmen SOLL"),
  `lib/features/properties/models/form_field_config.dart:313-314`.
- In `expose_pdf_builder.dart` kommt weder `rentalIncome` noch "Miete" vor — die Felder werden
  im Exposé-PDF nicht ausgegeben.
- Ein "vermietet"-Status am Objekt selbst fehlt generell (bereits durch früheres Ticket
  `2026-07-08-immocrm-vermietet-button-verkaufsobjekt.md` bestätigt: keine Spalte
  `vermietet`/`tenant_status` in der `properties`-Tabelle) — die Anzeige "bei vermieteten
  Objekten" ließe sich also aktuell nicht sauber bedingen, selbst wenn das Feld ins Exposé
  aufgenommen würde.

**Dringlichkeit:** Niedrig — Randfunktion (Exposé-Layout), kein Datenverlust-/DSGVO-Bezug,
Feature-Wunsch statt Bug, bisher eine Einzelmeldung.

**Antwortentwurf an den Kunden:**
> Vielen Dank für Ihre Rückmeldung. Mieteinnahmen können aktuell im Objektformular hinterlegt
> werden, erscheinen aber noch nicht automatisch im Exposé bei vermieteten Objekten. Wir haben
> das als Verbesserungswunsch aufgenommen und melden uns, sobald die Umsetzung geplant ist.

**Rückfragen-Guidance:** Konkretes Beispielobjekt (ID/Adresse) fehlt; unklar ob IST- oder
SOLL-Miete (oder beide) angezeigt werden soll; unklar ob nur Vermietungsobjekte gemeint sind oder
auch vermietete Verkaufsobjekte (Bezug zum offenen Vermietet/Leerstand-Status-Ticket vom
2026-07-08).
