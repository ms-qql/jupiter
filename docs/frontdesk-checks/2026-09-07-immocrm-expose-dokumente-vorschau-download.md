# Frontdesk-Check — Immo CRM: Exposé unter „Dokumente" öffnet Download statt Vorschau

- **Datum Analyse-Lauf:** 2026-09-07
- **Quelle:** Peppermint-Ticket `192dbb22-ee05-441d-ae41-dd8aa20137e4` (Freshdesk #158, „[Immo CRM Support] Kunden: IMMO CRM"), gemeldet von Beata Rutkowska / erolimmobilien.de über Auxevo Support
- **Hinweis:** Interne Ersteinschätzung (Frontdesk-Triage), **kein QA-Ergebnis**. Immo-CRM-Code liegt nicht in diesem Repo → Einordnung rein aus Ticket-Verlauf, nicht live geprüft.

---

## Gesamtübersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| #158 Exposé-Vorschau erzwingt Download | Übergreifendes Problem — **bereits behoben (v0.14.3) und vom Kunden bestätigt** | Niedrig |

---

### Ticket: Exposé unter „Kunde → Dokumente" öffnete sich als Download statt als Vorschau

**Kurzbefund:** Übergreifendes Problem — inzwischen erledigt.
Ursprüngliche Meldung (v0.14.2): In der Kundenansicht rechts unter „Dokumente" das angefragte
Exposé; Klick darauf öffnete keine Vorschau, sondern lud die Datei jedes Mal neu herunter. Der
Auslöser (Vorschau-Klick auf ein Exposé-Dokument) ist kein Sonderfall, sondern Standard-Bedienung
für jeden Kunden → übergreifend. Fix in v0.14.3 ausgeliefert; Support hat verifiziert
(„Bei mir geht es einwandfrei"), Kundin hat am 27.08.2026 bestätigt: „Super, funktioniert. Danke".
Das Peppermint-/Freshdesk-Ticket wurde nur durch diesen Dank-Kommentar automatisch re-opened —
kein neuer Fehler.

**Eingrenzung** (App-Fehler, historisch): Schicht: Frontend ↔ Backend-Grenze · Modul: Kunden →
Dokumente/Exposé-Anzeige.
Typisches Muster für „Download statt Vorschau": `Content-Disposition: attachment` statt `inline`
in der Datei-/Presigned-URL-Antwort bzw. Frontend öffnet den Blob als Download statt im
PDF-Viewer/Tab. Genaue Ursache nicht weiter verfolgt, da bereits gefixt.

**Dringlichkeit:** Niedrig.
Randfunktion (Komfort-Vorschau), kein Daten- oder DSGVO-Risiko, Umweg (Download) war vorhanden.
Zudem bereits in Produktion behoben und vom Kunden bestätigt — keine offene Arbeit.

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für die Rückmeldung — schön, dass die Exposé-Vorschau in der Kundenansicht jetzt
> wie erwartet funktioniert. Wir betrachten das Anliegen damit als erledigt und schließen das
> Ticket. Falls das Verhalten doch noch einmal auftritt, melden Sie sich gern jederzeit wieder.
>
> Viele Grüße
> Ihr Auxevo-Support-Team

**Rückfragen-Guidance:** Keine — Ticket ist durch die Kundenbestätigung abgeschlossen. Für die
Zukunft nützlich, falls ein ähnlicher Vorschau-/Download-Fall neu aufkommt: betroffene
Software-Version, Browser/Client, ob der Effekt bei allen Dokumenten oder nur bei bestimmten
Exposés auftritt, und ein kurzer Screenshot des „Dokumente"-Bereichs.
