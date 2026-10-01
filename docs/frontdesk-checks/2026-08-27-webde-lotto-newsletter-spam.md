# Frontdesk-Check — WEB.DE Lotto-Newsletter (Fehlrouting/Spam)

- **Datum:** 2026-08-27
- **Quelle:** Peppermint-Support-Postfach (Ticket-ID 680ac3af-ad85-485e-b2d1-986a151a664b)
- **Hinweis:** Interne Ersteinschätzung (Frontdesk-Triage), kein QA-Ergebnis.

## Gesamtübersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| WEB.DE „informiert"-Newsletter (Postcode Lotterie) im Support-Postfach | Kein Systemfehler (Fehlrouting/Spam) | Niedrig |

---

### Ticket: WEB.DE-Marketing-Newsletter „23 Millionen € Gesamtgewinne" im Support-Postfach gelandet

**Kernfakten:**
- Absender: `neu@mailings.web.de` / „WEB.DE informiert" — Massenversand-Adresse, keine Kundenadresse.
- Inhalt: reiner Werbe-Newsletter (Postcode Lotterie, Magazin-Artikel, Suchtrends, App-Promos). Body enthält es selbst: „automatisch versendete Nachricht", „Eine Antwort auf diese E-Mail ist nicht möglich".
- Kein Anliegen, keine Frage, kein Bezug zum Produkt. Anrede „Herr Schmitz" stammt aus dem WEB.DE-Postfach, nicht aus einem CRM-Kunden.
- Status `needs_support`, Priorität `low` — vom Eingangssystem/Peppermint automatisch vergeben.

**Kurzbefund:** Kein Systemfehler — Fehlrouting: fremder Marketing-Newsletter wird ins Peppermint-Support-Postfach eingesammelt und als Ticket angelegt. Wiederkehrendes Muster (siehe `2026-07-09-webde-newsletter-fehlrouting.md`, `2026-07-17-webde-lotto-spam.md`, `2026-07-28-webde-handytarif-spam.md`, `2026-08-03-webde-onlinespeicher-marketing.md`).

**Eingrenzung:** Kein App-Fehler im Jupiter-Code. Falls überhaupt Handlungsbedarf: Ingest-/Filter-Regeln des Support-Postfachs (Peppermint-Mailbox-Konfiguration), nicht Frontend/Backend/DB von Jupiter.

**Dringlichkeit:** Niedrig — kein Datenverlust, kein blockierter Nutzer, keine DSGVO-Relevanz. Nur Rausch im Ticketstream. Sammelhinweis: Bei anhaltendem Aufkommen lohnt eine Absender-/Domain-Filterregel für `mailings.web.de` bzw. `*@web.de`-Newsletter im Postfach-Ingest.

**Antwortentwurf an den Kunden:**
> Keine Antwort nötig — automatischer Massenversand ohne echtes Anliegen, Absender nimmt keine Antworten entgegen. Ticket ohne Rückmeldung als Spam/kein Anliegen schließen.

**Rückfragen-Guidance:** Keine — Sachverhalt aus dem Rohinhalt eindeutig. Für die Zukunft: solche Absender (`mailings.web.de`, Newsletter-Header wie `X-Template-Info: client=webde`) direkt im Postfach-Filter aussortieren, damit sie gar nicht erst als Ticket erscheinen.
