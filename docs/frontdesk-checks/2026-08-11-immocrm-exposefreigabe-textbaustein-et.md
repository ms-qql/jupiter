# Frontdesk-Triage — 2026-08-11

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint b815bc6f (Freshdesk #143) — "Exposéfreigabe als Textbaustein zum Versenden an der ET" | Benutzerfehler / fehlende Bedienkenntnis — Vorlage existiert bereits vollständig | Niedrig |

---

### Ticket: Peppermint-Ticket "ImmoCRM - Exposéfreigabe" (Peppermint b815bc6f-68e3-485b-959b-a0c208848cf5, Freshdesk #143, Absender: Auxevo Support / Erol Immobilien GmbH)

**Kurzbefund:** Kein Systemfehler. Sehr knappes Ticket ("Exposéfreigabe als textbaustein zum
versenden an der ET" — ET = Eigentümer/Auftraggeber), ohne weitere Details. Der gewünschte
Textbaustein zur Exposé-Freigabe an den Eigentümer existiert bereits vollständig im System.

**Eingrenzung:** Kein Fehler in einer bestimmten Schicht — Bedienhinweis. Betroffenes Modul:
Nachrichten/Kommunikation, Kategorie Eigentümer (`immo-crm`).

Code-Grep-Befund (`/home/dev/projects/immo-crm`):
- `backend/app/seed_templates.py:237-262`: Vorlage "Exposé-Vorschlag zur Freigabe", Kategorie
  "Eigentümer", Betreff "Exposé-Entwurf für {Objektname} – Bitte um Ihre Freigabe", Text bittet den
  Eigentümer um Prüfung/Freigabe/Änderungswünsche und enthält `{ExposéLink}` — inhaltlich exakt der
  im Ticket gewünschte Textbaustein.
- Auswahl/Nutzung wie bereits im früheren, praktisch identischen Ticket #71 dokumentiert
  (`docs/frontdesk-checks/2026-07-08-immocrm-expose-freigabe-link.md`): über "Neue Nachricht" →
  Kunde/Immobilie auswählen → Button "Vorlage" → "Exposé-Vorschlag zur Freigabe". Seit diesem
  früheren Ticket keine Code-Änderung an der Vorlage erkennbar (identischer Stand).

**Dringlichkeit:** Niedrig
Freshdesk hat bereits "low" gesetzt; kein Kernfunktions-, Daten- oder DSGVO-Bezug; die Funktion
existiert und funktioniert bereits, niemand ist blockiert — es fehlt nur die Bedienkenntnis; kein
Fristdruck erkennbar.

**Antwortentwurf an den Kunden:**
> Hallo,
>
> vielen Dank für Ihre Nachricht — den gewünschten Textbaustein für die Exposéfreigabe an den
> Eigentümer gibt es bei uns bereits:
>
> 1. Öffnen Sie im Nachrichten-Bereich **"Neue Nachricht"**.
> 2. Wählen Sie über die Suchfelder zuerst die **Immobilie** und den **Eigentümer** aus.
> 3. Klicken Sie auf **"Vorlage"** und wählen Sie die Vorlage **"Exposé-Vorschlag zur Freigabe"**
>    (Kategorie "Eigentümer").
>
> Der Exposé-Link wird dabei automatisch für das ausgewählte Objekt eingesetzt, und der Text bittet
> den Eigentümer bereits um Prüfung sowie Freigabe oder Änderungswünsche — Sie müssen nur noch auf
> "Senden" klicken.
>
> Sehr gerne zeigen wir Ihnen das auch einmal kurz in einem Bildschirmteilen-Termin, falls das
> hilfreich ist.

**Rückfragen-Guidance:** Ticket ist sehr knapp (ein Halbsatz, kein konkretes Problem/keine
Fehlerbeschreibung genannt). Unklar, ob der Absender die Vorlage gar nicht gefunden hat, sie nicht
kannte, oder ob es um eine inhaltliche Änderung des bestehenden Textbausteins ging (das Ticket
nennt keine gewünschte Textänderung). Falls es tatsächlich um eine Anpassung des Wordings ging,
wäre die genaue gewünschte Formulierung nachzufragen. Für `immo-crm` existiert weiterhin keine
Kunden-Anleitung (`docs/customer-journeys/`) zu diesem Ablauf — bei wiederkehrenden Rückfragen
(dies ist bereits das zweite Ticket zum selben Thema, vgl. Freshdesk #71) wäre
`/abc-customer-journey` sinnvoll.

---

Nächster Schritt bei Bedarf: Keine Code-Änderung nötig. Da dies das zweite Ticket zum selben Thema
ist, `/abc-customer-journey` für "immo-crm" laufen lassen, um eine bebilderte Anleitung zu
"Exposé-Vorlage an Eigentümer versenden" zu erzeugen und künftige Rückfragen zu vermeiden.
