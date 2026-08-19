# Frontdesk-Triage — 2026-08-11

Quelle: Peppermint-Ticket-Notification (Auxevo Support/Freshdesk-Weiterleitung, Ticket #144)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint afd5eaae (Freshdesk #144) — "Signatur erscheint nach zitierter Kundenmail statt direkt nach dem Antworttext" | Übergreifendes Problem | Niedrig |

---

### Ticket: Reihenfolge in Antwort-Mails — Signatur landet nach der zitierten Original-Mail statt direkt danach

**Kurzbefund:** Übergreifendes Problem. Beim Antworten (Reply/ReplyAll) auf eine Kunden-Mail
erscheint nach dem eigenen Antworttext ("... mit freundlichen Grüßen") zunächst nochmal die
zitierte Original-Mail des Kunden, und erst danach die eigene Signatur — statt Text → Signatur →
Zitat.

**Eingrenzung:** Frontend · Modul E-Mail/Kommunikation (Compose-Reply)
`lib/features/email/email_screen.dart:1414-1449` (Projekt `immo-crm`, nicht Jupiter). Beim
Reply/ReplyAll/Forward wird `_composeBody.text` als fester String
`$sigBlock\n\n--- Ursprüngliche Nachricht ---\n...\n\n$quoteText` gesetzt (Signatur-Block bereits
vor dem Zitat verklebt) — anders als beim "neue E-Mail"-Pfad (Zeile 1380f.), der den Cursor
explizit auf Offset 0 setzt, damit der Text vor der Signatur landet. Für Reply/Forward fehlt diese
explizite `TextSelection`-Positionierung; der Standard-Cursor von `TextEditingController` springt
nach dem Setzen von `.text` ans Ende. Tippt der Makler dort weiter, entsteht die vom Kunden
beschriebene Reihenfolge (Text zuerst getippt, Signatur+Zitat als vorbefüllter Block dahinter,
wobei die interne Reihenfolge Signatur-vor-Zitat nicht der erwarteten Text→Signatur→Zitat-Anzeige
entspricht). Strukturell bei jedem Reply/ReplyAll/Forward reproduzierbar, kein Einzeldatensatz-Fall
— daher übergreifend. Verwandt, aber nicht identisch mit dem bereits dokumentierten
Signatur-Namensduplikations-Ticket (`2026-07-08-immocrm-signatur-bild-doppelter-name.md`), das
denselben Compose-/Signatur-Mechanismus betrifft, aber ein anderes Symptom (Doppelname statt
Reihenfolge).

**Dringlichkeit:** Niedrig
Rein kosmetisch/Wahrnehmungsfrage, kein Datenverlust-, DSGVO- oder Blockade-Risiko — Mail geht
weiterhin korrekt raus, nur die optische Abfolge im Reply-Editor wirkt verwirrend. Deckt sich mit
der von Freshdesk gesetzten Priorität "low".

**Antwortentwurf an den Kunden:**
> Hallo,
>
> vielen Dank für den Hinweis. Wir haben uns die Reihenfolge im Antwort-Editor angeschaut — das
> Verhalten ist reproduzierbar und wird als Verbesserung eingeplant, damit Ihre Signatur künftig
> direkt nach Ihrem Antworttext erscheint und die zitierte Original-Mail erst danach. Eine
> Rückmeldung, sobald die Anpassung umgesetzt ist, folgt.
>
> Mit freundlichen Grüßen

**Rückfragen-Guidance:** Kein Reproduktions-Screenshot vorhanden — hilfreich wäre ein Screenshot
des Reply-Editors direkt nach dem Öffnen (vor dem Tippen) sowie einer, nachdem der Kollege
geantwortet hat, um zu verifizieren, ob Ursache tatsächlich die Cursor-Position ist oder der
Kollege selbst manuell umsortiert. Kein Live-Check durchgeführt (nur Code-Analyse).
