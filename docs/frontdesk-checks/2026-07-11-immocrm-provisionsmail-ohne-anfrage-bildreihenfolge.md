# Frontdesk-Triage — 2026-07-11

Quelle: Peppermint-Ticket-Notification (Auxevo Support / Freshdesk-Weiterleitung, Ticket #127)
Hinweis: Interne Ersteinschätzung, kein QA-Ergebnis.

## Übersicht

| Ticket | Kurzbefund | Dringlichkeit |
|---|---|---|
| Peppermint 3716edf6 (Freshdesk #127) — "IMMO CRM, unvollständige Anfrage" | Übergreifendes Problem (zwei getrennte, strukturelle Befunde) | Mittel |

---

### Ticket: Peppermint-Ticket "IMMO CRM, unvollständige Anfrage" (Peppermint 3716edf6-64fa-4f0e-aab7-3ec85e15ecca, Freshdesk #127, Absenderin: Beata Rutkowska / Erol Immobilien GmbH, zugewiesen an "Pepper Mint")

**Kurzbefund:** Übergreifendes Problem. Das Ticket vermischt zwei getrennte Beobachtungen zu
einem neu angelegten Objekt (Schuberstr. 32):

1. Vom Kunden Johannes Prüßen ist eine E-Mail eingegangen, in der nur die Provisionserklärung
   bestätigt wird — eine zugehörige Anfrage ist weder in IMMO CRM noch bei ImmoScout24 auffindbar.
2. Beim Öffnen des Exposés über den Link aus der Provisions-Mail erscheint zuerst ein
   Werbe-/Agentenbild (Firat) statt der Objektfotos in korrekter Reihenfolge; bei ImmoScout24 ist
   die Reihenfolge korrekt.

**Eingrenzung:** Backend (immo-crm) · Module: Exposé-Provisionsbestätigung / OpenImmo-Bildimport.

Code-Grep-Befund (immo-crm-Repo, rein lesend geprüft, kein Reproduktions-Login mit echten
Kundendaten):
- **Zu 1)**: Die Provisions-Bestätigung läuft über den öffentlichen Endpoint
  `POST /{slug}/expose/{token}/provision` (`backend/app/routes/expose.py:1340`,
  `_send_provision_confirmation` bei `:430`). Dieser Endpoint ist architektonisch **komplett
  vom eigentlichen Anfrage-Flow entkoppelt**: er schreibt nur einen Eintrag in `expose_consents`
  (`:1426`) und verknüpft optional einen *bereits existierenden* Kunden per E-Mail-Abgleich
  (`:1419-1424`) — er legt aber nie einen Kunden, eine Konversation oder eine Nachricht an, so
  wie es der echte Anfrage-Flow `_handle_expose_inquiry` (`:538`) tut. Das erklärt technisch
  präzise, warum Beata weder in IMMO CRM noch bei ImmoScout24 etwas findet: Der Kunde hat
  offenbar nur den Provisions-Consent-Schritt auf der Exposé-Seite bestätigt (nötig, um
  Dokumente/Fotos freizuschalten), aber nie eine tatsächliche Anfrage abgeschickt — vermutlich,
  weil die beiden Schritte in der Oberfläche nicht klar als getrennt erkennbar sind. Die aus einem
  früheren Check bekannte Phase-24-05-Autoset-Logik (`email_service.py:3727-3761`, automatisches
  Setzen von `provision_consent='Ja'` für ImmoScout24-Absenderdomains) ist hier **nicht** die
  Ursache — sie verschickt keine E-Mail und betrifft nur IS24-Portal-Mails.
- **Zu 2)**: Agentenfotos werden separat geladen (`expose.py:776-801`) und nur in der dedizierten
  Makler-Karte gerendert (`expose.html:804-821`), nicht in der Bildergalerie selbst. Die
  eigentliche Ursache liegt im OpenImmo-Import: `import_export.py:1386-1424` setzt
  `sort_order`/`is_main_image` rein nach Reihenfolge der XML-Anhänge; `openimmo_parser.py:333-358`
  extrahiert jeden Bild-Anhang, wertet aber **das `gruppe`-Attribut nicht aus** (kein Treffer für
  "gruppe" im Parser). Ein Makler-/Werbebild, das im Feed vor den eigentlichen Objektfotos steht,
  wird dadurch fälschlich zum Hauptbild — passend zu "bei IS24 korrekt, im CRM falsch" und dazu,
  dass es ein gerade erst (5 Minuten zuvor) importiertes Objekt betrifft.

Beide Befunde sind strukturell (jeder OpenImmo-Import bzw. jeder Kunde, der nur den
Consent-Schritt abschließt, wäre betroffen) — daher "Übergreifendes Problem", nicht Einzelfall.

**Dringlichkeit:** Mittel
Begründung: Kein Datenverlust, keine akute DSGVO-Verletzung, kein blockierter Kunde/Mitarbeiter —
beide Mechanismen sind aber reproduzierbar für jedes vergleichbare Objekt bzw. jeden Kunden, der
den gleichen Teil-Flow durchläuft. Punkt 2 ist zudem nach außen sichtbar (falsches Werbebild statt
Objektfoto im Kunden-Exposé) und wirkt unprofessionell; Punkt 1 erzeugt wiederkehrende
Verwirrung/Mehraufwand beim Team, weil eine bestätigte Provisionserklärung ohne zuordenbare
Anfrage im System "hängt".

**Antwortentwurf an den Kunden:**
> Hallo Frau Rutkowska,
>
> vielen Dank für die Meldung. Wir konnten beides technisch nachvollziehen:
>
> 1. Die Bestätigung der Provisionserklärung ist im System bewusst ein eigener Schritt, der von
>    der eigentlichen Anfrage getrennt läuft — Herr Prüßen hat offenbar nur diesen Bestätigungs-
>    Schritt abgeschlossen, aber keine separate Anfrage abgeschickt. Deshalb ist dazu weder in
>    IMMO CRM noch bei ImmoScout24 ein Datensatz zu finden. Wir prüfen, wie wir diese beiden
>    Schritte für Kunden klarer erkennbar machen können.
> 2. Das falsch einsortierte Bild beim Öffnen des Exposés ist ein Anzeigefehler beim Bildimport
>    neu angelegter Objekte, den wir uns genauer ansehen.
>
> Wir melden uns, sobald wir mehr wissen.

**Rückfragen-Guidance:** Keine notwendig für die Ersteinschätzung — Code-Analyse liefert für beide
Beobachtungen eine plausible, strukturelle Erklärung. Für die Weiterbearbeitung wäre hilfreich:
der genaue Zeitstempel/Wortlaut der Kunden-Mail (bestätigt sie tatsächlich nur den Provisions-Text,
oder enthält sie doch eine Anfrage, die nur nicht ins CRM übernommen wurde?) sowie ein Screenshot
des fehlerhaft sortierten Exposés zur Bestätigung des Bildimport-Befunds.

---

Nächster Schritt bei Bedarf: Für Punkt 1 den Anfrage-/Consent-Flow via `/abc-requirements` im
`immo-crm`-Projekt schärfen (z. B. Hinweis/Pflichtfeld, dass nach Provisions-Bestätigung noch eine
Anfrage folgen muss). Für Punkt 2 den OpenImmo-Parser (`openimmo_parser.py`) um Auswertung des
`gruppe`-Attributs ergänzen, um Makler-/Werbebilder aus der Objekt-Bildergalerie auszuschließen —
Backend-Developer-Ticket, kein akuter Hotfix.
