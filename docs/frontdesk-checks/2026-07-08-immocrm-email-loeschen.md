# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #101)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 0a18bb08 (Freshdesk #101) — "E-MAil löschen" | Unklar (zu wenig Info): vermutlich Einzelfall/Bedienfrage, evtl. Verwechslung mit read-only Kundenverlauf | Niedrig |

---

### Ticket: Peppermint "Ticket Assigned - E-MAil löschen" (Peppermint 0a18bb08-371c-4775-a4cf-81d1d082ec6b, Freshdesk #101, Absender: Firat Erol / Erol Immobilien GmbH, adressiert an Manfred)

**Kurzbefund:** Firat Erol berichtet, er sei "auf eine E-Mail in meinem FE-Account" gegangen und
habe versucht, diese zu löschen — es funktioniere nicht. Kein Fehlertext, keine Screenshot-Angabe,
keine Angabe, welche E-Mail/welcher Ordner, kein Hinweis ob eine Fehlermeldung erschien oder der
Button gar nicht reagierte. "FE-Account" ist kein bekannter Fachbegriff im Produkt — vermutlich
meint er schlicht seinen eigenen Account im Frontend (immo-crm).

**Eingrenzung:** Frontend/Backend · Modul: E-Mail-Client (Postfach/IMAP) bzw. Kundenverlauf,
Repo `immo-crm`.

Code-Grep-Befund:
- Es gibt eine funktionierende Lösch-Funktion für einzelne/mehrere E-Mails im echten
  IMAP-Postfach-Client (`lib/features/email/email_screen.dart`, Buttons/Handler u.a. Zeilen 1263,
  1292, 2410, 3133 → `EmailMailboxApi.deleteMessage` → `DELETE
  /email-accounts/{account_id}/folders/{folder}/messages/{uid}`,
  `backend/app/routes/email_mailbox.py:575-594`). Normale Ordner → Verschieben nach Papierkorb;
  im Papierkorb selbst → permanentes `STORE \Deleted` + `EXPUNGE`. Fehler werden per Snackbar
  angezeigt — ein stiller, kommentarloser Fehlschlag ist im Code nicht vorgesehen.
- Getrennt davon existiert der **Kommunikationsverlauf** am Kundendatensatz
  (`clients_mailview`/`kunden_neu_screen`), der laut `features/PROJ-91-...md` **bewusst read-only**
  ist ("kein Senden/Gelesen/Löschen/Bulk"). Meint der Kunde diese Ansicht, ist "Löschen geht nicht"
  kein Bug, sondern Absicht.
- Kein bekannter Bug-Cluster zu "einzelne E-Mail löschen fehlschlägt" in `features/INDEX.md`;
  PROJ-60 betrifft nur Ordner-Löschen/Papierkorb-Leeren, kein direkter Treffer.
- Ohne Angabe, in welcher der beiden Ansichten (Postfach vs. Kundenverlauf) der Kunde war und ohne
  Fehlermeldung/Screenshot lässt sich Benutzerfehler (falsche Ansicht), Bedienfrage (Ordner
  Papierkorb vs. normal) und echter Bug (z. B. IMAP-Fehler beim EXPUNGE) nicht unterscheiden.

**Dringlichkeit:** Niedrig
Betrifft (soweit erkennbar) nur einen einzelnen Nutzer, keine Kernfunktion blockiert (E-Mail bleibt
lesbar, nur Löschen scheitert), kein Hinweis auf Datenverlust oder DSGVO-Bezug, Freshdesk-Priorität
bereits "low". Kein Anhaltspunkt für ein übergreifendes Problem.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre Nachricht. Damit wir das genau nachvollziehen können: In welchem Bereich
> waren Sie beim Versuch, die E-Mail zu löschen — im Postfach (E-Mail-Ansicht mit Ordnern) oder im
> Kommunikationsverlauf eines Kundendatensatzes? Erscheint dabei eine Fehlermeldung, oder passiert
> beim Klick auf "Löschen" gar nichts? Und befand sich die E-Mail bereits im Papierkorb-Ordner?
> Mit diesen Angaben können wir gezielt weiterhelfen.

**Rückfragen-Guidance:**
- In welcher Ansicht war der Kunde (Postfach/E-Mail-Client vs. Kundenverlauf/Kommunikationsverlauf
  am Kundendatensatz)?
- War eine Fehlermeldung sichtbar, oder reagiert der Löschen-Button/-Aktion gar nicht?
- War die E-Mail bereits im Papierkorb-Ordner (dort ist Löschen = endgültig via EXPUNGE) oder in
  einem normalen Ordner (dort ist Löschen = Verschieben nach Papierkorb)?
- Browser/Client, Datum/Uhrzeit des Versuchs, ggf. Screenshot.

---

Nächster Schritt bei Bedarf: nach Klärung der Rückfragen ggf. gezielter Test im `immo-crm`-Projekt
(`/abc-qa`) des betroffenen Lösch-Pfads (Postfach-Delete bzw. Klarstellung read-only
Kundenverlauf).
