# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #91)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint d870614d (Freshdesk #91) — "Bei Mietobjekten bitte Kalt oder Warmmiete einfügen" | Berechtigte, per Code-Grep bestätigte Feature-Lücke: Mietsumme in Immobilien-Übersicht/Kachel zeigt nur "€X/Monat" ohne Kalt-/Warmmiete-Label | Niedrig-Mittel |

---

### Ticket: Peppermint-Ticket "Bei Mietobjekten bitte Kalt oder Warmmiete einfügen" (Peppermint d870614d-076c-4692-92b7-4726caa2755e, Freshdesk #91, Absenderin: Beata Rutkowska / Erol Immobilien GmbH, zugewiesen an "Pepper Mint")

**Kurzbefund:** Kein Fehlerbericht, sondern ein konkreter, gut lesbarer Verbesserungswunsch:
"Bei Mietobjekten auf der ersten Seite wo man die Summe der Miete sieht, muss entweder kalt oder
warmmiete steht". Kein Datum, kein konkreter Datensatz nötig — die Anfrage bezieht sich auf die
allgemeine Anzeige-Logik, nicht auf einen Einzelfall.

**Eingrenzung:** Frontend · Modul: Immobilien-Übersicht/-Kachel
(`immo-crm`, `lib/features/properties/property_list_screen.dart`).

Code-Grep-Befund:
- `_formatPrice()` (Zeile 56–65) rendert die Mietsumme als reinen Betrag mit Suffix `/Monat`
  (z. B. "€1.200/Monat") — ohne Hinweis, ob es sich um Kalt- oder Warmmiete handelt. Wird an
  zwei Stellen verwendet (Zeile 593 und 1070), also sowohl in der Listen- als auch in der
  Kachel-/Detail-Kopfzeile.
- Die zugrunde liegenden Formularfelder unterscheiden Kalt-/Warmmiete durchaus: für
  Wohn-Mietobjekte trägt `price_value`/`priceValue` selbst das Label "Kaltmiete"
  (`lib/features/properties/models/form_field_config.dart:288`); für Gewerbe-Mietobjekte gibt es
  getrennt `baseRent` ("Kaltmiete") und `totalRent` ("Warmmiete", Zeile 295–296). Das Exposé-PDF
  (`backend/app/routes/expose.py:897,903`) beschriftet beide Werte bereits korrekt mit "Kaltmiete"
  bzw. "Warmmiete".
- Die Übersicht zeigt also faktisch (bei Wohnobjekten) die Kaltmiete, aber ohne das Wort
  "Kaltmiete" davorzusetzen — dadurch entsteht bei Betrachtung der Kachel der Eindruck, es sei
  unklar, welcher Mietbetrag gemeint ist. Kein Datenfehler, reine Anzeige-Lücke.
- Betrifft strukturell **jedes** Mietobjekt in der Übersicht (Wohnen wie Gewerbe), nicht nur den
  meldenden Datensatz — daher trotz "Einzeltickets" mit übergreifender Reichweite einzustufen,
  auch wenn keine Datenintegrität oder Kernfunktion blockiert ist.

**Dringlichkeit:** Niedrig-Mittel
Freshdesk hat "low" gesetzt, was zum Charakter passt: keine Blockade, kein Datenrisiko, kein
DSGVO-Bezug, Workaround vorhanden (Klick ins Bearbeiten-Formular zeigt das korrekte Label). Der
Grund für "Mittel" statt reinem "Niedrig": In der Immobilienbranche ist der Unterschied
Kalt-/Warmmiete geschäftlich relevant (Vergleichbarkeit, Kundenkommunikation) und die Lücke
betrifft die am häufigsten gesehene Ansicht (Übersichtsliste) für jedes einzelne Mietobjekt.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für den Hinweis, das ist nachvollziehbar. Aktuell wird in der Immobilien-Übersicht
> bei Mietobjekten nur der Betrag angezeigt (z. B. "1.200 €/Monat"), ohne dazuzuschreiben, ob es
> sich um die Kalt- oder Warmmiete handelt — bei Wohnobjekten ist es aktuell die Kaltmiete. Wir
> nehmen das als kleine Verbesserung für die Anzeige auf und melden uns, sobald sie umgesetzt ist.

**Rückfragen-Guidance:** Keine notwendig für die Einstufung — das Ticket ist klar genug, um es
direkt als Frontend-Anzeige-Verbesserung umzusetzen. Für die Umsetzung selbst wäre höchstens zu
klären, ob das Label immer ausgeschrieben ("Kaltmiete: 1.200 €/Monat") oder platzsparend als
Kürzel/Tooltip in der Kachel erscheinen soll — das ist aber eine Umsetzungsdetail-Frage für
`/abc-requirements`, keine fehlende Information für diese Triage.

---

Nächster Schritt bei Bedarf: `/abc-requirements` im `immo-crm`-Projekt für eine kleine Frontend-Spec
("Kalt-/Warmmiete-Label in Immobilien-Übersicht") — kein Bug-Fix, sondern regulärer Feature-Weg.
