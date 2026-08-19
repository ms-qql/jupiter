# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 712b5f3c (Freshdesk #112) — "Mail geblockt auf Outlook aber trotzdem auf Immo CRM erhalten" | Benutzerfehler/Wissenslücke — gewünschte Absender-Blockierfunktion existiert in ImmoCRM bereits, Kunde kennt sie nicht | Niedrig |

---

### Ticket: Peppermint-Ticket "Mail geblockt auf Outlook aber trotzdem auf Immo CRM erhalten" (Peppermint 712b5f3c-2bb5-4547-a6ff-ff8d89eb82a4, Freshdesk #112, Kunde: Firat Erol / Erol Immobilien GmbH, Nachricht an "Manfred")

**Kurzbefund:** Kein Systemfehler. Der Kunde hat den Absender `lisahartmann@hallo-heidi.org`
in Outlook geblockt — das wirkt aber nur auf sein eigenes Outlook-Postfach, nicht auf das
ImmoCRM-eigene Nachrichten-/E-Mail-Modul, das unabhängig per IMAP synchronisiert. Der Kunde fragt
explizit, ob man "das auch hier einbauen" kann — die gewünschte Funktion (Absender in ImmoCRM
blockieren) **existiert bereits**, ist ihm nur offenbar nicht bekannt.

**Eingrenzung:** Frontend + Backend · Modul: Nachrichten/E-Mail-Blacklist (`immo-crm`,
`lib/features/messages/messages_screen.dart` [Blacklist-Button je Konversation, ruft
`BlacklistApi.addToBlacklist`], `lib/core/services/blacklist_api.dart`,
`backend/app/routes/blacklist.py` [`GET/POST/DELETE /email-blacklist`],
`backend/app/services/email_service.py::_store_inbound_email_impl` [Zeile ~4203: eingehende
Mails von blacklisteten Absendern werden beim Sync-Import still verworfen]).

Code-Grep-Befund: Die komplette Kette ist bereits implementiert — UI-Button "Blacklist" in der
Konversationsansicht (mit Bestätigungsdialog "E-Mails von … werden zukünftig ignoriert"),
REST-Endpunkte zum Verwalten der Blacklist, und ein serverseitiger Check beim Mail-Import, der
Nachrichten blacklisteter Absender kommentarlos verwirft. Der Kunde muss dafür nichts einbauen
lassen, sondern lediglich die vorhandene Funktion nutzen.

Randbeobachtung (nicht Teil dieser Triage, nur zur Kenntnis): Der Blacklist-Check in
`email_service.py` filtert nicht nach `tenant_id` — anders als die Blacklist-Routen selbst, die
`WHERE tenant_id = %s` verwenden. Das wäre ggf. für `/abc-qa` als Mandanten-Isolationsfrage zu
prüfen, ist aber unabhängig vom hier gemeldeten Kundenwunsch.

**Dringlichkeit:** Niedrig
Freshdesk hat bereits "low" gesetzt; die gewünschte Funktion existiert bereits und ist nutzbar;
kein Kernfunktions-, Daten- oder DSGVO-Risiko; der Kunde ist nicht blockiert, sondern nur nicht
über die vorhandene Funktion informiert.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre Nachricht. Das Blockieren in Outlook wirkt nur auf Ihr eigenes
> Outlook-Postfach — ImmoCRM liest eingehende E-Mails unabhängig davon über eine eigene
> Synchronisation, deshalb kam die Nachricht dort trotzdem an.
>
> Die gute Nachricht: Genau die von Ihnen gewünschte Funktion gibt es in ImmoCRM bereits. Öffnen
> Sie im Modul "Nachrichten" die betreffende Konversation und klicken Sie dort auf "Blacklist" —
> zukünftige E-Mails von diesem Absender (z. B. lisahartmann@hallo-heidi.org) werden dann
> automatisch ignoriert und die aktuelle Konversation wird archiviert.
>
> Sollten Sie den Button nicht finden oder mehrere Absender auf einmal blockieren wollen, melden
> Sie sich gerne — dann zeigen wir Ihnen das kurz.

**Rückfragen-Guidance:** Keine zwingend offenen Fragen für die Einstufung selbst. Für die
Kundenkommunikation wäre hilfreich zu wissen, ob der Kunde die Blacklist-Funktion im Nachrichten-Modul
schon einmal gesehen hat (falls sie z. B. durch fehlende Berechtigung nicht sichtbar war) — das
lässt sich aus dem Ticket nicht ablesen.

---

Nächster Schritt bei Bedarf: Keiner — Funktion existiert bereits, reine Kundenaufklärung per
Antwort-Mail ausreichend. Optional: prüfen, ob eine Kurzanleitung dazu in
`docs/customer-journeys/` des `immo-crm`-Projekts sinnvoll wäre, falls solche Rückfragen häufiger
auftreten.
