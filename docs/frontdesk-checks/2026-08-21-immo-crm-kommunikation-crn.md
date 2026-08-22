# Frontdesk-Check — 2026-08-21

**Quelle:** Peppermint-Ticket (Freshdesk #153, Peppermint-ID 88f39132-45ea-442c-9934-beeac1c87518), weitergeleitet über Auxevo Support.
Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Fehlermeldung CRN — fremde Mail im falschen Kundenverlauf | Übergreifendes Problem | Hoch |

---

### Ticket: Mail von Frau Tiller Hein (nicht im System angelegt) taucht im Kommunikationsverlauf von Herrn Woltering auf, Absender ist Firat

**Kurzbefund:** Übergreifendes Problem

**Eingrenzung:** Schicht: Backend · Modul: Kommunikation / E-Mail-Sync (Immo-CRM-Repo, nicht Jupiter)
`find_or_create_conversation` in `backend/app/services/email_service.py` (immo-crm) matcht eine eingehende Mail primär über `In-Reply-To`/`References`-Header gegen `messages.metadata->>'message_id'` — **ohne** dabei zu prüfen, ob der tatsächliche Absender/Empfänger überhaupt zum `client_id` der gefundenen Conversation passt (Schritt 1+2 vor dem `client_id`-Check in Schritt 3). Antwortet oder referenziert ein fremder Absender (z. B. Frau Tiller Hein) eine Message-ID, die zufällig aus Woltering's Thread stammt (Forward/CC-Kette, geteilte Mailbox), wird die Mail in dessen Verlauf gehängt statt einen neuen Kontakt/Verlauf anzulegen. Bereits als Cluster bekannt: **PROJ-41 "Mail↔Kunde-Matching & Verlauf-Navigation — Bug-Cluster"** (Status: Deployed) — dieser Fall wirkt wie eine nicht abgedeckte Kante desselben Mechanismus, kein Einzelfall.

**Dringlichkeit:** Hoch
Kernfunktion Kommunikation betroffen, Mechanismus ist strukturell (jede geteilte Mailbox/Forward-Kette kann das auslösen, nicht nur dieser Kunde), Fehlzuordnung fremder Personendaten in falschen Kundenverlauf hat DSGVO-Relevanz. Kein akuter Blocker (Kunde kann weiterarbeiten), daher nicht "Dringend".

**Antwortentwurf an den Kunden:**
> Guten Tag,
>
> vielen Dank für Ihre Meldung. Wir prüfen aktuell, wie es zu der falschen Zuordnung der E-Mail im Kommunikationsverlauf von Herrn Woltering kommen konnte. Bitte teilen Sie uns, sofern möglich, noch mit, ob es sich bei der betreffenden Mail um eine Weiterleitung oder Antwort auf eine ältere Nachricht handelte — das hilft uns bei der Eingrenzung. Wir melden uns, sobald wir mehr wissen.
>
> Freundliche Grüße
> Ihr Support-Team

**Rückfragen-Guidance:** War die Mail von Frau Tiller Hein eine Antwort/Weiterleitung einer bestehenden Nachricht (Reply/Fwd) oder eine komplett neue Mail? Betrifft es eine gemeinsam genutzte Mailbox (Firat)? Ist der Fall reproduzierbar oder einmalig aufgetreten? Screenshot des Verlaufs wäre hilfreich zur Verifikation.

**Hinweis:** Reproduktion nur per Code-Analyse geprüft, nicht live nachgestellt (kein Zugriff auf echte Kundendaten ohne Freigabe).
