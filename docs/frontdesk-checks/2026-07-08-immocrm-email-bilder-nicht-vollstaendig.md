# Frontdesk-Triage — 2026-07-08

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #79)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 873e83c1 (Freshdesk #79) — "Inhalt der Mail nicht Vollständig" | Vermutlich Benutzerfehler: Bilder von unbekanntem externem Absender werden im Immo-CRM per Trusted-Sender-Gate (PROJ-72) absichtlich zurückgehalten, bis "Bilder anzeigen" geklickt wird | Niedrig |

---

### Ticket: Peppermint-Ticket "Inhalt der Mail nicht Vollständig" (Peppermint 873e83c1-0de4-4459-8dd0-5b004674192d, Freshdesk #79, weitergeleitet von Firat Erol / Erol Immobilien GmbH, adressiert an Manfred)

**Kurzbefund:** Eine an `Info@erol` eingegangene Mail von "Haus & Grund" wird im Immo-CRM
angezeigt, aber ohne die im Mailtext enthaltenen Bilder — in Outlook sind dieselben Bilder
sichtbar. Der Kunde vermutet einen Anzeigefehler im CRM.

**Eingrenzung:** Frontend · Modul: E-Mail-Viewer / Bilddarstellung
(`immo-crm`, `lib/features/email/email_screen.dart`, `lib/features/email/utils/cid_image_rewriter.dart`)
— ergänzend Backend: `backend/app/services/email_service.py` (HTML-Sanitizing, Content-ID-Handling).

Code-Grep-Befund:
- Der HTML-Sanitizer im Backend (`_sanitize_email_html`, `email_service.py:534`) entfernt
  `<script>`, `<style>`, `<iframe>`, MSO-Conditional-Blöcke, `on*`-Handler und `javascript:`-URLs —
  `<img>`-Tags sowie `data:`/`cid:`-Quellen werden **nicht** entfernt.
- `cid:`-eingebettete Bilder (klassischer Outlook-Signatur-/Inline-Fall) werden im Frontend über
  `rewriteCidImages` gegen `EmailAttachment.content_id` aufgelöst und als `data:`-URI eingesetzt —
  dieser Pfad ist über **PROJ-39 → PROJ-72** ("E-Mail-Viewer — Eingebettete Bilder zuverlässig
  anzeigen") bereits gebaut und deployed; die Problembeschreibung dieses abgeschlossenen Features
  ist nahezu identisch mit diesem Ticket.
- Für externe `http(s)`-Bilder gilt laut PROJ-72 ein **Trusted-Sender-Modell**: Bilder werden nur
  für bekannte CRM-Kontakte/Domains automatisch geladen; bei unbekannten Absendern erscheint
  stattdessen ein Banner "Bilder anzeigen", das erst per Klick die Bilder nachlädt (Schutz vor
  Tracking-Pixeln).
- Plausibelste Erklärung: "Haus & Grund" ist im CRM vermutlich kein hinterlegter/bekannter
  Kontakt, sodass dessen Bilder hinter dem "Bilder anzeigen"-Banner liegen — der Kunde hat diesen
  Klick vermutlich übersehen oder nicht als notwendig erkannt. Das im Ticket sichtbare
  Signaturbild (`crm.erol.msce.info/api/public/agent-photo/...`) stammt aus einer anderen Mail
  (der Peppermint-Benachrichtigung selbst, Absender Firat Erol) und ist nicht Teil des
  eigentlichen Kundenproblems.
- Nicht live geprüft (kein Zugriff auf die konkrete Mail/den Absender-Header von "Haus & Grund"
  im System) — daher nicht auszuschließen, dass die Bilder tatsächlich `cid:`-referenziert sind
  und der Rewrite dort aus einem anderen Grund fehlschlägt (z. B. fehlendes Attachment). Da der
  cid-Pfad aber bereits gehärtet und deployed ist (PROJ-72), ist das Trusted-Sender-Gate die
  wahrscheinlichere Ursache.

**Dringlichkeit:** Niedrig
Rein kosmetisch (keine fehlenden/verlorenen Daten, kein DSGVO-Bezug), betrifft nur die
Bild-Darstellung bei einem einzelnen, vermutlich unbekannten Absender, und es existiert ein
bekannter, funktionierender Workaround (Klick auf "Bilder anzeigen"). Kein Hinweis auf ein
strukturelles Problem, da der zugrunde liegende Mechanismus (cid-Bilder) bereits gehärtet ist.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für den Hinweis. Bilder aus E-Mails von unbekannten oder noch nicht als Kontakt
> hinterlegten Absendern werden im Immo-CRM aus Datenschutzgründen (Schutz vor Tracking-Pixeln)
> zunächst nicht automatisch geladen. Stattdessen erscheint über dem Mailtext ein Hinweis
> "Bilder anzeigen" — erst nach einem Klick darauf werden die Bilder nachgeladen.
>
> Könnten Sie beim nächsten Mal kurz prüfen, ob dieser Hinweis bei der Mail von Haus & Grund
> sichtbar war, und ob ein Klick darauf die Bilder anzeigt? Falls die Bilder auch danach nicht
> erscheinen, melden Sie sich bitte mit einem Screenshot bei uns — dann schauen wir uns das genauer
> an.

**Rückfragen-Guidance:**
- War über dem Mailtext ein Banner/Hinweis "Bilder anzeigen" sichtbar, und wurde darauf geklickt?
- Falls ja und die Bilder erscheinen trotzdem nicht: Screenshot der Mailansicht im CRM.
- Die genaue Absenderadresse der Haus & Grund-Mail (zur Prüfung, ob/als was sie im CRM als Kontakt
  hinterlegt ist).

---

Nächster Schritt bei Bedarf: Falls die Rückfrage ergibt, dass "Bilder anzeigen" geklickt wurde und
die Bilder trotzdem fehlen, gezielter `/abc-qa`-Test des `cid_image_rewriter.dart`-Pfads im
`immo-crm`-Projekt mit einer echten `cid:`-Testmail.
