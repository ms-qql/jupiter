# Frontdesk-Triage — 2026-07-10

Quelle: Peppermint-Ticket-Notification
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint ce1a55c6 — "Immo CRM Mail erneut senden" (Firat Erol, Erol Immobilien) | Feature-Wunsch, kein Fehler — "Nachricht erneut senden"-Funktion für bereits gesendete E-Mails existiert nicht | Niedrig |

---

### Ticket: Peppermint-Ticket "Immo CRM Mail erneut senden" (Peppermint ce1a55c6-1d67-4949-9ef8-cfa4b58ae87a, Absender: Firat Erol, Erol Immobilien GmbH, via Auxevo/Freshdesk)

**Kurzbefund:** Kein Systemfehler. Der Kunde (Firat Erol, Erol Immobilien) wünscht sich eine neue
Funktion im E-Mail-Modul von ImmoCRM: Bei einer bereits versendeten Mail soll man über eine
Leiste/Toolbar "Nachricht erneut senden" anklicken können — mit der Möglichkeit, die Nachricht vor
dem erneuten Versand noch zu bearbeiten oder einen vergessenen Anhang nachträglich hinzuzufügen.
Das ist eine funktionale Erweiterung, kein Fehlverhalten der bestehenden App.

**Eingrenzung:** Schicht: Frontend · Modul: E-Mail-Client/Composer (`immo-crm/lib/features/email/email_screen.dart`)
Code-Grep im Composer-Toolbar-Bereich (Zeilen ~3109–3111, ~3868–3870) zeigt aktuell nur die
Aktionen "Antworten", "Allen Antworten" und "Weiterleiten" für eine geöffnete Mail — keine
"Erneut senden"/"Bearbeiten & erneut senden"-Aktion für bereits gesendete Nachrichten. Damit ist
bestätigt: Die gewünschte Funktion fehlt tatsächlich, es handelt sich nicht um eine
Bedienungslücke beim Kunden.

**Dringlichkeit:** Niedrig
Randfunktion (kein Kernfunktions-, Daten- oder DSGVO-Bezug), kein Kunde blockiert — ein
Workaround existiert bereits über "Weiterleiten" (öffnet einen editierbaren Composer mit
Anhängen der Originalmail, an den man die Empfängeradresse erneut eintragen kann). Peppermint
selbst hat das Ticket bereits mit Priorität "low" eingestuft, was zur Einschätzung passt.

**Antwortentwurf an den Kunden:**
> Guten Tag Herr Erol,
>
> vielen Dank für Ihren Vorschlag. Aktuell gibt es im E-Mail-Bereich die Funktionen "Antworten",
> "Allen antworten" und "Weiterleiten" — eine direkte "Erneut senden"-Funktion für bereits
> versendete Nachrichten mit Bearbeiten-Möglichkeit gibt es noch nicht.
>
> Als kurzfristigen Workaround können Sie die gesendete Mail über "Weiterleiten" öffnen: Der Text
> und eventuell vorhandene Anhänge werden übernommen, Sie können Inhalt und Anhänge anpassen und
> müssen lediglich den ursprünglichen Empfänger erneut eintragen.
>
> Ihren Wunsch nach einer echten "Erneut senden"-Funktion nehmen wir gerne als Feature-Vorschlag
> für eine künftige Erweiterung auf.

**Rückfragen-Guidance:** Keine zwingend offenen Informationen für die Einstufung selbst — der
Wunsch ist klar beschrieben. Für eine spätere Priorisierung wäre hilfreich zu wissen, wie oft
diese Situation (vergessener Anhang / Korrektur nach dem Senden) bei Herrn Erol vorkommt, ist aber
keine Voraussetzung, um das Ticket korrekt einzuordnen.

---

Nächster Schritt bei Bedarf: Kein `/abc-qa` nötig (kein Bug). Falls der Wunsch priorisiert werden
soll, gehört er als neues Feature über `/abc-requirements` in `immo-crm/features/INDEX.md`
(z. B. im Bereich E-Mail-Client, ähnlich den bestehenden Composer-Erweiterungen PROJ-67/PROJ-82).
