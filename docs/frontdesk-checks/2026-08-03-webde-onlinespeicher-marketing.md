# Frontdesk-Check — 2026-08-03

Quelle: Peppermint-Ticket a06f3cfb-0aae-487b-983a-58caebcb5c0a (needs_support, low)
Hinweis: interne Ersteinschätzung, kein QA-Ergebnis.

## Ticket: "Ihr kostenloser, sicherer Online-Speicher – schon entdeckt?" (WEB.DE Marketing-Mail)

**Kurzbefund:** Kein Systemfehler. Absender `neu@mailings.web.de` — automatisierte WEB.DE-Werbe-Mail (Cloud-Speicher-Promo) an "Herrn Schmitz", hat nix mit Immo-CRM zu tun. Landete nur im Support-Postfach/Peppermint, kein echtes Kundenanliegen.

**Eingrenzung:** entfällt (kein App-Fehler, keine Modul-Zuordnung nötig).

**Dringlichkeit:** Niedrig
Kein Kernfunktions-, Daten- oder DSGVO-Bezug zu unserem System; reine Fehlzustellung ins Ticketsystem.

**Antwortentwurf an den Kunden:**
> Diese Mail beantworten wir nicht — sie kommt automatisiert von WEB.DE (Absender `mailings.web.de`) und betrifft nicht unser System. Ticket kann geschlossen/ignoriert werden.

**Rückfragen-Guidance:** Keine — Fall ist eindeutig. Ggf. prüfen, ob Peppermint-Mail-Ingest versehentlich Werbe-Mails von `mailings.web.de` aufnimmt, und dort ausfiltern, falls das öfter passiert.
