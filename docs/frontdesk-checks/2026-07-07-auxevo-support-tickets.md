# Frontdesk-Triage — 2026-07-07

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint d1ded3af (Freshdesk #111) — "Test Weiterleitung intern" | Kein Systemfehler (interner Test) | Niedrig |
| Peppermint 07e95a7a (Freshdesk #110) — "Test Weiterleitung" | Kein Systemfehler (interner Test) | Niedrig |
| Peppermint 24829df5 — "Manfred Schmitz lädt Sie ein, Freshdesk beizutreten" | Kein Kunden-Ticket (automatisierte Freshworks-Werbe-/Einladungsmail) | Niedrig |
| Peppermint 8124f1ab — "Ticket 1" (Manfred Schmitz) | Kein Systemfehler (Test-Ticket ohne Anliegen) | Niedrig |

---

### Ticket: Peppermint-Notification "Test Weiterleitung intern" (Freshdesk #111 → Peppermint d1ded3af)

**Kurzbefund:** Kein Kunden-Ticket / kein Bug — internes Testereignis. Absender ist die interne
Support-Mailbox selbst (`support@auxevo.freshdesk.com`), Betreff und Inhalt sind wörtlich
"Test Weiterleitung intern" / "Test intern". Das ist die automatische Freshdesk→Peppermint
Zuweisungs-Benachrichtigung für ein Ticket, das offensichtlich angelegt wurde, um die
Weiterleitung selbst zu prüfen — keine echte Kundenanfrage, keine Fehlermeldung.

**Eingrenzung:** — (kein App-Fehler; die Weiterleitung selbst hat sichtbar funktioniert, sonst
läge dieses Ticket nicht in Peppermint vor).

**Dringlichkeit:** Niedrig
Kein Kernfunktions-, Daten- oder DSGVO-Bezug; niemand ist blockiert; es handelt sich um einen
bewusst ausgelösten internen Testlauf, keine offene Anfrage, die eine Antwort erwartet.

**Antwortentwurf an den Kunden:**
> Dies war ein interner Testlauf zur Prüfung der Freshdesk-Weiterleitung nach Peppermint. Keine
> Kundenantwort erforderlich — das Ticket kann geschlossen werden.

**Rückfragen-Guidance:** Keine. Der Zweck des Tickets ist aus Betreff und Inhalt eindeutig
(interner Test), es fehlen keine Angaben, die eine andere Einstufung nahelegen würden.

---

### Ticket: Peppermint-Notification "Test Weiterleitung" (Freshdesk #110 → Peppermint 07e95a7a)

**Kurzbefund:** Kein Kunden-Ticket / kein Bug — internes Testereignis, gleiches Muster wie das
oben erfasste Ticket #111. Absender ist die interne Support-Mailbox selbst
(`support@auxevo.freshdesk.com`), Betreff "Test Weiterleitung", Inhalt wörtlich
"Weiterleitung an Pepper". Automatische Freshdesk→Peppermint Zuweisungs-Benachrichtigung für ein
offensichtlich zu Testzwecken angelegtes Ticket — keine echte Kundenanfrage, keine Fehlermeldung.

**Eingrenzung:** — (kein App-Fehler; die Weiterleitung selbst hat sichtbar funktioniert, sonst
läge dieses Ticket nicht in Peppermint vor).

**Dringlichkeit:** Niedrig
Kein Kernfunktions-, Daten- oder DSGVO-Bezug; niemand ist blockiert; bewusst ausgelöster interner
Testlauf, keine offene Anfrage, die eine Antwort erwartet.

**Antwortentwurf an den Kunden:**
> Dies war ein interner Testlauf zur Prüfung der Freshdesk-Weiterleitung nach Peppermint. Keine
> Kundenantwort erforderlich — das Ticket kann geschlossen werden.

**Rückfragen-Guidance:** Keine. Der Zweck des Tickets ist aus Betreff und Inhalt eindeutig
(interner Test), es fehlen keine Angaben, die eine andere Einstufung nahelegen würden.

---

### Ticket: Peppermint-Notification "Manfred Schmitz lädt Sie ein, Freshdesk beizutreten" (Peppermint 24829df5)

**Kurzbefund:** Kein Kunden-Ticket / kein Bug — automatisierte Produkt-Einladungsmail von
Freshworks selbst (Absender `support@freshworks.com`, Betreff/Inhalt sind die Standard-Freshdesk-
"Jetzt beitreten"-Einladung inkl. Invite-Link `auxevo.myfreshworks.com/invite/...`). Die Mail
richtet sich an "Pepper Mint" (den Bot-/Systemnamen, unter dem die Support-Mailbox in Freshdesk
läuft), nicht an einen echten Endkunden. Es handelt sich nicht um eine Support-Anfrage, sondern um
eine über die Mail-Weiterleitung fälschlich als Ticket erfasste Werbe-/Einladungs-Nachricht —
gleiches Grundmuster wie die beiden Test-Weiterleitungs-Tickets oben, nur diesmal von einem
externen Freshworks-System statt intern ausgelöst.

**Eingrenzung:** — (kein App-Fehler im Immo-CRM; die Weiterleitung von Freshdesk nach Peppermint
funktioniert sichtbar wie vorgesehen. Höchstens relevant für die Peppermint-/Freshdesk-Filterregeln,
welche Mails als Ticket erfasst werden — das ist eine Konfigurationsfrage, kein Produktbug.)

**Dringlichkeit:** Niedrig
Kein Kernfunktions-, Daten- oder DSGVO-Bezug; kein Kunde ist blockiert; es ist keine echte
Support-Anfrage, sondern eine automatisierte Drittanbieter-Mail, die keine inhaltliche Antwort
erwartet.

**Antwortentwurf an den Kunden:**
> Diese Nachricht ist keine Kundenanfrage, sondern eine automatisierte Einladungsmail von Freshworks
> (Freshdesk-Produkteinladung). Es ist keine Antwort erforderlich — das Ticket kann geschlossen
> werden. Optional: prüfen, ob die Freshdesk→Peppermint-Weiterleitungsregel solche
> System-/Marketing-Mails künftig herausfiltern kann.

**Rückfragen-Guidance:** Keine inhaltlichen Rückfragen an einen Kunden nötig, da kein Kunde
beteiligt ist. Falls das häufiger vorkommt, wäre die einzig relevante Zusatzinfo, ob es weitere
gleichartige Freshworks-System-Mails gibt, die die Weiterleitungsregel bereits fälschlich als
Tickets erfasst hat.

---

### Ticket: Peppermint-Ticket "Ticket 1" (Peppermint 8124f1ab, Absender Manfred Schmitz <schmitz.manfred@pm.me>)

**Kurzbefund:** Kein Systemfehler — Test-Ticket ohne inhaltliches Anliegen. Betreff wörtlich
"Ticket 1", Beschreibung wörtlich "Test Ticket", darüber hinaus nur der leere ProtonMail-
Signatur-Block (HTML-Artefakt der ProtonMail-Weboberfläche, kein echter Inhalt). Absender
schmitz.manfred@pm.me ist dieselbe Person, die bereits als Absender der oben erfassten
Freshdesk-Einladungsmail (Peppermint 24829df5) aufgetreten ist — vermutlich die Person, die die
Freshdesk→Peppermint-Weiterleitung gerade einrichtet/testet, nicht ein Endkunde mit einem echten
Anliegen. Kein Fehlerbericht, keine Funktionsbeschreibung, kein Reproduktionsschritt vorhanden —
es gibt nichts, was auf einen App-Fehler hindeutet.

**Eingrenzung:** — (kein App-Fehler beschrieben; nichts zu reproduzieren).

**Dringlichkeit:** Niedrig
Kein Kernfunktions-, Daten- oder DSGVO-Bezug; niemand ist blockiert; Inhalt und Kontext (gleicher
Absender wie das vorherige Setup-/Einladungs-Ticket) sprechen eindeutig für einen bewussten
Testlauf des Ticket-Systems, keine echte Kundenanfrage.

**Antwortentwurf an den Kunden:**
> Vielen Dank für Ihre Nachricht. Dieses Ticket enthält offenbar nur einen Testinhalt ("Test
> Ticket") ohne konkretes Anliegen. Falls Sie tatsächlich ein Problem melden wollten, antworten
> Sie bitte auf dieses Ticket mit einer kurzen Beschreibung, was genau nicht wie erwartet
> funktioniert hat — dann können wir uns umgehend darum kümmern. Andernfalls können wir dieses
> Ticket schließen.

**Rückfragen-Guidance:** Sollte dies tatsächlich (versehentlich) ein echtes Anliegen gewesen
sein, fehlen: eine Beschreibung des eigentlichen Problems, wann/wo es aufgetreten ist, und welches
Ergebnis erwartet wurde. Aktuell deutet aber nichts im Ticket auf ein echtes Anliegen hin —
vermutlich reines Testereignis analog zu den bereits erfassten Weiterleitungs-Tests.
