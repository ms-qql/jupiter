# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung), automatisch
angestoßen (PROJ-67/PROJ-68 Frontdesk-Triage).
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 1a1990b8 (Freshdesk #71) — "Link einbauen für Freigabe an den Eigentümer zu versenden" | Benutzerfehler / fehlende Bedienkenntnis — die beschriebene Funktion existiert bereits vollständig | Niedrig |

---

### Ticket: Peppermint-Ticket "Link einbauen für Freigabe an den Eigentümer zu versenden" (Peppermint 1a1990b8-c2d9-444d-a696-28678d9e29ca, Freshdesk #71, Absender: Firat Erol / Erol Immobilien GmbH)

**Kurzbefund:** Kein Systemfehler. Der Absender beschreibt den gewünschten Ablauf (Vorlage mit
Exposé-Link-Platzhalter, Objekt + Kunde über eine Suchleiste auswählen, Link wird automatisch für
das gewählte Objekt eingesetzt, Kunde erhält Standardtext mit Bitte um Freigabe/Änderungswünsche,
Klick öffnet das Exposé) — genau dieser Ablauf existiert im `immo-crm`-Projekt bereits vollständig
und funktionsfähig.

**Eingrenzung:** Kein Fehler in einer bestimmten Schicht — Bedienhinweis. Betroffenes Modul:
Nachrichten/Kommunikation (`immo-crm`).

Code-Grep-Befund (`/home/dev/projects/immo-crm`):
- Der beschriebene Ablauf ist als Dialog "Neue Nachricht" umgesetzt
  (`lib/features/messages/widgets/new_conversation_dialog.dart`): durchsuchbare Auswahlfelder für
  "Kunde" und "Immobilie", danach Button "Vorlage" öffnet den
  `TemplatePickerDialog` (`lib/features/messages/widgets/template_picker_dialog.dart`) mit
  `clientId`/`propertyId` aus der Auswahl.
- Es existiert bereits eine passende, vorbereitete Vorlage "Exposé-Vorschlag zur Freigabe"
  (`backend/app/seed_templates.py:238-262`, Betreff "Exposé-Entwurf für {Objektname} – Bitte um
  Ihre Freigabe", Text u. a. mit Bitte um Prüfung/Freigabe/Änderungswünsche — inhaltlich praktisch
  identisch zu dem im Ticket gewünschten Standardtext).
- Beim Rendern der Vorlage (`POST /templates/{id}/render`, `backend/app/routes/templates.py:200-225`)
  wird `{ExposéLink}` korrekt **pro ausgewähltem Objekt** aus dessen `public_token` gebaut
  (`context["ExposéLink"] = f"{base_url}/{slug}/expose/{public_token}"`), nicht als fixer
  Platzhalter — genau das vom Kunden gewünschte automatische Übernehmen des Links.

**Caveat (Nebenbefund, nicht Kern des Tickets):** Wird dieselbe Vorlage stattdessen direkt aus dem
allgemeinen E-Mail-Postfach heraus geöffnet (`lib/features/messages/email_screen.dart:1589`,
`TemplatePickerDialog` dort **ohne** `clientId`/`propertyId`), lässt sich `{ExposéLink}` nicht
auflösen. Sollte der Absender genau darüber gestolpert sein, wäre der Hinweis "über 'Neue
Nachricht' statt aus dem Postfach heraus starten" die Lösung — das lässt sich aus dem Ticket allein
nicht sicher unterscheiden.

**Dringlichkeit:** Niedrig
Freshdesk hat bereits "low" gesetzt; kein Kernfunktions-, Daten- oder DSGVO-Bezug; die Funktion
existiert und funktioniert bereits, niemand ist blockiert — es fehlt nur die Bedienkenntnis, wo der
vorhandene Ablauf zu finden ist; kein Fristdruck erkennbar.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre Nachricht — die von Ihnen beschriebene Funktion gibt es bei uns bereits:
>
> 1. Öffnen Sie im Nachrichten-Bereich **"Neue Nachricht"**.
> 2. Wählen Sie dort über die Suchfelder zuerst die **Immobilie** und den **Kunden** aus.
> 3. Klicken Sie anschließend auf **"Vorlage"** und wählen Sie die Vorlage
>    **"Exposé-Vorschlag zur Freigabe"**.
>
> Der Exposé-Link wird dabei automatisch für genau das ausgewählte Objekt eingesetzt, und der Text
> bittet den Kunden bereits um Prüfung sowie Freigabe oder Änderungswünsche — Sie müssen nur noch
> auf "Senden" klicken.
>
> Falls Sie stattdessen direkt aus dem allgemeinen E-Mail-Postfach heraus eine Vorlage öffnen,
> kann der Link nicht automatisch eingesetzt werden, da dort kein Objekt/Kunde vorausgewählt ist —
> bitte in diesem Fall den Weg über "Neue Nachricht" nutzen.
>
> Sehr gerne zeigen wir Ihnen das auch einmal kurz in einem Bildschirmteilen-Termin, falls das
> hilfreich ist.

**Rückfragen-Guidance:** Aus dem Ticket geht nicht hervor, über welchen Bildschirm der Absender es
versucht hat (Postfach direkt vs. "Neue Nachricht"-Dialog) — das würde die Antwort präzisieren,
ändert aber nichts an der Einstufung. Für `immo-crm` existiert noch keine Kunden-Anleitung
(`docs/customer-journeys/`) zu diesem konkreten Ablauf (Vorlage mit Objekt-/Kunden-Suche für
Exposé-Freigabe) — bei wiederkehrenden Rückfragen wäre `/abc-customer-journey` dafür sinnvoll.

---

Nächster Schritt bei Bedarf: Keine Code-Änderung nötig. Bei Bedarf `/abc-customer-journey` für
"immo-crm" laufen lassen, um eine bebilderte Anleitung zu "Exposé-Vorlage mit automatischem Link
versenden" zu erzeugen — das würde diese und ähnliche Rückfragen künftig vermeiden.
