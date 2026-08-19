# Frontdesk-Triage — 2026-08-11

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 0d1c97ae (Freshdesk #145) — "ImmoCRM - Spamschutz" | Benutzerfehler/Wissenslücke — gewünschte Absender-Sperrfunktion existiert in ImmoCRM bereits | Niedrig |

---

### Ticket: Peppermint-Ticket "ImmoCRM - Spamschutz" (Peppermint 0d1c97ae-7957-46b3-a91d-0c4cd50017c3, Freshdesk #145, Kunde/Melder: nicht genannt — nur "Auxevo Support" als Weiterleiter)

**Kurzbefund:** Kein Systemfehler. Kerninhalt des Tickets: "E-Mail Absender sperren, wenn es fake
ist" — ein Feature-Wunsch für Spamschutz. Die gewünschte Funktion (Absender in ImmoCRM blockieren)
**existiert bereits** — identisch zum bereits erfassten Ticket-Cluster vom 2026-07-08
(`2026-07-08-immocrm-sender-blacklist.md`, Freshdesk #112).

**Eingrenzung:** Frontend + Backend · Modul: Nachrichten/E-Mail-Blacklist (`immo-crm`,
`backend/app/routes/blacklist.py` [`GET/POST /email-blacklist`], Blacklist-Button in der
Konversationsansicht unter `lib/features/messages/`).

Code-Grep-Befund: `backend/app/routes/blacklist.py` bestätigt existierende Endpunkte
`list_blacklist` (GET `/email-blacklist`) und POST zum Hinzufügen. Kette bereits vollständig
implementiert (siehe Vorgänger-Ticket #112 für Detailpfade) — nichts zu bauen, nur Kundenaufklärung
nötig.

**Dringlichkeit:** Niedrig
Freshdesk hat bereits "low" gesetzt; gewünschte Funktion existiert und ist nutzbar; kein
Kernfunktions-, Daten- oder DSGVO-Risiko; kein blockierter Kunde, nur fehlende Information über
vorhandene Funktion. Gehört zum selben wiederkehrenden Wissenslücken-Cluster wie #112 — kein neuer
Bug, aber ein Hinweis, dass die Funktion nicht auffindbar genug ist.

**Antwortentwurf an den Kunden:**
> Guten Tag,
>
> vielen Dank für Ihre Nachricht. Der gewünschte Spamschutz ist in ImmoCRM bereits vorhanden:
> Öffnen Sie im Modul "Nachrichten" die betreffende Konversation und klicken Sie dort auf
> "Blacklist" — E-Mails von diesem Absender werden danach automatisch als Spam erkannt und nicht
> mehr zugestellt.
>
> Sollten Sie den Button nicht finden, melden Sie sich gerne — dann zeigen wir Ihnen das kurz.

**Rückfragen-Guidance:** Ticket nennt keinen konkreten Absender/Kunden und keinen Melder-Namen —
für eine personalisierte Antwort wäre der ursprüngliche Freshdesk-Ticket-Text (#145) mit Kontext
hilfreich (wer meldet, welcher Absender konkret gemeint ist).

---

Nächster Schritt bei Bedarf: Keiner (Funktion existiert) — optional: da dies der zweite Fall
desselben Wissenslücken-Musters ist (nach #112), `/abc-customer-journey` für das
Blacklist/Spamschutz-Feature erwägen, um zukünftige Tickets dieser Art zu vermeiden.
