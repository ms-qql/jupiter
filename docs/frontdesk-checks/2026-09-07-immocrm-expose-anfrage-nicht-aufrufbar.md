# Frontdesk-Check — 2026-09-07 — Exposé-Anfrage lässt sich nicht öffnen / Nachricht nicht in Kommunikation auffindbar

**Quelle:** Peppermint-Ticket 39c492c0-4436-4989-a12c-d113be693a84 (Freshdesk #161), weitergeleitet
über Auxevo Support. Ursprungsmail: Firat Erol / Erol Immobilien GmbH (`crm.erol.msce.info`), am
06.09.2026 an Manfred. Betreff „WG: CRM Programm Exposé Herunterladen".
Interne Ersteinschätzung, **kein QA-Ergebnis**.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Exposé-Anfrage von Dierk Borstel: Klick zeigt Fehlermeldung, Nachricht nicht in Kommunikation auffindbar | Übergreifendes Problem | Hoch |

---

### Ticket: Anfrage des Interessenten Dierk Borstel („Exposé herunterladen") — Klick auf die Anfrage wirft eine Fehlermeldung, und unter „Kommunikation" ist die Nachricht nicht auffindbar

**Kernfakten aus dem Ticket:**
- Melder: Firat Erol (Erol Immobilien) für sein Team, weitergeleitet an Auxevo/Manfred.
- Betroffener Interessent: **Dierk Borstel**. Kein Datensatz-/Kunden-ID, kein Objekt, kein
  Zeitstempel im Ticket.
- Zwei Beobachtungen (zusammenhängend, daher in einem Report):
  1. Eine eingegangene **Anfrage** (laut Betreff Exposé-/Download-bezogen) wird im CRM angezeigt;
     ein Klick darauf zeigt „eine Fehlermeldung" (Wortlaut nicht mitgeliefert).
  2. Beim Versuch, dieselbe Nachricht unter **Kommunikation** zu öffnen, ist sie „nicht
     auffindbar".
- Screenshot ist am Ticket angehängt (`Screenshot 2026-09-06 142035.png`), lag dieser Analyse
  **nicht** vor (Freshdesk-Attachment, nicht abrufbar).
- Melder hat selbst schon einen zweiten Weg (über Kommunikation) probiert — erfolglos.

**Kurzbefund:** Übergreifendes Problem.
Die auslösende Vorbedingung — „ein Interessent stellt über das Web-Exposé eine Exposé-Anfrage" — ist
der Normalfall dieser Funktion, kein anomaler Einzeldatensatz. `_handle_expose_inquiry`
(`backend/app/routes/expose.py:603`) legt bei **jeder** solchen Anfrage automatisch Kontakt +
Objekt-Verknüpfung + Conversation + Inbound-Message (`metadata.expose_inquiry = true`, kein
E-Mail-Konto) + PROJ-64-Anfrage-Ereignis an. Wenn das Aufrufen/Anzeigen dieser automatisch
erzeugten Nachricht bricht, trifft das jede Exposé-Anfrage gleichermaßen — auch wenn bisher nur ein
Ticket vorliegt.

**Eingrenzung (mutmaßlicher App-Fehler):** Schicht: **Frontend** (Navigation/Listendarstellung),
Backend als Zweitverdacht · Modul: **Kommunikation / Anfragen** (Web-Exposé-Anfrage →
Nachricht/Verlauf-Navigation).
Stütze der Eingrenzung (nur Code-Analyse, nicht live nachgestellt — kein Zugriff auf echte
Kundendaten ohne Freigabe):
- Beide Symptome sind Anzeige-/Navigationsverhalten: „Klick wirft Fehlermeldung" (defekter
  Deep-Link/Route auf eine Message-/Conversation-ID) und „in der Liste nicht auffindbar"
  (Filter-/Sichtbarkeits-Mismatch), nicht Datenverlust.
- Die von `_handle_expose_inquiry` erzeugte Conversation hat **kein** `email_account_id` und die
  Message `sender_type = "client"` / `direction = "inbound"` mit `metadata.expose_inquiry`. Der
  seit PROJ-73/74 read-only „Kommunikation"-Screen ist auf den E-Mail-Stil-Verlauf ausgelegt
  (PROJ-61) — eine konto-lose Auto-Conversation kann dort durch einen Filter fallen → „nicht
  auffindbar".
- Passt in die bereits getrackten Bug-Cluster **PROJ-41 „Mail↔Kunde-Matching & Verlauf-Navigation"**
  und **PROJ-38 „E-Mail-Verlauf — Anzeige & Cross-User-Sichtbarkeit"** (On Hold) sowie in die
  PROJ-114-Fix-Iteration zur Cross-User-Sichtbarkeit. Verwandt, aber nicht identisch:
  PROJ-100/132 (Provisions-Consent bzw. Auto-Anlage Interessent aus Exposé-Anfrage).
- Nicht der wahrscheinlichste, aber zu prüfen: PROJ-102/103 (200-Nachrichten-Deckel im
  Kundenverlauf) — hier unwahrscheinlich, da es um eine ganz frische Nachricht geht.

**Dringlichkeit:** Hoch.
- Kernfunktion betroffen: eingehende Interessenten-Anfragen + Kommunikationsverlauf.
- Vermutlich übergreifend (Mechanismus greift bei jeder Web-Exposé-Anfrage), nicht Einzelfall.
- Lead-/Geschäftsrisiko: Die Anfrage eines Kaufinteressenten (inkl. dessen Kontaktdaten und
  Anliegen) ist faktisch nicht einsehbar — potenziell verlorener Lead.
- Kein bestätigter Datenverlust (Nachricht liegt vermutlich in der DB, nur nicht erreichbar) und
  Makler nicht hart blockiert (die automatische Antwortmail an den Interessenten geht laut Code
  unabhängig raus) → daher Hoch, nicht Dringend.

**Antwortentwurf an den Kunden:**
> Hallo Herr Erol,
>
> vielen Dank für Ihre Meldung. Wir prüfen aktuell, warum sich die Exposé-Anfrage von Herrn Borstel
> nicht öffnen lässt und die zugehörige Nachricht im Bereich „Kommunikation" nicht auftaucht.
> Damit wir das gezielt nachstellen können, wären folgende Angaben hilfreich: um welche Immobilie
> ging es, wann kam die Anfrage ungefähr herein, und an welcher Stelle im CRM haben Sie die Anfrage
> angeklickt (z. B. Startseite/Dashboard, Benachrichtigung, Kundendetail)? Der genaue Wortlaut der
> Fehlermeldung bzw. ein Screenshot davon hilft uns zusätzlich. Wir melden uns, sobald wir die
> Ursache eingegrenzt haben.
>
> Freundliche Grüße
> Ihr Support-Team

**Rückfragen-Guidance:** Für dieses Ticket fehlten konkret:
- **Wo** die Anfrage angeklickt wurde (Dashboard-Widget „neue Anfragen" / Glocken-Benachrichtigung
  / Kundendetail / E-Mail-Link) und die **exakte Fehlermeldung** (Text/Screenshot) — unterscheidet
  defekten Deep-Link von Render-Fehler.
- **Objekt** und **ungefährer Zeitpunkt** der Anfrage sowie die interne **Kunden-/Datensatz-ID**
  von Dierk Borstel (nicht nur der Name).
- Ob unter dem Interessenten überhaupt ein **Kontakt angelegt** wurde und ob die **automatische
  Antwortmail** beim Interessenten ankam (zeigt, wie weit `_handle_expose_inquiry` durchlief).
- Welcher Screen mit „Kommunikation" gemeint ist (neuer read-only Live-Screen vs. alter
  Kundenverlauf im Kundendetail).
- Verwendeter **Browser/Client** und ob mit einer frischen Test-Anfrage **reproduzierbar**.

**Hinweis:** Reproduktion nur per Code-Analyse geprüft, nicht live nachgestellt. Wenn die
Rückfragen einen bestätigten Navigations-/Sichtbarkeits-Bug ergeben, ist der nächste Schritt ein
gezielter `/abc-qa`-Lauf im `immo-crm`-Projekt (Web-Exposé-Anfrage stellen → erwartet: Anfrage
anklickbar + Nachricht im Kommunikationsverlauf sichtbar), mit Bezug zu PROJ-38/41/114.
