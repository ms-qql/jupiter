# Frontdesk-Triage — 2026-07-28

Quelle: Peppermint-Ticket (Auxevo Support / Freshdesk-Weiterleitung, Ticket #134)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 41ba2765 (Freshdesk #134) — "Mails sind nicht zusehen" | Übergreifendes Problem: Backend filtert Konversationen für Nicht-Admins hart auf die eigenen `user_email_accounts` — Nutzer ohne Zuweisung zu Beatas Postfach sehen ihre Mails grundsätzlich nicht | Hoch |

---

### Ticket: "Mails sind nicht zusehen" (Peppermint 41ba2765-3f2f-4bee-82a8-e1d99776332e, Freshdesk #134, Nutzer f.erol@erolimmobilien.de)

**Kurzbefund:** f.erol@erolimmobilien.de sieht seit längerem keine Mails, die Beata sendet/empfängt
— reproduzierbar, immer. Erwartung: alle Mails von Beata sehen können.

**Eingrenzung:** Backend · Modul: E-Mail/Konversationen (`immo-crm`,
`backend/app/routes/messaging.py:38` `_email_account_filter`).

Code-Grep-Befund:
- `_email_account_filter()` (messaging.py:38-47) schränkt Konversationen für alle Nutzer außer
  `Admin`/`Supereditor` explizit auf `email_account_id IN (SELECT email_account_id FROM
  user_email_accounts WHERE user_id = %s)` ein — jede Query gegen `conversations`
  (`/conversations/counts` u.a.) wendet diesen Filter an.
- Das ist kein Rand-Bug, sondern die **bewusste** aktuelle Architektur: Sichtbarkeit ist an
  Postfach-Zuweisung gekoppelt, nicht an Mandant/Kunde.
- Exakter Treffer im bekannten Bug-Cluster **PROJ-38** ("E-Mail-Verlauf — Anzeige &
  Cross-User-Sichtbarkeit", On Hold seit 2026-05-26), Punkt B16: "Mails von User A komplett
  fehlend im Kunden-Verlauf für User B" — inklusive fast identischem Original-Zitat aus der
  damaligen Discovery ("Wir müssen beide immer sehen können, was mit welchem Kunden
  kommuniziert wurde").
- Die auslösende Vorbedingung (zwei Makler, gemeinsame Kundenbetreuung, getrennte Mail-Konten)
  ist Kernrealität eines Makler-CRMs, kein Sonderfall — der Mechanismus trifft strukturell jeden
  Nutzer ohne Zuweisung zum jeweils anderen Postfach.

**Dringlichkeit:** Hoch
Kernfunktion Kommunikation/Vertretung betroffen, übergreifender (architektonischer) Mechanismus,
bereits als Critical-Bug (B16) in einem seit 2026-05-26 offenen, aber "On Hold" gesetzten Cluster
dokumentiert. Kein Datenverlust (Mails liegen vor, nur Sichtbarkeitsfilter), aber blockierend für
Vertretung zwischen Maklern. Empfehlung: PROJ-38 aus "On Hold" zurück auf "Planned" heben statt
neues Ticket isoliert zu bearbeiten.

**Antwortentwurf an den Kunden:**
> Hallo, vielen Dank für die Meldung. Wir haben den Grund gefunden: Mails werden aktuell nur für
> die Nutzer sichtbar, deren Konto dem jeweiligen E-Mail-Postfach zugeordnet ist — Ihr Konto ist
> (noch) nicht mit Beatas Postfach verknüpft, daher fehlen deren Mails bei Ihnen. Das betrifft
> nicht nur diesen Fall, sondern die Postfach-Zuweisung generell, und ist uns bereits als
> größeres Thema bekannt. Wir kümmern uns darum und melden uns, sobald es behoben ist.

**Rückfragen-Guidance:** Keine wesentlichen fehlenden Infos für die Eingrenzung — Ticket war
präzise genug (Nutzer, Reproduzierbarkeit, Dauer). Für die spätere Umsetzung wäre hilfreich zu
wissen, ob f.erol grundsätzlich alle Postfächer im Mandanten sehen soll (Rolle Admin-artig) oder
gezielt nur Beatas — das entscheidet, ob Fix eine Postfach-Zuweisung oder ein Rollen-Upgrade ist.
