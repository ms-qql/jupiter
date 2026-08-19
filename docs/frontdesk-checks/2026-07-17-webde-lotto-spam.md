# Frontdesk-Triage — 2026-07-17

Quelle: Peppermint-Ticket-Notification
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint e0577ca6 — "50 Mio. € Super-Jackpot: Jetzt Chance mit 1 € Einsatz sichern!¹" | Kein Kunden-Ticket / kein Systemfehler (WEB.DE-Marketing-Newsletter, fehlgeleitet ins Support-System) | Niedrig |

---

### Ticket: Peppermint e0577ca6 — "50 Mio. € Super-Jackpot..."

**Kurzbefund:** Kein Kunden-Ticket, kein Bug. Absender `neu@mailings.web.de` ist der offizielle
WEB.DE-Newsletter-Versand ("WEB.DE informiert"), Inhalt ist reine Lotto-/Werbe-HTML-Mail
(Tracking-Links `mailing.web.de/go/...`, Impressum 1&1 Mail & Media GmbH). Kein Bezug zum Immo-CRM,
kein Fehlerbild, kein Anliegen eines Kunden am System. Vermutlich landete die Mail über eine
Weiterleitungsregel oder eine falsch verknüpfte Postfach-Adresse im Peppermint-Ticketsystem statt
im normalen Postfach.

**Eingrenzung:** entfällt (kein App-Fehler).

**Dringlichkeit:** Niedrig
Kein Kernfunktions-, Daten- oder DSGVO-Bezug, kein blockierter Nutzer — reine Fehlzustellung einer
Werbe-Mail ins Ticketsystem.

**Antwortentwurf an den Kunden:**
> Diese Nachricht ist kein Support-Anliegen, sondern ein automatischer Marketing-Newsletter von
> WEB.DE. Wir schließen das Ticket ohne weitere Bearbeitung.

**Rückfragen-Guidance:** Keine Rückfragen an einen "Kunden" nötig, da kein echter Absender mit
Anliegen vorliegt. Sinnvoll wäre stattdessen intern zu prüfen, über welche Weiterleitung/Regel
diese Absenderadresse (`mailings.web.de`) überhaupt in Peppermint landet, damit ähnliche
Newsletter-Mails künftig nicht als Tickets erzeugt werden (ggf. Sender-Filter/Blacklist im
Peppermint-Mail-Ingest ergänzen).
