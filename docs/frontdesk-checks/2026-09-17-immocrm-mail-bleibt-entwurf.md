# Frontdesk-Check — 2026-09-17

**Quelle:** Peppermint-Ticket (Freshdesk #163, Peppermint-ID 62c47e28-ff82-469a-a19c-1a9d3b501745), weitergeleitet über Auxevo Support.
Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Mail an Hagen Koop verschickt, bleibt zusätzlich als Entwurf sichtbar | Übergreifendes Problem (unverifiziert) | Mittel |

---

### Ticket: E-Mail an Kunde Hagen Koop wurde verschickt, ist aber weiterhin in "Entwürfe" sichtbar

**Kurzbefund:** Übergreifendes Problem (unverifiziert — Reproduktion nicht möglich, siehe unten)

**Eingrenzung:** Schicht: Backend/Frontend (unklar, welche) · Modul: Kommunikation / E-Mail-Verlauf (Immo-CRM-Repo, nicht Jupiter)
Kein Code-Zugriff auf das Immo-CRM-Repo aus dieser Jupiter-Session heraus möglich (geprüft: `backend/app/routes/expose.py` und die Kunden-/Kommunikations-Domäne existieren hier nicht — Jupiter ist die separate Agenten-Cockpit-Codebasis). Einschätzung stützt sich daher nur auf frühere Frontdesk-Checks zum selben Modul:
- Bekannter, verwandter Fund vom 2026-07-08 (`2026-07-08-immocrm-mailverlauf-kein-autorefresh.md`): der Kunden-Mailverlauf (`clients_mailview`/`KundenNeuNotifier`) cached Nachrichten pro Kunde und gleicht nur bei erneutem Öffnen/F5 ab, nicht live — eine bewusste PROJ-91-Scope-Entscheidung. Ein plausibler, aber unbestätigter Mechanismus für dieses Ticket: Falls der Compose-Screen einen Entwurf automatisch zwischenspeichert und beim Senden dieser Entwurfs-Datensatz nicht als "gesendet" markiert bzw. gelöscht wird, bliebe er im gecachten Verlauf sichtbar, bis der Kunde neu geöffnet/reloaded wird.
- Kein bestehender Bug-Cluster in `features/INDEX.md` (dortige PROJ-Nummern gehören zu Jupiter-eigenen Features, nicht zum Immo-CRM) mit exaktem Treffer zu "Entwurf bleibt nach Versand bestehen" gefunden.
- **Nicht live geprüft** — weder Code noch Produktivdaten des Immo-CRM standen dieser Session zur Verfügung. Diese Eingrenzung ist eine begründete Vermutung, kein bestätigter Befund.

**Dringlichkeit:** Mittel
Kernfunktion Kommunikation betroffen, aber kein Datenverlust (Mail ist laut Melder tatsächlich rausgegangen) und kein Blocker (Mitarbeiter kann weiterarbeiten) — nur eine verwirrende Doppel-Anzeige. Falls sich beim Nachfassen bestätigt, dass der Mechanismus strukturell jeden Versand betrifft (nicht nur diesen Kunden), wäre eine Hochstufung zu erwägen.

**Antwortentwurf an den Kunden:**
> Guten Tag,
>
> vielen Dank für Ihre Meldung. Die E-Mail an Herrn Koop ist laut Ihrer Beschreibung tatsächlich versendet worden — dass sie zusätzlich noch unter "Entwürfe" angezeigt wird, deutet auf einen Anzeigefehler im System hin, nicht auf einen doppelten Versand. Wir prüfen die Ursache. Bitte prüfen Sie zur Sicherheit kurz, ob die Mail auch nach einem Neuladen der Seite (F5) noch unter "Entwürfe" auftaucht, und teilen Sie uns das Ergebnis mit — das hilft uns bei der Eingrenzung. Wir melden uns mit dem Ergebnis.
>
> Freundliche Grüße
> Ihr Support-Team

**Rückfragen-Guidance:**
- Bleibt der Entwurf-Eintrag auch nach einem Seiten-Reload (F5) bzw. erneutem Öffnen des Kunden Hagen Koop sichtbar, oder verschwindet er dann? (Unterscheidet reinen Anzeige-Cache-Fehler von einem echten, persistierten Doppel-Datensatz.)
- Exakte Uhrzeit des Vorfalls.
- Wurde vor dem Senden der Entwurf zwischengespeichert (z. B. Seite verlassen und zurückgekehrt) oder in einem Zug geschrieben und direkt gesendet?
- Ist das Verhalten bei einer weiteren Testmail reproduzierbar?
- Screenshot des Entwürfe-Eintrags wäre hilfreich zur Verifikation.

---

**Hinweis:** Diese Einschätzung beruht ausschließlich auf früheren Frontdesk-Check-Dokumenten zum selben Modul, nicht auf direkter Code-Prüfung — das Immo-CRM-Repo lag dieser Jupiter-Session nicht vor. Bei Bestätigung als strukturelles Problem: `/abc-qa` im Immo-CRM-Repo für vollständige Prüfung des Compose-/Send-Flows.
