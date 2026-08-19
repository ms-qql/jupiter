# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #72)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint aabfd7a5-a6a4-4ca2-b205-5d0c70c7336d (Freshdesk #72) — "Adressfeld im Exposé" | Übergreifendes Problem (CSS-Zeilenumbruch im PDF-Footer) | Niedrig |

---

### Ticket: "Adressfeld im Exposé" (Peppermint aabfd7a5-a6a4-4ca2-b205-5d0c70c7336d, Freshdesk #72, Absender: Firat Erol / Erol Immobilien GmbH)

**Kernaussage des Kunden:** "Im Exposé unten steht ja immer unsere Adresse. Da ein Absatz
[Zeilenumbruch] wischen [zwischen] der Straße und der Hausnummer." Kein Datum, kein konkretes
Objekt genannt, kein Screenshot — die Meldung bezieht sich offenbar auf die Fußzeile des
PDF-Exposés generell, nicht auf einen einzelnen Datensatz.

**Kurzbefund:** Vermutlich echter Anzeigefehler, keine Fehlbedienung. Code-Grep (im separaten
Projekt `immo-crm`, dort liegt der Exposé-Code — `jupiter` selbst enthält keinen Exposé-Code) zeigt
eine plausible technische Ursache für genau dieses Symptom.

**Eingrenzung:** Backend/Template (Jinja2 + CSS, serverseitiges PDF-Rendering via WeasyPrint) ·
Modul: Exposé-PDF-Export, Projekt `immo-crm` (nicht `jupiter`).
Code-Grep-Befund:
- `backend/app/templates/expose_pdf.html:420` — die Firmenzeile im Footer wird aus einem einzigen
  Freitextfeld `company.street` zusammengesetzt (z. B. "Dorfstraße 90", Straße+Hausnummer bereits
  ein String, kein separates Feld, kein eingebettetes `\n`, kein `<br>`).
- `expose_pdf.html`, CSS-Klasse `.running-footer-info` (~Zeile 68): **leere Regel `{}`** — im
  Gegensatz zu `.running-footer-page` daneben, die explizit `white-space: nowrap` gesetzt hat.
- Der Footer ist ein Flex-Container (`justify-content: space-between`); wird die Firmenzeile zu
  lang für die verbleibende Breite, bricht WeasyPrint am nächsten Whitespace um — das ist bei
  "Straße Hausnummer" meist genau die Lücke vor der Zahl, weil das der letzte Space vor dem
  Zeilenende ist.
- Kein separates Feld für Hausnummer vorhanden (`lib/features/administration/company_settings_section.dart:240`,
  ein einzeiliges `TextFormField` für die komplette Adresse) — ein Fix müsste also am
  CSS/Layout ansetzen (z. B. gezieltes `white-space: nowrap` auf Straße+Hausnummer statt auf die
  ganze, potenziell lange Firmenzeile), nicht am Datenmodell.

**Warum übergreifend statt Einzelfall:** Die auslösende Vorbedingung ("Firmenname + Adresse in der
Fußzeile wird bei der aktuellen Fensterbreite zu lang") ist rein layoutbedingt und unabhängig vom
konkreten Kunden — jeder Mandant mit einer etwas längeren Firmenzeile in den Kontaktdaten würde
denselben zufälligen Umbruch bekommen. Es handelt sich um ein bislang nicht gemeldetes,
strukturelles CSS-Problem, nicht um einen kaputten Einzeldatensatz.

**Bekanntes Cluster:** Kein bestehender Feature-/Bug-Eintrag zu diesem konkreten Zeilenumbruch
gefunden (weder in `immo-crm/features/INDEX.md` noch in den bisherigen Frontdesk-Checks). Verwandt,
aber inhaltlich anders, ist `docs/frontdesk-checks/2026-07-08-expose-adresse-default.md`
(Freshdesk #106 — dort ging es um den Anzeige-Default `show_address`, nicht um den Zeilenumbruch).

**Dringlichkeit:** Niedrig
Begründung: rein kosmetisches Layout-Problem in der PDF-Fußzeile, keine Kernfunktion betroffen,
kein Datenverlust-/Datenintegritätsrisiko, keine DSGVO-Relevanz, Kunde nicht blockiert (Exposé ist
weiterhin nutzbar, nur optisch unschön). Freshdesk-Priorität "low" passt dazu.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für den Hinweis. Wir haben uns die Fußzeile im Exposé angesehen: Der Zeilenumbruch
> zwischen Straße und Hausnummer entsteht durch die automatische Textumbruch-Logik, wenn die
> Firmenzeile für die verfügbare Breite zu lang wird — kein Einzelfall, sondern ein
> layoutbedingtes Verhalten, das wir beheben werden, damit Straße und Hausnummer immer
> zusammenbleiben. Wir melden uns, sobald die Anpassung umgesetzt ist.

**Rückfragen-Guidance:** Kein Screenshot beigefügt und kein konkretes Objekt/Exposé genannt, an
dem der Kunde den Umbruch gesehen hat. Für die Umsetzung nicht zwingend nötig (Ursache ist über
Code-Grep klar erkennbar), aber ein Screenshot würde helfen, schnell zu bestätigen, dass es sich
um exakt dieses CSS-Wrap-Verhalten handelt und nicht um eine Sonderkonstellation (z. B. sehr langer
Firmenname bei einem bestimmten Mandanten-Branding).

---

Nächster Schritt bei Bedarf: kleiner CSS-Fix im `immo-crm`-Projekt
(`backend/app/templates/expose_pdf.html`, `.running-footer-info` bzw. gezieltes `nowrap` um
Straße+Hausnummer) — Bugfix-Ticket, kein neues Feature. Da der Code in `immo-crm` liegt, nicht in
`jupiter`, müsste der Fix dort eingeplant werden.
