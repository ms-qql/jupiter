# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #100)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 6f992aa3 (Freshdesk #100) — "Kundenverlauf nicht Vollständig" | Vermutlich Einzelfall: Mail einer bestimmten Absender-Adresse fehlt im Kunden-Verlauf, plausibelste Ursache eine fehlende/nicht-nachgezogene Alias-Zuordnung in einem bekannten Bug-Cluster-Bereich (PROJ-41/PROJ-42) — nicht live geprüft | Mittel |

---

### Ticket: Peppermint-Ticket "Kundenverlauf nicht Vollständig" (Peppermint 6f992aa3-7e9f-4d90-ab40-37959955ea65, Freshdesk #100, Absender: Firat Erol / Erol Immobilien GmbH, adressiert an Manfred)

**Kurzbefund:** Firat Erol berichtet, dass eine am 30.06. von "Anwalt Ulf Grabow" erhaltene Mail
im Kommunikationsverlauf des Kunden "Ulf Grabow Notar" nicht auffindbar ist. Er vermutet selbst
einen Zusammenhang damit, dass unter diesem Kunden zusätzlich zwei weitere Mailadressen von
Mitarbeitern angelegt wurden.

**Eingrenzung:** Backend · Modul: E-Mail↔Kunde-Matching / Kommunikationsverlauf
(`immo-crm`, `backend/app/services/email_service.py`, `client_email_aliases`).

Code-Grep-Befund:
- Eingehende Mails werden per `EmailProcessor.match_client_by_email()`
  (`email_service.py:3064`) gegen die Tabelle `client_email_aliases` gematcht — exakter,
  case-insensitiver Treffer auf `email`. Ist die konkrete Absenderadresse dort nicht als Alias
  hinterlegt, wird die Mail keinem Kunden zugeordnet und taucht folglich nicht im Verlauf auf.
- Mehrere Adressen pro Kunde sind ein explizit gebautes Feature (PROJ-42, deployed 2026-05-26):
  neue Aliase lösen einen **rückwirkenden Rematch** (`client_alias_rematch.py`) aus, der
  historische Mails nachträglich zuordnet — synchron oder als Job, mit Sweeper-Retry.
- Dieser Bereich (Mail↔Kunde-Matching bei mehreren Kontakten/Aliassen pro Kunde) ist laut
  `features/INDEX.md` ein bekannter **Bug-Cluster** (PROJ-41 "Mail↔Kunde-Matching &
  Verlauf-Navigation", PROJ-38 "E-Mail-Verlauf — Anzeige & Cross-User-Sichtbarkeit", On Hold).
- Plausibelste Erklärung ohne Live-Zugriff: Die tatsächliche Absenderadresse von "Ulf Grabow"
  selbst wurde nie als Alias hinterlegt (nur die zwei neu angelegten Mitarbeiter-Adressen) — dann
  ist es Konfigurationslücke/Benutzerfehler, kein Bug. Alternative: Alias wurde hinzugefügt, aber
  der asynchrone Rematch-Job ist fehlgeschlagen oder noch offen — dann wäre es ein Bug im
  PROJ-42-Pfad. Ohne Ticket-Absenderadresse und ohne DB-Einblick lässt sich das nicht
  unterscheiden.
- Notariate/Kanzleien mit mehreren Mitarbeiter-Adressen unter einem Kunden sind im
  Immobilienkontext ein normaler, wiederkehrender Fall — sollte sich der Rematch-Pfad als
  fehlerhaft herausstellen, würde das strukturell jeden Kunden mit mehreren Kontakten treffen.
  Aktuell aber nur ein einzelnes Ticket, daher vorerst als Einzelfall eingestuft, mit Hinweis auf
  den Bug-Cluster-Kontext.

**Dringlichkeit:** Mittel
Betrifft die Kernfunktion Kommunikationsverlauf und wirkt wie ein Datenintegritätsproblem
(Mail einer Anwaltskorrespondenz "verschwindet"), was bei rechtlich relevanter Kommunikation
sensibel ist. Kein bestätigter Datenverlust (Mail liegt vermutlich im System, nur nicht verknüpft)
und kein bestätigt übergreifendes Problem — daher Mittel statt Hoch, mit Empfehlung, bei
Bestätigung eines Rematch-Bugs auf Hoch hochzustufen (Bezug zum offenen Cluster PROJ-41/PROJ-38).

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für den Hinweis. Damit wir die fehlende Mail von Herrn Grabow gezielt finden
> können: Von welcher genauen E-Mail-Adresse kam die Nachricht vom 30.06.? Ist diese Adresse
> bereits unter "Ulf Grabow Notar" als weitere Mailadresse hinterlegt, oder nur die beiden
> zuletzt angelegten Mitarbeiter-Adressen? Wir prüfen das im Anschluss und melden uns mit dem
> Ergebnis.

**Rückfragen-Guidance:**
- Die genaue Absender-Mailadresse der fehlenden Nachricht vom 30.06. (nicht nur der Name
  "Ulf Grabow").
- Ob diese konkrete Adresse bereits unter "Ulf Grabow Notar" als (weiterer) Alias hinterlegt ist,
  oder ob bisher nur die zwei neuen Mitarbeiter-Adressen eingetragen wurden.
- Zeitliche Reihenfolge: wurden die zwei Mitarbeiter-Aliase VOR oder NACH dem 30.06. angelegt
  (relevant für den rückwirkenden Rematch-Zeitpunkt).

---

Nächster Schritt bei Bedarf: nach Klärung der Rückfragen ggf. `/abc-qa` im `immo-crm`-Projekt für
einen gezielten Test des PROJ-42-Rematch-Pfads (Alias hinzufügen → erwartet rückwirkende
Zuordnung), bzw. Bezug zu den offenen Clustern PROJ-38/PROJ-41 herstellen.
