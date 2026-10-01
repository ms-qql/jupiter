# Frontdesk-Check — Immo-CRM: Feature-Wunsch Verlinkung Kunde → Kommunikation

- **Datum des Laufs:** 2026-09-17
- **Quelle:** Peppermint-Ticket `d563f944-c63a-4297-9fa2-697c86aab8ac` (Freshdesk #162), gemeldet von f.erol@erolimmobilien.de
- **Hinweis:** Interne Ersteinschätzung (Frontdesk-Triage), **kein** QA-Ergebnis. Kein Code-Repro möglich — das Jupiter-Repo enthält den Immo-CRM-Code nicht; Einschätzung stützt sich rein auf Ticketinhalt + Domänenlogik.

---

## Gesamtübersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Wunsch: Direktsprung von Kundendatensatz zur zugehörigen Kommunikation (statt erneuter Suche); optional Menüpunkt "Kommunikation" entfernen | Feature-Wunsch (kein Fehler) | Niedrig |

---

### Ticket: Direktverlinkung Kunde → Kommunikation gewünscht

**Kernfakten aus dem Ticket:**
- Melder: f.erol@erolimmobilien.de, Mandant `00000000-0000-0000-0000-000000000001`
- Modul: Kunden
- Beschreibung: Beim Betrachten eines Kunden soll man direkt zur zugehörigen Kommunikation springen können, statt in der Kommunikation erneut nach dem Kunden zu suchen. Zusatzvorschlag: den separaten Menüpunkt "Kommunikation" im linken Navigationsbereich dafür entfernen.
- Erwartetes Verhalten / Zeitpunkt: nicht angegeben (Ticket-Vorlage mit "?????" ausgefüllt)
- Bereits ausprobiert: nichts, da kein Fehler, sondern Wunsch
- Softwareversion: v0.14.13

**Kurzbefund:** Feature-Wunsch (kein Systemfehler). Die App verhält sich nicht falsch — dem Kunden fehlt schlicht eine Navigationsabkürzung, die es laut Ticket noch nicht gibt.

**Eingrenzung:** Schicht: vermutlich Frontend (Navigation/Deep-Link von Kundenansicht zur Kommunikationsansicht) · Modul: Kunden + Kommunikation
Kein Code-Zugriff auf das Immo-CRM-Repo möglich; Eingrenzung rein aus der Beschreibung (reine UI-Verlinkung, kein Datenproblem).

**Dringlichkeit:** Niedrig
Kein Bug, kein Datenrisiko, keine DSGVO-Relevanz, keine Blockade — reine UX-Komfortverbesserung, Umweg (manuelle Suche) existiert bereits.

**Antwortentwurf an den Kunden:**
> Vielen Dank für Ihren Vorschlag! Wir haben Ihre Idee, direkt vom Kundendatensatz zur zugehörigen Kommunikation zu springen, als Verbesserungswunsch aufgenommen und werden sie für eine der nächsten Versionen einplanen. Eine konkrete Umsetzung können wir aktuell noch nicht terminieren, melden uns aber, sobald es Neuigkeiten gibt.

**Rückfragen-Guidance:**
- Konkretes Beispiel/Screenshot, wie der Sprung idealerweise aussehen soll (z. B. Button/Tab direkt im Kundendatensatz vs. automatischer Filter in der Kommunikationsansicht)
- Klärung, ob der Menüpunkt "Kommunikation" komplett entfernt werden soll oder nur als Zusatz-Idee gemeint war (das würde auch Zugriff auf Kommunikation ohne Kundenbezug betreffen — eigene Anforderung, nicht Teil dieses Wunsches)
- Da es sich um eine Anforderung statt einen Bug handelt: geeigneter nächster Schritt ist `/abc-requirements` (Feature-Spec) statt weiterer Bug-Triage.
