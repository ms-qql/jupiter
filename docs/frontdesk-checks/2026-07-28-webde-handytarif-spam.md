# Frontdesk-Triage — 2026-07-28

Quelle: Peppermint-Ticket-Notification
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 1f3c1cee — "Manfred Schmitz, Ihr 20 GB Handytarif für 6,99 € mtl.¹" | Kein Kunden-Ticket / kein Systemfehler (WEB.DE-Marketing-Newsletter, fehlgeleitet ins Support-System) | Niedrig |
| Peppermint c162fcc0 — "Manfred Schmitz, Ihr 50 GB Handytarif für 9,99 € mtl.¹" | Kein Kunden-Ticket / kein Systemfehler (WEB.DE-Marketing-Newsletter, fehlgeleitet ins Support-System) | Niedrig |

---

### Ticket: Peppermint 1f3c1cee — "Manfred Schmitz, Ihr 20 GB Handytarif..."

**Kurzbefund:** Kein Kunden-Ticket, kein Bug. Absender `neu@mailings.web.de` ist der offizielle
WEB.DE-Newsletter-Versand ("WEB.DE informiert"), Inhalt ist reine Mobilfunk-Tarif-Werbe-HTML-Mail
(Tracking-Links `mailing.web.de/go/...`, Impressum 1&1 Mail & Media GmbH). Kein Bezug zum Immo-CRM,
kein Fehlerbild, kein Anliegen eines Kunden am System. Gleiches Muster wie bereits am 2026-07-17
(siehe [`2026-07-17-webde-lotto-spam.md`](2026-07-17-webde-lotto-spam.md)) — vermutlich weiterhin
eine Weiterleitungsregel oder falsch verknüpfte Postfach-Adresse, die `mailings.web.de`-Mails ins
Peppermint-Ticketsystem statt ins normale Postfach einliefert.

**Eingrenzung:** entfällt (kein App-Fehler).

**Dringlichkeit:** Niedrig
Kein Kernfunktions-, Daten- oder DSGVO-Bezug, kein blockierter Nutzer — reine Fehlzustellung einer
Werbe-Mail ins Ticketsystem.

**Antwortentwurf an den Kunden:**
> Diese Nachricht ist kein Support-Anliegen, sondern ein automatischer Marketing-Newsletter von
> WEB.DE. Wir schließen das Ticket ohne weitere Bearbeitung.

**Rückfragen-Guidance:** Keine Rückfragen an einen "Kunden" nötig, da kein echter Absender mit
Anliegen vorliegt. Da dies bereits das zweite WEB.DE-Newsletter-Ticket in Peppermint ist (nach
2026-07-17), sinnvoll intern zu prüfen und einen Sender-Filter/Blacklist für `mailings.web.de` im
Peppermint-Mail-Ingest zu ergänzen, statt jedes Mal einzeln zu triagieren.

---

### Ticket: Peppermint c162fcc0 — "Manfred Schmitz, Ihr 50 GB Handytarif..."

**Kurzbefund:** Kein Kunden-Ticket, kein Bug. Identisches Muster wie Ticket 1f3c1cee oben, selber
Tag, selber Absender `neu@mailings.web.de` ("WEB.DE informiert"), selbe HTML-Newsletter-Struktur
(nur anderes Tarif-Angebot: 50 GB / 9,99 € statt 20 GB / 6,99 €). Kein Bezug zum Immo-CRM.

**Eingrenzung:** entfällt (kein App-Fehler).

**Dringlichkeit:** Niedrig
Reine Fehlzustellung einer Werbe-Mail ins Ticketsystem, kein Kernfunktions-, Daten- oder
DSGVO-Bezug.

**Antwortentwurf an den Kunden:**
> Diese Nachricht ist kein Support-Anliegen, sondern ein automatischer Marketing-Newsletter von
> WEB.DE. Wir schließen das Ticket ohne weitere Bearbeitung.

**Rückfragen-Guidance:** Keine. Dies ist bereits das dritte WEB.DE-Newsletter-Ticket in Peppermint
(nach 2026-07-17 und dem ersten Ticket heute) — verstärkt den Befund, dass ein Sender-Filter für
`mailings.web.de` im Mail-Ingest fällig ist.
