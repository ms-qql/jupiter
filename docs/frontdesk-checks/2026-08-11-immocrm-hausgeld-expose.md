# Frontdesk-Check — 2026-08-11

Quelle: Peppermint-Ticket-Zuweisung (Auxevo Support <support@auxevo.freshdesk.com>), Freshdesk #138.
Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 1b4a73f1 (Freshdesk #138) — "Hausgeld muss im Exposé zusehen sein" | Kein Bug — bereits bekannter Feature-Wunsch (Duplikat von Freshdesk #87) | Niedrig |

---

### Ticket: Peppermint-Ticket "Hausgeld muss im Exposé zusehen sein" (Peppermint 1b4a73f1-770a-4198-942a-04c6fb1dd875, Freshdesk #138)

**Kurzbefund:** Kein Systemfehler. Die Nachricht ist nur eine automatische Zuweisungs-Mail ohne
eigenen Fließtext ("Hausgeld muss im Exposé zusehen sein") — kein Kundenname, kein Datensatz
genannt. Inhaltlich identisch mit dem bereits behandelten Ticket Freshdesk #87
(`docs/frontdesk-checks/2026-07-08-immocrm-expose-mailtext.md`, Kunde Beata Rutkowska / Erol
Immobilien GmbH): fehlendes Hausgeld-Feld im Kaufobjekt-Formular, wodurch es im Exposé nicht
erscheinen kann.

**Eingrenzung:** Frontend · Modul: Objektverwaltung/Formular
(`immo-crm`, `lib/features/properties/models/form_field_config.dart::_getPriceGroup`).

Code-Grep-Befund (erneut geprüft, 2026-08-11): `grep -rn "hausgeld" --include="*.dart"` liefert
weiterhin keinen Treffer — das Feld wurde seit dem #87-Check nicht ergänzt, die Lücke besteht
unverändert. Kein neuer Feature-Eintrag in `features/INDEX.md`. Übergreifend (struktureller
Formular-Lücke im Kauf-Zweig für alle Objekttypen), kein Einzelfall — wie bereits im #87-Report
begründet.

**Dringlichkeit:** Niedrig
Freshdesk hat "low" gesetzt; unveränderte Einschätzung aus #87 — reine Formular-/Exposé-Erweiterung
ohne Kernfunktions-, Daten- oder DSGVO-Bezug, Workaround (Freitext-/Beschreibungsfeld) vorhanden.

**Antwortentwurf an den Kunden:**
> Hallo,
>
> vielen Dank für Ihre Nachricht. Dieser Wunsch — ein eigenes Hausgeld-Feld für Kaufobjekte im
> Exposé — liegt uns bereits vor und ist bei uns als kleine Erweiterung vorgemerkt. Aktuell lässt
> sich das Hausgeld übergangsweise über die freie Objektbeschreibung im Exposé ergänzen, zum
> Beispiel im Ausstattungs- oder Beschreibungstext.
>
> Wir melden uns, sobald wir mehr dazu sagen können.

**Rückfragen-Guidance:** Ticket #138 enthält keinen eigenen Text (nur die Betreffzeile), keinen
Kundennamen und keinen Objektbezug — unklar, ob es sich um dieselbe Person wie bei #87 handelt oder
um eine zweite, unabhängige Meldung desselben Wunsches. Für eine saubere Zusammenführung wäre
hilfreich: Kundenname/Firma, betroffenes Objekt, und ob #138 versehentlich doppelt zugewiesen wurde
(z. B. Freshdesk-Merge von #87 und #138 prüfen).

---

Nächster Schritt bei Bedarf: Kein neuer Aufwand nötig — Duplikat von #87. Falls Umsetzung gewünscht:
`/abc-requirements` für ein Hausgeld-Feld im Kauf-Zweig von `form_field_config.dart::_getPriceGroup`
+ Anzeige in `expose_pdf_builder.dart` / `expose_generator_screen.dart`. Empfehlung: #138 in
Freshdesk mit #87 zusammenführen/verlinken statt getrennt zu bearbeiten.
